from .utils import deep_merge
import random
import datetime as dt_module
import json

def handle_c_support(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # C1 - Logistics Fix
    if action == 'submit_ticket':
        ticket_id = f"TKT-{random.randint(1000, 9999)}"
        oid = payload.get('orderId', 'O-98321')
        issue_type = payload.get('type', 'delayed')

        # Create ticket
        env = deep_merge(env, {"support": {"tickets": {ticket_id: {"order_id": oid, "type": issue_type, "status": "open", "created_at": ts}}}})
        
        # Update order status (simulating agent intervention)
        env = deep_merge(env, {"orders": {oid: {"state": "investigating"}}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.ticket.last.id', ticket_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.ticket.last.status', 'open', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.ticket.last.order_id', oid, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/shop.local/help.html?status=ticket_created"}

    # C2 - Return Request
    if action == 'submit_return_request':
        return_id = f"RTN-{random.randint(10000, 99999)}"
        order_id = payload.get('order_id')
        reason = payload.get('reason')
        method = payload.get('method')

        env = deep_merge(env, {"returns": {"requests": {return_id: {
            "order_id": order_id,
            "reason": reason,
            "method": method,
            "status": "submitted",
            "submitted_at": ts
        }}}})
        
        # Also update "last" entry
        env = deep_merge(env, {"returns": {"last": {"id": return_id, "state": "submitted"}}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'returns.requests.{return_id}.id', return_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'returns.requests.{return_id}.status', 'submitted', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['returns.last.id', return_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['returns.last.state', 'submitted', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: C2 return request memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/returns-list.html"}

    # C3 - Subscription Refund (Prorated)
    if action == 'request_prorated_refund':
        request_id = f"REF-{random.randint(10000, 99999)}"
        sub_id = payload.get('subscription_id')
        reason = payload.get('reason')

        # Mock calculation logic
        estimated_refund = 0
        if sub_id == "SUB-8821": # Annual plan, 8 months left
            estimated_refund = 200 * (8/12) # Assuming 200 total
        elif sub_id == "SUB-9932": # Monthly plan, 10 days left
            estimated_refund = 30 * (10/30) # Assuming 30 total
        
        estimated_refund = round(estimated_refund, 2)

        env = deep_merge(env, {"support": {"refund_requests": {request_id: {
            "subscription_id": sub_id,
            "reason": reason,
            "status": "processing",
            "estimated_refund": estimated_refund,
            "submitted_at": ts
        }}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'support.refund_requests.{request_id}.id', request_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'support.refund_requests.{request_id}.status', 'processing', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'support.refund_requests.{request_id}.estimated_refund', str(estimated_refund), ts, task_id, 1.0])
            # Store "last" request details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.refund_requests.last.id', request_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.refund_requests.last.subscription_id', sub_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.refund_requests.last.status', 'processing', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['support.refund_requests.last.estimated_refund', str(estimated_refund), ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: C3 refund request memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/help-refund.html"}

    # C3 - Cancel Subscription
    if action == 'cancel_subscription':
        sub_id = payload.get('subscription_id')

        current_sub = env.get('subscriptions', {}).get(sub_id, {})
        current_sub['status'] = 'cancelled'
        env = deep_merge(env, {"subscriptions": {sub_id: current_sub}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'subscriptions.{sub_id}.status', 'cancelled', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['subscriptions.last.id', sub_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['subscriptions.last.status', 'cancelled', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: C3 cancel memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/subscriptions.html"}

    # C4 - Warranty Claim
    if action == 'submit_warranty_claim':
        serial = payload.get('serial')
        order_id = payload.get('orderId')
        
        env = deep_merge(env, {"warranty": {serial: {"state": "RMA_issued", "order_id": order_id, "claimed_at": ts}}})
        
        return env, {"redirect": f"/shop.local/warranty.html?status=accepted&serial={serial}"}

    # C5 - Reviews & Blacklist
    if action == 'submit_review':
        review_id = f"REV-{random.randint(1000, 9999)}"
        merchant = payload.get('merchant')
        rating = payload.get('rating')
        content = payload.get('content')
        add_to_blacklist = payload.get('add_to_blacklist', False)

        env = deep_merge(env, {"user_reviews": {"reviews": {review_id: {
            "merchant": merchant,
            "rating": rating,
            "content": content,
            "date": ts
        }}}})

        if add_to_blacklist:
            env = deep_merge(env, {"user_reviews": {"blacklist": {merchant: "blacklisted"}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'user_reviews.reviews.{review_id}.merchant', merchant, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'user_reviews.reviews.{review_id}.rating', str(rating), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'user_reviews.reviews.last.id', review_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_reviews.reviews.last.merchant', merchant, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['user_reviews.reviews.last.rating', str(rating), ts, task_id, 1.0])
            if add_to_blacklist:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'user_reviews.blacklist.{merchant}.status', 'blacklisted', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['user_reviews.blacklist.last.merchant', merchant, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: C5 submit review memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": "/shop.local/reviews.html"}

    # C5 - Manage Blacklist (remove)
    if action == 'manage_blacklist':
        merchant = payload.get('merchant')
        action_type = payload.get('action_type')

        if action_type == 'remove':
            if env.get('user_reviews', {}).get('blacklist', {}).pop(merchant, None):
                # Remove from memory_kv
                try:
                    execute_db_fn("DELETE FROM memory_kv WHERE key = ?", [f'user_reviews.blacklist.{merchant}.status'])
                except Exception as e:
                    print(f"ERROR: C5 remove blacklist memory_kv failed: {e}")
                    pass
            
        return env, {"redirect": "/shop.local/reviews.html"}

    return env, {}
