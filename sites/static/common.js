/**
 * Common utilities for WebAgent Dynamic Suite
 * Final Robust Edition for Proxy/Local Environments
 */

function getRelRoot() {
    return window.RelRoot || './';
}

function resolveTaskId(pageTaskId) {
    try {
        const runtimeBindingTaskId = String(window.__WEBAGENT_BINDING_TASK_ID__ || '').trim();
        if (runtimeBindingTaskId) return runtimeBindingTaskId;
    } catch (e) {}
    try {
        const runtimeTaskId = String(window.__WEBAGENT_TASK_ID__ || '').trim();
        if (runtimeTaskId) return runtimeTaskId;
    } catch (e) {}
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const queryTaskId = String(urlParams.get('task_id') || '').trim();
        if (queryTaskId) return queryTaskId;
        const legacyTaskId = String(urlParams.get('task') || '').trim();
        if (legacyTaskId) return legacyTaskId;
    } catch (e) {}
    return pageTaskId;
}

function getRuntimeTaskInputs() {
    try {
        const payload = window.__WEBAGENT_TASK_INPUTS__;
        if (payload && typeof payload === 'object') {
            return payload;
        }
    } catch (e) {}
    return {};
}

function getTaskInputValue(key, fallback = '') {
    try {
        const inputs = getRuntimeTaskInputs();
        const value = inputs[key];
        if (value === undefined || value === null || value === '') {
            return fallback;
        }
        return value;
    } catch (e) {}
    return fallback;
}

async function send(task_id, action, payload = {}) {
    const relRoot = getRelRoot();
    const apiURL = relRoot + 'api/mutate';
    const effectiveTaskId = resolveTaskId(task_id);
    
    if (effectiveTaskId !== task_id) {
        console.log(`[Action] ${effectiveTaskId} (page:${task_id}): ${action}`, payload, "=>", apiURL);
    } else {
        console.log(`[Action] ${effectiveTaskId}: ${action}`, payload, "=>", apiURL);
    }
    
    try {
        const response = await fetch(apiURL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: effectiveTaskId, action, payload })
        });
        
        const data = await response.json();
        
        if (data.redirect) {
            console.log("Redirect requested:", data.redirect);
            let target = data.redirect;
            if (target.startsWith('/')) {
                target = relRoot + target.substring(1);
            }
            window.location.href = target;
        }
        return data;
    } catch (e) {
        console.error('Action failed:', e);
        return { success: false, error: e.message };
    }
}

async function loadEnv() {
    const relRoot = getRelRoot();
    try {
        const res = await fetch(relRoot + 'api/env');
        return await res.json();
    } catch (e) {
        return {};
    }
}

// Global UI Helpers
window.Toast = {
    info: (m) => showToast(m, 'info'),
    success: (m) => showToast(m, 'success'),
    error: (m) => showToast(m, 'error')
};

function showToast(m, type) {
    let t = document.getElementById('__toast');
    if (!t) {
        t = document.createElement('div');
        t.id = '__toast';
        t.className = 'toast';
        document.body.appendChild(t);
    }
    t.textContent = m;
    t.className = `toast show ${type}`;
    setTimeout(() => t.classList.remove('show'), 3000);
}

// ID Proxy for Obfuscation Compatibility
(function() {
    const original = Document.prototype.getElementById;
    Document.prototype.getElementById = function(id) {
        const el = original.call(this, id);
        if (el || !id) return el;
        return this.querySelector(`[data-original-id="${id}"]`);
    };
})();

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('obfuscate') === 'true') {
        const seedParam = urlParams.get('obf_seed');
        let rand = Math.random;
        if (seedParam !== null) {
            let seed = 2166136261 >>> 0;
            const seedText = `${seedParam}|${window.location.pathname}`;
            for (let i = 0; i < seedText.length; i++) {
                seed ^= seedText.charCodeAt(i);
                seed = Math.imul(seed, 16777619);
            }
            rand = (() => {
                let t = seed >>> 0;
                return () => {
                    t += 0x6D2B79F5;
                    let x = t;
                    x = Math.imul(x ^ (x >>> 15), x | 1);
                    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
                    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
                };
            })();
        }
        document.querySelectorAll('button[id], input[id], select[id]').forEach(el => {
            const oldId = el.id;
            if (!oldId || oldId.startsWith('d-')) return;
            const suffix = Math.floor(rand() * 1679616).toString(36).padStart(4, '0').slice(0, 4);
            const newId = oldId + '_' + suffix;
            el.setAttribute('data-original-id', oldId);
            el.id = newId;
        });
    }
});
