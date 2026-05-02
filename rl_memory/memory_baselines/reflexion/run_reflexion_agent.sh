#!/usr/bin/env bash
set -euo pipefail

export AGENT_MEMORY_METHOD=reflexion
export AGENT_REFLEXION_STORE="${AGENT_REFLEXION_STORE:-/Users/masteryth/Documents/webagent/rl_memory/memory_baselines/reflexion/runs/default_reflections.json}"
export AGENT_REFLEXION_TOP_K="${AGENT_REFLEXION_TOP_K:-3}"

# Example backend defaults. Override these before running as needed.
export AGENT_BACKEND="${AGENT_BACKEND:-openai_compatible}"
export AGENT_MODEL="${AGENT_MODEL:-glm-4.6}"
export AGENT_BASE_URL="${AGENT_BASE_URL:-https://open.bigmodel.cn/api/paas/v4}"
export AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS:-256}"
export AGENT_TEMPERATURE="${AGENT_TEMPERATURE:-0.0}"
export AGENT_DISABLE_THINKING="${AGENT_DISABLE_THINKING:-true}"

python3 /Users/masteryth/Documents/webagent/chain_runner_dynamic.py "$@"
