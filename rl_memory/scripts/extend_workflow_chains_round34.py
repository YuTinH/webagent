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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round34'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND34_SPECS: dict[str, dict[str, Any]] = {
    'BP_GOV_ADDRESS_ALIGNMENT_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'address_records_aligned',
            'mailing_address_current',
            'permit_application_submitted',
        ],
        'instruction_templates': [
            'Finish the civic address packet only after address confirmation is verified, address records are aligned, the mailing address is current, and the permit application is submitted.',
            'Close the government-address workflow by securing the home first, verifying proof or utility evidence, aligning the address records, and then submitting the permit application.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; civic address workflows should carry through record alignment before the final permit submission.'
        ),
        'distinctness_rule': (
            'Either secure housing and verify the address through address proof before alignment and permit submission, '
            'or secure housing and verify the address through utility setup before the same alignment-and-submission closure.'
        ),
        'paths': [
            (
                'path_home_proof_change_permit',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_PERMIT_APP',
                ],
            ),
            (
                'path_home_utility_change_permit',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_PERMIT_APP',
                ],
            ),
        ],
    },
    'BP_GOV_ADDRESS_PROOF_PERMIT_ALIGNMENT': {'alias_of': 'BP_GOV_ADDRESS_ALIGNMENT_PACKET'},
    'BP_GOV_ADDRESS_RECORD_ALIGNMENT': {'alias_of': 'BP_GOV_ADDRESS_ALIGNMENT_PACKET'},
    'BP_GOV_CIVIC_RECORD_VERIFICATION': {'alias_of': 'BP_GOV_ADDRESS_ALIGNMENT_PACKET'},
    'BP_GOV_WORKFLOW_ALIGNMENT_READINESS': {'alias_of': 'BP_GOV_ADDRESS_ALIGNMENT_PACKET'},
    'BP_GOV_PERMIT_COMPLIANCE_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'parking_permit_active',
            'local_vehicle_compliance_verified',
            'vehicle_address_updated',
            'permit_renewed',
        ],
        'instruction_templates': [
            'Finish the permit-compliance packet only after address confirmation is verified, the parking permit is active, vehicle compliance is verified, the vehicle address is updated, and the permit is renewed.',
            'Close the permit-compliance workflow by securing the home first, verifying the address trail, and then completing parking-permit activation, address update, and renewal.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; permit-compliance workflows should include address verification plus both activation and renewal rather than ending after a single compliance step.'
        ),
        'distinctness_rule': (
            'Either secure housing and verify the address through address proof before permit activation, renewal, and vehicle-address update, '
            'or secure housing and verify the address through utility setup before the same vehicle, permit, and renewal closure.'
        ),
        'paths': [
            (
                'path_home_proof_permit_renew_update',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_PARKING_PERMIT_APPLICATION',
                    'MODULE_PERMIT_RENEWAL',
                    'MODULE_VEHICLE_ADDRESS_UPDATE',
                ],
            ),
            (
                'path_home_utility_vehicle_permit_renew',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_VEHICLE_ADDRESS_UPDATE',
                    'MODULE_PARKING_PERMIT_APPLICATION',
                    'MODULE_PERMIT_RENEWAL',
                ],
            ),
        ],
    },
    'BP_GOV_COMPLIANCE_PARKING_ALIGNMENT': {'alias_of': 'BP_GOV_PERMIT_COMPLIANCE_PACKET'},
    'BP_GOV_PERMIT_COMPLIANCE_ALT': {'alias_of': 'BP_GOV_PERMIT_COMPLIANCE_PACKET'},
    'BP_GOV_WORKFLOW_PERMIT_COMPLIANCE': {'alias_of': 'BP_GOV_PERMIT_COMPLIANCE_PACKET'},
    'BP_NEWCOMER_CONNECTIVITY_FINANCE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'residency_record_verified',
            'bank_account_active',
            'mobile_service_active',
        ],
        'instruction_templates': [
            'Finish the newcomer connectivity-finance packet only after housing is secured, residency is verified, the bank account is active, and the mobile service is active.',
            'Close the newcomer bootstrap workflow by finding housing first, verifying the address trail, opening the bank account, and ending with mobile service active.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer connectivity workflows should include banking before mobile activation rather than stopping at proof collection.'
        ),
        'distinctness_rule': (
            'Either secure housing and verify residency through address proof before bank opening and mobile activation, '
            'or secure housing and verify residency through utility setup before the same bank-and-mobile closure.'
        ),
        'paths': [
            (
                'path_home_proof_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
            (
                'path_home_utility_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_CONNECTIVITY_PROOF': {'alias_of': 'BP_NEWCOMER_CONNECTIVITY_FINANCE_PACKET'},
    'BP_NEWCOMER_FINANCE_ADDRESS_BOOTSTRAP': {'alias_of': 'BP_NEWCOMER_CONNECTIVITY_FINANCE_PACKET'},
    'BP_NEWCOMER_RESIDENCY_BANK_ALIGNMENT': {'alias_of': 'BP_NEWCOMER_CONNECTIVITY_FINANCE_PACKET'},
    'BP_NEWCOMER_ACTIVE_LEASE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'housing_finance_prepared',
            'bank_account_active',
            'mobile_service_active',
            'residency_record_verified',
        ],
        'instruction_templates': [
            'Finish the active-lease newcomer packet only after housing finance is prepared, the bank account is active, the mobile service is active, and residency is verified.',
            'Close the active-lease onboarding workflow by preparing the housing-finance record, opening the bank account, activating mobile service, and finishing the residency verification step.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; active-lease newcomer workflows should continue through proof or utility verification after banking and mobile setup.'
        ),
        'distinctness_rule': (
            'Either prepare housing finance through lease registration before bank opening, mobile activation, and address-proof verification, '
            'or prepare housing finance through lease review before the same bank, mobile, and utility-verification closure.'
        ),
        'paths': [
            (
                'path_register_bank_mobile_proof',
                [
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_ADDRESS_PROOF',
                ],
            ),
            (
                'path_review_bank_mobile_utility',
                [
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                    'MODULE_UTILITY_SETUP',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_FINANCE_BANK': {'alias_of': 'BP_NEWCOMER_ACTIVE_LEASE_PACKET'},
    'BP_NEWCOMER_WORKFLOW_FINANCE_RESIDENCY': {'alias_of': 'BP_NEWCOMER_ACTIVE_LEASE_PACKET'},
    'BP_NEWCOMER_FIND_HOME_FINANCE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'housing_finance_prepared',
            'bank_account_active',
            'mobile_service_active',
        ],
        'instruction_templates': [
            'Finish the newcomer housing-finance packet only after housing is secured, housing finance is prepared, the bank account is active, and the mobile service is active.',
            'Close the housing-finance onboarding workflow by finding housing first, preparing the lease-finance path, opening the bank account, and ending with mobile service active.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer housing-finance workflows should include a concrete connectivity closure after banking.'
        ),
        'distinctness_rule': (
            'Either secure housing and prepare finance through lease registration before bank opening and mobile activation, '
            'or secure housing and prepare finance through lease review before the same bank-and-mobile closure.'
        ),
        'paths': [
            (
                'path_home_register_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
            (
                'path_home_review_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_HOUSING_FINANCE_ALIGNMENT': {'alias_of': 'BP_NEWCOMER_FIND_HOME_FINANCE_PACKET'},
    'BP_NEWCOMER_LEASE_FINANCE_REGISTRY': {'alias_of': 'BP_NEWCOMER_FIND_HOME_FINANCE_PACKET'},
    'BP_NEWCOMER_WORKFLOW_CONNECTIVITY_FINANCE': {'alias_of': 'BP_NEWCOMER_FIND_HOME_FINANCE_PACKET'},
    'BP_NEWCOMER_HOUSING_UTILITY_FINANCE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'housing_finance_prepared',
            'utilities_active',
            'bank_account_active',
            'residency_record_verified',
        ],
        'instruction_templates': [
            'Finish the newcomer housing-utility packet only after housing is secured, housing finance is prepared, utilities are active, the bank account is active, and residency is verified.',
            'Close the housing-utility onboarding workflow by finding housing first, preparing the housing-finance path, activating utilities, and then opening the bank account.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; housing-utility newcomer workflows should extend through banking after utility activation.'
        ),
        'distinctness_rule': (
            'Either secure housing and prepare finance through lease registration before utility activation and bank opening, '
            'or secure housing and prepare finance through lease review before the same utility-and-bank closure.'
        ),
        'paths': [
            (
                'path_home_register_utility_bank',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                ],
            ),
            (
                'path_home_review_utility_bank',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_BANK_OPENING',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_HOUSING_UTILITY_FINANCE': {'alias_of': 'BP_NEWCOMER_HOUSING_UTILITY_FINANCE_PACKET'},
    'BP_DAILY_GROCERY_RESALE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'daily_order_bundle_prepared',
            'order_price_secured',
            'resale_listing_activated',
            'market_listing_active',
            'sale_listing_active',
        ],
        'instruction_templates': [
            'Finish the grocery-resale packet only after the daily order bundle is prepared, pricing is secured, the resale listing is activated, the market listing is active, and the sale listing is active.',
            'Close the daily resale workflow by preparing the grocery bundle, securing pricing, and then carrying the resale flow through both listing steps.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; daily resale workflows should include both listing stages rather than stopping at the first resale action.'
        ),
        'distinctness_rule': (
            'Reach the target state through the full grocery, coupon, listing, and sale chain rather than stopping at the first resale action.'
        ),
        'paths': [
            (
                'path_grocery_coupon_list_sale',
                [
                    'MODULE_GROCERY_RUN',
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_SECOND_HAND_ITEM_LISTING',
                    'MODULE_SECOND_HAND_SALE',
                ],
            ),
        ],
    },
    'BP_DAILY_RESALE_DISCOUNT_STACK': {'alias_of': 'BP_DAILY_GROCERY_RESALE_PACKET'},
    'BP_DAILY_SERVICE_RESALE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'service_stack_prepared',
            'order_price_secured',
            'resale_listing_activated',
            'market_listing_active',
            'sale_listing_active',
        ],
        'instruction_templates': [
            'Finish the service-resale packet only after the service stack is prepared, pricing is secured, the resale listing is activated, the market listing is active, and the sale listing is active.',
            'Close the daily service-resale workflow by preparing the service stack, securing pricing, and then carrying the resale flow through both listing steps.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; service-oriented daily resale workflows should include both listing stages rather than stopping at the first resale action.'
        ),
        'distinctness_rule': (
            'Reach the target state through the full service, coupon, listing, and sale chain rather than stopping at the first resale action.'
        ),
        'paths': [
            (
                'path_service_coupon_list_sale',
                [
                    'MODULE_HOUSEKEEPING_BOOKING',
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_SECOND_HAND_ITEM_LISTING',
                    'MODULE_SECOND_HAND_SALE',
                ],
            ),
        ],
    },
    'BP_DAILY_SERVICE_RESALE_BRIDGE': {'alias_of': 'BP_DAILY_SERVICE_RESALE_PACKET'},
    'BP_CAREER_EXPENSE_ARCHIVE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'expense_report_submitted',
            'receipt_archived',
            'conference_expense_logged',
            'conference_admin_recorded',
        ],
        'instruction_templates': [
            'Finish the expense-archive packet only after the expense report is submitted, the receipt is archived, and the conference expense log is recorded with its admin record.',
            'Close the career-expense workflow by booking travel, filing the expense report, archiving the receipt, and ending with the conference expense logged.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; career expense workflows should include a concrete conference-admin closure after archiving.'
        ),
        'distinctness_rule': (
            'Either prepare the expense flow from a flight booking before reporting, archiving, and conference logging, '
            'or prepare the same expense flow from a hotel booking before the same report, archive, and conference closure.'
        ),
        'paths': [
            (
                'path_flight_expense_archive_conference',
                [
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_EXPENSE_REPORT',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_CONFERENCE_REG',
                ],
            ),
            (
                'path_hotel_expense_archive_conference',
                [
                    'MODULE_BOOK_HOTEL',
                    'MODULE_EXPENSE_REPORT',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_CONFERENCE_REG',
                ],
            ),
        ],
    },
    'BP_CAREER_EXPENSE_ARCHIVE': {'alias_of': 'BP_CAREER_EXPENSE_ARCHIVE_PACKET'},
    'BP_CAREER_SIGNALING_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'career_signal_strengthened',
            'job_application_followup_created',
            'deadline_coordination_recorded',
            'conference_admin_recorded',
            'conference_registered',
        ],
        'instruction_templates': [
            'Finish the job-signaling packet only after the career signal is strengthened, the job-application follow-up is created, deadline coordination is recorded, and the conference registration admin record is complete.',
            'Close the career-signaling workflow by strengthening the signal first, creating the job follow-up, coordinating deadlines, and ending with conference registration recorded.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; career signaling workflows should extend through conference registration after deadline coordination.'
        ),
        'distinctness_rule': (
            'Either strengthen the signal through profile updates before job search, deadline coordination, and conference registration, '
            'or strengthen the signal through email tracking before the same follow-up, coordination, and registration closure.'
        ),
        'paths': [
            (
                'path_linkedin_job_calendar_conference',
                [
                    'MODULE_UPDATE_LINKEDIN',
                    'MODULE_JOB_SEARCH',
                    'MODULE_CALENDAR_AGGREGATION',
                    'MODULE_CONFERENCE_REGISTRATION',
                ],
            ),
            (
                'path_email_job_calendar_conference',
                [
                    'MODULE_EMAIL_TRACKING',
                    'MODULE_JOB_SEARCH',
                    'MODULE_CALENDAR_AGGREGATION',
                    'MODULE_CONFERENCE_REGISTRATION',
                ],
            ),
        ],
    },
    'BP_CAREER_JOB_SIGNALING': {'alias_of': 'BP_CAREER_SIGNALING_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND34_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND34_SPECS[alias]
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
        raise SystemExit('round34 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
