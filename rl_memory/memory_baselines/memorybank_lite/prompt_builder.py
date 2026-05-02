#!/usr/bin/env python3
"""Prompt augmentation helpers for the MemoryBank-lite baseline."""

from __future__ import annotations

from typing import Iterable


def build_memory_prefix(entries: Iterable[dict]) -> str:
    entries = list(entries)
    if not entries:
        return ""
    lines = ["Relevant persistent memory:"]
    for idx, item in enumerate(entries, start=1):
        task_id = item.get("task_id", "")
        summary = item.get("summary", "")
        lines.append(f"{idx}. [{task_id}] {summary}")
    lines.append("Use this memory only when it is relevant; the current page state remains the source of truth.")
    return "\n".join(lines).strip() + "\n\n"


def augment_instruction(original_instruction: str, entries: Iterable[dict]) -> str:
    prefix = build_memory_prefix(entries)
    if not prefix:
        return original_instruction
    return prefix + original_instruction
