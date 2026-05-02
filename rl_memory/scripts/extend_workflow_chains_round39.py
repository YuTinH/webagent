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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round39'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND39_SPECS: dict[str, dict[str, Any]] = {
    'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET': {
        'difficulty': 7,
        'max_steps': 70,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'account_data_exported',
            'account_exit_prepared',
            'access_surface_reviewed',
            'privacy_settings_updated',
            'credential_vault_updated',
            'security_audit_completed',
            'deletion_request_submitted',
        ],
        'instruction_templates': [
            'Finish the security-exit packet only after account export is complete, privacy settings are reviewed, the credential vault is updated, the audit is closed, and the deletion request is submitted.',
            'Close the security-exit workflow by exporting the account first, reviewing privacy and credentials, completing the audit, and ending with formal data deletion.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; security exit workflows should end with a deletion request after export, review, and audit rather than stopping once the audit is complete.'
        ),
        'distinctness_rule': (
            'Reach the target through the full export, privacy-review, credential-review, audit, and deletion chain rather than through a shorter exit subset.'
        ),
        'paths': [
            (
                'path_export_privacy_vault_audit_delete',
                [
                    'MODULE_DOWNLOAD_DATA',
                    'MODULE_PRIVACY_SETTINGS',
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_SECURITY_AUDIT',
                    'MODULE_DATA_DELETION',
                ],
            ),
        ],
    },
    'BP_SECURITY_EXIT_AUDIT': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_WORKFLOW_EXIT_SURFACE': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},

    'BP_SECURITY_RECOVERY_VAULT_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'password_reset_completed',
            'two_factor_enabled',
            'two_factor_device_updated',
            'credential_vault_updated',
        ],
        'instruction_templates': [
            'Finish the account-recovery packet only after the password reset is completed, two-factor is enabled, the replacement 2FA device is configured, and the credential vault is updated.',
            'Close the account-recovery route by completing the reset first, restoring 2FA, updating the device, and ending with the credential vault refreshed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; account-recovery security workflows should continue into credential-vault maintenance rather than stopping after device setup.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset, 2FA, device-update, and password-manager chain rather than through a shorter recovery subset.'
        ),
        'paths': [
            (
                'path_reset_twofa_device_vault',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_2FA_SETUP',
                    'MODULE_2FA_DEVICE',
                    'MODULE_PASSWORD_MANAGER',
                ],
            ),
        ],
    },
    'BP_SECURITY_ACCOUNT_RECOVERY': {'alias_of': 'BP_SECURITY_RECOVERY_VAULT_PACKET'},

    'BP_SECURITY_ALIGNMENT_DEVICE_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'access_surface_reviewed',
            'credential_vault_updated',
            'two_factor_enabled',
            'two_factor_device_updated',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the audit-hardening alignment only after access is reviewed, the credential vault is updated, 2FA is enabled, the 2FA device is refreshed, hardening is complete, and the audit is closed.',
            'Close the security alignment route by reviewing credentials first, enabling 2FA, refreshing the device, rotating security, and ending with the audit.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; audit-alignment security workflows should include explicit 2FA-device maintenance before the final audit closeout.'
        ),
        'distinctness_rule': (
            'Reach the target through the full password-manager, 2FA, device-update, rotation, and audit chain rather than through a shorter audit-hardening subset.'
        ),
        'paths': [
            (
                'path_passwordmgr_twofa_device_rotation_audit',
                [
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_2FA_SETUP',
                    'MODULE_2FA_DEVICE',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_AUDIT_HARDEN_ALIGNMENT': {'alias_of': 'BP_SECURITY_ALIGNMENT_DEVICE_PACKET'},

    'BP_NEWCOMER_BANK_MOBILE_ALIGNMENT_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'address_records_aligned',
            'bank_account_active',
            'mobile_service_active',
        ],
        'instruction_templates': [
            'Finish the newcomer bank-alignment packet only after address confirmation is verified, records are aligned, the bank account is active, and mobile service is active.',
            'Close the newcomer onboarding route by securing housing first, verifying and aligning the address, opening the bank account, and ending with mobile service activated.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer bank-alignment workflows should continue through mobile-service activation after the banking step.'
        ),
        'distinctness_rule': (
            'Either verify the address through address proof before alignment, bank opening, and mobile activation, '
            'or verify the address through utility setup before the same aligned bank-and-mobile closure.'
        ),
        'paths': [
            (
                'path_home_proof_change_bank_mobile',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_BANK_OPENING',
                    'MODULE_MOBILE_PLAN_SIGNUP',
                ],
            ),
            (
                'path_home_utility_change_bank_mobile',
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
    'BP_NEWCOMER_BANK_ADDRESS_ALIGNMENT': {'alias_of': 'BP_NEWCOMER_BANK_MOBILE_ALIGNMENT_PACKET'},

    'BP_NEWCOMER_LEASE_FINANCE_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'address_records_aligned',
            'housing_finance_prepared',
            'bank_account_active',
        ],
        'instruction_templates': [
            'Finish the newcomer lease-finance packet only after address confirmation is verified, records are aligned, housing finance is prepared, and the bank account is active.',
            'Close the newcomer settlement route by verifying and aligning the address first, preparing the lease-finance trail, and ending with the bank account opened.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer lease-finance workflows should extend into banking after the address and housing-finance steps.'
        ),
        'distinctness_rule': (
            'Either verify the address through address proof before alignment, lease registration, and bank opening, '
            'or verify the address through utility setup before alignment, lease review, and the same banking closure.'
        ),
        'paths': [
            (
                'path_home_proof_change_register_bank',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_LEASE_CONTRACT_REGISTRATION',
                    'MODULE_BANK_OPENING',
                ],
            ),
            (
                'path_home_utility_change_review_bank',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_LEASE_MANAGEMENT_REVIEW',
                    'MODULE_BANK_OPENING',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_ADDRESS_LEASE_FINANCE_SYNC': {'alias_of': 'BP_NEWCOMER_LEASE_FINANCE_PACKET'},

    'BP_NEWCOMER_SETTLEMENT_BANK_PACKET': {
        'difficulty': 5,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'utilities_active',
            'address_proof_available',
            'mailing_address_current',
            'bank_account_active',
        ],
        'instruction_templates': [
            'Finish the newcomer settlement packet only after housing is secured, utilities are active, address proof is available, the mailing address is current, and the bank account is active.',
            'Close the settlement workflow by securing housing first, activating utilities, collecting address proof, aligning the mailing address, and ending with the bank account opened.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; settlement-foundation newcomer workflows should continue into banking rather than stopping once the address is aligned.'
        ),
        'distinctness_rule': (
            'Reach the target through the full home, utility, proof, address-alignment, and bank-opening chain rather than through a shorter settlement subset.'
        ),
        'paths': [
            (
                'path_home_utility_proof_change_bank',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_BANK_OPENING',
                ],
            ),
        ],
    },
    'BP_NEWCOMER_SETTLEMENT_FOUNDATION': {'alias_of': 'BP_NEWCOMER_SETTLEMENT_BANK_PACKET'},

    'BP_GOV_BILL_VEHICLE_PACKET': {
        'difficulty': 5,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'address_records_aligned',
            'bills_reviewed',
            'vehicle_address_updated',
            'local_vehicle_compliance_verified',
        ],
        'instruction_templates': [
            'Finish the bill-alignment packet only after address confirmation is verified, records are aligned, bills are reviewed, the vehicle address is updated, and local vehicle compliance is verified.',
            'Close the government billing route by securing housing first, aligning the address, reviewing the bills, and ending with vehicle-address compliance updated.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; bill-alignment government workflows should continue into vehicle-address compliance rather than stopping at the billing review.'
        ),
        'distinctness_rule': (
            'Reach the target through the full home, address-proof, address-change, billing-review, and vehicle-address-update chain rather than through a shorter billing subset.'
        ),
        'paths': [
            (
                'path_home_proof_change_bill_vehicle',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_BILLING_REVIEW',
                    'MODULE_VEHICLE_ADDRESS_UPDATE',
                ],
            ),
        ],
    },
    'BP_GOV_BILL_ALIGNMENT': {'alias_of': 'BP_GOV_BILL_VEHICLE_PACKET'},

    'BP_DAILY_RESALE_SUBSCRIPTION_PACKET': {
        'difficulty': 7,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'daily_order_bundle_prepared',
            'order_price_secured',
            'resale_listing_activated',
            'market_listing_active',
            'sale_listing_active',
            'subscription_active',
        ],
        'instruction_templates': [
            'Finish the resale-discount packet only after the daily bundle is prepared, the order price is secured, both resale listing stages are active, and the subscription is active.',
            'Close the daily resale route by preparing the bundle first, securing the price layer, completing both resale listing stages, and ending with the subscription activated.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; daily resale workflows should continue into a recurring-subscription closeout rather than stopping after the two listing stages.'
        ),
        'distinctness_rule': (
            'Reach the target through the full grocery, coupon, listing, sale, and subscription chain rather than through a shorter resale subset.'
        ),
        'paths': [
            (
                'path_grocery_coupon_listing_sale_subscription',
                [
                    'MODULE_GROCERY_RUN',
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_SECOND_HAND_ITEM_LISTING',
                    'MODULE_SECOND_HAND_SALE',
                    'MODULE_FRESH_SUBSCRIPTION',
                ],
            ),
        ],
    },
    'BP_DAILY_RESALE_DISCOUNT_STACK': {'alias_of': 'BP_DAILY_RESALE_SUBSCRIPTION_PACKET'},

    'BP_DAILY_SERVICE_RESALE_SUBSCRIPTION_PACKET': {
        'difficulty': 7,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'service_stack_prepared',
            'order_price_secured',
            'resale_listing_activated',
            'market_listing_active',
            'sale_listing_active',
            'subscription_active',
        ],
        'instruction_templates': [
            'Finish the service-resale packet only after the service stack is prepared, the order price is secured, both resale listing stages are active, and the subscription is active.',
            'Close the daily service-resale route by preparing the service layer first, securing the price layer, completing both listing stages, and ending with the subscription activated.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; service-oriented daily resale workflows should continue into a recurring-subscription closeout rather than stopping after the listing stages.'
        ),
        'distinctness_rule': (
            'Reach the target through the full housekeeping, coupon, listing, sale, and subscription chain rather than through a shorter resale subset.'
        ),
        'paths': [
            (
                'path_service_coupon_listing_sale_subscription',
                [
                    'MODULE_HOUSEKEEPING_BOOKING',
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_SECOND_HAND_ITEM_LISTING',
                    'MODULE_SECOND_HAND_SALE',
                    'MODULE_FRESH_SUBSCRIPTION',
                ],
            ),
        ],
    },
    'BP_DAILY_SERVICE_RESALE_BRIDGE': {'alias_of': 'BP_DAILY_SERVICE_RESALE_SUBSCRIPTION_PACKET'},

    'BP_CAREER_PROFILE_SIGNAL_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'conference_admin_recorded',
            'receipt_archived',
            'deadline_coordination_recorded',
            'career_signal_strengthened',
            'professional_profile_updated',
        ],
        'instruction_templates': [
            'Finish the conference coordination packet only after conference admin is recorded, the receipt is archived, deadlines are coordinated, the career signal is strengthened, and the professional profile is updated.',
            'Close the conference route by recording admin first, archiving the receipt, coordinating the calendar, strengthening the signal, and ending with the public profile updated.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; conference coordination workflows should continue into profile maintenance rather than stopping after email tracking.'
        ),
        'distinctness_rule': (
            'Reach the target through the full conference registration, receipt archive, calendar coordination, email tracking, and profile-update chain rather than through a shorter coordination subset.'
        ),
        'paths': [
            (
                'path_conf_archive_calendar_email_profile',
                [
                    'MODULE_CONFERENCE_REG',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_CALENDAR_AGGREGATION',
                    'MODULE_EMAIL_TRACKING',
                    'MODULE_UPDATE_LINKEDIN',
                ],
            ),
        ],
    },
    'BP_CAREER_CONFERENCE_COORDINATION_CLOSURE': {'alias_of': 'BP_CAREER_PROFILE_SIGNAL_PACKET'},

    'BP_COMPOSITE_INVESTMENT_GROWTH_PACKET': {
        'difficulty': 8,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'investment_account_active',
            'investment_growth_verified',
            'auction_bid_placed',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the investment bootstrap packet only after the investment account is active, growth is verified, the auction bid is placed, and the calendar event is synced.',
            'Close the investment workflow by opening the bank account first, activating the investment path, verifying growth, placing the auction bid, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; investment bootstrap workflows should verify account growth before the auction-and-calendar closeout.'
        ),
        'distinctness_rule': (
            'Reach the target through the full bank-opening, investment activation, growth verification, auction, and calendar-sync chain rather than through a shorter investment subset.'
        ),
        'paths': [
            (
                'path_bank_invest_growth_auction_calendar',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_LIVE_AUCTION',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_INVESTMENT_CALENDAR_BOOTSTRAP': {'alias_of': 'BP_COMPOSITE_INVESTMENT_GROWTH_PACKET'},

    'BP_COMPOSITE_SUPPORT_SYNC_PACKET': {
        'difficulty': 8,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': ['shop_order_exists'],
        'target_state': [
            'password_reset_completed',
            'support_contacted',
            'order_tracking_opened',
            'order_followup_prepared',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the support-access sync packet only after password reset is completed, support is contacted, order tracking is open, order follow-up is prepared, and the calendar event is synced.',
            'Close the support-access route by completing the reset first, contacting support, opening tracking, preparing follow-up, and ending with the calendar synced.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; support-access composite workflows should include a calendar-sync closure after support and tracking follow-up.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset, support, tracking, and calendar-sync chain rather than through a shorter support-access subset.'
        ),
        'paths': [
            (
                'path_reset_service_track_calendar',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_CUSTOMER_SERVICE',
                    'MODULE_TRACK_ORDERS',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_SUPPORT_ACCESS_SYNC': {'alias_of': 'BP_COMPOSITE_SUPPORT_SYNC_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND39_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND39_SPECS[alias]
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
        raise SystemExit('round39 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
