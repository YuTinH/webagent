from .utils import deep_merge
import random
import datetime as dt_module

def handle_h_government(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # H1 - Municipal Address Change
    if action == 'change_municipal_address':
        new_address = payload.get('new_address')
        zip_code = payload.get('zip_code')
        proof_document = payload.get('proof_document')
        
        # Initialize user_profile if not exists
        if 'user_profile' not in env:
            env['user_profile'] = {}
        if 'address' not in env['user_profile']:
            env['user_profile']['address'] = {
                "current_address": "北京市朝阳区某某街道某某小区1号楼101室",
                "zip_code": "100000"
            }
        if 'address_change_history' not in env['user_profile']:
            env['user_profile']['address_change_history'] = {}

        change_id = f"ADDR-{random.randint(1000, 9999)}"
        env['user_profile']['address']['current_address'] = new_address
        env['user_profile']['address']['zip_code'] = zip_code
        env['user_profile']['address_change_history'][change_id] = {
            "new_address": new_address,
            "zip_code": zip_code,
            "proof_document": proof_document,
            "status": "pending",
            "submitted_at": ts
        }

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_profile.address.current_address', new_address, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_profile.address.zip_code', zip_code, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'user_profile.address_change_history.{change_id}.id', change_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'user_profile.address_change_history.{change_id}.status', 'pending', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_profile.address_change_history.last.id', change_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_profile.address_change_history.last.status', 'pending', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_profile.address.last_change_id', change_id, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: H1 address change memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/gov.local/address-change.html"}

    # H2 - Vehicle Address Update
    if action == 'update_vehicle_address':
        vehicle_id = payload.get('vehicle_id')
        new_address = payload.get('new_address')
        notify_insurance = payload.get('notify_insurance', False)
        
        # Initialize vehicles if not exists
        if 'gov' not in env: env['gov'] = {}
        if 'vehicles' not in env['gov']:
            env['gov']['vehicles'] = {
                "V-8821": { "plate": "沪A-12345", "model": "Tesla Model 3", "address": "旧地址..." }
            }

        current_vehicle = env['gov']['vehicles'].get(vehicle_id, {})
        current_vehicle['address'] = new_address
        env = deep_merge(env, {"gov": {"vehicles": {vehicle_id: current_vehicle}}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'gov.vehicles.{vehicle_id}.address', new_address, ts, task_id, 1.0])
            val_notify = '1' if notify_insurance else '0'
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'gov.vehicles.{vehicle_id}.insurance_notified', val_notify, ts, task_id, 1.0])
            # Store "last" update details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.vehicles.last.id', vehicle_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.vehicles.last.address', new_address, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.vehicles.last.insurance_notified', val_notify, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: H2 update vehicle address memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/gov.local/vehicle-registration.html"}

    # H3 - Permit Renewal
    if action == 'book_permit':
        permit_id = payload.get('permit_id', 'RP-2024-77')
        new_expiry = payload.get('new_expiry', dt_module.datetime.now().strftime('%Y-%m-%d') + 'T10:00')
        env = deep_merge(env, {"permits":{permit_id:{"next_appointment":new_expiry}}})
        
        # Update memory for assertion
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'permits.{permit_id}.next_appointment', new_expiry, ts, task_id, 1.0])
        except Exception:
            pass

        return env, {"redirect": f"/gov.local/permits.html?renewed=true"}

    # H4 - Parking Permit Application/Renewal
    if action == 'manage_parking_permit':
        sub_action = payload.get('action_type')

        # Initialize parking permits if not exists
        if 'gov' not in env: env['gov'] = {}
        if 'parking_permits' not in env['gov']:
            env['gov']['parking_permits'] = {}

        if sub_action == 'apply':
            permit_id = f"PRM-{random.randint(10000, 99999)}"
            plate_number = payload.get('plate_number')
            permit_type = payload.get('permit_type')
            duration_months = payload.get('duration_months')
            
            expiry_date = (dt_module.datetime.now() + dt_module.timedelta(days=duration_months * 30)).strftime('%Y-%m-%d')

            env = deep_merge(env, {"gov": {"parking_permits": {permit_id: {
                "plate_number": plate_number,
                "permit_type": permit_type,
                "duration_months": duration_months,
                "expiry_date": expiry_date,
                "status": "active",
                "applied_at": ts
            }}}})
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gov.parking_permits.{permit_id}.id', permit_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gov.parking_permits.{permit_id}.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gov.parking_permits.{permit_id}.expiry_date', expiry_date, ts, task_id, 1.0])
                # Store "last" permit details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.id', permit_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.expiry_date', expiry_date, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.plate_number', plate_number, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: H4 apply permit memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/gov.local/parking-permits.html"}

        elif sub_action == 'renew':
            permit_id = payload.get('permit_id')
            duration_months = payload.get('duration_months')
            
            current_permit = env.get('gov', {}).get('parking_permits', {}).get(permit_id, {})
            # Extend expiry date
            current_expiry = dt_module.datetime.strptime(current_permit.get('expiry_date', ts).split('T')[0], '%Y-%m-%d')
            new_expiry_date = (current_expiry + dt_module.timedelta(days=duration_months * 30)).strftime('%Y-%m-%d')
            current_permit['expiry_date'] = new_expiry_date
            current_permit['status'] = 'active'
            env = deep_merge(env, {"gov": {"parking_permits": {permit_id: current_permit}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gov.parking_permits.{permit_id}.expiry_date', new_expiry_date, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gov.parking_permits.{permit_id}.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.expiry_date', new_expiry_date, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.status', 'active', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: H4 renew permit memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/gov.local/parking-permits.html"}

        elif sub_action == 'cancel':
            permit_id = payload.get('permit_id')
            
            current_permit = env.get('gov', {}).get('parking_permits', {}).get(permit_id, {})
            current_permit['status'] = 'cancelled'
            env = deep_merge(env, {"gov": {"parking_permits": {permit_id: current_permit}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gov.parking_permits.{permit_id}.status', 'cancelled', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['gov.parking_permits.last.status', 'cancelled', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: H4 cancel permit memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/gov.local/parking-permits.html"}
            
        return env, {}

    return env, {}
