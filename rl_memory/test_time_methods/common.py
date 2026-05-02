from __future__ import annotations

import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit
from urllib.request import urlopen


UNSUPPORTED_SELECTOR_TOKENS = (
    ":contains(",
    ":has-parent(",
    "xpath=",
    "//",
)
XPATH_LIKE_SELECTOR_TOKENS = (
    "../",
    "./",
    "preceding-sibling::",
    "following-sibling::",
    "ancestor::",
    "descendant::",
    "parent::",
    "child::",
    "contains(",
    "normalize-space(",
    "starts-with(",
    "text()",
    "@class",
    "@id",
    "[@",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SELECT_LIKE_SELECTOR_HINTS = (
    "month",
    "frequency",
    "mode",
    "rule",
    "term",
    "type",
    "payee",
    "provider",
    "category",
    "plan",
    "status",
)
TEXT_LIKE_SELECTOR_HINTS = (
    "name",
    "title",
    "query",
    "password",
    "username",
    "account",
    "code",
    "date",
    "time",
    "amount",
    "price",
    "origin",
    "destination",
    "fullname",
    "student",
    "description",
    "reason",
    "number",
    "pickup",
)
CLICK_LIKE_SELECTOR_HINTS = (
    "btn",
    "button",
    "confirm",
    "submit",
    "apply",
    "book",
    "search",
    "open",
    "enroll",
    "list",
    "card",
    "item",
)
PLACEHOLDER_VALUE_HINTS = (
    "YOUR_",
    "CHECK_SOURCE",
    "CORRECT_CODE",
    "VERIFICATION_CODE",
    "FILL_IN",
)


def _sqlite_backup(source: Path, destination: Path, retries: int = 20, sleep_sec: float = 0.1) -> None:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for _ in range(max(1, retries)):
        src = None
        dst = None
        try:
            src = sqlite3.connect(str(source), timeout=30)
            dst = sqlite3.connect(str(destination), timeout=30)
            dst.execute("PRAGMA busy_timeout=30000")
            src.backup(dst)
            dst.commit()
            return
        except sqlite3.OperationalError as exc:
            last_exc = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(sleep_sec)
        finally:
            if src is not None:
                src.close()
            if dst is not None:
                dst.close()
    if last_exc is not None:
        raise last_exc


def sample_candidate_actions(
    client: Any,
    goal: str,
    page_content: str,
    history: list[Any],
    num_samples: int,
    temperature: float,
) -> list[str]:
    if hasattr(client, "sample_actions"):
        outputs = client.sample_actions(
            goal,
            page_content,
            history,
            num_samples=max(1, int(num_samples)),
            temperature=temperature,
        )
        return [str(x or "") for x in outputs]
    return [str(client.get_action(goal, page_content, history) or "") for _ in range(max(1, int(num_samples)))]


def _extract_selector_and_value(action: str) -> tuple[str, str]:
    raw = str(action or "").strip()
    m = re.match(r"(?is)^\s*(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\((.*)\)\s*$", raw)
    if not m:
        return "", ""
    body = m.group(2).strip()
    if m.group(1).upper() in {"DONE", "WAIT"}:
        return "", ""
    if m.group(1).upper() == "GOTO":
        return body.strip().strip('"').strip("'"), ""
    if "," not in body:
        return body.strip().strip('"').strip("'"), ""
    lhs, rhs = body.split(",", 1)
    return lhs.strip().strip('"').strip("'"), rhs.strip().strip('"').strip("'")


def _count_action_commands(raw: str) -> int:
    return len(list(re.finditer(r"(?i)\b(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\s*\(", raw or "")))


def _selector_element_tag(selector: str, observation: str) -> str:
    tag, _ = _selector_element_info(selector, observation)
    return tag


def _selector_element_info(selector: str, observation: str) -> tuple[str, str]:
    sel = str(selector or "").strip()
    obs = str(observation or "")
    if not sel or not obs:
        return "", ""

    patterns: list[str] = []
    id_tokens = re.findall(r"#([A-Za-z0-9_-]+)", sel)
    class_tokens = re.findall(r"\.([A-Za-z0-9_-]+)", sel)

    for token in id_tokens:
        elem_id = re.escape(token)
        patterns.append(rf"<([a-z0-9]+)\b[^>]*\bid=[\"']{elem_id}[\"'][^>]*>")
    for token in class_tokens:
        klass = re.escape(token)
        patterns.append(
            rf"<([a-z0-9]+)\b[^>]*\bclass=[\"'][^\"']*(?:^|\s){klass}(?:\s|$)[^\"']*[\"'][^>]*>"
        )

    for pattern in patterns:
        match = re.search(pattern, obs, re.IGNORECASE)
        if not match:
            continue
        tag = match.group(1).lower()
        element_markup = match.group(0)
        input_type = ""
        if tag == "input":
            type_match = re.search(r'\btype=["\']([^"\']+)["\']', element_markup, re.IGNORECASE)
            if type_match:
                input_type = type_match.group(1).lower()
        return tag, input_type

    return "", ""


def _selector_hint_flags(selector: str) -> tuple[bool, bool, bool]:
    sel = str(selector or "").lower()
    is_select_like = any(token in sel for token in SELECT_LIKE_SELECTOR_HINTS)
    is_text_like = any(token in sel for token in TEXT_LIKE_SELECTOR_HINTS)
    is_click_like = any(token in sel for token in CLICK_LIKE_SELECTOR_HINTS)
    return is_select_like, is_text_like, is_click_like


def _selector_grounding_notes(selector: str, observation: str) -> list[str]:
    sel = str(selector or "").strip()
    obs = str(observation or "")
    if not sel or not obs:
        return []

    notes: list[str] = []
    bare_token = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", sel)
    if bare_token:
        notes.append("ungrounded_bare_selector")
        return notes

    id_tokens = re.findall(r"#([A-Za-z0-9_-]+)", sel)
    class_tokens = re.findall(r"\.([A-Za-z0-9_-]+)", sel)
    grounded = False
    for token in id_tokens:
        if re.search(rf'\bid=["\']{re.escape(token)}["\']', obs, re.IGNORECASE) or f"#{token}" in obs:
            grounded = True
            break
    if not grounded:
        for token in class_tokens:
            if re.search(rf'\bclass=["\'][^"\']*{re.escape(token)}', obs, re.IGNORECASE) or f".{token}" in obs:
                grounded = True
                break

    if id_tokens and not grounded:
        notes.append("ungrounded_id_selector")
    if class_tokens and not grounded:
        notes.append("ungrounded_class_selector")
    if any(ch in sel for ch in (" ", ">")) and not grounded:
        notes.append("ungrounded_complex_selector")
    return notes


def _has_malformed_bracket_text(selector: str) -> bool:
    for inner in re.findall(r"\[([^\]]+)\]", str(selector or "")):
        stripped = inner.strip()
        if not stripped:
            return True
        has_assignment = any(op in stripped for op in ("=", "^=", "$=", "*=", "~=", "|="))
        if any(token in stripped for token in (">", "+")) and not has_assignment:
            return True
    return False


def _selector_format_notes(selector: str) -> list[str]:
    sel = str(selector or "").strip()
    lowered = sel.lower()
    notes: list[str] = []
    if not sel:
        return notes
    if any(token in lowered for token in XPATH_LIKE_SELECTOR_TOKENS):
        notes.append("xpath_selector_token")
    if re.fullmatch(r"[+>~]", sel):
        notes.append("malformed_selector_literal")
    if _has_malformed_bracket_text(sel):
        notes.append("malformed_selector_bracket_text")
    return notes


def _selector_role_from_action(
    cmd: str,
    selector: str,
    observation: str,
    current_url: str = "",
) -> str:
    act = str(cmd or "").strip().lower()
    sel = str(selector or "").strip().lower()
    url = str(current_url or "").strip().lower()
    tag, _input_type = _selector_element_info(selector, observation)

    if act == "goto":
        if any(tok in sel for tok in ("detail", "thread=", "property.html", "book=", "course=")):
            return "detail_navigation"
        return "page_entry"
    if act == "wait":
        return "success_signal"
    if act == "click":
        if any(tok in sel for tok in ("rules-check", "checkbox", "agree", "accept", "terms")):
            return "ack_control"
        if any(tok in sel for tok in ("open-", "upload-", "add-", "apply-", "create-", "new-", "join-", "enroll-")):
            return "open_form_trigger"
        if any(
            tok in sel
            for tok in (
                "modal-confirm",
                "submit",
                "confirm",
                "save",
                "setup",
                "book",
                "request",
                "send",
                "apply-btn",
                "join-modal",
            )
        ):
            return "submit_button"
        if ".btn.pri" in sel or "button.btn.pri" in sel:
            return "submit_button"
        if any(tok in sel for tok in ("card", "list", "item", "result", "email", "property", "group")):
            return "list_item"
        if tag == "button":
            return "click_target"
        return "click_target"
    if act == "select":
        if any(tok in sel for tok in ("sort", "order")):
            return "sort_control"
        if any(tok in sel for tok in ("doc", "document", "proof", "permit-type", "event-type", "new-type")):
            return "typed_selection"
        if tag == "select":
            return "selection_control"
        return "selection_control"
    if act == "type":
        if any(tok in sel for tok in ("msg", "message", "chat")):
            return "message_input"
        if any(tok in sel for tok in ("file", "proof", "upload")):
            return "file_field"
        if any(tok in sel for tok in ("date", "time", "slot")):
            return "date_time_field"
        if any(
            tok in sel
            for tok in ("amount", "price", "value", "rent", "spend", "cap", "count", "duration", "quantity")
        ):
            return "numeric_field"
        if tag in {"input", "textarea"}:
            return "text_field"
        return "text_field"
    if act == "done" and any(tok in url for tok in ("success", "confirmed", "submitted")):
        return "success_signal"
    return f"{act}_target" if act else "unknown"


def _indicator_matches_observation(indicator: str, observation: str) -> bool:
    raw = str(indicator or "").strip()
    obs = str(observation or "")
    if not raw or not obs:
        return False

    raw_lower = raw.lower()
    obs_lower = obs.lower()
    if raw_lower in obs_lower:
        return True

    text_phrases = re.findall(r":has-text\((['\"])(.*?)\1\)", raw, re.IGNORECASE)
    for _, phrase in text_phrases:
        if str(phrase or "").strip().lower() in obs_lower:
            return True

    id_tokens = re.findall(r"#([A-Za-z0-9_-]+)", raw)
    class_tokens = re.findall(r"\.([A-Za-z0-9_-]+)", raw)

    def _id_visible(token: str) -> bool:
        escaped = re.escape(token)
        return bool(re.search(rf'\bid=["\']{escaped}["\']', obs, re.IGNORECASE) or f"#{token.lower()}" in obs_lower)

    def _class_visible(token: str) -> bool:
        escaped = re.escape(token)
        return bool(
            re.search(rf'\bclass=["\'][^"\']*(?:^|\s){escaped}(?:\s|$)[^"\']*["\']', obs, re.IGNORECASE)
            or f".{token.lower()}" in obs_lower
        )

    if id_tokens or class_tokens:
        ids_ok = not id_tokens or any(_id_visible(token) for token in id_tokens)
        classes_ok = not class_tokens or all(_class_visible(token) for token in class_tokens)
        if ids_ok and classes_ok:
            return True

    return False


def _skill_action_key(cmd: str, selector_role: str) -> str:
    action_type = str(cmd or "").strip().upper()
    role = str(selector_role or "").strip()
    if not action_type:
        return ""
    return f"{action_type}:{role or 'unknown'}"


def _score_skill_context_bias(
    *,
    action: str,
    cmd: str,
    selector: str,
    observation: str,
    last_action: str | None,
    current_url: str,
    skill_context: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    ctx = dict(skill_context or {})
    if not ctx:
        return 0.0, []

    notes: list[str] = []
    score = 0.0

    preferred_action_types = {
        str(item or "").strip().upper()
        for item in (ctx.get("preferred_action_types") or [])
        if str(item or "").strip()
    }
    selector_roles = {
        str(item or "").strip()
        for item in (ctx.get("selector_roles") or [])
        if str(item or "").strip()
    }
    success_indicators = [
        str(item or "").strip()
        for item in (ctx.get("success_indicators") or [])
        if str(item or "").strip()
    ]
    action_sequences = [
        [str(step or "").strip() for step in sequence if str(step or "").strip()]
        for sequence in (ctx.get("action_sequences") or [])
        if isinstance(sequence, (list, tuple))
    ]
    failure_modes = {
        str(item or "").strip()
        for item in (ctx.get("failure_modes") or [])
        if str(item or "").strip()
    }

    selector_role = _selector_role_from_action(cmd, selector, observation, current_url=current_url)
    candidate_key = _skill_action_key(cmd, selector_role)
    if cmd in preferred_action_types:
        score += 1.0
        notes.append("skill_action_type_match")
    if selector_role and selector_role in selector_roles:
        score += 1.2
        notes.append("skill_selector_role_match")

    indicator_visible = any(_indicator_matches_observation(indicator, observation) for indicator in success_indicators)
    if cmd == "DONE":
        if success_indicators:
            if indicator_visible:
                score += 2.0
                notes.append("skill_success_indicator_visible")
            else:
                score -= 3.5
                notes.append("skill_stop_rule")
        if "premature_done" in failure_modes and not indicator_visible:
            score -= 1.0
            notes.append("skill_failure_mode_guard")
        return score, notes

    last_raw = str(last_action or "").strip()
    if "repeat_action_loop" in failure_modes and last_raw and str(action or "").strip() == last_raw:
        score -= 1.0
        notes.append("skill_repeat_loop_guard")

    last_key = ""
    if last_raw:
        last_match = re.match(r"(?is)^\s*(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\((.*)\)\s*$", last_raw)
        if last_match:
            last_cmd = last_match.group(1).upper()
            last_selector, _ = _extract_selector_and_value(last_raw)
            last_role = _selector_role_from_action(last_cmd, last_selector, observation, current_url=current_url)
            last_key = _skill_action_key(last_cmd, last_role)

    if candidate_key and action_sequences:
        if not last_key:
            if any(sequence and candidate_key == sequence[0] for sequence in action_sequences):
                score += 0.6
                notes.append("skill_sequence_start_match")
        else:
            matched_transition = False
            stalled_transition = False
            for sequence in action_sequences:
                for idx, step in enumerate(sequence):
                    if step != last_key:
                        continue
                    if idx + 1 < len(sequence):
                        expected = sequence[idx + 1]
                        if candidate_key == expected:
                            matched_transition = True
                        elif candidate_key == last_key and expected != last_key:
                            stalled_transition = True
            if matched_transition:
                score += 1.4
                notes.append("skill_sequence_match")
            elif stalled_transition:
                score -= 0.8
                notes.append("skill_sequence_stall")

    if cmd == "CLICK" and selector_role == "submit_button" and last_raw:
        last_match = re.match(r"(?is)^\s*(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\((.*)\)\s*$", last_raw)
        if last_match:
            last_cmd = last_match.group(1).upper()
            last_selector, _ = _extract_selector_and_value(last_raw)
            last_role = _selector_role_from_action(last_cmd, last_selector, observation, current_url=current_url)
            if last_role == "message_input":
                score += 1.2
                notes.append("skill_message_submit_transition")
            elif last_cmd in {"TYPE", "SELECT"} and last_role in {
                "text_field",
                "numeric_field",
                "date_time_field",
                "selection_control",
                "typed_selection",
            }:
                score += 0.9
                notes.append("skill_submit_transition")
            elif selector_roles & {
                "message_input",
                "text_field",
                "numeric_field",
                "date_time_field",
                "selection_control",
                "typed_selection",
            } and any(token in observation.lower() for token in ("<input", "<select", "<textarea")):
                score -= 0.8
                notes.append("skill_submit_without_recent_fill")

    return score, notes


def score_action_heuristics(
    action: str,
    observation: str,
    last_action: str | None,
    current_url: str,
    base_url: str,
    skill_context: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    raw = str(action or "").strip()
    obs = str(observation or "")
    notes: list[str] = []
    score = 0.0

    if not raw:
        return -8.0, ["empty_action"]
    if _count_action_commands(raw) > 1:
        return -8.0, ["multi_action_output"]

    m = re.match(r"(?is)^\s*(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\((.*)\)\s*$", raw)
    if not m:
        return -8.0, ["unknown_action_format"]

    cmd = m.group(1).upper()
    selector_or_url, value = _extract_selector_and_value(raw)
    selector_tag, selector_input_type = _selector_element_info(selector_or_url, obs)
    select_like_hint, text_like_hint, click_like_hint = _selector_hint_flags(selector_or_url)
    grounding_notes = _selector_grounding_notes(selector_or_url, obs)
    selector_format_notes = _selector_format_notes(selector_or_url)

    if raw == (last_action or "").strip():
        score -= 5.0
        notes.append("repeat_action")
    elif last_action:
        last_match = re.match(r"(?is)^\s*(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\((.*)\)\s*$", str(last_action).strip())
        if last_match:
            last_cmd = last_match.group(1).upper()
            last_selector, _ = _extract_selector_and_value(str(last_action))
            if selector_or_url and last_selector == selector_or_url and cmd == last_cmd and cmd in {"TYPE", "SELECT"}:
                score -= 2.5
                notes.append("repeat_same_field")

    if cmd == "DONE":
        success_cues = ("success", "confirmed", "completed", "submitted", "active", "booked", "scheduled")
        if not any(cue in obs.lower() for cue in success_cues):
            score -= 3.5
            notes.append("premature_done_risk")
        else:
            score += 2.0
            notes.append("done_with_success_cue")
        skill_score, skill_notes = _score_skill_context_bias(
            action=raw,
            cmd=cmd,
            selector=selector_or_url,
            observation=obs,
            last_action=last_action,
            current_url=current_url,
            skill_context=skill_context,
        )
        score += skill_score
        notes.extend(skill_notes)
        return score, notes

    if cmd == "WAIT":
        if any(token in obs.lower() for token in ("loading", "processing", "please wait")):
            score += 0.5
        else:
            score -= 1.0
            notes.append("idle_wait")
        skill_score, skill_notes = _score_skill_context_bias(
            action=raw,
            cmd=cmd,
            selector=selector_or_url,
            observation=obs,
            last_action=last_action,
            current_url=current_url,
            skill_context=skill_context,
        )
        score += skill_score
        notes.extend(skill_notes)
        return score, notes

    if cmd == "GOTO":
        target = selector_or_url
        if not re.match(r"^https?://", target, re.IGNORECASE):
            return -8.0, ["goto_requires_url"]
        target_host = urlsplit(target).netloc
        base_host = urlsplit(base_url).netloc
        if target_host != base_host:
            score -= 6.0
            notes.append("external_navigation")
        else:
            score -= 2.5
            notes.append("local_navigation_shortcut_risk")
        skill_score, skill_notes = _score_skill_context_bias(
            action=raw,
            cmd=cmd,
            selector=selector_or_url,
            observation=obs,
            last_action=last_action,
            current_url=current_url,
            skill_context=skill_context,
        )
        score += skill_score
        notes.extend(skill_notes)
        return score, notes

    lowered_selector = selector_or_url.lower()
    if any(tok in lowered_selector for tok in UNSUPPORTED_SELECTOR_TOKENS):
        score -= 4.0
        notes.append("unsupported_selector_token")
    if selector_format_notes:
        notes.extend(selector_format_notes)
        if "xpath_selector_token" in selector_format_notes:
            score -= 6.0
        if any(note.startswith("malformed_selector_") for note in selector_format_notes):
            score -= 6.0
    if grounding_notes:
        notes.extend(grounding_notes)
        if "ungrounded_bare_selector" in grounding_notes:
            score -= 6.0
        elif "ungrounded_complex_selector" in grounding_notes:
            score -= 4.0
        else:
            score -= 3.5
    if cmd == "CLICK" and re.search(r"\bbutton\s+\.", selector_or_url):
        score -= 3.0
        notes.append("suspicious_selector_pattern")

    if cmd in {"TYPE", "SELECT"}:
        upper_value = str(value or "").upper()
        if any(token in upper_value for token in PLACEHOLDER_VALUE_HINTS):
            score -= 6.0
            notes.append("placeholder_value")
        if cmd == "SELECT" and str(value or "").strip().lower() == "information":
            score -= 4.0
            notes.append("generic_option_value")

    if cmd == "SELECT":
        if selector_tag == "input" and selector_input_type in {"checkbox", "radio"}:
            score -= 6.0
            notes.append("select_on_checkable_input")
        elif selector_tag and selector_tag != "select":
            score -= 6.0
            notes.append("select_without_select_element")
        elif not selector_tag and text_like_hint and not select_like_hint:
            score -= 5.0
            notes.append("select_on_text_like_field")
        elif not selector_tag and click_like_hint and not select_like_hint:
            score -= 5.0
            notes.append("select_on_click_like_target")
        elif "<select" in obs.lower():
            score += 1.5
            if value:
                value_lower = value.lower()
                obs_lower = obs.lower()
                if value_lower not in obs_lower:
                    score -= 4.0
                    notes.append("select_option_not_visible")
        else:
            score -= 2.5
            notes.append("select_without_select_element")
    elif cmd == "TYPE":
        if selector_tag == "input" and selector_input_type in {"checkbox", "radio"}:
            score -= 6.0
            notes.append("type_on_checkable_input")
        elif selector_tag and selector_tag not in {"input", "textarea"}:
            score -= 6.0
            notes.append("type_without_input")
        elif not selector_tag and select_like_hint and "<select" in obs.lower():
            score -= 5.0
            notes.append("type_on_select_like_field")
        elif not selector_tag and click_like_hint and not text_like_hint:
            score -= 4.0
            notes.append("type_on_click_like_target")
        elif "<input" in obs.lower() or "<textarea" in obs.lower():
            score += 1.2
        else:
            score -= 2.0
            notes.append("type_without_input")
    elif cmd == "CLICK":
        score += 0.8

    if selector_or_url and selector_or_url in obs:
        score += 1.0
        notes.append("selector_visible")
    elif value and value in obs:
        score += 0.6
        notes.append("value_visible")
    else:
        text_match = re.search(r"['\"]([^'\"]+)['\"]", raw)
        if text_match and text_match.group(1) in obs:
            score += 0.8
            notes.append("text_visible")

    if any(token in obs.lower() for token in ("modal", "popup", "cookie", "offer", "notice")) and cmd not in {"CLICK", "WAIT"}:
        score -= 1.5
        notes.append("overlay_risk")

    skill_score, skill_notes = _score_skill_context_bias(
        action=raw,
        cmd=cmd,
        selector=selector_or_url,
        observation=obs,
        last_action=last_action,
        current_url=current_url,
        skill_context=skill_context,
    )
    score += skill_score
    notes.extend(skill_notes)

    return score, notes


class TaskRuntimeSnapshot:
    def __init__(self, source_root: Path, db_snapshot: Path, state_bytes: bytes | None):
        self.source_root = source_root
        self.db_snapshot = db_snapshot
        self.state_bytes = state_bytes

    @classmethod
    def capture(cls) -> "TaskRuntimeSnapshot":
        source_root = Path(os.environ.get("WEBAGENT_RUNTIME_ROOT") or REPO_ROOT).resolve()
        tmp = tempfile.NamedTemporaryFile(prefix="task_start_db_", suffix=".sqlite3", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        _sqlite_backup(source_root / "data.db", tmp_path)

        state_path = source_root / "env" / "state.json"
        state_bytes = state_path.read_bytes() if state_path.exists() else None
        return cls(source_root=source_root, db_snapshot=tmp_path, state_bytes=state_bytes)

    def materialize(self, branch_root: Path) -> None:
        branch_root.mkdir(parents=True, exist_ok=True)
        src_env = self.source_root / "env"
        if src_env.exists():
            shutil.copytree(src_env, branch_root / "env", dirs_exist_ok=True)
        else:
            (branch_root / "env").mkdir(parents=True, exist_ok=True)

        _sqlite_backup(self.db_snapshot, branch_root / "data.db")

        for suffix in ("-wal", "-shm"):
            path = branch_root / f"data.db{suffix}"
            if path.exists():
                path.unlink()

        state_path = branch_root / "env" / "state.json"
        if self.state_bytes is None:
            if state_path.exists():
                state_path.unlink()
        else:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_bytes(self.state_bytes)

        for name in ("sites", "database", "tasks"):
            target = self.source_root / name
            link = branch_root / name
            if target.exists() and not link.exists():
                link.symlink_to(target, target_is_directory=target.is_dir())

    def close(self) -> None:
        try:
            if self.db_snapshot.exists():
                self.db_snapshot.unlink()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()


def _pick_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


class TemporaryBranchRuntime:
    def __init__(self, root: Path, port: int, server_proc: subprocess.Popen[Any], server_log_path: Path):
        self.root = root
        self.port = port
        self.server_proc = server_proc
        self.server_log_path = server_log_path
        self.base_url = f"http://127.0.0.1:{self.port}"

    @classmethod
    def from_snapshot(cls, snapshot: TaskRuntimeSnapshot) -> "TemporaryBranchRuntime":
        branch_root = Path(tempfile.mkdtemp(prefix="branch_runtime_"))
        snapshot.materialize(branch_root)

        port = _pick_free_port()
        server_log_path = branch_root / f"server_{port}.log"
        log_fh = server_log_path.open("w", encoding="utf-8")
        env = os.environ.copy()
        env["WEBAGENT_RUNTIME_ROOT"] = str(branch_root)
        env["WEBAGENT_SERVER_PORT"] = str(port)
        env["WEBAGENT_SERVER_BASE_URL"] = f"http://127.0.0.1:{port}"

        proc = subprocess.Popen(
            ["python3", str(REPO_ROOT / "server.py"), str(port)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )

        started = False
        for _ in range(30):
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=1.5) as resp:
                    if 200 <= getattr(resp, "status", 200) < 500:
                        started = True
                        break
            except Exception:
                time.sleep(0.2)

        if not started:
            try:
                proc.kill()
            except Exception:
                pass
            log_fh.close()
            raise RuntimeError(f"branch_server_start_failed:{server_log_path}")

        log_fh.close()
        return cls(branch_root, port, proc, server_log_path)

    def activate_env(self) -> dict[str, str | None]:
        previous = {
            "WEBAGENT_RUNTIME_ROOT": os.environ.get("WEBAGENT_RUNTIME_ROOT"),
            "WEBAGENT_SERVER_PORT": os.environ.get("WEBAGENT_SERVER_PORT"),
            "WEBAGENT_SERVER_BASE_URL": os.environ.get("WEBAGENT_SERVER_BASE_URL"),
            "WEBAGENT_SUPPRESS_ACTION_LOGS": os.environ.get("WEBAGENT_SUPPRESS_ACTION_LOGS"),
            "WEBAGENT_SUPPRESS_ASSERTION_LOGS": os.environ.get("WEBAGENT_SUPPRESS_ASSERTION_LOGS"),
        }
        os.environ["WEBAGENT_RUNTIME_ROOT"] = str(self.root)
        os.environ["WEBAGENT_SERVER_PORT"] = str(self.port)
        os.environ["WEBAGENT_SERVER_BASE_URL"] = self.base_url
        os.environ["WEBAGENT_SUPPRESS_ACTION_LOGS"] = "1"
        os.environ["WEBAGENT_SUPPRESS_ASSERTION_LOGS"] = "1"
        return previous

    @staticmethod
    def restore_env(previous: dict[str, str | None]) -> None:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def close(self) -> None:
        try:
            if self.server_proc.poll() is None:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=5)
        except Exception:
            try:
                self.server_proc.kill()
            except Exception:
                pass
        shutil.rmtree(self.root, ignore_errors=True)
