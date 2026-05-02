#!/usr/bin/env python3
"""Lightweight external SkillBank for benchmark experiments."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-zA-Z0-9_]+", str(text or "").lower()) if tok]


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[k] * b[k] for k in common)
    den_a = math.sqrt(sum(v * v for v in a.values()))
    den_b = math.sqrt(sum(v * v for v in b.values()))
    if den_a == 0.0 or den_b == 0.0:
        return 0.0
    return num / (den_a * den_b)


def _task_family(task_id: str) -> str:
    task_id = str(task_id or "").strip()
    return task_id[:1].upper() if task_id else ""


def _parse_iso_z(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _selector_role(step: dict[str, Any]) -> str:
    act = str(step.get("act", "")).lower()
    selector = str(step.get("selector", "")).lower()
    url = str(step.get("url", "")).lower()

    if act == "open":
        if "id=" in url or "detail" in url or "property.html" in url:
            return "detail_navigation"
        return "page_entry"
    if act == "wait":
        return "success_signal"
    if act == "click":
        if any(tok in selector for tok in ("rules-check", "checkbox", "agree", "accept", "terms")):
            return "ack_control"
        if any(tok in selector for tok in ("open-", "upload-", "add-", "apply-", "create-", "new-", "join-", "enroll-")):
            return "open_form_trigger"
        if any(tok in selector for tok in ("modal-confirm", "submit", "confirm", "save", "setup", "book", "request", "send", "apply-btn", "join-modal")):
            return "submit_button"
        if ".btn.pri" in selector or "button.btn.pri" in selector:
            return "submit_button"
        if any(tok in selector for tok in ("card", "list", "item", "result", "email", "property", "group")):
            return "list_item"
        return "click_target"
    if act == "select":
        if any(tok in selector for tok in ("sort", "order")):
            return "sort_control"
        if any(tok in selector for tok in ("doc", "document", "proof", "permit-type", "event-type", "new-type")):
            return "typed_selection"
        return "selection_control"
    if act == "type":
        if any(tok in selector for tok in ("msg", "message", "chat")):
            return "message_input"
        if any(tok in selector for tok in ("file", "proof")):
            return "file_field"
        if any(tok in selector for tok in ("date", "time", "slot")):
            return "date_time_field"
        if any(tok in selector for tok in ("amount", "price", "value", "rent", "spend", "cap", "count", "duration", "quantity")):
            return "numeric_field"
        return "text_field"
    return f"{act}_target" if act else "unknown"


def _action_signature(steps: list[dict[str, Any]]) -> str:
    tokens: list[str] = []
    for step in steps:
        act = str(step.get("act", "")).lower()
        if not act or act in {"open", "wait", "done"}:
            continue
        tokens.append(f"{act}:{_selector_role(step)}")
    return ">".join(tokens)


def _success_indicators(steps: list[dict[str, Any]]) -> list[str]:
    indicators: list[str] = []
    for step in steps:
        if str(step.get("act", "")).lower() != "wait":
            continue
        selector = str(step.get("selector", "")).strip()
        if selector and selector not in indicators:
            indicators.append(selector)
    return indicators[:4]


def _infer_skill_template(task_id: str, goal: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    roles = [
        _selector_role(step)
        for step in steps
        if str(step.get("act", "")).lower() not in {"open", "wait", "done"}
    ]
    action_types = [
        str(step.get("act", "")).upper()
        for step in steps
        if str(step.get("act", "")).lower() not in {"", "open", "wait", "done"}
    ]
    unique_roles = sorted(set(roles))
    unique_action_types = sorted(set(action_types))

    skill_id = "structured_interaction"
    name = "Structured Interaction"
    description = "Follow the visible interaction structure on the page and complete the primary workflow without looping."
    termination_hint = "Stop only after the success signal is visible or the required state is written."
    failure_modes = ["repeat_action_loop", "premature_done"]

    if "message_input" in unique_roles:
        skill_id = "send_message_then_wait"
        name = "Send Message Then Wait"
        description = "Compose a concise request in the message field, send it with the primary action, then wait for the reply."
        termination_hint = "Do not stop until the requested entity or response appears in the chat output."
        failure_modes = ["repeat_action_loop", "premature_done", "element_not_found_or_timeout"]
    elif "sort_control" in unique_roles:
        skill_id = "sort_listing_then_choose"
        name = "Sort Listing Then Choose"
        description = "Adjust the listing sort control, inspect the ordered results, and then open or configure the target item."
        termination_hint = "After sorting, continue to the chosen item instead of repeating the same sort action."
        failure_modes = ["repeat_action_loop", "option_not_found"]
    elif "ack_control" in unique_roles and "submit_button" in unique_roles:
        skill_id = "acknowledge_then_confirm"
        name = "Acknowledge Then Confirm"
        description = "Accept the required rule or checkbox, then confirm the primary action in the modal or form."
        termination_hint = "Complete the confirmation flow before DONE()."
        failure_modes = ["overlay_block", "premature_done"]
    elif "open_form_trigger" in unique_roles and "submit_button" in unique_roles:
        skill_id = "open_form_fill_submit"
        name = "Open Form Fill Submit"
        description = "Open the form or modal, fill the required fields, then submit with the primary confirm button."
        termination_hint = "After opening the form, switch from entry actions to field completion and submit."
        failure_modes = ["repeat_action_loop", "action_type_error", "premature_done"]
    elif "submit_button" in unique_roles and ("text_field" in unique_roles or "numeric_field" in unique_roles or "selection_control" in unique_roles or "typed_selection" in unique_roles):
        skill_id = "fill_form_then_submit"
        name = "Fill Form Then Submit"
        description = "Fill the visible form fields, set required selections, and confirm with the submit button."
        termination_hint = "Do not emit DONE() until the submit action and success signal have happened."
        failure_modes = ["repeat_action_loop", "action_type_error", "premature_done"]
    elif unique_action_types.count("SELECT") >= 1 and "submit_button" in unique_roles:
        skill_id = "configure_options_then_submit"
        name = "Configure Options Then Submit"
        description = "Set the visible dropdown options needed for the task, then commit them with the primary action."
        termination_hint = "Prefer valid visible options and submit once the configuration is complete."
        failure_modes = ["option_not_found", "repeat_action_loop"]

    tags = sorted(
        {
            skill_id,
            name.lower().replace(" ", "_"),
            _task_family(task_id).lower(),
            *(_tokenize(goal)[:12]),
            *unique_roles,
            *[act.lower() for act in unique_action_types],
        }
    )
    return {
        "skill_id": skill_id,
        "name": name,
        "description": description,
        "termination_hint": termination_hint,
        "failure_modes": failure_modes,
        "selector_roles": unique_roles,
        "preferred_action_types": unique_action_types,
        "action_signature": _action_signature(steps),
        "success_indicators": _success_indicators(steps),
        "task_families": [_task_family(task_id)],
        "task_ids": [task_id],
        "example_goals": [goal] if goal else [],
        "bootstrap_count": 1,
        "usage_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "success_rate": 0.5,
        "updated_at": _iso_now(),
        "tags": tags,
    }


def _merge_skill(existing: dict[str, Any], new_item: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged["task_families"] = sorted(set(existing.get("task_families", [])) | set(new_item.get("task_families", [])))
    merged["task_ids"] = sorted(set(existing.get("task_ids", [])) | set(new_item.get("task_ids", [])))
    merged["example_goals"] = (existing.get("example_goals", []) + new_item.get("example_goals", []))[:8]
    merged["selector_roles"] = sorted(set(existing.get("selector_roles", [])) | set(new_item.get("selector_roles", [])))
    merged["preferred_action_types"] = sorted(set(existing.get("preferred_action_types", [])) | set(new_item.get("preferred_action_types", [])))
    merged["success_indicators"] = sorted(set(existing.get("success_indicators", [])) | set(new_item.get("success_indicators", [])))[:6]
    merged["failure_modes"] = sorted(set(existing.get("failure_modes", [])) | set(new_item.get("failure_modes", [])))[:8]
    merged["tags"] = sorted(set(existing.get("tags", [])) | set(new_item.get("tags", [])))
    merged["bootstrap_count"] = int(existing.get("bootstrap_count", 0) or 0) + int(new_item.get("bootstrap_count", 0) or 0)
    merged["online_count"] = int(existing.get("online_count", 0) or 0) + int(new_item.get("online_count", 0) or 0)
    merged["updated_at"] = _iso_now()
    return merged


def _parse_action_history_item(action: str) -> dict[str, Any] | None:
    raw = str(action or "").strip()
    if not raw:
        return None
    match = re.match(r"(?is)^\s*(CLICK|TYPE|SELECT|GOTO|WAIT|DONE)\((.*)\)\s*$", raw)
    if not match:
        return None
    cmd = match.group(1).strip().lower()
    body = match.group(2).strip()
    if cmd == "goto":
        url = body.strip().strip('"').strip("'")
        return {"act": "open", "url": url} if url else None
    if cmd in {"wait", "done"}:
        return None
    if cmd == "click":
        selector = body.strip().strip('"').strip("'")
        return {"act": "click", "selector": selector} if selector else None
    if "," not in body:
        return None
    selector, value = body.split(",", 1)
    selector = selector.strip().strip('"').strip("'")
    value = value.strip().strip('"').strip("'")
    if not selector:
        return None
    step = {"act": cmd, "selector": selector}
    if value:
        step["value"] = value
    return step


def _action_history_to_steps(action_history: list[str] | None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for action in action_history or []:
        parsed = _parse_action_history_item(action)
        if parsed is not None:
            steps.append(parsed)
    return steps


def bootstrap_skill_bank(tasks_root: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(tasks_root or REPO_ROOT / "tasks").resolve()
    grouped: dict[str, dict[str, Any]] = {}
    for task_dir in sorted(root.iterdir()):
        if not task_dir.is_dir():
            continue
        trace = _load_json(task_dir / "oracle_trace.json", {})
        steps = trace.get("steps", [])
        if not steps:
            continue
        spec = _load_json(task_dir / "task_spec.json", {})
        goal = str(spec.get("goal", "")).strip()
        task_id = task_dir.name
        item = _infer_skill_template(task_id=task_id, goal=goal, steps=steps)
        group_key = f"{item['skill_id']}|{item['action_signature']}"
        existing = grouped.get(group_key)
        grouped[group_key] = item if existing is None else _merge_skill(existing, item)
    skills = list(grouped.values())
    skills.sort(key=lambda item: (item.get("skill_id", ""), item.get("action_signature", "")))
    return skills


class SkillBankStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_bootstrap()

    def _ensure_bootstrap(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return
            except Exception:
                pass
        skills = bootstrap_skill_bank(os.environ.get("AGENT_SKILLBANK_BOOTSTRAP_ROOT"))
        self.save(skills)

    def load(self) -> list[dict[str, Any]]:
        self._ensure_bootstrap()
        return _load_json(self.path, [])

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def retrieve(self, query: str, top_k: int = 3, task_id: str = "") -> list[dict[str, Any]]:
        items = self.load()
        qvec = Counter(_tokenize(query))
        task_family = _task_family(task_id).lower()
        now = datetime.now(timezone.utc)
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in items:
            text = " ".join(
                [
                    str(item.get("skill_id", "")),
                    str(item.get("name", "")),
                    str(item.get("description", "")),
                    str(item.get("termination_hint", "")),
                    " ".join(item.get("tags", []) or []),
                    " ".join(item.get("task_ids", [])[:6]),
                    " ".join(item.get("example_goals", [])[:3]),
                ]
            )
            lexical = _cosine(qvec, Counter(_tokenize(text)))
            family_bonus = 0.15 if task_family and task_family in {f.lower() for f in item.get("task_families", [])} else 0.0
            success_rate = float(item.get("success_rate", 0.5) or 0.5)
            support_bonus = min(0.18, 0.03 * int(item.get("bootstrap_count", 1) or 1))
            online_bonus = min(0.25, 0.05 * int(item.get("online_count", 0) or 0))
            recency_bonus = 0.0
            updated_at = _parse_iso_z(str(item.get("updated_at", "")))
            if updated_at is not None:
                age_hours = max(0.0, (now - updated_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
                recency_bonus = max(0.0, 0.08 - min(0.08, age_hours / 240.0))
            score = lexical + family_bonus + 0.20 * success_rate + support_bonus + online_bonus + recency_bonus
            if score <= 0.0:
                continue
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            selected: list[dict[str, Any]] = []
            used_skill_ids: set[str] = set()
            for _score, item in scored:
                skill_id = str(item.get("skill_id", "")).strip()
                if skill_id and skill_id in used_skill_ids:
                    continue
                selected.append(item)
                if skill_id:
                    used_skill_ids.add(skill_id)
                if len(selected) >= top_k:
                    break
            if selected:
                return selected
        fallback = sorted(
            items,
            key=lambda item: (
                float(item.get("success_rate", 0.5) or 0.5),
                int(item.get("bootstrap_count", 0) or 0),
            ),
            reverse=True,
        )
        return fallback[:top_k]

    def record_run(
        self,
        *,
        task_id: str,
        goal: str,
        success: bool,
        failure_category: str,
        end_reason: str,
        action_history: list[str] | None,
        retrieved_skills: list[dict[str, Any]] | None,
    ) -> int:
        skills = self.load()
        if not skills or not retrieved_skills:
            if success and action_history:
                runtime_steps = _action_history_to_steps(action_history)
                if runtime_steps:
                    runtime_item = _infer_skill_template(task_id=task_id, goal=goal, steps=runtime_steps)
                    runtime_item["bootstrap_count"] = 0
                    runtime_item["online_count"] = 1
                    runtime_item["usage_count"] = 1
                    runtime_item["success_count"] = 1
                    runtime_item["failure_count"] = 0
                    runtime_item["success_rate"] = 1.0
                    runtime_item["source"] = "runtime"
                    skills = skills or []
                    skills.append(runtime_item)
                    self.save(skills)
                    return 1
            return 0
        by_id = {str(item.get("skill_id", "")): item for item in skills}
        updated = 0
        family = _task_family(task_id)
        action_types = sorted(
            {
                str(action).split("(", 1)[0].strip().upper()
                for action in (action_history or [])
                if str(action).strip()
            }
        )
        for retrieved in retrieved_skills[:1]:
            skill = by_id.get(str(retrieved.get("skill_id", "")))
            if skill is None:
                continue
            skill["usage_count"] = int(skill.get("usage_count", 0) or 0) + 1
            if success:
                skill["success_count"] = int(skill.get("success_count", 0) or 0) + 1
            else:
                skill["failure_count"] = int(skill.get("failure_count", 0) or 0) + 1
            total = int(skill.get("success_count", 0) or 0) + int(skill.get("failure_count", 0) or 0)
            skill["success_rate"] = float(skill.get("success_count", 0) or 0) / total if total else 0.5
            skill["task_families"] = sorted(set(skill.get("task_families", [])) | ({family} if family else set()))
            if goal:
                skill["example_goals"] = (skill.get("example_goals", []) + [goal])[-8:]
            if action_types:
                skill["preferred_action_types"] = sorted(set(skill.get("preferred_action_types", [])) | set(action_types))
            if not success and failure_category:
                skill["failure_modes"] = sorted(set(skill.get("failure_modes", [])) | {failure_category})[:8]
            if not success and end_reason:
                tags = set(skill.get("tags", []))
                tags.update(_tokenize(end_reason))
                skill["tags"] = sorted(tags)
            skill["updated_at"] = _iso_now()
            updated += 1
        if success and action_history:
            runtime_steps = _action_history_to_steps(action_history)
            if runtime_steps:
                runtime_item = _infer_skill_template(task_id=task_id, goal=goal, steps=runtime_steps)
                runtime_item["bootstrap_count"] = 0
                runtime_item["online_count"] = 1
                runtime_item["usage_count"] = 1
                runtime_item["success_count"] = 1
                runtime_item["failure_count"] = 0
                runtime_item["success_rate"] = 1.0
                runtime_item["source"] = "runtime"
                group_key = f"{runtime_item['skill_id']}|{runtime_item['action_signature']}"
                merged = False
                for idx, existing in enumerate(skills):
                    existing_key = f"{existing.get('skill_id', '')}|{existing.get('action_signature', '')}"
                    if existing_key != group_key:
                        continue
                    combined = _merge_skill(existing, runtime_item)
                    combined["usage_count"] = int(existing.get("usage_count", 0) or 0) + 1
                    combined["success_count"] = int(existing.get("success_count", 0) or 0) + 1
                    combined["failure_count"] = int(existing.get("failure_count", 0) or 0)
                    total = int(combined.get("success_count", 0) or 0) + int(combined.get("failure_count", 0) or 0)
                    combined["success_rate"] = float(combined.get("success_count", 0) or 0) / total if total else 1.0
                    combined["source"] = existing.get("source", "bootstrap")
                    skills[idx] = combined
                    merged = True
                    break
                if not merged:
                    skills.append(runtime_item)
                updated += 1
        self.save(skills)
        return updated
