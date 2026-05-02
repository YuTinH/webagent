#!/usr/bin/env python3
"""Run block-wise online adaptation over workflow benchmark goal streams.

This launcher enforces a clean update cadence:

1. A block reads only the memory snapshot produced before the block.
2. New experience from the block is written to a separate delta store.
3. After the block finishes, snapshot + delta are merged into the next snapshot.

That gives a defensible test-time learning protocol: no instance inside a block
can retrieve memories produced by earlier instances from the same block.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_SCRIPT = ROOT / "rl_memory" / "scripts" / "run_workflow_benchmark_goalset_shards.sh"

sys.path.insert(0, str(ROOT))


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_goals(batch_root: Path, split: str, goal_list: Path | None, limit: int) -> list[str]:
    if goal_list:
        goals = [
            line.strip()
            for line in goal_list.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        manifest = _read_json(batch_root / split / "manifest.json", {})
        goals = [
            str(item.get("goal_id", "")).strip()
            for item in (manifest.get("goals") or [])
            if str(item.get("goal_id", "")).strip()
        ]
        if not goals:
            goal_dir = batch_root / split / "workflow_goal_instances"
            goals = [path.stem for path in sorted(goal_dir.glob("*.json"))]
    if limit > 0:
        goals = goals[:limit]
    return goals


def _chunks(items: list[str], block_size: int) -> list[list[str]]:
    return [items[idx : idx + block_size] for idx in range(0, len(items), block_size)]


def _empty_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def _copy_or_empty(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copyfile(src, dst)
    else:
        dst.write_text("[]\n", encoding="utf-8")


def _merge_reflexion(snapshot: Path, delta: Path, out: Path) -> int:
    merged = list(_read_json(snapshot, [])) + list(_read_json(delta, []))
    _write_json(out, merged)
    return len(merged)


def _merge_trajectory(snapshot: Path, delta: Path, out: Path) -> int:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, bool]] = set()
    for item in list(_read_json(snapshot, [])) + list(_read_json(delta, [])):
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("task_id", "")),
            str(item.get("action_sketch", item.get("retrieval_text", ""))),
            bool(item.get("online_source", False)),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    _write_json(out, merged)
    return len(merged)


def _merge_memorybank(method: str, snapshot: Path, delta: Path, out: Path) -> int:
    _copy_or_empty(snapshot, out)
    entries = list(_read_json(delta, []))
    if not entries:
        return len(_read_json(out, []))
    if method == "memorybank":
        from rl_memory.memory_baselines.memorybank.store import MemoryBankStore

        store = MemoryBankStore(out)
    elif method == "memorybank_lite":
        from rl_memory.memory_baselines.memorybank_lite.store import MemoryBankLiteStore

        store = MemoryBankLiteStore(out)
    else:
        raise ValueError(f"unsupported memorybank method: {method}")
    store.append_many(entries)
    return len(store.load())


def _merge_store(method: str, snapshot: Path, delta: Path, out: Path) -> int:
    if method == "none":
        _copy_or_empty(snapshot, out)
        return len(_read_json(out, []))
    if method == "reflexion":
        return _merge_reflexion(snapshot, delta, out)
    if method in {"memorybank", "memorybank_lite"}:
        return _merge_memorybank(method, snapshot, delta, out)
    if method == "trajectory_rag":
        return _merge_trajectory(snapshot, delta, out)
    raise ValueError(f"unsupported method: {method}")


def _method_env(method: str, snapshot: Path, delta: Path) -> dict[str, str]:
    env: dict[str, str] = {
        "AGENT_MEMORY_METHOD": method,
        "AGENT_DECISION_METHOD": method,
    }
    if method == "none":
        env["AGENT_MEMORY_METHOD"] = "none"
        env["AGENT_DECISION_METHOD"] = "none"
    elif method == "reflexion":
        env.update(
            {
                "AGENT_REFLEXION_RETRIEVE_STORE": str(snapshot),
                "AGENT_REFLEXION_WRITE_STORE": str(delta),
                "AGENT_REFLEXION_STORE": str(delta),
                "AGENT_REFLEXION_TOP_K": os.environ.get("AGENT_REFLEXION_TOP_K", "3"),
            }
        )
    elif method in {"memorybank", "memorybank_lite"}:
        env.update(
            {
                "AGENT_MEMORYBANK_RETRIEVE_STORE": str(snapshot),
                "AGENT_MEMORYBANK_WRITE_STORE": str(delta),
                "AGENT_MEMORYBANK_STORE": str(delta),
                "AGENT_MEMORYBANK_TOP_K": os.environ.get("AGENT_MEMORYBANK_TOP_K", "5"),
                "AGENT_MEMORYBANK_EMBED_MODEL": os.environ.get("AGENT_MEMORYBANK_EMBED_MODEL", ""),
                "AGENT_MEMORYBANK_EMBED_DEVICE": os.environ.get("AGENT_MEMORYBANK_EMBED_DEVICE", "cpu"),
                "AGENT_MEMORYBANK_SUMMARIZER": os.environ.get("AGENT_MEMORYBANK_SUMMARIZER", "heuristic"),
            }
        )
    elif method == "trajectory_rag":
        env.update(
            {
                "AGENT_TRAJECTORY_RAG_RETRIEVE_CORPUS": str(snapshot),
                "AGENT_TRAJECTORY_RAG_WRITE_CORPUS": str(delta),
                "AGENT_TRAJECTORY_RAG_CORPUS": str(delta),
                "AGENT_TRAJECTORY_RAG_ONLINE_WRITE": "1",
                "AGENT_TRAJECTORY_RAG_REBUILD": "0",
                "AGENT_TRAJECTORY_RAG_TOP_K": os.environ.get("AGENT_TRAJECTORY_RAG_TOP_K", "1"),
                "AGENT_TRAJECTORY_RAG_ALLOW_SAME_TASK": os.environ.get("AGENT_TRAJECTORY_RAG_ALLOW_SAME_TASK", "0"),
                "AGENT_TRAJECTORY_RAG_ALLOW_SAME_FAMILY": os.environ.get("AGENT_TRAJECTORY_RAG_ALLOW_SAME_FAMILY", "1"),
            }
        )
    else:
        raise ValueError(f"unsupported method: {method}")
    return env


def _parse_run_dir(stdout: str, run_root: Path, tag: str, split: str) -> Path:
    match = re.search(r"Run dir:\s*(.+)", stdout)
    if match:
        return Path(match.group(1).strip())
    candidates = sorted(run_root.glob(f"*_{tag}_{split}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"Unable to locate run dir for tag={tag}")
    return candidates[0]


def _block_summary(run_dir: Path, split: str) -> dict[str, Any]:
    summary_path = run_dir / f"{split}_combined_summary.json"
    if not summary_path.exists():
        summary_path = run_dir / "train_combined_summary.json"
    if not summary_path.exists():
        summaries = sorted(run_dir.glob("*_combined_summary.json"))
        summary_path = summaries[0] if summaries else summary_path
    data = _read_json(summary_path, {})
    records = data.get("records") or []
    failure_counts: dict[str, int] = {}
    for record in records:
        if record.get("success"):
            continue
        # Workflow summaries keep only episode-level result. Detailed failure
        # categories can be recovered from traces later if needed.
        failure_counts[str(record.get("success_type", "failure"))] = failure_counts.get(str(record.get("success_type", "failure")), 0) + 1
    return {
        "summary_path": str(summary_path) if summary_path.exists() else "",
        "total_goals": int(data.get("total_goals", 0) or len(records)),
        "completed_goals": int(data.get("completed_goals", 0) or len(records)),
        "is_complete": bool(data.get("is_complete", False)),
        "success_count": int(data.get("final_success_count", 0) or sum(1 for item in records if item.get("success"))),
        "success_rate": float(data.get("final_success_rate", 0.0) or 0.0),
        "average_composite_score": float(data.get("average_composite_score", 0.0) or 0.0),
        "failure_counts": failure_counts,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Online Adaptation Pilot Summary",
        "",
        f"- Method: `{payload['method']}`",
        f"- Split: `{payload['split']}`",
        f"- Block size: {payload['block_size']}",
        f"- Goals: {payload['goal_count']}",
        f"- Completed: {payload['completed_goals']}",
        f"- Success: {payload['success_count']}",
        f"- Success rate: {payload['success_rate']:.4f}",
        f"- AULC: {payload['aulc']:.4f}",
        "",
        "## Blocks",
        "",
        "| block | goals | success | success rate | memory items after merge | run dir |",
        "| ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for block in payload["blocks"]:
        lines.append(
            "| {block_index} | {completed_goals}/{total_goals} | {success_count} | {success_rate:.4f} | {memory_items_after_merge} | `{run_dir}` |".format(**block)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run strict block-wise online adaptation experiments.")
    parser.add_argument("--method", choices=["none", "reflexion", "memorybank", "memorybank_lite", "trajectory_rag"], required=True)
    parser.add_argument("--split", choices=["train", "dev", "test"], default="dev")
    parser.add_argument("--batch-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--goal-list", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--block-size", type=int, default=100)
    parser.add_argument("--run-root", type=Path, default=ROOT / "rl_memory" / "runs" / "online_adaptation")
    parser.add_argument("--runner-script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--module-policy", choices=["llm", "heuristic", "reference"], default="reference")
    parser.add_argument("--atomic-policy", choices=["agent", "dry_run"], default="agent")
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--gpu-ids", default="0")
    parser.add_argument("--atomic-max-steps", type=int, default=10)
    parser.add_argument("--atomic-repeat-fail-threshold", type=int, default=2)
    parser.add_argument("--agent-max-tokens", type=int, default=64)
    parser.add_argument("--tag", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.num_shards != 1 and args.method != "none":
        raise SystemExit("Strict online adaptation currently requires --num-shards 1 for memory-writing methods.")

    goals = _load_goals(args.batch_root, args.split, args.goal_list, args.limit)
    if not goals:
        raise SystemExit("No goals selected.")
    blocks = _chunks(goals, max(1, args.block_size))

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    tag = args.tag or f"{args.method}_bs{args.block_size}_n{len(goals)}"
    exp_root = (args.run_root / f"{timestamp}_{tag}_{args.split}").resolve()
    block_run_root = exp_root / "block_runs"
    goal_dir = exp_root / "goal_blocks"
    store_dir = exp_root / "stores"
    exp_root.mkdir(parents=True, exist_ok=True)
    block_run_root.mkdir(parents=True, exist_ok=True)
    goal_dir.mkdir(parents=True, exist_ok=True)
    store_dir.mkdir(parents=True, exist_ok=True)

    snapshot = store_dir / "snapshot_block000.json"
    _empty_store(snapshot)

    payload: dict[str, Any] = {
        "version": 1,
        "method": args.method,
        "split": args.split,
        "block_size": args.block_size,
        "goal_count": len(goals),
        "goals": goals,
        "experiment_root": str(exp_root),
        "blocks": [],
    }
    _write_json(exp_root / "online_adaptation_manifest.json", payload)

    total_completed = 0
    total_success = 0
    aulc_num = 0.0
    aulc_den = 0
    composite_num = 0.0
    composite_den = 0

    for block_index, block_goals in enumerate(blocks):
        block_goal_file = goal_dir / f"block{block_index:03d}.txt"
        block_goal_file.write_text("".join(f"{goal}\n" for goal in block_goals), encoding="utf-8")
        delta = store_dir / f"delta_block{block_index:03d}.json"
        _empty_store(delta)
        next_snapshot = store_dir / f"snapshot_block{block_index + 1:03d}.json"

        block_tag = f"{tag}_block{block_index:03d}"
        env = os.environ.copy()
        env.update(_method_env(args.method, snapshot, delta))
        env.update(
            {
                "RUN_ROOT": str(block_run_root),
                "TAG": block_tag,
                "SPLIT": args.split,
                "BATCH_ROOT": str(args.batch_root),
                "SNAPSHOT_ROOT": str(args.runtime_root),
                "MODULE_POLICY": args.module_policy,
                "ATOMIC_POLICY": args.atomic_policy,
                "NUM_SHARDS": str(args.num_shards),
                "GPU_IDS": args.gpu_ids,
                "ATOMIC_MAX_STEPS": str(args.atomic_max_steps),
                "ATOMIC_REPEAT_FAIL_THRESHOLD": str(args.atomic_repeat_fail_threshold),
                "AGENT_MAX_TOKENS": str(args.agent_max_tokens),
            }
        )

        command = ["bash", str(args.runner_script), str(block_goal_file)]
        if args.dry_run:
            print("DRY_RUN", " ".join(command))
            run_dir = block_run_root / f"DRY_RUN_{block_tag}_{args.split}"
            summary = {
                "summary_path": "",
                "total_goals": len(block_goals),
                "completed_goals": 0,
                "is_complete": False,
                "success_count": 0,
                "success_rate": 0.0,
                "average_composite_score": 0.0,
                "failure_counts": {},
            }
        else:
            proc = subprocess.run(command, cwd=str(ROOT), env=env, text=True, capture_output=True)
            (exp_root / f"block{block_index:03d}.stdout.log").write_text(proc.stdout, encoding="utf-8")
            (exp_root / f"block{block_index:03d}.stderr.log").write_text(proc.stderr, encoding="utf-8")
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Block {block_index} failed with exit code {proc.returncode}. "
                    f"See {exp_root / f'block{block_index:03d}.stderr.log'}"
                )
            run_dir = _parse_run_dir(proc.stdout + "\n" + proc.stderr, block_run_root, block_tag, args.split)
            summary = _block_summary(run_dir, args.split)

        memory_items = _merge_store(args.method, snapshot, delta, next_snapshot)
        block_payload = {
            "block_index": block_index,
            "goal_file": str(block_goal_file),
            "goals": block_goals,
            "retrieve_snapshot": str(snapshot),
            "delta_store": str(delta),
            "next_snapshot": str(next_snapshot),
            "memory_items_after_merge": memory_items,
            "run_dir": str(run_dir),
            **summary,
        }
        payload["blocks"].append(block_payload)
        total_completed += int(summary["completed_goals"])
        total_success += int(summary["success_count"])
        aulc_num += float(summary["success_rate"]) * int(summary["completed_goals"])
        aulc_den += int(summary["completed_goals"])
        composite_num += float(summary["average_composite_score"]) * int(summary["completed_goals"])
        composite_den += int(summary["completed_goals"])
        payload["completed_goals"] = total_completed
        payload["success_count"] = total_success
        payload["success_rate"] = total_success / total_completed if total_completed else 0.0
        payload["aulc"] = aulc_num / aulc_den if aulc_den else 0.0
        payload["average_composite_score"] = composite_num / composite_den if composite_den else 0.0
        _write_json(exp_root / "online_adaptation_manifest.json", payload)
        _write_markdown(exp_root / "online_adaptation_summary.md", payload)
        print(
            json.dumps(
                {
                    "block": block_index,
                    "run_dir": str(run_dir),
                    "completed": summary["completed_goals"],
                    "success": summary["success_count"],
                    "success_rate": summary["success_rate"],
                    "memory_items": memory_items,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        snapshot = next_snapshot

    _write_json(exp_root / "online_adaptation_manifest.json", payload)
    _write_markdown(exp_root / "online_adaptation_summary.md", payload)
    print(json.dumps({"experiment_root": str(exp_root), "success_rate": payload["success_rate"], "aulc": payload["aulc"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
