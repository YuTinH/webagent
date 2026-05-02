#!/usr/bin/env python3
import argparse
import json
import sys
from itertools import combinations
from pathlib import Path


ROOT = Path("/Users/masteryth/Documents/webagent")
ORACLE_DIR = ROOT / "tasks" / "workflow_oracles"
DEFAULT_REQUIREMENTS = ROOT / "tasks" / "workflow_quality_requirements.json"
DEFAULT_OUTPUT_JSON = ROOT / ".task_sync_meta" / "workflow_goal_quality_audit.json"
DEFAULT_OUTPUT_MD = ROOT / ".task_sync_meta" / "workflow_goal_quality_audit.md"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit workflow-goal dataset quality against centralized requirements."
    )
    parser.add_argument(
        "--oracle-dir",
        default=str(ORACLE_DIR),
        help="Directory containing workflow oracle JSON files to audit.",
    )
    parser.add_argument(
        "--requirements",
        default=str(DEFAULT_REQUIREMENTS),
        help="Path to workflow quality requirements JSON.",
    )
    parser.add_argument(
        "--output-json",
        default=str(DEFAULT_OUTPUT_JSON),
        help="Where to write the machine-readable audit result.",
    )
    parser.add_argument(
        "--output-md",
        default=str(DEFAULT_OUTPUT_MD),
        help="Where to write the Markdown audit summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the dataset violates any hard quality requirement.",
    )
    return parser.parse_args()


def _load_oracles(oracle_dir: Path) -> list[tuple[Path, dict]]:
    out = []
    for path in sorted(oracle_dir.glob("*.json")):
        out.append((path, json.loads(path.read_text())))
    return out


def _load_requirements(path: Path) -> dict:
    return json.loads(path.read_text())


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def main() -> None:
    args = _parse_args()
    oracle_dir = Path(args.oracle_dir)
    requirements_path = Path(args.requirements)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    requirements = _load_requirements(requirements_path)
    multi_rules = requirements["multi_path"]
    single_rules = requirements["single_path"]
    dataset_rules = requirements["dataset"]
    soft_rules = requirements.get("soft_quality", {})

    oracles = _load_oracles(oracle_dir)
    total = len(oracles)
    multi = 0
    flagged = []
    soft_flagged = []
    hard_fail_reasons = []
    per_goal = []

    for oracle_path, oracle in oracles:
        goal_id = oracle["goal_id"]
        comp = oracle.get("composition", {})
        composition_type = comp.get("composition_type", "unknown")
        distinct_count = int(comp.get("num_semantically_distinct_paths", 0))
        success_paths = oracle.get("success_paths", [])
        required_sets = [set(p.get("required_modules", [])) for p in success_paths]
        unique_required_sets = {tuple(sorted(s)) for s in required_sets}
        pairwise = [_jaccard(a, b) for a, b in combinations(required_sets, 2)]
        max_jaccard = max(pairwise) if pairwise else None
        goal_flags = []
        soft_goal_flags = []
        has_subset_route = any(
            a < b or b < a for a, b in combinations(required_sets, 2)
        )
        goal_dir = oracle_path.parent.parent / "workflow_goal_instances"
        goal_path = goal_dir / oracle_path.name
        initial_target_overlap = []
        if goal_path.exists():
            goal = json.loads(goal_path.read_text())
            initial_state = goal.get("initial_world_state", [])
            if isinstance(initial_state, list):
                initial_state_predicates = {item for item in initial_state if isinstance(item, str)}
            elif isinstance(initial_state, dict):
                initial_state_predicates = {k for k, v in initial_state.items() if v is True}
            else:
                initial_state_predicates = set()
            target_predicates = set(goal.get("target_state", []))
            initial_target_overlap = sorted(initial_state_predicates & target_predicates)

        if composition_type == "multi_path":
            multi += 1
            if len(success_paths) < multi_rules["min_success_paths"]:
                goal_flags.append("multi_path_but_success_path_count_below_minimum")
            if distinct_count < multi_rules["min_semantically_distinct_paths"]:
                goal_flags.append("multi_path_but_declared_distinct_count_below_minimum")
            if (
                multi_rules["require_distinct_required_module_sets"]
                and len(unique_required_sets) < multi_rules["min_semantically_distinct_paths"]
            ):
                goal_flags.append("multi_path_but_required_module_sets_not_distinct")
            if max_jaccard is not None and max_jaccard > multi_rules["max_required_set_jaccard"]:
                goal_flags.append("multi_path_required_module_overlap_too_high")
            if has_subset_route:
                soft_goal_flags.append("multi_path_contains_subset_route")
        elif composition_type == "single_path":
            if len(success_paths) > single_rules["max_success_paths"]:
                goal_flags.append("single_path_but_multiple_success_paths_present")
            if distinct_count != single_rules["required_declared_distinct_paths"]:
                goal_flags.append("single_path_but_declared_distinct_count_invalid")
        else:
            goal_flags.append("unknown_composition_type")
        if initial_target_overlap:
            soft_goal_flags.append("initial_state_overlaps_target")

        for issue in goal_flags:
            flagged.append({"goal_id": goal_id, "issue": issue})
        for issue in soft_goal_flags:
            soft_flagged.append({"goal_id": goal_id, "issue": issue})

        per_goal.append(
            {
                "goal_id": goal_id,
                "composition_type": composition_type,
                "declared_distinct_paths": distinct_count,
                "success_path_count": len(success_paths),
                "unique_required_module_sets": len(unique_required_sets),
                "max_pairwise_required_set_jaccard": max_jaccard,
                "has_subset_route": has_subset_route,
                "initial_target_overlap": initial_target_overlap,
                "issues": goal_flags,
                "soft_issues": soft_goal_flags,
            }
        )

    ratio = (multi / total) if total else 0.0
    target_ratio = dataset_rules["min_multi_path_ratio"]
    meets_target = ratio >= target_ratio
    subset_like_count = sum(1 for item in per_goal if item["has_subset_route"])
    initial_overlap_count = sum(1 for item in per_goal if item["initial_target_overlap"])
    subset_like_ratio = (subset_like_count / total) if total else 0.0
    initial_overlap_ratio = (initial_overlap_count / total) if total else 0.0
    if not meets_target:
        hard_fail_reasons.append("dataset_multi_path_ratio_below_minimum")
    if (
        soft_rules.get("enforce_subset_like_as_hard")
        and subset_like_ratio > soft_rules.get("max_subset_like_multi_path_ratio", 1.0)
    ):
        hard_fail_reasons.append("dataset_subset_like_multi_path_ratio_above_maximum")
    if (
        soft_rules.get("enforce_initial_target_overlap_as_hard")
        and initial_overlap_ratio > soft_rules.get("max_initial_target_overlap_ratio", 1.0)
    ):
        hard_fail_reasons.append("dataset_initial_target_overlap_ratio_above_maximum")
    if flagged:
        hard_fail_reasons.append("goal_level_quality_violations_present")

    report = {
        "version": 2,
        "oracle_dir": str(oracle_dir),
        "requirements_file": str(requirements_path),
        "requirements": requirements,
        "total_goals": total,
        "multi_path_goals": multi,
        "multi_path_ratio": ratio,
        "target_ratio": target_ratio,
        "meets_target": meets_target,
        "hard_fail_reasons": hard_fail_reasons,
        "flagged_goals": flagged,
        "soft_flagged_goals": soft_flagged,
        "summary": {
            "hard_flagged_goal_count": len({item["goal_id"] for item in flagged}),
            "soft_flagged_goal_count": len({item["goal_id"] for item in soft_flagged}),
            "subset_like_multi_path_goals": subset_like_count,
            "subset_like_multi_path_ratio": subset_like_ratio,
            "subset_like_multi_path_ratio_target": soft_rules.get("max_subset_like_multi_path_ratio"),
            "initial_target_overlap_goals": initial_overlap_count,
            "initial_target_overlap_ratio": initial_overlap_ratio,
            "initial_target_overlap_ratio_target": soft_rules.get("max_initial_target_overlap_ratio"),
        },
        "per_goal": per_goal,
    }
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Workflow Goal Quality Audit",
        "",
        f"- oracle_dir: `{oracle_dir}`",
        f"- requirements_file: `{requirements_path}`",
        f"- total_goals: {total}",
        f"- multi_path_goals: {multi}",
        f"- multi_path_ratio: {ratio:.3f}",
        f"- target_ratio: {target_ratio:.3f}",
        f"- meets_target: {'yes' if meets_target else 'no'}",
        f"- strict_status: {'pass' if not hard_fail_reasons else 'fail'}",
        f"- subset_like_multi_path_goals: {report['summary']['subset_like_multi_path_goals']}",
        f"- subset_like_multi_path_ratio: {report['summary']['subset_like_multi_path_ratio']:.3f}",
        f"- initial_target_overlap_goals: {report['summary']['initial_target_overlap_goals']}",
        f"- initial_target_overlap_ratio: {report['summary']['initial_target_overlap_ratio']:.3f}",
        "",
        "## Requirements",
        f"- multi_path.min_success_paths: {multi_rules['min_success_paths']}",
        f"- multi_path.min_semantically_distinct_paths: {multi_rules['min_semantically_distinct_paths']}",
        f"- multi_path.require_distinct_required_module_sets: {multi_rules['require_distinct_required_module_sets']}",
        f"- multi_path.max_required_set_jaccard: {multi_rules['max_required_set_jaccard']:.3f}",
        f"- single_path.max_success_paths: {single_rules['max_success_paths']}",
        "",
        "## Per Goal",
    ]
    for item in per_goal:
        lines.append(
            f"- `{item['goal_id']}`: {item['composition_type']}, "
            f"declared={item['declared_distinct_paths']}, "
            f"paths={item['success_path_count']}, "
            f"unique_required_sets={item['unique_required_module_sets']}, "
            f"max_jaccard={item['max_pairwise_required_set_jaccard']}, "
            f"issues={item['issues'] or 'none'}, "
            f"soft_issues={item['soft_issues'] or 'none'}"
        )
    lines += ["", "## Hard Fail Reasons"]
    if not hard_fail_reasons:
        lines.append("- none")
    else:
        for reason in hard_fail_reasons:
            lines.append(f"- `{reason}`")
    lines += ["", "## Flags"]
    if not flagged:
        lines.append("- none")
    else:
        for item in flagged:
            lines.append(f"- `{item['goal_id']}`: {item['issue']}")
    lines += ["", "## Soft Flags"]
    if not soft_flagged:
        lines.append("- none")
    else:
        for item in soft_flagged:
            lines.append(f"- `{item['goal_id']}`: {item['issue']}")
    output_md.write_text("\n".join(lines) + "\n")

    if args.strict and hard_fail_reasons:
        print(
            "workflow goal quality check failed: " + ", ".join(hard_fail_reasons),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
