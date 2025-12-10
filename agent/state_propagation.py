"""
State Propagation Engine for Task Dependencies

This module handles:
1. State updates across tasks (memory, database, environment)
2. Resource consumption tracking (balance, inventory, etc.)
3. Cascading state changes
4. Dependency validation
"""

import json
import sqlite3
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path


class StateUpdate:
    """Represents a single state update operation"""

    def __init__(self, key: str, operation: str, value: Any = None, **kwargs):
        self.key = key
        self.operation = operation  # set, add, subtract, append, remove
        self.value = value
        self.kwargs = kwargs

    def __repr__(self):
        return f"StateUpdate({self.operation} {self.key}={self.value})"


class StatePropagationEngine:
    """
    Manages state propagation across tasks.

    Responsibilities:
    - Track memory state (memory_kv table)
    - Track database state (orders, transactions, etc.)
    - Track environment state (balance, inventory, etc.)
    - Apply state updates atomically
    - Rollback on failure
    - Validate dependencies
    """

    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path
        self.memory_cache = {}
        self.load_memory()

    def load_memory(self):
        """Load current memory state from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM memory_kv")
            for key, value_json in cursor.fetchall():
                try:
                    self.memory_cache[key] = json.loads(value_json)
                except json.JSONDecodeError:
                    self.memory_cache[key] = value_json

    def save_memory(self):
        """Save memory cache to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for key, value in self.memory_cache.items():
                value_json = json.dumps(value) if not isinstance(value, str) else value
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO memory_kv (key, value, source, ts)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, value_json, "system", datetime.now().isoformat())
                )
            conn.commit()

    def get_memory(self, key: str, default=None) -> Any:
        """Get value from memory using dot notation"""
        # Try direct match first (for flat keys from server/executor)
        if key in self.memory_cache:
            return self.memory_cache[key]

        parts = key.split('.')
        current = self.memory_cache

        for part in parts:
            # Handle array access like orders[0]
            if '[' in part and ']' in part:
                base = part[:part.index('[')]
                index = int(part[part.index('[')+1:part.index(']')])
                current = current.get(base, [])
                if isinstance(current, list) and len(current) > index:
                    current = current[index]
                else:
                    return default
            else:
                if isinstance(current, dict):
                    current = current.get(part, default)
                else:
                    return default

        return current

    def set_memory(self, key: str, value: Any):
        """Set value in memory using dot notation"""
        parts = key.split('.')
        current = self.memory_cache

        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set final value
        current[parts[-1]] = value

    def get_env_state(self, path: str) -> Any:
        """
        Get state from database (environment state) or JSON state file

        Examples:
        - banking.balance.checking → SELECT balance FROM accounts WHERE type='checking'
        - products.WM-5521.stock → SELECT stock FROM products WHERE sku='WM-5521'
        - health.prescriptions.RX-1001.refills_left → JSON lookup in env/state.json
        """
        # Check JSON state first for new domains
        json_domains = ("health.", "trips.", "work.", "expenses.", "meters.", "payments.", "permits.")
        if path.startswith(json_domains):
            return self._get_json_state(path)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if path.startswith("banking.balance."):
                account_type = path.split('.')[-1]
                cursor.execute(
                    "SELECT balance FROM accounts WHERE type=? LIMIT 1",
                    (account_type,)
                )
                result = cursor.fetchone()
                return result[0] if result else None

            elif path.startswith("products."):
                parts = path.split('.')
                sku = parts[1]
                field = parts[2] if len(parts) > 2 else 'stock'
                cursor.execute(
                    f"SELECT {field} FROM products WHERE sku=? LIMIT 1",
                    (sku,)
                )
                result = cursor.fetchone()
                return result[0] if result else None

            elif path.startswith("orders."):
                parts = path.split('.')
                order_id = parts[1]
                field = parts[2] if len(parts) > 2 else 'state'
                cursor.execute(
                    f"SELECT {field} FROM orders WHERE id=? LIMIT 1",
                    (order_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None

            elif path.startswith("cards."):
                # cards.*.state where last4='1234'
                if '*' in path:
                    cursor.execute("SELECT state FROM cards")
                    results = cursor.fetchall()
                    return [r[0] for r in results]
                else:
                    parts = path.split('.')
                    card_id = parts[1]
                    field = parts[2] if len(parts) > 2 else 'state'
                    cursor.execute(
                        f"SELECT {field} FROM cards WHERE last4=? LIMIT 1",
                        (card_id,)
                    )
                    result = cursor.fetchone()
                    return result[0] if result else None

            return None

    def _get_json_state(self, path: str) -> Any:
        """Helper to read from env/state.json"""
        state_path = Path(__file__).parent.parent / "env" / "state.json"
        if not state_path.exists():
            return None
        
        try:
            with open(state_path, 'r') as f:
                data = json.load(f)
            
            parts = path.split('.')
            current = data
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list):
                    try:
                        idx = int(part)
                        current = current[idx]
                    except (ValueError, IndexError):
                        return None
                else:
                    return None
                
                if current is None:
                    return None
            
            return current
        except Exception:
            return None

    def set_env_state(self, path: str, value: Any):
        """Update database state"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if path.startswith("banking.balance."):
                account_type = path.split('.')[-1]
                cursor.execute(
                    "UPDATE accounts SET balance=? WHERE type=?",
                    (value, account_type)
                )

            elif path.startswith("products."):
                parts = path.split('.')
                sku = parts[1]
                field = parts[2]
                cursor.execute(
                    f"UPDATE products SET {field}=? WHERE sku=?",
                    (value, sku)
                )

            elif path.startswith("orders."):
                parts = path.split('.')
                order_id = parts[1]
                field = parts[2]
                cursor.execute(
                    f"UPDATE orders SET {field}=?, updated_at=? WHERE id=?",
                    (value, datetime.now().isoformat(), order_id)
                )

            elif path.startswith("cards."):
                parts = path.split('.')
                last4 = parts[1]
                field = parts[2]
                cursor.execute(
                    f"UPDATE cards SET {field}=? WHERE last4=?",
                    (value, last4)
                )

            conn.commit()

    def apply_updates(self, updates: List[StateUpdate], rollback_on_error: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Apply a list of state updates atomically

        Returns: (success, error_message)
        """
        # Save current state for rollback
        original_memory = self.memory_cache.copy()

        try:
            for update in updates:
                if update.operation == "set":
                    if update.key.startswith("mem."):
                        key = update.key[4:]  # Remove "mem." prefix
                        self.set_memory(key, update.value)
                    elif update.key.startswith("env."):
                        key = update.key[4:]  # Remove "env." prefix
                        self.set_env_state(key, update.value)

                elif update.operation == "subtract":
                    if update.key.startswith("env.banking.balance."):
                        current = self.get_env_state(update.key[4:])
                        if current is not None:
                            new_value = current - update.value
                            if new_value < 0 and update.kwargs.get("allow_negative", False) is False:
                                raise ValueError(f"Insufficient funds: {current} - {update.value} < 0")
                            self.set_env_state(update.key[4:], new_value)

                elif update.operation == "add":
                    if update.key.startswith("env.banking.balance."):
                        current = self.get_env_state(update.key[4:])
                        if current is not None:
                            self.set_env_state(update.key[4:], current + update.value)

                elif update.operation == "decrement":
                    if update.key.startswith("env.products."):
                        current = self.get_env_state(update.key[4:])
                        if current is not None:
                            new_value = current - update.value
                            if new_value < 0:
                                raise ValueError(f"Insufficient stock: {current} - {update.value} < 0")
                            self.set_env_state(update.key[4:], new_value)

                elif update.operation == "append":
                    if update.key.startswith("mem."):
                        key = update.key[4:]
                        current = self.get_memory(key, [])
                        if not isinstance(current, list):
                            current = []
                        current.append(update.value)
                        self.set_memory(key, current)

            # Persist memory changes
            self.save_memory()
            return True, None

        except Exception as e:
            if rollback_on_error:
                # Rollback memory changes
                self.memory_cache = original_memory
                # Note: Database changes need transaction support for full rollback
            return False, str(e)

    def validate_preconditions(self, preconditions: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate task preconditions

        Preconditions are expressions like:
        - mem('orders.last.id') != ''
        - json('env', 'banking.balance.checking') >= 1000
        - mem('payment.cards[0].status') == 'active'

        Returns: (valid, error_message)
        """
        for condition in preconditions:
            try:
                # Create evaluation context
                context = {
                    'mem': lambda key, default='': self.get_memory(key, default),
                    'json': lambda source, path: self.get_env_state(path) if source == 'env' else self.get_memory(path),
                    'url': lambda: '',  # Placeholder
                    'text': lambda selector: '',  # Placeholder
                    'time_since': lambda key: 0,  # Placeholder
                    'time_until': lambda key: 999999,  # Placeholder
                    'float': float,
                    'int': int,
                    'str': str,
                    'len': len,
                    'true': True,
                    'false': False,
                    'null': None,
                }

                # Evaluate condition
                result = eval(condition, {"__builtins__": {}}, context)

                if not result:
                    return False, f"Precondition failed: {condition}"

            except Exception as e:
                return False, f"Error evaluating precondition '{condition}': {str(e)}"

        return True, None

        return True, None

    def get_task_dependencies(self, task_id: str) -> List[str]:
        """
        Get list of tasks that this task depends on

        Reads from task_spec.json
        """
        task_family = task_id.split('-')[0] + '-' + task_id.split('-')[1]
        task_dir = Path(__file__).parent.parent / "tasks" / task_family
        task_spec_path = task_dir / "task_spec.json"

        if not task_spec_path.exists():
            return []

        with open(task_spec_path) as f:
            spec = json.load(f)
            return spec.get("dependencies", [])

    def check_dependencies_met(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if all dependencies for a task are met

        Returns: (met, error_message)
        """
        dependencies = self.get_task_dependencies(task_id)

        for dep_task_id in dependencies:
            # Check if dependency task completed successfully
            success_key = f"tasks.{dep_task_id}.success"
            if not self.get_memory(success_key, False):
                return False, f"Dependency not met: {dep_task_id} must complete successfully first"

        return True, None

    def record_task_completion(self, task_id: str, success: bool, result: Dict[str, Any]):
        """Record that a task has completed"""
        self.set_memory(f"tasks.{task_id}.success", success)
        self.set_memory(f"tasks.{task_id}.timestamp", datetime.now().isoformat())
        self.set_memory(f"tasks.{task_id}.result", result)
        self.save_memory()


class TaskStateManager:
    """
    High-level manager for task-specific state changes

    Defines what state changes when each task completes
    """

    def __init__(self, engine: StatePropagationEngine):
        self.engine = engine

    def apply_task_completion_effects(self, task_id: str, task_result: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Apply state changes when a task completes successfully

        Each task has specific effects on the system state
        """
        updates = self.get_task_updates(task_id, task_result)
        return self.engine.apply_updates(updates)

    def get_task_updates(self, task_id: str, task_result: Dict[str, Any]) -> List[StateUpdate]:
        """
        Get list of state updates for a completed task

        This is the core logic that defines how tasks affect each other
        """
        updates = []

        # Extract task family and ID
        family = task_id.split('-')[0]

        # B1-shopping: Purchase product
        if family == "B1":
            order_id = task_result.get("order_id", "O-10001")
            total = task_result.get("total", 49.99)

            updates = [
                # Update memory
                StateUpdate("mem.orders.last.id", "set", order_id),
                StateUpdate("mem.orders.last.total", "set", total),
                StateUpdate("mem.orders.last.state", "set", "confirmed"),
                StateUpdate("mem.orders.last.timestamp", "set", datetime.now().isoformat()),
                StateUpdate("mem.orders.all", "append", order_id),

                # Deduct balance
                StateUpdate("env.banking.balance.checking", "subtract", total, allow_negative=False),

                # Update order state in DB
                StateUpdate("env.orders." + order_id + ".state", "set", "confirmed"),
            ]

        # C2-return: Return product
        elif family == "C2":
            order_id = task_result.get("order_id", self.engine.get_memory("orders.last.id"))
            return_id = task_result.get("return_id", "R-50001")
            refund_amount = task_result.get("refund_amount", 49.99)

            updates = [
                # Update memory
                StateUpdate("mem.returns.last.id", "set", return_id),
                StateUpdate("mem.returns.last.order_id", "set", order_id),
                StateUpdate("mem.returns.last.state", "set", "approved"),
                StateUpdate("mem.returns.last.refund_amount", "set", refund_amount),

                # Update order state
                StateUpdate("env.orders." + order_id + ".state", "set", "returned"),

                # Add refund (simulated - would be delayed in reality)
                StateUpdate("env.banking.balance.checking", "add", refund_amount),
            ]

        # D1-check-balance: Just reads, no state changes
        elif family == "D1":
            # Check extracted data first
            extracted = task_result.get("extracted_data", {})
            balance = extracted.get("balance")
            
            # Fallback to direct keys (legacy/testing)
            if balance is None:
                balance = task_result.get("balance", 0)
            
            print(f"DEBUG: D1 get_task_updates - balance variable: {balance}")

            updates = [
                StateUpdate("mem.banking.balance.checking", "set", balance),
                StateUpdate("mem.banking.balance.last_check", "set", datetime.now().isoformat()),
            ]

        # D3-autopay: Setup autopay
        elif family == "D3":
            autopay_id = task_result.get("autopay_id", "util-autopay-001")
            amount = task_result.get("amount", 150)
            card_last4 = task_result.get("card_last4", "1234")

            updates = [
                StateUpdate("mem.autopay." + autopay_id + ".active", "set", True),
                StateUpdate("mem.autopay." + autopay_id + ".card", "set", card_last4),
                StateUpdate("mem.autopay." + autopay_id + ".amount", "set", amount),
                StateUpdate("mem.autopay." + autopay_id + ".next_charge", "set",
                           (datetime.now() + timedelta(days=30)).isoformat()),
            ]

        # M1-lost-card-crisis: Block card
        elif family == "M1":
            card_last4 = task_result.get("card_last4", "1234")

            updates = [
                # Block the card
                StateUpdate("env.cards." + card_last4 + ".state", "set", "blocked"),

                # Disable all autopays on this card
                # Note: This requires a more complex query, simplified here
                StateUpdate("mem.autopay.all_on_card_" + card_last4 + ".active", "set", False),
            ]

        # D4-card-replacement: Get new card
        elif family == "D4":
            old_card = task_result.get("old_card_last4", "1234")
            new_card = task_result.get("new_card_last4", "5678")

            updates = [
                # Activate new card
                StateUpdate("env.cards." + new_card + ".state", "set", "active"),

                # Update memory
                StateUpdate("mem.banking.cards.active", "set", new_card),
            ]

        # H1-check-bill: Check utility bills
        elif family == "H1":
            updates = [
                StateUpdate("mem.bills.electricity.amount", "set", 150.00),
                StateUpdate("mem.bills.electricity.due_date", "set", "2025-12-31"),
                StateUpdate("mem.bills.electricity.id", "set", "UTIL-2025-E1"),
                StateUpdate("mem.bills.water.amount", "set", 45.50),
            ]

        # H2-permit-app: Apply for parking permit
        elif family == "H2":
            permit_id = task_result.get("permit_id", "RP-2024-77")
            updates = [
                StateUpdate("mem.permits.last.id", "set", permit_id),
                StateUpdate("mem.permits.last.status", "set", "active"),
            ]

        # B5-track-orders: Track order status
        elif family == "B5":
            order_id = self.engine.get_memory("orders.last.id", "O-10001")
            updates = [
                StateUpdate(f"mem.orders.{order_id}.last_tracked", "set", datetime.now().isoformat()),
            ]

        # K2-aa-split: Split expenses
        elif family == "K2":
            updates = [
                StateUpdate("mem.settlements.last.status", "set", "completed"),
            ]

        return updates


# Example usage
if __name__ == "__main__":
    engine = StatePropagationEngine()
    manager = TaskStateManager(engine)

    # Simulate B1-shopping completion
    print("=== Simulating B1-shopping completion ===")
    result = {
        "order_id": "O-10001",
        "total": 49.99,
    }

    success, error = manager.apply_task_completion_effects("B1-shopping", result)
    print(f"Success: {success}, Error: {error}")

    # Check memory
    print(f"Order ID in memory: {engine.get_memory('orders.last.id')}")
    print(f"Balance: {engine.get_env_state('banking.balance.checking')}")

    # Try to run C2-return (should succeed because B1 completed)
    print("\n=== Checking C2-return preconditions ===")
    preconditions = ["mem('orders.last.id') != ''"]
    valid, error = engine.validate_preconditions(preconditions)
    print(f"Preconditions valid: {valid}, Error: {error}")
