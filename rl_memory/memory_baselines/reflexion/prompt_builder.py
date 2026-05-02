#!/usr/bin/env python3
"""Prompt augmentation helpers for the Reflexion baseline."""

from __future__ import annotations

from typing import Iterable


def build_reflection_prefix(reflections: Iterable[dict]) -> str:
    reflections = list(reflections)
    if not reflections:
        return ""
    lines = ["Relevant prior reflections:"]
    for idx, item in enumerate(reflections, start=1):
        task_id = item.get("task_id", "")
        failure_category = item.get("failure_category", "")
        reflection = item.get("reflection", "")
        lines.append(f"{idx}. [{task_id}] {failure_category}: {reflection}")
    return "\n".join(lines).strip() + "\n\n"


def augment_instruction(original_instruction: str, reflections: Iterable[dict]) -> str:
    prefix = build_reflection_prefix(reflections)
    if not prefix:
        return original_instruction
    return prefix + original_instruction
