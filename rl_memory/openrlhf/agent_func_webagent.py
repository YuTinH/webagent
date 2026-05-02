"""OpenRLHF multi-turn agent function for the webagent benchmark."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import sqlite3
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import torch
except Exception:
    class _FakeTorch:
        float32 = "float32"

        @staticmethod
        def tensor(value, dtype=None):
            return value

    torch = _FakeTorch()

try:
    from openrlhf.utils.agent import AgentInstanceBase, MultiTurnAgentExecutor
    OPENRLHF_AVAILABLE = True
except Exception:
    OPENRLHF_AVAILABLE = False

    class AgentInstanceBase:  # pragma: no cover - local fallback for smoke testing
        pass

    class MultiTurnAgentExecutor:  # pragma: no cover - local fallback for smoke testing
        def __init__(self, instance_cls):
            self.instance_cls = instance_cls


# Resolve the benchmark root from this file so the adapter works after moving
# the repo or unpacking the environment on another machine.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.assertions_dsl import AssertionDSL
from agent.browser_env import BrowserEnv
from chain_runner_dynamic import inject_state, patch_spec, patch_trace
from llm_runner import _parse_scoring_checkpoints, normalize_action, validate_action_format
from rl_memory.memory_baselines.reflexion.reflexion_memory import ReflexionMemoryStore
from rl_memory.memory_baselines.reflexion.prompt_builder import augment_instruction
from rl_memory.openrlhf.runtime_manager import RuntimeSandbox
from runtime_paths import db_path, server_base_url, state_path, tasks_dir


def _repo_chdir() -> None:
    os.chdir(REPO_ROOT)


def _memory_method() -> str:
    return (os.environ.get("AGENT_MEMORY_METHOD") or "").strip().lower()


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _reward_mode() -> str:
    return (os.environ.get("OPENRLHF_REWARD_MODE") or "legacy").strip().lower()


def _clip_reward(value: float) -> float:
    low = _float_env("OPENRLHF_REWARD_MIN", -1.0)
    high = _float_env("OPENRLHF_REWARD_MAX", 1.0)
    if high < low:
        low, high = high, low
    return max(low, min(high, value))


def _progress_from_eval(eval_result: dict[str, Any]) -> tuple[float, Any]:
    checkpoint_score_percent = eval_result.get("checkpoint_score_percent")
    if isinstance(checkpoint_score_percent, (int, float)):
        progress = max(0.0, min(1.0, float(checkpoint_score_percent) / 100.0))
    elif eval_result["success"]:
        progress = 1.0
    else:
        progress = 0.0
    return progress, checkpoint_score_percent


def _episode_index_path() -> Path:
    env_path = os.environ.get("OPENRLHF_EPISODE_INDEX")
    if env_path:
        return Path(env_path)
    return REPO_ROOT / "rl_memory" / "openrlhf" / "data" / "clean_pool_v1_1000_200_300" / "episode_index.json"


@lru_cache(maxsize=1)
def _episode_index() -> dict[str, dict[str, Any]]:
    index_path = _episode_index_path()
    if index_path.exists():
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            return {str(k): v for k, v in payload.items()}
        except Exception:
            pass

    # Fallback: build the index from the exported jsonl files when the sidecar
    # file is absent. This keeps training robust across machines.
    data_dir = index_path.parent
    result: dict[str, dict[str, Any]] = {}
    for split_name in ("train", "val", "test"):
        split_path = data_dir / f"{split_name}.jsonl"
        if not split_path.exists():
            continue
        with split_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                episode = row.get("episode")
                row_id = row.get("id")
                label = row.get("label")
                if isinstance(episode, dict):
                    if row_id:
                        result[str(row_id)] = episode
                    if label:
                        result[str(label)] = episode
    return result


def _resolve_episode(states: dict[str, Any]) -> dict[str, Any]:
    if "episode" in states:
        episode = states["episode"]
        if isinstance(episode, str):
            episode = json.loads(episode)
        if isinstance(episode, dict):
            return episode

    # Some OpenRLHF code paths flatten or strip nested fields and only preserve
    # the top-level sample id. Recover the full episode from a local index.
    for key in ("id", "sample_id", "label"):
        row_id = states.get(key)
        if row_id:
            episode = _episode_index().get(str(row_id))
            if episode is not None:
                return episode

    observation = states.get("observation")
    if isinstance(observation, str):
        for line in observation.splitlines():
            if line.startswith("Chain: "):
                chain_id = line.split("Chain: ", 1)[1].strip()
                if chain_id:
                    episode = _episode_index().get(chain_id)
                    if episode is not None:
                        return episode

    if "steps" in states and isinstance(states["steps"], list):
        return states

    raise KeyError(
        f"Unable to resolve episode from reset state. Available keys: {sorted(states.keys())}"
    )


def _reflection_store():
    if _memory_method() != "reflexion":
        return None
    path = os.environ.get(
        "AGENT_REFLEXION_STORE",
        "/Users/masteryth/Documents/webagent/rl_memory/memory_baselines/reflexion/runs/default_reflections.json",
    )
    return ReflexionMemoryStore(path)


def _reflection_top_k() -> int:
    raw = os.environ.get("AGENT_REFLEXION_TOP_K", "3")
    try:
        return max(1, int(raw))
    except Exception:
        return 3


def _build_reflection_text(task_id: str, goal: str, success: bool, failure_note: str) -> str:
    if success:
        return (
            f"For {task_id}, stop once the target state is achieved and avoid extra actions after success."
        )
    return (
        f"For {task_id}, previous execution failed while trying to achieve: {goal}. "
        f"Use this note next time: {failure_note}"
    )


def _read_memory(conn: sqlite3.Connection) -> dict[str, Any]:
    memory: dict[str, Any] = {}
    try:
        cur = conn.execute("SELECT key, value FROM memory_kv")
        for row in cur.fetchall():
            raw = row["value"]
            try:
                memory[row["key"]] = json.loads(raw)
            except Exception:
                memory[row["key"]] = raw
    except Exception:
        pass
    return memory


def _env_api(_: str, path: str):
    env_state_path = state_path()
    if not env_state_path.exists():
        return None
    try:
        current = json.loads(env_state_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except Exception:
                return None
        else:
            return None
        if current is None:
            return None
    return current


def _evaluate_current_task(task_id: str, env: BrowserEnv) -> dict[str, Any]:
    spec_path = tasks_dir() / task_id / "task_spec.json"
    spec = json.loads(spec_path.read_text())
    criteria = spec.get("success_criteria", [])

    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        memory = _read_memory(conn)
        dsl = AssertionDSL(env.page, memory, _env_api)
        criteria_total = len(criteria)
        criteria_passed = 0
        criteria_failed = []
        criteria_all_passed = True

        for crit in criteria:
            try:
                res = bool(dsl.evaluate(crit))
            except Exception:
                res = False
            if res:
                criteria_passed += 1
            else:
                criteria_all_passed = False
                criteria_failed.append(crit)

        checkpoints, checkpoint_mode = _parse_scoring_checkpoints(spec, criteria)
        activation_map: Dict[str, bool] = {}
        final_pass_map: Dict[str, bool] = {}
        checkpoint_results = []
        checkpoint_required_failed = []
        checkpoint_required_passed = 0

        active_checkpoints: List[Dict[str, Any]] = []
        for cp in checkpoints:
            cp_id = cp["id"]
            when_expr = str(cp.get("when", "")).strip()
            if not when_expr:
                activation_map[cp_id] = True
                active_checkpoints.append(cp)
                continue
            try:
                is_active = bool(dsl.evaluate(when_expr))
            except Exception:
                is_active = False
            activation_map[cp_id] = is_active
            if is_active:
                active_checkpoints.append(cp)

        active_weight_sum = sum(max(float(cp.get("weight", 0.0)), 0.0) for cp in active_checkpoints)
        if active_checkpoints:
            if active_weight_sum <= 0:
                for cp in active_checkpoints:
                    cp["weight_norm_active"] = 1.0 / len(active_checkpoints)
            else:
                for cp in active_checkpoints:
                    cp["weight_norm_active"] = max(float(cp.get("weight", 0.0)), 0.0) / active_weight_sum

        checkpoint_weight_earned = 0.0
        for cp in active_checkpoints:
            cp_id = cp["id"]
            assertion = cp["assertion"]
            depends_on = cp.get("depends_on", [])
            deps_ok = all(final_pass_map.get(dep_id, False) for dep_id in depends_on)
            try:
                raw_pass = bool(dsl.evaluate(assertion))
            except Exception:
                raw_pass = False
            cp_pass = raw_pass and deps_ok
            final_pass_map[cp_id] = cp_pass
            earned = float(cp.get("weight_norm_active", 0.0)) if cp_pass else 0.0
            checkpoint_weight_earned += earned
            if cp.get("required", True):
                if cp_pass:
                    checkpoint_required_passed += 1
                else:
                    checkpoint_required_failed.append(cp_id)
            checkpoint_results.append(
                {
                    "id": cp_id,
                    "pass": cp_pass,
                    "required": bool(cp.get("required", True)),
                    "score": earned * 100.0,
                }
            )

        checkpoint_score_percent = checkpoint_weight_earned * 100.0 if active_checkpoints else None
        checkpoint_required_ok = not checkpoint_required_failed
        if active_checkpoints:
            passed = checkpoint_required_ok and (criteria_all_passed if criteria_total else True)
        else:
            passed = criteria_all_passed if criteria_total else True

        return {
            "success": bool(passed),
            "criteria_total": criteria_total,
            "criteria_passed": criteria_passed,
            "criteria_failed": criteria_failed,
            "checkpoint_mode": checkpoint_mode,
            "checkpoint_total": len(active_checkpoints),
            "checkpoint_required_passed": checkpoint_required_passed,
            "checkpoint_required_failed": checkpoint_required_failed,
            "checkpoint_score_percent": checkpoint_score_percent,
            "checkpoint_results": checkpoint_results,
        }
    finally:
        conn.close()


class AgentInstance(AgentInstanceBase):
    def __init__(self, *args, **kwargs):
        _repo_chdir()
        self.headless = bool(kwargs.get("headless", True))
        self.max_steps_per_task = int(kwargs.get("max_steps_per_task", 25))
        self.repeat_fail_threshold = int(kwargs.get("repeat_fail_threshold", 3))
        self.stop_on_first_fail_step = bool(kwargs.get("stop_on_first_fail_step", True))
        self.env: BrowserEnv | None = None
        self.episode: dict[str, Any] | None = None
        self.task_idx = 0
        self.task_step_idx = 0
        self.last_action = ""
        self.repeat_count = 0
        self.current_task_best_progress = 0.0
        self.flow_task_reports: list[dict[str, Any]] = []
        self.current_task: dict[str, Any] | None = None
        self.reflection_store = _reflection_store()
        self.retrieved_reflections: list[dict[str, Any]] = []
        self.use_isolated_runtime = str(
            os.environ.get("OPENRLHF_USE_ISOLATED_RUNTIME", "1")
        ).strip().lower() not in {"0", "false", "no"}
        self.runtime: RuntimeSandbox | None = None
        # Playwright Sync API objects must only be touched from one thread.
        self._sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="openrlhf-browser")

    async def _run_sync(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._sync_executor,
            lambda: fn(*args, **kwargs),
        )

    def _ensure_runtime(self) -> None:
        if not self.use_isolated_runtime:
            return
        if self.runtime is None:
            self.runtime = RuntimeSandbox(repo_root=REPO_ROOT)
            self.runtime.start_server()
        self.runtime.activate_process_env()

    def _reset_impl(self, states: dict, **kwargs):
        _repo_chdir()
        self._ensure_runtime()
        if self.env is not None:
            self.env.close()
            self.env = None
        try:
            self.episode = _resolve_episode(states)
            self.task_idx = 0
            self.task_step_idx = 0
            self.last_action = ""
            self.repeat_count = 0
            self.current_task_best_progress = 0.0
            self.flow_task_reports = []
            self.retrieved_reflections = []
            subprocess.run(
                [sys.executable, "init_db.py"],
                check=True,
                stdout=subprocess.DEVNULL,
                env=(self.runtime.env() if self.runtime is not None else None),
                cwd=str(REPO_ROOT),
            )
            env_state_path = state_path()
            try:
                env_state_path.unlink(missing_ok=True)
            except TypeError:
                if env_state_path.exists():
                    env_state_path.unlink()
            inject_state(self.episode.get("initial_state"))
            self.env = BrowserEnv(
                headless=self.headless,
                base_url=(self.runtime.base_url if self.runtime is not None else server_base_url()),
            )
            observation = self._prepare_current_task()
            return {"observation": observation}
        except Exception:
            if self.env is not None:
                self.env.close()
                self.env = None
            raise

    async def reset(self, states: dict, **kwargs):
        return await self._run_sync(self._reset_impl, states, **kwargs)

    def _prepare_current_task(self) -> str:
        assert self.episode is not None
        assert self.env is not None
        self.current_task = self.episode["steps"][self.task_idx]
        self.task_step_idx = 0
        self.last_action = ""
        self.repeat_count = 0
        self.current_task_best_progress = 0.0
        task_id = self.current_task["task_id"]
        trace = patch_trace(
            task_id,
            self.current_task["instruction"],
            self.current_task["success_criteria"],
            step_payload=self.current_task,
        )
        scoring_checkpoints = self.current_task.get("scoring_checkpoints") or self.current_task.get("checkpoints")
        patch_spec(
            task_id,
            self.current_task["instruction"],
            self.current_task["success_criteria"],
            scoring_checkpoints,
        )
        start_url = f"{server_base_url()}/shop.local/index.html"
        if trace and trace.get("steps") and trace["steps"][0].get("act") == "open":
            start_url = trace["steps"][0]["url"]
        page_obs = self.env.reset(start_url)
        return self._format_observation(page_obs)

    def _format_observation(self, page_obs: str) -> str:
        assert self.current_task is not None
        total = len(self.episode["steps"])
        instruction = self.current_task["instruction"]
        if self.reflection_store is not None:
            try:
                self.retrieved_reflections = self.reflection_store.retrieve(
                    query=f"{self.current_task['task_id']} {instruction}",
                    top_k=_reflection_top_k(),
                    task_id=self.current_task["task_id"],
                )
                instruction = augment_instruction(instruction, self.retrieved_reflections)
            except Exception:
                self.retrieved_reflections = []
        return (
            f"Task {self.task_idx + 1}/{total} [{self.current_task['task_id']}]\n"
            f"Instruction: {instruction}\n"
            f"{page_obs}\n"
            "Allowed actions: CLICK(...), TYPE(...), SELECT(...), CHECK(...), UNCHECK(...), "
            "UPLOAD(...), GOTO(...), WAIT(), DONE().\n"
            "Return exactly one browser action."
        )

    @staticmethod
    def _numeric_extra_logs(**kwargs) -> Dict[str, float]:
        logs: Dict[str, float] = {
            "task_step_idx": 0.0,
            "invalid_action": 0.0,
            "task_success": 0.0,
            "flow_success": 0.0,
            "checkpoint_score_percent": 0.0,
            "progress": 0.0,
        }
        for key, value in kwargs.items():
            if value is None:
                continue
            if isinstance(value, bool):
                logs[key] = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                logs[key] = float(value)
        return logs

    def _step_impl(self, states: dict, **kwargs) -> Dict[str, Any]:
        assert self.env is not None
        assert self.current_task is not None
        raw_action_text = str(states["action_text"])
        action_text = normalize_action(raw_action_text)
        done = False
        task_done = False
        invalid_action_penalty = 0.0
        invalid_action_penalty_value = _float_env("OPENRLHF_INVALID_ACTION_PENALTY", -1.0)
        repeat_action_penalty_value = _float_env("OPENRLHF_REPEAT_ACTION_PENALTY", -0.75)
        step_error_penalty_value = _float_env("OPENRLHF_STEP_ERROR_PENALTY", -0.5)
        premature_done_penalty_value = _float_env("OPENRLHF_PREMATURE_DONE_PENALTY", -0.25)
        success_bonus_value = _float_env("OPENRLHF_SUCCESS_BONUS", 1.0)
        flow_success_bonus_value = _float_env("OPENRLHF_FLOW_SUCCESS_BONUS", 1.0)
        progress_weight = _float_env("OPENRLHF_PROGRESS_WEIGHT", 1.0)
        selector_valid_bonus_value = _float_env("OPENRLHF_SELECTOR_VALID_BONUS", 0.0)
        stop_on_invalid_action = _bool_env("OPENRLHF_STOP_ON_INVALID_ACTION", True)
        reward_mode = _reward_mode()
        recognized_action = bool(
            re.match(r"^(CLICK|TYPE|SELECT|CHECK|UNCHECK|UPLOAD|GOTO|WAIT|DONE)\(.*\)$", action_text)
        )
        action_format_error = validate_action_format(action_text)

        if (not recognized_action) or action_format_error:
            action_text = "WAIT()"
            invalid_action_penalty = invalid_action_penalty_value
            if stop_on_invalid_action:
                task_done = True
                status = action_format_error or "invalid_action_format"
                keep_going = True

        if not task_done:
            if action_text == self.last_action:
                self.repeat_count += 1
            else:
                self.repeat_count = 1
                self.last_action = action_text

            if self.repeat_count >= max(2, self.repeat_fail_threshold):
                task_done = True
                invalid_action_penalty = min(invalid_action_penalty, repeat_action_penalty_value)
                status = "repeat_action_threshold"
                keep_going = True
            else:
                keep_going, status = self.env.step(action_text)
                self.task_step_idx += 1
                if isinstance(status, str) and status.startswith("Error:"):
                    invalid_action_penalty = min(invalid_action_penalty, step_error_penalty_value)
                    if self.stop_on_first_fail_step:
                        task_done = True
                if not keep_going:
                    task_done = True
                if self.task_step_idx >= self.max_steps_per_task:
                    task_done = True

        if not task_done:
            page_obs = self.env.get_observation()
            return {
                "rewards": torch.tensor(0.0),
                "scores": torch.tensor(0.0),
                "environment_feedback": (
                    "\n\nHuman: Observation update:\n"
                    + self._format_observation(page_obs)
                    + "\n</s>\n\nAssistant: "
                ),
                "done": False,
                "sampling_params": states.get("sampling_params", None),
                "extra_logs": self._numeric_extra_logs(
                    task_step_idx=self.task_step_idx,
                    invalid_action=(("Error:" in status) if isinstance(status, str) else False) or (not recognized_action),
                ),
            }

        eval_result = _evaluate_current_task(self.current_task["task_id"], self.env)
        completed_task_id = self.current_task["task_id"]
        progress, checkpoint_score_percent = _progress_from_eval(eval_result)
        self.current_task_best_progress = max(self.current_task_best_progress, progress)

        if reward_mode == "wfg_r1_module":
            selector_valid_bonus = (
                selector_valid_bonus_value
                if invalid_action_penalty >= 0.0 and (progress > 0.0 or eval_result["success"])
                else 0.0
            )
            reward_value = (
                progress_weight * progress
                + (success_bonus_value if eval_result["success"] else 0.0)
                + selector_valid_bonus
                + invalid_action_penalty
            )
            if action_text.startswith("DONE") and not eval_result["success"]:
                reward_value += premature_done_penalty_value
            reward_value = _clip_reward(reward_value)
        else:
            reward_value = progress + (success_bonus_value if eval_result["success"] else 0.0) + invalid_action_penalty
            if action_text.startswith("DONE") and not eval_result["success"]:
                reward_value += premature_done_penalty_value
        self.flow_task_reports.append(
            {
                "task_id": self.current_task["task_id"],
                "success": bool(eval_result["success"]),
                "progress": progress,
                "checkpoint_score_percent": checkpoint_score_percent,
            }
        )
        if self.reflection_store is not None:
            try:
                self.reflection_store.append(
                    {
                        "task_id": completed_task_id,
                        "goal": self.current_task["instruction"],
                        "success": bool(eval_result["success"]),
                        "failure_category": "criteria_or_checkpoint_failed" if not eval_result["success"] else "success",
                        "reflection": _build_reflection_text(
                            task_id=completed_task_id,
                            goal=self.current_task["instruction"],
                            success=bool(eval_result["success"]),
                            failure_note="Focus on satisfying the exact checkpointed state before finishing.",
                        ),
                    }
                )
            except Exception:
                pass

        self.task_idx += 1
        if self.task_idx >= len(self.episode["steps"]):
            done = True
            flow_success = all(item["success"] for item in self.flow_task_reports)
            if flow_success:
                reward_value += flow_success_bonus_value
            if reward_mode == "wfg_r1_module":
                reward_value = _clip_reward(reward_value)
            if self.env is not None:
                self.env.close()
                self.env = None
            return {
                "rewards": torch.tensor(reward_value, dtype=torch.float32),
                "scores": torch.tensor(reward_value, dtype=torch.float32),
                "environment_feedback": "\n\nHuman: Episode finished.\n</s>",
                "done": True,
                "sampling_params": states.get("sampling_params", None),
                "extra_logs": self._numeric_extra_logs(
                    task_success=bool(eval_result["success"]),
                    flow_success=flow_success,
                    checkpoint_score_percent=checkpoint_score_percent,
                    progress=progress,
                ),
            }

        next_obs = self._prepare_current_task()
        feedback_prefix = "completed successfully" if eval_result["success"] else "ended without success"
        return {
            "rewards": torch.tensor(reward_value, dtype=torch.float32),
            "scores": torch.tensor(reward_value, dtype=torch.float32),
            "environment_feedback": (
                f"\n\nHuman: Previous task {completed_task_id} {feedback_prefix}.\n"
                f"{next_obs}\n</s>\n\nAssistant: "
            ),
            "done": False,
            "sampling_params": states.get("sampling_params", None),
            "extra_logs": self._numeric_extra_logs(
                task_success=bool(eval_result["success"]),
                checkpoint_score_percent=checkpoint_score_percent,
                progress=progress,
            ),
        }

    async def step(self, states: dict, **kwargs) -> Dict[str, Any]:
        return await self._run_sync(self._step_impl, states, **kwargs)


class AgentExecutor(MultiTurnAgentExecutor):
    def __init__(self):
        super().__init__(AgentInstance)
