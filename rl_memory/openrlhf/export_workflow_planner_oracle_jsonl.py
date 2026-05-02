#!/usr/bin/env python3
"""Export train-split workflow planner oracle rows for SFT warm starts.

The existing OpenRLHF workflow exporter materializes an oracle path into a
fixed sequence of atomic web tasks. That teaches browser actions inside a
chosen module, but it does not supervise the module planner. This exporter keeps
the planner decision point:

    workflow goal + current symbolic state + candidate modules -> next module id

Only train-split workflow assets are accepted by default.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = ROOT / "tasks"
DEFAULT_BATCH_ROOT = TASKS_ROOT / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_MODULES = TASKS_ROOT / "workflow_module_library.json"
DEFAULT_SOURCE_ROOT = ROOT / "rl_memory" / "openrlhf" / "data" / "workflow_v20_train_grpo_100_20_0"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rl_memory.scripts.run_workflow_benchmark import (  # noqa: E402
    MODULE_CHOOSER_SYSTEM_PROMPT,
    allowed_modules_from_oracle,
    apply_effects,
    choose_reference_next_module,
    load_json,
    render_module_prompt,
    shortlist_candidates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--split", choices=["train"], default="train")
    parser.add_argument("--modules", type=Path, default=DEFAULT_MODULES)
    parser.add_argument("--source-train-jsonl", type=Path, default=DEFAULT_SOURCE_ROOT / "train.jsonl")
    parser.add_argument("--source-val-jsonl", type=Path, default=DEFAULT_SOURCE_ROOT / "val.jsonl")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--train-workflows", type=int, default=10)
    parser.add_argument("--val-workflows", type=int, default=2)
    parser.add_argument("--selection", choices=["stratified", "first"], default="stratified")
    parser.add_argument("--candidate-limit", type=int, default=6)
    parser.add_argument("--target-backward-depth", type=int, default=2)
    parser.add_argument("--planner-repeat", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-atomic", action="store_true", help="Also export mixed_sft with oracle browser-action rows.")
    parser.add_argument("--include-done", action="store_true", help="Include planner DONE rows when the oracle path ends.")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def select_rows(rows: list[dict[str, Any]], limit: int, strategy: str) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if strategy == "first":
        return rows[:limit]
    buckets: dict[str, list[dict[str, Any]]] = {}
    theme_order: list[str] = []
    for row in rows:
        theme = str(row.get("theme") or row.get("episode", {}).get("theme") or "unknown")
        if theme not in buckets:
            buckets[theme] = []
            theme_order.append(theme)
        buckets[theme].append(row)
    selected: list[dict[str, Any]] = []
    while len(selected) < limit and any(buckets.values()):
        for theme in theme_order:
            if buckets[theme]:
                selected.append(buckets[theme].pop(0))
                if len(selected) >= limit:
                    break
    return selected


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def planner_prompt(user_prompt: str) -> str:
    return (
        "SYSTEM:\n"
        f"{MODULE_CHOOSER_SYSTEM_PROMPT.strip()}\n\n"
        "USER:\n"
        f"{user_prompt}\n\n"
        "ASSISTANT:"
    )


def quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def clean_inline(value: Any) -> str:
    raw = str(value or "").replace("\n", " ").strip()
    return " ".join(raw.split())


def serialize_trace_action(step: dict[str, Any]) -> str | None:
    act = str(step.get("act") or "").strip().lower()
    selector = clean_inline(step.get("selector"))
    value = clean_inline(step.get("value"))
    url = clean_inline(step.get("url"))
    if act == "open":
        return f"GOTO({quote(url)})" if url else None
    if act == "click":
        return f"CLICK({selector})" if selector else None
    if act == "type":
        return f"TYPE({selector}, {quote(value)})" if selector else None
    if act == "select":
        return f"SELECT({selector}, {quote(value)})" if selector else None
    if act == "check":
        return f"CHECK({selector})" if selector else None
    if act == "uncheck":
        return f"UNCHECK({selector})" if selector else None
    if act == "upload":
        return f"UPLOAD({selector}, {quote(value)})" if selector and value else None
    if act == "wait":
        return "WAIT()"
    if act == "done":
        return "DONE()"
    return None


def atomic_prompt(row: dict[str, Any], step: dict[str, Any], current_url: str, history: list[str]) -> str:
    history_block = "\n".join(f"{idx + 1}. {action}" for idx, action in enumerate(history[-8:])) if history else "None"
    criteria = step.get("success_criteria") or []
    criteria_block = "\n".join(f"- {item}" for item in criteria[:4]) if criteria else "- Not provided"
    return (
        "You are a browser agent in the webagent benchmark.\n"
        "Return exactly one next action and nothing else.\n"
        "Allowed actions: CLICK(...), TYPE(...), SELECT(...), CHECK(...), UNCHECK(...), "
        "UPLOAD(...), GOTO(...), WAIT(), DONE().\n\n"
        f"Workflow: {row.get('id')}\n"
        f"Workflow instruction: {row.get('episode', {}).get('workflow_instruction', '')}\n"
        f"Task: {step.get('task_id', '')}\n"
        f"Instruction: {step.get('instruction', '')}\n"
        f"Current URL hint: {current_url or 'unknown'}\n"
        "Success criteria:\n"
        f"{criteria_block}\n\n"
        "Previous actions:\n"
        f"{history_block}\n\n"
        "Return exactly one next action."
    )


def build_atomic_rows(row: dict[str, Any], split_name: str) -> list[dict[str, Any]]:
    episode = row.get("episode") or {}
    rows: list[dict[str, Any]] = []
    for task_pos, step in enumerate(episode.get("steps") or []):
        raw_trace = step.get("oracle_trace_override") or []
        serialized = [(item, serialize_trace_action(item)) for item in raw_trace]
        filtered = [(item, action) for item, action in serialized if action]
        if not filtered:
            continue
        current_url = ""
        start_idx = 0
        if str(filtered[0][0].get("act") or "").lower() == "open":
            current_url = clean_inline(filtered[0][0].get("url"))
            start_idx = 1
        history: list[str] = []
        for local_idx in range(start_idx, len(filtered)):
            _, action = filtered[local_idx]
            assert action is not None
            rows.append(
                {
                    "id": f"{row.get('id')}:atomic:{task_pos}:{local_idx}",
                    "split": split_name,
                    "source": "workflow_atomic_oracle",
                    "workflow_id": row.get("id"),
                    "theme": row.get("theme"),
                    "module_id": step.get("module_id"),
                    "task_id": step.get("task_id"),
                    "task_position": task_pos,
                    "oracle_step_index": local_idx,
                    "prompt": atomic_prompt(row, step, current_url, history),
                    "response": action,
                }
            )
            history.append(action)
            if action.startswith("GOTO("):
                current_url = action[len("GOTO("):-1].strip().strip("\"").strip("'")
        if history:
            rows.append(
                {
                    "id": f"{row.get('id')}:atomic:{task_pos}:done",
                    "split": split_name,
                    "source": "workflow_atomic_oracle",
                    "workflow_id": row.get("id"),
                    "theme": row.get("theme"),
                    "module_id": step.get("module_id"),
                    "task_id": step.get("task_id"),
                    "task_position": task_pos,
                    "oracle_step_index": len(filtered),
                    "prompt": atomic_prompt(row, step, current_url, history),
                    "response": "DONE()",
                }
            )
    return rows


def build_planner_rows_for_workflow(
    *,
    row: dict[str, Any],
    split_name: str,
    batch_root: Path,
    split: str,
    modules_doc: dict[str, Any],
    candidate_limit: int,
    backward_depth: int,
    include_done: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workflow_id = str(row.get("id") or row.get("label") or row.get("episode", {}).get("workflow_goal_id") or "")
    split_root = batch_root / split
    goal = load_json(split_root / "workflow_goal_instances" / f"{workflow_id}.json")
    oracle = load_json(split_root / "workflow_oracles" / f"{workflow_id}.json")
    modules_by_id = {item["module_id"]: item for item in modules_doc["modules"]}
    allowed_module_ids = allowed_modules_from_oracle(oracle)
    max_module_invocations = int(goal.get("max_module_invocations", 0) or len(oracle.get("reference_invocations", [])) or 1)

    state = set(goal.get("initial_world_state", []))
    successful_modules: list[str] = []
    successful_invocations: set[str] = set()
    failed_modules: set[str] = set()
    planner_rows: list[dict[str, Any]] = []
    skipped_missing_candidate = 0
    stopped_reason = "max_turns"

    for turn in range(1, max_module_invocations + 1):
        remaining_targets = set(goal.get("target_state", [])) - state
        candidates = shortlist_candidates(
            modules_doc=modules_doc,
            state=state,
            remaining_targets=remaining_targets,
            theme=goal["theme"],
            candidate_limit=candidate_limit,
            backward_depth=backward_depth,
            failed_modules=failed_modules,
            successful_modules=successful_modules,
            remaining_invocations=max_module_invocations - turn + 1,
            allowed_module_ids=allowed_module_ids,
        )
        chosen_module_id, _, decision_meta = choose_reference_next_module(
            oracle,
            successful_modules,
            successful_invocations,
        )

        if chosen_module_id == "DONE":
            stopped_reason = "oracle_done"
            if include_done and candidates:
                prompt_body = render_module_prompt(goal, state, remaining_targets, candidates, successful_modules, failed_modules)
                planner_rows.append(
                    {
                        "id": f"{workflow_id}:planner:{turn}",
                        "split": split_name,
                        "source": "workflow_planner_oracle",
                        "workflow_id": workflow_id,
                        "theme": goal.get("theme"),
                        "turn": turn,
                        "selected_path_id": (oracle.get("success_paths") or [{}])[0].get("path_id", ""),
                        "reference_invocation_id": "",
                        "state_before": sorted(state),
                        "remaining_targets": sorted(remaining_targets),
                        "successful_modules": list(successful_modules),
                        "candidate_module_ids": [item["module_id"] for item in candidates],
                        "prompt": planner_prompt(prompt_body),
                        "response": "DONE",
                    }
                )
            break

        candidate_ids = {item["module_id"] for item in candidates}
        if chosen_module_id not in candidate_ids:
            skipped_missing_candidate += 1
        else:
            prompt_body = render_module_prompt(goal, state, remaining_targets, candidates, successful_modules, failed_modules)
            planner_rows.append(
                {
                    "id": f"{workflow_id}:planner:{turn}",
                    "split": split_name,
                    "source": "workflow_planner_oracle",
                    "workflow_id": workflow_id,
                    "theme": goal.get("theme"),
                    "turn": turn,
                    "selected_path_id": (oracle.get("success_paths") or [{}])[0].get("path_id", ""),
                    "reference_invocation_id": str(decision_meta.get("reference_invocation_id") or ""),
                    "state_before": sorted(state),
                    "remaining_targets": sorted(remaining_targets),
                    "successful_modules": list(successful_modules),
                    "candidate_module_ids": [item["module_id"] for item in candidates],
                    "prompt": planner_prompt(prompt_body),
                    "response": chosen_module_id,
                }
            )

        module = modules_by_id.get(chosen_module_id)
        if module is None:
            stopped_reason = "unknown_oracle_module"
            break
        successful_modules.append(chosen_module_id)
        reference_invocation_id = str(decision_meta.get("reference_invocation_id") or "")
        if reference_invocation_id:
            successful_invocations.add(reference_invocation_id)
        state = apply_effects(state, module)
    else:
        if set(goal.get("target_state", [])) <= state:
            stopped_reason = "target_satisfied_at_max_turns"

    return planner_rows, {
        "workflow_id": workflow_id,
        "split": split_name,
        "theme": goal.get("theme"),
        "planner_rows": len(planner_rows),
        "skipped_missing_candidate": skipped_missing_candidate,
        "final_state_covers_target": set(goal.get("target_state", [])) <= state,
        "stopped_reason": stopped_reason,
    }


def export_split(
    *,
    rows: list[dict[str, Any]],
    split_name: str,
    args: argparse.Namespace,
    modules_doc: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    planner_rows: list[dict[str, Any]] = []
    atomic_rows: list[dict[str, Any]] = []
    workflow_summaries: list[dict[str, Any]] = []
    for row in rows:
        built, summary = build_planner_rows_for_workflow(
            row=row,
            split_name=split_name,
            batch_root=args.batch_root,
            split=args.split,
            modules_doc=modules_doc,
            candidate_limit=args.candidate_limit,
            backward_depth=args.target_backward_depth,
            include_done=args.include_done,
        )
        planner_rows.extend(built)
        workflow_summaries.append(summary)
        if args.include_atomic:
            atomic_rows.extend(build_atomic_rows(row, split_name))
    return planner_rows, atomic_rows, workflow_summaries


def main() -> None:
    args = parse_args()
    modules_doc = load_json(args.modules)
    train_source = select_rows(read_jsonl(args.source_train_jsonl), args.train_workflows, args.selection)
    val_source = select_rows(read_jsonl(args.source_val_jsonl), args.val_workflows, args.selection)

    train_planner, train_atomic, train_summaries = export_split(
        rows=train_source,
        split_name="train",
        args=args,
        modules_doc=modules_doc,
    )
    val_planner, val_atomic, val_summaries = export_split(
        rows=val_source,
        split_name="val",
        args=args,
        modules_doc=modules_doc,
    )

    rng = random.Random(args.seed)
    write_jsonl(args.output_root / "planner_sft" / "train.jsonl", train_planner)
    write_jsonl(args.output_root / "planner_sft" / "val.jsonl", val_planner)
    write_jsonl(args.output_root / "planner_sft" / "test.jsonl", [])

    mixed_train = train_planner * max(1, args.planner_repeat) + train_atomic
    mixed_val = val_planner * max(1, args.planner_repeat) + val_atomic
    rng.shuffle(mixed_train)
    rng.shuffle(mixed_val)
    write_jsonl(args.output_root / "mixed_sft" / "train.jsonl", mixed_train)
    write_jsonl(args.output_root / "mixed_sft" / "val.jsonl", mixed_val)
    write_jsonl(args.output_root / "mixed_sft" / "test.jsonl", [])

    summary = {
        "batch_root": str(args.batch_root),
        "split": args.split,
        "source_train_jsonl": str(args.source_train_jsonl),
        "source_val_jsonl": str(args.source_val_jsonl),
        "train_workflows": len(train_source),
        "val_workflows": len(val_source),
        "selection": args.selection,
        "candidate_limit": args.candidate_limit,
        "target_backward_depth": args.target_backward_depth,
        "planner_repeat": args.planner_repeat,
        "include_atomic": bool(args.include_atomic),
        "counts": {
            "planner_train": len(train_planner),
            "planner_val": len(val_planner),
            "atomic_train": len(train_atomic),
            "atomic_val": len(val_atomic),
            "mixed_train": len(mixed_train),
            "mixed_val": len(mixed_val),
        },
        "workflow_summaries": train_summaries + val_summaries,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
