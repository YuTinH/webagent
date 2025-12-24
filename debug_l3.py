
import requests
import json

BASE_URL = "http://localhost:8014"

# 1. Trigger L3 Mutation
print("Triggering L3 rotation...")
payload = {
    "task_id": "L3-2025-SEC",
    "action": "rotate_keys",
    "payload": {
        "providers": ["mail", "cloud", "dev"],
        "method": "mfa+api"
    }
}
resp = requests.post(f"{BASE_URL}/api/mutate", json=payload)
print(f"Mutate Status: {resp.status_code}")
print(f"Mutate Response: {resp.text}")

# 2. Query Env directly
print("\nQuerying Env for security.last_rotation.providers...")
query_url = f"{BASE_URL}/api/env/query?path=security.last_rotation.providers"
resp = requests.get(query_url)
print(f"Query Status: {resp.status_code}")
print(f"Query Response: {resp.text}")

# 3. Check full Env
print("\nFetching full Env...")
resp = requests.get(f"{BASE_URL}/api/env")
env = resp.json()
sec = env.get('security', {{}})
print(f"Full Security State: {json.dumps(sec, indent=2)}")
