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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round38'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND38_SPECS: dict[str, dict[str, Any]] = {
    'BP_DAILY_PRICE_VISIBILITY_PACKET': {
        'difficulty': 6,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'payment_method_available',
            'daily_order_bundle_prepared',
            'order_price_secured',
            'delivery_visibility_confirmed',
            'shop_order_delivered',
        ],
        'instruction_templates': [
            'Finish the daily price-visibility packet only after the payment rail is active, the order bundle is prepared, delivery is visible, the order is delivered, and price protection is secured.',
            'Close the daily shopping route by opening the payment rail first, building the bundle, confirming order arrival, and ending with explicit price protection.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; daily price-bundle workflows should continue through visible order arrival before the price-protection closeout.'
        ),
        'distinctness_rule': (
            'Either activate the daily bundle through groceries before order arrival and price protection, '
            'or use the coupon-backed bundle route before the same arrival-and-protection closure.'
        ),
        'paths': [
            (
                'path_bank_shop_grocery_arrival_protect',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_SHOPPING',
                    'MODULE_GROCERY_RUN',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_PRICE_PROTECTION',
                ],
            ),
            (
                'path_bank_shop_coupon_arrival_protect',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_SHOPPING',
                    'MODULE_COUPON_MANAGEMENT',
                    'MODULE_ORDER_ARRIVAL',
                    'MODULE_PRICE_PROTECTION',
                ],
            ),
        ],
    },
    'BP_DAILY_PRICE_BUNDLE_DUAL': {'alias_of': 'BP_DAILY_PRICE_VISIBILITY_PACKET'},
    'BP_DAILY_ZTRAIN_01_PRICE_BUNDLE_DUAL': {'alias_of': 'BP_DAILY_PRICE_VISIBILITY_PACKET'},
    'BP_DAILY_ZTRAIN_04_PRICE_BUNDLE_DUAL': {'alias_of': 'BP_DAILY_PRICE_VISIBILITY_PACKET'},
    'BP_DAILY_ZTRAIN_07_PRICE_BUNDLE_DUAL': {'alias_of': 'BP_DAILY_PRICE_VISIBILITY_PACKET'},
    'BP_DAILY_ZTRAIN_10_PRICE_BUNDLE_DUAL': {'alias_of': 'BP_DAILY_PRICE_VISIBILITY_PACKET'},
    'BP_DAILY_ZTRAIN_13_PRICE_BUNDLE_DUAL': {'alias_of': 'BP_DAILY_PRICE_VISIBILITY_PACKET'},

    'BP_EDU_CERT_SUBMISSION_PACKET': {
        'difficulty': 6,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': ['education_account_activated'],
        'target_state': [
            'course_enrolled',
            'assignment_resources_provisioned',
            'assignment_submitted',
            'skill_certified',
            'certificate_downloaded',
        ],
        'instruction_templates': [
            'Finish the education credential packet only after the course is enrolled, resources are provisioned, the assignment is submitted, the skill is certified, and the certificate is downloaded.',
            'Close the coursework credential route by enrolling first, preparing the resources, submitting the assignment, certifying the skill, and ending with certificate download.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; resource-cert education workflows should continue through assignment submission before the final certification download.'
        ),
        'distinctness_rule': (
            'Either enroll through the library-resource route before submission, skill certification, and certificate download, '
            'or use the ebook-resource route before the same submission-and-certification closure.'
        ),
        'paths': [
            (
                'path_course_library_submit_certify_download',
                [
                    'MODULE_COURSE_ENROLLMENT',
                    'MODULE_LIBRARY_SERVICE',
                    'MODULE_SUBMIT_ASSIGNMENT',
                    'MODULE_SKILL_CERTIFICATION',
                    'MODULE_DOWNLOAD_CERT',
                ],
            ),
            (
                'path_course_ebook_submit_certify_download',
                [
                    'MODULE_COURSE_ENROLLMENT',
                    'MODULE_BUY_EBOOK',
                    'MODULE_SUBMIT_ASSIGNMENT',
                    'MODULE_SKILL_CERTIFICATION',
                    'MODULE_DOWNLOAD_CERT',
                ],
            ),
        ],
    },
    'BP_EDUCATION_CERT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_CERT_SUBMISSION_PACKET'},
    'BP_EDUCATION_ZTRAIN_02_CERT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_CERT_SUBMISSION_PACKET'},
    'BP_EDUCATION_ZTRAIN_05_CERT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_CERT_SUBMISSION_PACKET'},
    'BP_EDUCATION_ZTRAIN_08_CERT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_CERT_SUBMISSION_PACKET'},
    'BP_EDUCATION_ZTRAIN_11_CERT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_CERT_SUBMISSION_PACKET'},
    'BP_EDUCATION_ZTRAIN_14_CERT_RESOURCE_DUAL': {'alias_of': 'BP_EDU_CERT_SUBMISSION_PACKET'},

    'BP_SECURITY_AUDIT_DEVICE_PACKET': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'access_surface_reviewed',
            'two_factor_enabled',
            'two_factor_device_updated',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the security-audit packet only after the access surface is reviewed, 2FA is enabled, the 2FA device is updated, security hardening is completed, and the audit is closed.',
            'Close the security route by reviewing the access surface first, enabling 2FA, updating the verification device, hardening the credentials, and ending with the audit.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; audit-hardening security workflows should include explicit 2FA-device maintenance before the final audit closeout.'
        ),
        'distinctness_rule': (
            'Either review access through the password-manager route before 2FA setup, device update, rotation, and audit, '
            'or review access through privacy settings before the same 2FA, device, hardening, and audit closure.'
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
            (
                'path_privacy_twofa_device_rotation_audit',
                [
                    'MODULE_PRIVACY_SETTINGS',
                    'MODULE_2FA_SETUP',
                    'MODULE_2FA_DEVICE',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_AUDIT_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_AUDIT_DEVICE_PACKET'},
    'BP_SECURITY_ZTRAIN_03_AUDIT_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_AUDIT_DEVICE_PACKET'},
    'BP_SECURITY_ZTRAIN_06_AUDIT_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_AUDIT_DEVICE_PACKET'},
    'BP_SECURITY_ZTRAIN_09_AUDIT_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_AUDIT_DEVICE_PACKET'},
    'BP_SECURITY_ZTRAIN_12_AUDIT_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_AUDIT_DEVICE_PACKET'},

    'BP_GOV_PERMIT_LIFECYCLE_PACKET': {
        'difficulty': 7,
        'max_steps': 75,
        'max_module_invocations': 6,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'address_records_aligned',
            'permit_application_submitted',
            'parking_permit_active',
            'permit_renewed',
            'local_vehicle_compliance_verified',
        ],
        'instruction_templates': [
            'Finish the permit-lifecycle packet only after address verification is complete, records are aligned, the permit is submitted, the parking permit is active, and the renewal-driven compliance check is finished.',
            'Close the government permit workflow by securing housing first, verifying the address trail, aligning the records, submitting the permit, activating parking permission, and ending with renewal compliance.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; permit-oriented government workflows should carry through submission, activation, and renewal rather than stopping after the first permit action.'
        ),
        'distinctness_rule': (
            'Either verify the civic address through address proof before alignment, permit submission, parking activation, and renewal, '
            'or verify the same civic address through utility setup before the same submission, activation, and renewal closure.'
        ),
        'paths': [
            (
                'path_home_proof_change_submit_activate_renew',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_PERMIT_APP',
                    'MODULE_PARKING_PERMIT_APPLICATION',
                    'MODULE_PERMIT_RENEWAL',
                ],
            ),
            (
                'path_home_utility_change_submit_activate_renew',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_PERMIT_APP',
                    'MODULE_PARKING_PERMIT_APPLICATION',
                    'MODULE_PERMIT_RENEWAL',
                ],
            ),
        ],
    },
    'BP_GOV_ADDRESS_PERMIT_ALIGNMENT': {'alias_of': 'BP_GOV_PERMIT_LIFECYCLE_PACKET'},
    'BP_GOV_PERMIT_ADDRESS_ALIGNMENT': {'alias_of': 'BP_GOV_PERMIT_LIFECYCLE_PACKET'},
    'BP_GOV_PERMIT_SUPPORTING_ALIGNMENT': {'alias_of': 'BP_GOV_PERMIT_LIFECYCLE_PACKET'},
    'BP_GOV_PERMIT_LIFECYCLE': {'alias_of': 'BP_GOV_PERMIT_LIFECYCLE_PACKET'},
    'BP_GOV_PERMIT_VERIFICATION_BRIDGE': {'alias_of': 'BP_GOV_PERMIT_LIFECYCLE_PACKET'},
    'BP_GOV_ADDRESS_COMPLIANCE_PACKET': {
        'difficulty': 7,
        'max_steps': 70,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'address_confirmation_verified',
            'address_records_aligned',
            'parking_permit_active',
            'permit_renewed',
            'local_vehicle_compliance_verified',
        ],
        'instruction_templates': [
            'Finish the government compliance packet only after address verification is complete, address records are aligned, the parking permit is active, and the renewal-driven compliance review is finished.',
            'Close the permit-compliance route by securing housing first, verifying the address trail, aligning the civic record, activating parking permission, and ending with renewal compliance.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; address-compliance government workflows should continue through permit activation and renewal rather than ending after address alignment.'
        ),
        'distinctness_rule': (
            'Either verify the address through address proof before alignment, parking-permit activation, and renewal, '
            'or verify the address through utility setup before the same activation-and-renewal compliance closure.'
        ),
        'paths': [
            (
                'path_home_proof_change_activate_renew',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_ADDRESS_PROOF',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_PARKING_PERMIT_APPLICATION',
                    'MODULE_PERMIT_RENEWAL',
                ],
            ),
            (
                'path_home_utility_change_activate_renew',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ADDRESS_CHANGE',
                    'MODULE_PARKING_PERMIT_APPLICATION',
                    'MODULE_PERMIT_RENEWAL',
                ],
            ),
        ],
    },
    'BP_GOV_PERMIT_ADDRESS_DUAL': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
    'BP_GOV_DRIVING_COMPLIANCE': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
    'BP_GOVERNMENT_ZTRAIN_02_BP_GOV_PERMIT_ADDRESS_DUAL': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
    'BP_GOVERNMENT_ZTRAIN_05_BP_GOV_PERMIT_ADDRESS_DUAL': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
    'BP_GOVERNMENT_ZTRAIN_08_BP_GOV_PERMIT_ADDRESS_DUAL': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
    'BP_GOVERNMENT_ZTRAIN_11_BP_GOV_PERMIT_ADDRESS_DUAL': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
    'BP_GOVERNMENT_ZTRAIN_14_BP_GOV_PERMIT_ADDRESS_DUAL': {'alias_of': 'BP_GOV_ADDRESS_COMPLIANCE_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND38_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND38_SPECS[alias]
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
        raise SystemExit('round38 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
