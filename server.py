import http.server
import socketserver
import json
import os
import urllib.parse
import sqlite3
import random
import time
import re
from datetime import datetime
from pathlib import Path
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
from task_handlers.time_utils import advance_time, get_sim_time
from task_handlers.world_triggers import process_time_triggers
from task_handlers.utils import deep_merge
from runtime_paths import db_path, env_dir, sites_dir, server_port

ROOT = str(Path(__file__).resolve().parent)
ENV_DIR = str(env_dir())
STATE_PATH = str(env_dir() / 'state.json')
SITES_DIR = str(sites_dir())
DB_PATH = str(db_path())

def load_env():
    if os.path.exists(STATE_PATH):
        return json.load(open(STATE_PATH, 'r', encoding='utf-8'))
    return reset_env()

def save_env(env):
    os.makedirs(ENV_DIR, exist_ok=True)
    json.dump(env, open(STATE_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def reset_env():
    env = {}
    for fn in os.listdir(ENV_DIR):
        if fn.endswith('_initial.json'):
            with open(os.path.join(ENV_DIR, fn)) as f:
                data = json.load(f)
                env = deep_merge(env, data)
    # SEED DATA
    housing_data = [{"id": f"PROP-EXT-{i}", "title": f"Apartment {100+i}", "price": 1000 + (i * 150), "meta": f"BR | {40 + i*10}sqm"} for i in range(20)]
    if 'housing' not in env: env['housing'] = {}
    env['housing']['properties'] = housing_data
    save_env(env)
    return env

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(sql, args=[]):
    with sqlite3.connect(DB_PATH, timeout=60) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(sql, args)
        conn.commit()

def row_to_dict(row):
    return dict(row) if row else None


def merge_shop_order_map(order_map, env_orders):
    if not isinstance(env_orders, dict):
        return order_map

    for key, value in env_orders.items():
        # `shop.orders.last` is a convenience pointer, not a real order record.
        # Treating it as an order drops fields like `date` and can reorder the
        # latest delivered order behind older confirmed ones.
        if key == "last":
            continue
        if not isinstance(value, dict) or not value.get("id"):
            continue

        env_order = dict(value)
        if not isinstance(env_order.get("items"), list):
            env_order["items"] = []
        if "total" in env_order:
            try:
                env_order["total"] = float(env_order.get("total") or 0.0)
            except Exception:
                env_order["total"] = 0.0
        env_order.setdefault("state", "pending")
        env_order.setdefault("shipping_speed", "standard")
        env_order.setdefault("shipping_address", "")

        existing = dict(order_map.get(env_order["id"], {}))
        merged = dict(existing)
        for field, field_value in env_order.items():
            if field_value not in (None, "", []):
                merged[field] = field_value
        if existing.get("date") and not merged.get("date"):
            merged["date"] = existing["date"]

        order_map[env_order["id"]] = merged
    return order_map


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class Handler(http.server.SimpleHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200); self.send_cors_headers(); self.end_headers()

    def normalized_api_path(self):
        parsed = urllib.parse.urlsplit(self.path)
        route_path = parsed.path
        if route_path.startswith('/api/'):
            normalized = route_path
        else:
            m = re.match(r'^/[^/]+\.local(/api/.*)$', route_path)
            if not m:
                return None
            normalized = m.group(1)
        if parsed.query:
            return f"{normalized}?{parsed.query}"
        return normalized

    def translate_path(self, path):
        parsed = urllib.parse.urlsplit(path)
        p = parsed.path
        if p.startswith('/api/'): return super().translate_path(p)
        if p.startswith('/shop.local/order/confirmation/'):
            return os.path.join(SITES_DIR, 'shop.local', 'order.html')
        base = SITES_DIR
        if p == '/': return base
        if p.startswith('/static/'): 
            base = os.path.join(SITES_DIR, 'static')
            p = p[len('/static/'):]
        else: p = p.lstrip('/')
        full = os.path.join(base, p)
        if not os.path.exists(full) and not full.endswith('.html'):
            if os.path.exists(full + '.html'): full += '.html'
        return full

    def do_GET(self):
        api_path = self.normalized_api_path()
        full_path = self.translate_path(self.path)
        if api_path and api_path.startswith('/api/env'):
            env = load_env()
            try:
                accounts = query_db("SELECT balance FROM accounts WHERE user_id = 1")
                env['balance'] = sum(acc['balance'] for acc in accounts)
            except: pass
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps(env).encode('utf-8')); return

        if api_path and api_path.startswith('/api/products'):
            route_path = urllib.parse.urlsplit(api_path).path
            if route_path == '/api/products':
                products = query_db("SELECT * FROM products")
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success':True, 'products':[row_to_dict(p) for p in products]}).encode('utf-8')); return
            if route_path.startswith('/api/products/'):
                sku = urllib.parse.unquote(route_path.split('/api/products/', 1)[1])
                product = query_db("SELECT * FROM products WHERE sku = ?", (sku,), one=True)
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                if product:
                    self.wfile.write(json.dumps({'success': True, 'product': row_to_dict(product)}).encode('utf-8')); return
                self.wfile.write(json.dumps({'success': False, 'error': 'Product not found'}).encode('utf-8')); return

        if api_path and api_path.startswith('/api/orders'):
            env = load_env()
            orders = env.get('shop', {}).get('orders', {})
            parsed = urllib.parse.urlsplit(api_path)
            route_path = parsed.path
            if route_path == '/api/orders':
                order_map = {}
                db_orders = query_db("SELECT id, total, state, shipping_speed, shipping_address, created_at FROM orders ORDER BY created_at DESC")
                for order in db_orders:
                    order_dict = row_to_dict(order)
                    item_rows = query_db(
                        """
                        SELECT oi.sku, oi.quantity, oi.price, p.name, p.category
                        FROM order_items oi
                        LEFT JOIN products p ON p.sku = oi.sku
                        WHERE oi.order_id = ?
                        """,
                        (order_dict["id"],),
                    )
                    order_dict["date"] = order_dict.pop("created_at", "")
                    order_dict["items"] = [
                        {
                            "id": item["sku"],
                            "name": item["name"] or item["sku"],
                            "category": item["category"] or "default",
                            "quantity": item["quantity"],
                            "price": item["price"],
                        }
                        for item in item_rows
                    ]
                    order_map[order_dict["id"]] = order_dict
                order_map = merge_shop_order_map(order_map, orders)
                order_list = sorted(order_map.values(), key=lambda o: str(o.get("date", "")), reverse=True)
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'orders': order_list}).encode('utf-8')); return
            if route_path.startswith('/api/orders/'):
                order_id = urllib.parse.unquote(route_path.split('/api/orders/', 1)[1])
                order = orders.get(order_id)
                if not order:
                    db_order = query_db("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
                    if db_order:
                        order = row_to_dict(db_order)
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                if order:
                    self.wfile.write(json.dumps({'success': True, 'order': order}).encode('utf-8')); return
                self.wfile.write(json.dumps({'success': False, 'error': 'Order not found'}).encode('utf-8')); return

        if api_path and api_path.startswith('/api/cards'):
            cards = query_db("SELECT * FROM cards WHERE user_id = 1")
            env = load_env()
            env_cards = env.get("payments", {}).get("cards", {})
            merged = [row_to_dict(c) for c in cards]
            existing_last4 = {str(c.get("last4")) for c in merged}
            for last4, payload in env_cards.items():
                if last4 == "active_last4" or str(last4) in existing_last4 or not isinstance(payload, dict):
                    continue
                merged.append({
                    "user_id": 1,
                    "type": payload.get("type", "physical"),
                    "last4": str(last4),
                    "state": payload.get("state", payload.get("status", "active")),
                    "status": payload.get("status", payload.get("state", "active")),
                })
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success':True, 'cards':merged}).encode('utf-8')); return

        if api_path and api_path.startswith('/api/messages'):
            env = load_env()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success':True, 'messages':env.get('mobile',{}).get('messages',[])}).encode('utf-8')); return

        if api_path and api_path.startswith('/api/bills'):
            env = load_env()
            bills = env.get('gov', {}).get('bills')
            if not bills:
                bills = [
                    {
                        "id": "BILL-EL-2025-12",
                        "type": "electricity",
                        "amount": 188.50,
                        "state": "pending",
                        "period_start": "2025-11-01",
                        "period_end": "2025-11-30",
                        "due_date": "2025-12-20",
                    },
                    {
                        "id": "BILL-WA-2025-12",
                        "type": "water",
                        "amount": 72.30,
                        "state": "pending",
                        "period_start": "2025-11-01",
                        "period_end": "2025-11-30",
                        "due_date": "2025-12-22",
                    },
                    {
                        "id": "BILL-GA-2025-11",
                        "type": "gas",
                        "amount": 95.00,
                        "state": "paid",
                        "period_start": "2025-10-01",
                        "period_end": "2025-10-31",
                        "due_date": "2025-11-20",
                    },
                ]
                env.setdefault('gov', {})['bills'] = bills
                save_env(env)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success':True, 'bills': bills}).encode('utf-8')); return

        if os.path.exists(full_path) and full_path.endswith('.html'):
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            is_clean = (os.environ.get("BENCHMARK_CLEAN_MODE") == "true" or "clean=true" in self.path)
            if not is_clean: content = self.inject_distractors(content)
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(content.encode('utf-8')); return
        return super().do_GET()

    def inject_distractors(self, html):
        distractor = """
        <div id="d-blocker" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;background:rgba(255,255,255,0.9);display:none;align-items:center;justify-content:center;pointer-events:all;">
          <div style="background:white;padding:40px;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,0.2);text-align:center;max-width:400px;">
            <h2 style="color:#1e293b;margin-top:0;">📣 Security Notice</h2>
            <p style="color:#64748b;">Verify session to continue.</p>
            <button onclick="document.getElementById('d-blocker').style.display='none';document.body.style.overflow='auto';" 
                    style="background:#3b82f6;color:white;padding:12px 30px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">Confirm</button>
          </div>
        </div>
        <script>
        (function(){
          const params = new URLSearchParams(window.location.search);
          const level = (params.get('dlevel') || 'medium').toLowerCase();
          const levelProb = { off: 0.0, low: 0.25, medium: 0.5, high: 0.8 };
          const probability = Object.prototype.hasOwnProperty.call(levelProb, level) ? levelProb[level] : 0.5;
          const seedRaw = params.get('dseed') || '';

          function seeded01(input) {
            let h = 2166136261 >>> 0;
            for (let i = 0; i < input.length; i++) {
              h ^= input.charCodeAt(i);
              h = Math.imul(h, 16777619);
            }
            return (h >>> 0) / 4294967296;
          }

          const key = seedRaw ? (seedRaw + '|' + location.pathname + '|' + location.search) : '';
          const roll = key ? seeded01(key) : Math.random();

          setTimeout(() => {
            const blocker = document.getElementById('d-blocker');
            if (blocker && roll < probability) {
              blocker.style.display = 'flex';
              document.body.style.overflow = 'hidden';
            }
          }, 1000);
        })();
        </script>
        """
        return html.replace("</body>", distractor + "</body>")

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        api_path = self.normalized_api_path() or self.path
        route_path = urllib.parse.urlsplit(api_path).path
        if route_path == '/api/bills/pay':
            env = load_env()
            bill_id = data.get('bill_id')
            bills = env.setdefault('gov', {}).setdefault('bills', [])
            found = False
            for bill in bills:
                if bill.get('id') == bill_id:
                    bill['state'] = 'paid'
                    found = True
                    break
            save_env(env)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'success': found}).encode('utf-8'))
            return

        if route_path == '/api/memory':
            key = data.get('key')
            value = data.get('value')
            source = data.get('source', 'ui')
            ts = datetime.utcnow().isoformat() + "Z"
            if key is not None:
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [str(key), str(value), ts, source, 1.0])
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
            return

        if route_path == '/api/flights/search':
            departure = data.get('departure', '北京')
            destination = data.get('destination', '上海')
            flights = [
                {
                    "airline": "CA",
                    "flight_number": "CA1881",
                    "departure_airport": departure,
                    "destination_airport": destination,
                    "departure_time": "08:30",
                    "arrival_time": "10:45",
                    "price": 980.0,
                },
                {
                    "airline": "MU",
                    "flight_number": "MU5102",
                    "departure_airport": departure,
                    "destination_airport": destination,
                    "departure_time": "11:20",
                    "arrival_time": "13:40",
                    "price": 860.0,
                },
            ]
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "flights": flights}).encode('utf-8'))
            return

        if route_path == '/api/hotels/search':
            city = data.get('city', '上海')
            hotels = [
                {
                    "id": "HTL-PD-001",
                    "name": "浦东香格里拉大酒店",
                    "rating": "4.8",
                    "city": city,
                    "price": 1180.0,
                },
                {
                    "id": "HTL-PD-002",
                    "name": "外滩假日酒店",
                    "rating": "4.6",
                    "city": city,
                    "price": 860.0,
                },
            ]
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({"success": True, "hotels": hotels}).encode('utf-8'))
            return

        if route_path == '/api/debug/time_travel':
            env = load_env()
            days = int(data.get('days', 0) or 0)
            hours = int(data.get('hours', 0) or 0)
            env = advance_time(env, days=days, hours=hours)
            env = process_time_triggers(env, execute_db)
            save_env(env)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "system_time": env.get("system_time"),
                "applied": {"days": days, "hours": hours}
            }).encode('utf-8'))
            return

        if route_path == '/api/mutate':
            env = load_env()
            task_id, action, payload = data.get('task_id',''), data.get('action',''), data.get('payload',{})

            # Benchmark helper: allow direct state injection for flow setup.
            if action == 'set_state':
                if isinstance(payload, dict):
                    ts = datetime.now().isoformat()
                    source = task_id or "DEBUG"

                    def _mem_set(key, value):
                        try:
                            execute_db(
                                "INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                [str(key), str(value), ts, source, 1.0],
                            )
                        except Exception:
                            pass

                    env = deep_merge(env, payload)

                    if 'card_frozen' in payload:
                        frozen = bool(payload.get('card_frozen'))
                        last4 = str(
                            payload.get('card_last4')
                            or payload.get('last4')
                            or '7777'
                        )
                        card_state = 'blocked' if frozen else 'active'
                        env = deep_merge(env, {
                            "payments": {"cards": {last4: {"state": card_state}}},
                            "world_state": {"financial_context": {"liquidity": "frozen" if frozen else "active"}},
                        })
                        _mem_set("payment.cards[0].state", card_state)
                        _mem_set(f"payments.cards.{last4}.state", card_state)
                        try:
                            execute_db("UPDATE cards SET state = ? WHERE user_id = 1 AND last4 = ?", [card_state, last4])
                        except Exception:
                            pass

                    if 'pending_order' in payload:
                        pending = bool(payload.get('pending_order'))
                        food_status = "pending" if pending else "delivered"
                        shop_state = "confirmed" if pending else "delivered"
                        env = deep_merge(env, {
                            "food": {"order": {"last": {"status": food_status}}},
                            "shop": {"orders": {"last": {"id": "CF-ORDER", "state": shop_state, "total": 29.99}}},
                        })
                        _mem_set("food.order.last.status", food_status)
                        _mem_set("shop.orders.last.state", shop_state)
                        _mem_set("pending_order", "true" if pending else "false")
                        _mem_set("has_shop_delivered", "false" if pending else "true")

                    if 'has_sub' in payload:
                        enabled = bool(payload.get('has_sub'))
                        sub_status = "active" if enabled else "inactive"
                        subs = env.get("food", {}).get("subscriptions", {})
                        if not isinstance(subs, dict):
                            subs = {}
                        for sid, item in list(subs.items()):
                            if isinstance(item, dict):
                                item["status"] = sub_status
                                subs[sid] = item
                        subs["last"] = {"id": "CF-SUB", "status": sub_status}
                        env = deep_merge(env, {"food": {"subscriptions": subs}})
                        legacy_subs = env.get("subscriptions", {})
                        if isinstance(legacy_subs, dict):
                            for sid, item in list(legacy_subs.items()):
                                if isinstance(item, dict):
                                    item["status"] = sub_status
                                    legacy_subs[sid] = item
                            env = deep_merge(env, {"subscriptions": legacy_subs})
                        _mem_set("food.subscriptions.last.status", sub_status)
                        _mem_set("has_sub", "true" if enabled else "false")

                    if 'has_shop_delivered' in payload:
                        delivered = bool(payload.get('has_shop_delivered'))
                        st = "delivered" if delivered else "confirmed"
                        env = deep_merge(env, {"shop": {"orders": {"last": {"id": "CF-ORDER", "state": st, "total": 29.99}}}})
                        _mem_set("shop.orders.last.state", st)
                        _mem_set("has_shop_delivered", "true" if delivered else "false")

                    if 'has_invest' in payload:
                        enabled = bool(payload.get('has_invest'))
                        inv_status = "active" if enabled else "inactive"
                        accs = env.get("finance", {}).get("investment_accounts", {})
                        if not isinstance(accs, dict):
                            accs = {}
                        for aid, item in list(accs.items()):
                            if isinstance(item, dict):
                                item["status"] = inv_status
                                accs[aid] = item
                        accs["last"] = {"id": "CF-INV", "status": inv_status}
                        env = deep_merge(env, {"finance": {"investment_accounts": accs}})
                        _mem_set("finance.investment_accounts.last.status", inv_status)
                        _mem_set("has_invest", "true" if enabled else "false")

                    if 'has_home' in payload:
                        has_home = bool(payload.get('has_home'))
                        env = deep_merge(env, {"has_home": has_home})
                        _mem_set("has_home", "true" if has_home else "false")

                    if 'has_bank' in payload:
                        has_bank = bool(payload.get('has_bank'))
                        env = deep_merge(env, {"has_bank": has_bank})
                        _mem_set("has_bank", "true" if has_bank else "false")

                    if 'has_mobile' in payload:
                        has_mobile = bool(payload.get('has_mobile'))
                        env = deep_merge(env, {"has_mobile": has_mobile})
                        _mem_set("has_mobile", "true" if has_mobile else "false")

                    if 'has_utility' in payload:
                        has_utility = bool(payload.get('has_utility'))
                        env = deep_merge(env, {"has_utility": has_utility})
                        _mem_set("has_utility", "true" if has_utility else "false")

                    if 'certified' in payload:
                        cert = bool(payload.get('certified'))
                        env = deep_merge(env, {"world_state": {"skills": {"certified": cert}}})
                        _mem_set("world_state.skills.certified", "True" if cert else "False")

                    if 'energy_cost' in payload:
                        projected = "high" if str(payload.get('energy_cost')).strip().lower() == "high" else "low"
                        env = deep_merge(env, {"world_state": {"energy_context": {"projected_cost": projected}}})
                        _mem_set("energy_cost", projected)

                    if 'is_sick' in payload:
                        sick = bool(payload.get('is_sick'))
                        env = deep_merge(env, {
                            "world_state": {
                                "health_context": {"current_status": "ill" if sick else "healthy"},
                                "physical_context": {"status": "impaired" if sick else "normal", "energy_level": 20 if sick else 100},
                            }
                        })
                        _mem_set("is_sick", "true" if sick else "false")

                    if 'location' in payload:
                        loc = str(payload.get('location') or '').strip().lower()
                        tier = 'suburban' if loc == 'suburb' else 'city_center'
                        env = deep_merge(env, {"world_state": {"location_context": {"tier": tier}}})
                        _mem_set("location", loc or "city")

                    if 'commute_checked' in payload:
                        checked = bool(payload.get('commute_checked'))
                        if checked:
                            tier = env.get('world_state', {}).get('location_context', {}).get('tier', 'city_center')
                            commute_cost = 120.0 if tier == 'suburban' else 35.0
                            env = deep_merge(env, {"commute": {"last_search": {"cost": commute_cost}}})
                            _mem_set("commute.last_search.cost", commute_cost)
                        else:
                            env = deep_merge(env, {"commute": {"search_results": {}, "last_search": {}}})
                        _mem_set("commute_checked", "true" if checked else "false")

                    if 'trip_booked' in payload:
                        trip_booked = bool(payload.get('trip_booked'))
                        env = deep_merge(env, {"trip_booked": trip_booked})
                        _mem_set("trip_booked", "true" if trip_booked else "false")

                save_env(env)
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "injected": True}).encode('utf-8'))
                return
            
            # --- 核心路由重构：全处理器尝试 ---
            handlers = [handle_a_housing, handle_b_consumption, handle_c_support, handle_d_finance, handle_e_travel, handle_f_work, handle_g_health, handle_h_government, handle_i_repair, handle_j_learning, handle_k_social, handle_l_privacy, handle_m_crisis, handle_z_advanced]
            
            final_extra = {}
            action_found = False
            for handler in handlers:
                new_env, extra = handler(task_id, action, payload, env, execute_db)
                if extra or new_env != env: # 处理器产生了变化
                    env = new_env
                    final_extra.update(extra)
                    action_found = True
                    # 如果处理器明确表示处理了该 action，可以提前退出，或者为了蝴蝶效应继续遍历
            
            save_env(env)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
            resp = {"ok":True}; resp.update(final_extra)
            self.wfile.write(json.dumps(resp).encode('utf-8'))
            return

        self.send_response(404); self.send_header('Content-Type','application/json'); self.send_cors_headers(); self.end_headers()
        self.wfile.write(json.dumps({'ok': False, 'error': f'Unknown endpoint: {route_path}'}).encode('utf-8'))

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else server_port()
    with ReusableTCPServer(("", port), Handler) as httpd:
        print(f"Serving at port {port}"); httpd.serve_forever()
