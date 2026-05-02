#!/usr/bin/env python3
"""Recover benchmark summary JSON from a complete log with resumed duplicate chains."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


CHAIN_RE = re.compile(r"^▶️ Running Chain:\s+(\S+)")
TASK_RE = re.compile(r"^\s*👉 Task:\s+(.+?)\s+\(Diff:\s*(\d+)\)")
TASK_PASS_RE = re.compile(r"^\s*✅ Passed(?:\s+\(\+?(\d+)\))?")
TASK_FAIL_RE = re.compile(r"^\s*❌ Failed")
CHECKPOINT_RE = re.compile(r"^\s*([✅❌⏭])\s+([A-Za-z0-9_]+):")


def load_scenarios(repo_root: Path) -> dict[str, dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {}
    for path in sorted(repo_root.glob("sampled_*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in items:
            chain_id = str(item.get("chain_id", "")).strip()
            if chain_id:
                scenarios[chain_id] = item
    return scenarios


def classify_failure(block_lines: list[str]) -> str:
    text = "\n".join(block_lines)
    lower = text.lower()
    if "same action x3" in lower or "stuck in ui loop" in lower:
        return "repeat_action_loop"
    if "normalized: done()" in lower or "executor status: done" in lower or "llm output: done()" in lower:
        return "premature_done"
    if "intercepts pointer events" in lower:
        return "overlay_block"
    if "did not find some options" in lower:
        return "option_not_found"
    if "element is not an <input>" in lower or "element is not a <select>" in lower or "cannot be filled" in lower:
        return "action_type_error"
    if "waiting for locator" in lower or "timeout 10000ms exceeded" in lower:
        return "element_not_found_or_timeout"
    return "criteria_or_checkpoint_failed"


def parse_log(log_path: Path) -> list[dict[str, Any]]:
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    chain_occurrences: list[dict[str, Any]] = []
    current_chain: dict[str, Any] | None = None
    current_task: dict[str, Any] | None = None

    def finalize_task() -> None:
        nonlocal current_chain, current_task
        if current_chain is None or current_task is None:
            current_task = None
            return
        current_task["failure_category"] = (
            "none" if current_task.get("success") else classify_failure(current_task.get("block_lines", []))
        )
        current_chain["tasks"].append(current_task)
        current_task = None

    def finalize_chain() -> None:
        nonlocal current_chain
        if current_chain is None:
            return
        finalize_task()
        if current_chain.get("tasks"):
            chain_occurrences.append(current_chain)
        current_chain = None

    for line in lines:
        m_chain = CHAIN_RE.match(line)
        if m_chain:
            finalize_chain()
            current_chain = {
                "chain_id": m_chain.group(1).strip(),
                "tasks": [],
            }
            continue

        m_task = TASK_RE.match(line)
        if m_task:
            if current_chain is None:
                continue
            finalize_task()
            current_task = {
                "task_id": m_task.group(1).strip(),
                "difficulty": int(m_task.group(2)),
                "success": None,
                "block_lines": [line],
                "checkpoint_results": {},
            }
            continue

        if current_task is not None:
            current_task["block_lines"].append(line)
            if TASK_PASS_RE.match(line):
                current_task["success"] = True
            elif TASK_FAIL_RE.match(line):
                current_task["success"] = False
            else:
                m_cp = CHECKPOINT_RE.match(line)
                if m_cp:
                    mark, cp_id = m_cp.groups()
                    current_task["checkpoint_results"][cp_id] = mark

    finalize_chain()
    return chain_occurrences


def task_step_percent(task_occ: dict[str, Any], scenario_step: dict[str, Any] | None) -> tuple[float | None, str]:
    cp_results = task_occ.get("checkpoint_results") or {}
    step_success = bool(task_occ.get("success"))
    checkpoints = []
    if scenario_step is not None:
        checkpoints = list(scenario_step.get("scoring_checkpoints") or scenario_step.get("checkpoints") or [])

    if checkpoints and cp_results:
        total_weight = 0.0
        earned_weight = 0.0
        for cp in checkpoints:
            cp_id = str(cp.get("id", "")).strip()
            if not cp_id:
                continue
            mark = cp_results.get(cp_id)
            if mark == "⏭":
                continue
            weight = float(cp.get("weight", 1.0) or 1.0)
            total_weight += weight
            if mark == "✅":
                earned_weight += weight
        if total_weight > 0.0:
            return earned_weight / total_weight * 100.0, "checkpoint_recovered"

    if step_success:
        return 100.0, "task_success_fallback"
    return None, "no_step_signal"


def merge_last_occurrences(occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    last_by_chain: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for occ in occurrences:
        chain_id = str(occ.get("chain_id", ""))
        if chain_id not in last_by_chain:
            order.append(chain_id)
        last_by_chain[chain_id] = occ
    return [last_by_chain[chain_id] for chain_id in order]


def rebuild_summary(log_path: Path, repo_root: Path) -> dict[str, Any]:
    scenarios = load_scenarios(repo_root)
    occurrences = parse_log(log_path)
    deduped = merge_last_occurrences(occurrences)

    chain_reports: list[dict[str, Any]] = []
    failure_counts = Counter()
    theme_buckets: dict[str, dict[str, Any]] = {}
    total_step_earned = 0.0
    total_step_max = 0.0
    passed_tasks = 0
    total_tasks = 0
    total_planned_tasks = 0
    overall_score = 0
    overall_max = 0

    for occ in deduped:
        chain_id = str(occ.get("chain_id", ""))
        scenario = scenarios.get(chain_id, {})
        planned_steps = list(scenario.get("steps") or [])
        planned_tasks = len(planned_steps) if planned_steps else len(occ.get("tasks", []))
        task_reports: list[dict[str, Any]] = []
        chain_score = 0
        chain_max = 0
        chain_step_earned = 0.0

        for idx, task_occ in enumerate(occ.get("tasks", [])):
            scenario_step = planned_steps[idx] if idx < len(planned_steps) else None
            diff = int(task_occ.get("difficulty", 0) or (scenario_step or {}).get("difficulty", 0) or 0)
            success = bool(task_occ.get("success"))
            failure_category = str(task_occ.get("failure_category", "none"))
            if not success:
                failure_counts[failure_category] += 1
            step_percent, step_source = task_step_percent(task_occ, scenario_step)
            step_progress = (step_percent / 100.0) if isinstance(step_percent, (int, float)) else 0.0
            chain_score += diff if success else 0
            chain_max += diff
            chain_step_earned += step_progress
            task_reports.append(
                {
                    "task_id": str(task_occ.get("task_id", "")),
                    "difficulty": diff,
                    "success": success,
                    "failure_category": failure_category,
                    "step_score_percent": step_percent,
                    "step_score_source": step_source,
                    "step_progress": step_progress,
                }
            )

        if not chain_max and planned_steps:
            chain_max = sum(int(step.get("difficulty", 0) or 0) for step in planned_steps)
        chain_success = bool(task_reports) and planned_tasks == len(task_reports) and all(t["success"] for t in task_reports)
        chain_reports.append(
            {
                "chain_id": chain_id,
                "theme": scenario.get("theme"),
                "success": chain_success,
                "score": chain_score,
                "max_score": chain_max,
                "tasks": task_reports,
                "executed_tasks": len(task_reports),
                "planned_tasks": planned_tasks,
                "step_earned": chain_step_earned,
                "step_max": float(planned_tasks),
            }
        )

        theme = str(scenario.get("theme") or "unknown")
        bucket = theme_buckets.setdefault(
            theme,
            {
                "chains": 0,
                "chains_passed": 0,
                "total_tasks": 0,
                "passed_tasks": 0,
                "overall_score": 0,
                "overall_max": 0,
                "total_step_earned": 0.0,
                "total_step_max": 0.0,
            },
        )
        bucket["chains"] += 1
        bucket["chains_passed"] += 1 if chain_success else 0
        bucket["total_tasks"] += planned_tasks
        bucket["passed_tasks"] += sum(1 for t in task_reports if t["success"])
        bucket["overall_score"] += chain_score
        bucket["overall_max"] += chain_max
        bucket["total_step_earned"] += chain_step_earned
        bucket["total_step_max"] += float(planned_tasks)

        overall_score += chain_score
        overall_max += chain_max
        total_step_earned += chain_step_earned
        total_step_max += float(planned_tasks)
        total_tasks += len(task_reports)
        total_planned_tasks += planned_tasks
        passed_tasks += sum(1 for t in task_reports if t["success"])

    passed_chains = sum(1 for c in chain_reports if c["success"])
    task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
    step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
    flow_score = (passed_chains / len(chain_reports) * 100.0) if chain_reports else 0.0
    weighted_score = (overall_score / overall_max * 100.0) if overall_max else 0.0

    theme_breakdown: dict[str, Any] = {}
    for theme, bucket in sorted(theme_buckets.items()):
        theme_breakdown[theme] = {
            **bucket,
            "task_score": (bucket["passed_tasks"] / bucket["total_tasks"] * 100.0) if bucket["total_tasks"] else 0.0,
            "step_score": (bucket["total_step_earned"] / bucket["total_step_max"] * 100.0) if bucket["total_step_max"] else 0.0,
            "flow_score": (bucket["chains_passed"] / bucket["chains"] * 100.0) if bucket["chains"] else 0.0,
            "weighted_score": (bucket["overall_score"] / bucket["overall_max"] * 100.0) if bucket["overall_max"] else 0.0,
        }

    return {
        "log_path": str(log_path),
        "unique_chains": len(chain_reports),
        "duplicate_chain_occurrences_ignored": max(0, len(occurrences) - len(chain_reports)),
        "chains": chain_reports,
        "overall_score": overall_score,
        "overall_max": overall_max,
        "total_tasks": total_tasks,
        "total_planned_tasks": total_planned_tasks,
        "passed_tasks": passed_tasks,
        "total_step_earned": total_step_earned,
        "total_step_max": total_step_max,
        "metrics": {
            "chains_passed": passed_chains,
            "chains_total": len(chain_reports),
            "task_score": task_score,
            "step_score": step_score,
            "flow_score": flow_score,
            "weighted_score": weighted_score,
        },
        "theme_breakdown": theme_breakdown,
        "failure_analysis": {
            "category_counts": dict(failure_counts.most_common()),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, help="Path to benchmark log")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    summary = rebuild_summary(Path(args.log), Path(args.repo_root).resolve())
    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    metrics = summary["metrics"]
    print(f"Recovered from: {summary['log_path']}")
    print(f"Unique chains: {summary['unique_chains']}")
    print(f"Ignored duplicate chain runs: {summary['duplicate_chain_occurrences_ignored']}")
    print(f"Chains: {metrics['chains_passed']}/{metrics['chains_total']} passed")
    print(f"Tasks:  {summary['passed_tasks']}/{summary['total_planned_tasks']} passed")
    print(f"Step Score: {metrics['step_score']:.2f}/100")
    print(f"Task Score: {metrics['task_score']:.2f}/100")
    print(f"Flow Score: {metrics['flow_score']:.2f}/100")
    print(f"Weighted Score: {summary['overall_score']}/{summary['overall_max']}")
    print(f"Weighted Grade: {metrics['weighted_score']:.2f}/100")
    if summary["failure_analysis"]["category_counts"]:
        print("Top Failure Categories:")
        for name, count in list(summary["failure_analysis"]["category_counts"].items())[:5]:
            print(f"  - {name}: {count}")


if __name__ == "__main__":
    main()
