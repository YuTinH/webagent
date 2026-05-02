#!/usr/bin/env python3
import argparse
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


SYSTEM_PROMPT = """You rewrite benchmark task instructions for a web-agent evaluation suite.
Preserve semantics exactly while improving expression diversity.

Hard requirements:
- Keep every entity, ID, date, time, amount, plan name, quoted title, and constraint unchanged.
- Do not add or remove steps.
- Do not add hints that reveal the oracle path or selectors.
- Keep the result in English.
- Return JSON only: {"rewritten_instruction": "..."}
"""


FORCE_DISTINCT_APPEND = """
Additional requirement for this retry:
- Your previous rewrite was too close to the original.
- You must change the opening phrasing or sentence structure.
- Do not return the original sentence unchanged.
"""


GENERIC_CAPITALIZED = {
    "Your",
    "Task",
    "Complete",
    "Ensure",
    "Reserve",
    "Update",
    "Request",
    "Configure",
    "Online",
    "Book",
    "Find",
    "Set",
    "Enable",
    "Submit",
    "Activate",
    "Open",
    "Check",
    "Renew",
    "Create",
}


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_json_if_valid(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        if path.stat().st_size == 0:
            return default
    except Exception:
        return default
    try:
        return _read_json(path)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _iter_slot_values(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_slot_values(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            yield from _iter_slot_values(nested)
        return
    if isinstance(value, (int, float)):
        yield str(value)
        return
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            yield stripped


def _extract_quoted_strings(text: str) -> List[str]:
    tokens = []
    for m in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text):
        token = (m.group(1) or m.group(2) or "").strip()
        if token:
            tokens.append(token)
    return tokens


def _extract_regex_tokens(text: str, pattern: str) -> List[str]:
    return [m.group(0) for m in re.finditer(pattern, text)]


def _extract_capitalized_tokens(text: str) -> List[str]:
    tokens = []
    for token in re.findall(r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)*\b", text):
        if token in GENERIC_CAPITALIZED:
            continue
        tokens.append(token)
    return tokens


def protected_tokens_for_step(step: Dict[str, Any], original_instruction: str) -> List[str]:
    original = original_instruction or ""
    keep: List[str] = []
    seen = set()

    def add(token: str) -> None:
        token = str(token).strip()
        if not token:
            return
        if token not in original:
            return
        if token not in seen:
            seen.add(token)
            keep.append(token)

    for token in _extract_quoted_strings(original):
        add(token)
    for token in _extract_regex_tokens(original, r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?\b"):
        add(token)
    for token in _extract_regex_tokens(original, r"\b\d+(?:\.\d+)?\b"):
        add(token)
    for token in _extract_regex_tokens(original, r"\b[A-Z][A-Z0-9_-]*\d[A-Z0-9_-]*\b"):
        add(token)
    for token in _extract_capitalized_tokens(original):
        add(token)

    slot_values = (((step.get("template_info") or {}).get("slot_values")) or {})
    for token in _iter_slot_values(slot_values):
        add(token)

    return keep


def validate_rewrite(original: str, rewritten: str, protected_tokens: List[str]) -> Tuple[bool, List[str]]:
    rewritten = _normalize_ws(rewritten)
    problems: List[str] = []
    if not rewritten:
        problems.append("empty_output")
    if rewritten == _normalize_ws(original):
        problems.append("unchanged")
    for token in protected_tokens:
        if token not in rewritten:
            problems.append(f"missing:{token}")
    if "assistant:" in rewritten.lower() or "human:" in rewritten.lower():
        problems.append("dialogue_leak")
    if rewritten.startswith("{") and rewritten.endswith("}"):
        problems.append("json_leak")
    return len(problems) == 0, problems


def _extract_json_payload(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start:end + 1])
    raise ValueError(f"Could not parse JSON payload from: {cleaned[:400]}")


def _build_rewrite_user_prompt(original: str, protected_tokens: List[str], force_distinct: bool = False) -> str:
    prompt = (
        "Rewrite the following instruction with better phrasing diversity while preserving meaning exactly.\n\n"
        f"Original instruction:\n{original}\n\n"
        f"Protected tokens that must appear unchanged in the rewrite:\n{json.dumps(protected_tokens, ensure_ascii=False)}\n\n"
    )
    if force_distinct:
        prompt += FORCE_DISTINCT_APPEND.strip() + "\n\n"
    prompt += 'Return JSON only: {"rewritten_instruction": "..."}'
    return prompt


def _heuristic_rewrite(original: str) -> Optional[str]:
    text = _normalize_ws(original)
    lower = text.lower()
    rules = [
        ("complete the following task: ", "Please complete this task: "),
        ("your task is to ", "Please "),
        ("ensure you ", "Make sure to "),
        ("reserve ", "Please reserve "),
        ("update ", "Please update "),
        ("configure ", "Please configure "),
        ("request ", "Please request "),
        ("book ", "Please book "),
        ("find ", "Please find "),
        ("set ", "Please set "),
        ("enable ", "Please enable "),
        ("submit ", "Please submit "),
        ("activate ", "Please activate "),
        ("renew ", "Please renew "),
        ("create ", "Please create "),
        ("online check-in for ", "Please complete online check-in for "),
    ]
    for prefix, repl in rules:
        if lower.startswith(prefix):
            return repl + text[len(prefix):]
    return None


class OpenAICompatibleRewriter:
    def __init__(self, model: str, temperature: float):
        self.model = model
        self.temperature = temperature
        raw_disable_thinking = os.environ.get("REWRITE_DISABLE_THINKING")
        if raw_disable_thinking is None:
            self.disable_thinking = "glm-" in self.model.lower()
        else:
            self.disable_thinking = raw_disable_thinking.strip().lower() == "true"
        self.api_key = (
            os.environ.get("REWRITE_API_KEY")
            or os.environ.get("AGENT_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or ""
        )
        self.base_url = (
            os.environ.get("REWRITE_BASE_URL")
            or os.environ.get("AGENT_BASE_URL")
            or os.environ.get("ANTHROPIC_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        if not self.api_key:
            raise RuntimeError("Missing REWRITE_API_KEY or AGENT_API_KEY for openai_compatible backend")

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if "/api/paas/v4" in self.base_url:
            return f"{self.base_url}/chat/completions"
        if self.base_url.endswith("/v1") or self.base_url.endswith("/api/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def rewrite(self, original: str, protected_tokens: List[str], force_distinct: bool = False) -> str:
        user_prompt = _build_rewrite_user_prompt(original, protected_tokens, force_distinct=force_distinct)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 300,
        }
        if self.disable_thinking and "glm-" in self.model.lower():
            payload["thinking"] = {"type": "disabled"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(self._chat_completions_url(), headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        payload = _extract_json_payload(content)
        return str(payload.get("rewritten_instruction") or "").strip()


class LocalHFRewriter:
    def __init__(self, model: str, temperature: float):
        self.model_name = model
        self.temperature = temperature
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
        model_kwargs: Dict[str, Any] = {"trust_remote_code": True}
        dtype_name = (os.environ.get("AGENT_HF_DTYPE") or "auto").strip().lower()
        if dtype_name == "auto" and torch.cuda.is_available():
            model_kwargs["torch_dtype"] = getattr(torch, "bfloat16", torch.float16)
        elif dtype_name != "auto":
            dtype = getattr(torch, dtype_name, None)
            if dtype is not None:
                model_kwargs["torch_dtype"] = dtype
        device_map = os.environ.get("AGENT_HF_DEVICE_MAP", "auto")
        if device_map:
            model_kwargs["device_map"] = device_map
        self.model = AutoModelForCausalLM.from_pretrained(model, **model_kwargs)
        self.model.eval()

    def rewrite(self, original: str, protected_tokens: List[str], force_distinct: bool = False) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_rewrite_user_prompt(original, protected_tokens, force_distinct=force_distinct),
            },
        ]

        if hasattr(self.tokenizer, "apply_chat_template"):
            input_ids = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
            )
        else:
            prompt = SYSTEM_PROMPT + "\n\n" + messages[-1]["content"]
            input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids

        if not isinstance(input_ids, self.torch.Tensor):
            input_ids = input_ids["input_ids"]

        if hasattr(self.model, "device") and str(self.model.device) != "meta":
            input_ids = input_ids.to(self.model.device)

        gen_kwargs = {
            "max_new_tokens": 300,
            "do_sample": self.temperature > 0,
            "temperature": max(self.temperature, 1e-5),
            "pad_token_id": self.tokenizer.eos_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        with self.torch.no_grad():
            outputs = self.model.generate(input_ids, **gen_kwargs)
        generated = outputs[0][input_ids.shape[-1]:]
        text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        payload = _extract_json_payload(text)
        return str(payload.get("rewritten_instruction") or "").strip()


def build_rewriter(backend: str, model: str, temperature: float):
    if backend == "openai_compatible":
        return OpenAICompatibleRewriter(model=model, temperature=temperature)
    if backend == "hf_local":
        return LocalHFRewriter(model=model, temperature=temperature)
    raise ValueError(f"Unsupported backend: {backend}")


def rewrite_instruction(
    rewriter,
    original_instruction: str,
    protected_tokens: List[str],
    max_retries: int,
) -> Tuple[str, Dict[str, Any]]:
    last_error = None
    last_problems: List[str] = []
    for attempt in range(1, max_retries + 1):
        try:
            force_distinct = "unchanged" in last_problems
            rewritten = rewriter.rewrite(
                original_instruction,
                protected_tokens,
                force_distinct=force_distinct,
            )
            ok, problems = validate_rewrite(original_instruction, rewritten, protected_tokens)
            if ok:
                return _normalize_ws(rewritten), {
                    "validated": True,
                    "attempts": attempt,
                    "protected_tokens": protected_tokens,
                    "validation_problems": [],
                }
            last_problems = problems
            last_error = f"validation_failed:{problems}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(min(2 * attempt, 5) + random.random())

    if last_problems and set(last_problems) == {"unchanged"}:
        fallback = _heuristic_rewrite(original_instruction)
        if fallback:
            ok, problems = validate_rewrite(original_instruction, fallback, protected_tokens)
            if ok:
                return _normalize_ws(fallback), {
                    "validated": True,
                    "attempts": max_retries,
                    "protected_tokens": protected_tokens,
                    "validation_problems": [],
                    "fallback": "heuristic_template",
                }
    raise RuntimeError(f"rewrite_failed:{last_error}")


def process_file(
    src_path: Path,
    dst_path: Path,
    cache: Dict[str, Dict[str, Any]],
    rewriter,
    overwrite: bool,
    max_retries: int,
    max_chains: Optional[int],
) -> Dict[str, Any]:
    data = _read_json(src_path)
    if max_chains is not None:
        data = data[:max_chains]
    existing = _read_json_if_valid(dst_path)
    if isinstance(existing, list) and len(existing) == len(data):
        out_data = existing
    else:
        out_data = json.loads(json.dumps(data))

    changed = 0
    skipped = 0
    failed: List[Dict[str, Any]] = []
    total_steps = sum(len(chain.get("steps", [])) for chain in data)
    processed_steps = 0

    for chain_idx, chain in enumerate(data):
        out_chain = out_data[chain_idx]
        for step_idx, step in enumerate(chain.get("steps", [])):
            processed_steps += 1
            out_step = out_chain["steps"][step_idx]
            original_instruction = str(step.get("original_instruction") or step.get("instruction") or "").strip()
            if not original_instruction:
                print(
                    f"  [{processed_steps}/{total_steps}] {chain.get('chain_id')} / {step.get('task_id')} -> skip(empty)",
                    flush=True,
                )
                skipped += 1
                continue

            already_rewritten = (
                not overwrite
                and out_step.get("original_instruction") == original_instruction
                and out_step.get("instruction")
                and out_step.get("instruction") != original_instruction
            )
            if already_rewritten:
                print(
                    f"  [{processed_steps}/{total_steps}] {chain.get('chain_id')} / {step.get('task_id')} -> skip(existing)",
                    flush=True,
                )
                skipped += 1
                continue

            protected_tokens = protected_tokens_for_step(step, original_instruction)
            cache_entry = cache.get(original_instruction)
            if cache_entry:
                rewritten = str(cache_entry.get("rewritten_instruction") or "").strip()
                ok, problems = validate_rewrite(original_instruction, rewritten, protected_tokens)
                if ok:
                    meta = dict(cache_entry.get("instruction_rewrite_meta") or {})
                    meta["cache_hit"] = True
                    print(
                        f"  [{processed_steps}/{total_steps}] {chain.get('chain_id')} / {step.get('task_id')} -> cache",
                        flush=True,
                    )
                else:
                    cache_entry = None

            if not cache_entry:
                print(
                    f"  [{processed_steps}/{total_steps}] {chain.get('chain_id')} / {step.get('task_id')} -> rewriting",
                    flush=True,
                )
                try:
                    rewritten, meta = rewrite_instruction(
                        rewriter=rewriter,
                        original_instruction=original_instruction,
                        protected_tokens=protected_tokens,
                        max_retries=max_retries,
                    )
                    meta["cache_hit"] = False
                    cache[original_instruction] = {
                        "rewritten_instruction": rewritten,
                        "instruction_rewrite_meta": meta,
                    }
                except Exception as exc:
                    failed.append(
                        {
                            "chain_id": chain.get("chain_id"),
                            "task_id": step.get("task_id"),
                            "original_instruction": original_instruction,
                            "error": str(exc),
                        }
                    )
                    print(
                        f"  [{processed_steps}/{total_steps}] {chain.get('chain_id')} / {step.get('task_id')} -> failed: {exc}",
                        flush=True,
                    )
                    if processed_steps % 5 == 0:
                        _write_json(dst_path, out_data)
                    continue
            else:
                rewritten = str(cache_entry.get("rewritten_instruction") or "").strip()
                meta = dict(cache_entry.get("instruction_rewrite_meta") or {})
                meta["cache_hit"] = True

            out_step["original_instruction"] = original_instruction
            out_step["instruction"] = rewritten
            out_step["instruction_rewrite_meta"] = {
                **meta,
                "source_file": src_path.name,
                "chain_id": chain.get("chain_id"),
                "task_id": step.get("task_id"),
                "rewritten_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            changed += 1
            print(
                f"  [{processed_steps}/{total_steps}] {chain.get('chain_id')} / {step.get('task_id')} -> done",
                flush=True,
            )
            if processed_steps % 5 == 0:
                _write_json(dst_path, out_data)

    _write_json(dst_path, out_data)
    return {
        "source": str(src_path),
        "output": str(dst_path),
        "changed": changed,
        "skipped": skipped,
        "failed": failed,
    }


def main():
    parser = argparse.ArgumentParser(description="Rewrite sampled benchmark instructions with validation")
    parser.add_argument("--input-root", default="/Users/masteryth/Documents/webagent", help="Directory containing sampled_<theme>.json")
    parser.add_argument("--output-root", required=True, help="Directory to write rewritten sampled files")
    parser.add_argument("--themes", default="newcomer,daily,career,leisure,crisis")
    parser.add_argument("--backend", choices=["openai_compatible", "hf_local"], default="openai_compatible")
    parser.add_argument("--model", required=True, help="Rewrite model name or local path")
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-chains", type=int, default=None, help="Optional per-file chain cap for pilot runs")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite instructions even if output already exists")
    args = parser.parse_args()

    input_root = Path(args.input_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cache_path = output_root / "rewrite_cache.json"
    manifest_path = output_root / "rewrite_manifest.json"

    cache: Dict[str, Dict[str, Any]] = _read_json_if_valid(cache_path, default={}) or {}
    rewriter = build_rewriter(args.backend, args.model, args.temperature)

    manifest = {
        "backend": args.backend,
        "model": args.model,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "themes": [t.strip() for t in args.themes.split(",") if t.strip()],
        "files": [],
    }

    total_changed = 0
    total_failed = 0
    for theme in manifest["themes"]:
        src_path = input_root / f"sampled_{theme}.json"
        if not src_path.exists():
            raise FileNotFoundError(f"Missing source file: {src_path}")
        dst_path = output_root / src_path.name
        print(f"[rewrite] {src_path} -> {dst_path}")
        result = process_file(
            src_path=src_path,
            dst_path=dst_path,
            cache=cache,
            rewriter=rewriter,
            overwrite=args.overwrite,
            max_retries=args.max_retries,
            max_chains=args.max_chains,
        )
        manifest["files"].append(result)
        total_changed += result["changed"]
        total_failed += len(result["failed"])
        _write_json(cache_path, cache)
        _write_json(manifest_path, manifest)
        print(
            f"[done] {src_path.name}: changed={result['changed']} skipped={result['skipped']} failed={len(result['failed'])}"
        )

    manifest["totals"] = {
        "changed": total_changed,
        "failed": total_failed,
        "cache_entries": len(cache),
    }
    _write_json(cache_path, cache)
    _write_json(manifest_path, manifest)
    print(json.dumps(manifest["totals"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
