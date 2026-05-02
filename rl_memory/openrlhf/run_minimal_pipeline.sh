#!/usr/bin/env bash
set -euo pipefail

# Minimal end-to-end pipeline for a training machine.
# Assumes:
# - CUDA Python environment is active
# - local benchmark server can be started

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
SKIP_SETUP="${OPENRLHF_SKIP_SETUP:-0}"
TOPOLOGY_PROFILE="${TOPOLOGY_PROFILE:-single_gpu_stable}"
if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  IFS="," read -r -a _codex_visible_gpus <<< "${CUDA_VISIBLE_DEVICES}"
  DEFAULT_RAY_NUM_GPUS="${#_codex_visible_gpus[@]}"
else
  case "${TOPOLOGY_PROFILE}" in
    quad_gpu_fast)
      DEFAULT_RAY_NUM_GPUS=4
      ;;
    dual_gpu_balanced)
      DEFAULT_RAY_NUM_GPUS=2
      ;;
    *)
      DEFAULT_RAY_NUM_GPUS=1
      ;;
  esac
fi
RAY_NUM_GPUS="${RAY_NUM_GPUS:-${DEFAULT_RAY_NUM_GPUS}}"
RUNS_DIR="${ROOT}/rl_memory/runs"
TIMESTAMP="$(date +%F_%H-%M-%S)"
TRAIN_LOG_PATH="${TRAIN_LOG_PATH:-${RUNS_DIR}/openrlhf_train_${TIMESTAMP}.log}"
DATA_ROOT="${DATA_ROOT:-${ROOT}/rl_memory/openrlhf/data/clean_pool_quick50_50_20_25}"
RUN_SMOKE_TEST="${RUN_SMOKE_TEST:-1}"
SMOKE_INDEX="${SMOKE_INDEX:-0}"
SMOKE_MAX_ACTIONS="${SMOKE_MAX_ACTIONS:-1}"

mkdir -p "${RUNS_DIR}"

# Train on the clean benchmark first. Distactors/obfuscation can be enabled in
# later curriculum stages once the policy has learned the base interaction
# space.
export BENCHMARK_CLEAN_MODE="${BENCHMARK_CLEAN_MODE:-true}"
export BENCHMARK_OBFUSCATE="${BENCHMARK_OBFUSCATE:-false}"
export OPENRLHF_USE_ISOLATED_RUNTIME="${OPENRLHF_USE_ISOLATED_RUNTIME:-1}"

echo "[1/5] install / verify OpenRLHF runtime"
if [[ "${SKIP_SETUP}" == "1" ]]; then
  echo "skip setup: OPENRLHF_SKIP_SETUP=1"
else
  bash "${ROOT}/rl_memory/openrlhf/setup_openrlhf_env.sh"
fi

echo "[2/5] start benchmark server on 8014 if needed"
if ! "${PYTHON_BIN}" - <<'PY'
import urllib.request, sys
try:
    with urllib.request.urlopen("http://localhost:8014/", timeout=2) as r:
        sys.exit(0 if 200 <= r.status < 500 else 1)
except Exception:
    sys.exit(1)
PY
then
  nohup "${PYTHON_BIN}" "${ROOT}/server.py" 8014 > "${ROOT}/rl_memory/runs/server_8014.log" 2>&1 &
  sleep 3
fi

echo "[3/5] smoke test OpenRLHF adapter"
if [[ "${RUN_SMOKE_TEST}" == "1" ]]; then
  "${PYTHON_BIN}" "${ROOT}/rl_memory/openrlhf/smoke_test_agent_func.py" \
    --dataset "${DATA_ROOT}/train.jsonl" \
    --index "${SMOKE_INDEX}" \
    --max-actions "${SMOKE_MAX_ACTIONS}"
else
  echo "skip smoke test: RUN_SMOKE_TEST=0"
fi

echo "[4/5] start Ray"
echo "TOPOLOGY_PROFILE=${TOPOLOGY_PROFILE}"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-<unset>}"
echo "RAY_NUM_GPUS=${RAY_NUM_GPUS}"
ray stop || true
ray start --head --node-ip-address 0.0.0.0 --num-gpus "${RAY_NUM_GPUS}"

echo "[5/5] launch minimal clean-flow training"
echo "training log: ${TRAIN_LOG_PATH}"
echo "vllm sync backend: ${VLLM_SYNC_BACKEND:-<default from topology>}"
echo "vllm sync with ray: ${VLLM_SYNC_WITH_RAY:-<default from topology>}"
echo "use dynamic batch: ${USE_DYNAMIC_BATCH:-<default from topology>}"
echo "packing samples: ${PACKING_SAMPLES:-<default from topology>}"
echo "base model: ${BASE_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
echo "data root: ${DATA_ROOT}"
echo "save root: ${SAVE_ROOT:-${ROOT}/rl_memory/runs/openrlhf_qwen25_7b_clean_reinforce_v1}"
bash "${ROOT}/rl_memory/openrlhf/train_reinforce_clean.sh" 2>&1 | tee "${TRAIN_LOG_PATH}"
