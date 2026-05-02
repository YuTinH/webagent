#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a small balanced OpenRLHF jsonl subset.")
    parser.add_argument("--source-dir", required=True, help="Directory containing train/val/test jsonl exports.")
    parser.add_argument("--output-dir", required=True, help="Directory to write the small subset.")
    parser.add_argument("--train-per-theme", type=int, default=10, help="Train examples per theme.")
    parser.add_argument("--val-per-theme", type=int, default=4, help="Validation examples per theme.")
    parser.add_argument("--test-per-theme", type=int, default=5, help="Test examples per theme.")
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def take_balanced(records: list[dict[str, Any]], per_theme: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["theme"])].append(record)

    chosen: list[dict[str, Any]] = []
    for theme in sorted(grouped):
        items = grouped[theme]
        if len(items) < per_theme:
            raise RuntimeError(f"theme {theme} has only {len(items)} records, need {per_theme}")
        chosen.extend(items[:per_theme])
    return chosen


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_episode_index(*splits: list[dict[str, Any]]) -> dict[str, Any]:
    index: dict[str, Any] = {}
    for records in splits:
        for record in records:
            episode = record.get("episode")
            if not episode:
                continue
            index[str(record["id"])] = episode
            chain_id = episode.get("chain_id")
            if chain_id:
                index[str(chain_id)] = episode
    return index


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_records = load_records(source_dir / "train.jsonl")
    val_records = load_records(source_dir / "val.jsonl")
    test_records = load_records(source_dir / "test.jsonl")

    train_subset = take_balanced(train_records, args.train_per_theme)
    val_subset = take_balanced(val_records, args.val_per_theme)
    test_subset = take_balanced(test_records, args.test_per_theme)

    write_jsonl(output_dir / "train.jsonl", train_subset)
    write_jsonl(output_dir / "val.jsonl", val_subset)
    write_jsonl(output_dir / "test.jsonl", test_subset)

    episode_index = build_episode_index(train_subset, val_subset, test_subset)
    (output_dir / "episode_index.json").write_text(
        json.dumps(episode_index, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "source_dir": str(source_dir),
        "counts": {
            "train": len(train_subset),
            "val": len(val_subset),
            "test": len(test_subset),
        },
        "per_theme": {
            "train": args.train_per_theme,
            "val": args.val_per_theme,
            "test": args.test_per_theme,
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
