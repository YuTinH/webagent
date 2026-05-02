#!/usr/bin/env python3
from __future__ import annotations

import importlib
import re
from pathlib import Path


INSERT = '''\
        if os.getenv("OPENRLHF_VLLM_LANGUAGE_MODEL_ONLY", "0") == "1":
            actor_kwargs["language_model_only"] = True

        gdn_prefill_backend = os.getenv("OPENRLHF_VLLM_GDN_PREFILL_BACKEND")
        if gdn_prefill_backend:
            actor_kwargs["gdn_prefill_backend"] = gdn_prefill_backend

'''


def main() -> None:
    module = importlib.import_module("openrlhf.trainer.ray.vllm_engine")
    target = Path(module.__file__)
    text = target.read_text()

    if "OPENRLHF_VLLM_GDN_PREFILL_BACKEND" in text:
        print(f"already patched: {target}")
        return

    pattern = re.compile(
        r"(        actor_kwargs\.update\(\n"
        r"            \{\n"
        r"                \"agent_func_path\": agent_func_path,\n"
        r"                \"remote_rm_url\": remote_rm_url,\n"
        r"            \}\n"
        r"        \)\n\n)"
    )
    new_text, count = pattern.subn(r"\1" + INSERT, text, count=1)
    if count != 1:
        raise RuntimeError(f"could not find actor_kwargs insertion point in {target}")

    backup = target.with_suffix(target.suffix + ".bak.qwen35_vllm_args")
    if not backup.exists():
        backup.write_text(text)
    target.write_text(new_text)
    print(f"patched: {target}")


if __name__ == "__main__":
    main()
