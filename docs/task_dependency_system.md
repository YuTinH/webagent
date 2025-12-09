# Task Dependency System - Advanced Design

**Version**: 2.0
**Date**: 2025-11-28
**Difficulty Level**: 3-5 (Medium to Expert)

---

## 🎯 Design Philosophy

**Core Principle**: Tasks must have **real, cascading consequences**. A failed payment should prevent food delivery, which should prevent rating the meal, which should affect user reputation score.

### Key Features
1. **Hard Dependencies**: Tasks fail immediately if prerequisites aren't met
2. **State Propagation**: Success/failure ripples through the system
3. **Resource Constraints**: Limited money, inventory, time slots
4. **Cross-Domain Effects**: Shopping affects banking, banking affects utilities
5. **Temporal Constraints**: Some tasks must complete before others start

---

## 📊 Task Dependency Chains

### Chain 1: Shopping Crisis (High Difficulty)
```
T1: B1-shopping (Buy product - $50)
  ↓ [Order must exist & be confirmed]
T2: B5-track-orders (Track delivery)
  ↓ [Order must be delivered before return window]
T3: C2-return (Return defective item)
  ↓ [Refund must be issued to card]
T4: D1-check-balance (Verify refund received)
  ↓ [Balance must be sufficient after refund]
T5: K2-aa-split (Split expenses with roommate)

FAILURE SCENARIOS:
- T1 fails → No order exists → T2/T3/T5 all fail
- T1 overspends → Insufficient funds → T4 shows negative balance
- T3 fails → No refund → T4 shows wrong amount → T5 calculation wrong
- T5 fails → Roommate doesn't pay → Insufficient funds for next chain
```

### Chain 2: Financial Crisis (Expert Difficulty)
```
T1: D1-check-balance (Balance: $1000)
  ↓ [Must have minimum balance]
T2: H1-check-bill (Utility bill: $150 due in 3 days)
  ↓ [Must set up payment before due date]
T3: D3-autopay (Setup autopay for utilities)
  ↓ [Autopay must be active]
T4: Simulate time passage (3 days)
  ↓ [Autopay executes, balance drops]
T5: M1-lost-card-crisis (Card lost! Need emergency replacement)
  ↓ [Must cancel autopay on old card]
T6: D4-card-replacement (Get new card, rebind autopay)
  ↓ [If autopay not rebound → next bill fails]
T7: H1-check-bill (Next month - verify autopay worked)

FAILURE SCENARIOS:
- T1 shows low balance → T3 autopay rejected (insufficient funds)
- T3 fails → T4 bill not paid → Late fees added → Balance drain
- T5 delays → Autopay charges blocked card → Payment fails
- T6 incomplete → Autopay still on old card → Next bill fails
```

### Chain 3: Government Services Chain (Medium-High Difficulty)
```
T1: H2-permit-app (Apply for parking permit - requires proof)
  ↓ [Must upload valid documents]
T2: Wait for approval (24-48 hours simulated)
  ↓ [Permit approved or rejected]
T3a: If approved → Can park legally
T3b: If rejected → Must resubmit → Delayed parking
  ↓ [Without permit → Parking ticket issued]
T4: D1-check-balance (Find parking fine charged)
  ↓ [Must pay fine from balance]
T5: Contest ticket (requires permit proof)

FAILURE SCENARIOS:
- T1 missing documents → Rejected → T3b triggered
- T2 timeout → Can't wait forever → Risk parking anyway
- T3b → Parking ticket → T4 shows unexpected charge
- T5 needs original permit → If T1 failed, can't contest
```

### Chain 4: Cross-Site Multi-Step Workflow (Expert)
```
T1: B1-shopping (Buy groceries - $80)
  ↓ [Payment from card ending in 1234]
T2: D1-check-balance (Verify charge posted)
  ↓ [Balance: $1000 - $80 = $920]
T3: D3-autopay (Setup $150 utility autopay)
  ↓ [Scheduled for tomorrow]
T4: B1-shopping (Emergency purchase - $800)
  ↓ [Balance: $920 - $800 = $120]
T5: [TIME PASSES - Autopay attempts to charge $150]
  ↓ [Only $120 available → AUTOPAY FAILS]
T6: H1-check-bill (See failed payment + $25 late fee)
  ↓ [Balance: $120 - $25 = $95]
T7: M1-lost-card-crisis (Card compromised! Block it)
  ↓ [All autopays on that card now broken]
T8: D4-card-replacement (Get new card)
  ↓ [Must rebind ALL autopays]
T9: K2-aa-split (Roommate owes share of utility)
  ↓ [Calculate split including late fees]
T10: D1-check-balance (Final reconciliation)

FAILURE SCENARIOS:
- T4 overspends → T5 autopay fails → Late fees cascade
- T7 without updating autopay → All future bills fail
- T8 incomplete → Merchant bindings lost → Services cancelled
- T9 wrong calculation → Roommate disputes → Relationship damage
```

---

## 🔗 Dependency Types

### 1. **Data Dependencies** (Must have exact data)
```json
{
  "preconditions": [
    "mem('orders.last.id') == 'O-10001'",
    "mem('orders.last.state') == 'delivered'",
    "mem('orders.last.total') > 0"
  ],
  "failure_message": "No completed order found. Must complete B1-shopping first."
}
```

### 2. **State Dependencies** (System must be in specific state)
```json
{
  "preconditions": [
    "json('env', 'cards.*.state') == 'active'",
    "json('env', 'banking.balance.checking') >= 1000",
    "json('env', 'permits.*.status') == 'approved'"
  ],
  "failure_message": "Account not in valid state for this operation."
}
```

### 3. **Resource Dependencies** (Consume limited resources)
```json
{
  "preconditions": [
    "json('env', 'banking.balance.checking') >= 500",
    "json('env', 'products.WM-5521.stock') > 0"
  ],
  "on_execution": {
    "deduct_balance": 500,
    "decrement_stock": "WM-5521"
  },
  "rollback_on_failure": true
}
```

### 4. **Temporal Dependencies** (Time-based)
```json
{
  "preconditions": [
    "time_since('orders.last.timestamp') >= 86400",
    "time_until('bills.next_due') <= 259200"
  ],
  "failure_message": "Cannot return order until 24 hours after delivery."
}
```

### 5. **Cascading Failures** (Failures propagate)
```json
{
  "on_failure": {
    "block_tasks": ["B5-track-orders", "C2-return"],
    "add_penalty": {
      "balance_deduction": 50,
      "reputation_impact": -10
    },
    "trigger_events": ["order_cancelled", "refund_delayed"]
  }
}
```

---

## 💾 State Propagation System

### Memory Structure (Enhanced)
```json
{
  "orders": {
    "last": {
      "id": "O-10001",
      "total": 49.99,
      "state": "delivered",
      "items": ["WM-5521"],
      "timestamp": "2025-11-16T09:30:00Z",
      "can_return": true,
      "return_deadline": "2025-11-30T23:59:59Z"
    },
    "all": ["O-10001", "O-10002"],
    "total_spent": 149.97
  },
  "banking": {
    "balance": {
      "checking": 920.00,
      "last_check": "2025-11-16T10:00:00Z",
      "pending_charges": [
        {"amount": 150, "merchant": "Utility Co", "date": "2025-11-17"}
      ]
    },
    "cards": [
      {
        "last4": "1234",
        "state": "active",
        "autopays": ["util-autopay-001"]
      }
    ]
  },
  "returns": {
    "last": {
      "id": "R-50001",
      "order_id": "O-10001",
      "state": "approved",
      "refund_amount": 49.99,
      "refund_posted": false
    }
  },
  "permits": {
    "parking": {
      "status": "pending",
      "application_id": "P-2025-001",
      "submitted": "2025-11-16T11:00:00Z"
    }
  },
  "autopay": {
    "util-autopay-001": {
      "card": "1234",
      "amount": 150,
      "frequency": "monthly",
      "next_charge": "2025-11-17T00:00:00Z",
      "active": true
    }
  }
}
```

### State Transitions
```python
# When B1-shopping completes
{
  "updates": [
    {"key": "orders.last", "value": {...}},
    {"key": "banking.balance.checking", "operation": "subtract", "amount": 49.99},
    {"key": "banking.pending_charges", "operation": "clear"}
  ],
  "enables": ["B5-track-orders", "C2-return", "K2-aa-split"]
}

# When C2-return completes
{
  "updates": [
    {"key": "returns.last", "value": {...}},
    {"key": "orders.O-10001.state", "value": "returned"},
    {"key": "banking.pending_charges", "operation": "add",
     "value": {"amount": 49.99, "type": "refund", "eta": "3-5 days"}}
  ],
  "enables": ["D1-check-balance"]
}

# When M1-lost-card-crisis completes
{
  "updates": [
    {"key": "banking.cards[0].state", "value": "blocked"},
    {"key": "banking.cards[0].blocked_reason", "value": "lost_reported"},
    {"key": "autopay.*.active", "value": false, "where": "card == '1234'"}
  ],
  "disables": ["All tasks requiring card 1234"],
  "requires_fix": ["D4-card-replacement"]
}
```

---

## 🎲 Advanced Difficulty Features

### Level 3: Medium Challenge

#### 1. Dynamic Inventory
```python
class DynamicInventory:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def get_stock(self, sku):
        # Stock varies by seed + time
        base_stock = 10
        variation = self.rng.randint(-5, 15)
        return max(0, base_stock + variation)

    def apply_to_page(self, html):
        # Replace stock values in HTML
        for product in products:
            stock = self.get_stock(product.sku)
            if stock == 0:
                # Show "Out of Stock" - task must adapt
                html = html.replace(f'data-stock="{product.sku}"',
                                  f'data-stock="0" class="out-of-stock"')
```

#### 2. Price Variations
```python
class DynamicPricing:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def get_price(self, base_price, sku):
        # Prices vary ±20% based on seed
        multiplier = self.rng.uniform(0.8, 1.2)
        return round(base_price * multiplier, 2)

    def affects_task(self, task, budget):
        # If price increased, budget constraint might fail
        if self.get_price(29.99, "WM-5521") > budget:
            return "FAIL: Item exceeds budget"
```

#### 3. Form Validation Errors
```python
class FormValidator:
    def validate_permit_application(self, data):
        errors = []

        # Dynamic validation rules
        if not data.get('proof_of_address'):
            errors.append("Missing proof of address")

        if data.get('vehicle_year') < 2010:
            errors.append("Vehicle too old for permit")

        # Random rejections (10% chance)
        if random.random() < 0.1:
            errors.append("Address not in eligible zone")

        return errors
```

### Level 4: Advanced

#### 1. Session Management
```python
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.timeout = 300  # 5 minutes

    def check_session(self, task):
        # Sessions expire between tasks
        if time.time() - task.start_time > self.timeout:
            return "SESSION_EXPIRED: Must login again"

        # Concurrent sessions conflict
        if self.sessions.get(task.user_id) != task.session_id:
            return "SESSION_CONFLICT: Logged in elsewhere"
```

#### 2. Error Recovery Required
```python
class ErrorScenarios:
    scenarios = [
        {
            "trigger": "payment_processing",
            "probability": 0.15,
            "error": "Payment gateway timeout",
            "recovery": "Must retry payment within 10 minutes"
        },
        {
            "trigger": "document_upload",
            "probability": 0.10,
            "error": "File too large",
            "recovery": "Must compress file or use different format"
        },
        {
            "trigger": "autopay_setup",
            "probability": 0.20,
            "error": "Bank authorization failed",
            "recovery": "Must verify account via micro-deposits"
        }
    ]
```

#### 3. Complex State Tracking
```python
class StateTracker:
    def track_multi_task_state(self):
        # Track states across tasks
        state = {
            "balance_history": [],
            "order_states": {},
            "autopay_failures": 0,
            "late_fees_accumulated": 0,
            "reputation_score": 100
        }

        # Reputation affects future tasks
        if state["autopay_failures"] > 2:
            state["reputation_score"] -= 30
            # Banks may reject autopay setup

        if state["late_fees_accumulated"] > 100:
            # Utility company requires deposit
            state["required_deposit"] = 200
```

### Level 5: Expert

#### 1. Full DOM Shuffling
```python
class DOMShuffler:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def shuffle_page(self, html):
        soup = BeautifulSoup(html, 'html.parser')

        # Shuffle navigation items
        nav = soup.find('nav')
        if nav:
            items = nav.find_all('li')
            self.rng.shuffle(items)
            for item in items:
                nav.append(item)

        # Shuffle product cards
        products = soup.find_all(class_='product-card')
        container = products[0].parent if products else None
        if container:
            self.rng.shuffle(products)
            for product in products:
                container.append(product)

        # Randomize CSS classes
        for elem in soup.find_all(class_=True):
            elem['class'] = [self.randomize_class(c) for c in elem['class']]

        return str(soup)

    def randomize_class(self, cls):
        # btn → button-primary → action-btn (semantic equivalents)
        equivalents = {
            'btn': ['button', 'action-btn', 'clickable'],
            'card': ['item', 'box', 'container'],
            'input': ['field', 'textbox', 'form-control']
        }
        options = equivalents.get(cls, [cls])
        return self.rng.choice(options)
```

#### 2. Semantic Equivalents
```python
class SemanticVariations:
    def transform_element(self, elem_type, seed):
        variations = {
            'button': [
                '<button class="btn">Submit</button>',
                '<div class="clickable" onclick="submit()">Submit</div>',
                '<a href="#" onclick="submit(); return false;">Submit</a>',
                '<input type="button" value="Submit" onclick="submit()">'
            ],
            'text_input': [
                '<input type="text" name="email">',
                '<div contenteditable="true" data-field="email"></div>',
                '<textarea name="email" rows="1"></textarea>'
            ]
        }

        options = variations[elem_type]
        return random.Random(seed).choice(options)
```

#### 3. Multi-Tab Workflows
```python
class MultiTabScenario:
    """
    Some tasks require multiple tabs/windows:
    - Tab 1: Shopping cart
    - Tab 2: Banking to verify balance
    - Tab 3: Return to shopping to complete checkout

    Agent must coordinate across tabs and remember context.
    """

    def require_multi_tab(self, task):
        if task.task_id == "K2-aa-split":
            return {
                "tabs_needed": 3,
                "tab_1": "shop.local/orders",  # View shared orders
                "tab_2": "bank.local/transactions",  # Check who paid
                "tab_3": "pay.local/split",  # Create split request
                "coordination": "Must copy order IDs from tab 1 to tab 3"
            }
```

#### 4. Time-Sensitive Operations
```python
class TimeConstraints:
    def apply_constraints(self, task):
        constraints = {
            "autopay_setup": {
                "must_complete_before": "next_bill_due - 24_hours",
                "failure": "Bill will be late, incur fees"
            },
            "return_window": {
                "must_complete_before": "order_delivered + 30_days",
                "failure": "Return rejected, no refund"
            },
            "permit_renewal": {
                "must_complete_before": "permit_expiry",
                "failure": "Parking ticket issued, $150 fine"
            },
            "card_replacement_urgency": {
                "must_complete_before": "next_autopay_charge",
                "failure": "Autopay fails, services suspended"
            }
        }
```

---

## 🧪 Testing Strategy

### 1. Dependency Validation Tests
```python
def test_hard_dependency():
    # Try C2-return without B1-shopping
    result = executor.run("C2-return", skip_preconditions=False)
    assert result.status == "FAILED"
    assert "precondition" in result.error.lower()
    assert "B1-shopping" in result.error

def test_cascading_failure():
    # B1 fails → C2, B5, K2 all fail
    executor.run("B1-shopping", force_fail=True)

    c2_result = executor.run("C2-return")
    assert c2_result.status == "BLOCKED"

    b5_result = executor.run("B5-track-orders")
    assert b5_result.status == "BLOCKED"
```

### 2. Resource Constraint Tests
```python
def test_insufficient_funds():
    # Set balance to $50
    executor.set_env_state("banking.balance.checking", 50)

    # Try to buy $500 item
    result = executor.run("B1-shopping", params={"max_price": 500})
    assert result.status == "FAILED"
    assert "insufficient funds" in result.error.lower()

def test_out_of_stock():
    # Set product stock to 0
    executor.set_env_state("products.WM-5521.stock", 0)

    result = executor.run("B1-shopping", params={"item_sku": "WM-5521"})
    assert result.status == "FAILED" or result.adapted_to_alternative
```

### 3. State Propagation Tests
```python
def test_state_propagation():
    # Complete B1
    b1_result = executor.run("B1-shopping")
    assert b1_result.status == "SUCCESS"

    # Check memory updated
    memory = executor.get_memory()
    assert memory["orders.last.id"] is not None

    # Check balance deducted
    balance = executor.get_env_state("banking.balance.checking")
    assert balance == 1000 - b1_result.amount_charged

    # C2 should now be enabled
    c2_result = executor.run("C2-return", skip_preconditions=False)
    assert c2_result.status != "BLOCKED"
```

---

## 📈 Difficulty Progression

| Level | Features | Agent Success Rate | Example |
|-------|----------|-------------------|---------|
| 1 | Static pages, no dependencies | 90-100% | Current baseline |
| 2 | CSS randomization, soft dependencies | 70-90% | Element order shuffled |
| 3 | Dynamic content, resource constraints | 50-70% | Out of stock, price changes |
| 4 | Session management, error recovery | 30-50% | Payment failures, timeouts |
| 5 | Full DOM shuffle, multi-tab, time limits | 10-30% | Semantic equivalents |

---

## 🎯 Implementation Plan

### Phase 1: Strengthen Dependencies (Week 1)
- [ ] Update all task preconditions to be strict
- [ ] Implement state propagation system
- [ ] Add resource tracking (balance, stock, etc.)
- [ ] Create dependency validator

### Phase 2: Add Medium Difficulty (Week 2)
- [ ] Dynamic inventory system
- [ ] Price variations based on seed
- [ ] Form validation errors
- [ ] Session timeouts

### Phase 3: Add Advanced Features (Week 3)
- [ ] Error recovery scenarios
- [ ] Multi-task state tracking
- [ ] Cascading failure system
- [ ] Temporal constraints

### Phase 4: Expert Level (Week 4)
- [ ] DOM shuffling engine
- [ ] Semantic element variations
- [ ] Multi-tab coordination
- [ ] Time-sensitive operations

---

## 🚀 Next Steps

1. Review this design with user
2. Implement state propagation system
3. Update task specs with strict dependencies
4. Add perturbation engine
5. Create comprehensive test suite
6. Benchmark with real agents

---

**Status**: Design complete, ready for implementation
**Estimated Effort**: 2-3 weeks for full implementation
**Expected Impact**: Agent success rate drops from 100% to 30-70% (realistic challenge)
