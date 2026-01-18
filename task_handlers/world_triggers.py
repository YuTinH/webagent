from .utils import deep_merge
from .time_utils import get_sim_time
from datetime import datetime, timedelta
import os

def process_time_triggers(env, execute_db_fn=None):
    """
    Check environment state and update it based on time passage.
    This acts as a simulator for background processes (e.g., approval workflows, shipping).
    """
    current_time = get_sim_time(env)
    ts = current_time.isoformat()
    
    # Debug logging
    with open("trigger_debug.log", "a") as f:
        f.write(f"--- Trigger Check at {current_time} ---")
        f.write(f"DEBUG_WORLD_TRIGGER: Initial env['shop']['orders']: {env.get('shop',{}).get('orders',{})}\n")
    
    # --- Trigger 1: Visa Application Approval ---
    # Logic: If a visa application is 'pending' and submitted more than 3 days ago, approve it.
    if 'gov' in env and 'visa_applications' in env['gov']:
        applications = env['gov']['visa_applications']
        for app_id, app in applications.items():
            if app_id == 'last': continue 
            
            with open("trigger_debug.log", "a") as f:
                f.write(f"Checking app {app_id}: {app}\n")

            if app.get('status') == 'pending':
                submitted_at_str = app.get('submitted_at')
                if submitted_at_str:
                    try:
                        submitted_at = datetime.fromisoformat(submitted_at_str)
                        delta_days = (current_time - submitted_at).days
                        
                        with open("trigger_debug.log", "a") as f:
                            f.write(f"  Submitted: {submitted_at}, Delta days: {delta_days}\n")

                        if delta_days >= 3:
                            app['status'] = 'approved'
                            app['updated_at'] = ts
                            
                            with open("trigger_debug.log", "a") as f:
                                f.write(f"  -> APPROVED!\n")

                            # Update Memory KV
                            if execute_db_fn:
                                try:
                                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                               [f'gov.visa_applications.{app_id}.status', 'approved', ts, 'world_trigger', 1.0])
                                except Exception as e:
                                    with open("trigger_debug.log", "a") as f: f.write(f"DB Error: {e}\n")

                            # Update 'last' pointer if needed
                            if env['gov']['visa_applications'].get('last', {}).get('id') == app_id:
                                env['gov']['visa_applications']['last']['status'] = 'approved'
                                if execute_db_fn:
                                    try:
                                        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                                   ['gov.visa_applications.last.status', 'approved', ts, 'world_trigger', 1.0])
                                    except: pass
                    except Exception as e:
                        with open("trigger_debug.log", "a") as f:
                            f.write(f"  Error: {e}\n")

    # --- Trigger 2: Order Delivery ---
    # Logic: If order is 'confirmed' and > 2 days old, mark as 'delivered'.
    if 'shop' in env and 'orders' in env['shop']:
        for oid, order in env['shop']['orders'].items():
            if oid == 'last': continue
            
            # Determine status key
            status_key = 'state' if 'state' in order else 'status'
            current_status = order.get(status_key)
            
            if current_status == 'confirmed':
                # Date field might be 'date' (B1) or 'ordered_at' (B4)
                date_str = order.get('date') or order.get('ordered_at')
                
                if date_str:
                    try:
                        order_date = datetime.fromisoformat(date_str)
                        if (current_time - order_date).days >= 2:
                            order[status_key] = 'delivered'
                            with open("trigger_debug.log", "a") as f:
                                f.write(f"  Order {oid} DELIVERED!\n")
                            
                            # Update Memory KV
                            if execute_db_fn:
                                try:
                                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                               [f'shop.orders.{oid}.{status_key}', 'delivered', ts, 'world_trigger', 1.0])
                                    # Also update SQL table for UI consistency
                                    execute_db_fn("UPDATE orders SET state = ? WHERE id = ?", ['delivered', oid])
                                except: pass
                                
                            # Update last pointer if matches
                            if env['shop']['orders'].get('last', {}).get('id') == oid:
                                env['shop']['orders']['last'][status_key] = 'delivered'
                                if execute_db_fn:
                                    try:
                                        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                                   [f'shop.orders.last.{status_key}', 'delivered', ts, 'world_trigger', 1.0])
                                    except: pass
                    except: pass

    # --- Trigger 3: Investment Growth ---
    # Logic: If investment account active > 7 days, add 5% interest (simulated once).
    if 'finance' in env and 'investment_accounts' in env['finance']:
        for acc_id, acc in env['finance']['investment_accounts'].items():
            if acc_id == 'last': continue
            
            if acc.get('status') == 'active' and not acc.get('interest_applied'):
                opened_at_str = acc.get('opened_at')
                if opened_at_str:
                    try:
                        opened_at = datetime.fromisoformat(opened_at_str)
                        if (current_time - opened_at).days >= 7:
                            # Apply 5% interest
                            current_bal = float(acc.get('balance', 0))
                            new_bal = round(current_bal * 1.05, 2)
                            acc['balance'] = new_bal
                            acc['interest_applied'] = True # Flag to prevent double application
                            
                            with open("trigger_debug.log", "a") as f:
                                f.write(f"  Investment {acc_id} GROWTH! {current_bal} -> {new_bal}\n")
                            
                            if execute_db_fn:
                                try:
                                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                               [f'finance.investment_accounts.{acc_id}.balance', str(new_bal), ts, 'world_trigger', 1.0])
                                except: pass
                                
                            if env['finance']['investment_accounts'].get('last', {}).get('id') == acc_id:
                                env['finance']['investment_accounts']['last']['balance'] = str(new_bal) # specific logic uses str in memory
                                if execute_db_fn:
                                    try:
                                        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                                   ['finance.investment_accounts.last.balance', str(new_bal), ts, 'world_trigger', 1.0])
                                    except: pass
                    except: pass

    return env