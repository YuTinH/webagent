"""
Enhanced Task Executor with State Propagation and Perturbations

This module extends the base executor with:
1. Task dependency validation
2. State propagation across tasks
3. Dynamic difficulty perturbations
4. Resource constraint management
5. Cascading failure handling
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.executor import TaskExecutor, ExecutionResult
from agent.state_propagation import StatePropagationEngine, TaskStateManager
from agent.perturbation_engine import PerturbationEngine, PerturbationLevel


class EnhancedExecutionResult(ExecutionResult):
    """Extended execution result with dependency information"""

    def __init__(self, task_id: str):
        super().__init__(task_id)
        self.dependencies_met = True
        self.dependency_errors = []
        self.state_updates_applied = []
        self.perturbation_level = PerturbationLevel.BASELINE
        self.resource_constraints_hit = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with extended fields"""
        base_dict = super().to_dict()
        base_dict.update({
            "dependencies_met": self.dependencies_met,
            "dependency_errors": self.dependency_errors,
            "state_updates_applied": self.state_updates_applied,
            "perturbation_level": self.perturbation_level,
            "resource_constraints_hit": self.resource_constraints_hit
        })
        return base_dict


class EnhancedTaskExecutor(TaskExecutor):
    """
    Enhanced executor with dependency management and perturbations
    """

    def __init__(
        self,
        database_path: str = "data.db",
        env_api_url: Optional[str] = None,
        headless: bool = False,
        slow_mo: int = 0,
        perturbation_seed: int = 42,
        perturbation_level: int = PerturbationLevel.BASELINE,
        enable_dependencies: bool = True
    ):
        """
        Initialize enhanced executor

        Args:
            database_path: Path to SQLite database
            env_api_url: URL for environment API
            headless: Run browser in headless mode
            slow_mo: Slow down operations by N milliseconds
            perturbation_seed: Seed for deterministic perturbations
            perturbation_level: Difficulty level (1-5)
            enable_dependencies: Enable dependency checking
        """
        super().__init__(database_path, env_api_url, headless, slow_mo)

        # Initialize new systems
        self.state_engine = StatePropagationEngine(database_path)
        self.state_manager = TaskStateManager(self.state_engine)
        self.perturbation_engine = PerturbationEngine(perturbation_seed, perturbation_level)
        self.enable_dependencies = enable_dependencies

        print(f"\n{'='*80}")
        print(f"🎯 Enhanced Executor Initialized")
        print(f"{'='*80}")
        config = self.perturbation_engine.get_configuration_summary()
        print(f"📊 Perturbation Level: {config['level_name']}")
        print(f"🎲 Seed: {config['seed']}")
        print(f"✨ Features: {', '.join(config['features'])}")
        print(f"📈 Expected Success Rate: {config['expected_success_rate']}")
        print(f"🔗 Dependencies: {'Enabled' if enable_dependencies else 'Disabled'}")
        print(f"{'='*80}\n")

    def run(self, task_spec_path: str, oracle_trace_path: Optional[str] = None) -> EnhancedExecutionResult:
        """
        Execute a task with dependency checking and state propagation

        Flow:
        1. Load task spec
        2. Check dependencies
        3. Validate preconditions
        4. Apply perturbations to pages
        5. Execute task
        6. Validate success criteria
        7. Apply state updates
        8. Record completion

        Args:
            task_spec_path: Path to task_spec.json
            oracle_trace_path: Optional path to oracle_trace.json

        Returns:
            EnhancedExecutionResult with extended information
        """
        # Load task spec
        with open(task_spec_path) as f:
            task_spec = json.load(f)

        task_id = task_spec['task_id']
        result = EnhancedExecutionResult(task_id)
        result.perturbation_level = self.perturbation_engine.level

        print(f"\n{'='*80}")
        print(f"🚀 Executing Enhanced Task: {task_id}")
        print(f"{'='*80}")

        try:
            # Step 1: Check dependencies
            if self.enable_dependencies:
                print("\n🔗 Checking task dependencies...")
                deps_met, dep_error = self.state_engine.check_dependencies_met(task_id)

                if not deps_met:
                    result.success = False
                    result.final_state = "blocked"
                    result.dependencies_met = False
                    result.dependency_errors.append(dep_error)
                    print(f"❌ {dep_error}")
                    return result

                print("✅ All dependencies met")

            # Step 2: Validate preconditions
            print("\n📋 Validating preconditions...")
            preconditions = task_spec.get('preconditions', [])

            if preconditions:
                valid, error = self.state_engine.validate_preconditions(preconditions)

                if not valid:
                    result.success = False
                    result.final_state = "failed"
                    result.error = error
                    print(f"❌ {error}")
                    return result

            print("✅ All preconditions satisfied")

            # Step 3: Check resource constraints
            print("\n💰 Checking resource constraints...")
            constraints_ok, constraint_error = self._check_resource_constraints(task_spec)

            if not constraints_ok:
                result.success = False
                result.final_state = "failed"
                result.resource_constraints_hit.append(constraint_error)
                print(f"❌ {constraint_error}")
                return result

            print("✅ Resource constraints satisfied")

            # Step 4: Execute base task (with perturbations)
            print("\n🎭 Executing task with perturbations...")
            base_result = super().run(task_spec_path, oracle_trace_path)

            # Copy base result data
            result.success = base_result.success
            result.final_state = base_result.final_state
            result.steps_completed = base_result.steps_completed
            result.steps_total = base_result.steps_total
            result.time_elapsed = base_result.time_elapsed
            result.error = base_result.error
            result.trace = base_result.trace
            result.memory_updates = base_result.memory_updates
            result.artifacts = base_result.artifacts
            result.extracted_data = base_result.extracted_data # Copy extracted data

            # Step 5: If successful, apply state updates
            if result.success:
                print("\n✨ Applying state updates...")

                # Extract task result data for state updates
                task_result = self._extract_task_result(task_id, result)

                # Apply state updates
                updates_ok, update_error = self.state_manager.apply_task_completion_effects(
                    task_id, task_result
                )

                if updates_ok:
                    result.state_updates_applied = self.state_manager.get_task_updates(task_id, task_result)
                    print(f"✅ Applied {len(result.state_updates_applied)} state updates")

                    # Record task completion
                    self.state_engine.record_task_completion(task_id, True, task_result)
                    print(f"✅ Task completion recorded")
                else:
                    print(f"⚠️  Warning: State updates failed: {update_error}")
                    result.warnings.append(f"State updates failed: {update_error}")

            else:
                # Record failure
                self.state_engine.record_task_completion(task_id, False, {"error": str(result.error)})

            return result

        except Exception as e:
            import traceback
            result.success = False
            result.final_state = "error"
            result.error = str(e)
            print(f"\n❌ Error during execution: {e}")
            print("\nFull traceback:")
            traceback.print_exc()
            return result

    def _check_resource_constraints(self, task_spec: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check resource constraints before execution

        Examples:
        - Sufficient balance for purchase
        - Product in stock
        - Time slot available
        """
        task_id = task_spec['task_id']
        family = task_id.split('-')[0]

        # B1-shopping: Check balance and stock
        if family == 'B1':
            # Check if user has sufficient balance
            max_price = task_spec.get('inputs', {}).get('max_price', 0)
            if max_price > 0:
                balance = self.state_engine.get_env_state('banking.balance.checking')
                if balance is not None and balance < max_price:
                    return False, f"Insufficient balance: ${balance:.2f} < ${max_price:.2f}"

            # Check if item is in stock (if perturbations enabled)
            if self.perturbation_engine.level >= PerturbationLevel.MEDIUM:
                item_keywords = task_spec.get('inputs', {}).get('item_keywords', [])
                # For simplicity, assume first matching product
                sku = "WM-5521"  # Would normally search by keywords

                stock = self.state_engine.get_env_state(f'products.{sku}.stock')
                if stock is not None and stock == 0:
                    return False, f"Product {sku} is out of stock"

        # D3-autopay: Check sufficient balance for autopay amount
        elif family == 'D3':
            autopay_amount = task_spec.get('inputs', {}).get('amount', 150)
            balance = self.state_engine.get_env_state('banking.balance.checking')

            if balance is not None and balance < autopay_amount:
                return False, f"Insufficient balance for autopay: ${balance:.2f} < ${autopay_amount:.2f}"

        # C2-return: Check if order exists and is returnable
        elif family == 'C2':
            order_id = task_spec.get('inputs', {}).get('order_id')
            if not order_id:
                order_id = self.state_engine.get_memory('orders.last.id')

            if not order_id:
                return False, "No order found to return"

            order_state = self.state_engine.get_env_state(f'orders.{order_id}.state')
            if order_state and order_state not in ['confirmed', 'delivered']:
                return False, f"Order {order_id} cannot be returned (state: {order_state})"

        return True, None

    def _extract_task_result(self, task_id: str, execution_result: EnhancedExecutionResult) -> Dict[str, Any]:
        """
        Extract relevant data from execution result for state updates

        This determines what data gets propagated to other tasks
        """
        family = task_id.split('-')[0]
        result = {}

        # Extract from memory updates made during task
        memory_updates = execution_result.memory_updates
        
        # Include extracted data
        if hasattr(execution_result, 'extracted_data'):
            result['extracted_data'] = execution_result.extracted_data

        if family == 'B1':
            # Shopping task - extract order info
            result['order_id'] = memory_updates.get('orders.last.id', 'O-10001')
            result['total'] = memory_updates.get('orders.last.total', 49.99)

        elif family == 'C2':
            # Return task - extract return info
            result['return_id'] = memory_updates.get('returns.last.id', 'R-50001')
            result['order_id'] = memory_updates.get('returns.last.order_id', 'O-10001')
            result['refund_amount'] = memory_updates.get('returns.last.refund_amount', 49.99)

        elif family == 'D1':
            # Balance check - extract balance
            result['balance'] = memory_updates.get('banking.balance.checking', 0)

        elif family == 'D3':
            # Autopay setup - extract autopay info
            result['autopay_id'] = memory_updates.get('autopay.id', 'util-autopay-001')
            result['amount'] = memory_updates.get('autopay.amount', 150)
            result['card_last4'] = memory_updates.get('autopay.card', '1234')

        elif family == 'M1':
            # Lost card - extract card info
            result['card_last4'] = memory_updates.get('banking.cards.blocked', '1234')

        elif family == 'D4':
            # Card replacement - extract new card
            result['old_card_last4'] = memory_updates.get('banking.cards.old', '1234')
            result['new_card_last4'] = memory_updates.get('banking.cards.new', '5678')

        elif family == 'G1':
            # Doctor appointment
            result['appointment_id'] = memory_updates.get('health.appointment.last.id', 'APT-9001')

        elif family == 'D2':
            # Budget report
            result['category'] = memory_updates.get('budget.category', 'food')
            result['limit'] = memory_updates.get('budget.limit', 600)

        elif family == 'B6':
            result['claim_id'] = memory_updates.get('claims.price_protection.last.id', 'PP-1001')

        elif family == 'A4':
            result['phone'] = memory_updates.get('mobile.subscription.phone', '555-000-0000')

        elif family == 'A6':
            result['verified'] = memory_updates.get('identity.address_verified', True)

        elif family == 'B7':
            result['item_id'] = memory_updates.get('market.listed_items.last.id', f"2H-{random.randint(1000, 9999)}")

        elif family == 'F5':
            result['doc_id'] = memory_updates.get('cloud.documents.last.id', f"DOC-{random.randint(10000, 99999)}")
        
        elif family == 'G5':
            result['plan_name'] = memory_updates.get('health.plan.name', 'Standard Wellness')
        
        elif family == 'G6':
            result['vaccine_id'] = memory_updates.get('health.vaccines.last.id', f"VC-{random.randint(10000, 99999)}")

        return result

    def apply_page_perturbations(self, html: str, page_type: str = 'product') -> str:
        """
        Apply perturbations to a page before rendering

        This would be called from the server or via page interception
        """
        return self.perturbation_engine.perturb_page(html, page_type)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get current state summary for debugging"""
        return {
            'memory': dict(list(self.state_engine.memory_cache.items())[:10]),  # First 10 items
            'balance': self.state_engine.get_env_state('banking.balance.checking'),
            'last_order': self.state_engine.get_memory('orders.last.id'),
            'completed_tasks': [
                k.replace('tasks.', '').replace('.success', '')
                for k in self.state_engine.memory_cache.keys()
                if k.startswith('tasks.') and k.endswith('.success')
                and self.state_engine.memory_cache[k] is True
            ]
        }


def run_task_with_dependencies(
    task_dir: str,
    perturbation_level: int = PerturbationLevel.BASELINE,
    seed: int = 42,
    headless: bool = True
) -> EnhancedExecutionResult:
    """
    Convenience function to run a task with full dependency support

    Args:
        task_dir: Task directory name (e.g., "B1-shopping")
        perturbation_level: Difficulty level (1-5)
        seed: Random seed for perturbations
        headless: Run browser in headless mode

    Returns:
        EnhancedExecutionResult
    """
    tasks_base = Path(__file__).parent.parent / "tasks"
    task_path = tasks_base / task_dir
    task_spec_path = task_path / "task_spec.json"
    oracle_trace_path = task_path / "oracle_trace.json"

    if not task_spec_path.exists():
        raise FileNotFoundError(f"Task spec not found: {task_spec_path}")

    executor = EnhancedTaskExecutor(
        headless=headless,
        perturbation_seed=seed,
        perturbation_level=perturbation_level,
        enable_dependencies=True
    )

    result = executor.run(
        str(task_spec_path),
        str(oracle_trace_path) if oracle_trace_path.exists() else None
    )

    # Print summary
    print(f"\n{'='*80}")
    print(f"📊 Execution Summary")
    print(f"{'='*80}")
    print(f"Task: {result.task_id}")
    print(f"Success: {'✅' if result.success else '❌'}")
    print(f"Final State: {result.final_state}")
    print(f"Steps: {result.steps_completed}/{result.steps_total}")
    print(f"Time: {result.time_elapsed:.2f}s")
    print(f"Dependencies Met: {'✅' if result.dependencies_met else '❌'}")

    if result.dependency_errors:
        print(f"\n⚠️  Dependency Errors:")
        for error in result.dependency_errors:
            print(f"  - {error}")

    if result.state_updates_applied:
        print(f"\n✨ State Updates Applied: {len(result.state_updates_applied)}")

    if result.resource_constraints_hit:
        print(f"\n⚠️  Resource Constraints Hit:")
        for constraint in result.resource_constraints_hit:
            print(f"  - {constraint}")

    print(f"{'='*80}\n")

    return result


if __name__ == "__main__":
    """
    Example: Run a task chain with dependencies

    This demonstrates how tasks depend on each other:
    1. B1-shopping creates an order
    2. C2-return depends on that order existing
    """
    import sys

    # Configure
    HEADLESS = True
    PERTURBATION_LEVEL = PerturbationLevel.MEDIUM  # Level 3
    SEED = 42

    # Run B1-shopping first
    print("Running B1-shopping (creates order)...")
    b1_result = run_task_with_dependencies(
        "B1-shopping",
        perturbation_level=PERTURBATION_LEVEL,
        seed=SEED,
        headless=HEADLESS
    )

    if not b1_result.success:
        print("❌ B1-shopping failed, cannot proceed to C2-return")
        sys.exit(1)

    # Now run C2-return (depends on B1)
    print("\n\nRunning C2-return (depends on B1-shopping order)...")
    c2_result = run_task_with_dependencies(
        "C2-return",
        perturbation_level=PERTURBATION_LEVEL,
        seed=SEED,
        headless=HEADLESS
    )

    if c2_result.success:
        print("\n✅ Task chain completed successfully!")
    else:
        print(f"\n❌ C2-return failed: {c2_result.error}")
