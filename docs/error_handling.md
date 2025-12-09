# Error Handling Mechanisms (P0)

**Version**: v1.0
**Last Updated**: 2025-11-16
**Purpose**: Define comprehensive error handling for timeouts, network errors, assertion failures, and recovery strategies

---

## 1. Error Taxonomy

### 1.1 Error Categories
```
Errors
├── Infrastructure Errors (recoverable)
│   ├── Network Errors (DNS, connection, timeout)
│   ├── Browser Errors (crash, unresponsive)
│   └── Service Errors (backend down, DB locked)
│
├── Execution Errors (partially recoverable)
│   ├── Timeout (task-level, step-level)
│   ├── Element Not Found
│   ├── Selector Ambiguous (multiple matches)
│   └── Action Failed (click intercepted, input disabled)
│
├── Logic Errors (agent mistakes)
│   ├── Assertion Failed (expected != actual)
│   ├── Precondition Not Met
│   ├── Invalid Input (out of range, wrong format)
│   └── State Inconsistency (memory vs reality)
│
└── Catastrophic Errors (non-recoverable)
    ├── Authentication Failure (account locked)
    ├── Budget Exceeded
    ├── Legal/Policy Violation
    └── Data Corruption
```

---

## 2. Extended TaskSpec Schema with Error Handling

### 2.1 Enhanced TaskSpec
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TaskSpec_v2_ErrorHandling",
  "type": "object",
  "required": ["task_id", "family", "goal", "inputs", "success_criteria", "error_recovery"],
  "properties": {
    "... (previous fields)": "...",

    "timeout": {
      "type": "integer",
      "description": "Task-level timeout in seconds (default: 300)",
      "default": 300,
      "minimum": 10,
      "maximum": 3600
    },

    "step_timeout": {
      "type": "integer",
      "description": "Per-step timeout in seconds (default: 30)",
      "default": 30,
      "minimum": 1,
      "maximum": 300
    },

    "error_recovery": {
      "type": "object",
      "description": "Error handling strategies",
      "properties": {
        "on_timeout": {
          "type": "string",
          "enum": ["abort", "capture_state_and_abort", "retry_from_checkpoint", "skip_step"],
          "default": "capture_state_and_abort"
        },
        "on_network_error": {
          "type": "object",
          "properties": {
            "strategy": {
              "type": "string",
              "enum": ["retry", "exponential_backoff", "abort"],
              "default": "retry"
            },
            "max_retries": {"type": "integer", "default": 3},
            "retry_delay_ms": {"type": "integer", "default": 1000},
            "backoff_multiplier": {"type": "number", "default": 2.0}
          }
        },
        "on_element_not_found": {
          "type": "object",
          "properties": {
            "strategy": {
              "type": "string",
              "enum": ["wait_and_retry", "try_fallback_selector", "abort"],
              "default": "wait_and_retry"
            },
            "wait_seconds": {"type": "integer", "default": 10},
            "fallback_selectors": {
              "type": "object",
              "description": "Map of original_selector -> fallback_selector[]"
            }
          }
        },
        "on_assertion_fail": {
          "type": "object",
          "properties": {
            "strategy": {
              "type": "string",
              "enum": ["save_trace_and_report", "retry_after_wait", "abort_silent"],
              "default": "save_trace_and_report"
            },
            "capture_screenshot": {"type": "boolean", "default": true},
            "capture_dom": {"type": "boolean", "default": true},
            "capture_memory": {"type": "boolean", "default": true},
            "wait_before_retry_seconds": {"type": "integer", "default": 5}
          }
        },
        "on_precondition_fail": {
          "type": "string",
          "enum": ["abort_with_warning", "attempt_repair", "skip_task"],
          "default": "abort_with_warning"
        },
        "on_state_inconsistency": {
          "type": "string",
          "enum": ["trust_env", "trust_memory", "manual_resolution", "abort"],
          "default": "trust_env"
        }
      },
      "required": ["on_timeout", "on_network_error", "on_assertion_fail"]
    },

    "checkpoints": {
      "type": "array",
      "description": "Checkpoint step indices for rollback",
      "items": {"type": "integer"},
      "example": [0, 10, 20]
    },

    "fallback_plan": {
      "type": "object",
      "description": "Alternative execution plan if primary fails",
      "properties": {
        "enabled": {"type": "boolean", "default": false},
        "alternative_task_id": {"type": "string"},
        "relaxed_success_criteria": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 3. Error Response Schema

### 3.1 ErrorReport
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ErrorReport",
  "type": "object",
  "required": ["task_id", "error_type", "timestamp", "step_index"],
  "properties": {
    "task_id": {"type": "string"},
    "error_type": {
      "type": "string",
      "enum": [
        "timeout_task",
        "timeout_step",
        "network_dns_failure",
        "network_connection_refused",
        "network_timeout",
        "element_not_found",
        "selector_ambiguous",
        "action_failed",
        "assertion_failed",
        "precondition_not_met",
        "state_inconsistency",
        "authentication_failed",
        "budget_exceeded",
        "unknown"
      ]
    },
    "timestamp": {"type": "string", "format": "date-time"},
    "step_index": {"type": "integer", "description": "Which step failed (0-indexed)"},
    "step": {
      "type": "object",
      "description": "The failed step from Trace"
    },
    "error_message": {"type": "string"},
    "stack_trace": {"type": "string"},
    "context": {
      "type": "object",
      "properties": {
        "url": {"type": "string"},
        "screenshot_id": {"type": "string"},
        "dom_snapshot_id": {"type": "string"},
        "memory_snapshot": {"type": "object"},
        "env_snapshot": {"type": "object"},
        "browser_console_logs": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "recovery_attempted": {"type": "boolean"},
    "recovery_strategy": {"type": "string"},
    "recovery_success": {"type": "boolean"},
    "final_state": {
      "type": "string",
      "enum": ["completed", "partial_success", "failed", "aborted"]
    },
    "metrics": {
      "type": "object",
      "properties": {
        "steps_completed": {"type": "integer"},
        "steps_total": {"type": "integer"},
        "time_elapsed_seconds": {"type": "number"},
        "retries_count": {"type": "integer"}
      }
    }
  }
}
```

---

## 4. Error Handling Strategies (Detailed)

### 4.1 Timeout Handling

#### Strategy A: Capture State and Abort (Default)
```python
def handle_timeout(task, current_step_index):
    """
    When timeout occurs:
    1. Capture full state (screenshot, DOM, memory, env)
    2. Generate ErrorReport
    3. Save partial trace
    4. Mark task as 'failed' with reason 'timeout'
    5. Clean up resources
    """
    error_report = ErrorReport(
        task_id=task.task_id,
        error_type="timeout_task",
        timestamp=now(),
        step_index=current_step_index,
        context={
            "screenshot_id": capture_screenshot(),
            "dom_snapshot_id": capture_dom(),
            "memory_snapshot": memory.dump(),
            "env_snapshot": env_api.get_all()
        },
        recovery_attempted=False,
        final_state="failed"
    )
    save_error_report(error_report)
    cleanup_browser()
    return "aborted"
```

#### Strategy B: Retry from Checkpoint
```python
def handle_timeout_with_retry(task, current_step_index):
    """
    1. Find nearest checkpoint before current_step_index
    2. Restore state from checkpoint
    3. Retry from checkpoint with increased timeout
    4. If retry fails again, abort
    """
    checkpoint_index = find_nearest_checkpoint(task.checkpoints, current_step_index)
    if checkpoint_index is None:
        return handle_timeout(task, current_step_index)  # fallback to abort

    restore_from_checkpoint(checkpoint_index)
    task.timeout *= 1.5  # increase timeout by 50%

    try:
        execute_from_step(task, checkpoint_index)
    except TimeoutError:
        return handle_timeout(task, current_step_index)
```

---

### 4.2 Network Error Handling

#### Strategy A: Simple Retry (Default)
```python
def handle_network_error(task, step, error):
    """
    Retry up to max_retries times with fixed delay
    """
    config = task.error_recovery["on_network_error"]
    max_retries = config.get("max_retries", 3)
    retry_delay_ms = config.get("retry_delay_ms", 1000)

    for attempt in range(max_retries):
        time.sleep(retry_delay_ms / 1000.0)
        try:
            execute_step(step)
            return "success"
        except NetworkError as e:
            if attempt == max_retries - 1:
                raise  # re-raise on final attempt

    return "failed"
```

#### Strategy B: Exponential Backoff
```python
def handle_network_error_with_backoff(task, step, error):
    """
    Retry with exponentially increasing delays
    1st retry: 1s
    2nd retry: 2s
    3rd retry: 4s
    """
    config = task.error_recovery["on_network_error"]
    max_retries = config.get("max_retries", 3)
    initial_delay_ms = config.get("retry_delay_ms", 1000)
    multiplier = config.get("backoff_multiplier", 2.0)

    delay_ms = initial_delay_ms
    for attempt in range(max_retries):
        time.sleep(delay_ms / 1000.0)
        try:
            execute_step(step)
            return "success"
        except NetworkError as e:
            if attempt == max_retries - 1:
                error_report = create_network_error_report(task, step, e, attempts=max_retries)
                save_error_report(error_report)
                raise
            delay_ms *= multiplier
```

---

### 4.3 Element Not Found Handling

#### Strategy A: Wait and Retry (Default)
```python
def handle_element_not_found(task, step):
    """
    Wait up to wait_seconds for element to appear
    """
    config = task.error_recovery.get("on_element_not_found", {})
    wait_seconds = config.get("wait_seconds", 10)

    try:
        element = wait_for_element(step.selector, timeout=wait_seconds)
        return element
    except TimeoutError:
        # Try fallback selectors if available
        fallback_selectors = config.get("fallback_selectors", {}).get(step.selector, [])
        for fallback in fallback_selectors:
            try:
                element = wait_for_element(fallback, timeout=5)
                return element
            except TimeoutError:
                continue

        # All attempts failed
        error_report = ErrorReport(
            task_id=task.task_id,
            error_type="element_not_found",
            step_index=step.index,
            error_message=f"Element not found: {step.selector}",
            context={
                "selector": step.selector,
                "fallback_selectors": fallback_selectors,
                "screenshot_id": capture_screenshot()
            }
        )
        raise ElementNotFoundError(error_report)
```

#### Example: Fallback Selectors
```json
{
  "error_recovery": {
    "on_element_not_found": {
      "strategy": "try_fallback_selector",
      "wait_seconds": 10,
      "fallback_selectors": {
        "#checkout-button": [
          "button[aria-label='Checkout']",
          ".checkout-btn",
          "//button[contains(text(),'Checkout')]"
        ],
        "#search-box": [
          "input[name='q']",
          "input[type='search']",
          "[aria-label='Search']"
        ]
      }
    }
  }
}
```

---

### 4.4 Assertion Failure Handling

#### Strategy A: Save Trace and Report (Default)
```python
def handle_assertion_failure(task, assertion, actual_value, expected_value):
    """
    When assertion fails:
    1. Capture full context (screenshot, DOM, memory, env)
    2. Generate detailed error report
    3. Save trace with all steps up to failure
    4. Mark task as failed
    """
    config = task.error_recovery["on_assertion_fail"]

    context = {}
    if config.get("capture_screenshot", True):
        context["screenshot_id"] = capture_screenshot()
    if config.get("capture_dom", True):
        context["dom_snapshot_id"] = capture_dom()
    if config.get("capture_memory", True):
        context["memory_snapshot"] = memory.dump()

    # Capture actual vs expected
    context["assertion"] = {
        "expression": assertion,
        "expected": expected_value,
        "actual": actual_value,
        "diff": compute_diff(expected_value, actual_value)
    }

    error_report = ErrorReport(
        task_id=task.task_id,
        error_type="assertion_failed",
        timestamp=now(),
        step_index=current_step_index(),
        error_message=f"Assertion failed: {assertion}",
        context=context,
        final_state="failed"
    )

    save_error_report(error_report)
    save_partial_trace(task)

    return "failed"
```

#### Strategy B: Retry After Wait
```python
def handle_assertion_failure_with_retry(task, assertion, actual_value, expected_value):
    """
    Some assertions may fail temporarily (e.g., waiting for async update)
    Wait and retry once before giving up
    """
    config = task.error_recovery["on_assertion_fail"]
    wait_seconds = config.get("wait_before_retry_seconds", 5)

    time.sleep(wait_seconds)

    # Re-evaluate assertion
    new_actual_value = evaluate_assertion(assertion)
    if new_actual_value == expected_value:
        return "success"
    else:
        # Still failing, proceed with default strategy
        return handle_assertion_failure(task, assertion, new_actual_value, expected_value)
```

---

### 4.5 Precondition Failure Handling

```python
def check_preconditions(task):
    """
    Before executing task, verify all preconditions
    """
    for precondition in task.preconditions:
        try:
            result = evaluate_assertion(precondition)
            if not result:
                handle_precondition_failure(task, precondition)
        except Exception as e:
            handle_precondition_failure(task, precondition, error=e)

def handle_precondition_failure(task, precondition, error=None):
    """
    Strategies:
    - abort_with_warning: Don't execute, log warning
    - attempt_repair: Try to set up precondition (e.g., create missing data)
    - skip_task: Mark as skipped, continue to next task
    """
    strategy = task.error_recovery.get("on_precondition_fail", "abort_with_warning")

    if strategy == "abort_with_warning":
        error_report = ErrorReport(
            task_id=task.task_id,
            error_type="precondition_not_met",
            timestamp=now(),
            step_index=-1,
            error_message=f"Precondition not met: {precondition}",
            context={"precondition": precondition, "error": str(error)},
            final_state="aborted"
        )
        save_error_report(error_report)
        raise PreconditionError(precondition)

    elif strategy == "attempt_repair":
        # Example: if mem("address.primary") is missing, try to set default
        repair_success = attempt_precondition_repair(precondition)
        if not repair_success:
            raise PreconditionError(precondition)

    elif strategy == "skip_task":
        log.warning(f"Skipping task {task.task_id} due to precondition failure: {precondition}")
        return "skipped"
```

---

## 5. Error Handling Examples (E2E Tasks)

### 5.1 Example: B1 with Timeout Error

**Scenario**: Search results take >30 seconds to load

```json
{
  "task_id": "B1-2025-001-ERROR-TIMEOUT",
  "... (other fields same as B1)": "...",
  "step_timeout": 30,
  "error_recovery": {
    "on_timeout": "capture_state_and_abort",
    "on_network_error": {"strategy": "retry", "max_retries": 3}
  }
}
```

**Trace (Partial - Failure)**:
```json
{
  "steps": [
    {"t": 0, "url": "https://shop.local", "act": "open"},
    {"t": 1.2, "act": "click", "selector": "#search-box"},
    {"t": 1.5, "act": "type", "selector": "#search-box", "value": "wireless mouse"},
    {"t": 2.0, "act": "click", "selector": "button[type='submit']"},
    {
      "t": 32.5,
      "act": "wait",
      "selector": ".product-grid .product-item",
      "note": "TIMEOUT: Element not visible after 30 seconds"
    }
  ],
  "error": {
    "type": "timeout_step",
    "step_index": 4,
    "message": "Step timeout: wait for .product-grid .product-item exceeded 30s"
  }
}
```

**ErrorReport**:
```json
{
  "task_id": "B1-2025-001-ERROR-TIMEOUT",
  "error_type": "timeout_step",
  "timestamp": "2025-11-16T09:00:32Z",
  "step_index": 4,
  "step": {
    "t": 32.5,
    "act": "wait",
    "selector": ".product-grid .product-item"
  },
  "error_message": "Step timeout: wait for .product-grid .product-item exceeded 30s",
  "context": {
    "url": "https://shop.local/search?q=wireless+mouse",
    "screenshot_id": "error_timeout_b1_step4.png",
    "dom_snapshot_id": "error_timeout_b1_step4.html",
    "browser_console_logs": [
      "[ERROR] Failed to fetch /api/search: net::ERR_CONNECTION_TIMED_OUT"
    ]
  },
  "recovery_attempted": false,
  "final_state": "failed",
  "metrics": {
    "steps_completed": 4,
    "steps_total": 23,
    "time_elapsed_seconds": 32.5,
    "retries_count": 0
  }
}
```

---

### 5.2 Example: D4 with Network Error (Retry Success)

**Scenario**: Bank.local temporarily unreachable, retry succeeds

```json
{
  "task_id": "D4-2025-003-ERROR-NETWORK",
  "error_recovery": {
    "on_network_error": {
      "strategy": "exponential_backoff",
      "max_retries": 3,
      "retry_delay_ms": 1000,
      "backoff_multiplier": 2.0
    }
  }
}
```

**Trace (with Retry)**:
```json
{
  "steps": [
    {
      "t": 0,
      "url": "https://bank.local/cards",
      "act": "open",
      "note": "ATTEMPT 1: FAILED - Connection refused"
    },
    {
      "t": 1.0,
      "url": "https://bank.local/cards",
      "act": "open",
      "note": "RETRY 1 (after 1s): FAILED - Connection refused"
    },
    {
      "t": 3.0,
      "url": "https://bank.local/cards",
      "act": "open",
      "note": "RETRY 2 (after 2s): SUCCESS"
    },
    {"t": 5.0, "act": "click", "selector": "#card-1234 .activate-new-card"}
  ],
  "warnings": [
    {
      "type": "network_error_recovered",
      "step_index": 0,
      "retries": 2,
      "message": "Network error recovered after 2 retries"
    }
  ]
}
```

---

### 5.3 Example: C2 with Assertion Failure

**Scenario**: Return state is "processing" instead of "approved"

```json
{
  "task_id": "C2-2025-002-ERROR-ASSERTION",
  "error_recovery": {
    "on_assertion_fail": {
      "strategy": "retry_after_wait",
      "wait_before_retry_seconds": 5,
      "capture_screenshot": true,
      "capture_dom": true
    }
  }
}
```

**Trace (Assertion Retry)**:
```json
{
  "steps": [
    "... (steps 0-9 successful) ...",
    {
      "t": 13,
      "act": "assert",
      "selector": "#return-state",
      "value": "approved",
      "note": "FAILED: actual value = 'processing'"
    },
    {
      "t": 18,
      "act": "assert",
      "selector": "#return-state",
      "value": "approved",
      "note": "RETRY after 5s: SUCCESS"
    }
  ],
  "warnings": [
    {
      "type": "assertion_retry_success",
      "step_index": 10,
      "message": "Assertion succeeded on retry after 5s wait"
    }
  ]
}
```

---

### 5.4 Example: H3 with Element Not Found (Fallback Success)

**Scenario**: Primary calendar selector fails, fallback succeeds

```json
{
  "task_id": "H3-2025-004-ERROR-ELEMENT",
  "error_recovery": {
    "on_element_not_found": {
      "strategy": "try_fallback_selector",
      "wait_seconds": 10,
      "fallback_selectors": {
        ".calendar-date[data-date='2025-12-01']": [
          "#calendar-day-2025-12-01",
          "//td[@data-date='2025-12-01']",
          "button:has-text('December 1')"
        ]
      }
    }
  }
}
```

**Trace**:
```json
{
  "steps": [
    {
      "t": 38,
      "act": "click",
      "selector": ".calendar-date[data-date='2025-12-01']",
      "note": "PRIMARY SELECTOR FAILED: Element not found"
    },
    {
      "t": 48,
      "act": "click",
      "selector": "#calendar-day-2025-12-01",
      "note": "FALLBACK 1: FAILED"
    },
    {
      "t": 53,
      "act": "click",
      "selector": "//td[@data-date='2025-12-01']",
      "note": "FALLBACK 2: SUCCESS"
    }
  ],
  "warnings": [
    {
      "type": "fallback_selector_used",
      "step_index": 38,
      "original_selector": ".calendar-date[data-date='2025-12-01']",
      "successful_fallback": "//td[@data-date='2025-12-01']"
    }
  ]
}
```

---

## 6. Monitoring & Debugging

### 6.1 Error Rate Metrics
```json
{
  "error_metrics": {
    "total_tasks": 100,
    "successful": 85,
    "failed": 15,
    "error_breakdown": {
      "timeout_task": 3,
      "timeout_step": 5,
      "network_error": 4,
      "assertion_failed": 2,
      "element_not_found": 1
    },
    "recovery_success_rate": {
      "network_error": 0.75,
      "element_not_found": 1.0,
      "assertion_retry": 0.5
    }
  }
}
```

### 6.2 Debug Artifacts
For each error, save:
1. **Screenshot** (PNG): Visual state at failure
2. **DOM Snapshot** (HTML): Full page HTML
3. **Memory Snapshot** (JSON): All memory KV entries
4. **Env Snapshot** (JSON): All env state
5. **Console Logs** (TXT): Browser console output
6. **Network Logs** (HAR): HTTP requests/responses
7. **Trace** (JSON): All steps up to failure

**Directory Structure**:
```
/errors/
  /B1-2025-001-ERROR-TIMEOUT/
    error_report.json
    screenshot.png
    dom_snapshot.html
    memory_snapshot.json
    env_snapshot.json
    console_logs.txt
    network_logs.har
    partial_trace.json
```

---

## 7. Testing Error Handling

### 7.1 Fault Injection for Testing
```python
# Test timeout handling
def test_timeout_handling():
    task = load_task("B1-2025-001")
    task.step_timeout = 1  # Force timeout

    result = execute_task(task)
    assert result.final_state == "failed"
    assert result.error.error_type == "timeout_step"
    assert os.path.exists(f"errors/{task.task_id}/screenshot.png")

# Test network error recovery
def test_network_error_retry():
    inject_network_failure(duration=2000)  # Fail for 2 seconds

    task = load_task("D4-2025-003")
    result = execute_task(task)

    assert result.final_state == "completed"
    assert len(result.warnings) > 0
    assert result.warnings[0].type == "network_error_recovered"

# Test assertion retry
def test_assertion_retry():
    # Simulate async state update (approved after 3 seconds)
    simulate_delayed_state_update("return_state", "approved", delay=3)

    task = load_task("C2-2025-002")
    result = execute_task(task)

    assert result.final_state == "completed"
    assert any(w.type == "assertion_retry_success" for w in result.warnings)
```

---

## 8. Best Practices

### 8.1 Choosing Timeout Values
- **Simple tasks** (T1-T3): 300s task, 30s step
- **Medium tasks** (T4-T7): 450s task, 45s step
- **Complex tasks** (T8-T10): 600s task, 60s step

### 8.2 When to Retry vs Abort
| Error Type | Retry? | Max Retries | Reason |
|------------|--------|-------------|--------|
| Network timeout | Yes | 3 | Transient issue |
| DNS failure | Yes | 2 | May resolve quickly |
| Element not found | Yes | 1 | May need more wait |
| Assertion failed (state) | Yes | 1 | Async updates |
| Assertion failed (value) | No | 0 | Logic error |
| Authentication failed | No | 0 | Credentials issue |
| Timeout (task) | No | 0 | Task too complex |

### 8.3 Error Logging Verbosity
- **Production**: Log errors only (ERROR level)
- **Evaluation**: Log errors + warnings (WARN level)
- **Debug**: Log all steps + context (DEBUG level)

---

## 9. Summary

### Error Handling Coverage
✅ **Timeout**: Task-level, step-level, with state capture
✅ **Network**: Retry with exponential backoff
✅ **Element Not Found**: Wait + fallback selectors
✅ **Assertion Failure**: Retry + detailed debugging
✅ **Precondition**: Validation + repair strategies
✅ **State Inconsistency**: Trust env vs memory policies

### Implementation Checklist
- [ ] Extend TaskSpec schema with error_recovery field
- [ ] Implement ErrorReport class
- [ ] Build timeout handler with state capture
- [ ] Build network error handler with retry logic
- [ ] Build element not found handler with fallbacks
- [ ] Build assertion failure handler with debugging
- [ ] Create error artifact storage system
- [ ] Add error injection for testing
- [ ] Collect error metrics dashboard
- [ ] Document error codes & troubleshooting guide

### Next Steps
1. Implement error handling in Playwright wrapper
2. Test all 5 e2e examples with injected faults
3. Validate ErrorReport schema
4. Create error analysis tools (log parser, visualizer)
