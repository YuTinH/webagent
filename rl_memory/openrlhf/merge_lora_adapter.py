#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge a LoRA adapter into a base causal LM for local evaluation.")
    parser.add_argument("--base-model", required=True, help="Path or HF id of the base model")
    parser.add_argument("--adapter", required=True, help="Path to the saved LoRA adapter directory")
    parser.add_argument("--output", required=True, help="Directory to save the merged model")
    parser.add_argument("--dtype", default="bfloat16", help="torch dtype name: bfloat16/float16/float32/auto")
    parser.add_argument("--trust-remote-code", action="store_true", help="Enable trust_remote_code when loading")
    return parser.parse_args()


def resolve_dtype(torch_mod, name: str):
    name = (name or "auto").strip().lower()
    if name == "auto":
        if torch_mod.cuda.is_available():
            return getattr(torch_mod, "bfloat16", torch_mod.float16)
        return None
    return getattr(torch_mod, name)


def main() -> int:
    args = parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    torch_dtype = resolve_dtype(torch, args.dtype)
    model_kwargs = {"trust_remote_code": args.trust_remote_code}
    if torch_dtype is not None:
        model_kwargs["torch_dtype"] = torch_dtype

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=args.trust_remote_code)
    base_model = AutoModelForCausalLM.from_pretrained(args.base_model, **model_kwargs)
    peft_model = PeftModel.from_pretrained(base_model, args.adapter)
    merged_model = peft_model.merge_and_unload()

    merged_model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"merged model saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
