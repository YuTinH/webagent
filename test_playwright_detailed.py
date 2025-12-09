#!/usr/bin/env python3
"""Test with detailed Playwright logging"""
import os
import sys

# Clear ALL proxy settings
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

print("Environment after cleanup:")
for key in os.environ:
    if 'proxy' in key.lower():
        print(f"  {key}={os.environ[key]}")

from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        print("\n🚀 Launching browser...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-proxy-server',
                '--disable-proxy',
                '--proxy-server=direct://',
                '--proxy-bypass-list=*'
            ]
        )

        print("✅ Browser launched")
        page = browser.new_page()
        print("✅ Page created")

        print("🔄 Navigating to localhost:8000...")
        response = page.goto(
            'http://localhost:8000/shop.local/index.html',
            timeout=10000,
            wait_until='domcontentloaded'
        )

        print(f"✅ SUCCESS! Status: {response.status}")
        print(f"   URL: {page.url}")
        print(f"   Title: {page.title()}")

        browser.close()
        sys.exit(0)

except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
