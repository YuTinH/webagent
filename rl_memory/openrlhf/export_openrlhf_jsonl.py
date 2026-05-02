#!/usr/bin/env python3
"""Export split manifests plus merged pool into OpenRLHF jsonl datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", required=True, help="Merged combined_clean_pool.json")
    parser.add_argument("--split-dir", required=True, help="Directory containing train/val/test manifests")
    parser.add_argument("--output-dir", required=True, help="Directory to write jsonl files")
    return parser.parse_args()


def load_pool(pool_path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(pool_path.read_text())
    return {item["pool_signature"]: item for item in payload}


def make_record(manifest_item: dict[str, Any], chain: dict[str, Any]) -> dict[str, Any]:
    first_step = (chain.get("steps") or [{}])[0]
    first_instruction = first_step.get("instruction", "")
    observation = (
        f"Theme: {chain.get('theme')}\n"
        f"Chain: {chain.get('chain_id')}\n"
        f"Current task: {first_step.get('task_id', '')}\n"
        f"Instruction: {first_instruction}\n"
        "Return exactly one browser action."
    )
    return {
        "id": manifest_item["signature"],
        "label": chain.get("chain_id", manifest_item["signature"]),
        "theme": chain.get("theme"),
        "num_steps": len(chain.get("steps", [])),
        "observation": observation,
        "episode": chain,
    }


def export_split(pool_map: dict[str, dict[str, Any]], split_path: Path, output_path: Path) -> int:
    manifest = json.loads(split_path.read_text())
    with output_path.open("w", encoding="utf-8") as f:
        for item in manifest:
            sig = item["signature"]
            chain = pool_map[sig]
            record = make_record(item, chain)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(manifest)


def main() -> None:
    args = parse_args()
    pool_path = Path(args.pool)
    split_dir = Path(args.split_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pool_map = load_pool(pool_path)
    summary = {}
    episode_index: dict[str, dict[str, Any]] = {}
    for split_name in ("train", "val", "test"):
        split_path = split_dir / f"{split_name}.json"
        output_path = output_dir / f"{split_name}.jsonl"
        summary[split_name] = export_split(pool_map, split_path, output_path)
        manifest = json.loads(split_path.read_text())
        for item in manifest:
            sig = item["signature"]
            chain = pool_map[sig]
            episode_index[item["signature"]] = chain
            chain_id = chain.get("chain_id")
            if chain_id:
                episode_index[str(chain_id)] = chain

    (output_dir / "episode_index.json").write_text(
        json.dumps(episode_index, ensure_ascii=False)
    )

    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "pool": str(pool_path),
                "split_dir": str(split_dir),
                "counts": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
