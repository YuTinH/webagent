# WebAgent Dynamic Suite v2 - Enhanced Version

## 🎯 Overview

This enhanced version adds **strong task dependencies**, **dynamic difficulty levels**, and **realistic failure scenarios** to create a challenging benchmark for web agents.

### Key Features

✅ **Task Dependencies**: Tasks depend on each other - failures cascade
✅ **5 Difficulty Levels**: From baseline to expert
✅ **State Propagation**: Changes in one task affect others
✅ **Resource Constraints**: Limited money, inventory, time
✅ **Dynamic Perturbations**: DOM shuffling, price changes, errors
✅ **Realistic Scenarios**: Payment failures, out of stock, session timeouts

---

## 📊 Difficulty Levels

| Level | Name | Features | Expected Success Rate |
|-------|------|----------|---------------------|
| 1 | Baseline | Static pages, no perturbations | 90-100% |
| 2 | Light | CSS/DOM shuffling, class randomization | 70-90% |
| 3 | Medium | Dynamic prices, inventory, form errors | 50-70% |
| 4 | Advanced | Payment errors, session timeouts, recovery | 30-50% |
| 5 | Expert | Full DOM shuffle, semantic equivalents | 10-30% |

---

## 🔗 Task Dependency Chains

### Chain 1: Shopping & Returns
```
B1-shopping (Buy product $50)
  ↓ Order must exist
C2-return (Return defective item)
  ↓ Refund must be issued
D1-check-balance (Verify refund received)
  ↓ Balance must be sufficient
K2-aa-split (Split expenses with roommate)
```

**Failure Scenarios:**
- B1 fails → No order → C2 blocked ❌
- B1 overspends → Insufficient balance later
- C2 fails → No refund → D1 shows wrong amount
- K2 fails → Roommate doesn't pay → Next chain blocked

### Chain 2: Financial Crisis
```
D1-check-balance ($1000)
  ↓ Must have minimum balance
H1-check-bill (Utility $150 due)
  ↓ Must pay before due date
D3-autopay (Setup autopay)
  ↓ Autopay active
[Time passes - autopay charges]
  ↓ Balance drops
M1-lost-card-crisis (Card lost!)
  ↓ Must cancel autopay on old card
D4-card-replacement (New card, rebind autopay)
  ↓ If not rebound → next bill fails
```

**Failure Scenarios:**
- D1 low balance → D3 autopay rejected
- D3 fails → H1 bill not paid → Late fees
- M1 delays → Autopay on blocked card → Payment fails
- D4 incomplete → Autopay broken → Services cancelled

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Server

```bash
python3 server.py 8014
```

### 3. Run Tasks with Dependencies

#### Basic Usage

```python
from agent.enhanced_executor import run_task_with_dependencies
from agent.perturbation_engine import PerturbationLevel

# Run single task at advanced difficulty (recommended)
result = run_task_with_dependencies(
    task_dir="B1-shopping",
    perturbation_level=PerturbationLevel.ADVANCED,  # Level 4
    seed=42,
    headless=True
)

print(f"Success: {result.success}")
print(f"Steps: {result.steps_completed}/{result.steps_total}")
```

#### Run Task Chain

```python
from agent.enhanced_executor import EnhancedTaskExecutor
from agent.perturbation_engine import PerturbationLevel

executor = EnhancedTaskExecutor(
    headless=True,
    perturbation_seed=42,
    perturbation_level=PerturbationLevel.ADVANCED,
    enable_dependencies=True
)

# Run B1 first (creates order)
b1_result = executor.run("tasks/B1-shopping/task_spec.json")

if b1_result.success:
    # Run C2 (depends on B1 order)
    c2_result = executor.run("tasks/C2-return/task_spec.json")

    if not c2_result.dependencies_met:
        print("C2 blocked due to missing dependencies")
```

### 4. Test Dependency Chains

```bash
# Run all test scenarios
python3 test_dependency_chains.py --level 3 --seed 42

# Run specific scenario
python3 test_dependency_chains.py --scenario 1 --level 4

# Test cascading failures
python3 test_dependency_chains.py --scenario 5 --level 5
```

---

## 📖 Detailed Examples

### Example 1: Success Chain

```python
"""
Scenario: Shopping and return - everything succeeds
"""
from agent.state_propagation import StatePropagationEngine

# Setup: Reset state
engine = StatePropagationEngine()
engine.set_env_state('banking.balance.checking', 1000.00)

# Step 1: Buy product ($50)
b1_result = run_task_with_dependencies("B1-shopping", level=3)
# ✅ Order O-10001 created
# 💰 Balance: $1000 - $50 = $950

# Step 2: Return product
c2_result = run_task_with_dependencies("C2-return", level=3)
# ✅ Return R-50001 approved
# 💰 Balance: $950 + $50 = $1000

# Step 3: Check balance
d1_result = run_task_with_dependencies("D1-check-balance", level=3)
# ✅ Balance verified: $1000
```

### Example 2: Insufficient Balance Failure

```python
"""
Scenario: Not enough money to buy product
"""
# Setup: Set low balance
engine.set_env_state('banking.balance.checking', 10.00)

# Try to buy $30 product
result = run_task_with_dependencies("B1-shopping", level=3)

# ❌ FAILED: "Insufficient balance: $10.00 < $30.00"
# Subsequent tasks blocked
```

### Example 3: Cascading Failure

```python
"""
Scenario: B1 fails → C2 blocked → entire chain broken
"""
# Setup: Insufficient balance
engine.set_env_state('banking.balance.checking', 10.00)

# B1 fails
b1_result = run_task_with_dependencies("B1-shopping")
assert not b1_result.success  # ❌

# C2 blocked (no order exists)
c2_result = run_task_with_dependencies("C2-return")
assert c2_result.final_state == "blocked"  # 🚫
assert "B1-shopping" in c2_result.dependency_errors[0]
```

### Example 4: Out of Stock (Level 3+)

```python
"""
Scenario: Product out of stock at medium difficulty
"""
executor = EnhancedTaskExecutor(
    perturbation_level=PerturbationLevel.MEDIUM,
    perturbation_seed=123  # Some seeds cause out-of-stock
)

result = executor.run("tasks/B1-shopping/task_spec.json")

if "out of stock" in result.resource_constraints_hit:
    print("❌ Product unavailable - agent must adapt!")
    # Agent could:
    # 1. Choose alternative product
    # 2. Wait for restock
    # 3. Fail gracefully
```

### Example 5: Payment Error (Level 4+)

```python
"""
Scenario: Payment gateway timeout at advanced difficulty
"""
executor = EnhancedTaskExecutor(
    perturbation_level=PerturbationLevel.ADVANCED
)

# During checkout, payment might fail
result = executor.run("tasks/B1-shopping/task_spec.json")

# Agent must handle:
# - Payment timeout → Retry
# - Card declined → Try different card
# - Network error → Wait and retry
```

---

## 🎭 Perturbation System

### DOM Shuffling (Level 2+)

```python
from agent.perturbation_engine import PerturbationEngine

engine = PerturbationEngine(seed=42, level=2)

html = """
<nav>
  <li><a href="/home">Home</a></li>
  <li><a href="/products">Products</a></li>
  <li><a href="/cart">Cart</a></li>
</nav>
"""

# Navigation order randomized
perturbed = engine.perturb_page(html, 'navigation')
# Result: Products, Cart, Home (order changed!)
```

### Dynamic Pricing (Level 3+)

```python
engine = PerturbationEngine(seed=42, level=3)

base_price = 29.99
sku = "WM-5521"

# Price varies ±20% based on seed
actual_price = engine.content_manager.get_dynamic_price(sku, base_price)
# Result: $34.56 (might be $24.99 with different seed)
```

### Error Injection (Level 4+)

```python
engine = PerturbationEngine(seed=42, level=4)

# Check if payment error should occur
error = engine.should_inject_payment_error()

if error:
    print(f"Error: {error['message']}")
    # "Payment gateway timeout. Please try again."

    if error['recoverable']:
        # Agent can retry
        pass
```

---

## 💾 State Management

### Reading State

```python
from agent.state_propagation import StatePropagationEngine

engine = StatePropagationEngine()

# Get memory value
order_id = engine.get_memory('orders.last.id')

# Get database state
balance = engine.get_env_state('banking.balance.checking')
stock = engine.get_env_state('products.WM-5521.stock')
order_state = engine.get_env_state('orders.O-10001.state')
```

### Updating State

```python
from agent.state_propagation import StateUpdate

updates = [
    StateUpdate("mem.orders.last.id", "set", "O-10001"),
    StateUpdate("env.banking.balance.checking", "subtract", 49.99),
    StateUpdate("env.orders.O-10001.state", "set", "confirmed"),
]

success, error = engine.apply_updates(updates)
```

### Checking Dependencies

```python
# Check if task can run
deps_met, error = engine.check_dependencies_met("C2-return")

if not deps_met:
    print(f"Cannot run: {error}")
    # "Dependency not met: B1-shopping must complete successfully first"

# Validate preconditions
preconditions = [
    "mem('orders.last.id') != ''",
    "json('env', 'banking.balance.checking') >= 1000"
]

valid, error = engine.validate_preconditions(preconditions)
```

---

## 🧪 Testing

### Run Test Suite

```bash
# All scenarios at level 3
python3 test_dependency_chains.py --level 3

# Expert level (very difficult)
python3 test_dependency_chains.py --level 5

# Specific seed for reproducibility
python3 test_dependency_chains.py --seed 12345
```

### Expected Output

```
🧪 TEST SCENARIO: Success Chain: B1 → C2
================================================================================
Tasks: B1-shopping → C2-return
Expected: ✅ All succeed
================================================================================

[1/2] Running B1-shopping...
✅ B1-shopping     confirmed   22/22 steps  7.50s

[2/2] Running C2-return...
✅ C2-return       confirmed   3/3 steps    1.80s

📊 SCENARIO RESULTS: Success Chain: B1 → C2
================================================================================
✅ B1-shopping       confirmed   22/22
✅ C2-return         confirmed   3/3

Scenario: ✅ PASS
```

---

## 📁 File Structure

```
webagent_dynamic_suite_v2_skin/
├── agent/
│   ├── executor.py                  # Base executor
│   ├── enhanced_executor.py         # Enhanced with dependencies
│   ├── state_propagation.py         # State management
│   ├── perturbation_engine.py       # Dynamic difficulty
│   ├── assertions_dsl.py            # Assertion language
│   └── error_handlers.py            # Error handling
├── tasks/                           # 10 task definitions
├── sites/                           # 3 frontend sites
├── docs/
│   ├── task_dependency_system.md    # System design
│   └── ...
├── test_dependency_chains.py        # Test suite
├── server.py                        # Flask backend
└── data.db                          # SQLite database
```

---

## 🎯 Creating New Task Chains

### Step 1: Define Dependencies

Edit `task_spec.json`:

```json
{
  "task_id": "NEW-2025-001",
  "dependencies": ["B1-2025-001"],
  "preconditions": [
    "mem('orders.last.id') != ''"
  ]
}
```

### Step 2: Define State Updates

Edit `agent/state_propagation.py` in `TaskStateManager.get_task_updates()`:

```python
elif family == "NEW":
    updates = [
        StateUpdate("mem.new_task.data", "set", task_result.get("data")),
        StateUpdate("env.some_table.field", "set", "value"),
    ]
```

### Step 3: Test Chain

```python
from agent.enhanced_executor import run_task_with_dependencies

# Run prerequisite
b1_result = run_task_with_dependencies("B1-shopping")

# Run new task (depends on B1)
new_result = run_task_with_dependencies("NEW-task")
```

---

## 📊 Metrics & Evaluation

### Success Metrics

```python
result = run_task_with_dependencies("B1-shopping", level=3)

metrics = {
    "success_rate": result.success,
    "completion_rate": result.steps_completed / result.steps_total,
    "efficiency": result.steps_completed / result.time_elapsed,  # steps/sec
    "dependency_compliance": result.dependencies_met,
    "resource_efficiency": len(result.resource_constraints_hit) == 0
}
```

### Benchmark Scoring

```python
def calculate_score(results, difficulty_level):
    """
    Score = (Success Rate × 100) × Difficulty Multiplier

    Multipliers:
    Level 1: 1.0x (baseline)
    Level 2: 1.5x
    Level 3: 2.0x
    Level 4: 3.0x
    Level 5: 5.0x
    """
    multipliers = {1: 1.0, 2: 1.5, 3: 2.0, 4: 3.0, 5: 5.0}
    success_rate = sum(r.success for r in results) / len(results)
    return success_rate * 100 * multipliers[difficulty_level]
```

---

## 🔧 Troubleshooting

### Issue: Tasks always blocked

```python
# Check dependencies are recorded
engine = StatePropagationEngine()
completed = engine.get_memory('tasks.B1-shopping.success')

if not completed:
    print("B1-shopping didn't complete successfully")
    # Run B1 first, then try C2
```

### Issue: Balance doesn't update

```python
# Manually check balance
balance = engine.get_env_state('banking.balance.checking')
print(f"Current balance: ${balance:.2f}")

# Reset if needed
engine.set_env_state('banking.balance.checking', 1000.00)
```

### Issue: Perturbations too difficult

```python
# Lower difficulty level
executor = EnhancedTaskExecutor(
    perturbation_level=PerturbationLevel.LIGHT  # Level 2 instead of 5
)
```

---

## 📚 Further Reading

- [Task Dependency System Design](docs/task_dependency_system.md)
- [Backend API Reference](BACKEND_API_REFERENCE.md)
- [Original Project Status](STATUS.md)
- [Final Test Report](FINAL_TEST_REPORT.md)

---

## 🎉 Summary

You now have a **production-ready benchmark** with:

✅ **Strong task dependencies** - Real cascading failures
✅ **5 difficulty levels** - From easy to nearly impossible
✅ **Dynamic perturbations** - DOM shuffle, price changes, errors
✅ **Realistic constraints** - Limited money, stock, time
✅ **Comprehensive testing** - Automated test suite

**Next steps:**
1. Run test suite to verify everything works
2. Start with Level 1 (baseline) to ensure agents can handle basics
3. Gradually increase difficulty to Level 3-4 for real challenge
4. Use Level 5 for cutting-edge research

**Recommended difficulty:**
- Level 4 (Advanced): 30-50% success rate - Best for production benchmarking

**Expected agent performance:**
- Level 1: 90-100% (too easy - baseline only)
- Level 2: 70-90% (warm-up)
- Level 3: 50-70% (moderate challenge)
- Level 4: 30-50% (production benchmark - RECOMMENDED)
- Level 5: 10-30% (research frontier)

Good luck! 🚀
