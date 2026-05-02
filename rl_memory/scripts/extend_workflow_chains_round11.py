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
    digest = hashlib.sha256(f"{goal_id}:{blueprint_id}:round11".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


ROUND11_SPECS: dict[str, dict[str, Any]] = {
    "BP_FINANCE_DISPUTE_TRIAGE_HARDENED": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "account_issue_triaged",
            "account_access_contained",
            "transaction_dispute_submitted",
        ],
        "instruction_templates": [
            "Finish the dispute workflow only after the account issue is triaged, access is contained, and the transaction dispute is submitted.",
            "Close the finance remediation route by triaging the issue first, containing access second, and ending with the dispute already on file.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; dispute remediation should include a real containment step before the final dispute filing."
        ),
        "distinctness_rule": (
            "Either review the balance, freeze the compromised card, and then file the dispute, "
            "or aggregate the bills before freezing the card and reaching the same disputed-and-contained outcome."
        ),
        "paths": [
            (
                "path_balance_freeze_dispute",
                [
                    "MODULE_CHECK_BALANCE",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_DISPUTE_TRANSACTION",
                ],
            ),
            (
                "path_bills_freeze_dispute",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_DISPUTE_TRANSACTION",
                ],
            ),
        ],
    },
    "BP_FINANCE_ACCOUNT_DISPUTE_TRIAGE": {
        "alias_of": "BP_FINANCE_DISPUTE_TRIAGE_HARDENED",
    },
    "BP_FINANCE_TRANSACTION_REMEDIATION": {
        "alias_of": "BP_FINANCE_DISPUTE_TRIAGE_HARDENED",
    },
    "BP_FINANCE_TRIAGE_READINESS_HARDENED": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "bank_account_active",
            "account_issue_triaged",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Finish the account-readiness workflow only after the bank account is active, the account issue is triaged, and the supporting receipt is archived.",
            "Close the finance-admin route by opening the account first, triaging the issue next, and ending with the receipt archived.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; account-readiness triage should include a recordkeeping step, "
            "not stop immediately after the first triage action."
        ),
        "distinctness_rule": (
            "Either open the bank account, review the balance, and then archive the receipt, "
            "or open the same account, aggregate the bills, and then reach the same triage-and-archive outcome."
        ),
        "paths": [
            (
                "path_open_balance_archive",
                [
                    "MODULE_BANK_OPENING",
                    "MODULE_CHECK_BALANCE",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_open_bills_archive",
                [
                    "MODULE_BANK_OPENING",
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
    "BP_FINANCE_ACCOUNT_TRIAGE_READINESS": {
        "alias_of": "BP_FINANCE_TRIAGE_READINESS_HARDENED",
    },
    "BP_FINANCE_TRIAGE_ARCHIVE_HARDENED": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "account_issue_triaged",
            "account_access_contained",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Finish the triage-archive workflow only after the issue is triaged, access is contained, and the receipt is archived.",
            "Close the finance recordkeeping route by triaging the issue first, containing access second, and ending with the receipt archived.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; archive-oriented triage should include a real containment step before the final receipt archival."
        ),
        "distinctness_rule": (
            "Either review the balance, freeze the compromised card, and then archive the receipt, "
            "or aggregate the bills before freezing the card and reaching the same contained-and-archived outcome."
        ),
        "paths": [
            (
                "path_balance_freeze_archive",
                [
                    "MODULE_CHECK_BALANCE",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_bills_freeze_archive",
                [
                    "MODULE_BILL_AGGREGATION",
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
    "BP_FINANCE_TRIAGE_RECEIPT_ALIGNMENT": {
        "alias_of": "BP_FINANCE_TRIAGE_ARCHIVE_HARDENED",
    },
    "BP_FINANCE_WORKFLOW_TRIAGE_ARCHIVE": {
        "alias_of": "BP_FINANCE_TRIAGE_ARCHIVE_HARDENED",
    },
    "BP_FINANCE_INVESTMENT_FUNDING": {
        "difficulty": 5,
        "max_steps": 36,
        "max_module_invocations": 4,
        "target_state": [
            "investment_account_active",
            "transfer_completed",
            "receipt_archived",
        ],
        "instruction_templates": [
            "Finish the investment-funding workflow only after the investment account is active, the transfer is completed, and the receipt is archived.",
            "Close the finance route by activating the investment path first, completing the transfer second, and ending with the receipt archived.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; investment funding should finish with a concrete archival step instead of stopping immediately after transfer."
        ),
        "distinctness_rule": (
            "Either activate the investment account, transfer the funds, and then archive the receipt, "
            "or use the growth-verification route before reaching the same funded-and-archived investment outcome."
        ),
        "paths": [
            (
                "path_account_transfer_archive",
                [
                    "MODULE_INVESTMENT_ACCOUNT",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
            (
                "path_growth_transfer_archive",
                [
                    "MODULE_INVESTMENT_GROWTH",
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_RECEIPT_ARCHIVING",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED": {
        "difficulty": 6,
        "max_steps": 42,
        "max_module_invocations": 4,
        "target_state": [
            "account_access_contained",
            "delivery_visibility_confirmed",
            "order_followup_prepared",
            "order_tracking_opened",
        ],
        "instruction_templates": [
            "Finish the access-followup workflow only after account access is contained, delivery visibility is confirmed, detailed tracking is opened, and the order followup is prepared.",
            "Close the composite recovery route by containing access first, confirming delivery visibility next, and ending with detailed tracking and followup prepared.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; access-followup workflows should include explicit order tracking after the access-containment step."
        ),
        "distinctness_rule": (
            "Either complete password recovery, use customer service, and then open detailed tracking, "
            "or contain the account through the lost-card route before reaching the same visibility-and-followup outcome."
        ),
        "paths": [
            (
                "path_recovery_service_tracking",
                [
                    "MODULE_PASSWORD_RECOVERY_E2E",
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_TRACK_ORDERS",
                ],
            ),
            (
                "path_freeze_service_tracking",
                [
                    "MODULE_LOST_CARD_FREEZE",
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_TRACK_ORDERS",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_ACCESS_FOLLOWUP_DUAL": {
        "alias_of": "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_02_ACCESS_FOLLOWUP_DUAL": {
        "alias_of": "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_05_ACCESS_FOLLOWUP_DUAL": {
        "alias_of": "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_08_ACCESS_FOLLOWUP_DUAL": {
        "alias_of": "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_11_ACCESS_FOLLOWUP_DUAL": {
        "alias_of": "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_14_ACCESS_FOLLOWUP_DUAL": {
        "alias_of": "BP_COMPOSITE_ACCESS_FOLLOWUP_HARDENED",
    },
    "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED": {
        "difficulty": 6,
        "max_steps": 42,
        "max_module_invocations": 4,
        "target_state": [
            "payment_stack_prepared",
            "delivery_visibility_confirmed",
            "order_tracking_opened",
        ],
        "instruction_templates": [
            "Finish the payment-visibility workflow only after the payment stack is prepared, delivery visibility is confirmed, and detailed tracking is opened.",
            "Close the composite payment route by preparing the payment stack first, confirming visibility next, and ending with detailed tracking opened.",
        ],
        "notes_template": (
            "Generated from {blueprint_id}; payment-visibility workflows should include detailed tracking after the visibility step."
        ),
        "distinctness_rule": (
            "Either prepare the payment stack through complex autopay, confirm delivery through order arrival, and then open detailed tracking, "
            "or transfer the funds before reaching the same tracking-and-visibility outcome through customer service."
        ),
        "paths": [
            (
                "path_autopay_arrival_tracking",
                [
                    "MODULE_COMPLEX_AUTOPAY",
                    "MODULE_ORDER_ARRIVAL",
                    "MODULE_TRACK_ORDERS",
                ],
            ),
            (
                "path_transfer_service_tracking",
                [
                    "MODULE_TRANSFER_FUNDS",
                    "MODULE_CUSTOMER_SERVICE",
                    "MODULE_TRACK_ORDERS",
                ],
            ),
        ],
    },
    "BP_COMPOSITE_PAYMENT_VISIBILITY_DUAL": {
        "alias_of": "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_01_PAYMENT_VISIBILITY_DUAL": {
        "alias_of": "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_04_PAYMENT_VISIBILITY_DUAL": {
        "alias_of": "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_07_PAYMENT_VISIBILITY_DUAL": {
        "alias_of": "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_10_PAYMENT_VISIBILITY_DUAL": {
        "alias_of": "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED",
    },
    "BP_COMPOSITE_ZTRAIN_13_PAYMENT_VISIBILITY_DUAL": {
        "alias_of": "BP_COMPOSITE_PAYMENT_VISIBILITY_HARDENED",
    },
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND11_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get("alias_of")
    if alias:
        base = ROUND11_SPECS[alias]
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
        raise SystemExit("round11 blueprint validation failed:\n- " + "\n- ".join(validation_issues))

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
