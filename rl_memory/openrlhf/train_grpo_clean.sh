#!/usr/bin/env bash
set -euo pipefail

# Minimal GRPO launcher for the WebAgent OpenRLHF adapter.
#
# This intentionally trains the vanilla/static Qwen policy first. Memory,
# Reflexion, and Trajectory-RAG should be evaluated after the parameter-level
# policy update is validated, not mixed into the first GRPO run.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

export ADV_ESTIMATOR="${ADV_ESTIMATOR:-group_norm}"
export N_SAMPLES_PER_PROMPT="${N_SAMPLES_PER_PROMPT:-4}"
export USE_KL_LOSS="${USE_KL_LOSS:-1}"
export KL_ESTIMATOR="${KL_ESTIMATOR:-k3}"
export INIT_KL_COEF="${INIT_KL_COEF:-0.001}"
export ACTOR_LR="${ACTOR_LR:-5e-7}"
export PTX_COEF="${PTX_COEF:-0.0}"
export SAVE_STEPS="${SAVE_STEPS:-1}"
export EVAL_STEPS="${EVAL_STEPS:-5}"
export MAX_CKPT_NUM="${MAX_CKPT_NUM:-2}"
export MAX_SAMPLES="${MAX_SAMPLES:-8}"
export TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-4}"
export ROLLOUT_BATCH_SIZE="${ROLLOUT_BATCH_SIZE:-4}"
export MICRO_TRAIN_BATCH_SIZE="${MICRO_TRAIN_BATCH_SIZE:-1}"
export MICRO_ROLLOUT_BATCH_SIZE="${MICRO_ROLLOUT_BATCH_SIZE:-1}"
export GENERATE_MAX_LEN="${GENERATE_MAX_LEN:-96}"
export PROMPT_MAX_LEN="${PROMPT_MAX_LEN:-1024}"
export AGENT_MEMORY_METHOD="${AGENT_MEMORY_METHOD:-none}"
export AGENT_DECISION_METHOD="${AGENT_DECISION_METHOD:-none}"
export SAVE_ROOT="${SAVE_ROOT:-${ROOT}/rl_memory/runs/openrlhf_qwen25_7b_grpo_smoke_${TIMESTAMP}}"

echo "GRPO smoke configuration:"
echo "  ADV_ESTIMATOR=${ADV_ESTIMATOR}"
echo "  N_SAMPLES_PER_PROMPT=${N_SAMPLES_PER_PROMPT}"
echo "  KL_ESTIMATOR=${KL_ESTIMATOR}"
echo "  MAX_SAMPLES=${MAX_SAMPLES}"
echo "  SAVE_ROOT=${SAVE_ROOT}"
echo "  OPENRLHF_REWARD_MODE=${OPENRLHF_REWARD_MODE:-wfg_r1_module}"
echo "  OPENRLHF_PROGRESS_WEIGHT=${OPENRLHF_PROGRESS_WEIGHT:-0.75}"
echo "  OPENRLHF_SUCCESS_BONUS=${OPENRLHF_SUCCESS_BONUS:-0.15}"

bash "${ROOT}/rl_memory/openrlhf/train_reinforce_clean.sh"
