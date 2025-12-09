#!/usr/bin/env python3
"""Quick test to verify Playwright can access localhost:8000"""
from playwright.sync_api import sync_playwright
import sys

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-proxy-server'])
        page = browser.new_page()

        print("🔄 Testing connection to localhost:8000...")
        response = page.goto('http://localhost:8000/shop.local/index.html',
                            timeout=10000,
                            wait_until='domcontentloaded')

        print(f"✅ SUCCESS! Status: {response.status}")
        print(f"   URL: {page.url}")
        print(f"   Title: {page.title()}")

        # Check if search box exists
        search_box = page.query_selector('#search-box')
        if search_box:
            print(f"   ✅ Search box found!")
        else:
            print(f"   ⚠️  Search box not found")

        browser.close()
        sys.exit(0)

except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)
