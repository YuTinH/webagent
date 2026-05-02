import unittest

from server import merge_shop_order_map


class OrderApiMergeTests(unittest.TestCase):
    def test_last_pointer_does_not_override_real_order(self):
        order_map = {
            "O-45364": {
                "id": "O-45364",
                "state": "delivered",
                "date": "2026-04-21T19:19:05.419298",
                "total": 29.99,
                "items": [{"name": "Wireless Mouse", "quantity": 1, "price": 29.99}],
            }
        }
        env_orders = {
            "O-45364": {
                "id": "O-45364",
                "state": "delivered",
                "date": "2026-04-21T19:19:05.419298",
                "total": 29.99,
                "items": [{"name": "Wireless Mouse", "quantity": 1, "price": 29.99}],
            },
            "last": {
                "id": "O-45364",
                "state": "confirmed",
                "total": 29.99,
            },
        }

        merged = merge_shop_order_map(order_map, env_orders)

        self.assertEqual(merged["O-45364"]["state"], "delivered")
        self.assertEqual(merged["O-45364"]["date"], "2026-04-21T19:19:05.419298")

    def test_existing_db_date_is_preserved_when_env_entry_is_partial(self):
        order_map = {
            "O-70001": {
                "id": "O-70001",
                "state": "confirmed",
                "date": "2026-04-21T20:00:00",
                "shipping_speed": "standard",
                "shipping_address": "123 Main St",
                "items": [{"name": "Wireless Mouse", "quantity": 1, "price": 29.99}],
                "total": 29.99,
            }
        }
        env_orders = {
            "O-70001": {
                "id": "O-70001",
                "state": "delivered",
                "total": 29.99,
            }
        }

        merged = merge_shop_order_map(order_map, env_orders)

        self.assertEqual(merged["O-70001"]["state"], "delivered")
        self.assertEqual(merged["O-70001"]["date"], "2026-04-21T20:00:00")


if __name__ == "__main__":
    unittest.main()
