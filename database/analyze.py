#!/usr/bin/env python3
"""
SQLite to Pandas - Data Analysis Helper
"""

import sqlite3
import pandas as pd


def analyze_database(db_path="data.db"):
    """Analyze database with pandas"""
    conn = sqlite3.connect(db_path)

    # Load tables
    print("📊 Loading data...\n")

    # Orders analysis
    orders = pd.read_sql_query("SELECT * FROM orders", conn)
    print("=" * 80)
    print("📦 ORDERS ANALYSIS")
    print("=" * 80)
    print(f"\nTotal orders: {len(orders)}")
    print(f"Total revenue: ${orders['total'].sum():.2f}")
    print(f"\nOrders by state:")
    print(orders['state'].value_counts())
    print(f"\nOrders by shipping speed:")
    print(orders['shipping_speed'].value_counts())

    # Products analysis
    products = pd.read_sql_query("SELECT * FROM products", conn)
    print("\n" + "=" * 80)
    print("🛍️  PRODUCTS ANALYSIS")
    print("=" * 80)
    print(f"\nTotal products: {len(products)}")
    print(f"\nProducts by category:")
    print(products['category'].value_counts())
    print(f"\nPrice statistics:")
    print(products['price'].describe())
    print(f"\nTop 5 most expensive products:")
    print(products.nlargest(5, 'price')[['name', 'price', 'category']])

    # Accounts analysis
    accounts = pd.read_sql_query("SELECT * FROM accounts", conn)
    print("\n" + "=" * 80)
    print("💰 ACCOUNTS ANALYSIS")
    print("=" * 80)
    print(f"\nTotal accounts: {len(accounts)}")
    print(f"\nTotal balance across all accounts: ${accounts['balance'].sum():.2f}")
    print(f"\nBalance by account type:")
    print(accounts.groupby('type')['balance'].sum())

    # Memory analysis
    memory = pd.read_sql_query("SELECT * FROM memory_kv", conn)
    print("\n" + "=" * 80)
    print("🧠 MEMORY KV ANALYSIS")
    print("=" * 80)
    print(f"\nTotal memory entries: {len(memory)}")
    print(f"\nMemory entries by source:")
    print(memory['source'].value_counts())
    print(f"\nAll memory keys:")
    for _, row in memory.iterrows():
        print(f"  {row['key']:<30} = {row['value']:<30} (from {row['source']})")

    conn.close()


if __name__ == "__main__":
    analyze_database()
