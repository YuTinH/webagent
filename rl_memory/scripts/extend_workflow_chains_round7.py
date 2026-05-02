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


ROUND7_SPECS: dict[str, dict[str, Any]] = {
    "BP_TRAVEL_BOOKING_TRANSFER_DUAL": {
        "difficulty": 5,
        "max_steps": 70,
        "max_module_invocations": 5,
        "target_state": [
            "mobility_clearance_verified",
            "travel_booking_confirmed",
            "airport_transfer_arranged",
            "check_in_completed",
            "expense_report_submitted",
        ],
        "instruction_templates": [
            "Finish the travel workflow only after mobility clearance is checked, the booking is confirmed, airport transfer is arranged, check-in is completed, and the expense report is submitted.",
            "Close the travel route by first clearing the trip, then arranging transfer, completing check-in, and leaving the expense report already filed.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "mobility_clearance_verified",
                "travel_booking_confirmed",
                "airport_transfer_arranged",
                "check_in_completed",
                "expense_report_submitted",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; realistic transfer readiness should start from trip clearance or a long-haul bundle, "
            "then continue through transfer, check-in, and expense filing."
        ),
        "distinctness_rule": (
            "Either verify visa requirements before booking the flight, then arrange airport transfer, complete check-in, and submit the expense report, "
            "or use the long-haul trip route before reaching the same transfer, check-in, and expense outcome."
        ),
        "paths": [
            (
                "path_clearance_transfer_stack",
                [
                    "MODULE_VISA_REQUIREMENTS",
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_CHECK_IN",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
            (
                "path_longhaul_transfer_stack",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_CHECK_IN",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
        ],
    },
    "BP_TRAVEL_ZTRAIN_01_BOOKING_TRANSFER_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_TRANSFER_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_04_BOOKING_TRANSFER_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_TRANSFER_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_07_BOOKING_TRANSFER_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_TRANSFER_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_10_BOOKING_TRANSFER_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_TRANSFER_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_13_BOOKING_TRANSFER_DUAL": {
        "alias_of": "BP_TRAVEL_BOOKING_TRANSFER_DUAL",
    },
    "BP_TRAVEL_BOOKING_CHECKIN_ALIGNMENT": {
        "difficulty": 5,
        "max_steps": 65,
        "max_module_invocations": 4,
        "target_state": [
            "mobility_clearance_verified",
            "travel_booking_confirmed",
            "check_in_completed",
            "expense_report_submitted",
        ],
        "instruction_templates": [
            "Before travel day, make sure the trip is cleared, the booking is confirmed, check-in is completed, and the expense report is already prepared.",
            "Finish the travel prep by confirming the booking, completing the right clearance path, checking in, and filing the expense report.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "mobility_clearance_verified",
                "travel_booking_confirmed",
                "check_in_completed",
                "expense_report_submitted",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; check-in readiness should be grounded in either explicit clearance before booking or the bundled long-haul route, "
            "and then close with check-in plus expense filing."
        ),
        "distinctness_rule": (
            "Either verify visa requirements, book the flight, complete check-in, and then submit the expense report, "
            "or use the long-haul booking route, arrange transfer on the way, complete check-in, and then reach the same expense-filed outcome."
        ),
        "paths": [
            (
                "path_clearance_then_checkin",
                [
                    "MODULE_VISA_REQUIREMENTS",
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_CHECK_IN",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
            (
                "path_longhaul_then_checkin",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_CHECK_IN",
                    "MODULE_EXPENSE_REPORT",
                ],
            ),
        ],
    },
    "BP_TRAVEL_REBOOK_BOOKING_DUAL": {
        "difficulty": 5,
        "max_steps": 65,
        "max_module_invocations": 4,
        "target_state": [
            "travel_booking_confirmed",
            "itinerary_rebooked",
            "airport_transfer_arranged",
            "check_in_completed",
        ],
        "instruction_templates": [
            "Finish the travel workflow only after the booking is confirmed, the itinerary is rebooked, airport transfer is arranged, and check-in is completed.",
            "Close the travel route by stabilizing the itinerary first, then arranging transfer, and ending with a completed check-in.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "travel_booking_confirmed",
                "itinerary_rebooked",
                "airport_transfer_arranged",
                "check_in_completed",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; rebooking should not stop at itinerary repair, but continue through transfer planning and check-in completion."
        ),
        "distinctness_rule": (
            "Either book a standard flight, rebook the itinerary, arrange airport transfer, and then complete check-in, "
            "or use the long-haul route before reaching the same rebooked-and-checked-in state."
        ),
        "paths": [
            (
                "path_standard_rebook_stack",
                [
                    "MODULE_BOOK_FLIGHT",
                    "MODULE_FLIGHT_REBOOKING",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_CHECK_IN",
                ],
            ),
            (
                "path_longhaul_rebook_stack",
                [
                    "MODULE_LONG_HAUL_TRIP",
                    "MODULE_FLIGHT_REBOOKING",
                    "MODULE_AIRPORT_TRANSFER",
                    "MODULE_CHECK_IN",
                ],
            ),
        ],
    },
    "BP_TRAVEL_ZTRAIN_03_REBOOK_BOOKING_DUAL": {
        "alias_of": "BP_TRAVEL_REBOOK_BOOKING_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_06_REBOOK_BOOKING_DUAL": {
        "alias_of": "BP_TRAVEL_REBOOK_BOOKING_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_09_REBOOK_BOOKING_DUAL": {
        "alias_of": "BP_TRAVEL_REBOOK_BOOKING_DUAL",
    },
    "BP_TRAVEL_ZTRAIN_12_REBOOK_BOOKING_DUAL": {
        "alias_of": "BP_TRAVEL_REBOOK_BOOKING_DUAL",
    },
    "BP_CRISIS_ACCESS_LIQUIDITY_DUAL": {
        "difficulty": 5,
        "max_steps": 70,
        "max_module_invocations": 4,
        "target_state": [
            "password_reset_completed",
            "account_access_contained",
            "crisis_intake_completed",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "During the crisis workflow, restore access, contain the account, complete intake, and secure liquidity before you stop.",
            "Close the crisis route only after the reset path is complete, access is contained, intake is logged, and emergency liquidity is secured.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "password_reset_completed",
                "account_access_contained",
                "crisis_intake_completed",
                "emergency_liquidity_secured",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; emergency liquidity should come only after access recovery or containment, followed by a concrete crisis-intake step."
        ),
        "distinctness_rule": (
            "Either request the reset code, complete the reset, freeze the card, and then secure the urgent loan, "
            "or use the end-to-end recovery route, freeze the card, complete an intake report, and then reach the same liquidity outcome."
        ),
        "paths": [
            (
                "path_reset_then_contain_then_loan",
                [
                    "MODULE_PASSWORD_RESET_REQUEST",
                    "MODULE_PASSWORD_RESET_COMPLETION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_URGENT_LOAN",
                ],
            ),
            (
                "path_recovery_then_triage_then_loan",
                [
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
    "BP_CRISIS_ZTRAIN_03_ACCESS_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_ACCESS_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_06_ACCESS_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_ACCESS_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_09_ACCESS_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_ACCESS_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_12_ACCESS_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_ACCESS_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_INTAKE_LIQUIDITY_DUAL": {
        "difficulty": 5,
        "max_steps": 75,
        "max_module_invocations": 5,
        "target_state": [
            "password_reset_completed",
            "crisis_intake_completed",
            "account_access_contained",
            "emergency_liquidity_secured",
        ],
        "instruction_templates": [
            "Finish the crisis workflow by restoring access, completing intake, containing the account, and securing emergency liquidity.",
            "Treat the crisis route as complete only once the reset path is done, intake is recorded, the account is contained, and emergency liquidity is in place.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "password_reset_completed",
                "crisis_intake_completed",
                "account_access_contained",
                "emergency_liquidity_secured",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; realistic intake-liquidity handling should move from account recovery into crisis reporting, then containment, and only then into emergency funds."
        ),
        "distinctness_rule": (
            "Either request the reset code, complete the reset, freeze the card, log the illness intake, and then secure the urgent loan, "
            "or use the end-to-end recovery route, report the supply disruption, freeze the card, and then reach the same liquidity outcome."
        ),
        "paths": [
            (
                "path_reset_intake_liquidity",
                [
                    "MODULE_PASSWORD_RESET_REQUEST",
                    "MODULE_PASSWORD_RESET_COMPLETION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_URGENT_LOAN",
                ],
            ),
            (
                "path_recovery_supply_liquidity",
                [
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_SUPPLY_DISRUPTION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_URGENT_LOAN",
                ],
            ),
        ],
    },
    "BP_CRISIS_ZTRAIN_01_INTAKE_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_INTAKE_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_04_INTAKE_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_INTAKE_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_07_INTAKE_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_INTAKE_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_10_INTAKE_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_INTAKE_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_ZTRAIN_13_INTAKE_LIQUIDITY_DUAL": {
        "alias_of": "BP_CRISIS_INTAKE_LIQUIDITY_DUAL",
    },
    "BP_CRISIS_CONTAINMENT_TRIAGE_DUAL": {
        "difficulty": 5,
        "max_steps": 65,
        "max_module_invocations": 4,
        "target_state": [
            "password_reset_completed",
            "crisis_intake_completed",
            "account_access_contained",
        ],
        "instruction_templates": [
            "Finish the crisis triage only after the reset route is complete, access is contained, and the intake record is already filed.",
            "Close the containment workflow by restoring access first, then containing the account, and making sure crisis intake is recorded.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "password_reset_completed",
                "crisis_intake_completed",
                "account_access_contained",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; containment should be coupled with explicit recovery plus a concrete intake report rather than a bare two-step reaction."
        ),
        "distinctness_rule": (
            "Either request the reset code, complete the reset, freeze the card, and then log the illness intake, "
            "or use the end-to-end recovery route before freezing the card and reporting the supply disruption to reach the same containment target."
        ),
        "paths": [
            (
                "path_reset_then_triage",
                [
                    "MODULE_PASSWORD_RESET_REQUEST",
                    "MODULE_PASSWORD_RESET_COMPLETION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_ILLNESS_REPORTING",
                ],
            ),
            (
                "path_recovery_then_supply_triage",
                [
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_SUPPLY_DISRUPTION",
                ],
            ),
        ],
    },
    "BP_CRISIS_ZTRAIN_02_CONTAINMENT_TRIAGE_DUAL": {
        "alias_of": "BP_CRISIS_CONTAINMENT_TRIAGE_DUAL",
    },
    "BP_CRISIS_ZTRAIN_05_CONTAINMENT_TRIAGE_DUAL": {
        "alias_of": "BP_CRISIS_CONTAINMENT_TRIAGE_DUAL",
    },
    "BP_CRISIS_ZTRAIN_08_CONTAINMENT_TRIAGE_DUAL": {
        "alias_of": "BP_CRISIS_CONTAINMENT_TRIAGE_DUAL",
    },
    "BP_CRISIS_ZTRAIN_11_CONTAINMENT_TRIAGE_DUAL": {
        "alias_of": "BP_CRISIS_CONTAINMENT_TRIAGE_DUAL",
    },
    "BP_CRISIS_ZTRAIN_14_CONTAINMENT_TRIAGE_DUAL": {
        "alias_of": "BP_CRISIS_CONTAINMENT_TRIAGE_DUAL",
    },
    "BP_SUPPORT_REMEDY_SUPPORT_DUAL": {
        "difficulty": 5,
        "initial_world_state": ["shop_order_exists"],
        "max_steps": 75,
        "max_module_invocations": 4,
        "target_state": [
            "order_followup_prepared",
            "delivery_visibility_confirmed",
            "support_contacted",
            "post_purchase_remedy_requested",
        ],
        "instruction_templates": [
            "Resolve the support case end to end: verify the order status, confirm delivery visibility, contact support, and finish with a concrete remedy request.",
            "Close the support route by checking the order, confirming delivery, opening the support channel, and leaving with the remedy request already submitted.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "order_followup_prepared",
                "delivery_visibility_confirmed",
                "support_contacted",
                "post_purchase_remedy_requested",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; realistic post-purchase remediation should establish order visibility first, then open the support channel, and only then request the remedy."
        ),
        "distinctness_rule": (
            "Either track the order, confirm arrival, contact support, and then file the return, "
            "or confirm order visibility through customer service, verify arrival, open logistics follow-up, and then reach the same remedy outcome through warranty."
        ),
        "paths": [
            (
                "path_tracking_contact_return",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_RETURN",
                ],
            ),
            (
                "path_service_logistics_warranty",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_LOGISTICS_FIX",
                    "MODULE_WARRANTY_CLAIM",
                ],
            ),
        ],
    },
    "BP_SUPPORT_ZTRAIN_02_REMEDY_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REMEDY_SUPPORT_DUAL",
    },
    "BP_SUPPORT_ZTRAIN_05_REMEDY_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REMEDY_SUPPORT_DUAL",
    },
    "BP_SUPPORT_ZTRAIN_08_REMEDY_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REMEDY_SUPPORT_DUAL",
    },
    "BP_SUPPORT_ZTRAIN_11_REMEDY_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REMEDY_SUPPORT_DUAL",
    },
    "BP_SUPPORT_ZTRAIN_14_REMEDY_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REMEDY_SUPPORT_DUAL",
    },
    "BP_SUPPORT_POST_PURCHASE_REMEDY_TRACK": {
        "difficulty": 5,
        "initial_world_state": ["shop_order_exists"],
        "max_steps": 85,
        "max_module_invocations": 5,
        "target_state": [
            "order_followup_prepared",
            "delivery_visibility_confirmed",
            "support_contacted",
            "post_purchase_remedy_requested",
            "product_review_submitted",
        ],
        "instruction_templates": [
            "Finish the support workflow only after the order is tracked, delivery is confirmed, support is contacted, the remedy is requested, and the final review step is submitted.",
            "Close the post-purchase case by verifying the order first, then handling support and remedy, and ending with the review already recorded.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "order_followup_prepared",
                "delivery_visibility_confirmed",
                "support_contacted",
                "post_purchase_remedy_requested",
                "product_review_submitted",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; a realistic remediation track should verify the order, open the right support channel, request the remedy, and only then close with the feedback step."
        ),
        "distinctness_rule": (
            "Either track the order, confirm arrival, contact support, request the return, and then leave the review, "
            "or confirm order visibility through customer service, verify arrival, open logistics follow-up, request the warranty remedy, and then reach the same review-submitted outcome through the blacklist route."
        ),
        "paths": [
            (
                "path_tracking_remedy_feedback",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_RETURN",
                    "MODULE_LEAVE_REVIEW",
                ],
            ),
            (
                "path_service_remedy_blacklist",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_LOGISTICS_FIX",
                    "MODULE_WARRANTY_CLAIM",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
        ],
    },
    "BP_SUPPORT_TRACK_PRICE_ALIGNMENT": {
        "difficulty": 5,
        "initial_world_state": ["shop_order_exists"],
        "max_steps": 75,
        "max_module_invocations": 4,
        "target_state": [
            "order_followup_prepared",
            "delivery_visibility_confirmed",
            "support_contacted",
            "order_price_secured",
        ],
        "instruction_templates": [
            "Before requesting price protection, verify the order status, confirm delivery visibility, and make sure a support channel is already open.",
            "Finish the price-alignment workflow by checking the order first, opening the right support path, and ending with price protection secured.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "order_followup_prepared",
                "delivery_visibility_confirmed",
                "support_contacted",
                "order_price_secured",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; realistic price protection should come after order visibility and a concrete support touchpoint."
        ),
        "distinctness_rule": (
            "Either track the order, confirm arrival, contact support, and then secure price protection, "
            "or confirm order visibility through customer service, verify arrival, open logistics follow-up, and then reach the same price-protected outcome."
        ),
        "paths": [
            (
                "path_tracking_then_price_support",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_PRICE_PROTECTION",
                ],
            ),
            (
                "path_service_then_price_support",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_LOGISTICS_FIX",
                    "MODULE_PRICE_PROTECTION",
                ],
            ),
        ],
    },
    "BP_HEALTH_CONTINUITY_CLAIM": {
        "difficulty": 5,
        "initial_world_state": [],
        "max_steps": 70,
        "max_module_invocations": 4,
        "target_state": [
            "coverage_path_active",
            "medical_appointment_booked",
            "care_continuity_established",
            "medical_claim_submitted",
        ],
        "instruction_templates": [
            "Finish the health workflow only after the coverage path is active, the appointment is booked, continuity is established, and the medical claim is submitted.",
            "Close the care route by activating coverage first, then booking the appointment, completing the continuity step, and filing the claim.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "coverage_path_active",
                "medical_appointment_booked",
                "care_continuity_established",
                "medical_claim_submitted",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; continuity plus reimbursement should follow a realistic care path: activate coverage, book care, complete the continuity action, and only then submit the claim."
        ),
        "distinctness_rule": (
            "Either activate insurance policy coverage, book the doctor appointment, refill the prescription, and then submit the medical claim, "
            "or activate the health plan before reaching the same appointment, continuity, and claim outcome."
        ),
        "paths": [
            (
                "path_policy_care_claim",
                [
                    "MODULE_INSURANCE_POLICY",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_PRESCRIPTION_REFILL",
                    "MODULE_MEDICAL_CLAIM",
                ],
            ),
            (
                "path_plan_care_claim",
                [
                    "MODULE_HEALTH_PLAN_ACTIVATION",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_PRESCRIPTION_REFILL",
                    "MODULE_MEDICAL_CLAIM",
                ],
            ),
        ],
    },
    "BP_HEALTH_COVERAGE_VACCINE": {
        "difficulty": 5,
        "initial_world_state": [],
        "max_steps": 70,
        "max_module_invocations": 4,
        "target_state": [
            "coverage_path_active",
            "medical_appointment_booked",
            "vaccination_record_updated",
            "medical_claim_submitted",
        ],
        "instruction_templates": [
            "Finish the care workflow only after coverage is active, the appointment is booked, the vaccination record is updated, and the claim is submitted.",
            "Close the immunization route by activating coverage first, then booking the appointment, updating the vaccine record, and filing the claim.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "coverage_path_active",
                "medical_appointment_booked",
                "vaccination_record_updated",
                "medical_claim_submitted",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; vaccine reimbursement should not be a two-click shortcut, but a full care path through coverage, appointment, record update, and claim filing."
        ),
        "distinctness_rule": (
            "Either activate insurance policy coverage, book the doctor appointment, update the vaccine record, and then submit the medical claim, "
            "or activate the health plan before reaching the same appointment, vaccine, and claim outcome."
        ),
        "paths": [
            (
                "path_policy_vaccine_claim",
                [
                    "MODULE_INSURANCE_POLICY",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_VACCINE_MGMT",
                    "MODULE_MEDICAL_CLAIM",
                ],
            ),
            (
                "path_plan_vaccine_claim",
                [
                    "MODULE_HEALTH_PLAN_ACTIVATION",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_VACCINE_MGMT",
                    "MODULE_MEDICAL_CLAIM",
                ],
            ),
        ],
    },
    "BP_HEALTH_COVERAGE_VACCINE_ALIGNMENT": {
        "alias_of": "BP_HEALTH_COVERAGE_VACCINE",
    },
    "BP_HEALTH_CLINIC_CONTINUITY": {
        "difficulty": 5,
        "initial_world_state": [],
        "max_steps": 70,
        "max_module_invocations": 4,
        "target_state": [
            "coverage_path_active",
            "medical_appointment_booked",
            "care_continuity_established",
            "vaccination_record_updated",
        ],
        "instruction_templates": [
            "Keep the clinic workflow on track by activating coverage, booking the appointment, completing the continuity step, and updating the vaccination record before the care window closes.",
            "Finish the clinic route only after coverage is active, the appointment is secured, continuity is established, and the vaccination record is updated.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "coverage_path_active",
                "medical_appointment_booked",
                "care_continuity_established",
                "vaccination_record_updated",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; clinic continuity should combine coverage activation, an actual visit, follow-on care, and record upkeep instead of stopping after a two-step shortcut."
        ),
        "distinctness_rule": (
            "Either activate insurance coverage, book the doctor appointment, refill the prescription, and then update the vaccination record, "
            "or activate the health plan before reaching the same appointment, continuity, and vaccine-record outcome."
        ),
        "paths": [
            (
                "path_policy_clinic_continuity",
                [
                    "MODULE_INSURANCE_POLICY",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_PRESCRIPTION_REFILL",
                    "MODULE_VACCINE_MGMT",
                ],
            ),
            (
                "path_plan_clinic_continuity",
                [
                    "MODULE_HEALTH_PLAN_ACTIVATION",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_PRESCRIPTION_REFILL",
                    "MODULE_VACCINE_MGMT",
                ],
            ),
        ],
    },
    "BP_CAREER_CONFERENCE_ADMIN": {
        "difficulty": 5,
        "max_steps": 65,
        "max_module_invocations": 4,
        "target_state": [
            "conference_admin_recorded",
            "receipt_archived",
            "deadline_coordination_recorded",
            "career_signal_strengthened",
        ],
        "instruction_templates": [
            "Finish the conference workflow only after admin is recorded, the receipt is archived, the deadline coordination record exists, and the final signal-strengthening action is completed.",
            "Close the conference route by completing the registration admin first, then archiving the receipt, coordinating the deadline, and ending with a concrete signaling action.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "conference_admin_recorded",
                "receipt_archived",
                "deadline_coordination_recorded",
                "career_signal_strengthened",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; conference administration should continue through archival and calendar coordination before the final signaling step."
        ),
        "distinctness_rule": (
            "Either complete the formal conference registration, archive the receipt, aggregate the calendar deadline, and then track the related email thread, "
            "or use the admin-record route before the same archival and coordination steps, then finish by strengthening the public career signal."
        ),
        "paths": [
            (
                "path_registration_archive_signal",
                [
                    "MODULE_CONFERENCE_REGISTRATION",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_CALENDAR_AGGREGATION",
                    "MODULE_EMAIL_TRACKING",
                ],
            ),
            (
                "path_admin_archive_signal",
                [
                    "MODULE_CONFERENCE_REG",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_CALENDAR_AGGREGATION",
                    "MODULE_UPDATE_LINKEDIN",
                ],
            ),
        ],
    },
    "BP_CAREER_CONFERENCE_ARCHIVE": {
        "alias_of": "BP_CAREER_CONFERENCE_ADMIN",
    },
    "BP_CAREER_CONFERENCE_COORDINATION_CLOSURE": {
        "difficulty": 5,
        "max_steps": 55,
        "max_module_invocations": 4,
        "target_state": [
            "conference_admin_recorded",
            "receipt_archived",
            "deadline_coordination_recorded",
            "career_signal_strengthened",
        ],
        "instruction_templates": [
            "Close the conference coordination workflow only after the admin record exists, the receipt is archived, the deadline is coordinated, and the related signal-strengthening step is finished.",
            "Finish the conference coordination route by recording admin first, then archiving the receipt, creating the deadline coordination record, and ending with a signaling action.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "conference_admin_recorded",
                "receipt_archived",
                "deadline_coordination_recorded",
                "career_signal_strengthened",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; conference coordination closure should include the archival step and a final signaling action, not just raw admin plus calendar."
        ),
        "distinctness_rule": (
            "Complete the conference admin route, archive the receipt, aggregate the deadline into the calendar, and then track the related email thread to close the workflow."
        ),
        "paths": [
            (
                "path_admin_archive_calendar_signal",
                [
                    "MODULE_CONFERENCE_REG",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_CALENDAR_AGGREGATION",
                    "MODULE_EMAIL_TRACKING",
                ],
            ),
        ],
    },
    "BP_CAREER_SUBMISSION_DEADLINE_SYNC": {
        "difficulty": 5,
        "max_steps": 65,
        "max_module_invocations": 4,
        "target_state": [
            "paper_submitted",
            "deadline_coordination_recorded",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Finish the submission workflow only after the paper is submitted, the deadline coordination record exists, and the receipt is archived.",
            "Close the submission route by preparing the right thread or registration context first, then submitting the paper, coordinating the deadline, and archiving the receipt.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "paper_submitted",
                "deadline_coordination_recorded",
                "receipt_archived",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; a realistic submission workflow should not stop at the paper action, but continue through deadline coordination and archival."
        ),
        "distinctness_rule": (
            "Either track the relevant email thread before submitting the paper, then coordinate the deadline and archive the receipt, "
            "or use the conference-registration route before reaching the same submitted-and-archived outcome."
        ),
        "paths": [
            (
                "path_threaded_submission_sync",
                [
                    "MODULE_EMAIL_TRACKING",
                    "MODULE_PAPER_SUBMISSION",
                    "MODULE_CALENDAR_AGGREGATION",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_registered_submission_sync",
                [
                    "MODULE_CONFERENCE_REGISTRATION",
                    "MODULE_PAPER_SUBMISSION",
                    "MODULE_CALENDAR_AGGREGATION",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any]:
    spec = ROUND7_SPECS[blueprint_id]
    alias_of = spec.get("alias_of")
    if not alias_of:
        return spec
    base = copy.deepcopy(resolve_spec(alias_of))
    base.update({k: v for k, v in spec.items() if k != "alias_of"})
    return base


def main() -> None:
    blueprints_doc = load_json(BLUEPRINTS_PATH)
    global_lookup = build_global_step_lookup(blueprints_doc["blueprints"])
    patched: list[str] = []

    for blueprint in blueprints_doc["blueprints"]:
        blueprint_id = blueprint["blueprint_id"]
        if blueprint_id not in ROUND7_SPECS:
            continue

        spec = resolve_spec(blueprint_id)
        local_lookup = base_step_lookup(blueprint.get("paths", []))
        allowed_shared_vars = set(blueprint.get("shared_variable_pools", {}))

        if "difficulty" in spec:
            blueprint["difficulty"] = spec["difficulty"]
        if "initial_world_state" in spec:
            blueprint["initial_world_state"] = spec["initial_world_state"]
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
            build_path(local_lookup, global_lookup, allowed_shared_vars, path_id, module_ids)
            for path_id, module_ids in spec["paths"]
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
