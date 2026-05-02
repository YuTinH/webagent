from .utils import deep_merge
from .time_utils import get_sim_time
import random
from datetime import datetime


def _normalize_city_name(value, fallback=''):
    raw = str(value or '').strip()
    if not raw:
        return fallback
    aliases = {
        'beijing': '北京',
        'shanghai': '上海',
        'guangzhou': '广州',
        'shenzhen': '深圳',
        'hangzhou': '杭州',
    }
    return aliases.get(raw.lower(), raw)


def _get_visa_requirement_result(destination, passport):
    destination = str(destination or '').strip() or 'France'
    passport = str(passport or '').strip() or 'China'
    passport_cn = {
        'China': '中国',
        'Singapore': '新加坡',
        'Thailand': '泰国',
        'Vietnam': '越南',
        'Japan': '日本',
        'Malaysia': '马来西亚',
        'Philippines': '菲律宾',
        'South Korea': '韩国',
    }.get(passport, passport)
    presets = {
        'Japan': {
            "destination_cn": "日本",
            "visa_type": "短期滞在 (旅游)",
            "stay_duration": "15天 / 30天 / 90天",
            "documents": ["护照", "照片", "申请表", "行程单", "资产证明"],
            "notes": "电子签证 (eVISA) 已对部分中国公民开放。"
        },
        'France': {
            "destination_cn": "法国",
            "visa_type": "申根签证 (Type C)",
            "stay_duration": "最长90天 (180天内)",
            "documents": ["护照", "照片", "申请表", "保险", "机票预订", "酒店预订", "银行流水"],
            "notes": "需前往签证中心采集指纹。"
        },
        'Singapore': {
            "destination_cn": "新加坡",
            "visa_type": "电子入境许可 / 以使馆要求为准",
            "stay_duration": "通常可停留30天",
            "documents": ["护照", "回程机票", "酒店预订", "资金证明"],
            "notes": "部分护照可免签或线上申报，请按最新政策确认。"
        },
        'Thailand': {
            "destination_cn": "泰国",
            "visa_type": "旅游签证 / 免签政策以当期要求为准",
            "stay_duration": "通常可停留30天 / 60天",
            "documents": ["护照", "回程机票", "住宿证明", "资金证明"],
            "notes": "入境政策更新较频繁，出行前需再次确认。"
        },
        'Vietnam': {
            "destination_cn": "越南",
            "visa_type": "电子签证 (eVisa)",
            "stay_duration": "通常可停留90天",
            "documents": ["护照", "电子照片", "行程单", "住宿信息"],
            "notes": "多数申请可在线完成，结果通常以电子邮件通知。"
        },
        'UAE': {
            "destination_cn": "阿联酋",
            "visa_type": "电子签或落地签（视护照而定）",
            "stay_duration": "通常可停留30天",
            "documents": ["护照", "行程单", "住宿证明", "保险"],
            "notes": "不同护照的签证要求差异较大，请核对航空公司与使馆指引。"
        },
        'United Arab Emirates': {
            "destination_cn": "阿联酋",
            "visa_type": "电子签或落地签（视护照而定）",
            "stay_duration": "通常可停留30天",
            "documents": ["护照", "行程单", "住宿证明", "保险"],
            "notes": "不同护照的签证要求差异较大，请核对航空公司与使馆指引。"
        },
    }
    preset = presets.get(destination, {
        "destination_cn": destination,
        "visa_type": "需要查询使馆官网",
        "stay_duration": "未知",
        "documents": ["一般需要护照和申请表"],
        "notes": "请咨询相关大使馆。"
    })
    return {
        "destination": destination,
        "destination_cn": preset["destination_cn"],
        "passport": passport,
        "passport_cn": passport_cn,
        "visa_type": preset["visa_type"],
        "stay_duration": preset["stay_duration"],
        "documents": preset["documents"],
        "notes": preset["notes"],
    }


def _compute_hotel_nights(checkin, checkout, fallback=None):
    try:
        if checkin and checkout:
            return max(
                1,
                (
                    datetime.fromisoformat(str(checkout)).date()
                    - datetime.fromisoformat(str(checkin)).date()
                ).days,
            )
    except Exception:
        pass
    try:
        if fallback is not None:
            return max(1, int(fallback))
    except Exception:
        pass
    return 3

def handle_e_travel(task_id, action, payload, env, execute_db_fn):
    # Use sim time instead of system time for consistency where appropriate
    # For now, most legacy E tasks use dt_module.datetime.now(). 
    # We'll use get_sim_time for the new E7 task.
    ts = datetime.now().isoformat()
    sim_ts = get_sim_time(env).isoformat()

    # E7 - Visa Application (Long Haul Trip Step 1)
    if action == 'apply_visa':
        app_id = f"VISA-{random.randint(10000, 99999)}"
        destination = _normalize_city_name(payload.get('destination'), '上海')
        passport_number = payload.get('passport_number')
        long_haul_task = str(task_id or '').startswith('E7-LONG-HAUL')
        
        # Initialize structure in 'gov' key (even if handled by E handler, it affects Gov state)
        if 'gov' not in env: env['gov'] = {}
        if 'visa_applications' not in env['gov']: env['gov']['visa_applications'] = {}

        env = deep_merge(env, {"gov": {"visa_applications": {
            app_id: {
                "destination": destination,
                "passport": passport_number,
                "status": "approved" if long_haul_task else "pending",
                "submitted_at": sim_ts
            },
            "last": {
                "id": app_id,
                "destination": destination,
                "status": "approved" if long_haul_task else "pending"
            }
        }}})
        if long_haul_task:
            env['trip_booked'] = False
        
        try:
            status_value = 'approved' if long_haul_task else 'pending'
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'gov.visa_applications.{app_id}.status', status_value, sim_ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.visa_applications.last.status', status_value, sim_ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['gov.visa_applications.last.destination', destination, sim_ts, task_id, 1.0])
            if long_haul_task:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['trip_booked', 'false', sim_ts, task_id, 1.0])
        except Exception:
            pass

        if long_haul_task:
            return env, {"redirect": f"/trip.local/flights.html?task={task_id}"}
        return env, {"redirect": "/gov.local/visa-apply.html"}

    # E1 - Commute Route Comparison
    if action == 'search_commute_route':
        origin = payload.get('origin')
        destination = payload.get('destination')
        transport_mode = payload.get('transport_mode')

        # BUTTERFLY EFFECT: Calculate costs based on Abstract World Attribute
        location_tier = env.get('world_state', {}).get('location_context', {}).get('tier', 'city_center')
        
        # Base stats (City Center)
        taxi_cost = 35.0
        taxi_time = "20分钟"
        subway_cost = 5.0
        subway_time = "30分钟"
        
        # Logic: If address is Suburban, costs increase significantly
        if location_tier == 'suburban':
            taxi_cost = 120.0
            taxi_time = "50分钟"
            subway_cost = 15.0
            subway_time = "70分钟"

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
                "duration": subway_time, "cost": subway_cost, "details": "直达，早高峰人多"
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
                "duration": taxi_time, "cost": taxi_cost, "details": "最快，费用高"
            }

        env = deep_merge(env, {"commute": {"search_results": results}})
        env = deep_merge(env, {"commute_checked": True})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.origin', origin, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.destination', destination, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.transport_mode', transport_mode, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['commute.last_search.cost', str(taxi_cost), ts, task_id, 1.0])
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
        departure = _normalize_city_name(payload.get('departure'), '北京')
        destination = _normalize_city_name(payload.get('destination'), '上海')
        date = payload.get('date', datetime.now().strftime('%Y-%m-%d'))
        price = float(payload.get('price', 450))
        env = deep_merge(
            env,
            {
                "trip_booked": True,
                "trips": {"flight": {"pnr": pnr, "departure": departure, "destination": destination, "date": date, "price": price}},
            },
        )
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.pnr', pnr, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.departure', departure, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.destination', destination, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/trip.local/manage.html?pnr={pnr}&status=confirmed&date={date}"}

    # E2 - Hotel Booking
    if action == 'book_hotel':
        booking_id = payload.get('bookingId', f"HTL-{random.randint(700,999)}")
        city = _normalize_city_name(payload.get('city', '上海'), '上海')
        checkin = payload.get('checkin', datetime.now().strftime('%Y-%m-%d'))
        checkout = payload.get('checkout')
        nights = _compute_hotel_nights(checkin, checkout, payload.get('nights'))
        env = deep_merge(
            env,
            {
                "trips": {
                    "hotel": {
                        "id": booking_id,
                        "city": city,
                        "checkin": checkin,
                        "checkout": checkout,
                        "nights": nights,
                    }
                }
            },
        )
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.id', booking_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.checkin', checkin, ts, task_id, 1.0])
            if checkout:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['travel.hotel.last.checkout', checkout, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.nights', str(nights), ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/trip.local/manage.html?status=confirmed"}

    # E3 - Airport Transfer
    if action == 'book_airport_transfer':
        method = payload.get('method') # 'self_drive', 'taxi', 'shuttle'
        
        # BUTTERFLY EFFECT: Check Vehicle Condition
        if method == 'self_drive':
            condition = env.get('world_state', {}).get('vehicle_context', {}).get('condition', 'good')
            if condition == 'under_repair' or condition == 'broken':
                return env, {"error": "Cannot self-drive: Vehicle is currently under repair.", "success": False}

        transfer_id = f"TRF-{random.randint(1000,9999)}"
        env = deep_merge(env, {"trips": {"transfer": {"id": transfer_id, "method": method, "status": "booked"}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['trips.transfer.id', transfer_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['trips.transfer.method', method, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['trips.transfer.status', 'booked', ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": "/trip.local/transfer.html?booked=true"}

    # E4 - Visa Requirements Search
    if action == 'search_visa_requirements':
        destination = payload.get('destination_country')
        passport = payload.get('passport_country', 'China')
        visa_info = _get_visa_requirement_result(destination, passport)

        env = deep_merge(env, {"visa": {"last_search_result": visa_info}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['visa.search.last.destination', destination, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['visa.search.last.visa_type', visa_info['visa_type'], ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['visa.search.last.stay_duration', visa_info['stay_duration'], ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: E4 visa search memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/trip.local/visa-requirements.html"}

    # E5 - Expense Report
    if action == 'submit_expense':
        report_id = payload.get('reportId', "EXP-3344")
        total = float(payload.get('total', 1200))
        linked_pnr = payload.get('pnr', env.get('trips', {}).get('flight', {}).get('pnr', 'PNR-UNKNOWN'))
        description_defaults = {
            'E5-2025-EXPENSE': 'Hotel and taxi reimbursement',
            'F2-2025-CONFREG': 'Conference registration and travel',
        }
        description = str(payload.get('description') or description_defaults.get(task_id, '')).strip()
        env = deep_merge(env, {"expenses": {"reports": {report_id: {"state": "submitted", "total": total, "pnr": linked_pnr}}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.id', report_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.total', str(total), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.pnr', str(linked_pnr), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.description', description, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/bank.local/expense-report.html?report={report_id}&task={task_id}"}

    # E6 - Travel Rebooking
    if action == 'rebook_ok':
        import time
        policy = payload.get('policy', 'min-cost')
        new_date = payload.get('new_date', '2025-01-16')
        hist = {"action":"rebook","ts":time.time()}
        env = deep_merge(env, {"trips":{"PNR9ZZ":{"status":"rebooked","history":[hist], "policy": policy, "new_date": new_date}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.rebook.last.policy', policy, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.rebook.last.date', new_date, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.rebook.last.pnr', payload.get('pnr', 'PNR9ZZ'), ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/trip.local/manage/PNR9ZZ.html?status=rebooked&policy={policy}&date={new_date}&task={task_id}"}

    return env, {}
