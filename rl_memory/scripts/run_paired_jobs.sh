#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ROOT="${RUN_ROOT:-${ROOT}/rl_memory/runs/paired_jobs}"
mkdir -p "${RUN_ROOT}"

PRIMARY_NAME="${PRIMARY_NAME:-primary}"
SECONDARY_NAME="${SECONDARY_NAME:-secondary}"
PRIMARY_CMD="${PRIMARY_CMD:-}"
SECONDARY_CMD="${SECONDARY_CMD:-}"
POLL_SECONDS="${POLL_SECONDS:-15}"
STOP_SECONDARY_ON_PRIMARY_EXIT="${STOP_SECONDARY_ON_PRIMARY_EXIT:-1}"

if [[ -z "${PRIMARY_CMD}" ]]; then
  echo "PRIMARY_CMD is required." >&2
  echo "Example:" >&2
  echo "  PRIMARY_CMD='bash /abs/path/to/run_baseline_full_2gpu.sh' \\" >&2
  echo "  SECONDARY_CMD='bash /abs/path/to/run_memorybank_local_2gpu.sh' \\" >&2
  echo "  bash /Users/masteryth/Documents/webagent/rl_memory/scripts/run_paired_jobs.sh" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d_%H%M%S)"
PRIMARY_LOG="${PRIMARY_LOG:-${RUN_ROOT}/${timestamp}_${PRIMARY_NAME}.log}"
SECONDARY_LOG="${SECONDARY_LOG:-${RUN_ROOT}/${timestamp}_${SECONDARY_NAME}.log}"
STATUS_FILE="${STATUS_FILE:-${RUN_ROOT}/${timestamp}_status.txt}"

primary_pid=""
secondary_pid=""

cleanup() {
  {
    echo "[$(date '+%F %T')] cleanup invoked"
    if [[ -n "${primary_pid}" ]] && kill -0 "${primary_pid}" 2>/dev/null; then
      echo "[$(date '+%F %T')] stopping primary pid=${primary_pid}"
      kill "${primary_pid}" 2>/dev/null || true
    fi
    if [[ -n "${secondary_pid}" ]] && kill -0 "${secondary_pid}" 2>/dev/null; then
      echo "[$(date '+%F %T')] stopping secondary pid=${secondary_pid}"
      kill "${secondary_pid}" 2>/dev/null || true
    fi
  } >> "${STATUS_FILE}"
}

trap cleanup INT TERM

echo "Primary log: ${PRIMARY_LOG}"
echo "Secondary log: ${SECONDARY_LOG}"
echo "Status file: ${STATUS_FILE}"

{
  echo "[$(date '+%F %T')] starting primary"
  echo "CMD=${PRIMARY_CMD}"
} >> "${STATUS_FILE}"

bash -lc "${PRIMARY_CMD}" > "${PRIMARY_LOG}" 2>&1 &
primary_pid=$!

if [[ -n "${SECONDARY_CMD}" ]]; then
  {
    echo "[$(date '+%F %T')] starting secondary"
    echo "CMD=${SECONDARY_CMD}"
  } >> "${STATUS_FILE}"
  bash -lc "${SECONDARY_CMD}" > "${SECONDARY_LOG}" 2>&1 &
  secondary_pid=$!
fi

primary_exit=0
secondary_exit=0

while true; do
  if ! kill -0 "${primary_pid}" 2>/dev/null; then
    wait "${primary_pid}" || primary_exit=$?
    {
      echo "[$(date '+%F %T')] primary exited code=${primary_exit}"
    } >> "${STATUS_FILE}"
    if [[ -n "${secondary_pid}" ]] && [[ "${STOP_SECONDARY_ON_PRIMARY_EXIT}" == "1" ]] && kill -0 "${secondary_pid}" 2>/dev/null; then
      {
        echo "[$(date '+%F %T')] stopping secondary because primary finished"
      } >> "${STATUS_FILE}"
      kill "${secondary_pid}" 2>/dev/null || true
      wait "${secondary_pid}" || secondary_exit=$?
      {
        echo "[$(date '+%F %T')] secondary exited code=${secondary_exit}"
      } >> "${STATUS_FILE}"
    elif [[ -n "${secondary_pid}" ]] && ! kill -0 "${secondary_pid}" 2>/dev/null; then
      wait "${secondary_pid}" || secondary_exit=$?
      {
        echo "[$(date '+%F %T')] secondary had already exited code=${secondary_exit}"
      } >> "${STATUS_FILE}"
    fi
    exit "${primary_exit}"
  fi

  if [[ -n "${secondary_pid}" ]] && ! kill -0 "${secondary_pid}" 2>/dev/null; then
    wait "${secondary_pid}" || secondary_exit=$?
    {
      echo "[$(date '+%F %T')] secondary exited early code=${secondary_exit}"
    } >> "${STATUS_FILE}"
    secondary_pid=""
  fi

  sleep "${POLL_SECONDS}"
done
