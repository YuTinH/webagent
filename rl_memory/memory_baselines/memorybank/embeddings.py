#!/usr/bin/env python3
"""Optional dense embedding backend for MemoryBank retrieval."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable


def _normalize(vec: list[float]) -> list[float]:
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


class HFTextEmbedder:
    def __init__(self, model_name: str, device: str = "cpu", trust_remote_code: bool = True, batch_size: int = 8):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = device
        self.batch_size = max(1, int(batch_size))
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote_code)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=trust_remote_code)
        self.model.eval()
        try:
            self.model.to(device)
        except Exception:
            self.device = "cpu"
            self.model.to("cpu")

    def _mean_pool(self, outputs, attention_mask):
        token_embeddings = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        masked = token_embeddings * mask
        summed = masked.sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        return summed / counts

    def encode_many(self, texts: Iterable[str]) -> list[list[float]]:
        texts = [str(t or "") for t in texts]
        if not texts:
            return []
        all_vecs: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            encoded = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=256,
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with self.torch.no_grad():
                outputs = self.model(**encoded)
                pooled = self._mean_pool(outputs, encoded["attention_mask"])
                pooled = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
            all_vecs.extend([row.detach().cpu().tolist() for row in pooled])
        return all_vecs

    def encode(self, text: str) -> list[float]:
        out = self.encode_many([text])
        return out[0] if out else []


@lru_cache(maxsize=4)
def get_embedder_from_env():
    model_name = (os.environ.get("AGENT_MEMORYBANK_EMBED_MODEL") or "").strip()
    if not model_name:
        return None
    device = (os.environ.get("AGENT_MEMORYBANK_EMBED_DEVICE") or "cpu").strip() or "cpu"
    trust_remote_code = (os.environ.get("AGENT_MEMORYBANK_EMBED_TRUST_REMOTE_CODE", "true").strip().lower() == "true")
    batch_size = int(os.environ.get("AGENT_MEMORYBANK_EMBED_BATCH_SIZE", "8"))
    return HFTextEmbedder(model_name, device=device, trust_remote_code=trust_remote_code, batch_size=batch_size)


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(float(x) * float(y) for x, y in zip(a, b))
