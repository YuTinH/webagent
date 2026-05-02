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

SIG_ADDRESS_BILL = (
    ('MODULE_FIND_HOME', 'MODULE_ADDRESS_PROOF', 'MODULE_ADDRESS_CHANGE', 'MODULE_BILLING_REVIEW'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_ADDRESS_CHANGE', 'MODULE_BILLING_REVIEW'),
)
SIG_LOCAL_VEHICLE = (
    ('MODULE_FIND_HOME', 'MODULE_ADDRESS_PROOF', 'MODULE_PARKING_PERMIT_APPLICATION', 'MODULE_PERMIT_RENEWAL'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_VEHICLE_ADDRESS_UPDATE', 'MODULE_PARKING_PERMIT_APPLICATION'),
)
SIG_ADDRESS_PERMIT = (
    ('MODULE_FIND_HOME', 'MODULE_ADDRESS_PROOF', 'MODULE_ADDRESS_CHANGE', 'MODULE_PERMIT_APP'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_ADDRESS_CHANGE', 'MODULE_PERMIT_APP'),
)
SIG_MAILING_PERMIT = (
    ('MODULE_FIND_HOME', 'MODULE_ADDRESS_PROOF', 'MODULE_ADDRESS_CHANGE', 'MODULE_PERMIT_APP'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_PERMIT_APP', 'MODULE_ADDRESS_CHANGE'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round54'.encode('utf-8')).hexdigest()
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
    if bp.get('theme') != 'government':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_ADDRESS_BILL:
        target_state = unique_extend(list(bp.get('target_state', [])), ['permit_application_submitted'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the civic records workflow only after address records are aligned, billing is reviewed, and the permit application is submitted for the new residence.',
                'Close the civic-address route by securing the residence evidence first, aligning records, reviewing billing, and ending with a submitted permit application.',
            ],
            'notes_template': 'Generated from {blueprint_id}; civic record workflows should continue into permit submission after address and billing verification.',
            'distinctness_rule': 'Follow one full civic-record route to completion and do not stop before address alignment, billing review, and permit submission are all completed.',
            'paths': [
                (
                    'path_home_proof_change_billing_permit',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_ADDRESS_PROOF',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_BILLING_REVIEW',
                        'MODULE_PERMIT_APP',
                    ],
                ),
                (
                    'path_home_utility_change_billing_permit',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_UTILITY_SETUP',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_BILLING_REVIEW',
                        'MODULE_PERMIT_APP',
                    ],
                ),
            ],
        }

    if sig == SIG_LOCAL_VEHICLE:
        target_state = unique_extend(list(bp.get('target_state', [])), ['permit_renewed'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the civic vehicle workflow only after address confirmation is verified, the permit is activated, and the local vehicle record is brought through final compliance renewal.',
                'Close the local vehicle route by confirming the address first, activating the permit path, and ending with renewed local compliance.',
            ],
            'notes_template': 'Generated from {blueprint_id}; local vehicle workflows should continue through the final permit-renewal checkpoint.',
            'distinctness_rule': 'Follow one full local-vehicle route to completion and do not stop before permit activation and final renewal-based compliance are completed.',
            'paths': [
                (
                    'path_home_proof_change_permit_renewal',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_ADDRESS_PROOF',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_PARKING_PERMIT_APPLICATION',
                        'MODULE_PERMIT_RENEWAL',
                    ],
                ),
                (
                    'path_home_utility_vehicle_permit_renewal',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_UTILITY_SETUP',
                        'MODULE_VEHICLE_ADDRESS_UPDATE',
                        'MODULE_PARKING_PERMIT_APPLICATION',
                        'MODULE_PERMIT_RENEWAL',
                    ],
                ),
            ],
        }

    if sig == SIG_ADDRESS_PERMIT:
        target_state = unique_extend(list(bp.get('target_state', [])), ['bills_reviewed'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the civic address packet only after address records are aligned, the permit is submitted, and the residence billing review is completed.',
                'Close the government-address route by securing home evidence first, aligning the address records, submitting the permit, and ending with a completed billing review.',
            ],
            'notes_template': 'Generated from {blueprint_id}; address-permit workflows should not stop at permit submission and should continue into billing verification.',
            'distinctness_rule': 'Follow one full address-permit route to completion and do not stop before address alignment, permit submission, and billing review are all completed.',
            'paths': [
                (
                    'path_home_proof_change_permit_billing',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_ADDRESS_PROOF',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_PERMIT_APP',
                        'MODULE_BILLING_REVIEW',
                    ],
                ),
                (
                    'path_home_utility_change_permit_billing',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_UTILITY_SETUP',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_PERMIT_APP',
                        'MODULE_BILLING_REVIEW',
                    ],
                ),
            ],
        }

    if sig == SIG_MAILING_PERMIT:
        target_state = unique_extend(list(bp.get('target_state', [])), ['bills_reviewed'])
        return {
            'difficulty': 8,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': target_state,
            'instruction_templates': [
                'Finish the mailing-and-permit workflow only after the mailing address is current, the permit is submitted, and the residence billing review is completed.',
                'Close the mailing-permit route by preparing the residence evidence first, completing permit and address updates in full, and ending with a completed billing review.',
            ],
            'notes_template': 'Generated from {blueprint_id}; mailing-permit workflows should continue into billing verification after address and permit work are completed.',
            'distinctness_rule': 'Follow one full mailing-permit route to completion and do not stop before the mailing address is current, the permit is submitted, and billing review is completed.',
            'paths': [
                (
                    'path_home_proof_change_permit_billing_tail',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_ADDRESS_PROOF',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_PERMIT_APP',
                        'MODULE_BILLING_REVIEW',
                    ],
                ),
                (
                    'path_home_utility_permit_change_billing_tail',
                    [
                        'MODULE_FIND_HOME',
                        'MODULE_UTILITY_SETUP',
                        'MODULE_PERMIT_APP',
                        'MODULE_ADDRESS_CHANGE',
                        'MODULE_BILLING_REVIEW',
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
        raise SystemExit('round54 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
