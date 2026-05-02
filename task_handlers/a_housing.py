from .utils import deep_merge
import random
import datetime as dt_module

def handle_a_housing(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    if action == 'rent_property':
        prop_id = payload.get('property_id', 'PROP-101')
        term = payload.get('term', '12')
        location_tier = "suburban" if str(prop_id).upper() == "PROP-102" else "city_center"
        env = deep_merge(
            env,
            {
                "has_home": True,
                "housing": {"lease": {"last": {"id": prop_id, "term": term}}},
                "world_state": {"location_context": {"tier": location_tier}},
            },
        )
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['housing.lease.last.id', prop_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['housing.lease.last.term', str(term), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['world_state.location_context.tier', location_tier, ts, task_id, 1.0])
        except: pass
        return env, {"redirect": "/housing.local/index.html"}

    if action == 'open_account':
        fullname = payload.get('fullname', '')
        enable_2fa = bool(payload.get('enable2fa', False))
        env = deep_merge(
            env,
            {
                "has_bank": True,
                "bank": {"account": {"status": "active", "holder_name": fullname, "2fa_enabled": enable_2fa}},
            },
        )
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.holder_name', fullname, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['bank.account.2fa_enabled', '1' if enable_2fa else '0', ts, task_id, 1.0])
        except: pass
        holder = str(fullname or "").replace(" ", "%20")
        enabled = '1' if enable_2fa else '0'
        return env, {"redirect": f"/bank.local/open-account.html?opened=true&holder={holder}&twofa={enabled}&task={task_id}"}

    if action == 'manage_lease':
        sub = payload.get('action_type')
        lease_id = payload.get('lease_id', 'PROP-101')
        if sub == 'add':
            rent_raw = payload.get('rent')
            try:
                rent = float(rent_raw)
                if rent.is_integer():
                    rent = int(rent)
            except Exception:
                rent = rent_raw
            env = deep_merge(
                env,
                {
                    "housing": {
                        "leases": {
                            lease_id: {
                                "status": "active",
                                "end_date": payload.get('end_date'),
                                "rent": rent,
                            }
                        }
                    }
                },
            )
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'housing.leases.{lease_id}.end_date', payload.get('end_date'), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'housing.leases.{lease_id}.rent', str(rent), ts, task_id, 1.0])
            except: pass
        return env, {}

    if action == 'verify_address':
        doc_type = payload.get('doc_type', 'utility_bill')
        file_name = payload.get('file_name', '')
        env = deep_merge(env, {"identity": {"address_verified": True, "address_proof": {"doc_type": doc_type, "file_name": file_name}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['identity.address_verified', 'true', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['identity.address_proof.doc_type', doc_type, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['identity.address_proof.file_name', file_name, ts, task_id, 1.0])
        except: pass
        return env, {"redirect": "/gov.local/profile.html?verified=true"}

    if action == 'mobile_subscribe':
        plan_id = payload.get('planId', 'unlimited')
        plan_profiles = {
            'starter': {'name': 'Starter Plan', 'data_limit': '5GB'},
            'unlimited': {'name': 'Unlimited Plan', 'data_limit': 'Unlimited'},
            'pro': {'name': 'Pro Plan', 'data_limit': 'Unlimited Premium'}
        }
        profile = plan_profiles.get(plan_id, plan_profiles['unlimited'])

        subscription = {
            "plan_id": plan_id,
            "plan_name": profile['name'],
            "data_limit": profile['data_limit'],
            "next_bill_date": "2026-03-16",
            "status": "active",
            "phone": "555-219-8937",
            "name": payload.get('name', ''),
            "address": payload.get('address', '')
        }
        env = deep_merge(env, {"has_mobile": True, "mobile": {"subscription": subscription}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['mobile.subscription.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['mobile.subscription.phone', subscription['phone'], ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['mobile.subscription.plan_id', plan_id, ts, task_id, 1.0])
        except:
            pass
        return env, {"redirect": "/mobile.local/account.html?status=active"}

    return env, {}
