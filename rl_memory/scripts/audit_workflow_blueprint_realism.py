#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'
REQUIREMENTS_PATH = ROOT / 'tasks' / 'workflow_quality_requirements.json'
DEFAULT_OUTPUT_JSON = ROOT / '.task_sync_meta' / 'workflow_blueprint_realism_audit.json'
DEFAULT_OUTPUT_MD = ROOT / '.task_sync_meta' / 'workflow_blueprint_realism_audit.md'

POST_PURCHASE_CONTEXT_MODULES = {
    'MODULE_CONTACT_SUPPORT',
    'MODULE_LOGISTICS_FIX',
    'MODULE_RETURN',
    'MODULE_WARRANTY_CLAIM',
    'MODULE_CUSTOMER_SERVICE',
}
POST_PURCHASE_TARGETS = {
    'post_purchase_remedy_requested',
    'return_requested',
    'warranty_claim_submitted',
    'order_followup_prepared',
    'support_contacted',
}
DELIVERED_ORDER_TARGETS = {
    'post_purchase_remedy_requested',
    'return_requested',
    'warranty_claim_submitted',
    'merchant_blacklisted',
    'product_review_submitted',
}
DELIVERY_BOOTSTRAP_TARGETS = {
    'delivery_visibility_confirmed',
    'shop_order_delivered',
}
SUBSCRIPTION_EXIT_CONTEXT_MODULES = {
    'MODULE_CANCEL_SUBSCRIPTION',
    'MODULE_SUBSCRIPTION_REFUND',
}
SUBSCRIPTION_EXIT_TARGETS = {
    'subscription_exit_processed',
    'subscription_canceled',
    'refund_requested',
}

NEWCOMER_HOUSING_MODULES = {
    'MODULE_ADDRESS_PROOF',
    'MODULE_UTILITY_SETUP',
    'MODULE_ADDRESS_CHANGE',
}
GOV_RESIDENCY_MODULES = {
    'MODULE_PARKING_PERMIT_APPLICATION',
    'MODULE_VEHICLE_ADDRESS_UPDATE',
    'MODULE_RENEW_PERMIT',
    'MODULE_PERMIT_APP',
    'MODULE_PERMIT_RENEWAL',
    'MODULE_ADDRESS_CHANGE',
}
HOME_RESIDENCE_MODULES = {
    'MODULE_SMART_METER',
    'MODULE_THERMOSTAT_SCHEDULE',
    'MODULE_ENERGY_OPTIMIZE',
    'MODULE_SMART_BULB_SETUP',
    'MODULE_HOUSE_REPAIR',
}
EDU_CERT_MODULES = {'MODULE_DOWNLOAD_CERT'}
EDU_CERT_PREREQ_MODULES = {'MODULE_COURSE_ENROLLMENT', 'MODULE_SKILL_CERTIFICATION'}
EDU_ASSIGNMENT_MODULES = {'MODULE_SUBMIT_ASSIGNMENT'}
EDU_ASSIGNMENT_PREREQ_MODULES = {'MODULE_COURSE_ENROLLMENT'}
HEALTH_CLAIM_MODULES = {'MODULE_MEDICAL_CLAIM'}
HEALTH_CLAIM_PREREQ_MODULES = {'MODULE_INSURANCE_POLICY', 'MODULE_HEALTH_PLAN_ACTIVATION'}
SOCIAL_PAYMENT_MODULES = {'MODULE_CHARITY_DONATION'}
CAREER_EXPENSE_MODULES = {'MODULE_EXPENSE_REPORT'}
CAREER_EXPENSE_PREREQ_MODULES = {
    'MODULE_BOOK_FLIGHT',
    'MODULE_BOOK_HOTEL',
    'MODULE_CONFERENCE_REG',
    'MODULE_CONFERENCE_REGISTRATION',
}
SECURITY_RESET_COMPLETION = 'MODULE_PASSWORD_RESET_COMPLETION'
SECURITY_RESET_REQUEST = 'MODULE_PASSWORD_RESET_REQUEST'
SECURITY_RECOVERY_BUNDLE = 'MODULE_PASSWORD_RECOVERY_E2E'
SECURITY_TWOFA_DEVICE = 'MODULE_2FA_DEVICE'
SECURITY_TWOFA_SETUP = 'MODULE_2FA_SETUP'
HOUSING_ANCHOR_MODULES = {
    'MODULE_FIND_HOME',
    'MODULE_ADDRESS_PROOF',
    'MODULE_UTILITY_SETUP',
    'MODULE_ADDRESS_CHANGE',
    'MODULE_LEASE_CONTRACT_REGISTRATION',
    'MODULE_LEASE_MANAGEMENT_REVIEW',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit workflow blueprints for human realism.')
    parser.add_argument('--blueprints', default=str(BLUEPRINTS_PATH))
    parser.add_argument('--requirements', default=str(REQUIREMENTS_PATH))
    parser.add_argument('--output-json', default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument('--output-md', default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument('--strict', action='store_true')
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def modules_for_blueprint(blueprint: dict[str, Any]) -> list[str]:
    return [step['module_id'] for path in blueprint['paths'] for step in path['steps']]


def path_modules(path: dict[str, Any]) -> list[str]:
    return [step['module_id'] for step in path['steps']]


def path_has_prior(path: dict[str, Any], index: int, candidates: set[str]) -> bool:
    return any(step['module_id'] in candidates for step in path['steps'][:index])


def add_issue(bucket: list[dict[str, Any]], blueprint_id: str, theme: str, issue: str, path_id: str | None = None) -> None:
    item = {'blueprint_id': blueprint_id, 'theme': theme, 'issue': issue}
    if path_id is not None:
        item['path_id'] = path_id
    bucket.append(item)


def audit_order_and_subscription_context(
    blueprint: dict[str, Any],
    issues: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> None:
    if not cfg.get('enabled', True):
        return
    blueprint_id = blueprint['blueprint_id']
    theme = blueprint['theme']
    initial = set(blueprint.get('initial_world_state', []))
    module_set = set(modules_for_blueprint(blueprint))
    targets = set(blueprint.get('target_state', []))

    subscription_case = bool(module_set & SUBSCRIPTION_EXIT_CONTEXT_MODULES or targets & SUBSCRIPTION_EXIT_TARGETS)
    order_case = bool((module_set & POST_PURCHASE_CONTEXT_MODULES or targets & POST_PURCHASE_TARGETS) and not subscription_case)

    if subscription_case:
        if not (set(cfg.get('subscription_context_required', [])) & initial):
            add_issue(issues, blueprint_id, theme, 'subscription_context_missing_active_subscription')
        if module_set & set(cfg.get('forbid_subscription_bootstrap_modules', [])):
            add_issue(issues, blueprint_id, theme, 'subscription_context_contains_bootstrap_subscription_module')

    if order_case:
        if not (set(cfg.get('order_context_any_of', [])) & initial):
            add_issue(issues, blueprint_id, theme, 'order_context_missing_existing_order')
        if module_set & set(cfg.get('forbid_order_bootstrap_modules', [])):
            add_issue(issues, blueprint_id, theme, 'order_context_contains_bootstrap_order_module')
        delivered_required = bool(
            module_set & set(cfg.get('delivered_order_required_modules', []))
            or targets & DELIVERED_ORDER_TARGETS
        )
        has_delivery_bootstrap = 'MODULE_ORDER_ARRIVAL' in module_set or bool(targets & DELIVERY_BOOTSTRAP_TARGETS)
        if delivered_required and 'shop_order_delivered' not in initial and not has_delivery_bootstrap:
            add_issue(issues, blueprint_id, theme, 'order_context_missing_delivered_order_state')
        if delivered_required and 'MODULE_ORDER_ARRIVAL' in module_set and 'shop_order_delivered' in initial:
            add_issue(issues, blueprint_id, theme, 'order_context_contains_redundant_delivery_bootstrap')


def audit_bank_issue_context(
    blueprint: dict[str, Any],
    issues: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> None:
    if not cfg.get('enabled', True):
        return
    blueprint_id = blueprint['blueprint_id']
    theme = blueprint['theme']
    initial = set(blueprint.get('initial_world_state', []))
    module_set = set(modules_for_blueprint(blueprint))
    targets = set(blueprint.get('target_state', []))

    issue_modules = set(cfg.get('issue_modules', []))
    if not (module_set & issue_modules):
        return

    account_context = set(cfg.get('required_account_context', []))
    if not ((account_context & initial) or ('bank_account_active' in targets) or (cfg.get('bootstrap_module') in module_set)):
        add_issue(issues, blueprint_id, theme, 'bank_issue_missing_account_context')

    if cfg.get('bootstrap_module') in module_set and not (targets & set(cfg.get('bootstrap_allowed_target_predicates', []))):
        add_issue(issues, blueprint_id, theme, 'bank_issue_contains_bootstrap_bank_opening')


def audit_travel_context(
    blueprint: dict[str, Any],
    issues: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> None:
    if not cfg.get('enabled', True):
        return
    blueprint_id = blueprint['blueprint_id']
    theme = blueprint['theme']
    initial = set(blueprint.get('initial_world_state', []))
    booking_context = set(cfg.get('booking_context_any_of', []))
    bootstrap_modules = set(cfg.get('booking_bootstrap_modules', []))
    requires_booking_modules = set(cfg.get('requires_booking_modules', []))

    for path in blueprint['paths']:
        steps = path['steps']
        for index, step in enumerate(steps):
            module_id = step['module_id']
            if module_id not in requires_booking_modules:
                continue
            if booking_context & initial:
                continue
            if path_has_prior(path, index, bootstrap_modules):
                continue
            add_issue(issues, blueprint_id, theme, 'travel_missing_booking_context', path['path_id'])


def audit_newcomer_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'newcomer':
        return
    module_set = set(modules_for_blueprint(blueprint))
    initial = set(blueprint.get('initial_world_state', []))
    if module_set & NEWCOMER_HOUSING_MODULES and 'lease_active' not in initial and 'MODULE_FIND_HOME' not in module_set:
        add_issue(issues, blueprint['blueprint_id'], blueprint['theme'], 'newcomer_missing_housing_anchor')


def audit_government_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'government':
        return
    module_set = set(modules_for_blueprint(blueprint))
    initial = set(blueprint.get('initial_world_state', []))
    residency_context = {'lease_active', 'address_proof_available', 'residency_record_verified'}
    residency_bootstrap = {'MODULE_FIND_HOME', 'MODULE_ADDRESS_PROOF', 'MODULE_UTILITY_SETUP'}
    if module_set & GOV_RESIDENCY_MODULES and not ((initial & residency_context) or (module_set & residency_bootstrap)):
        add_issue(issues, blueprint['blueprint_id'], blueprint['theme'], 'government_missing_residency_anchor')


def audit_education_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'education':
        return
    blueprint_id = blueprint['blueprint_id']
    initial = set(blueprint.get('initial_world_state', []))
    for path in blueprint['paths']:
        steps = path['steps']
        for index, step in enumerate(steps):
            module_id = step['module_id']
            if module_id in EDU_ASSIGNMENT_MODULES and 'course_enrolled' not in initial and not path_has_prior(path, index, EDU_ASSIGNMENT_PREREQ_MODULES):
                add_issue(issues, blueprint_id, blueprint['theme'], 'education_assignment_missing_course_context', path['path_id'])
            if module_id in EDU_CERT_MODULES and 'course_enrolled' not in initial and 'skill_certified' not in initial and not path_has_prior(path, index, EDU_CERT_PREREQ_MODULES):
                add_issue(issues, blueprint_id, blueprint['theme'], 'education_certificate_missing_completion_context', path['path_id'])


def audit_health_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'health':
        return
    blueprint_id = blueprint['blueprint_id']
    initial = set(blueprint.get('initial_world_state', []))
    for path in blueprint['paths']:
        for index, step in enumerate(path['steps']):
            if step['module_id'] in HEALTH_CLAIM_MODULES and not ({'coverage_path_active', 'health_plan_active', 'insurance_policy_active'} & initial) and not path_has_prior(path, index, HEALTH_CLAIM_PREREQ_MODULES):
                add_issue(issues, blueprint_id, blueprint['theme'], 'health_claim_missing_coverage_context', path['path_id'])


def audit_home_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'home':
        return
    initial = set(blueprint.get('initial_world_state', []))
    for path in blueprint['paths']:
        for index, step in enumerate(path['steps']):
            module_id = step['module_id']
            if module_id not in HOME_RESIDENCE_MODULES:
                continue
            if {'lease_active', 'utilities_active'} & initial:
                continue
            if path_has_prior(path, index, {'MODULE_FIND_HOME', 'MODULE_UTILITY_SETUP'}):
                continue
            add_issue(issues, blueprint['blueprint_id'], blueprint['theme'], 'home_missing_residence_context', path['path_id'])


def audit_social_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'social':
        return
    module_set = set(modules_for_blueprint(blueprint))
    initial = set(blueprint.get('initial_world_state', []))
    if module_set & SOCIAL_PAYMENT_MODULES and 'bank_account_active' not in initial and 'MODULE_BANK_OPENING' not in module_set:
        add_issue(issues, blueprint['blueprint_id'], blueprint['theme'], 'social_missing_payment_anchor')


def audit_career_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'career':
        return
    module_set = set(modules_for_blueprint(blueprint))
    initial = set(blueprint.get('initial_world_state', []))
    if module_set & CAREER_EXPENSE_MODULES and not ((module_set & CAREER_EXPENSE_PREREQ_MODULES) or ('travel_booking_confirmed' in initial) or ('conference_admin_recorded' in initial)):
        add_issue(issues, blueprint['blueprint_id'], blueprint['theme'], 'career_expense_missing_source_context')


def audit_security_theme(blueprint: dict[str, Any], issues: list[dict[str, Any]], enabled: bool) -> None:
    if not enabled or blueprint['theme'] != 'security':
        return
    blueprint_id = blueprint['blueprint_id']
    initial = set(blueprint.get('initial_world_state', []))
    for path in blueprint['paths']:
        for index, step in enumerate(path['steps']):
            module_id = step['module_id']
            if module_id == SECURITY_RESET_COMPLETION and SECURITY_RECOVERY_BUNDLE not in path_modules(path):
                if 'password_reset_code_requested' not in initial and not path_has_prior(path, index, {SECURITY_RESET_REQUEST}):
                    add_issue(issues, blueprint_id, blueprint['theme'], 'security_reset_completion_missing_request', path['path_id'])
            if module_id == SECURITY_TWOFA_DEVICE:
                if 'two_factor_enabled' not in initial and not path_has_prior(path, index, {SECURITY_TWOFA_SETUP}):
                    add_issue(issues, blueprint_id, blueprint['theme'], 'security_2fa_device_missing_setup_context', path['path_id'])


def main() -> None:
    args = parse_args()
    blueprints_doc = load_json(Path(args.blueprints))
    requirements = load_json(Path(args.requirements))
    realism_cfg = requirements.get('realism', {})
    context_cfg = realism_cfg.get('contexts', {})
    theme_cfg = realism_cfg.get('themes', {})

    issues: list[dict[str, Any]] = []
    per_blueprint = []

    for blueprint in blueprints_doc['blueprints']:
        before = len(issues)
        audit_order_and_subscription_context(blueprint, issues, context_cfg.get('order_support', {}))
        audit_bank_issue_context(blueprint, issues, context_cfg.get('bank_account_issue', {}))
        audit_travel_context(blueprint, issues, context_cfg.get('travel_booking', {}))
        audit_newcomer_theme(blueprint, issues, theme_cfg.get('newcomer', {}).get('enabled', True))
        audit_government_theme(blueprint, issues, theme_cfg.get('government', {}).get('enabled', True))
        audit_education_theme(blueprint, issues, theme_cfg.get('education', {}).get('enabled', True))
        audit_health_theme(blueprint, issues, theme_cfg.get('health', {}).get('enabled', True))
        audit_home_theme(blueprint, issues, theme_cfg.get('home', {}).get('enabled', True))
        audit_social_theme(blueprint, issues, theme_cfg.get('social', {}).get('enabled', True))
        audit_career_theme(blueprint, issues, theme_cfg.get('career', {}).get('enabled', True))
        audit_security_theme(blueprint, issues, theme_cfg.get('security', {}).get('enabled', True))
        blueprint_issues = issues[before:]
        per_blueprint.append({
            'blueprint_id': blueprint['blueprint_id'],
            'theme': blueprint['theme'],
            'issues': [item['issue'] for item in blueprint_issues],
        })

    issue_counter = Counter(item['issue'] for item in issues)
    theme_counter = Counter(item['theme'] for item in issues)
    report = {
        'version': 2,
        'source_blueprints': str(Path(args.blueprints)),
        'requirements': str(Path(args.requirements)),
        'issue_count': len(issues),
        'flagged_blueprints': sorted({item['blueprint_id'] for item in issues}),
        'issue_type_counts': dict(sorted(issue_counter.items())),
        'theme_issue_counts': dict(sorted(theme_counter.items())),
        'issues': issues,
        'per_blueprint': per_blueprint,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# Workflow Blueprint Realism Audit',
        '',
        f'- source_blueprints: `{Path(args.blueprints)}`',
        f'- issue_count: {len(issues)}',
        '',
        '## Issue Type Counts',
    ]
    if not issue_counter:
        lines.append('- none')
    else:
        for issue, count in sorted(issue_counter.items()):
            lines.append(f'- `{issue}`: {count}')
    lines += ['', '## Theme Issue Counts']
    if not theme_counter:
        lines.append('- none')
    else:
        for theme, count in sorted(theme_counter.items()):
            lines.append(f'- `{theme}`: {count}')
    lines += ['', '## Issues']
    if not issues:
        lines.append('- none')
    else:
        for item in issues:
            path_suffix = f" [{item['path_id']}]" if 'path_id' in item else ''
            lines.append(f"- `{item['blueprint_id']}`{path_suffix}: {item['issue']}")
    output_md.write_text('\n'.join(lines) + '\n')

    if args.strict and issues:
        print('workflow blueprint realism audit failed', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
