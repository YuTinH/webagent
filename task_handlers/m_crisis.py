from .utils import deep_merge
import os
import random
import datetime as dt_module


def _should_log_debug() -> bool:
    value = os.environ.get("WEBAGENT_DEBUG_LOGS", "").strip().lower()
    return value in {"1", "true", "yes", "on"}

def handle_m_crisis(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()
    fallback_alternatives = {
        "ALT-101": {
            "item_name": "Protein Powder",
            "alternative_source": "Downtown pickup locker",
            "action_needed": "Switch to pickup to receive it today",
            "status": "available",
        },
        "ALT-202": {
            "item_name": "Baby Formula",
            "alternative_source": "North hub reroute",
            "action_needed": "Keep shipping and reroute the package",
            "status": "available",
        },
        "ALT-303": {
            "item_name": "Spare Water Filter",
            "alternative_source": "Supplier refund desk",
            "action_needed": "Cancel the disrupted order and request a refund",
            "status": "available",
        },
        "ALT-404": {
            "item_name": "Prescription Cold Pack",
            "alternative_source": "Central pharmacy pickup shelf",
            "action_needed": "Switch to pickup for same-day medical access",
            "status": "available",
        },
        "ALT-505": {
            "item_name": "Desk Air Purifier",
            "alternative_source": "Regional return warehouse",
            "action_needed": "Cancel the disrupted shipment and request a refund",
            "status": "available",
        },
    }

    # M1 - Lost Bank Card
    if action in ('deactivate_card', 'block_card'):
        last4 = payload.get('last4','1234')
        if _should_log_debug():
            print(f"DEBUG: Deactivating card with last4: {last4} (Type: {type(last4)})")
        env = deep_merge(env, {"payments":{"cards":{last4:{"state":"blocked"}}}})
        env = deep_merge(env, {"merchant_bindings":{"updated":["shop.local","ride.local","food.local","stream.local","cloud.local"]}}) 
        
        # Abstract Attribute Update
        env = deep_merge(env, {"world_state": {"financial_context": {"liquidity": "frozen"}}})

        # Sync to SQLite DB for consistency with _env_api queries
        try:
            execute_db_fn("UPDATE cards SET state = 'blocked' WHERE last4 = ?", (last4,))
        except Exception: pass

        try:
            # FIX: Write to both specific and generic keys for criteria matching
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'payments.cards.{last4}.state', 'blocked', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].state', 'blocked', ts, task_id, 1.0])
        except Exception:
            pass 

        return env, {} # Remove redirect to keep on same page

    # M2 - Supply Chain Disruption
    if action == 'handle_supply_disruption':
        sub_action = payload.get('action_type')
        alternative_id = payload.get('alternative_id')

        if 'supply_chain' not in env:
            env['supply_chain'] = {}
        if 'alternatives' not in env['supply_chain']:
            env['supply_chain']['alternatives'] = {}

        alternatives = env['supply_chain']['alternatives']
        target = dict(alternatives.get(alternative_id) or fallback_alternatives.get(alternative_id) or {})

        if sub_action == 'switch_to_pickup':
            target['status'] = 'pickup_confirmed'
            target['action_needed'] = 'Switched to pickup mode'
        elif sub_action == 'keep_shipping':
            target['status'] = 'reroute_shipping'
            target['action_needed'] = 'Delivery is being rerouted to an alternate hub'
        elif sub_action == 'cancel_order':
            target['status'] = 'refund_pending'
            target['action_needed'] = 'Refund has been requested for the disrupted shipment'
        else:
            target['status'] = target.get('status', 'available')

        env = deep_merge(env, {"supply_chain": {"alternatives": {alternative_id: target}}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['supply_chain.alternatives.last.id', alternative_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['supply_chain.alternatives.last.status', target.get('status', ''), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['supply_chain.alternatives.last.action_type', sub_action, ts, task_id, 1.0])
        except Exception:
            pass

        return env, {"redirect": "/shop.local/supply-disruption.html"}

    # M3 - Sudden Illness/Isolation
    if action == 'submit_illness_report':
        report_id = f"ILL-{random.randint(10000, 99999)}"
        report_type = payload.get('type')
        reason = payload.get('reason', '')
        end_date = payload.get('end_date')
        
        # BUTTERFLY EFFECT: Set low energy level
        env = deep_merge(env, {"world_state": {"physical_context": {"status": "impaired", "energy_level": 20}}})

        # Initialize illness reports if not exists
        if 'health' not in env: env['health'] = {}
        if 'illness_reports' not in env['health']:
            env['health']['illness_reports'] = {}

        env = deep_merge(env, {"health": {"illness_reports": {report_id: {
            "type": report_type,
            "reason": reason,
            "end_date": end_date,
            "status": "pending",
            "submitted_at": ts
        }}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'health.illness_reports.{report_id}.id', report_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'health.illness_reports.{report_id}.type', report_type, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'health.illness_reports.{report_id}.reason', reason, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'health.illness_reports.{report_id}.end_date', str(end_date), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'health.illness_reports.{report_id}.status', 'pending', ts, task_id, 1.0])
            # Store "last" report details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.id', report_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.type', report_type, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.reason', reason, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.end_date', str(end_date), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.status', 'pending', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: M3 submit illness report memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/health.local/illness-reporting.html"}

    # M4 - Urgent Loan
    if action == 'apply_urgent_loan':
        amount = float(payload.get('amount', 500))
        purpose = payload.get('purpose', 'emergency')
        loan_id = f"UL-{random.randint(10000, 99999)}"

        env = deep_merge(env, {"banking": {"loans": {"urgent": {"last": {
            "id": loan_id,
            "amount": amount,
            "purpose": purpose,
            "status": "submitted",
            "submitted_at": ts
        }}}}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['banking.loans.urgent.last.id', loan_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['banking.loans.urgent.last.status', 'submitted', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['banking.loans.urgent.last.amount', str(amount), ts, task_id, 1.0])
        except Exception:
            pass

        return env, {"redirect": f"/bank.local/dashboard.html?loan=submitted&task={task_id}"}

    return env, {}
