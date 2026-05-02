#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_PATH="${VENV_PATH:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/envs/webagent/bin/activate}"

GPU_GROUP_A="${GPU_GROUP_A:-0,1}"
GPU_GROUP_B="${GPU_GROUP_B:-2,3}"

RUN_BASE="${RUN_BASE:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs}"

BASELINE_RUN_ROOT="${BASELINE_RUN_ROOT:-${RUN_BASE}/plain_baseline_qwen25_7b_gpu01_clean}"
REFLEXION_RUN_ROOT="${REFLEXION_RUN_ROOT:-${RUN_BASE}/reflexion_qwen25_7b_gpu23_clean}"
MEMORYBANK_RUN_ROOT="${MEMORYBANK_RUN_ROOT:-${RUN_BASE}/memorybank_qwen25_7b_gpu01_clean}"
TRAGRAG_RUN_ROOT="${TRAGRAG_RUN_ROOT:-${RUN_BASE}/trajectory_rag_qwen25_7b_gpu23_clean}"

BASELINE_SERVER_PORT="${BASELINE_SERVER_PORT:-8048}"
REFLEXION_SERVER_PORT="${REFLEXION_SERVER_PORT:-8016}"
MEMORYBANK_SERVER_PORT="${MEMORYBANK_SERVER_PORT:-8020}"
TRAGRAG_SERVER_PORT="${TRAGRAG_SERVER_PORT:-8024}"

timestamp="$(date +%Y%m%d_%H%M%S)"
STATUS_DIR="${STATUS_DIR:-${RUN_BASE}/suite_status}"
mkdir -p "${STATUS_DIR}"
STATUS_FILE="${STATUS_DIR}/${timestamp}_2x2gpu_eval_suite.status"

if [[ -f "${VENV_PATH}" ]]; then
  # shellcheck disable=SC1090
  source "${VENV_PATH}"
fi

run_pair() {
  local primary_name="$1"
  local primary_cmd="$2"
  local secondary_name="$3"
  local secondary_cmd="$4"

  echo "[$(date '+%F %T')] starting pair: ${primary_name} + ${secondary_name}" | tee -a "${STATUS_FILE}"

  bash -lc "${primary_cmd}" &
  local pid_a=$!
  bash -lc "${secondary_cmd}" &
  local pid_b=$!

  local exit_a=0
  local exit_b=0
  wait "${pid_a}" || exit_a=$?
  wait "${pid_b}" || exit_b=$?

  echo "[$(date '+%F %T')] pair done: ${primary_name}=${exit_a} ${secondary_name}=${exit_b}" | tee -a "${STATUS_FILE}"

  if [[ "${exit_a}" -ne 0 || "${exit_b}" -ne 0 ]]; then
    echo "pair failed" | tee -a "${STATUS_FILE}"
    exit 1
  fi
}

BASELINE_CMD="cd ${ROOT} && CUDA_VISIBLE_DEVICES=${GPU_GROUP_A} RUN_ROOT=${BASELINE_RUN_ROOT} SERVER_PORT=${BASELINE_SERVER_PORT} bash ${ROOT}/rl_memory/test_time_methods/plain/run_plain_baseline_local_2gpu.sh"
REFLEXION_CMD="cd ${ROOT} && CUDA_VISIBLE_DEVICES=${GPU_GROUP_B} RUN_ROOT=${REFLEXION_RUN_ROOT} SERVER_PORT=${REFLEXION_SERVER_PORT} bash ${ROOT}/rl_memory/memory_baselines/reflexion/run_reflexion_local_2gpu.sh"
MEMORYBANK_CMD="cd ${ROOT} && CUDA_VISIBLE_DEVICES=${GPU_GROUP_A} RUN_ROOT=${MEMORYBANK_RUN_ROOT} SERVER_PORT=${MEMORYBANK_SERVER_PORT} bash ${ROOT}/rl_memory/memory_baselines/memorybank/run_memorybank_local_2gpu.sh"
TRAGRAG_CMD="cd ${ROOT} && CUDA_VISIBLE_DEVICES=${GPU_GROUP_B} RUN_ROOT=${TRAGRAG_RUN_ROOT} SERVER_PORT=${TRAGRAG_SERVER_PORT} bash ${ROOT}/rl_memory/memory_baselines/trajectory_rag/run_trajectory_rag_local_2gpu.sh"

run_pair "baseline" "${BASELINE_CMD}" "reflexion" "${REFLEXION_CMD}"
run_pair "memorybank" "${MEMORYBANK_CMD}" "trajectory_rag" "${TRAGRAG_CMD}"

echo "[$(date '+%F %T')] all pairs completed" | tee -a "${STATUS_FILE}"
