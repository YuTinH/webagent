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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round15".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND15_SPECS: dict[str, dict[str, Any]] = {
    "BP_HOME_DEVICE_STACK_HARDENED": {
        "difficulty": 5,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "utilities_active",
            "camera_config_verified",
            "home_device_readiness_confirmed",
            "home_service_monitored",
        ],
        "instruction_templates": [
            "Finish the home-device workflow only after utilities are active, the camera configuration is verified, device readiness is confirmed, and home monitoring is on record.",
            "Close the home setup route by activating utilities first, confirming device readiness next, and ending with the camera and monitoring checks verified.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; home-device readiness should include utility activation plus explicit monitoring verification instead of stopping after a shallow two-step setup."
        ),
        "distinctness_rule": (
            "Either activate utilities, configure the smart bulb, and then verify the camera, "
            "or activate utilities before reaching the same monitored home-device state through the firmware-update route."
        ),
        "paths": [
            (
                "path_utility_bulb_camera",
                [
                    "MODULE_UTILITY_SETUP",
                    "MODULE_SMART_BULB_SETUP",
                    "MODULE_CAMERA_CHECK",
                ],
            ),
            (
                "path_utility_firmware_camera",
                [
                    "MODULE_UTILITY_SETUP",
                    "MODULE_FIRMWARE_UPDATE",
                    "MODULE_CAMERA_CHECK",
                ],
            ),
        ],
    },
    "BP_HOME_CAMERA_FIRMWARE_STABILITY": {
        "alias_of": "BP_HOME_DEVICE_STACK_HARDENED",
    },
    "BP_HOME_DEVICE_READINESS": {
        "alias_of": "BP_HOME_DEVICE_STACK_HARDENED",
    },
    "BP_HOME_MONITORING_DEVICE_READINESS": {
        "alias_of": "BP_HOME_DEVICE_STACK_HARDENED",
    },
    "BP_HOME_UTILITY_DEVICE_READY": {
        "alias_of": "BP_HOME_DEVICE_STACK_HARDENED",
    },
    "BP_HOME_CONTROL_STACK_HARDENED": {
        "difficulty": 5,
        "max_steps": 46,
        "max_module_invocations": 4,
        "target_state": [
            "energy_control_configured",
            "camera_config_verified",
            "home_device_readiness_confirmed",
            "home_service_monitored",
        ],
        "instruction_templates": [
            "Finish the home-control workflow only after energy control is configured, the camera configuration is verified, device readiness is confirmed, and monitoring is active.",
            "Close the home-control route by setting the control layer first, verifying monitoring second, and ending with device readiness fully confirmed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; control-oriented home workflows should continue through camera and firmware verification instead of stopping after a two-step control shortcut."
        ),
        "distinctness_rule": (
            "Either configure the home through the smart-meter route, verify the camera, and then complete firmware readiness, "
            "or use the energy-optimization route before reaching the same monitored control state."
        ),
        "paths": [
            (
                "path_meter_camera_firmware",
                [
                    "MODULE_SMART_METER",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_FIRMWARE_UPDATE",
                ],
            ),
            (
                "path_optimize_camera_firmware",
                [
                    "MODULE_ENERGY_OPTIMIZE",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_FIRMWARE_UPDATE",
                ],
            ),
        ],
    },
    "BP_HOME_CONTROL_MONITOR_ALIGNMENT": {
        "alias_of": "BP_HOME_CONTROL_STACK_HARDENED",
    },
    "BP_HOME_CONTROL_READINESS_ALT": {
        "alias_of": "BP_HOME_CONTROL_STACK_HARDENED",
    },
    "BP_HOME_ENERGY_MONITOR_ALIGNMENT": {
        "alias_of": "BP_HOME_CONTROL_STACK_HARDENED",
    },
    "BP_HOME_MONITOR_READINESS_ALIGNMENT": {
        "alias_of": "BP_HOME_CONTROL_STACK_HARDENED",
    },
    "BP_HOME_WORKFLOW_CONTROL_READINESS": {
        "alias_of": "BP_HOME_CONTROL_STACK_HARDENED",
    },
    "BP_HOME_MONITOR_READY_DUAL_HARDENED": {
        "difficulty": 5,
        "max_steps": 58,
        "max_module_invocations": 5,
        "target_state": [
            "utilities_active",
            "camera_config_verified",
            "home_device_readiness_confirmed",
            "home_service_monitored",
        ],
        "instruction_templates": [
            "Finish the home-readiness workflow only after housing is secured, utilities are active, the camera configuration is verified, and device readiness is fully confirmed.",
            "Close the home-readiness route by securing housing first, activating utilities next, and ending with both camera verification and device readiness complete.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; zero-context home-readiness workflows should bootstrap housing and utilities before any monitoring or readiness steps."
        ),
        "distinctness_rule": (
            "Either secure housing, activate utilities, complete firmware readiness, and then verify the camera, "
            "or secure housing and activate utilities before reaching the same monitored readiness state through the smart-bulb route."
        ),
        "paths": [
            (
                "path_home_utility_firmware_camera",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_UTILITY_SETUP",
                    "MODULE_FIRMWARE_UPDATE",
                    "MODULE_CAMERA_CHECK",
                ],
            ),
            (
                "path_home_utility_bulb_camera",
                [
                    "MODULE_FIND_HOME",
                    "MODULE_UTILITY_SETUP",
                    "MODULE_SMART_BULB_SETUP",
                    "MODULE_CAMERA_CHECK",
                ],
            ),
        ],
    },
    "BP_HOME_MONITOR_READINESS_DUAL": {
        "alias_of": "BP_HOME_MONITOR_READY_DUAL_HARDENED",
    },
    "BP_HOME_ZTRAIN_01_MONITOR_READINESS_DUAL": {
        "alias_of": "BP_HOME_MONITOR_READY_DUAL_HARDENED",
    },
    "BP_HOME_ZTRAIN_04_MONITOR_READINESS_DUAL": {
        "alias_of": "BP_HOME_MONITOR_READY_DUAL_HARDENED",
    },
    "BP_HOME_ZTRAIN_07_MONITOR_READINESS_DUAL": {
        "alias_of": "BP_HOME_MONITOR_READY_DUAL_HARDENED",
    },
    "BP_HOME_ZTRAIN_10_MONITOR_READINESS_DUAL": {
        "alias_of": "BP_HOME_MONITOR_READY_DUAL_HARDENED",
    },
    "BP_HOME_ZTRAIN_13_MONITOR_READINESS_DUAL": {
        "alias_of": "BP_HOME_MONITOR_READY_DUAL_HARDENED",
    },
    "BP_HOME_MONITOR_THERMOSTAT": {
        "difficulty": 5,
        "max_steps": 56,
        "max_module_invocations": 5,
        "target_state": [
            "energy_control_configured",
            "camera_config_verified",
            "home_device_readiness_confirmed",
            "home_service_monitored",
            "thermostat_schedule_configured",
        ],
        "instruction_templates": [
            "Finish the thermostat workflow only after energy control is configured, the camera is verified, device readiness is confirmed, monitoring is active, and the thermostat schedule is configured.",
            "Close the home-control route by configuring energy control first, verifying devices next, and ending with the thermostat schedule already in place.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; thermostat workflows should include both monitoring verification and final device-readiness checks before the scheduling step."
        ),
        "distinctness_rule": (
            "Either configure the smart meter, verify the camera, complete firmware readiness, and then set the thermostat schedule, "
            "or use the energy-optimization route before reaching the same scheduled-and-monitored home-control outcome."
        ),
        "paths": [
            (
                "path_meter_camera_firmware_thermostat",
                [
                    "MODULE_SMART_METER",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_FIRMWARE_UPDATE",
                    "MODULE_THERMOSTAT_SCHEDULE",
                ],
            ),
            (
                "path_optimize_camera_firmware_thermostat",
                [
                    "MODULE_ENERGY_OPTIMIZE",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_FIRMWARE_UPDATE",
                    "MODULE_THERMOSTAT_SCHEDULE",
                ],
            ),
        ],
    },
    "BP_HOME_REPAIR_CONTROL": {
        "difficulty": 5,
        "max_steps": 56,
        "max_module_invocations": 5,
        "target_state": [
            "home_repair_requested",
            "energy_control_configured",
            "camera_config_verified",
            "home_device_readiness_confirmed",
            "home_service_monitored",
        ],
        "instruction_templates": [
            "Finish the repair-control workflow only after the repair is requested, energy control is configured, the camera is verified, and device readiness is confirmed.",
            "Close the home-repair route by filing the repair first, configuring control next, and ending with both monitoring and readiness fully verified.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; repair-control workflows should continue through actual monitoring and firmware checks instead of stopping after a shallow repair-plus-control pair."
        ),
        "distinctness_rule": (
            "Either request the repair, configure the smart meter, verify the camera, and then complete firmware readiness, "
            "or request the same repair before reaching the same monitored control state through the energy-optimization route."
        ),
        "paths": [
            (
                "path_repair_meter_camera_firmware",
                [
                    "MODULE_HOUSE_REPAIR",
                    "MODULE_SMART_METER",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_FIRMWARE_UPDATE",
                ],
            ),
            (
                "path_repair_optimize_camera_firmware",
                [
                    "MODULE_HOUSE_REPAIR",
                    "MODULE_ENERGY_OPTIMIZE",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_FIRMWARE_UPDATE",
                ],
            ),
        ],
    },
    "BP_HOME_REPAIR_MONITOR_HARDENED": {
        "difficulty": 5,
        "max_steps": 44,
        "max_module_invocations": 4,
        "target_state": [
            "home_repair_requested",
            "camera_config_verified",
            "home_device_readiness_confirmed",
            "home_service_monitored",
        ],
        "instruction_templates": [
            "Finish the home-repair monitoring workflow only after the repair is requested, the camera is verified, device readiness is confirmed, and monitoring is active.",
            "Close the repair-monitoring route by filing the repair first, verifying monitoring next, and ending with device readiness confirmed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; repair-monitoring workflows should include a real readiness step instead of stopping after a shallow repair-and-monitor pair."
        ),
        "distinctness_rule": (
            "Either request the repair, verify the camera, and then confirm device readiness through the smart-bulb route, "
            "or request the same repair before reaching the same monitored readiness state through the firmware-update route."
        ),
        "paths": [
            (
                "path_repair_camera_bulb",
                [
                    "MODULE_HOUSE_REPAIR",
                    "MODULE_CAMERA_CHECK",
                    "MODULE_SMART_BULB_SETUP",
                ],
            ),
            (
                "path_repair_firmware_camera",
                [
                    "MODULE_HOUSE_REPAIR",
                    "MODULE_FIRMWARE_UPDATE",
                    "MODULE_CAMERA_CHECK",
                ],
            ),
        ],
    },
    "BP_HOME_REPAIR_MONITORING_LOOP": {
        "alias_of": "BP_HOME_REPAIR_MONITOR_HARDENED",
    },
    "BP_HOME_REPAIR_MONITOR_ALIGNMENT": {
        "alias_of": "BP_HOME_REPAIR_MONITOR_HARDENED",
    },
    "BP_HOME_SERVICE_MONITORING": {
        "alias_of": "BP_HOME_REPAIR_MONITOR_HARDENED",
    },
    "BP_HOME_WORKFLOW_REPAIR_MONITOR": {
        "alias_of": "BP_HOME_REPAIR_MONITOR_HARDENED",
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND15_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND15_SPECS[alias]
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
        raise SystemExit("round15 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
