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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round23".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND23_SPECS: dict[str, dict[str, Any]] = {
    "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED": {
        "difficulty": 6,
        "max_steps": 48,
        "max_module_invocations": 5,
        "initial_world_state": ["shop_order_exists"],
        "target_state": [
            "delivery_visibility_confirmed",
            "shop_order_delivered",
            "support_contacted",
            "product_review_submitted",
            "merchant_blacklisted",
        ],
        "instruction_templates": [
            "Finish the review-support workflow only after delivery visibility is confirmed, the order is delivered, support is contacted, a product review is submitted, and the merchant is blacklisted.",
            "Close the review-support route by confirming delivery first, escalating support next, and only then finishing the review and blacklist actions."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; review-oriented support workflows should continue through delivery confirmation before the support and review escalation instead of stopping after a short post-delivery shortcut."
        ),
        "distinctness_rule": (
            "Either confirm delivery, contact support, and then complete the review-blacklist sequence, "
            "or confirm delivery before reaching the same reviewed-and-blacklisted support outcome through the logistics route."
        ),
        "paths": [
            (
                "path_arrival_contact_review_blacklist",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_LEAVE_REVIEW",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
            (
                "path_arrival_logistics_review_blacklist",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_LOGISTICS_FIX",
                    "MODULE_LEAVE_REVIEW",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
        ],
    },
    "BP_SUPPORT_REVIEW_CONTACT_BRIDGE": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_REVIEW_CONTACT_ALIGNMENT": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_REVIEW_CONTACT": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_REVIEW_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_03_REVIEW_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_06_REVIEW_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_09_REVIEW_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_ZTRAIN_12_REVIEW_SUPPORT_DUAL": {
        "alias_of": "BP_SUPPORT_REVIEW_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_VISIBILITY_REVIEW_SUPPORT_HARDENED": {
        "difficulty": 6,
        "max_steps": 50,
        "max_module_invocations": 5,
        "initial_world_state": ["shop_order_exists"],
        "target_state": [
            "order_followup_prepared",
            "delivery_visibility_confirmed",
            "shop_order_delivered",
            "support_contacted",
            "product_review_submitted",
            "merchant_blacklisted",
        ],
        "instruction_templates": [
            "Finish the visibility-escalation workflow only after order follow-up is prepared, delivery visibility is confirmed, the order is delivered, support is contacted, a product review is submitted, and the merchant is blacklisted.",
            "Close the visibility route by preparing follow-up and delivery confirmation before the support, review, and blacklist escalation is complete."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; visibility-oriented support workflows should include order follow-up and explicit review escalation instead of ending after a shallow delivery-support shortcut."
        ),
        "distinctness_rule": (
            "Either open order tracking, confirm delivery, and then finish the support-blacklist sequence, "
            "or reach customer service first before taking the arrival-through-review route to the same visibility-resolved outcome."
        ),
        "paths": [
            (
                "path_track_arrival_support_blacklist",
                [
                    "MODULE_TRACK_ORDERS",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
            (
                "path_service_arrival_review_blacklist",
                [
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_LEAVE_REVIEW",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
        ],
    },
    "BP_SUPPORT_DELIVERED_ESCALATION": {
        "alias_of": "BP_SUPPORT_VISIBILITY_REVIEW_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_VISIBILITY_CONTACT_ALIGNMENT": {
        "alias_of": "BP_SUPPORT_VISIBILITY_REVIEW_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_WORKFLOW_VISIBILITY_BLACKLIST": {
        "alias_of": "BP_SUPPORT_VISIBILITY_REVIEW_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_REMEDY_DELIVERY_SUPPORT_HARDENED": {
        "difficulty": 6,
        "max_steps": 50,
        "max_module_invocations": 5,
        "initial_world_state": ["shop_order_exists"],
        "target_state": [
            "delivery_visibility_confirmed",
            "shop_order_delivered",
            "support_contacted",
            "post_purchase_remedy_requested",
            "product_review_submitted",
            "merchant_blacklisted",
        ],
        "instruction_templates": [
            "Finish the remedy-support workflow only after delivery visibility is confirmed, the order is delivered, support is contacted, a post-purchase remedy is requested, a product review is submitted, and the merchant is blacklisted.",
            "Close the remedy-support route by confirming delivery first, escalating remedy handling next, and only then finishing the review and blacklist actions."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; remedy-oriented support workflows should continue through delivery confirmation before the support and remedy escalation instead of stopping after a short post-delivery shortcut."
        ),
        "distinctness_rule": (
            "Either confirm delivery, contact support, and then complete the return-blacklist route, "
            "or confirm delivery before reaching the same remedied-and-blacklisted support outcome through the logistics warranty route."
        ),
        "paths": [
            (
                "path_arrival_contact_return_blacklist",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_CONTACT_SUPPORT",
                    "MODULE_RETURN",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
            (
                "path_arrival_logistics_warranty_blacklist",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_LOGISTICS_FIX",
                    "MODULE_WARRANTY_CLAIM",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
        ],
    },
    "BP_SUPPORT_ORDER_REMEDIATION": {
        "alias_of": "BP_SUPPORT_REMEDY_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_REMEDY_CONTACT_ALIGNMENT": {
        "alias_of": "BP_SUPPORT_REMEDY_DELIVERY_SUPPORT_HARDENED",
    },
    "BP_SUPPORT_REMEDY_FEEDBACK_DELIVERY_HARDENED": {
        "difficulty": 6,
        "max_steps": 48,
        "max_module_invocations": 5,
        "initial_world_state": ["shop_order_exists"],
        "target_state": [
            "delivery_visibility_confirmed",
            "shop_order_delivered",
            "post_purchase_remedy_requested",
            "product_review_submitted",
            "merchant_blacklisted",
        ],
        "instruction_templates": [
            "Finish the remedy-feedback workflow only after delivery visibility is confirmed, the order is delivered, a post-purchase remedy is requested, a product review is submitted, and the merchant is blacklisted.",
            "Close the remedy-feedback route by confirming delivery first, opening the remedy next, and only then finishing the review and blacklist actions."
        ],
        "notes_template": (
            "Generated from {blueprint_id}; remedy-feedback workflows should continue through delivery confirmation before the remedy and review escalation instead of stopping after a shallow post-delivery shortcut."
        ),
        "distinctness_rule": (
            "Either confirm delivery, request a return remedy, and then complete the review-blacklist sequence, "
            "or confirm delivery before reaching the same reviewed-and-blacklisted remedy outcome through the warranty route."
        ),
        "paths": [
            (
                "path_arrival_return_review_blacklist",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_RETURN",
                    "MODULE_LEAVE_REVIEW",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
            (
                "path_arrival_warranty_review_blacklist",
                [
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_WARRANTY_CLAIM",
                    "MODULE_LEAVE_REVIEW",
                    "MODULE_REVIEWS_BLACKLIST",
                ],
            ),
        ],
    },
    "BP_SUPPORT_WARRANTY_ESCALATION": {
        "alias_of": "BP_SUPPORT_REMEDY_FEEDBACK_DELIVERY_HARDENED",
    },
    "BP_SUPPORT_RETURN_FEEDBACK_RESOLUTION": {
        "alias_of": "BP_SUPPORT_REMEDY_FEEDBACK_DELIVERY_HARDENED",
    },
    "BP_SUPPORT_REMEDY_BLACKLIST": {
        "alias_of": "BP_SUPPORT_REMEDY_FEEDBACK_DELIVERY_HARDENED",
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND23_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND23_SPECS[alias]
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
        raise SystemExit("round23 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
