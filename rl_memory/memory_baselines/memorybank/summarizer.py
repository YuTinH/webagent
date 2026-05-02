#!/usr/bin/env python3
"""Optional MemoryBank consolidation summarizer."""

from __future__ import annotations

import json
import os
from collections import Counter
from functools import lru_cache
from typing import Any

import requests


def _tokenize(text: str) -> list[str]:
    import re
    return [tok for tok in re.split(r"[^a-zA-Z0-9_]+", text.lower()) if tok]


def _mode() -> str:
    return (os.environ.get("AGENT_MEMORYBANK_SUMMARIZER") or "heuristic").strip().lower()


class HeuristicSummarizer:
    def summarize_group(self, *, entry_type: str, task_family: str, source_items: list[dict[str, Any]]) -> str:
        goals = [str(item.get("goal", "")) for item in source_items if item.get("goal")]
        tags = Counter(tag for item in source_items for tag in (item.get("tags") or []))
        keys = Counter(str(item.get("key", "")) for item in source_items if item.get("key") and not str(item.get("key")).startswith("__"))
        failures = Counter(str(item.get("value", {}).get("failure_category", "")) for item in source_items if entry_type == "pitfall")
        top_tags = [tag for tag, _ in tags.most_common(4) if len(tag) >= 3]
        top_keys = [key for key, _ in keys.most_common(3)]
        goal_hint = goals[0] if goals else f"family {task_family}"
        if entry_type == "pitfall":
            top_failures = [name for name, _ in failures.most_common(3) if name]
            failure_text = ", ".join(top_failures) if top_failures else "common execution mistakes"
            key_text = "; ".join(top_keys) if top_keys else "visible selectors and valid options"
            return (
                f"For family {task_family}, avoid {failure_text}. Re-check page state, use visible selectors, "
                f"and verify fields like {key_text} before repeating actions."
            )
        key_text = "; ".join(top_keys) if top_keys else "the expected memory fields"
        tag_text = ", ".join(top_tags) if top_tags else "relevant page state"
        return (
            f"For family {task_family}, successful tasks similar to '{goal_hint}' usually require checking {key_text}. "
            f"Prioritize cues related to {tag_text}, and stop only after the target state is reflected in memory or environment state."
        )


class OpenAICompatibleSummarizer:
    def __init__(self):
        self.api_key = (
            os.environ.get("AGENT_MEMORYBANK_SUMMARIZER_API_KEY")
            or os.environ.get("AGENT_API_KEY")
            or ""
        )
        self.base_url = (
            os.environ.get("AGENT_MEMORYBANK_SUMMARIZER_BASE_URL")
            or os.environ.get("AGENT_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.model = (
            os.environ.get("AGENT_MEMORYBANK_SUMMARIZER_MODEL")
            or os.environ.get("AGENT_MODEL")
            or ""
        )
        self.max_tokens = int(os.environ.get("AGENT_MEMORYBANK_SUMMARIZER_MAX_TOKENS", "128"))
        self.temperature = float(os.environ.get("AGENT_MEMORYBANK_SUMMARIZER_TEMPERATURE", "0.0"))

    def _chat_completions_url(self):
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if "/api/paas/v4" in self.base_url:
            return f"{self.base_url}/chat/completions"
        if self.base_url.endswith("/v1") or self.base_url.endswith("/api/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def summarize_group(self, *, entry_type: str, task_family: str, source_items: list[dict[str, Any]]) -> str:
        if not self.api_key or not self.model:
            return HeuristicSummarizer().summarize_group(entry_type=entry_type, task_family=task_family, source_items=source_items)
        compact_items = []
        for item in source_items[:8]:
            compact_items.append(
                {
                    "task_id": item.get("task_id"),
                    "goal": item.get("goal"),
                    "summary": item.get("summary"),
                    "tags": item.get("tags", [])[:8],
                    "key": item.get("key"),
                    "value": item.get("value") if entry_type == "pitfall" else None,
                }
            )
        system = (
            "You summarize benchmark memories for a web agent. Output one short English paragraph only. "
            "Keep semantics faithful, no invented facts, no markdown."
        )
        user = (
            f"Summarize the recurring {entry_type} memory for task family {task_family}. "
            f"Source items: {json.dumps(compact_items, ensure_ascii=False)}"
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            response = requests.post(self._chat_completions_url(), headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            content = str(content).strip()
            if content:
                return content
        except Exception:
            pass
        return HeuristicSummarizer().summarize_group(entry_type=entry_type, task_family=task_family, source_items=source_items)


@lru_cache(maxsize=1)
def get_memory_summarizer():
    mode = _mode()
    if mode == "off":
        return None
    if mode == "llm":
        return OpenAICompatibleSummarizer()
    return HeuristicSummarizer()
