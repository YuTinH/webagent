#!/usr/bin/env python3
"""Test using 127.0.0.1 instead of localhost"""
import os
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]
os.environ['NO_PROXY'] = '*'

from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-proxy-server', '--proxy-server=direct://']
        )
        page = browser.new_page()

        print("🔄 Testing with 127.0.0.1...")
        response = page.goto(
            'http://127.0.0.1:8000/shop.local/index.html',
            timeout=10000,
            wait_until='domcontentloaded'
        )

        print(f"✅ SUCCESS! Status: {response.status}")
        print(f"   Title: {page.title()}")
        browser.close()

except Exception as e:
    print(f"❌ FAILED: {e}")
