from .utils import deep_merge
import random
import datetime as dt_module

def handle_a_housing(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # A1 - Find Home
    if action == 'rent_property':
        prop_id = payload.get('propertyId', 'PROP-101')
        term = payload.get('leaseTerm', '12 months')
        
        # Define address based on property ID
        address_map = {
            'PROP-101': '中央大街101号',
            'PROP-102': '阳光海岸别墅区20号'
        }
        new_address = address_map.get(prop_id, '未知地址')

        # Update leases
        env = deep_merge(env, {"housing": {"leases": {prop_id: {"status": "signed", "term": term}}}})
        
        # BUTTERFLY EFFECT: Update global user profile address
        if 'user_profile' not in env: env['user_profile'] = {}
        if 'address' not in env['user_profile']: env['user_profile']['address'] = {}
        env['user_profile']['address']['current_address'] = new_address
        
        # New Abstract Attribute Update
        if 'world_state' not in env: env['world_state'] = {}
        if 'location_context' not in env['world_state']: env['world_state']['location_context'] = {}
        
        if prop_id == 'PROP-102': # Suburban Villa
            env['world_state']['location_context']['tier'] = 'suburban'
        else:
            env['world_state']['location_context']['tier'] = 'city_center'
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['housing.lease.last.id', prop_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['housing.lease.last.status', 'signed', ts, task_id, 1.0])
            # Also record address change for consistency
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_profile.address.current_address', new_address, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/housing.local/index.html"}

    # A2 - Bank Account Opening
    if action == 'open_account':
        fullname = payload.get('fullname')
        phone = payload.get('phone')
        address = payload.get('address')
        enable2fa = payload.get('enable2fa', False)
        
        account_id = f"ACC-{random.randint(100000, 999999)}"
        env = deep_merge(env, {
            "bank": {
                "account": {
                    "id": account_id,
                    "fullname": fullname,
                    "phone": phone,
                    "address": address,
                    "status": "active",
                    "2fa": enable2fa
                }
            }
        })
        
        try:
             execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.id', account_id, ts, task_id, 1.0])
             execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.status', 'active', ts, task_id, 1.0])
             val_2fa = '1' if enable2fa else '0'
             execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.2fa', val_2fa, ts, task_id, 1.0])
             execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.fullname', fullname, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: A2 memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/bank.local/dashboard.html"}

    # A3 - Utility Setup
    if action == 'setup_utility':
        services = payload.get('services', [])
        plans = payload.get('plans', {})
        addr = payload.get('address', '')
        
        contracts = {}
        for svc in services:
            contracts[svc] = {"status": "active", "plan": plans.get(svc, "standard"), "address": addr, "start_date": payload.get('date')}
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'contracts.{svc}.id', f'CTR-{svc.upper()}-{random.randint(1000,9999)}', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'contracts.{svc}.status', 'active', ts, task_id, 1.0])
            except Exception:
                pass
        
        env = deep_merge(env, {"contracts": contracts})
        return env, {"redirect": "/energy.local/plan.html?setup_success=true"}

    # A4 - Mobile Plan
    if action == 'mobile_subscribe':
        plan_id = payload.get('planId', 'starter')
        plan_name = {'starter': 'Starter Plan', 'unlimited': 'Unlimited Plan', 'pro': 'Pro Plan'}.get(plan_id, 'Unknown Plan')
        data_limit = {'starter': '5GB', 'unlimited': 'Unlimited', 'pro': 'Unlimited'}.get(plan_id, '5GB')
        
        phone_number = f"555-{random.randint(100,999)}-{random.randint(1000,9999)}"
        next_bill = (dt_module.datetime.now() + dt_module.timedelta(days=30)).strftime('%Y-%m-%d')
        
        env = deep_merge(env, {"mobile": {"subscription": {
            "status": "active",
            "plan_id": plan_id,
            "plan_name": plan_name,
            "phone_number": phone_number,
            "data_limit": data_limit,
            "next_bill_date": next_bill
        }}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['mobile.subscription.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['mobile.subscription.phone', phone_number, ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": "/mobile.local/account.html"}

    # A5 - Lease Management
    if action == 'manage_lease':
        sub_action = payload.get('action_type', 'add')
        lease_id = payload.get('lease_id')
        
        if sub_action == 'add':
            rent = payload.get('rent')
            deposit = payload.get('deposit')
            end_date = payload.get('end_date')
            terms = payload.get('deposit_terms')
            reminder = payload.get('reminder', False)
            
            env = deep_merge(env, {"housing": {"leases": {lease_id: {
                "status": "active",
                "rent": rent,
                "deposit": deposit,
                "end_date": end_date,
                "deposit_terms": terms,
                "reminder": reminder
            }}}})
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'housing.leases.{lease_id}.id', lease_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'housing.leases.{lease_id}.deposit', str(deposit), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'housing.leases.{lease_id}.end_date', end_date, ts, task_id, 1.0])
                val_reminder = '1' if reminder else '0'
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'housing.leases.{lease_id}.reminder', val_reminder, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: A5 memory_kv insert failed: {e}")
                pass

        elif sub_action == 'update':
            end_date = payload.get('end_date')
            reminder = payload.get('reminder')
            
            current_lease = env.get('housing', {}).get('leases', {}).get(lease_id, {})
            if end_date: current_lease['end_date'] = end_date
            if reminder is not None: current_lease['reminder'] = reminder
            
            env = deep_merge(env, {"housing": {"leases": {lease_id: current_lease}}})
            
            try:
                if end_date:
                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                               [f'housing.leases.{lease_id}.end_date', end_date, ts, task_id, 1.0])
                if reminder is not None:
                    val_reminder = '1' if reminder else '0'
                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                               [f'housing.leases.{lease_id}.reminder', val_reminder, ts, task_id, 1.0])
            except Exception:
                pass

        return env, {}

    # A6 - Address Proof
    if action == 'verify_address':
        doc_type = payload.get('docType')
        fn = payload.get('fileName')
        
        env = deep_merge(env, {"identity": {"address_verified": True, "proof_doc": {"type": doc_type, "file": fn, "uploaded_at": ts}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['identity.address_verified', 'true', ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": "/gov.local/profile.html?verified=true"}

    return env, {}
