
function qs(s){return document.querySelector(s)}; function qsa(s){return Array.from(document.querySelectorAll(s))};
async function api(path, method='GET', data=null){
  const opt = {method, headers:{}};
  if (data){ opt.headers['Content-Type']='application/json'; opt.body=JSON.stringify(data); }
  const r = await fetch(path, opt);
  const text = await r.text();
  try {
    return JSON.parse(text);
  } catch (e) {
    console.error('API Error:', path, r.status, text);
    throw new Error(`API response is not JSON. Status: ${r.status}. Body: ${text.substring(0, 100)}...`);
  }
}
async function loadEnv(){ return await api('/api/env'); }
function toast(msg){ const t=qs('#__toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1800); }
function openModal(id){ qs(id).classList.add('open'); }
function closeModal(id){ qs(id).classList.remove('open'); }

async function send(taskId, action, payload){
  const root = window.RelRoot || '../';
  try { await api(root + 'api/trace','POST',{task_id:taskId, action, payload, url:location.pathname, ts:Date.now()}); } catch(e){}
  const data = await api(root + 'api/mutate','POST',{task_id:taskId, action, payload});
  await render(); if (data.redirect) location.href = data.redirect; else toast('已提交操作：'+action);
}

async function render(){
  const env = await loadEnv();
  // Shop B6
  const pp = env?.orders?.["O-98321"]?.claims?.price_protect?.state || 'none';
  if (qs('#pp-state')) { qs('#pp-state').textContent = pp; }
  // Wallet D4
  const last4 = env?.payments?.cards?.active_last4 || '1234';
  if (qs('#active-card')) qs('#active-card').textContent = '****'+last4;
  if (qs('#default-card .last4')) qs('#default-card .last4').textContent = last4;
  qsa('[data-merchant]').forEach(li => {
    const m = li.dataset.merchant; const map = env?.payments?.merchant_bindings?.map || {};
    const bound = map[m] || last4;
    li.textContent = m + ' - ****' + bound;
    li.classList.add('merchant-binding');
    if (bound === last4) {
      li.classList.add('updated');
    } else {
      li.classList.remove('updated');
    }
  });
  // Trip E6
  const st = env?.trips?.PNR9ZZ?.status || 'ticketed';
  if (qs('#ticket-status')) qs('#ticket-status').textContent = st;
  // Permit H3
  const appt = env?.permits?.["RP-2024-77"]?.next_appointment || '未预约';
  if (qs('#appointment')) qs('#appointment').textContent = appt;
  // Energy I5
  const plan = env?.meters?.["M-321"]?.plan || 'standard';
  if (qs('#plan')) qs('#plan').textContent = plan;
}



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
            // this.runSecurityCheck();
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
