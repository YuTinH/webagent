#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN_ROOT="${RUN_ROOT:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/reflexion_qwen25_7b_gpu23}"
RUNTIME_ROOT="${RUN_ROOT}/runtime"
SERVER_PORT="${SERVER_PORT:-8016}"
SERVER_LOG="${RUN_ROOT}/server_${SERVER_PORT}.log"
REFLECTION_STORE="${REFLECTION_STORE:-${RUN_ROOT}/reflections.json}"
PASS1_SUMMARY="${PASS1_SUMMARY:-${RUN_ROOT}/reflexion_build_pass.json}"
PASS2_SUMMARY="${PASS2_SUMMARY:-${RUN_ROOT}/reflexion_retrieve_pass.json}"
PASS1_LOG="${PASS1_LOG:-${RUN_ROOT}/reflexion_build_pass.log}"
PASS2_LOG="${PASS2_LOG:-${RUN_ROOT}/reflexion_retrieve_pass.log}"

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
export AGENT_MEMORY_METHOD="reflexion"
export AGENT_REFLEXION_STORE="${REFLECTION_STORE}"
export AGENT_REFLEXION_TOP_K="${AGENT_REFLEXION_TOP_K:-3}"
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

rm -f "${REFLECTION_STORE}"

cd "${RUNTIME_ROOT}"

export BENCHMARK_LOG_FILE="${PASS1_LOG}"
python3 -u "${ROOT}/chain_runner_dynamic.py" \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --log-file "${PASS1_LOG}" \
  --summary-json "${PASS1_SUMMARY}"

export BENCHMARK_LOG_FILE="${PASS2_LOG}"
python3 -u "${ROOT}/chain_runner_dynamic.py" \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --log-file "${PASS2_LOG}" \
  --summary-json "${PASS2_SUMMARY}"
