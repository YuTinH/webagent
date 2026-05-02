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
BASE_MODEL="${BASE_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
DATA_ROOT="${DATA_ROOT:-${ROOT}/rl_memory/openrlhf/data/oracle_sft_dpo_v1/sft}"
SAVE_ROOT="${SAVE_ROOT:-${ROOT}/rl_memory/runs/openrlhf_qwen25_7b_sft_v1}"

TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-64}"
MICRO_TRAIN_BATCH_SIZE="${MICRO_TRAIN_BATCH_SIZE:-1}"
MAX_EPOCHS="${MAX_EPOCHS:-1}"
MAX_LEN="${MAX_LEN:-1024}"
LEARNING_RATE="${LEARNING_RATE:-5e-6}"
ZERO_STAGE="${ZERO_STAGE:-2}"
PARAM_DTYPE="${PARAM_DTYPE:-bf16}"
SAVE_STEPS="${SAVE_STEPS:-50}"
EVAL_STEPS="${EVAL_STEPS:-50}"
MAX_CKPT_NUM="${MAX_CKPT_NUM:-3}"
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
  --module openrlhf.cli.train_sft
  --pretrain "${BASE_MODEL}"
  --dataset "${DATA_ROOT}/train.jsonl"
  --eval_dataset "${DATA_ROOT}/val.jsonl"
  --input_key prompt
  --output_key response
  --input_template '{}'
  --save_path "${SAVE_ROOT}"
  --save_steps "${SAVE_STEPS}"
  --save_hf_ckpt
  --max_ckpt_num "${MAX_CKPT_NUM}"
  --logging_steps 1
  --eval_steps "${EVAL_STEPS}"
  --train_batch_size "${TRAIN_BATCH_SIZE}"
  --micro_train_batch_size "${MICRO_TRAIN_BATCH_SIZE}"
  --max_samples "${MAX_SAMPLES}"
  --max_epochs "${MAX_EPOCHS}"
  --max_len "${MAX_LEN}"
  --zero_stage "${ZERO_STAGE}"
  --param_dtype "${PARAM_DTYPE}"
  --learning_rate "${LEARNING_RATE}"
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

printf 'SFT base model: %s\n' "${BASE_MODEL}"
printf 'SFT data root: %s\n' "${DATA_ROOT}"
printf 'SFT save root: %s\n' "${SAVE_ROOT}"
printf 'SFT num gpus: %s\n' "${NUM_GPUS}"

"${CMD[@]}"
