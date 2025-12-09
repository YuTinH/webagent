import os

# ================= 1. 新的入口仪表盘 (Complex Dashboard) =================
NEW_INDEX_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebAgent Simulation Hub</title>
<link rel="stylesheet" href="static/skin.css">
<style>
    body { background: #0f172a; color: #cbd5e1; font-family: 'Inter', sans-serif; display: flex; height: 100vh; overflow: hidden; }
    .sidebar { width: 260px; background: #1e293b; padding: 20px; display: flex; flex-direction: column; border-right: 1px solid #334155; }
    .sidebar h2 { font-size: 18px; color: #fff; margin-bottom: 30px; display: flex; align-items: center; gap: 10px; }
    .menu-item { padding: 12px; margin-bottom: 5px; border-radius: 8px; cursor: pointer; color: #94a3b8; text-decoration: none; display: flex; align-items: center; gap: 10px; transition: .2s; }
    .menu-item:hover, .menu-item.active { background: #334155; color: #fff; }
    .main { flex: 1; padding: 40px; overflow-y: auto; }
    .status-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 40px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; position: relative; overflow: hidden; }
    .card h3 { color: #94a3b8; font-size: 14px; margin: 0 0 10px 0; }
    .card .val { font-size: 28px; font-weight: bold; color: #fff; }
    .card::after { content: ''; position: absolute; right: -20px; top: -20px; width: 100px; height: 100px; background: rgba(99, 102, 241, 0.1); border-radius: 50%; blur: 20px; }
    .service-link { display: block; background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; padding: 30px; border-radius: 16px; text-decoration: none; transition: .3s; position: relative; }
    .service-link:hover { transform: translateY(-5px); border-color: #6366f1; box-shadow: 0 10px 30px -10px rgba(99, 102, 241, 0.3); }
    .service-link h2 { color: #fff; margin: 0 0 10px 0; font-size: 24px; }
    .service-link p { color: #64748b; margin: 0; }
    .service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .badge.green { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .badge.yellow { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
</style>
</head>
<body>

<div class="sidebar">
    <h2>⚡️ AgentHub <span style="font-size:10px; opacity:0.5">v2.1</span></h2>
    <a href="#" class="menu-item active">📊 Dashboard</a>
    <a href="#" class="menu-item">📡 Network Status</a>
    <a href="#" class="menu-item">📝 API Logs</a>
    <div style="flex:1"></div>
    <div class="menu-item">⚙️ Settings</div>
</div>

<div class="main">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px">
        <h1 style="color:#fff; margin:0">System Overview</h1>
        <div style="display:flex; gap:10px">
            <span class="badge green">● Systems Operational</span>
            <span class="badge yellow">⚠ Low Latency</span>
        </div>
    </div>

    <div class="status-grid">
        <div class="card">
            <h3>ACTIVE SESSIONS</h3>
            <div class="val">1,204</div>
            <div style="color:#10b981; font-size:12px; margin-top:5px">▲ 12% vs last hour</div>
        </div>
        <div class="card">
            <h3>AVG RESPONSE</h3>
            <div class="val">42ms</div>
            <div style="color:#64748b; font-size:12px; margin-top:5px">Optimal range</div>
        </div>
        <div class="card">
            <h3>ERROR RATE</h3>
            <div class="val">0.01%</div>
            <div style="color:#10b981; font-size:12px; margin-top:5px">Stable</div>
        </div>
    </div>

    <h2 style="color:#fff; margin-bottom:20px">Environment Access</h2>
    <div class="service-grid">
        <a href="shop.local/index.html" class="service-link">
            <div style="font-size:32px; margin-bottom:15px">🛍️</div>
            <h2>Shop.local</h2>
            <p>E-commerce platform simulation. <br><span style="color:#6366f1">Status: Online</span></p>
        </a>
        <a href="bank.local/dashboard.html" class="service-link">
            <div style="font-size:32px; margin-bottom:15px">🏦</div>
            <h2>Bank.local</h2>
            <p>Financial services portal. <br><span style="color:#6366f1">Status: Online</span></p>
        </a>
        <a href="gov.local/index.html" class="service-link">
            <div style="font-size:32px; margin-bottom:15px">🏛️</div>
            <h2>Gov.local</h2>
            <p>Public services & utilities. <br><span style="color:#6366f1">Status: Online</span></p>
        </a>
    </div>
</div>

<script>
// Dynamic noise: Update numbers randomly
setInterval(() => {
    const els = document.querySelectorAll('.val');
    els.forEach(el => {
        if(Math.random() > 0.7) {
            let val = parseInt(el.innerText.replace(/\D/g,''));
            val += Math.floor(Math.random() * 10) - 5;
            if(el.innerText.includes('ms')) el.innerText = val + 'ms';
            else if(el.innerText.includes('%')) el.innerText = (Math.random()*0.1).toFixed(2) + '%';
            else el.innerText = val.toLocaleString();
        }
    });
}, 2000);
</script>

</body>
</html>
'''

# ================= 2. 轮播图组件 (Carousel Logic) =================
CAROUSEL_CSS = r'''
/* Carousel Styles */
.carousel-container { position: relative; overflow: hidden; border-radius: 16px; margin-bottom: 32px; height: 320px; box-shadow: var(--shadow-lg); }
.carousel-track { display: flex; transition: transform 0.5s ease-in-out; height: 100%; }
.carousel-slide { min-width: 100%; height: 100%; position: relative; display: flex; align-items: center; justify-content: center; background-size: cover; background-position: center; }
.carousel-content { text-align: center; color: white; z-index: 2; text-shadow: 0 2px 10px rgba(0,0,0,0.5); padding: 20px; background: rgba(0,0,0,0.3); backdrop-filter: blur(4px); border-radius: 12px; }
.carousel-btn { position: absolute; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.2); border: none; color: white; padding: 16px; cursor: pointer; border-radius: 50%; backdrop-filter: blur(4px); transition: .2s; z-index: 10; }
.carousel-btn:hover { background: white; color: black; }
.carousel-btn.prev { left: 20px; }
.carousel-btn.next { right: 20px; }
.carousel-dots { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); display: flex; gap: 8px; z-index: 10; }
.carousel-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.4); cursor: pointer; transition: .2s; }
.carousel-dot.active { background: white; width: 24px; border-radius: 4px; }
'''

CAROUSEL_HTML = r'''
  <div class="carousel-container" id="hero-carousel">
    <div class="carousel-track">
      <div class="carousel-slide" style="background: linear-gradient(135deg, #4f46e5, #ec4899)">
        <div class="carousel-content">
            <h1 style="font-size:48px; margin:0">年度科技盛典</h1>
            <p style="font-size:20px">全场电子产品低至 5 折</p>
            <button class="btn pri" style="margin-top:16px; font-size:16px" onclick="filterCategory('electronics')">立即抢购</button>
        </div>
      </div>
      <div class="carousel-slide" style="background: linear-gradient(135deg, #059669, #3b82f6)">
        <div class="carousel-content">
            <h1 style="font-size:48px; margin:0">新书首发</h1>
            <p style="font-size:20px">《Web Agent 编程指南》限量预售</p>
            <button class="btn pri" style="margin-top:16px; font-size:16px" onclick="filterCategory('books')">查看详情</button>
        </div>
      </div>
      <div class="carousel-slide" style="background: linear-gradient(135deg, #f59e0b, #ef4444)">
        <div class="carousel-content">
            <h1 style="font-size:48px; margin:0">会员专享</h1>
            <p style="font-size:20px">注册即送 $50 优惠券</p>
            <button class="btn pri" style="margin-top:16px; font-size:16px">免费注册</button>
        </div>
      </div>
    </div>
    <button class="carousel-btn prev" onclick="moveCarousel(-1)">❮</button>
    <button class="carousel-btn next" onclick="moveCarousel(1)">❯</button>
    <div class="carousel-dots">
        <div class="carousel-dot active" onclick="setCarousel(0)"></div>
        <div class="carousel-dot" onclick="setCarousel(1)"></div>
        <div class="carousel-dot" onclick="setCarousel(2)"></div>
    </div>
  </div>
'''

# ================= 3. 安全检查 (Security Interstitial) =================
# 添加到 Common.js 的 init 逻辑中
SECURITY_CHECK_JS = r'''
    // --- Simulated Security Check (Cloudflare style) ---
    async runSecurityCheck() {
        // 10% chance to trigger full page block on load
        if (Math.random() > 0.1) return; 
        
        const overlay = document.createElement('div');
        overlay.id = 'security-check-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:#000;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;font-family:sans-serif';
        overlay.innerHTML = `
            <div style="font-size:40px;margin-bottom:20px">🛡️</div>
            <h2 style="margin-bottom:10px">Verifying you are human...</h2>
            <p style="color:#888">This process is automatic. Please wait.</p>
            <div style="width:200px;height:4px;background:#333;margin-top:20px;border-radius:2px;overflow:hidden">
                <div style="width:0%;height:100%;background:#10b981;transition:width 2s ease" id="sec-progress"></div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        // Fake loading process
        setTimeout(() => document.getElementById('sec-progress').style.width = '70%', 500);
        setTimeout(() => document.getElementById('sec-progress').style.width = '100%', 1500);
        setTimeout(() => {
            overlay.remove();
            Toast.success('Verification Complete');
        }, 2000);
    }
'''

def update_file(path, content, mode='w'):
    with open(path, mode, encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Updated {path}")

def patch_shop_index():
    path = 'sites/shop.local/index.html'
    if not os.path.exists(path): return
    
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 1. 替换原有的 Hero Section
    if '<div class="hero">' in html:
        # 移除旧的 Hero
        import re
        html = re.sub(r'<div class="hero">[\s\S]*?</div>', CAROUSEL_HTML, html)
        
        # 添加 Carousel JS
        script = r'''
<script>
let currentSlide = 0;
const slides = document.querySelectorAll('.carousel-slide');
const dots = document.querySelectorAll('.carousel-dot');
const track = document.querySelector('.carousel-track');

function updateCarousel() {
    track.style.transform = `translateX(-${currentSlide * 100}%)`;
    dots.forEach((dot, i) => dot.classList.toggle('active', i === currentSlide));
}

function moveCarousel(n) {
    currentSlide = (currentSlide + n + slides.length) % slides.length;
    updateCarousel();
}

function setCarousel(n) {
    currentSlide = n;
    updateCarousel();
}

// Auto play
setInterval(() => moveCarousel(1), 5000);
</script>
'''
        html = html.replace('</body>', script + '\n</body>')
        update_file(path, html)

def patch_css():
    path = 'sites/static/skin.css'
    with open(path, 'r', encoding='utf-8') as f:
        css = f.read()
    if '.carousel-container' not in css:
        update_file(path, css + '\n' + CAROUSEL_CSS)

def patch_common_js():
    path = 'sites/static/common.js'
    with open(path, 'r', encoding='utf-8') as f:
        js = f.read()
    
    # Insert runSecurityCheck into DistractorEngine
    if 'renderChatWidget() {' in js and 'runSecurityCheck' not in js:
        # Add the method
        js = js.replace('renderChatWidget() {', SECURITY_CHECK_JS + '\n    renderChatWidget() {')
        # Call it in init
        js = js.replace('this.renderChatWidget();', 'this.renderChatWidget(); this.runSecurityCheck();')
        update_file(path, js)

if __name__ == "__main__":
    print("🚀 Optimizing Main Pages...")
    
    # 1. Rewrite Dashboard
    update_file('sites/index.html', NEW_INDEX_HTML)
    
    # 2. Add Carousel to Shop
    patch_css()
    patch_shop_index()
    
    # 3. Add Security Check
    patch_common_js()
    
    print("✨ Optimization Complete! Restart server to see changes.")