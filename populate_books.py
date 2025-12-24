
import sqlite3
import os

DB_PATH = "webagent_dynamic_suite_v2_skin/data.db"

def populate_books():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    if not cursor.fetchone():
        print("Creating products table...")
        cursor.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                sku TEXT UNIQUE,
                name TEXT,
                price REAL,
                original_price REAL,
                category TEXT,
                stock INTEGER,
                description TEXT,
                image_url TEXT
            )
        """)

    books = [
        ("BK-101", "Deep Learning Basics", 59.99, 79.99, "books", 50),
        ("BK-102", "Python for Data Science", 45.00, 45.00, "books", 100),
        ("BK-103", "Web Agent Programming", 89.99, 99.99, "books", 20)
    ]

    for book in books:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO products (sku, name, price, original_price, category, stock)
                VALUES (?, ?, ?, ?, ?, ?)
            """, book)
        except Exception as e:
            print(f"Error inserting {book[0]}: {e}")

    conn.commit()
    conn.close()
    print("Books populated.")

if __name__ == "__main__":
    populate_books()
