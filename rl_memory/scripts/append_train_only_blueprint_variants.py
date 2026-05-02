#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'

SEED_MAP = {
    'career': [
        'BP_CAREER_ADMIN_SIGNAL_DUAL',
        'BP_CAREER_DEADLINE_SIGNAL_LOOP',
        'BP_CAREER_ARCHIVE_SIGNAL_STACK',
    ],
    'composite': [
        'BP_COMPOSITE_PAYMENT_VISIBILITY_DUAL',
        'BP_COMPOSITE_ACCESS_FOLLOWUP_DUAL',
        'BP_COMPOSITE_CALENDAR_VISIBILITY_SYNC',
    ],
    'crisis': [
        'BP_CRISIS_INTAKE_LIQUIDITY_DUAL',
        'BP_CRISIS_CONTAINMENT_TRIAGE_DUAL',
        'BP_CRISIS_ACCESS_LIQUIDITY_DUAL',
    ],
    'daily': [
        'BP_DAILY_PRICE_BUNDLE_DUAL',
        'BP_DAILY_RESALE_BUNDLE_DUAL',
        'BP_DAILY_PENDING_PRICE_DUAL',
    ],
    'education': [
        'BP_EDUCATION_COURSE_RESOURCE_DUAL',
        'BP_EDUCATION_CERT_RESOURCE_DUAL',
        'BP_EDUCATION_ASSIGNMENT_RESOURCE_DUAL',
    ],
    'finance': [
        'BP_FINANCE_TRIAGE_REPLACEMENT_DUAL',
        'BP_FINANCE_FUNDING_INVESTMENT_DUAL',
        'BP_FINANCE_AUTOPAY_BUDGET_DUAL',
    ],
    'government': [
        'BP_GOV_ADDRESS_COMPLIANCE_DUAL',
        'BP_GOV_PERMIT_ADDRESS_DUAL',
        'BP_GOV_RENEWAL_REVIEW_DUAL',
    ],
    'health': [
        'BP_HEALTH_CONTINUITY_COVERAGE_DUAL',
        'BP_HEALTH_CLAIM_COVERAGE_DUAL',
        'BP_HEALTH_VACCINE_CONTINUITY_DUAL',
    ],
    'home': [
        'BP_HOME_MONITOR_READINESS_DUAL',
        'BP_HOME_CONTROL_SCHEDULE_DUAL',
        'BP_HOME_REPAIR_MONITOR_DUAL',
    ],
    'newcomer': [
        'BP_NEWCOMER_FINANCE_CONNECTIVITY_DUAL',
        'BP_NEWCOMER_PROOF_BANK_DUAL',
        'BP_NEWCOMER_BANK_SWITCH_DUAL',
    ],
    'security': [
        'BP_SECURITY_SURFACE_HARDEN_DUAL',
        'BP_SECURITY_EXIT_DELETION_DUAL',
        'BP_SECURITY_AUDIT_HARDEN_DUAL',
    ],
    'social': [
        'BP_SOCIAL_COMMITMENT_CONTRIBUTION_DUAL',
        'BP_SOCIAL_SETTLEMENT_COMMITMENT_DUAL',
        'BP_SOCIAL_CONTRIBUTION_ACCOUNT_DUAL',
    ],
    'support': [
        'BP_SUPPORT_EXIT_CONTACT_DUAL',
        'BP_SUPPORT_REMEDY_SUPPORT_DUAL',
        'BP_SUPPORT_REVIEW_SUPPORT_DUAL',
    ],
    'travel': [
        'BP_TRAVEL_BOOKING_TRANSFER_DUAL',
        'BP_TRAVEL_BOOKING_CLEARANCE_DUAL',
        'BP_TRAVEL_REBOOK_BOOKING_DUAL',
    ],
}

VERB_VARIANTS = [
    ('Finish', 'Close'),
    ('Complete', 'Wrap up'),
    ('Finalize', 'Finish out'),
    ('Close', 'Complete'),
    ('Wrap up', 'Finalize'),
    ('Lock in', 'Close out'),
    ('Bring to completion', 'Close'),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def paraphrase(instructions: list[str], variant_index: int) -> list[str]:
    if not instructions:
        return instructions
    a, b = VERB_VARIANTS[variant_index % len(VERB_VARIANTS)]
    out = []
    for idx, text in enumerate(instructions):
        if idx == 0:
            for src in ('Finish', 'Complete', 'Finalize', 'Close', 'Wrap up', 'Lock in'):
                if text.startswith(src + ' '):
                    text = a + text[len(src):]
                    break
        else:
            for src in ('Close', 'End', 'Finish', 'Complete', 'Wrap up', 'Finalize'):
                if text.startswith(src + ' '):
                    text = b + text[len(src):]
                    break
        out.append(text)
    return out


def theme_prefix(theme: str) -> str:
    return theme.upper()


def make_variant_id(theme: str, source_id: str, variant_no: int) -> str:
    stem = source_id.removeprefix(f'BP_{theme_prefix(theme)}_')
    return f'BP_{theme_prefix(theme)}_ZTRAIN_{variant_no:02d}_{stem}'


def main() -> None:
    parser = argparse.ArgumentParser(description='Append train-only blueprint variants up to a target-per-theme count.')
    parser.add_argument('--target-per-theme', type=int, default=36)
    args = parser.parse_args()

    doc = load_json(BLUEPRINTS_PATH)
    blueprints = doc['blueprints']
    by_theme: dict[str, list[dict]] = {}
    for bp in blueprints:
        by_theme.setdefault(bp['theme'], []).append(bp)
    lookup = {bp['blueprint_id']: bp for bp in blueprints}
    existing_ids = set(lookup)

    added = []
    for theme, seeds in SEED_MAP.items():
        current = len(by_theme.get(theme, []))
        need = max(0, args.target_per_theme - current)
        for i in range(need):
            source_id = seeds[i % len(seeds)]
            source = copy.deepcopy(lookup[source_id])
            variant_no = i + 1
            new_id = make_variant_id(theme, source_id, variant_no)
            if new_id in existing_ids:
                raise SystemExit(f'duplicate blueprint id: {new_id}')
            source['blueprint_id'] = new_id
            source['instruction_templates'] = paraphrase(source.get('instruction_templates', []), variant_no)
            deadline = 3 + (variant_no % 4)
            source['visible_constraints']['deadline_days'] = deadline
            source['counterfactual_axes'] = [{
                'path': 'visible_constraints.deadline_days',
                'type': 'numeric_shift',
                'values': [max(2, deadline - 1), deadline],
            }]
            source['notes_template'] = (
                source.get('notes_template', 'Generated from {blueprint_id}; training-only expansion variant.')
                + f' Training-only expansion variant {variant_no}, derived from {source_id}.'
            )
            if isinstance(source.get('max_steps'), int):
                source['max_steps'] = source['max_steps'] + (variant_no % 2)
            added.append(source)
            existing_ids.add(new_id)

    blueprints.extend(added)
    doc['version'] = max(doc.get('version', 0), 1) + 1
    BLUEPRINTS_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'added': len(added),
        'total': len(blueprints),
        'version': doc['version'],
        'target_per_theme': args.target_per_theme,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
