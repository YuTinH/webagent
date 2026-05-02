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

SIG_TRIAGE_REPLACEMENT = (
    ('MODULE_CHECK_BALANCE', 'MODULE_LOST_CARD_FREEZE', 'MODULE_CARD_REPLACEMENT', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_BILL_AGGREGATION', 'MODULE_LOST_CARD_FREEZE', 'MODULE_CARD_REPLACEMENT', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_FUNDING_INVESTMENT = (
    ('MODULE_BANK_OPENING', 'MODULE_TAX_PREPARATION', 'MODULE_INVESTMENT_ACCOUNT', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_BANK_OPENING', 'MODULE_TRANSFER_FUNDS', 'MODULE_INVESTMENT_ACCOUNT', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_TRIAGE_DISPUTE = (
    ('MODULE_CHECK_BALANCE', 'MODULE_LOST_CARD_FREEZE', 'MODULE_DISPUTE_TRANSACTION', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_BILL_AGGREGATION', 'MODULE_LOST_CARD_FREEZE', 'MODULE_DISPUTE_TRANSACTION', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_INVESTMENT_FUNDING = (
    ('MODULE_INVESTMENT_ACCOUNT', 'MODULE_TRANSFER_FUNDS', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_INVESTMENT_GROWTH', 'MODULE_TRANSFER_FUNDS', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_TAX_FILING = (
    ('MODULE_BANK_OPENING', 'MODULE_TRANSFER_FUNDS', 'MODULE_FILE_TAXES', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_BANK_OPENING', 'MODULE_TAX_PREPARATION', 'MODULE_FILE_TAXES', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_ACCOUNT_TRIAGE_READY = (
    ('MODULE_BANK_OPENING', 'MODULE_CHECK_BALANCE', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_BUDGET_LIMIT_UPDATE'),
    ('MODULE_BANK_OPENING', 'MODULE_BILL_AGGREGATION', 'MODULE_RECEIPT_ARCHIVING', 'MODULE_BUDGET_LIMIT_UPDATE'),
)
SIG_AUTOPAY_READY = (
    ('MODULE_BILL_AGGREGATION', 'MODULE_BILLING_REVIEW', 'MODULE_BANK_OPENING', 'MODULE_AUTOPAY'),
    ('MODULE_BILL_AGGREGATION', 'MODULE_BILLING_REVIEW', 'MODULE_BANK_OPENING', 'MODULE_COMPLEX_AUTOPAY'),
)
SIG_BUDGET_FUNDING = (
    ('MODULE_TAX_PREPARATION', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_FILE_TAXES', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_TRANSFER_FUNDS', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_FILE_TAXES', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_CARD_TAX = (
    ('MODULE_CARD_REPLACEMENT', 'MODULE_TAX_PREPARATION', 'MODULE_FILE_TAXES', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_CARD_REPLACEMENT', 'MODULE_TRANSFER_FUNDS', 'MODULE_FILE_TAXES', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_INVESTMENT_BUDGET = (
    ('MODULE_BANK_OPENING', 'MODULE_INVESTMENT_ACCOUNT', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_BANK_OPENING', 'MODULE_INVESTMENT_GROWTH', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_RECEIPT_ARCHIVING'),
)
SIG_TRANSFER_ARCHIVE = (
    ('MODULE_BILL_AGGREGATION', 'MODULE_TRANSFER_FUNDS', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_RECEIPT_ARCHIVING'),
    ('MODULE_BILL_AGGREGATION', 'MODULE_COMPLEX_AUTOPAY', 'MODULE_BUDGET_LIMIT_UPDATE', 'MODULE_RECEIPT_ARCHIVING'),
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
    digest = hashlib.sha256(f'{goal_id}:{blueprint_id}:round48'.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)


def blueprint_signature(bp: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(step['module_id'] for step in path.get('steps', [])) for path in bp.get('paths', []))


def spec_for_blueprint(bp: dict[str, Any]) -> dict[str, Any] | None:
    if bp.get('theme') != 'finance':
        return None

    sig = blueprint_signature(bp)

    if sig == SIG_TRIAGE_REPLACEMENT:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'account_issue_triaged',
                'account_access_contained',
                'replacement_card_requested',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the card-replacement packet only after the account issue is triaged, access is contained, the replacement card is requested, the receipt record is archived, and the replacement follow-up is synced to the calendar.',
                'Close the card-remediation workflow by triaging the issue, freezing exposure, requesting a replacement card, archiving the receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; replacement-oriented finance workflows should include an explicit follow-up scheduling step after archival.'
            ),
            'distinctness_rule': (
                'Either use the balance-check route before freeze, replacement, archival, and calendar sync, '
                'or use the bill-aggregation route before the same freeze, replacement, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_balance_freeze_replace_archive_calendar',
                    [
                        'MODULE_CHECK_BALANCE',
                        'MODULE_LOST_CARD_FREEZE',
                        'MODULE_CARD_REPLACEMENT',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_bills_freeze_replace_archive_calendar',
                    [
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_LOST_CARD_FREEZE',
                        'MODULE_CARD_REPLACEMENT',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_FUNDING_INVESTMENT:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'bank_account_active',
                'tax_funding_prepared',
                'investment_account_active',
                'budget_limit_updated',
                'receipt_archived',
            ],
            'instruction_templates': [
                'Finish the funding-investment packet only after the bank account is opened, tax funding is prepared, the investment account is active, the budget limit is updated, and the receipt trail is archived.',
                'Close the capital-setup workflow by opening the account, preparing the funding path, activating the investment account, updating the budget limit, and archiving the receipt record.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; funding-and-investment finance workflows should include a budget-limit closure before archival.'
            ),
            'distinctness_rule': (
                'Either use the tax-preparation route before investment activation, budget update, and archival, '
                'or use the transfer-funding route before the same investment, budget, and archival closure.'
            ),
            'paths': [
                (
                    'path_bank_tax_invest_budget_archive',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_TAX_PREPARATION',
                        'MODULE_INVESTMENT_ACCOUNT',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
                (
                    'path_bank_transfer_invest_budget_archive',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_INVESTMENT_ACCOUNT',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
            ],
        }

    if sig == SIG_TRIAGE_DISPUTE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'account_issue_triaged',
                'account_access_contained',
                'transaction_dispute_submitted',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the dispute-remediation packet only after the account issue is triaged, access is contained, the transaction dispute is submitted, the receipt record is archived, and the dispute follow-up is synced to the calendar.',
                'Close the dispute workflow by triaging the issue, freezing exposure, submitting the dispute, archiving the supporting receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; dispute-oriented finance workflows should include a scheduled follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the balance-check route before freeze, dispute, archival, and calendar sync, '
                'or use the bill-aggregation route before the same freeze, dispute, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_balance_freeze_dispute_archive_calendar',
                    [
                        'MODULE_CHECK_BALANCE',
                        'MODULE_LOST_CARD_FREEZE',
                        'MODULE_DISPUTE_TRANSACTION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_bills_freeze_dispute_archive_calendar',
                    [
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_LOST_CARD_FREEZE',
                        'MODULE_DISPUTE_TRANSACTION',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_INVESTMENT_FUNDING:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'investment_account_active',
                'transfer_completed',
                'budget_limit_updated',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the active-investment packet only after the investment account is active, the transfer is completed, the budget limit is updated, the receipt trail is archived, and the investment follow-up is synced to the calendar.',
                'Close the investment-funding workflow by activating the investment path, completing the transfer, updating the budget limit, archiving the receipt record, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; active-investment finance workflows should schedule a follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the direct investment-account route before transfer, budget update, archival, and calendar sync, '
                'or use the investment-growth route before the same transfer, budget, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_invest_transfer_budget_archive_calendar',
                    [
                        'MODULE_INVESTMENT_ACCOUNT',
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_growth_transfer_budget_archive_calendar',
                    [
                        'MODULE_INVESTMENT_GROWTH',
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_TAX_FILING:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'bank_account_active',
                'tax_funding_prepared',
                'tax_filing_submitted',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the tax-filing packet only after the bank account is opened, tax funding is prepared, the filing is submitted, the receipt trail is archived, and the filing follow-up is synced to the calendar.',
                'Close the filing workflow by opening the account, preparing funding, submitting the filing, archiving the receipt record, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; tax-filing finance workflows should include a post-filing calendar follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the transfer-funding route before filing, archival, and calendar sync, '
                'or use the tax-preparation route before the same filing, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_bank_transfer_file_archive_calendar',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_FILE_TAXES',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_bank_taxprep_file_archive_calendar',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_TAX_PREPARATION',
                        'MODULE_FILE_TAXES',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_ACCOUNT_TRIAGE_READY:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'bank_account_active',
                'account_issue_triaged',
                'budget_limit_updated',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the account-readiness packet only after the bank account is opened, the issue is triaged, the budget limit is updated, the receipt trail is archived, and the readiness follow-up is synced to the calendar.',
                'Close the finance-readiness workflow by opening the account, triaging the account state, updating the budget limit, archiving the receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; account-readiness finance workflows should close with budget and follow-up scheduling after triage.'
            ),
            'distinctness_rule': (
                'Either use the balance-check route before budget update, archival, and calendar sync, '
                'or use the bill-aggregation route before the same budget, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_bank_balance_budget_archive_calendar',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_CHECK_BALANCE',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_bank_bills_budget_archive_calendar',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_AUTOPAY_READY:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'bills_reviewed',
                'bank_account_active',
                'autopay_enabled',
                'receipt_archived',
            ],
            'instruction_templates': [
                'Finish the autopay-readiness packet only after the bills are reviewed, the account is opened, autopay is enabled, and the setup record is archived.',
                'Close the recurring-payment workflow by reviewing the bill stack, activating the account, enabling autopay, and ending with the setup record archived.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; autopay-readiness workflows should archive the setup record after the autopay step.'
            ),
            'distinctness_rule': (
                'Either use the standard-autopay route before archival, '
                'or use the complex-autopay route before the same archival closure.'
            ),
            'paths': [
                (
                    'path_bills_review_bank_autopay_archive',
                    [
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_BILLING_REVIEW',
                        'MODULE_BANK_OPENING',
                        'MODULE_AUTOPAY',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
                (
                    'path_bills_review_bank_complex_archive',
                    [
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_BILLING_REVIEW',
                        'MODULE_BANK_OPENING',
                        'MODULE_COMPLEX_AUTOPAY',
                        'MODULE_RECEIPT_ARCHIVING',
                    ],
                ),
            ],
        }

    if sig == SIG_BUDGET_FUNDING:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'budget_limit_updated',
                'tax_funding_prepared',
                'tax_filing_submitted',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the budget-filing packet only after the budget limit is updated, tax funding is prepared, the filing is submitted, the receipt trail is archived, and the filing follow-up is synced to the calendar.',
                'Close the tax-budget workflow by preparing funding, updating the budget, submitting the filing, archiving the receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; tax-budget finance workflows should include a calendar follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the tax-preparation route before filing, archival, and calendar sync, '
                'or use the transfer-funding route before the same filing, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_taxprep_budget_file_archive_calendar',
                    [
                        'MODULE_TAX_PREPARATION',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_FILE_TAXES',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_transfer_budget_file_archive_calendar',
                    [
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_FILE_TAXES',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_CARD_TAX:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'replacement_card_requested',
                'tax_funding_prepared',
                'tax_filing_submitted',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the replacement-tax packet only after the replacement card is requested, tax funding is prepared, the filing is submitted, the receipt trail is archived, and the filing follow-up is synced to the calendar.',
                'Close the replacement-tax workflow by requesting the card replacement, preparing funding, submitting the filing, archiving the receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; replacement-and-tax finance workflows should include a scheduled follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the tax-preparation route before filing, archival, and calendar sync, '
                'or use the transfer-funding route before the same filing, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_replace_taxprep_file_archive_calendar',
                    [
                        'MODULE_CARD_REPLACEMENT',
                        'MODULE_TAX_PREPARATION',
                        'MODULE_FILE_TAXES',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_replace_transfer_file_archive_calendar',
                    [
                        'MODULE_CARD_REPLACEMENT',
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_FILE_TAXES',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_INVESTMENT_BUDGET:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'bank_account_active',
                'investment_account_active',
                'budget_limit_updated',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the investment-budget packet only after the bank account is opened, the investment account is active, the budget limit is updated, the receipt trail is archived, and the investment follow-up is synced to the calendar.',
                'Close the investment-budget workflow by opening the account, activating the investment path, updating the budget limit, archiving the receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; investment-budget finance workflows should include a scheduled follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the investment-account route before budget update, archival, and calendar sync, '
                'or use the investment-growth route before the same budget, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_bank_invest_budget_archive_calendar',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_INVESTMENT_ACCOUNT',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_bank_growth_budget_archive_calendar',
                    [
                        'MODULE_BANK_OPENING',
                        'MODULE_INVESTMENT_GROWTH',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
            ],
        }

    if sig == SIG_TRANSFER_ARCHIVE:
        return {
            'difficulty': 7,
            'max_steps': 60,
            'max_module_invocations': 5,
            'target_state': [
                'bills_aggregated',
                'payment_stack_prepared',
                'budget_limit_updated',
                'receipt_archived',
                'calendar_event_synced',
            ],
            'instruction_templates': [
                'Finish the transfer-archive packet only after bills are aggregated, the payment stack is prepared, the budget limit is updated, the receipt trail is archived, and the payment follow-up is synced to the calendar.',
                'Close the payment-archive workflow by aggregating bills, preparing the payment stack, updating the budget limit, archiving the receipt trail, and ending with a synced follow-up reminder.',
            ],
            'notes_template': (
                'Generated from {blueprint_id}; payment-archive finance workflows should include a scheduled follow-up after archival.'
            ),
            'distinctness_rule': (
                'Either use the transfer-funding route before budget update, archival, and calendar sync, '
                'or use the complex-autopay route before the same budget, archival, and follow-up closure.'
            ),
            'paths': [
                (
                    'path_bills_transfer_budget_archive_calendar',
                    [
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_TRANSFER_FUNDS',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
                    ],
                ),
                (
                    'path_bills_complex_budget_archive_calendar',
                    [
                        'MODULE_BILL_AGGREGATION',
                        'MODULE_COMPLEX_AUTOPAY',
                        'MODULE_BUDGET_LIMIT_UPDATE',
                        'MODULE_RECEIPT_ARCHIVING',
                        'MODULE_EMAIL_CALENDAR',
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
        raise SystemExit('round48 blueprint validation failed:\n- ' + '\n- '.join(validation_issues))

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
