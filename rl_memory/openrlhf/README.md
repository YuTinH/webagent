# OpenRLHF Adapter

This directory contains the first OpenRLHF integration layer for the webagent benchmark.

## Purpose

The adapter reuses the existing benchmark runtime instead of re-implementing another environment stack.

It is designed around the current benchmark components:
- `/Users/masteryth/Documents/webagent/scenario_generator_v3.py`
- `/Users/masteryth/Documents/webagent/chain_runner_dynamic.py`
- `/Users/masteryth/Documents/webagent/llm_runner.py`
- `/Users/masteryth/Documents/webagent/agent/browser_env.py`

## Files

- `agent_func_webagent.py`
  - OpenRLHF multi-turn agent function using `AgentInstanceBase`
  - wraps task-flow execution, task patching, browser interaction, and reward calculation

- `export_openrlhf_jsonl.py`
  - converts split manifests plus the merged clean pool into jsonl files for OpenRLHF

- `train_reinforce_clean.sh`
  - a first training launcher template for clean-flow RL

- `export_sft_dpo_oracle_jsonl.py`
  - builds local jsonl datasets for:
    - SFT from oracle next actions
    - DPO from oracle actions plus synthetic rejected actions based on observed failure modes

- `train_sft_clean.sh`
  - LoRA SFT launcher on top of OpenRLHF `train_sft`

- `train_dpo_clean.sh`
  - LoRA DPO launcher on top of OpenRLHF `train_dpo`

## Workflow

1. Build a clean flow pool under:
   - `/Users/masteryth/Documents/webagent/rl_memory/runs/...`
2. Create train/val/test manifests under:
   - `/Users/masteryth/Documents/webagent/rl_memory/splits/...`
3. Export jsonl datasets with:
   - `export_openrlhf_jsonl.py`
4. Train with OpenRLHF using:
   - `agent_func_webagent.py`
   - `train_reinforce_clean.sh`

## SFT / DPO Workflow

1. Export oracle-action datasets:
   - `export_sft_dpo_oracle_jsonl.py`
2. Train a behavior-cloning policy with:
   - `train_sft_clean.sh`
3. Merge the SFT LoRA adapter into a standalone HF checkpoint if you want to use it as the DPO initialization model
4. Train preference optimization with:
   - `train_dpo_clean.sh`

### Dataset Design

- SFT prompt:
  - task instruction
  - success criteria
  - current URL hint
  - previous oracle actions
- SFT target:
  - exactly one next browser action

- DPO chosen:
  - oracle next action

- DPO rejected:
  - synthetic failure-mode action matching observed benchmark errors, such as:
    - multi-action output
    - premature `DONE()`
    - repeated previous action
    - action-type mismatch
    - external navigation

## Current Scope

This is a first integration layer, not the final training recipe.

Implemented:
- flow dataset export
- benchmark-backed multi-turn environment
- sparse+dense reward from checkpoint progress, task success, and flow success

Not implemented yet:
- dedicated memory module integration
- asynchronous throughput tuning
- full distributed launch validation on your target cluster
