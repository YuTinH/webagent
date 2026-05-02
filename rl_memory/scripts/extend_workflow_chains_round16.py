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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round16".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND16_SPECS: dict[str, dict[str, Any]] = {
    "BP_EDUCATION_EVENT_ACCESS_CERTIFIED": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "skill_certified",
            "certificate_downloaded",
            "event_ticket_booked",
        ],
        "instruction_templates": [
            "Finish the campus-access workflow only after the skill credential is completed, the certificate is downloaded, and the event access ticket is booked.",
            "Close the student-access route by completing the credential first, downloading the certificate next, and ending with the event ticket booked.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; campus access should include actual credential issuance before the final ticket-booking step."
        ),
        "distinctness_rule": (
            "Either complete skill certification, download the certificate, and then book the event ticket, "
            "or complete the same certification flow before reaching the same certified-access outcome through the movie-ticket route."
        ),
        "paths": [
            (
                "path_skill_cert_event",
                [
                    "MODULE_SKILL_CERTIFICATION",
                    "MODULE_DOWNLOAD_CERT",
                    "MODULE_EVENT_TICKETS",
                ],
            ),
            (
                "path_skill_cert_movie",
                [
                    "MODULE_SKILL_CERTIFICATION",
                    "MODULE_DOWNLOAD_CERT",
                    "MODULE_MOVIE_TICKETS",
                ],
            ),
        ],
    },
    "BP_EDUCATION_CAMPUS_EVENT_ACCESS": {
        "alias_of": "BP_EDUCATION_EVENT_ACCESS_CERTIFIED",
    },
    "BP_EDUCATION_CREDENTIAL_READY": {
        "difficulty": 5,
        "max_steps": 40,
        "max_module_invocations": 4,
        "target_state": [
            "certificate_downloaded",
            "event_ticket_booked",
        ],
        "instruction_templates": [
            "Finish the credential workflow only after the certificate is downloaded and the event access ticket is booked.",
            "Close the credential route by securing the qualifying certificate first and ending with the event ticket already booked.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; credential readiness should not stop at certificate download, but continue through a concrete access step."
        ),
        "distinctness_rule": (
            "Either enroll in the course, download the certificate, and then book the event ticket, "
            "or use direct skill certification before reaching the same certificate-and-access outcome through the movie-ticket route."
        ),
        "paths": [
            (
                "path_course_cert_event",
                [
                    "MODULE_COURSE_ENROLLMENT",
                    "MODULE_DOWNLOAD_CERT",
                    "MODULE_EVENT_TICKETS",
                ],
            ),
            (
                "path_skill_cert_movie",
                [
                    "MODULE_SKILL_CERTIFICATION",
                    "MODULE_DOWNLOAD_CERT",
                    "MODULE_MOVIE_TICKETS",
                ],
            ),
        ],
    },
    "BP_EDUCATION_COURSE_RESOURCE_STACK": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "target_state": [
            "course_enrolled",
            "assignment_resources_provisioned",
            "certificate_downloaded",
        ],
        "instruction_templates": [
            "Finish the course-resource workflow only after the course is enrolled, assignment resources are provisioned, and the certificate is downloaded.",
            "Close the education route by enrolling first, provisioning the study resources next, and ending with the certificate downloaded.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; course-resource workflows should continue through final credential download instead of stopping after a shallow resource step."
        ),
        "distinctness_rule": (
            "Either enroll in the course, buy the ebook, and then download the certificate, "
            "or enroll in the same course before reaching the same credential-ready study state through the library-service route."
        ),
        "paths": [
            (
                "path_course_ebook_cert",
                [
                    "MODULE_COURSE_ENROLLMENT",
                    "MODULE_BUY_EBOOK",
                    "MODULE_DOWNLOAD_CERT",
                ],
            ),
            (
                "path_course_library_cert",
                [
                    "MODULE_COURSE_ENROLLMENT",
                    "MODULE_LIBRARY_SERVICE",
                    "MODULE_DOWNLOAD_CERT",
                ],
            ),
        ],
    },
    "BP_EDUCATION_COURSE_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_READING_ACCESS": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_RESOURCE_COURSE": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_ZTRAIN_01_COURSE_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_ZTRAIN_04_COURSE_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_ZTRAIN_07_COURSE_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_ZTRAIN_10_COURSE_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_ZTRAIN_13_COURSE_RESOURCE_DUAL": {
        "alias_of": "BP_EDUCATION_COURSE_RESOURCE_STACK",
    },
    "BP_EDUCATION_RESOURCE_CERT_SUBMISSION_STACK": {
        "difficulty": 5,
        "max_steps": 44,
        "max_module_invocations": 4,
        "target_state": [
            "assignment_resources_provisioned",
            "certificate_downloaded",
            "assignment_submitted",
        ],
        "instruction_templates": [
            "Finish the study-completion workflow only after assignment resources are provisioned, the certificate is downloaded, and the assignment is submitted.",
            "Close the education workflow by provisioning the study resources first, downloading the certificate next, and ending with the assignment submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; study-completion workflows should continue through both credential download and final assignment submission."
        ),
        "distinctness_rule": (
            "Either provision the resources through library service, download the certificate, and then submit the assignment, "
            "or provision the same study path through ebook purchase before reaching the same certified submission outcome."
        ),
        "paths": [
            (
                "path_library_cert_submit",
                [
                    "MODULE_LIBRARY_SERVICE",
                    "MODULE_DOWNLOAD_CERT",
                    "MODULE_SUBMIT_ASSIGNMENT",
                ],
            ),
            (
                "path_ebook_cert_submit",
                [
                    "MODULE_BUY_EBOOK",
                    "MODULE_DOWNLOAD_CERT",
                    "MODULE_SUBMIT_ASSIGNMENT",
                ],
            ),
        ],
    },
    "BP_EDUCATION_RESOURCE_CERT": {
        "alias_of": "BP_EDUCATION_RESOURCE_CERT_SUBMISSION_STACK",
    },
    "BP_EDUCATION_RESOURCE_SUBMISSION_ALIGNMENT": {
        "alias_of": "BP_EDUCATION_RESOURCE_CERT_SUBMISSION_STACK",
    },
    "BP_EDUCATION_RESOURCE_RENTAL_SUBMISSION_STACK": {
        "difficulty": 5,
        "max_steps": 44,
        "max_module_invocations": 4,
        "target_state": [
            "assignment_resources_provisioned",
            "rental_listing_active",
            "assignment_submitted",
        ],
        "instruction_templates": [
            "Finish the resource-rental workflow only after assignment resources are provisioned, the rental listing is active, and the assignment is submitted.",
            "Close the education logistics route by provisioning resources first, activating the rental listing next, and ending with the assignment submitted.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; resource-rental workflows should continue through final assignment submission instead of stopping after a shallow provisioning step."
        ),
        "distinctness_rule": (
            "Either provision the resources through library service, activate the rental listing, and then submit the assignment, "
            "or use ebook purchase before reaching the same rental-backed submission outcome."
        ),
        "paths": [
            (
                "path_library_rental_submit",
                [
                    "MODULE_LIBRARY_SERVICE",
                    "MODULE_GEAR_RENTAL",
                    "MODULE_SUBMIT_ASSIGNMENT",
                ],
            ),
            (
                "path_ebook_rental_submit",
                [
                    "MODULE_BUY_EBOOK",
                    "MODULE_GEAR_RENTAL",
                    "MODULE_SUBMIT_ASSIGNMENT",
                ],
            ),
        ],
    },
    "BP_EDUCATION_RESOURCE_RENTAL_BRIDGE": {
        "alias_of": "BP_EDUCATION_RESOURCE_RENTAL_SUBMISSION_STACK",
    },
    "BP_EDUCATION_WORKFLOW_RESOURCE_RENTAL": {
        "alias_of": "BP_EDUCATION_RESOURCE_RENTAL_SUBMISSION_STACK",
    },
    "BP_EDUCATION_STUDY_EVENT_BRIDGE": {
        "difficulty": 5,
        "max_steps": 42,
        "max_module_invocations": 4,
        "target_state": [
            "assignment_resources_provisioned",
            "assignment_submitted",
            "event_ticket_booked",
        ],
        "instruction_templates": [
            "Finish the study-event workflow only after assignment resources are provisioned, the assignment is submitted, and the event ticket is booked.",
            "Close the student workflow by preparing study resources first, submitting the assignment next, and ending with the event ticket booked.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; study-event workflows should include actual assignment completion before the final event-access step."
        ),
        "distinctness_rule": (
            "Either provision the study resources through library service, submit the assignment, and then book the event ticket, "
            "or use ebook purchase before reaching the same academic-and-event outcome through the movie-ticket route."
        ),
        "paths": [
            (
                "path_library_submit_event",
                [
                    "MODULE_LIBRARY_SERVICE",
                    "MODULE_SUBMIT_ASSIGNMENT",
                    "MODULE_EVENT_TICKETS",
                ],
            ),
            (
                "path_ebook_submit_movie",
                [
                    "MODULE_BUY_EBOOK",
                    "MODULE_SUBMIT_ASSIGNMENT",
                    "MODULE_MOVIE_TICKETS",
                ],
            ),
        ],
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND16_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND16_SPECS[alias]
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
        raise SystemExit("round16 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
