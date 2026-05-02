#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_LAUNCHER = ROOT / "rl_memory" / "scripts" / "run_workflow_benchmark_goalset_shards.sh"

CATEGORY_LOGIC = "benchmark_logic_or_eval"
CATEGORY_PLANNING = "agent_planning"
CATEGORY_INFRA = "benchmark_infra_or_atomic_env"
CATEGORY_EXECUTION = "agent_execution"
CATEGORY_UNRESOLVED = "unresolved"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staged workflow failure attribution on a failed goal set.")
    parser.add_argument("--baseline-run-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--split", choices=["train", "dev", "test"], default="train")
    parser.add_argument("--launcher", default=str(DEFAULT_LAUNCHER))
    parser.add_argument("--num-shards", type=int, default=2)
    parser.add_argument("--gpu-ids", default="0,1")
    parser.add_argument("--snapshot-root", default=str(ROOT))
    parser.add_argument("--agent-model", default=os.environ.get("AGENT_MODEL", ""))
    parser.add_argument("--env-activate", default=os.environ.get("ENV_ACTIVATE", ""))
    parser.add_argument("--playwright-browsers-path", default=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
    parser.add_argument("--candidate-limit", type=int, default=6)
    parser.add_argument("--target-backward-depth", type=int, default=2)
    parser.add_argument("--module-max-tokens", type=int, default=32)
    parser.add_argument("--module-temperature", type=float, default=0.0)
    parser.add_argument("--atomic-max-steps", type=int, default=25)
    parser.add_argument("--atomic-repeat-fail-threshold", type=int, default=3)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--tag-prefix", default="workflow_failure_attr")
    parser.add_argument("--reuse-existing", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_run_summary(run_dir: Path, split: str) -> dict[str, Any]:
    combined_path = run_dir / f"{split}_combined_summary.json"
    if combined_path.exists():
        return load_json(combined_path)

    shard_summaries = sorted(run_dir.glob(f"shard*/{split}_summary.json"))
    if not shard_summaries:
        raise FileNotFoundError(f"No summary found under {run_dir}")

    records: list[dict[str, Any]] = []
    success_type_counts: Counter[str] = Counter()
    per_theme_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_goals = 0
    all_complete = True
    agent_backend = ""
    agent_model = ""
    batch_root = ""

    for summary_path in shard_summaries:
        summary = load_json(summary_path)
        batch_root = batch_root or summary.get("batch_root", "")
        agent_backend = agent_backend or summary.get("agent_backend", "")
        agent_model = agent_model or summary.get("agent_model", "")
        total_goals += int(summary.get("total_goals", 0) or 0)
        if not bool(summary.get("is_complete", False)):
            all_complete = False
        for record in summary.get("records", []):
            records.append(record)
            success_type_counts[record.get("success_type", "unknown")] += 1
            per_theme_buckets[record.get("theme", "unknown")].append(record)

    completed_goals = len(records)
    final_success_count = sum(1 for record in records if record.get("success"))
    per_theme = {}
    for theme, items in per_theme_buckets.items():
        per_theme[theme] = {
            "goal_count": len(items),
            "success_count": sum(1 for item in items if item.get("success")),
            "average_composite_score": (
                sum(float(item.get("composite_score", 0.0)) for item in items) / len(items)
                if items else 0.0
            ),
        }

    summary = {
        "version": 1,
        "batch_root": batch_root,
        "split": split,
        "total_goals": total_goals,
        "completed_goals": completed_goals,
        "is_complete": all_complete and completed_goals == total_goals,
        "final_success_count": final_success_count,
        "final_success_rate": (final_success_count / completed_goals) if completed_goals else 0.0,
        "agent_backend": agent_backend,
        "agent_model": agent_model,
        "success_type_counts": dict(sorted(success_type_counts.items())),
        "per_theme": per_theme,
        "records": records,
        "shard_summaries": [str(path) for path in shard_summaries],
    }
    return summary


def write_goal_ids(path: Path, goal_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{goal_id}\n" for goal_id in goal_ids), encoding="utf-8")


def parse_run_dir(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("Run dir: "):
            return Path(line.split("Run dir: ", 1)[1].strip())
    raise RuntimeError("Unable to parse run dir from launcher output")


def run_stage(
    *,
    args: argparse.Namespace,
    stage_name: str,
    goal_file: Path,
    module_policy: str,
    atomic_policy: str,
    stage_root: Path,
) -> tuple[Path, dict[str, Any]]:
    stage_root.mkdir(parents=True, exist_ok=True)
    run_root = stage_root / "runs"
    stdout_path = stage_root / "launcher.stdout.log"
    stderr_path = stage_root / "launcher.stderr.log"

    existing = sorted(run_root.glob(f"*_{args.tag_prefix}_{stage_name}_{args.split}"))
    if args.reuse_existing and existing:
        run_dir = existing[-1]
        summary = load_run_summary(run_dir, args.split)
        return run_dir, summary

    env = os.environ.copy()
    env.update(
        {
            "BATCH_ROOT": str(Path(args.batch_root).resolve()),
            "RUN_ROOT": str(run_root),
            "SPLIT": args.split,
            "GOAL_ID_FILE": str(goal_file.resolve()),
            "NUM_SHARDS": str(args.num_shards),
            "GPU_IDS": args.gpu_ids,
            "TAG": f"{args.tag_prefix}_{stage_name}",
            "SNAPSHOT_ROOT": str(Path(args.snapshot_root).resolve()),
            "MODULE_POLICY": module_policy,
            "ATOMIC_POLICY": atomic_policy,
            "CANDIDATE_LIMIT": str(args.candidate_limit),
            "TARGET_BACKWARD_DEPTH": str(args.target_backward_depth),
            "MODULE_MAX_TOKENS": str(args.module_max_tokens),
            "MODULE_TEMPERATURE": str(args.module_temperature),
            "ATOMIC_MAX_STEPS": str(args.atomic_max_steps),
            "ATOMIC_REPEAT_FAIL_THRESHOLD": str(args.atomic_repeat_fail_threshold),
            "HEADLESS": "1" if args.headless else "0",
        }
    )
    if args.env_activate:
        env["ENV_ACTIVATE"] = args.env_activate
    if args.playwright_browsers_path:
        env["PLAYWRIGHT_BROWSERS_PATH"] = args.playwright_browsers_path
    if args.agent_model:
        env["AGENT_MODEL"] = args.agent_model

    proc = subprocess.run(
        [str(Path(args.launcher).resolve())],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Stage {stage_name} failed with exit code {proc.returncode}. "
            f"See {stdout_path} and {stderr_path}."
        )
    run_dir = parse_run_dir(proc.stdout)
    summary = load_run_summary(run_dir, args.split)
    return run_dir, summary


def summarize_records(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    passed: set[str] = set()
    failed: set[str] = set()
    for record in records:
        goal_id = record["goal_id"]
        if record.get("success"):
            passed.add(goal_id)
        else:
            failed.add(goal_id)
    return {"passed": passed, "failed": failed}


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root).resolve()
    split_root = batch_root / args.split
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = load_json(split_root / "manifest.json")
    goal_meta = {item["goal_id"]: item for item in manifest.get("goals", [])}
    total_theme_goal_counts = Counter(item["theme"] for item in manifest.get("goals", []))

    baseline_summary = load_run_summary(Path(args.baseline_run_dir).resolve(), args.split)
    baseline_records = baseline_summary.get("records", [])
    baseline_failures = [record for record in baseline_records if not record.get("success")]
    baseline_failure_ids = [record["goal_id"] for record in baseline_failures]

    failure_by_theme = Counter(record["theme"] for record in baseline_failures)
    ordered_themes = [theme for theme, _ in failure_by_theme.most_common()]
    baseline_failure_ids.sort(key=lambda gid: (ordered_themes.index(goal_meta[gid]["theme"]), gid))

    write_goal_ids(output_root / "stage0_failed_goal_ids.txt", baseline_failure_ids)
    dump_json(
        output_root / "stage0_failed_goals.json",
        {
            "baseline_total_goals": baseline_summary.get("total_goals", 0),
            "baseline_success_count": baseline_summary.get("final_success_count", 0),
            "baseline_failure_count": len(baseline_failure_ids),
            "theme_order": ordered_themes,
            "theme_failure_counts": dict(sorted(failure_by_theme.items())),
        },
    )

    stage1_run_dir, stage1_summary = run_stage(
        args=args,
        stage_name="stage1_reference_dryrun",
        goal_file=output_root / "stage0_failed_goal_ids.txt",
        module_policy="reference",
        atomic_policy="dry_run",
        stage_root=output_root / "stage1_reference_dryrun",
    )
    stage1 = summarize_records(stage1_summary.get("records", []))
    write_goal_ids(output_root / "stage1_pass_goal_ids.txt", sorted(stage1["passed"]))
    write_goal_ids(output_root / "stage1_fail_goal_ids.txt", sorted(stage1["failed"]))

    stage2_run_dir = None
    stage2_summary: dict[str, Any] = {"records": []}
    stage2 = {"passed": set(), "failed": set()}
    if stage1["passed"]:
        stage2_run_dir, stage2_summary = run_stage(
            args=args,
            stage_name="stage2_llm_dryrun",
            goal_file=output_root / "stage1_pass_goal_ids.txt",
            module_policy="llm",
            atomic_policy="dry_run",
            stage_root=output_root / "stage2_llm_dryrun",
        )
        stage2 = summarize_records(stage2_summary.get("records", []))
    write_goal_ids(output_root / "stage2_pass_goal_ids.txt", sorted(stage2["passed"]))
    write_goal_ids(output_root / "stage2_fail_goal_ids.txt", sorted(stage2["failed"]))

    stage3_run_dir = None
    stage3_summary: dict[str, Any] = {"records": []}
    stage3 = {"passed": set(), "failed": set()}
    if stage2["passed"]:
        stage3_run_dir, stage3_summary = run_stage(
            args=args,
            stage_name="stage3_reference_agent",
            goal_file=output_root / "stage2_pass_goal_ids.txt",
            module_policy="reference",
            atomic_policy="agent",
            stage_root=output_root / "stage3_reference_agent",
        )
        stage3 = summarize_records(stage3_summary.get("records", []))
    write_goal_ids(output_root / "stage3_pass_goal_ids.txt", sorted(stage3["passed"]))
    write_goal_ids(output_root / "stage3_fail_goal_ids.txt", sorted(stage3["failed"]))

    category_by_goal: dict[str, str] = {}
    baseline_by_goal = {record["goal_id"]: record for record in baseline_failures}

    for goal_id in baseline_failure_ids:
        if goal_id in stage1["failed"]:
            category_by_goal[goal_id] = CATEGORY_LOGIC
        elif goal_id in stage2["failed"]:
            category_by_goal[goal_id] = CATEGORY_PLANNING
        elif goal_id in stage3["failed"]:
            category_by_goal[goal_id] = CATEGORY_INFRA
        elif goal_id in stage3["passed"]:
            category_by_goal[goal_id] = CATEGORY_EXECUTION
        else:
            category_by_goal[goal_id] = CATEGORY_UNRESOLVED

    category_counts = Counter(category_by_goal.values())
    per_theme: dict[str, dict[str, Any]] = {}
    category_order = [CATEGORY_LOGIC, CATEGORY_PLANNING, CATEGORY_INFRA, CATEGORY_EXECUTION, CATEGORY_UNRESOLVED]

    for theme in sorted(total_theme_goal_counts):
        theme_fail_ids = [goal_id for goal_id in baseline_failure_ids if goal_meta[goal_id]["theme"] == theme]
        theme_category_counts = Counter(category_by_goal[goal_id] for goal_id in theme_fail_ids)
        per_theme[theme] = {
            "total_theme_goals": total_theme_goal_counts[theme],
            "baseline_failure_count": len(theme_fail_ids),
            "baseline_failure_rate": (
                len(theme_fail_ids) / total_theme_goal_counts[theme]
                if total_theme_goal_counts[theme]
                else 0.0
            ),
            "category_counts": {key: theme_category_counts.get(key, 0) for key in category_order},
            "category_rates_within_failures": {
                key: (
                    theme_category_counts.get(key, 0) / len(theme_fail_ids)
                    if theme_fail_ids else 0.0
                )
                for key in category_order
            },
        }

    attribution_records = []
    for goal_id in baseline_failure_ids:
        base = baseline_by_goal[goal_id]
        attribution_records.append(
            {
                "goal_id": goal_id,
                "theme": base["theme"],
                "blueprint_id": base.get("blueprint_id", ""),
                "baseline_success_type": base.get("success_type", ""),
                "baseline_composite_score": base.get("composite_score", 0.0),
                "category": category_by_goal[goal_id],
            }
        )

    summary = {
        "version": 1,
        "split": args.split,
        "baseline_run_dir": str(Path(args.baseline_run_dir).resolve()),
        "baseline_total_goals": baseline_summary.get("total_goals", 0),
        "baseline_success_count": baseline_summary.get("final_success_count", 0),
        "baseline_failure_count": len(baseline_failure_ids),
        "baseline_failure_rate": (
            len(baseline_failure_ids) / baseline_summary.get("total_goals", 1)
            if baseline_summary.get("total_goals", 0)
            else 0.0
        ),
        "theme_order": ordered_themes,
        "stage_runs": {
            "stage1_reference_dryrun": str(stage1_run_dir),
            "stage2_llm_dryrun": str(stage2_run_dir) if stage2_run_dir else "",
            "stage3_reference_agent": str(stage3_run_dir) if stage3_run_dir else "",
        },
        "category_counts": {key: category_counts.get(key, 0) for key in category_order},
        "category_rates_within_failures": {
            key: (category_counts.get(key, 0) / len(baseline_failure_ids) if baseline_failure_ids else 0.0)
            for key in category_order
        },
        "per_theme": per_theme,
        "attribution_records": attribution_records,
    }
    dump_json(output_root / "failure_attribution_summary.json", summary)

    lines = [
        "# Workflow Failure Attribution Summary",
        "",
        f"- split: `{args.split}`",
        f"- baseline_total_goals: {summary['baseline_total_goals']}",
        f"- baseline_success_count: {summary['baseline_success_count']}",
        f"- baseline_failure_count: {summary['baseline_failure_count']}",
        f"- baseline_failure_rate: {summary['baseline_failure_rate']:.4f}",
        "",
        "## Category Counts",
    ]
    for key in category_order:
        lines.append(
            f"- `{key}`: {summary['category_counts'][key]} ({summary['category_rates_within_failures'][key]:.4f})"
        )
    lines += ["", "## Per Theme"]
    for theme, item in per_theme.items():
        counts = item["category_counts"]
        lines.append(
            f"- `{theme}`: failures={item['baseline_failure_count']}/{item['total_theme_goals']}, "
            f"logic={counts[CATEGORY_LOGIC]}, planning={counts[CATEGORY_PLANNING]}, "
            f"infra={counts[CATEGORY_INFRA]}, execution={counts[CATEGORY_EXECUTION]}, "
            f"unresolved={counts[CATEGORY_UNRESOLVED]}"
        )
    (output_root / "failure_attribution_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "baseline_failure_count": len(baseline_failure_ids),
        "category_counts": summary["category_counts"],
        "stage_runs": summary["stage_runs"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
