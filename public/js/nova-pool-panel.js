/* nova-pool-panel.js — shared helpers for the pool-drain panels.
 *
 * PURE dedup: the six pool panels (nova-taskly2fa, nova-tasklycookie,
 * nova-fastpay2fa, nova-paygopool, nova-paygocookie, nova-paygo2fa) used to
 * carry byte-identical copies of esc() / toast() / statCard() / the SSE log
 * buffer / the POST wrapper / the SSE subscription. They now share this file.
 *
 * Nothing here changes a DOM id, a route, a task string or an API payload —
 * the panels keep all of their own logic and call these helpers instead.
 */
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function toast(msg, kind, ms) {
    if (typeof window.showToast === 'function') { try { window.showToast(msg, kind || 'info'); return; } catch (e) {} }
    var host = document.getElementById('toast-container');
    if (!host) return;
    var el = document.createElement('div');
    el.className = 'toast ' + (kind || 'info');
    el.style.cssText = 'position:relative;padding:10px 12px;margin-top:8px;' +
      'border-left:3px solid #f59e0b;border-radius:8px;background:#111726;' +
      'color:#e2e8f0;font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,.45);';
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(function () { try { host.removeChild(el); } catch (e) {} }, ms || 9000);
  }

  function statCard(label, id, sub, color) {
    return '<div class="insta-stat-card" style="background:var(--bg-card);' +
             'border:1px solid var(--border-color);border-radius:var(--radius-md);' +
             'padding:14px 16px;position:relative;overflow:hidden;">' +
      '<div style="position:absolute;left:0;top:0;bottom:0;width:3px;background:' + color + ';opacity:.9;"></div>' +
      '<div class="insta-stat-label" style="color:var(--text-dim);">' + esc(label) + '</div>' +
      '<div class="insta-stat-value" id="' + id + '" style="color:var(--text-main);">0</div>' +
      '<div class="insta-stat-sub" style="color:var(--text-muted);">' + esc(sub) + '</div></div>';
  }

  /* In-memory log buffer shared by every pool panel. `push` prepends a
   * `[time] ` prefix and, once the buffer exceeds `max`, keeps only the last
   * 400 entries (matching the panels' original slice(-400)). */
  function logBuffer(max) {
    var arr = [];
    var limit = max || 500;
    return {
      push: function (line) {
        var entry = '[' + new Date().toLocaleTimeString() + '] ' + line;
        arr.push(entry);
        if (arr.length > limit) arr = arr.slice(-400);
        return entry;
      },
      text: function () { return arr.join('\n'); },
      clear: function () { arr = []; }
    };
  }

  /* The panels' POST wrapper: log the request/response through `onLog`, toast
   * on an error payload, schedule `onDone` (their refresh) and resolve with the
   * parsed JSON. */
  function postJson(url, body, onLog, onDone) {
    if (typeof onLog === 'function') onLog('> POST ' + url + ' ' + JSON.stringify(body || {}));
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (typeof onLog === 'function') onLog('< ' + JSON.stringify(j));
        if (j && (j.error || j.status === 'ERROR')) toast(j.error || 'Request failed', 'error', 12000);
        if (typeof onDone === 'function') setTimeout(onDone, 400);
        return j;
      })
      .catch(function (e) {
        if (typeof onLog === 'function') onLog('! ' + e);
        toast('Request failed: ' + e, 'error', 12000);
      });
  }

  /* Route the shared SSE hub (nova-core.js) or a single fallback EventSource to
   * `handler`. `key` (e.g. 'pgp') scopes the guard flags so a panel never
   * double-subscribes. Both single events and the {type:'batch',items:[...]}
   * envelope are delivered to the handler. */
  function subscribe(handler, key) {
    if (typeof handler !== 'function') return;
    key = key || 'pool';
    var sharedFlag = '__' + key + 'EsShared';
    var esFlag = '__' + key + 'Es';
    try {
      if (!window[sharedFlag] && typeof window.__novaEsSubscribe === 'function') {
        window[sharedFlag] = true;
        window.__novaEsSubscribe(handler);
      } else if (!window[esFlag] && typeof window.__novaEsSubscribe !== 'function') {
        window[esFlag] = new EventSource('/api/meta-insta/events');
        window[esFlag].onmessage = function (ev) {
          try {
            var d = JSON.parse(ev.data);
            if (d && d.type === 'batch' && Array.isArray(d.items)) {
              for (var i = 0; i < d.items.length; i++) { try { handler(d.items[i]); } catch (e) {} }
              return;
            }
            handler(d);
          } catch (e) {}
        };
      }
    } catch (e) {}
  }

  window.NovaPoolPanel = {
    esc: esc,
    toast: toast,
    statCard: statCard,
    logBuffer: logBuffer,
    postJson: postJson,
    subscribe: subscribe
  };
})();
