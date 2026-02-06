import os
import json
import subprocess
import time

def run_step(task_id, goal):
    print(f"\n🚀 Running Task: {task_id}")
    print(f"🎯 Goal: {goal}")
    res = subprocess.run(["python3", "run_task.py", task_id, "--headless"], capture_output=True, text=True)
    if "Task completed successfully" in res.stdout:
        print("✅ Step OK")
    else:
        print("❌ Step Failed (Expected for some butterfly nodes)")
    return res.stdout

def main():
    # Reset
    print("🔄 Initializing clean environment...")
    subprocess.run(["python3", "init_db.py"], capture_output=True)
    if os.path.exists("env/state.json"): os.remove("env/state.json")
    
    print("\n--- BEGIN TRIPLE-HOP BUTTERFLY EFFECT TEST ---")
    
    # Step 1: Get Sick
    run_step("M3-illness-reporting", "Report flu to health system.")
    
    # Step 2: Enroll Course
    # We need to make sure the task name is correct (J1-course-enroll)
    run_step("J1-course-enroll", "Enroll in Writing class while sick.")
    
    # Step 3: Submit Paper
    run_step("F3-paper-submission", "Submit paper to top journal.")
    
    # Final Verification of the Chain
    print("\n🧐 Final State Verification:")
    with open("env/state.json") as f:
        env = json.load(f)
        energy = env.get('world_state',{}).get('physical_context',{}).get('energy_level')
        skill = env.get('world_state',{}).get('skills',{}).get('writing')
        # Find the latest submission status
        work = env.get('work', {}).get('paper_submissions', {})
        status = "None"
        for sub in work.values():
            status = sub.get('status')
            
    print(f"  1. Energy Level: {energy}% (Expected: 20)")
    print(f"  2. Writing Skill: {skill} (Expected: basic)")
    print(f"  3. Paper Status: {status} (Expected: rejected_low_quality)")
    
    if energy == 20 and skill == 'basic' and status == 'rejected_low_quality':
        print("\n🏆 DOMINO EFFECT VERIFIED: The chain of consequences is fully operational!")
    else:
        print("\n💀 VERIFICATION FAILED: The ripple didn't reach the end.")

if __name__ == "__main__":
    main()
