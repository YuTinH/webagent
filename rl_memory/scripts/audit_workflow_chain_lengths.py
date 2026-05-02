#!/usr/bin/env python3
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_OUTPUT_JSON = ROOT / "rl_memory" / "reports" / "workflow_chain_length_audit_v20.json"
DEFAULT_OUTPUT_MD = ROOT / "rl_memory" / "reports" / "workflow_chain_length_audit_v20.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit active workflow chain lengths and surface short-chain benchmark candidates by theme."
    )
    parser.add_argument("--blueprints", default=str(BLUEPRINTS_PATH))
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=["train", "dev", "test"],
        default=["train", "dev", "test"],
        help="Only audit the selected workflow splits.",
    )
    parser.add_argument("--max-chain-len", type=int, default=3)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def path_modules(path: dict[str, Any]) -> list[str]:
    return [step.get("module_id") for step in path.get("steps", []) if step.get("module_id")]


def summarize_blueprint(
    blueprint: dict[str, Any],
    active_goal_count: int,
    split_names: list[str],
) -> dict[str, Any]:
    paths = blueprint.get("paths", [])
    module_paths = [path_modules(path) for path in paths]
    lengths = [len(modules) for modules in module_paths if modules]
    if not lengths:
        raise ValueError(f"Blueprint {blueprint['blueprint_id']} has no usable module paths.")
    return {
        "blueprint_id": blueprint["blueprint_id"],
        "theme": blueprint.get("theme", ""),
        "goal_count": active_goal_count,
        "splits": split_names,
        "num_paths": len(paths),
        "min_chain_len": min(lengths),
        "max_chain_len": max(lengths),
        "path_module_sequences": module_paths,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Workflow Chain Length Audit")
    lines.append("")
    lines.append(f"- Batch root: `{report['batch_root']}`")
    lines.append(f"- Splits: `{', '.join(report['splits'])}`")
    lines.append(f"- Active blueprints: `{report['active_blueprint_count']}`")
    lines.append(f"- Short-chain threshold: `max_chain_len <= {report['short_chain_threshold']}`")
    lines.append(f"- Short-chain blueprints: `{report['short_chain_blueprint_count']}`")
    lines.append(f"- Short-chain goals: `{report['short_chain_goal_count']}`")
    lines.append("")
    lines.append("## Theme Summary")
    lines.append("")
    lines.append("| Theme | Active Blueprints | Active Goals | Short Blueprints | Short Goals | 1-step | 2-step | 3-step | 4-step | 5+ step |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in report["theme_summary"]:
        dist = item["max_chain_len_distribution"]
        lines.append(
            "| {theme} | {active_bp} | {active_goals} | {short_bp} | {short_goals} | {l1} | {l2} | {l3} | {l4} | {l5p} |".format(
                theme=item["theme"],
                active_bp=item["active_blueprints"],
                active_goals=item["active_goals"],
                short_bp=item["short_chain_blueprints"],
                short_goals=item["short_chain_goals"],
                l1=dist.get("1", 0),
                l2=dist.get("2", 0),
                l3=dist.get("3", 0),
                l4=dist.get("4", 0),
                l5p=dist.get("5+", 0),
            )
        )
    lines.append("")
    lines.append("## Short-Chain Candidates")
    lines.append("")
    for theme_group in report["short_chain_candidates_by_theme"]:
        lines.append(f"### {theme_group['theme']}")
        lines.append("")
        for item in theme_group["blueprints"]:
            split_text = ",".join(item["splits"])
            lines.append(
                "- `{blueprint_id}`: goals={goal_count}, splits={splits}, paths={num_paths}, min={min_chain_len}, max={max_chain_len}".format(
                    blueprint_id=item["blueprint_id"],
                    goal_count=item["goal_count"],
                    splits=split_text,
                    num_paths=item["num_paths"],
                    min_chain_len=item["min_chain_len"],
                    max_chain_len=item["max_chain_len"],
                )
            )
            for index, modules in enumerate(item["path_module_sequences"], start=1):
                lines.append(f"  path{index}: `{ ' -> '.join(modules) }`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    blueprints_doc = load_json(Path(args.blueprints))
    blueprints = {item["blueprint_id"]: item for item in blueprints_doc["blueprints"]}
    batch_root = Path(args.batch_root)

    counts = Counter()
    splits_by_blueprint: dict[str, set[str]] = defaultdict(set)
    for split in args.splits:
        manifest_path = batch_root / split / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = load_json(manifest_path)
        for goal in manifest.get("goals", []):
            blueprint_id = goal["blueprint_id"]
            counts[blueprint_id] += 1
            splits_by_blueprint[blueprint_id].add(split)

    active_summaries: list[dict[str, Any]] = []
    for blueprint_id, goal_count in sorted(counts.items()):
        blueprint = blueprints.get(blueprint_id)
        if blueprint is None:
            continue
        active_summaries.append(
            summarize_blueprint(
                blueprint=blueprint,
                active_goal_count=goal_count,
                split_names=sorted(splits_by_blueprint.get(blueprint_id, set())),
            )
        )

    short_candidates = [item for item in active_summaries if item["max_chain_len"] <= args.max_chain_len]

    theme_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "active_blueprints": 0,
            "active_goals": 0,
            "short_chain_blueprints": 0,
            "short_chain_goals": 0,
            "max_chain_len_distribution": Counter(),
        }
    )
    for item in active_summaries:
        theme = item["theme"]
        stats = theme_stats[theme]
        stats["active_blueprints"] += 1
        stats["active_goals"] += item["goal_count"]
        max_len = item["max_chain_len"]
        bucket = "5+" if max_len >= 5 else str(max_len)
        stats["max_chain_len_distribution"][bucket] += 1
        if max_len <= args.max_chain_len:
            stats["short_chain_blueprints"] += 1
            stats["short_chain_goals"] += item["goal_count"]

    theme_summary = []
    for theme, stats in sorted(theme_stats.items(), key=lambda kv: (-kv[1]["short_chain_goals"], kv[0])):
        theme_summary.append(
            {
                "theme": theme,
                "active_blueprints": stats["active_blueprints"],
                "active_goals": stats["active_goals"],
                "short_chain_blueprints": stats["short_chain_blueprints"],
                "short_chain_goals": stats["short_chain_goals"],
                "max_chain_len_distribution": {
                    "1": stats["max_chain_len_distribution"].get("1", 0),
                    "2": stats["max_chain_len_distribution"].get("2", 0),
                    "3": stats["max_chain_len_distribution"].get("3", 0),
                    "4": stats["max_chain_len_distribution"].get("4", 0),
                    "5+": stats["max_chain_len_distribution"].get("5+", 0),
                },
            }
        )

    grouped_candidates: list[dict[str, Any]] = []
    candidates_by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in short_candidates:
        candidates_by_theme[item["theme"]].append(item)
    for theme, items in sorted(candidates_by_theme.items(), key=lambda kv: (-sum(x["goal_count"] for x in kv[1]), kv[0])):
        grouped_candidates.append(
            {
                "theme": theme,
                "blueprints": sorted(
                    items,
                    key=lambda entry: (-entry["goal_count"], entry["max_chain_len"], entry["blueprint_id"]),
                ),
            }
        )

    report = {
        "version": 1,
        "batch_root": str(batch_root),
        "splits": list(args.splits),
        "short_chain_threshold": args.max_chain_len,
        "active_blueprint_count": len(active_summaries),
        "short_chain_blueprint_count": len(short_candidates),
        "short_chain_goal_count": sum(item["goal_count"] for item in short_candidates),
        "theme_summary": theme_summary,
        "short_chain_candidates_by_theme": grouped_candidates,
    }

    save_json(Path(args.output_json), report)
    save_text(Path(args.output_md), build_markdown(report))
    print(json.dumps(
        {
            "output_json": str(Path(args.output_json)),
            "output_md": str(Path(args.output_md)),
            "active_blueprint_count": report["active_blueprint_count"],
            "short_chain_blueprint_count": report["short_chain_blueprint_count"],
            "short_chain_goal_count": report["short_chain_goal_count"],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
