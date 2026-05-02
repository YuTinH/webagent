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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round9".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND9_SPECS: dict[str, dict[str, Any]] = {
    "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED": {
        "difficulty": 5,
        "max_steps": 32,
        "max_module_invocations": 4,
        "target_state": [
            "account_issue_triaged",
            "account_access_contained",
            "replacement_card_requested",
        ],
        "instruction_templates": [
            "Close the card-issue workflow only after the account issue is triaged, access is contained, and the replacement card request is already on file.",
            "Finish the finance route by triaging the account issue first, containing access second, and ending with the replacement card request submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; lost-card handling should not stop after shallow triage, "
            "but continue through containment before the replacement request is filed."
        ),
        "distinctness_rule": (
            "Either review the balance, freeze the compromised card, and then request the replacement, "
            "or aggregate the bills before freezing the card and reaching the same contained-access replacement outcome."
        ),
        "paths": [
            (
                "path_balance_freeze_replace",
                [
                    "MODULE_CHECK_BALANCE",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
            (
                "path_bills_freeze_replace",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_CARD_REPLACEMENT",
                ],
            ),
        ],
    },
    "BP_FINANCE_CARD_TRIAGE_REPLACEMENT": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_TRIAGE_REPLACEMENT": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_TRIAGE_REPLACEMENT_ALIGNMENT": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_TRIAGE_REPLACEMENT_DUAL": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_ZTRAIN_01_TRIAGE_REPLACEMENT_DUAL": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_ZTRAIN_04_TRIAGE_REPLACEMENT_DUAL": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_ZTRAIN_07_TRIAGE_REPLACEMENT_DUAL": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_ZTRAIN_10_TRIAGE_REPLACEMENT_DUAL": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_FINANCE_ZTRAIN_13_TRIAGE_REPLACEMENT_DUAL": {
        "alias_of": "BP_FINANCE_TRIAGE_REPLACEMENT_HARDENED",
    },
    "BP_GOV_LOCAL_VEHICLE_COMPLIANCE": {
        "difficulty": 5,
        "max_steps": 55,
        "max_module_invocations": 5,
        "target_state": [
            "address_confirmation_verified",
            "parking_permit_active",
            "local_vehicle_compliance_verified",
        ],
        "instruction_templates": [
            "Finish the civic vehicle workflow only after address confirmation is verified, the parking permit is active, and local vehicle compliance is verified.",
            "Close the local vehicle route by confirming the address first, activating the permit second, and ending with compliance verification complete.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; vehicle compliance should include actual address verification support "
            "before the permit and compliance steps are considered complete."
        ),
        "distinctness_rule": (
            "Either secure housing, collect address proof, activate the parking permit, and then complete renewal-based compliance, "
            "or secure housing, activate utilities, update the vehicle address, and then reach the same verified-permit compliance state."
        ),
        "paths": [
            (
                "path_proof_permit_renewal",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_ADDRESS_PROOF",
                    "MODULE_PARKING_PERMIT_APPLICATION",
                    "MODULE_PERMIT_RENEWAL",
                ],
            ),
            (
                "path_utility_update_permit",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_UTILITY_SETUP",
                    "MODULE_VEHICLE_ADDRESS_UPDATE",
                    "MODULE_PARKING_PERMIT_APPLICATION",
                ],
            ),
        ],
    },
    "BP_TRAVEL_STAY_EXPENSE_READY": {
        "difficulty": 5,
        "max_steps": 55,
        "max_module_invocations": 4,
        "target_state": [
            "travel_booking_confirmed",
            "airport_transfer_arranged",
            "expense_report_submitted",
        ],
        "instruction_templates": [
            "Leave the travel-admin workflow only after the booking is confirmed, the airport transfer is arranged, and the expense report is filed.",
            "Finish the travel route by locking the booking first, arranging the airport transfer next, and ending with the expense report submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; travel-expense closure should include ground-transfer logistics, "
            "not just a direct booking plus expense-report shortcut."
        ),
        "distinctness_rule": (
            "Either book the flight, arrange the airport transfer, and then submit the expense report, "
            "or use the long-haul booking bundle before reaching the same transfer-and-expense closure."
        ),
        "paths": [
            (
                "path_flight_transfer_expense",
                [
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
            (
                "path_longhaul_transfer_expense",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
        ],
    },
    "BP_TRAVEL_FLIGHT_COMMUTE_READY": {
        "difficulty": 5,
        "max_steps": 50,
        "max_module_invocations": 4,
        "target_state": [
            "flight_booked",
            "airport_transfer_arranged",
            "commute_route_checked",
        ],
        "instruction_templates": [
            "Finish the departure workflow only after the flight is booked, the airport transfer is arranged, and the onward commute route is checked.",
            "Close the travel-readiness route by securing the flight first, arranging the airport transfer second, and ending with the commute plan checked.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; departure readiness should include airport-transfer planning "
            "instead of ending right after a direct commute check."
        ),
        "distinctness_rule": (
            "Either book the flight directly, arrange the airport transfer, and then check the commute route, "
            "or use the long-haul travel bundle before reaching the same transfer-and-commute outcome."
        ),
        "paths": [
            (
                "path_flight_transfer_commute",
                [
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_COMMUTE_ROUTE",
                ],
            ),
            (
                "path_longhaul_transfer_commute",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_COMMUTE_ROUTE",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_AUTOPAY_ORCHESTRATION": {
        "difficulty": 5,
        "max_steps": 55,
        "max_module_invocations": 4,
        "target_state": [
            "bank_account_active",
            "bills_aggregated",
            "autopay_enabled",
        ],
        "instruction_templates": [
            "Finish the payment-orchestration workflow only after the bank account is active, the bills are aggregated, and autopay ends in the enabled state.",
            "Close the composite autopay route by activating the account first, consolidating the bills next, and ending with autopay fully enabled.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; autopay setup should include bill consolidation as an explicit administrative step, "
            "not just account opening plus a one-click autopay action."
        ),
        "distinctness_rule": (
            "Either open the bank account, aggregate the bills, and then enable standard autopay, "
            "or open the same account, aggregate the bills, and then reach the same autopay state through the complex-autopay route."
        ),
        "paths": [
            (
                "path_standard_autopay_with_bills",
                [
                    "MODULE_BANK_OPENING",
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_AUTOPAY",
                ],
            ),
            (
                "path_complex_autopay_with_bills",
                [
                    "MODULE_BANK_OPENING",
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_COMPLEX_AUTOPAY",
                ],
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND9_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND9_SPECS[alias]
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
        raise SystemExit("round9 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    refreshed_counts = {"dev": 0, "test": 0, "train": 0}
    for split in ["dev", "test", "train"]:
        manifest = load_json(BATCH_ROOT / split / "manifest.json")
        for ref in manifest.get("goals", []):
            blueprint_id = ref["blueprint_id"]
            if blueprint_id not in patched_blueprints:
                continue

            blueprint = patched_blueprints[blueprint_id]
            seed = stable_goal_seed(ref["goal_id"], blueprint_id)
            rng = random.Random(seed)
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
