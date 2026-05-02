#!/usr/bin/env python3
import argparse
import json
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_BLUEPRINTS = ROOT / "tasks" / "workflow_generation_blueprints.json"
DEFAULT_OUTPUT_JSON = ROOT / "docs" / "workflow_difficulty_audit_v20.json"
DEFAULT_OUTPUT_MD = ROOT / "docs" / "workflow_difficulty_audit_v20.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze structural difficulty and saturation risk for workflow benchmark goals."
    )
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--blueprints", default=str(DEFAULT_BLUEPRINTS))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def summarize(values: list[float | int]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "min": min(values),
        "max": max(values),
    }


def count_leaves(value: Any) -> int:
    if isinstance(value, dict):
        return sum(count_leaves(v) for v in value.values())
    if isinstance(value, list):
        return sum(count_leaves(v) for v in value)
    return 1


def initial_state_size(initial_world_state: Any) -> int:
    if isinstance(initial_world_state, list):
        return sum(1 for item in initial_world_state if isinstance(item, str))
    if isinstance(initial_world_state, dict):
        return sum(1 for _, value in initial_world_state.items() if value is True)
    return 0


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def average_pairwise_jaccard(path_sets: list[set[str]]) -> float | None:
    if len(path_sets) < 2:
        return None
    return round(
        statistics.mean(jaccard(a, b) for a, b in combinations(path_sets, 2)),
        4,
    )


def compute_goal_metrics(split: str, goal: dict[str, Any], oracle: dict[str, Any]) -> dict[str, Any]:
    success_paths = oracle.get("success_paths", [])
    required_sets = [set(path.get("required_modules", [])) for path in success_paths]
    required_lengths = [len(path.get("required_modules", [])) for path in success_paths]
    shortest_path_len = min(required_lengths) if required_lengths else 0
    longest_path_len = max(required_lengths) if required_lengths else 0
    module_budget = int(goal.get("max_module_invocations", 0) or 0)
    step_budget = int(goal.get("max_steps", 0) or 0)
    target_size = len(goal.get("target_state", []))
    visible_constraints = goal.get("visible_constraints", {})
    visible_constraint_count = count_leaves(visible_constraints) if visible_constraints else 0
    counterfactual_axis_count = count_leaves(goal.get("counterfactual_axes", []))
    initial_size = initial_state_size(goal.get("initial_world_state", []))
    module_union_size = len(set().union(*required_sets)) if required_sets else 0
    step_budget_ratio = round(step_budget / shortest_path_len, 4) if shortest_path_len else None
    module_budget_slack = module_budget - shortest_path_len if shortest_path_len else None
    path_overlap = average_pairwise_jaccard(required_sets)

    risk_flags = []
    if shortest_path_len <= 2:
        risk_flags.append("shortest_path_le_2")
    if target_size <= 2:
        risk_flags.append("target_size_le_2")
    if len(success_paths) <= 2:
        risk_flags.append("success_paths_le_2")
    if step_budget_ratio is not None and step_budget_ratio >= 15:
        risk_flags.append("step_budget_ratio_ge_15")
    if module_budget_slack is not None and module_budget_slack <= 1:
        risk_flags.append("module_budget_slack_le_1")

    return {
        "goal_id": goal["goal_id"],
        "split": split,
        "theme": goal.get("theme", "unknown"),
        "difficulty": goal.get("difficulty"),
        "target_state_size": target_size,
        "visible_constraint_count": visible_constraint_count,
        "counterfactual_axis_count": counterfactual_axis_count,
        "initial_state_size": initial_size,
        "num_success_paths": len(success_paths),
        "shortest_path_len": shortest_path_len,
        "longest_path_len": longest_path_len,
        "module_union_size": module_union_size,
        "mean_required_path_len": round(statistics.mean(required_lengths), 4) if required_lengths else None,
        "mean_path_overlap_jaccard": path_overlap,
        "max_steps": step_budget,
        "max_module_invocations": module_budget,
        "step_budget_ratio_vs_shortest_path": step_budget_ratio,
        "module_budget_slack_vs_shortest_path": module_budget_slack,
        "saturation_risk_flags": risk_flags,
        "saturation_risk_score": len(risk_flags),
    }


def aggregate_goal_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    theme_counts = Counter(item["theme"] for item in items)
    difficulty_counts = Counter(item["difficulty"] for item in items)
    score_counts = Counter(item["saturation_risk_score"] for item in items)
    total = len(items) or 1

    def ratio(predicate: str) -> float:
        hits = sum(1 for item in items if predicate in item["saturation_risk_flags"])
        return round(hits / total, 4)

    return {
        "goal_count": len(items),
        "theme_counts": dict(sorted(theme_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "shortest_path_len_stats": summarize([item["shortest_path_len"] for item in items]),
        "longest_path_len_stats": summarize([item["longest_path_len"] for item in items]),
        "num_success_paths_stats": summarize([item["num_success_paths"] for item in items]),
        "target_state_size_stats": summarize([item["target_state_size"] for item in items]),
        "visible_constraint_count_stats": summarize([item["visible_constraint_count"] for item in items]),
        "counterfactual_axis_count_stats": summarize([item["counterfactual_axis_count"] for item in items]),
        "max_steps_stats": summarize([item["max_steps"] for item in items]),
        "max_module_invocations_stats": summarize([item["max_module_invocations"] for item in items]),
        "step_budget_ratio_stats": summarize(
            [item["step_budget_ratio_vs_shortest_path"] for item in items if item["step_budget_ratio_vs_shortest_path"] is not None]
        ),
        "module_budget_slack_stats": summarize(
            [item["module_budget_slack_vs_shortest_path"] for item in items if item["module_budget_slack_vs_shortest_path"] is not None]
        ),
        "saturation_risk_score_counts": dict(sorted(score_counts.items())),
        "share_shortest_path_le_2": ratio("shortest_path_le_2"),
        "share_target_size_le_2": ratio("target_size_le_2"),
        "share_success_paths_le_2": ratio("success_paths_le_2"),
        "share_step_budget_ratio_ge_15": ratio("step_budget_ratio_ge_15"),
        "share_module_budget_slack_le_1": ratio("module_budget_slack_le_1"),
    }


def sort_easiest(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -item["saturation_risk_score"],
            item["shortest_path_len"],
            item["target_state_size"],
            item["num_success_paths"],
            -(item["step_budget_ratio_vs_shortest_path"] or 0),
        ),
    )


def sort_hardest(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -item["shortest_path_len"],
            -item["target_state_size"],
            -item["num_success_paths"],
            -(item["visible_constraint_count"]),
            -(item["counterfactual_axis_count"]),
        ),
    )


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root)
    blueprints_doc = load_json(Path(args.blueprints))
    blueprints = blueprints_doc.get("blueprints", [])
    blueprint_theme_counts = Counter(bp.get("theme", "unknown") for bp in blueprints)
    blueprint_difficulty_counts = Counter(bp.get("difficulty") for bp in blueprints)
    blueprint_path_counts = [len(bp.get("paths", [])) for bp in blueprints]
    blueprint_step_lengths = [
        len(path.get("steps", []))
        for bp in blueprints
        for path in bp.get("paths", [])
    ]

    per_goal: list[dict[str, Any]] = []
    for split in ["dev", "test", "train"]:
        split_dir = batch_root / split
        manifest = load_json(split_dir / "manifest.json")
        for ref in manifest.get("goals", []):
            goal = load_json(split_dir / ref["goal_file"])
            oracle = load_json(split_dir / ref["oracle_file"])
            per_goal.append(compute_goal_metrics(split, goal, oracle))

    global_summary = aggregate_goal_metrics(per_goal)
    per_split = {
        split: aggregate_goal_metrics([item for item in per_goal if item["split"] == split])
        for split in ["dev", "test", "train"]
    }

    per_theme: dict[str, Any] = {}
    for theme in sorted({item["theme"] for item in per_goal}):
        per_theme[theme] = aggregate_goal_metrics([item for item in per_goal if item["theme"] == theme])

    report = {
        "version": 1,
        "batch_root": str(batch_root),
        "blueprints_file": str(Path(args.blueprints)),
        "blueprints": {
            "count": len(blueprints),
            "theme_counts": dict(sorted(blueprint_theme_counts.items())),
            "difficulty_counts": dict(sorted(blueprint_difficulty_counts.items())),
            "path_count_stats": summarize(blueprint_path_counts),
            "path_step_length_stats": summarize(blueprint_step_lengths),
        },
        "global": global_summary,
        "per_split": per_split,
        "per_theme": per_theme,
        "easiest_candidates": sort_easiest(per_goal)[:25],
        "hardest_candidates": sort_hardest(per_goal)[:25],
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Workflow Difficulty Audit",
        "",
        f"- batch_root: `{batch_root}`",
        f"- blueprints_file: `{Path(args.blueprints)}`",
        f"- blueprint_count: {report['blueprints']['count']}",
        f"- goal_count: {report['global']['goal_count']}",
        "",
        "## Blueprint-Level Stats",
        f"- difficulty_counts: {report['blueprints']['difficulty_counts']}",
        f"- mean_path_count_per_blueprint: {report['blueprints']['path_count_stats']['mean']}",
        f"- mean_step_length_per_blueprint_path: {report['blueprints']['path_step_length_stats']['mean']}",
        "",
        "## Global Goal-Level Stats",
        f"- shortest_path_len.mean: {report['global']['shortest_path_len_stats']['mean']}",
        f"- shortest_path_len.median: {report['global']['shortest_path_len_stats']['median']}",
        f"- num_success_paths.mean: {report['global']['num_success_paths_stats']['mean']}",
        f"- target_state_size.mean: {report['global']['target_state_size_stats']['mean']}",
        f"- visible_constraint_count.mean: {report['global']['visible_constraint_count_stats']['mean']}",
        f"- counterfactual_axis_count.mean: {report['global']['counterfactual_axis_count_stats']['mean']}",
        f"- max_steps.mean: {report['global']['max_steps_stats']['mean']}",
        f"- max_module_invocations.mean: {report['global']['max_module_invocations_stats']['mean']}",
        f"- step_budget_ratio_vs_shortest_path.mean: {report['global']['step_budget_ratio_stats']['mean']}",
        f"- module_budget_slack.mean: {report['global']['module_budget_slack_stats']['mean']}",
        "",
        "## Saturation-Risk Indicators",
        f"- share_shortest_path_le_2: {report['global']['share_shortest_path_le_2']:.3f}",
        f"- share_target_size_le_2: {report['global']['share_target_size_le_2']:.3f}",
        f"- share_success_paths_le_2: {report['global']['share_success_paths_le_2']:.3f}",
        f"- share_step_budget_ratio_ge_15: {report['global']['share_step_budget_ratio_ge_15']:.3f}",
        f"- share_module_budget_slack_le_1: {report['global']['share_module_budget_slack_le_1']:.3f}",
        f"- saturation_risk_score_counts: {report['global']['saturation_risk_score_counts']}",
        "",
        "## Split Stats",
    ]
    for split in ["dev", "test", "train"]:
        summary = report["per_split"][split]
        lines.extend(
            [
                f"### {split}",
                f"- goals: {summary['goal_count']}",
                f"- difficulty_counts: {summary['difficulty_counts']}",
                f"- shortest_path_len.mean: {summary['shortest_path_len_stats']['mean']}",
                f"- num_success_paths.mean: {summary['num_success_paths_stats']['mean']}",
                f"- target_state_size.mean: {summary['target_state_size_stats']['mean']}",
                f"- max_steps.mean: {summary['max_steps_stats']['mean']}",
                f"- step_budget_ratio_vs_shortest_path.mean: {summary['step_budget_ratio_stats']['mean']}",
                f"- share_shortest_path_le_2: {summary['share_shortest_path_le_2']:.3f}",
                f"- share_target_size_le_2: {summary['share_target_size_le_2']:.3f}",
                f"- share_step_budget_ratio_ge_15: {summary['share_step_budget_ratio_ge_15']:.3f}",
                "",
            ]
        )

    lines.extend(["## Highest Saturation-Risk Candidates"])
    for item in report["easiest_candidates"][:15]:
        lines.append(
            f"- `{item['goal_id']}` ({item['split']}/{item['theme']}): "
            f"difficulty={item['difficulty']}, paths={item['num_success_paths']}, "
            f"shortest_path={item['shortest_path_len']}, target={item['target_state_size']}, "
            f"step_ratio={item['step_budget_ratio_vs_shortest_path']}, risk={item['saturation_risk_score']}"
        )

    lines.extend(["", "## Highest Structural-Complexity Candidates"])
    for item in report["hardest_candidates"][:15]:
        lines.append(
            f"- `{item['goal_id']}` ({item['split']}/{item['theme']}): "
            f"difficulty={item['difficulty']}, paths={item['num_success_paths']}, "
            f"shortest_path={item['shortest_path_len']}, target={item['target_state_size']}, "
            f"constraints={item['visible_constraint_count']}, counterfactual_axes={item['counterfactual_axis_count']}"
        )

    lines.extend(["", "## Theme-Level Means"])
    ranked_themes = sorted(
        report["per_theme"].items(),
        key=lambda kv: (
            -kv[1]["share_shortest_path_le_2"],
            -kv[1]["share_target_size_le_2"],
            -(kv[1]["step_budget_ratio_stats"]["mean"] or 0),
        ),
    )
    for theme, summary in ranked_themes:
        lines.append(
            f"- `{theme}`: goals={summary['goal_count']}, "
            f"shortest_path.mean={summary['shortest_path_len_stats']['mean']}, "
            f"target.mean={summary['target_state_size_stats']['mean']}, "
            f"paths.mean={summary['num_success_paths_stats']['mean']}, "
            f"step_ratio.mean={summary['step_budget_ratio_stats']['mean']}, "
            f"share_short_path={summary['share_shortest_path_le_2']:.3f}"
        )

    output_md.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
