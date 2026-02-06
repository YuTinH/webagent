import subprocess
import json
import os

def run_b1():
    print("🚀 Verifying B1-shopping (Mouse)...")
    
    # 1. Reset
    subprocess.run(["python3", "init_db.py"], stdout=subprocess.DEVNULL)
    if os.path.exists("env/state.json"): os.remove("env/state.json")
    try: subprocess.run(["curl", "-s", "http://localhost:8014/api/env"], stdout=subprocess.DEVNULL, timeout=1) 
    except: pass

    # 2. Run Task
    res = subprocess.run(
        ["python3", "run_task.py", "B1-shopping", "--headless"],
        capture_output=True, text=True
    )
    
    print(res.stdout)
    
    if "Task completed successfully" in res.stdout:
        print("\n✅ B1 Passed!")
    else:
        print("\n❌ B1 Failed!")

if __name__ == "__main__":
    run_b1()

