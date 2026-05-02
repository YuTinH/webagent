#!/usr/bin/env python3
import copy
import hashlib
import importlib.util
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"
BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
GENERATOR_PATH = ROOT / "rl_memory" / "scripts" / "generate_workflow_goal_batch.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load_generator_module():
    spec = importlib.util.spec_from_file_location("workflow_goal_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load generator from {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_step_lookup(paths: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in paths:
        for step in path.get("steps", []):
            module_id = step.get("module_id")
            if module_id and module_id not in lookup:
                lookup[module_id] = copy.deepcopy(step)
    return lookup


def build_global_step_lookup(blueprints: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for blueprint in blueprints:
        for module_id, step in base_step_lookup(blueprint.get("paths", [])).items():
            lookup.setdefault(module_id, step)
    return lookup


def step_from_lookup(
    local_lookup: dict[str, dict[str, Any]],
    global_lookup: dict[str, dict[str, Any]],
    allowed_shared_vars: set[str],
    module_id: str,
) -> dict[str, Any]:
    if module_id in local_lookup:
        step = copy.deepcopy(local_lookup[module_id])
    elif module_id in global_lookup:
        step = copy.deepcopy(global_lookup[module_id])
    else:
        step = {"module_id": module_id}

    bindings = step.get("parameter_bindings")
    if isinstance(bindings, dict):
        referenced = {
            value[1:]
            for value in bindings.values()
            if isinstance(value, str) and value.startswith("@")
        }
        if not referenced.issubset(allowed_shared_vars):
            step.pop("parameter_bindings", None)
    return step


def build_path(
    local_lookup: dict[str, dict[str, Any]],
    global_lookup: dict[str, dict[str, Any]],
    allowed_shared_vars: set[str],
    path_id: str,
    module_ids: list[str],
    kind: str = "alternative",
) -> dict[str, Any]:
    return {
        "path_id": path_id,
        "kind": kind,
        "steps": [
            step_from_lookup(local_lookup, global_lookup, allowed_shared_vars, module_id)
            for module_id in module_ids
        ],
    }


def replace_preferred_outcomes(existing: dict[str, Any], outcomes: list[str]) -> dict[str, Any]:
    updated = copy.deepcopy(existing)
    updated["preferred_outcomes"] = outcomes
    return updated


def stable_goal_seed(goal_id: str, blueprint_id: str) -> int:
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round19".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND19_SPECS: dict[str, dict[str, Any]] = {
    "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_LIQUIDITY": {
        "difficulty": 6,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "account_access_contained",
            "crisis_intake_completed",
            "password_reset_completed",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "Finish the crisis workflow only after access is contained, intake is completed, password reset is completed, and emergency liquidity is secured.",
            "Close the crisis route by handling intake or containment first, restoring access next, and ending with emergency liquidity secured.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; crisis liquidity should come only after the intake or containment step is followed by real access recovery."
        ),
        "distinctness_rule": (
            "Either freeze the compromised card, complete end-to-end password recovery, and then secure emergency liquidity, "
            "or report the supply disruption before reaching the same recovered-and-liquid crisis state."
        ),
        "paths": [
            (
                "path_freeze_recovery_loan",
                [
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
            (
                "path_supply_recovery_loan",
                [
                    "MODULE_SUPPLY_DISRUPTION",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
    "BP_CRISIS_SUPPLY_LIQUIDITY_STABILIZATION": {
        "alias_of": "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_FREEZE_SUPPLY_STABILIZATION": {
        "alias_of": "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_CONTAINMENT_INTAKE": {
        "alias_of": "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_CONTAINMENT_INTAKE_BRIDGE": {
        "alias_of": "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_CONTAINMENT_LIQUIDITY_ALIGNMENT": {
        "alias_of": "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_ILLNESS_SUPPLY_RECOVERY_LIQUIDITY": {
        "difficulty": 6,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "account_access_contained",
            "crisis_intake_completed",
            "password_reset_completed",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "Finish the crisis-liquidity workflow only after intake is completed, access is contained, password reset is completed, and emergency liquidity is secured.",
            "Close the crisis route by logging the intake first, restoring access next, and ending with emergency liquidity secured.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; crisis-liquidity workflows should include explicit access recovery after the intake signal and before the urgent-loan step."
        ),
        "distinctness_rule": (
            "Either report the illness, complete end-to-end password recovery, and then secure emergency liquidity, "
            "or report the supply disruption before reaching the same recovered-and-liquid crisis state."
        ),
        "paths": [
            (
                "path_illness_recovery_loan",
                [
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
            (
                "path_supply_recovery_loan",
                [
                    "MODULE_SUPPLY_DISRUPTION",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
    "BP_CRISIS_REPORT_LIQUIDITY_STABILIZATION": {
        "alias_of": "BP_CRISIS_ILLNESS_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_INTAKE_LIQUIDITY_SPLIT": {
        "alias_of": "BP_CRISIS_ILLNESS_SUPPLY_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_ILLNESS_FREEZE_RECOVERY_LIQUIDITY": {
        "difficulty": 6,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "account_access_contained",
            "crisis_intake_completed",
            "password_reset_completed",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "Finish the crisis-response workflow only after intake is completed, access is contained, password reset is completed, and emergency liquidity is secured.",
            "Close the crisis workflow by recording the intake or containment first, restoring access next, and ending with emergency liquidity secured.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; intake-driven crisis workflows should include a real account-recovery step before the liquidity action."
        ),
        "distinctness_rule": (
            "Either report the illness, complete end-to-end password recovery, and then secure emergency liquidity, "
            "or freeze the compromised card before reaching the same recovered-and-liquid crisis state."
        ),
        "paths": [
            (
                "path_illness_recovery_loan",
                [
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
            (
                "path_freeze_recovery_loan",
                [
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
    "BP_CRISIS_INTAKE_LIQUIDITY_ROUTE": {
        "alias_of": "BP_CRISIS_ILLNESS_FREEZE_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_WORKFLOW_INTAKE_LIQUIDITY": {
        "alias_of": "BP_CRISIS_ILLNESS_FREEZE_RECOVERY_LIQUIDITY",
    },
    "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_REPLACEMENT": {
        "difficulty": 6,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "account_access_contained",
            "crisis_intake_completed",
            "password_reset_completed",
            "replacement_card_requested",
        ],
        "instruction_templates": [
            "Finish the crisis-replacement workflow only after access is contained, intake is completed, password reset is completed, and the replacement card is requested.",
            "Close the crisis replacement route by handling containment or intake first, restoring access next, and ending with the replacement card requested.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; crisis replacement should come only after the intake or containment path is followed by explicit access recovery."
        ),
        "distinctness_rule": (
            "Either freeze the compromised card, complete end-to-end password recovery, and then request the replacement card, "
            "or report the supply disruption before reaching the same recovered-and-replaced crisis state."
        ),
        "paths": [
            (
                "path_freeze_recovery_replace",
                [
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
            (
                "path_supply_recovery_replace",
                [
                    "MODULE_SUPPLY_DISRUPTION",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
        ],
    },
    "BP_CRISIS_CONTAINMENT_REPLACEMENT_ROUTE": {
        "alias_of": "BP_CRISIS_FREEZE_SUPPLY_RECOVERY_REPLACEMENT",
    },
    "BP_CRISIS_ILLNESS_FREEZE_RECOVERY_REPLACEMENT": {
        "difficulty": 6,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "account_access_contained",
            "crisis_intake_completed",
            "password_reset_completed",
            "replacement_card_requested",
        ],
        "instruction_templates": [
            "Finish the intake-replacement workflow only after intake is completed, access is contained, password reset is completed, and the replacement card is requested.",
            "Close the crisis replacement route by recording intake or containment first, restoring access next, and ending with the replacement card requested.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; intake-to-replacement workflows should include a real account-recovery step before the replacement request."
        ),
        "distinctness_rule": (
            "Either report the illness, complete end-to-end password recovery, and then request the replacement card, "
            "or freeze the compromised card before reaching the same recovered-and-replaced crisis state."
        ),
        "paths": [
            (
                "path_illness_recovery_replace",
                [
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
            (
                "path_freeze_recovery_replace",
                [
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
        ],
    },
    "BP_CRISIS_INTAKE_REPLACEMENT_ALIGNMENT": {
        "alias_of": "BP_CRISIS_ILLNESS_FREEZE_RECOVERY_REPLACEMENT",
    },
    "BP_CRISIS_ILLNESS_CONTAINMENT_ROUTE": {
        "difficulty": 6,
        "max_steps": 44,
        "max_module_invocations": 4,
        "target_state": [
            "illness_report_submitted",
            "account_access_contained",
            "replacement_card_requested",
        ],
        "instruction_templates": [
            "Finish the illness-containment workflow only after the illness report is submitted, access is contained, and the replacement card is requested.",
            "Close the illness response route by filing the illness report first, containing access next, and ending with the replacement card requested.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; illness-containment workflows should continue through a concrete replacement action instead of stopping after a shallow containment branch."
        ),
        "distinctness_rule": (
            "Either report the illness, freeze the compromised card, and then request the replacement card, "
            "or report the same illness before reaching the same contained-and-replaced outcome through end-to-end password recovery."
        ),
        "paths": [
            (
                "path_illness_freeze_replace",
                [
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
            (
                "path_illness_recovery_replace",
                [
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
        ],
    },
    "BP_CRISIS_RESET_LIQUIDITY": {
        "difficulty": 6,
        "max_steps": 56,
        "max_module_invocations": 5,
        "initial_world_state": ["bank_account_active"],
        "target_state": [
            "password_reset_completed",
            "crisis_intake_completed",
            "account_access_contained",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "Finish the reset crisis workflow only after password reset is completed, crisis intake is completed, access is contained, and emergency liquidity is secured.",
            "Close the crisis reset route by finishing reset first, completing intake next, restoring access, and ending with emergency liquidity secured.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; reset-driven crisis workflows should continue through access recovery and emergency liquidity instead of stopping after intake."
        ),
        "distinctness_rule": (
            "Either request the reset code, complete the reset, report the illness, restore account access, and then secure emergency liquidity, "
            "or use end-to-end password recovery before reaching the same reset-and-liquidity crisis state through supply-disruption intake."
        ),
        "paths": [
            (
                "path_code_reset_illness_recovery_loan",
                [
                    "MODULE_PASSWORD_RESET_REQUEST",
                    "MODULE_PASSWORD_RESET_COMPLETION",
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
            (
                "path_recovery_supply_loan",
                [
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_SUPPLY_DISRUPTION",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
    "BP_CRISIS_RESET_INTAKE": {
        "alias_of": "BP_CRISIS_RESET_LIQUIDITY",
    },
    "BP_CRISIS_WORKFLOW_RESET_INTAKE": {
        "alias_of": "BP_CRISIS_RESET_LIQUIDITY",
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND19_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND19_SPECS[alias]
        merged = {key: copy.deepcopy(value) for key, value in base.items() if key != "alias_of"}
        for key, value in spec.items():
            if key != "alias_of":
                merged[key] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(spec)


def main() -> None:
    generator = load_generator_module()
    modules_doc = load_json(generator.MODULE_LIBRARY)
    modules_by_id = {m["module_id"]: m for m in modules_doc["modules"]}
    bindings_doc = load_json(generator.BINDING_LIBRARY)
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings_doc["bindings"]:
        bindings_by_module[binding["module_id"]].append(binding)
    requirements = load_json(generator.QUALITY_REQUIREMENTS)

    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc["blueprints"]
    global_lookup = build_global_step_lookup(blueprints)

    patched_blueprints: dict[str, dict[str, Any]] = {}
    validation_issues: list[str] = []

    for bp in blueprints:
        blueprint_id = bp["blueprint_id"]
        spec = resolve_spec(blueprint_id)
        if spec is None:
            continue

        local_lookup = base_step_lookup(bp.get("paths", []))
        allowed_shared_vars = set(bp.get("shared_variable_pools", {}).keys())
        target_state = spec["target_state"]

        bp["difficulty"] = spec["difficulty"]
        bp["max_steps"] = spec["max_steps"]
        bp["max_module_invocations"] = spec["max_module_invocations"]
        bp["target_state"] = copy.deepcopy(target_state)
        bp["instruction_templates"] = copy.deepcopy(spec["instruction_templates"])
        bp["visible_constraints"] = replace_preferred_outcomes(bp.get("visible_constraints", {}), target_state)
        bp["notes_template"] = spec["notes_template"]
        bp["distinctness_rule"] = spec["distinctness_rule"]
        if "initial_world_state" in spec:
            bp["initial_world_state"] = copy.deepcopy(spec["initial_world_state"])
        bp["paths"] = [
            build_path(
                local_lookup,
                global_lookup,
                allowed_shared_vars,
                path_id,
                module_ids,
            )
            for path_id, module_ids in spec["paths"]
        ]

        issues = generator.validate_blueprint(bp, modules_by_id, requirements)
        if issues:
            validation_issues.extend(issues)
        patched_blueprints[blueprint_id] = copy.deepcopy(bp)

    if validation_issues:
        raise SystemExit("round19 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    refreshed_counts = {"dev": 0, "test": 0, "train": 0}
    for split in ["dev", "test", "train"]:
        manifest = load_json(BATCH_ROOT / split / "manifest.json")
        for ref in manifest.get("goals", []):
            blueprint_id = ref["blueprint_id"]
            if blueprint_id not in patched_blueprints:
                continue

            blueprint = patched_blueprints[blueprint_id]
            rng = random.Random(stable_goal_seed(ref["goal_id"], blueprint_id))
            shared_vars = generator.sample_shared_variables(blueprint, rng)
            goal = generator.build_goal(ref["goal_id"], blueprint, shared_vars, rng)
            oracle = generator.build_oracle(
                ref["goal_id"],
                blueprint,
                modules_by_id,
                bindings_by_module,
                shared_vars,
            )
            save_json(BATCH_ROOT / split / ref["goal_file"], goal)
            save_json(BATCH_ROOT / split / ref["oracle_file"], oracle)
            refreshed_counts[split] += 1

    print(
        json.dumps(
            {
                "patched_blueprints": sorted(patched_blueprints),
                "patched_blueprint_count": len(patched_blueprints),
                "refreshed_counts": refreshed_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
