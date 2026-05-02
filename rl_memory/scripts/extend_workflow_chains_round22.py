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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round22".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND22_SPECS: dict[str, dict[str, Any]] = {
    "BP_SUPPORT_DIRECT_REMEDY_ESCALATION": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": ["shop_order_delivered"],
        "target_state": [
            "support_contacted",
            "post_purchase_remedy_requested",
            "product_review_submitted",
            "merchant_blacklisted",
        ],
        "instruction_templates": [
            "Finish the direct-remedy support workflow only after support is contacted, a post-purchase remedy is requested, a product review is submitted, and the merchant is blacklisted.",
            "Close the direct-remedy route by escalating support and remedy handling before ending with review submission and merchant blacklisting."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; direct-remedy support workflows should continue through review and blacklist resolution instead of stopping after a shallow two-step escalation."
        ),
        "distinctness_rule": (
            "Either contact support, open the warranty remedy, and then finalize the review-blacklist step, "
            "or use the logistics route before reaching the same remedied-and-blacklisted support outcome through a return."
        ),
        "paths": [
            (
                "path_contact_warranty_blacklist",
                [
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_WARRANTY_CLAIM",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
            (
                "path_logistics_return_blacklist",
                [
                    "MODULE_LOGISTICS_FIX",
                    "MODULE_RETURN",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
        ],
    },
    "BP_SUPPORT_EXIT_CONTACT_DUAL": {
        "difficulty": 5,
        "max_steps": 44,
        "max_module_invocations": 4,
        "initial_world_state": ["subscription_active", "shop_order_delivered"],
        "target_state": [
            "support_contacted",
            "refund_requested",
            "subscription_canceled",
            "subscription_exit_processed",
        ],
        "instruction_templates": [
            "Finish the subscription-exit workflow only after support is contacted, a refund is requested, the subscription is canceled, and the subscription exit is fully processed.",
            "Close the exit-contact route by resolving the support, refund, and cancellation steps before the subscription is fully closed."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; subscription-exit workflows should use a real support channel and refund escalation before the final exit state instead of stopping after a two-step shortcut."
        ),
        "distinctness_rule": (
            "Either open a direct support contact on the recent order, request the refund, and then cancel the subscription, "
            "or reach customer service first, cancel the subscription next, and only then resolve the refund route to the same exited state."
        ),
        "paths": [
            (
                "path_contact_refund_cancel",
                [
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_SUBSCRIPTION_REFUND",
                    "MODULE_CANCEL_SUBSCRIPTION",
                ],
            ),
            (
                "path_service_cancel_refund",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_CANCEL_SUBSCRIPTION",
                    "MODULE_SUBSCRIPTION_REFUND",
                ],
            ),
        ],
    },
    "BP_TRAVEL_BOOKING_EXPENSE_PACKET": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": [],
        "target_state": [
            "travel_booking_confirmed",
            "expense_report_submitted",
        ],
        "instruction_templates": [
            "Finish the travel booking-expense workflow only after travel is booked and the expense report is submitted through a complete travel-prep route.",
            "Close the booking-expense route by extending the travel booking into a fuller prep chain before filing the expense report."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; booking-expense workflows should include a real travel-prep step before the report instead of stopping after a shallow two-step booking shortcut."
        ),
        "distinctness_rule": (
            "Either book the flight, arrange the airport transfer, and then submit the expense report, "
            "or assemble the hotel-plus-flight route before reaching the same booked-and-reported travel outcome."
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
                "path_hotel_flight_expense",
                [
                    "MODULE_BOOK_HOTEL",
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
        ],
    },
    "BP_TRAVEL_BOOKING_TOPUP": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": [],
        "target_state": [
            "travel_booking_confirmed",
            "transit_balance_topped_up",
        ],
        "instruction_templates": [
            "Finish the travel booking-topup workflow only after travel is booked and transit balance is topped up through a complete travel-prep route.",
            "Close the booking-topup route by extending the travel booking into a fuller prep chain before the final transit top-up."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; booking-topup workflows should include a real travel-prep step before the transit top-up instead of stopping after a two-step shortcut."
        ),
        "distinctness_rule": (
            "Either book the flight, arrange the airport transfer, and then top up transit, "
            "or assemble the long-haul-plus-hotel route before reaching the same booked-and-topped-up travel outcome."
        ),
        "paths": [
            (
                "path_flight_transfer_topup",
                [
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_TRANSPORT_TOPUP",
                ],
            ),
            (
                "path_longhaul_hotel_topup",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_BOOK_HOTEL",
                    "MODULE_TRANSPORT_TOPUP",
                ],
            ),
        ],
    },
    "BP_CRISIS_CARD_LIQUIDITY_CONTAINMENT": {
        "difficulty": 6,
        "max_steps": 46,
        "max_module_invocations": 4,
        "initial_world_state": ["bank_account_active"],
        "target_state": [
            "account_access_contained",
            "crisis_intake_completed",
            "password_reset_completed",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "Finish the crisis-liquidity workflow only after access is contained, intake is completed, password reset is completed, and emergency liquidity is secured.",
            "Close the crisis route by handling containment or intake first, restoring access next, and ending with emergency liquidity secured."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; crisis-liquidity workflows should include explicit account recovery between the intake signal and the urgent-loan step instead of stopping after a two-step shortcut."
        ),
        "distinctness_rule": (
            "Either freeze the compromised card, complete end-to-end password recovery, and then secure emergency liquidity, "
            "or report the crisis intake before reaching the same recovered-and-liquid state through the recovery route."
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
                "path_illness_recovery_loan",
                [
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND22_SPECS.get(blueprint_id)
    if spec is None:
        return None
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
        raise SystemExit("round22 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
