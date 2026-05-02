from .utils import deep_merge
import random
import datetime as dt_module
import os
import sqlite3
from runtime_paths import db_path


def _should_log_debug() -> bool:
    value = os.environ.get("WEBAGENT_DEBUG_LOGS", "").strip().lower()
    return value in {"1", "true", "yes", "on"}

def handle_d_finance(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    def _balance_breakdown(total_balance):
        total = round(float(total_balance or 0), 2)
        checking = round(total * 0.64, 2)
        savings = round(total - checking, 2)
        return {
            "total": total,
            "checking": checking,
            "savings": savings,
        }

    def _resolve_total_balance():
        try:
            with sqlite3.connect(db_path()) as conn:
                row = conn.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE user_id = 1").fetchone()
                total = float((row or [0])[0] or 0)
                if total > 0:
                    return total
        except Exception:
            pass
        if env.get('balance') is not None:
            return float(env.get('balance') or 0)
        return 0.0

    # D1 - Check Balance
    if action == 'check_balance':
        account_type = payload.get('account_type', 'total')
        breakdown = _balance_breakdown(_resolve_total_balance())
        viewed_amount = breakdown.get(account_type, breakdown['total'])
        env = deep_merge(env, {"banking": {"balance_view": {
            "account_type": account_type,
            "amount": viewed_amount,
            "checked_at": ts,
        }}})
        # Simple logging of check action
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['banking.balance.last_check', ts, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['banking.balance.last_view', account_type, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['banking.balance.last_amount', str(viewed_amount), ts, task_id, 1.0])
        except: pass
        return env, {}

    # D2 - Budget Report
    if action == 'update_budget' or action == 'adjust_budget':
        cat = payload.get('category', 'food')
        limit = float(payload.get('limit', 500))
        
        env = deep_merge(env, {"finance": {"budgets": {cat: {"limit": limit}}}})
        
        # BUTTERFLY EFFECT: Energy Cost Impact
        energy_cost = env.get('world_state', {}).get('energy_context', {}).get('projected_cost', 'low')
        if cat == 'utilities' and energy_cost == 'high' and limit < 300:
             # Generate warning alert
             if 'finance' not in env: env['finance'] = {}
             env['finance']['warnings'] = ["Budget Alert: Your Premium Energy Plan exceeds the utility budget!"]
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'finance.budgets.{cat}.limit', str(limit), ts, task_id, 1.0])
        except Exception:
            pass
        return env, {"redirect": f"/bank.local/budget.html?updated=true&task={task_id}"}

    # D3 - Setup Autopay
    if action == 'setup_autopay':
        payee = payload.get('payee', 'Electricity Dept')
        acc_num = payload.get('account_number', 'UTIL-DEFAULT')
        amount = payload.get('amount', '200')
        
        env = deep_merge(env, {
            "has_utility": True,
            "autopay": {"utility": {
                'payee': payee,
                'amount': amount,
                'account_number': acc_num,
                'status': 'active'
            }},
            "contracts": {"electricity": {
                "status": "active",
                "account_number": acc_num
            }}
        })
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.payee', payee, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.amount', str(amount), ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.account_number', acc_num, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['contracts.electricity.status', 'active', ts, task_id, 1.0])
        except Exception:
            pass

        return env, {"redirect": f"/bank.local/autopay.html?state=active&payee={payee}&acc={acc_num}&amount={amount}&task={task_id}"}

    # D1 - Bill Aggregation
    if action == 'manage_bill_source':
        sub_action = payload.get('action_type')
        source_id = payload.get('source_id')

        if sub_action == 'add':
            source_id = f"BILL-{random.randint(1000, 9999)}"
            name = payload.get('name', 'Utility')
            source_type = payload.get('type', 'utility')
            account_id = payload.get('account_id')
            env = deep_merge(env, {"bills": {"sources": {source_id: {
                "name": name,
                "type": source_type,
                "account_id": account_id,
                "status": "active",
                "last_synced": None
            }, "last": {
                "id": source_id,
                "name": name,
                "type": source_type,
                "account_id": account_id,
                "status": "active",
                "last_synced": None
            }}}})
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.id', source_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.account_id', str(account_id or ''), ts, task_id, 1.0])
            except Exception:
                pass

        elif sub_action == 'sync' and source_id:
            current = env.get('bills', {}).get('sources', {}).get(source_id, {})
            current['last_synced'] = ts
            env = deep_merge(env, {"bills": {"sources": {
                source_id: current,
                "last": {
                    "id": source_id,
                    "name": current.get('name'),
                    "type": current.get('type'),
                    "account_id": current.get('account_id'),
                    "status": current.get('status', 'active'),
                    "last_synced": current.get('last_synced')
                }
            }}})
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.id', source_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.status', str(current.get('status', 'active')), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.last_synced', str(current.get('last_synced') or ''), ts, task_id, 1.0])
            except Exception:
                pass

        elif sub_action == 'remove' and source_id:
            env.get('bills', {}).get('sources', {}).pop(source_id, None)
        return env, {"redirect": "/bank.local/bill-aggregation.html"}

    # D4/D6 - Card Replacement / Card lifecycle
    if action in ('deactivate_card', 'block_card'):
        last4 = str(payload.get('last4', '1234') or '1234')
        env = deep_merge(env, {"payments": {"cards": {last4: {"state": "blocked"}}}})
        try:
            execute_db_fn("UPDATE cards SET state = 'blocked' WHERE last4 = ?", (last4,))
        except Exception:
            pass
        try:
            execute_db_fn(
                "INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                ['payment.cards[0].state', 'blocked', ts, task_id, 1.0]
            )
            execute_db_fn(
                "INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                ['payment.cards[0].last4', last4, ts, task_id, 1.0]
            )
        except Exception:
            pass
        return env, {}

    if action == 'request_otp':
        from datetime import datetime
        code = str(random.randint(100000, 999999))
        ts_now = datetime.now().isoformat()
        if 'mobile' not in env: env['mobile'] = {}
        if 'messages' not in env['mobile']: env['mobile']['messages'] = []
        env['mobile']['messages'].insert(0, {"sender": "BankSecure", "content": f"Your verification code is {code}", "timestamp": ts_now, "otp": code})
        return env, {"ok": True, "message": "OTP sent to your mobile."}

    if action == 'rebind_confirm':
        # Support both 'last4' (from unblock) and 'newLast4' (from replacement)
        last4 = payload.get('last4') or payload.get('newLast4', '7777')
        otp = payload.get('otp')
        
        if _should_log_debug():
            print(f"DEBUG: Processing rebind_confirm for last4: {last4}")
        
        # Sync to SQL Database (ROBUST FIX)
        try:
            # We update state to active for this card
            execute_db_fn("UPDATE cards SET state = 'active', last4 = ? WHERE last4 = ? OR id = 1", (last4, last4))
            if _should_log_debug():
                print(f"DEBUG: Database update executed for card {last4}")
        except Exception as e:
            print(f"DB Sync Error in rebind: {e}")

        env = deep_merge(env, {"payments":{"cards":{"active_last4": last4}}})
        for m in ["shop.local","ride.local","food.local","stream.local","cloud.local"]:
            env = deep_merge(env, {"payments":{"merchant_bindings":{"map":{m:last4}}}})
            
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].state', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].last4', last4, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: D4 rebind memory_kv failed: {e}")
            pass
            
        return env, {"redirect": f"/pay.local/wallet/cards.html?rebind=true&newLast4={last4}"}

    # D5 - Tax Preparation
    if action == 'upload_tax_document':
        sub_action = payload.get('action_type')
        if sub_action == 'upload':
            doc_id = f"TAX-{random.randint(10000, 99999)}"
            name = payload.get('name', 'Document')
            doc_type = payload.get('type', 'invoice')
            amount = payload.get('amount', 0)
            date = payload.get('date', '')
            env = deep_merge(env, {"finance": {"tax_documents": {doc_id: {
                "status": "pending",
                "uploaded_at": ts,
                "name": name,
                "type": doc_type,
                "amount": amount,
                "date": date
            }}}})
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.status', 'pending', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.id', doc_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.type', doc_type, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.amount', str(amount), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.date', str(date), ts, task_id, 1.0])
            except: pass
        return env, {"redirect": f"/bank.local/taxes.html?task={task_id}"}

    # D6 - Investment Account
    if action == 'manage_investment' or action == 'manage_investment_account':
        sub_action = payload.get('action_type')
        if sub_action == 'open':
            has_bank = bool(env.get('has_bank', True))
            try:
                liquid = float(env.get('balance', 5000) or 5000)
            except Exception:
                liquid = 5000.0
            if (not has_bank) or liquid <= 500:
                return env, {"success": False, "error": "Cannot open investment account without eligible banking profile."}
            acc_id = f"INV-{random.randint(1000, 9999)}"
            initial_deposit = float(payload.get('initial_deposit', payload.get('deposit', 500)))
            name = payload.get('name', 'Investment Account')
            acc_type = payload.get('type', 'stocks')
            env = deep_merge(env, {"has_invest": True, "finance": {"investment_accounts": {acc_id: {
                "name": name, "type": acc_type, "balance": initial_deposit, "status": "active", "opened_at": ts
            }}}})
            env = deep_merge(env, {"finance": {"investment_accounts": {"last": {
                "id": acc_id, "name": name, "type": acc_type, "balance": initial_deposit, "status": "active"
            }}}})
            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.balance', str(initial_deposit), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.status', 'active', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.type', acc_type, ts, task_id, 1.0])
            except: pass
        return env, {"redirect": f"/bank.local/investments.html?task={task_id}"}

    return env, {}
