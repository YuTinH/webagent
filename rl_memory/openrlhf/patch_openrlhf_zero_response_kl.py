#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import re
import shutil
from datetime import datetime
from pathlib import Path

DIV_PATTERN = re.compile(
    r'^(?P<indent>[ \t]*)status\["(?P<metric>[^"]+)"\] /\= status\["response_length"\]$',
    re.M,
)


def resolve_target(explicit_target: str | None) -> Path:
    if explicit_target:
        return Path(explicit_target).expanduser().resolve()
    module = importlib.import_module("openrlhf.trainer.ray.ppo_actor")
    return Path(module.__file__).resolve()


def patch_file(path: Path) -> None:
    original = path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        metric = match.group("metric")
        return (
            f'{indent}response_length = status.get("response_length", 0)\n'
            f'{indent}if response_length:\n'
            f'{indent}    status["{metric}"] /= response_length\n'
            f'{indent}else:\n'
            f'{indent}    status["{metric}"] = 0.0'
        )

    updated, count = DIV_PATTERN.subn(repl, original)
    if count == 0:
        print(f"already patched or no response_length divisions found: {path}")
        return

    backup = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"patched: {path}")
    print(f"backup:  {backup}")
    print(f"replaced divisions: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch OpenRLHF PPO actor to guard any metric averaged by zero response_length."
    )
    parser.add_argument("--target", help="Optional explicit path to ppo_actor.py")
    args = parser.parse_args()

    target = resolve_target(args.target)
    if not target.exists():
        raise FileNotFoundError(target)
    patch_file(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
