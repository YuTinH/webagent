#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export TOPOLOGY_PROFILE="${TOPOLOGY_PROFILE:-dual_gpu_balanced}"
export RAY_NUM_GPUS="${RAY_NUM_GPUS:-2}"

export BASE_MODEL="${BASE_MODEL:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/models/Qwen2.5-7B-Instruct}"
export DATA_ROOT="${DATA_ROOT:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/openrlhf/data/clean_pool_v1_1000_200_300}"
export SAVE_ROOT="${SAVE_ROOT:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/openrlhf_qwen25_7b_clean_reinforce_full_v1}"

export VLLM_SYNC_BACKEND="${VLLM_SYNC_BACKEND:-nccl}"
export VLLM_SYNC_WITH_RAY="${VLLM_SYNC_WITH_RAY:-1}"

export OPENRLHF_SKIP_SETUP="${OPENRLHF_SKIP_SETUP:-1}"
export OPENRLHF_USE_ISOLATED_RUNTIME="${OPENRLHF_USE_ISOLATED_RUNTIME:-1}"
export BENCHMARK_CLEAN_MODE="${BENCHMARK_CLEAN_MODE:-true}"
export BENCHMARK_OBFUSCATE="${BENCHMARK_OBFUSCATE:-false}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/.cache/ms-playwright}"

export TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-8}"
export ROLLOUT_BATCH_SIZE="${ROLLOUT_BATCH_SIZE:-8}"
export PROMPT_MAX_LEN="${PROMPT_MAX_LEN:-1536}"
export GENERATE_MAX_LEN="${GENERATE_MAX_LEN:-128}"
export LORA_RANK="${LORA_RANK:-16}"
export LOAD_IN_4BIT="${LOAD_IN_4BIT:-0}"

cd "${ROOT}"

python rl_memory/openrlhf/patch_openrlhf_lora_weight_sync_v2.py
python rl_memory/openrlhf/patch_openrlhf_lora_broadcast_merge.py
python rl_memory/openrlhf/patch_openrlhf_zero_response_kl.py

ray stop --force || true
pkill -f "openrlhf.cli.train_ppo_ray" || true
pkill -f "ray::" || true
pkill -f "VLLM::EngineCore" || true
pkill -f "chrome-headless-shell" || true
pkill -f "/webagent/server.py" || true

bash rl_memory/openrlhf/run_minimal_pipeline.sh
