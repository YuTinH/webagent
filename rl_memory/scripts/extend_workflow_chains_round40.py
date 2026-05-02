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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round40'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND40_SPECS: dict[str, dict[str, Any]] = {
    'BP_CRISIS_FREEZE_LIQUIDITY_DISPUTE_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'account_access_contained',
            'crisis_intake_completed',
            'password_reset_completed',
            'emergency_liquidity_secured',
            'account_balance_reviewed',
            'transaction_dispute_submitted',
        ],
        'instruction_templates': [
            'Finish the crisis-liquidity packet only after access is contained, intake is logged, recovery is complete, emergency liquidity is secured, the balance is reviewed, and a dispute is submitted.',
            'Close the crisis route by containing the account first, restoring access, securing urgent liquidity, reviewing the balance, and ending with transaction dispute submission.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; freeze-side crisis workflows should continue from liquidity support into explicit balance review and transaction dispute handling.'
        ),
        'distinctness_rule': (
            'Reach the target through the full containment, recovery, urgent-loan, balance-review, and dispute chain rather than through a shorter crisis subset.'
        ),
        'paths': [
            (
                'path_freeze_recovery_loan_balance_dispute',
                [
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_URGENT_LOAN',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_DISPUTE_TRANSACTION',
                ],
            ),
        ],
    },
    'BP_CRISIS_CONTAINMENT_INTAKE': {'alias_of': 'BP_CRISIS_FREEZE_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_CONTAINMENT_INTAKE_BRIDGE': {'alias_of': 'BP_CRISIS_FREEZE_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_CONTAINMENT_LIQUIDITY_ALIGNMENT': {'alias_of': 'BP_CRISIS_FREEZE_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_FREEZE_SUPPLY_STABILIZATION': {'alias_of': 'BP_CRISIS_FREEZE_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_SUPPLY_LIQUIDITY_STABILIZATION': {'alias_of': 'BP_CRISIS_FREEZE_LIQUIDITY_DISPUTE_PACKET'},

    'BP_CRISIS_ILLNESS_LIQUIDITY_DISPUTE_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'illness_report_submitted',
            'crisis_intake_completed',
            'password_reset_completed',
            'emergency_liquidity_secured',
            'account_balance_reviewed',
            'transaction_dispute_submitted',
        ],
        'instruction_templates': [
            'Finish the illness-side crisis packet only after illness reporting is submitted, recovery is complete, emergency liquidity is secured, the balance is reviewed, and a dispute is submitted.',
            'Close the illness-side crisis route by logging the intake first, restoring access, securing urgent liquidity, reviewing the balance, and ending with transaction dispute submission.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; illness-side crisis workflows should continue from liquidity support into explicit balance review and transaction dispute handling.'
        ),
        'distinctness_rule': (
            'Reach the target through the full illness-report, recovery, urgent-loan, balance-review, and dispute chain rather than through a shorter crisis subset.'
        ),
        'paths': [
            (
                'path_illness_recovery_loan_balance_dispute',
                [
                    'MODULE_ILLNESS_REPORTING',
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_URGENT_LOAN',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_DISPUTE_TRANSACTION',
                ],
            ),
        ],
    },
    'BP_CRISIS_INTAKE_LIQUIDITY_ROUTE': {'alias_of': 'BP_CRISIS_ILLNESS_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_INTAKE_LIQUIDITY_SPLIT': {'alias_of': 'BP_CRISIS_ILLNESS_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_REPORT_LIQUIDITY_STABILIZATION': {'alias_of': 'BP_CRISIS_ILLNESS_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_WORKFLOW_INTAKE_LIQUIDITY': {'alias_of': 'BP_CRISIS_ILLNESS_LIQUIDITY_DISPUTE_PACKET'},

    'BP_CRISIS_RESET_LIQUIDITY_DISPUTE_PACKET': {
        'difficulty': 7,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'password_reset_completed',
            'emergency_liquidity_secured',
            'account_balance_reviewed',
            'transaction_dispute_submitted',
        ],
        'instruction_templates': [
            'Finish the reset-liquidity packet only after password reset is complete, emergency liquidity is secured, the balance is reviewed, and a dispute is submitted.',
            'Close the reset-driven crisis route by completing recovery first, securing urgent liquidity, reviewing the balance, and ending with a transaction dispute filed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; reset-driven crisis workflows should continue from liquidity support into explicit balance review and dispute handling.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset-request, reset-completion, urgent-loan, balance-review, and dispute chain rather than through a shorter crisis subset.'
        ),
        'paths': [
            (
                'path_reset_loan_balance_dispute',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_URGENT_LOAN',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_DISPUTE_TRANSACTION',
                ],
            ),
        ],
    },
    'BP_CRISIS_ACCESS_LIQUIDITY': {'alias_of': 'BP_CRISIS_RESET_LIQUIDITY_DISPUTE_PACKET'},
    'BP_CRISIS_RESET_LIQUIDITY_RECOVERY': {'alias_of': 'BP_CRISIS_RESET_LIQUIDITY_DISPUTE_PACKET'},

    'BP_CRISIS_FREEZE_REPLACEMENT_DISPUTE_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'account_access_contained',
            'crisis_intake_completed',
            'password_reset_completed',
            'replacement_card_requested',
            'account_balance_reviewed',
            'transaction_dispute_submitted',
        ],
        'instruction_templates': [
            'Finish the replacement-side crisis packet only after access is contained, recovery is complete, the replacement card is requested, the balance is reviewed, and a dispute is submitted.',
            'Close the replacement-side crisis route by containing the account first, restoring access, requesting the replacement card, reviewing the balance, and ending with a transaction dispute filed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; replacement-oriented crisis workflows should continue from card replacement into balance review and dispute handling.'
        ),
        'distinctness_rule': (
            'Reach the target through the full containment, recovery, card-replacement, balance-review, and dispute chain rather than through a shorter crisis subset.'
        ),
        'paths': [
            (
                'path_freeze_recovery_replace_balance_dispute',
                [
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_DISPUTE_TRANSACTION',
                ],
            ),
        ],
    },
    'BP_CRISIS_CONTAINMENT_REPLACEMENT_ROUTE': {'alias_of': 'BP_CRISIS_FREEZE_REPLACEMENT_DISPUTE_PACKET'},
    'BP_CRISIS_INTAKE_REPLACEMENT_ALIGNMENT': {'alias_of': 'BP_CRISIS_FREEZE_REPLACEMENT_DISPUTE_PACKET'},

    'BP_CRISIS_ILLNESS_REPLACEMENT_DISPUTE_PACKET': {
        'difficulty': 7,
        'max_steps': 65,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'illness_report_submitted',
            'crisis_intake_completed',
            'password_reset_completed',
            'replacement_card_requested',
            'account_balance_reviewed',
            'transaction_dispute_submitted',
        ],
        'instruction_templates': [
            'Finish the illness-side replacement packet only after illness reporting is submitted, recovery is complete, the replacement card is requested, the balance is reviewed, and a dispute is submitted.',
            'Close the illness-side replacement route by logging the intake first, restoring access, requesting the replacement card, reviewing the balance, and ending with a transaction dispute filed.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; illness-side replacement workflows should continue from card replacement into balance review and dispute handling.'
        ),
        'distinctness_rule': (
            'Reach the target through the full illness-report, recovery, card-replacement, balance-review, and dispute chain rather than through a shorter crisis subset.'
        ),
        'paths': [
            (
                'path_illness_recovery_replace_balance_dispute',
                [
                    'MODULE_ILLNESS_REPORTING',
                    'MODULE_PASSWORD_RECOVERY_E2E',
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_DISPUTE_TRANSACTION',
                ],
            ),
        ],
    },
    'BP_CRISIS_ILLNESS_CONTAINMENT_ROUTE': {'alias_of': 'BP_CRISIS_ILLNESS_REPLACEMENT_DISPUTE_PACKET'},

    'BP_CRISIS_CARD_REPLACEMENT_REVIEW_PACKET': {
        'difficulty': 7,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'password_reset_completed',
            'card_frozen',
            'account_access_contained',
            'replacement_card_requested',
            'account_balance_reviewed',
        ],
        'instruction_templates': [
            'Finish the card-containment packet only after password reset is completed, the card is frozen, account access is contained, the replacement card is requested, and the balance is reviewed.',
            'Close the lost-card route by completing the reset first, freezing the card, requesting replacement, and ending with a balance review instead of stopping at replacement.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; lost-card containment should continue through post-replacement balance review rather than stopping once the replacement is requested.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset, freeze, replacement, and balance-review chain rather than through a shorter containment subset.'
        ),
        'paths': [
            (
                'path_reset_freeze_replace_balance',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_CHECK_BALANCE',
                ],
            ),
        ],
    },
    'BP_CRISIS_CARD_ACCESS_CONTAINMENT': {'alias_of': 'BP_CRISIS_CARD_REPLACEMENT_REVIEW_PACKET'},

    'BP_CRISIS_HEALTH_CALENDAR_PACKET': {
        'difficulty': 7,
        'max_steps': 55,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'password_reset_completed',
            'illness_report_submitted',
            'medical_appointment_booked',
            'calendar_event_synced',
        ],
        'instruction_templates': [
            'Finish the health-access packet only after password reset is complete, illness reporting is submitted, the medical appointment is booked, and the calendar event is synced.',
            'Close the health-access crisis route by restoring access first, logging the illness report, booking the medical appointment, and ending with the follow-up synced to the calendar.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; health-access crisis workflows should continue into explicit calendar follow-up after the medical appointment is booked.'
        ),
        'distinctness_rule': (
            'Reach the target through the full reset, illness-report, doctor-appointment, and calendar-sync chain rather than through a shorter health-access subset.'
        ),
        'paths': [
            (
                'path_reset_illness_doctor_calendar',
                [
                    'MODULE_PASSWORD_RESET_REQUEST',
                    'MODULE_PASSWORD_RESET_COMPLETION',
                    'MODULE_ILLNESS_REPORTING',
                    'MODULE_DOCTOR_APPT',
                    'MODULE_EMAIL_CALENDAR',
                ],
            ),
        ],
    },
    'BP_CRISIS_HEALTH_ACCESS_REPORTING': {'alias_of': 'BP_CRISIS_HEALTH_CALENDAR_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND40_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND40_SPECS[alias]
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
        raise SystemExit('round40 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
