
function qs(s){return document.querySelector(s)}; function qsa(s){return Array.from(document.querySelectorAll(s))};

// 使用 XHR 替代 fetch 避免流锁定问题
function api(path, method='GET', data=null){
  // Resolve path to absolute URL for debugging
  const a = document.createElement('a');
  a.href = path;
  console.log('DEBUG: API Request to:', a.href, 'Method:', method);

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
    xhr.onerror = () => {
        if (completed) return; // Prevent double handling
        completed = true;
        console.error('Network Error during API call to', path, 'Status:', xhr.status, 'Response:', xhr.responseText, 'XHR object:', xhr);
        reject(new Error('Network Error: Could not connect to server or empty response.'));
    };
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
