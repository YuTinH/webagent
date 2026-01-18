from .utils import deep_merge
import random
import datetime as dt_module

def handle_g_health(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # G1 - Doctor appointment booking
    if action == 'book_doctor':
        appt_id = payload.get('appointmentId', 'APT-9001')
        doctor_id = payload.get('doctorId', 'DR-001')
        slot = payload.get('slot', '2025-12-02T09:00')
        env = deep_merge(env, {"health": {"appointments": {"last": {"id": appt_id, "doctor": doctor_id, "slot": slot}}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.appointment.last_id', appt_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.appointment.slot', slot, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/health.local/index.html"}

    # G2 - Insurance Policy Purchase
    if action == 'purchase_insurance':
        plan_id = payload.get('plan_id')
        plan_name = payload.get('plan_name')
        provider = payload.get('provider')
        
        # Calculate expiry (1 year from now)
        expiry_date = (dt_module.datetime.now() + dt_module.timedelta(days=365)).strftime('%Y-%m-%d')
        policy_number = f"POL-{random.randint(100000, 999999)}"

        env = deep_merge(env, {"health": {"insurance": {
            "active": True,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "provider": provider,
            "policy_number": policy_number,
            "expiry_date": expiry_date,
            "purchased_at": ts
        }}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.insurance.active', '1', ts, task_id, 1.0]) # '1' for true
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.insurance.plan_name', plan_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.insurance.provider', provider, ts, task_id, 1.0]) # Add provider
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.insurance.policy_number', policy_number, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.insurance.expiry_date', expiry_date, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: G2 purchase insurance memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/health.local/insurance.html"}

    # G3 - Medical insurance claim
    if action == 'submit_claim':
        claim_id = payload.get('claimId', 'CLM-5501')
        appt_id = payload.get('appointmentId', 'APT-9001')
        amount = float(payload.get('amount', 250))
        env = deep_merge(env, {"health": {"claims": {claim_id: {"state": "processing", "appointment_id": appt_id, "amount": amount}}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['insurance.claim.last.id', claim_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['insurance.claim.last.status', 'processing', ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/gov.local/applications/status.html?id={claim_id}"}
    
    # G4 - Prescription Refill
    if action == 'refill_rx':
        rx_id = payload.get('prescriptionId', 'RX-1001')
        medication = payload.get('medication', 'Amoxicillin 250mg')
        prev_refills = env.get('health', {}).get('prescriptions', {}).get(rx_id, {}).get('refills_left', 2)
        refills_left = max(prev_refills - 1, 0)
        refill_ts = ts
        env = deep_merge(env, {"health": {"prescriptions": {rx_id: {"medication": medication, "refills_left": refills_left, "last_refill": refill_ts}}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.rx.last_id', rx_id, refill_ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.rx.last_refill', refill_ts, refill_ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/health.local/records.html"}

    # G5 - Health Plan Activation
    if action == 'activate_health_plan':
        plan_name = payload.get('planName', 'Standard Wellness')
        focus = payload.get('focus', 'Weight Management')
        calories = payload.get('calories', 1800)
        exercise = payload.get('exercise', '30min daily')

        env = deep_merge(env, {"health": {"plan": {
            "status": "active",
            "name": plan_name,
            "focus": focus,
            "calories": calories,
            "exercise": exercise,
            "activated_at": ts
        }}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.plan.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.plan.name', plan_name, ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": "/health.local/plan.html?status=active"}

    # G6 - Book Vaccination
    if action == 'book_vaccine':
        vaccine_type = payload.get('type')
        appt_date = payload.get('date')
        appt_time = payload.get('time')
        clinic = payload.get('clinic', 'City Health Clinic')
        
        vaccine_id = f"VC-{random.randint(10000, 99999)}"
        env = deep_merge(env, {"health": {"vaccines": {vaccine_id: {
            "type": vaccine_type, "date": appt_date, "time": appt_time,
            "clinic": clinic, "status": "booked", "booked_at": ts
        }}}})
        
        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                   [f'health.vaccines.{vaccine_id}.status', 'booked', ts, task_id, 1.0])
        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                   [f'health.vaccines.{vaccine_id}.type', vaccine_type, ts, task_id, 1.0])
        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                   ['health.vaccines.last.status', 'booked', ts, task_id, 1.0])
        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                   ['health.vaccines.last.id', vaccine_id, ts, task_id, 1.0])
        
        return env, {"redirect": "/health.local/vaccine.html?booked=true"}

    return env, {}
