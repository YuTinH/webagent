# Task Executor - Usage Guide

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install playwright jsonschema

# Install Playwright browsers
playwright install chromium
```

### 2. Run a Task

```bash
# Run B1 (shopping) task with oracle trace (recommended for testing)
python run_task.py B1-shopping

# Run with visible browser (slow motion for debugging)
python run_task.py B1-shopping --slow 500

# Run in headless mode (faster)
python run_task.py B1-shopping --headless

# Run without oracle (let agent decide - not implemented yet)
python run_task.py B1-shopping --no-oracle
```

### 3. Check Results

```bash
# Results are saved to output/<task-name>/result.json
cat output/B1-shopping/result.json

# Screenshots are saved to screenshots/
ls screenshots/

# Error reports are saved to errors/<task-id>/
ls errors/
```

---

## 📖 Usage Examples

### Example 1: Run Single Task (Interactive)

```bash
# Run with visible browser and slow motion
python run_task.py B1-shopping --slow 1000
```

This will:
1. Load task spec from `tasks/B1-shopping/task_spec.json`
2. Load oracle trace from `tasks/B1-shopping/oracle_trace.json`
3. Check preconditions (e.g., memory entries exist)
4. Launch browser (Chromium)
5. Execute each step from oracle trace
6. Verify success criteria
7. Update memory
8. Save results to `output/B1-shopping/result.json`

### Example 2: Run All Tasks (Batch)

```bash
# Run all tasks in headless mode
python run_task.py --all --headless
```

This will run all 10 tasks sequentially and show a summary.

### Example 3: Programmatic Usage

```python
from agent.executor import TaskExecutor

# Create executor
executor = TaskExecutor(
    database_path="data.db",
    headless=False,
    slow_mo=500  # Slow down by 500ms
)

# Run task
result = executor.run(
    task_spec_path="tasks/B1-shopping/task_spec.json",
    oracle_trace_path="tasks/B1-shopping/oracle_trace.json"
)

# Check result
if result.success:
    print(f"✅ Task completed in {result.time_elapsed:.2f}s")
    print(f"   Steps: {result.steps_completed}/{result.steps_total}")
else:
    print(f"❌ Task failed: {result.error.error_message}")
```

---

## 🧩 Components

### TaskExecutor

Main class for executing tasks.

**Constructor**:
```python
TaskExecutor(
    database_path: str = "data.db",        # SQLite database path
    env_api_url: str = "http://...",       # Environment API URL
    headless: bool = False,                # Run browser in headless mode
    slow_mo: int = 0                       # Slow down by N milliseconds
)
```

**Methods**:
- `run(task_spec_path, oracle_trace_path)` - Execute a task
- `_execute_step(step, task_spec)` - Execute a single step
- `_verify_success(task_spec)` - Verify success criteria
- `_update_memory(task_spec)` - Update memory after execution

### ExecutionResult

Result object containing execution details.

**Fields**:
- `success` (bool) - Whether task succeeded
- `final_state` (str) - Final state: completed, failed, aborted
- `steps_completed` (int) - Number of steps completed
- `steps_total` (int) - Total number of steps
- `time_elapsed` (float) - Execution time in seconds
- `error` (ErrorReport) - Error details if failed
- `trace` (list) - Execution trace
- `memory_updates` (dict) - Memory updates made
- `warnings` (list) - Non-fatal warnings

---

## 🎯 Supported Actions

The executor supports these actions from oracle traces:

| Action | Description | Example |
|--------|-------------|---------|
| `open` | Navigate to URL | `{"act": "open", "url": "https://shop.local"}` |
| `click` | Click element | `{"act": "click", "selector": "#search-box"}` |
| `type` | Type text | `{"act": "type", "selector": "#input", "value": "text"}` |
| `select` | Select option | `{"act": "select", "selector": "#dropdown", "value": "option"}` |
| `wait` | Wait for element | `{"act": "wait", "selector": ".loading"}` |
| `assert` | Assert value | `{"act": "assert", "selector": "#status", "value": "success"}` |
| `upload` | Upload file | `{"act": "upload", "selector": "#file", "value": "file.pdf"}` |
| `download` | Download file | `{"act": "download", "selector": "a.download"}` |
| `screenshot` | Take screenshot | `{"act": "screenshot", "screenshot_id": "step_01"}` |

---

## 🔍 Debugging

### Verbose Output

The executor prints detailed logs during execution:

```
================================================================================
🚀 Executing task: B1-2025-001
================================================================================

📋 Checking preconditions...
✅ All preconditions met

🌐 Starting browser...
📜 Loaded oracle trace with 22 steps

⚡ Executing 22 steps...

  Step 1/22: open Navigate to e-commerce homepage
    → Opening https://shop.local

  Step 2/22: click Focus on search input
    → Clicking #search-box

  ... (more steps)

✓ Verifying success criteria...
    ✅ Criterion passed: ALL[url().includes('/order/confirmation')...

✅ Task completed successfully!

💾 Updating 4 memory entries...
  ✅ orders.last.id = O-10001
  ✅ orders.last.total = 30.98
  ✅ orders.last.items = [...]
  ✅ orders.last.timestamp = 2025-11-16T...

================================================================================
📊 Execution completed in 23.45s
   Success: True
   Steps: 22/22
================================================================================
```

### Screenshots

Screenshots are automatically captured:
- On errors: `errors/<task-id>/error_step_<N>.png`
- On specific steps: `screenshots/<screenshot_id>.png`

### Error Reports

Detailed error reports are saved to `errors/<task-id>/error_report.json`:

```json
{
  "task_id": "B1-2025-001",
  "error_type": "TimeoutError",
  "step_index": 5,
  "error_message": "Timeout waiting for selector",
  "context": {
    "url": "https://shop.local/search",
    "screenshot": "errors/B1-2025-001/error_step_5.png"
  },
  "final_state": "aborted"
}
```

---

## ⚙️ Configuration

### Task Timeout

Set in task_spec.json:

```json
{
  "timeout": 300,        // Task-level timeout (seconds)
  "step_timeout": 30     // Per-step timeout (seconds)
}
```

### Error Recovery

Configure error handling strategies:

```json
{
  "error_recovery": {
    "on_timeout": "capture_state_and_abort",
    "on_network_error": {
      "strategy": "retry",
      "max_retries": 3,
      "retry_delay_ms": 1000
    },
    "on_element_not_found": {
      "strategy": "wait_and_retry",
      "wait_seconds": 10
    }
  }
}
```

---

## 🧪 Testing

### Run a Single Test

```bash
# Test B1 shopping task
python run_task.py B1-shopping --slow 500

# Verify result
cat output/B1-shopping/result.json | python -m json.tool
```

### Run All Tests

```bash
# Run all tasks and generate report
python run_task.py --all --headless > test_results.log

# Check summary
tail -20 test_results.log
```

---

## 🐛 Troubleshooting

### Problem: Browser doesn't open

**Solution**:
```bash
# Install Playwright browsers
playwright install chromium
```

### Problem: Element not found

**Solution**:
- Check if selector is correct in oracle trace
- Increase `step_timeout` in task_spec.json
- Add fallback selectors in error_recovery config

### Problem: Assertion fails

**Solution**:
- Check expected vs actual values in error report
- Verify success criteria in task_spec.json
- Check if page state matches expectations

### Problem: Database connection error

**Solution**:
```bash
# Verify database exists
ls -la data.db

# Recreate if needed
sqlite3 data.db < database/schema.sql
sqlite3 data.db < database/seed_data.sql
```

---

## 📁 Output Structure

```
output/
└── B1-shopping/
    └── result.json       # Execution result

screenshots/
├── step_001_homepage.png
├── step_002_search.png
└── ...

errors/
└── B1-2025-001/
    ├── error_report.json
    ├── error_step_5.png
    └── dom_snapshot.html
```

---

## 🚧 Current Limitations

1. **No autonomous agent** - Currently only executes oracle traces
2. **Limited frontend** - Requires actual websites to be running
3. **Simple env API** - Direct database queries, not full JSON path support
4. **No network perturbation** - All requests succeed
5. **No DOM perturbation** - Selectors are static

---

## 🔜 Next Steps

To make the executor fully functional:

1. **Start backend server**:
   ```bash
   python server.py
   ```

2. **Create frontend sites**:
   - Implement shop.local pages
   - Implement bank.local pages
   - Implement gov.local pages

3. **Test with real sites**:
   ```bash
   python run_task.py B1-shopping
   ```

---

## 📚 See Also

- [COMPLETENESS_REPORT.md](COMPLETENESS_REPORT.md) - Full analysis
- [tasks/README.md](tasks/README.md) - Task definitions
- [docs/mvp_scope.md](docs/mvp_scope.md) - MVP scope
- [agent/assertions_dsl.py](agent/assertions_dsl.py) - Assertions DSL
- [agent/error_handlers.py](agent/error_handlers.py) - Error handlers
