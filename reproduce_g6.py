
import requests
import json

BASE_URL = "http://localhost:8014"

# 1. Mutate (Book Vaccine)
print("Booking vaccine...")
payload = {
    "task_id": "G6-2025-GEN",
    "action": "book_vaccine",
    "payload": {
        "type": "flu",
        "date": "2025-12-17",
        "time": "09:00",
        "clinic": "City Health Clinic"
    }
}
resp = requests.post(f"{BASE_URL}/api/mutate", json=payload)
print(f"Mutate response: {resp.text}")

# 2. Get env again
print("Getting updated env...")
resp = requests.get(f"{BASE_URL}/api/env")
env = resp.json()
vaccines = env.get('health', {}).get('vaccines', {})
print(f"Health vaccines state: {json.dumps(vaccines, indent=2)}")

if any(v.get('status') == 'booked' for v in vaccines.values()):
    print("✅ SUCCESS: Vaccine booked correctly in backend.")
else:
    print("❌ FAILURE: Vaccine not booked.")
