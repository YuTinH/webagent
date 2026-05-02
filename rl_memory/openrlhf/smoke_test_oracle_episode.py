#!/usr/bin/env python3
"""Oracle-style smoke test for the OpenRLHF webagent adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.request

from agent_func_webagent import AgentInstance
from chain_runner_dynamic import patch_trace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="OpenRLHF jsonl dataset path")
    parser.add_argument("--index", type=int, default=0, help="Episode index in jsonl file")
    parser.add_argument("--max-tasks", type=int, default=2, help="How many tasks to drive with oracle actions")
    return parser.parse_args()


def ensure_server_up() -> None:
    try:
        with urllib.request.urlopen("http://localhost:8014/", timeout=3) as response:
            if response.status < 200 or response.status >= 500:
                raise RuntimeError(f"unexpected_status:{response.status}")
    except Exception as exc:
        raise SystemExit(
            "Benchmark server is not reachable on http://localhost:8014/. "
            "Start the server before running the oracle smoke test."
        ) from exc


def load_episode(dataset_path: Path, index: int) -> dict:
    with dataset_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)
    raise SystemExit(f"Dataset index {index} out of range for {dataset_path}")


def oracle_actions_for_task(task_step: dict) -> list[str]:
    trace = patch_trace(
        task_step["task_id"],
        task_step["instruction"],
        task_step.get("success_criteria", []),
        step_payload=task_step,
    )
    actions = []
    if not trace:
        return ["DONE()"]
    for step in trace.get("steps", []):
        act = step.get("act")
        if act == "open":
            continue
        if act == "click":
            actions.append(f"CLICK({step['selector']})")
        elif act == "select":
            actions.append(f"SELECT({step['selector']}, {step['value']})")
        elif act == "type":
            actions.append(f"TYPE({step['selector']}, {step['value']})")
    actions.append("DONE()")
    return actions


def main() -> None:
    args = parse_args()
    ensure_server_up()
    item = load_episode(Path(args.dataset), args.index)
    agent = AgentInstance(headless=True, max_steps_per_task=20, repeat_fail_threshold=3, stop_on_first_fail_step=True)
    state = agent._reset_impl({"episode": item["episode"]})
    print("RESET_OK")
    print(state["observation"][:500])

    tasks_driven = 0
    total_reward = 0.0
    done = False
    while not done and tasks_driven < args.max_tasks:
        current = agent.current_task
        assert current is not None
        actions = oracle_actions_for_task(current)
        print(f"RUNNING_TASK={current['task_id']} ACTIONS={actions}")
        for action in actions:
            reply = agent._step_impl({"action_text": action})
            reward = float(reply["rewards"])
            total_reward += reward
            done = bool(reply["done"])
            print(f"ACTION={action} REWARD={reward} DONE={done}")
            if action == "DONE()":
                logs = reply.get("extra_logs", {})
                print("TASK_RESULT", logs)
            if done:
                break
        tasks_driven += 1

    print("ORACLE_SMOKE_FINISHED", {"tasks_driven": tasks_driven, "done": done, "total_reward": total_reward})


if __name__ == "__main__":
    main()
