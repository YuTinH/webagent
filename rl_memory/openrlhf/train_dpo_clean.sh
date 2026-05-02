#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  IFS=',' read -r -a _visible_gpus <<< "${CUDA_VISIBLE_DEVICES}"
  NUM_GPUS_DEFAULT="${#_visible_gpus[@]}"
else
  NUM_GPUS_DEFAULT=1
fi

NUM_GPUS="${NUM_GPUS:-${NUM_GPUS_DEFAULT}}"
PRETRAIN_MODEL="${PRETRAIN_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
REF_PRETRAIN="${REF_PRETRAIN:-${PRETRAIN_MODEL}}"
DATA_ROOT="${DATA_ROOT:-${ROOT}/rl_memory/openrlhf/data/oracle_sft_dpo_v1/dpo}"
SAVE_ROOT="${SAVE_ROOT:-${ROOT}/rl_memory/runs/openrlhf_qwen25_7b_dpo_v1}"

TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-32}"
MICRO_TRAIN_BATCH_SIZE="${MICRO_TRAIN_BATCH_SIZE:-1}"
MAX_EPOCHS="${MAX_EPOCHS:-1}"
MAX_LEN="${MAX_LEN:-1024}"
LEARNING_RATE="${LEARNING_RATE:-2e-7}"
ZERO_STAGE="${ZERO_STAGE:-2}"
PARAM_DTYPE="${PARAM_DTYPE:-bf16}"
SAVE_STEPS="${SAVE_STEPS:-50}"
MAX_CKPT_NUM="${MAX_CKPT_NUM:-3}"
BETA="${BETA:-0.1}"
NLL_LOSS_COEF="${NLL_LOSS_COEF:-0.02}"
LORA_RANK="${LORA_RANK:-16}"
LORA_ALPHA="${LORA_ALPHA:-32}"
LOAD_IN_4BIT="${LOAD_IN_4BIT:-0}"
USE_ADAM_OFFLOAD="${USE_ADAM_OFFLOAD:-1}"
USE_GRADIENT_CHECKPOINTING="${USE_GRADIENT_CHECKPOINTING:-1}"
PACKING_SAMPLES="${PACKING_SAMPLES:-0}"
ATTN_IMPL="${ATTN_IMPL:-flash_attention_2}"
MAX_SAMPLES="${MAX_SAMPLES:-1000000}"

mkdir -p "${SAVE_ROOT}"

CMD=(
  deepspeed
  --num_gpus "${NUM_GPUS}"
  --module openrlhf.cli.train_dpo
  --pretrain "${PRETRAIN_MODEL}"
  --ref_pretrain "${REF_PRETRAIN}"
  --dataset "${DATA_ROOT}/train.jsonl"
  --eval_dataset "${DATA_ROOT}/val.jsonl"
  --prompt_key prompt
  --chosen_key chosen
  --rejected_key rejected
  --input_template '{}'
  --save_path "${SAVE_ROOT}"
  --save_steps "${SAVE_STEPS}"
  --save_hf_ckpt
  --max_ckpt_num "${MAX_CKPT_NUM}"
  --logging_steps 1
  --eval_steps 50
  --train_batch_size "${TRAIN_BATCH_SIZE}"
  --micro_train_batch_size "${MICRO_TRAIN_BATCH_SIZE}"
  --max_samples "${MAX_SAMPLES}"
  --max_epochs "${MAX_EPOCHS}"
  --max_len "${MAX_LEN}"
  --zero_stage "${ZERO_STAGE}"
  --param_dtype "${PARAM_DTYPE}"
  --learning_rate "${LEARNING_RATE}"
  --beta "${BETA}"
  --nll_loss_coef "${NLL_LOSS_COEF}"
  --attn_implementation "${ATTN_IMPL}"
)

if [[ "${LORA_RANK}" != "0" ]]; then
  CMD+=(--lora_rank "${LORA_RANK}" --lora_alpha "${LORA_ALPHA}")
fi

if [[ "${LOAD_IN_4BIT}" == "1" ]]; then
  CMD+=(--load_in_4bit)
fi

if [[ "${USE_ADAM_OFFLOAD}" == "1" ]]; then
  CMD+=(--adam_offload)
fi

if [[ "${USE_GRADIENT_CHECKPOINTING}" == "1" ]]; then
  CMD+=(--gradient_checkpointing)
fi

if [[ "${PACKING_SAMPLES}" == "1" ]]; then
  CMD+=(--packing_samples)
fi

printf 'DPO pretrain: %s\n' "${PRETRAIN_MODEL}"
printf 'DPO ref model: %s\n' "${REF_PRETRAIN}"
printf 'DPO data root: %s\n' "${DATA_ROOT}"
printf 'DPO save root: %s\n' "${SAVE_ROOT}"
printf 'DPO num gpus: %s\n' "${NUM_GPUS}"

"${CMD[@]}"
