#!/usr/bin/env python3
"""
Web Agent Dynamic Suite v2 - Backend Server
Provides REST API endpoints for all benchmark tasks.
"""
import http.server, socketserver, json, os, time, sys, sqlite3, urllib.parse, random, hashlib, re
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_DIR = os.path.join(ROOT, 'env')
STATE_PATH = os.path.join(ENV_DIR, 'state.json')
TRACE_PATH = os.path.join(ROOT, 'traces.jsonl')
SITES_DIR = os.path.join(ROOT, 'sites')
DB_PATH = os.path.join(ROOT, 'data.db')

# ============================================================================
# Utility Functions
# ============================================================================

def deep_merge(a, b):
    """Deep merge two dictionaries"""
    if isinstance(a, dict) and isinstance(b, dict):
        r = dict(a)
        for k, v in b.items():
            r[k] = deep_merge(r.get(k), v) if k in r else v
        return r
    return b

def load_env():
    """Load environment state from JSON file"""
    return json.load(open(STATE_PATH, 'r', encoding='utf-8')) if os.path.exists(STATE_PATH) else {}

def save_env(env):
    """Save environment state to JSON file"""
    os.makedirs(ENV_DIR, exist_ok=True)
    json.dump(env, open(STATE_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def reset_env():
    """Reset environment to initial state by merging all *_initial.json files"""
    env = {}
    for fn in os.listdir(ENV_DIR):
        if fn.endswith('_initial.json'):
            env = deep_merge(env, json.load(open(os.path.join(ENV_DIR, fn), 'r', encoding='utf-8')))
    save_env(env)

def query_env_path(env, path):
    """
    Query environment state using dot notation path.
    Supports: 'orders.O-10001.state', 'accounts.checking.balance', 'orders.*.state'
    """
    parts = path.split('.')
    current = env

    for i, part in enumerate(parts):
        if current is None:
            return None

        if part == '*':
            # Wildcard: return all values from remaining path
            if isinstance(current, dict):
                remaining_path = '.'.join(parts[i+1:])
                if remaining_path:
                    results = []
                    for key, val in current.items():
                        result = query_env_path(val, remaining_path)
                        if result is not None:
                            results.append(result)
                    return results
                else:
                    return list(current.values())
            elif isinstance(current, list):
                remaining_path = '.'.join(parts[i+1:])
                if remaining_path:
                    return [query_env_path(item, remaining_path) for item in current]
                else:
                    return current
            return None

        # Array index notation: items[0]
        match = re.match(r'(\w+)\[(\d+)\]', part)
        if match:
            key, idx = match.groups()
            if isinstance(current, dict) and key in current:
                current = current[key]
                if isinstance(current, list) and int(idx) < len(current):
                    current = current[int(idx)]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None

    return current

def mutate_env(task_id, action, payload, env):
    # G1 - Doctor appointment booking
    if task_id.startswith('G1') and action == 'book_doctor':
        appt_id = payload.get('appointmentId', 'APT-9001')
        doctor_id = payload.get('doctorId', 'DR-001')
        slot = payload.get('slot', '2025-12-02T09:00')
        env = deep_merge(env, {"health": {"appointments": {"last": {"id": appt_id, "doctor": doctor_id, "slot": slot}}}})
        ts = datetime.now().isoformat()
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.appointment.last_id', appt_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.appointment.slot', slot, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/health.local/index.html"}

    # G2 - Prescription refill
    if task_id.startswith('G2') and action == 'refill_rx':
        rx_id = payload.get('prescriptionId', 'RX-1001')
        medication = payload.get('medication', 'Amoxicillin 250mg')
        prev_refills = env.get('health', {}).get('prescriptions', {}).get(rx_id, {}).get('refills_left', 2)
        refills_left = max(prev_refills - 1, 0)
        refill_ts = datetime.now().isoformat()
        env = deep_merge(env, {"health": {"prescriptions": {rx_id: {"medication": medication, "refills_left": refills_left, "last_refill": refill_ts}}}})
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.rx.last_id', rx_id, refill_ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['health.rx.last_refill', refill_ts, refill_ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/health.local/records.html"}

    # G3 - Medical insurance claim
    if task_id.startswith('G3') and action == 'submit_claim':
        claim_id = payload.get('claimId', 'CLM-5501')
        appt_id = payload.get('appointmentId', 'APT-9001')
        amount = float(payload.get('amount', 250))
        env = deep_merge(env, {"health": {"claims": {claim_id: {"status": "submitted", "appointment_id": appt_id, "amount": amount}}}})
        ts = datetime.now().isoformat()
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['insurance.claim.last.id', claim_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['insurance.claim.last.status', 'submitted', ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/gov.local/applications/status.html?id={claim_id}"}

    # E1 - Flight booking
    if task_id.startswith('E1') and action == 'book_flight':
        pnr = payload.get('pnr', f"PNR-{random.randint(8000, 8999)}")
        destination = payload.get('destination', 'Paris')
        date = payload.get('date', datetime.now().strftime('%Y-%m-%d'))
        price = float(payload.get('price', 450))
        env = deep_merge(env, {"trips": {"flight": {"pnr": pnr, "destination": destination, "date": date, "price": price}}})
        ts = datetime.now().isoformat()
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.pnr', pnr, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.flight.last.destination', destination, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/trip.local/manage.html?pnr={pnr}&status=confirmed&date={date}"}

    # E2 - Hotel booking
    if task_id.startswith('E2') and action == 'book_hotel':
        booking_id = payload.get('bookingId', f"HTL-{random.randint(700,999)}")
        city = payload.get('city', 'Paris')
        checkin = payload.get('checkin', datetime.now().strftime('%Y-%m-%d'))
        nights = int(payload.get('nights', 3))
        env = deep_merge(env, {"trips": {"hotel": {"id": booking_id, "city": city, "checkin": checkin, "nights": nights}}})
        ts = datetime.now().isoformat()
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.id', booking_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['travel.hotel.last.checkin', checkin, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/trip.local/manage.html?status=confirmed"}

    # F2 - Conference registration
    if task_id.startswith('F2') and action == 'conference_register':
        reg_id = payload.get('registrationId', "CONF-8801")
        event_name = payload.get('event', 'AI Summit Paris')
        city = payload.get('city', 'Paris')
        env = deep_merge(env, {"work": {"conference": {"last": {"id": reg_id, "event": event_name, "city": city, "status": "confirmed"}}}})
        ts = datetime.now().isoformat()
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.conference.last.id', reg_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.conference.last.event', event_name, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/event.local/registration.html?state=confirmed"}

    # E5 - Expense report
    if task_id.startswith('E5') and action == 'submit_expense':
        report_id = payload.get('reportId', "EXP-3344")
        total = float(payload.get('total', 1200))
        linked_pnr = payload.get('pnr', env.get('trips', {}).get('flight', {}).get('pnr', 'PNR-UNKNOWN'))
        env = deep_merge(env, {"expenses": {"reports": {report_id: {"state": "submitted", "total": total, "pnr": linked_pnr}}}})
        ts = datetime.now().isoformat()
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.id', report_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['expenses.last.total', str(total), ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/bank.local/expense-report.html?report={report_id}"}

    if task_id.startswith('B6') and action == 'submit_price_protect':
        oid = payload.get('orderId', 'O-98321')
        patch = {"orders": {oid: {"claims": {"price_protect": {"state":"submitted"}}}}}
        return deep_merge(env, patch), {"redirect": "/shop.local/index.html"}
    if task_id.startswith('D4') and action == 'rebind_confirm':
        last4 = payload.get('newLast4', '7777')
        env = deep_merge(env, {"payments":{"cards":{"active_last4": last4}}})
        for m in ["shop.local","ride.local","food.local","stream.local","cloud.local"]:
            env = deep_merge(env, {"payments":{"merchant_bindings":{"map":{m:last4}}}})
        return env, {"redirect": "/pay.local/wallet/cards.html"}
    if task_id.startswith('E6') and action == 'rebook_ok':
        hist = {"action":"rebook","ts":time.time()}
        env = deep_merge(env, {"trips":{"PNR9ZZ":{"status":"rebooked","history":[hist]}}})
        return env, {"redirect": "/trip.local/manage/PNR9ZZ.html"}
    if task_id.startswith('H3') and action == 'book_permit':
        slot = payload.get('slot', '2025-12-01T10:00')
        env = deep_merge(env, {"permits":{"RP-2024-77":{"next_appointment":slot}}})
        return env, {"redirect": "/permit.local/RP-2024-77.html"}
    if task_id.startswith('I5') and action == 'set_energy_plan':
        plan = payload.get('plan','green_offpeak')
        meter = payload.get('meterId','M-321')
        env = deep_merge(env, {"meters":{meter:{"plan":plan}}})
        return env, {"redirect": "/energy.local/plan.html"}
    if task_id.startswith('M1') and action == 'block_card':
        last4 = payload.get('last4','1234')
        env = deep_merge(env, {"payments":{"cards":{last4:{"state":"blocked"}}}})
        env = deep_merge(env, {"merchant_bindings":{"updated":["shop.local","ride.local","food.local","stream.local","cloud.local"]}})
        return env, {"redirect": "/card.local/block.html"}

    # A3 - Utility Setup
    if task_id.startswith('A3') and action == 'setup_utility':
        services = payload.get('services', [])
        plans = payload.get('plans', {})
        addr = payload.get('address', '')
        ts = datetime.now().isoformat()
        
        # Update contracts in env
        contracts = {}
        for svc in services:
            contracts[svc] = {"status": "active", "plan": plans.get(svc, "standard"), "address": addr, "start_date": payload.get('date')}
            # Write to memory
            try:
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'contracts.{svc}.id', f'CTR-{svc.upper()}-{random.randint(1000,9999)}', ts, task_id, 1.0])
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'contracts.{svc}.status', 'active', ts, task_id, 1.0])
            except Exception:
                pass
        
        env = deep_merge(env, {"contracts": contracts})
        return env, {"redirect": "/energy.local/plan.html"}

    # J1 - Course Enrollment
    if task_id.startswith('J1') and action == 'enroll_course':
        course_id = payload.get('courseId', 'DL101')
        ts = datetime.now().isoformat()
        
        env = deep_merge(env, {"courses": {course_id: {"state": "enrolled", "enrolled_at": ts}}})
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'courses.{course_id}.state', 'enrolled', ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/school.local/my-learning.html"}

    # A1 - Find Home
    if task_id.startswith('A1') and action == 'rent_property':
        prop_id = payload.get('propertyId', 'PROP-101')
        term = payload.get('leaseTerm', '12 months')
        ts = datetime.now().isoformat()
        
        env = deep_merge(env, {"housing": {"leases": {prop_id: {"status": "signed", "term": term}}}})
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['housing.lease.last.id', prop_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['housing.lease.last.status', 'signed', ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/housing.local/index.html"}

    # B4 - Food Delivery
    if task_id.startswith('B4') and action == 'order_food':
        order_id = f"ODR-{random.randint(10000, 99999)}"
        restaurant = payload.get('restaurant', 'Unknown')
        items = payload.get('items', [])
        total = payload.get('total', 0.0)
        ts = datetime.now().isoformat()

        env = deep_merge(env, {"food": {"orders": {order_id: {"restaurant": restaurant, "items": items, "total": total, "status": "pending", "ordered_at": ts}}}})
        try:
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['food.order.last.id', order_id, ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['food.order.last.status', 'pending', ts, task_id, 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['food.order.last.total', total, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/food.local/orders.html"}

    return env, {}

# Database helpers
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, args=(), one=False):
    conn = get_db()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cur = conn.execute(query, args)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

def row_to_dict(row):
    if not row:
        return None
    d = dict(row)
    # Add product_id alias for id if this is a product
    if 'id' in d and 'sku' in d and 'price' in d:
        d['product_id'] = d['id']
    return d

class Handler(http.server.SimpleHTTPRequestHandler):
    def send_cors_headers(self):
        """Add CORS headers for cross-origin requests"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def translate_path(self, path):
        parsed = urllib.parse.urlsplit(path)
        path = parsed.path
        if path.startswith('/api/'):
            return http.server.SimpleHTTPRequestHandler.translate_path(self, path)
        base = SITES_DIR
        # Allow directory listing at root by pointing to sites dir directly
        if path == '/':
            return base
        if path == '/transactions':
            path = '/bank.local/transactions.html'
        if path.startswith('/shop.local/order/confirmation/'):
            path = '/shop.local/order.html'
        if path.startswith('/static/'):
            base = os.path.join(SITES_DIR, 'static')
            path = path[len('/static/'):]
        else:
            path = path.lstrip('/')
        full = os.path.join(base, path)
        if not os.path.exists(full):
            html_path = full + '.html'
            if os.path.exists(html_path):
                full = html_path
        if os.path.isdir(full):
            index = os.path.join(full, 'index.html')
            return index if os.path.exists(index) else full  # fall back to listing if no index
        return full

    def do_GET(self):
        print(f"DEBUG: GET {self.path}")
        try:
            with open("server_debug.log", "a") as f:
                f.write(f"GET {self.path}\n")
        except: pass

        # Serve static CSV with attachment header
        if self.path.startswith('/static/transactions.csv'):
            fp = os.path.join(ROOT, 'static', 'transactions.csv')
            if os.path.exists(fp):
                data = open(fp, 'rb').read()
                self.send_response(200)
                self.send_header('Content-Type','text/csv')
                self.send_header('Content-Disposition','attachment; filename=\"transactions.csv\"')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        # Support product detail friendly URL: /shop.local/product/<SKU>
        if self.path.startswith('/shop.local/product/'):
            parts = self.path.split('/')
            sku = parts[3].split('?')[0] if len(parts) >= 4 else ''
            # Serve the product detail HTML while keeping the pretty URL
            self.path = '/shop.local/product.html'

        if '/api/env' in self.path:
            env = load_env()
            # merge latest account balances from DB
            accounts = query_db("SELECT type, balance, currency FROM accounts WHERE user_id = ?", [1])
            env_accounts = env.get('accounts', {})
            for acc in accounts:
                env_accounts[acc['type']] = {
                    'balance': acc['balance'],
                    'currency': acc['currency']
                }
            env['accounts'] = env_accounts
            data = json.dumps(env, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(data); return
        if self.path.startswith('/api/reset'):
            reset_env()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(b'{"ok":true}'); return

        # Products API
        if self.path.startswith('/api/products'):
            parsed = urllib.parse.urlparse(self.path)
            path_parts = parsed.path.split('/')

            # GET /api/products/:id
            if len(path_parts) >= 4:
                identifier = path_parts[3]
                product = None
                if identifier.isdigit():
                    product = query_db("SELECT * FROM products WHERE id = ?", [int(identifier)], one=True)
                else:
                    product = query_db("SELECT * FROM products WHERE sku = ?", [identifier], one=True)
                if product:
                    data = json.dumps({'success': True, 'product': row_to_dict(product)}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                else:
                    data = json.dumps({'success': False, 'error': 'Product not found'}, ensure_ascii=False).encode('utf-8')
                    self.send_response(404)
                self.send_header('Content-Type','application/json; charset=utf-8'); self.end_headers()
                self.wfile.write(data); return

            # GET /api/products?category=...&search=...
            params = urllib.parse.parse_qs(parsed.query)
            category = params.get('category', [None])[0]
            search = params.get('search', [None])[0]
            max_price = params.get('max_price', [None])[0]
            limit = int(params.get('limit', [20])[0])

            query = "SELECT * FROM products WHERE 1=1"
            args = []
            if category:
                query += " AND category = ?"
                args.append(category)
            if search:
                query += " AND (name LIKE ?)"
                args.append(f"%{search}%")
            if max_price:
                query += " AND price <= ?"
                args.append(float(max_price))
            query += f" LIMIT {limit}"

            products = query_db(query, args)
            data = json.dumps({
                'success': True,
                'products': [row_to_dict(p) for p in products],
                'count': len(products)
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(data); return

        # Accounts API
        if self.path.startswith('/api/accounts'):
            accounts = query_db("SELECT * FROM accounts WHERE user_id = ?", [1])
            data = json.dumps({
                'success': True,
                'accounts': [row_to_dict(a) for a in accounts]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(data); return

        # Transactions API
        if self.path.startswith('/api/transactions'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            account_id = int(params.get('account_id', [1])[0])
            days = int(params.get('days', [30])[0])
            tx = query_db("""
                SELECT * FROM transactions
                WHERE account_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT 100
            """, [account_id])
            data = json.dumps({
                'success': True,
                'transactions': [row_to_dict(t) for t in tx]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(data); return

        # Autopay API
        if self.path.startswith('/api/autopay'):
            env = load_env()
            items = []
            for ap_id, info in env.get('autopay', {}).items():
                entry = {'id': ap_id}
                entry.update(info)
                items.append(entry)
            data = json.dumps({'success': True, 'items': items}, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(data); return

        # Orders API
        if self.path.startswith('/api/orders/'):
            path_parts = self.path.split('/')
            if len(path_parts) >= 4:
                order_id = path_parts[3]  # Orders use string IDs like "O-10001"
                order = query_db("SELECT * FROM orders WHERE id = ?", [order_id], one=True)
                if order:
                    items = query_db("""
                        SELECT oi.*, p.name
                        FROM order_items oi
                        JOIN products p ON oi.sku = p.sku
                        WHERE oi.order_id = ?
                    """, [order_id])
                    order_dict = row_to_dict(order)
                    order_dict['items'] = [row_to_dict(item) for item in items]
                    order_dict['order_number'] = order_id
                    data = json.dumps({'success': True, 'order': order_dict}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                else:
                    data = json.dumps({'success': False, 'error': 'Order not found'}, ensure_ascii=False).encode('utf-8')
                    self.send_response(404)
                self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(data); return

        # Orders list API (GET /api/orders)
        if self.path.startswith('/api/orders'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            user_id = int(params.get('user_id', [1])[0])
            limit = int(params.get('limit', [20])[0])
            orders = query_db("""
                SELECT * FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, [user_id, limit])
            orders_list = []
            for order in orders:
                order_dict = row_to_dict(order)
                items = query_db("SELECT oi.*, p.name FROM order_items oi JOIN products p ON oi.sku = p.sku WHERE oi.order_id = ?", [order['id']])
                order_dict['items'] = [row_to_dict(item) for item in items]
                orders_list.append(order_dict)
            data = json.dumps({'success': True, 'orders': orders_list}, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # Bills API
        if self.path.startswith('/api/bills'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            user_id = int(params.get('user_id', [1])[0])
            bills = query_db("SELECT * FROM bills WHERE user_id = ? ORDER BY due_date DESC", [user_id])
            data = json.dumps({
                'success': True,
                'bills': [row_to_dict(b) for b in bills]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # Cards API
        if self.path.startswith('/api/cards'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            user_id = int(params.get('user_id', [1])[0])
            cards = query_db("SELECT * FROM cards WHERE user_id = ?", [user_id])
            data = json.dumps({
                'success': True,
                'cards': [row_to_dict(c) for c in cards]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # Permits API
        if self.path.startswith('/api/permits'):
            parsed = urllib.parse.urlparse(self.path)
            path_parts = parsed.path.split('/')
            params = urllib.parse.parse_qs(parsed.query)

            # GET /api/permits/:id
            if len(path_parts) >= 4:
                permit_id = path_parts[3]
                permit = query_db("SELECT * FROM permits WHERE id = ?", [permit_id], one=True)
                if permit:
                    data = json.dumps({'success': True, 'permit': row_to_dict(permit)}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                else:
                    data = json.dumps({'success': False, 'error': 'Permit not found'}, ensure_ascii=False).encode('utf-8')
                    self.send_response(404)
                self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(data); return

            # GET /api/permits
            user_id = int(params.get('user_id', [1])[0])
            permits = query_db("SELECT * FROM permits WHERE user_id = ?", [user_id])
            data = json.dumps({
                'success': True,
                'permits': [row_to_dict(p) for p in permits]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # Applications API
        if self.path.startswith('/api/applications'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            user_id = int(params.get('user_id', [1])[0])
            apps = query_db("SELECT * FROM applications WHERE user_id = ?", [user_id])
            data = json.dumps({
                'success': True,
                'applications': [row_to_dict(a) for a in apps]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # Returns API
        if self.path.startswith('/api/returns'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            user_id = int(params.get('user_id', [1])[0])
            returns = query_db("SELECT * FROM returns WHERE user_id = ?", [user_id])
            data = json.dumps({
                'success': True,
                'returns': [row_to_dict(r) for r in returns]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # Memory KV API
        if self.path.startswith('/api/memory'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            key = params.get('key', [None])[0]

            if key:
                # Get specific key
                kv = query_db("SELECT * FROM memory_kv WHERE key = ?", [key], one=True)
                if kv:
                    data = json.dumps({'success': True, 'key': kv['key'], 'value': kv['value'], 'ts': kv['ts']}, ensure_ascii=False).encode('utf-8')
                else:
                    data = json.dumps({'success': False, 'error': 'Key not found'}, ensure_ascii=False).encode('utf-8')
            else:
                # Get all keys (with optional pattern)
                pattern = params.get('pattern', ['%'])[0]
                kvs = query_db("SELECT * FROM memory_kv WHERE key LIKE ?", [pattern])
                data = json.dumps({
                    'success': True,
                    'items': [{'key': kv['key'], 'value': kv['value'], 'ts': kv['ts']} for kv in kvs]
                }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # ========================================================================
        # User/Auth API
        # ========================================================================
        if self.path.startswith('/api/users/me') or self.path.startswith('/api/user'):
            # Get current user info (default user_id=1 for demo)
            user = query_db("SELECT id, username, email, created_at FROM users WHERE id = ?", [1], one=True)
            if user:
                # Also get user's memory (preferences, address, etc.)
                memory = {}
                kvs = query_db("SELECT key, value FROM memory_kv WHERE key LIKE 'address.%' OR key LIKE 'payment.%'")
                for kv in kvs:
                    memory[kv['key']] = kv['value']
                user_dict = row_to_dict(user)
                user_dict['memory'] = memory
                data = json.dumps({'success': True, 'user': user_dict}, ensure_ascii=False).encode('utf-8')
            else:
                data = json.dumps({'success': False, 'error': 'User not found'}, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # ========================================================================
        # Appointments API
        # ========================================================================
        if self.path.startswith('/api/appointments'):
            parsed = urllib.parse.urlparse(self.path)
            path_parts = parsed.path.split('/')
            params = urllib.parse.parse_qs(parsed.query)

            # GET /api/appointments/:id
            if len(path_parts) >= 4 and path_parts[3]:
                apt_id = path_parts[3]
                apt = query_db("SELECT * FROM appointments WHERE id = ?", [apt_id], one=True)
                if apt:
                    data = json.dumps({'success': True, 'appointment': row_to_dict(apt)}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                else:
                    data = json.dumps({'success': False, 'error': 'Appointment not found'}, ensure_ascii=False).encode('utf-8')
                    self.send_response(404)
                self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(data); return

            # GET /api/appointments
            user_id = int(params.get('user_id', [1])[0])
            appointments = query_db("SELECT * FROM appointments WHERE user_id = ? ORDER BY date DESC, time DESC", [user_id])
            data = json.dumps({
                'success': True,
                'appointments': [row_to_dict(a) for a in appointments]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # ========================================================================
        # Settlements API (for expense splitting tasks)
        # ========================================================================
        if self.path.startswith('/api/settlements'):
            parsed = urllib.parse.urlparse(self.path)
            path_parts = parsed.path.split('/')
            params = urllib.parse.parse_qs(parsed.query)

            # GET /api/settlements/:id
            if len(path_parts) >= 4 and path_parts[3]:
                settle_id = path_parts[3]
                settlement = query_db("SELECT * FROM settlements WHERE id = ?", [settle_id], one=True)
                if settlement:
                    data = json.dumps({'success': True, 'settlement': row_to_dict(settlement)}, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                else:
                    data = json.dumps({'success': False, 'error': 'Settlement not found'}, ensure_ascii=False).encode('utf-8')
                    self.send_response(404)
                self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(data); return

            # GET /api/settlements
            user_id = int(params.get('user_id', [1])[0])
            period = params.get('period', [None])[0]
            query = "SELECT * FROM settlements WHERE user_id = ?"
            args = [user_id]
            if period:
                query += " AND period = ?"
                args.append(period)
            query += " ORDER BY created_at DESC"
            settlements = query_db(query, args)
            data = json.dumps({
                'success': True,
                'settlements': [row_to_dict(s) for s in settlements]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # ========================================================================
        # Merchant Bindings API
        # ========================================================================
        if self.path.startswith('/api/merchant_bindings'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            user_id = int(params.get('user_id', [1])[0])
            merchant = params.get('merchant', [None])[0]

            query = "SELECT * FROM merchant_bindings WHERE user_id = ?"
            args = [user_id]
            if merchant:
                query += " AND merchant = ?"
                args.append(merchant)

            bindings = query_db(query, args)
            data = json.dumps({
                'success': True,
                'bindings': [row_to_dict(b) for b in bindings]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # ========================================================================
        # Env JSON Path Query API
        # ========================================================================
        if self.path.startswith('/api/env/query'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            path = params.get('path', [None])[0]

            if not path:
                data = json.dumps({'success': False, 'error': 'Missing path parameter'}, ensure_ascii=False).encode('utf-8')
                self.send_response(400)
            else:
                env = load_env()
                result = query_env_path(env, path)
                data = json.dumps({
                    'success': True,
                    'path': path,
                    'value': result
                }, ensure_ascii=False).encode('utf-8')
                self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        # ========================================================================
        # Task Executions API (for monitoring)
        # ========================================================================
        
        # ========================================================================
        # Marketing / Distractors API (Added by AI)
        # ========================================================================
        if self.path.startswith('/api/marketing/promos'):
            promos = [
                {"type": "banner_top", "content": "⚡️ 限时特惠：全场满$500减$50！", "color": "#ef4444"},
                {"type": "popup_center", "content": "订阅简报，立享9折优惠", "delay": 2000},
                {"type": "toast_bottom", "content": "有人刚刚购买了 iPhone 15 Pro", "delay": 5000},
                {"type": "sidebar_ad", "content": "新书上架：《Web Agent 指南》", "img": "book.jpg"}
            ]
            import random
            active_promos = random.sample(promos, k=random.randint(1, 3))
            
            data = json.dumps({
                'success': True,
                'promos': active_promos,
                'cookie_consent_required': True
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        if self.path.startswith('/api/task_executions'):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            task_id = params.get('task_id', [None])[0]
            state = params.get('state', [None])[0]
            limit = int(params.get('limit', [50])[0])

            query = "SELECT * FROM task_executions WHERE 1=1"
            args = []
            if task_id:
                query += " AND task_id = ?"
                args.append(task_id)
            if state:
                query += " AND state = ?"
                args.append(state)
            query += " ORDER BY started_at DESC LIMIT ?"
            args.append(limit)

            executions = query_db(query, args)
            data = json.dumps({
                'success': True,
                'executions': [row_to_dict(e) for e in executions]
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        return super().do_GET()

    def do_POST(self):
        print(f"DEBUG: POST {self.path}")
        try:
            with open("server_debug.log", "a") as f:
                f.write(f"POST {self.path}\n")
        except: pass

        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length) if length>0 else b'{}'
        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = {}

        if '/api/trace' in self.path:
            with open(TRACE_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(b'{"ok":true}'); return

        if self.path.startswith('/api/orders/track'):
            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['orders.tracking.last_check', ts, ts, 'server', 1.0])
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "ts": ts}).encode('utf-8')); return

        if '/api/mutate' in self.path:
            env = load_env()
            env, extra = mutate_env(data.get('task_id',''), data.get('action',''), data.get('payload',{}), env)
            save_env(env)
            resp = {"ok": True}; resp.update(extra)
            out = json.dumps(resp, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(out); return

        if self.path.startswith('/api/autopay'):
            payee = data.get('payee','utilities')
            account_type = data.get('account_type','checking')
            amount = float(data.get('amount',0))
            frequency = data.get('frequency','monthly')
            start_date = data.get('start_date', datetime.now().strftime('%Y-%m-%d'))
            ap_id = f"AP-{random.randint(1000,9999)}"
            env = load_env()
            env.setdefault('autopay', {})[ap_id] = {
                'payee': payee,
                'account_type': account_type,
                'amount': amount,
                'frequency': frequency,
                'next_date': start_date,
                'state': 'active'
            }
            save_env(env)
            ts = datetime.now().isoformat()
            for key, value in [
                ('autopay.utility.id', ap_id),
                ('autopay.utility.status', 'active'),
                ('autopay.utility.next_date', start_date)
            ]:
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [key, value, ts, 'server', 1.0])
            resp = {'success': True, 'autopay': {'id': ap_id, 'state': 'active', 'payee': payee}}
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8')); return

        if self.path.startswith('/api/permits/apply'):
            application_id = f"APP-{random.randint(1000,9999)}"
            env = load_env()
            env.setdefault('permits', {}).setdefault('parking', {})['application_id'] = application_id
            env['permits']['parking']['state'] = 'submitted'
            save_env(env)
            ts = datetime.now().isoformat()
            for key, value in [
                ('permits.parking.application_id', application_id),
                ('permits.parking.state', 'submitted'),
                ('permits.parking.documents_uploaded', 'true')
            ]:
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [key, value, ts, 'server', 1.0])
            resp = {'success': True, 'application_id': application_id}
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8')); return

        if self.path.startswith('/api/cards/activate'):
            new_last4 = data.get('new_last4','7777')
            env = load_env()
            env = deep_merge(env, {"payments":{"cards":{"active_last4": new_last4}}})
            env = deep_merge(env, {"payments":{"cards":{new_last4:{"state":"active","exp_date":"12/2029"}}}})
            for m in ["shop.local","util.local","gov.local"]:
                env = deep_merge(env, {"payments":{"merchant_bindings":{"map":{m:new_last4}}}})
            save_env(env)
            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].last4', new_last4, ts, 'server', 1.0])
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success':True,'exp_date':'12/2029'}).encode('utf-8')); return

        if self.path.startswith('/api/cards/deactivate'):
            last4 = data.get('last4','1234')
            env = load_env()
            env = deep_merge(env, {"payments":{"cards":{last4:{"state":"inactive"}}}})
            save_env(env)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(b'{"success":true}'); return

        if self.path.startswith('/api/merchant_bindings/update'):
            merchant = data.get('merchant','shop.local')
            last4 = data.get('last4','7777')
            env = load_env()
            env = deep_merge(env, {"payments":{"merchant_bindings":{"map":{merchant:last4}}}})
            save_env(env)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(b'{"success":true}'); return

        # Create order
        if self.path.startswith('/api/orders'):
            user_id = data.get('user_id', 1)
            items = data.get('items', [])
            shipping_address = data.get('shipping_address', '')
            shipping_speed = data.get('shipping_speed', 'standard')

            if not items:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'No items'}).encode('utf-8')); return

            # Calculate total and get SKUs
            total = 0
            items_with_sku = []
            for item in items:
                # Get product by id to find sku and price
                product = query_db("SELECT id, sku, price FROM products WHERE id = ?", [item['product_id']], one=True)
                if product:
                    total += product['price'] * item['quantity']
                    items_with_sku.append({
                        'sku': product['sku'],
                        'quantity': item['quantity'],
                        'price': product['price']
                    })

            # Generate order ID
            order_number = random.randint(10001, 99999)
            order_id = f'O-{order_number:05d}'

            # Create order
            execute_db(
                "INSERT INTO orders (id, user_id, total, state, shipping_speed, shipping_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [order_id, user_id, round(total, 2), 'confirmed', shipping_speed, shipping_address, datetime.now().isoformat()]
            )

            # Create order items
            for item in items_with_sku:
                execute_db(
                    "INSERT INTO order_items (order_id, sku, quantity, price) VALUES (?, ?, ?, ?)",
                    [order_id, item['sku'], item['quantity'], item['price']]
                )

            # Update memory
            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['orders.last.id', order_id, ts, 'server', 1.0])
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['orders.last.total', str(round(total, 2)), ts, 'server', 1.0])

            result = {'success': True, 'order_id': order_id, 'order_number': order_id, 'total': round(total, 2)}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # Create return
        if self.path.startswith('/api/returns'):
            order_id = data.get('order_id', '')
            user_id = data.get('user_id', 1)
            reason = data.get('reason', 'other')

            if not order_id:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing order_id'}).encode('utf-8')); return

            # Verify order exists
            order = query_db("SELECT * FROM orders WHERE id = ?", [order_id], one=True)
            if not order:
                self.send_response(404); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Order not found'}).encode('utf-8')); return

            # Generate return ID
            return_number = random.randint(50001, 59999)
            return_id = f'R-{return_number:05d}'

            # Create return
            execute_db(
                "INSERT INTO returns (id, order_id, user_id, reason, state, refund_amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [return_id, order_id, user_id, reason, 'submitted', order['total'], datetime.now().isoformat()]
            )

            # Update memory
            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['returns.last.id', return_id, ts, 'server', 1.0])

            result = {'success': True, 'return_id': return_id, 'state': 'submitted'}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # Memory KV write
        if self.path.startswith('/api/memory'):
            key = data.get('key', '')
            value = data.get('value', '')
            source = data.get('source', 'user')

            if not key:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing key'}).encode('utf-8')); return

            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      [key, str(value), ts, source, 1.0])

            result = {'success': True, 'key': key, 'value': value}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # ========================================================================
        # Appointments POST - Create new appointment
        # ========================================================================
        if self.path.startswith('/api/appointments'):
            user_id = data.get('user_id', 1)
            application_id = data.get('application_id')
            date = data.get('date')
            time = data.get('time')

            if not date or not time:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing date or time'}).encode('utf-8')); return

            apt_id = f"APT-{random.randint(1000,9999)}"
            execute_db(
                "INSERT INTO appointments (id, application_id, user_id, date, time, state) VALUES (?, ?, ?, ?, ?, ?)",
                [apt_id, application_id, user_id, date, time, 'booked']
            )

            # Update memory
            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['appointments.last.id', apt_id, ts, 'server', 1.0])

            result = {'success': True, 'appointment_id': apt_id, 'date': date, 'time': time, 'state': 'booked'}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # ========================================================================
        # Settlements POST - Create expense settlement
        # ========================================================================
        if self.path.startswith('/api/settlements'):
            user_id = data.get('user_id', 1)
            period = data.get('period')
            members = data.get('members', [])
            total_amount = float(data.get('total_amount', 0))

            if not period:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing period'}).encode('utf-8')); return

            settle_id = f"SETTLE-{period}"
            execute_db(
                "INSERT INTO settlements (id, user_id, period, members, total_amount, state) VALUES (?, ?, ?, ?, ?, ?)",
                [settle_id, user_id, period, json.dumps(members), total_amount, 'pending']
            )

            # Update memory
            ts = datetime.now().isoformat()
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['settlements.last.id', settle_id, ts, 'server', 1.0])

            result = {'success': True, 'settlement_id': settle_id, 'total_amount': total_amount, 'state': 'pending'}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # ========================================================================
        # Bills POST - Pay bill
        # ========================================================================
        if self.path.startswith('/api/bills/pay'):
            bill_id = data.get('bill_id')
            account_id = data.get('account_id', 1)

            if not bill_id:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing bill_id'}).encode('utf-8')); return

            # Check bill exists
            bill = query_db("SELECT * FROM bills WHERE id = ?", [bill_id], one=True)
            if not bill:
                self.send_response(404); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Bill not found'}).encode('utf-8')); return

            # Update bill status
            execute_db("UPDATE bills SET state = 'paid', paid_at = ? WHERE id = ?", [datetime.now().isoformat(), bill_id])

            # Create transaction
            execute_db(
                "INSERT INTO transactions (account_id, amount, type, description) VALUES (?, ?, ?, ?)",
                [account_id, -bill['amount'], 'debit', f"Bill payment: {bill['type']}"]
            )

            # Update account balance
            execute_db("UPDATE accounts SET balance = balance - ? WHERE id = ?", [bill['amount'], account_id])

            result = {'success': True, 'bill_id': bill_id, 'amount': bill['amount'], 'state': 'paid'}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # ========================================================================
        # Task Execution POST - Start task execution
        # ========================================================================
        
        # ========================================================================
        # Marketing / Distractors API (Added by AI)
        # ========================================================================
        if self.path.startswith('/api/marketing/promos'):
            promos = [
                {"type": "banner_top", "content": "⚡️ 限时特惠：全场满$500减$50！", "color": "#ef4444"},
                {"type": "popup_center", "content": "订阅简报，立享9折优惠", "delay": 2000},
                {"type": "toast_bottom", "content": "有人刚刚购买了 iPhone 15 Pro", "delay": 5000},
                {"type": "sidebar_ad", "content": "新书上架：《Web Agent 指南》", "img": "book.jpg"}
            ]
            import random
            active_promos = random.sample(promos, k=random.randint(1, 3))
            
            data = json.dumps({
                'success': True,
                'promos': active_promos,
                'cookie_consent_required': True
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

        if self.path.startswith('/api/task_executions'):
            task_id = data.get('task_id', '')
            agent_version = data.get('agent_version', 'unknown')
            steps_total = data.get('steps_total', 0)

            if not task_id:
                self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Missing task_id'}).encode('utf-8')); return

            exec_id = execute_db(
                "INSERT INTO task_executions (task_id, agent_version, state, steps_total) VALUES (?, ?, ?, ?)",
                [task_id, agent_version, 'running', steps_total]
            )

            result = {'success': True, 'execution_id': exec_id, 'task_id': task_id, 'state': 'running'}
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        self.send_response(404); self.send_cors_headers(); self.end_headers()

    def do_PUT(self):
        """Handle PUT requests for updating resources"""
        length = int(self.headers.get('Content-Length','0'))
        body = self.rfile.read(length) if length>0 else b'{}'
        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = {}

        # ========================================================================
        # Orders PUT - Update order status
        # ========================================================================
        if self.path.startswith('/api/orders/'):
            path_parts = self.path.split('/')
            if len(path_parts) >= 4:
                order_id = path_parts[3].split('?')[0]
                state = data.get('state')
                shipping_speed = data.get('shipping_speed')

                if not state and not shipping_speed:
                    self.send_response(400); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'No update fields provided'}).encode('utf-8')); return

                # Build update query
                updates = []
                args = []
                if state:
                    updates.append("state = ?")
                    args.append(state)
                if shipping_speed:
                    updates.append("shipping_speed = ?")
                    args.append(shipping_speed)

                args.append(order_id)
                query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
                execute_db(query, args)

                result = {'success': True, 'order_id': order_id}
                if state:
                    result['state'] = state
                if shipping_speed:
                    result['shipping_speed'] = shipping_speed

                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # ========================================================================
        # Task Executions PUT - Update execution status
        # ========================================================================
        if self.path.startswith('/api/task_executions/'):
            path_parts = self.path.split('/')
            if len(path_parts) >= 4:
                exec_id = int(path_parts[3].split('?')[0])
                state = data.get('state')
                steps_completed = data.get('steps_completed')
                error_type = data.get('error_type')
                error_message = data.get('error_message')

                updates = []
                args = []

                if state:
                    updates.append("state = ?")
                    args.append(state)
                    if state in ['completed', 'failed', 'aborted']:
                        updates.append("completed_at = ?")
                        args.append(datetime.now().isoformat())

                if steps_completed is not None:
                    updates.append("steps_completed = ?")
                    args.append(steps_completed)

                if error_type:
                    updates.append("error_type = ?")
                    args.append(error_type)

                if error_message:
                    updates.append("error_message = ?")
                    args.append(error_message)

                if updates:
                    args.append(exec_id)
                    query = f"UPDATE task_executions SET {', '.join(updates)} WHERE id = ?"
                    execute_db(query, args)

                result = {'success': True, 'execution_id': exec_id}
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        # ========================================================================
        # Appointments PUT - Update appointment
        # ========================================================================
        if self.path.startswith('/api/appointments/'):
            path_parts = self.path.split('/')
            if len(path_parts) >= 4:
                apt_id = path_parts[3].split('?')[0]
                state = data.get('state')
                date = data.get('date')
                time = data.get('time')

                updates = []
                args = []
                if state:
                    updates.append("state = ?")
                    args.append(state)
                if date:
                    updates.append("date = ?")
                    args.append(date)
                if time:
                    updates.append("time = ?")
                    args.append(time)

                if updates:
                    args.append(apt_id)
                    query = f"UPDATE appointments SET {', '.join(updates)} WHERE id = ?"
                    execute_db(query, args)

                result = {'success': True, 'appointment_id': apt_id}
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        self.send_response(404); self.send_cors_headers(); self.end_headers()

    def do_DELETE(self):
        """Handle DELETE requests for removing resources"""
        # ========================================================================
        # Memory KV DELETE
        # ========================================================================
        if self.path.startswith('/api/memory/'):
            path_parts = self.path.split('/')
            if len(path_parts) >= 4:
                key = urllib.parse.unquote(path_parts[3])
                execute_db("DELETE FROM memory_kv WHERE key = ?", [key])
                result = {'success': True, 'key': key}
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8')); return

        self.send_response(404); self.send_cors_headers(); self.end_headers()

def main(port=8000):
    os.chdir(ROOT)
    if not os.path.exists(STATE_PATH):
        reset_env()
    class ThreadingHTTPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    print(f"Serving HTTP on port {port}...")
    with socketserver.TCPServer(('', port), Handler) as httpd:
        httpd.serve_forever()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv)>1 else 8000
    main(port)
