#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/masteryth/Documents/webagent")
DEFAULT_BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
DEFAULT_BINDINGS = ROOT / "tasks" / "workflow_module_bindings.json"


class SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        raise KeyError(f"missing template variable: {key}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair workflow oracle reference_invocations by re-rendering descriptions/observables from bindings."
    )
    parser.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    parser.add_argument("--bindings", default=str(DEFAULT_BINDINGS))
    parser.add_argument(
        "--binding-ids",
        nargs="*",
        default=["BIND_A5_LEASE_MANAGEMENT"],
        help="Only repair invocations whose binding_id is in this allowlist.",
    )
    parser.add_argument(
        "--reset-nonoverridable-params",
        action="store_true",
        help="Reset parameter_values back to binding defaults when the binding disallows overrides.",
    )
    parser.add_argument(
        "--report-json",
        help="Optional JSON path for a machine-readable repair report.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_template(text: str, context: dict[str, Any]) -> str:
    normalized: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, (dict, list)):
            normalized[key] = json.dumps(value, ensure_ascii=False)
        else:
            normalized[key] = value
    return text.format_map(SafeFormatDict(normalized))


def main() -> None:
    args = parse_args()
    batch_root = Path(args.batch_root)
    bindings_payload = load_json(Path(args.bindings))
    if isinstance(bindings_payload, dict):
        bindings = list(bindings_payload.get("bindings", []) or [])
    else:
        bindings = list(bindings_payload or [])
    bindings_by_id = {item["binding_id"]: item for item in bindings}
    allowed = set(args.binding_ids or [])

    changed_files = 0
    changed_invocations = 0
    scanned_invocations = 0
    reset_parameter_invocations = 0
    impacted_goals_by_split: dict[str, set[str]] = {}

    for oracle_path in sorted(batch_root.glob("*/workflow_oracles/*.json")):
        oracle = load_json(oracle_path)
        split = oracle_path.parent.parent.name
        goal_id = oracle_path.stem
        file_changed = False
        for invocation in oracle.get("reference_invocations", []):
            binding_id = invocation.get("binding_id")
            if not binding_id or binding_id not in allowed:
                continue
            binding = bindings_by_id.get(binding_id)
            if binding is None:
                continue
            scanned_invocations += 1
            expected_params = dict(binding.get("default_parameter_values", {}) or {})
            params = dict(invocation.get("parameter_values", {}) or {})
            if args.reset_nonoverridable_params and not binding.get("allow_parameter_overrides", True):
                if params != expected_params:
                    invocation["parameter_values"] = dict(expected_params)
                    params = dict(expected_params)
                    reset_parameter_invocations += 1
                    file_changed = True
                    impacted_goals_by_split.setdefault(split, set()).add(goal_id)
            expected_description = render_template(binding.get("description_template", ""), params)
            expected_observables = [
                render_template(template, params)
                for template in binding.get("observable_templates", [])
            ]
            if (
                invocation.get("description") != expected_description
                or list(invocation.get("expected_observables", []) or []) != expected_observables
            ):
                invocation["description"] = expected_description
                invocation["expected_observables"] = expected_observables
                changed_invocations += 1
                file_changed = True
                impacted_goals_by_split.setdefault(split, set()).add(goal_id)
        if file_changed:
            dump_json(oracle_path, oracle)
            changed_files += 1

    report = {
        "batch_root": str(batch_root),
        "binding_ids": sorted(allowed),
        "scanned_invocations": scanned_invocations,
        "changed_invocations": changed_invocations,
        "reset_parameter_invocations": reset_parameter_invocations,
        "changed_files": changed_files,
        "impacted_goals_by_split": {
            split: sorted(goal_ids)
            for split, goal_ids in sorted(impacted_goals_by_split.items())
        },
    }
    if args.report_json:
        dump_json(Path(args.report_json), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
