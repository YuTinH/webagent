#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path('/Users/masteryth/Documents/webagent')
BLUEPRINTS_PATH = ROOT / 'tasks' / 'workflow_generation_blueprints.json'

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
SUBSCRIPTION_TARGETS = {
    'subscription_exit_processed',
    'subscription_canceled',
    'refund_requested',
}
SUBSCRIPTION_CONTEXT_MODULES = {
    'MODULE_CANCEL_SUBSCRIPTION',
    'MODULE_SUBSCRIPTION_REFUND',
    'MODULE_FRESH_SUBSCRIPTION',
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def strip_modules(path_steps: list[dict], forbidden: set[str]) -> list[dict]:
    return [step for step in path_steps if step['module_id'] not in forbidden]


def main() -> None:
    doc = load_json(BLUEPRINTS_PATH)
    updated = 0
    for bp in doc['blueprints']:
        if bp['theme'] != 'support':
            continue
        targets = set(bp.get('target_state', []))
        module_set = {step['module_id'] for path in bp['paths'] for step in path['steps']}
        original = json.dumps(bp, ensure_ascii=False, sort_keys=True)

        subscription_case = bool(module_set & SUBSCRIPTION_CONTEXT_MODULES or targets & SUBSCRIPTION_TARGETS)
        if subscription_case:
            bp['initial_world_state'] = ['subscription_active']
            for path in bp['paths']:
                path['steps'] = strip_modules(path['steps'], {'MODULE_FRESH_SUBSCRIPTION'})

        else:
            delivered_required = bool(module_set & DELIVERED_REQUIRED_MODULES or targets & DELIVERED_ORDER_TARGETS)
            has_delivery_bootstrap = bool('MODULE_ORDER_ARRIVAL' in module_set or targets & DELIVERY_BOOTSTRAP_TARGETS)
            if delivered_required and not has_delivery_bootstrap:
                bp['initial_world_state'] = ['shop_order_delivered']
                forbidden = {'MODULE_BANK_OPENING', 'MODULE_SHOPPING', 'MODULE_ORDER_ARRIVAL'}
            else:
                bp['initial_world_state'] = ['shop_order_exists']
                forbidden = {'MODULE_BANK_OPENING', 'MODULE_SHOPPING'}
            for path in bp['paths']:
                path['steps'] = strip_modules(path['steps'], forbidden)

        for path in bp['paths']:
            if not path['steps']:
                raise SystemExit(f"empty path after normalization: {bp['blueprint_id']} / {path['path_id']}")

        current = json.dumps(bp, ensure_ascii=False, sort_keys=True)
        if current != original:
            updated += 1

    BLUEPRINTS_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'updated_support_blueprints': updated}, ensure_ascii=False))


if __name__ == '__main__':
    main()
