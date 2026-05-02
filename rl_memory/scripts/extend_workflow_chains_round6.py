#!/usr/bin/env python3
import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def base_step_lookup(paths: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in paths:
        for step in path.get("steps", []):
            module_id = step.get("module_id")
            if module_id and module_id not in lookup:
                lookup[module_id] = copy.deepcopy(step)
    return lookup


def step_from_lookup(lookup: dict[str, dict[str, Any]], module_id: str) -> dict[str, Any]:
    return copy.deepcopy(lookup.get(module_id, {"module_id": module_id}))


def build_path(
    lookup: dict[str, dict[str, Any]],
    path_id: str,
    module_ids: list[str],
    kind: str = "alternative",
) -> dict[str, Any]:
    return {
        "path_id": path_id,
        "kind": kind,
        "steps": [step_from_lookup(lookup, module_id) for module_id in module_ids],
    }


def replace_preferred_outcomes(existing: dict[str, Any], outcomes: list[str]) -> dict[str, Any]:
    updated = copy.deepcopy(existing)
    updated["preferred_outcomes"] = outcomes
    return updated


ROUND6_SPECS: dict[str, dict[str, Any]] = {
    "BP_NEWCOMER_PROOF_BANK_DUAL": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "housing_finance_prepared",
            "address_confirmation_verified",
            "bank_account_active",
        ],
        "instruction_templates": [
            "Finish the newcomer workflow with housing finance prepared, address confirmation verified, and the bank account active.",
            "Close the newcomer route after formalizing housing finance, confirming the address, and activating the bank account.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "housing_finance_prepared",
                "address_confirmation_verified",
                "bank_account_active",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; newcomer settlement should first formalize the lease route, "
            "then confirm the address, and only then finish bank activation."
        ),
        "distinctness_rule": (
            "Either secure housing, register the lease contract, verify the address, and then open the bank account, "
            "or secure housing, review lease management, confirm the address through utilities, and then reach the same banking outcome."
        ),
        "paths": [
            (
                "path_alpha",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_LEASE_CONTRACT_REGISTRATION",
                    "MODULE_ADDRESS_PROOF",
                    "MODULE_BANK_OPENING",
                ],
            ),
            (
                "path_beta",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_LEASE_MANAGEMENT_REVIEW",
                    "MODULE_UTILITY_SETUP",
                    "MODULE_BANK_OPENING",
                ],
            ),
        ],
    },
    "BP_NEWCOMER_ZTRAIN_02_PROOF_BANK_DUAL": {
        "alias_of": "BP_NEWCOMER_PROOF_BANK_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_05_PROOF_BANK_DUAL": {
        "alias_of": "BP_NEWCOMER_PROOF_BANK_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_08_PROOF_BANK_DUAL": {
        "alias_of": "BP_NEWCOMER_PROOF_BANK_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_11_PROOF_BANK_DUAL": {
        "alias_of": "BP_NEWCOMER_PROOF_BANK_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_14_PROOF_BANK_DUAL": {
        "alias_of": "BP_NEWCOMER_PROOF_BANK_DUAL",
    },
    "BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL": {
        "difficulty": 5,
        "max_steps": 70,
        "max_module_invocations": 5,
        "target_state": [
            "housing_finance_prepared",
            "address_confirmation_verified",
            "bank_account_active",
            "mobile_service_active",
        ],
        "instruction_templates": [
            "Finish the newcomer workflow with housing finance prepared, address confirmation verified, the bank account active, and mobile service ready.",
            "Close the newcomer route after formalizing housing, confirming the address, activating banking, and turning mobile service on.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "housing_finance_prepared",
                "address_confirmation_verified",
                "bank_account_active",
                "mobile_service_active",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; newcomer connectivity should come only after the housing route is formalized, "
            "the address is confirmed, and banking is active."
        ),
        "distinctness_rule": (
            "Either secure housing, register the lease contract, verify the address, open the bank account, and then activate mobile service, "
            "or secure housing, review lease management, confirm the address through utilities, open the bank account, and then reach the same mobile-service outcome."
        ),
        "paths": [
            (
                "path_alpha",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_LEASE_CONTRACT_REGISTRATION",
                    "MODULE_ADDRESS_PROOF",
                    "MODULE_BANK_OPENING",
                    "MODULE_MOBILE_PLAN_SIGNUP",
                ],
            ),
            (
                "path_beta",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_LEASE_MANAGEMENT_REVIEW",
                    "MODULE_UTILITY_SETUP",
                    "MODULE_BANK_OPENING",
                    "MODULE_MOBILE_PLAN_SIGNUP",
                ],
            ),
        ],
    },
    "BP_NEWCOMER_ZTRAIN_01_FINANCE_CONNECTIVITY_DUAL": {
        "alias_of": "BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_04_FINANCE_CONNECTIVITY_DUAL": {
        "alias_of": "BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_07_FINANCE_CONNECTIVITY_DUAL": {
        "alias_of": "BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_10_FINANCE_CONNECTIVITY_DUAL": {
        "alias_of": "BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL",
    },
    "BP_NEWCOMER_ZTRAIN_13_FINANCE_CONNECTIVITY_DUAL": {
        "alias_of": "BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL",
    },
    "BP_FINANCE_AUTOPAY_BUDGET_DUAL": {
        "difficulty": 5,
        "max_steps": 70,
        "max_module_invocations": 5,
        "target_state": [
            "bills_reviewed",
            "bank_account_active",
            "autopay_enabled",
            "budget_limit_updated",
        ],
        "instruction_templates": [
            "Finish the finance workflow with bills reviewed, the account active, autopay enabled, and the budget limit updated.",
            "End the finance route after reviewing the bills, activating banking, turning on autopay, and updating the budget limit.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "bank_account_active",
                "autopay_enabled",
                "budget_limit_updated",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; stable recurring-payment discipline should first gather and review the bills, "
            "then activate banking, and only then finish autopay plus budget control."
        ),
        "distinctness_rule": (
            "Either aggregate the bills, review them, open the bank account, enable standard autopay, and then tighten the budget limit, "
            "or aggregate the bills, review them, open the bank account, finish complex autopay, and then reach the same budget-controlled outcome."
        ),
        "paths": [
            (
                "path_alpha",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_AUTOPAY",
                    "MODULE_BUDGET_LIMIT_UPDATE",
                ],
            ),
            (
                "path_beta",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_BUDGET_LIMIT_UPDATE",
                ],
            ),
        ],
    },
    "BP_FINANCE_ZTRAIN_03_AUTOPAY_BUDGET_DUAL": {
        "alias_of": "BP_FINANCE_AUTOPAY_BUDGET_DUAL",
    },
    "BP_FINANCE_ZTRAIN_06_AUTOPAY_BUDGET_DUAL": {
        "alias_of": "BP_FINANCE_AUTOPAY_BUDGET_DUAL",
    },
    "BP_FINANCE_ZTRAIN_09_AUTOPAY_BUDGET_DUAL": {
        "alias_of": "BP_FINANCE_AUTOPAY_BUDGET_DUAL",
    },
    "BP_FINANCE_ZTRAIN_12_AUTOPAY_BUDGET_DUAL": {
        "alias_of": "BP_FINANCE_AUTOPAY_BUDGET_DUAL",
    },
    "BP_FINANCE_AUTOPAY_READINESS": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "bills_reviewed",
            "bank_account_active",
            "autopay_enabled",
        ],
        "instruction_templates": [
            "Set up recurring-payment readiness this week by reviewing the bill stack, opening the account, and ending with autopay enabled.",
            "Get financial basics in place: review the bills, activate the account, and finish with a reliable autopay path.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "bank_account_active",
                "autopay_enabled",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; recurring-payment readiness should first review the bill stack before banking and autopay setup."
        ),
        "distinctness_rule": (
            "Either aggregate the bills, review them, open the bank account, and then enable standard autopay, "
            "or aggregate the bills, review them, open the bank account, and then finish the complex autopay route."
        ),
        "paths": [
            (
                "path_standard_autopay",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_AUTOPAY",
                ],
            ),
            (
                "path_complex_autopay",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_AUTOPAY_RECEIPT_ALIGNMENT": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 5,
        "target_state": [
            "bills_reviewed",
            "bank_account_active",
            "autopay_enabled",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Close the mixed admin workflow with the bills reviewed, autopay enabled, and the receipt already archived.",
            "Finish the composite route after reviewing the bill stack, turning on autopay, and leaving a receipt archive behind.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "bank_account_active",
                "autopay_enabled",
                "receipt_archived",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; the payment route should first gather and review the bills, then activate banking, "
            "and only afterwards close with autopay plus receipt archiving."
        ),
        "distinctness_rule": (
            "Either aggregate the bills, review them, open the bank account, enable standard autopay, and then archive the receipt, "
            "or aggregate the bills, review them, open the bank account, finish complex autopay, and then reach the same archived-receipt outcome."
        ),
        "paths": [
            (
                "path_autopay_then_archive",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_AUTOPAY",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_complex_then_archive",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_PAYMENT_SYNC": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 5,
        "target_state": [
            "bills_reviewed",
            "payment_stack_prepared",
            "calendar_event_synced",
        ],
        "instruction_templates": [
            "Finish the composite workflow with the bills reviewed, the payment stack prepared, and the calendar reminder already synced.",
            "Close the composite route by reviewing the bill stack, preparing payment, and leaving a synced calendar reminder in place.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "payment_stack_prepared",
                "calendar_event_synced",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; payment synchronization should first gather and review the bills, then build the payment stack, "
            "and only then sync the reminder."
        ),
        "distinctness_rule": (
            "Either aggregate the bills, review them, open the bank account, prepare the payment stack with a transfer, and then sync the calendar, "
            "or aggregate the bills, review them, open the bank account, prepare the payment stack with complex autopay, and then reach the same calendar-synced outcome."
        ),
        "paths": [
            (
                "path_alpha",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
            (
                "path_beta",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_PAYMENT_CALENDAR_ALIGNMENT": {
        "difficulty": 5,
        "max_steps": 65,
        "max_module_invocations": 5,
        "target_state": [
            "bills_reviewed",
            "payment_stack_prepared",
            "receipt_archived",
            "calendar_event_synced",
        ],
        "instruction_templates": [
            "Before the billing deadline, review the bills, prepare payment, archive the receipt, and leave with the reminder calendar already synced.",
            "End the admin workflow with the bill stack reviewed, payment prepared, the receipt archived, and a synced calendar reminder in place.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "payment_stack_prepared",
                "receipt_archived",
                "calendar_event_synced",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; payment-calendar alignment should first review the bills, then prepare payment, archive the receipt, "
            "and only then sync the reminder."
        ),
        "distinctness_rule": (
            "Either review the bills, open the bank account, prepare the payment stack with complex autopay, archive the receipt, and then sync the calendar, "
            "or review the bills, open the bank account, prepare the payment stack with a transfer, archive the receipt, and then reach the same calendar-synced outcome."
        ),
        "paths": [
            (
                "path_complex_autopay_sync",
                [
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
            (
                "path_transfer_sync",
                [
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_EMAIL_CALENDAR",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_AUCTION_PAYMENT_BRIDGE": {
        "difficulty": 5,
        "max_steps": 70,
        "max_module_invocations": 5,
        "target_state": [
            "bills_reviewed",
            "payment_stack_prepared",
            "calendar_event_synced",
            "auction_bid_placed",
        ],
        "instruction_templates": [
            "Prepare the auction workflow by reviewing the bill stack, preparing payment, syncing the reminder, and placing the bid before the window closes.",
            "End the auction route with the bills reviewed, payment ready, the calendar synced, and the bid successfully placed.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "payment_stack_prepared",
                "calendar_event_synced",
                "auction_bid_placed",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; auction readiness should first review the bill stack, then prepare payment, sync the reminder, "
            "and only then place the bid."
        ),
        "distinctness_rule": (
            "Either review the bills, open the bank account, prepare the payment stack with a transfer, sync the auction reminder, and then place the bid, "
            "or review the bills, open the bank account, prepare the payment stack with complex autopay, sync the auction reminder, and then reach the same bidding outcome."
        ),
        "paths": [
            (
                "path_transfer_then_auction",
                [
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_EMAIL_CALENDAR",
                    "MODULE_LIVE_AUCTION",
                ],
            ),
            (
                "path_autopay_then_auction",
                [
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_EMAIL_CALENDAR",
                    "MODULE_LIVE_AUCTION",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_AUCTION_PAYMENT_READY": {
        "difficulty": 5,
        "max_steps": 70,
        "max_module_invocations": 5,
        "target_state": [
            "bills_reviewed",
            "payment_stack_prepared",
            "calendar_event_synced",
            "auction_bid_placed",
        ],
        "instruction_templates": [
            "Prepare the auction workflow by reviewing the bill stack, preparing payment, syncing the reminder, and placing the bid before the listing window closes.",
            "End the auction workflow with the bills reviewed, payment ready, the reminder synced, and the bid already placed.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bills_reviewed",
                "payment_stack_prepared",
                "calendar_event_synced",
                "auction_bid_placed",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; auction readiness should first review the bill stack, then prepare payment, sync the reminder, "
            "and only then place the bid."
        ),
        "distinctness_rule": (
            "Either review the bills, open the bank account, prepare the payment stack with a transfer, sync the auction reminder, and then place the bid, "
            "or review the bills, open the bank account, prepare the payment stack with complex autopay, sync the auction reminder, and then reach the same bidding outcome."
        ),
        "paths": [
            (
                "path_transfer_backed_auction",
                [
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_EMAIL_CALENDAR",
                    "MODULE_LIVE_AUCTION",
                ],
            ),
            (
                "path_autopay_backed_auction",
                [
                    "MODULE_BILLING_REVIEW",
                    "MODULE_BANK_OPENING",
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_EMAIL_CALENDAR",
                    "MODULE_LIVE_AUCTION",
                ],
            ),
        ],
    },
    "BP_TRAVEL_BOOKING_CLEARANCE_DUAL": {
        "notes_template": (
            "Generated from {blueprint_id}; booking clearance should be completed either through the standard flight-booking route or through the long-haul booking route before the same visa check outcome."
        ),
        "distinctness_rule": (
            "Either book the flight and then check visa requirements, or use the long-haul booking route and then check the same visa requirements to reach the same clearance target."
        ),
        "paths": [
            ("path_alpha", ["MODULE_BOOK_FLIGHT", "MODULE_VISA_REQUIREMENTS"]),
            ("path_beta", ["MODULE_LONG_HAUL_TRIP", "MODULE_VISA_REQUIREMENTS"]),
        ],
    },
    "BP_TRAVEL_ZTRAIN_02_BOOKING_CLEARANCE_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_CLEARANCE_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_05_BOOKING_CLEARANCE_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_CLEARANCE_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_08_BOOKING_CLEARANCE_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_CLEARANCE_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_11_BOOKING_CLEARANCE_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_CLEARANCE_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_14_BOOKING_CLEARANCE_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_CLEARANCE_DUAL",
    },
    "BP_TRAVEL_WORKFLOW_CLEARANCE_BOOKING": {
        "notes_template": (
            "Generated from {blueprint_id}; travel-clearance booking should either check visa requirements before lodging or complete the long-haul booking route before final lodging and clearance confirmation."
        ),
        "distinctness_rule": (
            "Either check visa requirements and then book lodging, or use the long-haul booking route, book lodging, and then confirm the same visa-clearance outcome."
        ),
        "paths": [
            ("path_visa_then_hotel", ["MODULE_VISA_REQUIREMENTS", "MODULE_BOOK_HOTEL"]),
            ("path_longhaul_bundle", ["MODULE_LONG_HAUL_TRIP", "MODULE_BOOK_HOTEL", "MODULE_VISA_REQUIREMENTS"]),
        ],
    },
    "BP_EDUCATION_ZTRAIN_03_ASSIGNMENT_RESOURCE_DUAL": {
        "notes_template": (
            "Generated from {blueprint_id}; both assignment-resource routes should first enroll in the course, then diverge in how resources are prepared before submission."
        ),
        "distinctness_rule": (
            "Either enroll in the course, buy the ebook, and then submit the assignment, or enroll in the course, reserve the library resources, and then reach the same submission outcome."
        ),
        "paths": [
            ("path_alpha", ["MODULE_COURSE_ENROLLMENT", "MODULE_BUY_EBOOK", "MODULE_SUBMIT_ASSIGNMENT"]),
            ("path_beta", ["MODULE_COURSE_ENROLLMENT", "MODULE_LIBRARY_SERVICE", "MODULE_SUBMIT_ASSIGNMENT"]),
        ],
    },
    "BP_EDUCATION_ASSIGNMENT_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_ZTRAIN_03_ASSIGNMENT_RESOURCE_DUAL",
    },
    "BP_EDUCATION_ZTRAIN_06_ASSIGNMENT_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_ZTRAIN_03_ASSIGNMENT_RESOURCE_DUAL",
    },
    "BP_EDUCATION_ZTRAIN_09_ASSIGNMENT_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_ZTRAIN_03_ASSIGNMENT_RESOURCE_DUAL",
    },
    "BP_EDUCATION_ZTRAIN_12_ASSIGNMENT_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_ZTRAIN_03_ASSIGNMENT_RESOURCE_DUAL",
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any]:
    spec = ROUND6_SPECS[blueprint_id]
    alias_of = spec.get("alias_of")
    if not alias_of:
        return spec
    base = copy.deepcopy(resolve_spec(alias_of))
    base.update({k: v for k, v in spec.items() if k != "alias_of"})
    return base


def main() -> None:
    blueprints_doc = load_json(BLUEPRINTS_PATH)
    patched: list[str] = []

    for blueprint in blueprints_doc["blueprints"]:
        blueprint_id = blueprint["blueprint_id"]
        if blueprint_id not in ROUND6_SPECS:
            continue

        spec = resolve_spec(blueprint_id)
        step_lookup = base_step_lookup(blueprint.get("paths", []))

        if "difficulty" in spec:
            blueprint["difficulty"] = spec["difficulty"]
        if "max_steps" in spec:
            blueprint["max_steps"] = spec["max_steps"]
        if "max_module_invocations" in spec:
            blueprint["max_module_invocations"] = spec["max_module_invocations"]
        if "target_state" in spec:
            blueprint["target_state"] = spec["target_state"]
        if "instruction_templates" in spec:
            blueprint["instruction_templates"] = spec["instruction_templates"]
        if "visible_constraints" in spec:
            blueprint["visible_constraints"] = replace_preferred_outcomes(
                blueprint.get("visible_constraints", {}),
                spec["visible_constraints"]["preferred_outcomes"],
            )
        if "notes_template" in spec:
            blueprint["notes_template"] = spec["notes_template"]
        if "distinctness_rule" in spec:
            blueprint["distinctness_rule"] = spec["distinctness_rule"]
        blueprint["paths"] = [
            build_path(step_lookup, path_id, module_ids) for path_id, module_ids in spec["paths"]
        ]
        patched.append(blueprint_id)

    save_json(BLUEPRINTS_PATH, blueprints_doc)
    print(
        json.dumps(
            {
                "patched_blueprints": len(patched),
                "blueprint_ids": patched,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
