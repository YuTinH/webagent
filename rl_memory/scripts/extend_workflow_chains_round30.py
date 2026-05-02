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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round30'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


ROUND30_SPECS: dict[str, dict[str, Any]] = {
    'BP_FINANCE_DISPUTE_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'account_issue_triaged',
            'account_access_contained',
            'transaction_dispute_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the dispute-remediation packet only after the account issue is triaged, access is contained, the transaction dispute is submitted, and the receipt record is archived.',
            'Close the account-dispute workflow by triaging the issue, freezing exposure, submitting the dispute, and archiving the supporting receipt trail.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; dispute-oriented finance tasks should continue through evidence archiving rather than stopping at the dispute submission.'
        ),
        'distinctness_rule': (
            'Either triage through balance checking before freeze, dispute, and receipt archiving, '
            'or start from bill aggregation before the same freeze, dispute, and archive closure.'
        ),
        'paths': [
            (
                'path_balance_freeze_dispute_archive',
                [
                    'MODULE_CHECK_BALANCE',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_DISPUTE_TRANSACTION',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bills_freeze_dispute_archive',
                [
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_DISPUTE_TRANSACTION',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_ACCOUNT_DISPUTE_TRIAGE': {'alias_of': 'BP_FINANCE_DISPUTE_PACKET'},
    'BP_FINANCE_TRANSACTION_REMEDIATION': {'alias_of': 'BP_FINANCE_DISPUTE_PACKET'},
    'BP_FINANCE_REPLACEMENT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'account_issue_triaged',
            'account_access_contained',
            'replacement_card_requested',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the card-replacement packet only after the account issue is triaged, access is contained, the replacement card is requested, and the receipt record is archived.',
            'Close the card-remediation workflow by triaging the issue, freezing exposure, requesting a replacement card, and archiving the supporting receipt trail.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; replacement-oriented finance tasks should continue through documentation archiving rather than stopping once the replacement is requested.'
        ),
        'distinctness_rule': (
            'Either triage through balance checking before freeze, replacement, and receipt archiving, '
            'or start from bill aggregation before the same freeze, replacement, and archive closure.'
        ),
        'paths': [
            (
                'path_balance_freeze_replace_archive',
                [
                    'MODULE_CHECK_BALANCE',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bills_freeze_replace_archive',
                [
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_CARD_TRIAGE_REPLACEMENT': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_TRIAGE_REPLACEMENT': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_TRIAGE_REPLACEMENT_ALIGNMENT': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_TRIAGE_REPLACEMENT_DUAL': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_01_TRIAGE_REPLACEMENT_DUAL': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_04_TRIAGE_REPLACEMENT_DUAL': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_07_TRIAGE_REPLACEMENT_DUAL': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_10_TRIAGE_REPLACEMENT_DUAL': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_13_TRIAGE_REPLACEMENT_DUAL': {'alias_of': 'BP_FINANCE_REPLACEMENT_PACKET'},
    'BP_FINANCE_TRIAGE_ARCHIVE_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'account_issue_triaged',
            'account_access_contained',
            'transaction_dispute_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the triage-archive packet only after the account issue is triaged, access is contained, the related dispute is submitted, and the receipt trail is archived.',
            'Close the account-archive workflow by triaging the issue, freezing exposure, submitting the dispute, and archiving the supporting receipt evidence.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; archive-oriented finance tasks should still require a concrete remediation step before the archive is considered complete.'
        ),
        'distinctness_rule': (
            'Either triage through balance checking before freeze, dispute, and receipt archiving, '
            'or start from bill aggregation before the same freeze, dispute, and archive closure.'
        ),
        'paths': [
            (
                'path_balance_freeze_dispute_archive',
                [
                    'MODULE_CHECK_BALANCE',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_DISPUTE_TRANSACTION',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bills_freeze_dispute_archive',
                [
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_LOST_CARD_FREEZE',
                    'MODULE_DISPUTE_TRANSACTION',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_TRIAGE_RECEIPT_ALIGNMENT': {'alias_of': 'BP_FINANCE_TRIAGE_ARCHIVE_PACKET'},
    'BP_FINANCE_WORKFLOW_TRIAGE_ARCHIVE': {'alias_of': 'BP_FINANCE_TRIAGE_ARCHIVE_PACKET'},
    'BP_FINANCE_ACCOUNT_READINESS_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'account_issue_triaged',
            'receipt_archived',
            'budget_limit_updated',
        ],
        'instruction_templates': [
            'Finish the account-readiness packet only after the bank account is opened, the issue is triaged, the receipt trail is archived, and the budget limit is updated.',
            'Close the finance-readiness workflow by opening the account, triaging the account state, archiving the receipt trail, and updating the budget limit.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; readiness-oriented finance tasks should carry through account setup and a concrete post-triage follow-up step.'
        ),
        'distinctness_rule': (
            'Either open the bank account and triage through balance checking before receipt archiving and budget update, '
            'or open the account and triage through bill aggregation before the same archive-and-budget closure.'
        ),
        'paths': [
            (
                'path_open_balance_archive_budget',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_CHECK_BALANCE',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                ],
            ),
            (
                'path_open_bills_archive_budget',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_RECEIPT_ARCHIVING',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                ],
            ),
        ],
    },
    'BP_FINANCE_ACCOUNT_TRIAGE_READINESS': {'alias_of': 'BP_FINANCE_ACCOUNT_READINESS_PACKET'},
    'BP_FINANCE_FUNDING_INVESTMENT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'tax_funding_prepared',
            'investment_account_active',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the funding-investment packet only after the bank account is opened, tax funding is prepared, the investment account is active, and the receipt trail is archived.',
            'Close the capital-setup workflow by opening the account, preparing the funding path, activating the investment account, and archiving the related receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; capital-setup finance tasks should include post-activation documentation rather than stopping immediately after investment activation.'
        ),
        'distinctness_rule': (
            'Either open the account and prepare funding through tax preparation before investment activation and receipt archiving, '
            'or open the account and use the transfer-funding path before the same investment-and-archive closure.'
        ),
        'paths': [
            (
                'path_open_tax_invest_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TAX_PREPARATION',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_open_transfer_invest_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_FUNDING_INVESTMENT_DUAL': {'alias_of': 'BP_FINANCE_FUNDING_INVESTMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_02_FUNDING_INVESTMENT_DUAL': {'alias_of': 'BP_FINANCE_FUNDING_INVESTMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_05_FUNDING_INVESTMENT_DUAL': {'alias_of': 'BP_FINANCE_FUNDING_INVESTMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_08_FUNDING_INVESTMENT_DUAL': {'alias_of': 'BP_FINANCE_FUNDING_INVESTMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_11_FUNDING_INVESTMENT_DUAL': {'alias_of': 'BP_FINANCE_FUNDING_INVESTMENT_PACKET'},
    'BP_FINANCE_ZTRAIN_14_FUNDING_INVESTMENT_DUAL': {'alias_of': 'BP_FINANCE_FUNDING_INVESTMENT_PACKET'},
    'BP_FINANCE_OPEN_INVEST_BUDGET_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'investment_account_active',
            'budget_limit_updated',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the investment-budget packet only after the bank account is opened, the investment account is active, the budget limit is updated, and the receipt trail is archived.',
            'Close the investment-budget workflow by opening the account, activating the investment path, updating the budget limit, and archiving the supporting receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; investment-budget tasks that begin from lease setup should carry through account opening and post-update documentation.'
        ),
        'distinctness_rule': (
            'Either open the account and activate investment directly before budget update and receipt archiving, '
            'or open the account and verify investment growth before the same budget-and-archive closure.'
        ),
        'paths': [
            (
                'path_open_invest_budget_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_open_growth_budget_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_INVESTMENT_BUDGET_ALIGNMENT': {'alias_of': 'BP_FINANCE_OPEN_INVEST_BUDGET_PACKET'},
    'BP_FINANCE_ACTIVE_INVESTMENT_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'investment_account_active',
            'transfer_completed',
            'budget_limit_updated',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the active-investment packet only after the investment account is active, the transfer is completed, the budget limit is updated, and the receipt trail is archived.',
            'Close the investment-funding workflow by activating the investment path, completing the transfer, updating the budget limit, and archiving the supporting receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; active-account investment workflows should include a post-transfer budgeting step and documentation rather than ending after the transfer.'
        ),
        'distinctness_rule': (
            'Either activate investment directly before transfer, budget update, and receipt archiving, '
            'or use the investment-growth route before the same transfer, budget, and archive closure.'
        ),
        'paths': [
            (
                'path_invest_transfer_budget_archive',
                [
                    'MODULE_INVESTMENT_ACCOUNT',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_growth_transfer_budget_archive',
                [
                    'MODULE_INVESTMENT_GROWTH',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_INVESTMENT_FUNDING': {'alias_of': 'BP_FINANCE_ACTIVE_INVESTMENT_PACKET'},
    'BP_FINANCE_TRANSFER_INVESTMENT': {'alias_of': 'BP_FINANCE_ACTIVE_INVESTMENT_PACKET'},
    'BP_FINANCE_WORKFLOW_INVESTMENT_BUDGET': {'alias_of': 'BP_FINANCE_ACTIVE_INVESTMENT_PACKET'},
    'BP_FINANCE_TAX_FILING_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['lease_active'],
        'target_state': [
            'bank_account_active',
            'tax_funding_prepared',
            'tax_filing_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the tax-filing packet only after the bank account is opened, tax funding is prepared, the tax filing is submitted, and the receipt trail is archived.',
            'Close the filing workflow by opening the account, preparing the funding path, submitting the filing, and archiving the supporting receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; filing-oriented finance tasks should include documentation after filing rather than stopping at submission.'
        ),
        'distinctness_rule': (
            'Either open the account and prepare funding through transfer before filing and receipt archiving, '
            'or open the account and prepare funding through tax preparation before the same filing-and-archive closure.'
        ),
        'paths': [
            (
                'path_open_transfer_file_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_FILE_TAXES',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_open_tax_file_archive',
                [
                    'MODULE_BANK_OPENING',
                    'MODULE_TAX_PREPARATION',
                    'MODULE_FILE_TAXES',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_TAX_FILING_FUNDING': {'alias_of': 'BP_FINANCE_TAX_FILING_PACKET'},
    'BP_FINANCE_TAX_FUNDING_ALIGNMENT': {'alias_of': 'BP_FINANCE_TAX_FILING_PACKET'},
    'BP_FINANCE_BUDGET_FILING_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'budget_limit_updated',
            'tax_funding_prepared',
            'tax_filing_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the budget-filing packet only after the budget limit is updated, tax funding is prepared, the tax filing is submitted, and the receipt trail is archived.',
            'Close the tax-budget workflow by preparing funding, updating the budget, submitting the filing, and archiving the supporting receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; budget-and-filing tasks should not stop at funding or budgeting and should include both filing and archiving.'
        ),
        'distinctness_rule': (
            'Either prepare funding through tax preparation before budget update, filing, and receipt archiving, '
            'or use the transfer-funding path before the same budget, filing, and archive closure.'
        ),
        'paths': [
            (
                'path_tax_budget_file_archive',
                [
                    'MODULE_TAX_PREPARATION',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_FILE_TAXES',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_transfer_budget_file_archive',
                [
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_FILE_TAXES',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_BUDGET_FUNDING': {'alias_of': 'BP_FINANCE_BUDGET_FILING_PACKET'},
    'BP_FINANCE_CARD_TAX_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'replacement_card_requested',
            'tax_funding_prepared',
            'tax_filing_submitted',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the replacement-tax packet only after the replacement card is requested, tax funding is prepared, the tax filing is submitted, and the receipt trail is archived.',
            'Close the replacement-tax workflow by requesting the card replacement, preparing the funding path, submitting the filing, and archiving the supporting receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; card-replacement tax tasks should carry through filing and documentation rather than stopping at funding preparation.'
        ),
        'distinctness_rule': (
            'Either request the replacement card and prepare funding through tax preparation before filing and receipt archiving, '
            'or request the replacement card and use the transfer-funding path before the same filing-and-archive closure.'
        ),
        'paths': [
            (
                'path_replace_tax_file_archive',
                [
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_TAX_PREPARATION',
                    'MODULE_FILE_TAXES',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_replace_transfer_file_archive',
                [
                    'MODULE_CARD_REPLACEMENT',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_FILE_TAXES',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_CARD_TAX_PREP': {'alias_of': 'BP_FINANCE_CARD_TAX_PACKET'},
    'BP_FINANCE_TRANSFER_ARCHIVE_PACKET': {
        'difficulty': 6,
        'max_steps': 50,
        'max_module_invocations': 4,
        'initial_world_state': ['bank_account_active'],
        'target_state': [
            'bills_aggregated',
            'payment_stack_prepared',
            'budget_limit_updated',
            'receipt_archived',
        ],
        'instruction_templates': [
            'Finish the transfer-archive packet only after bills are aggregated, the payment stack is prepared, the budget limit is updated, and the receipt trail is archived.',
            'Close the payment-archive workflow by aggregating bills, preparing the payment stack, updating the budget limit, and archiving the supporting receipt record.',
        ],
        'notes_template': (
            'Generated from {blueprint_id}; transfer-archive tasks should include a budgeting follow-up before documentation is considered complete.'
        ),
        'distinctness_rule': (
            'Either aggregate bills and prepare the payment stack through a transfer before budget update and receipt archiving, '
            'or aggregate bills and use the complex-autopay path before the same budget-and-archive closure.'
        ),
        'paths': [
            (
                'path_bills_transfer_budget_archive',
                [
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_TRANSFER_FUNDS',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
            (
                'path_bills_autopay_budget_archive',
                [
                    'MODULE_BILL_AGGREGATION',
                    'MODULE_COMPLEX_AUTOPAY',
                    'MODULE_BUDGET_LIMIT_UPDATE',
                    'MODULE_RECEIPT_ARCHIVING',
                ],
            ),
        ],
    },
    'BP_FINANCE_TRANSFER_ARCHIVE_ALIGNMENT': {'alias_of': 'BP_FINANCE_TRANSFER_ARCHIVE_PACKET'},
}


def resolve_spec(blueprint_id: str) -> dict[str, Any] | None:
    spec = ROUND30_SPECS.get(blueprint_id)
    if spec is None:
        return None
    alias = spec.get('alias_of')
    if alias:
        base = ROUND30_SPECS[alias]
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
        raise SystemExit('round30 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
