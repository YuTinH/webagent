#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LIMIT_PER_THEME=20
BASE_PORT=8214
THEMES_CSV="newcomer,daily,career,leisure,crisis"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
SUMMARY_JSON=""
HEADLESS=1
KEEP_WORKERS=1
TASK_TIMEOUT_SEC=180
DISTRACTOR_LEVEL="${BENCHMARK_DISTRACTOR_LEVEL:-off}"
DISTRACTOR_SEED="${BENCHMARK_DISTRACTOR_SEED:-20260220}"
OBFUSCATION_SEED="${BENCHMARK_OBFUSCATION_SEED:-20260220}"
CLEAN_MODE=1
OBFUSCATE_MODE=0
SEED=42
TARGET_KEY=""
IMPACT_PROFILE="balanced"

usage() {
  cat <<'EOF'
Usage: ./run_counterfactual_parallel.sh [options]

Options:
  --limit-per-theme N           Chains per theme (default: 20)
  --themes CSV                  Comma-separated themes (default: newcomer,daily,career,leisure,crisis)
  --base-port N                 Worker base port (default: 8214)
  --run-id ID                   Custom run id (default: timestamp)
  --summary-json PATH           Final merged summary filename in repo root
  --task-timeout-sec N          Per-task timeout for each worker (default: 180)
  --seed N                      Counterfactual mutation seed (default: 42)
  --target-key KEY              Force mutate this initial_state key (default: auto)
  --impact-profile MODE         balanced|strong (default: balanced)
  --distractor-level LEVEL      off|low|medium|high (default: env or off)
  --distractor-seed N           Distractor seed (default: env or 20260220)
  --obfuscation-seed N          Obfuscation seed (default: env or 20260220)
  --clean-mode                  Force clean mode on (default)
  --no-clean-mode               Disable clean mode
  --obfuscate-mode              Enable obfuscation mode
  --no-obfuscate-mode           Disable obfuscation mode (default)
  --no-headless                 Run headed browser
  --cleanup-workers             Remove worker dirs after merge
  -h, --help                    Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit-per-theme) LIMIT_PER_THEME="$2"; shift 2 ;;
    --themes) THEMES_CSV="$2"; shift 2 ;;
    --base-port) BASE_PORT="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --summary-json) SUMMARY_JSON="$2"; shift 2 ;;
    --task-timeout-sec) TASK_TIMEOUT_SEC="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --target-key) TARGET_KEY="$2"; shift 2 ;;
    --impact-profile) IMPACT_PROFILE="$2"; shift 2 ;;
    --distractor-level) DISTRACTOR_LEVEL="$2"; shift 2 ;;
    --distractor-seed) DISTRACTOR_SEED="$2"; shift 2 ;;
    --obfuscation-seed) OBFUSCATION_SEED="$2"; shift 2 ;;
    --clean-mode) CLEAN_MODE=1; shift ;;
    --no-clean-mode) CLEAN_MODE=0; shift ;;
    --obfuscate-mode) OBFUSCATE_MODE=1; shift ;;
    --no-obfuscate-mode) OBFUSCATE_MODE=0; shift ;;
    --no-headless) HEADLESS=0; shift ;;
    --cleanup-workers) KEEP_WORKERS=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${SUMMARY_JSON}" ]]; then
  SUMMARY_JSON="audit_chain_counterfactual_parallel_${RUN_ID}.json"
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
    cleanup() { kill "${spid}" >/dev/null 2>&1 || true; }
    trap cleanup EXIT
    sleep 2

    cmd=(
      python3 -u chain_runner_counterfactual.py
      --themes "${theme}"
      --limit-per-theme "${LIMIT_PER_THEME}"
      --summary-json "summary_${theme}.json"
      --task-timeout-sec "${TASK_TIMEOUT_SEC}"
      --base-url "http://localhost:${port}"
      --seed "${SEED}"
      --impact-profile "${IMPACT_PROFILE}"
      --distractor-level "${DISTRACTOR_LEVEL}"
      --distractor-seed "${DISTRACTOR_SEED}"
      --obfuscation-seed "${OBFUSCATION_SEED}"
    )
    if [[ "${HEADLESS}" -eq 1 ]]; then cmd+=(--headless); fi
    if [[ -n "${TARGET_KEY}" ]]; then cmd+=(--target-key "${TARGET_KEY}"); fi
    if [[ "${CLEAN_MODE}" -eq 1 ]]; then cmd+=(--clean-mode); else cmd+=(--no-clean-mode); fi
    if [[ "${OBFUSCATE_MODE}" -eq 1 ]]; then cmd+=(--obfuscate-mode); else cmd+=(--no-obfuscate-mode); fi

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
LIMIT_PER_THEME="${LIMIT_PER_THEME}" \
SEED="${SEED}" \
TARGET_KEY="${TARGET_KEY}" \
IMPACT_PROFILE="${IMPACT_PROFILE}" \
python3 - <<'PY'
import json
import os
from pathlib import Path

work_base = Path(os.environ["WORK_BASE"])
root = Path(os.environ["ROOT"])
summary_json = os.environ["SUMMARY_JSON"]
themes = [t for t in os.environ["THEMES_CSV"].split(",") if t]
ports = [p for p in os.environ["PORTS_CSV"].split(",") if p]
limit_per_theme = int(os.environ.get("LIMIT_PER_THEME", "0") or 0)
seed = int(os.environ.get("SEED", "42") or 42)
target_key = os.environ.get("TARGET_KEY", "")
impact_profile = os.environ.get("IMPACT_PROFILE", "balanced")

comparisons = []
workers = []
for idx, theme in enumerate(themes):
    p = work_base / theme / f"summary_{theme}.json"
    if not p.exists():
        workers.append({"theme": theme, "port": int(ports[idx]) if idx < len(ports) else None, "missing_summary": True})
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    comps = data.get("comparisons") or []
    comparisons.extend(comps)
    workers.append({
        "theme": theme,
        "port": int(ports[idx]) if idx < len(ports) else None,
        "chains_total": int((data.get("metrics") or {}).get("chains_total", len(comps))),
        "chains_impacted": int((data.get("metrics") or {}).get("chains_impacted", 0)),
        "summary_json": str(p),
    })

chains_total = len(comparisons)
chains_impacted = sum(1 for c in comparisons if c.get("impacted"))
baseline_pass = sum(int((c.get("baseline") or {}).get("passed_tasks", 0)) for c in comparisons)
baseline_total = sum(int((c.get("baseline") or {}).get("total_tasks", 0)) for c in comparisons)
counter_pass = sum(int((c.get("counterfactual") or {}).get("passed_tasks", 0)) for c in comparisons)
counter_total = sum(int((c.get("counterfactual") or {}).get("total_tasks", 0)) for c in comparisons)
task_drop_sum = sum(float((c.get("delta") or {}).get("task_drop", 0.0)) for c in comparisons)
step_drop_sum = sum(float((c.get("delta") or {}).get("step_drop", 0.0)) for c in comparisons)

final = {
    "run_config": {
        "themes": themes,
        "limit_per_theme": limit_per_theme or None,
        "seed": seed,
        "target_key": target_key,
        "impact_profile": impact_profile,
        "workers_base": str(work_base),
    },
    "workers": workers,
    "comparisons": comparisons,
    "metrics": {
        "chains_total": chains_total,
        "chains_impacted": chains_impacted,
        "impact_rate": (chains_impacted / chains_total * 100.0) if chains_total else 0.0,
        "baseline_task_score": (baseline_pass / baseline_total * 100.0) if baseline_total else 0.0,
        "counterfactual_task_score": (counter_pass / counter_total * 100.0) if counter_total else 0.0,
        "avg_task_drop": (task_drop_sum / chains_total) if chains_total else 0.0,
        "avg_step_drop": (step_drop_sum / chains_total) if chains_total else 0.0,
    },
}

out_path = root / summary_json
out_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Merged summary -> {out_path}")
print(json.dumps(final["metrics"], ensure_ascii=False, indent=2))
PY

if [[ "${KEEP_WORKERS}" -eq 0 ]]; then
  rm -rf "${WORK_BASE}"
  echo "Cleaned worker dir: ${WORK_BASE}"
fi

if [[ ${FAILURES} -ne 0 ]]; then
  exit 1
fi
