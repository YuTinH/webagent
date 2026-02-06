from .utils import deep_merge
import random
import datetime as dt_module

def handle_b_consumption(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # B1 - Shopping Checkout (Legacy)
    if action == 'checkout':
        try:
            import time
            items = payload.get('items', [])
            total = sum([float(i.get('price', 0)) * int(i.get('qty', 1)) for i in items])
            order_id = "ORD-" + str(int(time.time()))[-6:]
            
            new_order = {
                "id": order_id, "items": items, "total": total,
                "status": "confirmed", "date": ts
            }
            
            shop_state = env.get('shop', {})
            shop_state['cart'] = [] 
            if 'orders' not in shop_state: shop_state['orders'] = {}
            shop_state['orders'][order_id] = new_order
            env['shop'] = shop_state
            
            return env, {"redirect": "order.html"}
        except Exception as e:
            print(f"B1 Error: {e}")
            return env, {}

    # B1/Z1 - Create Order (Used by cart.html)
    if action == 'create_order':
        # CHECK BUTTERFLY EFFECT: Financial Liquidity
        liquidity = env.get('world_state', {}).get('financial_context', {}).get('liquidity', 'active')
        if liquidity == 'frozen':
            # Simulation of payment declined due to card block (M1)
            return env, {"error": "Payment Declined: Your payment methods are currently restricted.", "success": False}

        order_id = payload.get('order_id', f'O-{random.randint(10001, 99999)}')
        items = payload.get('items', [])
        total = payload.get('total', 0.0)
        shipping_speed = payload.get('shipping_speed', 'standard')
        shipping_address = payload.get('shipping_address', '')

        new_order_data = {
            "id": order_id,
            "items": items,
            "total": total,
            "state": "confirmed", # Using 'state' to match world_triggers
            "shipping_speed": shipping_speed,
            "shipping_address": shipping_address,
            "date": ts
        }

        # Use deep_merge to correctly set nested structure
        env = deep_merge(env, {"shop": {"orders": {order_id: new_order_data}}})
        env = deep_merge(env, {"shop": {"orders": {"last": {
            "id": order_id,
            "total": total,
            "state": "confirmed"
        }}}})
        
        # Add debug logging for env state after order creation
        with open("trigger_debug.log", "a") as f:
            f.write(f"DEBUG_B_CONSUMPTION: Order {order_id} created. Env['shop']['orders']: {env.get('shop',{}).get('orders',{})}\n")

        try:
            # FIX: Insert into SQL DB for API access (C2 Return flow)
            execute_db_fn("INSERT INTO orders (id, user_id, total, state, shipping_speed, shipping_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       [order_id, 1, total, "confirmed", shipping_speed, shipping_address, ts])
            
            for item in items:
                # items is list of dicts or strings? Payload usually has dicts with name, price?
                # Need to map item name to SKU if possible, or just insert dummy SKU
                # Simplified: insert with dummy SKU if not present
                sku = item.get('id', 'GENERIC')
                qty = item.get('qty', 1)
                price = item.get('price', 0)
                execute_db_fn("INSERT INTO order_items (order_id, sku, quantity, price) VALUES (?, ?, ?, ?)",
                           [order_id, sku, qty, price])

            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['shop.orders.last.id', order_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['shop.orders.last.state', 'confirmed', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['shop.orders.last.total', str(total), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'shop.orders.{order_id}.state', 'confirmed', ts, task_id, 1.0])
        except Exception:
            pass
            
        return env, {"redirect": f"order/confirmation/{order_id}?total={total}"}

    # B2 - Fresh Food Subscription
    if action == 'manage_subscription':
        sub_action = payload.get('action_type')
        
        if sub_action == 'subscribe':
            sub_id = f"SUB-{random.randint(1000, 9999)}"
            name = payload.get('name')
            frequency = payload.get('frequency')
            items = payload.get('items')
            price = payload.get('price_per_delivery')
            next_delivery_date = payload.get('next_delivery_date')

            env = deep_merge(env, {"food": {"subscriptions": {
                sub_id: {
                    "name": name,
                    "frequency": frequency,
                    "items": items,
                    "price_per_delivery": price,
                    "next_delivery_date": next_delivery_date,
                    "status": "active"
                },
                "last": {
                    "id": sub_id,
                    "status": "active",
                    "next_delivery_date": next_delivery_date
                }
            }}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'food.subscriptions.{sub_id}.id', sub_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'food.subscriptions.{sub_id}.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'food.subscriptions.{sub_id}.next_delivery_date', next_delivery_date, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['food.subscriptions.last.id', sub_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['food.subscriptions.last.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['food.subscriptions.last.next_delivery_date', next_delivery_date, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: B2 subscribe memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/food.local/subscription.html"}

        elif sub_action == 'reschedule':
            sub_id = payload.get('subscription_id')
            next_delivery_date = payload.get('next_delivery_date')

            current_sub = env.get('food', {}).get('subscriptions', {}).get(sub_id, {})
            current_sub['next_delivery_date'] = next_delivery_date
            env = deep_merge(env, {"food": {"subscriptions": {sub_id: current_sub}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'food.subscriptions.{sub_id}.next_delivery_date', next_delivery_date, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: B2 reschedule memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/food.local/subscription.html"}

        elif sub_action == 'toggle_status':
            sub_id = payload.get('subscription_id')
            status = payload.get('status') 

            current_sub = env.get('food', {}).get('subscriptions', {}).get(sub_id, {})
            current_sub['status'] = status
            env = deep_merge(env, {"food": {"subscriptions": {sub_id: current_sub}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'food.subscriptions.{sub_id}.status', status, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: B2 toggle_status memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/food.local/subscription.html"}

    # B3 - Local Housekeeping Booking
    if action == 'book_housekeeping':
        booking_id = f"HSK-{random.randint(1000, 9999)}"
        service_type = payload.get('service_type')
        service_date = payload.get('service_date')
        service_time = payload.get('service_time')
        instructions = payload.get('instructions', '')
        
        env = deep_merge(env, {"local_services": {"housekeeping_bookings": {booking_id: {
            "service_type": service_type,
            "service_date": service_date,
            "service_time": service_time,
            "instructions": instructions,
            "status": "confirmed",
            "booked_at": ts
        }}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'local_services.housekeeping_bookings.{booking_id}.id', booking_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'local_services.housekeeping_bookings.{booking_id}.date', service_date, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'local_services.housekeeping_bookings.{booking_id}.time', service_time, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'local_services.housekeeping_bookings.{booking_id}.type', service_type, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['local_services.housekeeping_bookings.last.id', booking_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['local_services.housekeeping_bookings.last.status', 'confirmed', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['local_services.housekeeping_bookings.last.date', service_date, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['local_services.housekeeping_bookings.last.time', service_time, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['local_services.housekeeping_bookings.last.type', service_type, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: B3 memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/housekeeping.html"}

    # B4 - Food Delivery
    if action == 'order_food' or action == 'order_food_with_promo':
        order_id = f"ODR-{random.randint(10000, 99999)}"
        restaurant = payload.get('restaurant', 'Unknown')
        items = payload.get('items', [])
        total = payload.get('total', 0.0)

        env = deep_merge(env, {"food": {"orders": {order_id: {"restaurant": restaurant, "items": items, "total": total, "status": "pending", "ordered_at": ts}}}})
        env = deep_merge(env, {"food": {"orders": {"last": {"id": order_id, "restaurant": restaurant, "items": items, "total": total, "status": "pending", "ordered_at": ts}}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['food.order.last.id', order_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['food.order.last.status', 'pending', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['food.order.last.total', str(total), ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/food.local/orders.html"}

    # B5 - Coupons & Discounts
    if action == 'manage_coupon':
        sub_action = payload.get('action_type')
        
        if sub_action == 'add':
            coupon_id = f"CPN-{random.randint(1000, 9999)}"
            name = payload.get('name')
            code = payload.get('code')
            
            # BUTTERFLY EFFECT CHECK: VIP Coupons
            if 'VIP' in code:
                has_access = env.get('world_state', {}).get('social_context', {}).get('has_coupon_access', False)
                if not has_access:
                    return env, {"error": "Coupon Invalid: You are not a member of the required community.", "success": False}

            coupon_type = payload.get('type')
            value = payload.get('value')
            min_spend = payload.get('min_spend')
            expiry_date = payload.get('expiry_date')

            env = deep_merge(env, {"shop": {"coupons": {coupon_id: {
                "name": name,
                "code": code,
                "type": coupon_type,
                "value": value,
                "min_spend": min_spend,
                "expiry_date": expiry_date,
                "status": "active"
            }}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'shop.coupons.{coupon_id}.id', coupon_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'shop.coupons.{coupon_id}.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'shop.coupons.{coupon_id}.code', code, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'shop.coupons.{coupon_id}.expiry_date', expiry_date, ts, task_id, 1.0])
                # Store "last" coupon details for easy assertion
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['shop.coupons.last.id', coupon_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['shop.coupons.last.code', code, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['shop.coupons.last.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['shop.coupons.last.expiry_date', expiry_date, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: B5 add coupon memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/shop.local/coupons.html"}

        elif sub_action == 'delete':
            coupon_id = payload.get('coupon_id')
            
            if env.get('shop', {}).get('coupons', {}).pop(coupon_id, None):
                # Remove from memory_kv
                try:
                    execute_db_fn("DELETE FROM memory_kv WHERE key LIKE ?", [f'shop.coupons.{coupon_id}%'])
                except Exception as e:
                    print(f"ERROR: B5 delete coupon memory_kv failed: {e}")
                    pass
            
            return env, {"redirect": "/shop.local/coupons.html"}

    # B6 - Price Protection
    if action == 'submit_price_protect':
        oid = payload.get('orderId', 'O-98321')
        patch = {"orders": {oid: {"claims": {"price_protect": {"state":"submitted"}}}}}
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'orders.{oid}.claims.price_protect.state', 'submitted', ts, task_id, 1.0])
        except: pass
        return deep_merge(env, patch), {"redirect": "/shop.local/price-protection.html?status=submitted"}

    # B7 - Second Hand Item Listing
    if action == 'list_second_hand_item':
        item_id = f"2H-{random.randint(1000, 9999)}"
        name = payload.get('name')
        desc = payload.get('description')
        price = float(payload.get('price', 0))
        category = payload.get('category')
        photo_name = payload.get('photo_name', '')

        # BUTTERFLY EFFECT: Expert Value
        is_certified = env.get('world_state', {}).get('skills', {}).get('certified', False)
        if is_certified and category == 'service': # Assuming 'service' category for gigs
            price *= 2.0

        env = deep_merge(env, {"market": {"listings": {item_id: {
            "name": name, "description": desc, "price": price, "category": category,
            "seller": "current_user", "status": "listed", "listed_at": ts, "photo": photo_name
        }}}})
        
        # Also update "last" entry in env for assertions
        env = deep_merge(env, {"market": {"listed_items": {"last": {
            "id": item_id, "name": name, "price": price, "category": category, "status": "listed"
        }}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['market.listed_items.last.id', item_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['market.listed_items.last.name', name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['market.listed_items.last.price', str(price), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['market.listed_items.last.category', category, ts, task_id, 1.0])
        except: pass

        return env, {"redirect": "/market.local/index.html?listed=true"}

    return env, {}
