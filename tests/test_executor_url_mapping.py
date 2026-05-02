import unittest

from agent.executor import TaskExecutor


class ExecutorUrlMappingTests(unittest.TestCase):
    def setUp(self):
        self.executor = TaskExecutor.__new__(TaskExecutor)
        self.executor.SUITE_PORT = 8017

    def test_maps_domain_style_urls(self):
        mapped = self.executor._map_url("http://shop.local/help-refund.html?clean=true")
        self.assertEqual(
            mapped,
            "http://localhost:8017/shop.local/help-refund.html?clean=true",
        )

    def test_maps_legacy_localhost_suite_urls(self):
        mapped = self.executor._map_url("http://localhost:8014/shop.local/help-refund.html?clean=true")
        self.assertEqual(
            mapped,
            "http://localhost:8017/shop.local/help-refund.html?clean=true",
        )

    def test_maps_legacy_loopback_suite_urls(self):
        mapped = self.executor._map_url("http://127.0.0.1:8014/shop.local/help-refund.html?clean=true")
        self.assertEqual(
            mapped,
            "http://localhost:8017/shop.local/help-refund.html?clean=true",
        )

    def test_leaves_external_urls_unchanged(self):
        mapped = self.executor._map_url("https://example.com/help-refund.html")
        self.assertEqual(mapped, "https://example.com/help-refund.html")


if __name__ == "__main__":
    unittest.main()
