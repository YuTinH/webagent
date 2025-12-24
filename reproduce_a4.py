
import requests
import json

BASE_URL = "http://localhost:8014"

# 1. Mutate
print("Subscribing...")
payload = {
    "task_id": "A4-2025-GEN",
    "action": "mobile_subscribe",
    "payload": {
        "planId": "unlimited",
        "name": "Test User"
    }
}
resp = requests.post(f"{BASE_URL}/api/mutate", json=payload)
print(f"Mutate response: {resp.text}")

# 2. Get env
print("Getting env...")
resp = requests.get(f"{BASE_URL}/api/env")
env = resp.json()
mobile = env.get('mobile', {})
print(f"Mobile state: {json.dumps(mobile, indent=2)}")

if mobile.get('subscription', {}).get('status') == 'active':
    print("✅ SUCCESS")
else:
    print("❌ FAILURE")
