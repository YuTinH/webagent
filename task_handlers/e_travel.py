from .utils import deep_merge
from .time_utils import get_sim_time
import random
from datetime import datetime, timedelta

def handle_e_travel(task_id, action, payload, env, execute_db_fn):
    # Use sim time instead of system time for consistency where appropriate
    # For now, most legacy E tasks use dt_module.datetime.now(). 
    # We'll use get_sim_time for the new E7 task.
    ts = datetime.now().isoformat()
    sim_ts = get_sim_time(env).isoformat()

    # E7 - Visa Application (Long Haul Trip Step 1)
    if action == 'apply_visa':
        app_id = f"VISA-{random.randint(10000, 99999)}"
        destination = payload.get('destination')
        passport_number = payload.get('passport_number')
        
        # Initialize structure in 'gov' key (even if handled by E handler, it affects Gov state)
        if 'gov' not in env: env['gov'] = {}
        if 'visa_applications' not in env['gov']: env['gov']['visa_applications'] = {}

        env = deep_merge(env, {"gov": {"visa_applications": {
            app_id: {
                "destination": destination,
                "passport": passport_number,
                "status": "pending",
                "submitted_at": sim_ts
            },
            "last": {
                "id": app_id,
                "destination": destination,
                "status": "pending"
            }
        }}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'gov.visa_applications.{app_id}.status', 'pending', sim_ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.visa_applications.last.status', 'pending', sim_ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.visa_applications.last.destination', destination, sim_ts, task_id, 1.0])
        except Exception:
            pass
            
        return env, {"redirect": "/gov.local/visa-apply.html"}

    # E1 - Commute Route Comparison
    if action == 'search_commute_route':
        origin = payload.get('origin')
        destination = payload.get('destination')
        commute_time = payload.get('commute_time')
        transport_mode = payload.get('transport_mode')

        # Simulate route results based on mode
        results = {}
        if transport_mode == 'bus' or transport_mode == 'all':
            results['bus_route'] = {
                "transport_mode_cn": "公交", "route_name": "快速公交线1号",
                "origin": origin, "destination": destination,
                "duration": "45分钟", "cost": 3.0, "details": "途径3个站点，高峰期较拥堵"
            }
        if transport_mode == 'subway' or transport_mode == 'all':
            results['subway_route'] = {
                "transport_mode_cn": "地铁", "route_name": "地铁2号线",
                "origin": origin, "destination": destination,
                "duration": "30分钟", "cost": 5.0, "details": "直达，早高峰人多"
            }
        if transport_mode == 'bike' or transport_mode == 'all':
            results['bike_route'] = {
                "transport_mode_cn": "骑行", "route_name": "沿河绿道",
                "origin": origin, "destination": destination,
                "duration": "25分钟", "cost": 0.0, "details": "风景优美，适合晴天"
            }
        if transport_mode == 'car_hailing' or transport_mode == 'all':
            results['car_hailing_route'] = {
                "transport_mode_cn": "打车", "route_name": "出租车/网约车",
                "origin": origin, "destination": destination,
                "duration": "20分钟", "cost": 35.0, "details": "最快，费用高"
            }

        env = deep_merge(env, {"commute": {"search_results": results}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.origin', origin, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.destination', destination, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.transport_mode', transport_mode, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: E1 commute search memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/trip.local/commute.html"}

    # E2 - Transport Card Top-up
    if action == 'transport_topup':
        sub_action = payload.get('action_type')
        
        # Initialize transport card if not exists
        if 'transport' not in env:
            env['transport'] = {}
        if 'card' not in env['transport']:
            env['transport']['card'] = {
                "number": "TR-8888-8888",
                "balance": 25.50,
                "status": "active",
                "auto_recharge": {"enabled": False, "threshold": 20, "amount": 50}
            }
            
        current_card = env['transport']['card']

        if sub_action == 'topup':
            amount = payload.get('amount', 0)
            current_card['balance'] += amount
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['transport.card.balance', str(current_card['balance']), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['transport.card.last_topup_amount', str(amount), ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: E2 topup memory_kv insert failed: {e}")
                pass

        elif sub_action == 'set_auto_recharge':
            enabled = payload.get('enabled')
            threshold = payload.get('threshold')
            amount = payload.get('amount')
            
            current_card['auto_recharge'] = {
                "enabled": enabled,
                "threshold": threshold,
                "amount": amount
            }
            
            try:
                val_enabled = '1' if enabled else '0'
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['transport.card.auto_recharge.enabled', val_enabled, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['transport.card.auto_recharge.threshold', str(threshold), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['transport.card.auto_recharge.amount', str(amount), ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: E2 auto-recharge memory_kv update failed: {e}")
                pass
        
        env['transport']['card'] = current_card
        return env, {"redirect": "/trip.local/transport-card.html"}

    # E1 - Flight Booking
    if action == 'book_flight':
        pnr = payload.get('pnr', f"PNR-{random.randint(8000, 8999)}")
        destination = payload.get('destination')
        date = payload.get('date', dt_module.datetime.now().strftime('%Y-%m-%d'))
        price = float(payload.get('price', 450))
        env = deep_merge(env, {"trips": {"flight": {"pnr": pnr, "destination": destination, "date": date, "price": price}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.pnr', pnr, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.destination', destination, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/trip.local/manage.html?pnr={pnr}&status=confirmed&date={date}"}

    # E2 - Hotel Booking
    if action == 'book_hotel':
        booking_id = payload.get('bookingId', f"HTL-{random.randint(700,999)}")
        city = payload.get('city', '上海') 
        checkin = payload.get('checkin', dt_module.datetime.now().strftime('%Y-%m-%d'))
        nights_val = payload.get('nights')
        nights = int(nights_val) if nights_val is not None else 3
        env = deep_merge(env, {"trips": {"hotel": {"id": booking_id, "city": city, "checkin": checkin, "nights": nights}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.id', booking_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.checkin', checkin, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/trip.local/manage.html?status=confirmed"}

    # E4 - Visa Requirements Search
    if action == 'search_visa_requirements':
        destination = payload.get('destination_country')
        passport = payload.get('passport_country', 'China')

        # Mock data for visa requirements
        visa_info = {}
        if destination == 'Japan':
            visa_info = {
                "destination": "Japan", "destination_cn": "日本",
                "passport": "China", "passport_cn": "中国",
                "visa_type": "短期滞在 (旅游)",
                "stay_duration": "15天 / 30天 / 90天",
                "documents": ["护照", "照片", "申请表", "行程单", "资产证明"],
                "notes": "电子签证 (eVISA) 已对部分中国公民开放。"
            }
        elif destination == 'France':
            visa_info = {
                "destination": "France", "destination_cn": "法国",
                "passport": "China", "passport_cn": "中国",
                "visa_type": "申根签证 (Type C)",
                "stay_duration": "最长90天 (180天内)",
                "documents": ["护照", "照片", "申请表", "保险", "机票预订", "酒店预订", "银行流水"],
                "notes": "需前往签证中心采集指纹。"
            }
        else: # Default/Generic
            visa_info = {
                "destination": destination, "destination_cn": destination,
                "passport": "China", "passport_cn": "中国",
                "visa_type": "需要查询使馆官网",
                "stay_duration": "未知",
                "documents": ["一般需要护照和申请表"],
                "notes": "请咨询相关大使馆。"
            }

        env = deep_merge(env, {"visa": {"last_search_result": visa_info}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['visa.search.last.destination', destination, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['visa.search.last.visa_type', visa_info['visa_type'], ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: E4 visa search memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/trip.local/visa-requirements.html"}

    # E5 - Expense Report
    if action == 'submit_expense':
        report_id = payload.get('reportId', "EXP-3344")
        total = float(payload.get('total', 1200))
        linked_pnr = payload.get('pnr', env.get('trips', {}).get('flight', {}).get('pnr', 'PNR-UNKNOWN'))
        env = deep_merge(env, {"expenses": {"reports": {report_id: {"state": "submitted", "total": total, "pnr": linked_pnr}}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.id', report_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.total', str(total), ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/bank.local/expense-report.html?report={report_id}"}

    # E6 - Travel Rebooking
    if action == 'rebook_ok':
        import time
        hist = {"action":"rebook","ts":time.time()}
        env = deep_merge(env, {"trips":{"PNR9ZZ":{"status":"rebooked","history":[hist]}}})
        return env, {"redirect": "/trip.local/manage/PNR9ZZ.html?status=rebooked"}

    return env, {}
