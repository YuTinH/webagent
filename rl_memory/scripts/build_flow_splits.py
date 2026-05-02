#!/usr/bin/env python3
"""Build reproducible train/val/test flow splits from sampled flow files."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


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
        "--inputs",
        nargs="+",
        required=True,
        help="Input sampled_*.json files",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for split manifests",
    )
    parser.add_argument("--train-per-theme", type=int, required=True)
    parser.add_argument("--val-per-theme", type=int, required=True)
    parser.add_argument("--test-per-theme", type=int, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()

    for input_path in [Path(x) for x in args.inputs]:
        payload = json.loads(input_path.read_text())
        for chain in payload:
            sig = flow_signature(chain)
            if sig in seen:
                continue
            seen.add(sig)
            theme = chain["theme"]
            pools[theme].append(
                {
                    "signature": sig,
                    "source_file": str(input_path),
                    "chain_id": chain.get("chain_id"),
                    "theme": theme,
                    "num_steps": len(chain.get("steps", [])),
                    "task_ids": [step.get("task_id") for step in chain.get("steps", [])],
                    "requirement_ids": [
                        (step.get("template_info") or {}).get("requirement_id") or "baseline"
                        for step in chain.get("steps", [])
                    ],
                }
            )

    split = {"train": [], "val": [], "test": []}
    summary: dict[str, Any] = {
        "seed": args.seed,
        "requested": {
            "train_per_theme": args.train_per_theme,
            "val_per_theme": args.val_per_theme,
            "test_per_theme": args.test_per_theme,
        },
        "themes": {},
    }

    for theme, records in sorted(pools.items()):
        rng.shuffle(records)
        need = args.train_per_theme + args.val_per_theme + args.test_per_theme
        if len(records) < need:
            raise SystemExit(
                f"Theme {theme} has only {len(records)} unique flows, need {need}"
            )
        train = records[: args.train_per_theme]
        val = records[
            args.train_per_theme : args.train_per_theme + args.val_per_theme
        ]
        test = records[
            args.train_per_theme
            + args.val_per_theme : args.train_per_theme
            + args.val_per_theme
            + args.test_per_theme
        ]
        split["train"].extend(train)
        split["val"].extend(val)
        split["test"].extend(test)
        summary["themes"][theme] = {
            "available_unique_flows": len(records),
            "train": len(train),
            "val": len(val),
            "test": len(test),
        }

    for name, records in split.items():
        out = output_dir / f"{name}.json"
        out.write_text(json.dumps(records, ensure_ascii=False, indent=2))

    summary["totals"] = {name: len(records) for name, records in split.items()}
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
