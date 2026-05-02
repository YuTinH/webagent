#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_combined_or_shards(run_dir: Path, split: str) -> dict[str, Any]:
    combined_path = run_dir / f"{split}_combined_summary.json"
    if combined_path.exists():
        return json.loads(combined_path.read_text(encoding="utf-8"))

    records: list[dict[str, Any]] = []
    shard_summaries: list[str] = []
    total_goals = 0
    for shard_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("shard")):
        summary_path = shard_dir / f"{split}_summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        shard_summaries.append(str(summary_path))
        total_goals += int(summary.get("total_goals", 0) or 0)
        records.extend(summary.get("records", []))
    return {
        "split": split,
        "total_goals": total_goals or len(records),
        "completed_goals": len(records),
        "records": records,
        "shard_summaries": shard_summaries,
    }


def _find_stage1_success_map(run_dir: Path, split: str) -> dict[str, bool]:
    combined = _load_combined_or_shards(run_dir, split)
    return {record["goal_id"]: bool(record.get("success")) for record in combined.get("records", [])}


def _find_baseline_failed_records(run_dir: Path, split: str) -> list[dict[str, Any]]:
    combined = _load_combined_or_shards(run_dir, split)
    return [record for record in combined.get("records", []) if not record.get("success")]


def _extract_failure_category(goal_dir: Path) -> str:
    trace_path = goal_dir / "workflow_execution_trace.json"
    if not trace_path.exists():
        return "missing_execution_trace"

    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception:
        return "unreadable_execution_trace"

    executed_modules = trace.get("executed_modules", []) if isinstance(trace, dict) else []
    if not executed_modules:
        return "no_module_execution"

    categories: list[str] = []
    for module in executed_modules:
        atomic_result = module.get("atomic_result") or {}
        category = atomic_result.get("failure_category")
        if category:
            categories.append(str(category))

    if categories:
        return categories[-1]
    return "no_failure_category"


def _theme_summary_template() -> dict[str, Any]:
    return {
        "total_failed": 0,
        "analyzed": 0,
        "benchmark_logic_or_eval": 0,
        "agent_side": 0,
        "incomplete_stage1": 0,
        "agent_failure_categories": Counter(),
        "benchmark_goal_ids": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize stage1-only failure attribution results.")
    parser.add_argument("--baseline-run-dir", required=True, help="Baseline benchmark run dir.")
    parser.add_argument("--stage1-run-dir", required=True, help="Stage1 run dir containing shard outputs.")
    parser.add_argument("--split", default="train")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    baseline_run_dir = Path(args.baseline_run_dir)
    stage1_run_dir = Path(args.stage1_run_dir)
    split = args.split

    stage1_success = _find_stage1_success_map(stage1_run_dir, split)
    baseline_failed = _find_baseline_failed_records(baseline_run_dir, split)

    per_theme: dict[str, dict[str, Any]] = defaultdict(_theme_summary_template)
    global_agent_categories: Counter[str] = Counter()
    benchmark_goal_ids: list[str] = []

    for record in baseline_failed:
        goal_id = record["goal_id"]
        theme = record.get("theme", "unknown")
        theme_bucket = per_theme[theme]
        theme_bucket["total_failed"] += 1

        stage1_ok = stage1_success.get(goal_id)
        if stage1_ok is None:
            theme_bucket["incomplete_stage1"] += 1
            continue

        theme_bucket["analyzed"] += 1
        output_dir_value = record.get("output_dir", "")
        goal_dir = Path(output_dir_value)
        if not goal_dir.is_absolute():
            goal_dir = baseline_run_dir / goal_dir

        if not stage1_ok:
            theme_bucket["benchmark_logic_or_eval"] += 1
            theme_bucket["benchmark_goal_ids"].append(goal_id)
            benchmark_goal_ids.append(goal_id)
            continue

        theme_bucket["agent_side"] += 1
        failure_category = _extract_failure_category(goal_dir)
        theme_bucket["agent_failure_categories"][failure_category] += 1
        global_agent_categories[failure_category] += 1

    serializable_themes: dict[str, Any] = {}
    for theme, bucket in sorted(per_theme.items()):
        analyzed = bucket["analyzed"]
        benchmark_count = bucket["benchmark_logic_or_eval"]
        agent_count = bucket["agent_side"]
        serializable_themes[theme] = {
            "total_failed": bucket["total_failed"],
            "analyzed": analyzed,
            "incomplete_stage1": bucket["incomplete_stage1"],
            "benchmark_logic_or_eval": benchmark_count,
            "agent_side": agent_count,
            "benchmark_issue_rate": (benchmark_count / analyzed) if analyzed else 0.0,
            "agent_side_rate": (agent_count / analyzed) if analyzed else 0.0,
            "top_agent_failure_categories": dict(bucket["agent_failure_categories"].most_common(10)),
            "benchmark_goal_ids": bucket["benchmark_goal_ids"],
        }

    global_analyzed = sum(item["analyzed"] for item in serializable_themes.values())
    global_benchmark = sum(item["benchmark_logic_or_eval"] for item in serializable_themes.values())
    global_agent = sum(item["agent_side"] for item in serializable_themes.values())

    summary = {
        "version": 1,
        "split": split,
        "baseline_run_dir": str(baseline_run_dir),
        "stage1_run_dir": str(stage1_run_dir),
        "global": {
            "total_failed": len(baseline_failed),
            "analyzed": global_analyzed,
            "benchmark_logic_or_eval": global_benchmark,
            "agent_side": global_agent,
            "benchmark_issue_rate": (global_benchmark / global_analyzed) if global_analyzed else 0.0,
            "agent_side_rate": (global_agent / global_analyzed) if global_analyzed else 0.0,
            "top_agent_failure_categories": dict(global_agent_categories.most_common(20)),
            "benchmark_goal_ids": benchmark_goal_ids,
        },
        "per_theme": serializable_themes,
    }

    output_json = Path(args.output_json) if args.output_json else stage1_run_dir / f"{split}_stage1_failure_attribution_summary.json"
    output_md = Path(args.output_md) if args.output_md else stage1_run_dir / f"{split}_stage1_failure_attribution_summary.md"
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Stage1 Failure Attribution Summary",
        "",
        f"- split: `{split}`",
        f"- total_failed: {summary['global']['total_failed']}",
        f"- analyzed: {summary['global']['analyzed']}",
        f"- benchmark_logic_or_eval: {summary['global']['benchmark_logic_or_eval']}",
        f"- agent_side: {summary['global']['agent_side']}",
        f"- benchmark_issue_rate: {summary['global']['benchmark_issue_rate']:.4f}",
        "",
        "## Global Top Agent Failure Categories",
    ]
    for name, count in summary["global"]["top_agent_failure_categories"].items():
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Per Theme"])
    for theme, item in serializable_themes.items():
        lines.append(
            f"- {theme}: benchmark {item['benchmark_logic_or_eval']}/{item['analyzed']} "
            f"({item['benchmark_issue_rate']:.2%}), agent_side {item['agent_side']}/{item['analyzed']}"
        )
        for name, count in item["top_agent_failure_categories"].items():
            lines.append(f"  - {name}: {count}")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "output_json": str(output_json),
        "output_md": str(output_md),
        "global_benchmark_issue_rate": summary["global"]["benchmark_issue_rate"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
