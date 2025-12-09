import os
import re

# ================= 配置部分 =================

# 1. Server.py 的新增代码片段 (营销 API)
SERVER_PATCH = r'''
        # ========================================================================
        # Marketing / Distractors API (Added by AI)
        # ========================================================================
        if self.path.startswith('/api/marketing/promos'):
            promos = [
                {"type": "banner_top", "content": "⚡️ 限时特惠：全场满$500减$50！", "color": "#ef4444"},
                {"type": "popup_center", "content": "订阅简报，立享9折优惠", "delay": 2000},
                {"type": "toast_bottom", "content": "有人刚刚购买了 iPhone 15 Pro", "delay": 5000},
                {"type": "sidebar_ad", "content": "新书上架：《Web Agent 指南》", "img": "book.jpg"}
            ]
            import random
            active_promos = random.sample(promos, k=random.randint(1, 3))
            
            data = json.dumps({
                'success': True,
                'promos': active_promos,
                'cookie_consent_required': True
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_cors_headers(); self.end_headers()
            self.wfile.write(data); return

'''

# 2. Common.js 的新增代码片段 (干扰引擎)
JS_PATCH = r'''
// --- Distractor Engine (Added by AI) ---
class DistractorEngine {
    constructor() { this.init(); }
    async init() {
        try {
            const res = await api('/api/marketing/promos');
            if (res.success) {
                if (res.cookie_consent_required) this.renderCookieBanner();
                res.promos.forEach(promo => this.renderPromo(promo));
            }
            this.renderChatWidget();
        } catch (e) { console.log('Marketing system offline'); }
    }
    renderTopBanner(content, color) {
        const b = document.createElement('div');
        b.className = 'promo-banner-top';
        b.style.cssText = `background:${color};color:white;text-align:center;padding:10px;font-size:14px;position:relative;animation:slideDown 0.5s ease;z-index:1001;`;
        b.innerHTML = `<span>${content}</span><button onclick="this.parentElement.remove()" style="background:none;border:none;color:white;float:right;cursor:pointer;font-weight:bold">✕</button>`;
        document.body.prepend(b);
    }
    renderCookieBanner() {
        const d = document.createElement('div');
        d.className = 'cookie-consent-banner';
        d.innerHTML = `<div style="flex:1">我们使用 Cookie 来提升体验。<a href="#">隐私政策</a></div><div style="display:flex;gap:10px"><button class="btn" onclick="this.parentElement.parentElement.remove()">拒绝</button><button class="btn pri" onclick="this.parentElement.parentElement.remove()">接受</button></div>`;
        document.body.appendChild(d);
    }
    renderPopup(content, delay) {
        setTimeout(() => {
            const id = 'promo-' + Date.now();
            document.body.insertAdjacentHTML('beforeend', `<div id="${id}" class="modal-overlay open" style="z-index:9999"><div class="modal-container" style="text-align:center"><h3>限时福利</h3><p>${content}</p><button class="btn pri" onclick="document.getElementById('${id}').remove()">领取</button></div></div>`);
        }, delay);
    }
    renderChatWidget() {
        const w = document.createElement('div');
        w.className = 'chat-widget-floating';
        w.innerHTML = '💬';
        w.onclick = function() { this.classList.toggle('expanded'); if(this.classList.contains('expanded')) this.innerHTML='<div>客服在线</div><input placeholder="输入消息...">'; else this.innerHTML='💬'; };
        document.body.appendChild(w);
    }
    renderPromo(p) {
        if (p.type === 'banner_top') this.renderTopBanner(p.content, p.color);
        if (p.type === 'popup_center') this.renderPopup(p.content, p.delay);
    }
}
document.addEventListener('DOMContentLoaded', () => { window.distractorEngine = new DistractorEngine(); render(); });
'''

# 3. Skin.css 的新增代码片段 (干扰项样式)
CSS_PATCH = r'''
/* --- Distractors & Noise Styles --- */
.cookie-consent-banner { position: fixed; bottom: 0; left: 0; right: 0; background: var(--panel-elevated); border-top: 1px solid var(--border); padding: 16px 24px; z-index: 9000; display: flex; align-items: center; gap: 24px; box-shadow: 0 -4px 20px rgba(0,0,0,0.2); animation: slideUp 0.5s ease; }
.chat-widget-floating { position: fixed; bottom: 24px; right: 24px; width: 60px; height: 60px; background: var(--pri); border-radius: 30px; box-shadow: var(--shadow-lg); display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 8000; transition: all 0.3s; color: white; font-size: 24px; }
.chat-widget-floating:hover { transform: scale(1.1); }
.chat-widget-floating.expanded { width: 300px; height: 300px; border-radius: 12px; flex-direction: column; align-items: stretch; justify-content: flex-start; padding: 16px; background: var(--panel); border: 1px solid var(--border); cursor: default; font-size: 14px; }
@keyframes slideDown { from { transform: translateY(-100%); } to { transform: translateY(0); } }
@keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
.product-card.sponsored { border-color: var(--warn-bg); background: linear-gradient(to bottom right, var(--card), rgba(245, 158, 11, 0.05)); }
.product-card.sponsored::after { content: '广告'; position: absolute; bottom: 8px; right: 8px; font-size: 10px; color: var(--muted); border: 1px solid var(--border); padding: 2px 4px; border-radius: 4px; }
'''

# 4. renderProducts 函数替换 (Shop Index)
NEW_RENDER_FUNC = r'''
function renderProducts(products) {
  const grid = document.getElementById('products-grid');
  const fakeProduct = { product_id: 99999, sku: 'AD-001', name: '【推广】超强性能笔记本 (Sponsored)', price: 2999.00, original_price: 3500.00, category: 'electronics', stock: 100, is_ad: true };
  if (Math.random() > 0.3) products.splice(Math.floor(Math.random() * 3), 0, fakeProduct);

  grid.innerHTML = products.map(product => {
    const icon = getCategoryIcon(product.category);
    const hasStock = product.stock > 0;
    const isLowStock = product.stock < 10;
    const discount = product.original_price ? Math.round((1 - product.price / product.original_price) * 100) : 0;
    const inWishlist = isInWishlist(product.product_id);
    const adClass = product.is_ad ? 'sponsored' : '';
    const clickAction = product.is_ad ? "Toast.info('这是一个广告链接')" : `window.location.href='../shop.local/product/${product.sku}'`;

    return `
      <div onclick="${clickAction}" class="product-card product-item ${adClass}" data-product-id="${product.product_id}" style="cursor:pointer; display:block; position:relative; text-decoration:none; color:var(--text);">
        ${product.is_ad ? '' : `
            ${discount > 0 ? `<div class="sale-badge" style="position:absolute;top:12px;left:12px;background:var(--err);color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;z-index:10">${discount}% OFF</div>` : ''}
            <div class="product-card-actions">
              <button class="wishlist-btn ${inWishlist ? 'active' : ''}" onclick="event.stopPropagation(); toggleWishlist(${product.product_id}, ${JSON.stringify(product).replace(/"/g, '&quot;')})">${inWishlist ? '❤️' : '🤍'}</button>
            </div>
        `}
        <div class="product-image"><div style="font-size:64px">${icon}</div></div>
        <div class="product-info">
          <div class="product-name product-link">${escapeHtml(product.name)}</div>
          <div class="product-price"><span class="price-current">¥${product.price.toFixed(2)}</span>${product.original_price ? `<span class="price-original">¥${product.original_price.toFixed(2)}</span>` : ''}</div>
          <div class="product-meta">${product.is_ad ? '<div style="color:var(--muted)">赞助商链接</div>' : `<div class="stock-status"><span class="stock-dot ${isLowStock ? 'low' : ''}"></span>${hasStock ? (isLowStock ? `仅剩${product.stock}件` : '有货') : '缺货'}</div>`}</div>
        </div>
      </div>
    `;
  }).join('');
}
'''

def update_file(path, operation, content):
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        original = f.read()
    
    new_content = original
    if operation == 'append':
        if "Distractor Engine" not in original and "Distractors & Noise Styles" not in original: # Simple duplicate check
            new_content = original + "\n" + content
            print(f"✅ Appended to {path}")
        else:
            print(f"⚠️  Skipping {path} (already patched?)")
            return
            
    elif operation == 'insert_before':
        marker, patch = content
        if "/api/marketing/promos" not in original:
            new_content = original.replace(marker, patch + marker)
            print(f"✅ Inserted API into {path}")
        else:
             print(f"⚠️  Skipping {path} (already patched?)")
             return

    elif operation == 'replace_func':
        # Simple naive replacement for the specific function
        pattern = r'function renderProducts\(products\)\s*\{[\s\S]*?\n\}'
        if "sponsored" not in original:
            new_content = re.sub(pattern, content.strip(), original)
            print(f"✅ Updated function in {path}")
        else:
            print(f"⚠️  Skipping {path} (already patched?)")
            return

    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)

# 执行更新
if __name__ == "__main__":
    print("🚀 Starting WebAgent Distractor Injection...")
    
    # 1. Update Server
    update_file('server.py', 'insert_before', ('if self.path.startswith(\'/api/task_executions\'):', SERVER_PATCH))
    
    # 2. Update JS
    # Remove the old listener if appending (simplification for script)
    with open('sites/static/common.js', 'r', encoding='utf-8') as f:
        js_content = f.read()
    js_content = js_content.replace("document.addEventListener('DOMContentLoaded', render);", "")
    with open('sites/static/common.js', 'w', encoding='utf-8') as f:
        f.write(js_content)
    update_file('sites/static/common.js', 'append', JS_PATCH)
    
    # 3. Update CSS
    update_file('sites/static/skin.css', 'append', CSS_PATCH)
    
    # 4. Update HTML
    update_file('sites/shop.local/index.html', 'replace_func', NEW_RENDER_FUNC)
    
    print("\n✨ All Done! Restart your server to see the changes.")