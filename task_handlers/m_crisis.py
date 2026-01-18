from .utils import deep_merge
import random
import datetime as dt_module

def handle_m_crisis(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # M1 - Lost Bank Card
    if action == 'block_card':
        last4 = payload.get('last4','1234')
        env = deep_merge(env, {"payments":{"cards":{last4:{"state":"blocked"}}}})
        env = deep_merge(env, {"merchant_bindings":{"updated":["shop.local","ride.local","food.local","stream.local","cloud.local"]}}) 
        
        # Sync to SQLite DB for consistency with _env_api queries
        try:
            execute_db_fn("UPDATE cards SET state = 'blocked' WHERE last4 = ?", (last4,))
        except Exception: pass

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'payments.cards.{last4}.state', 'blocked', ts, task_id, 1.0])
        except Exception:
            pass 

        return env, {"redirect": "/card.local/block.html"}

    # M2 - Supply Chain Disruption
    if action == 'handle_supply_disruption':
        sub_action = payload.get('action_type')

        # Initialize supply chain data if not exists (Simulate a disruption event)
        if 'supply_chain' not in env:
            env['supply_chain'] = {
                "disruptions": {
                    "DIS-001": {
                        "title": "物流罢工预警",
                        "description": "由于区域物流罢工，部分快递配送将延迟3-5天。",
                        "affected_areas": ["市中心", "高新区"]
                    }
                },
                "alternatives": {
                    "ALT-101": {
                        "item_name": "生鲜蔬菜包",
                        "alternative_source": "社区合作自提点",
                        "status": "available",
                        "action_needed": "建议切换为自提以避免延误"
                    }
                }
            }

        if sub_action == 'switch_to_pickup':
            alt_id = payload.get('alternative_id')
            
            # Update status to reflect user took action
            if alt_id in env['supply_chain']['alternatives']:
                env['supply_chain']['alternatives'][alt_id]['status'] = 'switched_to_pickup'
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'supply_chain.alternatives.{alt_id}.status', 'switched_to_pickup', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['supply_chain.last_action.type', 'switch_to_pickup', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: M2 handle disruption memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/shop.local/supply-disruption.html"}
            
        return env, {}

    # M3 - Sudden Illness/Isolation
    if action == 'submit_illness_report':
        report_id = f"ILL-{random.randint(10000, 99999)}"
        report_type = payload.get('type')
        reason = payload.get('reason')
        end_date = payload.get('end_date')

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
                       [f'health.illness_reports.{report_id}.status', 'pending', ts, task_id, 1.0])
            # Store "last" report details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.id', report_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.type', report_type, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.illness_reports.last.status', 'pending', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: M3 submit illness report memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/health.local/illness-reporting.html"}

    return env, {}
