#!/usr/bin/env python3
"""Simple persistent reflection memory for benchmark experiments."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
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


class ReflexionMemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def append(self, item: dict[str, Any]) -> None:
        items = self.load()
        items.append(item)
        self.save(items)

    def retrieve(self, query: str, top_k: int = 3, task_id: str | None = None) -> list[dict[str, Any]]:
        items = self.load()
        qvec = Counter(_tokenize(query))
        scored = []
        for item in items:
            if task_id and item.get("task_id") not in {task_id, "*"}:
                continue
            text = " ".join(
                [
                    str(item.get("task_id", "")),
                    str(item.get("theme", "")),
                    str(item.get("failure_category", "")),
                    str(item.get("reflection", "")),
                ]
            )
            score = _cosine(qvec, Counter(_tokenize(text)))
            if score > 0.0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
