#!/bin/bash
#
# Quick Setup Script for Web Agent Lifelong Learning Dataset
#

set -e

echo "=================================="
echo "Web Agent Dataset - Quick Setup"
echo "=================================="

# Check Python version
echo ""
echo "1. Checking Python version..."
python3 --version || { echo "Error: Python 3 not found"; exit 1; }

# Install Python dependencies
echo ""
echo "2. Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo ""
echo "3. Installing Playwright browsers..."
playwright install chromium

# Setup database
echo ""
echo "4. Setting up database..."
if [ -f "data.db" ]; then
    echo "   ⚠️  data.db already exists, skipping..."
else
    echo "   Creating database..."
    sqlite3 data.db < database/schema.sql
    echo "   Loading seed data..."
    sqlite3 data.db < database/seed_data.sql
    echo "   ✅ Database created with sample data"
fi

# Create output directories
echo ""
echo "5. Creating output directories..."
mkdir -p output screenshots errors downloads

echo ""
echo "=================================="
echo "✅ Setup complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Run a test task:"
echo "     python run_task.py B1-shopping --slow 500"
echo ""
echo "  2. View database:"
echo "     python database/viewer.py -i"
echo ""
echo "  3. Read documentation:"
echo "     cat agent/README.md"
echo ""
