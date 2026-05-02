#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "tasks" / "workflow_generation_blueprints.json"
BATCH_ROOT = ROOT / "tasks" / "generated_workflow_split_batches" / "workflow_split_batch_v20"

# Round 4 hardening targets blueprints that still expose a shorter shortcut path
# while also having a longer, realistic path of at least 4 modules.
MIN_LONGEST_PATH_LEN = 4
TARGET_BLUEPRINT_IDS = {
    "BP_EDUCATION_CERT_RESOURCE_DUAL",
    "BP_EDUCATION_ZTRAIN_02_CERT_RESOURCE_DUAL",
    "BP_EDUCATION_ZTRAIN_05_CERT_RESOURCE_DUAL",
    "BP_EDUCATION_ZTRAIN_08_CERT_RESOURCE_DUAL",
    "BP_EDUCATION_ZTRAIN_11_CERT_RESOURCE_DUAL",
    "BP_EDUCATION_ZTRAIN_14_CERT_RESOURCE_DUAL",
    "BP_FINANCE_BILL_DISCIPLINE",
    "BP_GOVERNMENT_ZTRAIN_01_BP_GOV_ADDRESS_COMPLIANCE_DUAL",
    "BP_GOVERNMENT_ZTRAIN_02_BP_GOV_PERMIT_ADDRESS_DUAL",
    "BP_GOVERNMENT_ZTRAIN_03_BP_GOV_RENEWAL_REVIEW_DUAL",
    "BP_GOVERNMENT_ZTRAIN_04_BP_GOV_ADDRESS_COMPLIANCE_DUAL",
    "BP_GOVERNMENT_ZTRAIN_05_BP_GOV_PERMIT_ADDRESS_DUAL",
    "BP_GOVERNMENT_ZTRAIN_06_BP_GOV_RENEWAL_REVIEW_DUAL",
    "BP_GOVERNMENT_ZTRAIN_07_BP_GOV_ADDRESS_COMPLIANCE_DUAL",
    "BP_GOVERNMENT_ZTRAIN_08_BP_GOV_PERMIT_ADDRESS_DUAL",
    "BP_GOVERNMENT_ZTRAIN_09_BP_GOV_RENEWAL_REVIEW_DUAL",
    "BP_GOVERNMENT_ZTRAIN_10_BP_GOV_ADDRESS_COMPLIANCE_DUAL",
    "BP_GOVERNMENT_ZTRAIN_11_BP_GOV_PERMIT_ADDRESS_DUAL",
    "BP_GOVERNMENT_ZTRAIN_12_BP_GOV_RENEWAL_REVIEW_DUAL",
    "BP_GOVERNMENT_ZTRAIN_13_BP_GOV_ADDRESS_COMPLIANCE_DUAL",
    "BP_GOVERNMENT_ZTRAIN_14_BP_GOV_PERMIT_ADDRESS_DUAL",
    "BP_GOV_ADDRESS_COMPLIANCE_DUAL",
    "BP_GOV_ADDRESS_PERMIT_ALIGNMENT",
    "BP_GOV_BILL_ALIGNMENT",
    "BP_GOV_DRIVING_COMPLIANCE",
    "BP_GOV_PERMIT_ADDRESS_ALIGNMENT",
    "BP_GOV_PERMIT_ADDRESS_DUAL",
    "BP_GOV_PERMIT_APPLICATION_VERIFICATION",
    "BP_GOV_PERMIT_BILL_READINESS",
    "BP_GOV_PERMIT_LIFECYCLE",
    "BP_GOV_PERMIT_SUPPORTING_ALIGNMENT",
    "BP_GOV_PERMIT_VERIFICATION_BRIDGE",
    "BP_GOV_RENEWAL_REVIEW_DUAL",
    "BP_NEWCOMER_ADDRESS_LEASE_FINANCE_SYNC",
    "BP_NEWCOMER_BANK_ADDRESS_ALIGNMENT",
    "BP_SECURITY_ACCOUNT_RECOVERY",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def extract_blueprint_id(notes: str) -> str | None:
    match = re.search(r"Generated from ([A-Z0-9_]+);", notes or "")
    return match.group(1) if match else None


def path_steps(path: dict[str, Any]) -> list[str]:
    return [step.get("module_id") for step in path.get("steps", []) if step.get("module_id")]


def describe_steps(steps: list[str]) -> str:
    phrases = [MODULE_ACTIONS.get(step, step) for step in steps]
    if not phrases:
        return "complete the workflow"
    if len(phrases) == 1:
        return phrases[0]
    return ", then ".join(phrases)


def compose_distinctness_rule(paths: list[list[str]]) -> str:
    if not paths:
        return "Complete the workflow to reach the target."
    if len(paths) == 1:
        return f"Complete {describe_steps(paths[0])} to reach the target."
    rendered = [describe_steps(path) for path in paths]
    return "Either " + ", or ".join(rendered) + " to reach the same target."


def compose_goal_note(blueprint_id: str, paths: list[list[str]]) -> str:
    if len(paths) == 1:
        body = f"Complete {describe_steps(paths[0])} after removing the shorter shortcut routes."
    else:
        rendered = [describe_steps(path) for path in paths]
        body = "Only the longer route variants remain: either " + ", or ".join(rendered) + "."
    return f"Generated from {blueprint_id}; {body}"


def used_modules_from_oracle(oracle: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for path in oracle.get("success_paths", []):
        used |= set(path.get("required_modules", []))
        used |= set(path.get("optional_modules", []))
    for invocation in oracle.get("reference_invocations", []):
        module_id = invocation.get("module_id")
        if module_id:
            used.add(module_id)
    return used


MODULE_ACTIONS = {
    "MODULE_2FA_DEVICE": "update the replacement 2FA device",
    "MODULE_2FA_SETUP": "re-enable 2FA",
    "MODULE_ADDRESS_CHANGE": "submit the address change",
    "MODULE_ADDRESS_PROOF": "collect address proof",
    "MODULE_AUTOPAY": "enable standard autopay",
    "MODULE_BANK_OPENING": "activate the bank account",
    "MODULE_BILLING_REVIEW": "review current bills",
    "MODULE_BILL_AGGREGATION": "aggregate the bills",
    "MODULE_BUY_EBOOK": "buy the ebook",
    "MODULE_BUDGET_LIMIT_UPDATE": "tighten the budget limit",
    "MODULE_COMPLEX_AUTOPAY": "finish complex autopay setup",
    "MODULE_COURSE_ENROLLMENT": "enroll in the course",
    "MODULE_DOWNLOAD_CERT": "download the certificate",
    "MODULE_FIND_HOME": "secure housing",
    "MODULE_LIBRARY_SERVICE": "prepare the library resources",
    "MODULE_PARKING_PERMIT_APPLICATION": "submit the parking permit application",
    "MODULE_PASSWORD_RECOVERY_E2E": "complete end-to-end recovery",
    "MODULE_PASSWORD_RESET_COMPLETION": "finish the password reset",
    "MODULE_PASSWORD_RESET_REQUEST": "start the password reset",
    "MODULE_PERMIT_RENEWAL": "complete permit renewal",
    "MODULE_RENEW_PERMIT": "renew the permit",
    "MODULE_SKILL_CERTIFICATION": "finish skill certification",
    "MODULE_UTILITY_SETUP": "activate utilities",
    "MODULE_VEHICLE_ADDRESS_UPDATE": "update the vehicle address",
}


def main() -> None:
    blueprints_doc = load_json(BLUEPRINTS_PATH)
    blueprints = blueprints_doc["blueprints"]

    patched_blueprints: dict[str, dict[str, Any]] = {}
    for bp in blueprints:
        blueprint_id = bp["blueprint_id"]
        if blueprint_id not in TARGET_BLUEPRINT_IDS:
            continue

        paths = bp.get("paths", [])
        if len(paths) < 2:
            # Already hardened to a single path on a previous round4 run.
            if paths and len(path_steps(paths[0])) >= MIN_LONGEST_PATH_LEN:
                remaining_steps = [path_steps(paths[0])]
                patched_blueprints[blueprint_id] = {
                    "removed_path_ids": [],
                    "kept_path_ids": [paths[0]["path_id"]],
                    "remaining_steps": remaining_steps,
                    "longest_len": len(remaining_steps[0]),
                    "shortest_len": len(remaining_steps[0]),
                }
            continue

        annotated_paths: list[tuple[dict[str, Any], list[str]]] = []
        lengths: list[int] = []
        for path in paths:
            steps = path_steps(path)
            if not steps:
                continue
            annotated_paths.append((path, steps))
            lengths.append(len(steps))

        if len(lengths) < 2:
            continue

        shortest_len = min(lengths)
        longest_len = max(lengths)
        if longest_len < MIN_LONGEST_PATH_LEN:
            continue

        kept = [(path, steps) for path, steps in annotated_paths if len(steps) == longest_len]
        removed = [(path, steps) for path, steps in annotated_paths if len(steps) < longest_len]
        if not kept:
            continue

        if removed:
            bp["paths"] = [path for path, _ in kept]
        remaining_steps = [steps for _, steps in kept]
        bp["distinctness_rule"] = compose_distinctness_rule(remaining_steps)
        bp["notes_template"] = bp["distinctness_rule"]
        patched_blueprints[blueprint_id] = {
            "removed_path_ids": [path["path_id"] for path, _ in removed],
            "kept_path_ids": [path["path_id"] for path, _ in kept],
            "remaining_steps": remaining_steps,
            "longest_len": longest_len,
            "shortest_len": shortest_len,
        }

    save_json(BLUEPRINTS_PATH, blueprints_doc)

    patched_goals = 0
    patched_oracles = 0
    for split in ["dev", "test", "train"]:
        manifest = load_json(BATCH_ROOT / split / "manifest.json")
        for ref in manifest.get("goals", []):
            goal_path = BATCH_ROOT / split / ref["goal_file"]
            oracle_path = BATCH_ROOT / split / ref["oracle_file"]

            goal = load_json(goal_path)
            blueprint_id = extract_blueprint_id(goal.get("notes", ""))
            if blueprint_id not in patched_blueprints:
                continue

            patch = patched_blueprints[blueprint_id]
            goal["notes"] = compose_goal_note(blueprint_id, patch["remaining_steps"])
            save_json(goal_path, goal)
            patched_goals += 1

            oracle = load_json(oracle_path)
            oracle["success_paths"] = [
                path for path in oracle.get("success_paths", [])
                if path.get("path_id") in patch["kept_path_ids"]
            ]
            kept_invocation_ids = {
                invocation_id
                for path in oracle.get("success_paths", [])
                for invocation_id in path.get("reference_invocation_ids", [])
            }
            oracle["reference_invocations"] = [
                inv for inv in oracle.get("reference_invocations", [])
                if inv.get("invocation_id") in kept_invocation_ids
            ]
            remaining_steps = [path.get("required_modules", []) for path in oracle.get("success_paths", [])]
            oracle.setdefault("composition", {})["composition_type"] = (
                "single_path" if len(remaining_steps) == 1 else "multi_path"
            )
            oracle["composition"]["num_semantically_distinct_paths"] = len(remaining_steps)
            oracle["composition"]["distinctness_rule"] = compose_distinctness_rule(remaining_steps)

            used_modules = used_modules_from_oracle(oracle)
            oracle["module_nodes"] = [
                node for node in oracle.get("module_nodes", [])
                if node.get("module_id") in used_modules
            ]
            oracle["dependency_edges"] = [
                edge for edge in oracle.get("dependency_edges", [])
                if edge.get("from") in used_modules and edge.get("to") in used_modules
            ]
            save_json(oracle_path, oracle)
            patched_oracles += 1

    print(
        json.dumps(
            {
                "min_longest_path_len": MIN_LONGEST_PATH_LEN,
                "patched_blueprints": len(patched_blueprints),
                "patched_goals": patched_goals,
                "patched_oracles": patched_oracles,
                "blueprint_ids": sorted(patched_blueprints),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
