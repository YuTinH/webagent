#!/usr/bin/env python3
"""Export workflow-v20 reference paths as OpenRLHF multi-turn episodes.

This is a smoke/training bridge for the existing OpenRLHF agent adapter.  It
does not train the workflow module planner directly; each exported episode is a
reference workflow path whose modules are materialized as atomic web tasks.
The policy learns browser actions inside those workflow modules, while dev/test
workflow evaluation remains held out.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = ROOT / "tasks"
DEFAULT_BATCH_ROOT = TASKS_ROOT / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_BINDINGS = TASKS_ROOT / "workflow_module_bindings.json"

sys.path.insert(0, str(ROOT))

from rl_memory.scripts.run_workflow_episode import (  # noqa: E402
    build_execution_plan,
    instantiate_atomic_task,
    load_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--split", choices=["train", "dev", "test"], default="train")
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-count", type=int, default=8)
    parser.add_argument("--val-count", type=int, default=2)
    parser.add_argument("--test-count", type=int, default=0)
    parser.add_argument("--max-modules", type=int, default=5)
    parser.add_argument("--goal-id", action="append", default=[])
    return parser.parse_args()


def _read_goal_refs(batch_root: Path, split: str, goal_ids: list[str]) -> list[dict[str, Any]]:
    manifest = load_json(batch_root / split / "manifest.json")
    refs = list(manifest.get("goals", []))
    if goal_ids:
        allowed = set(goal_ids)
        refs = [item for item in refs if item.get("goal_id") in allowed]
    return refs


def _materialize_episode(
    *,
    batch_root: Path,
    split: str,
    bindings_doc: dict[str, Any],
    goal_ref: dict[str, Any],
    max_modules: int,
) -> dict[str, Any] | None:
    split_root = batch_root / split
    goal_id = str(goal_ref["goal_id"])
    goal = load_json(split_root / "workflow_goal_instances" / f"{goal_id}.json")
    oracle = load_json(split_root / "workflow_oracles" / f"{goal_id}.json")
    path = (oracle.get("success_paths") or [{}])[0]
    if not path.get("reference_invocation_ids"):
        return None

    plan, path_id = build_execution_plan(
        goal=goal,
        oracle=oracle,
        bindings_doc=bindings_doc,
        path_id=path.get("path_id"),
        module_trace_json=None,
    )
    if max_modules > 0:
        plan = plan[:max_modules]
    if not plan:
        return None

    stage_root = TASKS_ROOT / "_workflow_runtime" / goal_id
    steps: list[dict[str, Any]] = []
    for item in plan:
        spec_path, oracle_path = instantiate_atomic_task(item, item, stage_root)
        spec = load_json(spec_path)
        trace = load_json(oracle_path)
        task_id = str(spec_path.parent.relative_to(TASKS_ROOT))
        steps.append(
            {
                "task_id": task_id,
                "module_id": item.get("module_id", ""),
                "binding_id": item.get("binding_id", ""),
                "binding_task_id": item.get("binding_task_id", ""),
                "invocation_id": item.get("invocation_id", ""),
                "instruction": spec.get("goal", item.get("description", "")),
                "success_criteria": spec.get("success_criteria", []),
                "scoring_checkpoints": spec.get("scoring_checkpoints", []),
                "oracle_trace_override": trace.get("steps", []),
                "difficulty": 1,
            }
        )

    return {
        "chain_id": goal_id,
        "workflow_goal_id": goal_id,
        "theme": goal.get("theme", goal_ref.get("theme", "")),
        "difficulty": goal.get("difficulty", goal_ref.get("difficulty", 0)),
        "selected_path_id": path_id,
        "workflow_instruction": goal.get("instruction", ""),
        "initial_state": {},
        "initial_world_state": goal.get("initial_world_state", []),
        "target_state": goal.get("target_state", []),
        "steps": steps,
    }


def _make_record(episode: dict[str, Any]) -> dict[str, Any]:
    first = (episode.get("steps") or [{}])[0]
    observation = (
        f"Theme: {episode.get('theme')}\n"
        f"Workflow: {episode.get('workflow_goal_id')}\n"
        f"Workflow instruction: {episode.get('workflow_instruction')}\n"
        f"Current task: {first.get('task_id', '')}\n"
        f"Instruction: {first.get('instruction', '')}\n"
        "Return exactly one browser action."
    )
    row_id = str(episode["workflow_goal_id"])
    return {
        "id": row_id,
        "label": row_id,
        "theme": episode.get("theme", ""),
        "num_steps": len(episode.get("steps", [])),
        "observation": observation,
        "episode": episode,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.split != "train":
        raise SystemExit("Refusing to export non-train split for RL data. Use --split train.")

    bindings_doc = load_json(args.bindings)
    goal_refs = _read_goal_refs(args.batch_root, args.split, args.goal_id)
    needed = args.train_count + args.val_count + args.test_count
    if needed <= 0:
        raise SystemExit("At least one output record is required.")

    episodes: list[dict[str, Any]] = []
    skipped = 0
    for ref in goal_refs:
        episode = _materialize_episode(
            batch_root=args.batch_root,
            split=args.split,
            bindings_doc=bindings_doc,
            goal_ref=ref,
            max_modules=args.max_modules,
        )
        if episode is None:
            skipped += 1
            continue
        episodes.append(episode)
        if len(episodes) >= needed:
            break

    if len(episodes) < needed:
        raise SystemExit(f"Only exported {len(episodes)} episodes; needed {needed}. Skipped {skipped}.")

    train_rows = [_make_record(item) for item in episodes[: args.train_count]]
    val_rows = [_make_record(item) for item in episodes[args.train_count : args.train_count + args.val_count]]
    test_rows = [_make_record(item) for item in episodes[args.train_count + args.val_count :]]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "train.jsonl", train_rows)
    _write_jsonl(args.output_dir / "val.jsonl", val_rows)
    _write_jsonl(args.output_dir / "test.jsonl", test_rows)

    index: dict[str, Any] = {}
    for row in train_rows + val_rows + test_rows:
        index[str(row["id"])] = row["episode"]
        index[str(row["label"])] = row["episode"]
    (args.output_dir / "episode_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "batch_root": str(args.batch_root),
        "split": args.split,
        "counts": {"train": len(train_rows), "val": len(val_rows), "test": len(test_rows)},
        "max_modules": args.max_modules,
        "episodes": [item["workflow_goal_id"] for item in episodes],
        "skipped": skipped,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
