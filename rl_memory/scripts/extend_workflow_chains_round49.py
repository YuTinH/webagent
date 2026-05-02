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

SIG_RESALE_SUBSCRIPTION = (
    ('MODULE_SECOND_HAND_ITEM_LISTING', 'MODULE_COUPON_MANAGEMENT', 'MODULE_GROCERY_RUN', 'MODULE_FRESH_SUBSCRIPTION'),
    ('MODULE_SECOND_HAND_SALE', 'MODULE_COUPON_MANAGEMENT', 'MODULE_GROCERY_RUN', 'MODULE_FRESH_SUBSCRIPTION'),
)
SIG_ORDER_VALUE_PROTECTION = (
    ('MODULE_SHOPPING', 'MODULE_TRACK_ORDERS', 'MODULE_PRICE_PROTECTION', 'MODULE_ORDER_ARRIVAL'),
    ('MODULE_SHOPPING', 'MODULE_COUPON_MANAGEMENT', 'MODULE_TRACK_ORDERS', 'MODULE_ORDER_ARRIVAL'),
)
SIG_SUBSCRIPTION_SERVICE = (
    ('MODULE_HOUSEKEEPING_BOOKING', 'MODULE_COUPON_MANAGEMENT', 'MODULE_FRESH_SUBSCRIPTION', 'MODULE_FOOD_DELIVERY'),
    ('MODULE_GROCERY_RUN', 'MODULE_HOUSEKEEPING_BOOKING', 'MODULE_FRESH_SUBSCRIPTION', 'MODULE_FOOD_DELIVERY'),
)
SIG_TICKET_SERVICE = (
    ('MODULE_HOUSEKEEPING_BOOKING', 'MODULE_COUPON_MANAGEMENT', 'MODULE_FOOD_DELIVERY', 'MODULE_MOVIE_TICKETS'),
    ('MODULE_HOUSEKEEPING_BOOKING', 'MODULE_COUPON_MANAGEMENT', 'MODULE_FOOD_DELIVERY', 'MODULE_EVENT_TICKETS'),
)
SIG_BUNDLE_PREP = (
    ('MODULE_COUPON_MANAGEMENT', 'MODULE_HOUSEKEEPING_BOOKING', 'MODULE_FOOD_DELIVERY', 'MODULE_FRESH_SUBSCRIPTION'),
    ('MODULE_GROCERY_RUN', 'MODULE_HOUSEKEEPING_BOOKING', 'MODULE_FRESH_SUBSCRIPTION', 'MODULE_FOOD_DELIVERY'),
)
SIG_DISCOUNTED_PROTECTION = (
    ('MODULE_TRACK_ORDERS', 'MODULE_PRICE_PROTECTION', 'MODULE_ORDER_ARRIVAL', 'MODULE_CUSTOMER_SERVICE'),
    ('MODULE_COUPON_MANAGEMENT', 'MODULE_TRACK_ORDERS', 'MODULE_ORDER_ARRIVAL', 'MODULE_CUSTOMER_SERVICE'),
)
SIG_POST_PURCHASE_FEEDBACK = (
    ('MODULE_SHOPPING', 'MODULE_TRACK_ORDERS', 'MODULE_ORDER_ARRIVAL', 'MODULE_LEAVE_REVIEW'),
    ('MODULE_SHOPPING', 'MODULE_TRACK_ORDERS', 'MODULE_ORDER_ARRIVAL', 'MODULE_REVIEWS_BLACKLIST'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round49'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'daily':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_RESALE_SUBSCRIPTION:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'resale_listing_activated',
                'daily_order_bundle_prepared',
                'subscription_active',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the resale workflow only after the listing is active, the daily bundle is prepared, the subscription is turned on, and the follow-up schedule is synced to the calendar.',
                'Close the resale route by activating the listing first, building the bundle, turning on the subscription, and ending with a synced follow-up calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; resale-and-subscription daily workflows should end with an explicit scheduling handoff.'
            ),
            'distinctness_rule': (
                'Either use the item-listing route before bundle prep, subscription activation, and calendar sync, '
                'or use the second-hand-sale route before the same bundle, subscription, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_listing_coupon_grocery_subscription_calendar',
                    [
                        'MODULE_SECOND_HAND_ITEM_LISTING',
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_GROCERY_RUN',
                        'MODULE_FRESH_SUBSCRIPTION',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_sale_coupon_grocery_subscription_calendar',
                    [
                        'MODULE_SECOND_HAND_SALE',
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_GROCERY_RUN',
                        'MODULE_FRESH_SUBSCRIPTION',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_ORDER_VALUE_PROTECTION:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'order_followup_prepared',
                'order_price_secured',
                'delivery_visibility_confirmed',
                'shop_order_delivered',
                'support_contacted',
            ],
            'instruction_templates': [
                'Finish the order-protection workflow only after order follow-up is prepared, pricing is secured, delivery is confirmed, the order is delivered, and customer service is contacted.',
                'Close the daily protection route by creating the order context first, handling follow-up and price protection, confirming delivery, and ending with a concrete service contact.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; order-protection daily workflows should continue into explicit customer-service closure after delivery.'
            ),
            'distinctness_rule': (
                'Either use the direct tracking route before price protection, delivery, and customer service, '
                'or use the coupon-assisted tracking route before the same protection, delivery, and service closure.'
            ),
            'paths': [
                (
                    'path_shop_track_price_arrival_service',
                    [
                        'MODULE_SHOPPING',
                        'MODULE_TRACK_ORDERS',
                        'MODULE_PRICE_PROTECTION',
                        'MODULE_ORDER_ARRIVAL',
                        'MODULE_CUSTOMER_SERVICE',
                    ],
                ),
                (
                    'path_shop_coupon_track_arrival_service',
                    [
                        'MODULE_SHOPPING',
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_TRACK_ORDERS',
                        'MODULE_ORDER_ARRIVAL',
                        'MODULE_CUSTOMER_SERVICE',
                    ],
                ),
            ],
        }

    if sig == SIG_SUBSCRIPTION_SERVICE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'service_stack_prepared',
                'daily_order_bundle_prepared',
                'food_order_pending',
                'subscription_active',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the service-subscription workflow only after the service stack is prepared, the daily bundle is prepared, a food order is pending, the subscription is active, and the routine is synced to the calendar.',
                'Close the daily service stack by preparing both service and bundle context, completing the subscription and food steps, and ending with a synced routine calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; daily service-and-subscription workflows should end with an explicit calendar handoff.'
            ),
            'distinctness_rule': (
                'Either use the housekeeping-first route before subscription, food delivery, and calendar sync, '
                'or use the grocery-first route before the same subscription, food, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_housekeeping_coupon_subscription_food_calendar',
                    [
                        'MODULE_HOUSEKEEPING_BOOKING',
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_FRESH_SUBSCRIPTION',
                        'MODULE_FOOD_DELIVERY',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_grocery_housekeeping_subscription_food_calendar',
                    [
                        'MODULE_GROCERY_RUN',
                        'MODULE_HOUSEKEEPING_BOOKING',
                        'MODULE_FRESH_SUBSCRIPTION',
                        'MODULE_FOOD_DELIVERY',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_TICKET_SERVICE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'housekeeping_service_booked',
                'order_price_secured',
                'food_order_pending',
                'event_ticket_booked',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the ticket-service workflow only after housekeeping is booked, pricing is secured, a food order is pending, event access is booked, and the itinerary is synced to the calendar.',
                'Close the daily ticket-service route by booking housekeeping first, then finishing the price, food, and ticket steps, and ending with a synced itinerary calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; ticket-service daily workflows should end with a calendar handoff after booking access.'
            ),
            'distinctness_rule': (
                'Either use the movie-ticket route before calendar sync, '
                'or use the event-ticket route before the same calendar closure.'
            ),
            'paths': [
                (
                    'path_service_coupon_food_movie_calendar',
                    [
                        'MODULE_HOUSEKEEPING_BOOKING',
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_FOOD_DELIVERY',
                        'MODULE_MOVIE_TICKETS',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_service_coupon_food_event_calendar',
                    [
                        'MODULE_HOUSEKEEPING_BOOKING',
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_FOOD_DELIVERY',
                        'MODULE_EVENT_TICKETS',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_BUNDLE_PREP:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'daily_order_bundle_prepared',
                'service_stack_prepared',
                'food_order_pending',
                'subscription_active',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the bundle-prep workflow only after the order bundle is prepared, the service stack is prepared, the food order is pending, the subscription is active, and the daily routine is synced to the calendar.',
                'Close the daily route by preparing the household stack first, finishing the food-and-subscription bundle, and ending with a synced routine calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; bundle-prep daily workflows should end with an explicit routine-scheduling step.'
            ),
            'distinctness_rule': (
                'Either use the coupon-led prep route before subscription activation and calendar sync, '
                'or use the grocery-led prep route before the same subscription, food, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_coupon_service_food_subscription_calendar',
                    [
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_HOUSEKEEPING_BOOKING',
                        'MODULE_FOOD_DELIVERY',
                        'MODULE_FRESH_SUBSCRIPTION',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_grocery_service_subscription_food_calendar',
                    [
                        'MODULE_GROCERY_RUN',
                        'MODULE_HOUSEKEEPING_BOOKING',
                        'MODULE_FRESH_SUBSCRIPTION',
                        'MODULE_FOOD_DELIVERY',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_DISCOUNTED_PROTECTION:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'order_price_secured',
                'order_followup_prepared',
                'order_tracking_opened',
                'delivery_visibility_confirmed',
                'shop_order_delivered',
                'support_contacted',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the discounted-order protection workflow only after price protection is secured, tracking is open, delivery is visible, the order is delivered, support contact is completed, and the follow-up is synced to the calendar.',
                'Close the post-order protection route by opening tracking first, securing the price path, confirming delivery, completing the support follow-up, and ending with a synced reminder calendar.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; discounted-order protection workflows should include a scheduled follow-up after customer service.'
            ),
            'distinctness_rule': (
                'Either use the tracking-first route before delivery, customer service, and calendar sync, '
                'or use the coupon-assisted tracking route before the same delivery, service, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_track_price_arrival_service_calendar',
                    [
                        'MODULE_TRACK_ORDERS',
                        'MODULE_PRICE_PROTECTION',
                        'MODULE_ORDER_ARRIVAL',
                        'MODULE_CUSTOMER_SERVICE',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_coupon_track_arrival_service_calendar',
                    [
                        'MODULE_COUPON_MANAGEMENT',
                        'MODULE_TRACK_ORDERS',
                        'MODULE_ORDER_ARRIVAL',
                        'MODULE_CUSTOMER_SERVICE',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_POST_PURCHASE_FEEDBACK:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'shop_order_delivered',
                'product_review_submitted',
                'order_followup_prepared',
                'support_contacted',
            ],
            'instruction_templates': [
                'Finish the post-purchase feedback workflow only after the order is delivered, product feedback is submitted, order follow-up is prepared, and customer service is contacted.',
                'Close the post-purchase route by placing the order, opening follow-up, confirming delivery, completing the feedback action, and ending with a concrete service contact.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; post-purchase feedback daily workflows should continue into explicit customer-service closure.'
            ),
            'distinctness_rule': (
                'Either use the review route before customer service, '
                'or use the blacklist-feedback route before the same customer-service closure.'
            ),
            'paths': [
                (
                    'path_shop_track_arrival_review_service',
                    [
                        'MODULE_SHOPPING',
                        'MODULE_TRACK_ORDERS',
                        'MODULE_ORDER_ARRIVAL',
                        'MODULE_LEAVE_REVIEW',
                        'MODULE_CUSTOMER_SERVICE',
                    ],
                ),
                (
                    'path_shop_track_arrival_blacklist_service',
                    [
                        'MODULE_SHOPPING',
                        'MODULE_TRACK_ORDERS',
                        'MODULE_ORDER_ARRIVAL',
                        'MODULE_REVIEWS_BLACKLIST',
                        'MODULE_CUSTOMER_SERVICE',
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
        raise SystemExit('round49 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
