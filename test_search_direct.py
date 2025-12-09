#!/usr/bin/env python3
"""Test search page directly"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-proxy-server'])
    page = browser.new_page()

    # Test 1: Direct access without params
    print("Test 1: Accessing search.html without params...")
    resp = page.goto('http://localhost:8000/shop.local/search.html', wait_until='domcontentloaded')
    print(f"  Status: {resp.status}, Title: {page.title()}")

    # Test 2: Direct access with params
    print("\nTest 2: Accessing search.html WITH params...")
    resp = page.goto('http://localhost:8000/shop.local/search.html?q=wireless%20mouse', wait_until='domcontentloaded')
    print(f"  Status: {resp.status}, Title: {page.title()}")
    print(f"  URL: {page.url}")

    # Check page content
    html = page.content()[:500]
    print(f"  HTML snippet: {html}")

    browser.close()
