import json
import random

# ==========================================
# 1. 带参数的任务定义 (Parametric Task DB)
# ==========================================

TASKS_CONFIG = {
    "A1-find-home": {
        "family": "A",
        "pre": lambda s: not s.get("has_home"),
        "options": ["city", "suburb"],
        "logic": {
            "city": {
                "instr": "请在 **市中心** 租一套公寓（如中央大街）。",
                "criteria": ["mem('housing.lease.last.id') == 'PROP-101'"],
                "effect": {"location": "city_center", "has_home": True}
            },
            "suburb": {
                "instr": "由于预算有限，请在 **郊区** 租一套房子（如阳光海岸）。",
                "criteria": ["mem('housing.lease.last.id') == 'PROP-102'"],
                "effect": {"location": "suburban", "has_home": True}
            }
        }
    },
    "A2-bank-opening": {
        "family": "A",
        "pre": lambda s: s.get("has_home") and not s.get("has_bank"),
        "options": ["standard"],
        "logic": {
            "standard": {
                "instr": "在 Nebula Bank 开设一个新账户，使用姓名 'Alex Chen' 并开启 2FA。",
                "criteria": ["mem('bank.account.status') == 'active'", "mem('bank.account.2fa') == '1'"],
                "effect": {"has_bank": True, "balance": 1000}
            }
        }
    },
    "E1-commute-route": {
        "family": "E",
        "pre": lambda s: s.get("has_home"),
        "options": ["check"],
        "logic": {
            "check": {
                "instr": "查询从家到办公室的通勤方案。",
                "criteria_fn": lambda s: [f"mem('commute.last_search.cost') == {120.0 if s.get('location')=='suburban' else 35.0}"],
                "effect": {"knows_commute": True}
            }
        }
    },
    "B1-shopping": {
        "family": "B",
        "pre": lambda s: s.get("has_bank") and not s.get("card_frozen"),
        "options": ["mouse", "keyboard"],
        "logic": {
            "mouse": {
                "instr": "在商城购买一个 'Wireless Mouse'。",
                "criteria": ["mem('shop.orders.last.total') == 29.99"],
                "effect": {"pending_order": True, "orders_count": 1} # Incremental logic handled in generator
            },
            "keyboard": {
                "instr": "在商城购买一个 'Mechanical Keyboard'。",
                "criteria": ["mem('shop.orders.last.total') == 94.99"],
                "effect": {"pending_order": True, "orders_count": 1}
            }
        }
    },
    "Z1-order-arrival": {
        "family": "Z",
        "pre": lambda s: s.get("pending_order") and not s.get("card_frozen"),
        "options": ["wait"],
        "logic": {
            "wait": {
                "instr": "使用时间旅行功能快进 3 天，并确认订单已送达。",
                "criteria": ["mem('shop.orders.last.state') == 'delivered'"],
                "effect": {"pending_order": False, "has_item": True, "delivered_count": 1}
            }
        }
    },
    "M1-lost-card": {
        "family": "M",
        "pre": lambda s: s.get("has_bank") and not s.get("card_frozen"),
        "options": ["freeze"],
        "logic": {
            "freeze": {
                "instr": "不好！你的银行卡丢了，请立即登录并挂失结尾为 1234 的卡片。",
                "criteria": ["mem('payments.cards.1234.state') == 'blocked'"],
                "effect": {"card_frozen": True}
            }
        }
    },
    "D2-budget-report": {
        "family": "D",
        "pre": lambda s: s.get("has_bank"),
        "options": ["standard", "tight"],
        "logic": {
            "standard": {
                "instr": "查看本月预算报告，确认一切正常。",
                "criteria": ["mem('finance.budgets.food.limit') == 500"],
                "effect": {"budget_set": True}
            },
            "tight": {
                "instr": "设定一个较低的公用事业预算 (200元)。",
                "criteria_fn": lambda s: [
                    "mem('finance.budgets.utilities.limit') == 200",
                    "json('env','finance.warnings[0]').startswith('Budget Alert')" if s.get('energy_cost') == 'high' else "1 == 1"
                ],
                "effect": {"budget_set": True}
            }
        }
    },
    "E3-airport-transfer": {
        "family": "E",
        "pre": lambda s: s.get("has_bank"),
        "options": ["taxi", "drive"],
        "logic": {
            "taxi": {
                "instr": "预订机场接送（出租车）。",
                "criteria": ["mem('trips.transfer.method') == 'taxi'"],
                "effect": {}
            },
            "drive": {
                "instr": "预订机场接送（自驾）。",
                "criteria_fn": lambda s: ["mem('trips.transfer.method') == 'self_drive'"] if s.get('car_broken') != True else ["True"], 
                "effect": {}
            }
        }
    },
    "I2-appliance-repair": {
        "family": "I",
        "pre": lambda s: s.get("has_home"),
        "options": ["oven", "car"],
        "logic": {
            "oven": {
                "instr": "提交烤箱维修申请。",
                "criteria": ["mem('appliance_repairs.requests.last.appliance') == 'Oven'"],
                "effect": {}
            },
            "car": {
                "instr": "提交车辆故障维修申请。",
                "criteria": ["mem('appliance_repairs.requests.last.appliance') == 'My Car'"],
                "effect": {"car_broken": True}
            }
        }
    },
    "I5-energy-optimize": {
        "family": "I",
        "pre": lambda s: s.get("has_utility"),
        "options": ["green", "premium"],
        "logic": {
            "green": {
                "instr": "切换到绿色节能套餐。",
                "criteria": ["mem('meters.M-321.plan') == 'green_offpeak'"],
                "effect": {"energy_cost": "low"}
            },
            "premium": {
                "instr": "切换到全天候高性能套餐。",
                "criteria": ["mem('meters.M-321.plan') == 'premium_flat_rate'"],
                "effect": {"energy_cost": "high"}
            }
        }
    },
    "J4-gear-rental": {
        "family": "J",
        "pre": lambda s: s.get("has_bank"),
        "options": ["rent"],
        "logic": {
            "rent": {
                "instr": "租赁滑雪装备。",
                "criteria": ["mem('gear.rentals.last.status') == 'available'"],
                "effect": {}
            }
        }
    },
    "J5-skill-certification": {
        "family": "J",
        "pre": lambda s: True, # Anyone can certify
        "options": ["standard"],
        "logic": {
            "standard": {
                "instr": "完成专业技能认证。",
                "criteria": ["mem('world_state.skills.certified') == 'True'"],
                "effect": {"certified": True}
            }
        }
    },
    "B7-second-hand-sale": {
        "family": "B",
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["sell_item", "service"],
        "logic": {
            "sell_item": {
                "instr": "出售闲置物品。",
                "criteria": ["mem('market.listed_items.last.category') == 'home'"],
                "effect": {"balance": 50}
            },
            "service": {
                "instr": "发布专业咨询服务。",
                "criteria_fn": lambda s: [f"mem('market.listed_items.last.price') == '{200.0 if s.get('certified') else 100.0}'"],
                "effect": {"balance": 100}
            }
        }
    }
}

# ==========================================
# 2. 生成器引擎 (The Engine)
# ==========================================

def generate_dynamic_chain(cid, length=8):
    state = {
        "has_home": False, 
        "has_bank": False, 
        "location": None, 
        "balance": 500, 
        "pending_order": False,
        "orders_count": 0,
        "delivered_count": 0,
        "energy_cost": "low",
        "has_utility": True,
        "certified": False
    }
    steps = []
    task_counts = {} # Track frequency
    
    while len(steps) < length:
        # Filter:
        # 1. Preconditions met
        # 2. Not the same as last task (No consecutive repeats)
        # 3. Not appeared > 2 times in total
        
        last_tid = steps[-1]['task_id'] if steps else None
        
        candidates = []
        for tid, cfg in TASKS_CONFIG.items():
            if not cfg["pre"](state): continue
            if tid == last_tid: continue # Rule 2
            if task_counts.get(tid, 0) >= 2: continue # Rule 3
            
            candidates.append(tid)
            
        if not candidates: break
        
        tid = random.choice(candidates)
        cfg = TASKS_CONFIG[tid]
        
        # Update counts
        task_counts[tid] = task_counts.get(tid, 0) + 1
        
        # 随机选择一个选项 (Option)
        available_options = cfg["options"]
        if tid == "E3-airport-transfer" and state.get("car_broken"):
            available_options = ["taxi"]
            
        opt = random.choice(available_options)
        logic = cfg["logic"][opt]
        
        # 处理动态 Criteria (如果是函数则执行)
        if "criteria_fn" in logic:
            criteria = logic["criteria_fn"](state)
        else:
            criteria = logic["criteria"]
            
        # 记录这一步
        steps.append({
            "task_id": tid,
            "instruction": logic["instr"],
            "success_criteria": criteria
        })
        
        # 更新状态
        effect = logic["effect"]
        for k, v in effect.items():
            if k in ["orders_count", "delivered_count", "balance"]:
                if k == "balance":
                    state[k] += v
                else:
                    state[k] += v
            else:
                state[k] = v
        
    return {
        "chain_id": cid,
        "steps": steps
    }

def main():
    count = 5000
    scenarios = []
    print(f"Generating {count} dynamic scenarios...")
    
    for i in range(count):
        scenarios.append(generate_dynamic_chain(f"SCENARIO-{i+1:04d}"))
        
    with open("dynamic_scenarios_v2.json", "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Generated 5000 scenarios in dynamic_scenarios_v2.json")

if __name__ == "__main__":
    main()
