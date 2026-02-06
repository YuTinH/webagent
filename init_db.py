import sqlite3
import time

def init_db():
    max_retries = 10
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect('data.db', timeout=30)
            c = conn.cursor()

            # Define schema
            schema = {
                'memory_kv': '''CREATE TABLE IF NOT EXISTS memory_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    ts TEXT,
                    source TEXT,
                    confidence REAL
                )''',
                'task_executions': '''CREATE TABLE IF NOT EXISTS task_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    agent_version TEXT,
                    state TEXT,
                    steps_total INTEGER,
                    steps_completed INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    started_at TEXT
                )''',
                'products': '''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    name TEXT,
                    price REAL,
                    category TEXT,
                    stock INTEGER,
                    description TEXT,
                    original_price REAL
                )''',
                'orders': '''CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    total REAL,
                    state TEXT,
                    shipping_speed TEXT,
                    shipping_address TEXT,
                    created_at TEXT
                )''',
                'order_items': '''CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    sku TEXT,
                    quantity INTEGER,
                    price REAL
                )''',
                'users': '''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    email TEXT,
                    created_at TEXT
                )''',
                'accounts': '''CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    balance REAL,
                    currency TEXT
                )''',
                'returns': '''CREATE TABLE IF NOT EXISTS returns (
                    id TEXT PRIMARY KEY,
                    order_id TEXT,
                    user_id INTEGER,
                    reason TEXT,
                    state TEXT,
                    refund_amount REAL,
                    created_at TEXT
                )''',
                'permits': '''CREATE TABLE IF NOT EXISTS permits (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    type TEXT,
                    status TEXT,
                    expiry_date TEXT,
                    created_at TEXT
                )''',
                'applications': '''CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    type TEXT,
                    status TEXT,
                    details TEXT,
                    created_at TEXT
                )'''
            }

            # Create tables if not exist and clear data
            for table, create_sql in schema.items():
                c.execute(create_sql)
                try:
                    c.execute(f"DELETE FROM {table}")
                except:
                    pass

            # Seed initial data
            products = [
                ('WM-5521', 'Logitech M185 Wireless Mouse', 24.99, 'electronics', 100, 'Wireless mouse', 29.99),
                ('KB-8801', 'Mechanical Keyboard RGB', 89.99, 'electronics', 50, 'RGB Keyboard', 99.99)
            ]
            c.executemany("INSERT INTO products (sku, name, price, category, stock, description, original_price) VALUES (?,?,?,?,?,?,?)", products)
            
            c.execute("INSERT INTO users (id, username, email) VALUES (1, 'demo', 'demo@example.com')")

            conn.commit()
            conn.close()
            print("Database initialized.")
            return # Success

        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                print(f"Database locked, retrying ({attempt+1}/{max_retries})...")
                time.sleep(2)
            else:
                raise e
    
    raise Exception("Could not acquire database lock after multiple retries")

if __name__ == '__main__':
    init_db()
