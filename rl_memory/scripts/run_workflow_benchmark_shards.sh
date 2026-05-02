#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BATCH_ROOT="${BATCH_ROOT:-${ROOT}/tasks/generated_workflow_split_batches/workflow_split_batch_v20}"
RUN_ROOT="${RUN_ROOT:-${ROOT}/rl_memory/runs/workflow_benchmark_shards}"
SPLIT="${SPLIT:-train}"
LIMIT="${LIMIT:-0}"
NUM_SHARDS="${NUM_SHARDS:-2}"
GPU_IDS="${GPU_IDS:-0,1}"
TAG="${TAG:-workflow_eval}"
SNAPSHOT_ROOT="${SNAPSHOT_ROOT:-${ROOT}}"
ENV_ACTIVATE="${ENV_ACTIVATE:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/envs/webagent/bin/activate}"
PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/inspire/hdd/project/exploration-topic/huaitianyu-253108120130/.cache/ms-playwright}"
AGENT_BACKEND="${AGENT_BACKEND:-hf_local}"
AGENT_MODEL="${AGENT_MODEL:-}"
AGENT_PROMPT_PROFILE="${AGENT_PROMPT_PROFILE:-webrl}"
AGENT_MAX_TOKENS="${AGENT_MAX_TOKENS:-96}"
AGENT_TEMPERATURE="${AGENT_TEMPERATURE:-0.0}"
AGENT_HF_USE_CHAT_TEMPLATE="${AGENT_HF_USE_CHAT_TEMPLATE:-true}"
AGENT_HF_DEVICE_MAP="${AGENT_HF_DEVICE_MAP:-auto}"
AGENT_HF_DTYPE="${AGENT_HF_DTYPE:-bfloat16}"
CANDIDATE_LIMIT="${CANDIDATE_LIMIT:-6}"
TARGET_BACKWARD_DEPTH="${TARGET_BACKWARD_DEPTH:-2}"
MODULE_MAX_TOKENS="${MODULE_MAX_TOKENS:-32}"
MODULE_TEMPERATURE="${MODULE_TEMPERATURE:-0.0}"
ATOMIC_MAX_STEPS="${ATOMIC_MAX_STEPS:-25}"
ATOMIC_REPEAT_FAIL_THRESHOLD="${ATOMIC_REPEAT_FAIL_THRESHOLD:-3}"
HEADLESS="${HEADLESS:-1}"

if [[ -z "${AGENT_MODEL}" ]]; then
  echo "AGENT_MODEL is required." >&2
  exit 1
fi

if [[ -f "${ENV_ACTIVATE}" ]]; then
  set +u
  source "${ENV_ACTIVATE}"
  set -u
fi

export PLAYWRIGHT_BROWSERS_PATH
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

mkdir -p "${RUN_ROOT}"
timestamp="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${RUN_ROOT}/${timestamp}_${TAG}_${SPLIT}"
GOAL_SHARD_DIR="${RUN_DIR}/goal_shards"
mkdir -p "${RUN_DIR}" "${GOAL_SHARD_DIR}"

python3 - "${BATCH_ROOT}" "${SPLIT}" "${NUM_SHARDS}" "${LIMIT}" "${GOAL_SHARD_DIR}" <<'PY'
import json
import sys
from pathlib import Path

batch_root = Path(sys.argv[1])
split = sys.argv[2]
num_shards = int(sys.argv[3])
limit = int(sys.argv[4])
out_dir = Path(sys.argv[5])
manifest = json.loads((batch_root / split / "manifest.json").read_text(encoding="utf-8"))
goals = list(manifest.get("goals", []))
if limit > 0:
    goals = goals[:limit]
for shard in range(num_shards):
    shard_goals = goals[shard::num_shards]
    (out_dir / f"shard{shard}.txt").write_text(
        "".join(f"{item['goal_id']}\n" for item in shard_goals),
        encoding="utf-8",
    )
print(json.dumps({"selected_goals": len(goals), "num_shards": num_shards}, ensure_ascii=False))
PY

IFS=',' read -r -a GPU_ARRAY <<< "${GPU_IDS}"
if [[ "${#GPU_ARRAY[@]}" -lt "${NUM_SHARDS}" ]]; then
  echo "Need at least NUM_SHARDS entries in GPU_IDS." >&2
  exit 1
fi

PIDS=()
STATUS=0

for (( shard=0; shard<NUM_SHARDS; shard++ )); do
  mapfile -t SHARD_GOALS < "${GOAL_SHARD_DIR}/shard${shard}.txt"
  if [[ "${#SHARD_GOALS[@]}" -eq 0 ]]; then
    continue
  fi

  shard_run_root="${RUN_DIR}/shard${shard}"
  shard_log="${RUN_DIR}/shard${shard}.log"
  mkdir -p "${shard_run_root}"

  cmd=(
    env
    "CUDA_VISIBLE_DEVICES=${GPU_ARRAY[$shard]}"
    "AGENT_BACKEND=${AGENT_BACKEND}"
    "AGENT_MODEL=${AGENT_MODEL}"
    "AGENT_PROMPT_PROFILE=${AGENT_PROMPT_PROFILE}"
    "AGENT_MAX_TOKENS=${AGENT_MAX_TOKENS}"
    "AGENT_TEMPERATURE=${AGENT_TEMPERATURE}"
    "AGENT_HF_USE_CHAT_TEMPLATE=${AGENT_HF_USE_CHAT_TEMPLATE}"
    "AGENT_HF_DEVICE_MAP=${AGENT_HF_DEVICE_MAP}"
    "AGENT_HF_DTYPE=${AGENT_HF_DTYPE}"
    "PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}"
    "PYTHONPATH=${PYTHONPATH}"
    python3 -u "${ROOT}/rl_memory/scripts/run_workflow_benchmark.py"
    --batch-root "${BATCH_ROOT}"
    --split "${SPLIT}"
    --output-root "${shard_run_root}"
    --runtime-root "${SNAPSHOT_ROOT}"
    --runtime-isolation per_goal
    --module-policy llm
    --atomic-policy agent
    --candidate-limit "${CANDIDATE_LIMIT}"
    --target-backward-depth "${TARGET_BACKWARD_DEPTH}"
    --module-max-tokens "${MODULE_MAX_TOKENS}"
    --module-temperature "${MODULE_TEMPERATURE}"
    --atomic-max-steps "${ATOMIC_MAX_STEPS}"
    --atomic-repeat-fail-threshold "${ATOMIC_REPEAT_FAIL_THRESHOLD}"
  )

  if [[ "${HEADLESS}" == "1" ]]; then
    cmd+=(--headless)
  fi

  for goal_id in "${SHARD_GOALS[@]}"; do
    [[ -n "${goal_id}" ]] || continue
    cmd+=(--goal-id "${goal_id}")
  done

  echo "Launching shard ${shard}/${NUM_SHARDS} on GPU ${GPU_ARRAY[$shard]} with ${#SHARD_GOALS[@]} goals"
  "${cmd[@]}" > "${shard_log}" 2>&1 &
  PIDS+=("$!")
done

echo "Run dir: ${RUN_DIR}"
echo "Launched ${#PIDS[@]} shard processes"

for pid in "${PIDS[@]}"; do
  wait "${pid}" || STATUS=$?
done

python3 - "${RUN_DIR}" "${SPLIT}" <<'PY'
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

run_dir = Path(sys.argv[1])
split = sys.argv[2]
records = []
agent_backend = ""
agent_model = ""
batch_root = ""
success_type_counts = Counter()
per_theme_buckets = defaultdict(list)
shard_summaries = []

for shard_dir in sorted(run_dir.glob("shard*")):
    summary_path = shard_dir / f"{split}_summary.json"
    if not summary_path.exists():
        continue
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    shard_summaries.append(str(summary_path))
    batch_root = batch_root or summary.get("batch_root", "")
    agent_backend = agent_backend or summary.get("agent_backend", "")
    agent_model = agent_model or summary.get("agent_model", "")
    for record in summary.get("records", []):
        records.append(record)
        success_type_counts[record.get("success_type", "unknown")] += 1
        per_theme_buckets[record.get("theme", "unknown")].append(record)

per_theme = {}
for theme, items in sorted(per_theme_buckets.items()):
    per_theme[theme] = {
        "goal_count": len(items),
        "success_count": sum(1 for item in items if item.get("success")),
        "average_composite_score": (
            sum(float(item.get("composite_score", 0.0)) for item in items) / len(items)
            if items else 0.0
        ),
    }

completed_goals = len(records)
success_count = sum(1 for item in records if item.get("success"))
combined = {
    "version": 1,
    "batch_root": batch_root,
    "split": split,
    "completed_goals": completed_goals,
    "total_goals": completed_goals,
    "final_success_count": success_count,
    "final_success_rate": (success_count / completed_goals) if completed_goals else 0.0,
    "average_composite_score": (
        sum(float(item.get("composite_score", 0.0)) for item in records) / completed_goals
        if completed_goals else 0.0
    ),
    "agent_backend": agent_backend,
    "agent_model": agent_model,
    "success_type_counts": dict(sorted(success_type_counts.items())),
    "per_theme": per_theme,
    "records": records,
    "shard_summaries": shard_summaries,
}

(run_dir / f"{split}_combined_summary.json").write_text(
    json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

md_lines = [
    "# Workflow Benchmark Combined Summary",
    "",
    f"- split: `{split}`",
    f"- completed_goals: {combined['completed_goals']}",
    f"- final_success_count: {combined['final_success_count']}",
    f"- final_success_rate: {combined['final_success_rate']:.4f}",
    f"- average_composite_score: {combined['average_composite_score']:.4f}",
    f"- agent_backend: `{agent_backend}`",
    f"- agent_model: `{agent_model}`",
    "",
    "## Per Theme",
]
for theme, item in per_theme.items():
    md_lines.append(
        f"- {theme}: success {item['success_count']}/{item['goal_count']}, average_composite_score={item['average_composite_score']:.4f}"
    )
(run_dir / f"{split}_combined_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print(json.dumps({"combined_records": completed_goals, "combined_success": success_count}, ensure_ascii=False))
PY

exit "${STATUS}"
