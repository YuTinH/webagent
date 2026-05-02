#!/usr/bin/env python3
"""Prompt augmentation helpers for the fuller MemoryBank baseline."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Iterable


_SECTION_TITLES = {
    "family_summary": "High-level family summaries",
    "family_pitfall_summary": "Family-specific pitfalls",
    "strategy": "Relevant strategies",
    "fact": "Known persistent facts",
    "episode": "Prior successful episodes",
    "pitfall": "Pitfalls to avoid",
    "global_summary": "Global behavior summary",
}


def _allowed_types() -> set[str]:
    raw = (os.environ.get("AGENT_MEMORYBANK_ALLOWED_TYPES") or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def build_memory_prefix(entries: Iterable[dict]) -> str:
    entries = list(entries)
    allowed_types = _allowed_types()
    if allowed_types:
        entries = [item for item in entries if str(item.get("entry_type", "")) in allowed_types]
    if not entries:
        return ""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in entries:
        grouped[str(item.get("entry_type", "fact"))].append(item)

    lines = ["Relevant long-term memory:"]
    for entry_type in (
        "family_summary",
        "family_pitfall_summary",
        "strategy",
        "fact",
        "episode",
        "pitfall",
        "global_summary",
    ):
        bucket = grouped.get(entry_type, [])
        if not bucket:
            continue
        lines.append(f"{_SECTION_TITLES.get(entry_type, entry_type)}:")
        for item in bucket:
            task_id = item.get("task_id", "")
            summary = item.get("summary", "")
            lines.append(f"- [{task_id}] {summary}")
    lines.append("Use memory only when relevant. The current page state remains the source of truth.")
    return "\n".join(lines).strip() + "\n\n"


def augment_instruction(original_instruction: str, entries: Iterable[dict]) -> str:
    prefix = build_memory_prefix(entries)
    if not prefix:
        return original_instruction
    return prefix + original_instruction
