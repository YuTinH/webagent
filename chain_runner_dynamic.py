import json
import os
import subprocess
import time
import random
import sys

# Built-in Logger to save output to file
class Logger(object):
    def __init__(self, filename="evaluation.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush() # Force write to disk immediately

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger("evaluation.log")
sys.stderr = sys.stdout

print(f"\n{'='*60}")
print(f"NEW EVALUATION SESSION STARTED AT {time.ctime()}")
print(f"{'='*60}")

def load_scenarios():
    themes = ["newcomer", "daily", "career", "leisure", "crisis"]
    all_scenarios = {}
    for theme in themes:
        path = f"sampled_{theme}.json"
        if os.path.exists(path):
            print(f"Loading {theme} scenarios from {path}...")
            with open(path) as f:
                for s in json.load(f):
                    all_scenarios[s['chain_id']] = s
    return all_scenarios

def patch_trace(task_id, instruction):

    """

    Dynamically patch oracle_trace.json based on instruction keywords.

    """

    trace_path = f"tasks/{task_id}/oracle_trace.json"

    if not os.path.exists(trace_path): return

    

    with open(trace_path, 'r') as f:

        trace = json.load(f)

    

    # Logic for A1: City vs Suburb

    if task_id == "A1-find-home":

        if "郊区" in instruction or "房子" in instruction:

            print(f"  🛠️ Patching A1 trace for SUBURB (PROP-102)")

            for step in trace['steps']:

                if "property-card" in step.get('selector', ''):

                    step['selector'] = ".property-card:has(.property-title:has-text('阳光海岸别墅区20号'))"

        else:

            print(f"  🛠️ Patching A1 trace for CITY (PROP-101)")

            for step in trace['steps']:

                if "property-card" in step.get('selector', ''):

                    step['selector'] = ".property-card:has(.property-title:has-text('中央大街101号'))"



    # Logic for I5: Green vs Premium

    if task_id == "I5-energy-optimize":

        if "全天候" in instruction or "Premium" in instruction:

            print(f"  🛠️ Patching I5 trace for PREMIUM")

            for step in trace['steps']:

                if "plan-green_offpeak" in step.get('selector', ''):

                    step['selector'] = step['selector'].replace('green_offpeak', 'premium_flat_rate')

        else:

            print(f"  🛠️ Patching I5 trace for GREEN")

            for step in trace['steps']:

                if "plan-premium_flat_rate" in step.get('selector', ''):

                    step['selector'] = step['selector'].replace('premium_flat_rate', 'green_offpeak')



    # Logic for D2: Standard vs Tight (Utilities)

    if task_id == "D2-budget-report":

        if "公用事业" in instruction or "utilities" in instruction or "低预算" in instruction:

            print(f"  🛠️ Patching D2 trace for TIGHT (Utilities=200)")

            for step in trace['steps']:

                if "data-category='food'" in step.get('selector', ''):

                    step['selector'] = ".budget-item[data-category='utilities'] .btn-edit"

                if step.get('act') == 'type' and step.get('selector') == '#new-limit':

                    step['value'] = "200"

                if "limit-food" in step.get('selector', ''):

                    step['selector'] = "#limit-utilities:has-text('$200.00')"

        else:

            print(f"  🛠️ Patching D2 trace for STANDARD (Food=500)")

            for step in trace['steps']:

                if "data-category='utilities'" in step.get('selector', ''):

                    step['selector'] = ".budget-item[data-category='food'] .btn-edit"

                if step.get('act') == 'type' and step.get('selector') == '#new-limit':

                    step['value'] = "500"

                if "limit-utilities" in step.get('selector', ''):

                    step['selector'] = "#limit-food:has-text('$500.00')"



    # Logic for I2: Oven vs Car

    if task_id == "I2-appliance-repair":

        if "车辆" in instruction or "Car" in instruction:

            print(f"  🛠️ Patching I2 trace for CAR")

            for step in trace['steps']:

                if step.get('act') == 'type' and "appliance" in step.get('selector','') :

                    step['value'] = "My Car"

                if step.get('act') == 'type' and "problem" in step.get('selector','') :

                    step['value'] = "Engine noise"

        else:

            print(f"  🛠️ Patching I2 trace for OVEN")

            for step in trace['steps']:

                if step.get('act') == 'type' and "appliance" in step.get('selector','') :

                    step['value'] = "Oven"



    # Logic for E3: Taxi vs Drive

    if task_id == "E3-airport-transfer":

        if "自驾" in instruction or "drive" in instruction:

            print(f"  🛠️ Patching E3 trace for SELF_DRIVE")

            for step in trace['steps']:

                if step.get('act') == 'select' and "method" in step.get('selector','') :

                    step['value'] = "self_drive"

        else:

            print(f"  🛠️ Patching E3 trace for TAXI")

            for step in trace['steps']:

                if step.get('act') == 'select' and "method" in step.get('selector','') :

                    step['value'] = "taxi"



    # Logic for B1: Mouse vs Keyboard (REWRITTEN)

    if task_id == "B1-shopping":

        print(f"  🛠️ Rewriting B1 trace for DIRECT ACCESS")

        if "Keyboard" in instruction or "键盘" in instruction:

            target_url = "http://localhost:8014/shop.local/product.html?id=KB-8801"

        else:

            target_url = "http://localhost:8014/shop.local/product.html?id=WM-5521"

            

        trace['steps'] = [

            {"t": 0, "act": "open", "url": target_url, "note": "Directly open product page"},

            {"t": 1, "act": "click", "selector": "#add-to-cart-btn", "note": "Add to cart"},

            {"t": 2, "act": "open", "url": "http://localhost:8014/shop.local/cart.html", "note": "Open cart page"},

            {"t": 3, "act": "wait", "selector": "#checkout-btn", "note": "Wait for checkout button"},

            {"t": 4, "act": "click", "selector": "#checkout-btn", "note": "Proceed to checkout"},

            {"t": 5, "act": "wait", "selector": "#order-id", "note": "Wait for confirmation"}

        ]

        

    # Logic for B7: Home vs Service

    if task_id == "B7-second-hand-sale":

        if "服务" in instruction or "service" in instruction:

            print(f"  🛠️ Patching B7 trace for SERVICE")

            for step in trace['steps']:

                if step.get('act') == 'select' and "category" in step.get('selector','') :

                    step['value'] = "service"

                if step.get('act') == 'type' and "price" in step.get('selector','') :

                    step['value'] = "100" 

        else:

            print(f"  🛠️ Patching B7 trace for HOME")

            for step in trace['steps']:

                if step.get('act') == 'select' and "category" in step.get('selector','') :

                    step['value'] = "home"

                if step.get('act') == 'type' and "price" in step.get('selector','') :

                    step['value'] = "50"



    # Logic for C2: Return request

    if task_id == "C2-return":

        print(f"  🛠️ Patching C2 trace for order return flow")

        # Try to get order ID from DB

        import sqlite3

        order_id = "O-TEST"

        try:

            conn = sqlite3.connect('data.db')

            c = conn.cursor()

            c.execute("SELECT value FROM memory_kv WHERE key = 'shop.orders.last.id'")

            row = c.fetchone()

            if row: 

                order_id = row[0]

                print(f"  🔍 Found Order ID: {order_id}")

            else:

                print(f"  ⚠️ No Order ID found in memory_kv!")

            conn.close()

        except Exception as e: print(f"  ❌ DB Read Error: {e}")

        

        target_url = f"http://localhost:8014/shop.local/returns/new.html?order_id={order_id}"

        trace['steps'] = [

            {"t": 0, "act": "open", "url": target_url, "note": "Navigate to return form"},

            {"t": 1, "act": "click", "selector": ".reason-option:has-text('不想要了')", "note": "Select reason"},

            {"t": 2, "act": "type", "selector": "#return-description", "value": "Customer changed mind.", "note": "Describe reason"},

            {"t": 3, "act": "click", "selector": "button.btn.ok", "note": "Submit"},

            {"t": 4, "act": "wait", "selector": ".success-title:has-text('退货申请已提交')", "note": "Wait confirmation"}

        ]



    with open(trace_path, 'w') as f:

        json.dump(trace, f, indent=2, ensure_ascii=False)

def patch_spec(task_id, criteria):
    spec_path = f"tasks/{task_id}/task_spec.json"
    with open(spec_path, 'r') as f:
        spec = json.load(f)
    spec['success_criteria'] = criteria
    spec['preconditions'] = []
    with open(spec_path, 'w') as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

def inject_state(initial_state):
    """
    Injects initial state from generator into the backend environment.
    Crucial for tasks like E1 (Commute) that depend on location context.
    """
    if not initial_state: return
    
    payload = {"world_state": {}}
    
    # Map Location
    loc = initial_state.get('location')
    if loc:
        tier = 'suburban' if loc == 'suburb' else 'city_center'
        payload['world_state']['location_context'] = {'tier': tier}
        print(f"  🌍 Injecting Location: {loc} ({tier})")
        
    # Map Balance (if needed for H3 check)
    if 'balance' in initial_state:
        payload['balance'] = initial_state['balance']
        
    # Map Energy Level (for F3)
    if 'energy_level' in initial_state:
        payload['energy_level'] = initial_state['energy_level']

    if payload['world_state'] or 'balance' in payload or 'energy_level' in payload:
        cmd = [
            "curl", "-s", "-X", "POST", "http://localhost:8014/api/mutate",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"task_id": "DEBUG", "action": "set_state", "payload": payload})
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL)

def run_chain(scenario):
    print(f"\n▶️ Running Chain: {scenario['chain_id']}")
    print("  🔄 Resetting Environment (DB & State)...")
    subprocess.run(["python3", "init_db.py"], check=True, stdout=subprocess.DEVNULL)
    if os.path.exists("env/state.json"): os.remove("env/state.json")
    try: subprocess.run(["curl", "-s", "http://localhost:8014/api/env"], stdout=subprocess.DEVNULL, timeout=2)
    except: pass
    
    # Inject Initial State
    inject_state(scenario.get('initial_state'))
    
    try:
        for step in scenario['steps']:
            tid = step['task_id']
            print(f"  👉 Task: {tid} | Instr: {step['instruction'][:30]}...")
            
            patch_trace(tid, step['instruction'])
            patch_spec(tid, step['success_criteria'])
            
            res = subprocess.run(["python3", "run_task.py", tid, "--headless"], capture_output=True, text=True)
            
            if res.returncode != 0:
                print(f"  ❌ Failed: {tid}")
                print("--- STDOUT ---")
                print("\n".join(res.stdout.splitlines()[-20:]))
                print("--- STDERR ---")
                print(res.stderr)
                return False
            else:
                if "Task completed successfully" in res.stdout:
                    print(f"  ✅ Passed")
                else:
                    print(f"  ⚠️ Runner finished but success unclear: {tid}")
                    print("--- STDOUT ---")
                    print("\n".join(res.stdout.splitlines()[-20:]))
                    return False
            time.sleep(0.5)
                    
        print(f"🏆 Chain {scenario['chain_id']} COMPLETE!")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"  ❌ Chain Execution Error: {e}")
        return False

def main():
    print("🚀 Verifying Z1 in DAILY theme...")
    scenarios = load_scenarios()
    
    target_theme = "daily"
    target_task = "Z1-order-arrival"
    
    path = f"sampled_{target_theme}.json"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    with open(path) as f:
        theme_scenarios = json.load(f)
        
    filtered = []
    for s in theme_scenarios:
        tasks = [step['task_id'] for step in s['steps']]
        if target_task in tasks:
            filtered.append(s)
            
    print(f"Found {len(filtered)} scenarios with {target_task} in {target_theme}.")
    
    passed = 0
    for i, s in enumerate(filtered[:5]): # Test top 5
        print(f"\n[{i+1}/5] Testing {s['chain_id']}...")
        if run_chain(s):
            passed += 1
            
    print(f"\nPassed: {passed}/{min(len(filtered), 5)}")

if __name__ == "__main__":
    main()