import json
import random
import uuid

# ==========================================
# 1. 任务元数据定义 (Task Metadata & Logic)
# ==========================================
# 定义每个任务的前置条件(pre)和执行后产生的状态影响(effect)
# pre: lambda state -> bool
# effect: function(state) -> void

TASKS_DB = {
    # --- A. Housing & Infrastructure ---
    "A1-find-home": {
        "family": "A",
        "desc": "Find and rent a home",
        "pre": lambda s: not s.get("has_home"),
        "effect": lambda s: s.update({"has_home": True, "address_proof": True})
    },
    "A2-bank-opening": {
        "family": "A",
        "desc": "Open bank account",
        "pre": lambda s: s.get("has_home") and not s.get("has_bank"),
        "effect": lambda s: s.update({"has_bank": True, "balance": 1000})
    },
    "A3-utility-setup": {
        "family": "A",
        "desc": "Setup utilities",
        "pre": lambda s: s.get("has_home") and not s.get("has_utility"),
        "effect": lambda s: s.update({"has_utility": True})
    },
    "A4-mobile-plan": {
        "family": "A",
        "desc": "Get mobile plan",
        "pre": lambda s: not s.get("has_mobile"),
        "effect": lambda s: s.update({"has_mobile": True})
    },
    "A5-lease-management": {
        "family": "A",
        "desc": "Manage lease",
        "pre": lambda s: s.get("has_home"),
        "effect": lambda s: None
    },
    "A6-address-proof": {
        "family": "A",
        "desc": "Upload address proof",
        "pre": lambda s: s.get("address_proof"),
        "effect": lambda s: s.update({"verified_gov": True})
    },

    # --- B. Consumption ---
    "B1-shopping": {
        "family": "B",
        "desc": "Buy items online",
        "pre": lambda s: s.get("has_bank") and s.get("has_home"),
        "effect": lambda s: s["orders"].append("B1")
    },
    "B2-fresh-subscription": {
        "family": "B",
        "desc": "Subscribe to fresh food",
        "pre": lambda s: s.get("has_bank") and s.get("has_home") and not s.get("has_sub_food"),
        "effect": lambda s: s.update({"has_sub_food": True})
    },
    "B3-housekeeping-booking": {
        "family": "B",
        "desc": "Book housekeeping",
        "pre": lambda s: s.get("has_home"),
        "effect": lambda s: None
    },
    "B4-food-delivery": {
        "family": "B",
        "desc": "Order food delivery",
        "pre": lambda s: s.get("has_bank") and s.get("has_home"),
        "effect": lambda s: None
    },
    "B5-coupon-management": {
        "family": "B",
        "desc": "Manage coupons",
        "pre": lambda s: True,
        "effect": lambda s: s.update({"has_coupon": True})
    },
    "B6-price-protection": {
        "family": "B",
        "desc": "Apply for price protection",
        "pre": lambda s: len(s["orders"]) > 0,
        "effect": lambda s: None
    },
    "B7-second-hand-sale": {
        "family": "B",
        "desc": "Sell used items",
        "pre": lambda s: len(s["orders"]) > 3,
        "effect": lambda s: s.update({"balance": s.get("balance", 0) + 50})
    },

    # --- C. Support ---
    "C1-logistics-fix": {
        "family": "C",
        "desc": "Contact support for logistics",
        "pre": lambda s: len(s["orders"]) > 0,
        "effect": lambda s: None
    },
    "C2-return": {
        "family": "C",
        "desc": "Return an item",
        "pre": lambda s: len(s["delivered_orders"]) > 0,
        "effect": lambda s: s["delivered_orders"].pop() if s["delivered_orders"] else None
    },
    "C3-subscription-refund": {
        "family": "C",
        "desc": "Cancel and refund subscription",
        "pre": lambda s: s.get("has_sub_food"),
        "effect": lambda s: s.update({"has_sub_food": False})
    },
    "C4-warranty-claim": {
        "family": "C",
        "desc": "Submit warranty claim",
        "pre": lambda s: len(s["delivered_orders"]) > 0,
        "effect": lambda s: None
    },
    "C5-leave-review": {
        "family": "C",
        "desc": "Leave a review",
        "pre": lambda s: len(s["delivered_orders"]) > 0,
        "effect": lambda s: None
    },

    # --- D. Finance ---
    "D1-check-balance": {
        "family": "D",
        "desc": "Check bank balance",
        "pre": lambda s: s.get("has_bank"),
        "effect": lambda s: None
    },
    "D2-budget-report": {
        "family": "D",
        "desc": "View budget report",
        "pre": lambda s: s.get("has_bank"),
        "effect": lambda s: s.update({"budget_set": True})
    },
    "D3-autopay": {
        "family": "D",
        "desc": "Setup autopay",
        "pre": lambda s: s.get("has_bank") and s.get("has_utility") and not s.get("autopay"),
        "effect": lambda s: s.update({"autopay": True})
    },
    "D4-card-replacement": {
        "family": "D",
        "desc": "Replace bank card",
        "pre": lambda s: s.get("card_frozen"),
        "effect": lambda s: s.update({"card_frozen": False, "has_bank": True})
    },
    "D5-tax-preparation": {
        "family": "D",
        "desc": "Prepare taxes",
        "pre": lambda s: s.get("has_bank"),
        "effect": lambda s: None
    },
    "D6-investment-account": {
        "family": "D",
        "desc": "Open investment account",
        "pre": lambda s: s.get("has_bank") and s.get("balance", 0) > 500 and not s.get("has_invest"),
        "effect": lambda s: s.update({"has_invest": True})
    },

    # --- E. Travel ---
    "E1-commute-route": {
        "family": "E",
        "desc": "Check commute route",
        "pre": lambda s: s.get("has_home"),
        "effect": lambda s: s.update({"commute_planned": True})
    },
    "E2-transport-topup": {
        "family": "E",
        "desc": "Topup transport card",
        "pre": lambda s: s.get("commute_planned") and s.get("has_bank"),
        "effect": lambda s: None
    },
    "E3-airport-transfer": {
        "family": "E",
        "desc": "Book airport transfer",
        "pre": lambda s: s.get("trip_booked"),
        "effect": lambda s: None
    },
    "E4-visa-requirements": {
        "family": "E",
        "desc": "Check visa requirements",
        "pre": lambda s: True,
        "effect": lambda s: s.update({"knows_visa": True})
    },
    "E5-expense-report": {
        "family": "E",
        "desc": "Submit expense report",
        "pre": lambda s: s.get("trip_booked"),
        "effect": lambda s: None
    },
    "E6-flight-change": {
        "family": "E",
        "desc": "Change flight",
        "pre": lambda s: s.get("trip_booked"),
        "effect": lambda s: None
    },
    "E7-long-haul-trip": {
        "family": "E",
        "desc": "Apply visa and book trip",
        "pre": lambda s: s.get("has_bank") and s.get("knows_visa"),
        "effect": lambda s: s.update({"has_visa": True, "trip_booked": True})
    },

    # --- F. Work ---
    "F1-calendar-aggregation": {
        "family": "F",
        "desc": "Manage calendar",
        "pre": lambda s: True,
        "effect": lambda s: None
    },
    "F2-conference-reg": {
        "family": "F",
        "desc": "Register for conference",
        "pre": lambda s: s.get("has_bank"),
        "effect": lambda s: s.update({"conf_registered": True})
    },
    "F3-paper-submission": {
        "family": "F",
        "desc": "Submit paper",
        "pre": lambda s: True,
        "effect": lambda s: None
    },
    "F4-email-tracking": {
        "family": "F",
        "desc": "Track email",
        "pre": lambda s: True,
        "effect": lambda s: None
    },
    "F5-receipt-archive": {
        "family": "F",
        "desc": "Archive receipts",
        "pre": lambda s: len(s["orders"]) > 0,
        "effect": lambda s: None
    },
    
    # --- G. Health ---
    "G1-doctor-appt": {
        "family": "G",
        "desc": "Book doctor appointment",
        "pre": lambda s: s.get("is_sick"),
        "effect": lambda s: s.update({"has_prescription": True})
    },
    "G2-insurance-policy": {
        "family": "G",
        "desc": "Buy insurance",
        "pre": lambda s: s.get("has_bank") and not s.get("has_insurance"),
        "effect": lambda s: s.update({"has_insurance": True})
    },
    "G3-medical-claim": {
        "family": "G",
        "desc": "Submit medical claim",
        "pre": lambda s: s.get("has_insurance") and s.get("is_sick"),
        "effect": lambda s: None
    },
    "G4-gym-membership": { # Actually Pharmacy Refill in V2 impl
        "family": "G",
        "desc": "Pharmacy Refill", 
        "pre": lambda s: s.get("has_prescription"),
        "effect": lambda s: s.update({"is_sick": False, "has_prescription": False})
    },
    "G5-health-plan": {
        "family": "G",
        "desc": "Activate health plan",
        "pre": lambda s: True,
        "effect": lambda s: s.update({"health_plan": True})
    },
    "G6-vaccine-mgmt": {
        "family": "G",
        "desc": "Book vaccine",
        "pre": lambda s: s.get("health_plan"),
        "effect": lambda s: None
    },
    
    # --- H. Gov ---
    "H1-address-change": {
        "family": "H",
        "desc": "Update municipal address",
        "pre": lambda s: s.get("has_home") and not s.get("gov_addr_updated"),
        "effect": lambda s: s.update({"gov_addr_updated": True})
    },
    "H2-vehicle-address-update": {
        "family": "H",
        "desc": "Update vehicle address",
        "pre": lambda s: s.get("gov_addr_updated") and s.get("has_car"),
        "effect": lambda s: None
    },
    "H3-permit-renewal": {
        "family": "H",
        "desc": "Renew permit",
        "pre": lambda s: True,
        "effect": lambda s: None
    },
    "H4-parking-permit": {
        "family": "H",
        "desc": "Apply parking permit",
        "pre": lambda s: s.get("has_car") and s.get("gov_addr_updated"),
        "effect": lambda s: None
    },

    # --- I. Repair ---
    "I1-smart-bulb-setup": {
        "family": "I",
        "desc": "Setup smart bulb",
        "pre": lambda s: s.get("has_home") and s.get("has_utility"),
        "effect": lambda s: s.update({"smart_home": True})
    },
    "I2-appliance-repair": {
        "family": "I",
        "desc": "Appliance repair",
        "pre": lambda s: s.get("has_home"),
        "effect": lambda s: None
    },
    "I4-smart-meter": {
        "family": "I",
        "desc": "Check smart meter",
        "pre": lambda s: s.get("has_utility"),
        "effect": lambda s: None
    },
    "I5-energy-optimize": {
        "family": "I",
        "desc": "Optimize energy plan",
        "pre": lambda s: s.get("has_utility"),
        "effect": lambda s: None
    },

    # --- J. Learning ---
    "J1-course-enroll": {
        "family": "J",
        "desc": "Enroll in course",
        "pre": lambda s: not s.get("is_sick"),
        "effect": lambda s: s.update({"enrolled_course": True})
    },
    "J2-library-service": {
        "family": "J",
        "desc": "Library service",
        "pre": lambda s: s.get("enrolled_course"),
        "effect": lambda s: None
    },
    "J3-event-tickets": {
        "family": "J",
        "desc": "Buy event tickets",
        "pre": lambda s: s.get("has_bank"),
        "effect": lambda s: None
    },
    "J4-gear-rental": {
        "family": "J",
        "desc": "Rent hobby gear",
        "pre": lambda s: s.get("has_bank"),
        "effect": lambda s: None
    },

    # --- K. Social ---
    "K1-plan-party": {
        "family": "K",
        "desc": "Plan party",
        "pre": lambda s: s.get("has_home"),
        "effect": lambda s: s.update({"party_planned": True})
    },
    "K2-roommate-split": {
        "family": "K",
        "desc": "Split bills",
        "pre": lambda s: s.get("has_home"),
        "effect": lambda s: None
    },
    "K3-charity-donation": {
        "family": "K",
        "desc": "Donate to charity",
        "pre": lambda s: s.get("has_bank") and s.get("balance", 0) > 100,
        "effect": lambda s: s.update({"balance": s.get("balance", 0) - 50})
    },

    # --- L. Privacy & Security ---
    "L1-password-manager": {
        "family": "L",
        "desc": "Manage passwords",
        "pre": lambda s: True,
        "effect": lambda s: s.update({"secure_pw": True})
    },
    "L2-data-deletion": {
        "family": "L",
        "desc": "Request data deletion",
        "pre": lambda s: True,
        "effect": lambda s: None
    },
    "L3-security-audit": {
        "family": "L",
        "desc": "Security audit",
        "pre": lambda s: True,
        "effect": lambda s: s.update({"security_alert": True})
    },
    "L4-2fa-device": {
        "family": "L",
        "desc": "Change 2FA device",
        "pre": lambda s: s.get("has_mobile"),
        "effect": lambda s: None
    },
    
    # --- M. Crisis (Triggers) ---
    "M1-lost-card": {
        "family": "M",
        "desc": "Report lost card",
        "pre": lambda s: s.get("has_bank") and not s.get("card_frozen"),
        "effect": lambda s: s.update({"card_frozen": True})
    },
    "M2-supply-disruption": {
        "family": "M",
        "desc": "Supply chain disruption",
        "pre": lambda s: len(s["orders"]) > 0,
        "effect": lambda s: None
    },
    "M3-illness-reporting": {
        "family": "M",
        "desc": "Report illness",
        "pre": lambda s: not s.get("is_sick"),
        "effect": lambda s: s.update({"is_sick": True})
    },

    # --- Z. Advanced ---
    "Z1-order-arrival": {
        "family": "Z",
        "desc": "Wait for order delivery",
        "pre": lambda s: len(s["orders"]) > 0, # Needs an order
        "effect": lambda s: s["delivered_orders"].append(s["orders"].pop()) if s["orders"] else None
    },
    "Z2-investment-growth": {
        "family": "Z",
        "desc": "Wait for investment growth",
        "pre": lambda s: s.get("has_invest"),
        "effect": lambda s: s.update({"balance": s.get("balance", 0) * 1.05})
    },
    "Z3-live-auction": {
        "family": "Z",
        "desc": "Participate in auction",
        "pre": lambda s: s.get("has_bank") and s.get("balance", 0) > 300,
        "effect": lambda s: s.update({"balance": s.get("balance", 0) - 300})
    },
    "Z4-email-calendar": {
        "family": "Z",
        "desc": "Email to calendar workflow",
        "pre": lambda s: True,
        "effect": lambda s: None
    },
    "Z5-password-recovery": {
        "family": "Z",
        "desc": "Recover password via 2FA",
        "pre": lambda s: s.get("has_mobile") and (s.get("security_alert") or random.random() < 0.3),
        "effect": lambda s: s.update({"security_alert": False})
    },
    "Z6-customer-service": {
        "family": "Z",
        "desc": "Chat with customer service",
        "pre": lambda s: len(s["orders"]) > 0 or len(s["delivered_orders"]) > 0,
        "effect": lambda s: None
    }
}

# ==========================================
# 2. 生成器逻辑 (Generator Logic)
# ==========================================

def get_initial_state():
    return {
        "has_home": False,
        "has_bank": False,
        "has_mobile": False,
        "has_utility": False,
        "balance": 500, # Initial cash
        "orders": [], # List of pending orders
        "delivered_orders": [],
        "is_sick": False,
        "card_frozen": False,
        "has_invest": False
    }

def generate_chain(chain_id, min_length=5, max_length=15):
    state = get_initial_state()
    chain_tasks = []
    
    # 强制初始阶段 (Bootstrap Phase)
    # Most agents need a home and bank account to do anything interesting.
    # We force these if they are valid candidates to kickstart the chain.
    bootstrap_tasks = ["A1-find-home", "A4-mobile-plan", "A2-bank-opening"]
    for task_id in bootstrap_tasks:
        if TASKS_DB[task_id]["pre"](state):
            chain_tasks.append(task_id)
            TASKS_DB[task_id]["effect"](state)

    # 随机游走阶段 (Random Walk Phase)
    target_length = random.randint(min_length, max_length)
    
    while len(chain_tasks) < target_length:
        # Find all valid next tasks
        candidates = []
        for tid, tmeta in TASKS_DB.items():
            # Don't repeat non-repeatable setup tasks
            if tid in chain_tasks and tid.startswith("A"): continue
            if tid in chain_tasks and tid.startswith("I1"): continue
            if tid in chain_tasks and tid.startswith("D6"): continue
            
            if tmeta["pre"](state):
                candidates.append(tid)
        
        if not candidates:
            break # Dead end
            
        # Weighted selection (Prioritize Life(B) and Work(F) over Crisis(M))
        weights = []
        for tid in candidates:
            fam = TASKS_DB[tid]["family"]
            if fam == "M": w = 1  # Crisis rare
            elif fam == "Z": w = 3 # Advanced common
            elif fam == "B": w = 5 # Consumption very common
            else: w = 3
            weights.append(w)
            
        next_task = random.choices(candidates, weights=weights, k=1)[0]
        chain_tasks.append(next_task)
        TASKS_DB[next_task]["effect"](state)
        
        # Safety break for infinite loops or weird states
        if len(chain_tasks) > max_length * 1.5:
            break

    return {
        "chain_id": chain_id,
        "description": f"A generated sequence of {len(chain_tasks)} tasks starting with setup and evolving.",
        "tasks": chain_tasks,
        "final_state_summary": {k:v for k,v in state.items() if v}
    }

def main():
    total_chains = 5000
    all_scenarios = []
    
    print(f"Generating {total_chains} scenarios...")
    
    for i in range(total_chains):
        cid = f"CHAIN-{i+1:04d}"
        scenario = generate_chain(cid)
        all_scenarios.append(scenario)
        
    # Save to file
    output_file = "generated_scenarios.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_scenarios, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Successfully generated {len(all_scenarios)} scenarios in {output_file}")
    
    # Statistics
    lengths = [len(s['tasks']) for s in all_scenarios]
    avg_len = sum(lengths) / len(lengths)
    max_len = max(lengths)
    min_len = min(lengths)
    
    print(f"\n📊 Statistics:")
    print(f"  Total Chains: {len(all_scenarios)}")
    print(f"  Avg Length:   {avg_len:.2f} tasks")
    print(f"  Max Length:   {max_len} tasks")
    print(f"  Min Length:   {min_len} tasks")
    
    # Distribution
    from collections import Counter
    dist = Counter(lengths)
    print("\n  Length Distribution:")
    for length in sorted(dist.keys()):
        count = dist[length]
        print(f"    Length {length:2d}: {count:4d} ({count/total_chains*100:.1f}%)")

    # Print sample
    print("\n--- Sample Scenario ---")
    sample = all_scenarios[0]
    print(f"ID: {sample['chain_id']}")
    print("Tasks:", " -> ".join(sample['tasks']))
    print("Final State:", sample['final_state_summary'])

if __name__ == "__main__":
    main()
