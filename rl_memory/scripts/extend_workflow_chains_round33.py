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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round33'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND33_SPECS: dict[str, dict[str, Any]] = {
    'BP_HOME_UTILITY_DEVICE_MONITOR_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'utilities_active',
            'energy_control_configured',
            'camera_config_verified',
            'home_device_readiness_confirmed',
            'home_service_monitored',
        ],
        'instruction_templates': [
            'Finish the home-device packet only after utilities are active, energy control is configured, the camera is verified, device readiness is confirmed, and home monitoring is active.',
            'Close the home-readiness workflow by activating utilities, preparing the device path, verifying the camera, and ending with energy control configured and monitoring active.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; device-readiness home tasks should include an energy-control follow-up rather than ending after camera verification.'
        ),
        'distinctness_rule': (
            'Either activate utilities and reach readiness through smart-bulb setup before camera verification and smart-meter control, '
            'or activate utilities and reach readiness through firmware update before the same camera-and-control closure.'
        ),
        'paths': [
            (
                'path_utility_bulb_camera_meter',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_SMART_BULB_SETUP',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_SMART_METER',
                ],
            ),
            (
                'path_utility_firmware_camera_meter',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_SMART_METER',
                ],
            ),
        ],
    },
    'BP_HOME_CAMERA_FIRMWARE_STABILITY': {'alias_of': 'BP_HOME_UTILITY_DEVICE_MONITOR_PACKET'},
    'BP_HOME_DEVICE_READINESS': {'alias_of': 'BP_HOME_UTILITY_DEVICE_MONITOR_PACKET'},
    'BP_HOME_MONITORING_DEVICE_READINESS': {'alias_of': 'BP_HOME_UTILITY_DEVICE_MONITOR_PACKET'},
    'BP_HOME_UTILITY_DEVICE_READY': {'alias_of': 'BP_HOME_UTILITY_DEVICE_MONITOR_PACKET'},
    'BP_HOME_CONTROL_MONITOR_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['utilities_active'],
        'target_state': [
            'energy_control_configured',
            'camera_config_verified',
            'home_device_readiness_confirmed',
            'home_service_monitored',
            'thermostat_schedule_configured',
        ],
        'instruction_templates': [
            'Finish the home-control packet only after energy control is configured, the camera is verified, device readiness is confirmed, monitoring is active, and the thermostat schedule is configured.',
            'Close the control-monitor workflow by configuring energy control, validating the camera path, confirming device readiness, and ending with the thermostat schedule set.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; control-monitor home tasks should include thermostat scheduling after the monitoring steps.'
        ),
        'distinctness_rule': (
            'Either configure control through the smart-meter route before camera verification, firmware readiness, and thermostat scheduling, '
            'or configure control through the energy-optimization route before the same camera, readiness, and scheduling closure.'
        ),
        'paths': [
            (
                'path_meter_camera_firmware_thermostat',
                [
                    'MODULE_SMART_METER',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_THERMOSTAT_SCHEDULE',
                ],
            ),
            (
                'path_optimize_camera_firmware_thermostat',
                [
                    'MODULE_ENERGY_OPTIMIZE',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_THERMOSTAT_SCHEDULE',
                ],
            ),
        ],
    },
    'BP_HOME_CONTROL_MONITOR_ALIGNMENT': {'alias_of': 'BP_HOME_CONTROL_MONITOR_PACKET'},
    'BP_HOME_ENERGY_MONITOR_ALIGNMENT': {'alias_of': 'BP_HOME_CONTROL_MONITOR_PACKET'},
    'BP_HOME_MONITOR_READINESS_ALIGNMENT': {'alias_of': 'BP_HOME_CONTROL_MONITOR_PACKET'},
    'BP_HOME_WORKFLOW_CONTROL_READINESS': {'alias_of': 'BP_HOME_CONTROL_MONITOR_PACKET', 'initial_world_state': ['lease_active', 'utilities_active']},
    'BP_HOME_DEVICE_ENERGY_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'utilities_active',
            'energy_control_configured',
            'home_device_readiness_confirmed',
            'thermostat_schedule_configured',
        ],
        'instruction_templates': [
            'Finish the home energy-device packet only after utilities are active, energy control is configured, device readiness is confirmed, and the thermostat schedule is configured.',
            'Close the energy-device workflow by activating utilities, preparing the control path, confirming device readiness, and ending with thermostat scheduling complete.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; energy-device home tasks should include thermostat scheduling as a concrete follow-up to control and readiness.'
        ),
        'distinctness_rule': (
            'Either activate utilities and reach control through the smart-meter route before bulb readiness and thermostat scheduling, '
            'or activate utilities and reach control through the optimization route before firmware readiness and the same scheduling closure.'
        ),
        'paths': [
            (
                'path_utility_meter_bulb_thermostat',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_SMART_METER',
                    'MODULE_SMART_BULB_SETUP',
                    'MODULE_THERMOSTAT_SCHEDULE',
                ],
            ),
            (
                'path_utility_optimize_firmware_thermostat',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ENERGY_OPTIMIZE',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_THERMOSTAT_SCHEDULE',
                ],
            ),
        ],
    },
    'BP_HOME_DEVICE_ENERGY_BALANCE_LOOP': {'alias_of': 'BP_HOME_DEVICE_ENERGY_PACKET'},
    'BP_HOME_ENERGY_DEVICE_BALANCE': {'alias_of': 'BP_HOME_DEVICE_ENERGY_PACKET'},
    'BP_HOME_ENERGY_AUTOMATION_PACKET': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'utilities_active',
            'energy_control_configured',
            'thermostat_schedule_configured',
            'home_service_monitored',
        ],
        'instruction_templates': [
            'Finish the home automation packet only after utilities are active, energy control is configured, the thermostat schedule is configured, and home monitoring is active.',
            'Close the home-automation workflow by activating utilities, configuring energy control, setting the thermostat schedule, and ending with monitoring confirmed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; energy-automation home tasks should include a monitoring confirmation after scheduling.'
        ),
        'distinctness_rule': (
            'Either activate utilities and configure control through the smart-meter route before thermostat scheduling and monitoring, '
            'or activate utilities and configure control through the optimization route before the same scheduling-and-monitoring closure.'
        ),
        'paths': [
            (
                'path_utility_meter_thermostat_camera',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_SMART_METER',
                    'MODULE_THERMOSTAT_SCHEDULE',
                    'MODULE_CAMERA_CHECK',
                ],
            ),
            (
                'path_utility_optimize_thermostat_camera',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_ENERGY_OPTIMIZE',
                    'MODULE_THERMOSTAT_SCHEDULE',
                    'MODULE_CAMERA_CHECK',
                ],
            ),
        ],
    },
    'BP_HOME_ENERGY_AUTOMATION': {'alias_of': 'BP_HOME_ENERGY_AUTOMATION_PACKET'},
    'BP_HOME_ENERGY_CONTROL': {'alias_of': 'BP_HOME_ENERGY_AUTOMATION_PACKET'},
    'BP_HOME_REPAIR_MONITOR_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'utilities_active',
            'home_repair_requested',
            'camera_config_verified',
            'home_device_readiness_confirmed',
            'home_service_monitored',
        ],
        'instruction_templates': [
            'Finish the repair-monitor packet only after utilities are active, the home repair is requested, the camera is verified, device readiness is confirmed, and home monitoring is active.',
            'Close the repair-monitor workflow by activating utilities, requesting the repair, validating the camera path, and ending with device readiness and monitoring confirmed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; repair-monitor home tasks should include utility activation before the monitoring closure.'
        ),
        'distinctness_rule': (
            'Either activate utilities and request the repair before camera verification and smart-bulb readiness, '
            'or activate utilities and request the repair before firmware readiness and the same monitoring closure.'
        ),
        'paths': [
            (
                'path_utility_repair_camera_bulb',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_HOUSE_REPAIR',
                    'MODULE_CAMERA_CHECK',
                    'MODULE_SMART_BULB_SETUP',
                ],
            ),
            (
                'path_utility_repair_firmware_camera',
                [
                    'MODULE_UTILITY_SETUP',
                    'MODULE_HOUSE_REPAIR',
                    'MODULE_FIRMWARE_UPDATE',
                    'MODULE_CAMERA_CHECK',
                ],
            ),
        ],
    },
    'BP_HOME_REPAIR_MONITORING_LOOP': {'alias_of': 'BP_HOME_REPAIR_MONITOR_PACKET'},
    'BP_HOME_REPAIR_MONITOR_ALIGNMENT': {'alias_of': 'BP_HOME_REPAIR_MONITOR_PACKET'},
    'BP_HOME_SERVICE_MONITORING': {'alias_of': 'BP_HOME_REPAIR_MONITOR_PACKET'},
    'BP_HOME_WORKFLOW_REPAIR_MONITOR': {'alias_of': 'BP_HOME_REPAIR_MONITOR_PACKET'},
    'BP_HOME_FIND_REPAIR_MONITOR_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'lease_active',
            'utilities_active',
            'home_repair_requested',
            'home_service_monitored',
        ],
        'instruction_templates': [
            'Finish the find-and-repair packet only after housing is secured, utilities are active, the home repair is requested, and home monitoring is active.',
            'Close the housing-repair workflow by securing the home first, activating utilities, requesting the repair, and ending with monitoring confirmed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; newcomer-like home repair tasks should include housing and utility setup before the repair-monitor closure.'
        ),
        'distinctness_rule': (
            'Either secure housing, activate utilities, request repair, and then validate monitoring through the camera path, '
            'or secure housing, activate utilities, request repair, and then reach the same monitoring closure through firmware update.'
        ),
        'paths': [
            (
                'path_find_utility_repair_camera',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_HOUSE_REPAIR',
                    'MODULE_CAMERA_CHECK',
                ],
            ),
            (
                'path_find_utility_repair_firmware',
                [
                    'MODULE_FIND_HOME',
                    'MODULE_UTILITY_SETUP',
                    'MODULE_HOUSE_REPAIR',
                    'MODULE_FIRMWARE_UPDATE',
                ],
            ),
        ],
    },
    'BP_HOME_REPAIR_MONITOR_DUAL': {'alias_of': 'BP_HOME_FIND_REPAIR_MONITOR_PACKET'},
    'BP_HOME_ZTRAIN_03_REPAIR_MONITOR_DUAL': {'alias_of': 'BP_HOME_FIND_REPAIR_MONITOR_PACKET'},
    'BP_HOME_ZTRAIN_06_REPAIR_MONITOR_DUAL': {'alias_of': 'BP_HOME_FIND_REPAIR_MONITOR_PACKET'},
    'BP_HOME_ZTRAIN_09_REPAIR_MONITOR_DUAL': {'alias_of': 'BP_HOME_FIND_REPAIR_MONITOR_PACKET'},
    'BP_HOME_ZTRAIN_12_REPAIR_MONITOR_DUAL': {'alias_of': 'BP_HOME_FIND_REPAIR_MONITOR_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND33_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND33_SPECS[alias]
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
        raise SystemExit('round33 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
