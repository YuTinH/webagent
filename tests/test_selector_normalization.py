import unittest

from agent.browser_env import _normalize_selector_syntax, _selector_fallback_variants
from llm_runner import _repair_common_selector_patterns


class SelectorNormalizationTests(unittest.TestCase):
    def test_repair_contains_uses_has_text(self):
        selector = '#records-list .record-card h3:contains("Prescription - RX-2217")'
        repaired = _repair_common_selector_patterns(selector)
        self.assertEqual(
            repaired,
            '#records-list .record-card h3:has-text("Prescription - RX-2217")',
        )

    def test_repair_bare_onclick_exact_match_to_substring_match(self):
        selector = '.btn[type="button"][onclick="refillPrescription"]'
        repaired = _repair_common_selector_patterns(selector)
        self.assertEqual(
            repaired,
            '.btn[type="button"][onclick*="refillPrescription"]',
        )

    def test_repair_keeps_real_onclick_call_selector_stable(self):
        selector = 'button[onclick="openApplyCardModal()"]'
        repaired = _repair_common_selector_patterns(selector)
        self.assertEqual(repaired, selector)

    def test_browser_env_normalizes_bare_onclick_exact_match(self):
        selector = '.btn[type="button"][onclick="refillPrescription"]'
        normalized = _normalize_selector_syntax(selector)
        self.assertEqual(
            normalized,
            '.btn[type="button"][onclick*="refillPrescription"]',
        )

    def test_browser_env_builds_onclick_fallback_variants(self):
        selector = '.btn[type="button"][onclick="refillPrescription"]'
        variants = _selector_fallback_variants(selector)
        self.assertEqual(
            variants,
            [
                '.btn[type="button"][onclick*="refillPrescription"]',
                '[onclick*="refillPrescription"]',
                'button[onclick*="refillPrescription"]',
                'a[onclick*="refillPrescription"]',
            ],
        )

    def test_dotted_onclick_expression_is_repaired_to_substring_match(self):
        selector = 'button[onclick="window.location.href"]'
        repaired = _repair_common_selector_patterns(selector)
        normalized = _normalize_selector_syntax(selector)
        self.assertEqual(repaired, 'button[onclick*="window.location.href"]')
        self.assertEqual(normalized, 'button[onclick*="window.location.href"]')


if __name__ == "__main__":
    unittest.main()
