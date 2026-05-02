#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_OUTPUT_ROOT = ROOT / "rl_memory" / "reports" / "targeted_workflow_logic_audit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a targeted logic audit by executing workflow reference paths in isolated runtimes."
    )
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--split", choices=["train", "dev", "test"], default="train")
    parser.add_argument("--goal-id", action="append", required=True, help="Goal id to audit. Can be passed multiple times.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--server-port", type=int, default=8014)
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def prepare_runtime(runtime_root: Path) -> None:
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "output").mkdir(parents=True, exist_ok=True)
    env_src = ROOT / "env"
    env_dst = runtime_root / "env"
    env_dst.mkdir(parents=True, exist_ok=True)
    for src in env_src.iterdir():
        if src.name in {"state.json", "data.db", "data.db-wal", "data.db-shm"}:
            continue
        dst = env_dst / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    for name in ("database", "sites", "tasks"):
        dst = runtime_root / name
        src = ROOT / name
        try:
            dst.symlink_to(src, target_is_directory=True)
        except OSError:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    init_env = os.environ.copy()
    init_env["WEBAGENT_RUNTIME_ROOT"] = str(runtime_root)
    init_env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{init_env['PYTHONPATH']}" if init_env.get("PYTHONPATH") else str(ROOT)
    subprocess.run(
        [sys.executable, str(ROOT / "init_db.py")],
        cwd=str(ROOT),
        env=init_env,
        check=True,
        capture_output=True,
        text=True,
    )


def start_server(runtime_root: Path, server_log_path: Path, port: int) -> tuple[subprocess.Popen[str], str]:
    base_url = f"http://127.0.0.1:{port}"
    if not port_available(port):
        raise RuntimeError(f"Port {port} is already in use; targeted logic audit expects an idle fixed port.")
    server_log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(server_log_path, "a", encoding="utf-8")
    env = os.environ.copy()
    env["WEBAGENT_RUNTIME_ROOT"] = str(runtime_root)
    env["WEBAGENT_SERVER_PORT"] = str(port)
    env["WEBAGENT_SERVER_BASE_URL"] = base_url
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py"), str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 20
    last_error = "server did not respond"
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Server exited early. See {server_log_path}")
        try:
            with urlopen(f"{base_url}/api/env", timeout=1) as resp:
                if 200 <= getattr(resp, "status", 200) < 500:
                    return proc, base_url
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"Timed out waiting for server at {base_url}: {last_error}")


def stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_episode(
    goal_path: Path,
    oracle_path: Path,
    path_id: str,
    runtime_root: Path,
    episode_output_root: Path,
    server_port: int,
    headless: bool,
) -> dict[str, Any]:
    server_log_path = episode_output_root / "server.log"
    proc, base_url = start_server(runtime_root, server_log_path, server_port)
    try:
        env = os.environ.copy()
        port = base_url.rsplit(":", 1)[-1]
        env["WEBAGENT_RUNTIME_ROOT"] = str(runtime_root)
        env["WEBAGENT_SERVER_PORT"] = port
        env["WEBAGENT_SERVER_BASE_URL"] = base_url
        env["WEB_SUITE_PORT"] = port
        env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(ROOT)
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "run_workflow_episode.py"),
            "--goal",
            str(goal_path),
            "--oracle",
            str(oracle_path),
            "--path-id",
            path_id,
            "--output-root",
            str(episode_output_root),
            "--db-path",
            str(runtime_root / "data.db"),
            "--execute",
        ]
        if headless:
            cmd.append("--headless")
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        summary_path = episode_output_root / "workflow_run_summary.json"
        evaluation_path = episode_output_root / "workflow_execution_evaluation.json"
        result: dict[str, Any] = {
            "path_id": path_id,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "server_log_path": str(server_log_path),
        }
        if summary_path.exists():
            result["summary"] = load_json(summary_path)
        if evaluation_path.exists():
            result["evaluation"] = load_json(evaluation_path)
        return result
    finally:
        stop_server(proc)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Targeted Workflow Logic Audit",
        "",
        f"- batch_root: `{report['batch_root']}`",
        f"- split: `{report['split']}`",
        f"- selected_goals: {len(report['goals'])}",
        f"- total_reference_paths: {report['summary']['total_paths']}",
        f"- passed_paths: {report['summary']['passed_paths']}",
        f"- failed_paths: {report['summary']['failed_paths']}",
        "",
        "## Summary",
        f"- hard_fail_goals: {report['summary']['hard_fail_goals']}",
        f"- quality_or_realism_issues_in_selected_goals: {report['summary']['goals_with_existing_audit_flags']}",
        "",
    ]
    for goal in report["goals"]:
        lines.append(f"## {goal['goal_id']}")
        lines.append(f"- theme: `{goal['theme']}`")
        lines.append(f"- blueprint_id: `{goal['blueprint_id']}`")
        lines.append(f"- instruction: {goal['instruction']}")
        lines.append(f"- initial_world_state: `{goal['initial_world_state']}`")
        lines.append(f"- target_state: `{goal['target_state']}`")
        lines.append(f"- quality_issues: `{goal['quality_issues']}`")
        lines.append(f"- quality_soft_issues: `{goal['quality_soft_issues']}`")
        lines.append(f"- realism_issues: `{goal['realism_issues']}`")
        for path in goal["paths"]:
            ev = path.get("evaluation") or {}
            lines.append(
                f"- path `{path['path_id']}`: pass={'yes' if path['passed'] else 'no'}, "
                f"success_type=`{ev.get('success_type')}`, "
                f"final_success={ev.get('final_success')}, "
                f"invalid_transition_count={ev.get('invalid_transition_count')}, "
                f"hard_constraints_satisfied={ev.get('hard_constraints_satisfied')}"
            )
            lines.append(f"  modules: `{ ' -> '.join(path['required_modules']) }`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root).resolve()
    split_root = batch_root / args.split
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = load_json(split_root / "manifest.json")
    manifest_by_goal = {item["goal_id"]: item for item in manifest.get("goals", [])}
    quality_by_goal = {
        item["goal_id"]: item for item in load_json(split_root / "workflow_goal_quality_audit.json").get("per_goal", [])
    }
    realism_by_goal = {
        item["goal_id"]: item for item in load_json(batch_root / "workflow_batch_realism_audit.json").get("per_goal", [])
        if item.get("split") == args.split
    }

    goals_payload: list[dict[str, Any]] = []
    total_paths = 0
    passed_paths = 0
    hard_fail_goals = 0
    goals_with_existing_audit_flags = 0

    for goal_id in args.goal_id:
        ref = manifest_by_goal.get(goal_id)
        if ref is None:
            raise KeyError(f"Unknown goal id in split {args.split}: {goal_id}")
        goal_path = split_root / ref["goal_file"]
        oracle_path = split_root / ref["oracle_file"]
        goal = load_json(goal_path)
        oracle = load_json(oracle_path)
        quality = quality_by_goal.get(goal_id, {})
        realism = realism_by_goal.get(goal_id, {})

        goal_entry = {
            "goal_id": goal_id,
            "theme": ref["theme"],
            "blueprint_id": ref["blueprint_id"],
            "instruction": goal.get("instruction", ""),
            "initial_world_state": goal.get("initial_world_state", []),
            "target_state": goal.get("target_state", []),
            "quality_issues": quality.get("issues", []),
            "quality_soft_issues": quality.get("soft_issues", []),
            "realism_issues": realism.get("issues", []),
            "paths": [],
        }
        if goal_entry["quality_issues"] or goal_entry["quality_soft_issues"] or goal_entry["realism_issues"]:
            goals_with_existing_audit_flags += 1

        goal_passed = True
        for path in oracle.get("success_paths", []):
            path_id = path["path_id"]
            runtime_root = output_root / "_runtime" / safe_name(goal_id) / safe_name(path_id)
            episode_output_root = output_root / goal_id / path_id
            prepare_runtime(runtime_root)
            path_result = run_episode(
                goal_path=goal_path,
                oracle_path=oracle_path,
                path_id=path_id,
                runtime_root=runtime_root,
                episode_output_root=episode_output_root,
                server_port=int(args.server_port),
                headless=bool(args.headless),
            )
            evaluation = path_result.get("evaluation") or {}
            passed = bool(evaluation.get("final_success"))
            total_paths += 1
            if passed:
                passed_paths += 1
            else:
                goal_passed = False
            goal_entry["paths"].append(
                {
                    "path_id": path_id,
                    "required_modules": list(path.get("required_modules", [])),
                    "passed": passed,
                    "evaluation": evaluation,
                    "returncode": path_result.get("returncode"),
                    "stdout_tail": path_result.get("stdout_tail", ""),
                    "stderr_tail": path_result.get("stderr_tail", ""),
                    "server_log_path": path_result.get("server_log_path", ""),
                }
            )
        if not goal_passed:
            hard_fail_goals += 1
        goals_payload.append(goal_entry)

    report = {
        "version": 1,
        "batch_root": str(batch_root),
        "split": args.split,
        "goals": goals_payload,
        "summary": {
            "total_paths": total_paths,
            "passed_paths": passed_paths,
            "failed_paths": total_paths - passed_paths,
            "hard_fail_goals": hard_fail_goals,
            "goals_with_existing_audit_flags": goals_with_existing_audit_flags,
        },
    }

    json_path = output_root / "targeted_logic_audit.json"
    md_path = output_root / "targeted_logic_audit.md"
    dump_json(json_path, report)
    dump_text(md_path, render_markdown(report))
    print(json.dumps({"output_json": str(json_path), "output_md": str(md_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
