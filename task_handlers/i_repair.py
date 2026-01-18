from .utils import deep_merge
import random
import datetime as dt_module

def handle_i_repair(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # I1 - House Repair Order
    if action == 'submit_repair_request':
        request_id = f"RPR-{random.randint(10000, 99999)}"
        item = payload.get('item')
        problem = payload.get('problem')
        service_date = payload.get('service_date')
        contact_phone = payload.get('contact_phone')

        env = deep_merge(env, {"repairs": {"requests": {request_id: {
            "item": item,
            "problem": problem,
            "service_date": service_date,
            "contact_phone": contact_phone,
            "status": "submitted",
            "submitted_at": ts
        }}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'repairs.requests.{request_id}.id', request_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'repairs.requests.{request_id}.item', item, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'repairs.requests.{request_id}.problem', problem, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'repairs.requests.{request_id}.status', 'submitted', ts, task_id, 1.0])
            # Store "last" request details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                       ['repairs.requests.last.id', request_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                       ['repairs.requests.last.item', item, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                       ['repairs.requests.last.status', 'submitted', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                       ['repairs.requests.last.problem', problem, ts, task_id, 1.0])        
        except Exception as e:
            print(f"ERROR: I1 submit repair memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/repairs.html"}

    if action == 'cancel_repair_request':
        request_id = payload.get('request_id')

        current_request = env.get('repairs', {}).get('requests', {}).get(request_id, {})
        current_request['status'] = 'cancelled'
        env = deep_merge(env, {"repairs": {"requests": {request_id: current_request}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'repairs.requests.{request_id}.status', 'cancelled', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['repairs.requests.last.status', 'cancelled', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: I1 cancel repair memory_kv update failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/repairs.html"}

    # I2 - Appliance Repair and Warranty
    if action == 'submit_appliance_repair':
        request_id = f"APR-{random.randint(10000, 99999)}"
        appliance = payload.get('appliance')
        serial_number = payload.get('serial_number')
        problem = payload.get('problem')
        service_date = payload.get('service_date')

        env = deep_merge(env, {"appliance_repairs": {"requests": {request_id: {
            "appliance": appliance,
            "serial_number": serial_number,
            "problem": problem,
            "service_date": service_date,
            "status": "submitted",
            "submitted_at": ts
        }}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'appliance_repairs.requests.{request_id}.id', request_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'appliance_repairs.requests.{request_id}.appliance', appliance, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'appliance_repairs.requests.{request_id}.problem', problem, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'appliance_repairs.requests.{request_id}.status', 'submitted', ts, task_id, 1.0])
            # Store "last" request details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['appliance_repairs.requests.last.id', request_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['appliance_repairs.requests.last.appliance', appliance, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['appliance_repairs.requests.last.problem', problem, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['appliance_repairs.requests.last.status', 'submitted', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: I2 submit appliance repair memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/appliance-repair.html"}

    if action == 'cancel_appliance_repair':
        request_id = payload.get('request_id')

        current_request = env.get('appliance_repairs', {}).get('requests', {}).get(request_id, {})
        current_request['status'] = 'cancelled'
        env = deep_merge(env, {"appliance_repairs": {"requests": {request_id: current_request}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'appliance_repairs.requests.{request_id}.status', 'cancelled', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['appliance_repairs.requests.last.status', 'cancelled', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: I2 cancel appliance repair memory_kv update failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/appliance-repair.html"}
    
    # I3 - Smart Bulb Setup
    if action == 'setup_smart_bulb':
        device_id = payload.get('deviceId', 'BULB-001')
        location = payload.get('location', '客厅')
        color = payload.get('color', 'warm_white')

        env = deep_merge(env, {"devices": {device_id: {
            "type": "smart_bulb",
            "location": location,
            "color": color,
            "status": "active"
        }}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'devices.{device_id}.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'devices.{device_id}.location', location, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/energy.local/index.html?setup_success=true"}

    # I4 - Smart Meter Reading and Bill Verification
    if action == 'submit_meter_reading':
        reading = payload.get('reading')
        
        # Initialize meter data if not exists
        if 'meters' not in env:
            env['meters'] = {}
        if 'meter_data' not in env['meters']:
            env['meters']['meter_data'] = {
                "current_reading": 0.0,
                "last_billed_reading": 0.0,
                "last_bill_amount": 0.0,
                "last_bill_date": None
            }
        
        env['meters']['meter_data']['current_reading'] = reading

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['meters.meter_data.current_reading', str(reading), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['meters.meter_data.last_submitted_reading', str(reading), ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: I4 submit meter reading memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/energy.local/smart-meter.html"}

    # I5 - Energy Optimization
    if action == 'set_energy_plan':
        plan = payload.get('plan','green_offpeak')
        meter = payload.get('meterId','M-321')
        env = deep_merge(env, {"meters":{meter:{"plan":plan}}})
        return env, {"redirect": "/energy.local/plan.html"}

    return env, {}
