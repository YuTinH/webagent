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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round17".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND17_SPECS: dict[str, dict[str, Any]] = {
    "BP_NEWCOMER_FINANCE_BANK": {
        "difficulty": 5,
        "max_steps": 44,
        "max_module_invocations": 4,
        "target_state": [
            "housing_finance_prepared",
            "bank_account_active",
            "mobile_service_active",
        ],
        "instruction_templates": [
            "Finish the newcomer finance workflow only after housing finance is prepared, the bank account is active, and mobile service is active.",
            "Close the newcomer setup route by preparing the housing finance first, opening the bank account next, and ending with mobile service active.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; newcomer finance should not stop at lease paperwork, but continue through banking and mobile-service activation."
        ),
        "distinctness_rule": (
            "Either register the lease contract, open the bank account, and then activate mobile service, "
            "or review lease management before reaching the same bank-and-connectivity outcome."
        ),
        "paths": [
            (
                "path_registration_bank_mobile",
                [
                    "MODULE_LEASE_CONTRACT_REGISTRATION",
                    "MODULE_BANK_OPENING",
                    "MODULE_MOBILE_PLAN_SIGNUP",
                ],
            ),
            (
                "path_review_bank_mobile",
                [
                    "MODULE_LEASE_MANAGEMENT_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_MOBILE_PLAN_SIGNUP",
                ],
            ),
        ],
    },
    "BP_NEWCOMER_WORKFLOW_CONNECTIVITY_FINANCE": {
        "difficulty": 5,
        "max_steps": 50,
        "max_module_invocations": 5,
        "target_state": [
            "lease_active",
            "housing_finance_prepared",
            "mobile_service_active",
        ],
        "instruction_templates": [
            "Finish the newcomer connectivity workflow only after housing is secured, housing finance is prepared, and mobile service is active.",
            "Close the newcomer onboarding route by securing housing first, preparing the finance paperwork next, and ending with mobile service active.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; connectivity-oriented newcomer flows should include housing bootstrap before the finance and mobile steps."
        ),
        "distinctness_rule": (
            "Either secure housing, register the lease contract, and then activate mobile service, "
            "or secure housing before reaching the same finance-and-connectivity outcome through lease-management review."
        ),
        "paths": [
            (
                "path_home_registration_mobile",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_LEASE_CONTRACT_REGISTRATION",
                    "MODULE_MOBILE_PLAN_SIGNUP",
                ],
            ),
            (
                "path_home_review_mobile",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_LEASE_MANAGEMENT_REVIEW",
                    "MODULE_MOBILE_PLAN_SIGNUP",
                ],
            ),
        ],
    },
    "BP_NEWCOMER_WORKFLOW_FINANCE_RESIDENCY": {
        "difficulty": 5,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "housing_finance_prepared",
            "residency_record_verified",
            "bank_account_active",
        ],
        "instruction_templates": [
            "Finish the newcomer residency workflow only after housing finance is prepared, residency records are verified, and the bank account is active.",
            "Close the newcomer residency route by preparing the housing finance first, verifying residency next, and ending with the bank account active.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; finance-residency newcomer flows should include a real banking closeout after the residency-verification step."
        ),
        "distinctness_rule": (
            "Either register the lease contract, collect address proof, and then open the bank account, "
            "or review lease management before reaching the same finance-and-residency outcome through utility setup."
        ),
        "paths": [
            (
                "path_registration_proof_bank",
                [
                    "MODULE_LEASE_CONTRACT_REGISTRATION",
                    "MODULE_ADDRESS_PROOF",
                    "MODULE_BANK_OPENING",
                ],
            ),
            (
                "path_review_utility_bank",
                [
                    "MODULE_LEASE_MANAGEMENT_REVIEW",
                    "MODULE_UTILITY_SETUP",
                    "MODULE_BANK_OPENING",
                ],
            ),
        ],
    },
}


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
        spec = ROUND17_SPECS.get(blueprint_id)
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
        raise SystemExit("round17 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
