#!/usr/bin/env python3
"""Prompt augmentation helpers for the SkillBank baseline."""

from __future__ import annotations

from typing import Iterable


def build_skill_prefix(skills: Iterable[dict]) -> str:
    skills = list(skills)
    if not skills:
        return ""
    lines = ["Relevant reusable skills:"]
    for idx, skill in enumerate(skills, start=1):
        name = str(skill.get("name", "")).strip() or str(skill.get("skill_id", "")).strip()
        description = str(skill.get("description", "")).strip()
        action_types = ", ".join(skill.get("preferred_action_types", []) or [])
        termination_hint = str(skill.get("termination_hint", "")).strip()
        failure_modes = ", ".join(skill.get("failure_modes", [])[:4] or [])
        lines.append(f"{idx}. {name}: {description}")
        if action_types:
            lines.append(f"   Preferred action types: {action_types}.")
        if termination_hint:
            lines.append(f"   Stop rule: {termination_hint}")
        if failure_modes:
            lines.append(f"   Avoid: {failure_modes}.")
    lines.append("Choose the most relevant skill as the active plan, but still output exactly one primitive action.")
    return "\n".join(lines).strip() + "\n\n"


def augment_instruction(original_instruction: str, skills: Iterable[dict]) -> str:
    prefix = build_skill_prefix(skills)
    if not prefix:
        return original_instruction
    return prefix + original_instruction
