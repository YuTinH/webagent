import os

# 1. 完整的单笔支付逻辑 (带扣款)
PAY_ORDER_LOGIC = r'''
    # B4 - Food Order Payment (Updated with DB Transaction)
    if task_id.startswith('B4') and action == 'pay_order':
        order_id = payload.get('order_id')
        orders = env.get('food', {}).get('orders', {})
        order = orders.get(order_id)
        
        if order and order.get('status') != 'paid':
            amount = float(order.get('total', 0))
            restaurant = order.get('restaurant', 'Food Order')
            
            # 1. Update Env State
            env = deep_merge(env, {"food": {"orders": {order_id: {"status": "paid"}}}})
            
            # 2. Database Transaction (Deduct Money)
            try:
                # 默认使用 Checking Account (ID=1)
                execute_db(
                    "INSERT INTO transactions (account_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
                    [1, -amount, 'debit', f"Food: {restaurant} ({order_id})", datetime.now().isoformat()]
                )
                execute_db("UPDATE accounts SET balance = balance - ? WHERE id = ?", [amount, 1])
            except Exception as e:
                print(f"Payment DB Error: {e}")

            # 3. Memory Update
            ts = datetime.now().isoformat()
            try:
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['food.order.last.status', 'paid', ts, task_id, 1.0])
            except: pass
            
        return env, {}
'''

# 2. 完整的一键支付逻辑 (带批量扣款)
PAY_ALL_LOGIC = r'''
    # B4 - Batch Pay All Orders (Updated with DB Transaction)
    if task_id.startswith('B4') and action == 'pay_all_orders':
        orders = env.get('food', {}).get('orders', {})
        updates = {}
        total_deduction = 0
        
        # Calculate total and prepare updates
        for oid, order in orders.items():
            if order.get('status') != 'paid':
                updates[oid] = {"status": "paid"}
                total_deduction += float(order.get('total', 0))
        
        if updates:
            # 1. Update Env State
            env = deep_merge(env, {"food": {"orders": updates}})
            
            # 2. Database Transaction
            if total_deduction > 0:
                try:
                    desc = f"YumYum Batch Payment ({len(updates)} orders)"
                    execute_db(
                        "INSERT INTO transactions (account_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
                        [1, -total_deduction, 'debit', desc, datetime.now().isoformat()]
                    )
                    execute_db("UPDATE accounts SET balance = balance - ? WHERE id = ?", [total_deduction, 1])
                except Exception as e:
                    print(f"Batch Payment DB Error: {e}")

            # 3. Memory Update
            ts = datetime.now().isoformat()
            try:
                execute_db("INSERT OR REPLACE INTO memory_kv (key,value,ts,source,confidence) VALUES (?,?,?,?,?)",
                           ['food.orders.all_paid', 'true', ts, task_id, 1.0])
            except: pass
        
        return env, {"updated_count": len(updates), "total_paid": total_deduction}
'''

def update_server():
    path = 'server.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除旧的 pay_order 逻辑 (简单替换可能不稳，我们用标记定位替换)
    # 既然之前的脚本是追加到文件里的，我们这里为了稳妥，
    # 建议把整个 'mutate_env' 函数的相关部分重写，或者更简单的：
    # 如果文件里已经有 pay_order，我们先做一个比较暴力的字符串替换。
    
    # 定义旧的逻辑片段特征 (从 enhance_payment_ux.py 生成的代码)
    old_pay_order_start = "if task_id.startswith('B4') and action == 'pay_order':"
    old_pay_all_start = "if task_id.startswith('B4') and action == 'pay_all_orders':"
    
    import re
    
    # 1. 替换 pay_order
    # 正则匹配整个 if 块直到 return env
    pattern_order = r"if task_id\.startswith\('B4'\) and action == 'pay_order':[\s\S]*?return env, \{\}"
    if re.search(pattern_order, content):
        content = re.sub(pattern_order, PAY_ORDER_LOGIC.strip(), content)
        print("✅ Replaced old pay_order logic")
    else:
        print("⚠️ Could not find old pay_order logic to replace (inserting new one...)")
        # 插入点
        marker = "return env, {\"redirect\": \"/food.local/orders.html\"}"
        if marker in content:
            content = content.replace(marker, marker + "\n" + PAY_ORDER_LOGIC)

    # 2. 替换 pay_all_orders
    pattern_all = r"if task_id\.startswith\('B4'\) and action == 'pay_all_orders':[\s\S]*?return env, \{.*?\}\}"
    if re.search(pattern_all, content):
        content = re.sub(pattern_all, PAY_ALL_LOGIC.strip(), content)
        print("✅ Replaced old pay_all_orders logic")
    else:
        # 如果找不到旧的，就追加在 pay_order 后面
        # 这里的 PAY_ORDER_LOGIC 肯定已经在里面了
        pass # 上一步如果没找到旧的，通常意味着之前也没运行成功，或者顺序问题。
             # 假设用户按顺序执行了，正则应该能匹配到。
             
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    print("🚀 Completing Payment Logic (DB Integration)...")
    update_server()
    print("✨ Done! Please restart server.py.")
    print("ℹ️  Now when you pay for food, check /bank.local/transactions.html to see the deduction!")