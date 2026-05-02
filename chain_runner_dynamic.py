import json
import os
import subprocess
import time
import random
import sys
import argparse
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from agent.llm_client import build_client
from llm_runner import execute_agent_task
from runtime_paths import server_base_url, state_path, tasks_dir


def _preparse_cli_value(flag_name):
    for i, arg in enumerate(sys.argv[1:]):
        if arg == flag_name and i + 2 <= len(sys.argv[1:]):
            return sys.argv[1:][i + 1]
        if arg.startswith(flag_name + "="):
            return arg.split("=", 1)[1]
    return None


def _flag_present(flag_name):
    return flag_name in sys.argv[1:]


def _resolve_log_file():
    env_path = (os.environ.get("BENCHMARK_LOG_FILE") or "").strip()
    if env_path:
        return env_path

    cli_log = (_preparse_cli_value("--log-file") or "").strip()
    if cli_log:
        return cli_log

    summary_path = (_preparse_cli_value("--summary-json") or "").strip()
    if summary_path:
        base, ext = os.path.splitext(summary_path)
        return (base if ext else summary_path) + ".log"

    return "evaluation.log"


def _resolve_log_mode():
    env_mode = (os.environ.get("BENCHMARK_LOG_MODE") or "").strip().lower()
    if env_mode in {"a", "append"}:
        return "a"
    if _flag_present("--append-log"):
        return "a"
    return "w"


def _scenario_root() -> Path:
    raw = (os.environ.get("BENCHMARK_SCENARIO_ROOT") or ".").strip()
    return Path(raw).expanduser().resolve()

# Built-in Logger
class Logger(object):
    def __init__(self, filename="evaluation.log", mode="w"):
        self.terminal = sys.stdout
        self.filename = filename
        log_dir = os.path.dirname(os.path.abspath(filename))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        self.log = open(filename, mode, encoding="utf-8")
    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush() 
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()
    def isatty(self):
        try:
            return bool(self.terminal.isatty())
        except Exception:
            return False

_LOG_FILE = _resolve_log_file()
_LOG_MODE = _resolve_log_mode()
sys.stdout = Logger(_LOG_FILE, mode=_LOG_MODE)
sys.stderr = sys.stdout

print(f"\n{'='*60}")
print(f"NEW ENGLISH BENCHMARK SESSION AT {time.ctime()}")
print(f"LOG FILE: {_LOG_FILE}")
print(f"{'='*60}")

def load_scenarios():
    themes = ["newcomer", "daily", "career", "leisure", "crisis"]
    all_scenarios = {}
    root = _scenario_root()
    for theme in themes:
        path = root / f"sampled_{theme}.json"
        if path.exists():
            with open(path) as f:
                for s in json.load(f): all_scenarios[s['chain_id']] = s
    return all_scenarios

_MEM_KEY_RE = re.compile(r"mem\('([^']+)'\)")


def _parse_int_env(name, default=None):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _apply_runtime_url_flags(raw_url, is_clean, is_obfuscate, distractor_level, distractor_seed, obfuscation_seed):
    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for k in ["clean", "obfuscate", "dlevel", "dseed", "obf_seed"]:
        query.pop(k, None)

    if is_clean:
        query["clean"] = "true"
    if is_obfuscate:
        query["obfuscate"] = "true"
        if obfuscation_seed is not None:
            query["obf_seed"] = str(obfuscation_seed)
    if not is_clean and distractor_level:
        query["dlevel"] = str(distractor_level)
    if not is_clean and distractor_seed is not None:
        query["dseed"] = str(distractor_seed)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _server_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return f"{server_base_url()}{path}"


def _derive_hardened_checkpoints(criteria):
    checkpoints = []
    for i, crit in enumerate(criteria or []):
        crit = str(crit).strip()
        if not crit:
            continue
        cp_prefix = f"crit_{i+1}"
        mem_match = _MEM_KEY_RE.search(crit)
        can_add_intermediate = mem_match is not None and "!= ''" not in crit
        if can_add_intermediate:
            key = mem_match.group(1)
            cp_state_id = f"{cp_prefix}_state"
            checkpoints.append(
                {
                    "id": cp_state_id,
                    "name": f"Criterion {i+1} state set",
                    "assertion": f"mem('{key}') != ''",
                    "weight": 0.4,
                    "required": True,
                    "depends_on": [],
                }
            )
            checkpoints.append(
                {
                    "id": f"{cp_prefix}_final",
                    "name": f"Criterion {i+1} final",
                    "assertion": crit,
                    "weight": 0.6,
                    "required": True,
                    "depends_on": [cp_state_id],
                }
            )
        else:
            checkpoints.append(
                {
                    "id": f"{cp_prefix}_final",
                    "name": f"Criterion {i+1} final",
                    "assertion": crit,
                    "weight": 1.0,
                    "required": True,
                    "depends_on": [],
                }
            )
    return checkpoints


def _classify_step_error(step_error_message):
    msg = (step_error_message or "").lower()
    if "unknown command" in msg or "unknown action" in msg:
        return "invalid_action_format"
    if "bare_selector_token" in msg or "xpath_mixed_selector" in msg or "malformed_selector_" in msg:
        return "selector_parse_error"
    if (
        "element is not a <select> element" in msg
        or "type_on_checkable_input" in msg
        or "select_on_checkable_input" in msg
        or "missing_action_value" in msg
        or "click_takes_single_selector" in msg
    ):
        return "action_type_error"
    if "unexpected token" in msg and "selector" in msg:
        return "selector_parse_error"
    if "not a valid selector" in msg:
        return "selector_parse_error"
    if "intercepts pointer events" in msg:
        return "overlay_block"
    if "did not find some options" in msg:
        return "option_not_found"
    if "element is not editable" in msg:
        return "non_editable_target"
    if "timeout" in msg and "waiting for locator" in msg:
        return "element_not_found_or_timeout"
    if "timeout" in msg:
        return "step_timeout"
    return "executor_runtime_error"


def _derive_failure_classification(task_ok, agent_result, end_reason):
    if task_ok:
        return "none", "none"
    bucket = agent_result.get("failure_bucket", "")
    category = agent_result.get("failure_category", "")
    if bucket and category:
        return bucket, category

    step_error_abort = bool(agent_result.get("step_error_abort", False))
    step_error_message = str(agent_result.get("step_error_message", "") or agent_result.get("last_step_status", ""))
    repeat_fail = bool(agent_result.get("repeat_fail", False))
    end_reason = end_reason or ""
    if step_error_abort or step_error_message.startswith("Error:"):
        return "executor_failure", _classify_step_error(step_error_message)
    if repeat_fail or end_reason.startswith("repeat_action_threshold"):
        return "ability_failure", "repeat_action_loop"
    if end_reason == "agent_done":
        return "ability_failure", "premature_done"
    if end_reason == "criteria_or_checkpoint_failed":
        return "ability_failure", "criteria_or_checkpoint_failed"
    if end_reason:
        return "ability_failure", end_reason
    return "unknown_failure", "unknown"

def patch_trace(task_id, instruction, criteria=[], step_payload=None):
    trace_path = tasks_dir() / task_id / "oracle_trace.json"
    if not os.path.exists(trace_path): return
    with open(trace_path, 'r') as f: trace = json.load(f)

    has_override = isinstance(step_payload, dict) and isinstance(step_payload.get("oracle_trace_override"), list)
    if has_override:
        trace["steps"] = step_payload["oracle_trace_override"]
    
    if (not has_override) and task_id == "A1-find-home":
        if isinstance(step_payload, dict) and isinstance(step_payload.get("template_info"), dict):
            slot_values = step_payload["template_info"].get("slot_values") or {}
            sort_order = str(slot_values.get("sort_order", "price_low")).strip() or "price_low"
            target_property_id = str(slot_values.get("target_property_id", "PROP-EXT-0")).strip() or "PROP-EXT-0"
            lease_term = str(slot_values.get("lease_term", "12")).strip() or "12"
            trace["steps"] = [
                {"t": 0, "act": "open", "url": _server_url("/housing.local/index.html?clean=true")},
                {"t": 1, "act": "select", "selector": "#sort-order", "value": sort_order},
                {"t": 2, "act": "open", "url": _server_url(f"/housing.local/property.html?id={target_property_id}&clean=true")},
                {"t": 3, "act": "select", "selector": "#lease-term", "value": lease_term},
                {"t": 4, "act": "click", "selector": "#apply-btn"},
            ]
        elif any(k in instruction.lower() for k in ["cheapest", "least"]):
            trace['steps'] = [{"t": 0, "act": "open", "url": _server_url("/housing.local/index.html")}, {"t": 1, "act": "select", "selector": "#sort-order", "value": "price_low"}]
        else:
            for step in trace['steps']:
                if "property-card" in step.get('selector', ''): step['selector'] = ".property-card:has(.property-title:has-text('Premium Living'))"

    if (not has_override) and task_id == "A3-utility-setup":
        trace['steps'] = [{"t": 0, "act": "open", "url": _server_url("/energy.local/setup.html")}]

    if (not has_override) and task_id == "B1-shopping":
        target_url = _server_url("/shop.local/product.html?id=KB-8801") if "keyboard" in instruction.lower() else _server_url("/shop.local/product.html?id=WM-5521")
        trace['steps'] = [{"t": 0, "act": "open", "url": target_url}]

    if (not has_override) and task_id == "D3-autopay":
        trace['steps'] = [{"t": 0, "act": "open", "url": _server_url("/bank.local/autopay.html")}]

    if (not has_override) and task_id == "M1-lost-card":
        trace['steps'] = [{"t": 0, "act": "open", "url": _server_url("/bank.local/cards.html")}]

    if (not has_override) and task_id == "Z7-complex-autopay":
        # PURE ENGLISH PATH
        trace['steps'] = [
            {"t": 0, "act": "open", "url": _server_url("/work.local/email.html")},
            {"t": 1, "act": "type", "selector": "#email-search", "value": "Electricity"},
            {"t": 2, "act": "click", "selector": ".search-box button"},
            {"t": 3, "act": "wait", "selector": ".email-item"},
            {"t": 4, "act": "open", "url": _server_url("/bank.local/autopay.html")},
            {"t": 5, "act": "type", "selector": "#account-number", "value": "UTIL-998877"},
            {"t": 6, "act": "click", "selector": "#setup-btn"}
        ]

    # RUNTIME URL FLAGS
    is_clean = os.environ.get("BENCHMARK_CLEAN_MODE") == "true"
    is_obfuscate = os.environ.get("BENCHMARK_OBFUSCATE") == "true"
    distractor_level = (os.environ.get("BENCHMARK_DISTRACTOR_LEVEL") or "medium").strip().lower()
    distractor_seed = _parse_int_env("BENCHMARK_DISTRACTOR_SEED", None)
    obfuscation_seed = _parse_int_env("BENCHMARK_OBFUSCATION_SEED", None)
    for step in trace.get('steps', []):
        if step.get('act') == 'open':
            step['url'] = _apply_runtime_url_flags(
                step['url'],
                is_clean=is_clean,
                is_obfuscate=is_obfuscate,
                distractor_level=distractor_level,
                distractor_seed=distractor_seed,
                obfuscation_seed=obfuscation_seed,
            )

    with open(trace_path, 'w') as f: json.dump(trace, f, indent=2, ensure_ascii=False)
    return trace

def build_default_checkpoints(criteria):
    return _derive_hardened_checkpoints(criteria)


def patch_spec(task_id, instruction, criteria, scoring_checkpoints=None):
    spec_path = tasks_dir() / task_id / "task_spec.json"
    if not os.path.exists(spec_path): return
    with open(spec_path, 'r') as f: spec = json.load(f)
    spec['goal'] = instruction
    normalized = [str(c).strip() for c in (criteria or []) if str(c).strip()]
    if not normalized:
        normalized = [str(c).strip() for c in (spec.get('success_criteria') or []) if str(c).strip()]
    spec['success_criteria'] = normalized
    spec['preconditions'] = []
    if isinstance(scoring_checkpoints, list) and scoring_checkpoints:
        spec['scoring_checkpoints'] = scoring_checkpoints
    else:
        auto_checkpoints = build_default_checkpoints(normalized)
        if auto_checkpoints:
            spec['scoring_checkpoints'] = auto_checkpoints
        else:
            spec.pop('scoring_checkpoints', None)
    with open(spec_path, 'w') as f: json.dump(spec, f, indent=2, ensure_ascii=False)


def parse_step_progress(agent_result, task_ok, steps_executed, expected_steps):
    checkpoint_score_percent = agent_result.get("checkpoint_score_percent") if agent_result else None
    if isinstance(checkpoint_score_percent, str):
        try:
            checkpoint_score_percent = float(checkpoint_score_percent)
        except Exception:
            checkpoint_score_percent = None

    if isinstance(checkpoint_score_percent, (int, float)):
        progress = min(max(float(checkpoint_score_percent) / 100.0, 0.0), 1.0)
        return progress, float(checkpoint_score_percent), "checkpoints"

    if task_ok:
        return 1.0, 100.0, "task_success"
    if expected_steps > 0:
        progress = min(max(steps_executed, 0) / expected_steps, 1.0)
        return progress, progress * 100.0, "step_ratio_fallback"
    return 0.0, 0.0, "no_signal"

def inject_state(initial_state):
    if not initial_state: return
    payload = {"has_home":True, "has_bank":True, "has_utility":True, "location":"city", "balance":5000, "world_state":{"location_context":{"tier":"city_center"}}}
    payload.update(initial_state)
    if payload.get('location') == 'suburb': payload['world_state']['location_context']['tier'] = 'suburban'
    subprocess.run(["curl", "-s", "-X", "POST", _server_url("/api/mutate"), "-H", "Content-Type: application/json", "-d", json.dumps({"task_id": "DEBUG", "action": "set_state", "payload": payload})], stdout=subprocess.DEVNULL)

def run_chain(
    scenario,
    headless=True,
    max_steps=25,
    stop_on_first_fail_task=False,
    stop_on_first_fail_step=True,
    repeat_fail_threshold=3,
    shared_client=None,
):
    print(f"\n▶️ Running Chain: {scenario['chain_id']}")
    init_db_script = Path(__file__).with_name("init_db.py")
    subprocess.run(["python3", str(init_db_script)], check=True, stdout=subprocess.DEVNULL)
    if os.path.exists(state_path()): os.remove(state_path())
    inject_state(scenario.get('initial_state'))
    
    chain_score = 0
    chain_total = 0
    chain_step_earned = 0.0
    task_reports = []
    try:
        for step in scenario['steps']:
            tid = step['task_id']
            diff = step.get('difficulty', 1)
            chain_total += diff
            print(f"  👉 Task: {tid} (Diff: {diff})")
            trace = patch_trace(tid, step['instruction'], step['success_criteria'], step_payload=step)
            step_checkpoints = step.get("scoring_checkpoints") or step.get("checkpoints")
            patch_spec(tid, step['instruction'], step['success_criteria'], step_checkpoints)
            expected_steps = len(trace.get('steps', [])) if trace else 0
            
            start_url = _server_url("/shop.local/index.html")
            if trace and trace.get('steps') and trace['steps'][0].get('act') == 'open':
                start_url = trace['steps'][0]['url']

            # RUN AGENT
            result_path = os.path.join("output", tid, "agent_result.json")
            if os.path.exists(result_path):
                os.remove(result_path)
            agent_result = execute_agent_task(
                task_id=tid,
                start_url=start_url,
                max_steps=max_steps,
                repeat_fail_threshold=repeat_fail_threshold,
                stop_on_first_fail_step=stop_on_first_fail_step,
                headless=headless,
                client=shared_client,
                write_result=True,
                verbose=False,
            )
            full_output = str(agent_result.get("raw_output", "") or "")

            task_ok = bool(agent_result.get("success")) if agent_result else ("TASK PASSED" in full_output)
            steps_executed = int(agent_result.get("steps_executed", 0)) if agent_result else 0
            repeat_fail = bool(agent_result.get("repeat_fail", False)) if agent_result else False
            end_reason = agent_result.get("end_reason", "") if agent_result else ""
            step_error_abort = bool(agent_result.get("step_error_abort", False)) if agent_result else False
            step_error_message = str(agent_result.get("step_error_message", "") or agent_result.get("last_step_status", "")) if agent_result else ""
            checkpoint_total = int(agent_result.get("checkpoint_total", 0)) if agent_result else 0
            checkpoint_required_total = int(agent_result.get("checkpoint_required_total", 0)) if agent_result else 0
            checkpoint_required_passed = int(agent_result.get("checkpoint_required_passed", 0)) if agent_result else 0
            checkpoint_mode = agent_result.get("checkpoint_mode", "none") if agent_result else "none"
            checkpoint_required_failed = agent_result.get("checkpoint_required_failed", []) if agent_result else []

            step_progress, step_score_percent, step_score_source = parse_step_progress(
                agent_result,
                task_ok,
                steps_executed,
                expected_steps,
            )
            chain_step_earned += step_progress

            if task_ok:
                print(f"    ✅ Passed (+{diff})")
                chain_score += diff
                fail_reason = ""
            else:
                print(f"    ❌ Failed")
                print("--- DIAGNOSTIC INFO ---")
                tail = full_output.splitlines()[-20:]
                print("\n".join(tail))
                fail_reason = end_reason or (tail[-1] if tail else "unknown failure")

            failure_bucket, failure_category = _derive_failure_classification(task_ok, agent_result, end_reason)
            task_reports.append({
                "task_id": tid,
                "difficulty": diff,
                "success": task_ok,
                "failure_reason": fail_reason,
                "failure_bucket": failure_bucket,
                "failure_category": failure_category,
                "steps_executed": steps_executed,
                "expected_steps": expected_steps,
                "step_progress": step_progress,
                "step_score_percent": step_score_percent,
                "step_score_source": step_score_source,
                "repeat_fail": repeat_fail,
                "end_reason": end_reason,
                "step_error_abort": step_error_abort,
                "step_error_message": step_error_message,
                "checkpoint_mode": checkpoint_mode,
                "checkpoint_total": checkpoint_total,
                "checkpoint_required_total": checkpoint_required_total,
                "checkpoint_required_passed": checkpoint_required_passed,
                "checkpoint_required_failed": checkpoint_required_failed,
            })
            if stop_on_first_fail_task and not task_ok:
                break

        chain_success = len(task_reports) == len(scenario['steps']) and all(t["success"] for t in task_reports)
        return {
            "chain_id": scenario["chain_id"],
            "theme": scenario.get("theme"),
            "success": chain_success,
            "score": chain_score,
            "max_score": chain_total,
            "tasks": task_reports,
            "executed_tasks": len(task_reports),
            "planned_tasks": len(scenario["steps"]),
            "step_earned": chain_step_earned,
            "step_max": float(len(scenario["steps"])),
        }
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {
            "chain_id": scenario["chain_id"],
            "theme": scenario.get("theme"),
            "success": False,
            "score": chain_score,
            "max_score": chain_total,
            "tasks": task_reports,
            "executed_tasks": len(task_reports),
            "planned_tasks": len(scenario["steps"]),
            "step_earned": chain_step_earned,
            "step_max": float(len(scenario["steps"])),
            "error": str(e),
        }


def summarize_failures(chain_reports):
    bucket_counts = Counter()
    category_counts = Counter()
    end_reason_counts = Counter()
    for chain in chain_reports:
        for task in chain.get("tasks", []):
            if task.get("success"):
                continue
            bucket = task.get("failure_bucket", "unknown_failure")
            category = task.get("failure_category", "unknown")
            end_reason = task.get("end_reason", "unknown")
            bucket_counts[bucket] += 1
            category_counts[category] += 1
            end_reason_counts[end_reason] += 1
    return {
        "bucket_counts": dict(bucket_counts),
        "category_counts": dict(category_counts),
        "end_reason_counts": dict(end_reason_counts),
    }


def load_existing_summary(summary_path):
    if not summary_path or not os.path.exists(summary_path):
        return []
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chains = data.get("chains", [])
        if isinstance(chains, list):
            return chains
    except Exception as e:
        print(f"⚠️ Failed to load summary for resume: {e}")
    return []


def compute_aggregate_metrics(chain_reports):
    overall_score = sum(int(c.get("score", 0)) for c in chain_reports)
    overall_max = sum(int(c.get("max_score", 0)) for c in chain_reports)
    total_tasks = sum(int(c.get("executed_tasks", 0)) for c in chain_reports)
    total_planned_tasks = sum(int(c.get("planned_tasks", 0)) for c in chain_reports)
    passed_tasks = sum(
        1
        for chain in chain_reports
        for task in chain.get("tasks", [])
        if task.get("success")
    )
    total_step_earned = sum(float(c.get("step_earned", 0.0)) for c in chain_reports)
    total_step_max = sum(float(c.get("step_max", 0.0)) for c in chain_reports)
    task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
    step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
    flow_score = (
        sum(1 for c in chain_reports if c.get("success")) / len(chain_reports) * 100.0
        if chain_reports
        else 0.0
    )
    weighted_score = (overall_score / overall_max * 100.0) if overall_max else 0.0
    return {
        "overall_score": overall_score,
        "overall_max": overall_max,
        "total_tasks": total_tasks,
        "total_planned_tasks": total_planned_tasks,
        "passed_tasks": passed_tasks,
        "total_step_earned": total_step_earned,
        "total_step_max": total_step_max,
        "task_score": task_score,
        "step_score": step_score,
        "flow_score": flow_score,
        "weighted_score": weighted_score,
    }

def main():
    parser = argparse.ArgumentParser(description="Run dynamic benchmark using LLM agent")
    parser.add_argument("--themes", default="newcomer,daily,career,leisure,crisis", help="Comma-separated theme list")
    parser.add_argument("--limit-per-theme", type=int, default=20)
    parser.add_argument("--num-shards", type=int, default=1, help="Split selected chains evenly across N shards")
    parser.add_argument("--shard-index", type=int, default=0, help="0-based shard index")
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--scenario-root", default=None, help="Directory containing sampled_<theme>.json")
    parser.add_argument("--summary-json", default="audit_chain_dynamic_summary.json")
    parser.add_argument("--log-file", default=None, help="Optional per-run log file path")
    parser.add_argument("--resume", action="store_true", help="Resume from existing summary JSON at chain granularity")
    parser.add_argument("--start-chain-id", default="", help="Start execution from this chain_id (inclusive)")
    parser.add_argument("--resume-after-chain-id", default="", help="Skip execution until after this chain_id")
    parser.add_argument("--append-log", action="store_true", help="Append to the run log instead of overwriting it")
    parser.add_argument("--stop-on-first-fail-task", action="store_true")
    parser.add_argument("--stop-on-first-fail", action="store_true", dest="stop_on_first_fail_task")
    parser.add_argument("--stop-on-first-fail-step", dest="stop_on_first_fail_step", action="store_true")
    parser.add_argument("--no-stop-on-first-fail-step", dest="stop_on_first_fail_step", action="store_false")
    parser.set_defaults(stop_on_first_fail_step=True)
    parser.add_argument("--repeat-fail-threshold", type=int, default=3)
    parser.add_argument(
        "--distractor-level",
        choices=["off", "low", "medium", "high"],
        default=os.environ.get("BENCHMARK_DISTRACTOR_LEVEL", "medium"),
        help="Server-injected distractor intensity (reproducible when seed is fixed)",
    )
    parser.add_argument(
        "--distractor-seed",
        type=int,
        default=_parse_int_env("BENCHMARK_DISTRACTOR_SEED", 20260220),
        help="Seed for distractor injection sampling",
    )
    parser.add_argument(
        "--obfuscation-seed",
        type=int,
        default=_parse_int_env("BENCHMARK_OBFUSCATION_SEED", 20260220),
        help="Seed for obfuscation ID generation",
    )
    args = parser.parse_args()

    os.environ["BENCHMARK_DISTRACTOR_LEVEL"] = args.distractor_level
    os.environ["BENCHMARK_DISTRACTOR_SEED"] = str(args.distractor_seed)
    os.environ["BENCHMARK_OBFUSCATION_SEED"] = str(args.obfuscation_seed)
    if args.scenario_root:
        os.environ["BENCHMARK_SCENARIO_ROOT"] = args.scenario_root
    if args.num_shards < 1:
        raise ValueError("--num-shards must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.num_shards:
        raise ValueError("--shard-index must satisfy 0 <= shard-index < num-shards")
    if args.start_chain_id and args.resume_after_chain_id:
        raise ValueError("--start-chain-id and --resume-after-chain-id cannot be used together")

    themes = [t.strip() for t in args.themes.split(",") if t.strip()]
    scenario_root = _scenario_root()
    should_resume_summary = bool(args.resume or args.start_chain_id or args.resume_after_chain_id)
    existing_chain_reports = load_existing_summary(args.summary_json) if should_resume_summary else []
    chain_reports = list(existing_chain_reports)
    aggregate = compute_aggregate_metrics(chain_reports)
    overall_score = aggregate["overall_score"]
    overall_max = aggregate["overall_max"]
    total_tasks = aggregate["total_tasks"]
    total_planned_tasks = aggregate["total_planned_tasks"]
    passed_tasks = aggregate["passed_tasks"]
    total_step_earned = aggregate["total_step_earned"]
    total_step_max = aggregate["total_step_max"]
    completed_chain_ids = {str(c.get("chain_id")) for c in existing_chain_reports if c.get("chain_id")}
    if existing_chain_reports:
        print(f"🔁 Resuming with {len(existing_chain_reports)} completed chains loaded from {args.summary_json}")
    shared_client = build_client()
    start_chain_found = not bool(args.start_chain_id)
    resume_after_found = not bool(args.resume_after_chain_id)

    for theme in themes:
        path = scenario_root / f"sampled_{theme}.json"
        if not path.exists():
            continue
        with open(path) as f:
            scenarios = json.load(f)
        selected_scenarios = scenarios[: args.limit_per_theme]
        shard_scenarios = selected_scenarios[args.shard_index :: args.num_shards]
        target_scenarios = []
        for scenario in shard_scenarios:
            chain_id = str(scenario.get("chain_id"))
            if not start_chain_found:
                if chain_id == args.start_chain_id:
                    start_chain_found = True
                else:
                    continue
            if not resume_after_found:
                if chain_id == args.resume_after_chain_id:
                    resume_after_found = True
                continue
            if chain_id in completed_chain_ids:
                continue
            target_scenarios.append(scenario)
        if not target_scenarios:
            continue
        print(f"\n" + "#"*60 + f"\n🚀 THEME: {theme.upper()}\n" + "#"*60)
        print(
            f"Shard {args.shard_index + 1}/{args.num_shards} "
            f"processing {len(target_scenarios)} of {len(selected_scenarios)} selected chains",
        )
        for s in target_scenarios:
            report = run_chain(
                s,
                headless=args.headless,
                max_steps=args.max_steps,
                stop_on_first_fail_task=args.stop_on_first_fail_task,
                stop_on_first_fail_step=args.stop_on_first_fail_step,
                repeat_fail_threshold=args.repeat_fail_threshold,
                shared_client=shared_client,
            )
            chain_reports.append(report)
            overall_score += report["score"]
            overall_max += report["max_score"]
            total_tasks += report["executed_tasks"]
            total_planned_tasks += report["planned_tasks"]
            passed_tasks += sum(1 for t in report["tasks"] if t["success"])
            total_step_earned += float(report.get("step_earned", 0.0))
            total_step_max += float(report.get("step_max", 0.0))

            task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
            step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
            flow_score = (
                sum(1 for c in chain_reports if c.get("success")) / len(chain_reports) * 100.0
                if chain_reports else 0.0
            )
            weighted_score = (overall_score / overall_max * 100.0) if overall_max else 0.0
            failure_summary = summarize_failures(chain_reports)
            run_config = {
                "clean_mode": os.environ.get("BENCHMARK_CLEAN_MODE", "false"),
                "obfuscate_mode": os.environ.get("BENCHMARK_OBFUSCATE", "false"),
                "distractor_level": args.distractor_level,
                "distractor_seed": args.distractor_seed,
                "obfuscation_seed": args.obfuscation_seed,
                "repeat_fail_threshold": args.repeat_fail_threshold,
                "stop_on_first_fail_task": bool(args.stop_on_first_fail_task),
                "stop_on_first_fail_step": bool(args.stop_on_first_fail_step),
                "max_steps": args.max_steps,
                "scenario_root": str(scenario_root),
                "num_shards": args.num_shards,
                "shard_index": args.shard_index,
                "themes": themes,
                "limit_per_theme": args.limit_per_theme,
            }

            with open(args.summary_json, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "run_config": run_config,
                        "chains": chain_reports,
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
                        "failure_analysis": failure_summary,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

    if args.start_chain_id and not start_chain_found:
        raise ValueError(f"--start-chain-id not found in selected shard: {args.start_chain_id}")
    if args.resume_after_chain_id and not resume_after_found:
        raise ValueError(f"--resume-after-chain-id not found in selected shard: {args.resume_after_chain_id}")

    passed_chains = sum(1 for c in chain_reports if c["success"])
    task_score = (passed_tasks / total_planned_tasks * 100.0) if total_planned_tasks else 0.0
    step_score = (total_step_earned / total_step_max * 100.0) if total_step_max else 0.0
    flow_score = (passed_chains / len(chain_reports) * 100.0) if chain_reports else 0.0
    weighted_score = (overall_score / overall_max * 100.0) if overall_max else 0.0
    failure_summary = summarize_failures(chain_reports)
    top_categories = sorted(
        failure_summary["category_counts"].items(),
        key=lambda kv: kv[1],
        reverse=True,
    )[:5]
    print(f"\n{'='*50}\n📊 FINAL ENGLISH BENCHMARK SCORE REPORT\n{'='*50}")
    print(f"Chains: {passed_chains}/{len(chain_reports)} passed")
    print(f"Tasks:  {passed_tasks}/{total_planned_tasks} passed")
    print(f"Step Score: {step_score:.2f}/100")
    print(f"Task Score: {task_score:.2f}/100")
    print(f"Flow Score: {flow_score:.2f}/100")
    print(f"Weighted Score: {overall_score}/{overall_max}")
    print(f"Weighted Grade: {weighted_score:.2f}/100")
    if top_categories:
        print("Top Failure Categories:")
        for name, count in top_categories:
            print(f"  - {name}: {count}")
    print(f"Summary JSON: {args.summary_json}")
    print("="*50)

if __name__ == "__main__": main()
