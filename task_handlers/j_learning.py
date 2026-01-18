from .utils import deep_merge
import random
import datetime as dt_module

def handle_j_learning(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # J1 - Course Enrollment
    if action == 'enroll_course':
        course_id = payload.get('courseId', 'DL101')
        
        env = deep_merge(env, {"courses": {course_id: {"state": "enrolled", "enrolled_at": ts}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'courses.{course_id}.state', 'enrolled', ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": "/school.local/my-learning.html"}

    # J2 - Library Card and Book Booking
    if action == 'manage_library_service':
        sub_action = payload.get('action_type')

        # Initialize library data if not exists
        if 'library' not in env:
            env['library'] = {}
        if 'card' not in env['library']:
            env['library']['card'] = {"status": "inactive"}
        if 'reservations' not in env['library']:
            env['library']['reservations'] = {}

        if sub_action == 'apply_card':
            card_number = f"LC-{random.randint(10000, 99999)}"
            applicant_name = payload.get('applicant_name')
            student_id = payload.get('student_id')
            expiry_date = (dt_module.datetime.now() + dt_module.timedelta(days=365*4)).strftime('%Y-%m-%d') # 4 years validity

            env = deep_merge(env, {"library": {"card": {
                "card_number": card_number,
                "applicant_name": applicant_name,
                "student_id": student_id,
                "status": "active",
                "expiry_date": expiry_date,
                "borrow_limit": 10,
                "borrowed_count": 0
            }}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.card.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.card.card_number', card_number, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.card.expiry_date', expiry_date, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J2 apply card memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/school.local/library.html"}

        elif sub_action == 'reserve_book':
            reservation_id = f"RES-{random.randint(1000, 9999)}"
            book_query = payload.get('book_query')
            pickup_date = payload.get('pickup_date')
            pickup_deadline = (dt_module.datetime.strptime(pickup_date, '%Y-%m-%d') + dt_module.timedelta(days=7)).strftime('%Y-%m-%d')

            env = deep_merge(env, {"library": {"reservations": {reservation_id: {
                "book_title": book_query, # Simplified: query is title
                "reserve_date": ts.split('T')[0],
                "pickup_date": pickup_date,
                "pickup_deadline": pickup_deadline,
                "status": "pending"
            }}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'library.reservations.{reservation_id}.id', reservation_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'library.reservations.{reservation_id}.book_title', book_query, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'library.reservations.{reservation_id}.status', 'pending', ts, task_id, 1.0])
                # Store "last" reservation details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.reservations.last.id', reservation_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.reservations.last.book_title', book_query, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.reservations.last.status', 'pending', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J2 reserve book memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/school.local/library.html"}
            
        return env, {}

    # J3 - Event Tickets
    if action == 'manage_tickets':
        sub_action = payload.get('action_type')

        # Initialize tickets if not exists
        if 'tickets' not in env:
            env['tickets'] = {}
        if 'user_tickets' not in env['tickets']:
            env['tickets']['user_tickets'] = {}

        if sub_action == 'buy':
            ticket_id = f"TKT-{random.randint(10000, 99999)}"
            event_id = payload.get('event_id')
            event_name = payload.get('event_name')
            price = payload.get('price')

            env = deep_merge(env, {"tickets": {"user_tickets": {ticket_id: {
                "event_id": event_id,
                "event_name": event_name,
                "price": price,
                "status": "active",
                "purchased_at": ts
            }}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'tickets.user_tickets.{ticket_id}.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'tickets.user_tickets.{ticket_id}.event_name', event_name, ts, task_id, 1.0])
                # Store "last" ticket details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['tickets.user_tickets.last.id', ticket_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['tickets.user_tickets.last.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['tickets.user_tickets.last.event_name', event_name, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J3 buy ticket memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/school.local/event-tickets.html"}

        elif sub_action == 'transfer':
            ticket_id = payload.get('ticket_id')
            recipient_id = payload.get('recipient_id')
            
            current_ticket = env.get('tickets', {}).get('user_tickets', {}).get(ticket_id, {})
            current_ticket['status'] = 'transferred'
            current_ticket['recipient'] = recipient_id
            env = deep_merge(env, {"tickets": {"user_tickets": {ticket_id: current_ticket}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'tickets.user_tickets.{ticket_id}.status', 'transferred', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['tickets.user_tickets.last.status', 'transferred', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J3 transfer ticket memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/school.local/event-tickets.html"}

        elif sub_action == 'refund':
            ticket_id = payload.get('ticket_id')
            
            current_ticket = env.get('tickets', {}).get('user_tickets', {}).get(ticket_id, {})
            current_ticket['status'] = 'refunded'
            env = deep_merge(env, {"tickets": {"user_tickets": {ticket_id: current_ticket}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'tickets.user_tickets.{ticket_id}.status', 'refunded', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['tickets.user_tickets.last.status', 'refunded', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J3 refund ticket memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/school.local/event-tickets.html"}
            
        return env, {}

    # J4 - Hobby Gear Rent/Sell
    if action == 'manage_gear_listing':
        sub_action = payload.get('action_type')

        # Initialize gear data if not exists
        if 'gear' not in env:
            env['gear'] = {}
        if 'rentals' not in env['gear']:
            env['gear']['rentals'] = {}
        if 'sales' not in env['gear']:
            env['gear']['sales'] = {}

        if sub_action == 'list':
            gear_id = f"GEAR-{random.randint(10000, 99999)}"
            name = payload.get('name')
            listing_type = payload.get('type')
            price = payload.get('price')
            
            category = 'sales' if listing_type == 'sale' else 'rentals'

            if listing_type == 'sale':
                env = deep_merge(env, {"gear": {"sales": {gear_id: {
                    "name": name,
                    "type": "sale",
                    "price": price,
                    "status": "listed",
                    "listed_at": ts
                }}}})
            elif listing_type == 'rent':
                env = deep_merge(env, {"gear": {"rentals": {gear_id: {
                    "name": name,
                    "type": "rent",
                    "rental_price": price,
                    "status": "available",
                    "listed_at": ts
                }}}})
            
            try:
                status_val = 'listed' if listing_type == 'sale' else 'available'
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gear.{category}.{gear_id}.id', gear_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gear.{category}.{gear_id}.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gear.{category}.{gear_id}.status', status_val, ts, task_id, 1.0])
                # Store "last" gear details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gear.{category}.last.id', gear_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gear.{category}.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'gear.{category}.last.status', status_val, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J4 list gear memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/shop.local/gear-rental.html"}

        elif sub_action == 'remove':
            gear_id = payload.get('gear_id')
            
            removed_from_sales = env.get('gear', {}).get('sales', {}).pop(gear_id, None)
            removed_from_rentals = env.get('gear', {}).get('rentals', {}).pop(gear_id, None)

            if removed_from_sales or removed_from_rentals:
                try:
                    execute_db_fn("DELETE FROM memory_kv WHERE key LIKE ?", [f'gear.sales.{gear_id}%'])
                    execute_db_fn("DELETE FROM memory_kv WHERE key LIKE ?", [f'gear.rentals.{gear_id}%'])
                except Exception as e:
                    print(f"ERROR: J4 remove gear memory_kv failed: {e}")
                    pass
            
            return env, {"redirect": "/shop.local/gear-rental.html"}
            
        return env, {}

    return env, {}
