#!/usr/bin/env python3
"""
Web Agent Dynamic Suite v2 - Backend Server
Provides REST API endpoints for all benchmark tasks.
"""
import http.server, socketserver, json, os, time, sys, sqlite3, urllib.parse, random, hashlib, re
from datetime import datetime, timedelta

# Import task handlers
from task_handlers.utils import deep_merge
from task_handlers.time_utils import advance_time
from task_handlers.world_triggers import process_time_triggers
from task_handlers.a_housing import handle_a_housing
from task_handlers.b_consumption import handle_b_consumption
from task_handlers.c_support import handle_c_support
from task_handlers.d_finance import handle_d_finance
from task_handlers.e_travel import handle_e_travel
from task_handlers.f_work import handle_f_work
from task_handlers.g_health import handle_g_health
from task_handlers.h_government import handle_h_government
from task_handlers.i_repair import handle_i_repair
from task_handlers.j_learning import handle_j_learning
from task_handlers.k_social import handle_k_social
from task_handlers.l_privacy import handle_l_privacy
from task_handlers.m_crisis import handle_m_crisis
from task_handlers.z_advanced import handle_z_advanced

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_DIR = os.path.join(ROOT, 'env')
STATE_PATH = os.path.join(ENV_DIR, 'state.json')
TRACE_PATH = os.path.join(ROOT, 'traces.jsonl')
SITES_DIR = os.path.join(ROOT, 'sites')
DB_PATH = os.path.join(ROOT, 'data.db')

# ============================================================================ 
# Utility Functions
# ============================================================================ 

def load_env():
    """Load environment state from JSON file, initializing if missing"""
    if os.path.exists(STATE_PATH):
        return json.load(open(STATE_PATH, 'r', encoding='utf-8'))
    else:
        return reset_env()

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
    return env

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
        match = re.re.match(r'(\w+)\[(\d+)\]', part)
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
    # Dispatch to appropriate handler based on task family (A, B, C...)
    
    # execute_db is defined below, but will be available at runtime
    db_fn = execute_db 

    # DEBUG Handler
    if task_id == 'DEBUG':
        if action == 'set_state':
            return deep_merge(env, payload), {}

    if task_id.startswith('A'):
        return handle_a_housing(task_id, action, payload, env, db_fn)
    elif task_id.startswith('B'):
        return handle_b_consumption(task_id, action, payload, env, db_fn)
    elif task_id.startswith('C'):
        return handle_c_support(task_id, action, payload, env, db_fn)
    elif task_id.startswith('D'):
        return handle_d_finance(task_id, action, payload, env, db_fn)
    elif task_id.startswith('E'):
        return handle_e_travel(task_id, action, payload, env, db_fn)
    elif task_id.startswith('F'):
        return handle_f_work(task_id, action, payload, env, db_fn)
    elif task_id.startswith('G'):
        return handle_g_health(task_id, action, payload, env, db_fn)
    elif task_id.startswith('H'):
        return handle_h_government(task_id, action, payload, env, db_fn)
    elif task_id.startswith('I'):
        return handle_i_repair(task_id, action, payload, env, db_fn)
    elif task_id.startswith('J'):
        return handle_j_learning(task_id, action, payload, env, db_fn)
    elif task_id.startswith('K'):
        return handle_k_social(task_id, action, payload, env, db_fn)
    elif task_id.startswith('L'):
        return handle_l_privacy(task_id, action, payload, env, db_fn)
    elif task_id.startswith('M'):
        return handle_m_crisis(task_id, action, payload, env, db_fn)
    elif task_id.startswith('Z'):
        return handle_z_advanced(task_id, action, payload, env, db_fn)
    
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

def execute_db(sql, args=[]):
    import time
    for attempt in range(10):
        try:
            with sqlite3.connect(DB_PATH, timeout=30) as conn:
                conn.execute(sql, args)
                conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                time.sleep(0.5)
            else:
                raise e
    print(f"ERROR: Failed to execute DB after 10 attempts: {sql}")

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
                self.send_header('Content-Disposition','attachment; filename="transactions.csv"')
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

        if self.path == '/api/env' or self.path.startswith('/api/env?'):
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
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
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
            # Disabled by user request
            data = json.dumps({
                'success': True,
                'promos': [],
                'cookie_consent_required': False
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

        if self.path.startswith('/api/debug/time_travel'):
            days = int(data.get('days', 0))
            hours = int(data.get('hours', 0))
            
            env = load_env()
            # 1. Advance Time
            env = advance_time(env, days=days, hours=hours)
            
            # Add debug logging for env state before world triggers
            with open("trigger_debug.log", "a") as f:
                f.write(f"DEBUG_SERVER: Env before triggers: {json.dumps(env.get('shop', {}).get('orders', {}))}\n")
            
            # 2. Process World Triggers (Simulate state evolution)
            env = process_time_triggers(env, execute_db)
            save_env(env)
            
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "new_time": env['system_time']}).encode('utf-8')); return

        if '/api/mutate' in self.path:
            try:
                env = load_env()
                env, extra = mutate_env(data.get('task_id',''), data.get('action',''), data.get('payload',{}), env)
                # try:
                #     with open("server_debug.log", "a") as f:
                #         f.write(f"DEBUG_POST_ENV: Final env before save: {json.dumps(env, indent=2)}\n")
                # except Exception: pass
                save_env(env)
                resp = {"ok": True}
                resp.update(extra)
                try:
                    with open("server_debug.log", "a") as f:
                        f.write(f"DEBUG_RESP: {json.dumps(resp)}\n")
                except: pass
                out = json.dumps(resp, ensure_ascii=False).encode('utf-8')
                print(f"DEBUG: do_POST sending response: {resp}") # Added print
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(out)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                try:
                    with open("server_debug.log", "a") as f:
                        f.write(f"ERROR in do_POST /api/mutate: {str(e)}\n{tb}\n")
                    with open("server_error.log", "a") as f:
                        f.write(f"ERROR: {str(e)}\n{tb}\n")
                except: pass
                print(f"ERROR: {str(e)}")
                err_msg = f"Mutate Error: {str(e)}"
                self.send_response(500); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'ok': False, 'error': err_msg}).encode('utf-8'))
            return



        # Flight Search API
        if self.path.startswith('/api/flights/search'):
            departure = data.get('departure', '北京')
            destination = data.get('destination', '上海')
            date = data.get('depart_date', '2025-12-31')
            
            # Mock flights
            flights = [
                {
                    "airline": "Air China",
                    "flight_number": "CA1881",
                    "departure_airport": departure,
                    "destination_airport": destination,
                    "departure_time": "08:00",
                    "arrival_time": "10:15",
                    "price": 450.0
                },
                {
                    "airline": "China Eastern",
                    "flight_number": "MU5102",
                    "departure_airport": departure,
                    "destination_airport": destination,
                    "departure_time": "14:30",
                    "arrival_time": "16:45",
                    "price": 520.0
                }
            ]
            
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'flights': flights}, ensure_ascii=False).encode('utf-8')); return

        # Hotel Search API
        if self.path.startswith('/api/hotels/search'):
            city = data.get('city', '上海')
            checkin = data.get('check_in_date', '2025-12-31')
            checkout = data.get('check_out_date', '2026-01-03')
            
            # Mock hotels
            hotels = [
                {
                    "id": "HTL-001",
                    "name": "浦东香格里拉大酒店",
                    "rating": 5,
                    "city": city,
                    "price": 1200.0
                },
                {
                    "id": "HTL-002",
                    "name": "外滩华尔道夫酒店",
                    "rating": 5,
                    "city": city,
                    "price": 1500.0
                }
            ]
            
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'hotels': hotels}, ensure_ascii=False).encode('utf-8')); return
        
        # Property Search API
        if self.path.startswith('/api/properties/search'):
            location = data.get('location', 'Springfield')
            prop_type = data.get('type', 'apartment')
            
            # Mock properties
            properties = [
                {
                    "id": "PROP-101",
                    "address": "中央大街101号",
                    "location": location,
                    "type": "公寓",
                    "price": 3500
                },
                {
                    "id": "PROP-102",
                    "address": "阳光海岸别墅区20号",
                    "location": location,
                    "type": "独栋别墅",
                    "price": 8000
                }
            ]
            
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'properties': properties}, ensure_ascii=False).encode('utf-8')); return
        
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
            execute_db("INSERT OR REPLACE INTO memory_kv (key, value, ts, source, confidence) VALUES (?, ?, ?, ?, ?)",
                      ['returns.last.state', 'submitted', ts, 'server', 1.0])

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
            # Disabled by user request
            data = json.dumps({
                'success': True,
                'promos': [],
                'cookie_consent_required': False
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