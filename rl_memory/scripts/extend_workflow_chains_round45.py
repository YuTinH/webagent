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

SIG_CONTROL_READY = (
    ('MODULE_SMART_METER', 'MODULE_CAMERA_CHECK', 'MODULE_FIRMWARE_UPDATE', 'MODULE_THERMOSTAT_SCHEDULE'),
    ('MODULE_ENERGY_OPTIMIZE', 'MODULE_CAMERA_CHECK', 'MODULE_FIRMWARE_UPDATE', 'MODULE_THERMOSTAT_SCHEDULE'),
)
SIG_CONTROL_SCHEDULE = (
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_SMART_METER', 'MODULE_THERMOSTAT_SCHEDULE'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_ENERGY_OPTIMIZE', 'MODULE_THERMOSTAT_SCHEDULE'),
)
SIG_MONITOR_READINESS = (
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_FIRMWARE_UPDATE', 'MODULE_CAMERA_CHECK'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_SMART_BULB_SETUP', 'MODULE_CAMERA_CHECK'),
)
SIG_REPAIR_MONITOR = (
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_HOUSE_REPAIR', 'MODULE_CAMERA_CHECK'),
    ('MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP', 'MODULE_HOUSE_REPAIR', 'MODULE_FIRMWARE_UPDATE'),
)
SIG_DEVICE_READINESS = (
    ('MODULE_UTILITY_SETUP', 'MODULE_SMART_BULB_SETUP', 'MODULE_CAMERA_CHECK', 'MODULE_SMART_METER'),
    ('MODULE_UTILITY_SETUP', 'MODULE_FIRMWARE_UPDATE', 'MODULE_CAMERA_CHECK', 'MODULE_SMART_METER'),
)
SIG_SERVICE_MONITOR = (
    ('MODULE_UTILITY_SETUP', 'MODULE_HOUSE_REPAIR', 'MODULE_CAMERA_CHECK', 'MODULE_SMART_BULB_SETUP'),
    ('MODULE_UTILITY_SETUP', 'MODULE_HOUSE_REPAIR', 'MODULE_FIRMWARE_UPDATE', 'MODULE_CAMERA_CHECK'),
)
SIG_ENERGY_CONTROL = (
    ('MODULE_UTILITY_SETUP', 'MODULE_SMART_METER', 'MODULE_THERMOSTAT_SCHEDULE', 'MODULE_CAMERA_CHECK'),
    ('MODULE_UTILITY_SETUP', 'MODULE_ENERGY_OPTIMIZE', 'MODULE_THERMOSTAT_SCHEDULE', 'MODULE_CAMERA_CHECK'),
)
SIG_ENERGY_DEVICE = (
    ('MODULE_UTILITY_SETUP', 'MODULE_SMART_METER', 'MODULE_SMART_BULB_SETUP', 'MODULE_THERMOSTAT_SCHEDULE'),
    ('MODULE_UTILITY_SETUP', 'MODULE_ENERGY_OPTIMIZE', 'MODULE_FIRMWARE_UPDATE', 'MODULE_THERMOSTAT_SCHEDULE'),
)
SIG_REPAIR_CONTROL = (
    ('MODULE_HOUSE_REPAIR', 'MODULE_SMART_METER', 'MODULE_CAMERA_CHECK', 'MODULE_FIRMWARE_UPDATE'),
    ('MODULE_HOUSE_REPAIR', 'MODULE_ENERGY_OPTIMIZE', 'MODULE_CAMERA_CHECK', 'MODULE_FIRMWARE_UPDATE'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round45'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def unique_extend(items: list[str], extra: str) -> list[str]:
    out: list[str] = []
    for item in list(items) + [extra]:
        if item not in out:
            out.append(item)
    return out


def extend_templates(templates: list[str], addition: str) -> list[str]:
    updated: list[str] = []
    for text in templates[:2]:
        base = str(text).strip().rstrip('.')
        updated.append(f'{base}, and finish with {addition}.')
    if not updated:
        updated = [
            f'Finish the home workflow only after {addition}.',
            f'Close the home setup by ending with {addition}.',
        ]
    return updated


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'home':
        return None

    sig = blueprint_signature(bp)
    extra_module = None
    extra_state = None
    addition = None
    note = None

    if sig == SIG_CONTROL_READY:
        extra_module = 'MODULE_EMAIL_CALENDAR'
        extra_state = 'calendar_event_synced'
        addition = 'a synced maintenance calendar'
        note = 'control-readiness home workflows should end with a scheduled follow-up reminder'
    elif sig == SIG_CONTROL_SCHEDULE:
        extra_module = 'MODULE_CAMERA_CHECK'
        extra_state = 'camera_config_verified'
        addition = 'camera verification completed'
        note = 'control-schedule home workflows should verify the monitoring surface after thermostat setup'
    elif sig == SIG_MONITOR_READINESS:
        extra_module = 'MODULE_THERMOSTAT_SCHEDULE'
        extra_state = 'thermostat_schedule_configured'
        addition = 'the thermostat schedule configured'
        note = 'monitor-readiness home workflows should continue into thermostat scheduling after device checks'
    elif sig == SIG_REPAIR_MONITOR:
        extra_module = 'MODULE_EMAIL_CALENDAR'
        extra_state = 'calendar_event_synced'
        addition = 'a synced repair follow-up calendar'
        note = 'repair-monitor home workflows should end with a scheduled follow-up after the repair and monitoring steps'
    elif sig == SIG_DEVICE_READINESS:
        extra_module = 'MODULE_THERMOSTAT_SCHEDULE'
        extra_state = 'thermostat_schedule_configured'
        addition = 'the thermostat schedule configured'
        note = 'device-readiness home workflows should continue into thermostat scheduling after device configuration'
    elif sig == SIG_SERVICE_MONITOR:
        extra_module = 'MODULE_EMAIL_CALENDAR'
        extra_state = 'calendar_event_synced'
        addition = 'a synced service follow-up calendar'
        note = 'service-monitor home workflows should close with a scheduled service follow-up'
    elif sig == SIG_ENERGY_CONTROL:
        extra_module = 'MODULE_EMAIL_CALENDAR'
        extra_state = 'calendar_event_synced'
        addition = 'a synced control follow-up calendar'
        note = 'energy-control home workflows should schedule a follow-up after monitoring and thermostat setup'
    elif sig == SIG_ENERGY_DEVICE:
        extra_module = 'MODULE_EMAIL_CALENDAR'
        extra_state = 'calendar_event_synced'
        addition = 'a synced device follow-up calendar'
        note = 'energy-device balance workflows should end with a scheduled follow-up after the final control step'
    elif sig == SIG_REPAIR_CONTROL:
        extra_module = 'MODULE_EMAIL_CALENDAR'
        extra_state = 'calendar_event_synced'
        addition = 'a synced repair-control follow-up calendar'
        note = 'repair-control home workflows should schedule a follow-up after the final control check'
    else:
        return None

    new_paths = []
    for path in bp.get('paths', []):
        module_ids = [step['module_id'] for step in path.get('steps', [])]
        new_paths.append((f"{path['path_id']}_extended", module_ids + [extra_module]))

    target_state = unique_extend(list(bp.get('target_state', [])), extra_state)
    templates = extend_templates(list(bp.get('instruction_templates', [])), addition)

    return {
        'difficulty': max(int(bp.get('difficulty', 6)), 7),
        'max_steps': max(int(bp.get('max_steps', 45)), 60),
        'max_module_invocations': max(int(bp.get('max_module_invocations', 4)), 5),
        'target_state': target_state,
        'instruction_templates': templates,
        'notes_template': f"Generated from {{blueprint_id}}; {note}.",
        'distinctness_rule': (
            f"Follow one full home-control route to completion and do not stop before {addition}."
        ),
        'paths': new_paths,
    }


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
        raise SystemExit('round45 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
