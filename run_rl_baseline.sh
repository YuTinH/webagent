#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  cat <<'EOF'
Usage:
  ./run_rl_baseline.sh <model_or_path> [summary_json]

Examples:
  ./run_rl_baseline.sh zai-org/webrl-llama-3.1-8b audit_rl_webrl_llama.json
  AGENT_BACKEND=openai_compatible AGENT_BASE_URL=http://localhost:8000/v1 \
    ./run_rl_baseline.sh zai-org/webrl-glm-4-9b

Environment:
  AGENT_BACKEND=openai_compatible|hf_local
  AGENT_PROMPT_PROFILE=webrl
  AGENT_MAX_TOKENS=128
EOF
  exit 1
fi

MODEL_NAME="$1"
SUMMARY_JSON="${2:-audit_rl_baseline.json}"
LOG_FILE="${LOG_FILE:-${SUMMARY_JSON%.*}.log}"

export AGENT_MODEL="${AGENT_MODEL:-$MODEL_NAME}"
export AGENT_BACKEND="${AGENT_BACKEND:-hf_local}"
export AGENT_PROMPT_PROFILE="${AGENT_PROMPT_PROFILE:-webrl}"
export AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS:-128}"
export BENCHMARK_LOG_FILE="${BENCHMARK_LOG_FILE:-$LOG_FILE}"

python3 -u chain_runner_dynamic.py \
  --themes newcomer,daily,career,leisure,crisis \
  --limit-per-theme 20 \
  --headless \
  --max-steps 25 \
  --repeat-fail-threshold 3 \
  --distractor-level medium \
  --distractor-seed 20260220 \
  --obfuscation-seed 20260220 \
  --log-file "${BENCHMARK_LOG_FILE}" \
  --summary-json "${SUMMARY_JSON}"
