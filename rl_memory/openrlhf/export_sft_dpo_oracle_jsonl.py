#!/usr/bin/env python3
"""Build SFT and DPO jsonl datasets from sampled task-flow oracle traces.

The exporter uses chain-level `oracle_trace_override` entries from `sampled_*.json`
when available. These traces are parameterized to the sampled instruction and are
therefore safer than generic task-level `oracle_trace.json` files.

SFT examples:
- prompt: current task instruction + current URL hint + prior action history
- response: exactly one next browser action

DPO examples:
- prompt: same as SFT
- chosen: oracle action
- rejected: synthetic negative action patterned after observed failure modes
  (multi-action output, premature DONE, repeated action, action-type mismatch,
   external navigation)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO_ROOT = ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-root",
        default=str(DEFAULT_SCENARIO_ROOT),
        help="Directory containing sampled_<theme>.json files",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        help="Directory to write sft/ and dpo/ jsonl files",
    )
    parser.add_argument(
        "--themes",
        default="newcomer,daily,career,leisure,crisis",
        help="Comma-separated themes to include",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for chain-level train/val/test splits",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument(
        "--max-chains-per-theme",
        type=int,
        default=0,
        help="Optional cap per theme for quick experiments (0 = all)",
    )
    return parser.parse_args()


def _quote(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _sanitize_inline(text: Any) -> str:
    raw = str(text or "").replace("\n", " ").strip()
    return " ".join(raw.split())


def serialize_action(step: Dict[str, Any]) -> Optional[str]:
    act = str(step.get("act", "")).strip().lower()
    selector = _sanitize_inline(step.get("selector"))
    value = _sanitize_inline(step.get("value"))
    url = _sanitize_inline(step.get("url"))

    if act == "open":
        return f"GOTO({_quote(url)})" if url else None
    if act == "click":
        return f"CLICK({selector})" if selector else None
    if act == "type":
        return f"TYPE({selector}, {_quote(value)})" if selector else None
    if act == "select":
        return f"SELECT({selector}, {_quote(value)})" if selector else None
    if act == "check":
        return f"CHECK({selector})" if selector else None
    if act == "uncheck":
        return f"UNCHECK({selector})" if selector else None
    if act == "upload":
        return f"UPLOAD({selector}, {_quote(value)})" if selector and value else None
    if act == "wait":
        return "WAIT()"
    if act == "done":
        return "DONE()"
    return None


def build_prompt(
    *,
    theme: str,
    chain_id: str,
    task_id: str,
    instruction: str,
    success_criteria: Sequence[str],
    current_url: str,
    history: Sequence[str],
) -> str:
    criteria_block = "\n".join(f"- {c}" for c in success_criteria[:4]) if success_criteria else "- Not provided"
    history_block = "\n".join(f"{idx + 1}. {action}" for idx, action in enumerate(history[-8:])) if history else "None"
    url_hint = current_url or "unknown"
    return (
        "You are a browser agent in the webagent benchmark.\n"
        "Return exactly one next action and nothing else.\n"
        "Allowed formats:\n"
        "CLICK(selector)\n"
        "TYPE(selector, \"text\")\n"
        "SELECT(selector, \"value\")\n"
        "CHECK(selector)\n"
        "UNCHECK(selector)\n"
        "GOTO(\"url\")\n"
        "UPLOAD(selector, \"filepath\")\n"
        "WAIT()\n"
        "DONE()\n\n"
        f"Theme: {theme}\n"
        f"Chain: {chain_id}\n"
        f"Task: {task_id}\n"
        f"Instruction: {instruction}\n"
        f"Current URL hint: {url_hint}\n"
        "Success criteria:\n"
        f"{criteria_block}\n\n"
        "Previous actions:\n"
        f"{history_block}\n\n"
        "Return exactly one next action. Do not emit multiple actions."
    )


def mutate_negative(
    *,
    chosen_action: str,
    current_step: Dict[str, Any],
    history: Sequence[str],
    next_action: Optional[str],
    sample_key: str,
) -> Tuple[str, str]:
    act = str(current_step.get("act", "")).strip().lower()
    selector = _sanitize_inline(current_step.get("selector"))
    candidates: List[Tuple[str, str]] = []

    if history:
        candidates.append(("repeat_action_loop", history[-1]))

    if chosen_action != "DONE()":
        candidates.append(("premature_done", "DONE()"))

    if next_action:
        candidates.append(("multi_action_output", f"{chosen_action} {next_action}"))
    else:
        candidates.append(("multi_action_output", f"{chosen_action} WAIT()"))

    if act == "click" and selector:
        candidates.append(("action_type_error", f"SELECT({selector}, {_quote('Information')})"))
    elif act == "type" and selector:
        candidates.append(("action_type_error", f"CLICK({selector})"))
    elif act == "select" and selector:
        candidates.append(("action_type_error", f"CLICK({selector})"))
    elif act == "open":
        candidates.append(("external_navigation", 'GOTO("https://www.amazon.com/s?k=mechanical+keyboard")'))
    elif act == "wait":
        candidates.append(("premature_done", "DONE()"))

    if not candidates:
        candidates.append(("premature_done", "DONE()"))

    idx = int(hashlib.md5(sample_key.encode("utf-8")).hexdigest(), 16) % len(candidates)
    return candidates[idx]


def split_items(items: Sequence[Dict[str, Any]], train_ratio: float, val_ratio: float, rng: random.Random) -> Dict[str, List[Dict[str, Any]]]:
    buf = list(items)
    rng.shuffle(buf)
    n = len(buf)
    n_train = int(round(n * train_ratio))
    n_val = int(round(n * val_ratio))
    if n_train + n_val > n:
        n_val = max(0, n - n_train)
    n_test = n - n_train - n_val
    return {
        "train": buf[:n_train],
        "val": buf[n_train:n_train + n_val],
        "test": buf[n_train + n_val:n_train + n_val + n_test],
    }


def load_scenarios(scenario_root: Path, themes: Sequence[str], max_chains_per_theme: int) -> Dict[str, List[Dict[str, Any]]]:
    data: Dict[str, List[Dict[str, Any]]] = {}
    for theme in themes:
        path = scenario_root / f"sampled_{theme}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        chains = json.loads(path.read_text(encoding="utf-8"))
        if max_chains_per_theme > 0:
            chains = chains[:max_chains_per_theme]
        data[theme] = chains
    return data


def iter_records(theme: str, chain: Dict[str, Any]) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any]]]:
    chain_id = str(chain.get("chain_id", ""))
    for task_pos, step in enumerate(chain.get("steps") or []):
        trace = step.get("oracle_trace_override") or []
        if not trace:
            continue

        serialized = [serialize_action(item) for item in trace]
        filtered: List[Tuple[Dict[str, Any], str]] = [
            (item, action) for item, action in zip(trace, serialized) if action
        ]
        if not filtered:
            continue

        current_url = ""
        history: List[str] = []
        start_index = 0
        if filtered and str(filtered[0][0].get("act", "")).lower() == "open":
            current_url = _sanitize_inline(filtered[0][0].get("url"))
            start_index = 1

        task_id = str(step.get("task_id", ""))
        instruction = str(step.get("instruction", "")).strip()
        success_criteria = [str(x) for x in (step.get("success_criteria") or [])]

        for local_idx in range(start_index, len(filtered)):
            raw_step, chosen_action = filtered[local_idx]
            next_action = filtered[local_idx + 1][1] if local_idx + 1 < len(filtered) else None
            prompt = build_prompt(
                theme=theme,
                chain_id=chain_id,
                task_id=task_id,
                instruction=instruction,
                success_criteria=success_criteria,
                current_url=current_url,
                history=history,
            )
            sample_key = f"{chain_id}|{task_id}|{task_pos}|{local_idx}|{chosen_action}"
            negative_kind, rejected = mutate_negative(
                chosen_action=chosen_action,
                current_step=raw_step,
                history=history,
                next_action=next_action,
                sample_key=sample_key,
            )
            meta = {
                "id": f"{chain_id}:{task_id}:{task_pos}:{local_idx}",
                "theme": theme,
                "chain_id": chain_id,
                "task_id": task_id,
                "task_position": task_pos,
                "oracle_step_index": local_idx,
                "negative_kind": negative_kind,
            }
            yield (
                {**meta, "prompt": prompt, "response": chosen_action},
                {**meta, "prompt": prompt, "chosen": chosen_action, "rejected": rejected},
            )

            history.append(chosen_action)
            if chosen_action.startswith("GOTO("):
                current_url = chosen_action[len("GOTO("):-1].strip().strip('"').strip("'")

        if history:
            done_prompt = build_prompt(
                theme=theme,
                chain_id=chain_id,
                task_id=task_id,
                instruction=instruction,
                success_criteria=success_criteria,
                current_url=current_url,
                history=history,
            )
            done_meta = {
                "id": f"{chain_id}:{task_id}:{task_pos}:done",
                "theme": theme,
                "chain_id": chain_id,
                "task_id": task_id,
                "task_position": task_pos,
                "oracle_step_index": len(filtered),
                "negative_kind": "repeat_action_loop" if history else "premature_done",
            }
            rejected_done = history[-1] if history else "WAIT()"
            yield (
                {**done_meta, "prompt": done_prompt, "response": "DONE()"},
                {**done_meta, "prompt": done_prompt, "chosen": "DONE()", "rejected": rejected_done},
            )


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    scenario_root = Path(args.scenario_root)
    output_root = Path(args.output_root)
    if abs((args.train_ratio + args.val_ratio + args.test_ratio) - 1.0) > 1e-6:
        raise SystemExit("train/val/test ratios must sum to 1.0")

    themes = [part.strip() for part in args.themes.split(",") if part.strip()]
    rng = random.Random(args.seed)
    scenarios = load_scenarios(scenario_root, themes, args.max_chains_per_theme)

    split_chains: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {"train": [], "val": [], "test": []}
    chain_counts: Dict[str, Dict[str, int]] = {}
    for theme, chains in scenarios.items():
        themed = split_items(chains, args.train_ratio, args.val_ratio, rng)
        chain_counts[theme] = {name: len(items) for name, items in themed.items()}
        for split_name, items in themed.items():
            split_chains[split_name].extend((theme, chain) for chain in items)

    sft_rows: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}
    dpo_rows: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}
    negative_counts: Counter[str] = Counter()

    for split_name, themed_chains in split_chains.items():
        for theme, chain in themed_chains:
            for sft_row, dpo_row in iter_records(theme, chain):
                sft_rows[split_name].append(sft_row)
                dpo_rows[split_name].append(dpo_row)
                negative_counts[dpo_row["negative_kind"]] += 1

    for split_name in ("train", "val", "test"):
        write_jsonl(output_root / "sft" / f"{split_name}.jsonl", sft_rows[split_name])
        write_jsonl(output_root / "dpo" / f"{split_name}.jsonl", dpo_rows[split_name])

    summary = {
        "scenario_root": str(scenario_root),
        "themes": themes,
        "seed": args.seed,
        "chain_counts": chain_counts,
        "sft_counts": {k: len(v) for k, v in sft_rows.items()},
        "dpo_counts": {k: len(v) for k, v in dpo_rows.items()},
        "negative_kinds": dict(sorted(negative_counts.items())),
    }
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
