#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="${RUN_ROOT:-$ROOT/rl_memory/runs/workflow_benchmark_local}"
WORKFLOW_BATCH_ROOT="${WORKFLOW_BATCH_ROOT:-$ROOT/tasks/generated_workflow_split_batches/workflow_split_batch_v20}"
WORKFLOW_SPLIT="${WORKFLOW_SPLIT:-dev}"
WORKFLOW_LIMIT="${WORKFLOW_LIMIT:-0}"
SERVER_PORT="${SERVER_PORT:-8060}"
RUNTIME_ROOT="${WORKFLOW_RUNTIME_ROOT:-$RUN_ROOT/runtime}"
SERVER_LOG="${RUN_ROOT}/server_${SERVER_PORT}.log"

export AGENT_BACKEND="${AGENT_BACKEND:-hf_local}"
export AGENT_MODEL="${AGENT_MODEL:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/models/Qwen2.5-7B-Instruct}"
export AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS:-96}"
export AGENT_TEMPERATURE="${AGENT_TEMPERATURE:-0.0}"
export AGENT_HF_USE_CHAT_TEMPLATE="${AGENT_HF_USE_CHAT_TEMPLATE:-true}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/.cache/ms-playwright}"
export WEBAGENT_SERVER_PORT="${SERVER_PORT}"
export WEBAGENT_SERVER_BASE_URL="http://127.0.0.1:${SERVER_PORT}"
export WEBAGENT_RUNTIME_ROOT="${RUNTIME_ROOT}"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

mkdir -p "${RUN_ROOT}"
rm -rf "${RUNTIME_ROOT}"
mkdir -p "${RUNTIME_ROOT}/tasks" "${RUNTIME_ROOT}/output"
cp -R "${ROOT}/env" "${RUNTIME_ROOT}/env"
cp -R "${ROOT}/sites" "${RUNTIME_ROOT}/sites"
cp "${ROOT}/data.db" "${RUNTIME_ROOT}/data.db"
if [[ -f "${ROOT}/data.db-wal" ]]; then cp "${ROOT}/data.db-wal" "${RUNTIME_ROOT}/data.db-wal"; fi
if [[ -f "${ROOT}/data.db-shm" ]]; then cp "${ROOT}/data.db-shm" "${RUNTIME_ROOT}/data.db-shm"; fi

pkill -f "server.py ${SERVER_PORT}" || true
nohup python3 "${ROOT}/server.py" "${SERVER_PORT}" > "${SERVER_LOG}" 2>&1 &
SERVER_PID=$!
trap 'kill ${SERVER_PID} >/dev/null 2>&1 || true' EXIT
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

if [[ "${WORKFLOW_LIMIT}" == "0" ]]; then
  LIMIT_ARGS=()
else
  LIMIT_ARGS=(--limit "${WORKFLOW_LIMIT}")
fi

(
  cd "${RUNTIME_ROOT}"
  python3 "${ROOT}/rl_memory/scripts/run_workflow_benchmark.py" \
    --batch-root "${WORKFLOW_BATCH_ROOT}" \
    --split "${WORKFLOW_SPLIT}" \
    --output-root "${RUN_ROOT}/results" \
    --runtime-root "${RUNTIME_ROOT}" \
    --module-policy "${WORKFLOW_MODULE_POLICY:-llm}" \
    --atomic-policy "${WORKFLOW_ATOMIC_POLICY:-agent}" \
    --candidate-limit "${WORKFLOW_CANDIDATE_LIMIT:-6}" \
    --target-backward-depth "${WORKFLOW_BACKWARD_DEPTH:-2}" \
    --module-max-tokens "${WORKFLOW_MODULE_MAX_TOKENS:-32}" \
    --module-temperature "${WORKFLOW_MODULE_TEMPERATURE:-0.0}" \
    --atomic-max-steps "${WORKFLOW_ATOMIC_MAX_STEPS:-25}" \
    --atomic-repeat-fail-threshold "${WORKFLOW_ATOMIC_REPEAT_FAIL_THRESHOLD:-3}" \
    --headless \
    "${LIMIT_ARGS[@]}"
) | tee "${RUN_ROOT}/workflow_benchmark.log"
