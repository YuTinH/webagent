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
        
        # Abstract Attribute Update
        env = deep_merge(env, {"world_state": {"financial_context": {"liquidity": "frozen"}}})

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
    # ... (skipping)

    # M3 - Sudden Illness/Isolation
    if action == 'submit_illness_report':
        report_id = f"ILL-{random.randint(10000, 99999)}"
        report_type = payload.get('type')
        
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
