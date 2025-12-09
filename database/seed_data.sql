-- Sample data for testing and visualization
-- Run with: sqlite3 data.db < database/seed_data.sql

-- Users
INSERT INTO users (username, password_hash, email) VALUES
  ('testuser', 'hash123', 'test@example.com'),
  ('alice', 'hash456', 'alice@example.com'),
  ('bob', 'hash789', 'bob@example.com');

-- Products
INSERT INTO products (sku, name, price, category, stock) VALUES
  ('WM-5521', 'Logitech M185 Wireless Mouse', 24.99, 'electronics', 50),
  ('KB-8801', 'Mechanical Keyboard RGB', 89.99, 'electronics', 30),
  ('HD-3322', 'USB-C Hub 7-in-1', 35.50, 'electronics', 100),
  ('CH-6677', 'Ergonomic Office Chair', 199.99, 'furniture', 15),
  ('DK-9900', 'Standing Desk Adjustable', 299.00, 'furniture', 10);

-- Orders
INSERT INTO orders (id, user_id, total, state, shipping_speed, shipping_address) VALUES
  ('O-10001', 1, 30.98, 'confirmed', 'same_day', '123 Main St, Apt 5B'),
  ('O-10002', 1, 89.99, 'shipped', 'express', '123 Main St, Apt 5B'),
  ('O-10003', 2, 35.50, 'delivered', 'standard', '456 Oak Ave');

-- Order items
INSERT INTO order_items (order_id, sku, quantity, price) VALUES
  ('O-10001', 'WM-5521', 1, 24.99),
  ('O-10002', 'KB-8801', 1, 89.99),
  ('O-10003', 'HD-3322', 1, 35.50);

-- Accounts
INSERT INTO accounts (user_id, type, balance, currency) VALUES
  (1, 'checking', 1523.45, 'USD'),
  (1, 'savings', 5000.00, 'USD'),
  (2, 'checking', 3200.00, 'USD');

-- Cards
INSERT INTO cards (user_id, last4, type, state, exp_date) VALUES
  (1, '1234', 'physical', 'active', '12/2025'),
  (1, '7777', 'physical', 'active', '12/2029'),
  (2, '5678', 'physical', 'active', '06/2026');

-- Transactions
INSERT INTO transactions (account_id, amount, type, description) VALUES
  (1, -30.98, 'debit', 'Order O-10001 - Logitech Mouse'),
  (1, -89.99, 'debit', 'Order O-10002 - Keyboard'),
  (1, 1500.00, 'credit', 'Salary Deposit');

-- Bills
INSERT INTO bills (user_id, type, amount, due_date, state) VALUES
  (1, 'electricity', 85.50, '2025-12-01', 'unpaid'),
  (1, 'water', 45.00, '2025-12-01', 'unpaid'),
  (2, 'electricity', 92.00, '2025-11-25', 'paid');

-- Merchant Bindings
INSERT INTO merchant_bindings (user_id, merchant, card_last4, binding_type) VALUES
  (1, 'shop_local', '1234', 'default'),
  (1, 'util_local', '1234', 'autopay'),
  (2, 'shop_local', '5678', 'default');

-- Memory KV
INSERT INTO memory_kv (key, value, source, confidence) VALUES
  ('address.primary', '"123 Main St, Apt 5B"', 'system', 1.0),
  ('orders.last.id', '"O-10001"', 'B1-2025-001', 1.0),
  ('orders.last.total', '30.98', 'B1-2025-001', 1.0),
  ('payment.cards[0].last4', '"1234"', 'system', 1.0);

-- Applications
INSERT INTO applications (id, user_id, type, state, data) VALUES
  ('APP-7788', 1, 'parking_permit', 'submitted', '{"vehicle_plate": "ABC123"}'),
  ('APP-7789', 2, 'parking_permit', 'approved', '{"vehicle_plate": "XYZ789"}');

-- Permits
INSERT INTO permits (id, user_id, type, application_id, issue_date, expiry_date, state, renewal_eligible) VALUES
  ('RP-2024-77', 1, 'residence', NULL, '2024-01-15', '2025-01-15', 'active', 1),
  ('PP-2025-01', 2, 'parking', 'APP-7789', '2025-01-01', '2026-01-01', 'active', 0);

VACUUM;
