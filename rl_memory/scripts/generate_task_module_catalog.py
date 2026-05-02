#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path("/Users/masteryth/Documents/webagent")
TASKS_ROOT = ROOT / "tasks"
OUTPUT_PATH = TASKS_ROOT / "task_module_catalog.json"


def main() -> None:
    groups: dict[str, list[dict[str, str]]] = {}
    canonical_dir_by_group: dict[str, str] = {}

    for task_dir in sorted(path.name for path in TASKS_ROOT.iterdir() if path.is_dir()):
        spec_path = TASKS_ROOT / task_dir / "task_spec.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text())
        if spec.get("lifecycle_status") != "active":
            continue

        module_group = spec["module_group"]
        groups.setdefault(module_group, []).append(
            {
                "task_dir": task_dir,
                "task_id": spec["task_id"],
                "variant_kind": spec.get("variant_kind", "distinct"),
                "lifecycle_status": spec["lifecycle_status"],
            }
        )
        canonical_dir_by_group[module_group] = min(
            canonical_dir_by_group.get(module_group, task_dir),
            spec.get("canonical_task_dir", task_dir),
        )

    catalog = {
        "version": 2,
        "description": "Catalog of active atomic tasks grouped by workflow-relevant module semantics.",
        "groups": [
            {
                "module_group": module_group,
                "canonical_task_dir": canonical_dir_by_group[module_group],
                "members": sorted(groups[module_group], key=lambda item: item["task_dir"]),
            }
            for module_group in sorted(groups)
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
