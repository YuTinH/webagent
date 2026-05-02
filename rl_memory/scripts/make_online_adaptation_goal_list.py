#!/usr/bin/env python3
"""Build a stratified goal list for online adaptation pilots.

The default stream keeps each block similarly mixed:
- historically solved goals provide an easy anchor,
- high-score failures provide near-miss medium cases,
- low-score failures keep hard cases in the stream.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def _read_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return [item for item in data["records"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    raise ValueError(f"No records found in {path}")


def _score(record: dict[str, Any]) -> float:
    try:
        return float(record.get("composite_score", 0.0) or 0.0)
    except Exception:
        return 0.0


def _goal_id(record: dict[str, Any]) -> str:
    return str(record.get("goal_id", "")).strip()


def _theme(record: dict[str, Any]) -> str:
    return str(record.get("theme", "unknown")).strip() or "unknown"


def _theme_balanced_pick(records: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    if count <= 0 or not records:
        return []
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[_theme(record)].append(record)
    for items in buckets.values():
        rng.shuffle(items)

    picked: list[dict[str, Any]] = []
    while len(picked) < count and buckets:
        for theme in sorted(list(buckets)):
            items = buckets.get(theme) or []
            if not items:
                buckets.pop(theme, None)
                continue
            picked.append(items.pop())
            if len(picked) >= count:
                break
    return picked


def _interleave_blocks(groups: list[list[dict[str, Any]]], block_size: int, block_count: int) -> list[dict[str, Any]]:
    blocks: list[list[dict[str, Any]]] = [[] for _ in range(block_count)]
    for group in groups:
        for idx, record in enumerate(group):
            blocks[idx % block_count].append(record)
    for block in blocks:
        block.sort(key=lambda r: (_theme(r), _goal_id(r)))
        if len(block) > block_size:
            del block[block_size:]
    return [record for block in blocks for record in block]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a stratified online-adaptation goal list.")
    parser.add_argument("--source-summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--block-size", type=int, default=10)
    parser.add_argument("--easy-ratio", type=float, default=0.4)
    parser.add_argument("--near-miss-ratio", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=20260426)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    records = [record for record in _read_records(args.source_summary) if _goal_id(record)]
    easy = [record for record in records if bool(record.get("success"))]
    near_miss = [record for record in records if not record.get("success") and _score(record) >= 0.75]
    hard = [record for record in records if not record.get("success") and _score(record) < 0.75]

    easy.sort(key=lambda r: (_theme(r), -_score(r), _goal_id(r)))
    near_miss.sort(key=lambda r: (_theme(r), -_score(r), _goal_id(r)))
    hard.sort(key=lambda r: (_theme(r), _score(r), _goal_id(r)))

    limit = max(1, args.limit)
    easy_n = min(len(easy), round(limit * args.easy_ratio))
    near_n = min(len(near_miss), round(limit * args.near_miss_ratio))
    hard_n = max(0, limit - easy_n - near_n)
    if hard_n > len(hard):
        near_n = min(len(near_miss), near_n + hard_n - len(hard))
        hard_n = len(hard)
    if easy_n + near_n + hard_n < limit:
        deficit = limit - (easy_n + near_n + hard_n)
        extra_near = min(len(near_miss) - near_n, deficit)
        near_n += extra_near
        deficit -= extra_near
        easy_n += min(len(easy) - easy_n, deficit)

    picked_easy = _theme_balanced_pick(easy, easy_n, rng)
    picked_near = _theme_balanced_pick(near_miss, near_n, rng)
    picked_hard = _theme_balanced_pick(hard, hard_n, rng)
    block_count = max(1, (limit + max(1, args.block_size) - 1) // max(1, args.block_size))
    ordered = _interleave_blocks([picked_easy, picked_near, picked_hard], args.block_size, block_count)

    seen: set[str] = set()
    goal_ids: list[str] = []
    for record in ordered:
        gid = _goal_id(record)
        if gid and gid not in seen:
            seen.add(gid)
            goal_ids.append(gid)
    if len(goal_ids) < limit:
        for record in records:
            gid = _goal_id(record)
            if gid and gid not in seen:
                seen.add(gid)
                goal_ids.append(gid)
            if len(goal_ids) >= limit:
                break
    goal_ids = goal_ids[:limit]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(f"{goal_id}\n" for goal_id in goal_ids), encoding="utf-8")

    selected = {gid: record for record in records if (gid := _goal_id(record)) in set(goal_ids)}
    meta = {
        "source_summary": str(args.source_summary),
        "out": str(args.out),
        "limit": limit,
        "block_size": args.block_size,
        "goal_count": len(goal_ids),
        "historical_success_count": sum(1 for gid in goal_ids if selected.get(gid, {}).get("success")),
        "average_historical_composite_score": (
            sum(_score(selected[gid]) for gid in goal_ids if gid in selected) / len(goal_ids)
            if goal_ids else 0.0
        ),
        "goals": [
            {
                "goal_id": gid,
                "theme": _theme(selected.get(gid, {})),
                "historical_success": bool(selected.get(gid, {}).get("success")),
                "historical_composite_score": _score(selected.get(gid, {})),
            }
            for gid in goal_ids
        ],
    }
    args.out.with_suffix(args.out.suffix + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in meta.items() if k != "goals"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
