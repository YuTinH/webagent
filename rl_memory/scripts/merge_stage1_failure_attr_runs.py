#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _iter_summary_paths(run_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in ("shard*/train_summary.json", "shard*/train_summary.partial.json"):
        paths.extend(sorted(run_dir.glob(pattern)))
    return paths


def _load_records(summary_path: Path) -> list[dict[str, Any]]:
    return json.loads(summary_path.read_text(encoding="utf-8")).get("records", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge stage1 dry-run summary shards.")
    parser.add_argument("--run-dir", action="append", required=True, help="Run dir to merge. Can be specified multiple times.")
    parser.add_argument("--total-goals", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--batch-root", default="/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/tasks/generated_workflow_split_batches/workflow_split_batch_v20")
    parser.add_argument("--module-policy", default="reference")
    parser.add_argument("--atomic-policy", default="dry_run")
    args = parser.parse_args()

    records_by_goal: dict[str, dict[str, Any]] = {}
    summary_paths: list[str] = []
    success_type_counts: Counter[str] = Counter()
    per_theme_buckets: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for run_dir_str in args.run_dir:
        run_dir = Path(run_dir_str)
        for summary_path in _iter_summary_paths(run_dir):
            summary_paths.append(str(summary_path))
            for record in _load_records(summary_path):
                records_by_goal[record["goal_id"]] = record

    records = list(sorted(records_by_goal.values(), key=lambda item: item["goal_id"]))
    for record in records:
        success_type_counts[record.get("success_type", "unknown")] += 1
        per_theme_buckets[record.get("theme", "unknown")].append(record)

    per_theme = {}
    for theme, items in sorted(per_theme_buckets.items()):
        per_theme[theme] = {
            "goal_count": len(items),
            "success_count": sum(1 for item in items if item.get("success")),
            "average_composite_score": (
                sum(float(item.get("composite_score", 0.0)) for item in items) / len(items)
                if items else 0.0
            ),
        }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = sum(1 for record in records if record.get("success"))
    combined = {
        "version": 1,
        "batch_root": args.batch_root,
        "split": args.split,
        "module_policy": args.module_policy,
        "atomic_policy": args.atomic_policy,
        "total_goals": args.total_goals,
        "completed_goals": len(records),
        "is_complete": len(records) == args.total_goals,
        "final_success_count": success_count,
        "final_success_rate": (success_count / len(records)) if records else 0.0,
        "average_composite_score": (
            sum(float(record.get("composite_score", 0.0)) for record in records) / len(records)
            if records else 0.0
        ),
        "agent_backend": "",
        "agent_model": "",
        "success_type_counts": dict(sorted(success_type_counts.items())),
        "per_theme": per_theme,
        "records": records,
        "shard_summaries": summary_paths,
    }

    (output_dir / f"{args.split}_combined_summary.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Merged Stage1 Combined Summary",
        "",
        f"- total_goals: {combined['total_goals']}",
        f"- completed_goals: {combined['completed_goals']}",
        f"- is_complete: {combined['is_complete']}",
        f"- final_success_count: {combined['final_success_count']}",
        f"- final_success_rate: {combined['final_success_rate']:.4f}",
        "",
        "## Per Theme",
    ]
    for theme, item in per_theme.items():
        lines.append(
            f"- {theme}: success {item['success_count']}/{item['goal_count']}, "
            f"average_composite_score={item['average_composite_score']:.4f}"
        )
    (output_dir / f"{args.split}_combined_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": str(output_dir),
        "completed_goals": len(records),
        "is_complete": combined["is_complete"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
