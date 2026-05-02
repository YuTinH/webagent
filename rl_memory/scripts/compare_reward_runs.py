#!/usr/bin/env python3
"""Compare WFG reward reports across runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_reward(path: Path) -> dict[str, Any]:
    if path.is_dir():
        candidates = [
            path / "workflow_rewards.json",
            path / "rewards.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
    return json.loads(path.read_text(encoding="utf-8"))


def _label(path: Path, payload: dict[str, Any]) -> str:
    parent = path if path.is_dir() else path.parent
    return parent.name or str(path)


def _agg(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("aggregate") or {}


def _val(payload: dict[str, Any], key: str) -> float:
    try:
        return float(_agg(payload).get(key, 0.0) or 0.0)
    except Exception:
        return 0.0


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _block_rows(payloads: list[tuple[str, dict[str, Any]]]) -> list[str]:
    max_blocks = max((len(payload.get("blocks") or []) for _, payload in payloads), default=0)
    if max_blocks <= 0:
        return []
    lines = [
        "",
        "## Blocks",
        "",
        "| block | " + " | ".join(f"`{label}`" for label, _ in payloads) + " |",
        "| ---: | " + " | ".join("---:" for _ in payloads) + " |",
    ]
    for idx in range(max_blocks):
        cells = [str(idx)]
        for _, payload in payloads:
            blocks = payload.get("blocks") or []
            if idx >= len(blocks):
                cells.append("")
                continue
            block = blocks[idx]
            cells.append(
                "{reward:.4f} / cp={checkpoint:.4f} / cov={coverage:.4f}".format(
                    reward=float(block.get("average_episode_reward", 0.0) or 0.0),
                    checkpoint=float(block.get("average_checkpoint_progress", 0.0) or 0.0),
                    coverage=float(block.get("average_target_state_coverage", 0.0) or 0.0),
                )
            )
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render(paths: list[Path], baseline: Path | None = None) -> str:
    payloads = [(_label(path, _read_reward(path)), _read_reward(path)) for path in paths]
    baseline_payload = _read_reward(baseline) if baseline else payloads[0][1]
    base_reward = _val(baseline_payload, "average_episode_reward")
    base_coverage = _val(baseline_payload, "average_target_state_coverage")
    base_checkpoint = _val(baseline_payload, "average_checkpoint_progress")
    base_module = _val(baseline_payload, "average_module_reward")
    base_legal_module = _val(baseline_payload, "legal_module_completion_rate")

    lines = [
        "# Workflow Reward Run Comparison",
        "",
        "| run | success | avg reward | delta reward | coverage | delta coverage | checkpoint | delta checkpoint | legal module | delta legal module | module reward | delta module |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, payload in payloads:
        agg = _agg(payload)
        success_count = int(agg.get("success_count", 0) or 0)
        weighted = int(agg.get("weighted_records", 0) or 0)
        reward = _val(payload, "average_episode_reward")
        coverage = _val(payload, "average_target_state_coverage")
        checkpoint = _val(payload, "average_checkpoint_progress")
        module = _val(payload, "average_module_reward")
        legal_module = _val(payload, "legal_module_completion_rate")
        lines.append(
            "| `{label}` | {success}/{weighted} | {reward} | {delta_reward:+.4f} | {coverage} | {delta_coverage:+.4f} | {checkpoint} | {delta_checkpoint:+.4f} | {legal_module} | {delta_legal_module:+.4f} | {module} | {delta_module:+.4f} |".format(
                label=label,
                success=success_count,
                weighted=weighted,
                reward=_fmt(reward),
                delta_reward=reward - base_reward,
                coverage=_fmt(coverage),
                delta_coverage=coverage - base_coverage,
                checkpoint=_fmt(checkpoint),
                delta_checkpoint=checkpoint - base_checkpoint,
                legal_module=_fmt(legal_module),
                delta_legal_module=legal_module - base_legal_module,
                module=_fmt(module),
                delta_module=module - base_module,
            )
        )
    lines.extend(_block_rows(payloads))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare WFG reward reports.")
    parser.add_argument("runs", nargs="+", type=Path, help="Run dirs or workflow_rewards.json files.")
    parser.add_argument("--baseline", type=Path, help="Baseline run dir or reward JSON. Defaults to first run.")
    parser.add_argument("--out", type=Path, help="Markdown output path.")
    args = parser.parse_args()

    text = render(args.runs, args.baseline)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
