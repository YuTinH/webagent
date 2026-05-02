#!/usr/bin/env python3
from __future__ import annotations

import importlib
import re
from pathlib import Path


PPO_ITER = '''\
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

            if name.startswith("model.") or name.startswith("lm_head."):
                name = "language_model." + name

            yield name, param
'''.rstrip()


WORKER_NORMALIZER = '''\
def _normalize_vllm_weight_name(name: str):
    prefixes = (
        "base_model.model.",
        "base_model.",
    )
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    name = name.replace(".base_layer.", ".")
    name = name.replace(".modules_to_save.default.", ".")

    if name.startswith("model.") or name.startswith("lm_head."):
        name = "language_model." + name

    if ".lora_A." in name or ".lora_B." in name:
        return None
    if name.endswith(".lora_embedding_A") or name.endswith(".lora_embedding_B"):
        return None
    return name
'''.rstrip()


def _module_path(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    return Path(module.__file__).resolve()


def _patch_between(text: str, pattern: str, replacement: str, target: Path) -> str:
    new_text, count = re.subn(pattern, replacement + "\n\n", text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"could not patch expected block in {target}")
    return new_text


def patch_ppo_actor() -> None:
    target = _module_path("openrlhf.trainer.ray.ppo_actor")
    text = target.read_text()
    updated = _patch_between(
        text,
        r"def _iter_vllm_sync_named_parameters\(model\):.*?(?=\n\nclass ActorPPOTrainer)",
        PPO_ITER,
        target,
    )
    if updated == text:
        print(f"ppo_actor already patched: {target}")
        return
    target.write_text(updated)
    print(f"patched ppo_actor qwen3.5 names: {target}")


def patch_worker_wrap() -> None:
    target = _module_path("openrlhf.trainer.ray.vllm_worker_wrap")
    text = target.read_text()
    updated = _patch_between(
        text,
        r"def _normalize_vllm_weight_name\(name: str\).*?(?=\n\nclass WorkerWrap)",
        WORKER_NORMALIZER,
        target,
    )
    if updated == text:
        print(f"vllm_worker_wrap already patched: {target}")
        return
    target.write_text(updated)
    print(f"patched vllm_worker_wrap qwen3.5 names: {target}")


def main() -> None:
    patch_ppo_actor()
    patch_worker_wrap()


if __name__ == "__main__":
    main()
