#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="${RUN_ROOT:-${ROOT}/rl_memory/runs/eval_shards}"
mkdir -p "${RUN_ROOT}"

NUM_SHARDS="${NUM_SHARDS:-4}"
THEMES="${THEMES:-newcomer,daily,career,leisure,crisis}"
LIMIT_PER_THEME="${LIMIT_PER_THEME:-20}"
MAX_STEPS="${MAX_STEPS:-25}"
REPEAT_FAIL_THRESHOLD="${REPEAT_FAIL_THRESHOLD:-3}"
SCENARIO_ROOT="${SCENARIO_ROOT:-}"
MODEL_PATH="${MODEL_PATH:-}"
GPU_IDS="${GPU_IDS:-0,1,2,3}"
TAG="${TAG:-eval}"

if [[ -z "${MODEL_PATH}" ]]; then
  echo "MODEL_PATH is required." >&2
  exit 1
fi

IFS=',' read -r -a GPU_ARRAY <<< "${GPU_IDS}"
if [[ "${#GPU_ARRAY[@]}" -lt "${NUM_SHARDS}" ]]; then
  echo "Need at least NUM_SHARDS GPU ids in GPU_IDS." >&2
  exit 1
fi

timestamp="$(date +%Y%m%d_%H%M%S)"
pids=()

for (( shard=0; shard<NUM_SHARDS; shard++ )); do
  gpu="${GPU_ARRAY[$shard]}"
  summary="${RUN_ROOT}/${timestamp}_${TAG}_shard${shard}.json"
  log="${RUN_ROOT}/${timestamp}_${TAG}_shard${shard}.log"

  cmd=(
    env
    "CUDA_VISIBLE_DEVICES=${gpu}"
    "AGENT_BACKEND=${AGENT_BACKEND:-hf_local}"
    "AGENT_MODEL=${MODEL_PATH}"
    "AGENT_PROMPT_PROFILE=${AGENT_PROMPT_PROFILE:-webrl}"
    "AGENT_MAX_TOKENS=${AGENT_MAX_TOKENS:-128}"
    "AGENT_HF_DEVICE_MAP=${AGENT_HF_DEVICE_MAP:-auto}"
    "AGENT_HF_DTYPE=${AGENT_HF_DTYPE:-bfloat16}"
    "BENCHMARK_CLEAN_MODE=${BENCHMARK_CLEAN_MODE:-true}"
    "BENCHMARK_OBFUSCATE=${BENCHMARK_OBFUSCATE:-false}"
    "HF_HUB_OFFLINE=${HF_HUB_OFFLINE:-1}"
    "TRANSFORMERS_OFFLINE=${TRANSFORMERS_OFFLINE:-1}"
    "PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH:-}"
    python3 -u "${ROOT}/chain_runner_dynamic.py"
    --themes "${THEMES}"
    --limit-per-theme "${LIMIT_PER_THEME}"
    --num-shards "${NUM_SHARDS}"
    --shard-index "${shard}"
    --headless
    --max-steps "${MAX_STEPS}"
    --repeat-fail-threshold "${REPEAT_FAIL_THRESHOLD}"
    --summary-json "${summary}"
  )

  if [[ -n "${SCENARIO_ROOT}" ]]; then
    cmd+=(--scenario-root "${SCENARIO_ROOT}")
  fi

  echo "Launching shard ${shard}/${NUM_SHARDS} on GPU ${gpu}"
  "${cmd[@]}" > "${log}" 2>&1 &
  pids+=("$!")
done

echo "Launched ${#pids[@]} shards"
echo "Run root: ${RUN_ROOT}"
echo "Timestamp tag: ${timestamp}_${TAG}"

status=0
for pid in "${pids[@]}"; do
  wait "${pid}" || status=$?
done

exit "${status}"
