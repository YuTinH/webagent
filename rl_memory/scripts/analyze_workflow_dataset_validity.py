#!/usr/bin/env python3
import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_MODULES = ROOT / "tasks" / "workflow_module_library.json"
DEFAULT_BINDINGS = ROOT / "tasks" / "workflow_module_bindings.json"
DEFAULT_OUTPUT_JSON = ROOT / "docs" / "workflow_dataset_validity_report_v20.json"
DEFAULT_OUTPUT_MD = ROOT / "docs" / "workflow_dataset_validity_report_v20.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce paper-facing structural validity stats for the workflow benchmark."
    )
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--modules", default=str(DEFAULT_MODULES))
    parser.add_argument("--bindings", default=str(DEFAULT_BINDINGS))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def initial_state_predicates(initial_world_state: Any) -> set[str]:
    if isinstance(initial_world_state, list):
        return {predicate for predicate in initial_world_state if isinstance(predicate, str)}
    if isinstance(initial_world_state, dict):
        return {key for key, value in initial_world_state.items() if value is True}
    return set()


def preconditions_satisfied(requires: dict[str, Any], state: set[str]) -> bool:
    all_of = set(requires.get("all_of", []))
    any_of = set(requires.get("any_of", []))
    none_of = set(requires.get("none_of", []))
    if not all_of.issubset(state):
        return False
    if any_of and not (any_of & state):
        return False
    if none_of & state:
        return False
    return True


def summarize(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 4),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def load_existing_audit(batch_root: Path, relative_path: str) -> dict[str, Any] | None:
    path = batch_root / relative_path
    if not path.exists():
        return None
    return load_json(path)


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root)
    modules_doc = load_json(Path(args.modules))
    bindings_doc = load_json(Path(args.bindings))
    modules_by_id = {module["module_id"]: module for module in modules_doc["modules"]}
    bindings_by_id = {binding["binding_id"]: binding for binding in bindings_doc["bindings"]}

    split_reports: dict[str, Any] = {}
    global_theme_counts: Counter[str] = Counter()
    global_module_counts: Counter[str] = Counter()
    all_path_lengths: list[int] = []
    all_num_paths: list[int] = []
    all_distinct_counts: list[int] = []
    total_goals = 0
    solvable_goals = 0
    all_paths_executable_goals = 0
    invalid_path_records: list[dict[str, Any]] = []

    for split in ["dev", "test", "train"]:
        split_dir = batch_root / split
        manifest = load_json(split_dir / "manifest.json")
        goal_index = {item["goal_id"]: item for item in manifest.get("goals", [])}
        split_goal_count = 0
        split_solvable = 0
        split_all_paths_executable = 0
        split_path_lengths: list[int] = []
        split_num_paths: list[int] = []
        split_distinct_counts: list[int] = []
        split_theme_counts: Counter[str] = Counter()
        split_invalid_paths: list[dict[str, Any]] = []

        for goal_id, ref in goal_index.items():
            split_goal_count += 1
            goal = load_json(split_dir / ref["goal_file"])
            oracle = load_json(split_dir / ref["oracle_file"])
            state0 = initial_state_predicates(goal.get("initial_world_state", []))
            target = set(goal.get("target_state", []))
            paths = oracle.get("success_paths", [])
            split_num_paths.append(len(paths))
            all_num_paths.append(len(paths))
            distinct = int(oracle.get("composition", {}).get("num_semantically_distinct_paths", 0))
            split_distinct_counts.append(distinct)
            all_distinct_counts.append(distinct)
            theme = goal.get("theme", "unknown")
            split_theme_counts[theme] += 1
            global_theme_counts[theme] += 1

            executable_flags: list[bool] = []
            for path in paths:
                required_modules = path.get("required_modules", [])
                split_path_lengths.append(len(required_modules))
                all_path_lengths.append(len(required_modules))
                issues: list[str] = []
                state = set(state0)
                ref_ids = path.get("reference_invocation_ids", [])
                if len(ref_ids) != len(required_modules):
                    issues.append("invocation_count_mismatch")
                for module_id in required_modules:
                    global_module_counts[module_id] += 1
                    module = modules_by_id.get(module_id)
                    if module is None:
                        issues.append(f"unknown_module:{module_id}")
                        continue
                    if not preconditions_satisfied(module.get("requires", {}), state):
                        issues.append(f"precondition_unsatisfied:{module_id}")
                    state -= set(module.get("effects", {}).get("removes", []))
                    state |= set(module.get("effects", {}).get("adds", []))
                if not target.issubset(state):
                    issues.append("target_not_reached")
                for inv_id in ref_ids:
                    inv = next((x for x in oracle.get("reference_invocations", []) if x.get("invocation_id") == inv_id), None)
                    if inv is None:
                        issues.append(f"missing_reference_invocation:{inv_id}")
                        continue
                    binding = bindings_by_id.get(inv.get("binding_id"))
                    if binding is None:
                        issues.append(f"missing_binding:{inv.get('binding_id')}")
                        continue
                    if binding.get("backing_task_id") != inv.get("binding_task_id"):
                        issues.append(f"binding_task_mismatch:{inv_id}")
                executable = not issues
                executable_flags.append(executable)
                if not executable:
                    split_invalid_paths.append(
                        {
                            "goal_id": goal_id,
                            "theme": theme,
                            "path_id": path.get("path_id"),
                            "issues": issues,
                        }
                    )
                    invalid_path_records.append(
                        {
                            "split": split,
                            "goal_id": goal_id,
                            "theme": theme,
                            "path_id": path.get("path_id"),
                            "issues": issues,
                        }
                    )
            if any(executable_flags):
                split_solvable += 1
                solvable_goals += 1
            if executable_flags and all(executable_flags):
                split_all_paths_executable += 1
                all_paths_executable_goals += 1

        split_reports[split] = {
            "goal_count": split_goal_count,
            "solvable_goals": split_solvable,
            "solvable_ratio": round(split_solvable / split_goal_count, 6) if split_goal_count else None,
            "all_paths_executable_goals": split_all_paths_executable,
            "all_paths_executable_ratio": round(split_all_paths_executable / split_goal_count, 6) if split_goal_count else None,
            "theme_counts": dict(sorted(split_theme_counts.items())),
            "path_length_stats": summarize(split_path_lengths),
            "success_path_count_stats": summarize(split_num_paths),
            "declared_distinct_path_stats": summarize(split_distinct_counts),
            "invalid_path_count": len(split_invalid_paths),
            "invalid_path_examples": split_invalid_paths[:20],
        }
        total_goals += split_goal_count

    report = {
        "version": 1,
        "batch_root": str(batch_root),
        "module_library": str(Path(args.modules)),
        "binding_library": str(Path(args.bindings)),
        "global": {
            "goal_count": total_goals,
            "solvable_goals": solvable_goals,
            "solvable_ratio": round(solvable_goals / total_goals, 6) if total_goals else None,
            "all_paths_executable_goals": all_paths_executable_goals,
            "all_paths_executable_ratio": round(all_paths_executable_goals / total_goals, 6) if total_goals else None,
            "theme_counts": dict(sorted(global_theme_counts.items())),
            "top_modules_by_reference_frequency": global_module_counts.most_common(25),
            "path_length_stats": summarize(all_path_lengths),
            "success_path_count_stats": summarize(all_num_paths),
            "declared_distinct_path_stats": summarize(all_distinct_counts),
            "invalid_path_count": len(invalid_path_records),
            "invalid_path_examples": invalid_path_records[:40],
        },
        "existing_audits": {
            "workflow_blueprint_split_audit": load_existing_audit(batch_root, "workflow_blueprint_split_audit.json"),
            "workflow_blueprint_realism_audit": load_existing_audit(batch_root, "workflow_blueprint_realism_audit.json"),
            "workflow_batch_realism_audit": load_existing_audit(batch_root, "workflow_batch_realism_audit.json"),
            "dev_workflow_goal_quality_audit": load_existing_audit(batch_root, "dev/workflow_goal_quality_audit.json"),
            "test_workflow_goal_quality_audit": load_existing_audit(batch_root, "test/workflow_goal_quality_audit.json"),
            "train_workflow_goal_quality_audit": load_existing_audit(batch_root, "train/workflow_goal_quality_audit.json"),
        },
        "per_split": split_reports,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Workflow Dataset Validity Report",
        "",
        f"- batch_root: `{batch_root}`",
        f"- total_goals: {report['global']['goal_count']}",
        f"- solvable_goals: {report['global']['solvable_goals']}",
        f"- solvable_ratio: {report['global']['solvable_ratio']:.3f}",
        f"- all_paths_executable_goals: {report['global']['all_paths_executable_goals']}",
        f"- all_paths_executable_ratio: {report['global']['all_paths_executable_ratio']:.3f}",
        f"- invalid_path_count: {report['global']['invalid_path_count']}",
        "",
        "## Global Structural Stats",
        f"- path_length.mean: {report['global']['path_length_stats']['mean']}",
        f"- path_length.median: {report['global']['path_length_stats']['median']}",
        f"- path_length.min: {report['global']['path_length_stats']['min']}",
        f"- path_length.max: {report['global']['path_length_stats']['max']}",
        f"- success_path_count.mean: {report['global']['success_path_count_stats']['mean']}",
        f"- declared_distinct_path.mean: {report['global']['declared_distinct_path_stats']['mean']}",
        "",
        "## Split-level Solvability",
    ]
    for split, split_report in report["per_split"].items():
        lines.extend(
            [
                f"### {split}",
                f"- goals: {split_report['goal_count']}",
                f"- solvable_goals: {split_report['solvable_goals']}",
                f"- solvable_ratio: {split_report['solvable_ratio']:.3f}",
                f"- all_paths_executable_goals: {split_report['all_paths_executable_goals']}",
                f"- all_paths_executable_ratio: {split_report['all_paths_executable_ratio']:.3f}",
                f"- invalid_path_count: {split_report['invalid_path_count']}",
                f"- path_length.mean: {split_report['path_length_stats']['mean']}",
                f"- success_path_count.mean: {split_report['success_path_count_stats']['mean']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Existing Audit Snapshot",
            f"- blueprint_split_hard_fail_reasons: {report['existing_audits']['workflow_blueprint_split_audit'].get('hard_fail_reasons', []) if report['existing_audits']['workflow_blueprint_split_audit'] else 'missing'}",
            f"- blueprint_realism_issue_count: {report['existing_audits']['workflow_blueprint_realism_audit'].get('issue_count') if report['existing_audits']['workflow_blueprint_realism_audit'] else 'missing'}",
            f"- batch_realism_issue_count: {report['existing_audits']['workflow_batch_realism_audit'].get('issue_count') if report['existing_audits']['workflow_batch_realism_audit'] else 'missing'}",
            f"- dev_goal_quality_hard_fail_reasons: {report['existing_audits']['dev_workflow_goal_quality_audit'].get('hard_fail_reasons', []) if report['existing_audits']['dev_workflow_goal_quality_audit'] else 'missing'}",
            f"- test_goal_quality_hard_fail_reasons: {report['existing_audits']['test_workflow_goal_quality_audit'].get('hard_fail_reasons', []) if report['existing_audits']['test_workflow_goal_quality_audit'] else 'missing'}",
            f"- train_goal_quality_hard_fail_reasons: {report['existing_audits']['train_workflow_goal_quality_audit'].get('hard_fail_reasons', []) if report['existing_audits']['train_workflow_goal_quality_audit'] else 'missing'}",
            "",
            "## Invalid Path Examples",
        ]
    )
    if not report["global"]["invalid_path_examples"]:
        lines.append("- none")
    else:
        for item in report["global"]["invalid_path_examples"]:
            lines.append(
                f"- `{item['split']}` `{item['goal_id']}` `{item['path_id']}` ({item['theme']}): {item['issues']}"
            )

    output_md.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
