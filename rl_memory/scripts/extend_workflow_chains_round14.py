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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round14".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND14_SPECS: dict[str, dict[str, Any]] = {
    "BP_SECURITY_AUDIT_SURFACE_BRIDGE": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "access_surface_reviewed",
            "two_factor_enabled",
            "security_audit_completed",
        ],
        "instruction_templates": [
            "Finish the audit-surface workflow only after the access surface is reviewed, two-factor is enabled, and the security audit is completed.",
            "Close the security review route by reviewing the access surface first, enabling two-factor next, and ending with the audit completed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; surface-review audits should include an explicit 2FA step before the final security audit."
        ),
        "distinctness_rule": (
            "Either review privacy settings, enable two-factor, and then run the security audit, "
            "or use the password-manager route before reaching the same reviewed-and-audited security outcome."
        ),
        "paths": [
            (
                "path_privacy_twofa_audit",
                [
                    "MODULE_PRIVACY_SETTINGS",
                    "MODULE_2FA_SETUP",
                    "MODULE_SECURITY_AUDIT",
                ],
            ),
            (
                "path_passwordmgr_twofa_audit",
                [
                    "MODULE_PASSWORD_MANAGER",
                    "MODULE_2FA_SETUP",
                    "MODULE_SECURITY_AUDIT",
                ],
            ),
        ],
    },
    "BP_SECURITY_EXIT_DELETION_HARDENED": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "target_state": [
            "account_exit_prepared",
            "access_surface_reviewed",
            "deletion_request_submitted",
        ],
        "instruction_templates": [
            "Finish the exit-deletion workflow only after account exit is prepared, the access surface is reviewed, and the deletion request is submitted.",
            "Close the security exit route by preparing exit first, reviewing the access surface next, and ending with the deletion request submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; exit-deletion workflows should include an explicit access-surface review before the deletion request is submitted."
        ),
        "distinctness_rule": (
            "Either export the account data, review the password manager, and then submit the deletion request, "
            "or prepare the exit through privacy settings before reaching the same reviewed-and-deleted outcome."
        ),
        "paths": [
            (
                "path_export_review_delete",
                [
                    "MODULE_DOWNLOAD_DATA",
                    "MODULE_PASSWORD_MANAGER",
                    "MODULE_DATA_DELETION",
                ],
            ),
            (
                "path_privacy_review_delete",
                [
                    "MODULE_PRIVACY_SETTINGS",
                    "MODULE_PASSWORD_MANAGER",
                    "MODULE_DATA_DELETION",
                ],
            ),
        ],
    },
    "BP_SECURITY_EXIT_DELETION_ALIGNMENT": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_EXIT_DELETION_DUAL": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_EXIT_PRIVACY_ALIGNMENT": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_EXPORT_DELETE_SEQUENCE": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_ZTRAIN_02_EXIT_DELETION_DUAL": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_ZTRAIN_05_EXIT_DELETION_DUAL": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_ZTRAIN_08_EXIT_DELETION_DUAL": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_ZTRAIN_11_EXIT_DELETION_DUAL": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_ZTRAIN_14_EXIT_DELETION_DUAL": {
        "alias_of": "BP_SECURITY_EXIT_DELETION_HARDENED",
    },
    "BP_SECURITY_TWOFA_HARDENING_HARDENED": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "access_surface_reviewed",
            "two_factor_enabled",
            "security_hardening_completed",
        ],
        "instruction_templates": [
            "Finish the 2FA-hardening workflow only after the access surface is reviewed, two-factor is enabled, and security hardening is completed.",
            "Close the security-hardening route by reviewing the surface first, enabling two-factor next, and ending with hardening completed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; 2FA-hardening workflows should include the final rotation-based hardening step."
        ),
        "distinctness_rule": (
            "Either review the password manager, enable two-factor, and then complete security rotation, "
            "or use the privacy-settings route before reaching the same hardened 2FA state."
        ),
        "paths": [
            (
                "path_passwordmgr_twofa_rotation",
                [
                    "MODULE_PASSWORD_MANAGER",
                    "MODULE_2FA_SETUP",
                    "MODULE_SECURITY_ROTATION",
                ],
            ),
            (
                "path_privacy_twofa_rotation",
                [
                    "MODULE_PRIVACY_SETTINGS",
                    "MODULE_2FA_SETUP",
                    "MODULE_SECURITY_ROTATION",
                ],
            ),
        ],
    },
    "BP_SECURITY_SURFACE_TWOFA_ALIGNMENT": {
        "alias_of": "BP_SECURITY_TWOFA_HARDENING_HARDENED",
    },
    "BP_SECURITY_TWOFA_HARDENING_BRIDGE": {
        "alias_of": "BP_SECURITY_TWOFA_HARDENING_HARDENED",
    },
    "BP_SECURITY_WORKFLOW_EXIT_SURFACE": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "account_exit_prepared",
            "access_surface_reviewed",
            "privacy_settings_updated",
        ],
        "instruction_templates": [
            "Finish the exit-surface workflow only after account exit is prepared, the access surface is reviewed, and privacy settings are updated.",
            "Close the security exit route by exporting the account first, updating privacy settings next, and ending with the access-surface review completed.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; exit-surface workflows should include a concrete privacy-settings update instead of stopping after a shallow export-and-review pair."
        ),
        "distinctness_rule": (
            "Complete export the account data, then review privacy settings, then review the password manager to reach the target."
        ),
        "paths": [
            (
                "path_export_privacy_review",
                [
                    "MODULE_DOWNLOAD_DATA",
                    "MODULE_PRIVACY_SETTINGS",
                    "MODULE_PASSWORD_MANAGER",
                ],
                "required",
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND14_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND14_SPECS[alias]
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
        bp["paths"] = []
        for path_spec in spec["paths"]:
            if len(path_spec) == 3:
                path_id, module_ids, kind = path_spec
            else:
                path_id, module_ids = path_spec
                kind = "alternative"
            bp["paths"].append(
                build_path(
                    local_lookup,
                    global_lookup,
                    allowed_shared_vars,
                    path_id,
                    module_ids,
                    kind=kind,
                )
            )

        issues = generator.validate_blueprint(bp, modules_by_id, requirements)
        if issues:
            validation_issues.extend(issues)
        patched_blueprints[blueprint_id] = copy.deepcopy(bp)

    if validation_issues:
        raise SystemExit("round14 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
