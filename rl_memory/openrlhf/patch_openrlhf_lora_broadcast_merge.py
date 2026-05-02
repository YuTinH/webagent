#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import re
import shutil
from datetime import datetime
from pathlib import Path

HELPER = '''

from contextlib import contextmanager


@contextmanager
def _merged_lora_for_vllm(model):
    merged = False
    merge_method = getattr(model, "merge_adapter", None)
    unmerge_method = getattr(model, "unmerge_adapter", None)

    if callable(merge_method) and callable(unmerge_method):
        merge_method()
        merged = True
    try:
        yield
    finally:
        if merged:
            unmerge_method()


def _iter_vllm_sync_named_parameters(model):
    with _merged_lora_for_vllm(model):
        for name, param in model.named_parameters():
            if ".lora_A." in name or ".lora_B." in name:
                continue
            if name.endswith(".lora_embedding_A") or name.endswith(".lora_embedding_B"):
                continue

            if name.startswith("base_model.model."):
                name = name[len("base_model.model."):]
            elif name.startswith("base_model."):
                name = name[len("base_model."):]

            name = name.replace(".base_layer.", ".")
            name = name.replace(".modules_to_save.default.", ".")
            yield name, param
'''.rstrip()

CANDIDATE_MARKERS = [
    "class ActorPPOTrainer:",
    "class ActorPPOTrainer(",
]

METHOD_PATTERNS = [
    r"def broadcast_to_vllm\(self\):",
    r"def _broadcast_to_vllm\(self\):",
]


def resolve_target(explicit_target: str | None) -> Path:
    if explicit_target:
        return Path(explicit_target).expanduser().resolve()
    module = importlib.import_module("openrlhf.trainer.ray.ppo_actor")
    return Path(module.__file__).resolve()


def inject_helper(text: str) -> str:
    if "def _merged_lora_for_vllm" in text and "def _iter_vllm_sync_named_parameters" in text:
        text = re.sub(
            r"\nfrom contextlib import contextmanager\n.*?(?=\nclass ActorPPOTrainer(?:\(|:))",
            "\n" + HELPER + "\n\n",
            text,
            flags=re.S,
        )
        return text

    for marker in CANDIDATE_MARKERS:
        if marker in text:
            return text.replace(marker, HELPER + "\n\n\n" + marker, 1)
    raise RuntimeError("could not find ActorPPOTrainer class marker")


def patch_method_block(text: str) -> str:
    for pattern in METHOD_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        method_start = m.start()
        next_def = re.search(r"\n    def \w+\(", text[m.end():])
        next_class = re.search(r"\nclass \w+\(", text[m.end():]) or re.search(r"\nclass \w+:", text[m.end():])
        candidates = []
        if next_def:
            candidates.append(m.end() + next_def.start())
        if next_class:
            candidates.append(m.end() + next_class.start())
        method_end = min(candidates) if candidates else len(text)
        block = text[method_start:method_end]

        if "_iter_vllm_sync_named_parameters(model)" in block:
            return text

        patched = block.replace("len(list(model.named_parameters()))", "len(list(_iter_vllm_sync_named_parameters(model)))")
        patched = patched.replace("for name, param in model.named_parameters():", "for name, param in _iter_vllm_sync_named_parameters(model):")
        if patched == block:
            raise RuntimeError("did not find expected named_parameters() patterns in broadcast_to_vllm block")
        return text[:method_start] + patched + text[method_end:]

    raise RuntimeError("could not find broadcast_to_vllm method")


def patch_file(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = inject_helper(original)
    updated = patch_method_block(updated)

    if updated == original:
        print(f"already patched: {path}")
        return

    backup = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"patched: {path}")
    print(f"backup:  {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch OpenRLHF PPO actor to merge LoRA before broadcasting weights to vLLM.")
    parser.add_argument("--target", help="Optional explicit path to ppo_actor.py")
    args = parser.parse_args()

    target = resolve_target(args.target)
    if not target.exists():
        raise FileNotFoundError(target)
    patch_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
