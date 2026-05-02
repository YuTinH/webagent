#!/usr/bin/env python3
"""Compute WFG-R1 dense rewards from workflow benchmark outputs.

Inputs can be:
- a benchmark summary JSON containing `records`,
- an online adaptation experiment directory/manifest,
- a single `workflow_run_summary.json`,
- a run directory containing one of the above.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


REWARD_NAME = "WFG-R1"
REWARD_VERSION = 1


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "success", "passed"}
    return bool(value)


def _normalize_path(path: str | Path, base: Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute() or base is None:
        return p
    return (base / p).resolve()


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _find_summary_file(path: Path) -> Path:
    if path.is_file():
        return path
    candidates = [
        path / "online_adaptation_manifest.json",
        path / "dev_combined_summary.json",
        path / "train_combined_summary.json",
        path / "test_combined_summary.json",
        path / "dev_summary.json",
        path / "train_summary.json",
        path / "test_summary.json",
        path / "workflow_run_summary.json",
    ]
    found = _first_existing(candidates)
    if found is not None:
        return found
    summaries = sorted(path.glob("*_combined_summary.json")) + sorted(path.glob("*_summary.json"))
    if summaries:
        return summaries[0]
    raise FileNotFoundError(f"Unable to locate a supported summary file under {path}")


def _goal_id(record: dict[str, Any]) -> str:
    return str(record.get("goal_id", "")).strip()


def _theme(record: dict[str, Any]) -> str:
    return str(record.get("theme", "unknown")).strip() or "unknown"


def _hard_violation_count(record: dict[str, Any], evaluation: dict[str, Any] | None = None) -> int:
    raw = record.get("hard_constraint_violations")
    if raw is None and evaluation:
        raw = evaluation.get("hard_constraint_violations")
    if isinstance(raw, list):
        return len(raw)
    if isinstance(raw, dict):
        return len(raw)
    if raw:
        return 1
    return 0


def _load_record_sidecars(record: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    out_dir_raw = record.get("output_dir")
    if not out_dir_raw:
        return None, None, []
    out_dir = Path(str(out_dir_raw))
    evaluation = _read_json(out_dir / "workflow_execution_evaluation.json")
    trace = _read_json(out_dir / "workflow_execution_trace.json")
    selection_trace = _read_json(out_dir / "workflow_module_selection_trace.json", [])
    if not isinstance(evaluation, dict):
        evaluation = None
    if not isinstance(trace, dict):
        trace = None
    if not isinstance(selection_trace, list):
        selection_trace = []
    return evaluation, trace, selection_trace


def _atomic_progress(atomic: dict[str, Any]) -> float:
    if not isinstance(atomic, dict):
        return 0.0
    for key in ("step_progress", "checkpoint_weight_earned"):
        if key in atomic:
            return _clip(_float(atomic.get(key)), 0.0, 1.0)
    if "checkpoint_score_percent" in atomic:
        return _clip(_float(atomic.get("checkpoint_score_percent")) / 100.0, 0.0, 1.0)
    if _int(atomic.get("checkpoint_total")) > 0:
        return _clip(_float(atomic.get("checkpoint_passed")) / max(1, _int(atomic.get("checkpoint_total"))), 0.0, 1.0)
    if _int(atomic.get("criteria_total")) > 0:
        return _clip(_float(atomic.get("criteria_passed")) / max(1, _int(atomic.get("criteria_total"))), 0.0, 1.0)
    return 1.0 if _as_bool(atomic.get("success")) else 0.0


def _is_repeat_loop(atomic: dict[str, Any]) -> bool:
    text = " ".join(str(atomic.get(key, "")) for key in ("end_reason", "failure_category", "failure_bucket"))
    return "repeat" in text.lower() and "loop" in text.lower() or "repeat_action" in text.lower()


def _is_premature_done(atomic: dict[str, Any]) -> bool:
    end_reason = str(atomic.get("end_reason", "")).lower()
    category = str(atomic.get("failure_category", "")).lower()
    return (not _as_bool(atomic.get("success"))) and ("done" in end_reason or "premature_done" in category)


def _is_invalid_action(atomic: dict[str, Any]) -> bool:
    text = " ".join(str(atomic.get(key, "")) for key in ("end_reason", "failure_category", "step_error_message", "verify_error"))
    lowered = text.lower()
    needles = [
        "invalid_action",
        "parse_error",
        "unsupported",
        "selector",
        "element_not_found",
        "timeout",
        "strict mode violation",
    ]
    return any(token in lowered for token in needles)


def _selector_valid(atomic: dict[str, Any]) -> bool:
    return not _is_invalid_action(atomic)


def compute_module_reward(atomic: dict[str, Any]) -> dict[str, Any]:
    progress = _atomic_progress(atomic)
    success = 1.0 if _as_bool(atomic.get("success")) else 0.0
    selector_valid = 1.0 if _selector_valid(atomic) else 0.0
    repeat_loop = 1.0 if _is_repeat_loop(atomic) else 0.0
    premature_done = 1.0 if _is_premature_done(atomic) else 0.0
    invalid_action = 1.0 if _is_invalid_action(atomic) else 0.0
    reward = (
        0.75 * progress
        + 0.15 * success
        + 0.10 * selector_valid
        - 0.25 * repeat_loop
        - 0.30 * premature_done
        - 0.40 * invalid_action
    )
    return {
        "module_reward": round(_clip(reward), 6),
        "step_progress": round(progress, 6),
        "module_success": bool(success),
        "selector_valid": bool(selector_valid),
        "repeat_loop": bool(repeat_loop),
        "premature_done": bool(premature_done),
        "invalid_action": bool(invalid_action),
    }


def _module_rewards_from_trace(trace: dict[str, Any] | None, selection_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_modules: list[dict[str, Any]] = []
    if trace and isinstance(trace.get("executed_modules"), list):
        raw_modules = [item for item in trace.get("executed_modules", []) if isinstance(item, dict)]
    elif selection_trace:
        raw_modules = [item for item in selection_trace if isinstance(item, dict)]

    rewards = []
    for idx, module in enumerate(raw_modules, start=1):
        atomic = module.get("atomic_result") if isinstance(module.get("atomic_result"), dict) else {}
        reward_payload = compute_module_reward(atomic)
        rewards.append(
            {
                "index": idx,
                "module_id": module.get("module_id", ""),
                "status": module.get("status", ""),
                "binding_task_id": module.get("binding_task_id", ""),
                "failure_category": atomic.get("failure_category", ""),
                "end_reason": atomic.get("end_reason", ""),
                **reward_payload,
            }
        )
    return rewards


def _checkpoint_progress(record: dict[str, Any], module_rewards: list[dict[str, Any]]) -> float:
    for key in ("checkpoint_progress", "step_progress"):
        if key in record:
            return _clip(_float(record.get(key)), 0.0, 1.0)
    if module_rewards:
        return _clip(sum(_float(item.get("step_progress")) for item in module_rewards) / len(module_rewards), 0.0, 1.0)
    return _clip(_float(record.get("target_state_coverage")), 0.0, 1.0)


def _invalid_transition_indices(evaluation: dict[str, Any] | None) -> set[int]:
    if not evaluation:
        return set()
    indices: set[int] = set()
    for item in evaluation.get("invalid_transitions") or []:
        if not isinstance(item, dict):
            continue
        idx = _int(item.get("index"), -1)
        if idx > 0:
            indices.add(idx)
    return indices


def _module_completion_counts(
    module_rewards: list[dict[str, Any]],
    evaluation: dict[str, Any] | None,
    invalid_transition_count: int,
) -> dict[str, Any]:
    attempted = len(module_rewards)
    atomic_completed = sum(1 for item in module_rewards if item.get("module_success"))
    invalid_indices = _invalid_transition_indices(evaluation)

    if invalid_indices:
        legal_completed = sum(
            1
            for item in module_rewards
            if item.get("module_success") and _int(item.get("index")) not in invalid_indices
        )
    elif invalid_transition_count > 0:
        # If detailed transition indices are unavailable, conservatively assume
        # invalid transitions consumed successful module completions first.
        legal_completed = max(0, atomic_completed - invalid_transition_count)
    else:
        legal_completed = atomic_completed

    return {
        "attempted_module_count": attempted,
        "atomic_completed_module_count": atomic_completed,
        "legal_completed_module_count": legal_completed,
        "legal_module_completion_rate": (legal_completed / attempted) if attempted else 0.0,
    }


def _efficiency_score(record: dict[str, Any], evaluation: dict[str, Any] | None = None) -> float:
    if evaluation:
        score_breakdown = evaluation.get("score_breakdown") or {}
        if "efficiency_score" in score_breakdown:
            return _clip(_float(score_breakdown.get("efficiency_score"), 1.0), 0.0, 1.0)
    if "efficiency_score" in record:
        return _clip(_float(record.get("efficiency_score"), 1.0), 0.0, 1.0)
    return 1.0


def compute_episode_reward(record: dict[str, Any]) -> dict[str, Any]:
    evaluation, trace, selection_trace = _load_record_sidecars(record)
    module_rewards = _module_rewards_from_trace(trace, selection_trace)

    final_success = bool(record.get("success") if "success" in record else record.get("final_success", False))
    target_coverage = _clip(_float(record.get("target_state_coverage")), 0.0, 1.0)
    checkpoint_progress = _checkpoint_progress(record, module_rewards)
    efficiency = _efficiency_score(record, evaluation)
    invalid_transition_count = _int(record.get("invalid_transition_count", (evaluation or {}).get("invalid_transition_count", 0)))
    hard_violation_count = _hard_violation_count(record, evaluation)
    module_completion = _module_completion_counts(module_rewards, evaluation, invalid_transition_count)

    progress = 0.65 * target_coverage + 0.35 * checkpoint_progress
    quality = 0.75 + 0.25 * efficiency
    positive = progress * quality
    success_bonus = 0.20 if final_success else 0.0
    penalty = (
        0.35 * min(invalid_transition_count, 3)
        + 0.50 * (1 if hard_violation_count > 0 else 0)
        + 0.20 * max(0, hard_violation_count - 1)
    )
    reward = _clip(positive + success_bonus - penalty)

    excluded_reason = str(record.get("reward_excluded_reason", "") or "")
    reward_weight = 0.0 if excluded_reason else 1.0

    return {
        "goal_id": _goal_id(record),
        "theme": _theme(record),
        "success": final_success,
        "success_type": record.get("success_type", ""),
        "target_state_coverage": round(target_coverage, 6),
        "checkpoint_progress": round(checkpoint_progress, 6),
        "efficiency_score": round(efficiency, 6),
        "invalid_transition_count": invalid_transition_count,
        "hard_constraint_violation_count": hard_violation_count,
        **module_completion,
        "progress": round(progress, 6),
        "quality": round(quality, 6),
        "positive_reward": round(positive, 6),
        "success_bonus": round(success_bonus, 6),
        "penalty": round(penalty, 6),
        "episode_reward": round(reward, 6),
        "reward_weight": reward_weight,
        "reward_excluded_reason": excluded_reason,
        "module_reward_count": len(module_rewards),
        "average_module_reward": round(
            sum(_float(item.get("module_reward")) for item in module_rewards) / len(module_rewards),
            6,
        ) if module_rewards else 0.0,
        "module_rewards": module_rewards,
        "output_dir": record.get("output_dir", ""),
    }


def _load_records_from_summary(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = _read_json(path, {})
    if not isinstance(data, dict):
        raise ValueError(f"Unsupported JSON payload in {path}")
    if isinstance(data.get("records"), list):
        return [item for item in data["records"] if isinstance(item, dict)], {"source_type": "summary", "summary": data}
    if "goal_id" in data:
        return [data], {"source_type": "single_record", "summary": data}
    raise ValueError(f"No records found in {path}")


def _load_online_records(manifest_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    manifest = _read_json(manifest_path, {})
    if not isinstance(manifest, dict):
        raise ValueError(f"Unsupported online manifest payload in {manifest_path}")
    records: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for block in manifest.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        summary_path = Path(str(block.get("summary_path", "")))
        if not summary_path.exists():
            run_dir = Path(str(block.get("run_dir", "")))
            for candidate in sorted(run_dir.glob("*_combined_summary.json")):
                summary_path = candidate
                break
        block_records, _ = _load_records_from_summary(summary_path) if summary_path.exists() else ([], {})
        block_index = _int(block.get("block_index"), len(blocks))
        for record in block_records:
            cloned = dict(record)
            cloned["online_block_index"] = block_index
            records.append(cloned)
        blocks.append({"block_index": block_index, "summary_path": str(summary_path), "record_count": len(block_records)})
    return records, {"source_type": "online_manifest", "summary": manifest}, blocks


def load_records(source: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    summary_path = _find_summary_file(source)
    data = _read_json(summary_path, {})
    if isinstance(data, dict) and "blocks" in data and "method" in data:
        records, meta, blocks = _load_online_records(summary_path)
        meta["source_path"] = str(summary_path)
        return records, meta, blocks
    records, meta = _load_records_from_summary(summary_path)
    meta["source_path"] = str(summary_path)
    return records, meta, []


def _aggregate(reward_records: list[dict[str, Any]]) -> dict[str, Any]:
    weighted = [item for item in reward_records if _float(item.get("reward_weight"), 1.0) > 0.0]
    total = len(reward_records)
    count = len(weighted)
    if not weighted:
        return {
            "total_records": total,
            "weighted_records": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "average_episode_reward": 0.0,
            "average_target_state_coverage": 0.0,
            "average_checkpoint_progress": 0.0,
            "average_module_reward": 0.0,
            "legal_module_completion_rate": 0.0,
            "invalid_transition_rate": 0.0,
            "hard_constraint_violation_rate": 0.0,
        }
    attempted_modules = sum(_int(item.get("attempted_module_count")) for item in weighted)
    legal_completed_modules = sum(_int(item.get("legal_completed_module_count")) for item in weighted)
    return {
        "total_records": total,
        "weighted_records": count,
        "success_count": sum(1 for item in weighted if item.get("success")),
        "success_rate": sum(1 for item in weighted if item.get("success")) / count,
        "average_episode_reward": sum(_float(item.get("episode_reward")) for item in weighted) / count,
        "average_target_state_coverage": sum(_float(item.get("target_state_coverage")) for item in weighted) / count,
        "average_checkpoint_progress": sum(_float(item.get("checkpoint_progress")) for item in weighted) / count,
        "average_module_reward": sum(_float(item.get("average_module_reward")) for item in weighted) / count,
        "legal_module_completion_rate": (legal_completed_modules / attempted_modules) if attempted_modules else 0.0,
        "invalid_transition_rate": sum(1 for item in weighted if _int(item.get("invalid_transition_count")) > 0) / count,
        "hard_constraint_violation_rate": sum(1 for item in weighted if _int(item.get("hard_constraint_violation_count")) > 0) / count,
    }


def _by_theme(reward_records: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in reward_records:
        if _float(item.get("reward_weight"), 1.0) > 0.0:
            buckets[_theme(item)].append(item)
    out = {}
    for theme, items in sorted(buckets.items()):
        out[theme] = _aggregate(items)
    return out


def _by_block(reward_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in reward_records:
        if "online_block_index" in item:
            buckets[_int(item.get("online_block_index"))].append(item)
    return [{"block_index": idx, **_aggregate(items)} for idx, items in sorted(buckets.items())]


def _render_markdown(path: Path, payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    lines = [
        "# Workflow Reward Summary",
        "",
        f"- reward: `{payload['reward_name']}`",
        f"- source: `{payload['source_path']}`",
        f"- total_records: {agg['total_records']}",
        f"- weighted_records: {agg['weighted_records']}",
        f"- success_rate: {agg['success_rate']:.4f}",
        f"- average_episode_reward: {agg['average_episode_reward']:.4f}",
        f"- average_target_state_coverage: {agg['average_target_state_coverage']:.4f}",
        f"- average_checkpoint_progress: {agg['average_checkpoint_progress']:.4f}",
        f"- average_module_reward: {agg['average_module_reward']:.4f}",
        f"- legal_module_completion_rate: {agg['legal_module_completion_rate']:.4f}",
        f"- invalid_transition_rate: {agg['invalid_transition_rate']:.4f}",
        f"- hard_constraint_violation_rate: {agg['hard_constraint_violation_rate']:.4f}",
    ]
    if payload.get("blocks"):
        lines.extend(["", "## Blocks", "", "| block | goals | success rate | avg reward | target coverage | checkpoint progress | legal module completion |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for block in payload["blocks"]:
            lines.append(
                "| {block_index} | {weighted_records} | {success_rate:.4f} | {average_episode_reward:.4f} | {average_target_state_coverage:.4f} | {average_checkpoint_progress:.4f} | {legal_module_completion_rate:.4f} |".format(**block)
            )
    if payload.get("by_theme"):
        lines.extend(["", "## Themes", "", "| theme | goals | success rate | avg reward | target coverage | checkpoint progress | legal module completion |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for theme, item in payload["by_theme"].items():
            lines.append(
                "| {theme} | {weighted_records} | {success_rate:.4f} | {average_episode_reward:.4f} | {average_target_state_coverage:.4f} | {average_checkpoint_progress:.4f} | {legal_module_completion_rate:.4f} |".format(theme=theme, **item)
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute WFG-R1 rewards from workflow benchmark outputs.")
    parser.add_argument("source", type=Path, help="Summary JSON, online manifest, or run directory.")
    parser.add_argument("--output-json", type=Path, help="Reward JSON output path.")
    parser.add_argument("--output-md", type=Path, help="Reward Markdown output path.")
    parser.add_argument("--jsonl", type=Path, help="Optional per-goal reward JSONL output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records, meta, _ = load_records(args.source)
    reward_records = []
    for record in records:
        reward = compute_episode_reward(record)
        if "online_block_index" in record:
            reward["online_block_index"] = record["online_block_index"]
        reward_records.append(reward)

    payload = {
        "version": REWARD_VERSION,
        "reward_name": REWARD_NAME,
        "source_path": meta.get("source_path", str(args.source)),
        "source_type": meta.get("source_type", ""),
        "aggregate": _aggregate(reward_records),
        "blocks": _by_block(reward_records),
        "by_theme": _by_theme(reward_records),
        "records": reward_records,
    }

    output_json = args.output_json or (args.source.with_suffix(args.source.suffix + ".rewards.json") if args.source.is_file() else args.source / "workflow_rewards.json")
    output_md = args.output_md or output_json.with_suffix(".md")
    _write_json(output_json, payload)
    _render_markdown(output_md, payload)
    if args.jsonl:
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        args.jsonl.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in reward_records), encoding="utf-8")
    print(json.dumps({"output_json": str(output_json), "output_md": str(output_md), **payload["aggregate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
