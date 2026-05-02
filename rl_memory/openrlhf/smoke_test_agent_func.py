#!/usr/bin/env python3
"""Local smoke test for agent_func_webagent without full OpenRLHF training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.request

from agent_func_webagent import AgentInstance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="OpenRLHF jsonl dataset path")
    parser.add_argument("--index", type=int, default=0, help="Episode index in jsonl file")
    parser.add_argument("--max-actions", type=int, default=20, help="Maximum number of actions to simulate")
    return parser.parse_args()


def load_episode(dataset_path: Path, index: int) -> dict:
    with dataset_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)
    raise SystemExit(f"Dataset index {index} out of range for {dataset_path}")


def ensure_server_up() -> None:
    try:
        with urllib.request.urlopen("http://localhost:8014/", timeout=3) as response:
            if response.status < 200 or response.status >= 500:
                raise RuntimeError(f"unexpected_status:{response.status}")
    except Exception as exc:
        raise SystemExit(
            "Benchmark server is not reachable on http://localhost:8014/. "
            "Start the server before running the smoke test."
        ) from exc


def main() -> None:
    args = parse_args()
    ensure_server_up()
    item = load_episode(Path(args.dataset), args.index)
    agent = AgentInstance(headless=True, max_steps_per_task=5, repeat_fail_threshold=2, stop_on_first_fail_step=True)
    state = agent._reset_impl({"episode": item["episode"]})
    print("RESET_OK")
    print(state["observation"][:400])

    done = False
    step = 0
    while not done and step < args.max_actions:
        # This is an environment smoke test, not a policy-quality test.
        reply = agent._step_impl({"action_text": "DONE()"})
        step += 1
        done = bool(reply["done"])
        print(f"STEP={step} DONE={done} REWARD={float(reply['rewards'])}")
        feedback = reply.get("environment_feedback", "")
        print(feedback[:240])

    print("SMOKE_FINISHED", {"steps": step, "done": done})


if __name__ == "__main__":
    main()
