from .utils import deep_merge
import random
import datetime as dt_module
import hashlib

def handle_k_social(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # K1 - Join Community
    if action == 'join_group':
        gid = payload.get('groupId')
        gname = payload.get('groupName')
        
        env = deep_merge(env, {"social": {"groups": {gid: {"name": gname, "joined_at": ts}}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'social.groups.{gid}.status', 'joined', ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": "/social.local/my-groups.html"}

    # K2 - Roommate Split
    if action == 'split_expenses':
        month = payload.get('month')
        members = payload.get('members', [])
        rules = payload.get('rules')
        
        # In a real app, this would calculate actual splits. Here we just set state.
        settlement_id = f"{month}-{hashlib.md5(str(members).encode()).hexdigest()[:4]}"
        env = deep_merge(env, {"settlements": {month: {"state": "settled", "members": members, "rules": rules, "settled_at": ts}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'settlements.{month}.state', 'settled', ts, task_id, 1.0])
        except Exception:
            pass
        
        return env, {"redirect": f"/social.local/split.html?month={month}&state=settled"}

    # K3 - Charity Donation and Receipt Acquisition
    if action == 'make_donation':
        donation_id = f"DON-{random.randint(10000, 99999)}"
        charity_name = payload.get('charity_name')
        amount = payload.get('amount')
        tax_deductible = payload.get('tax_deductible', False)

        # Initialize charity data if not exists
        if 'charity' not in env:
            env['charity'] = {}
        if 'donations' not in env['charity']:
            env['charity']['donations'] = {}

        env = deep_merge(env, {"charity": {"donations": {donation_id: {
            "charity_name": charity_name,
            "amount": amount,
            "tax_deductible": tax_deductible,
            "date": ts.split('T')[0] # Store only date
        }}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'charity.donations.{donation_id}.id', donation_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'charity.donations.{donation_id}.charity_name', charity_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'charity.donations.{donation_id}.amount', str(amount), ts, task_id, 1.0])
            val_tax_deductible = '1' if tax_deductible else '0'
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'charity.donations.{donation_id}.tax_deductible', val_tax_deductible, ts, task_id, 1.0])
            # Store "last" donation details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['charity.donations.last.id', donation_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['charity.donations.last.charity_name', charity_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['charity.donations.last.amount', str(amount), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['charity.donations.last.tax_deductible', val_tax_deductible, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: K3 make donation memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/social.local/charity.html"}

    return env, {}
