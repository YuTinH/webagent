#!/bin/bash
# Test runner script for WebAgent benchmark
# Runs tasks individually to avoid state pollution

echo "=========================================="
echo "WebAgent Dynamic Suite v2 - Test Runner"
echo "=========================================="
echo ""

# Reset critical memory state
python3 -c "
import sqlite3
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute(\"UPDATE memory_kv SET value = '1234' WHERE key = 'payment.cards[0].last4'\")
cursor.execute(\"UPDATE memory_kv SET value = 'O-10001' WHERE key = 'orders.last.id'\")
conn.commit()
conn.close()
print('✅ Memory state reset')
"

echo ""
echo "Running tests..."
echo ""

# Track results
PASSED=0
FAILED=0
TASKS=(B1-shopping B5-track-orders C2-return D1-check-balance D3-autopay D4-card-replacement H1-check-bill H2-permit-app K2-aa-split M1-lost-card-crisis)

for task in "${TASKS[@]}"; do
  echo "Testing $task..."
  result=$(python3 run_task.py $task --headless 2>&1 | grep "Success: " | tail -1)

  if echo "$result" | grep -q "Success: True"; then
    echo "  ✅ PASS"
    ((PASSED++))
  else
    echo "  ❌ FAIL"
    ((FAILED++))
  fi
done

echo ""
echo "=========================================="
echo "Results: $PASSED/${#TASKS[@]} tasks passed"
echo "=========================================="
