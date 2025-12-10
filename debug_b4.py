
import requests
import json

URL = "http://localhost:8014/api/mutate"
PAYLOAD = {
    "task_id": "B4-TEST-001",
    "action": "order_food",
    "payload": {
        "restaurant": "Test Burger",
        "items": ["Burger", "Fries"],
        "total": 12.99
    }
}

try:
    print(f"Sending POST to {URL}...")
    response = requests.post(URL, json=PAYLOAD, timeout=5)
    print(f"Status Code: {response.status_code}")
    print("Response Headers:", response.headers)
    print("\nResponse Body:")
    print(response.text[:500]) # Print first 500 chars
    
    try:
        data = response.json()
        print("\nJSON Parsed Successfully:")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print("\n❌ Failed to parse JSON!")
except Exception as e:
    print(f"\n❌ Request Failed: {e}")
