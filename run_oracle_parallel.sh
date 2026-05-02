#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LIMIT_PER_THEME=20
BASE_PORT=8114
THEMES_CSV="newcomer,daily,career,leisure,crisis"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
SUMMARY_JSON=""
HEADLESS=1
KEEP_WORKERS=1
TASK_TIMEOUT_SEC=180
DISTRACTOR_LEVEL="${BENCHMARK_DISTRACTOR_LEVEL:-off}"
DISTRACTOR_SEED="${BENCHMARK_DISTRACTOR_SEED:-20260220}"
OBFUSCATION_SEED="${BENCHMARK_OBFUSCATION_SEED:-20260220}"
STOP_ON_FIRST_FAIL_TASK=0
CLEAN_MODE=1
OBFUSCATE_MODE=0

usage() {
  cat <<'EOF'
Usage: ./run_oracle_parallel.sh [options]

Options:
  --limit-per-theme N           Chains per theme (default: 20)
  --themes CSV                  Comma-separated themes (default: newcomer,daily,career,leisure,crisis)
  --base-port N                 Worker base port (default: 8114)
  --run-id ID                   Custom run id (default: timestamp)
  --summary-json PATH           Final merged summary filename in repo root
  --task-timeout-sec N          Per-task timeout for each worker (default: 180)
  --distractor-level LEVEL      off|low|medium|high (default: env or off)
  --distractor-seed N           Distractor seed (default: env or 20260220)
  --obfuscation-seed N          Obfuscation seed (default: env or 20260220)
  --clean-mode                  Force clean mode on (default)
  --no-clean-mode               Disable clean mode
  --obfuscate-mode              Enable obfuscation mode
  --no-obfuscate-mode           Disable obfuscation mode (default)
  --stop-on-first-fail-task     Stop remaining tasks in a chain after first fail
  --no-headless                 Run headed browser
  --cleanup-workers             Remove worker dirs after merge
  -h, --help                    Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit-per-theme)
      LIMIT_PER_THEME="$2"
      shift 2
      ;;
    --themes)
      THEMES_CSV="$2"
      shift 2
      ;;
    --base-port)
      BASE_PORT="$2"
      shift 2
      ;;
    --run-id)
      RUN_ID="$2"
      shift 2
      ;;
    --summary-json)
      SUMMARY_JSON="$2"
      shift 2
      ;;
    --task-timeout-sec)
      TASK_TIMEOUT_SEC="$2"
      shift 2
      ;;
    --distractor-level)
      DISTRACTOR_LEVEL="$2"
      shift 2
      ;;
    --distractor-seed)
      DISTRACTOR_SEED="$2"
      shift 2
      ;;
    --obfuscation-seed)
      OBFUSCATION_SEED="$2"
      shift 2
      ;;
    --clean-mode)
      CLEAN_MODE=1
      shift
      ;;
    --no-clean-mode)
      CLEAN_MODE=0
      shift
      ;;
    --obfuscate-mode)
      OBFUSCATE_MODE=1
      shift
      ;;
    --no-obfuscate-mode)
      OBFUSCATE_MODE=0
      shift
      ;;
    --stop-on-first-fail-task)
      STOP_ON_FIRST_FAIL_TASK=1
      shift
      ;;
    --no-headless)
      HEADLESS=0
      shift
      ;;
    --cleanup-workers)
      KEEP_WORKERS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${SUMMARY_JSON}" ]]; then
  SUMMARY_JSON="audit_chain_oracle_parallel_${RUN_ID}.json"
fi

IFS=',' read -r -a THEMES <<< "${THEMES_CSV}"
if [[ ${#THEMES[@]} -eq 0 ]]; then
  echo "No themes provided." >&2
  exit 2
fi

WORK_BASE="${ROOT}/.parallel_runs/${RUN_ID}"
mkdir -p "${WORK_BASE}"

copy_workspace() {
  local dest="$1"
  mkdir -p "${dest}"
  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required for parallel worker setup." >&2
    exit 2
  fi
  rsync -a --delete \
    --exclude='.git' \
    --exclude='.parallel_runs' \
    --exclude='output' \
    --exclude='__pycache__' \
    --exclude='data.db' \
    --exclude='data.db-shm' \
    --exclude='data.db-wal' \
    --exclude='*.log' \
    "${ROOT}/" "${dest}/"
}

declare -a PIDS
declare -a THEME_LIST
declare -a PORT_LIST

echo "Run ID: ${RUN_ID}"
echo "Worker base: ${WORK_BASE}"
echo "Themes: ${THEMES[*]}"

for idx in "${!THEMES[@]}"; do
  theme="${THEMES[$idx]}"
  port=$((BASE_PORT + idx))
  worker_dir="${WORK_BASE}/${theme}"
  copy_workspace "${worker_dir}"

  (
    cd "${worker_dir}"

    python3 server.py "${port}" > "server_${theme}.log" 2>&1 &
    spid=$!
    cleanup() {
      kill "${spid}" >/dev/null 2>&1 || true
    }
    trap cleanup EXIT
    sleep 2

    cmd=(
      python3 -u chain_runner_oracle.py
      --themes "${theme}"
      --limit-per-theme "${LIMIT_PER_THEME}"
      --summary-json "summary_${theme}.json"
      --task-timeout-sec "${TASK_TIMEOUT_SEC}"
      --distractor-level "${DISTRACTOR_LEVEL}"
      --distractor-seed "${DISTRACTOR_SEED}"
      --obfuscation-seed "${OBFUSCATION_SEED}"
      --base-url "http://localhost:${port}"
    )

    if [[ "${HEADLESS}" -eq 1 ]]; then
      cmd+=(--headless)
    fi
    if [[ "${STOP_ON_FIRST_FAIL_TASK}" -eq 1 ]]; then
      cmd+=(--stop-on-first-fail-task)
    fi

    if [[ "${CLEAN_MODE}" -eq 1 ]]; then
      worker_clean="true"
      cmd+=(--clean-mode)
    else
      worker_clean="false"
      cmd+=(--no-clean-mode)
    fi
    if [[ "${OBFUSCATE_MODE}" -eq 1 ]]; then
      worker_obf="true"
      cmd+=(--obfuscate-mode)
    else
      worker_obf="false"
      cmd+=(--no-obfuscate-mode)
    fi

    BENCHMARK_CLEAN_MODE="${worker_clean}" \
    BENCHMARK_OBFUSCATE="${worker_obf}" \
      "${cmd[@]}" > "runner_${theme}.log" 2>&1
  ) &

  pid="$!"
  PIDS+=("${pid}")
  THEME_LIST+=("${theme}")
  PORT_LIST+=("${port}")
  echo "Started worker theme=${theme} port=${port} pid=${pid}"
done

FAILURES=0
for idx in "${!PIDS[@]}"; do
  pid="${PIDS[$idx]}"
  theme="${THEME_LIST[$idx]}"
  if wait "${pid}"; then
    echo "Worker done: ${theme}"
  else
    echo "Worker failed: ${theme}" >&2
    FAILURES=$((FAILURES + 1))
  fi
done

WORK_BASE="${WORK_BASE}" \
ROOT="${ROOT}" \
SUMMARY_JSON="${SUMMARY_JSON}" \
THEMES_CSV="${THEMES_CSV}" \
PORTS_CSV="$(IFS=,; echo "${PORT_LIST[*]}")" \
python3 - <<'PY'
import json
import os
from pathlib import Path

work_base = Path(os.environ["WORK_BASE"])
root = Path(os.environ["ROOT"])
summary_json = os.environ["SUMMARY_JSON"]
themes = [t for t in os.environ["THEMES_CSV"].split(",") if t]
ports = [p for p in os.environ["PORTS_CSV"].split(",") if p]

chains = []
overall_score = 0
overall_max = 0
total_tasks = 0
passed_tasks = 0
total_planned_tasks = 0
total_step_earned = 0.0
total_step_max = 0.0
elapsed_sec = 0.0
run_configs = []
worker_reports = []

for idx, theme in enumerate(themes):
    path = work_base / theme / f"summary_{theme}.json"
    if not path.exists():
        worker_reports.append({
            "theme": theme,
            "port": int(ports[idx]) if idx < len(ports) else None,
            "summary": None,
            "status": "missing",
        })
        continue

    data = json.loads(path.read_text(encoding="utf-8"))
    worker_reports.append({
        "theme": theme,
        "port": int(ports[idx]) if idx < len(ports) else None,
        "summary": str(path),
        "status": "ok",
        "chains": len(data.get("chains", [])),
        "planned_tasks": data.get("total_planned_tasks", 0),
        "passed_tasks": data.get("passed_tasks", 0),
    })

    chains.extend(data.get("chains", []))
    overall_score += int(data.get("overall_score", 0))
    overall_max += int(data.get("overall_max", 0))
    total_tasks += int(data.get("total_tasks", 0))
    passed_tasks += int(data.get("passed_tasks", 0))
    total_planned_tasks += int(data.get("total_planned_tasks", 0))
    total_step_earned += float(data.get("total_step_earned", 0.0))
    total_step_max += float(data.get("total_step_max", 0.0))
    elapsed_sec += float(data.get("elapsed_sec", 0.0))

    rc = data.get("run_config", {})
    if isinstance(rc, dict):
        run_configs.append(rc)

passed_chains = sum(1 for c in chains if c.get("success"))
total_chains = len(chains)

step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
flow_score = (passed_chains / total_chains * 100.0) if total_chains else 0.0
weighted_score = (overall_score / overall_max * 100.0) if overall_max else 0.0

merged = {
    "run_config": {
        "parallel": True,
        "themes": themes,
        "ports": [int(p) for p in ports] if ports else [],
        "workers_root": str(work_base),
        "worker_run_configs": run_configs,
    },
    "workers": worker_reports,
    "chains": chains,
    "overall_score": overall_score,
    "overall_max": overall_max,
    "total_tasks": total_tasks,
    "passed_tasks": passed_tasks,
    "total_planned_tasks": total_planned_tasks,
    "total_step_earned": total_step_earned,
    "total_step_max": total_step_max,
    "metrics": {
        "step_score": step_score,
        "task_score": task_score,
        "flow_score": flow_score,
        "weighted_score": weighted_score,
    },
    "elapsed_sec_sum_workers": elapsed_sec,
}

out = root / summary_json
out.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Merged summary: {out}")
print(f"Chains: {passed_chains}/{total_chains}")
print(f"Tasks: {passed_tasks}/{total_planned_tasks}")
print(f"Weighted score: {weighted_score:.2f}/100")
PY

if [[ "${KEEP_WORKERS}" -eq 0 ]]; then
  rm -rf "${WORK_BASE}"
  echo "Removed worker directories: ${WORK_BASE}"
else
  echo "Worker directories kept at: ${WORK_BASE}"
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  exit 1
fi
