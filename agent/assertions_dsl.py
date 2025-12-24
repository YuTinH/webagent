"""
Assertions DSL Interpreter for Web Agent Task Evaluation.

Supports atoms like:
- exists("<selector>")
- text("<selector>") == "<str>"
- attr("<selector>", "<name>") == "<value>"
- count("<selector>") >= N
- url().includes("<path>")
- mem("<key>") == "<expected>"
- json("<channel>", "<path>") == <value>

And combinators:
- ALL[...]
- ANY[...]
- NOT[...]
- WITHIN(seconds, Expr)
- EVENTUALLY(Expr)
- STABLE(seconds, Expr)
"""

import re
import json
import time
from typing import Any, Dict, Callable, Optional
from playwright.sync_api import Page


class AssertionDSL:
    """Interpreter for Assertions DSL"""

    def __init__(
        self,
        page: Page,
        memory: Dict[str, Any],
        env_api_fn: Callable[[str, str], Any]
    ):
        """
        Args:
            page: Playwright Page object
            memory: Memory KV store dictionary
            env_api_fn: Function to query env API: (channel, path) -> value
        """
        self.page = page
        self.memory = memory
        self.env_api_fn = env_api_fn

    def evaluate(self, assertion: str) -> bool:
        """
        Evaluate an assertion expression

        Args:
            assertion: Assertion string (e.g., "text('#order-id') != ''")

        Returns:
            True if assertion holds, False otherwise
        """
        assertion = assertion.strip()

        # Combinators
        if assertion.startswith('ALL['):
            return self._eval_all(assertion)
        elif assertion.startswith('ANY['):
            return self._eval_any(assertion)
        elif assertion.startswith('NOT['):
            return self._eval_not(assertion)
        elif assertion.startswith('WITHIN('):
            return self._eval_within(assertion)
        elif assertion.startswith('EVENTUALLY('):
            return self._eval_eventually(assertion)
        elif assertion.startswith('STABLE('):
            return self._eval_stable(assertion)

        # Atoms
        res = self._eval_atom(assertion)
        # print(f"DEBUG: DSL eval '{assertion}' -> {res}")
        return res

    def _eval_atom(self, assertion: str) -> bool:
        """Evaluate atomic assertion"""
        print(f"DEBUG: Eval Atom: '{assertion}'")

        # exists("<selector>")
        match = re.match(r'exists\("(.+?)"\)', assertion)
        if match:
            selector = match.group(1)
            return self.page.locator(selector).count() > 0

        # text("<selector>") == "<str>" or text("<selector>") != ""
        match = re.match(r'text\([\'"](.+?)[\'"]\)\s*(==|!=|includes)\s*[\'"](.*?)[\'"]', assertion)
        if match:
            selector, op, expected = match.groups()
            try:
                actual = self.page.locator(selector).inner_text()
                if op == '==':
                    if actual != expected:
                        print(f"DEBUG: Text mismatch. Actual: '{actual}', Expected: '{expected}'")
                    return actual == expected
                elif op == '!=':
                    return actual != expected
                elif op == 'includes':
                    return expected in actual
            except:
                return False

        # text("<selector>") == mem("<key>")
        match = re.match(r'text\("(.+?)"\)\s*==\s*mem\(\'(.+?)\'\)', assertion)
        if match:
            selector, mem_key = match.groups()
            try:
                actual = self.page.locator(selector).inner_text()
                expected = self._get_memory(mem_key)
                return str(actual) == str(expected)
            except:
                return False

        # attr("<selector>", "<name>") == "<value>"
        match = re.match(r'attr\("(.+?)",\s*"(.+?)"\)\s*(==|!=)\s*"(.+?)"', assertion)
        if match:
            selector, attr_name, op, expected = match.groups()
            try:
                actual = self.page.locator(selector).get_attribute(attr_name)
                if op == '==':
                    return actual == expected
                elif op == '!=':
                    return actual != expected
            except:
                return False

        # count("<selector>") >= N
        match = re.match(r'count\([\'"](.+?)[\'"]\)\s*(>=|<=|==|>|<)\s*(\d+)', assertion)
        if match:
            selector, op, threshold = match.groups()
            threshold = int(threshold)
            actual_count = self.page.locator(selector).count()

            if op == '>=':
                return actual_count >= threshold
            elif op == '<=':
                return actual_count <= threshold
            elif op == '==':
                return actual_count == threshold
            elif op == '>':
                return actual_count > threshold
            elif op == '<':
                return actual_count < threshold

        # url().includes("<path>")
        match = re.match(r"url\(\)\.includes\(['\"](.+?)['\"]\)", assertion)
        if match:
            path = match.group(1)
            return path in self.page.url

        # mem("<key>") == "<expected>"
        match = re.match(r'mem\([\'"](.+?)[\'"]\)\s*(==|!=|>=|<=|>|<|includes)\s*[\'"]?(.+?)[\'"]?$', assertion)
        if match:
            key, op, expected = match.groups()
            actual = self._get_memory(key)
            print(f"DEBUG: DSL mem check: key='{key}', op='{op}', expected='{expected}', actual='{actual}' (type: {type(actual)})")
            # ...
            # Convert expected string to boolean if applicable
            if isinstance(actual, bool) and isinstance(expected, str):
                if expected.lower() == 'true': expected = True
                elif expected.lower() == 'false': expected = False
            
            if op == '==':
                # Try loose equality for numbers
                try:
                    if float(actual) == float(expected):
                        return True
                except (ValueError, TypeError):
                    pass
                return str(actual) == str(expected)
            elif op == '!=':
                return str(actual) != expected
            elif op == 'includes':
                return expected in str(actual)
            elif op == '>=':
                return float(actual) >= float(expected)
            elif op == '<=':
                return float(actual) <= float(expected)
            elif op == '>':
                return float(actual) > float(expected)
            elif op == '<':
                return float(actual) < float(expected)

        # mem("<key>") != ""
        match = re.match(r'mem\([\'"](.+?)[\'"]\)\s*!=\s*[\'"][\'"]', assertion)
        if match:
            key = match.group(1)
            actual = self._get_memory(key)
            return actual is not None and str(actual) != ""

        # mem("<key>").includes("<value>")
        match = re.match(r'mem\([\'"](.+?)[\'"]\)\.includes\([\'"](.+?)[\'"]\)', assertion)
        if match:
            key, expected = match.groups()
            actual = self._get_memory(key)
            print(f"DEBUG: AssertionDSL mem includes check: key='{key}', expected='{expected}', actual='{actual}'")
            return expected in str(actual)

        # json("<channel>", "<path>") == <value>
        match = re.match(r'json\([\'"](.+?)[\'"]\s*,\s*[\'"](.+?)[\'"]\)\s*(==|!=|>=|<=|>|<|includes)\s*[\'"]?(.+?)[\'"]?$', assertion)
        if match:
            channel, path, op, expected = match.groups()
            try:
                actual = self.env_api_fn(channel, path)
                print(f"DEBUG: AssertionDSL json check: channel='{channel}', path='{path}', op='{op}', expected='{expected}', actual='{actual}'")
                # Try to parse expected as JSON
                try:
                    expected_val = json.loads(expected.replace("'", '"'))
                except:
                    expected_val = expected

                if op == '==':
                    return actual == expected_val
                elif op == '!=':
                    return actual != expected_val
                elif op == 'includes':
                    return expected_val in actual # Assuming actual is a list or string.
                elif op in ('>=','<=','>','<'):
                    try:
                        a_val = float(actual)
                        b_val = float(expected_val)
                    except (TypeError, ValueError):
                        a_val = str(actual)
                        b_val = str(expected_val)
                    if op == '>=':
                        return a_val >= b_val
                    if op == '<=':
                        return a_val <= b_val
                    if op == '>':
                        return a_val > b_val
                    if op == '<':
                        return a_val < b_val
            except:
                return False

        raise ValueError(f"Unknown assertion format: {assertion}")

    def _eval_all(self, assertion: str) -> bool:
        """Evaluate ALL[...] combinator"""
        # Extract content between ALL[ and ]
        content = assertion[4:-1].strip()
        sub_assertions = self._split_assertions(content)

        for sub in sub_assertions:
            if not self.evaluate(sub):
                print(f"DEBUG: ALL check failed on: {sub}")
                return False
        return True

    def _eval_any(self, assertion: str) -> bool:
        """Evaluate ANY[...] combinator"""
        content = assertion[4:-1].strip()
        sub_assertions = self._split_assertions(content)

        for sub in sub_assertions:
            if self.evaluate(sub):
                return True
        return False

    def _eval_not(self, assertion: str) -> bool:
        """Evaluate NOT[...] combinator"""
        content = assertion[4:-1].strip()
        return not self.evaluate(content)

    def _eval_within(self, assertion: str) -> bool:
        """Evaluate WITHIN(seconds, Expr) - must satisfy within time limit"""
        match = re.match(r'WITHIN\((\d+),\s*(.+)\)', assertion, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid WITHIN syntax: {assertion}")

        seconds = int(match.group(1))
        expr = match.group(2).strip()

        start_time = time.time()
        while time.time() - start_time < seconds:
            try:
                if self.evaluate(expr):
                    return True
            except:
                pass
            time.sleep(0.5)

        return False

    def _eval_eventually(self, assertion: str) -> bool:
        """Evaluate EVENTUALLY(Expr) - must eventually be true (max 30s)"""
        content = assertion[11:-1].strip()  # Remove "EVENTUALLY(" and ")"
        return self._eval_within(f"WITHIN(30, {content})")

    def _eval_stable(self, assertion: str) -> bool:
        """Evaluate STABLE(seconds, Expr) - must remain true for N seconds"""
        match = re.match(r'STABLE\((\d+),\s*(.+)\)', assertion, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid STABLE syntax: {assertion}")

        seconds = int(match.group(1))
        expr = match.group(2).strip()

        start_time = time.time()
        while time.time() - start_time < seconds:
            try:
                if not self.evaluate(expr):
                    return False
            except:
                return False
            time.sleep(0.5)

        return True

    def _split_assertions(self, content: str) -> list:
        """Split comma-separated assertions, respecting nested brackets"""
        assertions = []
        current = ""
        depth = 0

        for char in content:
            if char in ['[', '(']:
                depth += 1
            elif char in [']', ')']:
                depth -= 1
            elif char == ',' and depth == 0:
                if current.strip():
                    assertions.append(current.strip())
                current = ""
                continue

            current += char

        if current.strip():
            assertions.append(current.strip())

        return assertions

    def _get_memory(self, key: str) -> Any:
        """Get value from memory with dot notation support"""
        # Direct match
        if key in self.memory:
            entry = self.memory[key]
            if isinstance(entry, dict) and 'value' in entry:
                return entry['value']
            return entry

        # Traversal
        parts = key.split('.')
        current = self.memory
        
        for i, part in enumerate(parts):
            # Handle array access like orders[0]
            if '[' in part and ']' in part:
                try:
                    base = part[:part.index('[')]
                    index = int(part[part.index('[')+1:part.index(']')])
                    
                    # Access base
                    if isinstance(current, dict):
                        current = current.get(base)
                    else:
                        return None
                        
                    # Access index
                    if isinstance(current, list) and len(current) > index:
                        current = current[index]
                    else:
                        return None
                except (ValueError, IndexError):
                    return None
            else:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
        
        # Handle wrapped value if applicable
        if isinstance(current, dict) and 'value' in current and len(current) == 1:
             return current['value']
             
        return current


# Example usage
if __name__ == "__main__":
    # Mock objects for testing
    class MockPage:
        def __init__(self):
            self.url = "https://shop.local/order/confirmation/O-10001"

        def locator(self, selector):
            return MockLocator(selector)

    class MockLocator:
        def __init__(self, selector):
            self.selector = selector

        def count(self):
            if self.selector == "#order-id":
                return 1
            return 0

        def inner_text(self):
            if self.selector == "#order-id":
                return "O-10001"
            elif self.selector == "#order-status":
                return "confirmed"
            return ""

    # Mock memory
    memory = {
        "orders.last.id": {"value": "O-10001", "source": "B1-2025-001"}
    }

    # Mock env API
    def mock_env_api(channel, path):
        if channel == "env" and path == "orders.O-10001.state":
            return "confirmed"
        return None

    # Test
    page = MockPage()
    dsl = AssertionDSL(page, memory, mock_env_api)

    # Test atoms
    print("Test 1 (exists):", dsl.evaluate('exists("#order-id")'))  # True
    print("Test 2 (text ==):", dsl.evaluate('text("#order-status") == "confirmed"'))  # True
    print("Test 3 (url):", dsl.evaluate('url().includes("/order/confirmation")'))  # True
    print("Test 4 (mem):", dsl.evaluate("mem('orders.last.id') == 'O-10001'"))  # True
    print("Test 5 (json):", dsl.evaluate("json('env','orders.O-10001.state') == 'confirmed'"))  # True

    # Test combinators
    complex_assertion = """ALL[
        url().includes("/order/confirmation"),
        text("#order-id") != "",
        text("#order-status") == "confirmed",
        json('env','orders.O-10001.state') == 'confirmed',
        mem('orders.last.id') == 'O-10001'
    ]"""
    print("Test 6 (ALL):", dsl.evaluate(complex_assertion))  # True
