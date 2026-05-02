#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import re
import shutil
from datetime import datetime
from pathlib import Path

HELPER = '''

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

    # LoRA adapter tensors are handled by merging into base weights before sync.
    if ".lora_A." in name or ".lora_B." in name:
        return None
    if name.endswith(".lora_embedding_A") or name.endswith(".lora_embedding_B"):
        return None
    return name
'''.rstrip()

LOAD_PATTERN = re.compile(
    r"(?P<indent>[ \t]*)self\.model_runner\.model\.load_weights\(weights=\[\((?P<namevar>[^,]+),\s*weight\)\]\)"
)


def resolve_target(explicit_target: str | None) -> Path:
    if explicit_target:
        return Path(explicit_target).expanduser().resolve()
    module = importlib.import_module("openrlhf.trainer.ray.vllm_worker_wrap")
    return Path(module.__file__).resolve()


def inject_helper(text: str) -> str:
    if "def _normalize_vllm_weight_name" in text:
        text = re.sub(
            r"\ndef _normalize_vllm_weight_name\(name: str\):.*?(?=\nclass WorkerWrap:)",
            "\n" + HELPER + "\n\n",
            text,
            flags=re.S,
        )
        return text

    marker = "class WorkerWrap:\n"
    if marker not in text:
        raise RuntimeError("could not find WorkerWrap class")
    return text.replace(marker, HELPER + "\n\n\n" + marker, 1)


def patch_load_weights(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        namevar = match.group("namevar").strip()
        return (
            f"{indent}normalized_name = _normalize_vllm_weight_name({namevar})\n"
            f"{indent}if normalized_name is not None:\n"
            f"{indent}    self.model_runner.model.load_weights(weights=[(normalized_name, weight)])"
        )

    new_text, count = LOAD_PATTERN.subn(repl, text)
    if count == 0:
        raise RuntimeError("did not find load_weights call to patch")
    return new_text


def patch_file(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = inject_helper(original)
    updated = patch_load_weights(updated)

    if updated == original:
        print(f"already patched: {path}")
        return

    backup = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"patched: {path}")
    print(f"backup:  {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch OpenRLHF vLLM weight sync for LoRA merged-weight naming.")
    parser.add_argument("--target", help="Optional explicit path to vllm_worker_wrap.py")
    args = parser.parse_args()

    target = resolve_target(args.target)
    if not target.exists():
        raise FileNotFoundError(target)
    patch_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
