#!/usr/bin/env python3
import argparse
import copy
import json
import os
import random
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from chain_runner_oracle import (
    THEMES,
    FileSnapshot,
    _normalize_base_url,
    _parse_bool_env,
    _parse_int_env,
    inject_state,
    inject_state_delta,
    load_theme_scenarios,
    patch_spec,
    patch_trace,
    run_chain as run_chain_oracle,
)
from scenario_generator_v3 import PRECONDITION_KEYS


MUTATION_PRIORITY = [
    "card_frozen",
    "certified",
    "location",
    "energy_cost",
    "has_sub",
    "trip_booked",
    "commute_checked",
    "has_shop_delivered",
    "has_home",
    "has_bank",
    "has_mobile",
    "has_utility",
    "is_sick",
    "balance",
    "energy_level",
]

HIGH_IMPACT_KEYS = {
    "card_frozen",
    "pending_order",
    "certified",
    "energy_cost",
    "location",
    "is_sick",
    "has_bank",
    "has_home",
    "has_mobile",
    "has_utility",
    "has_sub",
    "has_shop_delivered",
    "trip_booked",
    "commute_checked",
    "has_invest",
    "balance",
    "has_mobile",
    "has_sub",
}

ADVERSARIAL_TARGETS: Dict[str, Any] = {
    "card_frozen": True,
    "pending_order": False,
    "has_sub": False,
    "has_shop_delivered": False,
    "has_invest": False,
    "commute_checked": False,
    "certified": False,
    "energy_cost": "high",
    "location": "suburb",
    "is_sick": True,
    "balance": 100.0,
}

TIMED_INTERVENTION_KEYS = {
    "card_frozen",
    "pending_order",
    "has_sub",
    "has_shop_delivered",
    "has_invest",
    "commute_checked",
    "certified",
    "is_sick",
    "trip_booked",
    "has_mobile",
}

KEY_IMPACT_BONUS = {
    "trip_booked": 8.0,
    "has_sub": 7.0,
    "balance": 7.0,
    "commute_checked": 6.0,
    "has_mobile": 6.0,
    "is_sick": 6.0,
    "has_shop_delivered": 6.0,
    "has_invest": 5.0,
    "pending_order": 5.0,
    "card_frozen": 4.0,
}


def _flip_value(key: str, value: Any):
    if isinstance(value, bool):
        return not value
    if key == "location":
        if str(value) == "city":
            return "suburb"
        if str(value) == "suburb":
            return "city"
    if key == "energy_cost":
        if str(value) == "low":
            return "high"
        if str(value) == "high":
            return "low"
    if key == "balance":
        try:
            val = float(value)
            return max(100.0, val * 0.5)
        except Exception:
            return value
    if key == "energy_level":
        try:
            val = int(value)
            return 20 if val >= 50 else 80
        except Exception:
            return value
    return value


def _collect_chain_state_keys(scenario: Dict[str, Any]) -> List[str]:
    keys: Set[str] = set()
    for step in scenario.get("steps", []) or []:
        dep = step.get("dependency_context") or {}
        for field in ("changed_state_keys", "conflict_keys"):
            vals = dep.get(field) or []
            if not isinstance(vals, list):
                continue
            for key in vals:
                if isinstance(key, str) and key:
                    keys.add(key)
    return sorted(keys)


def _collect_chain_precondition_keys(scenario: Dict[str, Any]) -> List[str]:
    keys: Set[str] = set()
    for step in scenario.get("steps", []) or []:
        task_id = str(step.get("task_id", ""))
        for key in PRECONDITION_KEYS.get(task_id, []):
            if isinstance(key, str) and key:
                keys.add(key)
    return sorted(keys)


def _mutable_candidates(keys: List[str], state: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in keys:
        if key not in state:
            continue
        before = state.get(key)
        after = _flip_value(key, before)
        if after != before:
            out.append(key)
    return out


def _precondition_hit_count(scenario: Dict[str, Any], key: str) -> int:
    if not key:
        return 0
    count = 0
    for step in scenario.get("steps", []) or []:
        task_id = str(step.get("task_id", ""))
        if key in PRECONDITION_KEYS.get(task_id, []):
            count += 1
    return count


def _weighted_pick_key(keys: List[str], rng: random.Random, impact_profile: str, scenario: Dict[str, Any]) -> str:
    if not keys:
        return ""
    if len(keys) == 1:
        return keys[0]

    if impact_profile == "strong":
        weights: List[float] = []
        for key in keys:
            pre_hits = _precondition_hit_count(scenario, key)
            weight = 1.0 + pre_hits * 2.0
            weight += KEY_IMPACT_BONUS.get(key, 0.0)
            if key in HIGH_IMPACT_KEYS:
                weight += 2.0
            elif key in MUTATION_PRIORITY:
                weight += 0.8
            weights.append(max(weight, 0.1))
        return rng.choices(keys, weights=weights, k=1)[0]

    return rng.choice(keys)


def _find_first_precondition_step(scenario: Dict[str, Any], key: str) -> int:
    if not key:
        return -1
    for idx, step in enumerate(scenario.get("steps", []) or []):
        task_id = str(step.get("task_id", ""))
        if key in PRECONDITION_KEYS.get(task_id, []):
            return idx
    return -1


def _choose_after_value(key: str, before: Any, impact_profile: str) -> Any:
    if impact_profile == "strong" and key in ADVERSARIAL_TARGETS:
        return ADVERSARIAL_TARGETS[key]
    return _flip_value(key, before)


def mutate_initial_state(
    initial_state: Dict[str, Any],
    scenario: Dict[str, Any],
    rng: random.Random,
    target_key: str = "",
    preferred_keys: List[str] = None,
    impact_profile: str = "balanced",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    mutated = dict(initial_state or {})
    if not mutated:
        return mutated, {"key": "", "before": None, "after": None, "scope": "none"}

    chosen_key = ""
    scope = "fallback"
    if target_key:
        candidates = [target_key] if target_key in mutated else []
        mutable = _mutable_candidates(candidates, mutated)
        if mutable:
            chosen_key = mutable[0]
            scope = "targeted"
    else:
        precondition_keys = _collect_chain_precondition_keys(scenario)
        preferred = [k for k in (preferred_keys or []) if k in mutated]
        if impact_profile == "strong":
            precondition_mutable = _mutable_candidates([k for k in precondition_keys if k in mutated], mutated)
            effective_precondition = [k for k in precondition_mutable if k in KEY_IMPACT_BONUS]
            if effective_precondition:
                chosen_key = _weighted_pick_key(effective_precondition, rng, impact_profile, scenario)
                scope = "precondition_effective"
            elif precondition_mutable:
                chosen_key = _weighted_pick_key(precondition_mutable, rng, impact_profile, scenario)
                scope = "precondition"
        preferred_mutable = _mutable_candidates(preferred, mutated)
        if not chosen_key and preferred_mutable:
            chosen_key = _weighted_pick_key(preferred_mutable, rng, impact_profile, scenario)
            scope = "preferred"
        if not chosen_key:
            ordered = [k for k in MUTATION_PRIORITY if k in mutated]
            others = [k for k in mutated.keys() if k not in ordered]
            rng.shuffle(others)
            fallback = ordered + others
            fallback_mutable = _mutable_candidates(fallback, mutated)
            if fallback_mutable:
                chosen_key = _weighted_pick_key(fallback_mutable, rng, impact_profile, scenario)

    if not chosen_key:
        return mutated, {"key": "", "before": None, "after": None, "scope": "none"}

    before = mutated.get(chosen_key)
    intervention_step = _find_first_precondition_step(scenario, chosen_key)
    use_timed_intervention = (
        impact_profile == "strong" and chosen_key in TIMED_INTERVENTION_KEYS and intervention_step >= 1
    )
    after = _choose_after_value(chosen_key, before, impact_profile)

    if not use_timed_intervention:
        if after == before:
            after = _flip_value(chosen_key, before)
        if after == before:
            return mutated, {"key": "", "before": None, "after": None, "scope": "none"}
        mutated[chosen_key] = after
        return mutated, {
            "key": chosen_key,
            "before": before,
            "after": after,
            "scope": scope,
            "injection_mode": "initial",
            "intervention_step": -1,
            "intervention_task_id": "",
        }

    task_id = ""
    try:
        task_id = str((scenario.get("steps") or [])[intervention_step].get("task_id", ""))
    except Exception:
        task_id = ""
    return mutated, {
        "key": chosen_key,
        "before": before,
        "after": after,
        "scope": "timed_precondition",
        "injection_mode": "timed",
        "intervention_step": intervention_step,
        "intervention_task_id": task_id,
    }


def _count_passed_tasks(report: Dict[str, Any]) -> int:
    return sum(1 for t in report.get("tasks", []) if t.get("success"))


def _step_score_percent(report: Dict[str, Any]) -> float:
    step_max = float(report.get("step_max", 0.0) or 0.0)
    step_earned = float(report.get("step_earned", 0.0) or 0.0)
    if step_max <= 0:
        return 0.0
    return step_earned / step_max * 100.0


def _first_divergence(baseline_tasks: List[Dict[str, Any]], counter_tasks: List[Dict[str, Any]]) -> int:
    n = min(len(baseline_tasks), len(counter_tasks))
    for i in range(n):
        b = baseline_tasks[i]
        c = counter_tasks[i]
        if bool(b.get("success")) != bool(c.get("success")):
            return i + 1
        if abs(float(b.get("step_progress", 0.0)) - float(c.get("step_progress", 0.0))) > 1e-9:
            return i + 1
    if len(baseline_tasks) != len(counter_tasks):
        return n + 1
    return 0


def _trace_plan(task_id: str, base_url: str) -> Tuple[int, str]:
    trace_path = Path("tasks") / task_id / "oracle_trace.json"
    default_url = f"{_normalize_base_url(base_url)}/shop.local/index.html"
    if not trace_path.exists():
        return 0, default_url
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception:
        return 0, default_url

    steps = trace.get("steps", []) if isinstance(trace, dict) else []
    expected_steps = len(steps) if isinstance(steps, list) else 0
    start_url = default_url
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("act") == "open" and step.get("url"):
                start_url = str(step.get("url"))
                break
    return expected_steps, start_url


def _run_agent_task(
    task_id: str,
    start_url: str,
    headless: bool,
    max_steps: int,
    repeat_fail_threshold: int,
    stop_on_first_fail_step: bool,
    task_timeout_sec: int,
) -> Tuple[bool, str, Dict[str, Any]]:
    result_path = Path("output") / task_id / "agent_result.json"
    if result_path.exists():
        result_path.unlink()

    cmd = [
        "python3",
        "llm_runner.py",
        task_id,
        "--start_url",
        start_url,
        "--max_steps",
        str(max_steps),
        "--repeat-fail-threshold",
        str(repeat_fail_threshold),
    ]
    if stop_on_first_fail_step:
        cmd.append("--stop-on-first-fail-step")
    if headless:
        cmd.append("--headless")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=task_timeout_sec)
        combined = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"task timeout after {task_timeout_sec}s", {}

    agent_result: Dict[str, Any] = {}
    if result_path.exists():
        try:
            agent_result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            agent_result = {}

    task_ok = bool(agent_result.get("success")) if agent_result else ("TASK PASSED" in combined)
    if task_ok:
        return True, "", agent_result

    end_reason = str(agent_result.get("end_reason", "")).strip() if agent_result else ""
    step_err = str(agent_result.get("step_error_message", "") or agent_result.get("last_step_status", "")).strip() if agent_result else ""
    if end_reason:
        return False, end_reason, agent_result
    if step_err:
        return False, step_err, agent_result

    fail_lines = [ln for ln in combined.splitlines() if ("FAIL" in ln or "Error" in ln or "Aborting" in ln)]
    if fail_lines:
        return False, fail_lines[-1], agent_result
    return False, "agent returned failure", agent_result


def _parse_agent_step_progress(agent_result: Dict[str, Any], task_ok: bool, expected_steps: int) -> Tuple[float, float]:
    checkpoint_score_percent = agent_result.get("checkpoint_score_percent")
    if isinstance(checkpoint_score_percent, str):
        try:
            checkpoint_score_percent = float(checkpoint_score_percent)
        except Exception:
            checkpoint_score_percent = None
    if isinstance(checkpoint_score_percent, (int, float)):
        pct = max(0.0, min(float(checkpoint_score_percent), 100.0))
        return pct / 100.0, pct

    if task_ok:
        return 1.0, 100.0

    steps_executed = 0
    try:
        steps_executed = int(agent_result.get("steps_executed", 0))
    except Exception:
        steps_executed = 0
    if expected_steps > 0:
        progress = min(max(steps_executed, 0) / float(expected_steps), 1.0)
        return progress, progress * 100.0
    return 0.0, 0.0


def run_chain_agent(
    scenario: Dict[str, Any],
    snapshot: FileSnapshot,
    headless: bool,
    stop_on_first_fail_task: bool,
    stop_on_first_fail_step: bool,
    repeat_fail_threshold: int,
    max_steps: int,
    task_timeout_sec: int,
    base_url: str,
    step_pre_hook=None,
) -> Dict[str, Any]:
    chain_id = str(scenario.get("chain_id", ""))
    print(f"\n▶ Running Chain [{chain_id}] (agent)")

    subprocess.run(["python3", "init_db.py"], check=True, stdout=subprocess.DEVNULL)
    state_path = Path("env/state.json")
    if state_path.exists():
        state_path.unlink()
    inject_state(scenario.get("initial_state") or {}, base_url=base_url)

    chain_total = sum(int(s.get("difficulty", 1)) for s in scenario.get("steps", []))
    chain_score = 0
    chain_step_earned = 0.0
    task_results: List[Dict[str, Any]] = []
    executed_tasks = 0

    for step_idx, step in enumerate(scenario.get("steps", [])):
        if step_pre_hook is not None:
            try:
                step_pre_hook(step_idx, step)
            except Exception as exc:
                print(f"[warn] step_pre_hook failed at step {step_idx}: {exc}")

        task_id = str(step.get("task_id", ""))
        difficulty = int(step.get("difficulty", 1))
        patch_trace(task_id, str(step.get("instruction", "")), snapshot, step.get("success_criteria", []), base_url=base_url)
        patch_spec(
            task_id,
            str(step.get("instruction", "")),
            step.get("success_criteria", []),
            snapshot,
            scoring_checkpoints=(step.get("scoring_checkpoints") or step.get("checkpoints") or []),
        )

        expected_steps, start_url = _trace_plan(task_id, base_url)
        ok, reason, agent_result = _run_agent_task(
            task_id=task_id,
            start_url=start_url,
            headless=headless,
            max_steps=max_steps,
            repeat_fail_threshold=repeat_fail_threshold,
            stop_on_first_fail_step=stop_on_first_fail_step,
            task_timeout_sec=task_timeout_sec,
        )
        executed_tasks += 1
        step_progress, step_score_percent = _parse_agent_step_progress(agent_result, ok, expected_steps)
        chain_step_earned += step_progress

        if ok:
            chain_score += difficulty
            print(f"  ✅ {task_id} (+{difficulty})")
        else:
            print(f"  ❌ {task_id}: {reason}")

        task_results.append(
            {
                "task_id": task_id,
                "difficulty": difficulty,
                "success": bool(ok),
                "failure_reason": reason,
                "step_progress": step_progress,
                "step_score_percent": step_score_percent,
                "end_reason": str(agent_result.get("end_reason", "")) if agent_result else "",
                "steps_executed": int(agent_result.get("steps_executed", 0) or 0) if agent_result else 0,
                "expected_steps": expected_steps,
            }
        )
        if stop_on_first_fail_task and not ok:
            remaining = len(scenario.get("steps", [])) - executed_tasks
            if remaining > 0:
                print(f"  ⏭ Skipping remaining {remaining} tasks in chain due to first failure")
            break

    chain_success = all(t.get("success") for t in task_results) if task_results else False
    return {
        "chain_id": chain_id,
        "theme": scenario.get("theme"),
        "success": chain_success,
        "score": chain_score,
        "max_score": chain_total,
        "executed_tasks": executed_tasks,
        "planned_tasks": len(scenario.get("steps", [])),
        "tasks": task_results,
        "step_earned": chain_step_earned,
        "step_max": float(len(scenario.get("steps", []))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run counterfactual benchmark by mutating chain initial state")
    parser.add_argument("--mode", choices=["oracle", "agent"], default="oracle")
    parser.add_argument("--limit-per-theme", type=int, default=20)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--themes", default="newcomer,daily,career,leisure,crisis")
    parser.add_argument("--summary-json", default="audit_chain_counterfactual.json")
    parser.add_argument("--task-timeout-sec", type=int, default=180)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--repeat-fail-threshold", type=int, default=3)
    parser.add_argument(
        "--stop-on-first-fail-step",
        dest="stop_on_first_fail_step",
        action="store_true",
        default=True,
        help="In agent mode, abort task when one step action fails",
    )
    parser.add_argument(
        "--no-stop-on-first-fail-step",
        dest="stop_on_first_fail_step",
        action="store_false",
        help="In agent mode, continue task even if one step action fails",
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
    )
    parser.add_argument("--distractor-seed", type=int, default=_parse_int_env("BENCHMARK_DISTRACTOR_SEED", 20260220))
    parser.add_argument("--obfuscation-seed", type=int, default=_parse_int_env("BENCHMARK_OBFUSCATION_SEED", 20260220))
    parser.add_argument(
        "--clean-mode",
        dest="clean_mode",
        action="store_true",
        default=_parse_bool_env("BENCHMARK_CLEAN_MODE", True),
    )
    parser.add_argument("--no-clean-mode", dest="clean_mode", action="store_false")
    parser.add_argument(
        "--obfuscate-mode",
        dest="obfuscate_mode",
        action="store_true",
        default=_parse_bool_env("BENCHMARK_OBFUSCATE", False),
    )
    parser.add_argument("--no-obfuscate-mode", dest="obfuscate_mode", action="store_false")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-key", default="", help="Force mutation on one initial_state key")
    parser.add_argument(
        "--impact-profile",
        choices=["balanced", "strong"],
        default="balanced",
        help="Counterfactual mutation strength profile",
    )
    args = parser.parse_args()

    os.environ["BENCHMARK_DISTRACTOR_LEVEL"] = args.distractor_level
    os.environ["BENCHMARK_DISTRACTOR_SEED"] = str(args.distractor_seed)
    os.environ["BENCHMARK_OBFUSCATION_SEED"] = str(args.obfuscation_seed)
    os.environ["BENCHMARK_BASE_URL"] = _normalize_base_url(args.base_url)
    os.environ["BENCHMARK_CLEAN_MODE"] = "true" if args.clean_mode else "false"
    os.environ["BENCHMARK_OBFUSCATE"] = "true" if args.obfuscate_mode else "false"

    rng = random.Random(args.seed)
    selected_themes = [t.strip() for t in args.themes.split(",") if t.strip() and t.strip() in THEMES]

    started = time.time()
    comparisons: List[Dict[str, Any]] = []
    baseline_pass_tasks = 0
    baseline_total_tasks = 0
    counter_pass_tasks = 0
    counter_total_tasks = 0
    baseline_weighted_earned = 0.0
    baseline_weighted_max = 0.0
    counter_weighted_earned = 0.0
    counter_weighted_max = 0.0
    task_drop_sum = 0.0
    step_drop_sum = 0.0
    impacted = 0
    diverged = 0

    for theme in selected_themes:
        scenarios = load_theme_scenarios(theme)
        if not scenarios:
            print(f"\n[skip] sampled_{theme}.json not found or empty")
            continue
        subset = scenarios[: args.limit_per_theme]
        print(f"\n{'#' * 60}\nCOUNTERFACTUAL THEME: {theme.upper()} ({len(subset)} chains)\n{'#' * 60}")

        for scenario in subset:
            base_snapshot = FileSnapshot()
            try:
                if args.mode == "oracle":
                    base_report = run_chain_oracle(
                        scenario,
                        snapshot=base_snapshot,
                        headless=args.headless,
                        stop_on_first_fail_task=False,
                        task_timeout_sec=args.task_timeout_sec,
                        base_url=args.base_url,
                    )
                else:
                    base_report = run_chain_agent(
                        scenario,
                        snapshot=base_snapshot,
                        headless=args.headless,
                        stop_on_first_fail_task=False,
                        stop_on_first_fail_step=args.stop_on_first_fail_step,
                        repeat_fail_threshold=args.repeat_fail_threshold,
                        max_steps=args.max_steps,
                        task_timeout_sec=args.task_timeout_sec,
                        base_url=args.base_url,
                    )
            finally:
                base_snapshot.restore_all()

            preferred_keys = sorted(
                set(_collect_chain_state_keys(scenario)) | set(_collect_chain_precondition_keys(scenario))
            )
            mutated_state, mutation = mutate_initial_state(
                scenario.get("initial_state") or {},
                scenario,
                rng,
                target_key=args.target_key,
                preferred_keys=preferred_keys,
                impact_profile=args.impact_profile,
            )
            cf_scenario = copy.deepcopy(scenario)
            cf_scenario["chain_id"] = f"{scenario.get('chain_id')}-CF"
            cf_scenario["initial_state"] = mutated_state
            step_pre_hook = None
            if str(mutation.get("injection_mode", "")) == "timed":
                intervention_step = int(mutation.get("intervention_step", -1) or -1)
                key = str(mutation.get("key", ""))
                after_val = mutation.get("after")
                did_inject = {"done": False}

                def _hook(step_idx: int, _step: Dict[str, Any]):
                    if did_inject["done"]:
                        return
                    if step_idx != intervention_step:
                        return
                    if not key:
                        return
                    inject_state_delta({key: after_val}, base_url=args.base_url)
                    did_inject["done"] = True

                step_pre_hook = _hook
            cf_snapshot = FileSnapshot()
            try:
                if args.mode == "oracle":
                    cf_report = run_chain_oracle(
                        cf_scenario,
                        snapshot=cf_snapshot,
                        headless=args.headless,
                        stop_on_first_fail_task=False,
                        task_timeout_sec=args.task_timeout_sec,
                        base_url=args.base_url,
                        step_pre_hook=step_pre_hook,
                    )
                else:
                    cf_report = run_chain_agent(
                        cf_scenario,
                        snapshot=cf_snapshot,
                        headless=args.headless,
                        stop_on_first_fail_task=False,
                        stop_on_first_fail_step=args.stop_on_first_fail_step,
                        repeat_fail_threshold=args.repeat_fail_threshold,
                        max_steps=args.max_steps,
                        task_timeout_sec=args.task_timeout_sec,
                        base_url=args.base_url,
                        step_pre_hook=step_pre_hook,
                    )
            finally:
                cf_snapshot.restore_all()

            b_tasks = _count_passed_tasks(base_report)
            c_tasks = _count_passed_tasks(cf_report)
            b_total = len(base_report.get("tasks", []))
            c_total = len(cf_report.get("tasks", []))
            b_weighted_score = float(base_report.get("score", 0.0) or 0.0)
            b_weighted_max = float(base_report.get("max_score", 0.0) or 0.0)
            c_weighted_score = float(cf_report.get("score", 0.0) or 0.0)
            c_weighted_max = float(cf_report.get("max_score", 0.0) or 0.0)
            b_step = _step_score_percent(base_report)
            c_step = _step_score_percent(cf_report)
            task_drop = float(b_tasks - c_tasks)
            step_drop = float(b_step - c_step)
            divergence_at = _first_divergence(base_report.get("tasks", []), cf_report.get("tasks", []))
            is_impacted = task_drop > 0 or step_drop > 1e-9 or (bool(base_report.get("success")) and not bool(cf_report.get("success")))
            is_diverged = divergence_at > 0

            baseline_pass_tasks += b_tasks
            baseline_total_tasks += b_total
            counter_pass_tasks += c_tasks
            counter_total_tasks += c_total
            baseline_weighted_earned += b_weighted_score
            baseline_weighted_max += b_weighted_max
            counter_weighted_earned += c_weighted_score
            counter_weighted_max += c_weighted_max
            task_drop_sum += task_drop
            step_drop_sum += step_drop
            if is_impacted:
                impacted += 1
            if is_diverged:
                diverged += 1

            comparisons.append(
                {
                    "chain_id": scenario.get("chain_id"),
                    "theme": theme,
                    "mutation": mutation,
                    "baseline": {
                        "success": bool(base_report.get("success")),
                        "passed_tasks": b_tasks,
                        "total_tasks": b_total,
                        "step_score_percent": b_step,
                    },
                    "counterfactual": {
                        "success": bool(cf_report.get("success")),
                        "passed_tasks": c_tasks,
                        "total_tasks": c_total,
                        "step_score_percent": c_step,
                    },
                    "delta": {
                        "task_drop": task_drop,
                        "step_drop": step_drop,
                        "first_divergence_step": divergence_at,
                    },
                    "impacted": is_impacted,
                    "diverged": is_diverged,
                }
            )

            total_chains = len(comparisons)
            summary = {
                "run_config": {
                    "themes": selected_themes,
                    "mode": args.mode,
                    "limit_per_theme": args.limit_per_theme,
                    "seed": args.seed,
                    "target_key": args.target_key,
                    "impact_profile": args.impact_profile,
                    "max_steps": args.max_steps,
                    "repeat_fail_threshold": args.repeat_fail_threshold,
                    "stop_on_first_fail_step": args.stop_on_first_fail_step,
                    "clean_mode": os.environ.get("BENCHMARK_CLEAN_MODE", "false"),
                    "obfuscate_mode": os.environ.get("BENCHMARK_OBFUSCATE", "false"),
                    "distractor_level": args.distractor_level,
                    "distractor_seed": args.distractor_seed,
                    "obfuscation_seed": args.obfuscation_seed,
                    "base_url": _normalize_base_url(args.base_url),
                },
                "comparisons": comparisons,
                "metrics": {
                    "chains_total": total_chains,
                    "chains_impacted": impacted,
                    "impact_rate": (impacted / total_chains * 100.0) if total_chains else 0.0,
                    "chains_diverged": diverged,
                    "divergence_rate": (diverged / total_chains * 100.0) if total_chains else 0.0,
                    "baseline_task_score": (baseline_pass_tasks / baseline_total_tasks * 100.0) if baseline_total_tasks else 0.0,
                    "counterfactual_task_score": (counter_pass_tasks / counter_total_tasks * 100.0) if counter_total_tasks else 0.0,
                    "baseline_weighted_earned": baseline_weighted_earned,
                    "baseline_weighted_max": baseline_weighted_max,
                    "baseline_weighted_score": (baseline_weighted_earned / baseline_weighted_max * 100.0)
                    if baseline_weighted_max
                    else 0.0,
                    "counterfactual_weighted_earned": counter_weighted_earned,
                    "counterfactual_weighted_max": counter_weighted_max,
                    "counterfactual_weighted_score": (counter_weighted_earned / counter_weighted_max * 100.0)
                    if counter_weighted_max
                    else 0.0,
                    "avg_task_drop": (task_drop_sum / total_chains) if total_chains else 0.0,
                    "avg_step_drop": (step_drop_sum / total_chains) if total_chains else 0.0,
                },
                "elapsed_sec": time.time() - started,
            }
            Path(args.summary_json).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    final = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))
    metrics = final.get("metrics", {})
    print(f"\n{'=' * 60}")
    print("COUNTERFACTUAL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Chains impacted: {metrics.get('chains_impacted', 0)}/{metrics.get('chains_total', 0)}")
    print(f"Impact rate: {metrics.get('impact_rate', 0.0):.2f}%")
    print(f"Chains diverged: {metrics.get('chains_diverged', 0)}/{metrics.get('chains_total', 0)}")
    print(f"Divergence rate: {metrics.get('divergence_rate', 0.0):.2f}%")
    print(f"Baseline task score: {metrics.get('baseline_task_score', 0.0):.2f}")
    print(f"Counterfactual task score: {metrics.get('counterfactual_task_score', 0.0):.2f}")
    print(
        "Baseline weighted score: "
        f"{metrics.get('baseline_weighted_earned', 0.0):.0f}/{metrics.get('baseline_weighted_max', 0.0):.0f} "
        f"({metrics.get('baseline_weighted_score', 0.0):.2f}%)"
    )
    print(
        "Counterfactual weighted score: "
        f"{metrics.get('counterfactual_weighted_earned', 0.0):.0f}/{metrics.get('counterfactual_weighted_max', 0.0):.0f} "
        f"({metrics.get('counterfactual_weighted_score', 0.0):.2f}%)"
    )
    print(f"Avg task drop: {metrics.get('avg_task_drop', 0.0):.4f}")
    print(f"Avg step drop: {metrics.get('avg_step_drop', 0.0):.4f}")
    print(f"Summary JSON: {args.summary_json}")


if __name__ == "__main__":
    main()
