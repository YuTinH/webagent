#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../" && pwd)"
RUN_ROOT="${RUN_ROOT:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/best_of_n_qwen25_7b_gpu23}"
RUNTIME_ROOT="${RUN_ROOT}/runtime"
SERVER_PORT="${SERVER_PORT:-8054}"
SERVER_LOG="${RUN_ROOT}/server_${SERVER_PORT}.log"
NUM_SHARDS="${NUM_SHARDS:-1}"
SHARD_INDEX="${SHARD_INDEX:-0}"
SHARD_SUFFIX=""
if [[ "${NUM_SHARDS}" != "1" ]]; then
  SHARD_SUFFIX="_shard${SHARD_INDEX}of${NUM_SHARDS}"
fi
SUMMARY_JSON="${SUMMARY_JSON:-${RUN_ROOT}/best_of_n_eval${SHARD_SUFFIX}.json}"
LOG_FILE="${LOG_FILE:-${RUN_ROOT}/best_of_n_eval${SHARD_SUFFIX}.log}"
RESUME="${RESUME:-0}"
START_CHAIN_ID="${START_CHAIN_ID:-}"
RESUME_AFTER_CHAIN_ID="${RESUME_AFTER_CHAIN_ID:-}"

mkdir -p "${RUN_ROOT}"
rm -rf "${RUNTIME_ROOT}"
mkdir -p "${RUNTIME_ROOT}"
cp -R "${ROOT}/env" "${RUNTIME_ROOT}/env"
cp -R "${ROOT}/tasks" "${RUNTIME_ROOT}/tasks"
cp "${ROOT}"/sampled_*.json "${RUNTIME_ROOT}/"
python3 - <<PY
import sqlite3
from pathlib import Path

src = Path("${ROOT}/data.db")
dst = Path("${RUNTIME_ROOT}/data.db")
dst.parent.mkdir(parents=True, exist_ok=True)
sconn = sqlite3.connect(str(src), timeout=30)
dconn = sqlite3.connect(str(dst), timeout=30)
try:
    sconn.backup(dconn)
finally:
    sconn.close()
    dconn.close()
PY
ln -s "${ROOT}/sites" "${RUNTIME_ROOT}/sites"
ln -s "${ROOT}/database" "${RUNTIME_ROOT}/database"

export WEBAGENT_RUNTIME_ROOT="${RUNTIME_ROOT}"
export WEBAGENT_SERVER_PORT="${SERVER_PORT}"
export WEBAGENT_SERVER_BASE_URL="http://127.0.0.1:${SERVER_PORT}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-2,3}"
export AGENT_BACKEND="${AGENT_BACKEND:-hf_local}"
export AGENT_MODEL="${AGENT_MODEL:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/models/Qwen2.5-7B-Instruct}"
export AGENT_HF_DEVICE_MAP="${AGENT_HF_DEVICE_MAP:-auto}"
export AGENT_HF_DTYPE="${AGENT_HF_DTYPE:-bfloat16}"
export AGENT_HF_USE_CHAT_TEMPLATE="${AGENT_HF_USE_CHAT_TEMPLATE:-true}"
export AGENT_PROMPT_PROFILE="${AGENT_PROMPT_PROFILE:-webrl}"
export AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS:-96}"
export AGENT_TEMPERATURE="${AGENT_TEMPERATURE:-0.0}"
export WEBAGENT_SUPPRESS_ASSERTION_LOGS="${WEBAGENT_SUPPRESS_ASSERTION_LOGS:-1}"
export AGENT_DECISION_METHOD="best_of_n"
export AGENT_BEST_OF_N_NUM_SAMPLES="${AGENT_BEST_OF_N_NUM_SAMPLES:-4}"
export AGENT_BEST_OF_N_CANDIDATE_POOL="${AGENT_BEST_OF_N_CANDIDATE_POOL:-8}"
export AGENT_BEST_OF_N_MAX_SAMPLING_ROUNDS="${AGENT_BEST_OF_N_MAX_SAMPLING_ROUNDS:-2}"
export AGENT_BEST_OF_N_MIN_ACTION_SCORE="${AGENT_BEST_OF_N_MIN_ACTION_SCORE:--3.0}"
export AGENT_BEST_OF_N_TEMPERATURE="${AGENT_BEST_OF_N_TEMPERATURE:-0.5}"
export AGENT_BEST_OF_N_BRANCH_TOP_K="${AGENT_BEST_OF_N_BRANCH_TOP_K:-1}"
export AGENT_BEST_OF_N_FEEDBACK_MAX_TOKENS="${AGENT_BEST_OF_N_FEEDBACK_MAX_TOKENS:-96}"
export AGENT_BEST_OF_N_VALUE_SAMPLES="${AGENT_BEST_OF_N_VALUE_SAMPLES:-1}"
export AGENT_BEST_OF_N_VALUE_TEMPERATURE="${AGENT_BEST_OF_N_VALUE_TEMPERATURE:-0.0}"
export AGENT_BEST_OF_N_VALUE_MAX_TOKENS="${AGENT_BEST_OF_N_VALUE_MAX_TOKENS:-96}"
export AGENT_BEST_OF_N_ACCEPT_THRESHOLD="${AGENT_BEST_OF_N_ACCEPT_THRESHOLD:-1.0}"
export AGENT_BEST_OF_N_USE_BRANCH_VALIDATION="${AGENT_BEST_OF_N_USE_BRANCH_VALIDATION:-false}"
export BENCHMARK_CLEAN_MODE="${BENCHMARK_CLEAN_MODE:-true}"
export BENCHMARK_OBFUSCATE="${BENCHMARK_OBFUSCATE:-false}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/.cache/ms-playwright}"

pkill -f "server.py ${SERVER_PORT}" || true
nohup python "${ROOT}/server.py" "${SERVER_PORT}" > "${SERVER_LOG}" 2>&1 &
SERVER_PID=$!
trap 'kill ${SERVER_PID} 2>/dev/null || true' EXIT
for _ in {1..15}; do
  if curl --max-time 2 -sSf "http://127.0.0.1:${SERVER_PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl --max-time 2 -sSf "http://127.0.0.1:${SERVER_PORT}/" >/dev/null 2>&1; then
  echo "server failed to start on port ${SERVER_PORT}" >&2
  tail -n 80 "${SERVER_LOG}" >&2 || true
  exit 1
fi

cd "${RUNTIME_ROOT}"
export BENCHMARK_LOG_FILE="${LOG_FILE}"
if [[ "${RESUME}" == "1" || -n "${START_CHAIN_ID}" || -n "${RESUME_AFTER_CHAIN_ID}" ]]; then
  export BENCHMARK_LOG_MODE="append"
else
  export BENCHMARK_LOG_MODE="${BENCHMARK_LOG_MODE:-write}"
fi

RUN_ARGS=(
  --themes newcomer,daily,career,leisure,crisis
  --limit-per-theme 20
  --num-shards "${NUM_SHARDS}"
  --shard-index "${SHARD_INDEX}"
  --headless
  --max-steps 25
  --repeat-fail-threshold 3
  --log-file "${LOG_FILE}"
  --summary-json "${SUMMARY_JSON}"
)
if [[ "${RESUME}" == "1" || -n "${START_CHAIN_ID}" || -n "${RESUME_AFTER_CHAIN_ID}" ]]; then
  RUN_ARGS+=(--resume --append-log)
fi
if [[ -n "${START_CHAIN_ID}" ]]; then
  RUN_ARGS+=(--start-chain-id "${START_CHAIN_ID}")
fi
if [[ -n "${RESUME_AFTER_CHAIN_ID}" ]]; then
  RUN_ARGS+=(--resume-after-chain-id "${RESUME_AFTER_CHAIN_ID}")
fi

python3 -u "${ROOT}/chain_runner_dynamic.py" \
  "${RUN_ARGS[@]}"
