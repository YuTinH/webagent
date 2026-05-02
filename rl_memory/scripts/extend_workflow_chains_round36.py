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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round36'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND36_SPECS: dict[str, dict[str, Any]] = {
    'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET': {
        'difficulty': 7,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'account_access_contained',
            'delivery_visibility_confirmed',
            'order_followup_prepared',
            'order_tracking_opened',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the access-followup packet only after account access is contained, delivery visibility is confirmed, order follow-up is prepared, order tracking is open, and the calendar event is synced.',
            'Close the access-followup composite workflow by containing account access first, checking customer-service visibility, preparing tracking follow-up, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; cross-domain access-followup tasks should include a calendar synchronization closure after the commerce follow-up steps.'
        ),
        'distinctness_rule': (
            'Either restore access through end-to-end password recovery before customer service, order tracking, and calendar sync, '
            'or contain access through card freeze before the same customer-service, tracking, and sync closure.'
        ),
        'paths': [
            (
                'path_recovery_service_track_calendar',
                [
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
            (
                'path_freeze_service_track_calendar',
                [
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET'},
    'BP_COMPOSITE_ZTRAIN_02_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET'},
    'BP_COMPOSITE_ZTRAIN_05_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET'},
    'BP_COMPOSITE_ZTRAIN_08_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET'},
    'BP_COMPOSITE_ZTRAIN_11_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET'},
    'BP_COMPOSITE_ZTRAIN_14_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_FOLLOWUP_PACKET'},
    'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET': {
        'difficulty': 7,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active', 'lease_active', 'shop_order_exists'],
        'target_state': [
            'payment_stack_prepared',
            'delivery_visibility_confirmed',
            'order_tracking_opened',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the payment-visibility packet only after the payment stack is prepared, delivery visibility is confirmed, order tracking is open, and the calendar event is synced.',
            'Close the payment-visibility composite workflow by preparing the payment path first, then confirming delivery visibility, opening order tracking, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; payment-visibility composite tasks should include a calendar synchronization closure after the payment and tracking steps.'
        ),
        'distinctness_rule': (
            'Either prepare payment through complex autopay before delivery arrival, order tracking, and calendar sync, '
            'or prepare payment through direct transfer before customer-service visibility, order tracking, and the same sync closure.'
        ),
        'paths': [
            (
                'path_autopay_arrival_track_calendar',
                [
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
            (
                'path_transfer_service_track_calendar',
                [
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET'},
    'BP_COMPOSITE_ZTRAIN_01_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET'},
    'BP_COMPOSITE_ZTRAIN_04_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET'},
    'BP_COMPOSITE_ZTRAIN_07_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET'},
    'BP_COMPOSITE_ZTRAIN_10_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET'},
    'BP_COMPOSITE_ZTRAIN_13_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_VISIBILITY_PACKET'},
    'BP_COMPOSITE_VISIBILITY_SYNC_PACKET': {
        'difficulty': 7,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['shop_order_exists'],
        'target_state': [
            'delivery_visibility_confirmed',
            'order_tracking_opened',
            'order_followup_prepared',
            'calendar_event_synced',
            'job_application_followup_created',
        ],
        'instruction_templates': [
            'Finish the visibility-sync packet only after delivery visibility is confirmed, order tracking is open, order follow-up is prepared, the calendar event is synced, and a job follow-up is created.',
            'Close the visibility-sync composite workflow by confirming order visibility first, opening tracking, syncing the calendar, and ending with the cross-domain follow-up task created.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; visibility-sync composite tasks should require a cross-domain follow-up action after the commerce tracking and calendar steps.'
        ),
        'distinctness_rule': (
            'Either confirm visibility through order arrival before tracking, calendar sync, and the cross-domain follow-up, '
            'or confirm visibility through customer service before the same tracking, sync, and follow-up closure.'
        ),
        'paths': [
            (
                'path_arrival_track_calendar_job',
                [
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_JOB_SEARCH',
                ],
            ),
            (
                'path_service_track_calendar_job',
                [
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_JOB_SEARCH',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_DELIVERY_CALENDAR_ORCHESTRATION': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['shop_order_exists']},
    'BP_COMPOSITE_WORKFLOW_FOLLOWUP_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_WORKFLOW_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_ZTRAIN_03_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_ZTRAIN_06_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_ZTRAIN_09_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_ZTRAIN_12_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SYNC_PACKET', 'initial_world_state': ['bank_account_active', 'shop_order_exists']},
    'BP_COMPOSITE_AUTOPAY_PACKET': {
        'difficulty': 7,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'bills_aggregated',
            'autopay_enabled',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the autopay packet only after the bank account is active, bills are aggregated, autopay is enabled, and the receipt is archived.',
            'Close the autopay orchestration workflow by opening the bank account, aggregating bills, enabling autopay, and ending with the receipt archived.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; autopay composite tasks should include documentation after the payment-automation step.'
        ),
        'distinctness_rule': (
            'Either open the bank account and enable basic autopay after bill aggregation before receipt archiving, '
            'or open the account and enable the complex-autopay route before the same archive closure.'
        ),
        'paths': [
            (
                'path_bank_bills_autopay_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_AUTOPAY',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bank_bills_complex_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_AUTOPAY_ORCHESTRATION': {'alias_of': 'BP_COMPOSITE_AUTOPAY_PACKET'},
    'BP_COMPOSITE_FOLLOWUP_PAYMENT_PACKET': {
        'difficulty': 7,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'order_followup_prepared',
            'delivery_visibility_confirmed',
            'order_tracking_opened',
            'payment_stack_prepared',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the followup-payment packet only after order follow-up is prepared, delivery visibility is confirmed, order tracking is open, the payment stack is prepared, and the calendar event is synced.',
            'Close the followup-payment composite workflow by confirming the order follow-up first, preparing payment, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; followup-payment composite tasks should include a calendar-sync closure after follow-up and payment preparation.'
        ),
        'distinctness_rule': (
            'Either prepare follow-up through customer service before tracking, transfer-based payment, and calendar sync, '
            'or prepare follow-up through tracking plus customer service before complex-autopay payment and the same sync closure.'
        ),
        'paths': [
            (
                'path_service_track_transfer_calendar',
                [
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
            (
                'path_track_service_autopay_calendar',
                [
                    'MODULE_TRACK_ORDERS',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_FOLLOWUP_PAYMENT': {'alias_of': 'BP_COMPOSITE_FOLLOWUP_PAYMENT_PACKET'},
    'BP_COMPOSITE_ACCESS_PORTFOLIO_PACKET': {
        'difficulty': 7,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'password_reset_completed',
            'investment_growth_verified',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the access-portfolio packet only after password reset is completed, investment growth is verified, and the calendar event is synced.',
            'Close the access-portfolio composite workflow by completing the reset first, verifying portfolio growth, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; access-portfolio composite tasks should include a concrete scheduling closure after portfolio verification.'
        ),
        'distinctness_rule': 'Reach the target state through the full reset, portfolio-growth, and calendar-sync chain rather than through a shorter subset route.',
        'paths': [
            (
                'path_reset_growth_calendar',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_ACCESS_PORTFOLIO_READINESS': {'alias_of': 'BP_COMPOSITE_ACCESS_PORTFOLIO_PACKET'},
    'BP_COMPOSITE_INVESTMENT_CALENDAR_PACKET': {
        'difficulty': 7,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'investment_account_active',
            'auction_bid_placed',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the investment-calendar packet only after the investment account is active, the auction bid is placed, and the calendar event is synced.',
            'Close the investment-calendar composite workflow by opening the bank account, activating the investment path, placing the auction bid, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; investment-calendar composite tasks should include an auction action before the scheduling closure.'
        ),
        'distinctness_rule': 'Reach the target state through the full bank-opening, investment, auction, and calendar-sync chain rather than through a shorter subset route.',
        'paths': [
            (
                'path_bank_invest_auction_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_LIVE_AUCTION',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_INVESTMENT_CALENDAR_BOOTSTRAP': {'alias_of': 'BP_COMPOSITE_INVESTMENT_CALENDAR_PACKET'},
    'BP_COMPOSITE_INVEST_AUCTION_PACKET': {
        'difficulty': 7,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'investment_account_active',
            'auction_bid_placed',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the invest-auction packet only after the investment account is active, the auction bid is placed, and the calendar event is synced.',
            'Close the invest-auction composite workflow by opening the bank account, verifying the investment path, placing the auction bid, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; invest-auction composite tasks should include calendar synchronization after the auction action.'
        ),
        'distinctness_rule': (
            'Either open the bank account and activate the investment account before the auction and calendar sync, '
            'or open the bank account and verify investment growth before the same auction-and-sync closure.'
        ),
        'paths': [
            (
                'path_bank_invest_auction_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_LIVE_AUCTION',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
            (
                'path_bank_growth_auction_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_LIVE_AUCTION',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_INVEST_AUCTION': {'alias_of': 'BP_COMPOSITE_INVEST_AUCTION_PACKET'},
    'BP_COMPOSITE_SUBSCRIPTION_PAYMENT_PACKET': {
        'difficulty': 7,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active', 'subscription_active'],
        'target_state': [
            'subscription_exit_processed',
            'payment_stack_prepared',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the subscription-payment packet only after the subscription exit is processed, the payment stack is prepared, and the calendar event is synced.',
            'Close the subscription-exit composite workflow by opening the bank account, processing the exit, preparing the payment path, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; subscription-exit composite tasks should include a calendar-sync closure after the payment step.'
        ),
        'distinctness_rule': (
            'Either open the bank account and cancel the subscription before transfer-based payment and calendar sync, '
            'or open the account and request the subscription refund before complex-autopay payment and the same sync closure.'
        ),
        'paths': [
            (
                'path_bank_cancel_transfer_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_CANCEL_SUBSCRIPTION',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
            (
                'path_bank_refund_autopay_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_SUBSCRIPTION_REFUND',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_SUBSCRIPTION_PAYMENT_EXIT': {'alias_of': 'BP_COMPOSITE_SUBSCRIPTION_PAYMENT_PACKET'},
    'BP_COMPOSITE_SUPPORT_ACCESS_PACKET': {
        'difficulty': 7,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['shop_order_exists'],
        'target_state': [
            'password_reset_completed',
            'support_contacted',
            'order_tracking_opened',
            'order_followup_prepared',
        ],
        'instruction_templates': [
            'Finish the support-access packet only after password reset is completed, support is contacted, order tracking is open, and order follow-up is prepared.',
            'Close the support-access composite workflow by completing the reset first, contacting support, opening order tracking, and ending with follow-up prepared.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; support-access composite tasks should include an order-tracking follow-up after the support step.'
        ),
        'distinctness_rule': 'Reach the target state through the full reset, support, and order-tracking follow-up chain rather than through a shorter subset route.',
        'paths': [
            (
                'path_reset_support_track',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_SUPPORT_ACCESS_SYNC': {'alias_of': 'BP_COMPOSITE_SUPPORT_ACCESS_PACKET'},
    'BP_COMPOSITE_VISIBILITY_PAYMENT_PACKET': {
        'difficulty': 7,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'calendar_event_synced',
            'delivery_visibility_confirmed',
            'payment_stack_prepared',
            'order_tracking_opened',
        ],
        'instruction_templates': [
            'Finish the visibility-payment packet only after the calendar event is synced, delivery visibility is confirmed, the payment stack is prepared, and order tracking is open.',
            'Close the visibility-payment composite workflow by syncing the calendar first, then confirming delivery visibility, preparing the payment path, and ending with order tracking open.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; visibility-payment composite tasks should include order tracking after the calendar and payment steps.'
        ),
        'distinctness_rule': (
            'Either sync the calendar and confirm delivery through order arrival before transfer-based payment and order tracking, '
            'or sync the calendar and confirm delivery through customer service before complex-autopay payment and the same tracking closure.'
        ),
        'paths': [
            (
                'path_calendar_arrival_transfer_track',
                [
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_TRACK_ORDERS',
                ],
            ),
            (
                'path_calendar_service_autopay_track',
                [
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_TRACK_ORDERS',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_VISIBILITY_PAYMENT_STACK': {'alias_of': 'BP_COMPOSITE_VISIBILITY_PAYMENT_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND36_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND36_SPECS[alias]
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
        raise SystemExit('round36 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
