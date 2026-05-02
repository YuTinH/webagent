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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round10".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND10_SPECS: dict[str, dict[str, Any]] = {
    "BP_TRAVEL_CLEARANCE_HOTEL_HARDENED": {
        "difficulty": 5,
        "max_steps": 55,
        "max_module_invocations": 4,
        "target_state": [
            "mobility_clearance_verified",
            "hotel_booked",
            "expense_report_submitted",
        ],
        "instruction_templates": [
            "Finish the travel-admin route only after mobility clearance is verified, the hotel is booked, and the expense report is filed.",
            "Close the stay-readiness workflow by clearing mobility first, securing the hotel second, and ending with the expense report submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; mobility-and-stay workflows should continue through expense filing, "
            "not stop after a shallow hotel-booking shortcut."
        ),
        "distinctness_rule": (
            "Either verify mobility clearance, book the hotel, and then submit the expense report, "
            "or use the long-haul bundle before reaching the same hotel-and-expense closure."
        ),
        "paths": [
            (
                "path_clearance_hotel_expense",
                [
                    "MODULE_VISA_REQUIREMENTS",
                    "MODULE_BOOK_HOTEL",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
            (
                "path_longhaul_hotel_expense",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_BOOK_HOTEL",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
        ],
    },
    "BP_TRAVEL_CLEARANCE_HOTEL": {
        "alias_of": "BP_TRAVEL_CLEARANCE_HOTEL_HARDENED",
    },
    "BP_TRAVEL_EXPENSE_BOOKING_ALIGNMENT": {
        "difficulty": 5,
        "max_steps": 55,
        "max_module_invocations": 4,
        "target_state": [
            "travel_booking_confirmed",
            "airport_transfer_arranged",
            "expense_report_submitted",
        ],
        "instruction_templates": [
            "Close the booking-expense workflow only after the travel booking is confirmed, the airport transfer is arranged, and the expense report is filed.",
            "Finish the travel-admin route by confirming the booking first, arranging the airport transfer next, and ending with the expense report submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; booking-plus-expense workflows should include airport-transfer logistics, "
            "not just a direct booking action and immediate expense filing."
        ),
        "distinctness_rule": (
            "Either book the flight, arrange the airport transfer, and then submit the expense report, "
            "or use the long-haul bundle before reaching the same transfer-and-expense closure."
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
    "BP_TRAVEL_TOPUP_HARDENED": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 5,
        "target_state": [
            "mobility_clearance_verified",
            "airport_transfer_arranged",
            "transit_balance_topped_up",
        ],
        "instruction_templates": [
            "Finish the departure-readiness workflow only after mobility clearance is verified, the airport transfer is arranged, and the transit balance is topped up.",
            "Close the travel-readiness route by clearing mobility first, arranging the airport transfer second, and ending with the transit balance already topped up.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; mobility-and-topup workflows should include actual airport-transfer logistics "
            "rather than ending after a two-step clearance shortcut."
        ),
        "distinctness_rule": (
            "Either verify the visa requirements, book the flight, arrange the airport transfer, and then top up transit, "
            "or use the long-haul booking bundle before reaching the same transfer-and-topup outcome."
        ),
        "paths": [
            (
                "path_visa_flight_transfer_topup",
                [
                    "MODULE_VISA_REQUIREMENTS",
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_TRANSPORT_TOPUP",
                ],
            ),
            (
                "path_longhaul_transfer_topup",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_TRANSPORT_TOPUP",
                ],
            ),
        ],
    },
    "BP_TRAVEL_CLEARANCE_TOPUP_ALIGNMENT": {
        "alias_of": "BP_TRAVEL_TOPUP_HARDENED",
    },
    "BP_TRAVEL_MOBILITY_TOPUP_READY": {
        "alias_of": "BP_TRAVEL_TOPUP_HARDENED",
    },
    "BP_FINANCE_TRANSFER_ARCHIVE_ALIGNMENT": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "bills_aggregated",
            "payment_stack_prepared",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Finish the payment-admin route only after the bills are aggregated, the payment stack is prepared, and the receipt is archived.",
            "Close the finance workflow by consolidating the bills first, preparing the payment stack second, and ending with the receipt archived.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; payment-stack archiving should include bill consolidation before the funding or autopay branch, "
            "not just a direct payment action plus archive."
        ),
        "distinctness_rule": (
            "Either aggregate the bills, transfer the funds, and then archive the receipt, "
            "or aggregate the same bills before reaching the same archived payment stack through the complex-autopay route."
        ),
        "paths": [
            (
                "path_bills_transfer_archive",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_bills_complex_archive",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
    "BP_FINANCE_TRANSFER_INVESTMENT": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "investment_account_active",
            "transfer_completed",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Finish the investment-funding route only after the investment account is active, the transfer is completed, and the receipt is archived.",
            "Close the finance workflow by activating the investment path first, completing the transfer second, and ending with the receipt archived.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; investment funding should finish with post-transfer recordkeeping, "
            "not stop immediately after the transfer step."
        ),
        "distinctness_rule": (
            "Either activate the investment account, transfer the funds, and then archive the receipt, "
            "or use the growth-verification route before reaching the same funded-and-archived investment outcome."
        ),
        "paths": [
            (
                "path_account_transfer_archive",
                [
                    "MODULE_INVESTMENT_ACCOUNT",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_growth_transfer_archive",
                [
                    "MODULE_INVESTMENT_GROWTH",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
    "BP_FINANCE_WORKFLOW_INVESTMENT_BUDGET": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "investment_account_active",
            "transfer_completed",
            "budget_limit_updated",
        ],
        "instruction_templates": [
            "Finish the investment-budget workflow only after the investment account is active, the transfer is completed, and the budget limit is updated.",
            "Close the finance route by activating investment first, completing the transfer second, and ending with the budget limit already updated.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; investment-and-budget workflows should include actual funding before the final budget control step."
        ),
        "distinctness_rule": (
            "Either activate the investment account, transfer the funds, and then update the budget limit, "
            "or use the growth-verification route before reaching the same funded-and-budgeted investment outcome."
        ),
        "paths": [
            (
                "path_account_transfer_budget",
                [
                    "MODULE_INVESTMENT_ACCOUNT",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_BUDGET_LIMIT_UPDATE",
                ],
            ),
            (
                "path_growth_transfer_budget",
                [
                    "MODULE_INVESTMENT_GROWTH",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_BUDGET_LIMIT_UPDATE",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "delivery_visibility_confirmed",
            "order_tracking_opened",
            "calendar_event_synced",
        ],
        "instruction_templates": [
            "Finish the order-visibility workflow only after delivery visibility is confirmed, detailed tracking is opened, and the calendar event is synced.",
            "Close the composite visibility route by confirming delivery visibility first, opening detailed tracking next, and ending with the calendar sync completed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; visibility-sync workflows should include explicit detailed tracking, "
            "not stop after a shallow visibility-plus-calendar shortcut."
        ),
        "distinctness_rule": (
            "Either confirm delivery through the arrival route, open detailed tracking, and then sync the calendar, "
            "or use customer service before reaching the same tracking-and-calendar visibility outcome."
        ),
        "paths": [
            (
                "path_arrival_tracking_sync",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
            (
                "path_service_tracking_sync",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_CALENDAR_VISIBILITY_SYNC": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_DELIVERY_CALENDAR_ORCHESTRATION": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_WORKFLOW_VISIBILITY_SYNC": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_03_CALENDAR_VISIBILITY_SYNC": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_06_CALENDAR_VISIBILITY_SYNC": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_09_CALENDAR_VISIBILITY_SYNC": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_12_CALENDAR_VISIBILITY_SYNC": {
        "alias_of": "BP_COMPOSITE_VISIBILITY_SYNC_HARDENED",
    },
    "BP_COMPOSITE_VISIBILITY_PAYMENT_STACK": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "calendar_event_synced",
            "delivery_visibility_confirmed",
            "payment_stack_prepared",
        ],
        "instruction_templates": [
            "Finish the visibility-payment workflow only after delivery visibility is confirmed, the calendar event is synced, and the payment stack is prepared.",
            "Close the composite route by confirming visibility first, syncing the calendar next, and ending with the payment stack prepared.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; visibility-payment workflows should include calendar synchronization as an explicit coordination step."
        ),
        "distinctness_rule": (
            "Either sync the calendar, confirm delivery through the arrival route, and then prepare the payment stack, "
            "or sync the same calendar before reaching the same payment-ready visibility state through customer service and complex autopay."
        ),
        "paths": [
            (
                "path_calendar_arrival_payment",
                [
                    "MODULE_EMAIL_CALENDAR",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_TRANSFER_FUNDS",
                ],
            ),
            (
                "path_calendar_service_payment",
                [
                    "MODULE_EMAIL_CALENDAR",
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_COMPLEX_AUTOPAY",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_FOLLOWUP_PAYMENT": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "target_state": [
            "order_followup_prepared",
            "delivery_visibility_confirmed",
            "order_tracking_opened",
            "payment_stack_prepared",
        ],
        "instruction_templates": [
            "Finish the followup-payment workflow only after the order followup is prepared, delivery visibility is confirmed, detailed tracking is opened, and the payment stack is ready.",
            "Close the composite payment route by confirming visibility and opening detailed tracking before ending with the payment stack prepared.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; followup-payment workflows should include explicit tracking and visibility handling, "
            "not stop after a two-step support-or-payment shortcut."
        ),
        "distinctness_rule": (
            "Either use customer service, open detailed tracking, and then transfer the funds, "
            "or open tracking before customer service and reach the same followup-and-payment outcome through complex autopay."
        ),
        "paths": [
            (
                "path_service_tracking_transfer",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_TRANSFER_FUNDS",
                ],
            ),
            (
                "path_tracking_service_complex",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_COMPLEX_AUTOPAY",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_WORKFLOW_FOLLOWUP_SYNC": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "order_followup_prepared",
            "delivery_visibility_confirmed",
            "order_tracking_opened",
            "calendar_event_synced",
        ],
        "instruction_templates": [
            "Finish the followup-sync workflow only after the order followup is prepared, delivery visibility is confirmed, detailed tracking is opened, and the calendar event is synced.",
            "Close the composite coordination route by confirming visibility and opening detailed tracking before ending with the calendar sync completed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; followup-sync workflows should include explicit tracking and visibility handling, "
            "not stop after a shallow followup-plus-calendar shortcut."
        ),
        "distinctness_rule": (
            "Either confirm delivery through the arrival route, open detailed tracking, and then sync the calendar, "
            "or use customer service before reaching the same followup-and-calendar tracking outcome."
        ),
        "paths": [
            (
                "path_arrival_tracking_calendar",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
            (
                "path_service_tracking_calendar",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND10_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND10_SPECS[alias]
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
        raise SystemExit("round10 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
