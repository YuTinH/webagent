import os
import re

# ================= 1. Common.js (强制覆盖为代理兼容版) =================
COMMON_JS_CONTENT = r'''
function qs(s){return document.querySelector(s)}; function qsa(s){return Array.from(document.querySelectorAll(s))};

// 使用 XHR 替代 fetch 避免流锁定问题
function api(path, method='GET', data=null){
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, path);
    if (data) xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            try { resolve(xhr.responseText ? JSON.parse(xhr.responseText) : {}); } 
            catch (e) { resolve({}); }
        } else { reject(new Error(`API Error ${xhr.status}`)); }
    };
    xhr.onerror = () => reject(new Error('Network Error'));
    xhr.send(data ? JSON.stringify(data) : null);
  });
}

function getApiRoot() { return window.RelRoot || '../'; }
async function loadEnv(){ return await api(getApiRoot() + 'api/env'); }

function toast(msg){ 
    const t=qs('#__toast'); 
    if(t) { t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1800); }
}

async function send(taskId, action, payload){
  const root = getApiRoot();
  try { await api(root + 'api/trace','POST',{task_id:taskId, action, payload, url:location.pathname, ts:Date.now()}); } catch(e){}
  
  try {
      const data = await api(root + 'api/mutate','POST',{task_id:taskId, action, payload});
      
      // --- 关键修复：代理环境重定向 ---
      if (data.redirect) {
          console.log("Server requested redirect to:", data.redirect);
          
          // 如果是相对路径 (e.g. "order.html")，直接跳转，浏览器会自动处理
          if (!data.redirect.startsWith('/')) {
              location.href = data.redirect;
          } 
          // 如果是绝对路径 (e.g. "/shop.local/order.html")，必须手动转为相对
          else {
              // 假设当前在 sites/shop.local/cart.html，我们要去 sites/shop.local/order.html
              // 简单粗暴的方法：去掉开头的斜杠，拼接到 apiRoot (通常是 ../) 后面? 
              // 不，最稳妥的是去掉路径的前缀，只保留文件名。
              // 但为了兼容，我们尝试将其转换为相对于当前目录的路径
              const filename = data.redirect.split('/').pop();
              console.log("Force converting absolute path to relative:", filename);
              location.href = filename;
          }
      } else {
          toast('操作成功');
          // 重新渲染页面
          if(typeof render === 'function') await render();
      }
  } catch (e) {
      console.error('Mutation failed', e);
      alert('操作失败: ' + e.message);
  }
}

// 简单的 Distractor Stub 避免报错
class DistractorEngine { constructor(){this.init()} async init(){} }
document.addEventListener('DOMContentLoaded', () => { window.distractorEngine = new DistractorEngine(); if(typeof render === 'function') render(); });
'''

# ================= 2. Server.py (强制重写 B1 逻辑) =================
# 注意：我们这里使用相对路径 "order.html"
NEW_B1_LOGIC = r'''
    # B1 - Shopping Checkout Logic (Fixed Relative Path)
    if task_id.startswith('B1') and action == 'checkout':
        try:
            import time
            from datetime import datetime
            items = payload.get('items', [])
            total = sum([float(i.get('price', 0)) * int(i.get('qty', 1)) for i in items])
            order_id = "ORD-" + str(int(time.time()))[-6:]
            
            new_order = {
                "id": order_id, "items": items, "total": total,
                "status": "confirmed", "date": datetime.now().isoformat()
            }
            
            shop_state = env.get('shop', {})
            shop_state['cart'] = [] 
            if 'orders' not in shop_state: shop_state['orders'] = {}
            shop_state['orders'][order_id] = new_order
            env['shop'] = shop_state
            
            # --- 关键：返回纯文件名，让前端在当前目录下跳转 ---
            return env, {"redirect": "order.html"}
        except Exception as e:
            print(f"B1 Error: {e}")
            return env, {}
'''

def update_common_js():
    print("Overwrite sites/static/common.js...")
    with open('sites/static/common.js', 'w', encoding='utf-8') as f:
        f.write(COMMON_JS_CONTENT)

def update_server():
    path = 'server.py'
    print(f"Patching {path}...")
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    in_mutate = False
    b1_inserted = False
    
    # 逐行扫描
    for line in lines:
        # 1. 找到 mutate_env 函数定义
        if "def mutate_env" in line:
            new_lines.append(line)
            in_mutate = True
            # 在函数定义下一行立即插入新的 B1 逻辑
            new_lines.append(NEW_B1_LOGIC + "\n")
            b1_inserted = True
            continue
            
        # 2. 如果检测到旧的 B1 逻辑（以 if task_id.startswith('B1') 开头），跳过它
        if in_mutate and "if task_id.startswith('B1')" in line:
            # 跳过这一行，并且跳过后续直到下一个 if 或 return 的行？
            # 简单的正则剔除比较难，这里我们使用一个标记来跳过整个块
            # 但最简单的方法是：只要我们已经在开头插入了 B1 逻辑，
            # 旧的逻辑在下面即使存在，也会因为 env 已经被修改或者逻辑重复而覆盖，
            # 只要我们确保新的逻辑有 return。
            # 为了保险，我们把旧行注释掉
            new_lines.append("# " + line) # Comment out old logic
            continue
            
        new_lines.append(line)
    
    if not b1_inserted:
        print("❌ 警告：未找到 mutate_env 函数，无法修补 server.py")
        return

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✅ Server.py 已修补（B1 逻辑已更新为相对路径）。")

def update_cart_html():
    path = 'sites/shop.local/cart.html'
    print(f"Updating {path}...")
    if not os.path.exists(path): return
    
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 确保调用的是正确的 action
    if "send('B1-shopping', 'checkout'" not in html:
        # 替换旧的调用
        html = html.replace("send('B1-shopping', 'order'", "send('B1-shopping', 'checkout'")
        
    # 确保没有硬编码的 window.location
    if "window.location.href =" in html:
        print("   Removing hardcoded redirects from cart.html...")
        html = re.sub(r'window\.location\.href\s*=\s*["\'].*?["\']', '// Redirect handled by common.js', html)
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    print("🚀 正在执行 B1 任务强制修复...")
    update_common_js()
    update_server()
    update_cart_html()
    print("\n" + "="*50)
    print("✅ 修复脚本执行完毕！请务必执行以下 3 步：")
    print("1. [重启后端] 在终端按 Ctrl+C 停止 server.py，然后重新运行: python3 server.py")
    print("2. [清除缓存] 在浏览器中按 Shift + F5 (或 Cmd+Shift+R) 强制刷新 cart.html")
    print("3. [重新测试] 点击“去结算”")
    print("="*50)