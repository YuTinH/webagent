#!/usr/bin/env python3
"""
SQLite Database Viewer
Quick visualization tool for the web agent database
"""

import sqlite3
import sys
from typing import List, Tuple


def connect_db(db_path: str = "data.db") -> sqlite3.Connection:
    """Connect to SQLite database"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to {db_path}: {e}")
        sys.exit(1)


def get_all_tables(conn: sqlite3.Connection) -> List[str]:
    """Get list of all tables"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(conn: sqlite3.Connection, table_name: str) -> List[Tuple]:
    """Get schema for a table"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_table_count(conn: sqlite3.Connection, table_name: str) -> int:
    """Get row count for a table"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def print_table_info(conn: sqlite3.Connection, table_name: str):
    """Print detailed info about a table"""
    print(f"\n{'='*80}")
    print(f"📋 Table: {table_name}")
    print(f"{'='*80}")

    # Schema
    schema = get_table_schema(conn, table_name)
    print("\n🔧 Schema:")
    print(f"{'Column':<20} {'Type':<15} {'Not Null':<10} {'Default':<15} {'PK'}")
    print("-" * 80)
    for col in schema:
        cid, name, type_, notnull, default_val, pk = col
        print(f"{name:<20} {type_:<15} {bool(notnull):<10} {str(default_val or ''):<15} {bool(pk)}")

    # Row count
    count = get_table_count(conn, table_name)
    print(f"\n📊 Row count: {count}")

    # Sample data
    if count > 0:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()

        print(f"\n📄 Sample data (first 5 rows):")
        if rows:
            # Print column names
            columns = [description[0] for description in cursor.description]
            col_widths = [max(15, len(col)) for col in columns]

            # Header
            header = " | ".join(f"{col:<{w}}" for col, w in zip(columns, col_widths))
            print(header)
            print("-" * len(header))

            # Rows
            for row in rows:
                row_str = " | ".join(
                    f"{str(val)[:w]:<{w}}" if val is not None else f"{'NULL':<{w}}"
                    for val, w in zip(row, col_widths)
                )
                print(row_str)
    else:
        print("  (empty table)")


def print_database_summary(conn: sqlite3.Connection):
    """Print summary of entire database"""
    print("\n" + "="*80)
    print("🗄️  DATABASE SUMMARY")
    print("="*80)

    tables = get_all_tables(conn)
    print(f"\n📚 Total tables: {len(tables)}\n")

    print(f"{'Table Name':<30} {'Row Count':<15} {'Columns'}")
    print("-" * 80)

    for table in tables:
        count = get_table_count(conn, table)
        schema = get_table_schema(conn, table)
        col_count = len(schema)
        print(f"{table:<30} {count:<15} {col_count}")


def interactive_mode(conn: sqlite3.Connection):
    """Interactive exploration mode"""
    tables = get_all_tables(conn)

    while True:
        print("\n" + "="*80)
        print("🔍 INTERACTIVE MODE")
        print("="*80)
        print("\nAvailable tables:")
        for i, table in enumerate(tables, 1):
            count = get_table_count(conn, table)
            print(f"  {i}. {table:<30} ({count} rows)")

        print("\nCommands:")
        print("  [1-N]  : Show table details")
        print("  'q'    : Query mode")
        print("  's'    : Show summary")
        print("  'exit' : Exit")

        choice = input("\n> ").strip().lower()

        if choice == 'exit':
            break
        elif choice == 's':
            print_database_summary(conn)
        elif choice == 'q':
            query_mode(conn)
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(tables):
                print_table_info(conn, tables[idx])
            else:
                print("❌ Invalid table number")
        else:
            print("❌ Invalid command")


def query_mode(conn: sqlite3.Connection):
    """Execute custom SQL queries"""
    print("\n" + "="*80)
    print("💻 QUERY MODE (type 'back' to return)")
    print("="*80)

    while True:
        query = input("\nSQL> ").strip()

        if query.lower() == 'back':
            break

        if not query:
            continue

        try:
            cursor = conn.cursor()
            cursor.execute(query)

            if query.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    print("\n" + " | ".join(columns))
                    print("-" * 80)
                    for row in rows:
                        print(" | ".join(str(val) if val is not None else "NULL" for val in row))
                    print(f"\n✅ {len(rows)} rows returned")
                else:
                    print("✅ No rows returned")
            else:
                conn.commit()
                print(f"✅ Query executed successfully (affected rows: {cursor.rowcount})")

        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SQLite Database Viewer")
    parser.add_argument("--db", default="data.db", help="Database file path")
    parser.add_argument("--table", help="Show specific table")
    parser.add_argument("--summary", action="store_true", help="Show database summary")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    # Connect
    conn = connect_db(args.db)
    print(f"✅ Connected to {args.db}")

    # Execute based on arguments
    if args.summary:
        print_database_summary(conn)
    elif args.table:
        print_table_info(conn, args.table)
    elif args.interactive:
        interactive_mode(conn)
    else:
        # Default: show summary and enter interactive mode
        print_database_summary(conn)
        interactive_mode(conn)

    conn.close()
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
