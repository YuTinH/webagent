import os
import re

# B1 任务的核心逻辑
SERVER_PATCH_B1 = r'''
    # B1 - Shopping Checkout Logic (Injected by Robust Patcher)
    if task_id.startswith('B1') and action == 'checkout':
        # 1. 创建订单
        items = payload.get('items', [])
        total = sum([float(i.get('price', 0)) * int(i.get('qty', 1)) for i in items])
        import time
        order_id = "ORD-" + str(int(time.time()))[-6:]
        
        new_order = {
            "id": order_id,
            "items": items,
            "total": total,
            "status": "confirmed",
            "date": datetime.now().isoformat()
        }
        
        # 2. 更新环境：清空购物车，添加订单
        shop_state = env.get('shop', {})
        shop_state['cart'] = [] # Clear cart
        if 'orders' not in shop_state: shop_state['orders'] = {}
        shop_state['orders'][order_id] = new_order
        env['shop'] = shop_state
        
        # 3. 关键：返回 redirect 字段，指示前端跳转
        return env, {"redirect": "/shop.local/order.html"}
'''

def patch_server():
    path = 'server.py'
    if not os.path.exists(path):
        print(f"❌ 错误: 找不到文件 {path}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 使用正则表达式灵活查找函数定义
    # 匹配: def mutate_env ( 任意参数 ) :
    pattern = r"def\s+mutate_env\s*\(.*?\)\s*:"
    match = re.search(pattern, content)
    
    if match:
        print(f"✅ 定位到函数签名: {match.group(0)}")
        
        # 2. 确定插入点（函数定义行的下一行）
        insertion_point = match.end()
        
        # 3. 自动探测缩进风格 (读取下一行的缩进)
        rest_of_file = content[insertion_point:]
        next_line_match = re.search(r'\n(\s+)\S', rest_of_file)
        indentation = "    " # 默认 4 空格
        if next_line_match:
            indentation = next_line_match.group(1)
            print(f"ℹ️  探测到缩进格式: {len(indentation)} 个空格")
        
        # 4. 构造带缩进的代码块
        # 将我们的代码块按行分割，每一行都加上探测到的缩进
        lines = SERVER_PATCH_B1.strip().split('\n')
        indented_code = "\n" + "\n".join([indentation + line for line in lines]) + "\n"
        
        # 5. 执行插入
        # 放在函数体最前面，确保它优先执行
        new_content = content[:insertion_point] + indented_code + content[insertion_point:]
        
        # 6. 防止重复插入 (简单检查)
        if "B1 - Shopping Checkout Logic (Injected by Robust Patcher)" in content:
            print("⚠️  检测到补丁已存在，正在覆盖/更新...")
            # 如果想做完美覆盖比较复杂，这里我们假设如果脚本再次运行，我们不重复插入
            # 或者为了简单，我们先用 replace 移除旧的（如果有），再插入新的
            # 但最简单的方法是：如果已存在，提示用户手动检查或重启
            print("   (为安全起见，本次脚本将跳过重复插入。如果仍有问题，请手动检查 server.py)")
            return

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ server.py 已成功修补！")
        
    else:
        print("❌ 严重错误: 无法通过正则在 server.py 中找到 'def mutate_env(...):'")
        print("   请检查 server.py 文件内容是否被意外修改。")

if __name__ == "__main__":
    print("🚀 开始修复 B1 后端逻辑...")
    patch_server()