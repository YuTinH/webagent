# WebAgent Workflow Benchmark

WebAgent Workflow Benchmark 是一个本地 Web Agent 评测环境，用来测试模型在多站点、长程依赖、状态写入和模块化工作流中的规划与执行能力。当前仓库主线是 `workflow_split_batch_v20`，不是早期的 `sampled_{theme}.json` 动态任务流版本。

## Current Snapshot

- Dataset: `tasks/generated_workflow_split_batches/workflow_split_batch_v20`
- Size: 5,040 workflow goals
- Split: 4,760 train / 140 dev / 140 test
- Structural validity: 5,040 / 5,040 solvable, 0 invalid oracle paths
- Average workflow path length: about 5 modules
- Execution model: workflow-level module planning + atomic browser action execution

See [docs/workflow_dataset_validity_report_v20.md](docs/workflow_dataset_validity_report_v20.md) for the current validity audit.

## Repository Layout

- `agent/`: browser environment, executor, LLM client, assertion DSL.
- `sites/`: local HTML sites such as shop, bank, gov, health, work, travel, school, and security.
- `tasks/`: atomic task specs, oracle traces, workflow module library, module bindings, and v20 split batches.
- `rl_memory/scripts/`: workflow generation, audit, evaluation, reward calculation, and memory-method scripts.
- `rl_memory/openrlhf/`: OpenRLHF SFT/DPO/GRPO integration for workflow episodes.
- `docs/`: benchmark design notes, validity audits, experiment protocols, and reward design.

Large runtime artifacts are intentionally not tracked: `data.db`, logs, model weights, OpenRLHF datasets, checkpoints, and run outputs.

## Setup

Requirements:

- Python 3.8+
- Playwright Chromium

Install dependencies:

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

Initialize the local database:

```bash
python3 init_db.py
```

Start the benchmark server:

```bash
python3 server.py 8014
```

Runtime state lives in ignored files such as `data.db` and `env/state.json`; regenerate them locally rather than committing them.

## Quick Smoke Tests

Run one atomic oracle task:

```bash
python3 run_task.py A1-find-home --headless
```

Run a small workflow smoke without a model:

```bash
python3 -u rl_memory/scripts/run_workflow_benchmark.py \
  --split dev \
  --limit 5 \
  --output-root rl_memory/runs/readme_reference_smoke \
  --module-policy reference \
  --atomic-policy dry_run \
  --runtime-isolation per_goal \
  --headless
```

Recompute the dataset validity report:

```bash
python3 rl_memory/scripts/analyze_workflow_dataset_validity.py
```

## Workflow Evaluation

The official workflow runner executes each workflow goal as:

1. Select the next workflow module from legal candidates.
2. Bind that module to an executable atomic task.
3. Let the atomic policy interact with the local browser.
4. Evaluate the resulting workflow state against hidden oracle criteria.

Minimal local model run:

```bash
export AGENT_BACKEND=hf_local
export AGENT_MODEL=/path/to/local/model
export AGENT_PROMPT_PROFILE=webrl
export AGENT_MAX_TOKENS=96
export AGENT_TEMPERATURE=0.0

python3 -u rl_memory/scripts/run_workflow_benchmark.py \
  --split dev \
  --limit 20 \
  --output-root rl_memory/runs/dev_model_smoke \
  --runtime-root . \
  --runtime-isolation per_goal \
  --module-policy llm \
  --atomic-policy agent \
  --candidate-limit 6 \
  --target-backward-depth 2 \
  --atomic-max-steps 25 \
  --atomic-repeat-fail-threshold 3 \
  --headless
```

For parallel split evaluation, use:

```bash
bash rl_memory/scripts/run_workflow_benchmark_goalset_shards.sh path/to/goal_ids.txt
```

Relevant environment variables for the shard launcher:

- `BATCH_ROOT`: workflow batch root; defaults to v20.
- `RUN_ROOT`: output directory.
- `SPLIT`: `train`, `dev`, or `test`.
- `NUM_SHARDS`, `GPU_IDS`: shard and GPU assignment.
- `MODULE_POLICY`: `llm`, `heuristic`, or `reference`.
- `ATOMIC_POLICY`: `agent` or `dry_run`.
- `AGENT_BACKEND`, `AGENT_MODEL`, `AGENT_ADAPTER`, `AGENT_PROMPT_PROFILE`: model configuration.

See [docs/workflow_experiment_usage_zh.md](docs/workflow_experiment_usage_zh.md) for more experiment-oriented examples.

## Metrics

Workflow summaries report both final success and partial progress:

- `success_rate`: full workflow success rate.
- `average_composite_score`: benchmark composite score from the workflow runner.
- `average_checkpoint_progress`: checkpoint-level progress across workflow execution.
- `legal_module_completion_rate`: fraction of workflow modules completed through legal module choices.
- `average_episode_reward`: WFG-R1 dense reward.

Compute reward metrics from a workflow summary:

```bash
python3 rl_memory/scripts/reward_calculator.py path/to/dev_combined_summary.json \
  --output-json path/to/workflow_rewards.json \
  --output-md path/to/workflow_rewards.md \
  --jsonl path/to/workflow_rewards.jsonl
```

Reward details are documented in [docs/workflow_reward_design_20260426_zh.md](docs/workflow_reward_design_20260426_zh.md).

## Train / Dev / Test Isolation

The v20 benchmark uses explicit workflow split assets:

- `tasks/workflow_blueprint_splits.json`
- `tasks/generated_workflow_split_batches/workflow_split_batch_v20/train`
- `tasks/generated_workflow_split_batches/workflow_split_batch_v20/dev`
- `tasks/generated_workflow_split_batches/workflow_split_batch_v20/test`

Use train for SFT/RL data generation, dev for tuning and method selection, and test only for final reporting. Do not mix test workflow goals into training data or verifier data.

## Test-Time Memory Methods

Memory and test-time adaptation methods live under `rl_memory/memory_baselines/` and `rl_memory/test_time_methods/`. The current protocol compares static evaluation against methods such as Reflexion, MemoryBank, MemoryBank Lite, SkillBank, and Trajectory-RAG while preserving split isolation.

Protocol notes:

- [docs/test_time_online_adaptation_protocol_20260426_zh.md](docs/test_time_online_adaptation_protocol_20260426_zh.md)
- [docs/online_adaptation_reward_compare_20260426_zh.md](docs/online_adaptation_reward_compare_20260426_zh.md)

## SFT / RL

OpenRLHF integration is under `rl_memory/openrlhf/`.

Important entry points:

- `rl_memory/openrlhf/export_workflow_v20_jsonl.py`: export workflow data for SFT/RL.
- `rl_memory/openrlhf/train_sft_clean.sh`: LoRA SFT launcher.
- `rl_memory/openrlhf/train_grpo_clean.sh`: GRPO launcher.
- `rl_memory/openrlhf/agent_func_webagent.py`: multi-turn WebAgent environment for OpenRLHF.
- `rl_memory/openrlhf/merge_lora_adapter.py`: optional LoRA merge utility.

Model weights, exported RL datasets, LoRA adapters, and run directories are excluded from Git. Keep them on the experiment machine or shared storage and reference them through environment variables such as `BASE_MODEL`, `AGENT_MODEL`, and `AGENT_ADAPTER`.

See [rl_memory/openrlhf/README.md](rl_memory/openrlhf/README.md) for the integration details.

## Git Hygiene

Do not commit:

- `data.db`, `*.db-wal`, `*.db-shm`, `env/state.json`
- `rl_memory/runs/`
- `rl_memory/openrlhf/data/`
- model checkpoints or adapter weights
- local logs, screenshots, temporary files, or PDFs

The committed repository should contain benchmark source code, task assets, workflow split definitions, scripts, and paper-facing docs.
