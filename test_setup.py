#!/usr/bin/env python3
"""
Simple test to verify executor setup

This script tests the executor without requiring a running website.
It just verifies that the code can load and initialize properly.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("🧪 Testing Task Executor Setup")
print("="*80)

# Test 1: Import modules
print("\n1. Testing imports...")
try:
    from agent.executor import TaskExecutor, ExecutionResult
    from agent.assertions_dsl import AssertionDSL
    from agent.error_handlers import ErrorReport
    print("   ✅ All modules imported successfully")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Load a task spec
print("\n2. Testing task spec loading...")
try:
    task_spec_path = "tasks/B1-shopping/task_spec.json"
    with open(task_spec_path) as f:
        task_spec = json.load(f)
    print(f"   ✅ Loaded task: {task_spec['task_id']}")
    print(f"      Goal: {task_spec['goal'][:60]}...")
except Exception as e:
    print(f"   ❌ Failed to load task: {e}")
    sys.exit(1)

# Test 3: Load oracle trace
print("\n3. Testing oracle trace loading...")
try:
    oracle_path = "tasks/B1-shopping/oracle_trace.json"
    with open(oracle_path) as f:
        oracle_trace = json.load(f)
    print(f"   ✅ Loaded oracle trace with {len(oracle_trace['steps'])} steps")
except Exception as e:
    print(f"   ❌ Failed to load oracle: {e}")
    sys.exit(1)

# Test 4: Initialize executor
print("\n4. Testing executor initialization...")
try:
    executor = TaskExecutor(
        database_path="data.db",
        headless=True
    )
    print(f"   ✅ Executor initialized")
    print(f"      Memory entries loaded: {len(executor.memory)}")
except Exception as e:
    print(f"   ❌ Executor init failed: {e}")
    sys.exit(1)

# Test 5: Test assertions DSL
print("\n5. Testing Assertions DSL...")
try:
    from agent.assertions_dsl import AssertionDSL

    # Create mock objects
    class MockPage:
        def __init__(self):
            self.url = "https://shop.local/order/confirmation"
        def locator(self, selector):
            return MockLocator(selector)

    class MockLocator:
        def __init__(self, selector):
            self.selector = selector
        def count(self):
            return 1 if self.selector == "#order-id" else 0
        def inner_text(self):
            if self.selector == "#order-id":
                return "O-10001"
            return ""

    page = MockPage()
    memory = {"orders.last.id": "O-10001"}

    def mock_env_api(channel, path):
        return "confirmed"

    dsl = AssertionDSL(page, memory, mock_env_api)

    # Test simple assertions
    assert dsl.evaluate('exists("#order-id")') == True
    assert dsl.evaluate('url().includes("/order/confirmation")') == True
    assert dsl.evaluate("mem('orders.last.id') == 'O-10001'") == True

    print("   ✅ Assertions DSL working correctly")

except Exception as e:
    print(f"   ❌ Assertions DSL test failed: {e}")
    sys.exit(1)

# Test 6: Check database
print("\n6. Testing database connection...")
try:
    import sqlite3
    import os

    if os.path.exists("data.db"):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"   ✅ Database connected")
        print(f"      Tables found: {len(tables)}")

        # Check sample data
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"      Users: {user_count}")

        conn.close()
    else:
        print("   ⚠️  Database not found (data.db)")
        print("      Run: ./setup.sh")

except Exception as e:
    print(f"   ⚠️  Database check failed: {e}")

# Test 7: Check Playwright availability
print("\n7. Testing Playwright availability...")
try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        browser.close()

    print("   ✅ Playwright working correctly")

except Exception as e:
    print(f"   ❌ Playwright test failed: {e}")
    print("      Run: playwright install chromium")
    sys.exit(1)

# Summary
print("\n" + "="*80)
print("✅ ALL TESTS PASSED!")
print("="*80)
print("\nThe executor is ready to use. Try:")
print("  python run_task.py B1-shopping --slow 500")
print("\n")
