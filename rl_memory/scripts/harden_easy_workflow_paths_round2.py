#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"
BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"

SAFE_THEMES = {"security", "daily", "social", "health", "travel"}

MODULE_ACTIONS = {
    "MODULE_2FA_SETUP": "enable two-factor access",
    "MODULE_AIRPORT_TRANSFER": "arrange the airport transfer",
    "MODULE_BANK_OPENING": "activate the payment rail",
    "MODULE_BOOK_FLIGHT": "book the flight",
    "MODULE_CHARITY_DONATION": "complete the charity donation",
    "MODULE_GIFT_POOLING": "create the gift pool",
    "MODULE_GROCERY_RUN": "stage the grocery run",
    "MODULE_HEALTH_PLAN_ACTIVATION": "activate the health plan",
    "MODULE_INSURANCE_POLICY": "review the insurance policy",
    "MODULE_PASSWORD_MANAGER": "update the password manager",
    "MODULE_PASSWORD_RECOVERY_E2E": "complete end-to-end password recovery",
    "MODULE_PASSWORD_RESET_COMPLETION": "finish the password reset",
    "MODULE_PASSWORD_RESET_REQUEST": "start the password reset",
    "MODULE_PRESCRIPTION_REFILL": "refill the prescription",
    "MODULE_PRICE_PROTECTION": "request price protection",
    "MODULE_PRIVACY_SETTINGS": "review privacy settings",
    "MODULE_RSVP_EVENT": "record the RSVP commitment",
    "MODULE_SECURITY_AUDIT": "complete the security audit",
    "MODULE_SECURITY_ROTATION": "rotate the security secrets",
    "MODULE_SHOPPING": "place the shopping order",
    "MODULE_VACCINE_MGMT": "update vaccination management",
    "MODULE_VISA_REQUIREMENTS": "clear visa requirements",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def extract_blueprint_id(notes: str) -> str | None:
    match = re.search(r"Generated from ([A-Z0-9_]+);", notes or "")
    return match.group(1) if match else None


def describe_steps(steps: list[str]) -> str:
    phrases = [MODULE_ACTIONS.get(step, step) for step in steps]
    if not phrases:
        return "complete the workflow"
    if len(phrases) == 1:
        return phrases[0]
    return ", then ".join(phrases)


def eligible_blueprint(bp: dict[str, Any]) -> bool:
    if bp.get("theme") not in SAFE_THEMES:
        return False
    path_lengths = [len(path.get("steps", [])) for path in bp.get("paths", []) if path.get("steps")]
    if not path_lengths or min(path_lengths) != 2 or max(path_lengths) < 3:
        return False
    if bp.get("theme") == "travel" and bp.get("blueprint_id") != "BP_TRAVEL_CLEARANCE_TRANSFER_SYNC":
        return False
    min_paths = [path for path in bp.get("paths", []) if len(path.get("steps", [])) == 2]
    return len(min_paths) == 1


def used_modules_from_success_paths(oracle: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for path in oracle.get("success_paths", []):
        used |= set(path.get("required_modules", []))
        used |= set(path.get("optional_modules", []))
    return used


def compose_distinctness_rule(paths: list[list[str]]) -> str:
    if not paths:
        return "Complete the workflow to reach the target."
    if len(paths) == 1:
        return f"Complete {describe_steps(paths[0])} to reach the target."
    rendered = [describe_steps(path) for path in paths]
    return "Either " + ", or ".join(rendered) + " to reach the same target."


def main() -> None:
    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc["blueprints"]

    patched_blueprints: dict[str, dict[str, Any]] = {}
    for bp in blueprints:
        if not eligible_blueprint(bp):
            continue
        short_path = next(path for path in bp.get("paths", []) if len(path.get("steps", [])) == 2)
        remaining_paths = [path for path in bp.get("paths", []) if path["path_id"] != short_path["path_id"]]
        remaining_steps = [[step.get("module_id") for step in path.get("steps", [])] for path in remaining_paths]
        bp["paths"] = remaining_paths
        bp["distinctness_rule"] = compose_distinctness_rule(remaining_steps)
        bp["notes_template"] = bp["distinctness_rule"]
        patched_blueprints[bp["blueprint_id"]] = {
            "removed_path_id": short_path["path_id"],
            "removed_steps": [step.get("module_id") for step in short_path.get("steps", [])],
            "remaining_steps": remaining_steps,
            "distinctness_rule": bp["distinctness_rule"],
        }

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    patched_goals = 0
    patched_oracles = 0
    for split in ["dev", "test", "train"]:
        manifest = load_json(BATCH_ROOT / split / "manifest.json")
        for ref in manifest.get("goals", []):
            goal_path = BATCH_ROOT / split / ref["goal_file"]
            oracle_path = BATCH_ROOT / split / ref["oracle_file"]

            goal = load_json(goal_path)
            blueprint_id = extract_blueprint_id(goal.get("notes", ""))
            if blueprint_id not in patched_blueprints:
                continue
            patch = patched_blueprints[blueprint_id]
            primary_steps = patch["remaining_steps"][0]
            goal["notes"] = (
                f"Generated from {blueprint_id}; "
                f"Complete {describe_steps(primary_steps)} after removing the previous compact shortcut."
            )
            save_json(goal_path, goal)
            patched_goals += 1

            oracle = load_json(oracle_path)
            oracle["success_paths"] = [
                path for path in oracle.get("success_paths", [])
                if path.get("path_id") != patch["removed_path_id"]
            ]
            remaining_steps = [path.get("required_modules", []) for path in oracle.get("success_paths", [])]
            oracle.setdefault("composition", {})["composition_type"] = (
                "single_path" if len(remaining_steps) == 1 else "multi_path"
            )
            oracle["composition"]["num_semantically_distinct_paths"] = len(remaining_steps)
            oracle["composition"]["distinctness_rule"] = compose_distinctness_rule(remaining_steps)

            used_modules = used_modules_from_success_paths(oracle)
            oracle["reference_invocations"] = [
                inv for inv in oracle.get("reference_invocations", [])
                if inv.get("module_id") in used_modules
            ]
            oracle["module_nodes"] = [
                node for node in oracle.get("module_nodes", [])
                if node.get("module_id") in used_modules
            ]
            oracle["dependency_edges"] = [
                edge for edge in oracle.get("dependency_edges", [])
                if edge.get("from") in used_modules and edge.get("to") in used_modules
            ]
            save_json(oracle_path, oracle)
            patched_oracles += 1

    print(
        json.dumps(
            {
                "patched_blueprints": len(patched_blueprints),
                "patched_goals": patched_goals,
                "patched_oracles": patched_oracles,
                "blueprint_ids": sorted(patched_blueprints),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
