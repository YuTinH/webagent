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
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
BATCH_ROOT = ROOT / 'tasks' / 'generated_workflow_split_batches' / 'workflow_split_batch_v20'
GENERATOR_PATH = ROOT / 'rl_memory' / 'scripts' / 'generate_workflow_goal_batch.py'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def load_generator_module():
    spec = importlib.util.spec_from_file_location('workflow_goal_generator', GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'failed to load generator from {GENERATOR_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_step_lookup(paths: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in paths:
        for step in path.get('steps', []):
            module_id = step.get('module_id')
            if module_id and module_id not in lookup:
                lookup[module_id] = copy.deepcopy(step)
    return lookup


def build_global_step_lookup(blueprints: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for blueprint in blueprints:
        for module_id, step in base_step_lookup(blueprint.get('paths', [])).items():
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
        step = {'module_id': module_id}

    bindings = step.get('parameter_bindings')
    if isinstance(bindings, dict):
        referenced = {
            value[1:]
            for value in bindings.values()
            if isinstance(value, str) and value.startswith('@')
        }
        if not referenced.issubset(allowed_shared_vars):
            step.pop('parameter_bindings', None)
    return step


def build_path(
    local_lookup: dict[str, dict[str, Any]],
    global_lookup: dict[str, dict[str, Any]],
    allowed_shared_vars: set[str],
    path_id: str,
    module_ids: list[str],
    kind: str = 'alternative',
) -> dict[str, Any]:
    return {
        'path_id': path_id,
        'kind': kind,
        'steps': [
            step_from_lookup(local_lookup, global_lookup, allowed_shared_vars, module_id)
            for module_id in module_ids
        ],
    }


def replace_preferred_outcomes(existing: dict[str, Any], outcomes: list[str]) -> dict[str, Any]:
    updated = copy.deepcopy(existing)
    updated['preferred_outcomes'] = outcomes
    return updated


def stable_goal_seed(goal_id: str, blueprint_id: str) -> int:
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round37'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND37_SPECS: dict[str, dict[str, Any]] = {
    'BP_SUPPORT_DIRECT_REMEDY_ESCALATION': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 4,
        'initial_world_state': ['shop_order_delivered'],
        'target_state': [
            'support_contacted',
            'post_purchase_remedy_requested',
            'product_review_submitted',
            'merchant_blacklisted',
        ],
        'instruction_templates': [
            'Finish the direct-remedy escalation only after support is contacted, a concrete remedy is requested, a review is submitted, and the merchant is blacklisted.',
            'Close the support-remedy route by opening the remedy first, submitting explicit feedback next, and ending with the blacklist action.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; direct-remedy support workflows should include an explicit review step before the final blacklist action.'
        ),
        'distinctness_rule': (
            'Either contact support, request the return remedy, submit the review, and then blacklist the merchant, '
            'or open the logistics route, file the warranty claim, submit the review, and then reach the same blacklist closure.'
        ),
        'paths': [
            (
                'path_contact_return_review_blacklist',
                [
                    'MODULE_CONTACT_SUPPORT',
                    'MODULE_RETURN',
                    'MODULE_LEAVE_REVIEW',
                    'MODULE_REVIEWS_BLACKLIST',
                ],
            ),
            (
                'path_logistics_warranty_review_blacklist',
                [
                    'MODULE_LOGISTICS_FIX',
                    'MODULE_WARRANTY_CLAIM',
                    'MODULE_LEAVE_REVIEW',
                    'MODULE_REVIEWS_BLACKLIST',
                ],
            ),
        ],
    },
    'BP_SUPPORT_EXIT_CONTACT_DUAL': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 4,
        'initial_world_state': ['subscription_active', 'shop_order_delivered'],
        'target_state': [
            'support_contacted',
            'refund_requested',
            'subscription_canceled',
            'subscription_exit_processed',
            'product_review_submitted',
        ],
        'instruction_templates': [
            'Finish the subscription-exit contact flow only after support is reached, the refund is requested, the subscription is canceled, and the exit closes with explicit feedback submitted.',
            'Close the exit workflow by handling support and refund first, processing the cancellation, and ending with a submitted review about the experience.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; subscription-exit workflows should include explicit post-exit feedback instead of stopping once the cancellation is processed.'
        ),
        'distinctness_rule': (
            'Either contact support before refund, cancellation, and the final review step, '
            'or use the customer-service branch before the same refund, cancellation, and review-backed exit closure.'
        ),
        'paths': [
            (
                'path_contact_refund_cancel_review',
                [
                    'MODULE_CONTACT_SUPPORT',
                    'MODULE_SUBSCRIPTION_REFUND',
                    'MODULE_CANCEL_SUBSCRIPTION',
                    'MODULE_LEAVE_REVIEW',
                ],
            ),
            (
                'path_service_cancel_refund_review',
                [
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_CANCEL_SUBSCRIPTION',
                    'MODULE_SUBSCRIPTION_REFUND',
                    'MODULE_LEAVE_REVIEW',
                ],
            ),
        ],
    },
    'BP_SECURITY_AUDIT_HARDEN_ALIGNMENT': {
        'difficulty': 5,
        'max_steps': 48,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'access_surface_reviewed',
            'two_factor_enabled',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the security-hardening workflow only after the access surface is reviewed, two-factor is enabled, secrets are rotated, and the audit is completed.',
            'Close the security route by reviewing the password surface first, enabling 2FA next, hardening the credentials, and ending with the audit.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; audit-oriented security workflows should include an explicit access-surface review before the 2FA, rotation, and audit sequence.'
        ),
        'distinctness_rule': (
            'Reach the target through the full password-manager, 2FA, security-rotation, and audit chain rather than through a shorter audit-only shortcut.'
        ),
        'paths': [
            (
                'path_passwordmgr_twofa_rotation_audit',
                [
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_2FA_SETUP',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_CRISIS_CARD_ACCESS_CONTAINMENT': {
        'difficulty': 6,
        'max_steps': 55,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'password_reset_completed',
            'card_frozen',
            'account_access_contained',
            'replacement_card_requested',
        ],
        'instruction_templates': [
            'Finish the card-access containment workflow only after the password reset is completed, the card is frozen, account access is contained, and the replacement card is requested.',
            'Close the crisis route by completing the reset first, freezing the exposed card, and ending with a replacement-card request instead of stopping at containment.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; lost-card containment should continue through replacement handling rather than stopping once the card is frozen.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset-request, reset-completion, lost-card-freeze, and card-replacement chain rather than through a shorter containment subset.'
        ),
        'paths': [
            (
                'path_reset_freeze_replace',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_CARD_REPLACEMENT',
                ],
            ),
        ],
    },
    'BP_HOME_CONTROL_READINESS_ALT': {
        'difficulty': 6,
        'max_steps': 55,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active', 'utilities_active'],
        'target_state': [
            'energy_control_configured',
            'camera_config_verified',
            'home_device_readiness_confirmed',
            'home_service_monitored',
            'thermostat_schedule_configured',
        ],
        'instruction_templates': [
            'Finish the home-control readiness workflow only after energy control is configured, camera monitoring is verified, device readiness is confirmed, and the thermostat schedule is configured.',
            'Close the home-control route by setting the control layer first, verifying monitoring next, completing firmware readiness, and ending with the thermostat schedule configured.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; control-oriented home workflows should end with an explicit thermostat scheduling step after control, monitoring, and firmware readiness.'
        ),
        'distinctness_rule': (
            'Either configure the home through the smart-meter route before camera verification, firmware readiness, and thermostat scheduling, '
            'or use the energy-optimization route before the same monitored-scheduling closure.'
        ),
        'paths': [
            (
                'path_meter_camera_firmware_schedule',
                [
                    'MODULE_SMART_METER',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_THERMOSTAT_SCHEDULE',
                ],
            ),
            (
                'path_optimize_camera_firmware_schedule',
                [
                    'MODULE_ENERGY_OPTIMIZE',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_THERMOSTAT_SCHEDULE',
                ],
            ),
        ],
    },
    'BP_EDU_ASSIGNMENT_CERT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['education_account_activated'],
        'target_state': [
            'course_enrolled',
            'assignment_resources_provisioned',
            'assignment_submitted',
            'certificate_downloaded',
        ],
        'instruction_templates': [
            'Finish the assignment packet only after the course is enrolled, assignment resources are provisioned, the assignment is submitted, and the certificate is downloaded.',
            'Close the coursework flow by enrolling first, securing assignment resources, submitting the assignment, and downloading the related certificate artifact.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; assignment-oriented education tasks should continue through certificate retrieval rather than stopping at submission.'
        ),
        'distinctness_rule': (
            'Either enroll and provision resources through ebook purchase before submission and certificate download, '
            'or enroll and provision resources through the library route before the same submission-and-download closure.'
        ),
        'paths': [
            (
                'path_course_ebook_submit_cert',
                [
                    'MODULE_COURSE_ENROLLMENT',
                    'MODULE_BUY_EBOOK',
                    'MODULE_SUBMIT_ASSIGNMENT',
                    'MODULE_DOWNLOAD_CERT',
                ],
            ),
            (
                'path_course_library_submit_cert',
                [
                    'MODULE_COURSE_ENROLLMENT',
                    'MODULE_LIBRARY_SERVICE',
                    'MODULE_SUBMIT_ASSIGNMENT',
                    'MODULE_DOWNLOAD_CERT',
                ],
            ),
        ],
    },
    'BP_EDUCATION_ASSIGNMENT_RESOURCE_DELIVERY': {'alias_of': 'BP_EDU_ASSIGNMENT_CERT_PACKET'},
    'BP_EDUCATION_ASSIGNMENT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_ASSIGNMENT_CERT_PACKET'},
    'BP_TRAVEL_BOOKING_EXPENSE_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'travel_booking_confirmed',
            'hotel_booked',
            'airport_transfer_arranged',
            'expense_report_submitted',
        ],
        'instruction_templates': [
            'Finish the booking-expense workflow only after the travel booking is confirmed, the hotel is booked, the airport transfer is arranged, and the expense report is submitted.',
            'Close the travel workflow by confirming the trip first, adding the stay booking, arranging the airport transfer, and ending with the expense report filed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; booking-expense travel workflows should include both stay planning and airport transfer before the report is filed.'
        ),
        'distinctness_rule': (
            'Either book the flight before hotel, airport transfer, and expense reporting, '
            'or use the long-haul booking route before the same hotel, transfer, and reporting closure.'
        ),
        'paths': [
            (
                'path_flight_hotel_transfer_expense',
                [
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
            (
                'path_longhaul_hotel_transfer_expense',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
        ],
    },
    'BP_TRAVEL_BOOKING_TOPUP': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'travel_booking_confirmed',
            'hotel_booked',
            'airport_transfer_arranged',
            'transit_balance_topped_up',
        ],
        'instruction_templates': [
            'Finish the booking-topup workflow only after the travel booking is confirmed, the hotel is booked, the airport transfer is arranged, and the transit balance is topped up.',
            'Close the travel-readiness route by confirming the trip first, adding the stay booking, arranging transfer logistics, and ending with the transport top-up.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; booking-topup travel workflows should include both stay planning and transfer logistics before the transit balance is topped up.'
        ),
        'distinctness_rule': (
            'Either book the flight before hotel, airport transfer, and transit top-up, '
            'or use the long-haul route before the same hotel, transfer, and top-up closure.'
        ),
        'paths': [
            (
                'path_flight_hotel_transfer_topup',
                [
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_TRANSPORT_TOPUP',
                ],
            ),
            (
                'path_longhaul_hotel_transfer_topup',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_TRANSPORT_TOPUP',
                ],
            ),
        ],
    },
    'BP_DAILY_BUNDLE_SUBSCRIPTION_PREP': {
        'difficulty': 6,
        'max_steps': 55,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'daily_order_bundle_prepared',
            'service_stack_prepared',
            'food_order_pending',
            'subscription_active',
        ],
        'instruction_templates': [
            'Finish the daily bundle-prep workflow only after the order bundle is prepared, the service stack is prepared, the food order is pending, and the subscription is active.',
            'Close the daily route by preparing the household stack first, then finishing the food-and-subscription bundle instead of stopping at a shallow prep step.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; bundle-prep daily workflows should include a real household-service step before the final food-and-subscription closure.'
        ),
        'distinctness_rule': (
            'Either prepare the bundle through coupon management before housekeeping, food delivery, and subscription activation, '
            'or use the grocery route before the same housekeeping-backed food-and-subscription closure.'
        ),
        'paths': [
            (
                'path_coupon_service_food_subscription',
                [
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_HOUSEKEEPING_BOOKING',
                    'MODULE_FOOD_DELIVERY',
                    'MODULE_FRESH_SUBSCRIPTION',
                ],
            ),
            (
                'path_grocery_service_subscription_food',
                [
                    'MODULE_GROCERY_RUN',
                    'MODULE_HOUSEKEEPING_BOOKING',
                    'MODULE_FRESH_SUBSCRIPTION',
                    'MODULE_FOOD_DELIVERY',
                ],
            ),
        ],
    },
    'BP_DAILY_DISCOUNTED_ORDER_PROTECTION': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'order_price_secured',
            'order_followup_prepared',
            'order_tracking_opened',
            'delivery_visibility_confirmed',
            'shop_order_delivered',
            'support_contacted',
        ],
        'instruction_templates': [
            'Finish the discounted-order protection workflow only after the order price is secured, tracking is open, delivery is visible, the order is delivered, and support contact is completed.',
            'Close the post-order protection route by opening tracking first, securing the price path, confirming delivery, and ending with a concrete support follow-up.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; discounted order-protection workflows should continue through delivery confirmation and a real support follow-up instead of stopping after price protection.'
        ),
        'distinctness_rule': (
            'Either track the existing order, secure the price, confirm arrival, and then contact customer service, '
            'or prepare the coupon-backed protection route before the same tracking, arrival, and support-backed closure.'
        ),
        'paths': [
            (
                'path_track_price_arrival_service',
                [
                    'MODULE_TRACK_ORDERS',
                    'MODULE_PRICE_PROTECTION',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_CUSTOMER_SERVICE',
                ],
            ),
            (
                'path_coupon_track_arrival_service',
                [
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_CUSTOMER_SERVICE',
                ],
            ),
        ],
    },
    'BP_SOCIAL_CONTRIBUTION_COMMITMENT_BRIDGE': {
        'difficulty': 6,
        'max_steps': 55,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'social_contribution_completed',
            'event_ticket_booked',
            'event_rsvp_completed',
            'social_commitment_recorded',
            'shared_expenses_settled',
        ],
        'instruction_templates': [
            'Finish the contribution-commitment bridge only after the contribution is completed, the event ticket is booked, the RSVP is recorded, and the shared expenses are settled.',
            'Close the social route by completing the contribution first, locking the ticketed commitment next, and ending with shared-expense settlement.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; contribution workflows should include an explicit ticket-booking step before RSVP confirmation and expense settlement.'
        ),
        'distinctness_rule': (
            'Either donate before booking the event ticket, confirming the RSVP, and settling the shared expenses, '
            'or use gift pooling before the same ticketed-commitment and settlement closure.'
        ),
        'paths': [
            (
                'path_donation_ticket_rsvp_settlement',
                [
                    'MODULE_CHARITY_DONATION',
                    'MODULE_EVENT_TICKETS',
                    'MODULE_RSVP_EVENT',
                    'MODULE_ROOMMATE_EXPENSE_SPLIT',
                ],
            ),
            (
                'path_pooling_ticket_rsvp_settlement',
                [
                    'MODULE_GIFT_POOLING',
                    'MODULE_EVENT_TICKETS',
                    'MODULE_RSVP_EVENT',
                    'MODULE_ROOMMATE_EXPENSE_SPLIT',
                ],
            ),
        ],
    },
    'BP_CRISIS_CARD_LIQUIDITY_CONTAINMENT': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'account_access_contained',
            'crisis_intake_completed',
            'password_reset_completed',
            'account_balance_reviewed',
            'emergency_liquidity_secured',
        ],
        'instruction_templates': [
            'Finish the crisis-liquidity workflow only after access is contained, crisis intake is completed, password recovery is complete, the account balance is reviewed, and emergency liquidity is secured.',
            'Close the crisis route by completing intake and account recovery first, reviewing the account balance, and ending with the emergency-liquidity step.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; crisis-liquidity workflows should include an explicit account-balance review before the urgent-funds step.'
        ),
        'distinctness_rule': (
            'Either contain the lost-card access first before recovery, balance review, and the urgent-loan step, '
            'or use the illness-intake route before the same recovery, balance-review, and liquidity closure.'
        ),
        'paths': [
            (
                'path_freeze_recovery_balance_loan',
                [
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_URGENT_LOAN',
                ],
            ),
            (
                'path_illness_recovery_balance_loan',
                [
                    'MODULE_ILLNESS_REPORTING',
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_URGENT_LOAN',
                ],
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND37_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND37_SPECS[alias]
        merged = {key: copy.deepcopy(value) for key, value in base.items() if key != 'alias_of'}
        for key, value in spec.items():
            if key != 'alias_of':
                merged[key] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(spec)


def main() -> None:
    generator = load_generator_module()
    modules_doc = load_json(generator.MODULE_LIBRARY)
    modules_by_id = {m['module_id']: m for m in modules_doc['modules']}
    bindings_doc = load_json(generator.BINDING_LIBRARY)
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings_doc['bindings']:
        bindings_by_module[binding['module_id']].append(binding)
    requirements = load_json(generator.QUALITY_REQUIREMENTS)

    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc['blueprints']
    global_lookup = build_global_step_lookup(blueprints)

    patched_blueprints: dict[str, dict[str, Any]] = {}
    validation_issues: list[str] = []

    for bp in blueprints:
        blueprint_id = bp['blueprint_id']
        spec = resolve_spec(blueprint_id)
        if spec is None:
            continue

        local_lookup = base_step_lookup(bp.get('paths', []))
        allowed_shared_vars = set(bp.get('shared_variable_pools', {}).keys())
        target_state = spec['target_state']

        bp['difficulty'] = spec['difficulty']
        bp['max_steps'] = spec['max_steps']
        bp['max_module_invocations'] = spec['max_module_invocations']
        bp['target_state'] = copy.deepcopy(target_state)
        bp['instruction_templates'] = copy.deepcopy(spec['instruction_templates'])
        bp['visible_constraints'] = replace_preferred_outcomes(bp.get('visible_constraints', {}), target_state)
        bp['notes_template'] = spec['notes_template']
        bp['distinctness_rule'] = spec['distinctness_rule']
        if 'initial_world_state' in spec:
            bp['initial_world_state'] = copy.deepcopy(spec['initial_world_state'])
        bp['paths'] = [
            build_path(
                local_lookup,
                global_lookup,
                allowed_shared_vars,
                path_id,
                module_ids,
            )
            for path_id, module_ids in spec['paths']
        ]

        issues = generator.validate_blueprint(bp, modules_by_id, requirements)
        if issues:
            validation_issues.extend(issues)
        patched_blueprints[blueprint_id] = copy.deepcopy(bp)

    if validation_issues:
        raise SystemExit('round37 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    refreshed_counts = {'dev': 0, 'test': 0, 'train': 0}
    for split in ['dev', 'test', 'train']:
        manifest = load_json(BATCH_ROOT / split / 'manifest.json')
        for ref in manifest.get('goals', []):
            blueprint_id = ref['blueprint_id']
            if blueprint_id not in patched_blueprints:
                continue

            blueprint = patched_blueprints[blueprint_id]
            rng = random.Random(stable_goal_seed(ref['goal_id'], blueprint_id))
            shared_vars = generator.sample_shared_variables(blueprint, rng)
            goal = generator.build_goal(ref['goal_id'], blueprint, shared_vars, rng)
            oracle = generator.build_oracle(
                ref['goal_id'],
                blueprint,
                modules_by_id,
                bindings_by_module,
                shared_vars,
            )
            save_json(BATCH_ROOT / split / ref['goal_file'], goal)
            save_json(BATCH_ROOT / split / ref['oracle_file'], oracle)
            refreshed_counts[split] += 1

    print(
        json.dumps(
            {
                'patched_blueprints': sorted(patched_blueprints),
                'patched_blueprint_count': len(patched_blueprints),
                'refreshed_counts': refreshed_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
