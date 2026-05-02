#!/usr/bin/env python3
"""A fuller structured MemoryBank baseline for benchmark experiments."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rl_memory.memory_baselines.memorybank.embeddings import cosine_similarity, get_embedder_from_env
from rl_memory.memory_baselines.memorybank.summarizer import get_memory_summarizer


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


def _allowed_types_env() -> set[str]:
    raw = (os.environ.get("AGENT_MEMORYBANK_ALLOWED_TYPES") or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}

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


def _goal_tags(goal: str) -> set[str]:
    tags = set(_tokenize(goal))
    for group in re.findall(r"'([^']+)'|\"([^\"]+)\"", goal or ""):
        for part in group:
            if part:
                tags.update(_tokenize(part))
    return {tag for tag in tags if len(tag) >= 2}


def _key_tags(key: str) -> set[str]:
    base = re.sub(r"\[\d+\]", "", key or "")
    return set(_tokenize(base))


def _tags_for_entry(task_id: str, goal: str, key: str = "", value: Any = None) -> list[str]:
    tags = set()
    family = _task_family(task_id)
    if family:
        tags.add(family.lower())
    tags.update(_goal_tags(goal))
    tags.update(_key_tags(key))
    if isinstance(value, str):
        tags.update(tok for tok in _tokenize(value) if len(tok) >= 3)
    return sorted(tag for tag in tags if tag)


def _importance_for_key(key: str, value: Any) -> float:
    k = (key or "").lower()
    if any(token in k for token in ("id", "pnr", "account", "address", "status", "date", "time")):
        return 0.96
    if any(token in k for token in ("amount", "total", "price", "refund", "balance", "count")):
        return 0.90
    if isinstance(value, (str, int, float, bool)):
        return 0.82
    if isinstance(value, (list, dict)):
        return 0.72
    return 0.62


def _pitfall_summary(task_id: str, goal: str, failure_category: str, end_reason: str) -> str:
    category = (failure_category or "").strip()
    if category == "repeat_action_loop":
        return f"For {task_id}, do not repeat the same action when the page state is unchanged. Re-read the page and switch strategy."
    if category == "option_not_found":
        return f"For {task_id}, only select values or labels that are visibly available in the current dropdown."
    if category == "element_not_found_or_timeout":
        return f"For {task_id}, re-check the page state before clicking. If the selector is missing, choose a visible alternative or close blockers first."
    if category == "premature_done":
        return f"For {task_id}, do not emit DONE() until the goal state is visibly satisfied."
    if category == "action_type_error":
        return f"For {task_id}, match action type to widget type. Use SELECT only on real selects and TYPE only on editable inputs."
    if category == "selector_parse_error":
        return f"For {task_id}, produce clean selectors without stray quotes, markdown, or malformed syntax."
    if category == "overlay_block":
        return f"For {task_id}, close overlays, ads, cookie banners, or modals before continuing."
    if category == "invalid_action_format":
        return f"For {task_id}, output exactly one valid action command like CLICK(...), TYPE(...), SELECT(...), GOTO(...), WAIT(), or DONE()."
    return f"For {task_id}, the last run for '{goal}' failed with {category or end_reason or 'unknown_reason'}. Be conservative and verify state before acting."


def _strategy_summary(task_id: str, goal: str, expected_keys: list[str]) -> str:
    key_text = "; ".join(expected_keys[:4])
    if key_text:
        return f"For {task_id}, complete: {goal}. Verify or set these state fields before stopping: {key_text}."
    return f"For {task_id}, complete: {goal}. Stop only after the success criteria are reflected in environment state."


def _episode_summary(task_id: str, goal: str, expected_keys: list[str], checkpoint_score_percent: float | None) -> str:
    score_text = (
        f"{checkpoint_score_percent:.1f}"
        if isinstance(checkpoint_score_percent, (int, float))
        else "unknown"
    )
    key_text = ", ".join(expected_keys[:4]) if expected_keys else "no explicit expected memory"
    return f"Successful episode for {task_id}. Goal: {goal}. Key outcomes: {key_text}. Checkpoint score: {score_text}."


def _entry_identity(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("entry_type", "")), str(item.get("memory_id", "")))


def _merge_item(existing: dict[str, Any], new_item: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    preserved_embedding = existing.get("embedding")
    preserved_embedding_text = existing.get("embedding_text")
    preserved_embedding_model = existing.get("embedding_model")
    merged.update(new_item)
    old_reinforcement = int(existing.get("reinforcement_count", 1) or 1)
    new_reinforcement = int(new_item.get("reinforcement_count", 1) or 1)
    reinforcement_count = old_reinforcement + new_reinforcement
    merged["reinforcement_count"] = reinforcement_count

    old_access = int(existing.get("access_count", 0) or 0)
    new_access = int(new_item.get("access_count", 0) or 0)
    merged["access_count"] = old_access + new_access

    old_strength = float(existing.get("strength", 0.5))
    new_strength = float(new_item.get("strength", 0.5))
    boost = min(0.18, 0.025 * max(reinforcement_count - 1, 0))
    merged["strength"] = min(1.0, max(old_strength, new_strength) + boost)
    merged["importance"] = min(1.0, max(float(existing.get("importance", 0.5)), float(new_item.get("importance", 0.5))))
    merged["confidence"] = max(float(existing.get("confidence", 0.0)), float(new_item.get("confidence", 0.0)))
    merged["ts_created"] = min(str(existing.get("ts_created", "") or new_item.get("ts_created", "")), str(new_item.get("ts_created", "") or existing.get("ts_created", "")))
    merged["ts_updated"] = max(str(existing.get("ts_updated", "")), str(new_item.get("ts_updated", "")))
    merged["last_accessed_at"] = max(str(existing.get("last_accessed_at", "")), str(new_item.get("last_accessed_at", "")))
    merged["tags"] = sorted(set(existing.get("tags", []) or []) | set(new_item.get("tags", []) or []))
    if preserved_embedding is not None and preserved_embedding_text == merged.get("embedding_text"):
        merged["embedding"] = preserved_embedding
        merged["embedding_model"] = preserved_embedding_model
    return merged


def _effective_strength(item: dict[str, Any], now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    strength = float(item.get("strength", 0.5))
    importance = float(item.get("importance", 0.5))
    ts = _parse_ts(str(item.get("ts_updated", item.get("ts_created", ""))))
    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
    decay_days = max(1.0, _float_env("AGENT_MEMORYBANK_DECAY_DAYS", 28.0))
    decay = math.exp(-age_days / decay_days)

    reinforcement_count = max(1, int(item.get("reinforcement_count", 1) or 1))
    reinforcement_bonus = min(0.20, 0.03 * (reinforcement_count - 1))
    access_count = max(0, int(item.get("access_count", 0) or 0))
    access_bonus = min(0.10, 0.01 * access_count)
    success_bonus = 0.06 if bool(item.get("success", False)) else 0.0
    type_floor = 0.30 if str(item.get("entry_type", "")) in {"fact", "strategy", "family_summary"} else 0.0
    effective = max(type_floor, (0.55 * strength + 0.45 * importance) * decay + reinforcement_bonus + access_bonus + success_bonus)
    return min(1.0, effective)


def _entry_text_for_embedding(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("entry_type", "")),
        str(item.get("task_id", "")),
        str(item.get("task_family", "")),
        str(item.get("goal", "")),
        str(item.get("key", "")),
        str(item.get("summary", "")),
        _compact_value(item.get("value", ""), limit=200),
        " ".join(item.get("tags", []) or []),
    ]
    return " ".join(part for part in parts if part).strip()


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
    expected = _load_expected_memory(expected_memory_path)
    expected_keys = sorted(expected.keys())
    entries: list[dict[str, Any]] = []

    if success:
        for key in expected_keys:
            if key not in memory_snapshot:
                continue
            value = memory_snapshot[key]
            tags = _tags_for_entry(task_id, goal, key, value)
            item = {
                "entry_type": "fact",
                "memory_id": f"fact::{key}",
                "task_id": task_id,
                "task_family": family,
                "goal": goal,
                "key": key,
                "value": value,
                "summary": f"{key} = {_compact_value(value)}",
                "tags": tags,
                "importance": _importance_for_key(key, value),
                "strength": 0.90,
                "confidence": 1.0,
                "success": True,
                "reinforcement_count": 1,
                "access_count": 0,
                "ts_created": ts,
                "ts_updated": ts,
                "last_accessed_at": "",
            }
            item["embedding_text"] = _entry_text_for_embedding(item)
            entries.append(item)

        for entry_type, memory_id, summary, importance, strength in [
            ("strategy", f"strategy::{task_id}", _strategy_summary(task_id, goal, expected_keys), 0.82, 0.84),
            ("episode", f"episode::{task_id}", _episode_summary(task_id, goal, expected_keys, checkpoint_score_percent), 0.76, 0.78),
        ]:
            item = {
                "entry_type": entry_type,
                "memory_id": memory_id,
                "task_id": task_id,
                "task_family": family,
                "goal": goal,
                "key": f"__{entry_type}__",
                "value": {
                    "expected_keys": expected_keys,
                    "checkpoint_score_percent": checkpoint_score_percent,
                },
                "summary": summary,
                "tags": _tags_for_entry(task_id, goal, f"__{entry_type}__", " ".join(expected_keys)),
                "importance": importance,
                "strength": strength,
                "confidence": 1.0,
                "success": True,
                "reinforcement_count": 1,
                "access_count": 0,
                "ts_created": ts,
                "ts_updated": ts,
                "last_accessed_at": "",
            }
            item["embedding_text"] = _entry_text_for_embedding(item)
            entries.append(item)
    else:
        item = {
            "entry_type": "pitfall",
            "memory_id": f"pitfall::{family}::{failure_category or end_reason or 'unknown'}",
            "task_id": task_id,
            "task_family": family,
            "goal": goal,
            "key": "__pitfall__",
            "value": {
                "failure_category": failure_category,
                "end_reason": end_reason,
            },
            "summary": _pitfall_summary(task_id, goal, failure_category, end_reason),
            "tags": _tags_for_entry(task_id, goal, "__pitfall__", failure_category),
            "importance": 0.42,
            "strength": 0.38,
            "confidence": 0.9,
            "success": False,
            "reinforcement_count": 1,
            "access_count": 0,
            "ts_created": ts,
            "ts_updated": ts,
            "last_accessed_at": "",
        }
        item["embedding_text"] = _entry_text_for_embedding(item)
        entries.append(item)
    return entries


class MemoryBankStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh_embeddings(self, items: list[dict[str, Any]]) -> None:
        embedder = get_embedder_from_env()
        if embedder is None:
            return
        pending: list[tuple[int, str]] = []
        model_name = getattr(embedder, "model_name", "")
        for idx, item in enumerate(items):
            text = item.get("embedding_text") or _entry_text_for_embedding(item)
            if item.get("embedding") and item.get("embedding_text") == text and item.get("embedding_model") == model_name:
                continue
            item["embedding_text"] = text
            pending.append((idx, text))
        if not pending:
            return
        vectors = embedder.encode_many([text for _, text in pending])
        for (idx, _), vec in zip(pending, vectors):
            items[idx]["embedding"] = [round(float(v), 6) for v in vec]
            items[idx]["embedding_model"] = model_name

    def _consolidate_family(self, items: list[dict[str, Any]], family: str) -> None:
        summarizer = get_memory_summarizer()
        if summarizer is None:
            return
        now = _iso_now()
        family_items = [item for item in items if str(item.get("task_family", "")) == family and str(item.get("entry_type", "")) in {"fact", "strategy", "episode", "pitfall"}]
        if not family_items:
            return
        success_items = [item for item in family_items if bool(item.get("success", False))][:10]
        pitfall_items = [item for item in family_items if str(item.get("entry_type", "")) == "pitfall"][:10]
        summary_entries: list[dict[str, Any]] = []
        if success_items:
            summary = summarizer.summarize_group(entry_type="strategy", task_family=family, source_items=success_items)
            tags = sorted(set(tag for item in success_items for tag in (item.get("tags") or [])))[:16]
            item = {
                "entry_type": "family_summary",
                "memory_id": f"family_summary::{family}",
                "task_id": f"{family}*",
                "task_family": family,
                "goal": f"family {family} summary",
                "key": "__family_summary__",
                "value": {"source_count": len(success_items), "source_type": "success"},
                "summary": summary,
                "tags": tags,
                "importance": 0.88,
                "strength": 0.86,
                "confidence": 0.95,
                "success": True,
                "reinforcement_count": 1,
                "access_count": 0,
                "ts_created": now,
                "ts_updated": now,
                "last_accessed_at": "",
            }
            item["embedding_text"] = _entry_text_for_embedding(item)
            summary_entries.append(item)
        if pitfall_items:
            summary = summarizer.summarize_group(entry_type="pitfall", task_family=family, source_items=pitfall_items)
            tags = sorted(set(tag for item in pitfall_items for tag in (item.get("tags") or [])))[:16]
            item = {
                "entry_type": "family_pitfall_summary",
                "memory_id": f"family_pitfall_summary::{family}",
                "task_id": f"{family}*",
                "task_family": family,
                "goal": f"family {family} pitfall summary",
                "key": "__family_pitfall_summary__",
                "value": {"source_count": len(pitfall_items), "source_type": "pitfall"},
                "summary": summary,
                "tags": tags,
                "importance": 0.64,
                "strength": 0.58,
                "confidence": 0.9,
                "success": False,
                "reinforcement_count": 1,
                "access_count": 0,
                "ts_created": now,
                "ts_updated": now,
                "last_accessed_at": "",
            }
            item["embedding_text"] = _entry_text_for_embedding(item)
            summary_entries.append(item)
        if not summary_entries:
            return
        by_identity = {_entry_identity(item): item for item in items}
        for entry in summary_entries:
            ident = _entry_identity(entry)
            existing = by_identity.get(ident)
            by_identity[ident] = entry if existing is None else _merge_item(existing, entry)
        items[:] = list(by_identity.values())

    def _consolidate_global(self, items: list[dict[str, Any]]) -> None:
        summarizer = get_memory_summarizer()
        if summarizer is None:
            return
        family_summaries = [
            item for item in items
            if str(item.get("entry_type", "")) in {"family_summary", "family_pitfall_summary"}
        ]
        if len(family_summaries) < 2:
            return
        now = _iso_now()
        summary = summarizer.summarize_group(entry_type="strategy", task_family="global", source_items=family_summaries[:12])
        tags = sorted(set(tag for item in family_summaries for tag in (item.get("tags") or [])))[:20]
        entry = {
            "entry_type": "global_summary",
            "memory_id": "global_summary::__global__",
            "task_id": "GLOBAL",
            "task_family": "GLOBAL",
            "goal": "global memory summary",
            "key": "__global_summary__",
            "value": {"source_count": len(family_summaries)},
            "summary": summary,
            "tags": tags,
            "importance": 0.72,
            "strength": 0.68,
            "confidence": 0.88,
            "success": True,
            "reinforcement_count": 1,
            "access_count": 0,
            "ts_created": now,
            "ts_updated": now,
            "last_accessed_at": "",
        }
        entry["embedding_text"] = _entry_text_for_embedding(entry)
        by_identity = {_entry_identity(item): item for item in items}
        ident = _entry_identity(entry)
        existing = by_identity.get(ident)
        by_identity[ident] = entry if existing is None else _merge_item(existing, entry)
        items[:] = list(by_identity.values())

    def _prune(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        max_items = max(80, _int_env("AGENT_MEMORYBANK_MAX_ITEMS", 600))
        min_strength = max(0.0, min(1.0, _float_env("AGENT_MEMORYBANK_MIN_EFFECTIVE_IMPORTANCE", 0.14)))
        keep_types = {"fact", "strategy", "family_summary"}
        decorated: list[tuple[float, str, dict[str, Any]]] = []
        for item in items:
            eff = _effective_strength(item, now=now)
            if eff < min_strength and str(item.get("entry_type", "")) not in keep_types:
                continue
            decorated.append((eff, str(item.get("ts_updated", item.get("ts_created", ""))), item))
        decorated.sort(key=lambda x: (x[0], x[1]), reverse=True)
        kept = [item for _, _, item in decorated[:max_items]]
        kept.sort(key=lambda item: str(item.get("ts_updated", item.get("ts_created", ""))))
        return kept

    def append_many(self, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        items = self.load()
        by_identity: dict[tuple[str, str], dict[str, Any]] = {_entry_identity(item): item for item in items}
        affected_families: set[str] = set()
        for entry in entries:
            family = str(entry.get("task_family", ""))
            if family:
                affected_families.add(family)
            ident = _entry_identity(entry)
            existing = by_identity.get(ident)
            by_identity[ident] = entry if existing is None else _merge_item(existing, entry)
        merged_items = list(by_identity.values())
        for family in sorted(affected_families):
            self._consolidate_family(merged_items, family)
        self._consolidate_global(merged_items)
        self._refresh_embeddings(merged_items)
        self.save(self._prune(merged_items))

    def retrieve(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        items = self.load()
        if not items:
            return []
        allowed_types = _allowed_types_env()
        if allowed_types:
            items = [item for item in items if str(item.get("entry_type", "")) in allowed_types]
        if not items:
            return []
        self._refresh_embeddings(items)
        qvec = Counter(_tokenize(query))
        qtags = set(_tokenize(query))
        embedder = get_embedder_from_env()
        query_embedding = embedder.encode(query) if embedder is not None else None
        now = datetime.now(timezone.utc)
        per_type: dict[str, list[tuple[float, dict[str, Any]]]] = {
            "family_summary": [],
            "family_pitfall_summary": [],
            "strategy": [],
            "fact": [],
            "episode": [],
            "pitfall": [],
            "global_summary": [],
        }
        scored_all: list[tuple[float, dict[str, Any]]] = []
        for item in items:
            tags = set(item.get("tags", []) or [])
            text = item.get("embedding_text") or _entry_text_for_embedding(item)
            lexical = _cosine(qvec, Counter(_tokenize(text)))
            dense = cosine_similarity(query_embedding, item.get("embedding")) if query_embedding else 0.0
            tag_overlap = len(qtags & tags) / max(1, len(qtags | tags))
            task_exact_bonus = 0.18 if str(item.get("task_id", "")) and str(item.get("task_id", "")) in query else 0.0
            family_bonus = 0.08 if str(item.get("task_family", "")).lower() in qtags else 0.0
            type_bonus = {
                "family_summary": 0.24,
                "family_pitfall_summary": 0.10,
                "fact": 0.18,
                "strategy": 0.20,
                "episode": 0.10,
                "pitfall": 0.06,
                "global_summary": 0.08,
            }.get(str(item.get("entry_type", "")), 0.0)
            strength = _effective_strength(item, now=now)
            score = 0.70 * lexical + 0.85 * dense + 0.30 * tag_overlap + 0.25 * strength + task_exact_bonus + family_bonus + type_bonus
            if score <= 0.15:
                continue
            per_type.setdefault(str(item.get("entry_type", "")), []).append((score, item))
            scored_all.append((score, item))

        if allowed_types:
            scored_all.sort(key=lambda x: x[0], reverse=True)
            picked = [item for _, item in scored_all[:top_k]]
            if picked:
                items_by_identity = {_entry_identity(item): item for item in items}
                ts = _iso_now()
                for item in picked:
                    ident = _entry_identity(item)
                    stored = items_by_identity.get(ident)
                    if stored is None:
                        continue
                    stored["access_count"] = int(stored.get("access_count", 0) or 0) + 1
                    stored["last_accessed_at"] = ts
                self.save(self._prune(list(items_by_identity.values())))
            return picked

        quotas = {
            "family_summary": min(2, top_k),
            "strategy": min(2, top_k),
            "fact": min(3, top_k),
            "episode": 1 if top_k >= 4 else 0,
            "family_pitfall_summary": 1 if top_k >= 4 else 0,
            "pitfall": 1 if top_k >= 5 else 0,
            "global_summary": 1 if top_k >= 6 else 0,
        }
        selected: list[tuple[float, dict[str, Any]]] = []
        for entry_type, scored in per_type.items():
            scored.sort(key=lambda x: x[0], reverse=True)
            selected.extend(scored[: quotas.get(entry_type, 0)])
        selected.sort(key=lambda x: x[0], reverse=True)
        picked = [item for _, item in selected[:top_k]]
        if picked:
            items_by_identity = {_entry_identity(item): item for item in items}
            ts = _iso_now()
            for item in picked:
                ident = _entry_identity(item)
                stored = items_by_identity.get(ident)
                if stored is None:
                    continue
                stored["access_count"] = int(stored.get("access_count", 0) or 0) + 1
                stored["last_accessed_at"] = ts
            self.save(self._prune(list(items_by_identity.values())))
        return picked
