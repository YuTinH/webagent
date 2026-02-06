from .utils import deep_merge
import random
import datetime as dt_module

def handle_d_finance(task_id, action, payload, env, execute_db_fn):
    ts = dt_module.datetime.now().isoformat()

    # D1 - Bill Aggregation
    if action == 'manage_bill_source':
        sub_action = payload.get('action_type')

        if sub_action == 'add':
            source_id = f"BS-{random.randint(1000, 9999)}"
            name = payload.get('name')
            source_type = payload.get('type')
            account_id = payload.get('account_id')

            env = deep_merge(env, {"bills": {"sources": {source_id: {
                "name": name,
                "type": source_type,
                "account_id": account_id,
                "status": "active",
                "last_synced": None
            }}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'bills.sources.{source_id}.id', source_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'bills.sources.{source_id}.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'bills.sources.{source_id}.status', 'active', ts, task_id, 1.0])
                # Store "last" source details for easy assertion
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.id', source_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.status', 'active', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: D1 add bill source memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/bank.local/bill-aggregation.html"}

        elif sub_action == 'sync':
            source_id = payload.get('source_id')
            
            current_source = env.get('bills', {}).get('sources', {}).get(source_id, {})
            current_source['last_synced'] = ts
            env = deep_merge(env, {"bills": {"sources": {source_id: current_source}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'bills.sources.{source_id}.last_synced', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['bills.sources.last.last_synced', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: D1 sync bill source memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/bank.local/bill-aggregation.html"}

        elif sub_action == 'remove':
            source_id = payload.get('source_id')
            
            if env.get('bills', {}).get('sources', {}).pop(source_id, None):
                try:
                    execute_db_fn("DELETE FROM memory_kv WHERE key LIKE ?", [f'bills.sources.{source_id}%'])
                except Exception as e:
                    print(f"ERROR: D1 remove bill source memory_kv failed: {e}")
                    pass
            
            return env, {"redirect": "/bank.local/bill-aggregation.html"}

    # D2 - Budget Report
    if action == 'adjust_budget':
        cat = payload.get('category', 'food')
        limit = payload.get('limit', 500)
        
        # BUTTERFLY EFFECT: Energy Cost Impact
        energy_cost = env.get('world_state', {}).get('energy_context', {}).get('projected_cost', 'low')
        if cat == 'utilities' and energy_cost == 'high' and limit < 300:
             # If plan is high cost but budget is low, trigger warning
             env = deep_merge(env, {"finance": {"warnings": ["Budget Alert: Your Premium Energy Plan exceeds the utility budget!"]}})
        
        env = deep_merge(env, {"finance": {"budgets": {cat: {"limit": limit}}}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       [f'finance.budgets.{cat}.limit', limit, ts, task_id, 1.0])
        except: pass
        return env, {"redirect": "/bank.local/budget.html"}

    # D3 - Autopay Setup
    if action == 'setup_autopay':
        payee = payload.get('payee','Utilities')
        account_type = payload.get('account_type','checking')
        amount = float(payload.get('amount',0))
        frequency = payload.get('frequency','monthly')
        start_date = payload.get('start_date', dt_module.datetime.now().strftime('%Y-%m-%d'))

        env = deep_merge(env, {"autopay": {"utility": { 
            'payee': payee,
            'account_type': account_type,
            'amount': amount,
            'frequency': frequency,
            'next_date': start_date,
            'status': 'active'
        }}})
        
        try:
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.amount', amount, ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['autopay.utility.next_date', start_date, ts, task_id, 1.0])
        except Exception:
            pass

        return env, {"redirect": f"/bank.local/autopay.html?state=active&payee={payee}&amount={amount}&frequency={frequency}&next_date={start_date}"}

    # D4 - Card Replacement
    if action == 'rebind_confirm':
        last4 = payload.get('newLast4', '7777')
        env = deep_merge(env, {"payments":{"cards":{"active_last4": last4}}})
        for m in ["shop.local","ride.local","food.local","stream.local","cloud.local"]:
            env = deep_merge(env, {"payments":{"merchant_bindings":{"map":{m:last4}}}})
            
        try:
            # FIX: Write status to memory_kv
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].status', 'active', ts, task_id, 1.0])
            execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                       ['payment.cards[0].last4', last4, ts, task_id, 1.0])
        except Exception as e:
            print(f"ERROR: D4 rebind memory_kv failed: {e}")
            pass
            
        return env, {"redirect": "/pay.local/wallet/cards.html?rebind=true"}

    # D5 - Tax Preparation
    if action == 'upload_tax_document':
        sub_action = payload.get('action_type')

        if sub_action == 'upload':
            doc_id = f"TAX-{random.randint(10000, 99999)}"
            name = payload.get('name')
            doc_type = payload.get('type')
            amount = payload.get('amount')
            date = payload.get('date')

            env = deep_merge(env, {"finance": {"tax_documents": {doc_id: {
                "name": name,
                "type": doc_type,
                "amount": amount,
                "date": date,
                "status": "pending",
                "uploaded_at": ts
            }}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.tax_documents.{doc_id}.id', doc_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.tax_documents.{doc_id}.status', 'pending', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.tax_documents.{doc_id}.amount', str(amount), ts, task_id, 1.0])
                # Store "last" doc details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.id', doc_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.status', 'pending', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.amount', str(amount), ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: D5 upload tax doc memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/bank.local/taxes.html"}

        elif sub_action == 'verify':
            doc_id = payload.get('doc_id')
            
            current_doc = env.get('finance', {}).get('tax_documents', {}).get(doc_id, {})
            current_doc['status'] = 'verified'
            env = deep_merge(env, {"finance": {"tax_documents": {doc_id: current_doc}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.tax_documents.{doc_id}.status', 'verified', ts, task_id, 1.0])
                # Also update last status if this was the last one (simplified assumption)
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.tax_documents.last.status', 'verified', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: D5 verify tax doc memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/bank.local/taxes.html"}

        elif sub_action == 'delete':
            doc_id = payload.get('doc_id')
            
            if env.get('finance', {}).get('tax_documents', {}).pop(doc_id, None):
                try:
                    execute_db_fn("DELETE FROM memory_kv WHERE key LIKE ?", [f'finance.tax_documents.{doc_id}%'])
                except Exception as e:
                    print(f"ERROR: D5 delete tax doc memory_kv failed: {e}")
                    pass
            
            return env, {"redirect": "/bank.local/taxes.html"}

    # D6 - Investment Account
    if action == 'manage_investment_account':
        sub_action = payload.get('action_type')

        if sub_action == 'open':
            account_id = f"INV-{random.randint(10000, 99999)}"
            name = payload.get('name')
            account_type = payload.get('type')
            initial_deposit = payload.get('initial_deposit', 0.0)

            env = deep_merge(env, {"finance": {"investment_accounts": {
                account_id: {
                    "name": name,
                    "type": account_type,
                    "balance": initial_deposit,
                    "status": "active",
                    "opened_at": ts
                },
                "last": {
                    "id": account_id,
                    "name": name,
                    "balance": initial_deposit,
                    "status": "active"
                }
            }}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.investment_accounts.{account_id}.id', account_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.investment_accounts.{account_id}.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.investment_accounts.{account_id}.type', account_type, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.investment_accounts.{account_id}.balance', str(initial_deposit), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.investment_accounts.{account_id}.status', 'active', ts, task_id, 1.0])
                # Store "last" account details
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.id', account_id, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.name', name, ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.balance', str(initial_deposit), ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.status', 'active', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: D6 open account memory_kv insert failed: {e}")
                pass
            
            return env, {"redirect": "/bank.local/investments.html"}

        elif sub_action == 'close':
            account_id = payload.get('account_id')
            
            current_account = env.get('finance', {}).get('investment_accounts', {}).get(account_id, {})
            current_account['status'] = 'closed'
            env = deep_merge(env, {"finance": {"investment_accounts": {account_id: current_account}}})

            try:
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           [f'finance.investment_accounts.{account_id}.status', 'closed', ts, task_id, 1.0])
                execute_db_fn("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['finance.investment_accounts.last.status', 'closed', ts, task_id, 1.0])
            except Exception as e:
                print(f"ERROR: D6 close account memory_kv update failed: {e}")
                pass
            
            return env, {"redirect": "/bank.local/investments.html"}

    return env, {}
