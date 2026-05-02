#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize partially completed workflow benchmark runs.")
    parser.add_argument("results_dir", type=Path, help="Path to results/<split> directory containing per-goal folders.")
    args = parser.parse_args()

    results_dir = args.results_dir
    if not results_dir.exists():
        raise SystemExit(f"Results dir does not exist: {results_dir}")

    records: list[dict[str, Any]] = []
    success_type_counts: Counter[str] = Counter()
    per_theme: dict[str, dict[str, Any]] = defaultdict(lambda: {"goal_count": 0, "success_count": 0, "composite_total": 0.0})

    for goal_dir in sorted(path for path in results_dir.iterdir() if path.is_dir()):
        summary_path = goal_dir / "workflow_run_summary.json"
        if not summary_path.exists():
            continue
        summary = load_json(summary_path)
        record = {
            "goal_id": summary.get("goal_id"),
            "theme": summary.get("theme"),
            "blueprint_id": summary.get("blueprint_id"),
            "success": bool(summary.get("success")),
            "success_type": summary.get("success_type"),
            "target_state_coverage": float(summary.get("target_state_coverage", 0.0) or 0.0),
            "composite_score": float(summary.get("composite_score", 0.0) or 0.0),
            "attempted_module_invocations": int(summary.get("attempted_module_invocations", 0) or 0),
            "actual_step_count": int(summary.get("actual_step_count", 0) or 0),
            "used_reference_path": summary.get("used_reference_path"),
            "hard_constraint_violations": list(summary.get("hard_constraint_violations", [])),
            "invalid_transition_count": int(summary.get("invalid_transition_count", 0) or 0),
            "output_dir": str(goal_dir),
        }
        records.append(record)
        success_type = record["success_type"] or ("success" if record["success"] else "failure")
        success_type_counts[success_type] += 1
        theme_bucket = per_theme[record["theme"]]
        theme_bucket["goal_count"] += 1
        theme_bucket["success_count"] += int(record["success"])
        theme_bucket["composite_total"] += record["composite_score"]

    records.sort(key=lambda item: item["goal_id"] or "")
    completed_goals = len(records)
    final_success_count = sum(1 for record in records if record["success"])
    average_composite_score = (sum(record["composite_score"] for record in records) / completed_goals) if completed_goals else 0.0

    per_theme_output: dict[str, dict[str, Any]] = {}
    for theme, bucket in sorted(per_theme.items()):
        goal_count = bucket["goal_count"]
        per_theme_output[theme] = {
            "goal_count": goal_count,
            "success_count": bucket["success_count"],
            "average_composite_score": (bucket["composite_total"] / goal_count) if goal_count else 0.0,
        }

    payload = {
        "completed_goals": completed_goals,
        "final_success_count": final_success_count,
        "final_success_rate": (final_success_count / completed_goals) if completed_goals else 0.0,
        "average_composite_score": average_composite_score,
        "success_type_counts": dict(success_type_counts),
        "per_theme": per_theme_output,
        "records": records,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
