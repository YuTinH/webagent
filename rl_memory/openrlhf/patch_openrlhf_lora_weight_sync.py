#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from datetime import datetime
from pathlib import Path


HELPER = """

def _normalize_vllm_weight_name(name: str) -> str:
    prefixes = (
        "base_model.model.",
    )
    for prefix in prefixes:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name
""".strip(
    "\n"
)


NEEDLE = "self.model_runner.model.load_weights(weights=[(name, weight)])"
REPLACEMENT = (
    "normalized_name = _normalize_vllm_weight_name(name)\n"
    "        self.model_runner.model.load_weights(weights=[(normalized_name, weight)])"
)


def resolve_target(explicit_target: str | None) -> Path:
    if explicit_target:
        return Path(explicit_target).expanduser().resolve()

    module = importlib.import_module("openrlhf.trainer.ray.vllm_worker_wrap")
    return Path(module.__file__).resolve()


def patch_file(path: Path) -> None:
    original = path.read_text(encoding="utf-8")

    if "_normalize_vllm_weight_name" in original:
        print(f"already patched: {path}")
        return

    if NEEDLE not in original:
        raise RuntimeError(f"did not find target load_weights call in {path}")

    updated = original
    updated = updated.replace("class WorkerWrap:\n", HELPER + "\n\n\nclass WorkerWrap:\n", 1)
    updated = updated.replace(NEEDLE, REPLACEMENT)

    backup = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"patched: {path}")
    print(f"backup:  {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch OpenRLHF vLLM weight sync to normalize LoRA/Peft weight names."
    )
    parser.add_argument(
        "--target",
        help="Optional explicit path to vllm_worker_wrap.py. If omitted, import openrlhf and locate automatically.",
    )
    args = parser.parse_args()

    target = resolve_target(args.target)
    if not target.exists():
        raise FileNotFoundError(target)

    patch_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
