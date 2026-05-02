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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round29'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND29_SPECS: dict[str, dict[str, Any]] = {
    'BP_SECURITY_HARDEN_AUDIT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'access_surface_reviewed',
            'two_factor_enabled',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the security-hardening packet only after the access surface is reviewed, two-factor authentication is enabled, hardening is completed, and the security audit is done.',
            'Close the account-security workflow by reviewing the access surface, enabling two-factor protection, rotating the security posture, and ending with an audit complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; security-hardening tasks should require a full surface-review plus 2FA plus audit packet rather than a 3-step shortcut.'
        ),
        'distinctness_rule': (
            'Either start from privacy settings before 2FA, rotation, and audit, '
            'or start from the password-manager review before the same 2FA, rotation, and audit closure.'
        ),
        'paths': [
            (
                'path_privacy_twofa_rotation_audit',
                [
                    'MODULE_PRIVACY_SETTINGS',
                    'MODULE_2FA_SETUP',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
            (
                'path_password_manager_twofa_rotation_audit',
                [
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_2FA_SETUP',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_ACCESS_HARDENING': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_AUDIT_SURFACE_BRIDGE': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_HARDENING_AUDIT': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_HARDENING_VERIFICATION': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_ROTATION_READINESS': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_SURFACE_TWOFA_ALIGNMENT': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_TWOFA_HARDENING_BRIDGE': {'alias_of': 'BP_SECURITY_HARDEN_AUDIT_PACKET'},
    'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET': {
        'difficulty': 6,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'account_data_exported',
            'access_surface_reviewed',
            'account_exit_prepared',
            'privacy_settings_updated',
            'two_factor_enabled',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the exit-hardening packet only after account data is exported, the access surface is reviewed, exit prep is complete, privacy settings are updated, two-factor is enabled, hardening is complete, and the security audit is done.',
            'Close the account-exit security workflow by exporting data first, reviewing privacy settings, enabling two-factor, rotating security, and ending with an audit complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; exit-hardening workflows should carry through export, privacy review, 2FA hardening, and audit instead of terminating after a shallow surface action.'
        ),
        'distinctness_rule': (
            'Reach the target state through the full export, privacy, two-factor, rotation, and audit chain rather than through a shorter subset route.'
        ),
        'paths': [
            (
                'path_export_privacy_twofa_rotation_audit',
                [
                    'MODULE_DOWNLOAD_DATA',
                    'MODULE_PRIVACY_SETTINGS',
                    'MODULE_2FA_SETUP',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_EXIT_HARDENING_BRIDGE': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_SURFACE_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_WORKFLOW_SURFACE_HARDEN': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_ZTRAIN_01_SURFACE_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_ZTRAIN_04_SURFACE_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_ZTRAIN_07_SURFACE_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_ZTRAIN_10_SURFACE_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_ZTRAIN_13_SURFACE_HARDEN_DUAL': {'alias_of': 'BP_SECURITY_SURFACE_EXIT_HARDEN_PACKET'},
    'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'account_exit_prepared',
            'access_surface_reviewed',
            'credential_vault_updated',
            'deletion_request_submitted',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the account-exit deletion packet only after exit prep is complete, the access surface is reviewed, the credential vault is updated, the deletion request is submitted, and the security audit is done.',
            'Close the exit-hygiene workflow by preparing account exit, reviewing the access surface, updating credential handling, submitting deletion, and ending with an audit complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; deletion-oriented security workflows should include review and audit steps instead of ending immediately after deletion submission.'
        ),
        'distinctness_rule': (
            'Either prepare exit through account-data export before password-manager review, deletion, and audit, '
            'or review privacy settings first before the same credential, deletion, and audit closure.'
        ),
        'paths': [
            (
                'path_export_password_deletion_audit',
                [
                    'MODULE_DOWNLOAD_DATA',
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_DATA_DELETION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
            (
                'path_privacy_password_deletion_audit',
                [
                    'MODULE_PRIVACY_SETTINGS',
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_DATA_DELETION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_DATA_EXIT_HYGIENE': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_EXIT_DELETION_ALIGNMENT': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_EXIT_DELETION_DUAL': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_EXIT_PRIVACY_ALIGNMENT': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_EXPORT_DELETE_SEQUENCE': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_ZTRAIN_02_EXIT_DELETION_DUAL': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_ZTRAIN_05_EXIT_DELETION_DUAL': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_ZTRAIN_08_EXIT_DELETION_DUAL': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_ZTRAIN_11_EXIT_DELETION_DUAL': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_ZTRAIN_14_EXIT_DELETION_DUAL': {'alias_of': 'BP_SECURITY_EXIT_DELETION_AUDIT_PACKET'},
    'BP_SECURITY_DEVICE_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'two_factor_enabled',
            'two_factor_device_updated',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the device-hardening workflow only after two-factor is enabled, the two-factor device is updated, hardening is complete, and the security audit is done.',
            'Close the device-security packet by enabling two-factor, updating the second-factor device, hardening account security, and ending with an audit complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; device-hardening tasks should end in a verified audit state rather than stopping after the device update.'
        ),
        'distinctness_rule': (
            'Either start directly with two-factor setup before device update, rotation, and audit, '
            'or begin with password-manager review before the same two-factor-device-and-audit closure.'
        ),
        'paths': [
            (
                'path_twofa_device_rotation_audit',
                [
                    'MODULE_2FA_SETUP',
                    'MODULE_2FA_DEVICE',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
            (
                'path_password_twofa_device_audit',
                [
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_2FA_SETUP',
                    'MODULE_2FA_DEVICE',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_DEVICE_HARDEN': {'alias_of': 'BP_SECURITY_DEVICE_PACKET'},
    'BP_SECURITY_RESET_AUDIT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'password_reset_completed',
            'two_factor_enabled',
            'security_hardening_completed',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the password-reset recovery workflow only after the reset is completed, two-factor is enabled, hardening is complete, and the security audit is done.',
            'Close the account-recovery security packet by requesting the reset, completing it, enabling two-factor, hardening the account, and ending with an audit complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; reset workflows should continue through post-reset hardening and audit instead of stopping at reset completion.'
        ),
        'distinctness_rule': (
            'Reach the target state through the full reset request, reset completion, two-factor, rotation, and audit chain rather than through a shorter subset route.'
        ),
        'paths': [
            (
                'path_reset_completion_twofa_rotation_audit',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_2FA_SETUP',
                    'MODULE_SECURITY_ROTATION',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_RESET_AUDIT': {'alias_of': 'BP_SECURITY_RESET_AUDIT_PACKET'},
    'BP_SECURITY_EXIT_SURFACE_AUDIT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'account_data_exported',
            'account_exit_prepared',
            'access_surface_reviewed',
            'privacy_settings_updated',
            'credential_vault_updated',
            'security_audit_completed',
        ],
        'instruction_templates': [
            'Finish the exit-surface audit workflow only after account data is exported, exit prep is complete, the access surface is reviewed, privacy settings are updated, the credential vault is updated, and the security audit is done.',
            'Close the account-exit review packet by exporting data, reviewing privacy settings, updating credential handling, and ending with an audit complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; exit-review workflows should require export, privacy review, credential review, and audit rather than a minimal 3-step surface pass.'
        ),
        'distinctness_rule': (
            'Reach the target state through the full export, privacy review, password-manager review, and audit chain rather than through a shorter subset route.'
        ),
        'paths': [
            (
                'path_export_privacy_password_audit',
                [
                    'MODULE_DOWNLOAD_DATA',
                    'MODULE_PRIVACY_SETTINGS',
                    'MODULE_PASSWORD_MANAGER',
                    'MODULE_SECURITY_AUDIT',
                ],
            ),
        ],
    },
    'BP_SECURITY_EXIT_AUDIT': {'alias_of': 'BP_SECURITY_EXIT_SURFACE_AUDIT_PACKET'},
    'BP_SECURITY_WORKFLOW_EXIT_SURFACE': {'alias_of': 'BP_SECURITY_EXIT_SURFACE_AUDIT_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND29_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND29_SPECS[alias]
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
                kind='alternative',
            )
            for path_id, module_ids in spec['paths']
        ]

        issues = generator.validate_blueprint(bp, modules_by_id, requirements)
        if issues:
            validation_issues.extend(issues)
        patched_blueprints[blueprint_id] = copy.deepcopy(bp)

    if validation_issues:
        raise SystemExit('round29 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
