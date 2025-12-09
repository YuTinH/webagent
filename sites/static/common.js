
function qs(s){return document.querySelector(s)}; function qsa(s){return Array.from(document.querySelectorAll(s))};
async function api(path, method='GET', data=null){
  const opt = {method, headers:{}};
  if (data){ opt.headers['Content-Type']='application/json'; opt.body=JSON.stringify(data); }
  const r = await fetch(path, opt); return await r.json();
}
async function loadEnv(){ return await api('/api/env'); }
function toast(msg){ const t=qs('#__toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1800); }
function openModal(id){ qs(id).classList.add('open'); }
function closeModal(id){ qs(id).classList.remove('open'); }

async function send(taskId, action, payload){
  try { await api('/api/trace','POST',{task_id:taskId, action, payload, url:location.pathname, ts:Date.now()}); } catch(e){}
  const data = await api('/api/mutate','POST',{task_id:taskId, action, payload});
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
document.addEventListener('DOMContentLoaded', render);
