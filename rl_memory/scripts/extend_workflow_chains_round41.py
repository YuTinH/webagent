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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round41'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND41_SPECS: dict[str, dict[str, Any]] = {
    'BP_CAREER_SIGNAL_FOLLOWUP_PACKET': {
        'difficulty': 6,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'conference_admin_recorded',
            'receipt_archived',
            'deadline_coordination_recorded',
            'career_signal_strengthened',
            'job_application_followup_created',
        ],
        'instruction_templates': [
            'Finish the career follow-up packet only after conference administration is recorded, the receipt is archived, deadline coordination is captured, the career signal is strengthened, and a job follow-up is created.',
            'Close the career workflow by recording the conference admin first, archiving the receipt, coordinating the deadline, strengthening the signal, and ending with a concrete job follow-up action.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; conference-signal career workflows should continue into explicit job follow-up rather than stopping once the signal is strengthened.'
        ),
        'distinctness_rule': (
            'Either take the formal conference-registration route before archival, calendar coordination, signaling, and job follow-up, '
            'or take the conference-admin route before the same archival, coordination, signaling, and follow-up closure.'
        ),
        'paths': [
            (
                'path_conference_registration_followup',
                [
                    'MODULE_CONFERENCE_REGISTRATION',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_CALENDAR_AGGREGATION',
                    'MODULE_EMAIL_TRACKING',
                    'MODULE_JOB_SEARCH',
                ],
            ),
            (
                'path_conference_admin_followup',
                [
                    'MODULE_CONFERENCE_REG',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_CALENDAR_AGGREGATION',
                    'MODULE_UPDATE_LINKEDIN',
                    'MODULE_JOB_SEARCH',
                ],
            ),
        ],
    },
    'BP_CAREER_ADMIN_SIGNAL_DUAL': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ARCHIVE_SIGNAL_STACK': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_CONFERENCE_ADMIN': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_CONFERENCE_ARCHIVE': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_CONFERENCE_DEADLINE_TRACK': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_DEADLINE_SIGNAL_LOOP': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_SIGNAL_CONFERENCE_ALIGNMENT': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_SIGNAL_CONFERENCE_BRIDGE': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_SIGNAL_DEADLINE_ALIGNMENT': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_SIGNAL_RECEIPT': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_WORKFLOW_SIGNAL_ADMIN': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_WORKFLOW_SIGNAL_DEADLINE': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_01_ADMIN_SIGNAL_DUAL': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_02_DEADLINE_SIGNAL_LOOP': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_03_ARCHIVE_SIGNAL_STACK': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_04_ADMIN_SIGNAL_DUAL': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_05_DEADLINE_SIGNAL_LOOP': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_06_ARCHIVE_SIGNAL_STACK': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_07_ADMIN_SIGNAL_DUAL': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_08_DEADLINE_SIGNAL_LOOP': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_09_ARCHIVE_SIGNAL_STACK': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_10_ADMIN_SIGNAL_DUAL': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_11_DEADLINE_SIGNAL_LOOP': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_12_ARCHIVE_SIGNAL_STACK': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_13_ADMIN_SIGNAL_DUAL': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},
    'BP_CAREER_ZTRAIN_14_DEADLINE_SIGNAL_LOOP': {'alias_of': 'BP_CAREER_SIGNAL_FOLLOWUP_PACKET'},

    'BP_COMPOSITE_ACCESS_PORTFOLIO_SECURITY_PACKET': {
        'difficulty': 8,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'password_reset_completed',
            'investment_growth_verified',
            'calendar_event_synced',
            'access_surface_reviewed',
            'credential_vault_updated',
        ],
        'instruction_templates': [
            'Finish the access-portfolio packet only after password reset is completed, investment growth is verified, the calendar event is synced, and the access surface and credential vault are reviewed.',
            'Close the access-portfolio workflow by restoring access first, verifying portfolio growth, syncing the calendar, and ending with credential-surface maintenance.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; access-portfolio composite workflows should continue into credential-surface maintenance after growth verification and calendar sync.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset, portfolio-growth, calendar-sync, and password-manager closure rather than through a shorter access subset.'
        ),
        'paths': [
            (
                'path_reset_growth_calendar_vault',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_EMAIL_CALENDAR',
                    'MODULE_PASSWORD_MANAGER',
                ],
            ),
        ],
    },
    'BP_COMPOSITE_ACCESS_PORTFOLIO_READINESS': {'alias_of': 'BP_COMPOSITE_ACCESS_PORTFOLIO_SECURITY_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND41_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND41_SPECS[alias]
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
        raise SystemExit('round41 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
