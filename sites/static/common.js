function qs(s){return document.querySelector(s)}; function qsa(s){return Array.from(document.querySelectorAll(s))};

// 使用 XMLHttpRequest 替代 fetch，解决 "body stream already read"
function api(path, method='GET', data=null){
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let completed = false; // Flag to ensure resolve/reject is called only once

    xhr.open(method, path);
    if (data) xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onload = () => {
        if (completed) return; // Prevent double handling
        completed = true;

        if (xhr.status >= 200 && xhr.status < 300) {
            try {
                const text = xhr.responseText;
                console.log('DEBUG: API onload success:', xhr.status, text);
                resolve(text ? JSON.parse(text) : {});
            } catch (e) {
                console.error('JSON Parse Error', e, xhr.responseText);
                reject(new Error(`JSON Parse Error: ${e.message}`));
            }
        } else {
            console.error('API Error', path, xhr.status, xhr.responseText);
            reject(new Error(`API Error ${xhr.status}: ${xhr.responseText || 'Unknown error'}`));
        }
    };

    xhr.onerror = () => {
        if (completed) return; // Prevent double handling
        completed = true;
        console.error('Network Error during API call to', path, 'Status:', xhr.status, 'Response:', xhr.responseText);
        reject(new Error('Network Error: Could not connect to server or empty response.'));
    };

    xhr.onabort = () => { // Handle request aborts
        if (completed) return;
        completed = true;
        console.warn('API call aborted for', path);
        reject(new Error('Request aborted.'));
    };

    xhr.send(data ? JSON.stringify(data) : null);
  });
}

// 获取 API 根路径 (兼容代理环境)
function getApiRoot() {
    return window.RelRoot || '../';
}

// 获取完整的基路径，包括可能的代理前缀
function getBaseUrl() {
    const pathParts = window.location.pathname.split('/');
    const proxyIndex = pathParts.indexOf('proxy');
    if (proxyIndex > -1 && pathParts.length > proxyIndex + 1) {
        // Assume format like /ws-xxx/project-yyy/user-zzz/vscode-hash/proxy/8014/
        // We need to capture up to '8014/' or similar pattern after 'proxy'
        const base = pathParts.slice(0, proxyIndex + 2).join('/'); // Includes 'proxy' and the port part
        return `${window.location.origin}${base}/`;
    }
    return window.location.origin + '/';
}


async function loadEnv(){ 
    return await api(getApiRoot() + 'api/env'); 
}

function toast(msg){ 
    const t=qs('#__toast'); 
    if(t) {
        t.textContent=msg; 
        t.classList.add('show'); 
        setTimeout(()=>t.classList.remove('show'),1800); 
    }
}

function openModal(id){ qs(id).classList.add('open'); }
function closeModal(id){ qs(id).classList.remove('open'); }

async function send(taskId, action, payload){
  const root = getApiRoot();
  try { 
      await api(root + 'api/trace','POST',{task_id:taskId, action, payload, url:location.pathname, ts:Date.now()}); 
  } catch(e){}
  
  try {
      const data = await api(root + 'api/mutate','POST',{task_id:taskId, action, payload});
      console.log('DEBUG: API mutate response:', data);
      await render(); 
      
      if (data.redirect) {
          const baseUrl = getBaseUrl();
          // 如果服务器返回的是绝对路径 (e.g., /shop.local/order.html), 我们需要加上代理前缀
          if (data.redirect.startsWith('/')) {
              location.href = baseUrl + data.redirect.substring(1);
          } else {
              location.href = data.redirect; // 否则按原样跳转 (相对路径)
          }
      } else {
          toast('已提交操作：'+action);
      }
      return data;
  } catch (e) {
      console.error('Mutation failed', e);
      toast('操作失败: ' + e.message);
      throw e;
  }
}

async function render(){
  try {
      const env = await loadEnv();
      const pp = env?.orders?.["O-98321"]?.claims?.price_protect?.state || 'none';
      if (qs('#pp-state')) { qs('#pp-state').textContent = pp; }
      const last4 = env?.payments?.cards?.active_last4 || '1234';
      if (qs('#active-card')) qs('#active-card').textContent = '****'+last4;
      if (qs('#default-card .last4')) qs('#default-card .last4').textContent = last4;
      qsa('[data-merchant]').forEach(li => {
        const m = li.dataset.merchant; const map = env?.payments?.merchant_bindings?.map || {};
        const bound = map[m] || last4;
        li.textContent = m + ' - ****' + bound;
        li.classList.add('merchant-binding');
        if (bound === last4) li.classList.add('updated'); else li.classList.remove('updated');
      });
      const st = env?.trips?.PNR9ZZ?.status || 'ticketed';
      if (qs('#ticket-status')) qs('#ticket-status').textContent = st;
      const appt = env?.permits?.["RP-2024-77"]?.next_appointment || '未预约';
      if (qs('#appointment')) qs('#appointment').textContent = appt;
      const plan = env?.meters?.["M-321"]?.plan || 'standard';
      if (qs('#plan')) qs('#plan').textContent = plan;
  } catch(e) {}
}

// Restore rendering
document.addEventListener('DOMContentLoaded', () => { render(); });

/*
// --- Distractor Engine (Disabled) ---
class DistractorEngine {
    constructor() { this.init(); }
    async init() {
        return; // Disabled by user request
        try {
            const root = getApiRoot();
            const res = await api(root + 'api/marketing/promos');
            if (res.success) {
                if (res.cookie_consent_required) this.renderCookieBanner();
                res.promos.forEach(promo => this.renderPromo(promo));
            }
            this.renderChatWidget(); 
        } catch (e) {}
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
// document.addEventListener('DOMContentLoaded', () => { window.distractorEngine = new DistractorEngine(); render(); });
*/