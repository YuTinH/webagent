#!/usr/bin/env bash
set -euo pipefail

export MEMORYBANK_PROFILE="${MEMORYBANK_PROFILE:-slim}"
export RUN_ROOT="${RUN_ROOT:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/webagent/rl_memory/runs/memorybank_slim_qwen25_7b_gpu23}"
export SERVER_PORT="${SERVER_PORT:-8022}"
export AGENT_MEMORYBANK_TOP_K="${AGENT_MEMORYBANK_TOP_K:-2}"
export AGENT_MEMORYBANK_ALLOWED_TYPES="${AGENT_MEMORYBANK_ALLOWED_TYPES:-strategy,pitfall}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec bash "${ROOT}/rl_memory/memory_baselines/memorybank/run_memorybank_local_2gpu.sh"
