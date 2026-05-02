#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"
BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
MODULES_PATH = ROOT / "tasks" / "workflow_module_library.json"

TARGET_MODULES = {
    "MODULE_PASSWORD_MANAGER",
    "MODULE_GIFT_POOLING",
    "MODULE_LONG_HAUL_TRIP",
    "MODULE_COUPON_MANAGEMENT",
    "MODULE_HEALTH_PLAN_ACTIVATION",
    "MODULE_FIRMWARE_UPDATE",
}

MODULE_ACTIONS = {
    "MODULE_PASSWORD_MANAGER": "update the password manager",
    "MODULE_PRIVACY_SETTINGS": "review privacy settings",
    "MODULE_GIFT_POOLING": "create the gift pool",
    "MODULE_RSVP_EVENT": "record the RSVP commitment",
    "MODULE_LONG_HAUL_TRIP": "complete the bundled long-haul trip flow",
    "MODULE_VISA_REQUIREMENTS": "clear visa requirements",
    "MODULE_BOOK_FLIGHT": "book the flight",
    "MODULE_BOOK_HOTEL": "book lodging",
    "MODULE_COUPON_MANAGEMENT": "secure pricing with coupons",
    "MODULE_BANK_OPENING": "activate the payment rail",
    "MODULE_HEALTH_PLAN_ACTIVATION": "activate the health plan",
    "MODULE_INSURANCE_POLICY": "review the insurance policy",
    "MODULE_FIRMWARE_UPDATE": "finish the firmware recovery",
    "MODULE_CAMERA_CHECK": "verify the monitoring setup",
}

ROUND1_BLUEPRINT_RULES = (
    ("BP_SECURITY_", "MODULE_PASSWORD_MANAGER"),
    ("BP_SOCIAL_", "MODULE_GIFT_POOLING"),
    ("BP_TRAVEL_", "MODULE_LONG_HAUL_TRIP"),
    ("BP_DAILY_", "MODULE_COUPON_MANAGEMENT"),
    ("BP_HEALTH_", "MODULE_HEALTH_PLAN_ACTIVATION"),
    ("BP_HOME_", "MODULE_FIRMWARE_UPDATE"),
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def describe_steps(steps: list[str]) -> str:
    phrases = [MODULE_ACTIONS.get(step, step) for step in steps]
    if not phrases:
        return "complete the workflow"
    if len(phrases) == 1:
        return phrases[0]
    return ", then ".join(phrases)


def choose_replacement(bp: dict[str, Any], target_module: str) -> list[str] | None:
    all_modules = {
        step.get("module_id")
        for path in bp.get("paths", [])
        for step in path.get("steps", [])
    }
    if target_module == "MODULE_PASSWORD_MANAGER" and "MODULE_PRIVACY_SETTINGS" in all_modules:
        return ["MODULE_PASSWORD_MANAGER", "MODULE_PRIVACY_SETTINGS"]
    if target_module == "MODULE_GIFT_POOLING" and "MODULE_RSVP_EVENT" in all_modules:
        return ["MODULE_GIFT_POOLING", "MODULE_RSVP_EVENT"]
    if target_module == "MODULE_LONG_HAUL_TRIP":
        if {"MODULE_VISA_REQUIREMENTS", "MODULE_BOOK_FLIGHT"}.issubset(all_modules):
            return ["MODULE_VISA_REQUIREMENTS", "MODULE_BOOK_FLIGHT"]
        if {"MODULE_BOOK_HOTEL", "MODULE_VISA_REQUIREMENTS"}.issubset(all_modules):
            return ["MODULE_BOOK_HOTEL", "MODULE_VISA_REQUIREMENTS"]
    if target_module == "MODULE_COUPON_MANAGEMENT" and "MODULE_BANK_OPENING" in all_modules:
        return ["MODULE_BANK_OPENING", "MODULE_COUPON_MANAGEMENT"]
    if target_module == "MODULE_HEALTH_PLAN_ACTIVATION" and "MODULE_INSURANCE_POLICY" in all_modules:
        return ["MODULE_INSURANCE_POLICY", "MODULE_HEALTH_PLAN_ACTIVATION"]
    if target_module == "MODULE_FIRMWARE_UPDATE" and "MODULE_CAMERA_CHECK" in all_modules:
        return ["MODULE_FIRMWARE_UPDATE", "MODULE_CAMERA_CHECK"]
    return None


def extract_blueprint_id(notes: str) -> str | None:
    match = re.search(r"Generated from ([A-Z0-9_]+);", notes or "")
    return match.group(1) if match else None


def add_edge_if_missing(edges: list[dict[str, Any]], src: str, dst: str) -> None:
    for edge in edges:
        if edge.get("from") == src and edge.get("to") == dst:
            return
    edges.append({"from": src, "to": dst, "kind": "alternative"})


def used_modules_from_success_paths(oracle: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for path in oracle.get("success_paths", []):
        for module_id in path.get("required_modules", []):
            if module_id not in seen:
                seen.add(module_id)
                ordered.append(module_id)
        for module_id in path.get("optional_modules", []):
            if module_id not in seen:
                seen.add(module_id)
                ordered.append(module_id)
    return ordered


def infer_round1_target_module(blueprint_id: str) -> str | None:
    for prefix, module_id in ROUND1_BLUEPRINT_RULES:
        if blueprint_id.startswith(prefix):
            return module_id
    return None


def common_effect_target_state(bp: dict[str, Any], modules_by_id: dict[str, dict[str, Any]]) -> list[str]:
    path_effects: list[set[str]] = []
    for path in bp.get("paths", []):
        adds: set[str] = set()
        for step in path.get("steps", []):
            module_id = step.get("module_id")
            if not module_id or module_id not in modules_by_id:
                continue
            adds |= set(modules_by_id[module_id].get("effects", {}).get("adds", []))
        if adds:
            path_effects.append(adds)
    if not path_effects:
        return list(bp.get("target_state", []))
    common = set(path_effects[0])
    for adds in path_effects[1:]:
        common &= adds
    if not common:
        return list(bp.get("target_state", []))
    return sorted(common)


def main() -> None:
    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc["blueprints"]
    modules_doc = load_json(MODULES_PATH)
    modules_by_id = {module["module_id"]: module for module in modules_doc["modules"]}

    changed_blueprints: dict[str, dict[str, Any]] = {}
    for bp in blueprints:
        target_module = infer_round1_target_module(bp["blueprint_id"])
        if target_module not in TARGET_MODULES:
            continue
        replacement = choose_replacement(bp, target_module)
        if not replacement:
            continue
        changed = False
        for path in bp.get("paths", []):
            steps = [step.get("module_id") for step in path.get("steps", [])]
            if steps == [target_module]:
                path["steps"] = [{"module_id": module_id} for module_id in replacement]
                changed = True
                steps = list(replacement)
            if steps == replacement:
                changed = True
                changed_blueprints[bp["blueprint_id"]] = {
                    "path_id": path["path_id"],
                    "old_steps": [target_module],
                    "new_steps": replacement,
                    "new_target_state": [],
                }
        if changed:
            patched = changed_blueprints[bp["blueprint_id"]]
            patched["new_target_state"] = common_effect_target_state(bp, modules_by_id)
            paths = bp.get("paths", [])
            alt_paths = {path["path_id"]: [step.get("module_id") for step in path.get("steps", [])] for path in paths}
            other_steps = next(
                (
                    steps
                    for path_id, steps in alt_paths.items()
                    if path_id != patched["path_id"]
                ),
                [],
            )
            bp["distinctness_rule"] = (
                f"Either {describe_steps(patched['new_steps'])}, "
                f"or {describe_steps(other_steps)} to reach the same target."
            )
            bp["notes_template"] = bp["distinctness_rule"]
            bp["target_state"] = list(patched["new_target_state"])
            visible = dict(bp.get("visible_constraints", {}) or {})
            visible["preferred_outcomes"] = list(patched["new_target_state"])
            bp["visible_constraints"] = visible

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    patched_goal_count = 0
    patched_oracle_count = 0
    for split in ["dev", "test", "train"]:
        manifest = load_json(BATCH_ROOT / split / "manifest.json")
        for ref in manifest.get("goals", []):
            goal_path = BATCH_ROOT / split / ref["goal_file"]
            oracle_path = BATCH_ROOT / split / ref["oracle_file"]
            goal = load_json(goal_path)
            blueprint_id = extract_blueprint_id(goal.get("notes", ""))
            if blueprint_id not in changed_blueprints:
                continue
            patch = changed_blueprints[blueprint_id]

            goal["target_state"] = list(patch["new_target_state"])
            visible_constraints = dict(goal.get("visible_constraints", {}) or {})
            visible_constraints["preferred_outcomes"] = list(patch["new_target_state"])
            goal["visible_constraints"] = visible_constraints
            goal["notes"] = (
                f"Generated from {blueprint_id}; "
                f"{describe_steps(patch['new_steps']).capitalize()} to reach the compact route, "
                f"instead of using the previous one-step shortcut."
            )
            save_json(goal_path, goal)
            patched_goal_count += 1

            oracle = load_json(oracle_path)
            path_lookup = {path["path_id"]: path for path in oracle.get("success_paths", [])}
            path = path_lookup[patch["path_id"]]
            module_to_invocation = {
                inv["module_id"]: inv["invocation_id"]
                for inv in oracle.get("reference_invocations", [])
            }
            path["required_modules"] = patch["new_steps"]
            path["reference_invocation_ids"] = [
                module_to_invocation[module_id] for module_id in patch["new_steps"]
            ]
            path["optional_modules"] = []

            for success_path in oracle.get("success_paths", []):
                success_path["terminal_predicates"] = list(patch["new_target_state"])

            used_modules = set(used_modules_from_success_paths(oracle))
            oracle["reference_invocations"] = [
                inv for inv in oracle.get("reference_invocations", [])
                if inv.get("module_id") in used_modules
            ]
            oracle["module_nodes"] = [
                node for node in oracle.get("module_nodes", [])
                if node.get("module_id") in used_modules
            ]
            edges = oracle.setdefault("dependency_edges", [])
            edges[:] = [
                edge
                for edge in edges
                if edge.get("from") in used_modules and edge.get("to") in used_modules
            ]
            for src, dst in zip(patch["new_steps"], patch["new_steps"][1:]):
                add_edge_if_missing(edges, src, dst)

            # Keep composition text aligned with the patched blueprint wording.
            oracle["composition"]["distinctness_rule"] = next(
                bp["distinctness_rule"]
                for bp in blueprints
                if bp["blueprint_id"] == blueprint_id
            )
            oracle.setdefault("evaluation", {})["final_success"] = list(patch["new_target_state"])

            save_json(oracle_path, oracle)
            patched_oracle_count += 1

    print(
        json.dumps(
            {
                "patched_blueprints": len(changed_blueprints),
                "patched_goals": patched_goal_count,
                "patched_oracles": patched_oracle_count,
                "blueprint_ids": sorted(changed_blueprints),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
