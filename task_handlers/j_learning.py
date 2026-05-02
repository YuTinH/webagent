from .utils import deep_merge
import random
import datetime as dt_module

def handle_j_learning(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # J1 - Course Enrollment
    if action == 'enroll_course':
        # CHECK BUTTERFLY EFFECT: Health Status
        health = env.get('world_state', {}).get('physical_context', {}).get('status', 'healthy')
        if health == 'impaired':
            return env, {"error": "无法报名：您当前的体力值不足，请先休息或咨询医生。", "success": False}

        course_id = payload.get('courseId', 'DL101')
        
        # BUTTERFLY EFFECT: Skill Quality based on Energy
        energy = env.get('world_state', {}).get('physical_context', {}).get('energy_level', 100)
        skill_level = 'advanced' if energy >= 50 else 'basic'
        
        if 'Writing' in course_id or 'Writing' in payload.get('courseName', ''):
            if 'world_state' not in env: env['world_state'] = {}
            if 'skills' not in env['world_state']: env['world_state']['skills'] = {}
            env['world_state']['skills']['writing'] = skill_level
        
        term = payload.get('term', '')
        study_mode = payload.get('study_mode', '')
        learning_goal = payload.get('learning_goal', '')

        env = deep_merge(env, {"courses": {course_id: {
            "state": "enrolled",
            "enrolled_at": ts,
            "term": term,
            "study_mode": study_mode,
            "learning_goal": learning_goal,
        }}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'courses.{course_id}.state', 'enrolled', ts, task_id, 1.0])
            if term:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'courses.{course_id}.term', term, ts, task_id, 1.0])
            if study_mode:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'courses.{course_id}.study_mode', study_mode, ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/school.local/my-learning.html?task={task_id}"}

    # J2 - Ebook Purchase
    if action == 'buy_ebook':
        book_id = payload.get('bookId', 'BK-101')
        title = payload.get('title', '')
        price = payload.get('price', 0)
        delivery_email = payload.get('delivery_email', '')
        license_tier = payload.get('license_tier', '')
        reading_device = payload.get('reading_device', '')
        purchase_note = payload.get('purchase_note', '')

        if 'library' not in env:
            env['library'] = {}
        if 'books' not in env['library']:
            env['library']['books'] = {}

        env = deep_merge(env, {"library": {"books": {book_id: {
            "id": book_id,
            "title": title,
            "price": price,
            "owned": True,
            "purchased_at": ts,
            "delivery_email": delivery_email,
            "license_tier": license_tier,
            "reading_device": reading_device,
            "purchase_note": purchase_note,
        }}}})

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'library.books.{book_id}.owned', 'true', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'library.books.{book_id}.title', title, ts, task_id, 1.0])
            if license_tier:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'library.books.{book_id}.license_tier', license_tier, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['library.books.last.id', book_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['library.books.last.owned', 'true', ts, task_id, 1.0])
        except Exception:
            pass

        return env, {"redirect": f"/school.local/my-learning.html?new_book=true&task={task_id}"}

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
                           ['library.card.applicant_name', applicant_name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.card.student_id', student_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.card.expiry_date', expiry_date, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J2 apply card memory_kv insert failed: {e}")
                pass
            
            return env, {"success": True}

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
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['library.reservations.last.pickup_date', pickup_date, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: J2 reserve book memory_kv insert failed: {e}")
                pass
            
            return env, {"success": True}
            
        return env, {}

    # J7 - Assignment Submission
    if action == 'submit_assignment':
        submission_id = f"ASG-{random.randint(10000, 99999)}"
        course_id = payload.get('course_id', 'ML202')
        assignment_title = payload.get('assignment_title', 'ML202 Project Draft')
        file_name = payload.get('file_name', 'ml202_project_draft.pdf')
        submission_note = payload.get('submission_note', '')

        if 'courses' not in env:
            env['courses'] = {}
        if 'assignments' not in env['courses']:
            env['courses']['assignments'] = {}

        env = deep_merge(
            env,
            {
                "courses": {
                    course_id: {
                        "assignment_status": "submitted",
                        "last_submission_id": submission_id,
                    },
                    "assignments": {
                        submission_id: {
                            "course_id": course_id,
                            "title": assignment_title,
                            "file_name": file_name,
                            "submission_note": submission_note,
                            "status": "submitted",
                            "submitted_at": ts,
                        },
                        "last": {
                            "id": submission_id,
                            "course_id": course_id,
                            "title": assignment_title,
                            "file_name": file_name,
                            "submission_note": submission_note,
                            "status": "submitted",
                            "submitted_at": ts,
                        },
                    },
                }
            },
        )

        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['courses.assignments.last.id', submission_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['courses.assignments.last.course_id', course_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['courses.assignments.last.title', assignment_title, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['courses.assignments.last.file_name', file_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['courses.assignments.last.status', 'submitted', ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: J7 submit assignment memory_kv insert failed: {e}")
            pass

        return env, {"redirect": f"/school.local/my-learning.html?task={task_id}&submitted=true&submission_id={submission_id}"}
            
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
            
            return env, {"redirect": f"/school.local/event-tickets.html?task={task_id}"}

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
            
            return env, {"redirect": f"/school.local/event-tickets.html?task={task_id}"}

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
            
            return env, {"redirect": f"/school.local/event-tickets.html?task={task_id}"}
            
        return env, {}

    # J4 - Certification / Hobby Gear (Merged Handler)
    if action == 'issue_certificate':
        cert_name = payload.get('name')
        
        # BUTTERFLY EFFECT: Skill Certification
        if 'Certified' in cert_name:
            if 'world_state' not in env: env['world_state'] = {}
            if 'skills' not in env['world_state']: env['world_state']['skills'] = {}
            env['world_state']['skills']['certified'] = True
            env['world_state']['skills']['last_certificate'] = cert_name
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['world_state.skills.certified', 'True', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['world_state.skills.last_certificate', cert_name, ts, task_id, 1.0])
            except: pass
            
        return env, {"status": "issued"}

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
