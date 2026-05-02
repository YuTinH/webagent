from .utils import deep_merge
import random
import datetime as dt_module
import json

def handle_f_work(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # F1 - Calendar Aggregation
    if action == 'manage_calendar_event':
        sub_action = payload.get('action_type')

        # Initialize calendar events if not exists
        if 'calendar' not in env:
            env['calendar'] = {}
        if 'events' not in env['calendar']:
            env['calendar']['events'] = {}

        if sub_action == 'add':
            event_id = f"EVE-{random.randint(1000, 9999)}"
            title = payload.get('title')
            date = payload.get('date')
            time = payload.get('time')
            event_type = payload.get('type')
            description = payload.get('description', '')

            # Simulate conflict detection (simple: same date and time means conflict)
            is_conflict = False
            for existing_event in env['calendar']['events'].values():
                if existing_event['date'] == date and existing_event['time'] == time:
                    is_conflict = True
                    existing_event['conflict'] = True # Mark existing as conflict
                    # Update memory_kv for existing conflicting event too
                    try:
                        execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                   [f'calendar.events.{existing_event["id"]}.conflict', '1', ts, task_id, 1.0])
                    except Exception as e:
                        print(f"ERROR: F1 existing conflict memory_kv update failed: {e}")
                        pass
                    break
            
            env = deep_merge(env, {"calendar": {"events": {event_id: {
                "title": title,
                "date": date,
                "time": time,
                "type": event_type,
                "description": description,
                "conflict": is_conflict,
                "created_at": ts
            }}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.id', event_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.title', title, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.date', date, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.time', time, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.type', event_type, ts, task_id, 1.0])
                val_conflict = '1' if is_conflict else '0'
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.conflict', val_conflict, ts, task_id, 1.0])
                # Store "last" event details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.id', event_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.title', title, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.date', date, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.time', time, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.type', event_type, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.conflict', val_conflict, ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: F1 add event memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": f"/work.local/calendar.html?task={task_id}"}

        elif sub_action == 'resolve_conflict':
            event_id = payload.get('event_id')
            
            # Find the event and mark its conflict as false
            if event_id in env['calendar']['events']:
                env['calendar']['events'][event_id]['conflict'] = False
            
            # Also reset other conflicting events for simplicity (in a real app, this would be more complex)
            for eid, event in env['calendar']['events'].items():
                if eid != event_id and event.get('conflict', False):
                    # Check if there's an actual conflict with the now-resolved event
                    if event['date'] == env['calendar']['events'][event_id]['date'] and \
                       event['time'] == env['calendar']['events'][event_id]['time']:
                        event['conflict'] = False # Other event is no longer conflicting with this one
                        try:
                            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                                       [f'calendar.events.{eid}.conflict', '0', ts, task_id, 1.0])
                        except Exception as e:
                            print(f"ERROR: F1 other event conflict memory_kv update failed: {e}")
                            pass
            
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'calendar.events.{event_id}.conflict', '0', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['calendar.events.last.conflict', '0', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: F1 resolve conflict memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": f"/work.local/calendar.html?task={task_id}"}

    # F2 - Conference Registration
    if action == 'conference_register':
        conference_id = payload.get('conferenceId', 'CL-2026')
        invoice_title = payload.get('invoiceTitle', 'Your Lab')
        reg_id = f"CONF-{random.randint(1000, 9999)}"
        
        env = deep_merge(env, {"invoices": {"last": {"conference": conference_id, "invoice_title": invoice_title, "status": "paid", "reg_id": reg_id}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['invoices.last.conference', conference_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['invoices.last.status', 'paid', ts, task_id, 1.0])
        except Exception:
            pass
        
        return env, {"redirect": f"/event.local/registration.html?state=confirmed&regId={reg_id}&eventName={conference_id}&invoiceTitle={invoice_title}"}

    # F3 - Paper Submission
    if action == 'submit_paper':
        submission_id = f"SUB-{random.randint(10000, 99999)}"
        title = payload.get('title')
        
        # Record submission first; downstream quality review should not erase the
        # fact that the paper was submitted.
        skills = env.get('world_state', {}).get('skills', {})
        writing_skill = skills.get('writing', 'none')
        certified = str(skills.get('certified', 'False')).lower() == 'true'
        status = "submitted"
        quality_review = "approved"
        if writing_skill != 'advanced' and not certified:
            quality_review = "needs_revision"

        journal = payload.get('journal')
        authors = payload.get('authors')
        abstract = payload.get('abstract', '')
        track = payload.get('track', 'general')
        file_name = payload.get('file')

        submission_record = {
            "id": submission_id,
            "title": title,
            "journal": journal,
            "authors": authors,
            "abstract": abstract,
            "track": track,
            "file": file_name,
            "status": status,
            "quality_review": quality_review,
            "submitted_at": ts,
            "fees_paid": False
        }

        env = deep_merge(env, {"work": {"paper_submissions": {
            submission_id: submission_record,
            "last": submission_record,
        }}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.id', submission_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.title', title, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.journal', journal, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.track', track, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.file', file_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.status', status, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.quality_review', quality_review, ts, task_id, 1.0])
            val_fees_paid = '0' # False
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.fees_paid', val_fees_paid, ts, task_id, 1.0])
            # Store "last" submission details
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.id', submission_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.title', title, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.journal', journal, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.track', track, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.file', file_name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.status', status, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.quality_review', quality_review, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: F3 submit paper memory_kv insert failed: {e}")
            pass
            
        return env, {"redirect": f"/work.local/paper-submission.html?task={task_id}"}

    if action == 'pay_publication_fees':
        submission_id = payload.get('submission_id')

        current_submission = env.get('work', {}).get('paper_submissions', {}).get(submission_id, {})
        current_submission['fees_paid'] = True
        current_submission['id'] = submission_id
        env = deep_merge(env, {"work": {"paper_submissions": {
            submission_id: current_submission,
            "last": current_submission,
        }}})
            
        try:
            val_fees_paid = '1' # True
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'work.paper_submissions.{submission_id}.fees_paid', val_fees_paid, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['work.paper_submissions.last.fees_paid', val_fees_paid, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: F3 pay fees memory_kv update failed: {e}")
            pass
            
        return env, {"redirect": f"/work.local/paper-submission.html?task={task_id}"}

    # F4 - Email Thread Tracking
    if action == 'track_email_thread':
        sub_action = payload.get('action_type')

        if sub_action == 'add':
            thread_id = f"MSG-{random.randint(1000, 9999)}"
            subject = payload.get('subject')
            sender = payload.get('sender')
            summary = payload.get('summary', '')
            priority = payload.get('priority', 'normal')
            follow_up_date = payload.get('follow_up_date', '')

            thread_record = {
                "id": thread_id,
                "subject": subject,
                "sender": sender,
                "summary": summary,
                "priority": priority,
                "follow_up_date": follow_up_date,
                "status": "pending",
                "last_updated": ts
            }

            env = deep_merge(env, {"work": {"email_threads": {
                thread_id: thread_record,
                "last": thread_record,
            }}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.id', thread_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.subject', subject, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.sender', sender, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.summary', summary, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.priority', priority, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.status', 'pending', ts, task_id, 1.0])
                # Store "last" thread details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.id', thread_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.subject', subject, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.sender', sender, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.summary', summary, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.priority', priority, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.status', 'pending', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: F4 add email thread memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": f"/work.local/email-tracking.html?task={task_id}"}

        elif sub_action == 'mark_replied':
            thread_id = payload.get('thread_id')
            
            current_thread = env.get('work', {}).get('email_threads', {}).get(thread_id, {})
            current_thread['status'] = 'replied'
            current_thread['last_updated'] = ts
            current_thread['id'] = thread_id
            env = deep_merge(env, {"work": {"email_threads": {
                thread_id: current_thread,
                "last": current_thread,
            }}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'work.email_threads.{thread_id}.status', 'replied', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['work.email_threads.last.status', 'replied', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: F4 mark replied memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": f"/work.local/email-tracking.html?task={task_id}"}

    # F5 - Receipt Archiving
    if action == 'archive_document':
        doc_id = f"DOC-{random.randint(10000, 99999)}"
        name = payload.get('fileName', 'document.pdf')
        doc_type = payload.get('docType', 'receipt')
        size = payload.get('fileSize', 1024)

        env = deep_merge(env, {"cloud": {"documents": {doc_id: {
            "name": name, "type": doc_type, "size": size,
            "uploaded_at": ts, "tags": [doc_type]
        }}}})
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'cloud.documents.{doc_id}.status', 'archived', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'cloud.documents.{doc_id}.name', name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['cloud.documents.last.id', doc_id, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['cloud.documents.last.name', name, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['cloud.documents.last.type', doc_type, ts, task_id, 1.0])
        except: pass
        
        return env, {"redirect": f"/cloud.local/index.html?uploaded=true&task={task_id}"}

    return env, {}
