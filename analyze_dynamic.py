import json
import random
from collections import Counter

def analyze_scenarios():
    with open("dynamic_scenarios_v2.json", 'r') as f:
        data = json.load(f)
    
    total = len(data)
    lengths = [len(s['steps']) for s in data]
    
    # Analyze Butterfly Effect Coverage
    suburb_count = 0
    commute_check_count = 0
    butterfly_triggered = 0
    
    for s in data:
        is_suburb = False
        has_commute = False
        for step in s['steps']:
            if step['task_id'] == 'A1-find-home' and 'PROP-102' in step['success_criteria'][0]:
                is_suburb = True
                suburb_count += 1
            if step['task_id'] == 'E1-commute-route':
                has_commute = True
                commute_check_count += 1
                if '120.0' in step['success_criteria'][0]: # Checking for high cost
                    butterfly_triggered += 1
                    
    print(f"📊 Dataset Statistics (N={total})")
    print("-" * 40)
    print(f"Length: Min={min(lengths)}, Max={max(lengths)}, Avg={sum(lengths)/total:.2f}")
    print(f"A1 Suburb Choices: {suburb_count} ({suburb_count/total*100:.1f}%)")
    print(f"E1 Commute Checks: {commute_check_count} ({commute_check_count/total*100:.1f}%)")
    print(f"🦋 Butterfly Effect (Suburb -> High Cost) Verified in Config: {butterfly_triggered}")
    print("-" * 40)
    
    # Pick 3 random IDs to test
    sample_ids = [s['chain_id'] for s in random.sample(data, 3)]
    print(f"Selected for Verification: {sample_ids}")
    return sample_ids

if __name__ == "__main__":
    analyze_scenarios()
