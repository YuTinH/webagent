from .utils import deep_merge
import random
import datetime as dt_module
import json

def handle_l_privacy(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # L1 - Password Manager
    if action == 'manage_password':
        sub_action = payload.get('action_type')

        # Initialize passwords if not exists
        if 'security' not in env: env['security'] = {}
        if 'passwords' not in env['security']:
            env['security']['passwords'] = {}

        if sub_action == 'add':
            password_id = f"PW-{random.randint(10000, 99999)}"
            site = payload.get('site')
            username = payload.get('username')
            password = payload.get('password') # In real app, store hashed password

            env = deep_merge(env, {"security": {"passwords": {password_id: {
                "site": site,
                "username": username,
                "password": password, # Storing plaintext for simulation
                "last_updated": ts
            }}}})
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.passwords.{password_id}.id', password_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.passwords.{password_id}.site', site, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.passwords.{password_id}.username', username, ts, task_id, 1.0])
                # Store "last" password details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.passwords.last.id', password_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.passwords.last.site', site, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.passwords.last.username', username, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: L1 add password memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/security.local/password-manager.html"}

        elif sub_action == 'delete':
            password_id = payload.get('password_id')
            
            if env.get('security', {}).get('passwords', {}).pop(password_id, None):
                try:
                    execute_db_fn("DELETE FROM memory_kv WHERE key LIKE ?", [f'security.passwords.{password_id}%'])
                except Exception as e:
                    print(f"ERROR: L1 delete password memory_kv failed: {e}")
                    pass
            
            return env, {"redirect": "/security.local/password-manager.html"}

    # L2 - Data Deletion Request (DSR)
    if action == 'manage_data_request':
        sub_action = payload.get('action_type')

        # Initialize data deletion requests if not exists
        if 'security' not in env: env['security'] = {}
        if 'data_deletion_requests' not in env['security']:
            env['security']['data_deletion_requests'] = {}

        if sub_action == 'submit':
            request_id = f"DSR-{random.randint(10000, 99999)}"
            request_type = payload.get('request_type')
            platform = payload.get('platform')
            data_scope = payload.get('data_scope')

            env = deep_merge(env, {"security": {"data_deletion_requests": {request_id: {
                "request_type": request_type,
                "platform": platform,
                "data_scope": data_scope,
                "status": "pending",
                "submitted_at": ts
            }}}})
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.data_deletion_requests.{request_id}.id', request_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.data_deletion_requests.{request_id}.platform', platform, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.data_deletion_requests.{request_id}.status', 'pending', ts, task_id, 1.0])
                # Store "last" request details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.data_deletion_requests.last.id', request_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.data_deletion_requests.last.platform', platform, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.data_deletion_requests.last.status', 'pending', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: L2 submit DSR memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/security.local/data-deletion.html"}

        elif sub_action == 'cancel':
            request_id = payload.get('request_id')
            
            current_request = env.get('security', {}).get('data_deletion_requests', {}).get(request_id, {})
            current_request['status'] = 'cancelled'
            env = deep_merge(env, {"security": {"data_deletion_requests": {request_id: current_request}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'security.data_deletion_requests.{request_id}.status', 'cancelled', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.data_deletion_requests.last.status', 'cancelled', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: L2 cancel DSR memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/security.local/data-deletion.html"}

    # L3 - Security Key Rotation
    if action == 'rotate_keys':
        providers = payload.get('providers', [])
        
        env = deep_merge(env, {"security": {"last_rotation": {
            "providers": providers,
            "timestamp": ts,
            "status": "complete"
        }}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['security.rotation.status', 'complete', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['security.rotation.providers', json.dumps(providers), ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": "/security.local/dashboard.html?rotated=true"}

    # L4 - Change 2FA Device
    if action == 'change_2fa_device':
        new_device_name = payload.get('new_device_name')
        
        # Initialize security data if not exists
        if 'security' not in env: env['security'] = {}
        if 'mfa' not in env['security']:
            env['security']['mfa'] = {
                "enabled": True,
                "current_device": "Unknown Device",
                "last_updated": "2024-01-01"
            }
        if 'mfa_history' not in env['security']:
            env['security']['mfa_history'] = {}

        change_id = f"MFA-{random.randint(1000, 9999)}"
        env['security']['mfa']['current_device'] = new_device_name
        env['security']['mfa']['last_updated'] = ts
        
        env['security']['mfa_history'][change_id] = {
            "device_name": new_device_name,
            "date": ts
        }

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['security.mfa.current_device', new_device_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['security.mfa.last_updated', ts, ts, task_id, 1.0])
            # Store "last" history details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['security.mfa_history.last.device_name', new_device_name, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: L4 change 2FA memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/security.local/2fa.html"}

    return env, {}
