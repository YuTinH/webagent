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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round28'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND28_SPECS: dict[str, dict[str, Any]] = {
    'BP_TRAVEL_DEPARTURE_PACKET_HARDENED': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'flight_booked',
            'mobility_clearance_verified',
            'airport_transfer_arranged',
            'check_in_completed',
            'commute_route_checked',
        ],
        'instruction_templates': [
            'Finish the departure-prep packet only after mobility clearance is verified, the flight is secured, the airport transfer is arranged, check-in is completed, and the onward commute route is checked.',
            'Close the outbound travel workflow by clearing mobility requirements, locking the flight path, arranging airport transfer, completing check-in, and confirming the final commute route.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; departure readiness should include a concrete clearance-plus-transfer-plus-check-in chain rather than a 3-step shortcut.'
        ),
        'distinctness_rule': (
            'Either verify mobility requirements, book a direct flight, then finish transfer, check-in, and commute preparation, '
            'or use the bundled long-haul path before completing the same transfer, check-in, and commute closure.'
        ),
        'paths': [
            (
                'path_visa_flight_transfer_checkin_commute',
                [
                    'MODULE_VISA_REQUIREMENTS',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_CHECK_IN',
                    'MODULE_COMMUTE_ROUTE',
                ],
            ),
            (
                'path_longhaul_transfer_checkin_commute',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_CHECK_IN',
                    'MODULE_COMMUTE_ROUTE',
                ],
            ),
        ],
    },
    'BP_TRAVEL_FLIGHT_READY': {
        'alias_of': 'BP_TRAVEL_DEPARTURE_PACKET_HARDENED',
    },
    'BP_TRAVEL_FLIGHT_COMMUTE_READY': {
        'alias_of': 'BP_TRAVEL_DEPARTURE_PACKET_HARDENED',
    },
    'BP_TRAVEL_TRANSFER_CHECKIN_ALIGNMENT': {
        'alias_of': 'BP_TRAVEL_DEPARTURE_PACKET_HARDENED',
    },
    'BP_TRAVEL_CLEARANCE_TRANSFER_SYNC': {
        'alias_of': 'BP_TRAVEL_DEPARTURE_PACKET_HARDENED',
    },
    'BP_TRAVEL_EXPENSE_PACKET_HARDENED': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'mobility_clearance_verified',
            'travel_booking_confirmed',
            'airport_transfer_arranged',
            'check_in_completed',
            'expense_report_submitted',
        ],
        'instruction_templates': [
            'Finish the travel-expense packet only after mobility clearance is verified, the booking is confirmed, the airport transfer is arranged, check-in is completed, and the expense report is filed.',
            'Close the travel-admin route by clearing mobility requirements, locking the booking, arranging airport transfer, completing check-in, and ending with the expense report submitted.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; reimbursement-oriented travel workflows should require a full booking, transfer, and check-in packet before the expense step closes.'
        ),
        'distinctness_rule': (
            'Either verify mobility requirements and book a direct flight before transfer, check-in, and expense filing, '
            'or use the bundled long-haul booking path before the same transfer, check-in, and reporting closure.'
        ),
        'paths': [
            (
                'path_visa_flight_transfer_checkin_expense',
                [
                    'MODULE_VISA_REQUIREMENTS',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_CHECK_IN',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
            (
                'path_longhaul_transfer_checkin_expense',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_CHECK_IN',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
        ],
    },
    'BP_TRAVEL_EXPENSE_BOOKING_ALIGNMENT': {
        'alias_of': 'BP_TRAVEL_EXPENSE_PACKET_HARDENED',
    },
    'BP_TRAVEL_STAY_EXPENSE_READY': {
        'alias_of': 'BP_TRAVEL_EXPENSE_PACKET_HARDENED',
    },
    'BP_TRAVEL_TRANSFER_EXPENSE_BRIDGE': {
        'alias_of': 'BP_TRAVEL_EXPENSE_PACKET_HARDENED',
    },
    'BP_TRAVEL_HOTEL_CLEARANCE_HARDENED': {
        'difficulty': 6,
        'max_steps': 60,
        'max_module_invocations': 5,
        'initial_world_state': [],
        'target_state': [
            'mobility_clearance_verified',
            'hotel_booked',
            'airport_transfer_arranged',
            'expense_report_submitted',
        ],
        'instruction_templates': [
            'Finish the hotel-clearance workflow only after mobility clearance is verified, the hotel is booked, the airport transfer is arranged, and the expense report is filed.',
            'Close the stay-prep packet by clearing mobility requirements, securing the hotel, arranging airport transfer, and then filing the related expense record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; hotel-readiness travel flows should include mobility clearance plus transfer setup before the reporting step closes.'
        ),
        'distinctness_rule': (
            'Either verify mobility requirements, book a direct flight, secure the hotel, then arrange transfer before filing the expense record, '
            'or use the bundled long-haul trip before hotel booking, transfer setup, and expense filing.'
        ),
        'paths': [
            (
                'path_visa_flight_hotel_transfer_expense',
                [
                    'MODULE_VISA_REQUIREMENTS',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
            (
                'path_longhaul_hotel_transfer_expense',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_BOOK_HOTEL',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_EXPENSE_REPORT',
                ],
            ),
        ],
    },
    'BP_TRAVEL_CLEARANCE_HOTEL': {
        'alias_of': 'BP_TRAVEL_HOTEL_CLEARANCE_HARDENED',
    },
    'BP_TRAVEL_REBOOK_DEPARTURE_HARDENED': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'flight_booked',
            'itinerary_rebooked',
            'airport_transfer_arranged',
            'check_in_completed',
        ],
        'instruction_templates': [
            'Finish the rebooked-departure workflow only after the itinerary is rebooked, airport transfer is arranged, and check-in is completed for a valid booked flight.',
            'Close the trip-recovery route by securing the base flight, rebooking the itinerary, arranging airport transfer, and then completing check-in.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; rebooking should not terminate immediately after transfer setup and should carry through to departure readiness.'
        ),
        'distinctness_rule': (
            'Either book a direct flight and rebook it before transfer and check-in, or use the bundled long-haul path before the same rebook, transfer, and check-in closure.'
        ),
        'paths': [
            (
                'path_flight_rebook_transfer_checkin',
                [
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_CHECK_IN',
                ],
            ),
            (
                'path_longhaul_rebook_transfer_checkin',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_CHECK_IN',
                ],
            ),
        ],
    },
    'BP_TRAVEL_REBOOKED_DEPARTURE': {
        'alias_of': 'BP_TRAVEL_REBOOK_DEPARTURE_HARDENED',
    },
    'BP_TRAVEL_WORKFLOW_REBOOK_TRANSFER': {
        'alias_of': 'BP_TRAVEL_REBOOK_DEPARTURE_HARDENED',
    },
    'BP_TRAVEL_REBOOK_COMMUTE_HARDENED': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'flight_booked',
            'itinerary_rebooked',
            'airport_transfer_arranged',
            'commute_route_checked',
        ],
        'instruction_templates': [
            'Finish the rebook-commute recovery workflow only after the base flight remains valid, the itinerary is rebooked, airport transfer is arranged, and the final commute route is checked.',
            'Close the travel-recovery packet by preserving the booked flight, rebooking the itinerary, arranging airport transfer, and confirming the final commute route.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; commute recovery should flow through rebooking and transfer setup rather than ending in a 3-step shortcut.'
        ),
        'distinctness_rule': (
            'Either book a direct flight and rebook it before transfer and commute confirmation, or use the bundled long-haul route before the same rebook, transfer, and commute closure.'
        ),
        'paths': [
            (
                'path_flight_rebook_transfer_commute',
                [
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_COMMUTE_ROUTE',
                ],
            ),
            (
                'path_longhaul_rebook_transfer_commute',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_COMMUTE_ROUTE',
                ],
            ),
        ],
    },
    'BP_TRAVEL_REBOOK_COMMUTE_RECOVERY': {
        'alias_of': 'BP_TRAVEL_REBOOK_COMMUTE_HARDENED',
    },
    'BP_TRAVEL_REBOOK_TOPUP_HARDENED': {
        'difficulty': 6,
        'max_steps': 45,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'flight_booked',
            'itinerary_rebooked',
            'airport_transfer_arranged',
            'transit_balance_topped_up',
        ],
        'instruction_templates': [
            'Finish the rebook-topup workflow only after the base flight remains valid, the itinerary is rebooked, airport transfer is arranged, and the transit balance is topped up.',
            'Close the travel-adjustment route by preserving the booked flight, rebooking the itinerary, arranging airport transfer, and then topping up transit balance.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; transit top-up recovery should include transfer setup after rebooking rather than ending immediately after the top-up.'
        ),
        'distinctness_rule': (
            'Either book a direct flight and rebook it before transfer and transit top-up, or use the bundled long-haul route before the same rebook, transfer, and top-up closure.'
        ),
        'paths': [
            (
                'path_flight_rebook_transfer_topup',
                [
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_TRANSPORT_TOPUP',
                ],
            ),
            (
                'path_longhaul_rebook_transfer_topup',
                [
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_FLIGHT_REBOOKING',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_TRANSPORT_TOPUP',
                ],
            ),
        ],
    },
    'BP_TRAVEL_REBOOK_TOPUP': {
        'alias_of': 'BP_TRAVEL_REBOOK_TOPUP_HARDENED',
    },
    'BP_TRAVEL_MOBILITY_TOPUP_HARDENED': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': [],
        'target_state': [
            'visa_requirements_checked',
            'flight_booked',
            'airport_transfer_arranged',
            'transit_balance_topped_up',
        ],
        'instruction_templates': [
            'Finish the mobility-topup prep only after visa requirements are checked, the flight is secured, airport transfer is arranged, and the transit balance is topped up.',
            'Close the outbound mobility packet by verifying visa requirements, locking the flight path, arranging airport transfer, and topping up transit balance.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; visa-and-topup preparation should include transfer setup and a secured trip path rather than a minimal 3-step route.'
        ),
        'distinctness_rule': (
            'Either verify visa requirements and book a direct flight before arranging transfer and topping up transit, '
            'or verify the same visa requirements before switching to the bundled long-haul trip and then completing transfer and top-up.'
        ),
        'paths': [
            (
                'path_visa_flight_transfer_topup',
                [
                    'MODULE_VISA_REQUIREMENTS',
                    'MODULE_BOOK_FLIGHT',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_TRANSPORT_TOPUP',
                ],
            ),
            (
                'path_visa_longhaul_transfer_topup',
                [
                    'MODULE_VISA_REQUIREMENTS',
                    'MODULE_LONG_HAUL_TRIP',
                    'MODULE_AIRPORT_TRANSFER',
                    'MODULE_TRANSPORT_TOPUP',
                ],
            ),
        ],
    },
    'BP_TRAVEL_VISA_MOBILITY_PREP': {
        'alias_of': 'BP_TRAVEL_MOBILITY_TOPUP_HARDENED',
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND28_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND28_SPECS[alias]
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
        raise SystemExit('round28 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
