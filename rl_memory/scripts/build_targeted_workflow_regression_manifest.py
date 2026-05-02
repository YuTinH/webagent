#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_BINDINGS = ROOT / "tasks" / "workflow_module_bindings.json"
DEFAULT_OUTPUT_DIR = ROOT / "rl_memory" / "reports" / "targeted_workflow_regressions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build targeted workflow regression manifests for deterministic benchmark fixes."
    )
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--bindings", default=str(DEFAULT_BINDINGS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_goal_ids(path: Path, goal_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(goal_ids) + ("\n" if goal_ids else ""), encoding="utf-8")


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root)
    output_dir = Path(args.output_dir)
    bindings_payload = load_json(Path(args.bindings))
    bindings = list(bindings_payload.get("bindings", []) if isinstance(bindings_payload, dict) else bindings_payload)
    bindings_by_id = {item["binding_id"]: item for item in bindings}

    issue_buckets: dict[str, dict[str, Any]] = {
        "track_orders_executor_compat": {
            "description": "Goals that invoke BIND_B4_TRACK_ORDERS and should be revalidated after TRACK_ORDER/:has-text executor fixes.",
            "by_split": {},
        },
        "insurance_policy_param_drift": {
            "description": "Goals whose BIND_G2_INSURANCE_POLICY invocation drifted away from the fixed Prime Shield task defaults.",
            "by_split": {},
        },
    }

    for split_dir in sorted(path for path in batch_root.iterdir() if (path / "workflow_oracles").exists()):
        split = split_dir.name
        track_goal_ids: list[str] = []
        drift_goal_ids: list[str] = []
        for oracle_path in sorted((split_dir / "workflow_oracles").glob("*.json")):
            oracle = load_json(oracle_path)
            goal_id = oracle_path.stem
            reference_invocations = list(oracle.get("reference_invocations", []) or [])
            if any(inv.get("binding_id") == "BIND_B4_TRACK_ORDERS" for inv in reference_invocations):
                track_goal_ids.append(goal_id)
            for inv in reference_invocations:
                if inv.get("binding_id") != "BIND_G2_INSURANCE_POLICY":
                    continue
                binding = bindings_by_id.get("BIND_G2_INSURANCE_POLICY", {})
                defaults = dict(binding.get("default_parameter_values", {}) or {})
                params = dict(inv.get("parameter_values", {}) or {})
                if params != defaults:
                    drift_goal_ids.append(goal_id)
                    break
        issue_buckets["track_orders_executor_compat"]["by_split"][split] = track_goal_ids
        issue_buckets["insurance_policy_param_drift"]["by_split"][split] = drift_goal_ids

    summary = {
        "batch_root": str(batch_root),
        "issues": {},
    }
    markdown_lines = [
        "# Targeted Workflow Regression Manifest",
        "",
        f"- batch_root: `{batch_root}`",
        "",
    ]

    for issue_name, payload in issue_buckets.items():
        by_split = {split: goal_ids for split, goal_ids in payload["by_split"].items() if goal_ids}
        counts = {split: len(goal_ids) for split, goal_ids in by_split.items()}
        total = sum(counts.values())
        summary["issues"][issue_name] = {
            "description": payload["description"],
            "counts_by_split": counts,
            "total_goals": total,
            "goal_ids_by_split": by_split,
        }
        markdown_lines.extend(
            [
                f"## {issue_name}",
                "",
                payload["description"],
                "",
                f"- total_goals: `{total}`",
            ]
        )
        for split, goal_ids in by_split.items():
            txt_path = output_dir / f"{issue_name}.{split}.goal_ids.txt"
            dump_goal_ids(txt_path, goal_ids)
            markdown_lines.append(
                f"- {split}: `{len(goal_ids)}` goals -> `{txt_path}`"
            )
        markdown_lines.append("")

    dump_json(output_dir / "targeted_workflow_regression_manifest.json", summary)
    (output_dir / "targeted_workflow_regression_manifest.md").write_text(
        "\n".join(markdown_lines).rstrip() + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
