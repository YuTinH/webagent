import json
import random
from collections import Counter
import datetime as dt_module

# ==========================================
# 1. 全任务配置库 (The Complete Task DB)
# ==========================================

TASKS_DB = {
    # --- A. Housing & Infrastructure (Newcomer) ---
    "A1-find-home": {
        "family": "A", "theme": "newcomer",
        "pre": lambda s: not s.get("has_home"),
        "options": ["city", "suburb"],
        "logic": {
            "city": {"instr": "在市中心租一套公寓。", "criteria": ["mem('housing.lease.last.id') == 'PROP-101'"], "effect": {"has_home": True, "location": "city"}},
            "suburb": {"instr": "在郊区租一套房子。", "criteria": ["mem('housing.lease.last.id') == 'PROP-102'"], "effect": {"has_home": True, "location": "suburb"}}
        }
    },
    "A2-bank-opening": {
        "family": "A", "theme": "newcomer",
        "pre": lambda s: s.get("has_home") and not s.get("has_bank"),
        "options": ["standard"],
        "logic": {"standard": {"instr": "开立银行账户。", "criteria": ["mem('bank.account.status') == 'active'"], "effect": {"has_bank": True, "balance": 1000}}}
    },
    "A3-utility-setup": {
        "family": "A", "theme": "newcomer",
        "pre": lambda s: s.get("has_home") and not s.get("has_utility"),
        "options": ["setup"],
        "logic": {"setup": {"instr": "开通水电服务。", "criteria": ["mem('contracts.electricity.status') == 'active'"], "effect": {"has_utility": True}}}
    },
    "A4-mobile-plan": {
        "family": "A", "theme": "newcomer",
        "pre": lambda s: not s.get("has_mobile"),
        "options": ["starter"],
        "logic": {"starter": {"instr": "办理手机套餐。", "criteria": ["mem('mobile.subscription.status') == 'active'"], "effect": {"has_mobile": True}}}
    },
    "A5-lease-management": {
        "family": "A", "theme": "newcomer",
        "pre": lambda s: s.get("has_home"),
        "options": ["renew"],
        "logic": {"renew": {"instr": "续签租房合同。", "criteria": ["mem('housing.leases.PROP-101.end_date') != ''"], "effect": {}}}
    },
    "A6-address-proof": {
        "family": "A", "theme": "newcomer",
        "pre": lambda s: s.get("has_home"),
        "options": ["download"],
        "logic": {"download": {"instr": "下载地址证明文件。", "criteria": ["mem('identity.address_verified') == 'true'"], "effect": {"verified": True}}}
    },

    # --- B. Consumption (Daily Life) ---
    "B1-shopping": {
        "family": "B", "theme": "daily",
        "pre": lambda s: s.get("has_bank") and not s.get("card_frozen"),
        "options": ["mouse", "keyboard"],
        "logic": {
            "mouse": {"instr": "购买无线鼠标。", "criteria": ["mem('shop.orders.last.total') == 29.99"], "effect": {"pending_order": True, "orders_count": 1, "last_order_type": "shop"}},
            "keyboard": {"instr": "购买机械键盘。", "criteria": ["mem('shop.orders.last.total') == 94.99"], "effect": {"pending_order": True, "orders_count": 1, "last_order_type": "shop"}}
        }
    },
    "B2-fresh-subscription": {
        "family": "B", "theme": "daily",
        "pre": lambda s: s.get("has_home"),
        "options": ["subscribe"],
        "logic": {"subscribe": {"instr": "订阅生鲜配送。", "criteria": ["mem('food.subscriptions.last.status') == 'active'"], "effect": {"has_sub": True}}}
    },
    "B3-housekeeping-booking": {
        "family": "B", "theme": "daily",
        "pre": lambda s: s.get("has_home"),
        "options": ["book"],
        "logic": {"book": {"instr": "预约保洁服务。", "criteria": ["mem('local_services.housekeeping_bookings.last.status') == 'confirmed'"], "effect": {}}}
    },
    "B4-food-delivery": {
        "family": "B", "theme": "daily",
        "pre": lambda s: s.get("has_home"),
        "options": ["order"],
        "logic": {"order": {"instr": "点一份外卖。", "criteria": ["mem('food.order.last.status') == 'pending'"], "effect": {"pending_order": True, "orders_count": 1, "last_order_type": "food"}}}
    },
    "B5-coupon-management": {
        "family": "B", "theme": "daily",
        "pre": lambda s: True,
        "options": ["add"],
        "logic": {"add": {"instr": "添加一张优惠券。", "criteria": ["mem('shop.coupons.last.status') == 'active'"], "effect": {"has_coupon": True}}}
    },
    "B6-price-protection": {
        "family": "B", "theme": "daily",
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["apply"],
        "logic": {"apply": {"instr": "申请价格保护。", "criteria": [], "effect": {}}}
    },
    "B7-second-hand-sale": {
        "family": "B", "theme": "daily",
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["sell", "service"],
        "logic": {
            "sell": {"instr": "出售闲置物品。", "criteria": ["mem('market.listed_items.last.category') == 'home'"], "effect": {"balance": 50}},
            "service": {"instr": "发布专业服务。", "criteria_fn": lambda s: [f"mem('market.listed_items.last.price') == '{200.0 if s.get('certified') else 100.0}'"], "effect": {"balance": 100}}
        }
    },

    # --- C. Support (Crisis/Service) ---
    "C1-logistics-fix": {
        "family": "C", "theme": "crisis",
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["contact"],
        "logic": {"contact": {"instr": "联系物流客服。", "criteria": [], "effect": {}}}
    },
    "C2-return": {
        "family": "C", "theme": "daily",
        "pre": lambda s: s.get("has_shop_delivered"), # FIX: Only for shop items
        "options": ["return"],
        "logic": {"return": {"instr": "申请退货。", "criteria": ["mem('returns.last.state') == 'submitted'"], "effect": {"delivered_count": -1}}}
    },
    "C3-subscription-refund": {
        "family": "C", "theme": "daily",
        "pre": lambda s: s.get("has_sub"),
        "options": ["cancel"],
        "logic": {"cancel": {"instr": "取消订阅并退款。", "criteria": [], "effect": {"has_sub": False}}}
    },
    "C4-warranty-claim": {
        "family": "C", "theme": "crisis",
        "pre": lambda s: s.get("has_shop_delivered"), # FIX: Only for shop items
        "options": ["claim"],
        "logic": {"claim": {"instr": "申请保修。", "criteria": [], "effect": {}}}
    },
    "C5-leave-review": {
        "family": "C", "theme": "daily",
        "pre": lambda s: s.get("has_shop_delivered"), # FIX: Only for shop items
        "options": ["review"],
        "logic": {"review": {"instr": "评价商品。", "criteria": [], "effect": {}}}
    },

    # --- D. Finance (Daily/Career) ---
    "D1-check-balance": {
        "family": "D", "theme": "daily",
        "pre": lambda s: s.get("has_bank"),
        "options": ["check"],
        "logic": {"check": {"instr": "查询余额。", "criteria": [], "effect": {}}}
    },
    "D2-budget-report": {
        "family": "D", "theme": "daily",
        "pre": lambda s: s.get("has_bank"),
        "options": ["standard", "tight"],
        "logic": {
            "standard": {"instr": "查看并确认预算。", "criteria": ["mem('finance.budgets.food.limit') == 500"], "effect": {}},
            "tight": {
                "instr": "设定公用事业低预算。",
                "criteria_fn": lambda s: ["mem('finance.budgets.utilities.limit') == 200", "json('env','finance.warnings.0') includes 'Budget Alert'" if s.get('energy_cost') == 'high' else "mem('finance.budgets.utilities.limit') == 200"],
                "effect": {}
            }
        }
    },
    "D3-autopay": {
        "family": "D", "theme": "daily",
        "pre": lambda s: s.get("has_bank") and s.get("has_utility"),
        "options": ["setup"],
        "logic": {"setup": {"instr": "设置自动缴费。", "criteria": ["mem('autopay.utility.status') == 'active'"], "effect": {"autopay": True}}}
    },
    "D4-card-replacement": {
        "family": "D", "theme": "crisis",
        "pre": lambda s: s.get("card_frozen"),
        "options": ["replace"],
        "logic": {"replace": {"instr": "补办银行卡。", "criteria": ["mem('payment.cards[0].status') == 'active'"], "effect": {"card_frozen": False}}}
    },
    "D5-tax-preparation": {
        "family": "D", "theme": "career",
        "pre": lambda s: s.get("has_bank"),
        "options": ["upload"],
        "logic": {"upload": {"instr": "上传税务文件。", "criteria": ["mem('finance.tax_documents.last.status') == 'pending'"], "effect": {}}}
    },
    "D6-investment-account": {
        "family": "D", "theme": "career",
        "pre": lambda s: s.get("has_bank") and s.get("balance", 0) > 500,
        "options": ["open"],
        "logic": {"open": {"instr": "开通投资账户。", "criteria": ["mem('finance.investment_accounts.last.status') == 'active'"], "effect": {"has_invest": True}}}
    },

    # --- E. Travel (Career/Leisure) ---
    "E1-commute-route": {
        "family": "E", "theme": "career",
        "pre": lambda s: s.get("has_home"),
        "options": ["check"],
        "logic": {"check": {"instr": "查询通勤方案。", "criteria_fn": lambda s: [f"mem('commute.last_search.cost') == {120.0 if s.get('location')=='suburb' else 35.0}"], "effect": {"commute_checked": True}}}
    },
    "E2-transport-topup": {
        "family": "E", "theme": "career",
        "pre": lambda s: s.get("commute_checked") and s.get("has_bank"),
        "options": ["topup"],
        "logic": {"topup": {"instr": "充值公交卡。", "criteria": ["mem('transport.card.balance') > 25"], "effect": {}}}
    },
    "E3-airport-transfer": {
        "family": "E", "theme": "leisure",
        "pre": lambda s: s.get("has_bank"),
        "options": ["taxi", "drive"],
        "logic": {
            "taxi": {"instr": "预订机场专车。", "criteria": ["mem('trips.transfer.method') == 'taxi'"], "effect": {}},
            "drive": {"instr": "预订自驾停车。", "criteria_fn": lambda s: ["mem('trips.transfer.method') == 'self_drive'"] if not s.get('car_broken') else ["mem('trips.transfer.method') == 'taxi'"], "effect": {}}
        }
    },
    "E4-visa-requirements": {
        "family": "E", "theme": "leisure",
        "pre": lambda s: True,
        "options": ["check"],
        "logic": {"check": {"instr": "查询签证要求。", "criteria": ["mem('visa.search.last.destination') != ''"], "effect": {"knows_visa": True}}}
    },
    "E5-expense-report": {
        "family": "E", "theme": "career",
        "pre": lambda s: s.get("trip_booked"),
        "options": ["submit"],
        "logic": {"submit": {"instr": "提交差旅报销。", "criteria": ["mem('expenses.last.id') != ''"], "effect": {}}}
    },
    "E6-flight-change": {
        "family": "E", "theme": "leisure",
        "pre": lambda s: s.get("trip_booked"),
        "options": ["change"],
        "logic": {"change": {"instr": "改签航班。", "criteria": [], "effect": {}}}
    },
    "E7-long-haul-trip": {
        "family": "E", "theme": "leisure",
        "pre": lambda s: s.get("has_bank"),
        "options": ["book"],
        "logic": {"book": {"instr": "预订长途旅行（含签证）。", "criteria": ["mem('gov.visa_applications.last.status') == 'approved'"], "effect": {"trip_booked": True}}}
    },

    # --- F. Work (Career) ---
    "F1-calendar-aggregation": {
        "family": "F", "theme": "career",
        "pre": lambda s: True,
        "options": ["sync"],
        "logic": {"sync": {"instr": "同步工作日历。", "criteria": [], "effect": {}}}
    },
    "F2-conference-reg": {
        "family": "F", "theme": "career",
        "pre": lambda s: s.get("has_bank"),
        "options": ["register"],
        "logic": {"register": {"instr": "注册行业会议。", "criteria": [], "effect": {}}}
    },
    "F3-paper-submission": {
        "family": "F", "theme": "career",
        "pre": lambda s: True,
        "options": ["submit"],
        "logic": {"submit": {"instr": "提交论文。", "criteria_fn": lambda s: [f"mem('work.paper_submissions.last.status') == '{'rejected_low_quality' if s.get('energy_level', 100) < 50 else 'submitted'}'"], "effect": {}}}
    },
    "F4-email-tracking": {
        "family": "F", "theme": "career",
        "pre": lambda s: True,
        "options": ["track"],
        "logic": {"track": {"instr": "追踪重要邮件。", "criteria": [], "effect": {}}}
    },
    "F5-receipt-archive": {
        "family": "F", "theme": "career",
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["archive"],
        "logic": {"archive": {"instr": "归档发票。", "criteria": [], "effect": {}}}
    },

    # --- G. Health (Leisure/Crisis) ---
    "G1-doctor-appt": {
        "family": "G", "theme": "crisis",
        "pre": lambda s: s.get("is_sick"),
        "options": ["book"],
        "logic": {"book": {"instr": "预约看病。", "criteria": [], "effect": {"has_prescription": True}}}
    },
    "G2-insurance-policy": {
        "family": "G", "theme": "daily",
        "pre": lambda s: s.get("has_bank"),
        "options": ["buy"],
        "logic": {"buy": {"instr": "购买健康保险。", "criteria": [], "effect": {"has_insurance": True}}}
    },
    "G3-medical-claim": {
        "family": "G", "theme": "crisis",
        "pre": lambda s: s.get("has_insurance") and s.get("is_sick"),
        "options": ["claim"],
        "logic": {"claim": {"instr": "申请医疗理赔。", "criteria": [], "effect": {}}}
    },
    "G4-gym-membership": {
        "family": "G", "theme": "daily", # Actually Pharmacy Refill
        "pre": lambda s: s.get("has_prescription"),
        "options": ["refill"],
        "logic": {"refill": {"instr": "按处方买药。", "criteria": [], "effect": {"is_sick": False}}}
    },
    "G5-health-plan": {
        "family": "G", "theme": "leisure",
        "pre": lambda s: True,
        "options": ["plan"],
        "logic": {"plan": {"instr": "制定健康计划。", "criteria": [], "effect": {}}}
    },
    "G6-vaccine-mgmt": {
        "family": "G", "theme": "leisure",
        "pre": lambda s: True,
        "options": ["book"],
        "logic": {"book": {"instr": "预约疫苗。", "criteria": [], "effect": {}}}
    },

    # --- H. Gov (Newcomer) ---
    "H1-address-change": {
        "family": "H", "theme": "newcomer",
        "pre": lambda s: s.get("has_home"),
        "options": ["update"],
        "logic": {"update": {"instr": "更新市政地址。", "criteria": ["mem('gov.profile.address.verified') == 'true'"], "effect": {}}}
    },
    "H2-vehicle-address-update": {
        "family": "H", "theme": "newcomer",
        "pre": lambda s: s.get("has_home"),
        "options": ["update"],
        "logic": {"update": {"instr": "更新车辆注册地址。", "criteria": [], "effect": {}}}
    },
    "H3-permit-renewal": {
        "family": "H", "theme": "daily",
        "pre": lambda s: True,
        "options": ["renew"],
        "logic": {"renew": {"instr": "续期居住许可。", "criteria": [], "effect": {}}}
    },
    "H4-parking-permit": {
        "family": "H", "theme": "daily",
        "pre": lambda s: s.get("has_home"),
        "options": ["apply"],
        "logic": {"apply": {"instr": "申请停车证。", "criteria": ["mem('permits.parking.state') == 'submitted'"], "effect": {}}}
    },

    # --- I. Repair (Daily) ---
    "I1-smart-bulb-setup": {
        "family": "I", "theme": "daily",
        "pre": lambda s: s.get("has_utility"),
        "options": ["setup"],
        "logic": {"setup": {"instr": "设置智能灯泡。", "criteria": ["mem('devices.BULB-001.status') == 'active'"], "effect": {}}}
    },
    "I2-appliance-repair": {
        "family": "I", "theme": "daily",
        "pre": lambda s: s.get("has_home"),
        "options": ["oven", "car"],
        "logic": {
            "oven": {"instr": "维修烤箱。", "criteria": ["mem('appliance_repairs.requests.last.appliance') == 'Oven'"], "effect": {}},
            "car": {"instr": "维修车辆。", "criteria": ["mem('appliance_repairs.requests.last.appliance') == 'My Car'"], "effect": {"car_broken": True}}
        }
    },
    "I4-smart-meter": {
        "family": "I", "theme": "daily",
        "pre": lambda s: s.get("has_utility"),
        "options": ["read"],
        "logic": {"read": {"instr": "提交电表读数。", "criteria": [], "effect": {}}}
    },
    "I5-energy-optimize": {
        "family": "I", "theme": "daily",
        "pre": lambda s: s.get("has_utility"),
        "options": ["green", "premium"],
        "logic": {
            "green": {"instr": "切换绿色套餐。", "criteria": ["mem('meters.M-321.plan') == 'green_offpeak'"], "effect": {"energy_cost": "low"}},
            "premium": {"instr": "切换全天候套餐。", "criteria": ["mem('meters.M-321.plan') == 'premium_flat_rate'"], "effect": {"energy_cost": "high"}}
        }
    },

    # --- J. Learning (Career) ---
    "J1-course-enroll": {
        "family": "J", "theme": "career",
        "pre": lambda s: True,
        "options": ["enroll"],
        "logic": {"enroll": {"instr": "选修写作课程。", "criteria": ["mem('courses.DL101.state') == 'enrolled'"], "effect": {}}}
    },
    "J2-library-service": {
        "family": "J", "theme": "career",
        "pre": lambda s: True,
        "options": ["borrow"],
        "logic": {"borrow": {"instr": "借阅图书。", "criteria": [], "effect": {}}}
    },
    "J3-event-tickets": {
        "family": "J", "theme": "leisure",
        "pre": lambda s: s.get("has_bank"),
        "options": ["buy"],
        "logic": {"buy": {"instr": "购买演出门票。", "criteria": [], "effect": {}}}
    },
    "J4-gear-rental": {
        "family": "J", "theme": "leisure",
        "pre": lambda s: s.get("has_bank"),
        "options": ["rent"],
        "logic": {"rent": {"instr": "租赁滑雪装备。", "criteria": ["mem('gear.rentals.last.status') == 'available'"], "effect": {}}}
    },
    "J5-skill-certification": {
        "family": "J", "theme": "career",
        "pre": lambda s: True,
        "options": ["certify"],
        "logic": {"certify": {"instr": "申请专业认证。", "criteria": ["mem('world_state.skills.certified') == 'True'"], "effect": {"certified": True}}}
    },

    # --- K. Social (Leisure) ---
    "K1-plan-party": {
        "family": "K", "theme": "leisure",
        "pre": lambda s: True,
        "options": ["join"],
        "logic": {"join": {"instr": "加入兴趣群组。", "criteria": [], "effect": {}}}
    },
    "K2-roommate-split": {
        "family": "K", "theme": "daily",
        "pre": lambda s: s.get("has_home"),
        "options": ["split"],
        "logic": {"split": {"instr": "分摊房租。", "criteria": [], "effect": {}}}
    },
    "K3-charity-donation": {
        "family": "K", "theme": "leisure",
        "pre": lambda s: s.get("has_bank"),
        "options": ["donate"],
        "logic": {"donate": {"instr": "慈善捐赠。", "criteria": [], "effect": {}}}
    },

    # --- L. Privacy (Crisis) ---
    "L1-password-manager": {
        "family": "L", "theme": "crisis",
        "pre": lambda s: True,
        "options": ["update"],
        "logic": {"update": {"instr": "更新密码管理器。", "criteria": [], "effect": {}}}
    },
    "L2-data-deletion": {
        "family": "L", "theme": "crisis",
        "pre": lambda s: True,
        "options": ["delete"],
        "logic": {"delete": {"instr": "请求数据删除。", "criteria": [], "effect": {}}}
    },
    "L3-security-audit": {
        "family": "L", "theme": "crisis",
        "pre": lambda s: True,
        "options": ["audit"],
        "logic": {"audit": {"instr": "执行安全审计。", "criteria": [], "effect": {}}}
    },
    "L4-2fa-device": {
        "family": "L", "theme": "crisis",
        "pre": lambda s: s.get("has_mobile"),
        "options": ["change"],
        "logic": {"change": {"instr": "更换2FA设备。", "criteria": [], "effect": {}}}
    },

    # --- M. Crisis (Triggers) ---
    "M1-lost-card": {
        "family": "M", "theme": "crisis",
        "pre": lambda s: s.get("has_bank") and not s.get("card_frozen"),
        "options": ["freeze"],
        "logic": {"freeze": {"instr": "挂失银行卡。", "criteria": ["mem('payments.cards.1234.state') == 'blocked'"], "effect": {"card_frozen": True}}}
    },
    "M2-supply-disruption": {
        "family": "M", "theme": "crisis",
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["check"],
        "logic": {"check": {"instr": "检查物流中断。", "criteria": [], "effect": {}}}
    },
    "M3-illness-reporting": {
        "family": "M", "theme": "crisis",
        "pre": lambda s: not s.get("is_sick"),
        "options": ["report"],
        "logic": {"report": {"instr": "上报生病。", "criteria": [], "effect": {"is_sick": True, "energy_level": 20}}}
    },

    # --- Z. Advanced (Leisure/Daily) ---
    "Z1-order-arrival": {
        "family": "Z", "theme": "daily",
        "pre": lambda s: s.get("pending_order") and not s.get("card_frozen"),
        "options": ["wait"],
        "logic": {
            "wait": {
                "instr": "等待订单送达。", 
                "criteria_fn": lambda s: [f"mem('{'shop.orders.last.state' if s.get('last_order_type', 'shop') == 'shop' else 'food.order.last.status'}') == 'delivered'"], 
                "effect_fn": lambda s: {"pending_order": False, "delivered_count": 1, "has_shop_delivered": True} if s.get('last_order_type') == 'shop' else {"pending_order": False, "delivered_count": 1}
            }
        }
    },
    "Z2-investment-growth": {
        "family": "Z", "theme": "career",
        "pre": lambda s: s.get("has_invest"),
        "options": ["wait"],
        "logic": {"wait": {"instr": "查看投资收益。", "criteria": [], "effect": {}}}
    },
    "Z3-live-auction": {
        "family": "Z", "theme": "leisure",
        "pre": lambda s: s.get("has_bank"),
        "options": ["bid"],
        "logic": {"bid": {"instr": "参与竞拍。", "criteria": ["mem('auctions.VASE-001.highest_bidder') == 'user'"], "effect": {}}}
    },
    "Z4-email-calendar": {
        "family": "Z", "theme": "career",
        "pre": lambda s: True,
        "options": ["sync"],
        "logic": {"sync": {"instr": "从邮件同步日历。", "criteria": [], "effect": {}}}
    },
    "Z5-password-recovery": {
        "family": "Z", "theme": "crisis",
        "pre": lambda s: s.get("has_mobile"),
        "options": ["recover"],
        "logic": {"recover": {"instr": "找回密码。", "criteria": [], "effect": {}}}
    },
    "Z6-customer-service": {
        "family": "Z", "theme": "daily",
        "pre": lambda s: True,
        "options": ["chat"],
        "logic": {"chat": {"instr": "咨询人工客服。", "criteria": [], "effect": {}}}
    }
}

# ==========================================
# 2. 生成引擎 (Generator Engine)
# ==========================================

def get_initial_state(theme):
    state = {
        "has_home": False, "has_bank": False, "has_mobile": False, "has_utility": False,
        "balance": 1000, "orders": [], "delivered_count": 0, "orders_count": 0,
        "is_sick": False, "card_frozen": False, "has_invest": False,
        "location": None, "pending_order": False, "energy_cost": "low", 
        "certified": False, "energy_level": 100, "trip_booked": False,
        "commute_checked": False, "has_sub": False, "has_coupon": False,
        "has_shop_delivered": False, "last_order_type": None
    }
    if theme != "newcomer":
        state.update({
            "has_home": True, "has_bank": True, "has_mobile": True, "has_utility": True,
            "location": "city" if random.random() > 0.5 else "suburb",
            "balance": 5000
        })
    return state

def generate_chain(chain_id, target_theme, force_task=None):
    initial_state = get_initial_state(target_theme)
    state = initial_state.copy()
    steps = []
    task_counts = {}
    
    bootstrap_options = {
        "newcomer": ["A1-find-home", "A4-mobile-plan", "A2-bank-opening"],
        "daily":    ["B2-fresh-subscription", "D1-check-balance", "I4-smart-meter", "B4-food-delivery"],
        "career":   ["F1-calendar-aggregation", "E1-commute-route", "J5-skill-certification", "D5-tax-preparation"],
        "leisure":  ["K1-plan-party", "E4-visa-requirements", "J3-event-tickets", "G5-health-plan"],
        "crisis":   ["M1-lost-card", "M3-illness-reporting", "L1-password-manager", "L3-security-audit"]
    }
    
    starters = bootstrap_options.get(target_theme, [])
    valid_starters = [t for t in starters if TASKS_DB[t]["pre"](state)]
    
    if valid_starters:
        tid = random.choice(valid_starters)
        cfg = TASKS_DB[tid]
        opt = random.choice(cfg["options"])
        logic = cfg["logic"][opt]
        
        crit = logic.get("criteria", [])
        if "criteria_fn" in logic:
            crit = logic["criteria_fn"](state)
            
        steps.append({"task_id": tid, "instruction": logic["instr"], "success_criteria": crit})
        
        if "effect_fn" in logic:
            state.update(logic["effect_fn"](state))
        else:
            state.update(logic["effect"])
            
        task_counts[tid] = 1

    if force_task and force_task not in task_counts:
        # PAVING helper
        def pave(tid, opt):
            cfg = TASKS_DB[tid]
            logic = cfg["logic"][opt]
            crit = logic["criteria_fn"](state) if "criteria_fn" in logic else logic.get("criteria", [])
            steps.append({"task_id": tid, "instruction": logic["instr"], "success_criteria": crit})
            if "effect_fn" in logic:
                state.update(logic["effect_fn"](state))
            else:
                state.update(logic["effect"])
            task_counts[tid] = 1

        if force_task in ["C2-return", "C4-warranty-claim", "C5-leave-review"] and not state.get("has_shop_delivered"):
             if not state.get("pending_order"):
                pave("B1-shopping", "mouse")
             pave("Z1-order-arrival", "wait")

        if force_task == "G4-gym-membership" and not state.get("has_prescription"):
             if not state.get("is_sick"):
                pave("M3-illness-reporting", "report")
             pave("G1-doctor-appt", "book")

        if force_task == "G3-medical-claim" and not state.get("has_insurance"):
             if not state.get("has_bank"):
                 pave("A2-bank-opening", "standard")
             pave("G2-insurance-policy", "buy")
             if not state.get("is_sick"):
                pave("M3-illness-reporting", "report")

        if force_task in ["I4-smart-meter", "I5-energy-optimize", "I1-smart-bulb-setup", "D3-autopay"] and not state.get("has_utility"):
             if not state.get("has_home"):
                 pave("A1-find-home", "city")
             pave("A3-utility-setup", "setup")

        if TASKS_DB[force_task]["pre"](state):
            cfg = TASKS_DB[force_task]
            opt = random.choice(cfg["options"])
            logic = cfg["logic"][opt]
            crit = logic["criteria_fn"](state) if "criteria_fn" in logic else logic.get("criteria", [])
            steps.append({"task_id": force_task, "instruction": logic["instr"], "success_criteria": crit})
            if "effect_fn" in logic:
                state.update(logic["effect_fn"](state))
            else:
                state.update(logic["effect"])
            task_counts[force_task] = 1

    target_length = random.randint(6, 10)
    while len(steps) < target_length:
        last_tid = steps[-1]['task_id'] if steps else None
        candidates = []
        for tid, cfg in TASKS_DB.items():
            if not cfg["pre"](state): continue
            if tid == last_tid: continue
            if task_counts.get(tid, 0) >= 2: continue
            weight = 1
            if cfg["theme"] == target_theme: weight = 50
            if tid in ["D3-autopay", "I1-smart-bulb-setup", "I4-smart-meter", "I5-energy-optimize", "G3-medical-claim"]: weight += 50
            candidates.append((tid, weight))
        if not candidates: break
        tid = random.choices([c[0] for c in candidates], weights=[c[1] for c in candidates], k=1)[0]
        cfg = TASKS_DB[tid]
        opt = random.choice(cfg["options"])
        if tid == "E3-airport-transfer" and state.get("car_broken"): opt = "taxi"
        logic = cfg["logic"][opt]
        crit = logic["criteria_fn"](state) if "criteria_fn" in logic else logic.get("criteria", [])
        steps.append({"task_id": tid, "instruction": logic["instr"], "success_criteria": crit})
        if "effect_fn" in logic:
            state.update(logic["effect_fn"](state))
        else:
            state.update(logic["effect"])
        task_counts[tid] = task_counts.get(tid, 0) + 1
    return {"chain_id": chain_id, "theme": target_theme, "initial_state": initial_state, "steps": steps}

def main():
    themes = ["newcomer", "daily", "career", "leisure", "crisis"]
    output_dir = "."
    all_tasks = list(TASKS_DB.keys())
    visited_global = set()
    print("🚀 Generating stratified datasets (500 items)...")
    for theme in themes:
        print(f"  - Generating {theme}...")
        scenarios = []
        for i in range(500): # Canditates
            unvisited = [t for t in all_tasks if t not in visited_global]
            force = random.choice(unvisited) if unvisited else None
            s = generate_chain(f"SCENARIO-{theme.upper()}-{i:03d}", theme, force)
            scenarios.append(s)
            for step in s['steps']: visited_global.add(step['task_id'])
        sampled = random.sample(scenarios, 100)
        fname = f"{output_dir}/sampled_{theme}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(sampled, f, indent=2, ensure_ascii=False)
        print(f"    Saved 100 scenarios to {fname}")
    print(f"✅ All themes generated. Global coverage: {len(visited_global)}/{len(all_tasks)}")

if __name__ == "__main__":
    main()