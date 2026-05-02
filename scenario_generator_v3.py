import json
import random
import argparse
import re
from collections import Counter
import datetime as dt_module
from copy import deepcopy
from typing import Any, Dict, List

# ==========================================
# 1. Full 71 Tasks with Difficulty (English Version)
# ==========================================

TASKS_DB = {
    "A1-find-home": {
        "family": "A", "theme": "newcomer", "difficulty": 3,
        "pre": lambda s: not s.get("has_home"),
        "options": ["city", "suburb"],
        "logic": {
            "city": {"instr": "Rent the cheapest apartment in the city center.", "criteria": ["mem('housing.lease.last.id') != ''"], "effect": {"has_home": True, "location": "city"}},
            "suburb": {"instr": "Rent the cheapest house in the suburb.", "criteria": ["mem('housing.lease.last.id') != ''"], "effect": {"has_home": True, "location": "suburb"}}
        }
    },
    "A2-bank-opening": { "family": "A", "theme": "newcomer", "difficulty": 1, "pre": lambda s: s.get("has_home") and not s.get("has_bank"), "options": ["standard"], "logic": {"standard": {"instr": "Open a new bank account.", "criteria": ["mem('bank.account.status') == 'active'"], "effect": {"has_bank": True, "balance": 1000}}} },
    "A3-utility-setup": { "family": "A", "theme": "newcomer", "difficulty": 1, "pre": lambda s: s.get("has_home") and not s.get("has_utility"), "options": ["setup"], "logic": {"setup": {"instr": "Set up electricity and water services.", "criteria": ["mem('contracts.electricity.status') == 'active'"], "effect": {"has_utility": True}}} },
    "A4-mobile-plan": { "family": "A", "theme": "newcomer", "difficulty": 1, "pre": lambda s: not s.get("has_mobile"), "options": ["starter"], "logic": {"starter": {"instr": "Apply for a mobile phone plan.", "criteria": ["mem('mobile.subscription.status') == 'active'"], "effect": {"has_mobile": True}}} },
    "A5-lease-management": { "family": "A", "theme": "newcomer", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["renew"], "logic": {"renew": {"instr": "Renew your rental lease agreement.", "criteria": ["mem('housing.leases.PROP-101.end_date') != ''"], "effect": {}}} },
    "A6-address-proof": { "family": "A", "theme": "newcomer", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["download"], "logic": {"download": {"instr": "Download the proof of address document.", "criteria": ["mem('identity.address_verified') == 'true'"], "effect": {"verified": True}}} },

    "B1-shopping": {
        "family": "B", "theme": "daily", "difficulty": 3,
        "pre": lambda s: s.get("has_bank"),
        "options": ["mouse", "keyboard"],
        "logic": {
            "mouse": {
                "instr": "Purchase a wireless mouse.",
                "criteria_fn": lambda s: [
                    "ANY[mem('shop.orders.last.total') == 29.99, ALL[json('env','world_state.financial_context.liquidity') == 'frozen', json('env','shop.orders.last.id') == null]]"
                ],
                "scoring_checkpoints_fn": lambda s: [
                    {
                        "id": "cp_purchase_success",
                        "name": "Purchase succeeds when liquidity not frozen",
                        "assertion": "mem('shop.orders.last.total') == 29.99",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "NOT[json('env','world_state.financial_context.liquidity') == 'frozen']",
                    },
                    {
                        "id": "cp_blocked_expected",
                        "name": "Payment blocked outcome when liquidity frozen",
                        "assertion": "json('env','shop.orders.last.id') == null",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "json('env','world_state.financial_context.liquidity') == 'frozen'",
                    },
                ],
                "effect_fn": lambda s: (
                    {"pending_order": True, "orders_count": 1, "last_order_type": "shop"}
                    if not s.get("card_frozen")
                    else {"pending_order": False, "orders_count": s.get("orders_count", 0), "last_order_type": s.get("last_order_type")}
                ),
            },
            "keyboard": {
                "instr": "Purchase a mechanical keyboard.",
                "criteria_fn": lambda s: [
                    "ANY[mem('shop.orders.last.total') == 94.99, ALL[json('env','world_state.financial_context.liquidity') == 'frozen', json('env','shop.orders.last.id') == null]]"
                ],
                "scoring_checkpoints_fn": lambda s: [
                    {
                        "id": "cp_purchase_success",
                        "name": "Purchase succeeds when liquidity not frozen",
                        "assertion": "mem('shop.orders.last.total') == 94.99",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "NOT[json('env','world_state.financial_context.liquidity') == 'frozen']",
                    },
                    {
                        "id": "cp_blocked_expected",
                        "name": "Payment blocked outcome when liquidity frozen",
                        "assertion": "json('env','shop.orders.last.id') == null",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "json('env','world_state.financial_context.liquidity') == 'frozen'",
                    },
                ],
                "effect_fn": lambda s: (
                    {"pending_order": True, "orders_count": 1, "last_order_type": "shop"}
                    if not s.get("card_frozen")
                    else {"pending_order": False, "orders_count": s.get("orders_count", 0), "last_order_type": s.get("last_order_type")}
                ),
            },
        }
    },
    "B2-fresh-subscription": { "family": "B", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["subscribe"], "logic": {"subscribe": {"instr": "Subscribe to a fresh food delivery plan.", "criteria": ["mem('food.subscriptions.last.status') == 'active'"], "effect": {"has_sub": True}}} },
    "B3-housekeeping-booking": { "family": "B", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["book"], "logic": {"book": {"instr": "Book a professional housekeeping service.", "criteria": ["mem('local_services.housekeeping_bookings.last.status') == 'confirmed'"], "effect": {}}} },
    "B4-food-delivery": { "family": "B", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["order"], "logic": {"order": {"instr": "Order a food delivery.", "criteria": ["mem('food.order.last.status') == 'pending'"], "effect": {"pending_order": True, "orders_count": 1, "last_order_type": "food"}}} },
    "B5-coupon-management": { "family": "B", "theme": "daily", "difficulty": 1, "pre": lambda s: True, "options": ["add"], "logic": {"add": {"instr": "Add a discount coupon.", "criteria": ["mem('shop.coupons.last.status') == 'active'"], "effect": {"has_coupon": True}}} },
    "B6-price-protection": { "family": "B", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("orders_count", 0) > 0, "options": ["apply"], "logic": {"apply": {"instr": "Apply for price protection.", "criteria": [], "effect": {}}} },
    "B7-second-hand-sale": {
        "family": "B", "theme": "daily", "difficulty": 3,
        "pre": lambda s: s.get("orders_count", 0) > 0,
        "options": ["sell", "service"],
        "logic": {
            "sell": {"instr": "List a second-hand item for sale.", "criteria": ["mem('market.listed_items.last.category') == 'home'"], "effect": {"balance": 50}},
            "service": {
                "instr": "Post a professional gig listing.",
                "criteria_fn": lambda s: [
                    "ANY[ALL[json('env','world_state.skills.certified') == true, mem('market.listed_items.last.price') == 200.0], ALL[NOT[json('env','world_state.skills.certified') == true], mem('market.listed_items.last.price') == 100.0]]"
                ],
                "scoring_checkpoints_fn": lambda s: [
                    {
                        "id": "cp_service_price_uncertified",
                        "name": "Default service pricing when uncertified",
                        "assertion": "mem('market.listed_items.last.price') == 100.0",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "NOT[json('env','world_state.skills.certified') == true]",
                    },
                    {
                        "id": "cp_service_price_certified",
                        "name": "Premium service pricing when certified",
                        "assertion": "mem('market.listed_items.last.price') == 200.0",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "json('env','world_state.skills.certified') == true",
                    },
                ],
                "effect": {"balance": 100},
            }
        }
    },

    "C1-logistics-fix": { "family": "C", "theme": "crisis", "difficulty": 3, "pre": lambda s: s.get("orders_count", 0) > 0, "options": ["contact"], "logic": {"contact": {"instr": "Contact logistics customer support.", "criteria": [], "effect": {}}} },
    "C2-return": { "family": "C", "theme": "daily", "difficulty": 3, "pre": lambda s: s.get("has_shop_delivered"), "options": ["return"], "logic": {"return": {"instr": "Apply for a product return.", "criteria": ["mem('returns.last.state') == 'submitted'"], "effect": {"delivered_count": -1}}} },
    "C3-subscription-refund": { "family": "C", "theme": "daily", "difficulty": 3, "pre": lambda s: s.get("has_sub"), "options": ["cancel"], "logic": {"cancel": {"instr": "Cancel subscription and request refund.", "criteria": [], "effect": {"has_sub": False}}} },
    "C4-warranty-claim": { "family": "C", "theme": "crisis", "difficulty": 3, "pre": lambda s: s.get("has_shop_delivered"), "options": ["claim"], "logic": {"claim": {"instr": "Submit a warranty claim.", "criteria": [], "effect": {}}} },
    "C5-leave-review": { "family": "C", "theme": "daily", "difficulty": 3, "pre": lambda s: s.get("has_shop_delivered"), "options": ["review"], "logic": {"review": {"instr": "Write a product review.", "criteria": [], "effect": {}}} },

    "D1-check-balance": { "family": "D", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_bank"), "options": ["check"], "logic": {"check": {"instr": "Check your bank account balance.", "criteria": [], "effect": {}}} },
    "D2-budget-report": {
        "family": "D", "theme": "daily", "difficulty": 2,
        "pre": lambda s: s.get("has_bank"), "options": ["tight"],
        "logic": {
            "tight": {
                "instr": "Set a tight budget for utilities.",
                "criteria_fn": lambda s: [
                    "mem('finance.budgets.utilities.limit') == 200",
                    "ANY[NOT[json('env','world_state.energy_context.projected_cost') == 'high'], json('env','finance.warnings.0') includes 'Budget Alert']",
                ],
                "scoring_checkpoints_fn": lambda s: [
                    {
                        "id": "cp_budget_limit_set",
                        "name": "Utility budget set",
                        "assertion": "mem('finance.budgets.utilities.limit') == 200",
                        "weight": 0.6,
                        "required": True,
                        "depends_on": [],
                    },
                    {
                        "id": "cp_budget_high_cost_warning",
                        "name": "Warning appears under high projected energy cost",
                        "assertion": "json('env','finance.warnings.0') includes 'Budget Alert'",
                        "weight": 0.4,
                        "required": True,
                        "depends_on": ["cp_budget_limit_set"],
                        "when": "json('env','world_state.energy_context.projected_cost') == 'high'",
                    },
                ],
                "effect": {},
            }
        }
    },
    "D3-autopay": { "family": "D", "theme": "daily", "difficulty": 2, "pre": lambda s: s.get("has_bank") and s.get("has_utility"), "options": ["setup"], "logic": {"setup": {"instr": "Enable autopay for utilities.", "criteria": ["mem('autopay.utility.status') == 'active'"], "effect": {"autopay": True}}} },
    "D4-card-replacement": { "family": "D", "theme": "crisis", "difficulty": 3, "pre": lambda s: s.get("card_frozen"), "options": ["replace"], "logic": {"replace": {"instr": "Request a new bank card replacement.", "criteria": ["mem('payment.cards[0].status') == 'active'"], "effect": {"card_frozen": False}}} },
    "D5-tax-preparation": { "family": "D", "theme": "career", "difficulty": 3, "pre": lambda s: s.get("has_bank"), "options": ["upload"], "logic": {"upload": {"instr": "Upload your tax documents.", "criteria": ["mem('finance.tax_documents.last.status') == 'pending'"], "effect": {}}} },
    "D6-investment-account": { "family": "D", "theme": "career", "difficulty": 3, "pre": lambda s: s.get("has_bank") and s.get("balance", 0) > 500, "options": ["open"], "logic": {"open": {"instr": "Open an investment account.", "criteria": ["mem('finance.investment_accounts.last.status') == 'active'"], "effect": {"has_invest": True}}} },

    "E1-commute-route": {
        "family": "E",
        "theme": "career",
        "difficulty": 2,
        "pre": lambda s: s.get("has_home"),
        "options": ["check"],
        "logic": {
            "check": {
                "instr": "Check your daily commute route and cost.",
                "criteria_fn": lambda s: [
                    "ANY[ALL[json('env','world_state.location_context.tier') == 'suburban', mem('commute.last_search.cost') == 120.0], ALL[NOT[json('env','world_state.location_context.tier') == 'suburban'], mem('commute.last_search.cost') == 35.0]]"
                ],
                "scoring_checkpoints_fn": lambda s: [
                    {
                        "id": "cp_commute_cost_city",
                        "name": "City-center commute cost baseline",
                        "assertion": "mem('commute.last_search.cost') == 35.0",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "NOT[json('env','world_state.location_context.tier') == 'suburban']",
                    },
                    {
                        "id": "cp_commute_cost_suburb",
                        "name": "Suburban commute cost uplift",
                        "assertion": "mem('commute.last_search.cost') == 120.0",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "json('env','world_state.location_context.tier') == 'suburban'",
                    },
                ],
                "effect": {"commute_checked": True},
            }
        },
    },
    "E2-transport-topup": { "family": "E", "theme": "career", "difficulty": 1, "pre": lambda s: s.get("commute_checked") and s.get("has_bank"), "options": ["topup"], "logic": {"topup": {"instr": "Top up your transport card balance.", "criteria": ["mem('transport.card.balance') > 25"], "effect": {}}} },
    "E3-airport-transfer": {
        "family": "E",
        "theme": "leisure",
        "difficulty": 2,
        "pre": lambda s: s.get("has_bank"),
        "options": ["taxi", "drive"],
        "logic": {
            "taxi": {
                "instr": "Book a taxi for airport transfer.",
                "criteria": ["mem('trips.transfer.method') == 'taxi'"],
                "effect": {},
            },
            "drive": {
                "instr": "Reserve airport parking for driving.",
                "criteria_fn": lambda s: [
                    "ANY[ALL[ANY[json('env','world_state.vehicle_context.condition') == 'under_repair', json('env','world_state.vehicle_context.condition') == 'broken'], mem('trips.transfer.method') == 'taxi'], ALL[NOT[ANY[json('env','world_state.vehicle_context.condition') == 'under_repair', json('env','world_state.vehicle_context.condition') == 'broken']], mem('trips.transfer.method') == 'self_drive']]"
                ],
                "scoring_checkpoints_fn": lambda s: [
                    {
                        "id": "cp_transfer_drive_normal",
                        "name": "Self-drive selected when vehicle is healthy",
                        "assertion": "mem('trips.transfer.method') == 'self_drive'",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "NOT[ANY[json('env','world_state.vehicle_context.condition') == 'under_repair', json('env','world_state.vehicle_context.condition') == 'broken']]",
                    },
                    {
                        "id": "cp_transfer_drive_fallback_taxi",
                        "name": "Taxi fallback selected when vehicle is under repair",
                        "assertion": "mem('trips.transfer.method') == 'taxi'",
                        "weight": 1.0,
                        "required": True,
                        "depends_on": [],
                        "when": "ANY[json('env','world_state.vehicle_context.condition') == 'under_repair', json('env','world_state.vehicle_context.condition') == 'broken']",
                    },
                ],
                "effect": {},
            },
        },
    },
    "E4-visa-requirements": { "family": "E", "theme": "leisure", "difficulty": 1, "pre": lambda s: True, "options": ["check"], "logic": {"check": {"instr": "Search for travel visa requirements.", "criteria": ["mem('visa.search.last.destination') != ''"], "effect": {"knows_visa": True}}} },
    "E5-expense-report": { "family": "E", "theme": "career", "difficulty": 2, "pre": lambda s: s.get("trip_booked"), "options": ["submit"], "logic": {"submit": {"instr": "Submit a travel expense report.", "criteria": ["mem('expenses.last.id') != ''"], "effect": {}}} },
    "E6-flight-change": { "family": "E", "theme": "leisure", "difficulty": 2, "pre": lambda s: s.get("trip_booked"), "options": ["change"], "logic": {"change": {"instr": "Modify your flight booking.", "criteria": [], "effect": {}}} },
    "E7-long-haul-trip": { "family": "E", "theme": "leisure", "difficulty": 3, "pre": lambda s: s.get("has_bank"), "options": ["book"], "logic": {"book": {"instr": "Book a long-haul trip including visa.", "criteria": ["mem('gov.visa_applications.last.status') == 'approved'"], "effect": {"trip_booked": True}}} },

    "F1-calendar-aggregation": { "family": "F", "theme": "career", "difficulty": 1, "pre": lambda s: True, "options": ["sync"], "logic": {"sync": {"instr": "Sync your work calendar events.", "criteria": [], "effect": {}}} },
    "F2-conference-reg": { "family": "F", "theme": "career", "difficulty": 1, "pre": lambda s: s.get("has_bank"), "options": ["register"], "logic": {"register": {"instr": "Register for an industry conference.", "criteria": [], "effect": {}}} },
    "F3-paper-submission": { "family": "F", "theme": "career", "difficulty": 2, "pre": lambda s: s.get("certified"), "options": ["submit"], "logic": {"submit": {"instr": "Submit a research paper.", "criteria": ["mem('work.paper_submissions.last.status') == 'submitted'"], "effect": {}}} },
    "F4-email-tracking": { "family": "F", "theme": "career", "difficulty": 1, "pre": lambda s: True, "options": ["track"], "logic": {"track": {"instr": "Track important work emails.", "criteria": [], "effect": {}}} },
    "F5-receipt-archive": { "family": "F", "theme": "career", "difficulty": 1, "pre": lambda s: s.get("orders_count", 0) > 0, "options": ["archive"], "logic": {"archive": {"instr": "Archive your shopping receipts.", "criteria": [], "effect": {}}} },

    "G1-doctor-appt": { "family": "G", "theme": "crisis", "difficulty": 1, "pre": lambda s: s.get("is_sick"), "options": ["book"], "logic": {"book": {"instr": "Book a doctor appointment.", "criteria": [], "effect": {"has_prescription": True}}} },
    "G2-insurance-policy": { "family": "G", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_bank"), "options": ["buy"], "logic": {"buy": {"instr": "Purchase a health insurance policy.", "criteria": [], "effect": {"has_insurance": True}}} },
    "G3-medical-claim": { "family": "G", "theme": "crisis", "difficulty": 2, "pre": lambda s: s.get("has_insurance") and s.get("is_sick"), "options": ["claim"], "logic": {"claim": {"instr": "Submit a medical insurance claim.", "criteria": [], "effect": {}}} },
    "G4-gym-membership": { "family": "G", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_prescription"), "options": ["refill"], "logic": {"refill": {"instr": "Refill prescription medications.", "criteria": [], "effect": {"is_sick": False}}} },
    "G5-health-plan": { "family": "G", "theme": "leisure", "difficulty": 1, "pre": lambda s: True, "options": ["plan"], "logic": {"plan": {"instr": "Create a personalized health plan.", "criteria": [], "effect": {}}} },
    "G6-vaccine-mgmt": { "family": "G", "theme": "leisure", "difficulty": 1, "pre": lambda s: True, "options": ["book"], "logic": {"book": {"instr": "Schedule a vaccine appointment.", "criteria": [], "effect": {}}} },

    "H1-address-change": { "family": "H", "theme": "newcomer", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["update"], "logic": {"update": {"instr": "Update your residential address.", "criteria": ["mem('gov.profile.address.verified') == 'true'"], "effect": {}}} },
    "H2-vehicle-address-update": { "family": "H", "theme": "newcomer", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["update"], "logic": {"update": {"instr": "Update your vehicle registration address.", "criteria": [], "effect": {}}} },
    "H3-permit-renewal": { "family": "H", "theme": "daily", "difficulty": 1, "pre": lambda s: True, "options": ["renew"], "logic": {"renew": {"instr": "Renew your residency permit.", "criteria": [], "effect": {}}} },
    "H4-parking-permit": { "family": "H", "theme": "daily", "difficulty": 2, "pre": lambda s: s.get("has_home"), "options": ["apply"], "logic": {"apply": {"instr": "Apply for a residential parking permit.", "criteria": ["mem('permits.parking.state') == 'submitted'"], "effect": {}}} },

    "I1-smart-bulb-setup": { "family": "I", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_utility"), "options": ["setup"], "logic": {"setup": {"instr": "Set up a new smart bulb device.", "criteria": ["mem('devices.BULB-001.status') == 'active'"], "effect": {}}} },
    "I2-appliance-repair": { "family": "I", "theme": "daily", "difficulty": 2, "pre": lambda s: s.get("has_home"), "options": ["oven", "car"], "logic": {"oven": {"instr": "Request an oven repair service.", "criteria": ["mem('appliance_repairs.requests.last.appliance') == 'Oven'"], "effect": {}}, "car": {"instr": "Request a vehicle repair service.", "criteria": ["mem('appliance_repairs.requests.last.appliance') == 'My Car'"], "effect": {"car_broken": True}}} },
    "I4-smart-meter": { "family": "I", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_utility"), "options": ["read"], "logic": {"read": {"instr": "Submit your smart meter reading.", "criteria": [], "effect": {}}} },
    "I5-energy-optimize": { "family": "I", "theme": "daily", "difficulty": 2, "pre": lambda s: s.get("has_utility"), "options": ["green", "premium"], "logic": {"green": {"instr": "Switch to an eco-friendly energy plan.", "criteria": ["mem('meters.M-321.plan') == 'green_offpeak'"], "effect": {"energy_cost": "low"}}, "premium": {"instr": "Switch to an all-day premium energy plan.", "criteria": ["mem('meters.M-321.plan') == 'premium_flat_rate'"], "effect": {"energy_cost": "high"}}} },

    "J1-course-enroll": { "family": "J", "theme": "career", "difficulty": 1, "pre": lambda s: (not s.get("is_sick")) and s.get("energy_level", 100) >= 50, "options": ["enroll"], "logic": {"enroll": {"instr": "Enroll in a creative writing course.", "criteria": ["mem('courses.DL101.state') == 'enrolled'"], "effect": {}}} },
    "J2-library-service": { "family": "J", "theme": "career", "difficulty": 1, "pre": lambda s: True, "options": ["borrow"], "logic": {"borrow": {"instr": "Borrow a book from the library.", "criteria": [], "effect": {}}} },
    "J3-event-tickets": { "family": "J", "theme": "leisure", "difficulty": 1, "pre": lambda s: s.get("has_bank"), "options": ["buy"], "logic": {"buy": {"instr": "Purchase tickets for a live show.", "criteria": [], "effect": {}}} },
    "J4-gear-rental": { "family": "J", "theme": "leisure", "difficulty": 2, "pre": lambda s: s.get("has_bank"), "options": ["rent"], "logic": {"rent": {"instr": "Rent outdoor sports gear.", "criteria": ["mem('gear.rentals.last.status') == 'available'"], "effect": {}}} },
    "J5-skill-certification": { "family": "J", "theme": "career", "difficulty": 2, "pre": lambda s: True, "options": ["certify"], "logic": {"certify": {"instr": "Apply for a professional skill certification.", "criteria": ["mem('world_state.skills.certified') == 'True'"], "effect": {"certified": True}}} },

    "K1-plan-party": { "family": "K", "theme": "leisure", "difficulty": 1, "pre": lambda s: True, "options": ["join"], "logic": {"join": {"instr": "Join a local interest group.", "criteria": [], "effect": {}}} },
    "K2-roommate-split": { "family": "K", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("has_home"), "options": ["split"], "logic": {"split": {"instr": "Split the monthly rent with roommates.", "criteria": [], "effect": {}}} },
    "K3-charity-donation": { "family": "K", "theme": "leisure", "difficulty": 1, "pre": lambda s: s.get("has_bank"), "options": ["donate"], "logic": {"donate": {"instr": "Make a charitable donation.", "criteria": [], "effect": {}}} },

    "L1-password-manager": { "family": "L", "theme": "crisis", "difficulty": 1, "pre": lambda s: True, "options": ["update"], "logic": {"update": {"instr": "Update your password manager entries.", "criteria": [], "effect": {}}} },
    "L2-data-deletion": { "family": "L", "theme": "crisis", "difficulty": 1, "pre": lambda s: True, "options": ["delete"], "logic": {"delete": {"instr": "Request data deletion from a service.", "criteria": [], "effect": {}}} },
    "L3-security-audit": { "family": "L", "theme": "crisis", "difficulty": 1, "pre": lambda s: True, "options": ["audit"], "logic": {"audit": {"instr": "Perform a manual security audit.", "criteria": [], "effect": {}}} },
    "L4-2fa-device": { "family": "L", "theme": "crisis", "difficulty": 1, "pre": lambda s: s.get("has_mobile"), "options": ["change"], "logic": {"change": {"instr": "Change your 2FA authentication device.", "criteria": [], "effect": {}}} },

    "M1-lost-card": {
        "family": "M", "theme": "crisis", "difficulty": 2,
        "pre": lambda s: s.get("has_bank") and not s.get("card_frozen"),
        "options": ["freeze"],
        "logic": {"freeze": {"instr": "Report and freeze your lost bank card.", "criteria": ["mem('payment.cards[0].state') == 'blocked'"], "effect": {"card_frozen": True}}}
    },
    "M2-supply-disruption": { "family": "M", "theme": "crisis", "difficulty": 1, "pre": lambda s: s.get("orders_count", 0) > 0, "options": ["check"], "logic": {"check": {"instr": "Check for logistics supply chain disruptions.", "criteria": [], "effect": {}}} },
    "M3-illness-reporting": { "family": "M", "theme": "crisis", "difficulty": 1, "pre": lambda s: not s.get("is_sick"), "options": ["report"], "logic": {"report": {"instr": "Submit a sudden illness report.", "criteria": [], "effect": {"is_sick": True, "energy_level": 20}}} },

    "Z1-order-arrival": { "family": "Z", "theme": "daily", "difficulty": 1, "pre": lambda s: s.get("pending_order") and not s.get("card_frozen"), "options": ["wait"], "logic": {"wait": {"instr": "Wait for your order to be delivered.", "criteria_fn": lambda s: [f"mem('{'shop.orders.last.state' if (s.get('last_order_type') or 'shop') == 'shop' else 'food.order.last.status'}') == 'delivered'"], "effect_fn": lambda s: {"pending_order": False, "delivered_count": 1, "has_shop_delivered": True} if (s.get('last_order_type') or 'shop') == 'shop' else {"pending_order": False, "delivered_count": 1}}} },
    "Z2-investment-growth": { "family": "Z", "theme": "career", "difficulty": 2, "pre": lambda s: s.get("has_invest"), "options": ["wait"], "logic": {"wait": {"instr": "Check your investment returns.", "criteria": [], "effect": {}}} },
    "Z3-live-auction": { "family": "Z", "theme": "leisure", "difficulty": 2, "pre": lambda s: s.get("has_bank"), "options": ["bid"], "logic": {"bid": {"instr": "Participate in a live item auction.", "criteria": ["mem('auctions.VASE-001.highest_bidder') == 'user'"], "effect": {}}} },
    "Z4-email-calendar": { "family": "Z", "theme": "career", "difficulty": 2, "pre": lambda s: True, "options": ["sync"], "logic": {"sync": {"instr": "Sync calendar events from your email.", "criteria": [], "effect": {}}} },
    "Z5-password-recovery": { "family": "Z", "theme": "crisis", "difficulty": 1, "pre": lambda s: s.get("has_mobile"), "options": ["recover"], "logic": {"recover": {"instr": "Perform a password recovery process.", "criteria": [], "effect": {}}} },
    "Z6-customer-service": { "family": "Z", "theme": "daily", "difficulty": 1, "pre": lambda s: True, "options": ["chat"], "logic": {"chat": {"instr": "Consult with human customer support.", "criteria": [], "effect": {}}} },
    "Z7-complex-autopay": { "family": "Z", "theme": "daily", "difficulty": 3, "pre": lambda s: s.get("has_utility") and s.get("has_bank"), "options": ["retrieval"], "logic": {"retrieval": {"instr": "Search for 'Electricity Dept' in your Email, find your account number, and enable autopay for it.", "criteria": ["mem('autopay.utility.status') == 'active'"], "effect": {"autopay": True}}} },
}

# Fallback criteria for tasks whose scenario logic is intentionally open-ended.
# These assertions are strict enough to verify concrete state/UI outcomes.
FALLBACK_SUCCESS_CRITERIA = {
    "B6-price-protection": [
        "exists(\".status-badge.submitted\")",
        "url().includes('/shop.local/price-protection.html?status=submitted')",
        "mem('orders.O-98321.claims.price_protect.state') == 'submitted'",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "C1-logistics-fix": [
        "url().includes('/shop.local/help.html?status=ticket_created')",
        "mem('support.ticket.last.status') == 'open'",
        "mem('support.ticket.last.order_id') == 'O-98321'",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "C3-subscription-refund": [
        "exists(\"#refund-requests-list .card\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "C4-warranty-claim": [
        "text('#claim-status') == 'Accepted'",
        "url().includes('status=accepted')",
        "url().includes('serial=TV-42-2025-XY9')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "C5-leave-review": [
        "url().includes('/shop.local/reviews.html')",
        "mem('user_reviews.reviews.last.merchant') == '美味餐厅'",
        "mem('user_reviews.reviews.last.rating') == '5'",
        "NOT[mem('user_reviews.blacklist.美味餐厅.status') == 'blacklisted']",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "D1-check-balance": [
        "url().includes('/bank.local/dashboard.html')",
        "exists('#balance-display')",
        "text('#balance-display') includes '$'",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "E6-flight-change": [
        "text(\"#pnr\") == \"PNR9ZZ\"",
        "text(\"#ticket-status\") == \"Rebooked\"",
        "json(\"env\",\"trips.PNR9ZZ.status\") == \"rebooked\"",
        "url().includes('status=rebooked')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "F1-calendar-aggregation": [
        "mem('calendar.events.last.id') includes 'EVE-'",
        "mem('calendar.events.last.date') == '2026-01-15'",
        "mem('calendar.events.last.time') == '10:00'",
        "exists('#event-list .card')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "F2-conference-reg": [
        "mem('expenses.last.id') == 'EXP-2201'",
        "mem('expenses.last.total') == '980'",
        "url().includes('/bank.local/expense-report.html')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "F4-email-tracking": [
        "exists(\"#email-list .card\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "F5-receipt-archive": [
        "mem('cloud.documents.last.type') == 'receipt'",
        "mem('cloud.documents.last.name') == 'utility_bill_dec.pdf'",
        "mem('cloud.documents.last.id') includes 'DOC-'",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "G1-doctor-appt": [
        "exists(\".service-card:has-text('Your Next Appointment')\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "G2-insurance-policy": [
        "mem('health.insurance.active') == 1",
        "mem('health.insurance.policy_number') includes 'POL-'",
        "exists(\"#current-policy .badge.ok\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "G3-medical-claim": [
        "exists(\"#claim-state\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "G4-gym-membership": [
        "mem('health.plan.name') == 'Standard Health Plan'",
        "mem('health.plan.status') == 'active'",
        "exists(\"#plan-standard.active\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "G5-health-plan": [
        "mem('health.plan.status') == 'active'",
        "mem('health.plan.name') == 'Premium Health Plan'",
        "exists('#plan-premium.active')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "G6-vaccine-mgmt": [
        "mem('health.vaccines.last.status') == 'booked'",
        "mem('health.vaccines.last.id') includes 'VC-'",
        "exists('#records-list .badge.ok')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "H2-vehicle-address-update": [
        "mem('gov.vehicles.last.id') == 'V-8821'",
        "mem('gov.vehicles.last.address') includes '张江高科张衡路XXX号'",
        "mem('gov.vehicles.last.insurance_notified') == 1",
        "exists(\"#vehicle-list div:has-text('张江高科张衡路XXX号')\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "H3-permit-renewal": [
        "mem('permits.RP-2024-77.next_appointment') includes '2026-12-01'",
        "url().includes('/gov.local/permits.html')",
        "exists('#permit-expiry')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "I4-smart-meter": [
        "mem('meters.meter_data.current_reading') == 12500.5",
        "mem('meters.meter_data.last_submitted_reading') == 12500.5",
        "exists(\"#meter-reading:has-text('12500.50')\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "J2-library-service": [
        "mem('library.card.status') == 'active'",
        "mem('library.reservations.last.status') == 'pending'",
        "mem('library.reservations.last.book_title') == '智能体的崛起'",
        "exists('#library-card-info .badge.ok')",
        "exists('#reservations-list .card')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "J3-event-tickets": [
        "mem('tickets.user_tickets.last.status') == 'transferred'",
        "exists(\"#tickets-list .card .badge.pri\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "K1-plan-party": [
        "mem('social.groups.GRP-001.status') == 'joined'",
        "url().includes('/social.local/my-groups.html')",
        "exists(\"#my-groups-list .badge.ok\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "K2-roommate-split": [
        "mem('settlements.2025-10.state') == 'settled'",
        "url().includes('/social.local/split.html')",
        "url().includes('month=2025-10')",
        "url().includes('state=settled')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "K3-charity-donation": [
        "exists(\"#donations-list .card .badge.ok\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "L1-password-manager": [
        "exists(\"#password-list .card\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "L2-data-deletion": [
        "mem('security.data_deletion_requests.last.status') == 'pending'",
        "mem('security.data_deletion_requests.last.platform') == 'Facebook'",
        "exists('#requests-list .card')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "L3-security-audit": [
        "url().includes('/security.local/dashboard.html')",
        "exists(\"#alert-section\")",
        "exists(\".provider-card[data-provider='mail'] .status-badge\")",
        "exists(\".provider-card[data-provider='cloud'] .status-badge\")",
        "exists(\".provider-card[data-provider='dev'] .status-badge\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "L4-2fa-device": [
        "exists(\"//div[@id='2fa-status' and contains(., 'iPhone 15 Pro')]\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "M2-supply-disruption": [
        "mem('supply_chain.alternatives.last.status') == 'pickup_confirmed'",
        "exists(\"#alternative-options-list .card\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "M3-illness-reporting": [
        "mem('health.illness_reports.last.status') == 'pending'",
        "mem('health.illness_reports.last.type') == 'illness'",
        "json('env','world_state.physical_context.status') == 'impaired'",
        "json('env','world_state.physical_context.energy_level') == 20",
        "exists('#reports-list .card')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "Z2-investment-growth": [
        "exists(\"div:has-text('Balance: ¥1050.00')\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "Z4-email-calendar": [
        "exists(\"#event-list .card h3:has-text('项目启动会')\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "Z5-password-recovery": [
        "mem('security.password_reset.status') == 'success'",
        "url().includes('/security.local/login.html')",
        "url().includes('reset=success')",
        "exists('#reset-success')",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
    "Z6-customer-service": [
        "exists(\".message.bot:has-text('O-93902')\")",
        "NOT[url().includes('about:blank')]",
        "NOT[url().includes('chrome-error://')]",
    ],
}


def normalize_criteria(criteria):
    items = []
    for raw in (criteria or []):
        text = str(raw).strip()
        if text:
            items.append(text)
    # Preserve order and drop duplicates.
    return list(dict.fromkeys(items))


def normalize_checkpoints(checkpoints):
    out = []
    for raw in (checkpoints or []):
        if isinstance(raw, dict) and raw.get("assertion"):
            cp = dict(raw)
            cp["id"] = str(cp.get("id", "")).strip() or f"cp_{len(out)+1}"
            cp["name"] = str(cp.get("name", cp["id"]))
            cp["assertion"] = str(cp.get("assertion", "")).strip()
            if not cp["assertion"]:
                continue
            cp["required"] = bool(cp.get("required", True))
            cp["depends_on"] = cp.get("depends_on", []) or []
            if isinstance(cp["depends_on"], str):
                cp["depends_on"] = [cp["depends_on"]]
            cp["depends_on"] = [str(x).strip() for x in cp["depends_on"] if str(x).strip()]
            try:
                cp["weight"] = float(cp.get("weight", 1.0))
            except Exception:
                cp["weight"] = 1.0
            cp["when"] = str(cp.get("when", "")).strip()
            out.append(cp)
    return out


def resolve_step_criteria(task_id, logic, state):
    if "criteria_fn" in logic:
        crit = logic["criteria_fn"](state)
    else:
        crit = logic.get("criteria", [])
    crit = normalize_criteria(crit)
    if crit:
        return crit
    return normalize_criteria(FALLBACK_SUCCESS_CRITERIA.get(task_id, []))


def resolve_step_checkpoints(logic, state):
    if "scoring_checkpoints_fn" in logic:
        cps = logic["scoring_checkpoints_fn"](state)
    else:
        cps = logic.get("scoring_checkpoints", [])
    return normalize_checkpoints(cps)


NO_ERROR_NAV_CRITERIA = [
    "NOT[url().includes('about:blank')]",
    "NOT[url().includes('chrome-error://')]",
]

TRUE_SEMANTIC_TEMPLATE_TASKS = {
    "A1-find-home",
    "A2-bank-opening",
    "A3-utility-setup",
    "A4-mobile-plan",
    "A5-lease-management",
    "A6-address-proof",
    "B6-price-protection",
    "B2-fresh-subscription",
    "B3-housekeeping-booking",
    "B4-food-delivery",
    "B5-coupon-management",
    "C1-logistics-fix",
    "C2-return",
    "C3-subscription-refund",
    "C4-warranty-claim",
    "C5-leave-review",
    "D1-check-balance",
    "D3-autopay",
    "D4-card-replacement",
    "D5-tax-preparation",
    "D6-investment-account",
    "E2-transport-topup",
    "E4-visa-requirements",
    "E5-expense-report",
    "E6-flight-change",
    "E7-long-haul-trip",
    "F1-calendar-aggregation",
    "F2-conference-reg",
    "F3-paper-submission",
    "F4-email-tracking",
    "F5-receipt-archive",
    "G1-doctor-appt",
    "G2-insurance-policy",
    "G3-medical-claim",
    "G4-gym-membership",
    "G5-health-plan",
    "G6-vaccine-mgmt",
    "H1-address-change",
    "H2-vehicle-address-update",
    "H3-permit-renewal",
    "H4-parking-permit",
    "I1-smart-bulb-setup",
    "I4-smart-meter",
    "J1-course-enroll",
    "J2-library-service",
    "J3-event-tickets",
    "J4-gear-rental",
    "J5-skill-certification",
    "K1-plan-party",
    "K2-roommate-split",
    "K3-charity-donation",
    "L1-password-manager",
    "L2-data-deletion",
    "L3-security-audit",
    "L4-2fa-device",
    "M1-lost-card",
    "M2-supply-disruption",
    "M3-illness-reporting",
    "Z2-investment-growth",
    "Z3-live-auction",
    "Z4-email-calendar",
    "Z6-customer-service",
    "Z5-password-recovery",
    "Z7-complex-autopay",
}


def _build_equal_weight_checkpoints(criteria: List[str], prefix: str) -> List[Dict[str, Any]]:
    norm = normalize_criteria(criteria)
    weight = 1.0 / max(1, len(norm))
    return [
        {
            "id": f"{prefix}_{idx}",
            "name": f"{prefix} checkpoint {idx}",
            "assertion": assertion,
            "weight": weight,
            "required": True,
            "depends_on": [],
        }
        for idx, assertion in enumerate(norm, start=1)
    ]


def _has_dynamic_logic(task_id: str) -> bool:
    cfg = TASKS_DB.get(task_id) or {}
    options = list(cfg.get("options") or [])
    logic_map = cfg.get("logic", {}) or {}
    return any(
        any(key in (logic_map.get(opt, {}) or {}) for key in ("criteria_fn", "scoring_checkpoints_fn", "effect_fn"))
        for opt in options
    )


def _is_auto_requirement_upgrade_task(task_id: str) -> bool:
    # A1/B2 have dedicated templates below; native dynamic/multi-option tasks
    # already carry requirement-level branches.
    if task_id in TRUE_SEMANTIC_TEMPLATE_TASKS:
        return False
    cfg = TASKS_DB.get(task_id) or {}
    options = list(cfg.get("options") or [])
    return len(options) == 1 and not _has_dynamic_logic(task_id)


def _is_true_requirement_level_task(task_id: str) -> bool:
    cfg = TASKS_DB.get(task_id) or {}
    options = list(cfg.get("options") or [])
    has_dynamic_logic = _has_dynamic_logic(task_id)
    return len(options) > 1 or has_dynamic_logic or task_id in TRUE_SEMANTIC_TEMPLATE_TASKS


def _is_validation_only_requirement_task(task_id: str) -> bool:
    return _is_auto_requirement_upgrade_task(task_id)


def _derive_strict_branch_criteria(task_id: str, base_criteria: List[str]) -> List[str]:
    base = normalize_criteria(base_criteria)
    extras = []
    for cond in NO_ERROR_NAV_CRITERIA:
        if cond not in base and cond not in extras:
            extras.append(cond)
    # Keep at least one branch-specific requirement even if the task already
    # contains navigation safety checks.
    if not extras:
        extras.append('exists("body")')
    return normalize_criteria(base + extras)


_MEM_PATH_PATTERN = re.compile(r"mem\('([^']+)'\)")
_MEM_POSITIVE_ATOM_PATTERN = re.compile(r"mem\('([^']+)'\)\s*(==|includes|>=|<=|>|<)\s*")


def _derive_mem_state_guard_criteria(base_criteria: List[str]) -> List[str]:
    base = normalize_criteria(base_criteria)
    guards = []
    seen_paths = set()
    for cond in base:
        text = str(cond or "").strip()
        # Skip negative/compound forms to avoid turning optional fields into
        # mandatory fields (e.g., NOT[mem(...) == 'x']).
        if "NOT[" in text or "ANY[" in text or "ALL[" in text:
            continue
        for m in _MEM_POSITIVE_ATOM_PATTERN.finditer(text):
            path = str(m.group(1) or "").strip()
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            guard = f"mem('{path}') != ''"
            if guard not in base and guard not in guards:
                guards.append(guard)
    return normalize_criteria(base + guards)


def _auto_requirement_mode_specs(task_id: str, base_criteria: List[str]) -> List[Dict[str, Any]]:
    baseline = normalize_criteria(base_criteria)
    strict_verified = _derive_strict_branch_criteria(task_id, baseline)
    strict_state_guarded = _derive_mem_state_guard_criteria(strict_verified)
    candidates = [
        {"mode": "baseline", "criteria": baseline, "instruction_suffix": ""},
        {
            "mode": "strict_verified",
            "criteria": strict_verified,
            "instruction_suffix": " Before finishing, verify success state and ensure the page is valid.",
        },
        {
            "mode": "strict_state_guarded",
            "criteria": strict_state_guarded,
            "instruction_suffix": (
                " Before finishing, verify success state, key state fields, and ensure the page is valid."
            ),
        },
    ]
    # Keep only semantically distinct criteria sets to avoid forced branch inflation.
    out = []
    seen_criteria = set()
    for spec in candidates:
        sig = tuple(spec["criteria"])
        if not spec["criteria"] or sig in seen_criteria:
            continue
        seen_criteria.add(sig)
        out.append(spec)
    return out


def _is_requirement_level_task(task_id: str) -> bool:
    return _is_true_requirement_level_task(task_id) or _is_validation_only_requirement_task(task_id)


def _fallback_detail_instruction(base_instruction: str) -> tuple[str, str]:
    instr = str(base_instruction or "").strip()
    # Keep RNG consumption stable relative to the old detail-style path so that
    # removing surface-form variation does not perturb chain sampling.
    _ = random.choice(["plain", "confirm", "strict", "quick"])
    return instr, "direct"


def instantiate_task_step(task_id: str, option: str, logic: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compile a task step from template + option.
    We template a small set first to avoid broad behavior drift.
    """
    base_instruction = str(logic.get("instr", "")).strip()
    if task_id not in TRUE_SEMANTIC_TEMPLATE_TASKS:
        fallback_instruction, detail_style = _fallback_detail_instruction(base_instruction)
        requirement_level = _is_requirement_level_task(task_id)
        semantic_requirement_level = _is_true_requirement_level_task(task_id)
        auto_upgrade = _is_auto_requirement_upgrade_task(task_id)
        validation_only_requirement = bool(auto_upgrade)
        requirement_mode = "native_requirement_branch"
        criteria = None
        scoring_checkpoints = None
        if auto_upgrade:
            base_criteria = resolve_step_criteria(task_id, logic, {})
            mode_specs = _auto_requirement_mode_specs(task_id, base_criteria)
            picked = random.choice(mode_specs) if mode_specs else {"mode": "baseline", "criteria": normalize_criteria(base_criteria), "instruction_suffix": ""}
            requirement_mode = str(picked["mode"])
            criteria = normalize_criteria(picked.get("criteria") or [])
            scoring_checkpoints = []
            cp_weight = 1.0 / max(1, len(criteria))
            for idx, assertion in enumerate(criteria, start=1):
                scoring_checkpoints.append(
                    {
                        "id": f"cp_{requirement_mode}_{idx}",
                        "name": f"{requirement_mode} checkpoint {idx}",
                        "assertion": assertion,
                        "weight": cp_weight,
                        "required": True,
                        "depends_on": [],
                    }
                )
            suffix = str(picked.get("instruction_suffix") or "").strip()
            if suffix:
                fallback_instruction = f"{fallback_instruction}{suffix}"
        requirement_id = f"option={option}" if not requirement_level else f"option={option}|{requirement_mode}"
        return {
            "instruction": add_noise(fallback_instruction),
            "template_info": {
                "template_id": f"{task_id}/fallback-v1",
                "option": option,
                "requirement_id": requirement_id,
                "requirement_level": bool(requirement_level),
                "semantic_requirement_level": bool(semantic_requirement_level),
                "validation_only_requirement": bool(validation_only_requirement),
                "branch_kind": (
                    "semantic"
                    if semantic_requirement_level
                    else ("validation_only" if validation_only_requirement else "detail_only")
                ),
                "slot_values": {
                    "option": option,
                    "detail_style": detail_style,
                    "requirement_mode": requirement_mode,
                },
            },
            "criteria": criteria,
            "scoring_checkpoints": scoring_checkpoints,
            "oracle_trace_override": None,
        }

    if task_id == "A2-bank-opening":
        profile = random.choice(
            [
                {
                    "name": "Alex Chen",
                    "phone": "555-0102",
                    "address": "123 Main St, Springfield",
                    "enable_2fa": True,
                    "goal_text": "Open a new bank account and enable 2FA before finishing.",
                },
                {
                    "name": "Jamie Lee",
                    "phone": "555-0148",
                    "address": "88 River Rd, Springfield",
                    "enable_2fa": False,
                    "goal_text": "Open a standard bank account without enabling 2FA.",
                },
            ]
        )
        criteria = [
            "mem('bank.account.status') == 'active'",
            f"mem('bank.account.holder_name') == '{profile['name']}'",
            f"mem('bank.account.2fa_enabled') == '{'1' if profile['enable_2fa'] else '0'}'",
        ]
        oracle_trace_override = [
            {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/open-account.html?clean=true"},
            {"t": 1, "act": "type", "selector": "#fullname", "value": profile["name"]},
            {"t": 2, "act": "type", "selector": "#phone", "value": profile["phone"]},
            {"t": 3, "act": "type", "selector": "#address", "value": profile["address"]},
        ]
        if profile["enable_2fa"]:
            oracle_trace_override.append({"t": 4, "act": "click", "selector": "#enable2fa"})
        oracle_trace_override.append({"t": 5, "act": "click", "selector": "#submit-btn"})
        return {
            "instruction": add_noise(profile["goal_text"]),
            "template_info": {
                "template_id": "A2-bank-opening/v1",
                "option": option,
                "requirement_id": f"name={profile['name']}|enable_2fa={int(profile['enable_2fa'])}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(profile),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_a2"),
            "oracle_trace_override": oracle_trace_override,
        }

    if task_id == "A3-utility-setup":
        variant = random.choice(
            [
                {
                    "address": "123 Main St, Springfield",
                    "account_number": "UTIL-3344",
                    "payee": "Electricity Dept",
                    "amount": "180",
                    "goal_text": "Set up utility billing with Electricity Dept using account UTIL-3344 and a monthly cap of 180.",
                },
                {
                    "address": "88 River Rd, Springfield",
                    "account_number": "UTIL-7788",
                    "payee": "City Utilities",
                    "amount": "260",
                    "goal_text": "Set up utilities with City Utilities using account UTIL-7788 and a monthly cap of 260.",
                },
                {
                    "address": "21 Harbor Ave, Springfield",
                    "account_number": "UTIL-9910",
                    "payee": "City Utilities",
                    "amount": "320",
                    "goal_text": "Connect utilities with City Utilities using account UTIL-9910 and a monthly cap of 320.",
                },
            ]
        )
        criteria = [
            "mem('contracts.electricity.status') == 'active'",
            f"mem('autopay.utility.account_number') == '{variant['account_number']}'",
            f"mem('autopay.utility.payee') == '{variant['payee']}'",
            f"mem('autopay.utility.amount') == '{variant['amount']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "A3-utility-setup/v2",
                "option": option,
                "requirement_id": (
                    f"payee={variant['payee'].replace(' ', '_')}|account={variant['account_number']}|amount={variant['amount']}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_a3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/energy.local/setup.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#address", "value": variant["address"]},
                {"t": 2, "act": "type", "selector": "#account-number", "value": variant["account_number"]},
                {"t": 3, "act": "select", "selector": "#payee", "value": variant["payee"]},
                {"t": 4, "act": "type", "selector": "#monthly-cap", "value": variant["amount"]},
                {"t": 5, "act": "click", "selector": "#submit-btn"},
                {"t": 6, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "A4-mobile-plan":
        plan = random.choice(
            [
                {"plan_id": "starter", "plan_name": "Starter Plan", "goal_text": "Switch your mobile plan to Starter."},
                {"plan_id": "unlimited", "plan_name": "Unlimited Plan", "goal_text": "Switch your mobile plan to Unlimited."},
                {"plan_id": "pro", "plan_name": "Pro Plan", "goal_text": "Upgrade your mobile plan to Pro."},
            ]
        )
        criteria = [
            "mem('mobile.subscription.status') == 'active'",
            f"mem('mobile.subscription.plan_id') == '{plan['plan_id']}'",
        ]
        return {
            "instruction": add_noise(plan["goal_text"]),
            "template_info": {
                "template_id": "A4-mobile-plan/v2",
                "option": option,
                "requirement_id": f"plan_id={plan['plan_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(plan),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_a4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/mobile.local/account.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#plan-{plan['plan_id']} button"},
                {"t": 2, "act": "wait", "selector": f"#plan-{plan['plan_id']}.active"},
            ],
        }

    if task_id == "A5-lease-management":
        variant = random.choice(
            [
                {
                    "lease_id": "CTR-2101",
                    "rent": "1200",
                    "end_date": "2027-06-30",
                    "goal_text": "Add lease contract CTR-2101 with monthly rent 1200 ending on 2027-06-30.",
                },
                {
                    "lease_id": "CTR-3402",
                    "rent": "1450",
                    "end_date": "2027-09-15",
                    "goal_text": "Add lease contract CTR-3402 with monthly rent 1450 ending on 2027-09-15.",
                },
                {
                    "lease_id": "CTR-5503",
                    "rent": "980",
                    "end_date": "2026-12-31",
                    "goal_text": "Add lease contract CTR-5503 with monthly rent 980 ending on 2026-12-31.",
                },
            ]
        )
        criteria = [
            f"json('env','housing.leases.{variant['lease_id']}.status') == 'active'",
            f"json('env','housing.leases.{variant['lease_id']}.end_date') == '{variant['end_date']}'",
            f"json('env','housing.leases.{variant['lease_id']}.rent') == '{variant['rent']}'",
            f"exists(\"#leases-list .lease-card:has-text('Contract #{variant['lease_id']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "A5-lease-management/v2",
                "option": option,
                "requirement_id": f"lease={variant['lease_id']}|rent={variant['rent']}|end={variant['end_date']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_a5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/housing.local/lease-management.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#add-lease-btn"},
                {"t": 2, "act": "type", "selector": "#new-id", "value": variant["lease_id"]},
                {"t": 3, "act": "type", "selector": "#new-rent", "value": variant["rent"]},
                {"t": 4, "act": "type", "selector": "#new-end-date", "value": variant["end_date"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#leases-list .lease-card:has-text('Contract #{variant['lease_id']}')"},
            ],
        }

    if task_id == "A6-address-proof":
        variant = random.choice(
            [
                {
                    "doc_type": "utility_bill",
                    "file_name": "utility_bill_dec.pdf",
                    "goal_text": "Upload a utility bill named utility_bill_dec.pdf as address proof.",
                },
                {
                    "doc_type": "bank_statement",
                    "file_name": "bank_statement_q1.pdf",
                    "goal_text": "Upload a bank statement named bank_statement_q1.pdf as address proof.",
                },
                {
                    "doc_type": "lease_agreement",
                    "file_name": "lease_contract_2026.pdf",
                    "goal_text": "Upload a lease agreement named lease_contract_2026.pdf as address proof.",
                },
            ]
        )
        criteria = [
            "mem('identity.address_verified') == 'true'",
            f"mem('identity.address_proof.doc_type') == '{variant['doc_type']}'",
            f"mem('identity.address_proof.file_name') == '{variant['file_name']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "A6-address-proof/v2",
                "option": option,
                "requirement_id": f"doc={variant['doc_type']}|file={variant['file_name']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_a6"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/gov.local/profile.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#upload-proof-btn"},
                {"t": 2, "act": "select", "selector": "#doc-type", "value": variant["doc_type"]},
                {"t": 3, "act": "type", "selector": "#proof-file-name", "value": variant["file_name"]},
                {"t": 4, "act": "click", "selector": ".modal-confirm"},
                {"t": 5, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "B3-housekeeping-booking":
        booking = random.choice(
            [
                {
                    "service_type": "regular_cleaning",
                    "service_date": "2026-01-15",
                    "service_time": "09:00",
                    "instructions": "Bring vacuum cleaner",
                    "goal_text": "Book a regular cleaning visit for 2026-01-15 at 09:00.",
                },
                {
                    "service_type": "deep_cleaning",
                    "service_date": "2026-01-18",
                    "service_time": "13:00",
                    "instructions": "Focus on kitchen and bathroom",
                    "goal_text": "Book a deep cleaning session for 2026-01-18 at 13:00.",
                },
                {
                    "service_type": "move_out_cleaning",
                    "service_date": "2026-01-22",
                    "service_time": "15:00",
                    "instructions": "Include windows and cabinets",
                    "goal_text": "Schedule a move-out cleaning for 2026-01-22 at 15:00.",
                },
            ]
        )
        criteria = [
            "mem('local_services.housekeeping_bookings.last.status') == 'confirmed'",
            f"mem('local_services.housekeeping_bookings.last.type') == '{booking['service_type']}'",
            f"mem('local_services.housekeeping_bookings.last.date') == '{booking['service_date']}'",
            f"mem('local_services.housekeeping_bookings.last.time') == '{booking['service_time']}'",
        ]
        return {
            "instruction": add_noise(booking["goal_text"]),
            "template_info": {
                "template_id": "B3-housekeeping-booking/v2",
                "option": option,
                "requirement_id": (
                    f"type={booking['service_type']}|date={booking['service_date']}|time={booking['service_time']}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(booking),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_b3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/housekeeping.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#service-type", "value": booking["service_type"]},
                {"t": 2, "act": "type", "selector": "#service-date", "value": booking["service_date"]},
                {"t": 3, "act": "select", "selector": "#service-time", "value": booking["service_time"]},
                {"t": 4, "act": "type", "selector": "#instructions", "value": booking["instructions"]},
                {"t": 5, "act": "click", "selector": "#book-btn"},
                {"t": 6, "act": "wait", "selector": "#bookings-list .badge.ok"},
            ],
        }

    if task_id == "B4-food-delivery":
        variant = random.choice(
            [
                {
                    "restaurant_id": "RES-001",
                    "restaurant": "Burger Kingpin",
                    "items": ["Classic Burger", "Cheese Deluxe"],
                    "total": 19.98,
                    "promo_code": "",
                    "goal_text": "Order Classic Burger and Cheese Deluxe from Burger Kingpin.",
                },
                {
                    "restaurant_id": "RES-002",
                    "restaurant": "Pizza Palace",
                    "items": ["Margherita", "Garlic Knots"],
                    "total": 18.98,
                    "promo_code": "",
                    "goal_text": "Order Margherita and Garlic Knots from Pizza Palace.",
                },
                {
                    "restaurant_id": "RES-001",
                    "restaurant": "Burger Kingpin",
                    "items": ["Classic Burger", "Fries"],
                    "total": 10.38,
                    "promo_code": "SAVE20",
                    "goal_text": "Order Classic Burger and Fries from Burger Kingpin using promo code SAVE20.",
                },
            ]
        )
        criteria = [
            "mem('food.order.last.status') == 'pending'",
            f"mem('food.order.last.total') == {variant['total']}",
        ]
        if variant["promo_code"]:
            criteria.append(f"mem('food.order.last.promo_code') == '{variant['promo_code']}'")
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "B4-food-delivery/v2",
                "option": option,
                "requirement_id": (
                    f"restaurant={variant['restaurant_id']}|items={'+'.join(i.replace(' ', '_') for i in variant['items'])}"
                    f"|promo={variant['promo_code'] or 'none'}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_b4"),
            "oracle_trace_override": (
                [{"t": 0, "act": "open", "url": f"http://localhost:8014/food.local/restaurant.html?id={variant['restaurant_id']}&clean=true"}]
                + [
                    {
                        "t": idx + 1,
                        "act": "click",
                        "selector": f"div.menu-item:has(h3:has-text('{item}')) button.btn-add",
                    }
                    for idx, item in enumerate(variant["items"])
                ]
                + (
                    [
                        {"t": 3, "act": "type", "selector": "#promo-code", "value": variant["promo_code"]},
                        {"t": 4, "act": "click", "selector": "button.btn.sm"},
                        {"t": 5, "act": "click", "selector": "button.btn-checkout"},
                        {"t": 6, "act": "wait", "selector": "#order-list"},
                    ]
                    if variant["promo_code"]
                    else [
                        {"t": 3, "act": "click", "selector": "button.btn-checkout"},
                        {"t": 4, "act": "wait", "selector": "#order-list"},
                    ]
                )
            ),
        }

    if task_id == "B5-coupon-management":
        variant = random.choice(
            [
                {
                    "name": "Spring Saver",
                    "code": "SAVE20",
                    "coupon_type": "discount",
                    "value": "20.0",
                    "min_spend": "100.0",
                    "expiry_date": "2026-04-30",
                    "goal_text": "Add a fixed discount coupon SAVE20 worth 20 off with a minimum spend of 100.",
                },
                {
                    "name": "Weekend Boost",
                    "code": "WEEKEND15",
                    "coupon_type": "percentage",
                    "value": "15.0",
                    "min_spend": "80.0",
                    "expiry_date": "2026-05-15",
                    "goal_text": "Add a percentage coupon WEEKEND15 worth 15 percent off with a minimum spend of 80.",
                },
                {
                    "name": "Cart Rescue",
                    "code": "RESCUE10",
                    "coupon_type": "discount",
                    "value": "10.0",
                    "min_spend": "50.0",
                    "expiry_date": "2026-06-01",
                    "goal_text": "Add a fixed discount coupon RESCUE10 worth 10 off with a minimum spend of 50.",
                },
            ]
        )
        criteria = [
            "mem('shop.coupons.last.status') == 'active'",
            f"mem('shop.coupons.last.code') == '{variant['code']}'",
            f"mem('shop.coupons.last.type') == '{variant['coupon_type']}'",
            f"mem('shop.coupons.last.value') == '{variant['value']}'",
            f"mem('shop.coupons.last.min_spend') == '{variant['min_spend']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "B5-coupon-management/v2",
                "option": option,
                "requirement_id": (
                    f"code={variant['code']}|type={variant['coupon_type']}|value={variant['value']}|min={variant['min_spend']}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_b5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/coupons.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-add-coupon"},
                {"t": 2, "act": "type", "selector": "#new-name", "value": variant["name"]},
                {"t": 3, "act": "type", "selector": "#new-code", "value": variant["code"]},
                {"t": 4, "act": "select", "selector": "#new-type", "value": variant["coupon_type"]},
                {"t": 5, "act": "type", "selector": "#new-value", "value": variant["value"]},
                {"t": 6, "act": "type", "selector": "#new-min-spend", "value": variant["min_spend"]},
                {"t": 7, "act": "type", "selector": "#new-expiry-date", "value": variant["expiry_date"]},
                {"t": 8, "act": "click", "selector": ".modal-confirm"},
                {"t": 9, "act": "wait", "selector": "#coupons-list .badge.ok"},
            ],
        }

    if task_id == "B6-price-protection":
        variant = random.choice(
            [
                {
                    "order_id": "O-10001",
                    "goal_text": "Submit a price protection claim for order O-10001.",
                },
                {
                    "order_id": "O-10002",
                    "goal_text": "Submit a price protection claim for order O-10002.",
                },
                {
                    "order_id": "O-10003",
                    "goal_text": "Submit a price protection claim for order O-10003.",
                },
            ]
        )
        criteria = [
            f"mem('orders.{variant['order_id']}.claims.price_protect.state') == 'submitted'",
            "url().includes('/shop.local/price-protection.html?status=submitted')",
            "exists('.status-badge.submitted')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "B6-price-protection/v2",
                "option": option,
                "requirement_id": f"order={variant['order_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_b6"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/price-protection.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#order-id", "value": variant["order_id"]},
                {"t": 2, "act": "click", "selector": "button.btn.pri.lg"},
                {"t": 3, "act": "wait", "selector": ".status-badge.submitted"},
            ],
        }

    if task_id == "C1-logistics-fix":
        variant = random.choice(
            [
                {
                    "order_id": "O-98321",
                    "issue_type": "delayed",
                    "description": "My order has not arrived yet.",
                    "goal_text": "Open a logistics ticket for order O-98321 with issue type delayed.",
                },
                {
                    "order_id": "O-98321",
                    "issue_type": "damaged",
                    "description": "The package arrived with a damaged item.",
                    "goal_text": "Open a logistics ticket for order O-98321 with issue type damaged.",
                },
                {
                    "order_id": "O-98321",
                    "issue_type": "missing",
                    "description": "One item is missing from the shipment.",
                    "goal_text": "Open a logistics ticket for order O-98321 with issue type missing.",
                },
            ]
        )
        criteria = [
            "mem('support.ticket.last.status') == 'open'",
            f"mem('support.ticket.last.order_id') == '{variant['order_id']}'",
            f"mem('support.ticket.last.type') == '{variant['issue_type']}'",
            f"mem('support.ticket.last.description') includes '{variant['description'].split()[0]}'",
            "url().includes('/shop.local/help.html?status=ticket_created')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "C1-logistics-fix/v2",
                "option": option,
                "requirement_id": f"issue={variant['issue_type']}|order={variant['order_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_c1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/help.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#order-id", "value": variant["order_id"]},
                {"t": 2, "act": "select", "selector": "#issue-type", "value": variant["issue_type"]},
                {"t": 3, "act": "type", "selector": "#description", "value": variant["description"]},
                {"t": 4, "act": "click", "selector": "#submit-ticket-btn"},
                {"t": 5, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "C2-return":
        variant = random.choice(
            [
                {
                    "order_id": "O-10001",
                    "reason": "defective",
                    "goal_text": "Submit a return request for order O-10001 because the item is defective.",
                },
                {
                    "order_id": "O-10001",
                    "reason": "wrong_item",
                    "goal_text": "Submit a return request for order O-10001 because the wrong item arrived.",
                },
                {
                    "order_id": "O-10001",
                    "reason": "changed_mind",
                    "goal_text": "Submit a return request for order O-10001 because you changed your mind.",
                },
            ]
        )
        criteria = [
            "mem('returns.last.state') == 'submitted'",
            f"mem('returns.last.order_id') == '{variant['order_id']}'",
            f"mem('returns.last.reason') == '{variant['reason']}'",
            "url().includes('/shop.local/returns/confirm.html')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "C2-return/v2",
                "option": option,
                "requirement_id": f"order={variant['order_id']}|reason={variant['reason']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_c2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/orders.html?clean=true"},
                {"t": 1, "act": "click", "selector": f".return-order-btn[data-order-id='{variant['order_id']}']"},
                {"t": 2, "act": "click", "selector": f"#return-reasons .reason-option[data-reason='{variant['reason']}']"},
                {"t": 3, "act": "click", "selector": "#submit-return-btn"},
                {"t": 4, "act": "wait", "selector": "#return-id"},
            ],
        }

    if task_id == "C3-subscription-refund":
        variant = random.choice(
            [
                {
                    "subscription_id": "SUB-8821",
                    "reason": "Service is no longer needed.",
                    "estimated_refund": "133.33",
                    "goal_text": "Request a prorated refund for subscription SUB-8821 because the service is no longer needed.",
                },
                {
                    "subscription_id": "SUB-9932",
                    "reason": "I no longer need the monthly subscription.",
                    "estimated_refund": "10.0",
                    "goal_text": "Request a prorated refund for subscription SUB-9932 because the monthly plan is no longer needed.",
                },
            ]
        )
        criteria = [
            f"mem('support.refund_requests.last.subscription_id') == '{variant['subscription_id']}'",
            "mem('support.refund_requests.last.status') == 'processing'",
            f"mem('support.refund_requests.last.estimated_refund') == '{variant['estimated_refund']}'",
            f"mem('support.refund_requests.last.reason') includes '{variant['reason'].split()[0]}'",
            "exists(\"#refund-requests-list .card\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "C3-subscription-refund/v2",
                "option": option,
                "requirement_id": f"sub={variant['subscription_id']}|refund={variant['estimated_refund']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_c3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/help-refund.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#subscription-select", "value": variant["subscription_id"]},
                {"t": 2, "act": "type", "selector": "#refund-reason", "value": variant["reason"]},
                {"t": 3, "act": "click", "selector": "#submit-refund-btn"},
                {"t": 4, "act": "wait", "selector": "#refund-requests-list .card"},
            ],
        }

    if task_id == "C4-warranty-claim":
        variant = random.choice(
            [
                {
                    "serial": "TV-42-2025-XY9",
                    "order_id": "O-10123",
                    "issue": "Screen flickering intermittently",
                    "goal_text": "Submit a warranty claim for serial TV-42-2025-XY9 from order O-10123.",
                },
                {
                    "serial": "AC-11-2025-ZK2",
                    "order_id": "O-10124",
                    "issue": "Unit fails to cool properly",
                    "goal_text": "Submit a warranty claim for serial AC-11-2025-ZK2 from order O-10124.",
                },
                {
                    "serial": "WM-88-2025-PL7",
                    "order_id": "O-10125",
                    "issue": "Wireless connection drops repeatedly",
                    "goal_text": "Submit a warranty claim for serial WM-88-2025-PL7 from order O-10125.",
                },
            ]
        )
        criteria = [
            f"mem('warranty.last.serial') == '{variant['serial']}'",
            f"mem('warranty.last.order_id') == '{variant['order_id']}'",
            "mem('warranty.last.state') == 'RMA_issued'",
            "url().includes('status=accepted')",
            f"url().includes('serial={variant['serial']}')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "C4-warranty-claim/v2",
                "option": option,
                "requirement_id": f"serial={variant['serial']}|order={variant['order_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_c4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/warranty.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#serial", "value": variant["serial"]},
                {"t": 2, "act": "type", "selector": "#orderId", "value": variant["order_id"]},
                {"t": 3, "act": "type", "selector": "#issue", "value": variant["issue"]},
                {"t": 4, "act": "click", "selector": "#submit-warranty-claim"},
                {"t": 5, "act": "wait", "selector": "#claim-status"},
            ],
        }

    if task_id == "C5-leave-review":
        variant = random.choice(
            [
                {
                    "merchant": "Tasty Garden",
                    "rating": "5",
                    "content": "Excellent dinner service and very fresh ingredients.",
                    "blacklist": False,
                    "goal_text": "Leave a 5-star review for Tasty Garden without blacklisting the merchant.",
                },
                {
                    "merchant": "QuickFix Repairs",
                    "rating": "2",
                    "content": "The repair was slow and communication was poor.",
                    "blacklist": True,
                    "goal_text": "Leave a 2-star review for QuickFix Repairs and add the merchant to the blacklist.",
                },
                {
                    "merchant": "Northwind Cafe",
                    "rating": "4",
                    "content": "Good coffee and friendly staff overall.",
                    "blacklist": False,
                    "goal_text": "Leave a 4-star review for Northwind Cafe without blacklisting the merchant.",
                },
            ]
        )
        criteria = [
            f"mem('user_reviews.reviews.last.merchant') == '{variant['merchant']}'",
            f"mem('user_reviews.reviews.last.rating') == '{variant['rating']}'",
            (
                f"mem('user_reviews.blacklist.last.merchant') == '{variant['merchant']}'"
                if variant["blacklist"]
                else f"NOT[mem('user_reviews.blacklist.{variant['merchant']}.status') == 'blacklisted']"
            ),
            "exists('#review-history-list .card')",
        ]
        trace = [
            {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/reviews.html?clean=true"},
            {"t": 1, "act": "type", "selector": "#merchant-name", "value": variant["merchant"]},
            {"t": 2, "act": "click", "selector": f"#rating-component .rating-star[data-value='{variant['rating']}']"},
            {"t": 3, "act": "type", "selector": "#review-content", "value": variant["content"]},
        ]
        if variant["blacklist"]:
            trace.append({"t": 4, "act": "click", "selector": "#add-to-blacklist"})
        trace.extend(
            [
                {"t": 5, "act": "click", "selector": "#submit-btn"},
                {"t": 6, "act": "wait", "selector": "#review-history-list .card"},
            ]
        )
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "C5-leave-review/v2",
                "option": option,
                "requirement_id": f"merchant={variant['merchant'].replace(' ', '_')}|rating={variant['rating']}|blacklist={int(variant['blacklist'])}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_c5"),
            "oracle_trace_override": trace,
        }

    if task_id == "D1-check-balance":
        variant = random.choice(
            [
                {
                    "account_type": "total",
                    "amount_mem": "6523.45",
                    "amount_ui": "6,523.45",
                    "goal_text": "Open the bank dashboard and check the total balance view.",
                },
                {
                    "account_type": "checking",
                    "amount_mem": "4175.01",
                    "amount_ui": "4,175.01",
                    "goal_text": "Open the bank dashboard and switch to the checking balance view.",
                },
                {
                    "account_type": "savings",
                    "amount_mem": "2348.44",
                    "amount_ui": "2,348.44",
                    "goal_text": "Open the bank dashboard and switch to the savings balance view.",
                },
            ]
        )
        criteria = [
            "url().includes('/bank.local/dashboard.html')",
            f"mem('banking.balance.last_view') == '{variant['account_type']}'",
            f"mem('banking.balance.last_amount') == '{variant['amount_mem']}'",
            f"text('#balance-display') includes '{variant['amount_ui']}'",
            f"text('#balance-view-label') includes '{variant['account_type']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "D1-check-balance/v2",
                "option": option,
                "requirement_id": f"account_type={variant['account_type']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_d1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/dashboard.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#view-{variant['account_type']}"},
                {"t": 2, "act": "wait", "selector": "#balance-view-label"},
            ],
        }

    if task_id == "D3-autopay":
        variant = random.choice(
            [
                {
                    "payee": "Electricity Dept",
                    "account_number": "UTIL-2201",
                    "amount": "180",
                    "goal_text": "Enable autopay for Electricity Dept with account UTIL-2201 and a monthly limit of 180.",
                },
                {
                    "payee": "City Water Board",
                    "account_number": "WATER-4408",
                    "amount": "95",
                    "goal_text": "Enable autopay for City Water Board with account WATER-4408 and a monthly limit of 95.",
                },
                {
                    "payee": "Electricity Dept",
                    "account_number": "UTIL-6602",
                    "amount": "260",
                    "goal_text": "Enable autopay for Electricity Dept with account UTIL-6602 and a monthly limit of 260.",
                },
                {
                    "payee": "Neighborhood Gas Co",
                    "account_number": "GAS-1188",
                    "amount": "75",
                    "goal_text": "Enable autopay for Neighborhood Gas Co with account GAS-1188 and a monthly limit of 75.",
                },
                {
                    "payee": "Neighborhood Internet",
                    "account_number": "FIBER-9012",
                    "amount": "120",
                    "goal_text": "Enable autopay for Neighborhood Internet with account FIBER-9012 and a monthly limit of 120.",
                },
                {
                    "payee": "Electricity Dept",
                    "account_number": "UTIL-7710",
                    "amount": "310",
                    "goal_text": "Enable autopay for Electricity Dept with account UTIL-7710 and a monthly limit of 310.",
                },
            ]
        )
        criteria = [
            "mem('autopay.utility.status') == 'active'",
            f"mem('autopay.utility.payee') == '{variant['payee']}'",
            f"mem('autopay.utility.account_number') == '{variant['account_number']}'",
            f"mem('autopay.utility.amount') == '{variant['amount']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "D3-autopay/v2",
                "option": option,
                "requirement_id": (
                    f"payee={variant['payee'].replace(' ', '_')}|account={variant['account_number']}|amount={variant['amount']}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_d3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/autopay.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#payee", "value": variant["payee"]},
                {"t": 2, "act": "type", "selector": "#account-number", "value": variant["account_number"]},
                {"t": 3, "act": "type", "selector": "#amount", "value": variant["amount"]},
                {"t": 4, "act": "click", "selector": "#setup-btn"},
                {"t": 5, "act": "wait", "selector": "#success-card"},
            ],
        }

    if task_id == "D4-card-replacement":
        variant = random.choice(
            [
                {
                    "new_last4": "7777",
                    "goal_text": "Replace the current card and set the new card digits to 7777.",
                },
                {
                    "new_last4": "8888",
                    "goal_text": "Replace the current card and set the new card digits to 8888.",
                },
                {
                    "new_last4": "2468",
                    "goal_text": "Replace the current card and set the new card digits to 2468.",
                },
            ]
        )
        criteria = [
            "mem('payment.cards[0].status') == 'active'",
            f"mem('payment.cards[0].last4') == '{variant['new_last4']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "D4-card-replacement/v2",
                "option": option,
                "requirement_id": f"new_last4={variant['new_last4']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_d4"),
            "oracle_trace_override": [
                {
                    "t": 0,
                    "act": "open",
                    "url": f"http://localhost:8014/pay.local/wallet/cards.html?clean=true&newLast4={variant['new_last4']}&oldLast4=1234",
                },
                {"t": 1, "act": "click", "selector": "button.btn-replace"},
                {"t": 2, "act": "wait", "selector": "#active-card-last4"},
            ],
        }

    if task_id == "D5-tax-preparation":
        variant = random.choice(
            [
                {
                    "name": "Office Supply Invoice",
                    "doc_type": "invoice",
                    "amount": "150.0",
                    "date": "2025-12-01",
                    "goal_text": "Upload the tax document Office Supply Invoice as an invoice for 150.0 dated 2025-12-01.",
                },
                {
                    "name": "Client Dinner Receipt",
                    "doc_type": "receipt",
                    "amount": "88.5",
                    "date": "2025-12-03",
                    "goal_text": "Upload the tax document Client Dinner Receipt as a receipt for 88.5 dated 2025-12-03.",
                },
                {
                    "name": "Monthly Statement",
                    "doc_type": "statement",
                    "amount": "420.0",
                    "date": "2025-12-15",
                    "goal_text": "Upload the tax document Monthly Statement as a statement for 420.0 dated 2025-12-15.",
                },
            ]
        )
        criteria = [
            "mem('finance.tax_documents.last.status') == 'pending'",
            f"mem('finance.tax_documents.last.name') == '{variant['name']}'",
            f"mem('finance.tax_documents.last.type') == '{variant['doc_type']}'",
            f"mem('finance.tax_documents.last.amount') == '{variant['amount']}'",
            f"mem('finance.tax_documents.last.date') == '{variant['date']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "D5-tax-preparation/v2",
                "option": option,
                "requirement_id": f"type={variant['doc_type']}|amount={variant['amount']}|date={variant['date']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_d5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/taxes.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-tax-upload"},
                {"t": 2, "act": "type", "selector": "#doc-name", "value": variant["name"]},
                {"t": 3, "act": "select", "selector": "#doc-type", "value": variant["doc_type"]},
                {"t": 4, "act": "type", "selector": "#doc-amount", "value": variant["amount"]},
                {"t": 5, "act": "type", "selector": "#doc-date", "value": variant["date"]},
                {"t": 6, "act": "click", "selector": ".modal-confirm"},
                {"t": 7, "act": "wait", "selector": "#tax-docs-list .card"},
            ],
        }

    if task_id == "D6-investment-account":
        variant = random.choice(
            [
                {
                    "name": "Growth Portfolio",
                    "acc_type": "stocks",
                    "initial_deposit": "1000.0",
                    "goal_text": "Open a Growth Portfolio investment account of type stocks with an initial deposit of 1000.",
                },
                {
                    "name": "Income Builder",
                    "acc_type": "funds",
                    "initial_deposit": "1500.0",
                    "goal_text": "Open an Income Builder investment account of type funds with an initial deposit of 1500.",
                },
                {
                    "name": "Retirement Shield",
                    "acc_type": "retirement",
                    "initial_deposit": "2000.0",
                    "goal_text": "Open a Retirement Shield investment account of type retirement with an initial deposit of 2000.",
                },
            ]
        )
        criteria = [
            "mem('finance.investment_accounts.last.status') == 'active'",
            f"mem('finance.investment_accounts.last.name') == '{variant['name']}'",
            f"mem('finance.investment_accounts.last.type') == '{variant['acc_type']}'",
            f"mem('finance.investment_accounts.last.balance') == '{variant['initial_deposit']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "D6-investment-account/v2",
                "option": option,
                "requirement_id": f"name={variant['name'].replace(' ', '_')}|type={variant['acc_type']}|deposit={variant['initial_deposit']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_d6"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/investments.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-investment-account"},
                {"t": 2, "act": "type", "selector": "#new-name", "value": variant["name"]},
                {"t": 3, "act": "select", "selector": "#new-type", "value": variant["acc_type"]},
                {"t": 4, "act": "type", "selector": "#initial-deposit", "value": variant["initial_deposit"].replace('.0', '')},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": "#investment-accounts-list .card"},
            ],
        }

    if task_id == "E2-transport-topup":
        variant = random.choice(
            [
                {
                    "mode": "topup",
                    "amount": "50",
                    "balance": "75.5",
                    "last_topup_amount": "50.0",
                    "goal_text": "Top up the transport card by 50.",
                },
                {
                    "mode": "topup",
                    "amount": "120",
                    "balance": "145.5",
                    "last_topup_amount": "120.0",
                    "goal_text": "Top up the transport card by 120.",
                },
                {
                    "mode": "auto_recharge",
                    "threshold": "15",
                    "threshold_mem": "15.0",
                    "amount": "80",
                    "amount_mem": "80.0",
                    "goal_text": "Enable auto recharge when balance drops below 15 and reload 80 each time.",
                },
                {
                    "mode": "topup",
                    "amount": "30",
                    "balance": "55.5",
                    "last_topup_amount": "30.0",
                    "goal_text": "Top up the transport card by 30.",
                },
                {
                    "mode": "auto_recharge",
                    "threshold": "10",
                    "threshold_mem": "10.0",
                    "amount": "60",
                    "amount_mem": "60.0",
                    "goal_text": "Enable auto recharge when balance drops below 10 and reload 60 each time.",
                },
                {
                    "mode": "topup",
                    "amount": "200",
                    "balance": "225.5",
                    "last_topup_amount": "200.0",
                    "goal_text": "Top up the transport card by 200.",
                },
            ]
        )
        if variant["mode"] == "topup":
            criteria = [
                f"mem('transport.card.balance') == '{variant['balance']}'",
                f"mem('transport.card.last_topup_amount') == '{variant['last_topup_amount']}'",
            ]
            trace = [
                {"t": 0, "act": "open", "url": "http://localhost:8014/trip.local/transport-card.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-topup"},
                {"t": 2, "act": "type", "selector": "#topup-amount", "value": variant["amount"]},
                {"t": 3, "act": "click", "selector": ".modal-confirm"},
                {"t": 4, "act": "wait", "selector": "#card-balance"},
            ]
            requirement_id = f"mode=topup|amount={variant['amount']}"
        else:
            criteria = [
                "mem('transport.card.auto_recharge.enabled') == '1'",
                f"mem('transport.card.auto_recharge.threshold') == '{variant['threshold_mem']}'",
                f"mem('transport.card.auto_recharge.amount') == '{variant['amount_mem']}'",
            ]
            trace = [
                {"t": 0, "act": "open", "url": "http://localhost:8014/trip.local/transport-card.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-auto-recharge"},
                {"t": 2, "act": "click", "selector": "#ar-enable"},
                {"t": 3, "act": "type", "selector": "#ar-threshold", "value": variant["threshold"]},
                {"t": 4, "act": "type", "selector": "#ar-amount", "value": variant["amount"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": "#auto-recharge-status"},
            ]
            requirement_id = f"mode=auto_recharge|threshold={variant['threshold']}|amount={variant['amount']}"
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "E2-transport-topup/v2",
                "option": option,
                "requirement_id": requirement_id,
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_e2"),
            "oracle_trace_override": trace,
        }

    if task_id == "E4-visa-requirements":
        variant = random.choice(
            [
                {
                    "destination": "Japan",
                    "visa_type": "短期滞在 (旅游)",
                    "stay_duration": "15天 / 30天 / 90天",
                    "goal_text": "Check the tourist visa requirements for Japan.",
                },
                {
                    "destination": "France",
                    "visa_type": "申根签证 (Type C)",
                    "stay_duration": "最长90天 (180天内)",
                    "goal_text": "Check the visa requirements for France.",
                },
                {
                    "destination": "Singapore",
                    "visa_type": "需要查询使馆官网",
                    "stay_duration": "未知",
                    "goal_text": "Check the visa requirements for Singapore.",
                },
            ]
        )
        criteria = [
            f"mem('visa.search.last.destination') == '{variant['destination']}'",
            f"mem('visa.search.last.visa_type') == '{variant['visa_type']}'",
            f"mem('visa.search.last.stay_duration') == '{variant['stay_duration']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "E4-visa-requirements/v2",
                "option": option,
                "requirement_id": f"destination={variant['destination']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_e4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/trip.local/visa-requirements.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#destination-country", "value": variant["destination"]},
                {"t": 2, "act": "click", "selector": "#search-btn"},
                {"t": 3, "act": "wait", "selector": "#visa-result .card"},
            ],
        }

    if task_id == "E5-expense-report":
        variant = random.choice(
            [
                {
                    "report_id": "EXP-3344",
                    "total": "1200",
                    "total_mem": "1200.0",
                    "description": "Conference travel expenses",
                    "pnr": "PNR-0000",
                    "goal_text": "Submit travel expense report EXP-3344 for 1200 linked to PNR-0000.",
                },
                {
                    "report_id": "EXP-5520",
                    "total": "480",
                    "total_mem": "480.0",
                    "description": "Client visit rail expenses",
                    "pnr": "PNR-5520",
                    "goal_text": "Submit travel expense report EXP-5520 for 480 linked to PNR-5520.",
                },
                {
                    "report_id": "EXP-6631",
                    "total": "860",
                    "total_mem": "860.0",
                    "description": "Hotel and taxi reimbursement",
                    "pnr": "PNR-6631",
                    "goal_text": "Submit travel expense report EXP-6631 for 860 linked to PNR-6631.",
                },
                {
                    "report_id": "EXP-7742",
                    "total": "1520",
                    "total_mem": "1520.0",
                    "description": "International conference airfare",
                    "pnr": "PNR-7742",
                    "goal_text": "Submit travel expense report EXP-7742 for 1520 linked to PNR-7742.",
                },
                {
                    "report_id": "EXP-8810",
                    "total": "235",
                    "total_mem": "235.0",
                    "description": "Airport transfer reimbursement",
                    "pnr": "PNR-8810",
                    "goal_text": "Submit travel expense report EXP-8810 for 235 linked to PNR-8810.",
                },
            ]
        )
        criteria = [
            f"mem('expenses.last.id') == '{variant['report_id']}'",
            f"mem('expenses.last.total') == '{variant['total_mem']}'",
            f"mem('expenses.last.pnr') == '{variant['pnr']}'",
            f"mem('expenses.last.description') includes '{variant['description'].split()[0]}'",
            "url().includes('/bank.local/expense-report.html')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "E5-expense-report/v2",
                "option": option,
                "requirement_id": f"report={variant['report_id']}|total={variant['total']}|pnr={variant['pnr']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_e5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/expense-report.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#report-id", "value": variant["report_id"]},
                {"t": 2, "act": "type", "selector": "#total-amount", "value": variant["total"]},
                {"t": 3, "act": "type", "selector": "#description", "value": variant["description"]},
                {"t": 4, "act": "type", "selector": "#linked-pnr", "value": variant["pnr"]},
                {"t": 5, "act": "click", "selector": "button.btn.pri.lg"},
                {"t": 6, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "E6-flight-change":
        variant = random.choice(
            [
                {
                    "policy": "min-cost",
                    "new_date": "2025-01-16",
                    "goal_text": "Rebook flight PNR9ZZ with the lowest fare replacement policy for 2025-01-16.",
                },
                {
                    "policy": "morning-priority",
                    "new_date": "2025-01-17",
                    "goal_text": "Rebook flight PNR9ZZ with the morning departure priority policy for 2025-01-17.",
                },
                {
                    "policy": "flexible-change",
                    "new_date": "2025-01-18",
                    "goal_text": "Rebook flight PNR9ZZ with the flexible change policy for 2025-01-18.",
                },
            ]
        )
        criteria = [
            "mem('travel.rebook.last.pnr') == 'PNR9ZZ'",
            f"mem('travel.rebook.last.policy') == '{variant['policy']}'",
            f"mem('travel.rebook.last.date') == '{variant['new_date']}'",
            "text('#ticket-status') == 'Rebooked'",
            f"text('#status-message') includes '{variant['new_date']}'",
            "url().includes('status=rebooked')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "E6-flight-change/v2",
                "option": option,
                "requirement_id": f"policy={variant['policy']}|date={variant['new_date']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_e6"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/trip.local/manage/PNR9ZZ.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#rebook-policy", "value": variant["policy"]},
                {"t": 2, "act": "type", "selector": "#rebook-date", "value": variant["new_date"]},
                {"t": 3, "act": "click", "selector": "#rebook-flight-btn"},
                {"t": 4, "act": "wait", "selector": "#status-message"},
            ],
        }

    if task_id == "E7-long-haul-trip":
        variant = random.choice(
            [
                {
                    "destination": "Japan",
                    "passport_number": "E12345678",
                    "departure": "Shanghai",
                    "date": "2026-02-10",
                    "goal_text": "Apply for a Japan visa with passport E12345678, wait for approval, then book the Japan flight from Shanghai on 2026-02-10.",
                },
                {
                    "destination": "France",
                    "passport_number": "F99887766",
                    "departure": "Beijing",
                    "date": "2026-03-06",
                    "goal_text": "Apply for a France visa with passport F99887766, wait for approval, then book the France flight from Beijing on 2026-03-06.",
                },
                {
                    "destination": "USA",
                    "passport_number": "U55667788",
                    "departure": "Guangzhou",
                    "date": "2026-04-12",
                    "goal_text": "Apply for a USA visa with passport U55667788, wait for approval, then book the USA flight from Guangzhou on 2026-04-12.",
                },
                {
                    "destination": "Japan",
                    "passport_number": "J24681012",
                    "departure": "Shenzhen",
                    "date": "2026-05-09",
                    "goal_text": "Apply for a Japan visa with passport J24681012, wait for approval, then book the Japan flight from Shenzhen on 2026-05-09.",
                },
                {
                    "destination": "France",
                    "passport_number": "F13579135",
                    "departure": "Nanjing",
                    "date": "2026-06-14",
                    "goal_text": "Apply for a France visa with passport F13579135, wait for approval, then book the France flight from Nanjing on 2026-06-14.",
                },
                {
                    "destination": "USA",
                    "passport_number": "U22446688",
                    "departure": "Chengdu",
                    "date": "2026-07-20",
                    "goal_text": "Apply for a USA visa with passport U22446688, wait for approval, then book the USA flight from Chengdu on 2026-07-20.",
                },
            ]
        )
        criteria = [
            "mem('gov.visa_applications.last.status') == 'approved'",
            f"mem('gov.visa_applications.last.destination') == '{variant['destination']}'",
            "mem('travel.flight.last.pnr') includes 'PNR-'",
            f"mem('travel.flight.last.destination') == '{variant['destination']}'",
            "mem('trip_booked') == 'true'",
            "url().includes('/trip.local/manage.html')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "E7-long-haul-trip/v2",
                "option": option,
                "requirement_id": f"destination={variant['destination']}|date={variant['date']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_e7"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/gov.local/visa-apply.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#destination", "value": variant["destination"]},
                {"t": 2, "act": "type", "selector": "#passport-number", "value": variant["passport_number"]},
                {"t": 3, "act": "click", "selector": "button.btn.pri"},
                {"t": 4, "act": "click", "selector": "#debug-visa-time-travel"},
                {"t": 5, "act": "wait", "selector": "#application-status .badge.ok"},
                {
                    "t": 6,
                    "act": "open",
                    "url": f"http://localhost:8014/trip.local/flights.html?clean=true&departure={variant['departure']}&destination={variant['destination']}&date={variant['date']}",
                },
                {"t": 7, "act": "wait", "selector": "#book-flight-CA1881"},
                {"t": 8, "act": "click", "selector": "#book-flight-CA1881"},
                {"t": 9, "act": "wait", "selector": "#trips-list .card"},
            ],
        }

    if task_id == "F1-calendar-aggregation":
        variant = random.choice(
            [
                {
                    "title": "Team Sync",
                    "date": "2026-01-15",
                    "time": "10:00",
                    "event_type": "work",
                    "description": "Quarterly planning discussion",
                    "goal_text": "Add a work event Team Sync on 2026-01-15 at 10:00.",
                },
                {
                    "title": "Dentist Follow-up",
                    "date": "2026-01-16",
                    "time": "15:30",
                    "event_type": "personal",
                    "description": "Routine dental follow-up",
                    "goal_text": "Add a personal event Dentist Follow-up on 2026-01-16 at 15:30.",
                },
                {
                    "title": "Product Review",
                    "date": "2026-01-20",
                    "time": "09:15",
                    "event_type": "work",
                    "description": "Review launch metrics with the team",
                    "goal_text": "Add a work event Product Review on 2026-01-20 at 09:15.",
                },
                {
                    "title": "Investor Call",
                    "date": "2026-01-22",
                    "time": "16:00",
                    "event_type": "work",
                    "description": "Quarterly investor questions and strategy recap",
                    "goal_text": "Add a work event Investor Call on 2026-01-22 at 16:00.",
                },
                {
                    "title": "Visa Interview",
                    "date": "2026-01-24",
                    "time": "08:45",
                    "event_type": "personal",
                    "description": "Embassy appointment for travel visa",
                    "goal_text": "Add a personal event Visa Interview on 2026-01-24 at 08:45.",
                },
                {
                    "title": "Budget Workshop",
                    "date": "2026-01-27",
                    "time": "13:30",
                    "event_type": "work",
                    "description": "Finance planning workshop with the operations team",
                    "goal_text": "Add a work event Budget Workshop on 2026-01-27 at 13:30.",
                },
            ]
        )
        criteria = [
            "mem('calendar.events.last.id') includes 'EVE-'",
            f"mem('calendar.events.last.title') == '{variant['title']}'",
            f"mem('calendar.events.last.date') == '{variant['date']}'",
            f"mem('calendar.events.last.time') == '{variant['time']}'",
            f"mem('calendar.events.last.type') == '{variant['event_type']}'",
            "exists('#event-list .card')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "F1-calendar-aggregation/v2",
                "option": option,
                "requirement_id": (
                    f"title={variant['title'].replace(' ', '_')}|date={variant['date']}|time={variant['time']}|type={variant['event_type']}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_f1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/work.local/calendar.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "type", "selector": "#event-title", "value": variant["title"]},
                {"t": 3, "act": "type", "selector": "#event-date", "value": variant["date"]},
                {"t": 4, "act": "type", "selector": "#event-time", "value": variant["time"]},
                {"t": 5, "act": "select", "selector": "#event-type", "value": variant["event_type"]},
                {"t": 6, "act": "type", "selector": "#event-description", "value": variant["description"]},
                {"t": 7, "act": "click", "selector": ".modal-confirm"},
                {"t": 8, "act": "wait", "selector": f"#event-list .card:has-text('{variant['title']}')"},
            ],
        }

    if task_id == "F2-conference-reg":
        variant = random.choice(
            [
                {
                    "report_id": "EXP-2201",
                    "total": "980",
                    "total_mem": "980.0",
                    "description": "Conference registration and travel",
                    "pnr": "PNR-2201",
                    "goal_text": "Submit the conference registration expense report EXP-2201 for 980 linked to PNR-2201.",
                },
                {
                    "report_id": "EXP-3302",
                    "total": "650",
                    "total_mem": "650.0",
                    "description": "Workshop attendance reimbursement",
                    "pnr": "PNR-3302",
                    "goal_text": "Submit the workshop reimbursement expense report EXP-3302 for 650 linked to PNR-3302.",
                },
                {
                    "report_id": "EXP-4410",
                    "total": "1420",
                    "total_mem": "1420.0",
                    "description": "Conference booth setup and travel",
                    "pnr": "PNR-4410",
                    "goal_text": "Submit the conference booth and travel expense report EXP-4410 for 1420 linked to PNR-4410.",
                },
            ]
        )
        criteria = [
            f"mem('expenses.last.id') == '{variant['report_id']}'",
            f"mem('expenses.last.total') == '{variant['total_mem']}'",
            f"mem('expenses.last.pnr') == '{variant['pnr']}'",
            f"mem('expenses.last.description') includes '{variant['description'].split()[0]}'",
            "url().includes('/bank.local/expense-report.html')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "F2-conference-reg/v2",
                "option": option,
                "requirement_id": f"report={variant['report_id']}|total={variant['total']}|pnr={variant['pnr']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_f2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/expense-report.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#report-id", "value": variant["report_id"]},
                {"t": 2, "act": "type", "selector": "#total-amount", "value": variant["total"]},
                {"t": 3, "act": "type", "selector": "#description", "value": variant["description"]},
                {"t": 4, "act": "type", "selector": "#linked-pnr", "value": variant["pnr"]},
                {"t": 5, "act": "click", "selector": "button.btn.pri.lg"},
                {"t": 6, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "F4-email-tracking":
        variant = random.choice(
            [
                {
                    "subject": "Project Kickoff Follow-up",
                    "sender": "manager@example.com",
                    "summary": "Please confirm next week's kickoff schedule.",
                    "goal_text": "Track the email thread Project Kickoff Follow-up from manager@example.com.",
                },
                {
                    "subject": "Budget Review Request",
                    "sender": "finance@example.com",
                    "summary": "Need your feedback on the Q1 budget sheet.",
                    "goal_text": "Track the email thread Budget Review Request from finance@example.com.",
                },
                {
                    "subject": "Paper Revision Notes",
                    "sender": "editor@example.com",
                    "summary": "Reviewer comments are ready for your revision.",
                    "goal_text": "Track the email thread Paper Revision Notes from editor@example.com.",
                },
            ]
        )
        criteria = [
            "mem('work.email_threads.last.id') includes 'MSG-'",
            f"mem('work.email_threads.last.subject') == '{variant['subject']}'",
            f"mem('work.email_threads.last.sender') == '{variant['sender']}'",
            "mem('work.email_threads.last.status') == 'pending'",
            "exists('#email-list .card')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "F4-email-tracking/v2",
                "option": option,
                "requirement_id": f"subject={variant['subject'].replace(' ', '_')}|sender={variant['sender']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_f4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/work.local/email-tracking.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "type", "selector": "#email-subject", "value": variant["subject"]},
                {"t": 3, "act": "type", "selector": "#email-sender", "value": variant["sender"]},
                {"t": 4, "act": "type", "selector": "#email-summary", "value": variant["summary"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#email-list .card:has-text('{variant['subject']}')"},
            ],
        }

    if task_id == "F5-receipt-archive":
        variant = random.choice(
            [
                {
                    "doc_type": "receipt",
                    "file_path": "utility_bill_dec.pdf",
                    "file_name": "utility_bill_dec.pdf",
                    "goal_text": "Archive utility_bill_dec.pdf as a receipt.",
                },
                {
                    "doc_type": "contract",
                    "file_path": "insurance_policy.pdf",
                    "file_name": "insurance_policy.pdf",
                    "goal_text": "Archive insurance_policy.pdf as a contract.",
                },
                {
                    "doc_type": "other",
                    "file_path": "conference_receipt.pdf",
                    "file_name": "conference_receipt.pdf",
                    "goal_text": "Archive conference_receipt.pdf as a general document.",
                },
                {
                    "doc_type": "id_card",
                    "file_path": "resident_id_scan.pdf",
                    "file_name": "resident_id_scan.pdf",
                    "goal_text": "Archive resident_id_scan.pdf as an identity document.",
                },
                {
                    "doc_type": "receipt",
                    "file_path": "taxi_invoice_march.pdf",
                    "file_name": "taxi_invoice_march.pdf",
                    "goal_text": "Archive taxi_invoice_march.pdf as a receipt.",
                },
                {
                    "doc_type": "contract",
                    "file_path": "roommate_agreement.pdf",
                    "file_name": "roommate_agreement.pdf",
                    "goal_text": "Archive roommate_agreement.pdf as a contract.",
                },
            ]
        )
        criteria = [
            "mem('cloud.documents.last.id') includes 'DOC-'",
            f"mem('cloud.documents.last.type') == '{variant['doc_type']}'",
            f"mem('cloud.documents.last.name') == '{variant['file_name']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "F5-receipt-archive/v2",
                "option": option,
                "requirement_id": f"type={variant['doc_type']}|file={variant['file_name']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_f5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/cloud.local/index.html?clean=true"},
                {"t": 1, "act": "click", "selector": ".upload-area"},
                {"t": 2, "act": "select", "selector": "#doc-type", "value": variant["doc_type"]},
                {"t": 3, "act": "upload", "selector": "#file-upload", "value": variant["file_path"]},
                {"t": 4, "act": "click", "selector": ".modal-confirm"},
                {"t": 5, "act": "wait", "selector": ".file-item"},
            ],
        }

    if task_id == "F3-paper-submission":
        variant = random.choice(
            [
                {
                    "title": "Continual Web Agents",
                    "journal": "Nature Machine Intelligence",
                    "authors": "Tianyu Hu, Alice Zhang",
                    "file": "continual_web_agents.pdf",
                    "goal_text": "Submit the paper Continual Web Agents to Nature Machine Intelligence using file continual_web_agents.pdf.",
                },
                {
                    "title": "Memory-Aware Browser Benchmark",
                    "journal": "ACL Findings",
                    "authors": "Tianyu Hu, Bob Li",
                    "file": "memory_browser_benchmark.pdf",
                    "goal_text": "Submit the paper Memory-Aware Browser Benchmark to ACL Findings using file memory_browser_benchmark.pdf.",
                },
                {
                    "title": "Persistent Planning in Web RL",
                    "journal": "IEEE Transactions on Pattern Analysis",
                    "authors": "Tianyu Hu, Carol Xu",
                    "file": "persistent_planning_webrl.pdf",
                    "goal_text": "Submit the paper Persistent Planning in Web RL to IEEE Transactions on Pattern Analysis using file persistent_planning_webrl.pdf.",
                },
                {
                    "title": "Branch-Aware Benchmarking",
                    "journal": "EMNLP Findings",
                    "authors": "Tianyu Hu, David Sun",
                    "file": "branch_aware_benchmarking.pdf",
                    "goal_text": "Submit the paper Branch-Aware Benchmarking to EMNLP Findings using file branch_aware_benchmarking.pdf.",
                },
                {
                    "title": "Stateful Web Memory Agents",
                    "journal": "NeurIPS Datasets and Benchmarks",
                    "authors": "Tianyu Hu, Emma Qian",
                    "file": "stateful_web_memory_agents.pdf",
                    "goal_text": "Submit the paper Stateful Web Memory Agents to NeurIPS Datasets and Benchmarks using file stateful_web_memory_agents.pdf.",
                },
                {
                    "title": "Counterfactual Browser Chains",
                    "journal": "ICLR Workshop on Interactive Agents",
                    "authors": "Tianyu Hu, Frank Zhou",
                    "file": "counterfactual_browser_chains.pdf",
                    "goal_text": "Submit the paper Counterfactual Browser Chains to the ICLR Workshop on Interactive Agents using file counterfactual_browser_chains.pdf.",
                },
            ]
        )
        criteria = [
            "mem('work.paper_submissions.last.id') includes 'SUB-'",
            f"mem('work.paper_submissions.last.title') == '{variant['title']}'",
            f"mem('work.paper_submissions.last.journal') == '{variant['journal']}'",
            f"mem('work.paper_submissions.last.file') == '{variant['file']}'",
            "mem('work.paper_submissions.last.status') == 'submitted'",
            f"exists(\"#submissions-list .card:has-text('{variant['title']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "F3-paper-submission/v2",
                "option": option,
                "requirement_id": f"title={variant['title'].replace(' ', '_')}|journal={variant['journal'].replace(' ', '_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_f3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/work.local/paper-submission.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "type", "selector": "#paper-title", "value": variant["title"]},
                {"t": 3, "act": "type", "selector": "#journal-name", "value": variant["journal"]},
                {"t": 4, "act": "type", "selector": "#authors", "value": variant["authors"]},
                {"t": 5, "act": "type", "selector": "#paper-file", "value": variant["file"]},
                {"t": 6, "act": "click", "selector": ".modal-confirm"},
                {"t": 7, "act": "wait", "selector": f"#submissions-list .card:has-text('{variant['title']}')"},
            ],
        }

    if task_id == "G1-doctor-appt":
        variant = random.choice(
            [
                {
                    "appointment_id": "APT-9001",
                    "doctor_id": "DR-001",
                    "slot": "2025-12-02T09:00",
                    "goal_text": "Book doctor appointment APT-9001 with doctor DR-001 at 2025-12-02T09:00.",
                },
                {
                    "appointment_id": "APT-9012",
                    "doctor_id": "DR-004",
                    "slot": "2025-12-04T14:30",
                    "goal_text": "Book doctor appointment APT-9012 with doctor DR-004 at 2025-12-04T14:30.",
                },
                {
                    "appointment_id": "APT-9024",
                    "doctor_id": "DR-007",
                    "slot": "2025-12-06T11:15",
                    "goal_text": "Book doctor appointment APT-9024 with doctor DR-007 at 2025-12-06T11:15.",
                },
                {
                    "appointment_id": "APT-9036",
                    "doctor_id": "DR-010",
                    "slot": "2025-12-09T08:30",
                    "goal_text": "Book doctor appointment APT-9036 with doctor DR-010 at 2025-12-09T08:30.",
                },
                {
                    "appointment_id": "APT-9048",
                    "doctor_id": "DR-012",
                    "slot": "2025-12-11T16:45",
                    "goal_text": "Book doctor appointment APT-9048 with doctor DR-012 at 2025-12-11T16:45.",
                },
                {
                    "appointment_id": "APT-9060",
                    "doctor_id": "DR-015",
                    "slot": "2025-12-14T10:20",
                    "goal_text": "Book doctor appointment APT-9060 with doctor DR-015 at 2025-12-14T10:20.",
                },
            ]
        )
        criteria = [
            f"mem('health.appointment.last_id') == '{variant['appointment_id']}'",
            f"mem('health.appointment.doctor_id') == '{variant['doctor_id']}'",
            f"mem('health.appointment.slot') == '{variant['slot']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "G1-doctor-appt/v2",
                "option": option,
                "requirement_id": f"appointment={variant['appointment_id']}|doctor={variant['doctor_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_g1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/appointments.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#appointmentId", "value": variant["appointment_id"]},
                {"t": 2, "act": "type", "selector": "#doctorId", "value": variant["doctor_id"]},
                {"t": 3, "act": "type", "selector": "#slot", "value": variant["slot"]},
                {"t": 4, "act": "click", "selector": "#book-appointment-btn"},
                {"t": 5, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "G2-insurance-policy":
        variant = random.choice(
            [
                {
                    "card_id": "plan-basic",
                    "plan_name": "Basic Care Plan",
                    "provider": "Nova Health",
                    "goal_text": "Purchase the Basic Care Plan from Nova Health.",
                },
                {
                    "card_id": "plan-premium-plus",
                    "plan_name": "Premium Plus Plan",
                    "provider": "Prime Shield",
                    "goal_text": "Purchase the Premium Plus Plan from Prime Shield.",
                },
                {
                    "card_id": "plan-family-flex",
                    "plan_name": "Family Flex Plan",
                    "provider": "Harbor Mutual",
                    "goal_text": "Purchase the Family Flex Plan from Harbor Mutual.",
                },
            ]
        )
        criteria = [
            "mem('health.insurance.active') == 1",
            f"mem('health.insurance.plan_name') == '{variant['plan_name']}'",
            f"mem('health.insurance.provider') == '{variant['provider']}'",
            "mem('health.insurance.policy_number') includes 'POL-'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "G2-insurance-policy/v2",
                "option": option,
                "requirement_id": f"plan={variant['card_id']}|provider={variant['provider'].replace(' ', '_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_g2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/insurance.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#{variant['card_id']} button"},
                {"t": 2, "act": "click", "selector": ".modal-confirm"},
                {"t": 3, "act": "wait", "selector": "#current-policy .badge.ok"},
            ],
        }

    if task_id == "G3-medical-claim":
        variant = random.choice(
            [
                {
                    "claim_id": "CLM-5501",
                    "appointment_id": "APT-9001",
                    "amount": "250.0",
                    "policy_id": "P-9001",
                    "goal_text": "Submit insurance claim CLM-5501 for appointment APT-9001 under policy P-9001 for 250.",
                },
                {
                    "claim_id": "CLM-6602",
                    "appointment_id": "APT-9012",
                    "amount": "180.0",
                    "policy_id": "P-9012",
                    "goal_text": "Submit insurance claim CLM-6602 for appointment APT-9012 under policy P-9012 for 180.",
                },
                {
                    "claim_id": "CLM-7714",
                    "appointment_id": "APT-9024",
                    "amount": "320.0",
                    "policy_id": "P-9024",
                    "goal_text": "Submit insurance claim CLM-7714 for appointment APT-9024 under policy P-9024 for 320.",
                },
            ]
        )
        criteria = [
            f"mem('insurance.claim.last.id') == '{variant['claim_id']}'",
            "mem('insurance.claim.last.status') == 'processing'",
            f"mem('insurance.claim.last.appointment_id') == '{variant['appointment_id']}'",
            f"mem('insurance.claim.last.amount') == '{variant['amount']}'",
            f"mem('insurance.claim.last.policy_id') == '{variant['policy_id']}'",
            "exists('#claim-state')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "G3-medical-claim/v2",
                "option": option,
                "requirement_id": f"claim={variant['claim_id']}|policy={variant['policy_id']}|amount={variant['amount']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_g3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/claims.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#claimId", "value": variant["claim_id"]},
                {"t": 2, "act": "type", "selector": "#appointmentId", "value": variant["appointment_id"]},
                {"t": 3, "act": "type", "selector": "#amount", "value": variant["amount"].replace('.0', '')},
                {"t": 4, "act": "type", "selector": "#policyId", "value": variant["policy_id"]},
                {"t": 5, "act": "click", "selector": "#submit-claim-btn"},
                {"t": 6, "act": "wait", "selector": "#claim-state"},
            ],
        }

    if task_id == "G4-gym-membership":
        variant = random.choice(
            [
                {
                    "rx_id": "RX-1001",
                    "medication": "Amoxicillin 250mg",
                    "goal_text": "Refill prescription RX-1001 for Amoxicillin 250mg.",
                },
                {
                    "rx_id": "RX-2202",
                    "medication": "Ibuprofen 400mg",
                    "goal_text": "Refill prescription RX-2202 for Ibuprofen 400mg.",
                },
                {
                    "rx_id": "RX-3303",
                    "medication": "Vitamin D 1000IU",
                    "goal_text": "Refill prescription RX-3303 for Vitamin D 1000IU.",
                },
            ]
        )
        criteria = [
            f"json('env','health.prescriptions.{variant['rx_id']}.medication') == '{variant['medication']}'",
            f"json('env','health.prescriptions.{variant['rx_id']}.refills_left') == 1",
            f"json('env','health.prescriptions.{variant['rx_id']}.last_refill') != ''",
            "url().includes('/health.local/records.html')",
            f"exists(\"#records-list .record-card:has-text('Prescription - {variant['rx_id']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "G4-prescription-refill/v2",
                "option": option,
                "requirement_id": f"rx={variant['rx_id']}|med={variant['medication'].replace(' ', '_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_g4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/refill.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#prescriptionId", "value": variant["rx_id"]},
                {"t": 2, "act": "type", "selector": "#medication", "value": variant["medication"]},
                {"t": 3, "act": "click", "selector": ".btn-submit"},
                {"t": 4, "act": "wait", "selector": f"#records-list .record-card:has-text('Prescription - {variant['rx_id']}')"},
            ],
        }

    if task_id == "G5-health-plan":
        plan = random.choice(
            [
                {"plan_id": "standard", "plan_name": "Standard Health Plan", "goal_text": "Activate the Standard Health Plan."},
                {"plan_id": "premium", "plan_name": "Premium Health Plan", "goal_text": "Activate the Premium Health Plan."},
            ]
        )
        criteria = [
            "mem('health.plan.status') == 'active'",
            f"mem('health.plan.name') == '{plan['plan_name']}'",
            f"exists('#plan-{plan['plan_id']}.active')",
        ]
        return {
            "instruction": add_noise(plan["goal_text"]),
            "template_info": {
                "template_id": "G5-health-plan/v2",
                "option": option,
                "requirement_id": f"plan_id={plan['plan_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(plan),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_g5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/plan.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#plan-{plan['plan_id']} button"},
                {"t": 2, "act": "wait", "selector": f"#plan-{plan['plan_id']}.active"},
            ],
        }

    if task_id == "G6-vaccine-mgmt":
        variant = random.choice(
            [
                {
                    "vaccine_type": "flu",
                    "appointment_date": "2025-12-17",
                    "appointment_time": "09:00",
                    "goal_text": "Book a flu vaccine appointment for 2025-12-17 at 09:00.",
                },
                {
                    "vaccine_type": "covid",
                    "appointment_date": "2025-12-18",
                    "appointment_time": "10:00",
                    "goal_text": "Book a COVID-19 booster appointment for 2025-12-18 at 10:00.",
                },
                {
                    "vaccine_type": "mmr",
                    "appointment_date": "2025-12-19",
                    "appointment_time": "11:00",
                    "goal_text": "Book an MMR vaccine appointment for 2025-12-19 at 11:00.",
                },
            ]
        )
        criteria = [
            "mem('health.vaccines.last.status') == 'booked'",
            f"mem('health.vaccines.last.type') == '{variant['vaccine_type']}'",
            f"mem('health.vaccines.last.date') == '{variant['appointment_date']}'",
            f"mem('health.vaccines.last.time') == '{variant['appointment_time']}'",
            "exists('#records-list .badge.ok')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "G6-vaccine-mgmt/v2",
                "option": option,
                "requirement_id": f"type={variant['vaccine_type']}|date={variant['appointment_date']}|time={variant['appointment_time']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_g6"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/vaccine.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#vaccine-type", "value": variant["vaccine_type"]},
                {"t": 2, "act": "type", "selector": "#appt-date", "value": variant["appointment_date"]},
                {"t": 3, "act": "select", "selector": "#appt-time", "value": variant["appointment_time"]},
                {"t": 4, "act": "click", "selector": "#book-vaccine-btn"},
                {"t": 5, "act": "wait", "selector": "#records-list .badge.ok"},
            ],
        }

    if task_id == "H1-address-change":
        variant = random.choice(
            [
                {
                    "new_address": "742 Evergreen Terrace",
                    "zip_code": "12345",
                    "proof_document": "proof_of_address.pdf",
                    "goal_text": "Submit an address change to 742 Evergreen Terrace with zip code 12345.",
                },
                {
                    "new_address": "88 River Rd, Springfield",
                    "zip_code": "54321",
                    "proof_document": "bank_statement.pdf",
                    "goal_text": "Submit an address change to 88 River Rd, Springfield with zip code 54321.",
                },
                {
                    "new_address": "21 Harbor Ave, Springfield",
                    "zip_code": "10011",
                    "proof_document": "lease_contract.pdf",
                    "goal_text": "Submit an address change to 21 Harbor Ave, Springfield with zip code 10011.",
                },
            ]
        )
        criteria = [
            "mem('gov.profile.address.verified') == 'true'",
            f"mem('user_profile.address.current_address') == '{variant['new_address']}'",
            f"mem('user_profile.address.zip_code') == '{variant['zip_code']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "H1-address-change/v2",
                "option": option,
                "requirement_id": f"zip={variant['zip_code']}|address={variant['new_address'].replace(' ', '_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_h1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/gov.local/address-change.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#new-address", "value": variant["new_address"]},
                {"t": 2, "act": "type", "selector": "#zip-code", "value": variant["zip_code"]},
                {"t": 3, "act": "select", "selector": "#proof-document", "value": variant["proof_document"]},
                {"t": 4, "act": "click", "selector": "#submit-addr-btn"},
                {"t": 5, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "H2-vehicle-address-update":
        variant = random.choice(
            [
                {
                    "vehicle_id": "V-8821",
                    "new_address": "742 Evergreen Terrace",
                    "notify_insurance": True,
                    "notify_mem": "1",
                    "goal_text": "Update vehicle V-8821 to 742 Evergreen Terrace and notify insurance.",
                },
                {
                    "vehicle_id": "V-8821",
                    "new_address": "88 River Rd, Springfield",
                    "notify_insurance": False,
                    "notify_mem": "0",
                    "goal_text": "Update vehicle V-8821 to 88 River Rd, Springfield without notifying insurance.",
                },
                {
                    "vehicle_id": "V-8821",
                    "new_address": "21 Harbor Ave, Springfield",
                    "notify_insurance": True,
                    "notify_mem": "1",
                    "goal_text": "Update vehicle V-8821 to 21 Harbor Ave, Springfield and notify insurance.",
                },
            ]
        )
        criteria = [
            f"mem('gov.vehicles.last.id') == '{variant['vehicle_id']}'",
            f"mem('gov.vehicles.last.address') == '{variant['new_address']}'",
            f"mem('gov.vehicles.last.insurance_notified') == '{variant['notify_mem']}'",
            f"exists(\"#vehicle-list div:has-text('{variant['new_address']}')\")",
        ]
        trace = [
            {"t": 0, "act": "open", "url": "http://localhost:8014/gov.local/vehicle-registration.html?clean=true"},
            {"t": 1, "act": "select", "selector": "#vehicle-select", "value": variant["vehicle_id"]},
            {"t": 2, "act": "type", "selector": "#new-address", "value": variant["new_address"]},
        ]
        if variant["notify_insurance"]:
            trace.append({"t": 3, "act": "click", "selector": "#notify-insurance"})
        trace.extend(
            [
                {"t": 4, "act": "click", "selector": "#submit-vehicle-address"},
                {"t": 5, "act": "wait", "selector": f"#vehicle-list div:has-text('{variant['new_address']}')"},
            ]
        )
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "H2-vehicle-address-update/v2",
                "option": option,
                "requirement_id": (
                    f"vehicle={variant['vehicle_id']}|notify={variant['notify_mem']}|address={variant['new_address'].replace(' ', '_')}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_h2"),
            "oracle_trace_override": trace,
        }

    if task_id == "H3-permit-renewal":
        renewal = random.choice(
            [
                {
                    "permit_id": "RP-2024-77",
                    "new_expiry": "2026-12-01",
                    "payment_method": "card",
                    "goal_text": "Renew permit RP-2024-77 to 2026-12-01 and pay by card.",
                },
                {
                    "permit_id": "RP-2024-77",
                    "new_expiry": "2027-03-15",
                    "payment_method": "alipay",
                    "goal_text": "Renew permit RP-2024-77 to 2027-03-15 and pay with Alipay.",
                },
            ]
        )
        criteria = [
            f"mem('permits.{renewal['permit_id']}.next_appointment') includes '{renewal['new_expiry']}'",
            f"mem('permits.{renewal['permit_id']}.payment_method') == '{renewal['payment_method']}'",
            "url().includes('/gov.local/permits.html')",
        ]
        return {
            "instruction": add_noise(renewal["goal_text"]),
            "template_info": {
                "template_id": "H3-permit-renewal/v2",
                "option": option,
                "requirement_id": f"expiry={renewal['new_expiry']}|payment={renewal['payment_method']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(renewal),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_h3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/gov.local/permits.html?clean=true"},
                {"t": 1, "act": "click", "selector": ".permit-card:has(.permit-id:has-text('RP-2024-77')) button.btn.pri"},
                {"t": 2, "act": "wait", "selector": "#new-expiry"},
                {"t": 3, "act": "type", "selector": "#new-expiry", "value": renewal["new_expiry"]},
                {"t": 4, "act": "select", "selector": "#payment-method", "value": renewal["payment_method"]},
                {"t": 5, "act": "click", "selector": "button.btn.pri.lg"},
                {"t": 6, "act": "wait", "selector": "#permit-expiry"},
            ],
        }

    if task_id == "H4-parking-permit":
        variant = random.choice(
            [
                {
                    "plate_number": "A-12345",
                    "permit_type": "residential",
                    "duration_months": "12",
                    "goal_text": "Apply for a residential parking permit for plate A-12345 for 12 months.",
                },
                {
                    "plate_number": "B-90888",
                    "permit_type": "business",
                    "duration_months": "6",
                    "goal_text": "Apply for a business parking permit for plate B-90888 for 6 months.",
                },
                {
                    "plate_number": "C-55021",
                    "permit_type": "residential",
                    "duration_months": "3",
                    "goal_text": "Apply for a residential parking permit for plate C-55021 for 3 months.",
                },
            ]
        )
        criteria = [
            "mem('permits.parking.state') == 'submitted'",
            "mem('gov.parking_permits.last.status') == 'active'",
            f"mem('gov.parking_permits.last.plate_number') == '{variant['plate_number']}'",
            f"mem('gov.parking_permits.last.permit_type') == '{variant['permit_type']}'",
            f"mem('gov.parking_permits.last.duration_months') == '{variant['duration_months']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "H4-parking-permit/v2",
                "option": option,
                "requirement_id": (
                    f"type={variant['permit_type']}|plate={variant['plate_number']}|months={variant['duration_months']}"
                ),
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_h4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/gov.local/parking-permits.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-apply-permit"},
                {"t": 2, "act": "type", "selector": "#plate-number", "value": variant["plate_number"]},
                {"t": 3, "act": "select", "selector": "#permit-type", "value": variant["permit_type"]},
                {"t": 4, "act": "type", "selector": "#duration-months", "value": variant["duration_months"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": "#permits-list .badge.ok"},
            ],
        }

    if task_id == "I1-smart-bulb-setup":
        variant = random.choice(
            [
                {
                    "device_id": "BULB-101",
                    "location": "Bedroom",
                    "color": "rgb",
                    "goal_text": "Set up smart bulb BULB-101 in the Bedroom using RGB mode.",
                },
                {
                    "device_id": "BULB-202",
                    "location": "Kitchen",
                    "color": "warm_white",
                    "goal_text": "Set up smart bulb BULB-202 in the Kitchen using warm white mode.",
                },
                {
                    "device_id": "BULB-303",
                    "location": "Study",
                    "color": "white",
                    "goal_text": "Set up smart bulb BULB-303 in the Study using white mode.",
                },
            ]
        )
        criteria = [
            f"mem('devices.{variant['device_id']}.status') == 'active'",
            f"mem('devices.{variant['device_id']}.location') == '{variant['location']}'",
            f"json('env','devices.{variant['device_id']}.color') == '{variant['color']}'",
            f"exists(\"#devices-list:has-text('{variant['location']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "I1-smart-bulb-setup/v2",
                "option": option,
                "requirement_id": f"device={variant['device_id']}|location={variant['location']}|color={variant['color']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_i1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/energy.local/bulb-setup.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#device-id", "value": variant["device_id"]},
                {"t": 2, "act": "type", "selector": "#location", "value": variant["location"]},
                {"t": 3, "act": "select", "selector": "#color", "value": variant["color"]},
                {"t": 4, "act": "click", "selector": "button.btn.pri.lg"},
                {"t": 5, "act": "wait", "selector": f"#devices-list:has-text('{variant['location']}')"},
            ],
        }

    if task_id == "I4-smart-meter":
        reading = random.choice(
            [
                {"reading": 12500.50, "goal_text": "Submit a smart meter reading of 12500.50 kWh."},
                {"reading": 13020.75, "goal_text": "Submit a smart meter reading of 13020.75 kWh."},
                {"reading": 11888.40, "goal_text": "Submit a smart meter reading of 11888.40 kWh."},
                {"reading": 12111.10, "goal_text": "Submit a smart meter reading of 12111.10 kWh."},
                {"reading": 12765.35, "goal_text": "Submit a smart meter reading of 12765.35 kWh."},
                {"reading": 13333.90, "goal_text": "Submit a smart meter reading of 13333.90 kWh."},
            ]
        )
        reading_str = f"{reading['reading']:.2f}"
        criteria = [
            f"mem('meters.meter_data.current_reading') == {reading['reading']}",
            f"mem('meters.meter_data.last_submitted_reading') == {reading['reading']}",
            f"exists(\"#meter-reading:has-text('{reading_str}')\")",
        ]
        return {
            "instruction": add_noise(reading["goal_text"]),
            "template_info": {
                "template_id": "I4-smart-meter/v2",
                "option": option,
                "requirement_id": f"reading={reading_str}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(reading),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_i4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/energy.local/smart-meter.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#new-reading", "value": reading_str},
                {"t": 2, "act": "click", "selector": "button:has-text('Submit')"},
                {"t": 3, "act": "wait", "selector": f"#meter-reading:has-text('{reading_str}')"},
            ],
        }

    if task_id == "J1-course-enroll":
        variant = random.choice(
            [
                {
                    "course_id": "DL101",
                    "goal_text": "Enroll in course DL101.",
                },
                {
                    "course_id": "ML202",
                    "goal_text": "Enroll in course ML202.",
                },
                {
                    "course_id": "ART205",
                    "goal_text": "Enroll in course ART205.",
                },
            ]
        )
        criteria = [
            f"mem('courses.{variant['course_id']}.state') == 'enrolled'",
            "url().includes('/school.local/my-learning.html')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "J1-course-enroll/v2",
                "option": option,
                "requirement_id": f"course={variant['course_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_j1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": f"http://localhost:8014/school.local/course.html?id={variant['course_id']}&clean=true"},
                {"t": 1, "act": "click", "selector": "#enroll-button"},
                {"t": 2, "act": "wait", "selector": "#enrolled-courses-grid .course-card"},
            ],
        }

    if task_id == "J2-library-service":
        variant = random.choice(
            [
                {
                    "applicant_name": "张三",
                    "student_id": "S123456",
                    "book_query": "智能体的崛起",
                    "pickup_date": "2026-03-15",
                    "goal_text": "Apply for a library card for 张三 and reserve 智能体的崛起 for pickup on 2026-03-15.",
                },
                {
                    "applicant_name": "李四",
                    "student_id": "S654321",
                    "book_query": "Web Automation Patterns",
                    "pickup_date": "2026-03-18",
                    "goal_text": "Apply for a library card for 李四 and reserve Web Automation Patterns for pickup on 2026-03-18.",
                },
                {
                    "applicant_name": "王五",
                    "student_id": "S888999",
                    "book_query": "Playwright in Practice",
                    "pickup_date": "2026-03-20",
                    "goal_text": "Apply for a library card for 王五 and reserve Playwright in Practice for pickup on 2026-03-20.",
                },
            ]
        )
        criteria = [
            "mem('library.card.status') == 'active'",
            f"mem('library.card.student_id') == '{variant['student_id']}'",
            "mem('library.reservations.last.status') == 'pending'",
            f"mem('library.reservations.last.book_title') == '{variant['book_query']}'",
            f"mem('library.reservations.last.pickup_date') == '{variant['pickup_date']}'",
            "exists('#reservations-list .card')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "J2-library-service/v2",
                "option": option,
                "requirement_id": f"student={variant['student_id']}|book={variant['book_query'].replace(' ', '_')}|pickup={variant['pickup_date']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_j2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/school.local/library.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button[onclick='openApplyCardModal()']"},
                {"t": 2, "act": "type", "selector": "#applicant-name", "value": variant["applicant_name"]},
                {"t": 3, "act": "type", "selector": "#student-id", "value": variant["student_id"]},
                {"t": 4, "act": "click", "selector": ".modal-confirm"},
                {"t": 5, "act": "wait", "selector": "#library-card-info .badge.ok"},
                {"t": 6, "act": "type", "selector": "#book-query", "value": variant["book_query"]},
                {"t": 7, "act": "click", "selector": "button[onclick='searchAndReserveBook()']"},
                {"t": 8, "act": "type", "selector": "#pickup-date", "value": variant["pickup_date"]},
                {"t": 9, "act": "click", "selector": ".modal-confirm"},
                {"t": 10, "act": "wait", "selector": f"#reservations-list .card:has-text('{variant['book_query']}')"},
            ],
        }

    if task_id == "J3-event-tickets":
        flow = random.choice(
            [
                {
                    "event_index": 0,
                    "event_name": "Campus Music Fest",
                    "recipient_id": "S987654",
                    "final_status": "transferred",
                    "goal_text": "Buy a ticket for Campus Music Fest and transfer it to S987654.",
                },
                {
                    "event_index": 1,
                    "event_name": "Open Lecture Night",
                    "recipient_id": "",
                    "final_status": "refunded",
                    "goal_text": "Buy a ticket for Open Lecture Night and then refund it.",
                },
                {
                    "event_index": 2,
                    "event_name": "Outdoor Film Meetup",
                    "recipient_id": "S112233",
                    "final_status": "transferred",
                    "goal_text": "Buy a ticket for Outdoor Film Meetup and transfer it to S112233.",
                },
                {
                    "event_index": 0,
                    "event_name": "Campus Music Fest",
                    "recipient_id": "",
                    "final_status": "refunded",
                    "goal_text": "Buy a ticket for Campus Music Fest and then refund it.",
                },
                {
                    "event_index": 2,
                    "event_name": "Outdoor Film Meetup",
                    "recipient_id": "",
                    "final_status": "refunded",
                    "goal_text": "Buy a ticket for Outdoor Film Meetup and then refund it.",
                },
            ]
        )
        criteria = [
            f"mem('tickets.user_tickets.last.status') == '{flow['final_status']}'",
            f"mem('tickets.user_tickets.last.event_name') == '{flow['event_name']}'",
            (
                "exists(\"#tickets-list .card .badge.pri\")"
                if flow["final_status"] == "transferred"
                else "exists(\"#tickets-list .card .badge.warn\")"
            ),
        ]
        trace = [
            {"t": 0, "act": "open", "url": "http://localhost:8014/school.local/event-tickets.html?clean=true"},
            {"t": 1, "act": "click", "selector": f"#events-list .card:nth-of-type({flow['event_index'] + 1}) button.btn.pri"},
            {"t": 2, "act": "click", "selector": ".modal-confirm"},
            {"t": 3, "act": "wait", "selector": "#tickets-list .card .badge.ok"},
        ]
        if flow["final_status"] == "transferred":
            trace.extend(
                [
                    {"t": 4, "act": "click", "selector": "#tickets-list .card button.btn:not([disabled])"},
                    {"t": 5, "act": "type", "selector": "#recipient-id", "value": flow["recipient_id"]},
                    {"t": 6, "act": "click", "selector": ".modal-confirm"},
                    {"t": 7, "act": "wait", "selector": "#tickets-list .card .badge.pri"},
                ]
            )
        else:
            trace.extend(
                [
                    {"t": 4, "act": "click", "selector": "#tickets-list .card button.btn.secondary:not([disabled])"},
                    {"t": 5, "act": "click", "selector": ".modal-confirm"},
                    {"t": 6, "act": "wait", "selector": "#tickets-list .card .badge.warn"},
                ]
            )
        return {
            "instruction": add_noise(flow["goal_text"]),
            "template_info": {
                "template_id": "J3-event-tickets/v2",
                "option": option,
                "requirement_id": f"event={flow['event_name'].replace(' ', '_')}|status={flow['final_status']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(flow),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_j3"),
            "oracle_trace_override": trace,
        }

    if task_id == "J4-gear-rental":
        variant = random.choice(
            [
                {
                    "name": "Mountain Bike",
                    "price": "35",
                    "goal_text": "List Mountain Bike as rental gear for 35 per day.",
                },
                {
                    "name": "Camping Tent",
                    "price": "28",
                    "goal_text": "List Camping Tent as rental gear for 28 per day.",
                },
                {
                    "name": "Climbing Helmet",
                    "price": "12",
                    "goal_text": "List Climbing Helmet as rental gear for 12 per day.",
                },
                {
                    "name": "Kayak Paddle",
                    "price": "18",
                    "goal_text": "List Kayak Paddle as rental gear for 18 per day.",
                },
                {
                    "name": "Trail Backpack",
                    "price": "22",
                    "goal_text": "List Trail Backpack as rental gear for 22 per day.",
                },
                {
                    "name": "Snow Goggles",
                    "price": "16",
                    "goal_text": "List Snow Goggles as rental gear for 16 per day.",
                },
            ]
        )
        criteria = [
            f"mem('gear.rentals.last.name') == '{variant['name']}'",
            "mem('gear.rentals.last.status') == 'available'",
            f"exists(\"#rental-gear-list .card:has-text('{variant['name']}')\")",
            f"text('#rental-gear-list') includes '¥{variant['price']}/'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "J4-gear-rental/v2",
                "option": option,
                "requirement_id": f"name={variant['name'].replace(' ', '_')}|price={variant['price']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_j4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/gear-rental.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "type", "selector": "#gear-name", "value": variant["name"]},
                {"t": 3, "act": "select", "selector": "#listing-type", "value": "rent"},
                {"t": 4, "act": "type", "selector": "#gear-price", "value": variant["price"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#rental-gear-list .card:has-text('{variant['name']}')"},
            ],
        }

    if task_id == "J5-skill-certification":
        variant = random.choice(
            [
                {
                    "card_id": "cert-python",
                    "certificate_name": "Certified Python Expert",
                    "goal_text": "Apply for the Certified Python Expert certification.",
                },
                {
                    "card_id": "cert-data",
                    "certificate_name": "Certified Data Analyst",
                    "goal_text": "Apply for the Certified Data Analyst certification.",
                },
                {
                    "card_id": "cert-ops",
                    "certificate_name": "Certified Operations Specialist",
                    "goal_text": "Apply for the Certified Operations Specialist certification.",
                },
            ]
        )
        criteria = [
            "mem('world_state.skills.certified') == 'True'",
            f"mem('world_state.skills.last_certificate') == '{variant['certificate_name']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "J5-skill-certification/v2",
                "option": option,
                "requirement_id": f"certificate={variant['certificate_name'].replace(' ', '_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_j5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/school.local/certification.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#{variant['card_id']} button"},
                {"t": 2, "act": "wait", "selector": "body"},
            ],
        }

    if task_id == "K1-plan-party":
        variant = random.choice(
            [
                {
                    "group_id": "GRP-001",
                    "group_name": "Springfield Neighborhood",
                    "goal_text": "Join the Springfield Neighborhood group.",
                },
                {
                    "group_id": "GRP-002",
                    "group_name": "Tech Enthusiasts",
                    "goal_text": "Join the Tech Enthusiasts group.",
                },
                {
                    "group_id": "GRP-003",
                    "group_name": "Local Foodies",
                    "goal_text": "Join the Local Foodies group.",
                },
            ]
        )
        criteria = [
            f"mem('social.groups.{variant['group_id']}.status') == 'joined'",
            "url().includes('/social.local/my-groups.html')",
            "exists('#my-groups-list .badge.ok')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "K1-plan-party/v2",
                "option": option,
                "requirement_id": f"group={variant['group_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_k1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/social.local/index.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#groups-list .card:nth-of-type({int(variant['group_id'][-1])}) button.btn.pri"},
                {"t": 2, "act": "click", "selector": "#rules-check"},
                {"t": 3, "act": "click", "selector": "#join-modal button.btn.pri"},
                {"t": 4, "act": "wait", "selector": "#my-groups-list .badge.ok"},
            ],
        }

    if task_id == "K2-roommate-split":
        variant = random.choice(
            [
                {
                    "month": "2025-10",
                    "rules": "equal",
                    "goal_text": "Settle roommate expenses for 2025-10 using equal split.",
                },
                {
                    "month": "2025-11",
                    "rules": "by_amount",
                    "goal_text": "Settle roommate expenses for 2025-11 using split by amount.",
                },
                {
                    "month": "2025-12",
                    "rules": "by_percentage",
                    "goal_text": "Settle roommate expenses for 2025-12 using split by percentage.",
                },
                {
                    "month": "2025-10",
                    "rules": "by_amount",
                    "goal_text": "Settle roommate expenses for 2025-10 using split by amount.",
                },
                {
                    "month": "2025-11",
                    "rules": "equal",
                    "goal_text": "Settle roommate expenses for 2025-11 using equal split.",
                },
                {
                    "month": "2025-12",
                    "rules": "equal",
                    "goal_text": "Settle roommate expenses for 2025-12 using equal split.",
                },
            ]
        )
        criteria = [
            f"mem('settlements.{variant['month']}.state') == 'settled'",
            f"json('env','settlements.{variant['month']}.rules') == '{variant['rules']}'",
            f"url().includes('month={variant['month']}')",
            "url().includes('state=settled')",
            "exists('#member-list .member-tag')",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "K2-roommate-split/v2",
                "option": option,
                "requirement_id": f"month={variant['month']}|rules={variant['rules']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_k2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/social.local/split.html?clean=true"},
                {"t": 1, "act": "select", "selector": "#month", "value": variant["month"]},
                {"t": 2, "act": "select", "selector": "#split-rule", "value": variant["rules"]},
                {"t": 3, "act": "click", "selector": "button.btn.pri.lg"},
                {"t": 4, "act": "wait", "selector": "#total-expenses:has-text('200.00')"},
            ],
        }

    if task_id == "K3-charity-donation":
        variant = random.choice(
            [
                {
                    "charity_name": "希望工程",
                    "amount": "100.0",
                    "tax_deductible": True,
                    "tax_mem": "1",
                    "goal_text": "Donate 100 to 希望工程 and request a tax-deductible receipt.",
                },
                {
                    "charity_name": "爱心午餐",
                    "amount": "50.0",
                    "tax_deductible": False,
                    "tax_mem": "0",
                    "goal_text": "Donate 50 to 爱心午餐 without requesting a tax-deductible receipt.",
                },
                {
                    "charity_name": "社区基金",
                    "amount": "200.0",
                    "tax_deductible": True,
                    "tax_mem": "1",
                    "goal_text": "Donate 200 to 社区基金 and request a tax-deductible receipt.",
                },
            ]
        )
        criteria = [
            "mem('charity.donations.last.id') includes 'DON-'",
            f"mem('charity.donations.last.charity_name') == '{variant['charity_name']}'",
            f"mem('charity.donations.last.amount') == '{variant['amount']}'",
            f"mem('charity.donations.last.tax_deductible') == '{variant['tax_mem']}'",
            "exists('#donations-list .card')",
        ]
        trace = [
            {"t": 0, "act": "open", "url": "http://localhost:8014/social.local/charity.html?clean=true"},
            {"t": 1, "act": "click", "selector": "button.btn.pri"},
            {"t": 2, "act": "type", "selector": "#charity-name", "value": variant["charity_name"]},
            {"t": 3, "act": "type", "selector": "#donation-amount", "value": variant["amount"].replace('.0', '')},
        ]
        if variant["tax_deductible"]:
            trace.append({"t": 4, "act": "click", "selector": "#tax-deductible"})
        trace.extend(
            [
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": "#donations-list .card"},
            ]
        )
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "K3-charity-donation/v2",
                "option": option,
                "requirement_id": f"charity={variant['charity_name']}|amount={variant['amount']}|tax={variant['tax_mem']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_k3"),
            "oracle_trace_override": trace,
        }

    if task_id == "L1-password-manager":
        variant = random.choice(
            [
                {
                    "site": "GitHub",
                    "username": "masteryth@example.com",
                    "password": "Gh#Vault2026",
                    "goal_text": "Add a password manager entry for GitHub using username masteryth@example.com.",
                },
                {
                    "site": "Notion",
                    "username": "workspace.bot@example.com",
                    "password": "Notion!Plan88",
                    "goal_text": "Add a password manager entry for Notion using username workspace.bot@example.com.",
                },
                {
                    "site": "OpenRouter",
                    "username": "lab-eval@example.com",
                    "password": "ORouter$Trace77",
                    "goal_text": "Add a password manager entry for OpenRouter using username lab-eval@example.com.",
                },
                {
                    "site": "Anthropic Console",
                    "username": "api.ops@example.com",
                    "password": "Anthropic#Ops91",
                    "goal_text": "Add a password manager entry for Anthropic Console using username api.ops@example.com.",
                },
                {
                    "site": "Overleaf",
                    "username": "paper.drafts@example.com",
                    "password": "Overleaf$Draft6",
                    "goal_text": "Add a password manager entry for Overleaf using username paper.drafts@example.com.",
                },
                {
                    "site": "AWS Billing",
                    "username": "infra-finance@example.com",
                    "password": "AWSbill!Secure42",
                    "goal_text": "Add a password manager entry for AWS Billing using username infra-finance@example.com.",
                },
            ]
        )
        criteria = [
            "mem('security.passwords.last.id') includes 'PW-'",
            f"mem('security.passwords.last.site') == '{variant['site']}'",
            f"mem('security.passwords.last.username') == '{variant['username']}'",
            f"exists(\"#password-list .card:has-text('{variant['site']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "L1-password-manager/v2",
                "option": option,
                "requirement_id": f"site={variant['site']}|user={variant['username'].replace('@', '_at_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_l1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/security.local/password-manager.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "type", "selector": "#site-name", "value": variant["site"]},
                {"t": 3, "act": "type", "selector": "#username-input", "value": variant["username"]},
                {"t": 4, "act": "type", "selector": "#password-input", "value": variant["password"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#password-list .card:has-text('{variant['site']}')"},
            ],
        }

    if task_id == "L2-data-deletion":
        variant = random.choice(
            [
                {
                    "request_type": "deletion",
                    "platform": "Google",
                    "data_scope": "search history, location history",
                    "goal_text": "Submit a deletion request to Google covering search history and location history.",
                },
                {
                    "request_type": "export",
                    "platform": "Facebook",
                    "data_scope": "posts, photos, messages",
                    "goal_text": "Submit an export request to Facebook covering posts, photos, and messages.",
                },
                {
                    "request_type": "deletion",
                    "platform": "Discord",
                    "data_scope": "messages, account profile",
                    "goal_text": "Submit a deletion request to Discord covering messages and the account profile.",
                },
            ]
        )
        criteria = [
            "mem('security.data_deletion_requests.last.id') includes 'DSR-'",
            f"mem('security.data_deletion_requests.last.platform') == '{variant['platform']}'",
            f"mem('security.data_deletion_requests.last.request_type') == '{variant['request_type']}'",
            f"mem('security.data_deletion_requests.last.data_scope') == '{variant['data_scope']}'",
            "mem('security.data_deletion_requests.last.status') == 'pending'",
            f"exists(\"#requests-list .card:has-text('{variant['platform']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "L2-data-deletion/v2",
                "option": option,
                "requirement_id": f"type={variant['request_type']}|platform={variant['platform']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_l2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/security.local/data-deletion.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "select", "selector": "#request-type", "value": variant["request_type"]},
                {"t": 3, "act": "type", "selector": "#platform-name", "value": variant["platform"]},
                {"t": 4, "act": "type", "selector": "#data-scope", "value": variant["data_scope"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#requests-list .card:has-text('{variant['platform']}')"},
            ],
        }

    if task_id == "L3-security-audit":
        variant = random.choice(
            [
                {
                    "providers": ["mail", "cloud"],
                    "providers_mem": json.dumps(["mail", "cloud"]),
                    "method": "mfa+api",
                    "count": 2,
                    "goal_text": "Rotate credentials for Mail Service and Cloud Storage using MFA + API rotation.",
                },
                {
                    "providers": ["cloud", "dev"],
                    "providers_mem": json.dumps(["cloud", "dev"]),
                    "method": "api-only",
                    "count": 2,
                    "goal_text": "Rotate credentials for Cloud Storage and Dev Platform using API-only rotation.",
                },
                {
                    "providers": ["mail", "dev"],
                    "providers_mem": json.dumps(["mail", "dev"]),
                    "method": "ssh+api",
                    "count": 2,
                    "goal_text": "Rotate credentials for Mail Service and Dev Platform using SSH + API rotation.",
                },
            ]
        )
        trace = [
            {"t": 0, "act": "open", "url": "http://localhost:8014/security.local/dashboard.html?clean=true"},
        ]
        for provider in ["mail", "cloud", "dev"]:
            if provider not in variant["providers"]:
                trace.append({"t": len(trace), "act": "click", "selector": f"#provider-{provider}"})
        trace.extend(
            [
                {"t": len(trace), "act": "select", "selector": "#rotation-method", "value": variant["method"]},
                {"t": len(trace), "act": "click", "selector": "#alert-section button"},
                {"t": len(trace), "act": "wait", "selector": "#close-modal-btn:not(.hidden)"},
                {"t": len(trace), "act": "click", "selector": "#close-modal-btn"},
                {"t": len(trace), "act": "wait", "selector": ".rotation-complete"},
            ]
        )
        criteria = [
            "mem('security.rotation.status') == 'complete'",
            f"json('env','security.last_rotation.providers.0') == '{variant['providers'][0]}'",
            f"json('env','security.last_rotation.providers.1') == '{variant['providers'][1]}'",
            f"mem('security.rotation.method') == '{variant['method']}'",
            f"count('.rotation-complete') == {variant['count']}",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "L3-security-audit/v2",
                "option": option,
                "requirement_id": f"providers={'-'.join(variant['providers'])}|method={variant['method']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_l3"),
            "oracle_trace_override": trace,
        }

    if task_id == "L4-2fa-device":
        variant = random.choice(
            [
                {
                    "device": "Pixel 9 Pro",
                    "code": "112233",
                    "goal_text": "Move 2FA to the device Pixel 9 Pro.",
                },
                {
                    "device": "iPhone 16",
                    "code": "445566",
                    "goal_text": "Move 2FA to the device iPhone 16.",
                },
                {
                    "device": "Galaxy Fold 7",
                    "code": "778899",
                    "goal_text": "Move 2FA to the device Galaxy Fold 7.",
                },
            ]
        )
        criteria = [
            f"mem('security.mfa.current_device') == '{variant['device']}'",
            f"mem('security.mfa_history.last.device_name') == '{variant['device']}'",
            f"exists(\"#twofa-history-list .card:has-text('{variant['device']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "L4-2fa-device/v2",
                "option": option,
                "requirement_id": f"device={variant['device'].replace(' ', '_')}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_l4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/security.local/2fa.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#new-device-name", "value": variant["device"]},
                {"t": 2, "act": "type", "selector": "#verification-code", "value": variant["code"]},
                {"t": 3, "act": "click", "selector": "button.btn.pri"},
                {"t": 4, "act": "wait", "selector": f"#twofa-history-list .card:has-text('{variant['device']}')"},
            ],
        }

    if task_id == "M1-lost-card":
        variant = random.choice(
            [
                {
                    "last4": "1234",
                    "goal_text": "Report the card ending in 1234 as lost and freeze it immediately.",
                },
                {
                    "last4": "5678",
                    "goal_text": "Report the card ending in 5678 as lost and freeze it immediately.",
                },
                {
                    "last4": "7777",
                    "goal_text": "Report the card ending in 7777 as lost and freeze it immediately.",
                },
            ]
        )
        criteria = [
            f"mem('payments.cards.{variant['last4']}.state') == 'blocked'",
            "json('env','world_state.financial_context.liquidity') == 'frozen'",
            f"exists('#card-{variant['last4']}.blocked')",
            f"text('#card-status-{variant['last4']}') == 'Blocked'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "M1-lost-card/v2",
                "option": option,
                "requirement_id": f"last4={variant['last4']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_m1"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/cards.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#freeze-card-{variant['last4']}"},
                {"t": 2, "act": "wait", "selector": f"#card-status-{variant['last4']}"},
            ],
        }

    if task_id == "Z6-customer-service":
        variant = random.choice(
            [
                {
                    "order_id": "O-10001",
                    "message": "Please check the status of order O-10001 for me.",
                    "goal_text": "Ask customer service to check order O-10001.",
                },
                {
                    "order_id": "O-10002",
                    "message": "Can you look up order O-10002 and tell me its status?",
                    "goal_text": "Ask customer service to check order O-10002.",
                },
                {
                    "order_id": "O-10003",
                    "message": "I need the latest update for order O-10003.",
                    "goal_text": "Ask customer service to check order O-10003.",
                },
                {
                    "order_id": "O-10004",
                    "message": "Please help me verify whether order O-10004 has shipped yet.",
                    "goal_text": "Ask customer service to check order O-10004.",
                },
                {
                    "order_id": "O-10005",
                    "message": "What is going on with order O-10005? I need the current status.",
                    "goal_text": "Ask customer service to check order O-10005.",
                },
                {
                    "order_id": "O-10006",
                    "message": "Can support confirm the current state of order O-10006?",
                    "goal_text": "Ask customer service to check order O-10006.",
                },
            ]
        )
        criteria = [
            f"mem('support.chat.last_query_order') == '{variant['order_id']}'",
            "mem('support.chat.last_reply_status') == 'found'",
            f"exists(\"#messages .message.bot:has-text('{variant['order_id']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "Z6-customer-service/v2",
                "option": option,
                "requirement_id": f"order={variant['order_id']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_z6"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/support-chat.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#msg-input", "value": variant["message"]},
                {"t": 2, "act": "click", "selector": ".chat-input-area button.btn.pri"},
                {"t": 3, "act": "wait", "selector": f"#messages .message.bot:has-text('{variant['order_id']}')"},
            ],
        }

    if task_id == "M2-supply-disruption":
        variant = random.choice(
            [
                {
                    "alternative_id": "ALT-101",
                    "item_name": "生鲜蔬菜包",
                    "action_type": "switch_to_pickup",
                    "status": "pickup_confirmed",
                    "button_id": "pickup",
                    "goal_text": "Resolve the disruption by switching 生鲜蔬菜包 to pickup mode.",
                },
                {
                    "alternative_id": "ALT-202",
                    "item_name": "Baby Formula",
                    "action_type": "keep_shipping",
                    "status": "reroute_shipping",
                    "button_id": "ship",
                    "goal_text": "Resolve the disruption by rerouting Baby Formula shipping.",
                },
                {
                    "alternative_id": "ALT-303",
                    "item_name": "Spare Water Filter",
                    "action_type": "cancel_order",
                    "status": "refund_pending",
                    "button_id": "cancel",
                    "goal_text": "Resolve the disruption by cancelling the Spare Water Filter order and requesting a refund.",
                },
                {
                    "alternative_id": "ALT-404",
                    "item_name": "Prescription Cold Pack",
                    "action_type": "switch_to_pickup",
                    "status": "pickup_confirmed",
                    "button_id": "pickup",
                    "goal_text": "Resolve the disruption by switching Prescription Cold Pack to pharmacy pickup mode.",
                },
                {
                    "alternative_id": "ALT-505",
                    "item_name": "Desk Air Purifier",
                    "action_type": "cancel_order",
                    "status": "refund_pending",
                    "button_id": "cancel",
                    "goal_text": "Resolve the disruption by cancelling the Desk Air Purifier shipment and requesting a refund.",
                },
            ]
        )
        criteria = [
            f"mem('supply_chain.alternatives.last.id') == '{variant['alternative_id']}'",
            f"mem('supply_chain.alternatives.last.status') == '{variant['status']}'",
            f"exists(\"#alternative-options-list .card:has-text('{variant['item_name']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "M2-supply-disruption/v2",
                "option": option,
                "requirement_id": f"alt={variant['alternative_id']}|action={variant['action_type']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_m2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/supply-disruption.html?clean=true"},
                {"t": 1, "act": "click", "selector": f"#action-{variant['button_id']}-{variant['alternative_id']}"},
                {"t": 2, "act": "click", "selector": ".modal-confirm"},
                {"t": 3, "act": "wait", "selector": f"#alternative-options-list .card:has-text('{variant['status']}')"},
            ],
        }

    if task_id == "M3-illness-reporting":
        variant = random.choice(
            [
                {
                    "report_type": "illness",
                    "reason": "High fever and sore throat",
                    "end_date": "2026-01-18",
                    "goal_text": "Submit an illness report for high fever and sore throat until 2026-01-18.",
                },
                {
                    "report_type": "isolation",
                    "reason": "Close contact quarantine",
                    "end_date": "2026-01-22",
                    "goal_text": "Submit an isolation report for close contact quarantine until 2026-01-22.",
                },
                {
                    "report_type": "illness",
                    "reason": "Migraine recovery day",
                    "end_date": "2026-01-25",
                    "goal_text": "Submit an illness report for migraine recovery day until 2026-01-25.",
                },
            ]
        )
        criteria = [
            "mem('health.illness_reports.last.id') includes 'ILL-'",
            f"mem('health.illness_reports.last.type') == '{variant['report_type']}'",
            f"mem('health.illness_reports.last.reason') == '{variant['reason']}'",
            f"mem('health.illness_reports.last.end_date') == '{variant['end_date']}'",
            "mem('health.illness_reports.last.status') == 'pending'",
            "json('env','world_state.physical_context.status') == 'impaired'",
            "json('env','world_state.physical_context.energy_level') == 20",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "M3-illness-reporting/v2",
                "option": option,
                "requirement_id": f"type={variant['report_type']}|end={variant['end_date']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_m3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/health.local/illness-reporting.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "select", "selector": "#report-type", "value": variant["report_type"]},
                {"t": 3, "act": "type", "selector": "#report-reason", "value": variant["reason"]},
                {"t": 4, "act": "type", "selector": "#end-date", "value": variant["end_date"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#reports-list .card:has-text('{variant['reason']}')"},
            ],
        }

    if task_id == "Z2-investment-growth":
        variant = random.choice(
            [
                {
                    "name": "Growth Starter",
                    "account_type": "stocks",
                    "deposit": "1000",
                    "balance_mem": "1050.0",
                    "balance_text": "1050.00",
                    "goal_text": "Open a Growth Starter stocks account with 1000 and verify the balance grows to 1050.00 after time passes.",
                },
                {
                    "name": "Income Builder",
                    "account_type": "funds",
                    "deposit": "1200",
                    "balance_mem": "1260.0",
                    "balance_text": "1260.00",
                    "goal_text": "Open an Income Builder funds account with 1200 and verify the balance grows to 1260.00 after time passes.",
                },
                {
                    "name": "Retire Smart",
                    "account_type": "retirement",
                    "deposit": "2000",
                    "balance_mem": "2100.0",
                    "balance_text": "2100.00",
                    "goal_text": "Open a Retire Smart retirement account with 2000 and verify the balance grows to 2100.00 after time passes.",
                },
            ]
        )
        criteria = [
            f"mem('finance.investment_accounts.last.name') == '{variant['name']}'",
            f"mem('finance.investment_accounts.last.type') == '{variant['account_type']}'",
            "mem('finance.investment_accounts.last.status') == 'active'",
            f"mem('finance.investment_accounts.last.balance') == '{variant['balance_mem']}'",
            f"exists(\"#investment-accounts-list .card:has-text('{variant['name']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "Z2-investment-growth/v2",
                "option": option,
                "requirement_id": f"name={variant['name'].replace(' ', '_')}|type={variant['account_type']}|deposit={variant['deposit']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_z2"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/bank.local/investments.html?clean=true"},
                {"t": 1, "act": "click", "selector": "#open-investment-account"},
                {"t": 2, "act": "type", "selector": "#new-name", "value": variant["name"]},
                {"t": 3, "act": "select", "selector": "#new-type", "value": variant["account_type"]},
                {"t": 4, "act": "type", "selector": "#initial-deposit", "value": variant["deposit"]},
                {"t": 5, "act": "click", "selector": ".modal-confirm"},
                {"t": 6, "act": "wait", "selector": f"#investment-accounts-list .card:has-text('{variant['name']}')"},
                {"t": 7, "act": "click", "selector": "#debug-time-travel", "force": True},
                {"t": 8, "act": "wait", "selector": f"#investment-accounts-list .card:has-text('{variant['balance_text']}')"},
            ],
        }

    if task_id == "Z3-live-auction":
        variant = random.choice(
            [
                {
                    "bid_amount": "140",
                    "price_num": "140.0",
                    "price_text": "140.00",
                    "goal_text": "Place a bid of 140 in the live auction and become the highest bidder.",
                },
                {
                    "bid_amount": "180",
                    "price_num": "180.0",
                    "price_text": "180.00",
                    "goal_text": "Place a bid of 180 in the live auction and become the highest bidder.",
                },
                {
                    "bid_amount": "250",
                    "price_num": "250.0",
                    "price_text": "250.00",
                    "goal_text": "Place a bid of 250 in the live auction and become the highest bidder.",
                },
            ]
        )
        criteria = [
            "mem('auctions.VASE-001.highest_bidder') == 'user'",
            f"json('env','auctions.VASE-001.current_price') == {variant['price_num']}",
            f"text('#current-price') includes '{variant['price_text']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "Z3-live-auction/v2",
                "option": option,
                "requirement_id": f"bid={variant['bid_amount']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_z3"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/shop.local/auction.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#bid-amount", "value": variant["bid_amount"]},
                {"t": 2, "act": "click", "selector": "button.btn.pri"},
                {"t": 3, "act": "wait", "selector": f"#current-price:has-text('{variant['price_text']}')"},
            ],
        }

    if task_id == "Z4-email-calendar":
        variant = random.choice(
            [
                {
                    "title": "Client Kickoff",
                    "date": "2026-01-12",
                    "time": "09:30",
                    "event_type": "work",
                    "description": "Imported from client@example.com kickoff email",
                    "goal_text": "Sync the client@example.com kickoff email into the calendar as Client Kickoff on 2026-01-12 at 09:30.",
                },
                {
                    "title": "Patent Review",
                    "date": "2026-01-14",
                    "time": "14:00",
                    "event_type": "work",
                    "description": "Imported from legal@example.com patent review email",
                    "goal_text": "Sync the legal@example.com patent review email into the calendar as Patent Review on 2026-01-14 at 14:00.",
                },
                {
                    "title": "Wellness Check",
                    "date": "2026-01-19",
                    "time": "11:45",
                    "event_type": "personal",
                    "description": "Imported from clinic@example.com wellness email",
                    "goal_text": "Sync the clinic@example.com wellness email into the calendar as Wellness Check on 2026-01-19 at 11:45.",
                },
            ]
        )
        criteria = [
            "mem('calendar.events.last.id') includes 'EVE-'",
            f"mem('calendar.events.last.title') == '{variant['title']}'",
            f"mem('calendar.events.last.date') == '{variant['date']}'",
            f"mem('calendar.events.last.time') == '{variant['time']}'",
            f"mem('calendar.events.last.type') == '{variant['event_type']}'",
            f"exists(\"#event-list .card:has-text('{variant['title']}')\")",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "Z4-email-calendar/v2",
                "option": option,
                "requirement_id": f"title={variant['title'].replace(' ', '_')}|date={variant['date']}|time={variant['time']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_z4"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/work.local/calendar.html?clean=true"},
                {"t": 1, "act": "click", "selector": "button.btn.pri"},
                {"t": 2, "act": "type", "selector": "#event-title", "value": variant["title"]},
                {"t": 3, "act": "type", "selector": "#event-date", "value": variant["date"]},
                {"t": 4, "act": "type", "selector": "#event-time", "value": variant["time"]},
                {"t": 5, "act": "select", "selector": "#event-type", "value": variant["event_type"]},
                {"t": 6, "act": "type", "selector": "#event-description", "value": variant["description"]},
                {"t": 7, "act": "click", "selector": ".modal-confirm"},
                {"t": 8, "act": "wait", "selector": f"#event-list .card:has-text('{variant['title']}')"},
            ],
        }

    if task_id == "Z5-password-recovery":
        reset = random.choice(
            [
                {
                    "username": "byteblaze",
                    "new_password": "ByteBlaze#2026",
                    "goal_text": "Recover the password for byteblaze and set a new password ByteBlaze#2026.",
                },
                {
                    "username": "user123",
                    "new_password": "newpass123",
                    "goal_text": "Recover the password for user123 and set a new password newpass123.",
                },
            ]
        )
        criteria = [
            "mem('security.password_reset.status') == 'success'",
            f"mem('security.password_reset.user') == '{reset['username']}'",
            f"mem('security.password_reset.new_password') == '{reset['new_password']}'",
            "url().includes('/security.local/login.html')",
            "url().includes('reset=success')",
        ]
        return {
            "instruction": add_noise(reset["goal_text"]),
            "template_info": {
                "template_id": "Z5-password-recovery/v2",
                "option": option,
                "requirement_id": f"user={reset['username']}|password={reset['new_password']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(reset),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_z5"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/security.local/forgot-password.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#username", "value": reset["username"]},
                {"t": 2, "act": "click", "selector": "button:has-text('Verification Code')"},
                {"t": 3, "act": "open", "url": "http://localhost:8014/security.local/reset-password.html?clean=true"},
                {"t": 4, "act": "type", "selector": "#code", "value": "1234"},
                {"t": 5, "act": "type", "selector": "#new-password", "value": reset["new_password"]},
                {"t": 6, "act": "click", "selector": "button:has-text('ResetPassword')"},
                {"t": 7, "act": "wait", "selector": "#reset-success"},
            ],
        }

    if task_id == "Z7-complex-autopay":
        variant = random.choice(
            [
                {
                    "email_id": "billing-electricity-2201",
                    "query": "UTIL-2201",
                    "payee": "Electricity Dept",
                    "account_number": "UTIL-2201",
                    "amount": "180",
                    "goal_text": "Search your email for the Electricity Dept bill with account UTIL-2201, then enable autopay for that exact account with a monthly limit of 180.",
                },
                {
                    "email_id": "billing-water-4408",
                    "query": "WATER-4408",
                    "payee": "City Water Board",
                    "account_number": "WATER-4408",
                    "amount": "95",
                    "goal_text": "Search your email for the City Water Board bill with account WATER-4408, then enable autopay for that exact account with a monthly limit of 95.",
                },
                {
                    "email_id": "billing-electricity-6602",
                    "query": "UTIL-6602",
                    "payee": "Electricity Dept",
                    "account_number": "UTIL-6602",
                    "amount": "260",
                    "goal_text": "Search your email for the premium Electricity Dept bill with account UTIL-6602, then enable autopay for that exact account with a monthly limit of 260.",
                },
                {
                    "email_id": "billing-gas-1188",
                    "query": "GAS-1188",
                    "payee": "Neighborhood Gas Co",
                    "account_number": "GAS-1188",
                    "amount": "75",
                    "goal_text": "Search your email for the Neighborhood Gas Co bill with account GAS-1188, then enable autopay for that exact account with a monthly limit of 75.",
                },
                {
                    "email_id": "billing-fiber-9012",
                    "query": "FIBER-9012",
                    "payee": "Neighborhood Internet",
                    "account_number": "FIBER-9012",
                    "amount": "120",
                    "goal_text": "Search your email for the Neighborhood Internet bill with account FIBER-9012, then enable autopay for that exact account with a monthly limit of 120.",
                },
                {
                    "email_id": "billing-electricity-7710",
                    "query": "UTIL-7710",
                    "payee": "Electricity Dept",
                    "account_number": "UTIL-7710",
                    "amount": "310",
                    "goal_text": "Search your email for the enterprise Electricity Dept bill with account UTIL-7710, then enable autopay for that exact account with a monthly limit of 310.",
                },
            ]
        )
        criteria = [
            "mem('autopay.utility.status') == 'active'",
            f"mem('autopay.utility.payee') == '{variant['payee']}'",
            f"mem('autopay.utility.account_number') == '{variant['account_number']}'",
            f"mem('autopay.utility.amount') == '{variant['amount']}'",
            f"text('#success-summary') includes '{variant['account_number']}'",
        ]
        return {
            "instruction": add_noise(variant["goal_text"]),
            "template_info": {
                "template_id": "Z7-complex-autopay/v2",
                "option": option,
                "requirement_id": f"email={variant['email_id']}|account={variant['account_number']}",
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": dict(variant),
            },
            "criteria": criteria,
            "scoring_checkpoints": _build_equal_weight_checkpoints(criteria, "cp_z7"),
            "oracle_trace_override": [
                {"t": 0, "act": "open", "url": "http://localhost:8014/work.local/email.html?clean=true"},
                {"t": 1, "act": "type", "selector": "#email-search", "value": variant["query"]},
                {"t": 2, "act": "click", "selector": f"#email-item-{variant['email_id']}"},
                {"t": 3, "act": "wait", "selector": "#setup-autopay-from-email"},
                {"t": 4, "act": "click", "selector": "#setup-autopay-from-email"},
                {"t": 5, "act": "click", "selector": "#setup-btn"},
                {"t": 6, "act": "wait", "selector": "#success-summary"},
            ],
        }

    if task_id == "A1-find-home":
        # A1 template v3: requirement-level variation.
        # Goals:
        # - cheapest
        # - most_expensive
        # - best_rated_under_budget
        # - largest_area_under_budget
        property_catalog = []
        # Keep catalog consistent with server.reset_env seed list.
        # We additionally assign a deterministic rating for requirement-level targets.
        rating_pattern = [4.2, 3.8, 4.9, 4.1, 4.7, 4.4, 5.0, 3.9, 4.6, 4.3]
        for i in range(20):
            property_catalog.append(
                {
                    "id": f"PROP-EXT-{i}",
                    "price": 1000 + i * 150,
                    "area_sqm": 40 + i * 10,
                    "rating": rating_pattern[i % len(rating_pattern)],
                }
            )

        goal = random.choice(
            [
                "cheapest",
                "most_expensive",
                "best_rated_under_budget",
                "largest_area_under_budget",
            ]
        )
        budget = None
        candidates = list(property_catalog)
        if goal in {"best_rated_under_budget", "largest_area_under_budget"}:
            budget = random.choice([1800, 2200, 2600, 3000, 3400])
            candidates = [p for p in property_catalog if p["price"] <= budget]
            if not candidates:
                candidates = [property_catalog[0]]

        if goal == "cheapest":
            target = min(property_catalog, key=lambda p: p["price"])
            sort_order = "price_low"
            goal_text = "cheapest"
            ranking_hint = "lowest price first"
        elif goal == "most_expensive":
            target = max(property_catalog, key=lambda p: p["price"])
            sort_order = "price_high"
            goal_text = "most expensive"
            ranking_hint = "highest price first"
        elif goal == "best_rated_under_budget":
            target = max(candidates, key=lambda p: (p["rating"], -p["price"]))
            sort_order = "default"
            goal_text = "best-rated"
            ranking_hint = "review ratings"
        else:
            target = max(candidates, key=lambda p: (p["area_sqm"], -p["price"]))
            sort_order = "price_low"
            goal_text = "largest-area"
            ranking_hint = "area size"

        target_property_id = target["id"]
        lease_term = random.choice(["6", "12"])

        if option == "city":
            home_type = random.choice(["apartment", "studio apartment", "one-bedroom apartment"])
            area = random.choice(["city center", "central city area", "city downtown"])
        else:
            home_type = random.choice(["house", "townhouse", "family house"])
            area = random.choice(["suburb", "suburban area", "suburb district"])

        lead = random.choice(["Find and rent", "Rent", "Please rent"])
        if goal in {"cheapest", "most_expensive"}:
            sort_text = "lowest price first" if sort_order == "price_low" else "highest price first"
            decision_clause = random.choice(
                [
                    f"Sort by {sort_text}.",
                    f"First order the listings by {sort_text}.",
                    f"Apply a sort so {sort_text} appears first.",
                ]
            )
        elif goal == "best_rated_under_budget":
            decision_clause = random.choice(
                [
                    f"Set a maximum budget of ${budget}/month and choose the highest-rated listing within budget.",
                    f"Only consider listings up to ${budget}/month, then pick the best review rating.",
                    f"Use a budget cap of ${budget}/month and select the top-rated option under that cap.",
                ]
            )
        else:
            decision_clause = random.choice(
                [
                    f"Only consider listings at or below ${budget}/month, then pick the largest area.",
                    f"Use a budget limit of ${budget}/month and choose the listing with the most square meters.",
                    f"Apply a ${budget}/month cap and select the largest unit by area.",
                ]
            )
        term_clause = random.choice(
            [
                f"Use a {lease_term}-month lease term before applying.",
                f"Set lease term to {lease_term} months and then apply.",
                f"Choose {lease_term} months as the lease term if prompted.",
            ]
        )

        compiled = f"{lead} the {goal_text} {home_type} in the {area}. {decision_clause} {term_clause}"

        criteria = [
            f"mem('housing.lease.last.id') == '{target_property_id}'",
            f"mem('housing.lease.last.term') == '{lease_term}'",
        ]
        scoring_checkpoints = [
            {
                "id": "cp_property_selected",
                "name": "Target property selected",
                "assertion": f"mem('housing.lease.last.id') == '{target_property_id}'",
                "weight": 0.6,
                "required": True,
                "depends_on": [],
            },
            {
                "id": "cp_lease_term_selected",
                "name": "Lease term selected",
                "assertion": f"mem('housing.lease.last.term') == '{lease_term}'",
                "weight": 0.4,
                "required": True,
                "depends_on": ["cp_property_selected"],
            },
        ]
        oracle_trace_override = [
            {
                "t": 0,
                "act": "open",
                "url": "http://localhost:8014/housing.local/index.html?clean=true",
            },
            {
                "t": 1,
                "act": "select",
                "selector": "#sort-order",
                "value": sort_order,
            },
            {
                "t": 2,
                "act": "open",
                "url": f"http://localhost:8014/housing.local/property.html?id={target_property_id}&clean=true",
            },
            {
                "t": 3,
                "act": "select",
                "selector": "#lease-term",
                "value": lease_term,
            },
            {
                "t": 4,
                "act": "click",
                "selector": "#apply-btn",
            },
        ]

        requirement_id = f"goal={goal}|budget={budget if budget is not None else 'none'}|term={lease_term}"
        slot_values = {
            "goal": goal,
            "goal_text": goal_text,
            "home_type": home_type,
            "area": area,
            "ranking_hint": ranking_hint,
            "budget": budget,
            "sort_order": sort_order,
            "target_property_id": target_property_id,
            "lease_term": lease_term,
            "target_price": target["price"],
            "target_area_sqm": target["area_sqm"],
            "target_rating": target["rating"],
        }

        return {
            "instruction": add_noise(compiled),
            "template_info": {
                "template_id": "A1-find-home/v3",
                "option": option,
                "requirement_id": requirement_id,
                "requirement_level": True,
                "semantic_requirement_level": True,
                "validation_only_requirement": False,
                "branch_kind": "semantic",
                "slot_values": slot_values,
            },
            "criteria": criteria,
            "scoring_checkpoints": scoring_checkpoints,
            "oracle_trace_override": oracle_trace_override,
        }

    # B2 template v1: requirement-level variation on subscription targets.
    frequencies = ["weekly", "bi-weekly", "monthly"]
    date_pool = ["2026-01-10", "2026-01-17", "2026-01-24", "2026-02-07", "2026-02-14"]
    plan_prefix = random.choice(["Fresh", "Green", "Family", "Wellness"])
    target_date = random.choice(date_pool)
    frequency = random.choice(frequencies)
    price = random.choice([89, 99, 119, 129, 149, 169, 189])
    goal = random.choice(["activate_by_date", "activate_weekly_budget", "activate_monthly_premium"])

    if goal == "activate_weekly_budget":
        frequency = "weekly"
        price = random.choice([89, 99, 109, 119])
    elif goal == "activate_monthly_premium":
        frequency = "monthly"
        price = random.choice([159, 179, 199, 219])

    plan_name = f"{plan_prefix} Box {target_date[-2:]}"
    items_by_frequency = {
        "weekly": "fruit, vegetables, eggs",
        "bi-weekly": "fruit, vegetables, yogurt",
        "monthly": "grain, canned food, dry goods",
    }
    items = items_by_frequency.get(frequency, "fruit, vegetables, eggs")

    if goal == "activate_by_date":
        instruction = (
            f"Create a fresh-food subscription named '{plan_name}' with {frequency} delivery, "
            f"price {price} per delivery, and next delivery date {target_date}."
        )
        criteria = [
            "mem('food.subscriptions.last.status') == 'active'",
            f"mem('food.subscriptions.last.next_delivery_date') == '{target_date}'",
        ]
        scoring_checkpoints = [
            {
                "id": "cp_sub_active",
                "name": "Subscription active",
                "assertion": "mem('food.subscriptions.last.status') == 'active'",
                "weight": 0.5,
                "required": True,
                "depends_on": [],
            },
            {
                "id": "cp_date_matched",
                "name": "Next delivery date matched",
                "assertion": f"mem('food.subscriptions.last.next_delivery_date') == '{target_date}'",
                "weight": 0.5,
                "required": True,
                "depends_on": ["cp_sub_active"],
            },
        ]
    elif goal == "activate_weekly_budget":
        instruction = (
            f"Subscribe to a weekly fresh-food plan under 120 per delivery. "
            f"Use plan name '{plan_name}', set next delivery date to {target_date}, and complete activation."
        )
        criteria = [
            "mem('food.subscriptions.last.status') == 'active'",
            f"exists(\"#subscriptions-list .card:has-text('{frequency}')\")",
            f"exists(\"#subscriptions-list .card:has-text('¥{price}')\")",
        ]
        scoring_checkpoints = [
            {
                "id": "cp_sub_active",
                "name": "Subscription active",
                "assertion": "mem('food.subscriptions.last.status') == 'active'",
                "weight": 0.4,
                "required": True,
                "depends_on": [],
            },
            {
                "id": "cp_weekly_mode",
                "name": "Weekly frequency selected",
                "assertion": f"exists(\"#subscriptions-list .card:has-text('{frequency}')\")",
                "weight": 0.3,
                "required": True,
                "depends_on": ["cp_sub_active"],
            },
            {
                "id": "cp_budget_price",
                "name": "Budget price matched",
                "assertion": f"exists(\"#subscriptions-list .card:has-text('¥{price}')\")",
                "weight": 0.3,
                "required": True,
                "depends_on": ["cp_sub_active"],
            },
        ]
    else:
        instruction = (
            f"Activate a premium monthly fresh-food plan named '{plan_name}' at {price} per delivery. "
            f"Set next delivery date to {target_date} before confirming."
        )
        criteria = [
            "mem('food.subscriptions.last.status') == 'active'",
            f"exists(\"#subscriptions-list .card:has-text('{frequency}')\")",
            f"exists(\"#subscriptions-list .card:has-text('¥{price}')\")",
            f"mem('food.subscriptions.last.next_delivery_date') == '{target_date}'",
        ]
        scoring_checkpoints = [
            {
                "id": "cp_sub_active",
                "name": "Subscription active",
                "assertion": "mem('food.subscriptions.last.status') == 'active'",
                "weight": 0.35,
                "required": True,
                "depends_on": [],
            },
            {
                "id": "cp_monthly_mode",
                "name": "Monthly frequency selected",
                "assertion": f"exists(\"#subscriptions-list .card:has-text('{frequency}')\")",
                "weight": 0.2,
                "required": True,
                "depends_on": ["cp_sub_active"],
            },
            {
                "id": "cp_premium_price",
                "name": "Premium price matched",
                "assertion": f"exists(\"#subscriptions-list .card:has-text('¥{price}')\")",
                "weight": 0.2,
                "required": True,
                "depends_on": ["cp_sub_active"],
            },
            {
                "id": "cp_date_matched",
                "name": "Next delivery date matched",
                "assertion": f"mem('food.subscriptions.last.next_delivery_date') == '{target_date}'",
                "weight": 0.25,
                "required": True,
                "depends_on": ["cp_sub_active"],
            },
        ]

    oracle_trace_override = [
        {
            "t": 0,
            "act": "open",
            "url": "http://localhost:8014/food.local/subscription.html?clean=true",
        },
        {
            "t": 1,
            "act": "click",
            "selector": "button.btn.pri",
        },
        {
            "t": 2,
            "act": "type",
            "selector": "#new-name",
            "value": plan_name,
        },
        {
            "t": 3,
            "act": "select",
            "selector": "#new-frequency",
            "value": frequency,
        },
        {
            "t": 4,
            "act": "type",
            "selector": "#new-items",
            "value": items,
        },
        {
            "t": 5,
            "act": "type",
            "selector": "#new-price",
            "value": str(price),
        },
        {
            "t": 6,
            "act": "type",
            "selector": "#new-delivery-date",
            "value": target_date,
        },
        {
            "t": 7,
            "act": "click",
            "selector": ".modal-confirm",
        },
        {
            "t": 8,
            "act": "wait",
            "selector": "#subscriptions-list .card",
        },
    ]

    return {
        "instruction": add_noise(instruction),
        "template_info": {
            "template_id": "B2-fresh-subscription/v1",
            "option": option,
            "requirement_id": f"goal={goal}|frequency={frequency}|price={price}|date={target_date}",
            "requirement_level": True,
            "semantic_requirement_level": True,
            "validation_only_requirement": False,
            "branch_kind": "semantic",
            "slot_values": {
                "goal": goal,
                "plan_name": plan_name,
                "frequency": frequency,
                "price": price,
                "next_delivery_date": target_date,
                "items": items,
            },
        },
        "criteria": criteria,
        "scoring_checkpoints": scoring_checkpoints,
        "oracle_trace_override": oracle_trace_override,
    }

def add_noise(instr):
    # Preserve historical RNG consumption so the same seed keeps producing the
    # same semantic chains even though we no longer inject surface noise.
    pre = ["Hello, please ", "Could you ", "I need to ", "Task: "]
    post = [". Thanks!", ". Asap.", ". This is important.", "."]
    noisy_branch = random.random() > 0.5
    variant_hint = 0
    if noisy_branch:
        pre_pick = random.choice(pre)
        post_pick = random.choice(post)
        variant_hint = (pre.index(pre_pick) + post.index(post_pick)) % 3 + 1
    text = " ".join(str(instr or "").strip().split())
    if not text:
        return text

    body = text[:-1] if text.endswith(".") else text
    if not body:
        return text
    lowered = body[0].lower() + body[1:] if len(body) > 1 else body.lower()
    sentences = [seg.strip() for seg in text.rstrip(".").split(".") if seg.strip()]

    variants = [text]
    variants.append(f"Your task is to {lowered}.")
    variants.append(f"Complete the following task: {lowered}.")
    if len(sentences) >= 2:
        head = sentences[0]
        tail = " ".join(sentences[1:])
        tail = tail[0].lower() + tail[1:] if len(tail) > 1 else tail.lower()
        variants.append(f"{head}. Then {tail}.")
    else:
        variants.append(f"Ensure you {lowered}.")

    unique_variants = []
    seen = set()
    for item in variants:
        normalized = " ".join(str(item or "").strip().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_variants.append(normalized)
    return unique_variants[variant_hint % len(unique_variants)]

def get_initial_state(theme):
    state = {"has_home": False, "has_bank": False, "has_mobile": False, "has_utility": False, "balance": 1000, "orders": [], "delivered_count": 0, "orders_count": 0, "is_sick": False, "card_frozen": False, "has_invest": False, "location": None, "pending_order": False, "energy_cost": "low", "certified": False, "energy_level": 100, "trip_booked": False, "commute_checked": False, "has_sub": False, "has_coupon": False, "has_shop_delivered": False, "last_order_type": None}
    if theme != "newcomer": state.update({"has_home": True, "has_bank": True, "has_mobile": True, "has_utility": True, "location": "city" if random.random() > 0.5 else "suburb", "balance": 5000})
    return state


PRECONDITION_KEYS: Dict[str, List[str]] = {
    "A2-bank-opening": ["has_home", "has_bank"],
    "A3-utility-setup": ["has_home", "has_utility"],
    "A5-lease-management": ["has_home"],
    "A6-address-proof": ["has_home"],
    "B1-shopping": ["has_bank", "card_frozen"],
    "B2-fresh-subscription": ["has_home"],
    "B3-housekeeping-booking": ["has_home"],
    "B4-food-delivery": ["has_home"],
    "B6-price-protection": ["orders_count"],
    "B7-second-hand-sale": ["orders_count"],
    "C1-logistics-fix": ["orders_count"],
    "C2-return": ["has_shop_delivered"],
    "C3-subscription-refund": ["has_sub"],
    "C4-warranty-claim": ["has_shop_delivered"],
    "C5-leave-review": ["has_shop_delivered"],
    "D1-check-balance": ["has_bank"],
    "D2-budget-report": ["has_bank"],
    "D3-autopay": ["has_bank", "has_utility"],
    "D4-card-replacement": ["card_frozen"],
    "D5-tax-preparation": ["has_bank"],
    "D6-investment-account": ["has_bank", "balance"],
    "E1-commute-route": ["has_home"],
    "E2-transport-topup": ["commute_checked", "has_bank"],
    "E3-airport-transfer": ["has_bank"],
    "E5-expense-report": ["trip_booked"],
    "E6-flight-change": ["trip_booked"],
    "E7-long-haul-trip": ["has_bank"],
    "F2-conference-reg": ["has_bank"],
    "F3-paper-submission": ["certified"],
    "F5-receipt-archive": ["orders_count"],
    "G1-doctor-appt": ["is_sick"],
    "G2-insurance-policy": ["has_bank"],
    "G3-medical-claim": ["has_insurance", "is_sick"],
    "G4-gym-membership": ["has_prescription"],
    "H1-address-change": ["has_home"],
    "H2-vehicle-address-update": ["has_home"],
    "H4-parking-permit": ["has_home"],
    "I1-smart-bulb-setup": ["has_utility"],
    "I2-appliance-repair": ["has_home"],
    "I4-smart-meter": ["has_utility"],
    "I5-energy-optimize": ["has_utility"],
    "J1-course-enroll": ["is_sick", "energy_level"],
    "J3-event-tickets": ["has_bank"],
    "J4-gear-rental": ["has_bank"],
    "K2-roommate-split": ["has_home"],
    "K3-charity-donation": ["has_bank"],
    "L4-2fa-device": ["has_mobile"],
    "M1-lost-card": ["has_bank", "card_frozen"],
    "M2-supply-disruption": ["orders_count"],
    "M3-illness-reporting": ["is_sick"],
    "Z1-order-arrival": ["pending_order", "card_frozen"],
    "Z2-investment-growth": ["has_invest"],
    "Z3-live-auction": ["has_bank"],
    "Z5-password-recovery": ["has_mobile"],
    "Z7-complex-autopay": ["has_utility", "has_bank"],
}


CONFLICT_TRACK_KEYS = {
    "has_sub",
    "card_frozen",
    "energy_cost",
    "location",
    "is_sick",
    "pending_order",
    "trip_booked",
    "certified",
    "has_shop_delivered",
    "orders_count",
}


def _resolve_effect_preview(logic: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    if "effect_fn" in logic:
        out = logic["effect_fn"](dict(state))
    else:
        out = logic.get("effect", {})
    if not isinstance(out, dict):
        return {}
    return dict(out)


def _weighted_pick_candidates(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not candidates:
        return {}
    total = sum(max(float(c.get("_score", 0.0)), 0.0) for c in candidates)
    if total <= 0:
        return random.choice(candidates)
    r = random.random() * total
    cur = 0.0
    for cand in candidates:
        cur += max(float(cand.get("_score", 0.0)), 0.0)
        if r <= cur:
            return cand
    return candidates[-1]


def _constraint_satisfied(chain: Dict[str, Any], min_dep: int, min_long: int, min_conflict: int) -> bool:
    stats = chain.get("dependency_stats") or {}
    return (
        int(stats.get("dependent_steps", 0)) >= int(min_dep)
        and int(stats.get("long_dependency_steps", 0)) >= int(min_long)
        and int(stats.get("conflict_steps", 0)) >= int(min_conflict)
    )


def _constraint_score(chain: Dict[str, Any], min_dep: int, min_long: int, min_conflict: int) -> float:
    stats = chain.get("dependency_stats") or {}
    dep = int(stats.get("dependent_steps", 0))
    lng = int(stats.get("long_dependency_steps", 0))
    cfl = int(stats.get("conflict_steps", 0))
    gap = float(stats.get("avg_dependency_gap", 0.0))
    return (
        min(dep, int(min_dep)) * 1.0
        + min(lng, int(min_long)) * 1.2
        + min(cfl, int(min_conflict)) * 1.1
        + gap * 0.05
    )


def weighted_pick_by_usage(candidates, usage_counter):
    if not candidates:
        return None
    weighted = []
    for tid in candidates:
        usage = usage_counter.get(tid, 0)
        weight = 1.0 / (1.0 + usage)
        weighted.append((tid, weight))
    total = sum(w for _, w in weighted)
    if total <= 0:
        return random.choice(candidates)
    r = random.random() * total
    cur = 0.0
    for tid, w in weighted:
        cur += w
        if r <= cur:
            return tid
    return weighted[-1][0]


def generate_chain(
    chain_id,
    target_theme,
    theme_usage_counter,
    max_repeat_per_task=1,
    min_steps=4,
    max_steps=8,
    theme_task_cap=0,
    min_dependent_steps=2,
    min_long_dependency_steps=1,
    long_dependency_gap=3,
    min_conflict_steps=1,
    dependency_boost=0.7,
    long_dependency_boost=0.9,
    conflict_boost=1.0,
):
    initial_state = get_initial_state(target_theme)
    state = initial_state.copy()
    steps = []
    task_counts = {}
    key_last_writer: Dict[str, str] = {k: "__initial__" for k in state.keys()}
    key_last_writer_idx: Dict[str, int] = {k: -1 for k in state.keys()}
    key_change_history: Dict[str, List[Any]] = {k: [("__initial__", state[k])] for k in state.keys()}

    dependent_steps = 0
    long_dependency_steps = 0
    conflict_steps = 0
    dep_gap_sum = 0
    dep_gap_cnt = 0

    def build_option_candidate(tid, opt):
        cfg = TASKS_DB[tid]
        logic = cfg["logic"][opt]
        effect_preview = _resolve_effect_preview(logic, state)
        changed_keys = [k for k, v in effect_preview.items() if state.get(k) != v]

        dep_sources = []
        max_gap = 0
        for key in PRECONDITION_KEYS.get(tid, []):
            writer = key_last_writer.get(key, "__initial__")
            writer_idx = key_last_writer_idx.get(key, -1)
            if writer and writer != "__initial__":
                dep_sources.append(writer)
                max_gap = max(max_gap, max(0, len(steps) - writer_idx))
        dep_sources = list(dict.fromkeys(dep_sources))
        is_long_dep = max_gap >= long_dependency_gap and len(dep_sources) > 0

        conflict_keys = []
        for key in changed_keys:
            if key not in CONFLICT_TRACK_KEYS:
                continue
            hist = key_change_history.get(key, [])
            # Count conflict only when a prior task has already changed this key.
            if len(hist) > 1 and hist[-1][1] != effect_preview.get(key):
                conflict_keys.append(key)

        usage = theme_usage_counter.get(tid, 0)
        local_repeat = task_counts.get(tid, 0)
        score = 1.0 / (1.0 + usage + 0.6 * local_repeat)
        score *= 1.0 + dependency_boost * len(dep_sources)
        if is_long_dep:
            score += long_dependency_boost
        if conflict_keys:
            score += conflict_boost * len(conflict_keys)

        return {
            "task_id": tid,
            "option": opt,
            "cfg": cfg,
            "logic": logic,
            "effect_preview": effect_preview,
            "changed_keys": changed_keys,
            "dependency_tasks": dep_sources,
            "max_dependency_gap": max_gap,
            "long_dependency": is_long_dep,
            "conflict_keys": conflict_keys,
            "_score": max(score, 0.001),
        }

    def pave(candidate):
        nonlocal dependent_steps, long_dependency_steps, conflict_steps, dep_gap_sum, dep_gap_cnt
        tid = candidate["task_id"]
        opt = candidate["option"]
        cfg = candidate["cfg"]
        logic = candidate["logic"]
        instance = instantiate_task_step(tid, opt, logic)
        crit = normalize_criteria(instance.get("criteria") or resolve_step_criteria(tid, logic, state))
        cps = normalize_checkpoints(instance.get("scoring_checkpoints") or resolve_step_checkpoints(logic, state))
        if not crit:
            raise ValueError(f"Task {tid} has no success_criteria for option '{opt}'")
        step = {
            "task_id": tid,
            "task_option": opt,
            "instruction": instance["instruction"],
            "success_criteria": crit,
            "difficulty": cfg["difficulty"],
            "dependency_context": {
                "dependency_tasks": candidate.get("dependency_tasks", []),
                "max_dependency_gap": int(candidate.get("max_dependency_gap", 0)),
                "long_dependency": bool(candidate.get("long_dependency", False)),
                "conflict_keys": candidate.get("conflict_keys", []),
                "changed_state_keys": candidate.get("changed_keys", []),
            },
        }
        if instance.get("template_info"):
            step["template_info"] = instance["template_info"]
        if instance.get("oracle_trace_override"):
            step["oracle_trace_override"] = deepcopy(instance["oracle_trace_override"])
        if cps:
            step["scoring_checkpoints"] = cps
        steps.append(step)
        effect_preview = candidate.get("effect_preview") or {}
        if effect_preview:
            state.update(effect_preview)
        task_counts[tid] = task_counts.get(tid, 0) + 1
        theme_usage_counter[tid] += 1

        idx = len(steps) - 1
        for key, value in effect_preview.items():
            key_last_writer[key] = tid
            key_last_writer_idx[key] = idx
            key_change_history.setdefault(key, [("__initial__", initial_state.get(key))]).append((tid, value))

        dep_tasks = candidate.get("dependency_tasks", [])
        if dep_tasks:
            dependent_steps += 1
            gap = int(candidate.get("max_dependency_gap", 0))
            if gap > 0:
                dep_gap_sum += gap
                dep_gap_cnt += 1
        if candidate.get("long_dependency"):
            long_dependency_steps += 1
        if candidate.get("conflict_keys"):
            conflict_steps += 1

    starters = {"newcomer": ["A1-find-home", "A4-mobile-plan"], "daily": ["B2-fresh-subscription", "D1-check-balance"], "career": ["F1-calendar-aggregation", "E1-commute-route"], "leisure": ["K1-plan-party", "E4-visa-requirements"], "crisis": ["M1-lost-card", "M3-illness-reporting"]}
    starter_tasks = [
        t for t in starters.get(target_theme, [])
        if TASKS_DB[t]["pre"](state)
        and task_counts.get(t, 0) < max_repeat_per_task
        and (theme_task_cap <= 0 or theme_usage_counter.get(t, 0) < theme_task_cap)
    ]
    starter_candidates = []
    for tid in starter_tasks:
        for opt in TASKS_DB[tid]["logic"].keys():
            starter_candidates.append(build_option_candidate(tid, opt))
    if starter_candidates:
        picked = _weighted_pick_candidates(starter_candidates)
        if picked:
            pave(picked)

    target_len = random.randint(min_steps, max_steps)
    while len(steps) < target_len:
        valid_tasks = [
            t for t, c in TASKS_DB.items()
            if c["pre"](state)
            and task_counts.get(t, 0) < max_repeat_per_task
            and (theme_task_cap <= 0 or theme_usage_counter.get(t, 0) < theme_task_cap)
        ]
        if not valid_tasks:
            break
        candidates = []
        for tid in valid_tasks:
            for opt in TASKS_DB[tid]["logic"].keys():
                candidates.append(build_option_candidate(tid, opt))
        if not candidates:
            break

        remaining_slots = target_len - len(steps)
        need_dep = max(0, int(min_dependent_steps) - dependent_steps)
        need_long = max(0, int(min_long_dependency_steps) - long_dependency_steps)
        need_conflict = max(0, int(min_conflict_steps) - conflict_steps)

        chosen_pool = list(candidates)
        if need_dep >= remaining_slots:
            dep_pool = [c for c in chosen_pool if c.get("dependency_tasks")]
            if dep_pool:
                chosen_pool = dep_pool
        if need_long >= remaining_slots:
            long_pool = [c for c in chosen_pool if c.get("long_dependency")]
            if long_pool:
                chosen_pool = long_pool
        if need_conflict >= remaining_slots:
            conflict_pool = [c for c in chosen_pool if c.get("conflict_keys")]
            if conflict_pool:
                chosen_pool = conflict_pool

        for cand in chosen_pool:
            if need_dep > 0 and cand.get("dependency_tasks"):
                cand["_score"] += 0.6
            if need_long > 0 and cand.get("long_dependency"):
                cand["_score"] += 0.8
            if need_conflict > 0 and cand.get("conflict_keys"):
                cand["_score"] += 0.8

        picked = _weighted_pick_candidates(chosen_pool)
        if not picked:
            break
        pave(picked)

    dep_stats = {
        "dependent_steps": dependent_steps,
        "long_dependency_steps": long_dependency_steps,
        "conflict_steps": conflict_steps,
        "avg_dependency_gap": (dep_gap_sum / dep_gap_cnt) if dep_gap_cnt else 0.0,
    }
    return {
        "chain_id": chain_id,
        "theme": target_theme,
        "initial_state": initial_state,
        "steps": steps,
        "dependency_stats": dep_stats,
        "generation_constraints": {
            "min_dependent_steps": int(min_dependent_steps),
            "min_long_dependency_steps": int(min_long_dependency_steps),
            "long_dependency_gap": int(long_dependency_gap),
            "min_conflict_steps": int(min_conflict_steps),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate dynamic scenario flows with reduced template repetition")
    parser.add_argument("--themes", default="newcomer,daily,career,leisure,crisis", help="Comma-separated themes")
    parser.add_argument("--chains-per-theme", type=int, default=100)
    parser.add_argument("--min-steps", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--max-repeat-per-task", type=int, default=1, help="Max times the same task may appear in one chain")
    parser.add_argument("--theme-task-cap", type=int, default=30, help="Per-theme cap for each task across all chains (set <=0 to disable)")
    parser.add_argument("--min-dependent-steps", type=int, default=2, help="Minimum number of steps that should depend on prior tasks")
    parser.add_argument("--min-long-dependency-steps", type=int, default=1, help="Minimum number of long-range dependency steps")
    parser.add_argument("--long-dependency-gap", type=int, default=3, help="A dependency is long-range when source-target gap >= this value")
    parser.add_argument("--min-conflict-steps", type=int, default=1, help="Minimum number of state-overwrite conflict steps")
    parser.add_argument("--dependency-boost", type=float, default=0.7, help="Sampling boost for dependency-rich candidates")
    parser.add_argument("--long-dependency-boost", type=float, default=0.9, help="Extra sampling boost for long-range dependency candidates")
    parser.add_argument("--conflict-boost", type=float, default=1.0, help="Extra sampling boost for conflict-overwrite candidates")
    parser.add_argument("--constraint-retries", type=int, default=6, help="How many retries to satisfy dependency/long/conflict constraints per chain")
    parser.add_argument(
        "--report-requirement-variability",
        action="store_true",
        help="Print a summary of tasks that currently have requirement-level variability hooks",
    )
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if args.max_repeat_per_task < 1:
        args.max_repeat_per_task = 1
    if args.min_steps < 1:
        args.min_steps = 1
    if args.max_steps < args.min_steps:
        args.max_steps = args.min_steps

    themes = [t.strip() for t in args.themes.split(",") if t.strip()]

    if args.report_requirement_variability:
        semantic_variable = []
        validation_only = []
        likely_static = []
        for tid, cfg in TASKS_DB.items():
            if _is_true_requirement_level_task(tid):
                semantic_variable.append(tid)
            elif _is_validation_only_requirement_task(tid):
                validation_only.append(tid)
            else:
                likely_static.append(tid)
        print(
            f"[variability] semantic_total={len(semantic_variable)} "
            f"validation_only_total={len(validation_only)} static_like={len(likely_static)}"
        )
        print(f"[variability] semantic tasks: {', '.join(sorted(semantic_variable))}")
        if validation_only:
            print(f"[variability] validation-only sample: {', '.join(sorted(validation_only)[:20])}")
        if likely_static:
            print(f"[variability] static-like sample: {', '.join(sorted(likely_static)[:20])}")

    for theme in themes:
        theme_usage_counter = Counter()
        scenarios = []
        retries = max(1, int(args.constraint_retries))
        for i in range(args.chains_per_theme):
            chain_id = f"SCENARIO-{theme.upper()}-{i:03d}"
            best_chain = None
            best_counter = None
            best_score = -1.0

            for _ in range(retries):
                trial_counter = Counter(theme_usage_counter)
                trial_chain = generate_chain(
                    chain_id,
                    theme,
                    theme_usage_counter=trial_counter,
                    max_repeat_per_task=args.max_repeat_per_task,
                    min_steps=args.min_steps,
                    max_steps=args.max_steps,
                    theme_task_cap=args.theme_task_cap,
                    min_dependent_steps=args.min_dependent_steps,
                    min_long_dependency_steps=args.min_long_dependency_steps,
                    long_dependency_gap=args.long_dependency_gap,
                    min_conflict_steps=args.min_conflict_steps,
                    dependency_boost=args.dependency_boost,
                    long_dependency_boost=args.long_dependency_boost,
                    conflict_boost=args.conflict_boost,
                )
                if _constraint_satisfied(
                    trial_chain,
                    min_dep=args.min_dependent_steps,
                    min_long=args.min_long_dependency_steps,
                    min_conflict=args.min_conflict_steps,
                ):
                    best_chain = trial_chain
                    best_counter = trial_counter
                    break

                score = _constraint_score(
                    trial_chain,
                    min_dep=args.min_dependent_steps,
                    min_long=args.min_long_dependency_steps,
                    min_conflict=args.min_conflict_steps,
                )
                if score > best_score:
                    best_chain = trial_chain
                    best_counter = trial_counter
                    best_score = score

            if best_chain is None:
                best_chain = generate_chain(
                    chain_id,
                    theme,
                    theme_usage_counter=theme_usage_counter,
                    max_repeat_per_task=args.max_repeat_per_task,
                    min_steps=args.min_steps,
                    max_steps=args.max_steps,
                    theme_task_cap=args.theme_task_cap,
                    min_dependent_steps=args.min_dependent_steps,
                    min_long_dependency_steps=args.min_long_dependency_steps,
                    long_dependency_gap=args.long_dependency_gap,
                    min_conflict_steps=args.min_conflict_steps,
                    dependency_boost=args.dependency_boost,
                    long_dependency_boost=args.long_dependency_boost,
                    conflict_boost=args.conflict_boost,
                )
            else:
                theme_usage_counter.clear()
                theme_usage_counter.update(best_counter)

            scenarios.append(best_chain)
        with open(f"sampled_{theme}.json", "w") as f: json.dump(scenarios, f, indent=2, ensure_ascii=False)
        common = ", ".join(f"{k}:{v}" for k, v in theme_usage_counter.most_common(8))
        avg_dep = sum((s.get("dependency_stats") or {}).get("dependent_steps", 0) for s in scenarios) / max(1, len(scenarios))
        avg_long = sum((s.get("dependency_stats") or {}).get("long_dependency_steps", 0) for s in scenarios) / max(1, len(scenarios))
        avg_conflict = sum((s.get("dependency_stats") or {}).get("conflict_steps", 0) for s in scenarios) / max(1, len(scenarios))
        print(f"[{theme}] generated={len(scenarios)} | dep_avg={avg_dep:.2f} long_avg={avg_long:.2f} conflict_avg={avg_conflict:.2f} | top usage: {common}")
    print("🚀 English scenarios with reduced repetition generated.")

if __name__ == "__main__": main()
