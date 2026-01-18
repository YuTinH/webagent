from .utils import deep_merge
import random
import datetime as dt_module
import json
import re # Make sure re is imported outside the function for consistency, or inside if only used here

def handle_z_advanced(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # Z3 - Live Auction
    if action == 'place_bid':
        auction_id = payload.get('auction_id')
        bid_amount = float(payload.get('bid_amount'))
        
        # Initialize auction state if needed (simplified for simulation)
        if 'auctions' not in env: env['auctions'] = {}
        if auction_id not in env['auctions']:
            env['auctions'][auction_id] = {"current_price": 100.0, "highest_bidder": "system"}
            
        current_price = env['auctions'][auction_id]['current_price']
        
        if bid_amount > current_price:
            env['auctions'][auction_id]['current_price'] = bid_amount
            env['auctions'][auction_id]['highest_bidder'] = 'user'
            env['auctions'][auction_id]['last_bid_at'] = ts
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'auctions.{auction_id}.last_bid', str(bid_amount), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'auctions.{auction_id}.highest_bidder', 'user', ts, task_id, 1.0])
            except: pass
            
            return env, {"success": True, "new_price": bid_amount}
        else:
            return env, {"success": False, "message": "Bid too low"}

    # Z4 - Email (Mock fetch email content for verification logic if needed, usually just static)
    # But we need to validate the calendar event creation matches the email.
    # This is handled by F1 logic (add_event), but we can add a specific check here or reuse F1.
    # We'll rely on F1's manage_calendar_event. 
    # But we might need to seed the email in env.
    
    # Z5 - Password Recovery: Request Code
    if action == 'request_reset_code':
        username = payload.get('username')
        # Generate code (Fixed for testing Z5)
        code = "1234"
        
        # Store in mobile messages
        if 'mobile' not in env: env['mobile'] = {}
        if 'messages' not in env['mobile']: env['mobile']['messages'] = []
        
        message = {
            "from": "Security",
            "content": f"Your verification code is {code}",
            "timestamp": ts
        }
        env['mobile']['messages'].append(message)
        # Store code in session/env for verification
        if 'security' not in env: env['security'] = {}
        env['security']['reset_code'] = code
        env['security']['reset_user'] = username
        
        return env, {"redirect": "/security.local/reset-password.html"}

    # Z5 - Password Recovery: Reset
    if action == 'reset_password':
        code = payload.get('code')
        new_password = payload.get('new_password')
        
        stored_code = env.get('security', {}).get('reset_code')
        
        if code == stored_code:
            # Success
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['security.password_reset.status', 'success', ts, task_id, 1.0])
            except: pass
            return env, {"redirect": "/security.local/login.html?reset=success"}
        else:
            return env, {"error": "Invalid code"}

    # Z6 - Customer Service Chat
    if action == 'send_chat_message':
        # import re # Already imported at the top for current context
        message = payload.get('message', '')
        reply = "抱歉，我没听懂。您可以提供订单号（例如 O-12345）让我帮您查询吗？"
        
        # Simple intent: Check Order
        order_match = re.search(r'(O-\d+)', message)
        if order_match:
            order_id = order_match.group(1)
            orders = env.get('shop', {}).get('orders', {})
            
            with open("trigger_debug.log", "a") as f:
                f.write(f"Z6 Chat: Looking for order {order_id} in {orders}\n")
            
            order = orders.get(order_id)
            
            if order: # Correct indentation for this block
                status_map = {
                    'confirmed': '已确认，正在为您准备发货。',
                    'shipped': '已发货，物流正在运输中。',
                    'delivered': '已送达，感谢您的购买！',
                    'cancelled': '已取消。'
                }
                status_text = status_map.get(order.get('state', 'unknown'), f"当前状态：{order.get('state')}")
                reply = f"为您查询到订单 <b>{order_id}</b> 的状态：{status_text}<br>总金额：¥{order.get('total', 0)}"
                
        # Verify Success: If the user asked about a specific order and got a valid status, record it.
                try:
                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                               ['support.chat.last_query_order', order_id, ts, task_id, 1.0])
                    execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                               ['support.chat.last_reply_status', 'found', ts, task_id, 1.0])
                except: pass
            else:
                reply = f"抱歉，我没有找到订单号 <b>{order_id}</b> 的相关信息。"
        
        # Persist chat history
        if 'support' not in env: env['support'] = {}
        if 'chat_history' not in env['support']: env['support']['chat_history'] = []
        
        env['support']['chat_history'].append({"role": "user", "text": message, "time": ts})
        env['support']['chat_history'].append({"role": "bot", "text": reply, "time": ts})

        return env, {"reply": reply}

    return env, {}