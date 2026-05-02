#!/usr/bin/env python3
"""Generate a deduplicated clean flow pool from multiple scenario-generator seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path("/Users/masteryth/Documents/webagent")
GENERATOR = REPO_ROOT / "scenario_generator_v3.py"


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def flow_signature(chain: dict[str, Any]) -> str:
    task_ids = [step.get("task_id") for step in chain.get("steps", [])]
    req_ids = [
        (step.get("template_info") or {}).get("requirement_id") or "baseline"
        for step in chain.get("steps", [])
    ]
    initial_state_hash = hashlib.sha256(
        canonical_dumps(chain.get("initial_state", {})).encode("utf-8")
    ).hexdigest()
    base = {
        "theme": chain.get("theme"),
        "task_ids": task_ids,
        "requirement_ids": req_ids,
        "initial_state_hash": initial_state_hash,
    }
    return hashlib.sha256(canonical_dumps(base).encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write seed runs and the merged deduplicated pool",
    )
    parser.add_argument(
        "--seeds",
        required=True,
        help="Comma-separated seed list, for example: 42,43,44,45",
    )
    parser.add_argument(
        "--themes",
        default="newcomer,daily,career,leisure,crisis",
        help="Comma-separated themes",
    )
    parser.add_argument("--chains-per-theme", type=int, default=100)
    parser.add_argument("--min-steps", type=int, default=6)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--max-repeat-per-task", type=int, default=1)
    parser.add_argument("--theme-task-cap", type=int, default=30)
    parser.add_argument("--min-dependent-steps", type=int, default=2)
    parser.add_argument("--min-long-dependency-steps", type=int, default=1)
    parser.add_argument("--long-dependency-gap", type=int, default=3)
    parser.add_argument("--min-conflict-steps", type=int, default=1)
    parser.add_argument("--constraint-retries", type=int, default=6)
    return parser.parse_args()


def generator_cmd(args: argparse.Namespace, seed: int) -> list[str]:
    return [
        sys.executable,
        str(GENERATOR),
        "--themes",
        args.themes,
        "--chains-per-theme",
        str(args.chains_per_theme),
        "--min-steps",
        str(args.min_steps),
        "--max-steps",
        str(args.max_steps),
        "--max-repeat-per-task",
        str(args.max_repeat_per_task),
        "--theme-task-cap",
        str(args.theme_task_cap),
        "--min-dependent-steps",
        str(args.min_dependent_steps),
        "--min-long-dependency-steps",
        str(args.min_long_dependency_steps),
        "--long-dependency-gap",
        str(args.long_dependency_gap),
        "--min-conflict-steps",
        str(args.min_conflict_steps),
        "--constraint-retries",
        str(args.constraint_retries),
        "--seed",
        str(seed),
    ]


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    seed_run_root = output_dir / "seed_runs"
    merged_root = output_dir / "merged"
    by_theme_root = merged_root / "by_theme"
    seed_run_root.mkdir(parents=True, exist_ok=True)
    by_theme_root.mkdir(parents=True, exist_ok=True)

    themes = [x.strip() for x in args.themes.split(",") if x.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    all_unique: dict[str, dict[str, Any]] = {}
    unique_by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    summary: dict[str, Any] = {
        "generator": str(GENERATOR),
        "config": {
            "themes": themes,
            "seeds": seeds,
            "chains_per_theme": args.chains_per_theme,
            "min_steps": args.min_steps,
            "max_steps": args.max_steps,
            "max_repeat_per_task": args.max_repeat_per_task,
            "theme_task_cap": args.theme_task_cap,
            "min_dependent_steps": args.min_dependent_steps,
            "min_long_dependency_steps": args.min_long_dependency_steps,
            "long_dependency_gap": args.long_dependency_gap,
            "min_conflict_steps": args.min_conflict_steps,
            "constraint_retries": args.constraint_retries,
        },
        "seeds": {},
        "merged": {},
    }

    for seed in seeds:
        seed_dir = seed_run_root / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"webagent_seed_{seed}_") as tmp:
            tmpdir = Path(tmp)
            cmd = generator_cmd(args, seed)
            subprocess.run(cmd, cwd=tmpdir, check=True)

            theme_counts = {}
            unique_added = 0
            for theme in themes:
                sampled_file = tmpdir / f"sampled_{theme}.json"
                if not sampled_file.exists():
                    raise SystemExit(f"Missing generated file: {sampled_file}")
                copied = seed_dir / sampled_file.name
                shutil.copy2(sampled_file, copied)
                payload = json.loads(sampled_file.read_text())
                theme_counts[theme] = len(payload)
                for chain in payload:
                    sig = flow_signature(chain)
                    if sig in all_unique:
                        continue
                    chain = dict(chain)
                    chain["pool_signature"] = sig
                    chain["source_seed"] = seed
                    chain["source_file"] = str(copied)
                    all_unique[sig] = chain
                    unique_by_theme[chain["theme"]].append(chain)
                    unique_added += 1
            summary["seeds"][str(seed)] = {
                "theme_counts": theme_counts,
                "unique_added": unique_added,
            }

    merged_all = sorted(
        all_unique.values(),
        key=lambda x: (x.get("theme", ""), x.get("chain_id", ""), x["pool_signature"]),
    )
    (merged_root / "combined_clean_pool.json").write_text(
        json.dumps(merged_all, ensure_ascii=False, indent=2)
    )

    for theme in sorted(unique_by_theme):
        chains = sorted(
            unique_by_theme[theme],
            key=lambda x: (x.get("chain_id", ""), x["pool_signature"]),
        )
        (by_theme_root / f"sampled_{theme}.json").write_text(
            json.dumps(chains, ensure_ascii=False, indent=2)
        )

    summary["merged"] = {
        "total_unique_flows": len(merged_all),
        "unique_per_theme": {theme: len(unique_by_theme[theme]) for theme in sorted(unique_by_theme)},
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
