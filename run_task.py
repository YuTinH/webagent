#!/usr/bin/env python3
"""
Test Runner for Task Executor

Usage:
    python run_task.py B1-shopping           # Run with oracle trace
    python run_task.py B1-shopping --no-oracle  # Run without oracle
    python run_task.py B1-shopping --headless   # Run in headless mode
    python run_task.py --all                    # Run all tasks
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.executor import TaskExecutor


def find_task(task_name: str) -> tuple:
    """Find task spec and oracle trace paths"""
    tasks_dir = Path(__file__).parent / 'tasks'

    # Find matching directory
    for task_dir in tasks_dir.iterdir():
        if task_dir.is_dir() and task_name.lower() == task_dir.name.lower():
            task_spec = task_dir / 'task_spec.json'
            oracle_trace = task_dir / 'oracle_trace.json'

            if task_spec.exists():
                return (
                    str(task_spec),
                    str(oracle_trace) if oracle_trace.exists() else None,
                    task_dir.name
                )

    return None, None, None


def run_single_task(
    task_name: str,
    use_oracle: bool = True,
    headless: bool = False,
    slow_mo: int = 0
):
    """Run a single task"""

    task_spec, oracle_trace, full_name = find_task(task_name)

    if not task_spec:
        print(f"❌ Task not found: {task_name}")
        print("\nAvailable tasks:")
        tasks_dir = Path(__file__).parent / 'tasks'
        for task_dir in sorted(tasks_dir.iterdir()):
            if task_dir.is_dir():
                print(f"  - {task_dir.name}")
        return None

    print(f"✅ Found task: {full_name}")
    print(f"   Task spec: {task_spec}")

    if use_oracle and oracle_trace:
        print(f"   Oracle trace: {oracle_trace}")
    elif use_oracle:
        print(f"   ⚠️  No oracle trace found, running without oracle")
        oracle_trace = None
    else:
        print(f"   Running without oracle trace")
        oracle_trace = None

    # Create executor
    executor = TaskExecutor(
        database_path="data.db",
        headless=headless,
        slow_mo=slow_mo
    )

    # Run task
    result = executor.run(
        task_spec_path=task_spec,
        oracle_trace_path=oracle_trace if use_oracle else None
    )

    # Save result
    output_dir = Path('output') / full_name
    output_dir.mkdir(parents=True, exist_ok=True)

    result_path = output_dir / 'result.json'
    with open(result_path, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)

    print(f"\n💾 Result saved to: {result_path}")

    return result


def run_all_tasks(headless: bool = True, slow_mo: int = 0):
    """Run all tasks"""
    tasks_dir = Path(__file__).parent / 'tasks'
    results = []

    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir()])

    print(f"\n🚀 Running {len(task_dirs)} tasks...\n")

    for i, task_dir in enumerate(task_dirs, 1):
        print(f"\n{'='*80}")
        print(f"Task {i}/{len(task_dirs)}: {task_dir.name}")
        print(f"{'='*80}")

        result = run_single_task(
            task_dir.name,
            use_oracle=True,
            headless=headless,
            slow_mo=slow_mo
        )

        if result:
            results.append({
                'task': task_dir.name,
                'success': result.success,
                'steps': f"{result.steps_completed}/{result.steps_total}",
                'time': f"{result.time_elapsed:.2f}s"
            })

    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}\n")

    print(f"{'Task':<30} {'Success':<10} {'Steps':<15} {'Time'}")
    print("-" * 80)

    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"{r['task']:<30} {status:<10} {r['steps']:<15} {r['time']}")

    successful = sum(1 for r in results if r['success'])
    print(f"\n✅ {successful}/{len(results)} tasks successful")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run web agent tasks')

    parser.add_argument(
        'task',
        nargs='?',
        help='Task name (e.g., B1-shopping, D1-check-balance)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all tasks'
    )

    parser.add_argument(
        '--no-oracle',
        action='store_true',
        help='Run without oracle trace (let agent decide)'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )

    parser.add_argument(
        '--slow',
        type=int,
        default=0,
        metavar='MS',
        help='Slow down operations by N milliseconds (default: 0)'
    )

    args = parser.parse_args()

    if args.all:
        run_all_tasks(headless=args.headless, slow_mo=args.slow)
    elif args.task:
        run_single_task(
            args.task,
            use_oracle=not args.no_oracle,
            headless=args.headless,
            slow_mo=args.slow
        )
    else:
        parser.print_help()
        print("\n📋 Available tasks:")
        tasks_dir = Path(__file__).parent / 'tasks'
        for task_dir in sorted(tasks_dir.iterdir()):
            if task_dir.is_dir():
                print(f"  - {task_dir.name}")


if __name__ == '__main__':
    main()
