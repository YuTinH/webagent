#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

MODE="${MODE:-pilot}"
THEMES="${THEMES:-newcomer,daily,career,leisure,crisis}"
INPUT_ROOT="${INPUT_ROOT:-${ROOT}}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT}/rl_memory/runs/instruction_rewrite_glm_v1}"
MODEL="${MODEL:-glm-4.6}"
TEMPERATURE="${TEMPERATURE:-0.4}"
MAX_RETRIES="${MAX_RETRIES:-3}"
MAX_CHAINS="${MAX_CHAINS:-}"

export REWRITE_BASE_URL="${REWRITE_BASE_URL:-${AGENT_BASE_URL:-https://open.bigmodel.cn/api/paas/v4}}"
export REWRITE_API_KEY="${REWRITE_API_KEY:-${AGENT_API_KEY:-}}"
export REWRITE_DISABLE_THINKING="${REWRITE_DISABLE_THINKING:-true}"

if [[ -z "${REWRITE_API_KEY}" ]]; then
  echo "Missing REWRITE_API_KEY or AGENT_API_KEY" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

args=(
  python3 -u "${ROOT}/rl_memory/scripts/rewrite_sampled_instructions.py"
  --input-root "${INPUT_ROOT}"
  --output-root "${OUTPUT_ROOT}"
  --themes "${THEMES}"
  --backend openai_compatible
  --model "${MODEL}"
  --temperature "${TEMPERATURE}"
  --max-retries "${MAX_RETRIES}"
)

if [[ "${MODE}" == "pilot" ]]; then
  args+=(--max-chains "${MAX_CHAINS:-5}")
elif [[ "${MODE}" == "full" ]]; then
  if [[ -n "${MAX_CHAINS}" ]]; then
    args+=(--max-chains "${MAX_CHAINS}")
  fi
else
  echo "Unsupported MODE=${MODE}. Use MODE=pilot or MODE=full." >&2
  exit 1
fi

if [[ "${OVERWRITE:-0}" == "1" ]]; then
  args+=(--overwrite)
fi

echo "REWRITE_BASE_URL=${REWRITE_BASE_URL}"
echo "MODEL=${MODEL}"
echo "MODE=${MODE}"
echo "THEMES=${THEMES}"
echo "OUTPUT_ROOT=${OUTPUT_ROOT}"
echo "REWRITE_DISABLE_THINKING=${REWRITE_DISABLE_THINKING}"

"${args[@]}"
