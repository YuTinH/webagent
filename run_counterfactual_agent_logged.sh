#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

THEMES="${THEMES:-newcomer,daily,career,leisure,crisis}"
LIMIT_PER_THEME="${LIMIT_PER_THEME:-20}"
SEED="${SEED:-42}"
IMPACT_PROFILE="${IMPACT_PROFILE:-strong}"
MAX_STEPS="${MAX_STEPS:-8}"
REPEAT_FAIL_THRESHOLD="${REPEAT_FAIL_THRESHOLD:-3}"
TASK_TIMEOUT_SEC="${TASK_TIMEOUT_SEC:-180}"
BASE_URL="${BASE_URL:-http://localhost:8014}"
CLEAN_MODE="${CLEAN_MODE:-true}"
OBFUSCATE_MODE="${OBFUSCATE_MODE:-false}"
DISTRACTOR_LEVEL="${DISTRACTOR_LEVEL:-off}"
HEADLESS="${HEADLESS:-true}"

# LLM env (required for agent mode)
AGENT_BASE_URL="${AGENT_BASE_URL:-}"
AGENT_MODEL="${AGENT_MODEL:-}"
AGENT_API_KEY="${AGENT_API_KEY:-}"
AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS:-200}"

usage() {
  cat <<'EOF'
Usage:
  AGENT_BASE_URL=... AGENT_MODEL=... AGENT_API_KEY=... ./run_counterfactual_agent_logged.sh [options]

Options:
  --themes CSV                  Default: newcomer,daily,career,leisure,crisis
  --limit-per-theme N           Default: 20
  --seed N                      Default: 42
  --impact-profile MODE         balanced|strong (default: strong)
  --max-steps N                 Default: 8
  --repeat-fail-threshold N     Default: 3
  --task-timeout-sec N          Default: 180
  --base-url URL                Default: http://localhost:8014
  --clean-mode true|false       Default: true
  --obfuscate-mode true|false   Default: false
  --distractor-level LEVEL      off|low|medium|high (default: off)
  --headless true|false         Default: true
  --max-tokens N                Default: 200
  --tag NAME                    Optional run tag appended to filenames
  -h, --help                    Show help
EOF
}

RUN_TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --themes) THEMES="$2"; shift 2 ;;
    --limit-per-theme) LIMIT_PER_THEME="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --impact-profile) IMPACT_PROFILE="$2"; shift 2 ;;
    --max-steps) MAX_STEPS="$2"; shift 2 ;;
    --repeat-fail-threshold) REPEAT_FAIL_THRESHOLD="$2"; shift 2 ;;
    --task-timeout-sec) TASK_TIMEOUT_SEC="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    --clean-mode) CLEAN_MODE="$2"; shift 2 ;;
    --obfuscate-mode) OBFUSCATE_MODE="$2"; shift 2 ;;
    --distractor-level) DISTRACTOR_LEVEL="$2"; shift 2 ;;
    --headless) HEADLESS="$2"; shift 2 ;;
    --max-tokens) AGENT_MAX_TOKENS="$2"; shift 2 ;;
    --tag) RUN_TAG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${AGENT_BASE_URL}" || -z "${AGENT_MODEL}" || -z "${AGENT_API_KEY}" ]]; then
  echo "Missing required env: AGENT_BASE_URL / AGENT_MODEL / AGENT_API_KEY" >&2
  exit 2
fi

if ! curl -fsS "${BASE_URL}/" >/dev/null 2>&1; then
  echo "Benchmark server is not reachable at ${BASE_URL}" >&2
  echo "Start it first: python3 server.py 8014" >&2
  exit 2
fi

mkdir -p logs
ts="$(date +%Y%m%d_%H%M%S)"
model_slug="$(echo "${AGENT_MODEL}" | tr '/:.' '___' | tr -cd 'A-Za-z0-9_-')"
tag_suffix=""
if [[ -n "${RUN_TAG}" ]]; then
  tag_suffix="_${RUN_TAG}"
fi

summary_json="audit_chain_counterfactual_agent_logged_${model_slug}_${ts}${tag_suffix}.json"
runtime_log="logs/runtime_counterfactual_agent_${model_slug}_${ts}${tag_suffix}.log"

echo "Model: ${AGENT_MODEL}"
echo "Summary: ${summary_json}"
echo "Runtime Log: ${runtime_log}"

cmd=(
  python3 -u chain_runner_counterfactual.py
  --mode agent
  --themes "${THEMES}"
  --limit-per-theme "${LIMIT_PER_THEME}"
  --seed "${SEED}"
  --impact-profile "${IMPACT_PROFILE}"
  --max-steps "${MAX_STEPS}"
  --repeat-fail-threshold "${REPEAT_FAIL_THRESHOLD}"
  --stop-on-first-fail-step
  --task-timeout-sec "${TASK_TIMEOUT_SEC}"
  --base-url "${BASE_URL}"
  --distractor-level "${DISTRACTOR_LEVEL}"
  --summary-json "${summary_json}"
)

if [[ "${HEADLESS}" == "true" ]]; then
  cmd+=(--headless)
fi
if [[ "${CLEAN_MODE}" == "true" ]]; then
  cmd+=(--clean-mode)
else
  cmd+=(--no-clean-mode)
fi
if [[ "${OBFUSCATE_MODE}" == "true" ]]; then
  cmd+=(--obfuscate-mode)
else
  cmd+=(--no-obfuscate-mode)
fi

AGENT_BASE_URL="${AGENT_BASE_URL}" \
AGENT_MODEL="${AGENT_MODEL}" \
AGENT_API_KEY="${AGENT_API_KEY}" \
AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS}" \
  "${cmd[@]}" 2>&1 | tee "${runtime_log}"

echo ""
echo "Done."
echo "- Summary JSON: ${summary_json}"
echo "- Runtime Log: ${runtime_log}"
