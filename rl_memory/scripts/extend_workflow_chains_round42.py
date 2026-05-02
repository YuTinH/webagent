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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round42'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND42_SPECS: dict[str, dict[str, Any]] = {
    'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['shop_order_exists'],
        'target_state': [
            'delivery_visibility_confirmed',
            'order_tracking_opened',
            'order_followup_prepared',
            'calendar_event_synced',
            'job_application_followup_created',
            'professional_profile_updated',
        ],
        'instruction_templates': [
            'Finish the visibility-sync packet only after delivery visibility is confirmed, tracking is open, follow-up is prepared, the calendar is synced, a job follow-up is created, and the professional profile is updated.',
            'Close the visibility-sync composite workflow by confirming the order path first, opening tracking, syncing the calendar, creating the job follow-up, and ending with a concrete profile update.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; visibility-sync composite workflows should not stop at job search and must continue into an explicit profile-update closure.'
        ),
        'distinctness_rule': (
            'Either take the order-arrival route through tracking, calendar sync, job follow-up, and profile update, '
            'or take the customer-service route through the same tracking, calendar, follow-up, and profile closure.'
        ),
        'paths': [
            (
                'path_arrival_track_calendar_job_profile',
                [
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_JOB_SEARCH',
                    'MODULE_UPDATE_LINKEDIN',
                ],
            ),
            (
                'path_service_track_calendar_job_profile',
                [
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_JOB_SEARCH',
                    'MODULE_UPDATE_LINKEDIN',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_DELIVERY_CALENDAR_ORCHESTRATION': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_WORKFLOW_FOLLOWUP_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_WORKFLOW_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_ZTRAIN_03_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_ZTRAIN_06_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_ZTRAIN_09_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},
    'BP_COMPOSITE_ZTRAIN_12_CALENDAR_VISIBILITY_SYNC': {'alias_of': 'BP_COMPOSITE_VISIBILITY_SIGNAL_PACKET'},

    'BP_COMPOSITE_ACCESS_HYGIENE_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active', 'shop_order_exists'],
        'target_state': [
            'account_access_contained',
            'delivery_visibility_confirmed',
            'order_followup_prepared',
            'order_tracking_opened',
            'calendar_event_synced',
            'access_surface_reviewed',
            'credential_vault_updated',
        ],
        'instruction_templates': [
            'Finish the access-followup packet only after access is contained, delivery visibility is confirmed, order tracking is open, the calendar is synced, and the credential surface is reviewed and updated.',
            'Close the access-followup composite workflow by containing the access issue first, completing the service-tracking follow-up, syncing the calendar, and ending with password-manager hygiene.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; access-followup composite workflows should continue into credential-surface hygiene after the service and calendar steps.'
        ),
        'distinctness_rule': (
            'Either recover access and then go through service, tracking, calendar, and password-manager closure, '
            'or freeze the lost-card surface first and then complete the same downstream follow-up and hygiene chain.'
        ),
        'paths': [
            (
                'path_recovery_service_track_calendar_hygiene',
                [
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_PASSWORD_MANAGER',
                ],
            ),
            (
                'path_freeze_service_track_calendar_hygiene',
                [
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_PASSWORD_MANAGER',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_HYGIENE_PACKET'},
    'BP_COMPOSITE_ZTRAIN_02_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_HYGIENE_PACKET'},
    'BP_COMPOSITE_ZTRAIN_05_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_HYGIENE_PACKET'},
    'BP_COMPOSITE_ZTRAIN_08_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_HYGIENE_PACKET'},
    'BP_COMPOSITE_ZTRAIN_11_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_HYGIENE_PACKET'},
    'BP_COMPOSITE_ZTRAIN_14_ACCESS_FOLLOWUP_DUAL': {'alias_of': 'BP_COMPOSITE_ACCESS_HYGIENE_PACKET'},

    'BP_COMPOSITE_PAYMENT_RECORD_PACKET': {
        'difficulty': 8,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active', 'lease_active', 'shop_order_exists'],
        'target_state': [
            'payment_stack_prepared',
            'delivery_visibility_confirmed',
            'order_tracking_opened',
            'calendar_event_synced',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the payment-visibility packet only after the payment path is prepared, delivery visibility is confirmed, order tracking is open, the calendar is synced, and the payment record is archived.',
            'Close the payment-visibility composite workflow by preparing the payment route first, then confirming visibility, opening tracking, syncing the calendar, and ending with receipt archival.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; payment-visibility composite workflows should end with an explicit record-keeping step rather than stopping at calendar sync.'
        ),
        'distinctness_rule': (
            'Either use the autopay route before visibility, tracking, calendar, and receipt archival, '
            'or use the transfer route before the same visibility, tracking, calendar, and archival closure.'
        ),
        'paths': [
            (
                'path_autopay_arrival_track_calendar_archive',
                [
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_transfer_service_track_calendar_archive',
                [
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_RECORD_PACKET'},
    'BP_COMPOSITE_ZTRAIN_01_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_RECORD_PACKET'},
    'BP_COMPOSITE_ZTRAIN_04_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_RECORD_PACKET'},
    'BP_COMPOSITE_ZTRAIN_07_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_RECORD_PACKET'},
    'BP_COMPOSITE_ZTRAIN_10_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_RECORD_PACKET'},
    'BP_COMPOSITE_ZTRAIN_13_PAYMENT_VISIBILITY_DUAL': {'alias_of': 'BP_COMPOSITE_PAYMENT_RECORD_PACKET'},

    'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET': {
        'difficulty': 7,
        'max_steps': 75,
        'max_module_invocations': 6,
        'initial_world_state': [],
        'target_state': [
            'housing_finance_prepared',
            'address_confirmation_verified',
            'bank_account_active',
            'mobile_service_active',
            'mobile_plan_updated',
        ],
        'instruction_templates': [
            'Finish the newcomer finance-switch packet only after housing finance is prepared, the address is confirmed, the bank account is active, mobile service is active, and the mobile plan is updated.',
            'Close the newcomer onboarding route by formalizing housing first, verifying the address trail, activating banking, turning mobile service on, and ending with a plan update.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer finance/bootstrap flows should continue past bank activation into a live mobile-service and plan-update closure.'
        ),
        'distinctness_rule': (
            'Either take the formal lease-registration and address-proof route before banking, mobile activation, and mobile-plan switching, '
            'or take the lease-review and utility-backed route before the same banking and mobile closure.'
        ),
        'paths': [
            (
                'path_register_proof_bank_mobile_switch',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_MOBILE_PLAN_SWITCH',
                ],
            ),
            (
                'path_review_utility_bank_mobile_switch',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_MOBILE_PLAN_SWITCH',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_PROOF_BANK_DUAL': {'alias_of': 'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET'},
    'BP_NEWCOMER_ZTRAIN_02_PROOF_BANK_DUAL': {'alias_of': 'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET'},
    'BP_NEWCOMER_ZTRAIN_05_PROOF_BANK_DUAL': {'alias_of': 'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET'},
    'BP_NEWCOMER_ZTRAIN_08_PROOF_BANK_DUAL': {'alias_of': 'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET'},
    'BP_NEWCOMER_ZTRAIN_11_PROOF_BANK_DUAL': {'alias_of': 'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET'},
    'BP_NEWCOMER_ZTRAIN_14_PROOF_BANK_DUAL': {'alias_of': 'BP_NEWCOMER_FINANCE_SWITCH_READY_PACKET'},

    'BP_NEWCOMER_ADDRESS_FINANCE_BOOTSTRAP_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'residency_record_verified',
            'address_records_aligned',
            'bank_account_active',
            'mobile_service_active',
        ],
        'instruction_templates': [
            'Finish the newcomer address-finance bootstrap only after housing is secured, residency is verified, address records are aligned, the bank account is active, and mobile service is active.',
            'Close the newcomer bootstrap by finding housing first, validating the proof trail, aligning the address record, activating banking, and ending with live mobile service.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer address/bootstrap flows should align address records before concluding the banking and connectivity setup.'
        ),
        'distinctness_rule': (
            'Either use the direct address-proof route before address alignment, banking, and mobile activation, '
            'or use the utility-backed residency route before the same aligned address, banking, and mobile closure.'
        ),
        'paths': [
            (
                'path_home_proof_align_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
            (
                'path_home_utility_align_bank_mobile',
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
    'BP_NEWCOMER_CONNECTIVITY_PROOF': {'alias_of': 'BP_NEWCOMER_ADDRESS_FINANCE_BOOTSTRAP_PACKET'},
    'BP_NEWCOMER_FINANCE_ADDRESS_BOOTSTRAP': {'alias_of': 'BP_NEWCOMER_ADDRESS_FINANCE_BOOTSTRAP_PACKET'},
    'BP_NEWCOMER_FINANCE_CONNECTIVITY_BRIDGE': {'alias_of': 'BP_NEWCOMER_ADDRESS_FINANCE_BOOTSTRAP_PACKET'},
    'BP_NEWCOMER_RESIDENCY_BANK_ALIGNMENT': {'alias_of': 'BP_NEWCOMER_ADDRESS_FINANCE_BOOTSTRAP_PACKET'},

    'BP_NEWCOMER_HOUSING_FINANCE_ALIGNMENT_PACKET': {
        'difficulty': 7,
        'max_steps': 75,
        'max_module_invocations': 6,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'housing_finance_prepared',
            'residency_record_verified',
            'bank_account_active',
            'mobile_service_active',
            'address_records_aligned',
        ],
        'instruction_templates': [
            'Finish the newcomer housing-finance packet only after housing is secured, housing finance is prepared, residency is verified, the bank account is active, mobile service is active, and address records are aligned.',
            'Close the housing-finance onboarding workflow by finding housing first, completing the lease-finance path, verifying residency before banking, activating mobile service, and ending with address alignment.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; housing-finance onboarding should verify residency before banking and end with address-record alignment rather than stopping at mobile activation.'
        ),
        'distinctness_rule': (
            'Either take the lease-registration and address-proof route before banking, mobile activation, and address alignment, '
            'or take the lease-review and utility-backed route before the same banking, mobile, and address closure.'
        ),
        'paths': [
            (
                'path_home_register_proof_bank_mobile_align',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_ADDRESS_CHANGE',
                ],
            ),
            (
                'path_home_review_utility_bank_mobile_align',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_ADDRESS_CHANGE',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_LEASE_FINANCE_REGISTRY': {'alias_of': 'BP_NEWCOMER_HOUSING_FINANCE_ALIGNMENT_PACKET'},
    'BP_NEWCOMER_HOUSING_FINANCE_ALIGNMENT': {'alias_of': 'BP_NEWCOMER_HOUSING_FINANCE_ALIGNMENT_PACKET'},
    'BP_NEWCOMER_WORKFLOW_CONNECTIVITY_FINANCE': {'alias_of': 'BP_NEWCOMER_HOUSING_FINANCE_ALIGNMENT_PACKET'},

    'BP_NEWCOMER_FINANCE_RESIDENCY_SWITCH_PACKET': {
        'difficulty': 7,
        'max_steps': 75,
        'max_module_invocations': 6,
        'initial_world_state': [],
        'target_state': [
            'housing_finance_prepared',
            'bank_account_active',
            'mobile_service_active',
            'residency_record_verified',
            'mobile_plan_updated',
        ],
        'instruction_templates': [
            'Finish the newcomer finance-residency packet only after housing finance is prepared, the bank account is active, mobile service is active, residency is verified, and the mobile plan is updated.',
            'Close the newcomer finance-residency workflow by securing housing first, completing the finance and residency steps in order, activating mobile service, and ending with a plan update.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; finance-residency newcomer flows must establish housing first and should not open banking before residency evidence is available.'
        ),
        'distinctness_rule': (
            'Either follow the find-home, lease-registration, address-proof, banking, mobile-activation, and plan-switch route, '
            'or follow the find-home, lease-review, utility-backed residency, banking, mobile-activation, and plan-switch route.'
        ),
        'paths': [
            (
                'path_home_register_proof_bank_mobile_switch',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_MOBILE_PLAN_SWITCH',
                ],
            ),
            (
                'path_home_review_utility_bank_mobile_switch',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_MOBILE_PLAN_SWITCH',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_WORKFLOW_FINANCE_RESIDENCY': {'alias_of': 'BP_NEWCOMER_FINANCE_RESIDENCY_SWITCH_PACKET'},
    'BP_NEWCOMER_FINANCE_BANK': {'alias_of': 'BP_NEWCOMER_FINANCE_RESIDENCY_SWITCH_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND42_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND42_SPECS[alias]
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
        raise SystemExit('round42 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
