#!/usr/bin/env python3
"""Compare block-wise online adaptation experiment manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_manifest(path: Path) -> dict[str, Any]:
    if path.is_dir():
        path = path / "online_adaptation_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except Exception:
        return "0.0000"


def _block_rate(block: dict[str, Any]) -> float:
    try:
        return float(block.get("success_rate", 0.0) or 0.0)
    except Exception:
        return 0.0


def _block_success(block: dict[str, Any]) -> int:
    try:
        return int(block.get("success_count", 0) or 0)
    except Exception:
        return 0


def _composite(item: dict[str, Any]) -> float:
    try:
        if "average_composite_score" not in item and isinstance(item.get("blocks"), list):
            num = 0.0
            den = 0
            for block in item.get("blocks") or []:
                weight = _block_total(block)
                num += _composite(block) * weight
                den += weight
            return num / den if den else 0.0
        return float(item.get("average_composite_score", 0.0) or 0.0)
    except Exception:
        return 0.0


def _block_total(block: dict[str, Any]) -> int:
    try:
        return int(block.get("completed_goals", 0) or block.get("total_goals", 0) or 0)
    except Exception:
        return 0


def _write_markdown(path: Path, manifests: list[dict[str, Any]], baseline: dict[str, Any] | None) -> None:
    lines = [
        "# Online Adaptation Run Comparison",
        "",
        "| run | method | goals | success | success rate | AULC | avg composite | delta success | delta composite |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    base_rate = float((baseline or {}).get("success_rate", 0.0) or 0.0)
    base_comp = _composite(baseline or {})
    for item in manifests:
        rate = float(item.get("success_rate", 0.0) or 0.0)
        comp = _composite(item)
        lines.append(
            "| `{run}` | `{method}` | {goals} | {success} | {rate} | {aulc} | {comp} | {delta:+.4f} | {delta_comp:+.4f} |".format(
                run=Path(str(item.get("experiment_root", ""))).name,
                method=item.get("method", ""),
                goals=item.get("completed_goals", item.get("goal_count", 0)),
                success=item.get("success_count", 0),
                rate=_fmt_rate(rate),
                aulc=_fmt_rate(item.get("aulc", 0.0)),
                comp=_fmt_rate(comp),
                delta=rate - base_rate,
                delta_comp=comp - base_comp,
            )
        )

    max_blocks = max((len(item.get("blocks") or []) for item in manifests), default=0)
    lines.extend(["", "## Blocks", "", "| block | " + " | ".join(f"`{Path(str(item.get('experiment_root', ''))).name}`" for item in manifests) + " |", "| ---: | " + " | ".join("---:" for _ in manifests) + " |"])
    for idx in range(max_blocks):
        cells = [str(idx)]
        for item in manifests:
            blocks = item.get("blocks") or []
            if idx >= len(blocks):
                cells.append("")
                continue
            block = blocks[idx]
            cells.append(
                f"{_block_success(block)}/{_block_total(block)} "
                f"({ _block_rate(block):.4f}, comp={_composite(block):.4f})"
            )
        lines.append("| " + " | ".join(cells) + " |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare online adaptation experiment manifests.")
    parser.add_argument("runs", nargs="+", type=Path, help="Experiment directories or online_adaptation_manifest.json files.")
    parser.add_argument("--baseline", type=Path, help="Optional static baseline run. Defaults to the first run.")
    parser.add_argument("--out", type=Path, help="Write a Markdown comparison report.")
    args = parser.parse_args()

    manifests = [_read_manifest(path) for path in args.runs]
    baseline = _read_manifest(args.baseline) if args.baseline else manifests[0]
    _write_markdown(args.out or Path("/dev/stdout"), manifests, baseline)


if __name__ == "__main__":
    main()
