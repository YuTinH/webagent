#!/usr/bin/env python3
"""Debug search flow to see what's happening"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-proxy-server'])
    page = browser.new_page()

    print("Step 1: Opening homepage...")
    page.goto('http://localhost:8000/shop.local/index.html', wait_until='domcontentloaded')
    time.sleep(1)

    print("Step 2: Clicking search box...")
    page.click('#search-box')
    time.sleep(0.5)

    print("Step 3: Typing 'wireless mouse'...")
    page.fill('#search-box', 'wireless mouse')
    time.sleep(0.5)

    print("Step 4: Clicking search button...")
    page.click('button[type="submit"][aria-label="Search"]')
    print(f"  Current URL after click: {page.url}")

    print("Step 5: Waiting for navigation...")
    time.sleep(3)

    print(f"  Final URL: {page.url}")
    print(f"  Page title: {page.title()}")

    # Check for product grid container
    grid_container = page.query_selector('.product-grid')
    if grid_container:
        print(f"  ✅ Found .product-grid container")
        html_snippet = grid_container.inner_html()[:300]
        print(f"  Container HTML: {html_snippet}")
    else:
        print(f"  ❌ No .product-grid container")

    # Check for product items
    products = page.query_selector_all('.product-item')
    print(f"  Found {len(products)} .product-item elements")

    # Check products-list div
    products_list = page.query_selector('#products-list')
    if products_list:
        print(f"  ✅ Found #products-list")
        html_snippet = products_list.inner_html()[:500]
        print(f"  List HTML: {html_snippet}")
    else:
        print(f"  ❌ No #products-list")

    # Take screenshot
    page.screenshot(path='search_debug.png')
    print("  Screenshot saved to search_debug.png")

    browser.close()
