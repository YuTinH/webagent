#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _iter_goal_dirs(baseline_run_dir: Path) -> list[Path]:
    goal_dirs: list[Path] = []
    for shard_dir in sorted(p for p in baseline_run_dir.iterdir() if p.is_dir() and p.name.startswith("shard")):
        train_dir = shard_dir / "train"
        if not train_dir.exists():
            continue
        goal_dirs.extend(sorted(p for p in train_dir.iterdir() if p.is_dir()))
    return goal_dirs


def _last_failure_category(goal_dir: Path) -> str:
    trace_path = goal_dir / "workflow_execution_trace.json"
    if not trace_path.exists():
        return "missing_execution_trace"
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception:
        return "unreadable_execution_trace"
    executed_modules = trace.get("executed_modules", []) if isinstance(trace, dict) else []
    for module in reversed(executed_modules):
        atomic_result = module.get("atomic_result") or {}
        category = atomic_result.get("failure_category")
        if category:
            return str(category)
    return "none"


def _parse_theme_category(value: str) -> tuple[str, set[str]]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"Expected theme=cat1,cat2 format, got: {value}")
    theme, cats = value.split("=", 1)
    categories = {item.strip() for item in cats.split(",") if item.strip()}
    if not theme or not categories:
        raise argparse.ArgumentTypeError(f"Invalid theme/category selector: {value}")
    return theme.strip(), categories


def main() -> None:
    parser = argparse.ArgumentParser(description="Select failed goal samples by theme and failure category.")
    parser.add_argument("--baseline-run-dir", required=True)
    parser.add_argument(
        "--theme-category",
        action="append",
        type=_parse_theme_category,
        required=True,
        help="Format: theme=cat1,cat2",
    )
    parser.add_argument("--max-per-theme", type=int, default=6)
    parser.add_argument("--output-goal-file", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    baseline_run_dir = Path(args.baseline_run_dir)
    selectors = dict(args.theme_category)
    selected: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for goal_dir in _iter_goal_dirs(baseline_run_dir):
        summary_path = goal_dir / "workflow_run_summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("success"):
            continue
        theme = summary.get("theme", "")
        if theme not in selectors:
            continue
        if len(selected[theme]) >= args.max_per_theme:
            continue
        failure_category = _last_failure_category(goal_dir)
        if failure_category not in selectors[theme]:
            continue
        selected[theme].append(
            {
                "goal_id": goal_dir.name,
                "theme": theme,
                "failure_category": failure_category,
                "output_dir": str(goal_dir),
                "composite_score": summary.get("composite_score"),
            }
        )

    result = {
        "baseline_run_dir": str(baseline_run_dir),
        "max_per_theme": args.max_per_theme,
        "selected": {theme: items for theme, items in selected.items()},
    }

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.output_goal_file:
        goal_ids = []
        for theme in selectors:
            for item in selected.get(theme, []):
                goal_ids.append(item["goal_id"])
        Path(args.output_goal_file).write_text("".join(f"{goal_id}\n" for goal_id in goal_ids), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
