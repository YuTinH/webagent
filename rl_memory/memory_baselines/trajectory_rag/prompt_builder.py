#!/usr/bin/env python3
"""Prompt augmentation helpers for the Trajectory RAG baseline."""

from __future__ import annotations

from typing import Iterable


def build_trajectory_prefix(entries: Iterable[dict]) -> str:
    entries = list(entries)
    if not entries:
        return ""
    lines = ["Relevant short action patterns from similar tasks:"]
    for idx, item in enumerate(entries, start=1):
        task_id = item.get("task_id", "")
        goal = item.get("goal", "")
        sketch = item.get("action_sketch", "")
        score = item.get("score")
        score_text = f" score={float(score):.2f}" if isinstance(score, (int, float)) else ""
        lines.append(f"{idx}. [{task_id}{score_text}] Goal: {goal}")
        lines.append(f"   Action sketch: {sketch}")
    lines.append("Use these as weak hints only. Do not copy selectors or URLs blindly. The current page state is the source of truth.")
    lines.append("Output exactly one action.")
    return "\n".join(lines).strip() + "\n\n"


def augment_instruction(original_instruction: str, entries: Iterable[dict]) -> str:
    prefix = build_trajectory_prefix(entries)
    if not prefix:
        return original_instruction
    return prefix + original_instruction
