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
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"
BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"
GENERATOR_PATH = ROOT / "rl_memory" / "scripts" / "generate_workflow_goal_batch.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load_generator_module():
    spec = importlib.util.spec_from_file_location("workflow_goal_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load generator from {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_step_lookup(paths: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in paths:
        for step in path.get("steps", []):
            module_id = step.get("module_id")
            if module_id and module_id not in lookup:
                lookup[module_id] = copy.deepcopy(step)
    return lookup


def build_global_step_lookup(blueprints: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for blueprint in blueprints:
        for module_id, step in base_step_lookup(blueprint.get("paths", [])).items():
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
        step = {"module_id": module_id}

    bindings = step.get("parameter_bindings")
    if isinstance(bindings, dict):
        referenced = {
            value[1:]
            for value in bindings.values()
            if isinstance(value, str) and value.startswith("@")
        }
        if not referenced.issubset(allowed_shared_vars):
            step.pop("parameter_bindings", None)
    return step


def build_path(
    local_lookup: dict[str, dict[str, Any]],
    global_lookup: dict[str, dict[str, Any]],
    allowed_shared_vars: set[str],
    path_id: str,
    module_ids: list[str],
    kind: str = "alternative",
) -> dict[str, Any]:
    return {
        "path_id": path_id,
        "kind": kind,
        "steps": [
            step_from_lookup(local_lookup, global_lookup, allowed_shared_vars, module_id)
            for module_id in module_ids
        ],
    }


def replace_preferred_outcomes(existing: dict[str, Any], outcomes: list[str]) -> dict[str, Any]:
    updated = copy.deepcopy(existing)
    updated["preferred_outcomes"] = outcomes
    return updated


def stable_goal_seed(goal_id: str, blueprint_id: str) -> int:
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round21".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND21_SPECS: dict[str, dict[str, Any]] = {
    "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED": {
        "difficulty": 5,
        "max_steps": 44,
        "max_module_invocations": 4,
        "initial_world_state": ["subscription_active", "shop_order_delivered"],
        "target_state": [
            "support_contacted",
            "refund_requested",
            "subscription_canceled",
            "subscription_exit_processed",
        ],
        "instruction_templates": [
            "Finish the subscription-exit workflow only after support is contacted, a refund is requested, the subscription is canceled, and the subscription exit is fully processed.",
            "Close the subscription-support route by resolving the refund and cancellation steps and ending with support contact confirmed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; subscription-support workflows should use a real support channel and refund escalation before the final exit state instead of stopping after a shallow two-step cancellation shortcut."
        ),
        "distinctness_rule": (
            "Either open a direct support contact on the recent order, request the refund, and then cancel the subscription, "
            "or reach customer service first, cancel the subscription next, and only then resolve the refund route to the same exited state."
        ),
        "paths": [
            (
                "path_contact_refund_cancel",
                [
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_SUBSCRIPTION_REFUND",
                    "MODULE_CANCEL_SUBSCRIPTION",
                ],
            ),
            (
                "path_service_cancel_refund",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_CANCEL_SUBSCRIPTION",
                    "MODULE_SUBSCRIPTION_REFUND",
                ],
            ),
        ],
    },
    "BP_SUPPORT_REFUND_ESCALATION": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_SUBSCRIPTION_EXIT_CONTACT": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_CONTACT_CANCEL_BRIDGE": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_WORKFLOW_SUBSCRIPTION_EXIT_CONTACT": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_REFUND_CONTACT": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_01_EXIT_CONTACT_DUAL": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_04_EXIT_CONTACT_DUAL": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_07_EXIT_CONTACT_DUAL": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_10_EXIT_CONTACT_DUAL": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_13_EXIT_CONTACT_DUAL": {
        "alias_of": "BP_SUPPORT_SUBSCRIPTION_EXIT_ESCALATION_HARDENED",
    },
    "BP_DAILY_RESALE_DISCOUNT_HARDENED": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": ["lease_active"],
        "target_state": [
            "daily_order_bundle_prepared",
            "order_price_secured",
            "resale_listing_activated",
        ],
        "instruction_templates": [
            "Finish the daily resale-discount workflow only after a daily order bundle is prepared, pricing is secured, and the resale listing is activated.",
            "Close the resale-discount route by preparing the bundle and discount layer before activating the resale listing."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; daily resale workflows should include explicit bundle preparation and discount handling before the resale outcome instead of stopping after a two-step shortcut."
        ),
        "distinctness_rule": (
            "Either prepare the bundle first, secure the discount next, and then activate the resale listing, "
            "or secure the discount first before taking the bundle-through-resale route to the same prepared outcome."
        ),
        "paths": [
            (
                "path_bundle_coupon_listing",
                [
                    "MODULE_GROCERY_RUN",
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_SECOND_HAND_ITEM_LISTING",
                ],
            ),
            (
                "path_coupon_bundle_sale",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_GROCERY_RUN",
                    "MODULE_SECOND_HAND_SALE",
                ],
            ),
        ],
    },
    "BP_DAILY_RESALE_DISCOUNT_STACK": {
        "alias_of": "BP_DAILY_RESALE_DISCOUNT_HARDENED",
    },
    "BP_DAILY_SERVICE_RESALE_HARDENED": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": ["lease_active"],
        "target_state": [
            "service_stack_prepared",
            "order_price_secured",
            "resale_listing_activated",
        ],
        "instruction_templates": [
            "Finish the daily service-resale workflow only after the service stack is prepared, pricing is secured, and the resale listing is activated.",
            "Close the service-resale route by coordinating the service layer and discount step before the resale listing goes live."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; service-resale daily workflows should include discount handling in between the service setup and resale outcome instead of stopping after a shallow bridge."
        ),
        "distinctness_rule": (
            "Either prepare the service stack first, secure pricing next, and then activate the resale listing, "
            "or start from the pricing layer before returning to the same prepared resale state through the service route."
        ),
        "paths": [
            (
                "path_service_coupon_listing",
                [
                    "MODULE_HOUSEKEEPING_BOOKING",
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_SECOND_HAND_ITEM_LISTING",
                ],
            ),
            (
                "path_coupon_service_sale",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_HOUSEKEEPING_BOOKING",
                    "MODULE_SECOND_HAND_SALE",
                ],
            ),
        ],
    },
    "BP_DAILY_SERVICE_RESALE_BRIDGE": {
        "alias_of": "BP_DAILY_SERVICE_RESALE_HARDENED",
    },
    "BP_DAILY_SERVICE_TICKET_HARDENED": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": ["lease_active"],
        "target_state": [
            "service_stack_prepared",
            "order_price_secured",
            "event_ticket_booked",
        ],
        "instruction_templates": [
            "Finish the daily ticket-service workflow only after the service stack is prepared, pricing is secured, and the event ticket is booked.",
            "Close the ticket-service route by coordinating the service and pricing steps before the event booking is finalized."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; ticket-service workflows should include an explicit pricing or coupon step before the final booking instead of ending after a two-step shortcut."
        ),
        "distinctness_rule": (
            "Either prepare the service stack first, secure pricing next, and then book the ticket, "
            "or start from the pricing layer before returning to the same booked service state through the event-ticket route."
        ),
        "paths": [
            (
                "path_service_coupon_movie",
                [
                    "MODULE_HOUSEKEEPING_BOOKING",
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_MOVIE_TICKETS",
                ],
            ),
            (
                "path_coupon_service_event",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_HOUSEKEEPING_BOOKING",
                    "MODULE_EVENT_TICKETS",
                ],
            ),
        ],
    },
    "BP_DAILY_TICKET_SERVICE_ALIGNMENT": {
        "alias_of": "BP_DAILY_SERVICE_TICKET_HARDENED",
    },
    "BP_DAILY_WORKFLOW_SERVICE_TICKET_SYNC": {
        "alias_of": "BP_DAILY_SERVICE_TICKET_HARDENED",
    },
    "BP_DAILY_TRACK_PRICE_DELIVERY_HARDENED": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "initial_world_state": ["bank_account_active", "shop_order_exists"],
        "target_state": [
            "order_followup_prepared",
            "order_price_secured",
            "delivery_visibility_confirmed",
            "shop_order_delivered",
        ],
        "instruction_templates": [
            "Finish the daily tracking workflow only after order follow-up is prepared, pricing is secured, delivery visibility is confirmed, and the order is marked delivered.",
            "Close the daily tracking route by handling follow-up and price protection before confirming final delivery visibility."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; tracking-oriented daily workflows should continue through delivery confirmation instead of stopping after a two-step price shortcut."
        ),
        "distinctness_rule": (
            "Either open order tracking first, secure price protection next, and then confirm delivery, "
            "or secure pricing before taking the tracking-through-delivery route to the same follow-up outcome."
        ),
        "paths": [
            (
                "path_track_price_arrival",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_PRICE_PROTECTION",
                    "MODULE_ORDER_ARRIVAL",
                ],
            ),
            (
                "path_coupon_track_arrival",
                [
                    "MODULE_COUPON_MANAGEMENT",
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                ],
            ),
        ],
    },
    "BP_DAILY_TRACK_PRICE_STACK": {
        "alias_of": "BP_DAILY_TRACK_PRICE_DELIVERY_HARDENED",
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND21_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND21_SPECS[alias]
        merged = {key: copy.deepcopy(value) for key, value in base.items() if key != "alias_of"}
        for key, value in spec.items():
            if key != "alias_of":
                merged[key] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(spec)


def main() -> None:
    generator = load_generator_module()
    modules_doc = load_json(generator.MODULE_LIBRARY)
    modules_by_id = {m["module_id"]: m for m in modules_doc["modules"]}
    bindings_doc = load_json(generator.BINDING_LIBRARY)
    bindings_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings_doc["bindings"]:
        bindings_by_module[binding["module_id"]].append(binding)
    requirements = load_json(generator.QUALITY_REQUIREMENTS)

    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc["blueprints"]
    global_lookup = build_global_step_lookup(blueprints)

    patched_blueprints: dict[str, dict[str, Any]] = {}
    validation_issues: list[str] = []

    for bp in blueprints:
        blueprint_id = bp["blueprint_id"]
        spec = resolve_spec(blueprint_id)
        if spec is None:
            continue

        local_lookup = base_step_lookup(bp.get("paths", []))
        allowed_shared_vars = set(bp.get("shared_variable_pools", {}).keys())
        target_state = spec["target_state"]

        bp["difficulty"] = spec["difficulty"]
        bp["max_steps"] = spec["max_steps"]
        bp["max_module_invocations"] = spec["max_module_invocations"]
        bp["target_state"] = copy.deepcopy(target_state)
        bp["instruction_templates"] = copy.deepcopy(spec["instruction_templates"])
        bp["visible_constraints"] = replace_preferred_outcomes(bp.get("visible_constraints", {}), target_state)
        bp["notes_template"] = spec["notes_template"]
        bp["distinctness_rule"] = spec["distinctness_rule"]
        if "initial_world_state" in spec:
            bp["initial_world_state"] = copy.deepcopy(spec["initial_world_state"])
        bp["paths"] = [
            build_path(
                local_lookup,
                global_lookup,
                allowed_shared_vars,
                path_id,
                module_ids,
            )
            for path_id, module_ids in spec["paths"]
        ]

        issues = generator.validate_blueprint(bp, modules_by_id, requirements)
        if issues:
            validation_issues.extend(issues)
        patched_blueprints[blueprint_id] = copy.deepcopy(bp)

    if validation_issues:
        raise SystemExit("round21 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    refreshed_counts = {"dev": 0, "test": 0, "train": 0}
    for split in ["dev", "test", "train"]:
        manifest = load_json(BATCH_ROOT / split / "manifest.json")
        for ref in manifest.get("goals", []):
            blueprint_id = ref["blueprint_id"]
            if blueprint_id not in patched_blueprints:
                continue

            blueprint = patched_blueprints[blueprint_id]
            rng = random.Random(stable_goal_seed(ref["goal_id"], blueprint_id))
            shared_vars = generator.sample_shared_variables(blueprint, rng)
            goal = generator.build_goal(ref["goal_id"], blueprint, shared_vars, rng)
            oracle = generator.build_oracle(
                ref["goal_id"],
                blueprint,
                modules_by_id,
                bindings_by_module,
                shared_vars,
            )
            save_json(BATCH_ROOT / split / ref["goal_file"], goal)
            save_json(BATCH_ROOT / split / ref["oracle_file"], oracle)
            refreshed_counts[split] += 1

    print(
        json.dumps(
            {
                "patched_blueprints": sorted(patched_blueprints),
                "patched_blueprint_count": len(patched_blueprints),
                "refreshed_counts": refreshed_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
