import sqlite3

def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()

    # Memory KV
    c.execute('''CREATE TABLE IF NOT EXISTS memory_kv (
        key TEXT PRIMARY KEY,
        value TEXT,
        ts TEXT,
        source TEXT,
        confidence REAL
    )''')

    # Task Executions
    c.execute('''CREATE TABLE IF NOT EXISTS task_executions (
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
    )''')

    # Products (needed for shop)
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        name TEXT,
        price REAL,
        category TEXT,
        stock INTEGER,
        description TEXT,
        original_price REAL
    )''')
    
    # Check if products need seeding
    c.execute("SELECT count(*) FROM products")
    if c.fetchone()[0] == 0:
        products = [
            ('WM-5521', 'Logitech M185 Wireless Mouse', 24.99, 'electronics', 100, 'Wireless mouse', 29.99),
            ('KB-8801', 'Mechanical Keyboard RGB', 89.99, 'electronics', 50, 'RGB Keyboard', 99.99)
        ]
        c.executemany("INSERT INTO products (sku, name, price, category, stock, description, original_price) VALUES (?,?,?,?,?,?,?)", products)

    # Orders (needed for shop API)
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        total REAL,
        state TEXT,
        shipping_speed TEXT,
        shipping_address TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        sku TEXT,
        quantity INTEGER,
        price REAL
    )''')

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT,
        created_at TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO users (id, username, email) VALUES (1, 'demo', 'demo@example.com')")

    # Accounts
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        balance REAL,
        currency TEXT
    )''')
    
    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == '__main__':
    init_db()
