# Database Visualization Guide

## 🎯 Quick Start

### 1. View Database Summary (快速预览)
```bash
python database/viewer.py --summary
```

### 2. View Specific Table (查看特定表)
```bash
python database/viewer.py --table orders
python database/viewer.py --table products
python database/viewer.py --table memory_kv
```

### 3. Interactive Mode (交互模式 - 推荐)
```bash
python database/viewer.py -i
```

在交互模式中：
- 输入数字 `1-18` 查看对应表
- 输入 `q` 进入 SQL 查询模式
- 输入 `s` 显示数据库摘要
- 输入 `exit` 退出

---

## 📊 Available Tools (可用工具)

### Tool 1: Python Viewer Script ✅ (Already Created)

**Location**: `database/viewer.py`

**Features**:
- ✅ Database summary with row counts
- ✅ Table schema viewer
- ✅ Sample data display
- ✅ Interactive exploration
- ✅ Custom SQL queries

**Examples**:
```bash
# Summary
python database/viewer.py --summary

# Specific table
python database/viewer.py --table users

# Interactive
python database/viewer.py -i
```

---

### Tool 2: SQLite Command Line

**Start**:
```bash
sqlite3 data.db
```

**Useful Commands**:
```sql
-- List all tables
.tables

-- Show table schema
.schema orders

-- Pretty output
.mode column
.headers on

-- Query data
SELECT * FROM orders;
SELECT * FROM products WHERE category = 'electronics';
SELECT u.username, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id;

-- Export to CSV
.mode csv
.output orders.csv
SELECT * FROM orders;
.output stdout

-- Exit
.quit
```

---

### Tool 3: DB Browser for SQLite (GUI - Recommended)

**Install**:
```bash
# Ubuntu/Debian
sudo apt install sqlitebrowser

# macOS
brew install --cask db-browser-for-sqlite

# Windows
# Download from: https://sqlitebrowser.org/dl/
```

**Open**:
```bash
sqlitebrowser data.db
```

**Features**:
- ✅ Visual table browser
- ✅ ER diagram (relationship visualization)
- ✅ SQL editor with syntax highlighting
- ✅ Edit data inline
- ✅ Import/Export (CSV, JSON, SQL)
- ✅ Database structure modification

---

### Tool 4: DBeaver (Universal Database Tool)

**Install**:
```bash
# Download from: https://dbeaver.io/download/
```

**Features**:
- ✅ Supports multiple databases
- ✅ Advanced SQL editor
- ✅ Data visualization charts
- ✅ ER diagrams
- ✅ Query history

---

### Tool 5: Online Viewers (No Installation)

**1. SQLite Viewer Online**
- URL: https://inloop.github.io/sqlite-viewer/
- Drag & drop `data.db` to view

**2. SQLite Online**
- URL: https://sqliteonline.com/
- Upload database or paste SQL

---

## 🔍 Common Queries

### Check Task Execution Status
```sql
SELECT task_id, state, steps_completed, error_message
FROM task_executions
ORDER BY started_at DESC;
```

### View User Orders
```sql
SELECT u.username, o.id, o.total, o.state, o.created_at
FROM users u
JOIN orders o ON u.id = o.user_id
ORDER BY o.created_at DESC;
```

### Check Memory Entries
```sql
SELECT key, value, source, confidence
FROM memory_kv
ORDER BY ts DESC;
```

### Product Inventory
```sql
SELECT name, price, stock, category
FROM products
WHERE stock > 0
ORDER BY price DESC;
```

### Merchant Bindings by User
```sql
SELECT u.username, mb.merchant, mb.card_last4, mb.binding_type
FROM users u
JOIN merchant_bindings mb ON u.id = mb.user_id;
```

---

## 📁 Database Files

- `database/schema.sql` - Database schema definition
- `database/seed_data.sql` - Sample data
- `database/viewer.py` - Python visualization tool
- `database/analyze.py` - Pandas analysis (requires pandas)
- `data.db` - SQLite database file

---

## 🛠️ Maintenance Commands

### Reset Database (删除并重建)
```bash
rm data.db
sqlite3 data.db < database/schema.sql
sqlite3 data.db < database/seed_data.sql
```

### Backup Database
```bash
sqlite3 data.db .dump > backup_$(date +%Y%m%d).sql
```

### Restore from Backup
```bash
sqlite3 data_restored.db < backup_20251116.sql
```

### Check Database Integrity
```bash
sqlite3 data.db "PRAGMA integrity_check;"
```

### Vacuum (优化数据库)
```bash
sqlite3 data.db "VACUUM;"
```

---

## 📈 Database Statistics

Run this to see current stats:

```bash
python database/viewer.py --summary
```

Current tables (18 total):
- **E-commerce**: products, orders, order_items, returns
- **Banking**: accounts, cards, transactions, autopay
- **Government**: applications, appointments, permits
- **Utilities**: bills
- **Cross-cutting**: users, merchant_bindings, memory_kv, task_executions, settlements

---

## 🚀 Next Steps

1. **Explore the data**:
   ```bash
   python database/viewer.py -i
   ```

2. **Run custom queries**:
   - Use interactive mode → press 'q'
   - Or use sqlite3 directly

3. **Install GUI tool** (optional):
   ```bash
   sudo apt install sqlitebrowser
   sqlitebrowser data.db
   ```

4. **Modify schema** (if needed):
   - Edit `database/schema.sql`
   - Recreate database

---

## 💡 Tips

- Use `.mode column` and `.headers on` in sqlite3 for better formatting
- Export to CSV for Excel/Google Sheets: `.mode csv` → `.output file.csv`
- Use `EXPLAIN QUERY PLAN` to optimize slow queries
- Regular `VACUUM` keeps database compact
- Create indexes for frequently queried columns

---

## 🆘 Troubleshooting

**Problem**: Database locked
```bash
# Solution: Close all connections
fuser data.db  # Find processes using the file
```

**Problem**: Permission denied
```bash
# Solution: Check file permissions
chmod 644 data.db
```

**Problem**: Corrupted database
```bash
# Solution: Restore from backup or recreate
rm data.db
sqlite3 data.db < database/schema.sql
```
