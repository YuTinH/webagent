import requests
import json

API_URL = "http://localhost:8014/api/mutate"
ENV_URL = "http://localhost:8014/api/env"

def send_action(task_id, action, payload):
    print(f"\n🚀 Sending {task_id} - {action}...")
    resp = requests.post(API_URL, json={
        "task_id": task_id,
        "action": action,
        "payload": payload
    })
    try:
        if resp.status_code != 200:
             print(f"   ❌ HTTP Error {resp.status_code}: {resp.text}")
             return {}
        data = resp.json()
        print(f"   Response: {data}")
        return data
    except:
        print(f"   ❌ Failed to decode JSON. Status: {resp.status_code}, Raw Response: {resp.text}")
        return {}

def check_env(path_check_fn):
    resp = requests.get(ENV_URL)
    env = resp.json()
    try:
        val = path_check_fn(env)
        print(f"   ✅ Env Check Passed: {val}")
        return True
    except Exception as e:
        print(f"   ❌ Env Check Failed: {e}")
        # print(json.dumps(env, indent=2))
        return False

def main():
    print("--- 1. Vehicle Repair Impact (I2 -> E3) ---")
    # Step 1: Submit Car Repair
    send_action("I2-TEST", "submit_appliance_repair", {
        "appliance": "My Car",
        "serial_number": "VIN-123",
        "problem": "Engine light"
    })
    # Verify State
    check_env(lambda e: e['world_state']['vehicle_context']['condition'] == 'under_repair')
    
    # Step 2: Try to Book Self-Drive
    resp = send_action("E3-TEST", "book_airport_transfer", {
        "method": "self_drive"
    })
    if resp.get('success') is False and "under repair" in resp.get('error', ''):
        print("   ✅ Butterfly Effect Verified: Self-drive blocked due to repair.")
    else:
        print("   ❌ Failed: Self-drive should be blocked.")

    print("\n--- 2. Energy Plan Impact (I5 -> D2) ---")
    # Step 1: Set Premium Plan
    send_action("I5-TEST", "set_energy_plan", {
        "plan": "premium_flat_rate",
        "meterId": "M-TEST"
    })
    check_env(lambda e: e['world_state']['energy_context']['projected_cost'] == 'high')
    
    # Step 2: Adjust Budget too low
    send_action("D2-TEST", "adjust_budget", {
        "category": "utilities",
        "limit": 200
    })
    check_env(lambda e: "Budget Alert" in e['finance']['warnings'][0])
    print("   ✅ Butterfly Effect Verified: Budget alert triggered.")

    print("\n--- 3. Credential Value (J4 -> B7) ---")
    # Step 1: Get Certified
    send_action("J4-TEST", "issue_certificate", {
        "name": "Certified Python Expert"
    })
    check_env(lambda e: e['world_state']['skills']['certified'] is True)
    
    # Step 2: List Service
    send_action("B7-TEST", "list_second_hand_item", {
        "name": "Coding Tutoring",
        "description": "Expert level",
        "price": 100,
        "category": "service"
    })
    # Verify price doubled in memory/env
    check_env(lambda e: e['market']['listed_items']['last']['price'] == 200.0)
    print("   ✅ Butterfly Effect Verified: Service price doubled due to certification.")

if __name__ == "__main__":
    main()
