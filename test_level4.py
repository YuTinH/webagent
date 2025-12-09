#!/usr/bin/env python3
"""
Simple Level 4 Perturbation Test
Tests the frontend enhancements with Level 4 difficulty
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agent.enhanced_executor import EnhancedTaskExecutor
from agent.perturbation_engine import PerturbationLevel
from agent.state_propagation import StatePropagationEngine

def setup_initial_state():
    """Setup required initial memory and state"""
    print("\n📝 Setting up initial state...")

    engine = StatePropagationEngine()

    # Reset to clean state
    engine.set_env_state('banking.balance.checking', 1000.00)

    # Set required memory for tasks
    engine.set_memory('address.primary', '123 Main St, Apt 5B')
    engine.set_memory('address.city', 'San Francisco')
    engine.set_memory('address.zip', '94102')

    # Payment cards as nested structure
    engine.set_memory('payment', {
        'cards': [
            {
                'last4': '1234',
                'status': 'active',
                'type': 'visa'
            }
        ]
    })

    engine.set_memory('user.name', 'John Doe')
    engine.set_memory('user.email', 'john@example.com')
    engine.set_memory('user.phone', '555-0123')

    # IMPORTANT: Save memory to database
    engine.save_memory()

    print("✅ Initial state setup complete")

def test_level_4_shopping():
    """Test B1-shopping at Level 4"""
    print("\n" + "="*80)
    print("🧪 Testing Level 4: B1-Shopping with Enhanced Frontend")
    print("="*80)

    # Setup state
    setup_initial_state()

    # Create executor
    executor = EnhancedTaskExecutor(
        perturbation_level=PerturbationLevel.ADVANCED,  # Level 4
        perturbation_seed=42,
        enable_dependencies=True,
        headless=True
    )

    # Run task
    print("\n🚀 Running B1-shopping...")
    result = executor.run('tasks/B1-shopping/task_spec.json')

    # Print results
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    print(f"Success: {'✅ PASS' if result.success else '❌ FAIL'}")
    print(f"Final State: {result.final_state}")
    print(f"Steps Completed: {result.steps_completed}/{result.steps_total}")
    print(f"Time Elapsed: {result.time_elapsed:.2f}s")
    print(f"Dependencies Met: {'✅' if result.dependencies_met else '❌'}")
    print(f"Perturbation Level: Level {result.perturbation_level}")

    if result.resource_constraints_hit:
        print(f"\n⚠️  Resource Constraints:")
        for constraint in result.resource_constraints_hit:
            print(f"  - {constraint}")

    if result.dependency_errors:
        print(f"\n❌ Dependency Errors:")
        for error in result.dependency_errors:
            print(f"  - {error}")

    if result.state_updates_applied:
        print(f"\n✨ State Updates Applied:")
        for update in result.state_updates_applied:
            print(f"  - {update}")

    if result.error:
        print(f"\n❌ Error: {result.error}")

    print("="*80)

    return result.success

def test_comparison():
    """Compare different difficulty levels"""
    print("\n" + "="*80)
    print("📊 Comparing Difficulty Levels")
    print("="*80)

    levels = [
        (PerturbationLevel.BASELINE, "Level 1: Baseline"),
        (PerturbationLevel.LIGHT, "Level 2: Light"),
        (PerturbationLevel.MEDIUM, "Level 3: Medium"),
        (PerturbationLevel.ADVANCED, "Level 4: Advanced (RECOMMENDED)"),
    ]

    results = []

    for level, name in levels:
        print(f"\n🧪 Testing {name}...")
        setup_initial_state()

        executor = EnhancedTaskExecutor(
            perturbation_level=level,
            perturbation_seed=42,
            enable_dependencies=False,  # Disable for comparison
            headless=True
        )

        result = executor.run('tasks/B1-shopping/task_spec.json')

        results.append({
            'level': level,
            'name': name,
            'success': result.success,
            'steps': f"{result.steps_completed}/{result.steps_total}",
            'time': result.time_elapsed
        })

    # Print comparison table
    print("\n" + "="*80)
    print("📊 COMPARISON RESULTS")
    print("="*80)
    print(f"{'Level':<45} {'Result':<10} {'Steps':<10} {'Time':<10}")
    print("-"*80)

    for r in results:
        status = "✅ PASS" if r['success'] else "❌ FAIL"
        print(f"{r['name']:<45} {status:<10} {r['steps']:<10} {r['time']:<10.2f}s")

    print("="*80)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test Level 4 perturbations')
    parser.add_argument('--compare', action='store_true', help='Compare all difficulty levels')
    args = parser.parse_args()

    if args.compare:
        test_comparison()
    else:
        success = test_level_4_shopping()
        sys.exit(0 if success else 1)
