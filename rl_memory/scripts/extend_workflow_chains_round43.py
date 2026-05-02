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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round43'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND43_SPECS: dict[str, dict[str, Any]] = {
    'BP_NEWCOMER_ADDRESS_FINANCE_MOBILE_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'address_records_aligned',
            'bank_account_active',
            'payment_method_available',
            'mobile_service_active',
        ],
        'instruction_templates': [
            'Finish the newcomer paperwork-finance packet only after housing is active, address records are aligned, the bank account is active, payment is ready, and mobile service is active.',
            'Close the newcomer paperwork route by securing housing first, aligning the address records, opening the bank account, and ending with live mobile service.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer paperwork and finance flows should continue into a live connectivity step after address and banking alignment.'
        ),
        'distinctness_rule': (
            'Either use the direct address-proof route before address alignment, banking, and mobile activation, '
            'or use the utility-backed route before the same address, banking, and connectivity closure.'
        ),
        'paths': [
            (
                'path_direct_address_finance_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
            (
                'path_utility_backed_address_finance_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_ADDRESS_FINANCE_READY': {'alias_of': 'BP_NEWCOMER_ADDRESS_FINANCE_MOBILE_PACKET'},

    'BP_NEWCOMER_CONNECTIVITY_SWITCH_ALIGNMENT_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'mobile_plan_updated',
            'address_records_aligned',
        ],
        'instruction_templates': [
            'Finish the newcomer connectivity-switch packet only after address confirmation is established, the mobile plan is updated, and the address record is aligned.',
            'Close newcomer connectivity setup by verifying the address path first, switching the mobile plan, and ending with the address record aligned.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; connectivity-switch newcomer workflows should not stop at the mobile switch and must close with address-record alignment.'
        ),
        'distinctness_rule': (
            'Either use the address-proof route before mobile signup, switching, and address alignment, '
            'or use the utility-backed residency route before the same switching and address-alignment closure.'
        ),
        'paths': [
            (
                'path_proof_signup_switch_align',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_MOBILE_PLAN_SWITCH',
                    'MODULE_ADDRESS_CHANGE',
                ],
            ),
            (
                'path_utility_signup_switch_align',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_MOBILE_PLAN_SWITCH',
                    'MODULE_ADDRESS_CHANGE',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_PROOF_CONNECTIVITY_SWITCH': {'alias_of': 'BP_NEWCOMER_CONNECTIVITY_SWITCH_ALIGNMENT_PACKET'},
    'BP_NEWCOMER_CONNECTIVITY_SWITCH_READY': {'alias_of': 'BP_NEWCOMER_CONNECTIVITY_SWITCH_ALIGNMENT_PACKET'},
    'BP_NEWCOMER_RESIDENCY_MOBILE': {'alias_of': 'BP_NEWCOMER_CONNECTIVITY_SWITCH_ALIGNMENT_PACKET'},

    'BP_NEWCOMER_HOUSING_UTILITY_CONNECTIVITY_PACKET': {
        'difficulty': 7,
        'max_steps': 70,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'housing_finance_prepared',
            'utilities_active',
            'bank_account_active',
            'residency_record_verified',
            'mobile_service_active',
        ],
        'instruction_templates': [
            'Finish the newcomer housing-utility packet only after housing is secured, housing finance is prepared, utilities are active, the bank account is active, residency is verified, and mobile service is active.',
            'Close the housing-utility onboarding workflow by finding housing first, preparing the housing-finance path, activating utilities, opening the bank account, and ending with live mobile service.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; housing-utility newcomer flows should continue into live connectivity after utilities and banking are established.'
        ),
        'distinctness_rule': (
            'Either use the lease-registration route before utility activation, banking, and mobile activation, '
            'or use the lease-review route before the same utility, banking, and connectivity closure.'
        ),
        'paths': [
            (
                'path_home_register_utility_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
            (
                'path_home_review_utility_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_HOUSING_UTILITY_FINANCE': {'alias_of': 'BP_NEWCOMER_HOUSING_UTILITY_CONNECTIVITY_PACKET'},

    'BP_NEWCOMER_BANK_UTILITIES_ALIGNMENT_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'bank_account_active',
            'utilities_active',
            'residency_record_verified',
            'address_records_aligned',
        ],
        'instruction_templates': [
            'Finish the newcomer bank-utilities packet only after the bank account is active, utilities are active, residency is verified, and address records are aligned.',
            'Close the newcomer bank-utilities route by establishing the residency trail first, activating utilities, opening the bank account, and ending with address alignment.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer bank-and-utilities flows should align records after the residency and utility trail is established.'
        ),
        'distinctness_rule': (
            'Either use the address-proof route before utilities, banking, and address alignment, '
            'or use the lease-review route before utilities, banking, and the same address-alignment closure.'
        ),
        'paths': [
            (
                'path_proof_utility_bank_align',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_ADDRESS_CHANGE',
                ],
            ),
            (
                'path_review_utility_bank_align',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_ADDRESS_CHANGE',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_BANK_UTILITIES': {'alias_of': 'BP_NEWCOMER_BANK_UTILITIES_ALIGNMENT_PACKET'},

    'BP_COMPOSITE_AUTOPAY_CALENDAR_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'bills_aggregated',
            'autopay_enabled',
            'receipt_archived',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the autopay packet only after the bank account is active, bills are aggregated, autopay is enabled, the receipt is archived, and the calendar is synced.',
            'Close the autopay orchestration workflow by opening the bank account, aggregating bills, enabling autopay, archiving the receipt, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; autopay composite workflows should schedule a concrete reminder after archival rather than stopping at payment setup.'
        ),
        'distinctness_rule': (
            'Either use the standard autopay route before archival and calendar sync, '
            'or use the complex-autopay route before the same archival and calendar closure.'
        ),
        'paths': [
            (
                'path_bank_bills_autopay_archive_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_AUTOPAY',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
            (
                'path_bank_bills_complex_archive_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_AUTOPAY_ORCHESTRATION': {'alias_of': 'BP_COMPOSITE_AUTOPAY_CALENDAR_PACKET'},

    'BP_COMPOSITE_SUBSCRIPTION_PAYMENT_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active', 'subscription_active'],
        'target_state': [
            'subscription_exit_processed',
            'payment_stack_prepared',
            'calendar_event_synced',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the subscription-payment packet only after the subscription exit is processed, the payment stack is prepared, the calendar is synced, and the exit record is archived.',
            'Close the subscription-exit composite workflow by opening the bank account, completing the exit route, preparing the payment path, syncing the calendar, and ending with record archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; subscription-exit composite workflows should end with an explicit record-archival step after calendar sync.'
        ),
        'distinctness_rule': (
            'Either use the cancel-and-transfer route before calendar sync and archival, '
            'or use the refund-and-autopay route before the same calendar and archival closure.'
        ),
        'paths': [
            (
                'path_bank_cancel_transfer_calendar_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_CANCEL_SUBSCRIPTION',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bank_refund_autopay_calendar_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_SUBSCRIPTION_REFUND',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_SUBSCRIPTION_PAYMENT_EXIT': {'alias_of': 'BP_COMPOSITE_SUBSCRIPTION_PAYMENT_RECORD_PACKET'},

    'BP_COMPOSITE_VISIBILITY_PAYMENT_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'calendar_event_synced',
            'delivery_visibility_confirmed',
            'payment_stack_prepared',
            'order_tracking_opened',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the visibility-payment packet only after the calendar is synced, delivery visibility is confirmed, the payment path is prepared, order tracking is open, and the record is archived.',
            'Close the visibility-payment composite workflow by syncing the calendar first, confirming delivery visibility, preparing payment, reopening tracking, and ending with receipt archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; visibility-payment composite workflows should close with explicit archival after the payment and tracking steps.'
        ),
        'distinctness_rule': (
            'Either use the arrival-and-transfer route before tracking and archival, '
            'or use the service-and-autopay route before the same tracking and archival closure.'
        ),
        'paths': [
            (
                'path_calendar_arrival_transfer_track_archive',
                [
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_calendar_service_autopay_track_archive',
                [
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_VISIBILITY_PAYMENT_STACK': {'alias_of': 'BP_COMPOSITE_VISIBILITY_PAYMENT_RECORD_PACKET'},

    'BP_COMPOSITE_EXPENSE_PAYMENT_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'payment_stack_prepared',
            'expense_report_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the composite admin flow only after the payment stack is prepared, the expense packet is filed, and the receipt is archived.',
            'Close the mixed finance-travel workflow by lining up payment preparation, submitting the expense report, and ending with archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; finance-travel expense workflows should explicitly archive the proof bundle after expense submission.'
        ),
        'distinctness_rule': (
            'Either use the transfer-and-hotel route before expense submission and archival, '
            'or use the autopay-and-flight route before the same expense and archival closure.'
        ),
        'paths': [
            (
                'path_transfer_hotel_expense_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_EXPENSE_REPORT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_autopay_flight_expense_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_EXPENSE_REPORT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_EXPENSE_PAYMENT_ALIGNMENT': {'alias_of': 'BP_COMPOSITE_EXPENSE_PAYMENT_RECORD_PACKET'},

    'BP_COMPOSITE_REBOOK_FUNDING_EXPENSE_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'tax_funding_prepared',
            'itinerary_rebooked',
            'expense_report_submitted',
        ],
        'instruction_templates': [
            'Finish the mixed finance-travel workflow only after the tax-funding side is prepared, the itinerary is rebooked, and the expense report is submitted.',
            'Close the composite rebooking route by preparing the funding path, completing rebooking, and ending with the expense packet filed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; rebooking-and-funding composite flows should submit the expense claim after the itinerary is stabilized.'
        ),
        'distinctness_rule': (
            'Either use the transfer-based route before rebooking and expense submission, '
            'or use the tax-preparation route before the same rebooking and expense closure.'
        ),
        'paths': [
            (
                'path_transfer_then_rebook_expense',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
            (
                'path_prepare_then_longhaul_rebook_expense',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TAX_PREPARATION',
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_REBOOK_FUNDING_ALIGNMENT': {'alias_of': 'BP_COMPOSITE_REBOOK_FUNDING_EXPENSE_PACKET'},

    'BP_COMPOSITE_AUTOPAY_EXPENSE_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'autopay_enabled',
            'expense_report_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the mixed admin workflow only after autopay is enabled, the expense report is submitted, and the receipt is archived.',
            'Close the finance-travel route by turning on autopay, filing the expense packet, and ending with archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; autopay-and-expense composite workflows should archive the proof after the expense packet is filed.'
        ),
        'distinctness_rule': (
            'Either use the standard autopay and hotel route before expense archival, '
            'or use the complex-autopay and flight route before the same expense and archival closure.'
        ),
        'paths': [
            (
                'path_autopay_hotel_expense_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_AUTOPAY',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_EXPENSE_REPORT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_complex_flight_expense_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_EXPENSE_REPORT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_AUTOPAY_EXPENSE_ALIGNMENT': {'alias_of': 'BP_COMPOSITE_AUTOPAY_EXPENSE_RECORD_PACKET'},

    'BP_COMPOSITE_INVEST_AUCTION_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'investment_account_active',
            'auction_bid_placed',
            'calendar_event_synced',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the invest-auction packet only after the investment account is active, the auction bid is placed, the calendar is synced, and the record is archived.',
            'Close the invest-auction composite workflow by opening the bank account, verifying the investment path, placing the bid, syncing the calendar, and ending with archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; invest-auction composite workflows should archive the confirmation after the bid and calendar steps.'
        ),
        'distinctness_rule': (
            'Either use the direct investment-account route before auction, calendar, and archival, '
            'or use the investment-growth route before the same auction, calendar, and archival closure.'
        ),
        'paths': [
            (
                'path_bank_invest_auction_calendar_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_LIVE_AUCTION',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bank_growth_auction_calendar_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_LIVE_AUCTION',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_INVEST_AUCTION': {'alias_of': 'BP_COMPOSITE_INVEST_AUCTION_RECORD_PACKET'},

    'BP_COMPOSITE_FOLLOWUP_PAYMENT_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'order_followup_prepared',
            'delivery_visibility_confirmed',
            'order_tracking_opened',
            'payment_stack_prepared',
            'calendar_event_synced',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the followup-payment packet only after order follow-up is prepared, delivery visibility is confirmed, order tracking is open, the payment path is prepared, the calendar is synced, and the record is archived.',
            'Close the followup-payment composite workflow by confirming the order follow-up first, preparing payment, syncing the calendar, and ending with archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; followup-payment composite workflows should archive the proof after the calendar handoff.'
        ),
        'distinctness_rule': (
            'Either use the service-and-transfer route before calendar sync and archival, '
            'or use the tracking-and-autopay route before the same calendar and archival closure.'
        ),
        'paths': [
            (
                'path_service_track_transfer_calendar_archive',
                [
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_track_service_autopay_calendar_archive',
                [
                    'MODULE_TRACK_ORDERS',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_FOLLOWUP_PAYMENT': {'alias_of': 'BP_COMPOSITE_FOLLOWUP_PAYMENT_RECORD_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND43_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND43_SPECS[alias]
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
        raise SystemExit('round43 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
