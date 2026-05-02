# End-to-End Complete Examples (P0)

**Version**: v1.0
**Last Updated**: 2025-11-16
**Purpose**: Provide 5 complete task examples including TaskSpec, Trace, Assertions, and Memory updates

---

## Example 1: B1 - Basic E-commerce Shopping

### 1.1 TaskSpec (JSON)
```json
{
  "task_id": "B1-2025-001",
  "family": "B",
  "episode_id": "ep-001",
  "priority": 1,
  "seed": 42,
  "time": "2025-11-16T09:00:00Z",
  "persona": {
    "budget": 500,
    "preferences": ["electronics", "fast_shipping"],
    "address": "123 Main St, Apt 5B"
  },
  "goal": "Purchase a wireless mouse under $30 with same-day delivery to my primary address",
  "inputs": {
    "category": "electronics",
    "item_keywords": ["wireless", "mouse"],
    "max_price": 30,
    "shipping_speed": "same_day",
    "payment_method": "credit_card_1234"
  },
  "allowed_domains": [
    "shop.local"
  ],
  "preconditions": [
    "mem('address.primary') != ''",
    "mem('payment.cards[0].last4') == '1234'",
    "mem('payment.cards[0].status') == 'active'"
  ],
  "memory_keys": [
    "orders.last.id",
    "orders.last.total",
    "orders.last.items",
    "orders.last.timestamp"
  ],
  "success_criteria": [
    "ALL[url().includes('/order/confirmation'), text('#order-id') != '', json('env','orders.*.state') == 'confirmed', mem('orders.last.id') != '']"
  ],
  "artifacts": [
    "order_confirmation_screenshot",
    "receipt_pdf"
  ],
  "rubrics": {
    "SR": 1.0,
    "LH-F1": 0.3,
    "cost_efficiency": 0.2
  },
  "timeout": 300,
  "error_recovery": {
    "on_timeout": "capture_state_and_abort",
    "on_network_error": "retry_3_times",
    "on_assertion_fail": "save_trace_and_report"
  }
}
```

### 1.2 Execution Trace (JSON)
```json
{
  "task_id": "B1-2025-001",
  "agent_version": "v1.0.0",
  "steps": [
    {
      "t": 0,
      "url": "https://shop.local",
      "frame": "main",
      "act": "open",
      "note": "Navigate to e-commerce homepage"
    },
    {
      "t": 1.2,
      "url": "https://shop.local",
      "frame": "main",
      "act": "click",
      "selector": "#search-box",
      "screenshot_id": "step_001_homepage",
      "note": "Focus on search input"
    },
    {
      "t": 1.5,
      "url": "https://shop.local",
      "frame": "main",
      "act": "type",
      "selector": "#search-box",
      "value": "wireless mouse",
      "note": "Enter search keywords"
    },
    {
      "t": 2.0,
      "url": "https://shop.local",
      "frame": "main",
      "act": "click",
      "selector": "button[type='submit'][aria-label='Search']",
      "note": "Submit search form"
    },
    {
      "t": 3.5,
      "url": "https://shop.local/search?q=wireless+mouse",
      "frame": "main",
      "act": "wait",
      "selector": ".product-grid .product-item",
      "screenshot_id": "step_002_search_results",
      "note": "Wait for search results to load"
    },
    {
      "t": 4.0,
      "url": "https://shop.local/search?q=wireless+mouse",
      "frame": "main",
      "act": "click",
      "selector": "#filter-price-max",
      "note": "Open price filter"
    },
    {
      "t": 4.5,
      "url": "https://shop.local/search?q=wireless+mouse",
      "frame": "main",
      "act": "type",
      "selector": "#filter-price-max",
      "value": "30",
      "note": "Set max price to $30"
    },
    {
      "t": 5.0,
      "url": "https://shop.local/search?q=wireless+mouse",
      "frame": "main",
      "act": "click",
      "selector": "button.apply-filters",
      "note": "Apply price filter"
    },
    {
      "t": 6.5,
      "url": "https://shop.local/search?q=wireless+mouse&price_max=30",
      "frame": "main",
      "act": "wait",
      "selector": ".product-grid .product-item",
      "screenshot_id": "step_003_filtered_results",
      "note": "Wait for filtered results"
    },
    {
      "t": 8.0,
      "url": "https://shop.local/search?q=wireless+mouse&price_max=30",
      "frame": "main",
      "act": "click",
      "selector": ".product-item:first-child .product-link",
      "note": "Click first product matching criteria"
    },
    {
      "t": 10.0,
      "url": "https://shop.local/product/WM-5521",
      "frame": "main",
      "act": "wait",
      "selector": "#add-to-cart-btn",
      "screenshot_id": "step_004_product_detail",
      "note": "Wait for product detail page"
    },
    {
      "t": 11.0,
      "url": "https://shop.local/product/WM-5521",
      "frame": "main",
      "act": "assert",
      "selector": ".price-current",
      "value": "<= 30",
      "note": "Verify price is within budget"
    },
    {
      "t": 12.0,
      "url": "https://shop.local/product/WM-5521",
      "frame": "main",
      "act": "click",
      "selector": "#shipping-option-same-day",
      "note": "Select same-day shipping"
    },
    {
      "t": 13.0,
      "url": "https://shop.local/product/WM-5521",
      "frame": "main",
      "act": "click",
      "selector": "#add-to-cart-btn",
      "note": "Add to cart"
    },
    {
      "t": 14.5,
      "url": "https://shop.local/cart",
      "frame": "main",
      "act": "wait",
      "selector": ".cart-item",
      "screenshot_id": "step_005_cart",
      "note": "Wait for cart page"
    },
    {
      "t": 15.0,
      "url": "https://shop.local/cart",
      "frame": "main",
      "act": "click",
      "selector": "button.checkout",
      "note": "Proceed to checkout"
    },
    {
      "t": 17.0,
      "url": "https://shop.local/checkout",
      "frame": "main",
      "act": "wait",
      "selector": "#shipping-address",
      "screenshot_id": "step_006_checkout",
      "note": "Wait for checkout page"
    },
    {
      "t": 18.0,
      "url": "https://shop.local/checkout",
      "frame": "main",
      "act": "assert",
      "selector": "#shipping-address .address-display",
      "value": "mem('address.primary')",
      "note": "Verify shipping address matches memory"
    },
    {
      "t": 19.0,
      "url": "https://shop.local/checkout",
      "frame": "main",
      "act": "click",
      "selector": "#payment-card-1234",
      "note": "Select payment method from memory"
    },
    {
      "t": 20.0,
      "url": "https://shop.local/checkout",
      "frame": "main",
      "act": "click",
      "selector": "button.place-order",
      "note": "Place order"
    },
    {
      "t": 22.5,
      "url": "https://shop.local/order/confirmation/O-10001",
      "frame": "main",
      "act": "wait",
      "selector": "#order-id",
      "screenshot_id": "step_007_confirmation",
      "note": "Wait for confirmation page"
    },
    {
      "t": 23.0,
      "url": "https://shop.local/order/confirmation/O-10001",
      "frame": "main",
      "act": "assert",
      "selector": "#order-status",
      "value": "confirmed",
      "note": "Final assertion: order confirmed"
    }
  ]
}
```

### 1.3 Screenshot Descriptions
- **step_001_homepage**: Homepage with search box prominently displayed, DOM id randomized as `#search-box-a7f3` (seed=42)
- **step_002_search_results**: Grid of 24 products, price filter sidebar visible on left
- **step_003_filtered_results**: 8 products under $30, first product "Logitech M185" at $24.99
- **step_004_product_detail**: Product detail page showing price $24.99, shipping options, "Add to Cart" button
- **step_005_cart**: Shopping cart with 1 item, total $24.99 + $5.99 shipping = $30.98
- **step_006_checkout**: Checkout form with saved address pre-filled, payment method selector
- **step_007_confirmation**: Order confirmation page, order ID "O-10001", estimated delivery today 6-9 PM

### 1.4 Success Assertions (DSL)
```
ALL[
  url().includes("/order/confirmation"),
  text("#order-id") != "",
  text("#order-status") == "confirmed",
  json("env", "orders.O-10001.state") == "confirmed",
  json("env", "orders.O-10001.total") <= 35,
  json("env", "orders.O-10001.shipping_speed") == "same_day",
  mem("orders.last.id") == "O-10001"
]
```

### 1.5 Memory Updates (After Execution)
```json
{
  "orders.last.id": {
    "key": "orders.last.id",
    "value": "O-10001",
    "ts": "2025-11-16T09:00:23Z",
    "source": "B1-2025-001",
    "confidence": 1.0
  },
  "orders.last.total": {
    "key": "orders.last.total",
    "value": 30.98,
    "ts": "2025-11-16T09:00:23Z",
    "source": "B1-2025-001",
    "confidence": 1.0
  },
  "orders.last.items": {
    "key": "orders.last.items",
    "value": [{"sku": "WM-5521", "name": "Logitech M185", "qty": 1, "price": 24.99}],
    "ts": "2025-11-16T09:00:23Z",
    "source": "B1-2025-001",
    "confidence": 1.0
  },
  "orders.last.timestamp": {
    "key": "orders.last.timestamp",
    "value": "2025-11-16T09:00:20Z",
    "ts": "2025-11-16T09:00:23Z",
    "source": "B1-2025-001",
    "confidence": 1.0
  }
}
```

### 1.6 Expected Metrics
- **SR (Success Rate)**: 1.0 (task completed)
- **LH-F1 (Lifelong Hallucination F1)**: 1.0 (no false memory writes)
- **Step Efficiency**: 23 steps / 22.5 seconds ≈ 1.02 steps/sec
- **Cost**: $30.98 (within budget)

---

## Example 2: C2 - Return & Refund

### 2.1 TaskSpec (JSON)
```json
{
  "task_id": "C2-2025-002",
  "family": "C",
  "episode_id": "ep-001",
  "priority": 2,
  "seed": 42,
  "time": "2025-11-18T14:00:00Z",
  "persona": {
    "reason": "product_defective",
    "preference": "refund_to_card"
  },
  "goal": "Return the wireless mouse from order O-10001 due to defect and get a refund",
  "inputs": {
    "order_id": "O-10001",
    "item_sku": "WM-5521",
    "reason": "defective",
    "refund_method": "original_payment"
  },
  "allowed_domains": [
    "shop.local"
  ],
  "preconditions": [
    "mem('orders.last.id') == 'O-10001'",
    "json('env', 'orders.O-10001.state') == 'delivered'",
    "json('env', 'orders.O-10001.return_window_days') > 0"
  ],
  "memory_keys": [
    "returns.last.id",
    "returns.last.order_id",
    "returns.last.refund_amount",
    "returns.last.state"
  ],
  "success_criteria": [
    "ALL[url().includes('/returns/'), text('#return-id') != '', json('env','returns.*.state') == 'approved', mem('returns.last.id') != '']"
  ],
  "artifacts": [
    "return_label_pdf",
    "refund_confirmation"
  ],
  "rubrics": {
    "SR": 1.0,
    "LH-F1": 0.5
  },
  "timeout": 300,
  "dependencies": ["B1-2025-001"]
}
```

### 2.2 Execution Trace (Abbreviated)
```json
{
  "task_id": "C2-2025-002",
  "agent_version": "v1.0.0",
  "steps": [
    {"t": 0, "url": "https://shop.local/orders", "act": "open"},
    {"t": 2, "act": "click", "selector": "#order-O-10001"},
    {"t": 4, "act": "wait", "selector": "#order-detail"},
    {"t": 5, "act": "click", "selector": "button.return-item"},
    {"t": 7, "act": "select", "selector": "#return-reason", "value": "defective"},
    {"t": 8, "act": "type", "selector": "#return-description", "value": "Left button not working"},
    {"t": 9, "act": "click", "selector": "#refund-method-original"},
    {"t": 10, "act": "click", "selector": "button.submit-return"},
    {"t": 12, "url": "https://shop.local/returns/R-50001", "act": "wait", "selector": "#return-id", "screenshot_id": "return_confirmation"},
    {"t": 13, "act": "assert", "selector": "#return-state", "value": "approved"}
  ]
}
```

### 2.3 Success Assertions
```
ALL[
  url().includes("/returns/"),
  text("#return-id") == "R-50001",
  text("#return-state") == "approved",
  json("env", "returns.R-50001.order_id") == "O-10001",
  json("env", "returns.R-50001.refund_amount") == 30.98,
  mem("returns.last.id") == "R-50001"
]
```

### 2.4 Memory Updates
```json
{
  "returns.last.id": {"value": "R-50001", "source": "C2-2025-002"},
  "returns.last.order_id": {"value": "O-10001", "source": "C2-2025-002"},
  "returns.last.refund_amount": {"value": 30.98, "source": "C2-2025-002"},
  "returns.last.state": {"value": "approved", "source": "C2-2025-002"}
}
```

---

## Example 3: D4 - Credit Card Replacement & Binding Update

### 3.1 TaskSpec (JSON)
```json
{
  "task_id": "D4-2025-003",
  "family": "D",
  "episode_id": "ep-001",
  "priority": 3,
  "seed": 99,
  "time": "2025-12-01T10:00:00Z",
  "persona": {
    "risk_tolerance": "low",
    "automation_preference": "high"
  },
  "goal": "Replace expiring credit card (last4: 1234) with new card (last4: 7777) and update all merchant bindings",
  "inputs": {
    "old_card_last4": "1234",
    "new_card_last4": "7777",
    "new_card_exp": "12/2029",
    "update_bindings": true,
    "merchants_priority": ["shop.local", "util.local", "travel.local"]
  },
  "allowed_domains": [
    "bank.local",
    "shop.local",
    "util.local",
    "travel.local"
  ],
  "preconditions": [
    "mem('payment.cards[0].last4') == '1234'",
    "json('env', 'payments.cards.1234.exp_date') <= '2025-12-31'"
  ],
  "memory_keys": [
    "payment.cards[0].last4",
    "payment.cards[0].exp_date",
    "payment.bindings.updated_count"
  ],
  "success_criteria": [
    "ALL[json('env','payments.cards.7777.state') == 'active', count('.merchant-binding.updated') >= 3, mem('payment.cards[0].last4') == '7777']"
  ],
  "artifacts": [
    "binding_update_report"
  ],
  "rubrics": {
    "SR": 1.0,
    "Bind-Update": 1.0,
    "LH-F1": 0.3
  },
  "timeout": 600
}
```

### 3.2 Execution Trace (Multi-Site)
```json
{
  "task_id": "D4-2025-003",
  "agent_version": "v1.0.0",
  "steps": [
    {"t": 0, "url": "https://bank.local/cards", "act": "open"},
    {"t": 2, "act": "click", "selector": "#card-1234 .activate-new-card"},
    {"t": 4, "act": "type", "selector": "#new-card-number", "value": "****7777"},
    {"t": 5, "act": "type", "selector": "#new-card-cvv", "value": "123"},
    {"t": 6, "act": "click", "selector": "button.activate-card"},
    {"t": 8, "url": "https://bank.local/cards/7777", "act": "wait", "selector": "#card-status.active", "screenshot_id": "card_activated"},

    {"t": 10, "url": "https://shop.local/account/payment", "act": "open", "note": "Update binding #1: shop.local"},
    {"t": 12, "act": "click", "selector": "#card-1234 .edit-button"},
    {"t": 13, "act": "click", "selector": "#replace-with-new-card"},
    {"t": 14, "act": "select", "selector": "#new-card-selector", "value": "7777"},
    {"t": 15, "act": "click", "selector": "button.save-payment"},
    {"t": 17, "act": "assert", "selector": "#default-card .last4", "value": "7777", "screenshot_id": "shop_updated"},

    {"t": 20, "url": "https://util.local/billing/payment", "act": "open", "note": "Update binding #2: util.local"},
    {"t": 22, "act": "click", "selector": "a.manage-autopay"},
    {"t": 24, "act": "click", "selector": "#autopay-card .update"},
    {"t": 25, "act": "type", "selector": "#card-last4", "value": "7777"},
    {"t": 26, "act": "type", "selector": "#card-exp", "value": "12/2029"},
    {"t": 27, "act": "click", "selector": "button.save-autopay"},
    {"t": 29, "act": "assert", "selector": ".autopay-status", "value": "updated", "screenshot_id": "util_updated"},

    {"t": 32, "url": "https://travel.local/profile/wallet", "act": "open", "note": "Update binding #3: travel.local"},
    {"t": 34, "act": "click", "selector": ".wallet-card[data-last4='1234'] .remove"},
    {"t": 35, "act": "click", "selector": "button.add-new-card"},
    {"t": 36, "act": "type", "selector": "#card-number", "value": "4532********7777"},
    {"t": 37, "act": "type", "selector": "#card-exp", "value": "12/29"},
    {"t": 38, "act": "click", "selector": "#set-as-default"},
    {"t": 39, "act": "click", "selector": "button.save-card"},
    {"t": 41, "act": "assert", "selector": ".wallet-card.default .last4", "value": "7777", "screenshot_id": "travel_updated"},

    {"t": 45, "url": "https://bank.local/cards/1234", "act": "open", "note": "Deactivate old card"},
    {"t": 47, "act": "click", "selector": "button.deactivate-card"},
    {"t": 48, "act": "click", "selector": "button.confirm-deactivate"},
    {"t": 50, "act": "assert", "selector": "#card-status", "value": "inactive", "screenshot_id": "old_card_deactivated"}
  ]
}
```

### 3.3 Success Assertions
```
ALL[
  json("env", "payments.cards.7777.state") == "active",
  json("env", "payments.cards.1234.state") == "inactive",
  json("env", "merchants.shop_local.payment_last4") == "7777",
  json("env", "merchants.util_local.autopay_last4") == "7777",
  json("env", "merchants.travel_local.wallet_default_last4") == "7777",
  count(".merchant-binding.updated") >= 3,
  mem("payment.cards[0].last4") == "7777",
  mem("payment.bindings.updated_count") >= 3
]
```

### 3.4 Memory Updates
```json
{
  "payment.cards[0].last4": {"value": "7777", "source": "D4-2025-003"},
  "payment.cards[0].exp_date": {"value": "12/2029", "source": "D4-2025-003"},
  "payment.bindings.updated_count": {"value": 3, "source": "D4-2025-003"}
}
```

### 3.5 Expected Metrics
- **SR**: 1.0
- **Bind-Update**: 3/3 = 1.0 (all critical merchants updated)
- **Cross-Site Success**: 4/4 sites accessed successfully

---

## Example 4: H3 - Residence Permit Renewal (Government)

### 4.1 TaskSpec (JSON)
```json
{
  "task_id": "H3-2025-004",
  "family": "H",
  "episode_id": "ep-002",
  "priority": 5,
  "seed": 123,
  "time": "2025-11-01T08:00:00Z",
  "persona": {
    "nationality": "US",
    "permit_type": "work",
    "urgency": "high"
  },
  "goal": "Renew residence permit RP-2024-77 by booking appointment slot on 2025-12-01 at 10:00",
  "inputs": {
    "permit_id": "RP-2024-77",
    "appointment_date": "2025-12-01",
    "appointment_time": "10:00",
    "documents": ["passport_scan.pdf", "employment_letter.pdf", "lease_agreement.pdf"]
  },
  "allowed_domains": [
    "gov.local"
  ],
  "preconditions": [
    "mem('identity.permit_id') == 'RP-2024-77'",
    "json('env', 'permits.RP-2024-77.expiry_date') > '2025-11-01'",
    "json('env', 'permits.RP-2024-77.renewal_eligible') == true"
  ],
  "memory_keys": [
    "permits.RP-2024-77.next_appointment",
    "permits.RP-2024-77.renewal_state",
    "permits.RP-2024-77.documents_uploaded"
  ],
  "success_criteria": [
    "ALL[url().includes('/appointments/'), text('#appointment-state') == 'booked', json('env','permits.RP-2024-77.next_appointment') == '2025-12-01T10:00']"
  ],
  "artifacts": [
    "appointment_confirmation_pdf",
    "document_receipt"
  ],
  "rubrics": {
    "SR": 1.0,
    "LH-F1": 0.4
  },
  "timeout": 600
}
```

### 4.2 Execution Trace (Complex Flow)
```json
{
  "task_id": "H3-2025-004",
  "agent_version": "v1.0.0",
  "steps": [
    {"t": 0, "url": "https://gov.local", "act": "open"},
    {"t": 2, "act": "click", "selector": "a[href='/residence-permits']"},
    {"t": 4, "act": "wait", "selector": "#permit-services"},
    {"t": 5, "act": "click", "selector": "a.renewal-service"},
    {"t": 7, "act": "type", "selector": "#permit-id-input", "value": "RP-2024-77"},
    {"t": 8, "act": "click", "selector": "button.check-eligibility"},
    {"t": 10, "act": "wait", "selector": ".eligibility-result.eligible", "screenshot_id": "eligibility_confirmed"},
    {"t": 11, "act": "click", "selector": "button.start-renewal"},

    {"t": 13, "url": "https://gov.local/permits/RP-2024-77/renew/documents", "act": "wait", "selector": "#document-upload-form"},
    {"t": 15, "act": "upload", "selector": "#upload-passport", "value": "passport_scan.pdf"},
    {"t": 20, "act": "wait", "selector": ".upload-success[data-doc='passport']"},
    {"t": 22, "act": "upload", "selector": "#upload-employment", "value": "employment_letter.pdf"},
    {"t": 27, "act": "wait", "selector": ".upload-success[data-doc='employment']"},
    {"t": 29, "act": "upload", "selector": "#upload-lease", "value": "lease_agreement.pdf"},
    {"t": 34, "act": "wait", "selector": ".upload-success[data-doc='lease']", "screenshot_id": "documents_uploaded"},
    {"t": 35, "act": "click", "selector": "button.proceed-to-appointment"},

    {"t": 37, "url": "https://gov.local/permits/RP-2024-77/renew/appointment", "act": "wait", "selector": "#calendar-widget"},
    {"t": 38, "act": "click", "selector": ".calendar-date[data-date='2025-12-01']"},
    {"t": 40, "act": "wait", "selector": ".time-slots-available"},
    {"t": 41, "act": "click", "selector": ".time-slot[data-time='10:00']"},
    {"t": 42, "act": "assert", "selector": ".time-slot[data-time='10:00'].selected"},
    {"t": 43, "act": "click", "selector": "button.confirm-appointment"},

    {"t": 45, "url": "https://gov.local/appointments/APT-9988", "act": "wait", "selector": "#appointment-confirmation", "screenshot_id": "appointment_booked"},
    {"t": 46, "act": "assert", "selector": "#appointment-date", "value": "2025-12-01"},
    {"t": 47, "act": "assert", "selector": "#appointment-time", "value": "10:00"},
    {"t": 48, "act": "assert", "selector": "#appointment-state", "value": "booked"},
    {"t": 50, "act": "download", "selector": "a.download-confirmation", "value": "appointment_confirmation.pdf"}
  ]
}
```

### 4.3 Success Assertions
```
ALL[
  url().includes("/appointments/"),
  text("#appointment-id") == "APT-9988",
  text("#appointment-state") == "booked",
  text("#appointment-date") == "2025-12-01",
  text("#appointment-time") == "10:00",
  json("env", "permits.RP-2024-77.next_appointment") == "2025-12-01T10:00",
  json("env", "permits.RP-2024-77.renewal_state") == "appointment_scheduled",
  json("env", "permits.RP-2024-77.documents_uploaded") >= 3,
  mem("permits.RP-2024-77.next_appointment") == "2025-12-01T10:00"
]
```

### 4.4 Memory Updates
```json
{
  "permits.RP-2024-77.next_appointment": {
    "value": "2025-12-01T10:00",
    "source": "H3-2025-004"
  },
  "permits.RP-2024-77.renewal_state": {
    "value": "appointment_scheduled",
    "source": "H3-2025-004"
  },
  "permits.RP-2024-77.documents_uploaded": {
    "value": ["passport", "employment", "lease"],
    "source": "H3-2025-004"
  }
}
```

---

## Example 5: M1 - Lost Bank Card Crisis Handling

### 5.1 TaskSpec (JSON)
```json
{
  "task_id": "M1-2025-005",
  "family": "M",
  "episode_id": "ep-003",
  "priority": 10,
  "seed": 777,
  "time": "2025-11-16T15:30:00Z",
  "persona": {
    "panic_level": "high",
    "merchant_count": 8
  },
  "goal": "Block lost card 1234, order replacement, and update 5+ merchant bindings to temporary virtual card",
  "inputs": {
    "lost_card_last4": "1234",
    "reissue": true,
    "use_virtual_card": true,
    "critical_merchants": ["shop.local", "util.local", "food.local", "transport.local", "stream.local"]
  },
  "allowed_domains": [
    "bank.local",
    "shop.local",
    "util.local",
    "food.local",
    "transport.local",
    "stream.local"
  ],
  "preconditions": [
    "mem('payment.cards[0].last4') == '1234'",
    "json('env', 'payments.cards.1234.state') == 'active'"
  ],
  "memory_keys": [
    "payment.cards[0].state",
    "payment.cards.virtual.last4",
    "payment.crisis.last_block_time",
    "payment.bindings.temp_updated_count"
  ],
  "success_criteria": [
    "ALL[json('env','payments.cards.1234.state') == 'blocked', json('env','payments.cards.virtual.state') == 'active', count('.merchant-binding.updated') >= 5]"
  ],
  "artifacts": [
    "block_confirmation",
    "virtual_card_info",
    "binding_update_report"
  ],
  "rubrics": {
    "SR": 1.0,
    "Bind-Update": 1.0,
    "Crisis-Response-Time": 0.5
  },
  "timeout": 900
}
```

### 5.2 Execution Trace (Crisis Response)
```json
{
  "task_id": "M1-2025-005",
  "agent_version": "v1.0.0",
  "steps": [
    {"t": 0, "url": "https://bank.local/cards/emergency", "act": "open", "note": "Direct to emergency page"},
    {"t": 2, "act": "click", "selector": "#report-lost-card"},
    {"t": 3, "act": "select", "selector": "#card-selector", "value": "1234"},
    {"t": 4, "act": "click", "selector": "#reason-lost"},
    {"t": 5, "act": "click", "selector": "button.block-immediately"},
    {"t": 7, "act": "wait", "selector": ".block-confirmation", "screenshot_id": "card_blocked"},
    {"t": 8, "act": "assert", "selector": "#card-1234-status", "value": "blocked"},

    {"t": 10, "act": "click", "selector": "#issue-virtual-card"},
    {"t": 12, "act": "wait", "selector": "#virtual-card-details", "screenshot_id": "virtual_card_issued"},
    {"t": 13, "act": "assert", "selector": "#virtual-card-last4"},

    {"t": 15, "url": "https://shop.local/account/payment", "act": "open", "note": "Update merchant #1"},
    {"t": 17, "act": "click", "selector": ".default-card .edit"},
    {"t": 18, "act": "click", "selector": "#use-virtual-card"},
    {"t": 19, "act": "click", "selector": "button.save-payment"},
    {"t": 21, "act": "assert", "selector": ".payment-updated", "screenshot_id": "merchant1_updated"},

    {"t": 23, "url": "https://util.local/billing/payment", "act": "open", "note": "Update merchant #2"},
    {"t": 25, "act": "click", "selector": ".autopay-edit"},
    {"t": 26, "act": "select", "selector": "#payment-method", "value": "virtual"},
    {"t": 27, "act": "click", "selector": "button.update-autopay"},
    {"t": 29, "act": "assert", "selector": ".autopay-updated"},

    {"t": 31, "url": "https://food.local/wallet", "act": "open", "note": "Update merchant #3"},
    {"t": 33, "act": "click", "selector": ".wallet-card[data-last4='1234'] .replace"},
    {"t": 34, "act": "click", "selector": "#add-virtual-card"},
    {"t": 35, "act": "click", "selector": "button.save-wallet"},
    {"t": 37, "act": "assert", "selector": ".wallet-updated"},

    {"t": 39, "url": "https://transport.local/payment", "act": "open", "note": "Update merchant #4"},
    {"t": 41, "act": "click", "selector": ".default-payment .change"},
    {"t": 42, "act": "select", "selector": "#card-list", "value": "virtual"},
    {"t": 43, "act": "click", "selector": "button.save"},
    {"t": 45, "act": "assert", "selector": ".payment-changed"},

    {"t": 47, "url": "https://stream.local/account/billing", "act": "open", "note": "Update merchant #5"},
    {"t": 49, "act": "click", "selector": ".subscription-payment .update"},
    {"t": 50, "act": "select", "selector": "#billing-card", "value": "virtual"},
    {"t": 51, "act": "click", "selector": "button.update-billing"},
    {"t": 53, "act": "assert", "selector": ".billing-updated", "screenshot_id": "merchant5_updated"},

    {"t": 55, "url": "https://bank.local/cards/1234/replacement", "act": "open", "note": "Order physical replacement"},
    {"t": 57, "act": "click", "selector": "#same-address"},
    {"t": 58, "act": "click", "selector": "#expedited-shipping"},
    {"t": 59, "act": "click", "selector": "button.order-replacement"},
    {"t": 61, "act": "wait", "selector": "#replacement-ordered", "screenshot_id": "replacement_ordered"},
    {"t": 62, "act": "assert", "selector": "#replacement-status", "value": "ordered"}
  ]
}
```

### 5.3 Success Assertions
```
ALL[
  json("env", "payments.cards.1234.state") == "blocked",
  json("env", "payments.cards.1234.blocked_at") != "",
  json("env", "payments.cards.virtual.state") == "active",
  json("env", "merchants.shop_local.payment_method") == "virtual",
  json("env", "merchants.util_local.autopay_method") == "virtual",
  json("env", "merchants.food_local.wallet_method") == "virtual",
  json("env", "merchants.transport_local.payment_method") == "virtual",
  json("env", "merchants.stream_local.billing_method") == "virtual",
  count(".merchant-binding.updated") >= 5,
  mem("payment.cards[0].state") == "blocked",
  mem("payment.cards.virtual.last4") != "",
  mem("payment.bindings.temp_updated_count") >= 5
]
```

### 5.4 Memory Updates
```json
{
  "payment.cards[0].state": {"value": "blocked", "source": "M1-2025-005"},
  "payment.cards.virtual.last4": {"value": "8899", "source": "M1-2025-005"},
  "payment.crisis.last_block_time": {"value": "2025-11-16T15:30:07Z", "source": "M1-2025-005"},
  "payment.bindings.temp_updated_count": {"value": 5, "source": "M1-2025-005"}
}
```

### 5.5 Expected Metrics
- **SR**: 1.0
- **Bind-Update**: 5/5 = 1.0
- **Crisis-Response-Time**: 62 seconds (from block to all bindings updated)
- **Multi-Site Success**: 6/6 sites

---

## Summary

### Coverage Analysis
| Example | Family | Complexity | Sites | Steps | Memory Ops | Key Features |
|---------|--------|------------|-------|-------|------------|--------------|
| B1 | Shopping | Low | 1 | 23 | 4 writes | Basic flow, budget constraint |
| C2 | Returns | Medium | 1 | 10 | 4 writes | Depends on B1, state transition |
| D4 | Finance | High | 4 | 50 | 3 writes | Multi-site binding update |
| H3 | Government | High | 1 | 50 | 3 writes | Complex form, file upload |
| M1 | Crisis | Very High | 6 | 62 | 4 writes | Emergency response, parallel updates |

### Total Test Coverage
- **Task Families**: 5/13 (38%)
- **Interaction Patterns**: Search, filter, form fill, upload, download, multi-site
- **Memory Operations**: Read preconditions, write results, cross-task references
- **Assertions**: Simple equality, counts, JSON path, temporal logic

### Next Steps
1. Implement these 5 tasks in sandbox environment
2. Validate assertions DSL interpreter
3. Collect baseline metrics
4. Generate remaining 59 tasks following these templates
