#!/usr/bin/env python3
"""
Test New Dependency Chains (Medical & Travel)

This script verifies the new task chains:
1. Medical: G1 -> G2 -> G3
2. Travel: E1 -> E2 -> F2 -> E5
"""

import sys
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.enhanced_executor import EnhancedTaskExecutor, run_task_with_dependencies
from agent.perturbation_engine import PerturbationLevel
from agent.state_propagation import StatePropagationEngine

def deep_merge(a, b):
    """Deep merge two dictionaries"""
    if isinstance(a, dict) and isinstance(b, dict):
        r = dict(a)
        for k, v in b.items():
            r[k] = deep_merge(r.get(k), v) if k in r else v
        return r
    return b

class TestRunner:
    def __init__(self, perturbation_level: int = PerturbationLevel.ADVANCED, seed: int = 42):
        self.perturbation_level = perturbation_level
        self.seed = seed
        self.db_path = "data.db"
        self.results = []
        self.env_dir = Path("env")
        self.state_path = self.env_dir / "state.json"

    def reset_state(self):
        """Reset database and env state for clean test"""
        print("\n🔄 Resetting state...")
        
        # Clear memory_kv table
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memory_kv")
            conn.commit()
            
        engine = StatePropagationEngine(self.db_path)

        # 1. Reset SQL State (Banking, etc.)
        engine.set_env_state('banking.balance.checking', 5000.00) # Plenty of money for travel
        
        # Reset memory in SQL
        engine.memory_cache = {}
        
        # Preset User Profile
        engine.set_memory("address", {"primary": "123 Main St, Springfield"})
        engine.set_memory("payment", {
            "cards": [{"last4": "1234", "status": "active"}]
        })
        engine.set_memory("banking", {
            "username": "user123", 
            "password": "pass123",
            "balance": {"checking": 5000.00}
        })
        engine.set_memory("identity", {
            "address": "123 Main St, Springfield",
            "vehicle": {"plate": "ABC-1234"},
            "name": "John Doe",
            "dob": "1985-06-15"
        })
        
        engine.save_memory()

        # 2. Reset JSON Env State (Medical, Travel, etc.)
        
        # Ensure clean slate for state.json
        # The TestRunner will now explicitly print the state_path it is using.
        print(f"DEBUG: TestRunner using state.json at: {self.state_path}")
        if self.state_path.exists():
            self.state_path.unlink()

        initial_state = {}
        # Ensure all top-level keys are present as empty dicts for robustness with deep_merge
        initial_state = deep_merge(initial_state, {
            "health": {}, "trips": {}, "work": {}, "expenses": {}, 
            "contracts": {}, "courses": {}, "food": {}, "housing": {}, 
            "support": {}, "payments": {}, "permits": {}, "meters": {}
        })
        
        # Load G-medical
        medical_seed = self.env_dir / "G-medical_initial.json"
        if medical_seed.exists():
            with open(medical_seed) as f:
                initial_state = deep_merge(initial_state, json.load(f))
                
        # Load E-travel
        travel_seed = self.env_dir / "E-travel_initial.json"
        if travel_seed.exists():
            with open(travel_seed) as f:
                initial_state = deep_merge(initial_state, json.load(f))
        
        # Write to state.json
        with open(self.state_path, 'w') as f:
            json.dump(initial_state, f, indent=2)

        print("✅ State reset complete")

    def run_test_scenario(self, name: str, tasks: list):
        print(f"\n{'='*80}")
        print(f"🧪 TEST SCENARIO: {name}")
        print(f"{ '='*80}")
        print(f"Tasks: {' → '.join(tasks)}")
        
        scenario_results = []
        
        for i, task_dir in enumerate(tasks):
            print(f"\n[{i+1}/{len(tasks)}] Running {task_dir}...")
            
            try:
                # We assume the server is running and accessible
                result = run_task_with_dependencies(
                    task_dir,
                    perturbation_level=self.perturbation_level,
                    seed=self.seed,
                    headless=True
                )
                
                scenario_results.append({
                    'task': task_dir,
                    'success': result.success,
                    'state': result.final_state,
                    'error': str(result.error) if result.error else None
                })
                
                if not result.success:
                    print(f"❌ Task {task_dir} failed: {result.error}")
                    break # Stop chain on failure
                
            except Exception as e:
                print(f"❌ Exception running {task_dir}: {e}")
                scenario_results.append({'task': task_dir, 'success': False, 'error': str(e)})
                break

        # Summary
        all_success = all(r['success'] for r in scenario_results) and len(scenario_results) == len(tasks)
        print(f"\nScenario: {'✅ PASS' if all_success else '❌ FAIL'}")
        return all_success

    def scenario_medical(self):
        self.reset_state()
        return self.run_test_scenario(
            "Medical Chain: G1 → G2 → G3",
            ["G1-doctor-appt", "G2-prescription-refill", "G3-medical-claim"]
        )

    def scenario_travel(self):
        self.reset_state()
        return self.run_test_scenario(
            "Travel Chain: E1 → E2 → F2 → E5",
            ["E1-book-flight", "E2-book-hotel", "F2-conference-reg", "E5-expense-report"]
        )

    def scenario_housing(self):
        self.reset_state()
        return self.run_test_scenario(
            "Housing: A1 (Find Home)",
            ["A1-find-home"]
        )

    def scenario_utility(self):
        self.reset_state()
        return self.run_test_scenario(
            "Utility: A3 (Setup Services)",
            ["A3-utility-setup"]
        )

    def scenario_education(self):
        self.reset_state()
        return self.run_test_scenario(
            "Education: J1 (Course Enroll)",
            ["J1-course-enroll"]
        )

    def scenario_food(self):
        self.reset_state()
        return self.run_test_scenario(
            "Food: B4 (Delivery)",
            ["B4-food-delivery"]
        )

    def scenario_support(self):
        self.reset_state()
        return self.run_test_scenario(
            "Support: C1 (Logistics Fix)",
            ["C1-logistics-fix"]
        )

def main():
    runner = TestRunner(perturbation_level=1) # Use level 1 for functional verification
    
    print("🚀 Starting Verification for All Chains")
    
    res = {}
    res['Medical'] = runner.scenario_medical()
    res['Travel'] = runner.scenario_travel()
    res['Housing'] = runner.scenario_housing()
    res['Utility'] = runner.scenario_utility()
    res['Education'] = runner.scenario_education()
    res['Food'] = runner.scenario_food()
    res['Support'] = runner.scenario_support()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    all_pass = True
    for name, passed in res.items():
        status = '✅ PASS' if passed else '❌ FAIL'
        print(f"{name:15s}: {status}")
        if not passed: all_pass = False
    print("="*80)
    
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()
