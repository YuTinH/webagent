#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'

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
DELIVERED_REQUIRED_MODULES = {
    'MODULE_RETURN',
    'MODULE_WARRANTY_CLAIM',
    'MODULE_LEAVE_REVIEW',
    'MODULE_REVIEWS_BLACKLIST',
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
BANK_ISSUE_MODULES = {
    'MODULE_CARD_REPLACEMENT',
    'MODULE_DISPUTE_TRANSACTION',
    'MODULE_CHECK_BALANCE',
    'MODULE_LOST_CARD_FREEZE',
    'MODULE_URGENT_LOAN',
}
HOUSING_ANCHOR_MODULES = {
    'MODULE_FIND_HOME',
    'MODULE_ADDRESS_PROOF',
    'MODULE_UTILITY_SETUP',
    'MODULE_ADDRESS_CHANGE',
    'MODULE_LEASE_CONTRACT_REGISTRATION',
    'MODULE_LEASE_MANAGEMENT_REVIEW',
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def strip_modules(path_steps: list[dict], forbidden: set[str]) -> list[dict]:
    return [step for step in path_steps if step['module_id'] not in forbidden]


def normalize_order_and_subscription_context(bp: dict) -> bool:
    changed = False
    initial = set(bp.get('initial_world_state', []))
    targets = set(bp.get('target_state', []))
    module_set = {step['module_id'] for path in bp['paths'] for step in path['steps']}

    subscription_case = bool(module_set & SUBSCRIPTION_EXIT_CONTEXT_MODULES or targets & SUBSCRIPTION_EXIT_TARGETS)
    order_case = bool((module_set & POST_PURCHASE_CONTEXT_MODULES or targets & POST_PURCHASE_TARGETS) and not subscription_case)

    if subscription_case:
        if 'subscription_active' not in initial:
            initial.add('subscription_active')
            changed = True
        for path in bp['paths']:
            updated = strip_modules(path['steps'], {'MODULE_FRESH_SUBSCRIPTION'})
            if updated != path['steps']:
                path['steps'] = updated
                changed = True

    if order_case:
        delivered_required = bool(module_set & DELIVERED_REQUIRED_MODULES or targets & DELIVERED_ORDER_TARGETS)
        has_delivery_bootstrap = 'MODULE_ORDER_ARRIVAL' in module_set or bool(targets & DELIVERY_BOOTSTRAP_TARGETS)
        if delivered_required and not has_delivery_bootstrap:
            if 'shop_order_exists' in initial:
                initial.discard('shop_order_exists')
                changed = True
            if 'shop_order_delivered' not in initial:
                initial.add('shop_order_delivered')
                changed = True
            forbidden = {'MODULE_BANK_OPENING', 'MODULE_SHOPPING', 'MODULE_ORDER_ARRIVAL'}
        else:
            if 'shop_order_delivered' not in initial and 'shop_order_exists' not in initial:
                initial.add('shop_order_exists')
                changed = True
            forbidden = {'MODULE_BANK_OPENING', 'MODULE_SHOPPING'}
            if delivered_required and 'shop_order_delivered' in initial and 'MODULE_ORDER_ARRIVAL' in module_set:
                forbidden.add('MODULE_ORDER_ARRIVAL')
        for path in bp['paths']:
            updated = strip_modules(path['steps'], forbidden)
            if updated != path['steps']:
                path['steps'] = updated
                changed = True

    new_initial = sorted(initial)
    if bp.get('initial_world_state') != new_initial:
        bp['initial_world_state'] = new_initial
        changed = True
    return changed


def normalize_bank_issue_context(bp: dict) -> bool:
    changed = False
    initial = set(bp.get('initial_world_state', []))
    targets = set(bp.get('target_state', []))
    module_set = {step['module_id'] for path in bp['paths'] for step in path['steps']}

    if not (module_set & BANK_ISSUE_MODULES):
        return False
    if 'MODULE_BANK_OPENING' not in module_set:
        if 'bank_account_active' not in initial and 'bank_account_active' not in targets:
            initial.add('bank_account_active')
            changed = True
    elif 'bank_account_active' not in targets:
        if 'bank_account_active' not in initial:
            initial.add('bank_account_active')
            changed = True
        if 'lease_active' in initial and not (module_set & HOUSING_ANCHOR_MODULES):
            initial.discard('lease_active')
            changed = True
        for path in bp['paths']:
            updated = strip_modules(path['steps'], {'MODULE_BANK_OPENING'})
            if updated != path['steps']:
                path['steps'] = updated
                changed = True

    new_initial = sorted(initial)
    if bp.get('initial_world_state') != new_initial:
        bp['initial_world_state'] = new_initial
        changed = True
    return changed


def main() -> None:
    doc = load_json(BLUEPRINTS_PATH)
    updated = 0
    changed_ids = []

    for bp in doc['blueprints']:
        original = json.dumps(bp, ensure_ascii=False, sort_keys=True)
        normalize_bank_issue_context(bp)
        normalize_order_and_subscription_context(bp)
        for path in bp['paths']:
            if not path['steps']:
                raise SystemExit(f"empty path after realism normalization: {bp['blueprint_id']} / {path['path_id']}")
        current = json.dumps(bp, ensure_ascii=False, sort_keys=True)
        if current != original:
            updated += 1
            changed_ids.append(bp['blueprint_id'])

    BLUEPRINTS_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'updated_blueprints': updated, 'changed_blueprints': changed_ids}, ensure_ascii=False))


if __name__ == '__main__':
    main()
