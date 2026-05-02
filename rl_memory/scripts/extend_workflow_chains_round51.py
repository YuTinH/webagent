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

SIG_REBOOKED_DEPARTURE = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_FLIGHT_REBOOKING', 'MODULE_AIRPORT_TRANSFER', 'MODULE_CHECK_IN'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_FLIGHT_REBOOKING', 'MODULE_AIRPORT_TRANSFER', 'MODULE_CHECK_IN'),
)
SIG_BOOKING_CLEARANCE = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_VISA_REQUIREMENTS', 'MODULE_AIRPORT_TRANSFER', 'MODULE_COMMUTE_ROUTE'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_VISA_REQUIREMENTS', 'MODULE_AIRPORT_TRANSFER', 'MODULE_COMMUTE_ROUTE'),
)
SIG_BOOKING_CHECKIN = (
    ('MODULE_VISA_REQUIREMENTS', 'MODULE_BOOK_FLIGHT', 'MODULE_CHECK_IN', 'MODULE_EXPENSE_REPORT'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_AIRPORT_TRANSFER', 'MODULE_CHECK_IN', 'MODULE_EXPENSE_REPORT'),
)
SIG_BOOKING_EXPENSE = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_BOOK_HOTEL', 'MODULE_AIRPORT_TRANSFER', 'MODULE_EXPENSE_REPORT'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_BOOK_HOTEL', 'MODULE_AIRPORT_TRANSFER', 'MODULE_EXPENSE_REPORT'),
)
SIG_BOOKING_TOPUP = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_BOOK_HOTEL', 'MODULE_AIRPORT_TRANSFER', 'MODULE_TRANSPORT_TOPUP'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_BOOK_HOTEL', 'MODULE_AIRPORT_TRANSFER', 'MODULE_TRANSPORT_TOPUP'),
)
SIG_REBOOK_COMMUTE = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_FLIGHT_REBOOKING', 'MODULE_AIRPORT_TRANSFER', 'MODULE_COMMUTE_ROUTE'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_FLIGHT_REBOOKING', 'MODULE_AIRPORT_TRANSFER', 'MODULE_COMMUTE_ROUTE'),
)
SIG_REBOOK_TOPUP = (
    ('MODULE_BOOK_FLIGHT', 'MODULE_FLIGHT_REBOOKING', 'MODULE_AIRPORT_TRANSFER', 'MODULE_TRANSPORT_TOPUP'),
    ('MODULE_LONG_HAUL_TRIP', 'MODULE_FLIGHT_REBOOKING', 'MODULE_AIRPORT_TRANSFER', 'MODULE_TRANSPORT_TOPUP'),
)
SIG_VISA_MOBILITY = (
    ('MODULE_VISA_REQUIREMENTS', 'MODULE_BOOK_FLIGHT', 'MODULE_AIRPORT_TRANSFER', 'MODULE_TRANSPORT_TOPUP'),
    ('MODULE_VISA_REQUIREMENTS', 'MODULE_LONG_HAUL_TRIP', 'MODULE_AIRPORT_TRANSFER', 'MODULE_TRANSPORT_TOPUP'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round51'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'travel':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_REBOOKED_DEPARTURE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['calendar_event_synced'],
            'instruction_templates': [
                'Finish the rebooked-departure workflow only after the itinerary is rebooked, transfer is arranged, check-in is completed, and the departure follow-up is synced to the calendar.',
                'Close the rebooked-departure route by confirming the rebooked itinerary, arranging transfer, completing check-in, and ending with a synced departure calendar.',
            ],
            'notes_template': 'Generated from {blueprint_id}; rebooked-travel workflows should end with a synced departure follow-up.',
            'distinctness_rule': 'Follow one full rebooking route to completion and do not stop before the departure follow-up is synced to the calendar.',
            'paths': [
                (
                    'path_flight_rebook_transfer_checkin_calendar',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_FLIGHT_REBOOKING',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_CHECK_IN',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_longhaul_rebook_transfer_checkin_calendar',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_FLIGHT_REBOOKING',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_CHECK_IN',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_BOOKING_CLEARANCE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['check_in_completed'],
            'instruction_templates': [
                'Finish the booking-clearance workflow only after mobility clearance is verified, transfer is arranged, the commute route is checked, and check-in is completed.',
                'Close the clearance route by confirming travel clearance first, arranging transfer and commute readiness, and ending with completed check-in.',
            ],
            'notes_template': 'Generated from {blueprint_id}; booking-clearance travel workflows should continue through check-in rather than stopping at commute prep.',
            'distinctness_rule': 'Follow one full clearance route to completion and do not stop before check-in is completed.',
            'paths': [
                (
                    'path_flight_visa_transfer_commute_checkin',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_VISA_REQUIREMENTS',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_COMMUTE_ROUTE',
                        'MODULE_CHECK_IN',
                    ],
                ),
                (
                    'path_longhaul_visa_transfer_commute_checkin',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_VISA_REQUIREMENTS',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_COMMUTE_ROUTE',
                        'MODULE_CHECK_IN',
                    ],
                ),
            ],
        }

    if sig == SIG_BOOKING_CHECKIN:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['calendar_event_synced'],
            'instruction_templates': [
                'Finish the booking-checkin workflow only after check-in is completed, the expense report is submitted, and the travel follow-up is synced to the calendar.',
                'Close the booking-checkin route by confirming pre-departure readiness, submitting the expense report, and ending with a synced travel calendar.',
            ],
            'notes_template': 'Generated from {blueprint_id}; booking-checkin travel workflows should end with a calendar handoff after expense submission.',
            'distinctness_rule': 'Follow one full booking-checkin route to completion and do not stop before the travel follow-up is synced to the calendar.',
            'paths': [
                (
                    'path_visa_flight_checkin_expense_calendar',
                    [
                        'MODULE_VISA_REQUIREMENTS',
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_CHECK_IN',
                        'MODULE_EXPENSE_REPORT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_longhaul_transfer_checkin_expense_calendar',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_CHECK_IN',
                        'MODULE_EXPENSE_REPORT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_BOOKING_EXPENSE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['calendar_event_synced'],
            'instruction_templates': [
                'Finish the booking-expense workflow only after booking is confirmed, transfer is arranged, the expense report is submitted, and the itinerary follow-up is synced to the calendar.',
                'Close the booking-expense route by confirming travel and hotel booking first, arranging transfer, filing expenses, and ending with a synced itinerary calendar.',
            ],
            'notes_template': 'Generated from {blueprint_id}; booking-and-expense travel workflows should end with an itinerary calendar handoff.',
            'distinctness_rule': 'Follow one full booking-expense route to completion and do not stop before the itinerary follow-up is synced to the calendar.',
            'paths': [
                (
                    'path_flight_hotel_transfer_expense_calendar',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_BOOK_HOTEL',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_EXPENSE_REPORT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_longhaul_hotel_transfer_expense_calendar',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_BOOK_HOTEL',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_EXPENSE_REPORT',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_BOOKING_TOPUP:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['check_in_completed'],
            'instruction_templates': [
                'Finish the booking-topup workflow only after travel booking is confirmed, transfer is arranged, transit balance is topped up, and check-in is completed.',
                'Close the booking-topup route by confirming travel booking first, arranging transfer, topping up transit balance, and ending with completed check-in.',
            ],
            'notes_template': 'Generated from {blueprint_id}; booking-and-topup travel workflows should continue through check-in.',
            'distinctness_rule': 'Follow one full booking-topup route to completion and do not stop before check-in is completed.',
            'paths': [
                (
                    'path_flight_hotel_transfer_topup_checkin',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_BOOK_HOTEL',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_TRANSPORT_TOPUP',
                        'MODULE_CHECK_IN',
                    ],
                ),
                (
                    'path_longhaul_hotel_transfer_topup_checkin',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_BOOK_HOTEL',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_TRANSPORT_TOPUP',
                        'MODULE_CHECK_IN',
                    ],
                ),
            ],
        }

    if sig == SIG_REBOOK_COMMUTE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['check_in_completed'],
            'instruction_templates': [
                'Finish the rebook-commute workflow only after the itinerary is rebooked, transfer is arranged, the commute route is checked, and check-in is completed.',
                'Close the rebook-commute route by confirming the rebooked itinerary first, arranging transfer and commute readiness, and ending with completed check-in.',
            ],
            'notes_template': 'Generated from {blueprint_id}; rebook-and-commute travel workflows should continue through check-in.',
            'distinctness_rule': 'Follow one full rebook-commute route to completion and do not stop before check-in is completed.',
            'paths': [
                (
                    'path_flight_rebook_transfer_commute_checkin',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_FLIGHT_REBOOKING',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_COMMUTE_ROUTE',
                        'MODULE_CHECK_IN',
                    ],
                ),
                (
                    'path_longhaul_rebook_transfer_commute_checkin',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_FLIGHT_REBOOKING',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_COMMUTE_ROUTE',
                        'MODULE_CHECK_IN',
                    ],
                ),
            ],
        }

    if sig == SIG_REBOOK_TOPUP:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['check_in_completed'],
            'instruction_templates': [
                'Finish the rebook-topup workflow only after the itinerary is rebooked, transfer is arranged, transit balance is topped up, and check-in is completed.',
                'Close the rebook-topup route by confirming the rebooked itinerary first, arranging transfer, topping up transit balance, and ending with completed check-in.',
            ],
            'notes_template': 'Generated from {blueprint_id}; rebook-and-topup travel workflows should continue through check-in.',
            'distinctness_rule': 'Follow one full rebook-topup route to completion and do not stop before check-in is completed.',
            'paths': [
                (
                    'path_flight_rebook_transfer_topup_checkin',
                    [
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_FLIGHT_REBOOKING',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_TRANSPORT_TOPUP',
                        'MODULE_CHECK_IN',
                    ],
                ),
                (
                    'path_longhaul_rebook_transfer_topup_checkin',
                    [
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_FLIGHT_REBOOKING',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_TRANSPORT_TOPUP',
                        'MODULE_CHECK_IN',
                    ],
                ),
            ],
        }

    if sig == SIG_VISA_MOBILITY:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': list(bp.get('target_state', [])) + ['commute_route_checked'],
            'instruction_templates': [
                'Finish the visa-mobility workflow only after mobility clearance is verified, transfer is arranged, transit balance is topped up, and the commute route is checked.',
                'Close the visa-mobility route by verifying travel clearance first, arranging transfer, topping up transit balance, and ending with a checked commute route.',
            ],
            'notes_template': 'Generated from {blueprint_id}; visa-and-mobility travel workflows should continue into final commute-route readiness.',
            'distinctness_rule': 'Follow one full visa-mobility route to completion and do not stop before the commute route is checked.',
            'paths': [
                (
                    'path_visa_flight_transfer_topup_commute',
                    [
                        'MODULE_VISA_REQUIREMENTS',
                        'MODULE_BOOK_FLIGHT',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_TRANSPORT_TOPUP',
                        'MODULE_COMMUTE_ROUTE',
                    ],
                ),
                (
                    'path_visa_longhaul_transfer_topup_commute',
                    [
                        'MODULE_VISA_REQUIREMENTS',
                        'MODULE_LONG_HAUL_TRIP',
                        'MODULE_AIRPORT_TRANSFER',
                        'MODULE_TRANSPORT_TOPUP',
                        'MODULE_COMMUTE_ROUTE',
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
        raise SystemExit('round51 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
