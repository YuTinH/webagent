#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import requests

from agent.assertions_dsl import AssertionDSL


THEMES = ["newcomer", "daily", "career", "leisure", "crisis"]
_MEM_KEY_RE = re.compile(r"mem\('([^']+)'\)")
_MEM_EQ_STR_RE = re.compile(r"mem\('([^']+)'\)\s*==\s*'([^']*)'")
_MEM_EQ_NUM_RE = re.compile(r"mem\('([^']+)'\)\s*==\s*([0-9]+(?:\.[0-9]+)?)")


def _parse_int_env(name: str, default: int = None):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    s = str(raw).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _normalize_base_url(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return "http://localhost:8014"
    return base


def _retarget_url_to_base(raw_url: str, base_url: str) -> str:
    base = _normalize_base_url(base_url)
    parts = urlsplit(raw_url)
    if parts.scheme and parts.netloc:
        base_parts = urlsplit(base)
        return urlunsplit((base_parts.scheme, base_parts.netloc, parts.path, parts.query, parts.fragment))
    if raw_url.startswith("/"):
        return f"{base}{raw_url}"
    return urljoin(f"{base}/", raw_url)


def _apply_runtime_url_flags(
    raw_url: str,
    is_clean: bool,
    is_obfuscate: bool,
    distractor_level: str,
    distractor_seed: int,
    obfuscation_seed: int,
    base_url: str,
) -> str:
    raw_url = _retarget_url_to_base(raw_url, base_url)
    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k in ["clean", "obfuscate", "dlevel", "dseed", "obf_seed"]:
        query.pop(k, None)

    if is_clean:
        query["clean"] = "true"
    if is_obfuscate:
        query["obfuscate"] = "true"
        if obfuscation_seed is not None:
            query["obf_seed"] = str(obfuscation_seed)
    if not is_clean and distractor_level:
        query["dlevel"] = str(distractor_level)
    if not is_clean and distractor_seed is not None:
        query["dseed"] = str(distractor_seed)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _derive_hardened_checkpoints(criteria: List[str]) -> List[dict]:
    checkpoints: List[dict] = []
    for i, crit in enumerate(criteria or []):
        crit = str(crit).strip()
        if not crit:
            continue
        cp_prefix = f"crit_{i+1}"
        mem_match = _MEM_KEY_RE.search(crit)
        can_add_intermediate = mem_match is not None and "!= ''" not in crit
        if can_add_intermediate:
            key = mem_match.group(1)
            cp_state_id = f"{cp_prefix}_state"
            checkpoints.append(
                {
                    "id": cp_state_id,
                    "name": f"Criterion {i+1} state set",
                    "assertion": f"mem('{key}') != ''",
                    "weight": 0.4,
                    "required": True,
                    "depends_on": [],
                }
            )
            checkpoints.append(
                {
                    "id": f"{cp_prefix}_final",
                    "name": f"Criterion {i+1} final",
                    "assertion": crit,
                    "weight": 0.6,
                    "required": True,
                    "depends_on": [cp_state_id],
                }
            )
        else:
            checkpoints.append(
                {
                    "id": f"{cp_prefix}_final",
                    "name": f"Criterion {i+1} final",
                    "assertion": crit,
                    "weight": 1.0,
                    "required": True,
                    "depends_on": [],
                }
            )
    return checkpoints


class FileSnapshot:
    def __init__(self) -> None:
        self._original: Dict[Path, str] = {}

    def remember(self, path: Path) -> None:
        if path not in self._original and path.exists():
            self._original[path] = path.read_text(encoding="utf-8")

    def restore_all(self) -> None:
        for path, content in self._original.items():
            path.write_text(content, encoding="utf-8")


def load_theme_scenarios(theme: str) -> List[dict]:
    path = Path(f"sampled_{theme}.json")
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _criterion_eq_str(criteria: List[str], key: str) -> str:
    pattern = re.compile(rf"mem\('{re.escape(key)}'\)\s*==\s*'([^']*)'")
    for crit in criteria:
        m = pattern.search(crit)
        if m:
            return m.group(1)
    return ""


def _criterion_eq_float(criteria: List[str], key: str) -> float:
    pattern = re.compile(rf"mem\('{re.escape(key)}'\)\s*==\s*([0-9]+(?:\.[0-9]+)?)")
    for crit in criteria:
        m = pattern.search(crit)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return 0.0
    return 0.0


def _extract_required_checkpoint_assertions(scoring_checkpoints: List[dict]) -> List[str]:
    out: List[str] = []
    for cp in scoring_checkpoints or []:
        if not isinstance(cp, dict):
            continue
        if bool(cp.get("required", True)) is False:
            continue
        if str(cp.get("when", "")).strip():
            # Branch-gated checkpoints may intentionally differ by condition.
            continue
        assertion = str(cp.get("assertion", "")).strip()
        if assertion:
            out.append(assertion)
    return out


def _extract_mem_eq_targets(assertions: List[str]) -> Dict[str, set]:
    targets: Dict[str, set] = {}
    for expr in assertions or []:
        s = str(expr).strip()
        m = _MEM_EQ_STR_RE.match(s)
        if m:
            key, expected = m.group(1), m.group(2)
            targets.setdefault(key, set()).add(expected)
            continue
        m = _MEM_EQ_NUM_RE.match(s)
        if m:
            key, expected = m.group(1), m.group(2)
            targets.setdefault(key, set()).add(expected)
    return targets


def _checkpoints_contradict_criteria(criteria: List[str], scoring_checkpoints: List[dict]) -> bool:
    crit_targets = _extract_mem_eq_targets(criteria)
    cp_assertions = _extract_required_checkpoint_assertions(scoring_checkpoints)
    cp_targets = _extract_mem_eq_targets(cp_assertions)
    for key in set(crit_targets.keys()) & set(cp_targets.keys()):
        if crit_targets[key] and cp_targets[key] and crit_targets[key].isdisjoint(cp_targets[key]):
            return True
    return False


def patch_trace(
    task_id: str,
    instruction: str,
    snapshot: FileSnapshot,
    criteria: List[str],
    base_url: str,
    step_payload: Optional[dict] = None,
) -> None:
    trace_path = Path("tasks") / task_id / "oracle_trace.json"
    if not trace_path.exists():
        return
    snapshot.remember(trace_path)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    has_override = isinstance(step_payload, dict) and isinstance(step_payload.get("oracle_trace_override"), list)
    if has_override:
        trace["steps"] = step_payload["oracle_trace_override"]

    # A1 has template variants that can change sort target and lease term.
    if (not has_override) and task_id == "A1-find-home":
        lower_instr = (instruction or "").lower()
        target_prop = None
        if "suburb" in lower_instr:
            target_prop = "PROP-102"
        elif "city" in lower_instr:
            target_prop = "PROP-101"
        if any("housing.lease.last.id" in str(c) and "PROP-EXT-" in str(c) for c in criteria):
            target_prop = _criterion_eq_str(criteria, "housing.lease.last.id") or "PROP-EXT-0"
            expected_term = "12"
            for c in criteria:
                m = re.search(r"json\('env','housing\.lease\.last\.term'\)\s*==\s*'([^']+)'", str(c))
                if m:
                    expected_term = m.group(1)
                    break
            sort_order = "price_high" if str(target_prop).endswith("-19") else "price_low"
            trace["steps"] = [
                {
                    "t": 0,
                    "act": "open",
                    "url": f"{_normalize_base_url(base_url)}/housing.local/index.html?clean=true",
                },
                {"t": 1, "act": "select", "selector": "#sort-order", "value": sort_order},
                {
                    "t": 2,
                    "act": "open",
                    "url": f"{_normalize_base_url(base_url)}/housing.local/property.html?id={target_prop}&clean=true",
                },
                {"t": 3, "act": "select", "selector": "#lease-term", "value": expected_term},
                {"t": 4, "act": "click", "selector": "#apply-btn"},
            ]
        elif target_prop:
            for step in trace.get("steps", []):
                if step.get("act") == "open" and "housing.local/property.html" in step.get("url", ""):
                    step["url"] = f"{_normalize_base_url(base_url)}/housing.local/property.html?id={target_prop}"
                    break

    # B1 has keyboard/mouse variants with different expected totals.
    if task_id == "B1-shopping":
        expected_total = _criterion_eq_float(criteria, "shop.orders.last.total")
        target_sku = "KB-8801" if expected_total >= 90 else "WM-5521"
        for step in trace.get("steps", []):
            if step.get("act") == "open" and "shop.local/product.html" in step.get("url", ""):
                step["url"] = f"{_normalize_base_url(base_url)}/shop.local/product.html?id={target_sku}&clean=true"
                break

    # I5 has green/premium variants.
    if task_id == "I5-energy-optimize":
        target_plan = _criterion_eq_str(criteria, "meters.M-321.plan")
        if target_plan:
            for step in trace.get("steps", []):
                if step.get("act") == "click" and "#plan-" in step.get("selector", ""):
                    step["selector"] = f"#plan-{target_plan} button"
                if step.get("act") == "wait" and "#plan-" in step.get("selector", ""):
                    step["selector"] = f"#plan-{target_plan}.active"

    # E3 has taxi/self-drive variants.
    if task_id == "E3-airport-transfer":
        target_method = ""
        lower_instr = (instruction or "").lower()
        if "drive" in lower_instr or "parking" in lower_instr:
            # Default to self-drive for "drive" intent, then downgrade if vehicle is under repair.
            target_method = "self_drive"
            try:
                state_path = Path("env/state.json")
                if state_path.exists():
                    env_state = json.loads(state_path.read_text(encoding="utf-8"))
                    condition = (
                        env_state.get("world_state", {})
                        .get("vehicle_context", {})
                        .get("condition")
                    )
                    if str(condition) in {"under_repair", "broken"}:
                        target_method = "taxi"
            except Exception:
                pass
        elif "taxi" in lower_instr:
            target_method = "taxi"
        else:
            # Fallback for legacy criteria shapes.
            target_method = _criterion_eq_str(criteria, "trips.transfer.method")

        for step in trace.get("steps", []):
            if step.get("act") == "select" and step.get("selector") == "#transfer-method" and target_method:
                step["value"] = target_method
            if step.get("act") == "wait":
                # Locale-dependent success copy is unstable; rely on deterministic criteria for pass/fail.
                step["selector"] = "#transfer-method"

    # B7 has second-hand item vs professional service listing variants.
    if task_id == "B7-second-hand-sale":
        lower_instr = (instruction or "").lower()
        target_category = _criterion_eq_str(criteria, "market.listed_items.last.category")
        if not target_category:
            if "professional gig" in lower_instr or "service" in lower_instr:
                target_category = "service"
            else:
                target_category = "home"

        if target_category == "service":
            # Handler doubles service price for certified users.
            # Keep input at 100 so final memory target becomes 200 (not 400).
            target_price = 100.0
        else:
            target_price = _criterion_eq_float(criteria, "market.listed_items.last.price")

        for step in trace.get("steps", []):
            if step.get("act") == "select" and step.get("selector") == "#category":
                step["value"] = target_category
            if step.get("act") == "type" and step.get("selector") == "#price" and target_price > 0:
                if float(target_price).is_integer():
                    step["value"] = str(int(target_price))
                else:
                    step["value"] = str(target_price)

    # I2 has appliance variants (e.g., My Car vs Oven).
    if task_id == "I2-appliance-repair":
        target_appliance = _criterion_eq_str(criteria, "appliance_repairs.requests.last.appliance")
        if target_appliance:
            for step in trace.get("steps", []):
                if step.get("act") == "type" and step.get("selector") == "#appliance-name":
                    step["value"] = target_appliance
                if step.get("act") == "wait" and "appliance-repair-requests-list" in step.get("selector", ""):
                    step["value"] = target_appliance

    # D3 may carry different account numbers in flow variants.
    if task_id == "D3-autopay":
        target_acc = _criterion_eq_str(criteria, "autopay.utility.account_number")
        if target_acc:
            for step in trace.get("steps", []):
                if step.get("act") == "type" and step.get("selector") == "#account-number":
                    step["value"] = target_acc

    is_clean = os.environ.get("BENCHMARK_CLEAN_MODE") == "true"
    is_obfuscate = os.environ.get("BENCHMARK_OBFUSCATE") == "true"
    distractor_level = (os.environ.get("BENCHMARK_DISTRACTOR_LEVEL") or "medium").strip().lower()
    distractor_seed = _parse_int_env("BENCHMARK_DISTRACTOR_SEED", None)
    obfuscation_seed = _parse_int_env("BENCHMARK_OBFUSCATION_SEED", None)
    for step in trace.get("steps", []):
        if step.get("act") != "open":
            continue
        step["url"] = _apply_runtime_url_flags(
            step["url"],
            is_clean=is_clean,
            is_obfuscate=is_obfuscate,
            distractor_level=distractor_level,
            distractor_seed=distractor_seed,
            obfuscation_seed=obfuscation_seed,
            base_url=base_url,
        )

    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")


def patch_spec(
    task_id: str,
    instruction: str,
    criteria: List[str],
    snapshot: FileSnapshot,
    scoring_checkpoints: List[dict] = None,
) -> None:
    spec_path = Path("tasks") / task_id / "task_spec.json"
    if not spec_path.exists():
        return
    snapshot.remember(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    original_criteria = [str(c).strip() for c in (spec.get("success_criteria") or []) if str(c).strip()]
    spec["goal"] = instruction
    normalized = [str(c).strip() for c in (criteria or []) if str(c).strip()]
    if not normalized:
        normalized = [str(c).strip() for c in (spec.get("success_criteria") or []) if str(c).strip()]
    # Some generated chains still carry weak UI-only criteria placeholders.
    # Prefer task-authored criteria when generated criteria miss state assertions.
    if normalized and original_criteria:
        gen_has_state_assert = any(("mem(" in c or "json(" in c) for c in normalized)
        task_has_state_assert = any(("mem(" in c or "json(" in c) for c in original_criteria)
        if (not gen_has_state_assert) and task_has_state_assert:
            normalized = list(original_criteria)
    spec["success_criteria"] = normalized
    spec["preconditions"] = []
    if isinstance(scoring_checkpoints, list) and scoring_checkpoints:
        active_checkpoints = _resolve_active_checkpoints(scoring_checkpoints)
        if active_checkpoints:
            spec["scoring_checkpoints"] = active_checkpoints
        else:
            derived = _derive_hardened_checkpoints(normalized)
            if derived:
                spec["scoring_checkpoints"] = derived
            else:
                spec.pop("scoring_checkpoints", None)
    elif (
        normalized == original_criteria
        and isinstance(spec.get("scoring_checkpoints"), list)
        and spec.get("scoring_checkpoints")
        and not _checkpoints_contradict_criteria(normalized, spec.get("scoring_checkpoints") or [])
    ):
        # Keep task-authored checkpoints only when criteria are unchanged.
        pass
    else:
        derived = _derive_hardened_checkpoints(normalized)
        if derived:
            spec["scoring_checkpoints"] = derived
        else:
            spec.pop("scoring_checkpoints", None)
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _build_runtime_dsl() -> AssertionDSL:
    memory: Dict[str, object] = {}
    try:
        conn = sqlite3.connect("data.db")
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT key, value FROM memory_kv")
        for row in cur.fetchall():
            raw = row["value"]
            try:
                memory[row["key"]] = json.loads(raw)
            except Exception:
                memory[row["key"]] = raw
        conn.close()
    except Exception:
        pass

    def env_api(channel: str, path: str):
        state_path = Path("env/state.json")
        if not state_path.exists():
            return None
        try:
            current = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except Exception:
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    return AssertionDSL(None, memory, env_api)


def _resolve_active_checkpoints(scoring_checkpoints: List[dict]) -> List[dict]:
    if not isinstance(scoring_checkpoints, list) or not scoring_checkpoints:
        return []
    dsl = _build_runtime_dsl()
    active: List[dict] = []
    for raw in scoring_checkpoints:
        if not isinstance(raw, dict):
            continue
        assertion = str(raw.get("assertion", "")).strip()
        if not assertion:
            continue
        cp = dict(raw)
        when_expr = str(cp.get("when", "")).strip()
        is_active = True
        if when_expr:
            try:
                is_active = bool(dsl.evaluate(when_expr))
            except Exception:
                is_active = False
        if not is_active:
            continue
        cp.pop("when", None)
        active.append(cp)
    return active


def inject_state(initial_state: dict, base_url: str) -> None:
    if not initial_state:
        return

    payload = {
        "has_home": True,
        "has_bank": True,
        "has_utility": True,
        "location": "city",
        "balance": 5000,
        "world_state": {"location_context": {"tier": "city_center"}},
    }
    payload = _deep_merge(payload, initial_state)

    # Keep top-level generator state aligned with backend branch context.
    if "certified" in payload:
        payload.setdefault("world_state", {}).setdefault("skills", {})["certified"] = bool(payload.get("certified"))
    if "energy_cost" in payload:
        projected = "high" if str(payload.get("energy_cost")).strip().lower() == "high" else "low"
        payload.setdefault("world_state", {}).setdefault("energy_context", {})["projected_cost"] = projected
    if "is_sick" in payload:
        status = "ill" if bool(payload.get("is_sick")) else "healthy"
        payload.setdefault("world_state", {}).setdefault("health_context", {})["current_status"] = status
    if "card_frozen" in payload:
        frozen = bool(payload.get("card_frozen"))
        card_state = "blocked" if frozen else "active"
        payload.setdefault("world_state", {}).setdefault("financial_context", {})["liquidity"] = (
            "frozen" if frozen else "active"
        )
        payload.setdefault("payments", {}).setdefault("cards", {}).setdefault("1234", {})["state"] = card_state

    if payload.get("location") == "suburb":
        payload.setdefault("world_state", {}).setdefault("location_context", {})["tier"] = "suburban"

    data = {"task_id": "DEBUG", "action": "set_state", "payload": payload}
    resp = requests.post(
        f"{_normalize_base_url(base_url)}/api/mutate",
        json=data,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()


def inject_state_delta(delta: dict, base_url: str) -> None:
    if not isinstance(delta, dict) or not delta:
        return
    data = {"task_id": "DEBUG", "action": "set_state", "payload": delta}
    resp = requests.post(
        f"{_normalize_base_url(base_url)}/api/mutate",
        json=data,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()


def run_oracle_task(task_id: str, headless: bool, task_timeout_sec: int) -> Tuple[bool, str, dict]:
    result_path = Path("output") / task_id / "result.json"
    if result_path.exists():
        result_path.unlink()

    cmd = ["python3", "run_task.py", task_id]
    if headless:
        cmd.append("--headless")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=task_timeout_sec)
    except subprocess.TimeoutExpired:
        return False, f"task timeout after {task_timeout_sec}s", {}
    combined = (proc.stdout or "") + (proc.stderr or "")

    if not result_path.exists():
        return False, "missing result.json", {}

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"invalid result.json: {exc}", {}

    verification = result.get("verification")
    if not isinstance(verification, dict):
        verification = {}

    success = bool(result.get("success"))
    if success:
        return True, "", verification

    raw_error = result.get("error")
    if isinstance(raw_error, dict):
        reason = str(raw_error.get("error_message", "")).strip()
    elif isinstance(raw_error, str):
        reason = raw_error.strip()
    else:
        reason = ""
    if not reason and verification.get("required_failed"):
        failed = verification.get("required_failed") or []
        preview = ", ".join(str(x) for x in failed[:2])
        reason = f"required checkpoints failed: {preview}"
    if not reason:
        fail_lines = [line for line in combined.splitlines() if "FAIL" in line or "Error" in line]
        reason = fail_lines[-1] if fail_lines else "oracle returned failure"
    return False, reason, verification


def verification_to_checkpoint_eval(verification: dict) -> dict:
    if not isinstance(verification, dict) or not verification:
        return {}

    criteria_failed = verification.get("required_failed")
    if not isinstance(criteria_failed, list):
        raw = verification.get("criteria_failed")
        criteria_failed = raw if isinstance(raw, list) else []

    return {
        "criteria_total": int(verification.get("criteria_total", 0) or 0),
        "criteria_passed": int(verification.get("criteria_passed", 0) or 0),
        "criteria_failed": [str(x) for x in criteria_failed],
        "step_score_percent": float(verification.get("step_score_percent", 0.0) or 0.0),
        "step_progress": float(verification.get("step_progress", 0.0) or 0.0),
        "checkpoint_total": int(verification.get("checkpoint_total", 0) or 0),
    }


def evaluate_step_checkpoints(criteria: List[str], scoring_checkpoints: List[dict] = None) -> dict:
    """
    Evaluate criteria as checkpoints from current state and memory.
    This keeps oracle step scoring aligned with agent scoring logic.
    """
    if not criteria and not scoring_checkpoints:
        return {
            "criteria_total": 0,
            "criteria_passed": 0,
            "criteria_failed": [],
            "step_score_percent": 100.0,
            "step_progress": 1.0,
            "checkpoint_total": 0,
        }

    dsl = _build_runtime_dsl()
    checkpoints = scoring_checkpoints if isinstance(scoring_checkpoints, list) and scoring_checkpoints else _derive_hardened_checkpoints(criteria)

    if not checkpoints:
        return {
            "criteria_total": len(criteria),
            "criteria_passed": 0,
            "criteria_failed": list(criteria),
            "step_score_percent": 0.0,
            "step_progress": 0.0,
            "checkpoint_total": 0,
        }

    # Branch activation: checkpoints can declare `when` to gate branch-specific assertions.
    activation_map: Dict[str, bool] = {}
    active_checkpoints: List[dict] = []
    for cp in checkpoints:
        cp_id = str(cp.get("id", ""))
        when_expr = str(cp.get("when", "")).strip()
        is_active = True
        if when_expr:
            try:
                is_active = bool(dsl.evaluate(when_expr))
            except Exception:
                is_active = False
        activation_map[cp_id] = is_active
        if is_active:
            active_checkpoints.append(cp)

    if not active_checkpoints:
        return {
            "criteria_total": 0,
            "criteria_passed": 0,
            "criteria_failed": ["NO_ACTIVE_CHECKPOINT_BRANCH"],
            "step_score_percent": 0.0,
            "step_progress": 0.0,
            "checkpoint_total": 0,
        }

    total_weight = 0.0
    for cp in active_checkpoints:
        try:
            w = float(cp.get("weight", 1.0))
        except Exception:
            w = 1.0
        if w < 0:
            w = 0.0
        cp["weight"] = w
        total_weight += w
    if total_weight <= 0:
        for cp in active_checkpoints:
            cp["weight_norm"] = 1.0 / len(active_checkpoints)
    else:
        for cp in active_checkpoints:
            cp["weight_norm"] = float(cp.get("weight", 0.0)) / total_weight

    raw_pass_map: Dict[str, bool] = {}
    for cp in active_checkpoints:
        cp_id = str(cp.get("id", ""))
        assertion = str(cp.get("assertion", ""))
        if not cp_id or not assertion:
            raw_pass_map[cp_id] = False
            continue
        try:
            raw_pass_map[cp_id] = bool(dsl.evaluate(assertion))
        except Exception:
            raw_pass_map[cp_id] = False

    final_pass_map: Dict[str, bool] = {}
    criteria_failed: List[str] = []
    criteria_passed = 0
    earned = 0.0
    for cp in active_checkpoints:
        cp_id = str(cp.get("id", ""))
        depends_on = cp.get("depends_on", [])
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        deps_ok = all(final_pass_map.get(str(dep), False) for dep in depends_on)
        cp_ok = bool(raw_pass_map.get(cp_id, False)) and deps_ok
        final_pass_map[cp_id] = cp_ok
        if cp_ok:
            criteria_passed += 1
            earned += float(cp.get("weight_norm", 0.0))
        else:
            if bool(cp.get("required", True)):
                criteria_failed.append(str(cp.get("assertion", "")))

    return {
        "criteria_total": len(active_checkpoints),
        "criteria_passed": criteria_passed,
        "criteria_failed": criteria_failed,
        "step_score_percent": earned * 100.0,
        "step_progress": earned,
        "checkpoint_total": len(active_checkpoints),
    }


def run_chain(
    scenario: dict,
    snapshot: FileSnapshot,
    headless: bool,
    stop_on_first_fail_task: bool,
    task_timeout_sec: int,
    base_url: str,
    step_pre_hook: Optional[Callable[[int, dict], None]] = None,
) -> dict:
    chain_id = scenario["chain_id"]
    print(f"\n▶ Running Chain: {chain_id}")

    init_db_script = Path(__file__).with_name("init_db.py")
    subprocess.run(["python3", str(init_db_script)], check=True, stdout=subprocess.DEVNULL)
    state_path = Path("env/state.json")
    if state_path.exists():
        state_path.unlink()
    inject_state(scenario.get("initial_state") or {}, base_url=base_url)

    chain_total = sum(int(s.get("difficulty", 1)) for s in scenario["steps"])
    chain_score = 0
    chain_step_earned = 0.0
    task_results = []
    executed_tasks = 0

    for step_idx, step in enumerate(scenario["steps"]):
        if step_pre_hook is not None:
            try:
                step_pre_hook(step_idx, step)
            except Exception as exc:
                print(f"[warn] step_pre_hook failed at step {step_idx}: {exc}")
        task_id = step["task_id"]
        difficulty = int(step.get("difficulty", 1))
        patch_trace(
            task_id,
            step["instruction"],
            snapshot,
            step.get("success_criteria", []),
            base_url=base_url,
            step_payload=step,
        )
        patch_spec(
            task_id,
            step["instruction"],
            step.get("success_criteria", []),
            snapshot,
            scoring_checkpoints=(step.get("scoring_checkpoints") or step.get("checkpoints") or []),
        )

        raw_ok, reason, verification = run_oracle_task(task_id, headless=headless, task_timeout_sec=task_timeout_sec)
        executed_tasks += 1

        checkpoint_eval = verification_to_checkpoint_eval(verification)
        if not checkpoint_eval:
            checkpoint_eval = evaluate_step_checkpoints(
                step.get("success_criteria", []),
                scoring_checkpoints=(step.get("scoring_checkpoints") or step.get("checkpoints") or []),
            )
        chain_step_earned += float(checkpoint_eval.get("step_progress", 0.0))
        checkpoint_ok = len(checkpoint_eval.get("criteria_failed", [])) == 0
        ok = bool(raw_ok) and checkpoint_ok

        if not checkpoint_ok and raw_ok:
            failed = checkpoint_eval.get("criteria_failed", [])
            preview = ", ".join(failed[:2]) if failed else "required checkpoint failed"
            reason = f"required checkpoints failed: {preview}"
        elif not checkpoint_ok and not raw_ok:
            failed = checkpoint_eval.get("criteria_failed", [])
            if failed:
                preview = ", ".join(failed[:1])
                reason = f"{reason}; required checkpoints failed: {preview}"

        if ok:
            chain_score += difficulty
            print(f"  ✅ {task_id} (+{difficulty})")
        else:
            print(f"  ❌ {task_id}: {reason}")

        task_results.append(
            {
                "task_id": task_id,
                "difficulty": difficulty,
                "success": ok,
                "failure_reason": reason,
                "step_progress": checkpoint_eval.get("step_progress", 0.0),
                "step_score_percent": checkpoint_eval.get("step_score_percent", 0.0),
                "criteria_total": checkpoint_eval.get("criteria_total", 0),
                "criteria_passed": checkpoint_eval.get("criteria_passed", 0),
                "criteria_failed": checkpoint_eval.get("criteria_failed", []),
                "checkpoint_total": checkpoint_eval.get("checkpoint_total", 0),
            }
        )
        if stop_on_first_fail_task and not ok:
            remaining = len(scenario["steps"]) - executed_tasks
            if remaining > 0:
                print(f"  ⏭ Skipping remaining {remaining} tasks in chain due to first failure")
            break

    chain_success = all(t["success"] for t in task_results)
    return {
        "chain_id": chain_id,
        "theme": scenario.get("theme"),
        "success": chain_success,
        "score": chain_score,
        "max_score": chain_total,
        "executed_tasks": executed_tasks,
        "planned_tasks": len(scenario["steps"]),
        "tasks": task_results,
        "step_earned": chain_step_earned,
        "step_max": float(len(scenario["steps"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run task-flow benchmark using oracle traces")
    parser.add_argument("--limit-per-theme", type=int, default=20)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--themes",
        default="newcomer,daily,career,leisure,crisis",
        help="Comma-separated theme list",
    )
    parser.add_argument(
        "--summary-json",
        default="audit_chain_oracle_100_summary.json",
        help="Where to write structured report",
    )
    parser.add_argument(
        "--stop-on-first-fail-task",
        action="store_true",
        help="Stop remaining tasks in a chain after first failed task",
    )
    parser.add_argument(
        "--stop-on-first-fail",
        action="store_true",
        dest="stop_on_first_fail_task",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--task-timeout-sec",
        type=int,
        default=180,
        help="Per-task timeout in seconds to prevent benchmark hangs",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BENCHMARK_BASE_URL", "http://localhost:8014"),
        help="Base URL of benchmark server (e.g., http://localhost:8014)",
    )
    parser.add_argument(
        "--distractor-level",
        choices=["off", "low", "medium", "high"],
        default=os.environ.get("BENCHMARK_DISTRACTOR_LEVEL", "off"),
        help="Server-injected distractor intensity (reproducible with fixed seed)",
    )
    parser.add_argument(
        "--distractor-seed",
        type=int,
        default=_parse_int_env("BENCHMARK_DISTRACTOR_SEED", 20260220),
        help="Seed for distractor injection sampling",
    )
    parser.add_argument(
        "--obfuscation-seed",
        type=int,
        default=_parse_int_env("BENCHMARK_OBFUSCATION_SEED", 20260220),
        help="Seed for obfuscation ID generation",
    )
    parser.add_argument(
        "--clean-mode",
        dest="clean_mode",
        action="store_true",
        default=_parse_bool_env("BENCHMARK_CLEAN_MODE", True),
        help="Run oracle in clean mode (no injected distractors/overlays)",
    )
    parser.add_argument(
        "--no-clean-mode",
        dest="clean_mode",
        action="store_false",
        help="Disable clean mode",
    )
    parser.add_argument(
        "--obfuscate-mode",
        dest="obfuscate_mode",
        action="store_true",
        default=_parse_bool_env("BENCHMARK_OBFUSCATE", False),
        help="Enable DOM obfuscation mode during oracle run",
    )
    parser.add_argument(
        "--no-obfuscate-mode",
        dest="obfuscate_mode",
        action="store_false",
        help="Disable DOM obfuscation mode",
    )
    args = parser.parse_args()

    os.environ["BENCHMARK_DISTRACTOR_LEVEL"] = args.distractor_level
    os.environ["BENCHMARK_DISTRACTOR_SEED"] = str(args.distractor_seed)
    os.environ["BENCHMARK_OBFUSCATION_SEED"] = str(args.obfuscation_seed)
    os.environ["BENCHMARK_BASE_URL"] = _normalize_base_url(args.base_url)
    os.environ["BENCHMARK_CLEAN_MODE"] = "true" if args.clean_mode else "false"
    os.environ["BENCHMARK_OBFUSCATE"] = "true" if args.obfuscate_mode else "false"

    selected_themes = [t.strip() for t in args.themes.split(",") if t.strip()]
    selected_themes = [t for t in selected_themes if t in THEMES]

    started = time.time()
    chain_reports: List[dict] = []
    overall_score = 0
    overall_max = 0
    total_tasks = 0
    total_planned_tasks = 0
    passed_tasks = 0
    total_step_earned = 0.0
    total_step_max = 0.0

    for theme in selected_themes:
        scenarios = load_theme_scenarios(theme)
        if not scenarios:
            print(f"\n[skip] sampled_{theme}.json not found or empty")
            continue
        subset = scenarios[: args.limit_per_theme]
        print(f"\n{'#' * 60}\nTHEME: {theme.upper()} ({len(subset)} chains)\n{'#' * 60}")
        for scenario in subset:
            snapshot = FileSnapshot()
            try:
                report = run_chain(
                    scenario,
                    snapshot=snapshot,
                    headless=args.headless,
                    stop_on_first_fail_task=args.stop_on_first_fail_task,
                    task_timeout_sec=args.task_timeout_sec,
                    base_url=args.base_url,
                )
            finally:
                snapshot.restore_all()
            chain_reports.append(report)
            overall_score += report["score"]
            overall_max += report["max_score"]
            total_tasks += report["executed_tasks"]
            total_planned_tasks += report["planned_tasks"]
            passed_tasks += sum(1 for t in report["tasks"] if t["success"])
            total_step_earned += float(report.get("step_earned", 0.0))
            total_step_max += float(report.get("step_max", 0.0))

            step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
            task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
            flow_score = (
                sum(1 for c in chain_reports if c.get("success")) / len(chain_reports) * 100.0
                if chain_reports else 0.0
            )
            weighted_score = (overall_score / overall_max * 100.0) if overall_max else 0.0

            Path(args.summary_json).write_text(
                json.dumps(
                    {
                        "run_config": {
                            "clean_mode": os.environ.get("BENCHMARK_CLEAN_MODE", "false"),
                            "obfuscate_mode": os.environ.get("BENCHMARK_OBFUSCATE", "false"),
                            "distractor_level": args.distractor_level,
                            "distractor_seed": args.distractor_seed,
                            "obfuscation_seed": args.obfuscation_seed,
                            "base_url": _normalize_base_url(args.base_url),
                            "stop_on_first_fail_task": bool(args.stop_on_first_fail_task),
                            "task_timeout_sec": args.task_timeout_sec,
                            "themes": selected_themes,
                            "limit_per_theme": args.limit_per_theme,
                        },
                        "chains": chain_reports,
                        "overall_score": overall_score,
                        "overall_max": overall_max,
                        "total_tasks": total_tasks,
                        "passed_tasks": passed_tasks,
                        "total_planned_tasks": total_planned_tasks,
                        "total_step_earned": total_step_earned,
                        "total_step_max": total_step_max,
                        "metrics": {
                            "step_score": step_score,
                            "task_score": task_score,
                            "flow_score": flow_score,
                            "weighted_score": weighted_score,
                        },
                        "elapsed_sec": time.time() - started,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    passed_chains = sum(1 for c in chain_reports if c["success"])
    total_chains = len(chain_reports)
    step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
    task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
    flow_score = (passed_chains / total_chains * 100.0) if total_chains else 0.0
    normalized = (overall_score / overall_max * 100.0) if overall_max else 0.0
    elapsed = time.time() - started

    print(f"\n{'=' * 60}")
    print("ORACLE TASK-FLOW SUMMARY")
    print(f"{'=' * 60}")
    print(f"Chains: {passed_chains}/{total_chains} passed")
    print(f"Tasks:  {passed_tasks}/{total_planned_tasks} passed")
    print(f"Step Score: {step_score:.2f}/100")
    print(f"Task Score: {task_score:.2f}/100")
    print(f"Flow Score: {flow_score:.2f}/100")
    print(f"Weighted score: {overall_score}/{overall_max}")
    print(f"Normalized grade: {normalized:.2f}/100")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Summary JSON: {args.summary_json}")


if __name__ == "__main__":
    main()
