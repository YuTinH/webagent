#!/usr/bin/env python3
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path("/Users/masteryth/Documents/webagent")
BINDINGS_PATH = ROOT / "tasks" / "workflow_module_bindings.json"
OUTPUT_JSON = ROOT / "tasks" / "workflow_multibinding_inventory.json"
OUTPUT_MD = ROOT / ".task_sync_meta" / "workflow_multibinding_inventory.md"


def main() -> None:
    bindings = json.loads(BINDINGS_PATH.read_text())["bindings"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for binding in bindings:
        grouped[binding["module_id"]].append(binding)

    inventory = []
    for module_id, items in sorted(grouped.items()):
        if len(items) <= 1:
            continue
        param_signatures = {tuple(sorted(item.get("default_parameter_values", {}).keys())) for item in items}
        observable_signatures = {tuple(item.get("observable_templates", [])) for item in items}
        description_signatures = {item.get("description_template", "") for item in items}
        write_signatures = {
            (
                tuple(item.get("writes_memory", [])),
                tuple(item.get("writes_env", [])),
            )
            for item in items
        }
        recommend_explicit = (
            len(param_signatures) > 1
            or len(observable_signatures) > 1
            or len(description_signatures) > 1
            or len(write_signatures) > 1
        )
        inventory.append(
            {
                "module_id": module_id,
                "binding_count": len(items),
                "recommend_explicit_binding_id": recommend_explicit,
                "reason": (
                    "Bindings differ in parameter surface or observable behavior."
                    if recommend_explicit
                    else "Bindings are near-equivalent; default binding selection is usually acceptable."
                ),
                "bindings": [
                    {
                        "binding_id": item["binding_id"],
                        "backing_task_id": item["backing_task_id"],
                        "task_dir": item["task_dir"],
                        "default_parameter_keys": sorted(item.get("default_parameter_values", {}).keys()),
                    }
                    for item in items
                ],
            }
        )

    OUTPUT_JSON.write_text(json.dumps({"version": 1, "modules": inventory}, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# Workflow Multi-Binding Inventory",
        "",
        f"- source: `{BINDINGS_PATH}`",
        f"- multi_binding_modules: {len(inventory)}",
        "",
        "## Modules",
    ]
    if not inventory:
        lines.append("- none")
    else:
        for item in inventory:
            lines.append(
                f"- `{item['module_id']}`: {item['binding_count']} bindings, "
                f"recommend_explicit_binding_id={'yes' if item['recommend_explicit_binding_id'] else 'no'}"
            )
            lines.append(f"  reason: {item['reason']}")
            for binding in item["bindings"]:
                lines.append(
                    f"  - `{binding['binding_id']}` -> `{binding['task_dir']}` "
                    f"(task=`{binding['backing_task_id']}`, params={binding['default_parameter_keys']})"
                )
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
