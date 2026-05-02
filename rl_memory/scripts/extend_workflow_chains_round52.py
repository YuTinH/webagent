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

SIG_ACCESS_HARDENING = (
    ('MODULE_PRIVACY_SETTINGS', 'MODULE_2FA_SETUP', 'MODULE_SECURITY_ROTATION', 'MODULE_SECURITY_AUDIT'),
    ('MODULE_PASSWORD_MANAGER', 'MODULE_2FA_SETUP', 'MODULE_SECURITY_ROTATION', 'MODULE_SECURITY_AUDIT'),
)
SIG_DATA_EXIT = (
    ('MODULE_DOWNLOAD_DATA', 'MODULE_PASSWORD_MANAGER', 'MODULE_DATA_DELETION', 'MODULE_SECURITY_AUDIT'),
    ('MODULE_PRIVACY_SETTINGS', 'MODULE_PASSWORD_MANAGER', 'MODULE_DATA_DELETION', 'MODULE_SECURITY_AUDIT'),
)
SIG_DEVICE_HARDEN = (
    ('MODULE_2FA_SETUP', 'MODULE_2FA_DEVICE', 'MODULE_SECURITY_ROTATION', 'MODULE_SECURITY_AUDIT'),
    ('MODULE_PASSWORD_MANAGER', 'MODULE_2FA_SETUP', 'MODULE_2FA_DEVICE', 'MODULE_SECURITY_AUDIT'),
)


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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round52'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def unique_extend(items: list[str], extras: list[str]) -> list[str]:
    out: list[str] = []
    for item in list(items) + list(extras):
        if item not in out:
            out.append(item)
    return out


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'security':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_ACCESS_HARDENING:
        target_state = unique_extend(
            list(bp.get('target_state', [])),
            ['two_factor_device_updated'],
        )
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the security-hardening workflow only after access surfaces are reviewed, two-factor is enabled, secrets are rotated, the second-factor device is updated, and the final security audit is completed.',
                'Close the security-hardening route by reviewing the account surface first, enabling two-factor, rotating secrets, updating the second-factor device, and ending with a completed audit.',
            ],
            'notes_template': 'Generated from {blueprint_id}; security-hardening workflows should continue through explicit second-factor device remediation before the final audit.',
            'distinctness_rule': 'Follow one full hardening route to completion and do not stop before the second-factor device is updated and the final audit is completed.',
            'paths': [
                (
                    'path_privacy_twofa_rotation_device_audit',
                    [
                        'MODULE_PRIVACY_SETTINGS',
                        'MODULE_2FA_SETUP',
                        'MODULE_SECURITY_ROTATION',
                        'MODULE_2FA_DEVICE',
                        'MODULE_SECURITY_AUDIT',
                    ],
                ),
                (
                    'path_password_twofa_rotation_device_audit',
                    [
                        'MODULE_PASSWORD_MANAGER',
                        'MODULE_2FA_SETUP',
                        'MODULE_SECURITY_ROTATION',
                        'MODULE_2FA_DEVICE',
                        'MODULE_SECURITY_AUDIT',
                    ],
                ),
            ],
        }

    if sig == SIG_DATA_EXIT:
        target_state = unique_extend(
            list(bp.get('target_state', [])),
            ['calendar_event_synced'],
        )
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the account-exit security workflow only after export-or-privacy prep is completed, the password vault is updated, deletion is requested, the security audit is completed, and the follow-up is synced to the calendar.',
                'Close the data-exit route by completing the account-exit prep first, updating the credential vault, submitting deletion, completing the audit, and ending with a synced follow-up reminder.',
            ],
            'notes_template': 'Generated from {blueprint_id}; account-exit security workflows should carry a concrete follow-up reminder after deletion and audit closure.',
            'distinctness_rule': 'Follow one full account-exit route to completion and do not stop before deletion, audit closure, and the follow-up reminder are all completed.',
            'paths': [
                (
                    'path_export_password_delete_audit_calendar',
                    [
                        'MODULE_DOWNLOAD_DATA',
                        'MODULE_PASSWORD_MANAGER',
                        'MODULE_DATA_DELETION',
                        'MODULE_SECURITY_AUDIT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_privacy_password_delete_audit_calendar',
                    [
                        'MODULE_PRIVACY_SETTINGS',
                        'MODULE_PASSWORD_MANAGER',
                        'MODULE_DATA_DELETION',
                        'MODULE_SECURITY_AUDIT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_DEVICE_HARDEN:
        target_state = list(bp.get('target_state', []))
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the device-hardening workflow only after the account surface is reviewed, two-factor is enabled, the second-factor device is updated, secrets are rotated, and the final security audit is completed.',
                'Close the device-security route by reviewing the account surface first, enabling two-factor, updating the second-factor device, rotating secrets, and ending with a completed audit.',
            ],
            'notes_template': 'Generated from {blueprint_id}; device-hardening workflows should include both surface review and device remediation before the final audit.',
            'distinctness_rule': 'Follow one full device-hardening route to completion and do not stop before device remediation, rotation, and the final audit are all completed.',
            'paths': [
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
                (
                    'path_password_twofa_device_rotation_audit',
                    [
                        'MODULE_PASSWORD_MANAGER',
                        'MODULE_2FA_SETUP',
                        'MODULE_2FA_DEVICE',
                        'MODULE_SECURITY_ROTATION',
                        'MODULE_SECURITY_AUDIT',
                    ],
                ),
            ],
        }

    return None


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
        spec = spec_for_blueprint(bp)
        if spec is None:
            continue

        blueprint_id = bp['blueprint_id']
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
        raise SystemExit('round52 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
                'patched_blueprints': sorted(patched_blueprints.keys()),
                'patched_blueprint_count': len(patched_blueprints),
                'refreshed_counts': refreshed_counts,
            },
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
