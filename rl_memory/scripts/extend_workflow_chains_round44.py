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

SIG_VACCINE_CONTINUITY = (
    ('MODULE_INSURANCE_POLICY', 'MODULE_DOCTOR_APPT', 'MODULE_PRESCRIPTION_REFILL', 'MODULE_VACCINE_MGMT'),
    ('MODULE_HEALTH_PLAN_ACTIVATION', 'MODULE_DOCTOR_APPT', 'MODULE_PRESCRIPTION_REFILL', 'MODULE_VACCINE_MGMT'),
)
SIG_CLAIM_CONTINUITY = (
    ('MODULE_INSURANCE_POLICY', 'MODULE_DOCTOR_APPT', 'MODULE_PRESCRIPTION_REFILL', 'MODULE_MEDICAL_CLAIM'),
    ('MODULE_HEALTH_PLAN_ACTIVATION', 'MODULE_DOCTOR_APPT', 'MODULE_PRESCRIPTION_REFILL', 'MODULE_MEDICAL_CLAIM'),
)
SIG_VACCINE_CLAIM = (
    ('MODULE_INSURANCE_POLICY', 'MODULE_DOCTOR_APPT', 'MODULE_VACCINE_MGMT', 'MODULE_MEDICAL_CLAIM'),
    ('MODULE_HEALTH_PLAN_ACTIVATION', 'MODULE_DOCTOR_APPT', 'MODULE_VACCINE_MGMT', 'MODULE_MEDICAL_CLAIM'),
)
SIG_CLAIM_VACCINE = (
    ('MODULE_INSURANCE_POLICY', 'MODULE_DOCTOR_APPT', 'MODULE_MEDICAL_CLAIM', 'MODULE_VACCINE_MGMT'),
    ('MODULE_HEALTH_PLAN_ACTIVATION', 'MODULE_DOCTOR_APPT', 'MODULE_MEDICAL_CLAIM', 'MODULE_VACCINE_MGMT'),
)
SIG_ILLNESS_REFILL = (
    ('MODULE_INSURANCE_POLICY', 'MODULE_DOCTOR_APPT', 'MODULE_ILLNESS_REPORTING', 'MODULE_PRESCRIPTION_REFILL'),
    ('MODULE_HEALTH_PLAN_ACTIVATION', 'MODULE_DOCTOR_APPT', 'MODULE_ILLNESS_REPORTING', 'MODULE_PRESCRIPTION_REFILL'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round44'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'health':
        return None
    sig = blueprint_signature(bp)

    if sig == SIG_VACCINE_CONTINUITY:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'initial_world_state': [],
            'target_state': [
                'coverage_path_active',
                'medical_appointment_booked',
                'care_continuity_established',
                'vaccination_record_updated',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the health continuity packet only after coverage is active, the appointment is booked, continuity is established, the vaccination record is updated, and the follow-up calendar is synced.',
                'Close the health continuity workflow by activating coverage first, booking the appointment, completing continuity and vaccine management, and ending with a synced follow-up calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; continuity-and-vaccine health workflows should end with an explicit follow-up scheduling step.'
            ),
            'distinctness_rule': (
                'Either start from the insurance-policy route before appointment, refill, vaccine management, and calendar sync, '
                'or start from health-plan activation before the same appointment, refill, vaccine, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_policy_appt_refill_vaccine_calendar',
                    [
                        'MODULE_INSURANCE_POLICY',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_PRESCRIPTION_REFILL',
                        'MODULE_VACCINE_MGMT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_plan_appt_refill_vaccine_calendar',
                    [
                        'MODULE_HEALTH_PLAN_ACTIVATION',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_PRESCRIPTION_REFILL',
                        'MODULE_VACCINE_MGMT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_CLAIM_CONTINUITY:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'initial_world_state': [],
            'target_state': [
                'coverage_path_active',
                'medical_appointment_booked',
                'care_continuity_established',
                'medical_claim_submitted',
                'receipt_archived',
            ],
            'instruction_templates': [
                'Finish the health claim packet only after coverage is active, the appointment is booked, continuity is established, the medical claim is submitted, and the claim record is archived.',
                'Close the health claim workflow by activating coverage first, booking the appointment, completing continuity, submitting the claim, and ending with archival.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; claim-oriented health workflows should archive the claim proof after submission.'
            ),
            'distinctness_rule': (
                'Either start from the insurance-policy route before appointment, refill, claim, and archival, '
                'or start from health-plan activation before the same appointment, refill, claim, and archival closure.'
            ),
            'paths': [
                (
                    'path_policy_appt_refill_claim_archive',
                    [
                        'MODULE_INSURANCE_POLICY',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_PRESCRIPTION_REFILL',
                        'MODULE_MEDICAL_CLAIM',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
                (
                    'path_plan_appt_refill_claim_archive',
                    [
                        'MODULE_HEALTH_PLAN_ACTIVATION',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_PRESCRIPTION_REFILL',
                        'MODULE_MEDICAL_CLAIM',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
            ],
        }

    if sig == SIG_VACCINE_CLAIM:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'initial_world_state': [],
            'target_state': [
                'coverage_path_active',
                'medical_appointment_booked',
                'vaccination_record_updated',
                'medical_claim_submitted',
                'receipt_archived',
            ],
            'instruction_templates': [
                'Finish the vaccine-claim health packet only after coverage is active, the appointment is booked, the vaccination record is updated, the medical claim is submitted, and the record is archived.',
                'Close the vaccine-claim workflow by activating coverage first, completing the appointment and vaccine route, submitting the claim, and ending with archival.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; vaccine-claim health workflows should archive the claim bundle after submission.'
            ),
            'distinctness_rule': (
                'Either start from the insurance-policy route before appointment, vaccine management, claim submission, and archival, '
                'or start from health-plan activation before the same appointment, vaccine, claim, and archival closure.'
            ),
            'paths': [
                (
                    'path_policy_appt_vaccine_claim_archive',
                    [
                        'MODULE_INSURANCE_POLICY',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_VACCINE_MGMT',
                        'MODULE_MEDICAL_CLAIM',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
                (
                    'path_plan_appt_vaccine_claim_archive',
                    [
                        'MODULE_HEALTH_PLAN_ACTIVATION',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_VACCINE_MGMT',
                        'MODULE_MEDICAL_CLAIM',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
            ],
        }

    if sig == SIG_CLAIM_VACCINE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'initial_world_state': [],
            'target_state': [
                'coverage_path_active',
                'medical_appointment_booked',
                'medical_claim_submitted',
                'vaccination_record_updated',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the claim-vaccine health packet only after coverage is active, the appointment is booked, the medical claim is submitted, the vaccination record is updated, and the follow-up calendar is synced.',
                'Close the claim-vaccine workflow by activating coverage first, completing the appointment and claim path, updating the vaccine record, and ending with a synced follow-up calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; claim-then-vaccine health workflows should schedule a concrete follow-up after the vaccination step.'
            ),
            'distinctness_rule': (
                'Either start from the insurance-policy route before appointment, claim, vaccine management, and calendar sync, '
                'or start from health-plan activation before the same appointment, claim, vaccine, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_policy_appt_claim_vaccine_calendar',
                    [
                        'MODULE_INSURANCE_POLICY',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_MEDICAL_CLAIM',
                        'MODULE_VACCINE_MGMT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_plan_appt_claim_vaccine_calendar',
                    [
                        'MODULE_HEALTH_PLAN_ACTIVATION',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_MEDICAL_CLAIM',
                        'MODULE_VACCINE_MGMT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_ILLNESS_REFILL:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'initial_world_state': [],
            'target_state': [
                'coverage_path_active',
                'medical_appointment_booked',
                'illness_report_submitted',
                'prescription_refilled',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the illness-reporting health packet only after coverage is active, the appointment is booked, the illness report is submitted, the prescription is refilled, and the follow-up calendar is synced.',
                'Close the illness-reporting workflow by activating coverage first, booking the appointment, reporting the illness, completing the refill, and ending with a synced follow-up calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; illness-reporting health workflows should close with a follow-up scheduling step after the refill.'
            ),
            'distinctness_rule': (
                'Either start from the insurance-policy route before appointment, illness reporting, refill, and calendar sync, '
                'or start from health-plan activation before the same appointment, reporting, refill, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_policy_appt_illness_refill_calendar',
                    [
                        'MODULE_INSURANCE_POLICY',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_ILLNESS_REPORTING',
                        'MODULE_PRESCRIPTION_REFILL',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_plan_appt_illness_refill_calendar',
                    [
                        'MODULE_HEALTH_PLAN_ACTIVATION',
                        'MODULE_DOCTOR_APPT',
                        'MODULE_ILLNESS_REPORTING',
                        'MODULE_PRESCRIPTION_REFILL',
                        'MODULE_EMAIL_CALENDAR',
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
        raise SystemExit('round44 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
