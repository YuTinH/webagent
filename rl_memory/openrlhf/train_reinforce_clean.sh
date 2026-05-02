#!/usr/bin/env bash
set -euo pipefail

# Example launcher for OpenRLHF multi-turn training on clean webagent flows.
# Adjust cluster, model, and batch sizes to your hardware.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
export OPENRLHF_USE_ISOLATED_RUNTIME="${OPENRLHF_USE_ISOLATED_RUNTIME:-1}"

DATA_ROOT="${DATA_ROOT:-${ROOT}/rl_memory/openrlhf/data/clean_pool_quick50_50_20_25}"
AGENT_FUNC="${AGENT_FUNC:-${ROOT}/rl_memory/openrlhf/agent_func_webagent.py}"
SAVE_ROOT="${SAVE_ROOT:-${ROOT}/rl_memory/runs/openrlhf_qwen25_7b_clean_reinforce_v1}"
CKPT_PATH="${CKPT_PATH:-}"
BASE_MODEL="${BASE_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
TOPOLOGY_PROFILE="${TOPOLOGY_PROFILE:-single_gpu_stable}"
PARAM_DTYPE="${PARAM_DTYPE:-bf16}"
ATTN_IMPLEMENTATION="${ATTN_IMPLEMENTATION:-flash_attention_2}"
SAVE_STEPS="${SAVE_STEPS:-5}"
EVAL_STEPS="${EVAL_STEPS:-20}"
MAX_CKPT_NUM="${MAX_CKPT_NUM:-3}"
MAX_SAMPLES="${MAX_SAMPLES:-0}"
ACTOR_LR="${ACTOR_LR:-2e-7}"
CRITIC_LR="${CRITIC_LR:-5e-6}"
N_SAMPLES_PER_PROMPT="${N_SAMPLES_PER_PROMPT:-2}"
PTX_COEF="${PTX_COEF:-0.1}"
USE_KL_LOSS="${USE_KL_LOSS:-1}"
INIT_KL_COEF="${INIT_KL_COEF:-0.02}"
KL_ESTIMATOR="${KL_ESTIMATOR:-k3}"
ENTROPY_LOSS_COEF="${ENTROPY_LOSS_COEF:-}"
OPENRLHF_REWARD_MODE="${OPENRLHF_REWARD_MODE:-wfg_r1_module}"
OPENRLHF_PROGRESS_WEIGHT="${OPENRLHF_PROGRESS_WEIGHT:-0.75}"
OPENRLHF_SELECTOR_VALID_BONUS="${OPENRLHF_SELECTOR_VALID_BONUS:-0.10}"
OPENRLHF_INVALID_ACTION_PENALTY="${OPENRLHF_INVALID_ACTION_PENALTY:--0.40}"
OPENRLHF_REPEAT_ACTION_PENALTY="${OPENRLHF_REPEAT_ACTION_PENALTY:--0.25}"
OPENRLHF_STEP_ERROR_PENALTY="${OPENRLHF_STEP_ERROR_PENALTY:--0.40}"
OPENRLHF_PREMATURE_DONE_PENALTY="${OPENRLHF_PREMATURE_DONE_PENALTY:--0.30}"
OPENRLHF_SUCCESS_BONUS="${OPENRLHF_SUCCESS_BONUS:-0.15}"
OPENRLHF_FLOW_SUCCESS_BONUS="${OPENRLHF_FLOW_SUCCESS_BONUS:-0.20}"
OPENRLHF_REWARD_MIN="${OPENRLHF_REWARD_MIN:--1.0}"
OPENRLHF_REWARD_MAX="${OPENRLHF_REWARD_MAX:-1.0}"
OPENRLHF_STOP_ON_INVALID_ACTION="${OPENRLHF_STOP_ON_INVALID_ACTION:-1}"
export OPENRLHF_REWARD_MODE
export OPENRLHF_PROGRESS_WEIGHT
export OPENRLHF_SELECTOR_VALID_BONUS
export OPENRLHF_INVALID_ACTION_PENALTY
export OPENRLHF_REPEAT_ACTION_PENALTY
export OPENRLHF_STEP_ERROR_PENALTY
export OPENRLHF_PREMATURE_DONE_PENALTY
export OPENRLHF_SUCCESS_BONUS
export OPENRLHF_FLOW_SUCCESS_BONUS
export OPENRLHF_REWARD_MIN
export OPENRLHF_REWARD_MAX
export OPENRLHF_STOP_ON_INVALID_ACTION
case "${TOPOLOGY_PROFILE}" in
  single_gpu_stable)
    : "${VLLM_NUM_ENGINES:=1}"
    : "${VLLM_TP_SIZE:=1}"
    : "${VLLM_GPU_UTIL:=0.35}"
    : "${ACTOR_GPUS:=1}"
    : "${REF_GPUS:=1}"
    : "${CRITIC_GPUS:=1}"
    : "${REWARD_GPUS:=1}"
    : "${TRAIN_BATCH_SIZE:=4}"
    : "${ROLLOUT_BATCH_SIZE:=4}"
    : "${PROMPT_MAX_LEN:=1024}"
    : "${GENERATE_MAX_LEN:=96}"
    : "${COLOCATE_ALL_MODELS:=1}"
    : "${VLLM_SYNC_BACKEND:=nccl}"
    ;;
  dual_gpu_balanced)
    # Keep TP=1 and move to a conservative 2-GPU hybrid-engine topology first.
    # This uses one extra GPU to relieve rollout/training contention without
    # re-entering the much less stable TP=2 path.
    : "${VLLM_NUM_ENGINES:=1}"
    : "${VLLM_TP_SIZE:=1}"
    : "${VLLM_GPU_UTIL:=0.30}"
    : "${ACTOR_GPUS:=1}"
    : "${REF_GPUS:=1}"
    : "${CRITIC_GPUS:=1}"
    : "${REWARD_GPUS:=1}"
    : "${TRAIN_BATCH_SIZE:=8}"
    : "${ROLLOUT_BATCH_SIZE:=8}"
    : "${PROMPT_MAX_LEN:=1536}"
    : "${GENERATE_MAX_LEN:=128}"
    : "${COLOCATE_ALL_MODELS:=1}"
    : "${VLLM_SYNC_BACKEND:=nccl}"
    : "${VLLM_SYNC_WITH_RAY:=1}"
    ;;
  quad_gpu_fast)
    # 4-GPU throughput-oriented profile:
    # - keep TP=1 to avoid the fragile TP>1 sync path
    # - expand the colocated actor/ref/vLLM group to 4 GPUs so all 4 H200s
    #   participate without introducing a separate non-colocated topology
    : "${VLLM_NUM_ENGINES:=4}"
    : "${VLLM_TP_SIZE:=1}"
    : "${VLLM_GPU_UTIL:=0.30}"
    : "${ACTOR_GPUS:=4}"
    : "${REF_GPUS:=4}"
    : "${CRITIC_GPUS:=1}"
    : "${REWARD_GPUS:=1}"
    : "${TRAIN_BATCH_SIZE:=24}"
    : "${ROLLOUT_BATCH_SIZE:=24}"
    : "${PROMPT_MAX_LEN:=1536}"
    : "${GENERATE_MAX_LEN:=128}"
    : "${COLOCATE_ALL_MODELS:=1}"
    : "${VLLM_SYNC_BACKEND:=nccl}"
    : "${VLLM_SYNC_WITH_RAY:=1}"
    : "${USE_DYNAMIC_BATCH:=1}"
    : "${PACKING_SAMPLES:=1}"
    ;;
  *)
    echo "error: unsupported TOPOLOGY_PROFILE=${TOPOLOGY_PROFILE}" >&2
    echo "supported values: single_gpu_stable, dual_gpu_balanced, quad_gpu_fast" >&2
    exit 1
    ;;
esac

EXPECTED_ACTOR_GPUS=$(( VLLM_NUM_ENGINES * VLLM_TP_SIZE ))
ACTOR_GPUS="${ACTOR_GPUS:-${EXPECTED_ACTOR_GPUS}}"
MICRO_TRAIN_BATCH_SIZE="${MICRO_TRAIN_BATCH_SIZE:-1}"
MICRO_ROLLOUT_BATCH_SIZE="${MICRO_ROLLOUT_BATCH_SIZE:-1}"
ADV_ESTIMATOR="${ADV_ESTIMATOR:-reinforce}"
LORA_RANK="${LORA_RANK:-16}"
LORA_ALPHA="${LORA_ALPHA:-32}"
LOAD_IN_4BIT="${LOAD_IN_4BIT:-0}"
USE_GRADIENT_CHECKPOINTING="${USE_GRADIENT_CHECKPOINTING:-1}"
USE_ADAM_OFFLOAD="${USE_ADAM_OFFLOAD:-1}"
VLLM_SYNC_WITH_RAY="${VLLM_SYNC_WITH_RAY:-0}"
USE_DYNAMIC_BATCH="${USE_DYNAMIC_BATCH:-0}"
PACKING_SAMPLES="${PACKING_SAMPLES:-0}"

mkdir -p "${SAVE_ROOT}"
if [[ -n "${CKPT_PATH}" ]]; then
  mkdir -p "${CKPT_PATH}"
fi

if [[ "${ACTOR_GPUS}" -ne "${EXPECTED_ACTOR_GPUS}" ]]; then
  echo "error: ACTOR_GPUS (${ACTOR_GPUS}) must equal VLLM_NUM_ENGINES * VLLM_TP_SIZE (${EXPECTED_ACTOR_GPUS})" >&2
  echo "set ACTOR_GPUS=${EXPECTED_ACTOR_GPUS} or unset ACTOR_GPUS to use the derived default" >&2
  exit 1
fi

if [[ "${COLOCATE_ALL_MODELS}" != "1" && "${ACTOR_GPUS}" -ne "${REF_GPUS}" ]]; then
  echo "error: TP/actor topology requires ACTOR_GPUS and REF_GPUS to match when actor/ref colocation is enabled." >&2
  echo "current values: ACTOR_GPUS=${ACTOR_GPUS}, REF_GPUS=${REF_GPUS}, VLLM_NUM_ENGINES=${VLLM_NUM_ENGINES}, VLLM_TP_SIZE=${VLLM_TP_SIZE}" >&2
  echo "options:" >&2
  echo "  1) keep VLLM_TP_SIZE=1 (recommended first)" >&2
  echo "  2) set COLOCATE_ALL_MODELS=1 for an all-models-on-2-GPUs topology" >&2
  exit 1
fi

CMD=(
  "${PYTHON_BIN}" -m openrlhf.cli.train_ppo_ray
  --actor_num_nodes 1 \
  --actor_num_gpus_per_node "${ACTOR_GPUS}" \
  --ref_num_nodes 1 \
  --ref_num_gpus_per_node "${REF_GPUS}" \
  --critic_num_nodes 1 \
  --critic_num_gpus_per_node "${CRITIC_GPUS}" \
  --reward_num_nodes 1 \
  --reward_num_gpus_per_node "${REWARD_GPUS}" \
  --vllm_num_engines "${VLLM_NUM_ENGINES}" \
  --vllm_tensor_parallel_size "${VLLM_TP_SIZE}" \
  --vllm_gpu_memory_utilization "${VLLM_GPU_UTIL}" \
  --vllm_sync_backend "${VLLM_SYNC_BACKEND}" \
  --pretrain "${BASE_MODEL}" \
  --save_path "${SAVE_ROOT}" \
  --save_steps "${SAVE_STEPS}" \
  --save_hf_ckpt \
  --max_ckpt_num "${MAX_CKPT_NUM}" \
  --logging_steps 1 \
  --eval_steps "${EVAL_STEPS}" \
  --train_batch_size "${TRAIN_BATCH_SIZE}" \
  --micro_train_batch_size "${MICRO_TRAIN_BATCH_SIZE}" \
  --rollout_batch_size "${ROLLOUT_BATCH_SIZE}" \
  --micro_rollout_batch_size "${MICRO_ROLLOUT_BATCH_SIZE}" \
  --max_epochs 1 \
  --prompt_max_len "${PROMPT_MAX_LEN}" \
  --generate_max_len "${GENERATE_MAX_LEN}" \
  --zero_stage 2 \
  --param_dtype "${PARAM_DTYPE}" \
  --attn_implementation "${ATTN_IMPLEMENTATION}" \
  --actor_learning_rate "${ACTOR_LR}" \
  --critic_learning_rate "${CRITIC_LR}" \
  --ptx_coef "${PTX_COEF}" \
  --init_kl_coef "${INIT_KL_COEF}" \
  --kl_estimator "${KL_ESTIMATOR}" \
  --prompt_data "${DATA_ROOT}/train.jsonl" \
  --eval_dataset "${DATA_ROOT}/val.jsonl" \
  --input_key observation \
  --label_key label \
  --agent_func_path "${AGENT_FUNC}" \
  --advantage_estimator "${ADV_ESTIMATOR}" \
  --n_samples_per_prompt "${N_SAMPLES_PER_PROMPT}"
)

if [[ -n "${CKPT_PATH}" ]]; then
  CMD+=(--ckpt_path "${CKPT_PATH}")
fi

if [[ "${MAX_SAMPLES}" != "0" ]]; then
  CMD+=(--max_samples "${MAX_SAMPLES}")
fi

if [[ "${COLOCATE_ALL_MODELS}" == "1" ]]; then
  CMD+=(--colocate_all_models --vllm_enable_sleep --deepspeed_enable_sleep)
else
  CMD+=(--colocate_actor_ref --colocate_critic_reward)
fi

if [[ "${VLLM_SYNC_WITH_RAY}" == "1" ]]; then
  CMD+=(--vllm_sync_with_ray)
fi

if [[ "${USE_KL_LOSS}" == "1" ]]; then
  CMD+=(--use_kl_loss)
fi

if [[ -n "${ENTROPY_LOSS_COEF}" ]]; then
  CMD+=(--entropy_loss_coef "${ENTROPY_LOSS_COEF}")
fi

if [[ "${USE_DYNAMIC_BATCH}" == "1" ]]; then
  CMD+=(--use_dynamic_batch)
fi

if [[ "${PACKING_SAMPLES}" == "1" ]]; then
  CMD+=(--packing_samples)
fi

if [[ "${LOAD_IN_4BIT}" == "1" ]]; then
  CMD+=(--load_in_4bit)
fi

if [[ "${LORA_RANK}" != "0" ]]; then
  CMD+=(--lora_rank "${LORA_RANK}" --lora_alpha "${LORA_ALPHA}")
fi

if [[ "${USE_GRADIENT_CHECKPOINTING}" == "1" ]]; then
  CMD+=(--gradient_checkpointing)
fi

if [[ "${USE_ADAM_OFFLOAD}" == "1" ]]; then
  CMD+=(--adam_offload)
fi

"${CMD[@]}"
