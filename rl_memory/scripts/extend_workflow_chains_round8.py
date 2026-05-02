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


ROUND8_SPECS: dict[str, dict[str, Any]] = {
    "BP_SOCIAL_COMMITMENT_CONTRIBUTION_DUAL": {
        "difficulty": 5,
        "initial_world_state": ["bank_account_active"],
        "max_steps": 50,
        "max_module_invocations": 3,
        "target_state": [
            "event_rsvp_completed",
            "social_commitment_recorded",
            "social_contribution_completed",
            "shared_expenses_settled",
        ],
        "instruction_templates": [
            "Close the social contribution workflow only after the RSVP is recorded, the contribution is completed, and the shared expenses are settled.",
            "Finish the social route by making the contribution first, then locking the RSVP commitment, and ending with expense settlement.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "event_rsvp_completed",
                "social_commitment_recorded",
                "social_contribution_completed",
                "shared_expenses_settled",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; contribution workflows should not stop after a two-step action pair, "
            "but continue through RSVP confirmation and final shared-expense closure."
        ),
        "distinctness_rule": (
            "Either complete the contribution through charity donation, then confirm the RSVP and settle the shared expenses, "
            "or use gift pooling before reaching the same RSVP-and-settlement closure."
        ),
        "paths": [
            (
                "path_donation_commitment_closure",
                [
                    "MODULE_CHARITY_DONATION",
                    "MODULE_RSVP_EVENT",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                ],
            ),
            (
                "path_pooling_commitment_closure",
                [
                    "MODULE_GIFT_POOLING",
                    "MODULE_RSVP_EVENT",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                ],
            ),
        ],
    },
    "BP_SOCIAL_SETTLEMENT_COMMITMENT_DUAL": {
        "difficulty": 5,
        "initial_world_state": ["bank_account_active"],
        "max_steps": 50,
        "max_module_invocations": 3,
        "target_state": [
            "event_rsvp_completed",
            "social_commitment_recorded",
            "social_contribution_completed",
            "shared_expenses_settled",
        ],
        "instruction_templates": [
            "Finish the social settlement route only after the contribution is completed, the shared expenses are settled, and the RSVP commitment is on record.",
            "Close the settlement workflow by finishing the contribution path first, then settling expenses, and only then recording the RSVP commitment.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "event_rsvp_completed",
                "social_commitment_recorded",
                "social_contribution_completed",
                "shared_expenses_settled",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; settlement-oriented social workflows should include a full contribution path, "
            "actual expense settlement, and the final RSVP commitment."
        ),
        "distinctness_rule": (
            "Either donate first, then settle the shared expenses and record the RSVP commitment, "
            "or use gift pooling before the same settlement-and-commitment closure."
        ),
        "paths": [
            (
                "path_donation_settlement_commitment",
                [
                    "MODULE_CHARITY_DONATION",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                    "MODULE_RSVP_EVENT",
                ],
            ),
            (
                "path_pooling_settlement_commitment",
                [
                    "MODULE_GIFT_POOLING",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                    "MODULE_RSVP_EVENT",
                ],
            ),
        ],
    },
    "BP_SOCIAL_CONTRIBUTION_ACCOUNT_DUAL": {
        "difficulty": 5,
        "initial_world_state": ["lease_active"],
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "bank_account_active",
            "event_rsvp_completed",
            "social_commitment_recorded",
            "social_contribution_completed",
            "shared_expenses_settled",
        ],
        "instruction_templates": [
            "Finish the account-backed social contribution workflow only after the bank account is active, the RSVP is confirmed, the contribution is completed, and the shared expenses are settled.",
            "Close the workflow by opening the payment rail first, then completing the contribution branch, recording the RSVP commitment, and ending with expense settlement.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "bank_account_active",
                "event_rsvp_completed",
                "social_commitment_recorded",
                "social_contribution_completed",
                "shared_expenses_settled",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; account-backed social contribution workflows should combine payment setup, "
            "actual contribution, RSVP confirmation, and a final settlement step."
        ),
        "distinctness_rule": (
            "Either open banking, donate, confirm the RSVP, and then settle the shared expenses, "
            "or open banking and use gift pooling before reaching the same RSVP-and-settlement closure."
        ),
        "paths": [
            (
                "path_account_donation_commitment",
                [
                    "MODULE_BANK_OPENING",
                    "MODULE_CHARITY_DONATION",
                    "MODULE_RSVP_EVENT",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                ],
            ),
            (
                "path_account_pooling_commitment",
                [
                    "MODULE_BANK_OPENING",
                    "MODULE_GIFT_POOLING",
                    "MODULE_RSVP_EVENT",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                ],
            ),
        ],
    },
    "BP_SOCIAL_TICKET_COMMITMENT_ALIGNMENT": {
        "difficulty": 5,
        "initial_world_state": ["bank_account_active"],
        "max_steps": 55,
        "max_module_invocations": 4,
        "target_state": [
            "event_ticket_booked",
            "event_rsvp_completed",
            "social_commitment_recorded",
            "shared_expenses_settled",
        ],
        "instruction_templates": [
            "Finish the social ticket workflow only after the RSVP is recorded, the ticket is booked, and the shared-expense closure is complete.",
            "Close the social ticket route by recording the commitment, securing the ticket, and ending with expense settlement instead of stopping after a shallow shortcut.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "event_ticket_booked",
                "event_rsvp_completed",
                "social_commitment_recorded",
                "shared_expenses_settled",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; ticket workflows should close with both explicit commitment and shared-expense settlement, "
            "not just a ticket action plus one precursor."
        ),
        "distinctness_rule": (
            "Either confirm the RSVP, book the movie ticket, and then settle the shared expenses, "
            "or use gift pooling before booking the event ticket, confirming the RSVP, and reaching the same settlement outcome."
        ),
        "paths": [
            (
                "path_rsvp_movie_settlement",
                [
                    "MODULE_RSVP_EVENT",
                    "MODULE_MOVIE_TICKETS",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                ],
            ),
            (
                "path_pool_event_settlement",
                [
                    "MODULE_GIFT_POOLING",
                    "MODULE_EVENT_TICKETS",
                    "MODULE_RSVP_EVENT",
                    "MODULE_ROOMMATE_EXPENSE_SPLIT",
                ],
            ),
        ],
    },
    "BP_DAILY_BUNDLE_FOOD_ALIGNMENT": {
        "difficulty": 5,
        "initial_world_state": ["lease_active"],
        "max_steps": 45,
        "max_module_invocations": 3,
        "target_state": [
            "daily_order_bundle_prepared",
            "food_order_pending",
            "subscription_active",
        ],
        "instruction_templates": [
            "Finish the daily ordering workflow only after the bundle is prepared, the food order is placed, and the recurring subscription is active.",
            "Close the daily route by preparing the bundle first, placing the food order second, and then finishing with the subscription step.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "daily_order_bundle_prepared",
                "food_order_pending",
                "subscription_active",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; daily bundle workflows should continue beyond a two-step prep action and close with a real food-and-subscription stack."
        ),
        "distinctness_rule": (
            "Either prepare the bundle through coupon management, place the food order, and then activate the subscription, "
            "or use the grocery route before reaching the same food-and-subscription closure."
        ),
        "paths": [
            (
                "path_coupon_food_subscription",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_FOOD_DELIVERY",
                    "MODULE_FRESH_SUBSCRIPTION",
                ],
            ),
            (
                "path_grocery_food_subscription",
                [
                    "MODULE_GROCERY_RUN",
                    "MODULE_FOOD_DELIVERY",
                    "MODULE_FRESH_SUBSCRIPTION",
                ],
            ),
        ],
    },
    "BP_DAILY_SERVICE_FOOD_ALIGNMENT": {
        "difficulty": 5,
        "initial_world_state": ["lease_active"],
        "max_steps": 50,
        "max_module_invocations": 4,
        "target_state": [
            "service_stack_prepared",
            "food_order_pending",
            "subscription_active",
        ],
        "instruction_templates": [
            "Finish the service-oriented daily workflow only after the service stack is prepared, the food order is placed, and the subscription is active.",
            "Close the daily service route by preparing the service layer first, then completing the subscription step, and only then leaving the food order pending.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "service_stack_prepared",
                "food_order_pending",
                "subscription_active",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; service-based daily workflows should close with a concrete subscription and food-order stack instead of stopping after one preparation action."
        ),
        "distinctness_rule": (
            "Either book housekeeping before activating the subscription and placing the food order, "
            "or start from coupon preparation before the same service-and-food closure."
        ),
        "paths": [
            (
                "path_service_subscription_food",
                [
                    "MODULE_HOUSEKEEPING_BOOKING",
                    "MODULE_FRESH_SUBSCRIPTION",
                    "MODULE_FOOD_DELIVERY",
                ],
            ),
            (
                "path_coupon_service_subscription_food",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_HOUSEKEEPING_BOOKING",
                    "MODULE_FRESH_SUBSCRIPTION",
                    "MODULE_FOOD_DELIVERY",
                ],
            ),
        ],
    },
    "BP_DAILY_RESALE_BUNDLE_DUAL": {
        "difficulty": 5,
        "initial_world_state": ["lease_active"],
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "resale_listing_activated",
            "daily_order_bundle_prepared",
            "subscription_active",
        ],
        "instruction_templates": [
            "Finish the resale workflow only after the listing is active, the daily bundle is prepared, and the recurring subscription is turned on.",
            "Close the resale route by activating the listing first, then building the bundle, and ending with subscription activation.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "resale_listing_activated",
                "daily_order_bundle_prepared",
                "subscription_active",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; resale workflows should not stop after a listing-plus-coupon shortcut, "
            "but continue through bundle preparation and subscription closure."
        ),
        "distinctness_rule": (
            "Either activate the resale listing through item listing before coupon management, groceries, and subscription activation, "
            "or use the second-hand sale route before reaching the same bundle-and-subscription outcome."
        ),
        "paths": [
            (
                "path_listing_bundle_subscription",
                [
                    "MODULE_SECOND_HAND_ITEM_LISTING",
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_GROCERY_RUN",
                    "MODULE_FRESH_SUBSCRIPTION",
                ],
            ),
            (
                "path_sale_bundle_subscription",
                [
                    "MODULE_SECOND_HAND_SALE",
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_GROCERY_RUN",
                    "MODULE_FRESH_SUBSCRIPTION",
                ],
            ),
        ],
    },
    "BP_DAILY_PENDING_PRICE_DUAL": {
        "difficulty": 5,
        "initial_world_state": ["bank_account_active", "shop_order_exists"],
        "max_steps": 55,
        "max_module_invocations": 3,
        "target_state": [
            "order_price_secured",
            "order_followup_prepared",
            "delivery_visibility_confirmed",
        ],
        "instruction_templates": [
            "Finish the post-order protection workflow only after the price is secured, the follow-up tracking step is prepared, and delivery visibility is confirmed.",
            "Close the tracked-order route by following the order first, securing the price path, and ending with concrete delivery visibility instead of stopping at a shallow shortcut.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "order_price_secured",
                "order_followup_prepared",
                "delivery_visibility_confirmed",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; price-protection workflows in an order-followup context should start from an existing order and continue through tracking to a concrete delivery-visibility closure."
        ),
        "distinctness_rule": (
            "Either track the existing order, secure the price through explicit protection, and then confirm delivery visibility, "
            "or use the coupon-backed route before tracking the same order into the same visibility-and-follow-up outcome."
        ),
        "paths": [
            (
                "path_tracked_price_visibility",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_PRICE_PROTECTION",
                    "MODULE_ORDER_ARRIVAL",
                ],
            ),
            (
                "path_coupon_tracked_visibility",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                ],
            ),
        ],
    },
    "BP_DAILY_ORDER_VALUE_PROTECTION": {
        "difficulty": 5,
        "initial_world_state": ["bank_account_active", "shop_order_exists"],
        "max_steps": 50,
        "max_module_invocations": 3,
        "target_state": [
            "order_price_secured",
            "order_followup_prepared",
            "delivery_visibility_confirmed",
        ],
        "instruction_templates": [
            "Finish the post-order value workflow only after the price is secured, the follow-up tracking step is ready, and delivery visibility is confirmed.",
            "Close the value-protection route by working from the existing order, securing the price path, and ending with explicit follow-up visibility.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "order_price_secured",
                "order_followup_prepared",
                "delivery_visibility_confirmed",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; order-value protection in a post-purchase context should begin from an existing order and continue through tracking to visible delivery follow-up."
        ),
        "distinctness_rule": (
            "Either track the existing order, secure the price through explicit protection, and then confirm delivery visibility, "
            "or prepare coupons before tracking the order into the same visibility-and-follow-up outcome."
        ),
        "paths": [
            (
                "path_existing_order_protection",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_PRICE_PROTECTION",
                    "MODULE_ORDER_ARRIVAL",
                ],
            ),
            (
                "path_coupon_existing_order",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                ],
            ),
        ],
    },
    "BP_CAREER_ADMIN_SIGNAL_DUAL": {
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
    "BP_CAREER_SUBMISSION_SIGNAL": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "paper_submitted",
            "receipt_archived",
            "career_signal_strengthened",
        ],
        "instruction_templates": [
            "Finish the submission workflow only after the paper is submitted, the receipt is archived, and the final signaling step is completed.",
            "Close the submission route by preparing the right context first, then submitting the paper, archiving the receipt, and ending with a signal-strengthening action.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "paper_submitted",
                "receipt_archived",
                "career_signal_strengthened",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; publication workflows should not stop at submission plus one signal action, "
            "but continue through archival and a final public-facing career signal."
        ),
        "distinctness_rule": (
            "Either track the relevant email thread before submitting the paper, then archive the receipt and strengthen the public signal, "
            "or use the conference-registration route before reaching the same submitted-and-archived outcome."
        ),
        "paths": [
            (
                "path_threaded_submission_signal",
                [
                    "MODULE_EMAIL_TRACKING",
                    "MODULE_PAPER_SUBMISSION",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_UPDATE_LINKEDIN",
                ],
            ),
            (
                "path_registered_submission_signal",
                [
                    "MODULE_CONFERENCE_REGISTRATION",
                    "MODULE_PAPER_SUBMISSION",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_UPDATE_LINKEDIN",
                ],
            ),
        ],
    },
    "BP_CAREER_SUBMISSION_COORDINATION_CHAIN": {
        "difficulty": 5,
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "paper_submitted",
            "deadline_coordination_recorded",
            "receipt_archived",
            "career_signal_strengthened",
        ],
        "instruction_templates": [
            "Finish the coordinated submission workflow only after the paper is submitted, the deadline is coordinated, the receipt is archived, and the signaling step is completed.",
            "Close the submission route by preparing the timing context first, then submitting the paper, archiving the receipt, and ending with a final signaling action.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "paper_submitted",
                "deadline_coordination_recorded",
                "receipt_archived",
                "career_signal_strengthened",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; coordinated submission workflows should include explicit timing control, archival, and a final signaling step."
        ),
        "distinctness_rule": (
            "Either aggregate the deadline before submitting the paper, archive the receipt, and then strengthen the public signal, "
            "or use the conference-registration route before reaching the same submitted-and-coordinated outcome."
        ),
        "paths": [
            (
                "path_calendar_submission_signal",
                [
                    "MODULE_CALENDAR_AGGREGATION",
                    "MODULE_PAPER_SUBMISSION",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_UPDATE_LINKEDIN",
                ],
            ),
            (
                "path_conference_submission_signal",
                [
                    "MODULE_CONFERENCE_REGISTRATION",
                    "MODULE_PAPER_SUBMISSION",
                    "MODULE_RECEIPT_ARCHIVING",
                    "MODULE_UPDATE_LINKEDIN",
                ],
            ),
        ],
    },
    "BP_HEALTH_CLAIM_COVERAGE_DUAL": {
        "difficulty": 5,
        "initial_world_state": [],
        "max_steps": 65,
        "max_module_invocations": 4,
        "target_state": [
            "coverage_path_active",
            "medical_appointment_booked",
            "care_continuity_established",
            "medical_claim_submitted",
        ],
        "instruction_templates": [
            "Finish the care workflow only after coverage is active, the appointment is booked, continuity is established, and the medical claim is submitted.",
            "Close the health route by activating coverage first, then booking the appointment, completing the continuity step, and only then submitting the claim.",
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
            "Generated from {blueprint_id}; claim workflows should continue through an actual appointment and continuity step instead of ending right after activating coverage."
        ),
        "distinctness_rule": (
            "Either activate insurance coverage, book the doctor appointment, refill the prescription, and then submit the medical claim, "
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
    "BP_HEALTH_CONTINUITY_COVERAGE_DUAL": {
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
    "BP_HEALTH_COVERAGE_ILLNESS_REPORTING": {
        "difficulty": 5,
        "initial_world_state": [],
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "coverage_path_active",
            "medical_appointment_booked",
            "illness_report_submitted",
            "care_continuity_established",
        ],
        "instruction_templates": [
            "Finish the illness-report workflow only after coverage is active, the appointment is booked, the illness report is submitted, and continuity is established.",
            "Close the health reporting route by activating coverage first, then booking care, filing the illness report, and ending with the continuity step.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "coverage_path_active",
                "medical_appointment_booked",
                "illness_report_submitted",
                "care_continuity_established",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; illness-report workflows should include real care coordination around the report instead of ending after a bare two-step coverage action."
        ),
        "distinctness_rule": (
            "Either activate insurance coverage, book the doctor appointment, file the illness report, and then complete the follow-on care step, "
            "or activate the health plan before reaching the same appointment-and-report closure."
        ),
        "paths": [
            (
                "path_policy_illness_continuity",
                [
                    "MODULE_INSURANCE_POLICY",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PRESCRIPTION_REFILL",
                ],
            ),
            (
                "path_plan_illness_continuity",
                [
                    "MODULE_HEALTH_PLAN_ACTIVATION",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_ILLNESS_REPORTING",
                    "MODULE_PRESCRIPTION_REFILL",
                ],
            ),
        ],
    },
    "BP_HEALTH_CLAIM_VACCINE": {
        "difficulty": 5,
        "initial_world_state": [],
        "max_steps": 60,
        "max_module_invocations": 4,
        "target_state": [
            "coverage_path_active",
            "medical_appointment_booked",
            "medical_claim_submitted",
            "vaccination_record_updated",
        ],
        "instruction_templates": [
            "Finish the claim-plus-vaccine workflow only after coverage is active, the appointment is booked, the claim is submitted, and the vaccination record is updated.",
            "Close the health route by activating coverage first, then booking the appointment, filing the claim, and ending with the vaccine-record update.",
        ],
        "visible_constraints": {
            "preferred_outcomes": [
                "coverage_path_active",
                "medical_appointment_booked",
                "medical_claim_submitted",
                "vaccination_record_updated",
            ]
        },
        "notes_template": (
            "Generated from {blueprint_id}; claim-and-vaccine workflows should include real care coordination around the claim instead of jumping from coverage straight to a two-step closure."
        ),
        "distinctness_rule": (
            "Either activate insurance coverage, book the doctor appointment, submit the medical claim, and then update the vaccination record, "
            "or activate the health plan before reaching the same appointment, claim, and record outcome."
        ),
        "paths": [
            (
                "path_policy_claim_vaccine",
                [
                    "MODULE_INSURANCE_POLICY",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_MEDICAL_CLAIM",
                    "MODULE_VACCINE_MGMT",
                ],
            ),
            (
                "path_plan_claim_vaccine",
                [
                    "MODULE_HEALTH_PLAN_ACTIVATION",
                    "MODULE_DOCTOR_APPT",
                    "MODULE_MEDICAL_CLAIM",
                    "MODULE_VACCINE_MGMT",
                ],
            ),
        ],
    },
}


def add_aliases(base_id: str, aliases: list[str]) -> None:
    for alias in aliases:
        ROUND8_SPECS[alias] = {"alias_of": base_id}


add_aliases(
    "BP_SOCIAL_COMMITMENT_CONTRIBUTION_DUAL",
    [
        "BP_SOCIAL_COMMITMENT_CONTRIBUTION_ALIGNMENT",
        "BP_SOCIAL_CONTRIBUTION_COMMITMENT_BRIDGE",
        "BP_SOCIAL_CONTRIBUTION_RSVP",
        "BP_SOCIAL_RSVP_CONTRIBUTION_ALIGNMENT",
        "BP_SOCIAL_RSVP_CONTRIBUTION_BRIDGE",
        "BP_SOCIAL_RSVP_DONATION_READINESS",
        "BP_SOCIAL_WORKFLOW_CONTRIBUTION_RSVP",
        "BP_SOCIAL_GROUP_CONTRIBUTION",
        "BP_SOCIAL_ZTRAIN_01_COMMITMENT_CONTRIBUTION_DUAL",
        "BP_SOCIAL_ZTRAIN_04_COMMITMENT_CONTRIBUTION_DUAL",
        "BP_SOCIAL_ZTRAIN_07_COMMITMENT_CONTRIBUTION_DUAL",
        "BP_SOCIAL_ZTRAIN_10_COMMITMENT_CONTRIBUTION_DUAL",
        "BP_SOCIAL_ZTRAIN_13_COMMITMENT_CONTRIBUTION_DUAL",
    ],
)
add_aliases(
    "BP_SOCIAL_SETTLEMENT_COMMITMENT_DUAL",
    [
        "BP_SOCIAL_CONTRIBUTION_SETTLEMENT",
        "BP_SOCIAL_DONATION_SETTLEMENT_BRIDGE",
        "BP_SOCIAL_GIFT_SETTLEMENT_CLOSURE",
        "BP_SOCIAL_RSVP_SETTLEMENT_ALIGNMENT",
        "BP_SOCIAL_SETTLEMENT_COMMITMENT_SYNC",
        "BP_SOCIAL_SETTLEMENT_CONTRIBUTION_DUAL",
        "BP_SOCIAL_WORKFLOW_COMMITMENT_SETTLEMENT",
        "BP_SOCIAL_ZTRAIN_02_SETTLEMENT_COMMITMENT_DUAL",
        "BP_SOCIAL_ZTRAIN_05_SETTLEMENT_COMMITMENT_DUAL",
        "BP_SOCIAL_ZTRAIN_08_SETTLEMENT_COMMITMENT_DUAL",
        "BP_SOCIAL_ZTRAIN_11_SETTLEMENT_COMMITMENT_DUAL",
        "BP_SOCIAL_ZTRAIN_14_SETTLEMENT_COMMITMENT_DUAL",
    ],
)
add_aliases(
    "BP_SOCIAL_CONTRIBUTION_ACCOUNT_DUAL",
    [
        "BP_SOCIAL_ZTRAIN_03_CONTRIBUTION_ACCOUNT_DUAL",
        "BP_SOCIAL_ZTRAIN_06_CONTRIBUTION_ACCOUNT_DUAL",
        "BP_SOCIAL_ZTRAIN_09_CONTRIBUTION_ACCOUNT_DUAL",
        "BP_SOCIAL_ZTRAIN_12_CONTRIBUTION_ACCOUNT_DUAL",
    ],
)
add_aliases(
    "BP_SOCIAL_TICKET_COMMITMENT_ALIGNMENT",
    [
        "BP_SOCIAL_TICKET_COMMITMENT_ALT",
        "BP_SOCIAL_TICKET_SETTLEMENT",
        "BP_SOCIAL_EVENT_CONTRIBUTION_ACCESS",
    ],
)

add_aliases(
    "BP_DAILY_BUNDLE_FOOD_ALIGNMENT",
    [
        "BP_DAILY_BUNDLE_SUBSCRIPTION_ALIGNMENT",
        "BP_DAILY_BUNDLE_SUBSCRIPTION_PREP",
        "BP_DAILY_DUAL_ORDER_PREP",
    ],
)
add_aliases(
    "BP_DAILY_SERVICE_FOOD_ALIGNMENT",
    [
        "BP_DAILY_SERVICE_FOOD_STACK",
        "BP_DAILY_SERVICE_SUBSCRIPTION_STACK",
        "BP_DAILY_SUBSCRIPTION_SERVICE_STACK",
    ],
)
add_aliases(
    "BP_DAILY_RESALE_BUNDLE_DUAL",
    [
        "BP_DAILY_RESALE_COUPON",
        "BP_DAILY_RESALE_SUBSCRIPTION_LOOP",
        "BP_DAILY_WORKFLOW_RESALE_PRICE",
        "BP_DAILY_ZTRAIN_02_RESALE_BUNDLE_DUAL",
        "BP_DAILY_ZTRAIN_05_RESALE_BUNDLE_DUAL",
        "BP_DAILY_ZTRAIN_08_RESALE_BUNDLE_DUAL",
        "BP_DAILY_ZTRAIN_11_RESALE_BUNDLE_DUAL",
        "BP_DAILY_ZTRAIN_14_RESALE_BUNDLE_DUAL",
    ],
)
add_aliases(
    "BP_DAILY_PENDING_PRICE_DUAL",
    [
        "BP_DAILY_ZTRAIN_03_PENDING_PRICE_DUAL",
        "BP_DAILY_ZTRAIN_06_PENDING_PRICE_DUAL",
        "BP_DAILY_ZTRAIN_09_PENDING_PRICE_DUAL",
        "BP_DAILY_ZTRAIN_12_PENDING_PRICE_DUAL",
    ],
)
add_aliases(
    "BP_DAILY_ORDER_VALUE_PROTECTION",
    [
        "BP_DAILY_DISCOUNTED_ORDER_PROTECTION",
    ],
)

add_aliases(
    "BP_CAREER_ADMIN_SIGNAL_DUAL",
    [
        "BP_CAREER_ARCHIVE_SIGNAL_STACK",
        "BP_CAREER_CONFERENCE_DEADLINE_TRACK",
        "BP_CAREER_DEADLINE_SIGNAL_LOOP",
        "BP_CAREER_SIGNAL_CONFERENCE_ALIGNMENT",
        "BP_CAREER_SIGNAL_CONFERENCE_BRIDGE",
        "BP_CAREER_SIGNAL_DEADLINE_ALIGNMENT",
        "BP_CAREER_SIGNAL_RECEIPT",
        "BP_CAREER_WORKFLOW_SIGNAL_ADMIN",
        "BP_CAREER_WORKFLOW_SIGNAL_DEADLINE",
        "BP_CAREER_ZTRAIN_01_ADMIN_SIGNAL_DUAL",
        "BP_CAREER_ZTRAIN_02_DEADLINE_SIGNAL_LOOP",
        "BP_CAREER_ZTRAIN_03_ARCHIVE_SIGNAL_STACK",
        "BP_CAREER_ZTRAIN_04_ADMIN_SIGNAL_DUAL",
        "BP_CAREER_ZTRAIN_05_DEADLINE_SIGNAL_LOOP",
        "BP_CAREER_ZTRAIN_06_ARCHIVE_SIGNAL_STACK",
        "BP_CAREER_ZTRAIN_07_ADMIN_SIGNAL_DUAL",
        "BP_CAREER_ZTRAIN_08_DEADLINE_SIGNAL_LOOP",
        "BP_CAREER_ZTRAIN_09_ARCHIVE_SIGNAL_STACK",
        "BP_CAREER_ZTRAIN_10_ADMIN_SIGNAL_DUAL",
        "BP_CAREER_ZTRAIN_11_DEADLINE_SIGNAL_LOOP",
        "BP_CAREER_ZTRAIN_12_ARCHIVE_SIGNAL_STACK",
        "BP_CAREER_ZTRAIN_13_ADMIN_SIGNAL_DUAL",
        "BP_CAREER_ZTRAIN_14_DEADLINE_SIGNAL_LOOP",
    ],
)
add_aliases(
    "BP_CAREER_SUBMISSION_SIGNAL",
    [
        "BP_CAREER_PUBLICATION_SIGNALING",
        "BP_CAREER_SIGNAL_PAPER_ALIGNMENT",
        "BP_CAREER_SIGNAL_SUBMISSION_CHAIN",
    ],
)
add_aliases(
    "BP_CAREER_SUBMISSION_COORDINATION_CHAIN",
    [
        "BP_CAREER_SUBMISSION_TIMING_ALIGNMENT",
    ],
)

add_aliases(
    "BP_HEALTH_CLAIM_COVERAGE_DUAL",
    [
        "BP_HEALTH_CLAIM_COVERAGE_ALIGNMENT",
        "BP_HEALTH_COVERAGE_CLAIM",
        "BP_HEALTH_COVERAGE_CLAIM_ALIGNMENT",
        "BP_HEALTH_REIMBURSEMENT_CLOSURE",
        "BP_HEALTH_ZTRAIN_02_CLAIM_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_05_CLAIM_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_08_CLAIM_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_11_CLAIM_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_14_CLAIM_COVERAGE_DUAL",
    ],
)
add_aliases(
    "BP_HEALTH_CONTINUITY_COVERAGE_DUAL",
    [
        "BP_HEALTH_APPOINTMENT_MEDICATION_READY",
        "BP_HEALTH_CONTINUITY_APPOINTMENT_ACCESS",
        "BP_HEALTH_CONTINUITY_APPOINTMENT_ALIGNMENT",
        "BP_HEALTH_CONTINUITY_IMMUNIZATION_BRIDGE",
        "BP_HEALTH_COVERAGE_APPOINTMENT_BRIDGE",
        "BP_HEALTH_IMMUNIZATION_COVERAGE_READINESS",
        "BP_HEALTH_IMMUNIZATION_READINESS",
        "BP_HEALTH_WORKFLOW_CONTINUITY_VACCINE",
        "BP_HEALTH_WORKFLOW_COVERAGE_APPOINTMENT",
        "BP_HEALTH_ZTRAIN_01_CONTINUITY_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_04_CONTINUITY_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_07_CONTINUITY_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_10_CONTINUITY_COVERAGE_DUAL",
        "BP_HEALTH_ZTRAIN_13_CONTINUITY_COVERAGE_DUAL",
        "BP_HEALTH_VACCINE_CONTINUITY_DUAL",
        "BP_HEALTH_ZTRAIN_03_VACCINE_CONTINUITY_DUAL",
        "BP_HEALTH_ZTRAIN_06_VACCINE_CONTINUITY_DUAL",
        "BP_HEALTH_ZTRAIN_09_VACCINE_CONTINUITY_DUAL",
        "BP_HEALTH_ZTRAIN_12_VACCINE_CONTINUITY_DUAL",
    ],
)


def resolve_spec(blueprint_id: str) -> dict[str, Any]:
    spec = ROUND8_SPECS[blueprint_id]
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
        if blueprint_id not in ROUND8_SPECS:
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
    print(json.dumps({"patched_blueprints": len(patched), "blueprint_ids": patched}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
