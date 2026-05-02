#!/usr/bin/env python3
"""Lightweight structured memory bank for benchmark experiments."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-zA-Z0-9_]+", text.lower()) if tok]


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[k] * b[k] for k in common)
    den_a = math.sqrt(sum(v * v for v in a.values()))
    den_b = math.sqrt(sum(v * v for v in b.values()))
    if den_a == 0.0 or den_b == 0.0:
        return 0.0
    return num / (den_a * den_b)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts(raw: str | None) -> datetime:
    if not raw:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _task_family(task_id: str) -> str:
    task_id = (task_id or "").strip()
    return task_id[:1].upper() if task_id else ""


def _compact_value(value: Any, limit: int = 180) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _importance_for_key(key: str, value: Any) -> float:
    k = (key or "").lower()
    if any(token in k for token in ("id", "pnr", "policy", "account", "address", "date", "time", "status")):
        return 0.95
    if isinstance(value, (str, int, float, bool)):
        return 0.85
    if isinstance(value, (list, dict)):
        return 0.75
    return 0.65


def _load_expected_memory(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _entry_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    entry_type = str(item.get("entry_type", ""))
    key = str(item.get("key", ""))
    if entry_type == "kv":
        # KV memory should behave like persistent state: newer values replace older
        # ones for the same memory key.
        return (entry_type, key, "__global__")
    return (entry_type, key, str(item.get("task_id", "")))


def _merge_item(existing: dict[str, Any], new_item: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(new_item)
    old_count = int(existing.get("reinforcement_count", 1) or 1)
    new_count = int(new_item.get("reinforcement_count", 1) or 1)
    reinforcement_count = old_count + new_count
    merged["reinforcement_count"] = reinforcement_count

    old_importance = float(existing.get("importance", 0.5))
    new_importance = float(new_item.get("importance", 0.5))
    boost = min(0.12, 0.02 * max(reinforcement_count - 1, 0))
    merged["importance"] = min(1.0, max(old_importance, new_importance) + boost)
    merged["confidence"] = max(float(existing.get("confidence", 0.0)), float(new_item.get("confidence", 0.0)))
    merged["ts"] = max(str(existing.get("ts", "")), str(new_item.get("ts", "")))
    return merged


def _effective_importance(item: dict[str, Any], now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    base = float(item.get("importance", 0.5))
    ts = _parse_ts(str(item.get("ts", "")))
    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
    decay_days = max(1.0, _float_env("AGENT_MEMORYBANK_DECAY_DAYS", 21.0))
    decay = math.exp(-age_days / decay_days)

    reinforcement_count = max(1, int(item.get("reinforcement_count", 1) or 1))
    reinforcement_bonus = min(0.20, 0.03 * (reinforcement_count - 1))

    success_bonus = 0.05 if bool(item.get("success", False)) else 0.0
    kv_floor = 0.25 if str(item.get("entry_type", "")) == "kv" else 0.0
    effective = max(kv_floor, base * decay + reinforcement_bonus + success_bonus)
    return min(1.0, effective)


def build_task_memory_entries(
    *,
    task_id: str,
    goal: str,
    success: bool,
    memory_snapshot: dict[str, Any],
    expected_memory_path: str | Path | None,
    end_reason: str,
    failure_category: str,
    checkpoint_score_percent: float | None,
) -> list[dict[str, Any]]:
    ts = _iso_now()
    family = _task_family(task_id)
    entries: list[dict[str, Any]] = []
    expected = _load_expected_memory(expected_memory_path)

    if success:
        for key in expected:
            if key not in memory_snapshot:
                continue
            value = memory_snapshot[key]
            entries.append(
                {
                    "entry_type": "kv",
                    "task_id": task_id,
                    "task_family": family,
                    "source": task_id,
                    "key": key,
                    "value": value,
                    "summary": f"{key} = {_compact_value(value)}",
                    "importance": _importance_for_key(key, value),
                    "confidence": 1.0,
                    "success": True,
                    "reinforcement_count": 1,
                    "ts": ts,
                }
            )

    score_text = (
        f"{checkpoint_score_percent:.1f}"
        if isinstance(checkpoint_score_percent, (int, float))
        else "unknown"
    )
    if success:
        summary = (
            f"Task {task_id} succeeded. Goal: {goal}. "
            f"Checkpoint score: {score_text}."
        )
        importance = 0.7
    else:
        summary = (
            f"Task {task_id} failed. Goal: {goal}. "
            f"Failure category: {failure_category or 'unknown'}. "
            f"End reason: {end_reason or 'unknown'}."
        )
        importance = 0.45

    entries.append(
        {
            "entry_type": "summary",
            "task_id": task_id,
            "task_family": family,
            "source": task_id,
            "key": "__task_summary__",
            "value": {
                "goal": goal,
                "success": bool(success),
                "end_reason": end_reason,
                "failure_category": failure_category,
                "checkpoint_score_percent": checkpoint_score_percent,
            },
            "summary": summary,
            "importance": importance,
            "confidence": 1.0,
            "success": bool(success),
            "reinforcement_count": 1,
            "ts": ts,
        }
    )
    return entries


class MemoryBankLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_many(self, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        items = self.load()
        by_identity: dict[tuple[str, str, str], dict[str, Any]] = {
            _entry_identity(item): item for item in items
        }
        for entry in entries:
            ident = _entry_identity(entry)
            existing = by_identity.get(ident)
            if existing is None:
                by_identity[ident] = entry
            else:
                by_identity[ident] = _merge_item(existing, entry)
        merged_items = list(by_identity.values())
        self.save(self._prune(merged_items))

    def _prune(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        max_items = max(50, _int_env("AGENT_MEMORYBANK_MAX_ITEMS", 400))
        min_effective_importance = max(0.0, min(1.0, _float_env("AGENT_MEMORYBANK_MIN_EFFECTIVE_IMPORTANCE", 0.12)))

        decorated: list[tuple[float, str, dict[str, Any]]] = []
        for item in items:
            eff = _effective_importance(item, now=now)
            if eff < min_effective_importance and str(item.get("entry_type", "")) != "kv":
                continue
            decorated.append((eff, str(item.get("ts", "")), item))

        decorated.sort(key=lambda x: (x[0], x[1]), reverse=True)
        kept = [item for _, _, item in decorated[:max_items]]
        kept.sort(key=lambda item: str(item.get("ts", "")))
        return kept

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        items = self.load()
        qvec = Counter(_tokenize(query))
        scored: list[tuple[float, dict[str, Any]]] = []
        total = len(items)
        now = datetime.now(timezone.utc)
        for idx, item in enumerate(items):
            text = " ".join(
                [
                    str(item.get("task_id", "")),
                    str(item.get("task_family", "")),
                    str(item.get("key", "")),
                    str(item.get("summary", "")),
                    _compact_value(item.get("value", ""), limit=120),
                ]
            )
            lexical = _cosine(qvec, Counter(_tokenize(text)))
            if lexical <= 0.0:
                continue
            importance = _effective_importance(item, now=now)
            recency = (idx + 1) / max(total, 1)
            score = lexical + 0.25 * importance + 0.10 * recency
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
