#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_ROOT = ROOT / "tasks"
DEFAULT_BATCH_ROOT = TASKS_ROOT / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_MODULES = TASKS_ROOT / "workflow_module_library.json"
DEFAULT_BINDINGS = TASKS_ROOT / "workflow_module_bindings.json"

sys.path.insert(0, str(ROOT))

from agent.llm_client import build_client  # noqa: E402
from llm_runner import execute_agent_task  # noqa: E402


def _load_local_helper(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load local helper module from {SCRIPT_DIR / filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


try:
    from rl_memory.scripts.evaluate_workflow_episode import evaluate_episode  # noqa: E402
except ModuleNotFoundError:
    evaluate_episode = _load_local_helper(
        "_workflow_eval_local",
        "evaluate_workflow_episode.py",
    ).evaluate_episode

try:
    from rl_memory.scripts.run_workflow_episode import (  # noqa: E402
        apply_effects,
        dump_json,
        instantiate_atomic_task,
        load_json,
    )
except ModuleNotFoundError:
    _workflow_episode = _load_local_helper("_workflow_episode_local", "run_workflow_episode.py")
    apply_effects = _workflow_episode.apply_effects
    dump_json = _workflow_episode.dump_json
    instantiate_atomic_task = _workflow_episode.instantiate_atomic_task
    load_json = _workflow_episode.load_json


MODULE_CHOOSER_SYSTEM_PROMPT = """You are a workflow planner for a web agent benchmark.
Choose exactly one next workflow module from the provided candidate list.
Rules:
1. Prefer modules that legally advance the remaining target state.
2. Do not choose a module whose preconditions are not currently satisfied unless no executable candidate exists.
3. Avoid repeating already failed modules.
4. The candidate list is already sorted from most to least promising. Prefer the earliest executable candidate that directly satisfies a remaining target predicate.
4. Output exactly one token: a MODULE_ID from the candidate list, or DONE.
Do not explain your reasoning."""

RUNTIME_ISOLATION_NOTES = {
    "per_goal": (
        "Each goal runs in its own runtime root and server. "
        "Use this mode for official benchmark numbers."
    ),
    "shared": (
        "Shared runtime/server reuse is debug-only and can contaminate results across goals. "
        "Do not use shared-mode results as official benchmark numbers."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run workflow benchmark episodes with module-level planning and atomic execution.")
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--split", choices=["train", "dev", "test"], default="dev")
    parser.add_argument("--goal-id", action="append", default=[], help="Specific goal id to run. Can be passed multiple times.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of goals to run after filtering.")
    parser.add_argument("--modules", default=str(DEFAULT_MODULES))
    parser.add_argument("--bindings", default=str(DEFAULT_BINDINGS))
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--runtime-root", default=".", help="Runtime root whose data.db/env/state.json will be restored between episodes.")
    parser.add_argument("--module-policy", choices=["llm", "heuristic", "reference"], default="llm")
    parser.add_argument("--atomic-policy", choices=["agent", "dry_run"], default="agent")
    parser.add_argument("--candidate-limit", type=int, default=12)
    parser.add_argument("--target-backward-depth", type=int, default=2)
    parser.add_argument("--module-max-tokens", type=int, default=32)
    parser.add_argument("--module-temperature", type=float, default=0.0)
    parser.add_argument("--atomic-max-steps", type=int, default=25)
    parser.add_argument("--atomic-repeat-fail-threshold", type=int, default=3)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--runtime-isolation",
        choices=["per_goal", "shared"],
        default="per_goal",
        help="Runtime isolation mode. Use `per_goal` for official results; `shared` is debug-only.",
    )
    return parser.parse_args()


def _alloc_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _prepare_goal_runtime(runtime_root: Path, snapshot_root: Path) -> None:
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "tasks").mkdir(parents=True, exist_ok=True)
    (runtime_root / "output").mkdir(parents=True, exist_ok=True)

    def _ignore_transient_files(_src: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if (
                name == ".DS_Store"
                or name.startswith(".~")
                or name.startswith(".nfs")
                or name.endswith("~")
                or name.endswith(".swp")
                or name.endswith(".swo")
                or name.endswith(".tmp")
            ):
                ignored.add(name)
        return ignored

    shutil.copytree(ROOT / "env", runtime_root / "env", dirs_exist_ok=True, ignore=_ignore_transient_files)
    sites_dst = runtime_root / "sites"
    try:
        sites_dst.symlink_to(ROOT / "sites", target_is_directory=True)
    except OSError:
        shutil.copytree(ROOT / "sites", sites_dst, dirs_exist_ok=True, ignore=_ignore_transient_files)

    restore_runtime(runtime_root, snapshot_root)


def _start_goal_server(runtime_root: Path, server_log_path: Path) -> tuple[subprocess.Popen[str], str]:
    port = _alloc_port()
    base_url = f"http://127.0.0.1:{port}"
    server_log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(server_log_path, "a", encoding="utf-8")
    env = os.environ.copy()
    env["WEBAGENT_RUNTIME_ROOT"] = str(runtime_root)
    env["WEBAGENT_SERVER_PORT"] = str(port)
    env["WEBAGENT_SERVER_BASE_URL"] = base_url
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py"), str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.time() + 20
    last_error = "server did not respond"
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Goal server exited early for {runtime_root}. "
                f"See log: {server_log_path}"
            )
        try:
            with urlopen(f"{base_url}/api/env", timeout=1) as resp:
                if 200 <= getattr(resp, "status", 200) < 500:
                    return proc, base_url
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.2)

    proc.terminate()
    raise RuntimeError(
        f"Timed out waiting for goal server at {base_url}: {last_error}. "
        f"See log: {server_log_path}"
    )


@contextmanager
def _temporary_process_env(updates: dict[str, str]):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _pushd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def preconditions_satisfied(requires: dict[str, Any], state: set[str]) -> bool:
    all_of = set(requires.get("all_of", []))
    any_of = set(requires.get("any_of", []))
    none_of = set(requires.get("none_of", []))
    if not all_of.issubset(state):
        return False
    if any_of and not (any_of & state):
        return False
    if none_of & state:
        return False
    return True


def missing_preconditions(requires: dict[str, Any], state: set[str]) -> set[str]:
    missing = set(requires.get("all_of", [])) - state
    any_of = set(requires.get("any_of", []))
    if any_of and not (any_of & state):
        missing |= any_of
    return missing


def exception_payload(exc: Exception) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def summarize_atomic_result(task_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": bool(task_result.get("success")),
        "end_reason": task_result.get("end_reason", ""),
        "failure_category": task_result.get("failure_category", ""),
        "steps_executed": int(task_result.get("steps_executed", 0) or 0),
        "criteria_total": int(task_result.get("criteria_total", 0) or 0),
        "criteria_passed": int(task_result.get("criteria_passed", 0) or 0),
        "checkpoint_total": int(task_result.get("checkpoint_total", 0) or 0),
        "checkpoint_passed": int(task_result.get("checkpoint_passed", 0) or 0),
        "checkpoint_required_total": int(task_result.get("checkpoint_required_total", 0) or 0),
        "checkpoint_required_passed": int(task_result.get("checkpoint_required_passed", 0) or 0),
        "checkpoint_weight_earned": float(task_result.get("checkpoint_weight_earned", 0.0) or 0.0),
        "checkpoint_score_percent": task_result.get("checkpoint_score_percent"),
        "verify_error": task_result.get("verify_error", ""),
        "step_error_message": task_result.get("step_error_message", ""),
        "raw_output_tail": str(task_result.get("raw_output", "") or "")[-4000:],
    }


def build_candidate_trace_payload(
    module: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    needed_predicates: set[str],
    theme: str,
    *,
    score: float,
    executable: bool,
    reachable: bool,
) -> dict[str, Any]:
    adds = set(module.get("effects", {}).get("adds", []))
    direct_hits = adds & remaining_targets
    support_hits = adds & (needed_predicates - remaining_targets)
    return {
        "module_id": module["module_id"],
        "name": module.get("name", module["module_id"]),
        "family": module.get("family", ""),
        "theme_match": module.get("family") == theme,
        "requires": {
            "all_of": list(module.get("requires", {}).get("all_of", []) or []),
            "any_of": list(module.get("requires", {}).get("any_of", []) or []),
            "none_of": list(module.get("requires", {}).get("none_of", []) or []),
        },
        "adds": sorted(adds),
        "direct_target_hits": sorted(direct_hits),
        "support_target_hits": sorted(support_hits),
        "missing_preconditions": sorted(missing_preconditions(module.get("requires", {}), state)),
        "executable": executable,
        "reachable_within_remaining_budget": reachable,
        "score": score,
        "estimated_steps": int(module.get("constraints", {}).get("estimated_steps", 0) or 0),
        "budget_delta": float(module.get("constraints", {}).get("budget_delta", 0.0) or 0.0),
    }


def remap_runtime_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    target_base = os.environ.get("WEBAGENT_SERVER_BASE_URL", "").strip()
    if not target_base:
        return raw
    try:
        parsed = urlsplit(raw)
        source = urlsplit("http://localhost:8014")
        target = urlsplit(target_base)
    except Exception:
        return raw
    if parsed.scheme not in {"http", "https"}:
        return raw
    if parsed.netloc == source.netloc and target.netloc:
        return urlunsplit((target.scheme or parsed.scheme, target.netloc, parsed.path, parsed.query, parsed.fragment))
    return raw


def infer_start_url(oracle_trace_path: Path) -> str:
    if not oracle_trace_path.exists():
        return remap_runtime_url("http://localhost:8014/shop.local/index.html")
    oracle = load_json(oracle_trace_path)
    for step in oracle.get("steps", []):
        if step.get("act") == "open" and step.get("url"):
            return remap_runtime_url(str(step["url"]))
    return remap_runtime_url("http://localhost:8014/shop.local/index.html")


def collect_goals(batch_root: Path, split: str, goal_ids: list[str], limit: int) -> list[dict[str, Any]]:
    split_root = batch_root / split
    manifest = load_json(split_root / "manifest.json")
    refs = manifest.get("goals", [])
    if goal_ids:
        goal_id_set = set(goal_ids)
        refs = [item for item in refs if item["goal_id"] in goal_id_set]
    if limit > 0:
        refs = refs[:limit]
    return refs


def build_indices(modules_doc: dict[str, Any], bindings_doc: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    modules_by_id = {item["module_id"]: item for item in modules_doc["modules"]}
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings_doc["bindings"]:
        bindings_by_module[binding["module_id"]].append(binding)
    return modules_by_id, dict(bindings_by_module)


def allowed_modules_from_oracle(oracle: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for path in oracle.get("success_paths", []):
        allowed.update(path.get("required_modules", []) or [])
        allowed.update(path.get("optional_modules", []) or [])
    for invocation in oracle.get("reference_invocations", []):
        module_id = invocation.get("module_id")
        if module_id:
            allowed.add(module_id)
    return allowed


def compute_needed_predicates(
    modules_doc: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    depth: int,
    allowed_module_ids: set[str] | None = None,
) -> set[str]:
    modules = modules_doc["modules"]
    needed = set(remaining_targets)
    frontier = set(remaining_targets)
    for _ in range(max(0, depth)):
        new_preds: set[str] = set()
        for module in modules:
            if allowed_module_ids and module["module_id"] not in allowed_module_ids:
                continue
            adds = set(module.get("effects", {}).get("adds", []))
            if not adds & frontier:
                continue
            requires = module.get("requires", {})
            new_preds |= (set(requires.get("all_of", [])) - state)
            any_of = set(requires.get("any_of", []))
            if any_of and not (any_of & state):
                new_preds |= any_of
        new_preds -= needed
        if not new_preds:
            break
        needed |= new_preds
        frontier = new_preds
    return needed


def score_module_candidate(
    module: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    needed_predicates: set[str],
    theme: str,
) -> tuple[float, bool]:
    adds = set(module.get("effects", {}).get("adds", []))
    requires = module.get("requires", {})
    executable = preconditions_satisfied(requires, state)
    direct_hits = adds & remaining_targets
    support_hits = adds & (needed_predicates - remaining_targets)
    score = 0.0
    score += 12.0 * len(direct_hits)
    score += 3.0 * len(support_hits)
    if module.get("family") == theme:
        score += 0.75
    if executable:
        score += 2.0
    else:
        score -= 50.0 + len(missing_preconditions(requires, state))
    return score, executable


def can_reach_targets_within(
    modules_doc: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    depth: int,
    blocked_modules: set[str],
    allowed_module_ids: set[str] | None = None,
) -> bool:
    if not remaining_targets or remaining_targets <= state:
        return True
    if depth <= 0:
        return False

    visited: set[tuple[frozenset[str], int]] = set()
    frontier: list[tuple[set[str], int]] = [(set(state), depth)]

    while frontier:
        current_state, steps_left = frontier.pop(0)
        if remaining_targets <= current_state:
            return True
        if steps_left <= 0:
            continue

        current_remaining = remaining_targets - current_state
        needed_predicates = compute_needed_predicates(
            modules_doc,
            current_state,
            current_remaining,
            min(2, steps_left),
            allowed_module_ids=allowed_module_ids,
        )

        ranked_next: list[tuple[int, int, str, set[str]]] = []
        for module in modules_doc["modules"]:
            module_id = module["module_id"]
            if allowed_module_ids and module_id not in allowed_module_ids:
                continue
            if module_id in blocked_modules:
                continue
            if not preconditions_satisfied(module.get("requires", {}), current_state):
                continue

            adds = set(module.get("effects", {}).get("adds", []))
            relevant_hits = adds & current_remaining
            support_hits = adds & (needed_predicates - current_remaining)
            if not relevant_hits and not support_hits:
                continue

            next_state = apply_effects(current_state, module)
            if next_state == current_state:
                continue

            ranked_next.append(
                (len(relevant_hits), len(support_hits), module_id, next_state)
            )

        ranked_next.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

        for _, _, _, next_state in ranked_next[:16]:
            key = (frozenset(next_state), steps_left - 1)
            if key in visited:
                continue
            visited.add(key)
            frontier.append((next_state, steps_left - 1))

    return False


def shortlist_candidates(
    modules_doc: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    theme: str,
    candidate_limit: int,
    backward_depth: int,
    failed_modules: set[str],
    successful_modules: list[str],
    remaining_invocations: int,
    allowed_module_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    needed_predicates = compute_needed_predicates(
        modules_doc,
        state,
        remaining_targets,
        backward_depth,
        allowed_module_ids=allowed_module_ids,
    )
    ranked_relevant: list[dict[str, Any]] = []
    ranked_fallback: list[dict[str, Any]] = []
    for module in modules_doc["modules"]:
        module_id = module["module_id"]
        if allowed_module_ids and module_id not in allowed_module_ids:
            continue
        if module_id in failed_modules:
            continue
        if module_id in successful_modules:
            continue
        score, executable = score_module_candidate(module, state, remaining_targets, needed_predicates, theme)
        adds = set(module.get("effects", {}).get("adds", []))
        is_relevant = bool(adds & remaining_targets) or bool(adds & (needed_predicates - remaining_targets))
        if not executable and not is_relevant:
            continue
        reachable = True
        if executable:
            next_state = apply_effects(state, module)
            next_remaining = remaining_targets - next_state
            reachable = can_reach_targets_within(
                modules_doc=modules_doc,
                state=next_state,
                remaining_targets=next_remaining,
                depth=max(0, remaining_invocations - 1),
                blocked_modules=set(failed_modules) | set(successful_modules) | {module_id},
                allowed_module_ids=allowed_module_ids,
            )
            if next_remaining and not reachable:
                score -= 100.0
        trace_payload = build_candidate_trace_payload(
            module,
            state,
            remaining_targets,
            needed_predicates,
            theme,
            score=score,
            executable=executable,
            reachable=reachable,
        )
        materialized = dict(module)
        materialized["_candidate_trace"] = trace_payload
        bucket = ranked_relevant if is_relevant else ranked_fallback
        bucket.append(
            {
                "score": score,
                "module_id": module_id,
                "executable": executable,
                "reachable": reachable,
                "module": materialized,
            }
        )

    ranked_relevant.sort(
        key=lambda item: (item["reachable"], item["score"], item["executable"], item["module_id"]),
        reverse=True,
    )
    ranked_fallback.sort(
        key=lambda item: (item["reachable"], item["score"], item["executable"], item["module_id"]),
        reverse=True,
    )

    relevant_executable = [item for item in ranked_relevant if item["executable"]]
    fallback_executable = [item for item in ranked_fallback if item["executable"]]
    reachable_relevant_executable = [item for item in relevant_executable if item["reachable"]]
    reachable_fallback_executable = [item for item in fallback_executable if item["reachable"]]

    # If we already have executable relevant modules, do not distract the planner
    # with non-executable options. This is especially important for smaller models
    # that otherwise pick a semantically-good but currently-illegal module.
    if reachable_relevant_executable:
        ranked = reachable_relevant_executable[:candidate_limit]
        if len(ranked) < candidate_limit:
            ranked.extend(reachable_fallback_executable[: candidate_limit - len(ranked)])
    elif relevant_executable:
        ranked = relevant_executable[:candidate_limit]
        if len(ranked) < candidate_limit:
            ranked.extend(fallback_executable[: candidate_limit - len(ranked)])
    else:
        ranked = ranked_relevant[:candidate_limit]
        if len(ranked) < candidate_limit:
            ranked.extend(ranked_fallback[: candidate_limit - len(ranked)])

    shortlisted = ranked[:candidate_limit]
    for rank, item in enumerate(shortlisted, start=1):
        item["module"]["_candidate_trace"]["rank"] = rank
    return [item["module"] for item in shortlisted]


def format_requires(requires: dict[str, Any]) -> str:
    chunks = []
    if requires.get("all_of"):
        chunks.append("all:" + ",".join(requires["all_of"][:4]))
    if requires.get("any_of"):
        chunks.append("any:" + ",".join(requires["any_of"][:4]))
    if requires.get("none_of"):
        chunks.append("none:" + ",".join(requires["none_of"][:4]))
    return "; ".join(chunks) or "none"


def render_module_prompt(
    goal: dict[str, Any],
    state: set[str],
    remaining_targets: set[str],
    candidates: list[dict[str, Any]],
    successful_modules: list[str],
    failed_modules: set[str],
) -> str:
    lines = [
        f"THEME: {goal['theme']}",
        f"GOAL: {goal['instruction']}",
        f"VISIBLE_CONSTRAINTS: {json.dumps(goal.get('visible_constraints', {}), ensure_ascii=False)}",
        f"CURRENT_STATE: {json.dumps(sorted(state), ensure_ascii=False)}",
        f"TARGET_STATE: {json.dumps(goal.get('target_state', []), ensure_ascii=False)}",
        f"REMAINING_TARGETS: {json.dumps(sorted(remaining_targets), ensure_ascii=False)}",
        f"SUCCESSFUL_MODULES: {json.dumps(successful_modules, ensure_ascii=False)}",
        f"FAILED_MODULES_TO_AVOID: {json.dumps(sorted(failed_modules), ensure_ascii=False)}",
        "CANDIDATE_ORDERING_HINT: earlier candidates are more relevant; prefer executable modules that directly hit REMAINING_TARGETS.",
        "",
        "CANDIDATE_MODULES:",
    ]
    for module in candidates:
        lines.append(
            f"- {module['module_id']} | {module.get('name', module['module_id'])} | "
            f"requires: {format_requires(module.get('requires', {}))} | "
            f"adds: {','.join(module.get('effects', {}).get('adds', [])[:6]) or 'none'}"
        )
    lines += [
        "",
        "Return exactly one token: MODULE_ID or DONE",
        "Only return DONE when all REMAINING_TARGETS are already satisfied or when there is truly no candidate that can advance the goal.",
    ]
    return "\n".join(lines)


def parse_module_choice(raw: str, candidate_ids: set[str]) -> tuple[Optional[str], str]:
    text = (raw or "").strip()
    if not text:
        return None, "empty_output"
    first_line = text.splitlines()[0].strip()
    if first_line == "DONE":
        return "DONE", "first_line_done"
    if first_line in candidate_ids:
        return first_line, "first_line_exact"
    for token in first_line.replace(",", " ").split():
        token = token.strip()
        if token in candidate_ids or token == "DONE":
            return token, "first_line_token"
    for candidate in candidate_ids:
        if candidate in text:
            return candidate, "substring_candidate"
    if "DONE" in text:
        return "DONE", "substring_done"
    return None, "unparsed_output"


def select_next_module(
    client: Any,
    goal: dict[str, Any],
    state: set[str],
    candidates: list[dict[str, Any]],
    successful_modules: list[str],
    failed_modules: set[str],
    temperature: float,
    max_tokens: int,
) -> tuple[str, str, dict[str, Any]]:
    remaining_targets = set(goal.get("target_state", [])) - state
    if not remaining_targets:
        return "DONE", "target_already_satisfied", {
            "decision_source": "llm",
            "parsed_choice": "DONE",
            "parser_match_reason": "target_already_satisfied",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": len(candidates),
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    candidate_ids = {item["module_id"] for item in candidates}
    if not candidate_ids:
        return "DONE", "no_candidates", {
            "decision_source": "llm",
            "parsed_choice": "DONE",
            "parser_match_reason": "no_candidates",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": 0,
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    prompt = render_module_prompt(goal, state, remaining_targets, candidates, successful_modules, failed_modules)
    messages = [
        {"role": "system", "content": MODULE_CHOOSER_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    raw = client.sample_messages(messages, num_samples=1, temperature=temperature, max_tokens=max_tokens)[0]
    parsed, parse_reason = parse_module_choice(raw, candidate_ids)
    meta = {
        "decision_source": "llm",
        "parsed_choice": parsed,
        "parser_match_reason": parse_reason,
        "fallback_reason": "",
        "termination_override": False,
        "candidate_count": len(candidates),
        "planner_prompt": prompt,
        "chosen_module_id": "",
    }
    if parsed == "DONE" and remaining_targets and candidates:
        # Do not allow the planner to terminate while the goal still has unmet targets
        # and there is at least one executable candidate left to try.
        meta["fallback_reason"] = "override_done_with_remaining_targets"
        meta["termination_override"] = True
        meta["chosen_module_id"] = candidates[0]["module_id"]
        return candidates[0]["module_id"], raw, meta
    if parsed is not None:
        meta["chosen_module_id"] = parsed
        return parsed, raw, meta
    meta["fallback_reason"] = "unparsed_output_fallback_to_top_candidate"
    meta["chosen_module_id"] = candidates[0]["module_id"]
    return candidates[0]["module_id"], raw, meta


def choose_reference_next_module(
    oracle: dict[str, Any],
    successful_modules: list[str],
    successful_invocations: set[str],
) -> tuple[str, str, dict[str, Any]]:
    path = oracle.get("success_paths", [])[0]
    invocations_by_id = {
        invocation.get("invocation_id"): invocation
        for invocation in oracle.get("reference_invocations", [])
        if invocation.get("invocation_id")
    }

    reference_invocation_ids = [
        invocation_id
        for invocation_id in path.get("reference_invocation_ids", [])
        if invocation_id in invocations_by_id
    ]
    if reference_invocation_ids:
        for invocation_id in reference_invocation_ids:
            if invocation_id not in successful_invocations:
                module_id = invocations_by_id[invocation_id].get("module_id", "")
                return module_id, f"reference:{path['path_id']}:{invocation_id}", {
                    "decision_source": "reference",
                    "parsed_choice": module_id,
                    "parser_match_reason": "reference_next_invocation",
                    "fallback_reason": "",
                    "termination_override": False,
                    "candidate_count": 0,
                    "planner_prompt": "",
                    "chosen_module_id": module_id,
                    "reference_path_id": path.get("path_id", ""),
                    "reference_invocation_id": invocation_id,
                }
        return "DONE", f"reference:{path['path_id']}", {
            "decision_source": "reference",
            "parsed_choice": "DONE",
            "parser_match_reason": "reference_path_complete",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": 0,
            "planner_prompt": "",
            "chosen_module_id": "DONE",
            "reference_path_id": path.get("path_id", ""),
            "reference_invocation_id": "",
        }

    required = path.get("required_modules", [])
    for module_id in required:
        if module_id not in successful_modules:
            return module_id, f"reference:{path['path_id']}", {
                "decision_source": "reference",
                "parsed_choice": module_id,
                "parser_match_reason": "reference_next_required_module",
                "fallback_reason": "",
                "termination_override": False,
                "candidate_count": 0,
                "planner_prompt": "",
                "chosen_module_id": module_id,
                "reference_path_id": path.get("path_id", ""),
                "reference_invocation_id": "",
            }
    return "DONE", f"reference:{path['path_id']}", {
        "decision_source": "reference",
        "parsed_choice": "DONE",
        "parser_match_reason": "reference_path_complete",
        "fallback_reason": "",
        "termination_override": False,
        "candidate_count": 0,
        "planner_prompt": "",
        "chosen_module_id": "DONE",
        "reference_path_id": path.get("path_id", ""),
        "reference_invocation_id": "",
    }


def choose_heuristic_next_module(
    goal: dict[str, Any],
    state: set[str],
    candidates: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    remaining_targets = set(goal.get("target_state", [])) - state
    if not remaining_targets:
        return "DONE", "heuristic:target_already_satisfied", {
            "decision_source": "heuristic",
            "parsed_choice": "DONE",
            "parser_match_reason": "target_already_satisfied",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": len(candidates),
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    if not candidates:
        return "DONE", "heuristic:no_candidates", {
            "decision_source": "heuristic",
            "parsed_choice": "DONE",
            "parser_match_reason": "no_candidates",
            "fallback_reason": "",
            "termination_override": False,
            "candidate_count": 0,
            "planner_prompt": "",
            "chosen_module_id": "DONE",
        }
    return candidates[0]["module_id"], "heuristic:top_ranked_candidate", {
        "decision_source": "heuristic",
        "parsed_choice": candidates[0]["module_id"],
        "parser_match_reason": "top_ranked_candidate",
        "fallback_reason": "",
        "termination_override": False,
        "candidate_count": len(candidates),
        "planner_prompt": "",
        "chosen_module_id": candidates[0]["module_id"],
    }


def resolve_execution_binding(
    module_id: str,
    oracle: dict[str, Any],
    bindings_by_module: dict[str, list[dict[str, Any]]],
    used_invocations: set[str],
    forced_invocation_id: str = "",
) -> dict[str, Any]:
    invocations = oracle.get("reference_invocations", [])
    chosen_invocation = None
    if forced_invocation_id:
        for invocation in invocations:
            if invocation.get("invocation_id") == forced_invocation_id:
                if invocation.get("module_id") != module_id:
                    raise ValueError(
                        f"reference invocation {forced_invocation_id} belongs to "
                        f"{invocation.get('module_id')}, not {module_id}"
                    )
                chosen_invocation = invocation
                break
        if chosen_invocation is None:
            raise ValueError(f"reference invocation not found: {forced_invocation_id}")
    else:
        for invocation in invocations:
            if invocation.get("module_id") == module_id and invocation.get("invocation_id") not in used_invocations:
                chosen_invocation = invocation
                break

    bindings = bindings_by_module.get(module_id, [])
    if not bindings:
        raise ValueError(f"no binding available for module {module_id}")

    binding = None
    if chosen_invocation and chosen_invocation.get("binding_id"):
        for item in bindings:
            if item["binding_id"] == chosen_invocation["binding_id"]:
                binding = item
                break
    if binding is None:
        binding = bindings[0]

    invocation_matches_binding = False
    if chosen_invocation:
        chosen_binding_id = str(chosen_invocation.get("binding_id") or "").strip()
        chosen_binding_task_id = str(chosen_invocation.get("binding_task_id") or "").strip()
        invocation_matches_binding = (
            (not chosen_binding_id or chosen_binding_id == binding["binding_id"])
            and (not chosen_binding_task_id or chosen_binding_task_id == binding["backing_task_id"])
        )

    parameter_values = dict(binding.get("default_parameter_values", {}))
    description = binding.get("seed_example", {}).get("description") or module_id
    expected_observables = list(binding.get("seed_example", {}).get("observables", []) or [])
    invocation_id = None
    if chosen_invocation:
        invocation_id = chosen_invocation.get("invocation_id")
        if invocation_matches_binding:
            parameter_values.update(chosen_invocation.get("parameter_values", {}))
            if chosen_invocation.get("description"):
                description = chosen_invocation["description"]
            if chosen_invocation.get("expected_observables"):
                expected_observables = list(chosen_invocation["expected_observables"])

    return {
        "module_id": module_id,
        "binding_id": binding["binding_id"],
        "binding_task_id": binding["backing_task_id"],
        "task_dir": binding["task_dir"],
        "parameter_values": parameter_values,
        "description": description,
        "expected_observables": expected_observables,
        "invocation_id": invocation_id,
    }


def snapshot_runtime(runtime_root: Path, snapshot_root: Path) -> None:
    snapshot_root.mkdir(parents=True, exist_ok=True)
    for rel in ("data.db", "data.db-shm", "data.db-wal", "env/state.json"):
        src = runtime_root / rel
        dst = snapshot_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
        elif dst.exists():
            dst.unlink()


def restore_runtime(runtime_root: Path, snapshot_root: Path) -> None:
    for rel in ("data.db", "data.db-shm", "data.db-wal", "env/state.json"):
        src = snapshot_root / rel
        dst = runtime_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
        elif dst.exists():
            dst.unlink()


def _runtime_initial_predicates(raw: Any) -> set[str]:
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    if isinstance(raw, dict):
        return {key for key, value in raw.items() if value is True}
    return set()


def _load_runtime_state(runtime_root: Path) -> dict[str, Any]:
    state_path = runtime_root / "env" / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_runtime_state(runtime_root: Path, env: dict[str, Any]) -> None:
    state_path = runtime_root / "env" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(env, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _runtime_memory_set(conn: sqlite3.Connection, key: str, value: Any, ts: str, source: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
        [key, str(value), ts, source, 1.0],
    )


def _materialize_shop_order_predicate(runtime_root: Path, predicates: set[str]) -> None:
    needs_order = bool(predicates & {"shop_order_exists", "shop_order_pending", "shop_order_delivered"})
    if not needs_order:
        return

    delivered = "shop_order_delivered" in predicates and "shop_order_pending" not in predicates
    state = "delivered" if delivered else "confirmed"
    order_id = "O-70001"

    env = _load_runtime_state(runtime_root)
    ts = str(env.get("system_time") or datetime.now().isoformat())
    order_payload = {
        "id": order_id,
        "items": [
            {
                "id": "WM-5521",
                "sku": "WM-5521",
                "name": "Wireless Mouse",
                "category": "electronics",
                "quantity": 1,
                "qty": 1,
                "price": 29.99,
            }
        ],
        "total": 29.99,
        "state": state,
        "shipping_speed": "standard",
        "shipping_address": "123 Main St",
        "date": ts,
    }
    env.setdefault("shop", {}).setdefault("orders", {})
    env["shop"]["orders"][order_id] = order_payload
    env["shop"]["orders"]["last"] = {
        "id": order_id,
        "state": state,
        "total": 29.99,
    }
    env["pending_order"] = not delivered
    env["has_shop_delivered"] = delivered
    _save_runtime_state(runtime_root, env)

    db_path = runtime_root / "data.db"
    if not db_path.exists():
        return
    with sqlite3.connect(db_path, timeout=60) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DELETE FROM order_items WHERE order_id = ?", [order_id])
        conn.execute("DELETE FROM orders WHERE id = ?", [order_id])
        conn.execute(
            """
            INSERT INTO orders
              (id, user_id, total, state, shipping_speed, shipping_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [order_id, 1, 29.99, state, "standard", "123 Main St", ts],
        )
        conn.execute(
            "INSERT INTO order_items (order_id, sku, quantity, price) VALUES (?, ?, ?, ?)",
            [order_id, "WM-5521", 1, 29.99],
        )
        _runtime_memory_set(conn, "shop.orders.last.id", order_id, ts, "workflow_initial_state")
        _runtime_memory_set(conn, "shop.orders.last.state", state, ts, "workflow_initial_state")
        _runtime_memory_set(conn, "shop.orders.last.total", "29.99", ts, "workflow_initial_state")
        _runtime_memory_set(conn, f"shop.orders.{order_id}.state", state, ts, "workflow_initial_state")
        _runtime_memory_set(conn, "pending_order", "false" if delivered else "true", ts, "workflow_initial_state")
        _runtime_memory_set(conn, "has_shop_delivered", "true" if delivered else "false", ts, "workflow_initial_state")
        conn.commit()


def materialize_initial_world_state(runtime_root: Path, initial_world_state: Any) -> None:
    predicates = _runtime_initial_predicates(initial_world_state)
    _materialize_shop_order_predicate(runtime_root, predicates)


def execute_atomic_module(
    module: dict[str, Any],
    binding_payload: dict[str, Any],
    goal: dict[str, Any],
    stage_root: Path,
    client: Any,
    atomic_policy: str,
    atomic_max_steps: int,
    repeat_fail_threshold: int,
    headless: bool,
    verbose: bool,
    invocation_counter: int,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    invocation_id = binding_payload.get("invocation_id") or f"{goal['goal_id']}-R{invocation_counter}"
    plan_entry = {
        "index": invocation_counter,
        "module_id": module["module_id"],
        "binding_id": binding_payload["binding_id"],
        "binding_task_id": binding_payload["binding_task_id"],
        "task_dir": binding_payload["task_dir"],
        "invocation_id": invocation_id,
        "parameter_values": binding_payload["parameter_values"],
        "description": binding_payload["description"],
        "expected_observables": binding_payload["expected_observables"],
    }
    spec_path, oracle_path = instantiate_atomic_task(binding_payload, plan_entry, stage_root)
    if atomic_policy == "dry_run":
        return (
            {
                "success": True,
                "steps_executed": int(module.get("constraints", {}).get("estimated_steps", 0) or 0),
                "raw_output": "dry_run",
                "failure_category": "",
                "end_reason": "dry_run_success",
                "agent_backend": getattr(client, "backend_name", "unknown") if client else "none",
                "agent_model": getattr(client, "model", "") if client else "",
            },
            {
                "task_spec_path": str(spec_path),
                "oracle_trace_path": str(oracle_path),
            },
        )

    runtime_task_id = f"_workflow_runtime/{goal['goal_id']}/{invocation_id}"
    result = execute_agent_task(
        task_id=runtime_task_id,
        start_url=infer_start_url(oracle_path),
        max_steps=atomic_max_steps,
        repeat_fail_threshold=repeat_fail_threshold,
        stop_on_first_fail_step=True,
        headless=headless,
        client=client,
        write_result=False,
        verbose=verbose,
    )
    return result, {
        "task_spec_path": str(spec_path),
        "oracle_trace_path": str(oracle_path),
    }


def run_single_goal(
    goal_ref: dict[str, Any],
    split_root: Path,
    output_root: Path,
    runtime_root: Path,
    snapshot_root: Path,
    modules_doc: dict[str, Any],
    bindings_doc: dict[str, Any],
    client: Any,
    args: argparse.Namespace,
) -> dict[str, Any]:
    goal = load_json(split_root / goal_ref["goal_file"])
    oracle = load_json(split_root / goal_ref["oracle_file"])
    modules_by_id, bindings_by_module = build_indices(modules_doc, bindings_doc)
    allowed_module_ids = allowed_modules_from_oracle(oracle)

    restore_runtime(runtime_root, snapshot_root)
    materialize_initial_world_state(runtime_root, goal.get("initial_world_state", []))

    state = set(goal.get("initial_world_state", []))
    successful_modules: list[str] = []
    successful_invocations: set[str] = set()
    failed_modules: set[str] = set()
    used_invocations: set[str] = set()
    executed_modules: list[dict[str, Any]] = []
    selection_trace: list[dict[str, Any]] = []
    actual_step_count = 0
    actual_budget_spend = 0.0
    start_ts = time.time()

    max_module_invocations = int(goal.get("max_module_invocations", 0) or 0)
    episode_root = output_root / goal["goal_id"]
    stage_root = Path("tasks") / "_workflow_runtime" / goal["goal_id"]
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    for turn in range(1, max_module_invocations + 1):
        remaining_targets = set(goal.get("target_state", [])) - state
        candidates = shortlist_candidates(
            modules_doc=modules_doc,
            state=state,
            remaining_targets=remaining_targets,
            theme=goal["theme"],
            candidate_limit=args.candidate_limit,
            backward_depth=args.target_backward_depth,
            failed_modules=failed_modules,
            successful_modules=successful_modules,
            remaining_invocations=max_module_invocations - turn + 1,
            allowed_module_ids=allowed_module_ids,
        )

        selection_event = {
            "turn": turn,
            "module_policy": args.module_policy,
            "state_before": sorted(state),
            "remaining_targets": sorted(remaining_targets),
            "remaining_targets_before": sorted(remaining_targets),
            "successful_modules_before": list(successful_modules),
            "failed_modules_before": sorted(failed_modules),
            "candidate_count": len(candidates),
            "candidate_module_ids": [item["module_id"] for item in candidates],
            "candidate_details": [dict(item.get("_candidate_trace", {})) for item in candidates],
        }

        try:
            if args.module_policy == "reference":
                chosen_module_id, raw_decision, decision_meta = choose_reference_next_module(
                    oracle,
                    successful_modules,
                    successful_invocations,
                )
            elif args.module_policy == "heuristic":
                chosen_module_id, raw_decision, decision_meta = choose_heuristic_next_module(goal, state, candidates)
            else:
                chosen_module_id, raw_decision, decision_meta = select_next_module(
                    client=client,
                    goal=goal,
                    state=state,
                    candidates=candidates,
                    successful_modules=successful_modules,
                    failed_modules=failed_modules,
                    temperature=args.module_temperature,
                    max_tokens=args.module_max_tokens,
                )
        except Exception as exc:
            selection_event.update(
                {
                    "raw_decision": "",
                    "planner_raw_choice": "",
                    "chosen_module_id": "ERROR",
                    "module_id": "ERROR",
                    "decision_meta": {
                        "decision_source": args.module_policy,
                        "decision_error": exception_payload(exc),
                    },
                    "selection_error": exception_payload(exc),
                    "state_after": sorted(state),
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                }
            )
            selection_trace.append(selection_event)
            break

        selected_candidate = next(
            (dict(item.get("_candidate_trace", {})) for item in candidates if item["module_id"] == chosen_module_id),
            None,
        )
        selection_event.update(
            {
                "raw_decision": raw_decision,
                "planner_raw_choice": raw_decision,
                "chosen_module_id": chosen_module_id,
                "module_id": chosen_module_id,
                "decision_meta": decision_meta,
                "selected_candidate": selected_candidate,
                "selected_candidate_rank": selected_candidate.get("rank") if selected_candidate else None,
            }
        )

        if chosen_module_id == "DONE":
            selection_event.update(
                {
                    "terminated": True,
                    "state_after": sorted(state),
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                }
            )
            selection_trace.append(selection_event)
            break
        if chosen_module_id not in modules_by_id:
            failed_modules.add(chosen_module_id)
            selection_event.update(
                {
                    "selection_error": {
                        "type": "UnknownModule",
                        "message": f"unknown module selected: {chosen_module_id}",
                    },
                    "state_after": sorted(state),
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                }
            )
            selection_trace.append(selection_event)
            break

        module = modules_by_id[chosen_module_id]
        state_before = set(state)
        state_before_sorted = sorted(state_before)
        binding_payload = None
        staged = None
        try:
            binding_payload = resolve_execution_binding(
                chosen_module_id,
                oracle,
                bindings_by_module,
                used_invocations,
                forced_invocation_id=str(decision_meta.get("reference_invocation_id") or ""),
            )
            if binding_payload.get("invocation_id"):
                used_invocations.add(binding_payload["invocation_id"])

            task_result, staged = execute_atomic_module(
                module=module,
                binding_payload=binding_payload,
                goal=goal,
                stage_root=stage_root,
                client=client,
                atomic_policy=args.atomic_policy,
                atomic_max_steps=args.atomic_max_steps,
                repeat_fail_threshold=args.atomic_repeat_fail_threshold,
                headless=args.headless,
                verbose=args.verbose,
                invocation_counter=turn,
            )
        except Exception as exc:
            failed_modules.add(chosen_module_id)
            error_result = {
                "success": False,
                "end_reason": "exception",
                "failure_category": type(exc).__name__,
                "steps_executed": 0,
                "verify_error": "",
                "step_error_message": str(exc),
                "raw_output": "",
            }
            executed_modules.append(
                {
                    "module_id": chosen_module_id,
                    "binding_id": binding_payload["binding_id"] if binding_payload else "",
                    "status": "error",
                    "parameter_values": binding_payload["parameter_values"] if binding_payload else {},
                    "notes": binding_payload["description"] if binding_payload else "",
                    "task_dir": binding_payload["task_dir"] if binding_payload else "",
                    "binding_task_id": binding_payload["binding_task_id"] if binding_payload else "",
                    "instantiated_task_spec": staged["task_spec_path"] if staged else "",
                    "instantiated_oracle_trace": staged["oracle_trace_path"] if staged else "",
                    "state_before": state_before_sorted,
                    "state_after": state_before_sorted,
                    "module_decision_raw_output": raw_decision,
                    "atomic_result": summarize_atomic_result(error_result),
                    "execution_exception": exception_payload(exc),
                }
            )
            selection_event.update(
                {
                    "binding": (
                        {
                            "binding_id": binding_payload["binding_id"],
                            "binding_task_id": binding_payload["binding_task_id"],
                            "task_dir": binding_payload["task_dir"],
                            "invocation_id": binding_payload.get("invocation_id") or f"{goal['goal_id']}-R{turn}",
                        }
                        if binding_payload
                        else {}
                    ),
                    "execution_exception": exception_payload(exc),
                    "atomic_result": summarize_atomic_result(error_result),
                    "state_after": state_before_sorted,
                    "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                    "state_delta_added": [],
                    "state_delta_removed": [],
                }
            )
            selection_trace.append(selection_event)
            break

        success = bool(task_result.get("success"))
        if success:
            successful_modules.append(chosen_module_id)
            if binding_payload.get("invocation_id"):
                successful_invocations.add(binding_payload["invocation_id"])
            delta = float(module.get("constraints", {}).get("budget_delta", 0.0) or 0.0)
            if delta < 0:
                actual_budget_spend += -delta
            actual_step_count += int(task_result.get("steps_executed") or module.get("constraints", {}).get("estimated_steps", 0) or 0)
            state = apply_effects(state, module)
        else:
            failed_modules.add(chosen_module_id)
            actual_step_count += int(task_result.get("steps_executed") or 0)

        atomic_result_summary = summarize_atomic_result(task_result)
        state_after_sorted = sorted(state)

        executed_modules.append(
            {
                "module_id": chosen_module_id,
                "binding_id": binding_payload["binding_id"],
                "status": "success" if success else "failed",
                "parameter_values": binding_payload["parameter_values"],
                "notes": binding_payload["description"],
                "task_dir": binding_payload["task_dir"],
                "binding_task_id": binding_payload["binding_task_id"],
                "instantiated_task_spec": staged["task_spec_path"] if staged else "",
                "instantiated_oracle_trace": staged["oracle_trace_path"] if staged else "",
                "state_before": state_before_sorted,
                "state_after": state_after_sorted,
                "module_decision_raw_output": raw_decision,
                "atomic_result": atomic_result_summary,
            }
        )
        selection_event.update(
            {
                "binding": {
                    "binding_id": binding_payload["binding_id"],
                    "binding_task_id": binding_payload["binding_task_id"],
                    "task_dir": binding_payload["task_dir"],
                    "invocation_id": binding_payload.get("invocation_id") or f"{goal['goal_id']}-R{turn}",
                },
                "atomic_result": atomic_result_summary,
                "state_after": state_after_sorted,
                "remaining_targets_after": sorted(set(goal.get("target_state", [])) - state),
                "state_delta_added": sorted(state - state_before),
                "state_delta_removed": sorted(state_before - state),
            }
        )
        selection_trace.append(selection_event)

        if not success and args.module_policy == "reference":
            break
        if success and set(goal.get("target_state", [])) <= state:
            break

    trace = {
        "goal_id": goal["goal_id"],
        "selected_path": args.module_policy,
        "starting_state_override": goal.get("initial_world_state", []),
        "final_state_override": sorted(state),
        "actual_step_count": actual_step_count,
        "actual_budget_spend": actual_budget_spend,
        "actual_elapsed_hours": (time.time() - start_ts) / 3600.0,
        "executed_modules": executed_modules,
    }
    evaluation = evaluate_episode(goal, oracle, trace, modules_doc)

    dump_json(episode_root / "workflow_execution_trace.json", trace)
    dump_json(episode_root / "workflow_execution_evaluation.json", evaluation)
    dump_json(episode_root / "workflow_module_selection_trace.json", selection_trace)

    record = {
        "goal_id": goal["goal_id"],
        "theme": goal["theme"],
        "blueprint_id": goal_ref["blueprint_id"],
        "success": evaluation["final_success"],
        "success_type": evaluation["success_type"],
        "target_state_coverage": evaluation["target_state_coverage"],
        "composite_score": evaluation["score_breakdown"]["composite_score"],
        "attempted_module_invocations": evaluation["resource_usage"]["attempted_module_invocations"],
        "actual_step_count": evaluation["resource_usage"]["actual_step_count"],
        "used_reference_path": evaluation["used_reference_path"],
        "hard_constraint_violations": evaluation["hard_constraint_violations"],
        "invalid_transition_count": evaluation["invalid_transition_count"],
        "output_dir": str(episode_root),
    }
    dump_json(episode_root / "workflow_run_summary.json", record)
    return record


def render_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Workflow Benchmark Run",
        "",
        f"- batch_root: `{summary['batch_root']}`",
        f"- split: `{summary['split']}`",
        f"- module_policy: `{summary['module_policy']}`",
        f"- atomic_policy: `{summary['atomic_policy']}`",
        f"- runtime_isolation: `{summary['runtime_isolation']}`",
        f"- agent_backend: `{summary['agent_backend']}`",
        f"- agent_model: `{summary['agent_model']}`",
        f"- total_goals: {summary['total_goals']}",
        f"- final_success_count: {summary['final_success_count']}",
        f"- final_success_rate: {summary['final_success_rate']:.4f}",
        f"- average_composite_score: {summary['average_composite_score']:.4f}",
        f"- runtime_note: {summary['runtime_note']}",
        "",
        "## Success Types",
    ]
    for key, value in sorted(summary["success_type_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Per Theme"]
    for theme, item in sorted(summary["per_theme"].items()):
        lines.append(
            f"- `{theme}`: {item['success_count']}/{item['goal_count']} success, avg_score={item['average_composite_score']:.4f}"
        )
    if "completed_goals" in summary:
        lines += [
            "",
            "## Progress",
            f"- completed_goals: {summary['completed_goals']}",
            f"- is_complete: {summary.get('is_complete', False)}",
        ]
    path.write_text("\n".join(lines) + "\n")


def build_summary(
    *,
    batch_root: Path,
    split: str,
    args: argparse.Namespace,
    client: Any,
    records: list[dict[str, Any]],
    planned_total_goals: int,
    is_complete: bool,
) -> dict[str, Any]:
    success_type_counts = Counter(item["success_type"] for item in records)
    per_theme_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        per_theme_buckets[item["theme"]].append(item)

    per_theme = {}
    for theme, items in per_theme_buckets.items():
        per_theme[theme] = {
            "goal_count": len(items),
            "success_count": sum(1 for item in items if item["success"]),
            "average_composite_score": sum(item["composite_score"] for item in items) / len(items),
        }

    completed_goals = len(records)
    success_count = sum(1 for item in records if item["success"])
    summary = {
        "version": 1,
        "batch_root": str(batch_root),
        "split": split,
        "module_policy": args.module_policy,
        "atomic_policy": args.atomic_policy,
        "runtime_isolation": args.runtime_isolation,
        "runtime_note": RUNTIME_ISOLATION_NOTES[args.runtime_isolation],
        "agent_backend": getattr(client, "backend_name", "none") if client else "none",
        "agent_model": getattr(client, "model", "") if client else "",
        "total_goals": planned_total_goals if planned_total_goals else completed_goals,
        "completed_goals": completed_goals,
        "is_complete": is_complete,
        "final_success_count": success_count,
        "final_success_rate": (success_count / completed_goals) if completed_goals else 0.0,
        "average_composite_score": (sum(item["composite_score"] for item in records) / completed_goals) if completed_goals else 0.0,
        "success_type_counts": dict(sorted(success_type_counts.items())),
        "per_theme": per_theme,
        "records": records,
    }
    return summary


def main() -> None:
    args = parse_args()
    if args.runtime_isolation == "shared":
        print(
            "[workflow-benchmark] WARNING: shared runtime isolation reuses a single runtime and server "
            "across goals. This mode is for debugging only and can contaminate benchmark results. "
            "Use --runtime-isolation per_goal for official numbers.",
            file=sys.stderr,
        )

    batch_root = Path(args.batch_root).resolve()
    split_root = batch_root / args.split
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_root = Path(args.runtime_root).resolve()
    snapshot_root = output_root / "_runtime_snapshot"
    snapshot_runtime(runtime_root, snapshot_root)

    modules_doc = load_json(Path(args.modules))
    bindings_doc = load_json(Path(args.bindings))
    goal_refs = collect_goals(batch_root, args.split, args.goal_id, args.limit)

    client = None
    if args.module_policy == "llm" or args.atomic_policy == "agent":
        client = build_client()

    records = []
    goal_output_root = output_root / args.split
    planned_total_goals = len(goal_refs)

    def _write_partial_summary() -> None:
        partial_summary = build_summary(
            batch_root=batch_root,
            split=args.split,
            args=args,
            client=client,
            records=records,
            planned_total_goals=planned_total_goals,
            is_complete=False,
        )
        dump_json(output_root / f"{args.split}_summary.partial.json", partial_summary)
        render_markdown(output_root / f"{args.split}_summary.partial.md", partial_summary)

    if args.runtime_isolation == "shared":
        for goal_ref in goal_refs:
            records.append(
                run_single_goal(
                    goal_ref=goal_ref,
                    split_root=split_root,
                    output_root=goal_output_root,
                    runtime_root=runtime_root,
                    snapshot_root=snapshot_root,
                    modules_doc=modules_doc,
                    bindings_doc=bindings_doc,
                    client=client,
                    args=args,
                )
            )
            _write_partial_summary()
    else:
        isolated_root = output_root / "_goal_runtimes"
        isolated_root.mkdir(parents=True, exist_ok=True)
        for goal_ref in goal_refs:
            goal_id = goal_ref["goal_id"]
            goal_runtime_root = isolated_root / goal_id / "runtime"
            goal_server_log = isolated_root / goal_id / "server.log"
            _prepare_goal_runtime(goal_runtime_root, snapshot_root)
            proc = None
            try:
                proc, goal_base_url = _start_goal_server(goal_runtime_root, goal_server_log)
                env_updates = {
                    "WEBAGENT_RUNTIME_ROOT": str(goal_runtime_root),
                    "WEBAGENT_SERVER_BASE_URL": goal_base_url,
                    "WEBAGENT_SERVER_PORT": goal_base_url.rsplit(":", 1)[-1],
                }
                with _temporary_process_env(env_updates), _pushd(goal_runtime_root):
                    records.append(
                        run_single_goal(
                            goal_ref=goal_ref,
                            split_root=split_root,
                            output_root=goal_output_root,
                            runtime_root=goal_runtime_root,
                            snapshot_root=snapshot_root,
                            modules_doc=modules_doc,
                            bindings_doc=bindings_doc,
                            client=client,
                            args=args,
                        )
                    )
                    _write_partial_summary()
            finally:
                if proc is not None and proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        proc.kill()

    summary = build_summary(
        batch_root=batch_root,
        split=args.split,
        args=args,
        client=client,
        records=records,
        planned_total_goals=planned_total_goals,
        is_complete=True,
    )

    dump_json(output_root / f"{args.split}_summary.json", summary)
    render_markdown(output_root / f"{args.split}_summary.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
