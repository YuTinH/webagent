#!/usr/bin/env python3
"""Trajectory RAG baseline using short action sketches from task oracle traces."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from rl_memory.memory_baselines.memorybank.embeddings import HFTextEmbedder, cosine_similarity

_TOKEN_RE = re.compile(r"[^a-zA-Z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN_RE.split((text or "").lower()) if tok]


def _counter_cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[k] * b[k] for k in common)
    den_a = math.sqrt(sum(v * v for v in a.values()))
    den_b = math.sqrt(sum(v * v for v in b.values()))
    if den_a == 0.0 or den_b == 0.0:
        return 0.0
    return num / den_a / den_b


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _tasks_root() -> Path:
    raw = (os.environ.get("AGENT_TRAJECTORY_RAG_TASKS_ROOT") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[3] / "tasks"


def _corpus_path() -> Path:
    raw = (os.environ.get("AGENT_TRAJECTORY_RAG_CORPUS") or "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent / "runs" / "default_corpus.json"


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in {"clean", "dlevel", "dseed", "oseed"}:
            continue
        query_pairs.append((key, value))
    query = ""
    if query_pairs:
        query = "?" + "&".join(f"{k}={v}" for k, v in query_pairs)
    if host and not re.match(r"^(localhost|127\.0\.0\.1)(:\d+)?$", host):
        return f"{host}{path}{query}"
    return f"{path.lstrip('/')}{query}"


def _step_to_text(step: dict[str, Any]) -> str:
    act = str(step.get("act", "")).strip().lower()
    if act == "open":
        return f"OPEN {_normalize_url(str(step.get('url', '')))}".strip()
    if act == "click":
        return f"CLICK {str(step.get('selector', '')).strip()}".strip()
    if act == "type":
        selector = str(step.get("selector", "")).strip()
        value = str(step.get("value", "")).strip()
        return f"TYPE {selector} <= {value}".strip()
    if act == "select":
        selector = str(step.get("selector", "")).strip()
        value = str(step.get("value", "")).strip()
        return f"SELECT {selector} = {value}".strip()
    if act == "wait":
        selector = str(step.get("selector", "")).strip()
        return f"WAIT {selector}".strip()
    return act.upper() if act else "UNKNOWN"


def _action_sketch(trace_steps: list[dict[str, Any]], max_steps: int = 4) -> str:
    items = [_step_to_text(step) for step in trace_steps[:max_steps] if isinstance(step, dict)]
    if len(trace_steps) > max_steps:
        items.append("...")
    return " -> ".join(item for item in items if item)


def _action_history_sketch(actions: list[str], max_steps: int = 6) -> str:
    items = [str(action or "").strip() for action in actions[:max_steps] if str(action or "").strip()]
    if len(actions) > max_steps:
        items.append("...")
    return " -> ".join(items)


def _task_spec_for_slug(task_slug: str) -> dict[str, Any]:
    spec_path = _tasks_root() / task_slug / "task_spec.json"
    return _read_json(spec_path, {})


def _trace_for_slug(task_slug: str) -> dict[str, Any]:
    trace_path = _tasks_root() / task_slug / "oracle_trace.json"
    return _read_json(trace_path, {})


def _family_for_task(task_slug: str, spec: dict[str, Any]) -> str:
    family = str(spec.get("family", "")).strip().upper()
    if family:
        return family
    return task_slug[:1].upper()


def _corpus_entry(task_slug: str) -> dict[str, Any] | None:
    spec = _task_spec_for_slug(task_slug)
    trace = _trace_for_slug(task_slug)
    steps = trace.get("steps") if isinstance(trace, dict) else None
    if not isinstance(steps, list) or not steps:
        return None
    goal = str(spec.get("goal", "")).strip()
    family = _family_for_task(task_slug, spec)
    allowed_domains = [str(x).strip() for x in (spec.get("allowed_domains") or []) if str(x).strip()]
    sketch = _action_sketch(steps)
    retrieval_parts = [task_slug, family, goal, " ".join(allowed_domains), sketch]
    retrieval_text = " ".join(part for part in retrieval_parts if part).strip()
    return {
        "task_id": task_slug,
        "family": family,
        "goal": goal,
        "allowed_domains": allowed_domains,
        "trace_len": len(steps),
        "action_sketch": sketch,
        "trace_steps": steps,
        "retrieval_text": retrieval_text,
    }


def build_corpus(tasks_root: Path | None = None) -> list[dict[str, Any]]:
    root = tasks_root or _tasks_root()
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        entry = _corpus_entry(child.name)
        if entry is not None:
            items.append(entry)
    return items


class TrajectoryRAGStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else _corpus_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._embedder = None
        self._embed_model_name = ""
        self._ensure_corpus()

    def _ensure_corpus(self) -> None:
        rebuild = (os.environ.get("AGENT_TRAJECTORY_RAG_REBUILD", "0").strip() == "1")
        if rebuild or (not self.path.exists()) or self.path.stat().st_size == 0:
            corpus = build_corpus()
            self.path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        self._ensure_corpus()
        return _read_json(self.path, [])

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_embedder(self):
        model_name = (os.environ.get("AGENT_TRAJECTORY_RAG_EMBED_MODEL") or os.environ.get("AGENT_MEMORYBANK_EMBED_MODEL") or "").strip()
        if not model_name:
            return None
        device = (os.environ.get("AGENT_TRAJECTORY_RAG_EMBED_DEVICE") or os.environ.get("AGENT_MEMORYBANK_EMBED_DEVICE") or "cpu").strip() or "cpu"
        trust_remote_code = (os.environ.get("AGENT_TRAJECTORY_RAG_EMBED_TRUST_REMOTE_CODE", "true").strip().lower() == "true")
        batch_size = int(os.environ.get("AGENT_TRAJECTORY_RAG_EMBED_BATCH_SIZE", "8"))
        if self._embedder is None or self._embed_model_name != model_name:
            self._embedder = HFTextEmbedder(model_name, device=device, trust_remote_code=trust_remote_code, batch_size=batch_size)
            self._embed_model_name = model_name
        return self._embedder

    def _refresh_embeddings(self, items: list[dict[str, Any]]) -> None:
        embedder = self._get_embedder()
        if embedder is None:
            return
        missing = [item for item in items if item.get("embedding_model") != self._embed_model_name or not item.get("embedding")]
        if not missing:
            return
        vectors = embedder.encode_many([str(item.get("retrieval_text", "")) for item in missing])
        for item, vec in zip(missing, vectors):
            item["embedding"] = vec
            item["embedding_model"] = self._embed_model_name
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def retrieve(self, *, query: str, top_k: int = 2, task_id: str = "") -> list[dict[str, Any]]:
        items = self.load()
        if not items:
            return []
        current_spec = _task_spec_for_slug(task_id)
        current_family = _family_for_task(task_id, current_spec) if task_id else ""
        current_domains = {str(x).strip() for x in (current_spec.get("allowed_domains") or []) if str(x).strip()}
        allow_same_task = (os.environ.get("AGENT_TRAJECTORY_RAG_ALLOW_SAME_TASK", "0").strip() == "1")
        allow_same_family = (os.environ.get("AGENT_TRAJECTORY_RAG_ALLOW_SAME_FAMILY", "1").strip() == "1")

        filtered = []
        for item in items:
            if not allow_same_task and task_id and str(item.get("task_id", "")) == task_id:
                continue
            if not allow_same_family and current_family and str(item.get("family", "")) == current_family:
                continue
            filtered.append(item)
        if not filtered:
            return []

        self._refresh_embeddings(filtered)
        query_counter = Counter(_tokenize(query))
        query_embed = None
        embedder = self._get_embedder()
        if embedder is not None:
            try:
                query_embed = embedder.encode(query)
            except Exception:
                query_embed = None

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in filtered:
            lexical = _counter_cosine(query_counter, Counter(_tokenize(str(item.get("retrieval_text", "")))))
            embed = cosine_similarity(query_embed, item.get("embedding")) if query_embed is not None else 0.0
            family_bonus = 0.08 if current_family and str(item.get("family", "")) == current_family else 0.0
            domain_overlap = len(current_domains & set(item.get("allowed_domains", []) or []))
            domain_bonus = min(0.12, 0.06 * domain_overlap)
            score = 0.62 * lexical + 0.22 * embed + family_bonus + domain_bonus
            if lexical <= 0.0 and embed <= 0.0 and family_bonus <= 0.0 and domain_bonus <= 0.0:
                continue
            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        results = []
        for score, item in scored[: max(1, int(top_k))]:
            payload = dict(item)
            payload["score"] = round(float(score), 4)
            results.append(payload)
        return results

    def append_run(
        self,
        *,
        task_id: str,
        goal: str,
        action_history: list[str],
        allowed_domains: list[str] | None = None,
        success: bool = True,
    ) -> None:
        if not success or not action_history:
            return
        spec = _task_spec_for_slug(task_id)
        family = _family_for_task(task_id, spec)
        domains = [str(x).strip() for x in (allowed_domains or spec.get("allowed_domains") or []) if str(x).strip()]
        sketch = _action_history_sketch(action_history)
        retrieval_parts = [task_id, family, goal, " ".join(domains), sketch]
        entry = {
            "task_id": task_id,
            "family": family,
            "goal": goal,
            "allowed_domains": domains,
            "trace_len": len(action_history),
            "action_sketch": sketch,
            "trace_steps": [{"act": "agent_action", "action": action} for action in action_history],
            "retrieval_text": " ".join(part for part in retrieval_parts if part).strip(),
            "online_source": True,
            "success": True,
        }
        items = self.load()
        items = [
            item for item in items
            if not (
                bool(item.get("online_source"))
                and str(item.get("task_id", "")) == task_id
                and str(item.get("action_sketch", "")) == sketch
            )
        ]
        items.append(entry)
        self.save(items)
