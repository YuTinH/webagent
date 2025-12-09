#!/usr/bin/env python3
"""
Test Task Dependency Chains

This script demonstrates how tasks depend on each other and fail cascadingly.

Test scenarios:
1. Success chain: B1 → C2 → D1 (all succeed)
2. Failure chain: B1 fails → C2 blocked → D1 blocked
3. Resource constraint: Insufficient balance → B1 fails
4. Out of stock: Product unavailable → B1 fails
5. Complex chain: B1 → D1 → D3 → M1 → D4 (crisis scenario)
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.enhanced_executor import EnhancedTaskExecutor, run_task_with_dependencies
from agent.perturbation_engine import PerturbationLevel
from agent.state_propagation import StatePropagationEngine, StateUpdate


class TestRunner:
    """Run dependency chain tests"""

    def __init__(self, perturbation_level: int = PerturbationLevel.ADVANCED, seed: int = 42):
        self.perturbation_level = perturbation_level
        self.seed = seed
        self.db_path = "data.db"
        self.results = []

    def reset_state(self):
        """Reset database state for clean test"""
        print("\n🔄 Resetting state...")
        engine = StatePropagationEngine(self.db_path)

        # Reset balance to $1000
        engine.set_env_state('banking.balance.checking', 1000.00)

        # Reset memory
        engine.memory_cache = {}
        
        # Preset User Profile (Static info required by preconditions)
        engine.set_memory("address", {"primary": "123 Main St, Springfield"})
        engine.set_memory("payment", {
            "cards": [{"last4": "1234", "status": "active"}]
        })
        engine.set_memory("banking", {
            "username": "user123", 
            "password": "pass123",
            "balance": {"checking": 1000.00}
        })
        engine.set_memory("identity", {
            "address": "123 Main St, Springfield",
            "vehicle": {"plate": "ABC-1234"}
        })
        engine.set_memory("bills", {
            "electricity": {"id": "", "amount": 0}, # D3 expects these to be populated by H1, or initial state
        })
        
        engine.save_memory()
        
        engine.save_memory()

        print("✅ State reset complete")

    def run_test_scenario(self, name: str, tasks: list, expect_success: bool = True):
        """
        Run a test scenario with a chain of tasks

        Args:
            name: Scenario name
            tasks: List of task directories to run
            expect_success: Whether all tasks should succeed
        """
        print(f"\n{'='*80}")
        print(f"🧪 TEST SCENARIO: {name}")
        print(f"{'='*80}")
        print(f"Tasks: {' → '.join(tasks)}")
        print(f"Expected: {'✅ All succeed' if expect_success else '❌ Some fail'}")
        print(f"{'='*80}\n")

        scenario_results = []

        if "H1-check-bill" in tasks:
             # Special handling if needed, otherwise loop handles it
             pass

        for i, task_dir in enumerate(tasks):
            print(f"\n[{i+1}/{len(tasks)}] Running {task_dir}...")

            try:
                result = run_task_with_dependencies(
                    task_dir,
                    perturbation_level=self.perturbation_level,
                    seed=self.seed,
                    headless=True
                )

                scenario_results.append({
                    'task': task_dir,
                    'success': result.success,
                    'state': result.final_state,
                    'steps': f"{result.steps_completed}/{result.steps_total}",
                    'time': f"{result.time_elapsed:.2f}s",
                    'error': str(result.error) if result.error else None,
                    'dependencies_met': result.dependencies_met
                })

                if not result.success:
                    print(f"\n⚠️  Task {task_dir} failed, subsequent tasks may be blocked")

            except Exception as e:
                print(f"\n❌ Exception: {e}")
                scenario_results.append({
                    'task': task_dir,
                    'success': False,
                    'state': 'error',
                    'error': str(e)
                })

        # Summary
        print(f"\n{'='*80}")
        print(f"📊 SCENARIO RESULTS: {name}")
        print(f"{'='*80}")

        for r in scenario_results:
            status = '✅' if r['success'] else '❌'
            print(f"{status} {r['task']:20s} {r.get('state', 'unknown'):10s} {r.get('steps', 'N/A')}")

        all_success = all(r['success'] for r in scenario_results)
        scenario_pass = (all_success == expect_success)

        print(f"\nScenario: {'✅ PASS' if scenario_pass else '❌ FAIL'}")
        print(f"{'='*80}\n")

        self.results.append({
            'name': name,
            'expected': expect_success,
            'actual': all_success,
            'passed': scenario_pass,
            'tasks': scenario_results
        })

        return scenario_pass

    def scenario_1_success_chain(self):
        """Scenario 1: Normal success chain"""
        self.reset_state()
        return self.run_test_scenario(
            "Success Chain: B1 → C2",
            tasks=['B1-shopping', 'C2-return'],
            expect_success=True
        )

    def scenario_2_dependency_failure(self):
        """Scenario 2: C2 fails because B1 didn't run"""
        self.reset_state()
        return self.run_test_scenario(
            "Dependency Failure: C2 without B1",
            tasks=['C2-return'],  # Skip B1
            expect_success=False
        )

    def scenario_3_insufficient_balance(self):
        """Scenario 3: Insufficient balance prevents purchase"""
        self.reset_state()

        # Set balance too low
        engine = StatePropagationEngine(self.db_path)
        engine.set_env_state('banking.balance.checking', 10.00)
        print("💰 Set balance to $10.00 (insufficient for $30 item)")

        return self.run_test_scenario(
            "Resource Constraint: Insufficient Balance",
            tasks=['B1-shopping'],
            expect_success=False
        )

    def scenario_4_complex_chain(self):
        """Scenario 4: Complex multi-task chain"""
        self.reset_state()

        # Set sufficient balance for complex scenario
        engine = StatePropagationEngine(self.db_path)
        engine.set_env_state('banking.balance.checking', 2000.00)

        # Scenario 5: Complex chain
        return self.run_test_scenario(
            "Complex Chain: B1 → D1 → H1 → D3",
            ["B1-shopping", "D1-check-balance", "H1-check-bill", "D3-autopay"],
            expect_success=True
        )

    def scenario_5_cascading_failure(self):
        """Scenario 5: B1 fails → C2 blocked → chain broken"""
        self.reset_state()

        # Set balance too low to cause B1 failure
        engine = StatePropagationEngine(self.db_path)
        engine.set_env_state('banking.balance.checking', 10.00)

        return self.run_test_scenario(
            "Cascading Failure: B1 fails → C2 blocked",
            tasks=['B1-shopping', 'C2-return'],
            expect_success=False
        )

    def run_all_scenarios(self):
        """Run all test scenarios"""
        print(f"\n{'#'*80}")
        print(f"# TASK DEPENDENCY CHAIN TEST SUITE")
        print(f"#")
        print(f"# Perturbation Level: {self.perturbation_level}")
        print(f"# Seed: {self.seed}")
        print(f"# Time: {datetime.now().isoformat()}")
        print(f"{'#'*80}\n")

        scenarios = [
            ("Scenario 1: Success Chain", self.scenario_1_success_chain),
            ("Scenario 2: Dependency Failure", self.scenario_2_dependency_failure),
            ("Scenario 3: Insufficient Balance", self.scenario_3_insufficient_balance),
            ("Scenario 4: Complex Chain", self.scenario_4_complex_chain),
            ("Scenario 5: Cascading Failure", self.scenario_5_cascading_failure),
        ]

        passed = 0
        failed = 0

        for name, scenario_func in scenarios:
            try:
                if scenario_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n❌ Scenario failed with exception: {e}")
                failed += 1

        # Final summary
        print(f"\n{'#'*80}")
        print(f"# FINAL TEST RESULTS")
        print(f"{'#'*80}")
        print(f"Total Scenarios: {len(scenarios)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {passed/len(scenarios)*100:.1f}%")
        print(f"{'#'*80}\n")

        # Save detailed results
        self.save_results()

        return passed == len(scenarios)

    def save_results(self):
        """Save test results to file"""
        output_dir = Path(__file__).parent / "test_results"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"dependency_test_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'perturbation_level': self.perturbation_level,
                'seed': self.seed,
                'scenarios': self.results
            }, f, indent=2)

        print(f"📄 Results saved to: {output_file}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Test task dependency chains')
    parser.add_argument('--level', type=int, default=4, choices=[1,2,3,4,5],
                       help='Perturbation level (1=baseline, 4=recommended, 5=expert)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for perturbations')
    parser.add_argument('--scenario', type=str, default='all',
                       help='Run specific scenario (1-5) or "all"')

    args = parser.parse_args()

    runner = TestRunner(perturbation_level=args.level, seed=args.seed)

    if args.scenario == 'all':
        success = runner.run_all_scenarios()
        sys.exit(0 if success else 1)
    else:
        scenario_map = {
            '1': runner.scenario_1_success_chain,
            '2': runner.scenario_2_dependency_failure,
            '3': runner.scenario_3_insufficient_balance,
            '4': runner.scenario_4_complex_chain,
            '5': runner.scenario_5_cascading_failure,
        }

        if args.scenario in scenario_map:
            success = scenario_map[args.scenario]()
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Unknown scenario: {args.scenario}")
            sys.exit(1)


if __name__ == "__main__":
    main()
