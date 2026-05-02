"""
Error handling strategies for web agent task execution.
Implements timeout, network error, element not found, and assertion failure handling.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ErrorReport:
    """Structured error report"""

    def __init__(
        self,
        task_id: str,
        error_type: str,
        timestamp: str,
        step_index: int,
        error_message: str = "",
        context: Optional[Dict[str, Any]] = None,
        step: Optional[Dict[str, Any]] = None,
        recovery_attempted: bool = False,
        recovery_strategy: str = "",
        recovery_success: bool = False,
        final_state: str = "failed"
    ):
        self.task_id = task_id
        self.error_type = error_type
        self.timestamp = timestamp
        self.step_index = step_index
        self.error_message = error_message
        self.context = context or {}
        self.step = step
        self.recovery_attempted = recovery_attempted
        self.recovery_strategy = recovery_strategy
        self.recovery_success = recovery_success
        self.final_state = final_state
        self.metrics = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "task_id": self.task_id,
            "error_type": self.error_type,
            "timestamp": self.timestamp,
            "step_index": self.step_index,
            "error_message": self.error_message,
            "context": self.context,
            "step": self.step,
            "recovery_attempted": self.recovery_attempted,
            "recovery_strategy": self.recovery_strategy,
            "recovery_success": self.recovery_success,
            "final_state": self.final_state,
            "metrics": self.metrics
        }

    def save(self, output_dir: str):
        """Save error report to file"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "error_report.json")
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Error report saved to {filepath}")


class TimeoutHandler:
    """Handle task and step-level timeouts"""

    @staticmethod
    def handle_timeout(
        task: Dict[str, Any],
        current_step_index: int,
        capture_state_fn: Callable,
        cleanup_fn: Callable
    ) -> str:
        """
        Strategy A: Capture State and Abort (Default)

        Args:
            task: Task specification
            current_step_index: Index of step that timed out
            capture_state_fn: Function to capture current state
            cleanup_fn: Function to cleanup resources

        Returns:
            "aborted"
        """
        logger.error(f"Task {task['task_id']} timed out at step {current_step_index}")

        # Capture state
        state = capture_state_fn()

        # Generate error report
        error_report = ErrorReport(
            task_id=task['task_id'],
            error_type="timeout_task",
            timestamp=datetime.utcnow().isoformat() + "Z",
            step_index=current_step_index,
            error_message=f"Task timeout at step {current_step_index}",
            context=state,
            recovery_attempted=False,
            final_state="failed"
        )

        # Save error report
        error_dir = f"errors/{task['task_id']}"
        error_report.save(error_dir)

        # Cleanup
        cleanup_fn()

        return "aborted"


class NetworkErrorHandler:
    """Handle network-related errors"""

    @staticmethod
    def handle_with_retry(
        task: Dict[str, Any],
        step: Dict[str, Any],
        execute_step_fn: Callable,
        error: Exception
    ) -> str:
        """
        Strategy A: Simple Retry with fixed delay

        Args:
            task: Task specification
            step: Step that failed
            execute_step_fn: Function to execute the step
            error: Original network error

        Returns:
            "success" or "failed"
        """
        config = task.get('error_recovery', {}).get('on_network_error', {})
        max_retries = config.get('max_retries', 3)
        retry_delay_ms = config.get('retry_delay_ms', 1000)

        logger.warning(f"Network error on step {step.get('note', 'unnamed')}: {error}")

        for attempt in range(max_retries):
            time.sleep(retry_delay_ms / 1000.0)
            logger.info(f"Retry attempt {attempt + 1}/{max_retries}")

            try:
                execute_step_fn(step)
                logger.info(f"Retry successful on attempt {attempt + 1}")
                return "success"
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} retries failed")
                    raise
                logger.warning(f"Retry {attempt + 1} failed: {e}")

        return "failed"

    @staticmethod
    def handle_with_backoff(
        task: Dict[str, Any],
        step: Dict[str, Any],
        execute_step_fn: Callable,
        error: Exception
    ) -> str:
        """
        Strategy B: Exponential Backoff

        Retry with exponentially increasing delays:
        - 1st retry: initial_delay
        - 2nd retry: initial_delay * multiplier
        - 3rd retry: initial_delay * multiplier^2
        """
        config = task.get('error_recovery', {}).get('on_network_error', {})
        max_retries = config.get('max_retries', 3)
        initial_delay_ms = config.get('retry_delay_ms', 1000)
        multiplier = config.get('backoff_multiplier', 2.0)

        logger.warning(f"Network error (backoff mode): {error}")

        delay_ms = initial_delay_ms
        for attempt in range(max_retries):
            time.sleep(delay_ms / 1000.0)
            logger.info(f"Retry attempt {attempt + 1}/{max_retries} (delay: {delay_ms}ms)")

            try:
                execute_step_fn(step)
                logger.info(f"Retry successful on attempt {attempt + 1}")
                return "success"
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} retries failed with backoff")
                    # Create error report
                    error_report = ErrorReport(
                        task_id=task['task_id'],
                        error_type="network_timeout",
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        step_index=-1,
                        error_message=str(e),
                        recovery_attempted=True,
                        recovery_strategy="exponential_backoff",
                        recovery_success=False,
                        final_state="failed"
                    )
                    error_report.metrics['retries'] = max_retries
                    error_report.save(f"errors/{task['task_id']}")
                    raise

                delay_ms *= multiplier

        return "failed"


class ElementNotFoundHandler:
    """Handle element not found errors"""

    @staticmethod
    def handle_with_fallback(
        task: Dict[str, Any],
        step: Dict[str, Any],
        wait_for_element_fn: Callable
    ):
        """
        Try fallback selectors if primary selector fails

        Args:
            task: Task specification
            step: Step with selector
            wait_for_element_fn: Function to wait for element

        Returns:
            Element if found, raises exception otherwise
        """
        config = task.get('error_recovery', {}).get('on_element_not_found', {})
        wait_seconds = config.get('wait_seconds', 10)
        fallback_selectors = config.get('fallback_selectors', {})

        primary_selector = step['selector']

        # Try primary selector
        try:
            logger.info(f"Waiting for element: {primary_selector}")
            element = wait_for_element_fn(primary_selector, timeout=wait_seconds)
            return element
        except Exception as e:
            logger.warning(f"Primary selector failed: {primary_selector}")

        # Try fallback selectors
        fallbacks = fallback_selectors.get(primary_selector, [])
        for i, fallback in enumerate(fallbacks):
            try:
                logger.info(f"Trying fallback selector {i+1}/{len(fallbacks)}: {fallback}")
                element = wait_for_element_fn(fallback, timeout=5)
                logger.info(f"Fallback selector succeeded: {fallback}")
                return element
            except Exception as e:
                logger.warning(f"Fallback {i+1} failed: {fallback}")
                continue

        # All attempts failed
        error_report = ErrorReport(
            task_id=task['task_id'],
            error_type="element_not_found",
            timestamp=datetime.utcnow().isoformat() + "Z",
            step_index=step.get('index', -1),
            error_message=f"Element not found: {primary_selector}",
            context={
                "selector": primary_selector,
                "fallback_selectors": fallbacks
            },
            recovery_attempted=True,
            recovery_strategy="try_fallback_selector",
            recovery_success=False
        )
        error_report.save(f"errors/{task['task_id']}")

        raise Exception(f"Element not found after all attempts: {primary_selector}")


class AssertionFailureHandler:
    """Handle assertion failures"""

    @staticmethod
    def handle_with_retry(
        task: Dict[str, Any],
        assertion: str,
        actual_value: Any,
        expected_value: Any,
        evaluate_fn: Callable,
        capture_state_fn: Callable
    ) -> str:
        """
        Retry assertion after wait (for async state updates)

        Args:
            task: Task specification
            assertion: Assertion expression
            actual_value: Actual value from page
            expected_value: Expected value
            evaluate_fn: Function to re-evaluate assertion
            capture_state_fn: Function to capture state

        Returns:
            "success" or "failed"
        """
        config = task.get('error_recovery', {}).get('on_assertion_fail', {})
        wait_seconds = config.get('wait_before_retry_seconds', 5)

        logger.warning(f"Assertion failed: {assertion}")
        logger.warning(f"Expected: {expected_value}, Actual: {actual_value}")

        # Wait before retry
        logger.info(f"Waiting {wait_seconds}s before retry...")
        time.sleep(wait_seconds)

        # Re-evaluate
        new_actual_value = evaluate_fn(assertion)
        if new_actual_value == expected_value:
            logger.info("Assertion succeeded on retry")
            return "success"

        # Still failing - capture full state and report
        logger.error(f"Assertion still failing after retry: {new_actual_value}")

        state = {}
        if config.get('capture_screenshot', True):
            state['screenshot'] = "captured"
        if config.get('capture_dom', True):
            state['dom'] = "captured"
        if config.get('capture_memory', True):
            state['memory'] = capture_state_fn()

        error_report = ErrorReport(
            task_id=task['task_id'],
            error_type="assertion_failed",
            timestamp=datetime.utcnow().isoformat() + "Z",
            step_index=-1,
            error_message=f"Assertion failed: {assertion}",
            context={
                "assertion": assertion,
                "expected": expected_value,
                "actual_first": actual_value,
                "actual_retry": new_actual_value,
                **state
            },
            recovery_attempted=True,
            recovery_strategy="retry_after_wait",
            recovery_success=False,
            final_state="failed"
        )
        error_report.save(f"errors/{task['task_id']}")

        return "failed"


def check_preconditions(task: Dict[str, Any], evaluate_fn: Callable) -> bool:
    """
    Check all preconditions before executing task

    Args:
        task: Task specification
        evaluate_fn: Function to evaluate assertions

    Returns:
        True if all preconditions met, raises exception otherwise
    """
    preconditions = task.get('preconditions', [])

    for precondition in preconditions:
        try:
            result = evaluate_fn(precondition)
            if not result:
                strategy = task.get('error_recovery', {}).get('on_precondition_fail', 'abort_with_warning')

                if strategy == 'abort_with_warning':
                    logger.error(f"Precondition not met: {precondition}")
                    error_report = ErrorReport(
                        task_id=task['task_id'],
                        error_type="precondition_not_met",
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        step_index=-1,
                        error_message=f"Precondition not met: {precondition}",
                        context={"precondition": precondition},
                        final_state="aborted"
                    )
                    error_report.save(f"errors/{task['task_id']}")
                    raise Exception(f"Precondition not met: {precondition}")

        except Exception as e:
            logger.error(f"Error checking precondition '{precondition}': {e}")
            raise

    logger.info(f"All {len(preconditions)} preconditions met")
    return True
