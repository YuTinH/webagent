-- Web Agent Lifelong Learning Dataset - Database Schema
-- Version: 1.0
-- Purpose: MVP implementation for 3 sites (shop, bank, gov) × 10 tasks

-- ============================================================================
-- Users & Authentication
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  email TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);

-- ============================================================================
-- E-commerce (shop.local)
-- ============================================================================

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  price REAL NOT NULL CHECK(price >= 0),
  category TEXT,
  stock INTEGER DEFAULT 0 CHECK(stock >= 0),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_category ON products(category);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,  -- e.g., "O-10001"
  user_id INTEGER NOT NULL,
  total REAL NOT NULL CHECK(total >= 0),
  state TEXT NOT NULL DEFAULT 'pending',  -- pending, confirmed, shipped, delivered, cancelled
  shipping_speed TEXT,  -- standard, express, same_day
  shipping_address TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_state ON orders(state);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL,
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  price REAL NOT NULL CHECK(price >= 0),
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE RESTRICT
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);

CREATE TABLE IF NOT EXISTS returns (
  id TEXT PRIMARY KEY,  -- e.g., "R-50001"
  order_id TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  reason TEXT,  -- defective, wrong_item, changed_mind, etc.
  state TEXT NOT NULL DEFAULT 'submitted',  -- submitted, approved, rejected, refunded
  refund_amount REAL CHECK(refund_amount >= 0),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_returns_order_id ON returns(order_id);
CREATE INDEX idx_returns_state ON returns(state);

-- ============================================================================
-- Banking (bank.local)
-- ============================================================================

CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- checking, savings, credit
  balance REAL NOT NULL DEFAULT 0.0,
  currency TEXT DEFAULT 'USD',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_accounts_user_id ON accounts(user_id);

CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  last4 TEXT NOT NULL,
  type TEXT NOT NULL,  -- physical, virtual
  state TEXT NOT NULL DEFAULT 'active',  -- active, blocked, expired, cancelled
  exp_date TEXT,  -- MM/YYYY
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  blocked_at DATETIME,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_cards_user_id ON cards(user_id);
CREATE INDEX idx_cards_last4 ON cards(last4);
CREATE INDEX idx_cards_state ON cards(state);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  type TEXT NOT NULL,  -- debit, credit
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE INDEX idx_transactions_account_id ON transactions(account_id);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

CREATE TABLE IF NOT EXISTS autopay (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  payee TEXT NOT NULL,  -- utilities, landlord, etc.
  account_id INTEGER NOT NULL,
  amount REAL,  -- NULL for variable amounts
  frequency TEXT NOT NULL,  -- monthly, weekly, biweekly
  next_date DATE NOT NULL,
  state TEXT NOT NULL DEFAULT 'active',  -- active, paused, cancelled
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE INDEX idx_autopay_user_id ON autopay(user_id);
CREATE INDEX idx_autopay_state ON autopay(state);

-- ============================================================================
-- Government Services (gov.local)
-- ============================================================================

CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY,  -- e.g., "APP-7788"
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- parking_permit, residence_permit, business_license, etc.
  state TEXT NOT NULL DEFAULT 'submitted',  -- submitted, processing, approved, rejected
  data TEXT,  -- JSON blob for application-specific data
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_type ON applications(type);
CREATE INDEX idx_applications_state ON applications(state);

CREATE TABLE IF NOT EXISTS appointments (
  id TEXT PRIMARY KEY,  -- e.g., "APT-9988"
  application_id TEXT,
  user_id INTEGER NOT NULL,
  date DATE NOT NULL,
  time TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'booked',  -- booked, completed, cancelled, no_show
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_appointments_user_id ON appointments(user_id);
CREATE INDEX idx_appointments_date ON appointments(date);
CREATE INDEX idx_appointments_state ON appointments(state);

CREATE TABLE IF NOT EXISTS permits (
  id TEXT PRIMARY KEY,  -- e.g., "RP-2024-77"
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- residence, work, parking, etc.
  application_id TEXT,
  issue_date DATE,
  expiry_date DATE,
  state TEXT NOT NULL DEFAULT 'pending',  -- pending, active, expired, revoked
  renewal_eligible BOOLEAN DEFAULT 0,
  next_appointment TEXT,  -- ISO datetime
  documents_uploaded TEXT,  -- JSON array of document names
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE SET NULL
);

CREATE INDEX idx_permits_user_id ON permits(user_id);
CREATE INDEX idx_permits_type ON permits(type);
CREATE INDEX idx_permits_state ON permits(state);

-- ============================================================================
-- Utilities (shared across sites)
-- ============================================================================

CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- electricity, water, gas, internet
  amount REAL NOT NULL CHECK(amount >= 0),
  due_date DATE NOT NULL,
  state TEXT NOT NULL DEFAULT 'unpaid',  -- unpaid, paid, overdue
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  paid_at DATETIME,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_bills_user_id ON bills(user_id);
CREATE INDEX idx_bills_due_date ON bills(due_date);
CREATE INDEX idx_bills_state ON bills(state);

-- ============================================================================
-- Merchant Bindings (cross-site payment methods)
-- ============================================================================

CREATE TABLE IF NOT EXISTS merchant_bindings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  merchant TEXT NOT NULL,  -- shop_local, util_local, food_local, etc.
  card_last4 TEXT NOT NULL,
  binding_type TEXT DEFAULT 'default',  -- default, autopay, subscription
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_merchant_bindings_user_id ON merchant_bindings(user_id);
CREATE INDEX idx_merchant_bindings_merchant ON merchant_bindings(merchant);
CREATE INDEX idx_merchant_bindings_card_last4 ON merchant_bindings(card_last4);

-- ============================================================================
-- Memory KV Store (long-term agent memory)
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,  -- JSON serialized
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  source TEXT,  -- task_id or 'system'
  confidence REAL DEFAULT 1.0 CHECK(confidence >= 0 AND confidence <= 1)
);

CREATE INDEX idx_memory_kv_source ON memory_kv(source);

-- ============================================================================
-- Task Execution Logs
-- ============================================================================

CREATE TABLE IF NOT EXISTS task_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  agent_version TEXT,
  state TEXT NOT NULL,  -- running, completed, failed, aborted
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  error_type TEXT,
  error_message TEXT,
  steps_completed INTEGER DEFAULT 0,
  steps_total INTEGER
);

CREATE INDEX idx_task_executions_task_id ON task_executions(task_id);
CREATE INDEX idx_task_executions_state ON task_executions(state);

-- ============================================================================
-- Settlements (for expense splitting)
-- ============================================================================

CREATE TABLE IF NOT EXISTS settlements (
  id TEXT PRIMARY KEY,  -- e.g., "SETTLE-2025-10"
  user_id INTEGER NOT NULL,
  period TEXT NOT NULL,  -- "2025-10"
  members TEXT NOT NULL,  -- JSON array of member names
  total_amount REAL NOT NULL CHECK(total_amount >= 0),
  state TEXT NOT NULL DEFAULT 'pending',  -- pending, sent, settled
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_settlements_user_id ON settlements(user_id);
CREATE INDEX idx_settlements_period ON settlements(period);
CREATE INDEX idx_settlements_state ON settlements(state);

-- ============================================================================
-- Triggers for automatic timestamp updates
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS update_orders_timestamp
AFTER UPDATE ON orders
BEGIN
  UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_returns_timestamp
AFTER UPDATE ON returns
BEGIN
  UPDATE returns SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_applications_timestamp
AFTER UPDATE ON applications
BEGIN
  UPDATE applications SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_settlements_timestamp
AFTER UPDATE ON settlements
BEGIN
  UPDATE settlements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
