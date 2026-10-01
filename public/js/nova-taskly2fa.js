/* nova-taskly2fa.js — "Taskly 2FA" panel (POOL DRAIN mode).
 *
 * A NEW, self-contained page that runs Taskly's "📱 Create Inst (2FA)" task the
 * pool-drain way: it reuses a PRE-CREATED Instagram account from the IG Creator
 * pool (rename via the direct Web API + 2FA in Accounts Center, solving the
 * email re-auth from the account's STORED mail.td inbox) — NO Meta signup, NO
 * fresh IG creation. The pooled account is consumed (removed) after each submit.
 *
 * It is deliberately separate from the existing TG Classic / Taskly Bot panel
 * (nova-tg.js): same classes/CSS vocabulary, its own root (#tg-taskly2fa-root),
 * its own SSE log buffer, its own Start/Stop. The engine task alias is
 * "Taskly 2FA" → tg_tasks.INST_2FA_POOL → flow pool_2fa → run_pool_2fa_cycle.
 */
(function () {
  'use strict';

  var root = null, timer = null, tick = null;
  var state = {
    running: false,
    headless: true,
    pool: 0,
    submitted: 0,
    startedAt: 0,
    log: []
  };
  var MAX_LOG = 500;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function $(id) { return document.getElementById(id); }

  function toast(msg, kind, ms) {
    if (typeof window.showToast === 'function') { try { window.showToast(msg, kind || 'info'); return; } catch (e) {} }
    var host = $('toast-container');
    if (!host) return;
    var el = document.createElement('div');
    el.className = 'toast ' + (kind || 'info');
    el.style.cssText = 'position:relative;padding:10px 12px;margin-top:8px;' +
      'border-left:3px solid #4ade80;border-radius:8px;background:#111726;' +
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

  function shell() {
    root.innerHTML =
      /* ---- hero ---- */
      '<div class="page-title-box" style="margin-bottom:1rem;">' +
        '<div class="page-title-row" style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap;">' +
          '<div>' +
            '<h2 style="margin:0;display:flex;align-items:center;gap:.5rem;">' +
              '<i class="fa-solid fa-shield-halved" style="color:#4ade80;"></i> Taskly 2FA' +
              '<span class="nav-pill nav-pill--tool" style="background:rgba(74,222,128,.15);color:#4ade80;">POOL DRAIN</span>' +
            '</h2>' +
            '<p style="margin:.35rem 0 0;">Runs Taskly <strong>📱 Create Inst (2FA)</strong> from the ' +
              '<strong>IG Creator pool</strong> — reuses an existing Instagram account (rename via direct Web API + 2FA ' +
              'from its stored inbox). <u>No Meta signup, no fresh IG creation.</u> Each pooled account is consumed once.</p>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="t2fa-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start Pool Drain</button>' +
            '<button id="t2fa-stop" type="button" class="btn btn-danger" style="display:none;"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('IG CREATOR POOL', 't2fa-kpi-pool', 'available accounts ready to drain', '#a5b4fc') +
        statCard('SUBMITTED (Pool 2FA)', 't2fa-kpi-submitted', '2FA task accepted', '#4ade80') +
        statCard('PARALLEL SLOTS', 't2fa-kpi-conc', 'concurrent creators', '#38bdf8') +
        statCard('ENGINE', 't2fa-kpi-status', 'idle', '#f59e0b') +
      '</div>' +

      /* ---- live banner ---- */
      '<div id="t2fa-banner" style="margin-top:0.9rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem;' +
        'background:linear-gradient(180deg,#111726,#0d1117);border:1px solid var(--border-color);border-radius:12px;padding:14px 16px;">' +
        '<div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">' +
          '<span id="t2fa-badge" style="padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;background:#1e293b;color:#94a3b8;border:1px solid #334155;">IDLE</span>' +
          '<span id="t2fa-title" style="font-weight:700;color:var(--text-main);font-size:.95rem;">POOL DRAIN STOPPED</span>' +
          '<span id="t2fa-sub" style="font-size:.78rem;color:var(--text-muted);border-left:1px solid var(--border-color);padding-left:.75rem;">Ready. Reuses pooled IG accounts — no Meta.</span>' +
        '</div>' +
        '<div style="text-align:right;">' +
          '<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:600;">Execution Time</div>' +
          '<div id="t2fa-timer" style="font-size:1rem;font-weight:700;font-family:var(--font-mono);color:var(--text-main);">00:00:00</div>' +
        '</div>' +
      '</div>' +

      /* ---- how it works ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<h3 class="panel-header" style="margin:0 0 .6rem;"><i class="fa-solid fa-diagram-project" style="color:#4ade80;"></i> Pipeline</h3>' +
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">1 · TASK CREDS</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Lease TG → select <strong>Create Inst (2FA)</strong> → bot issues username.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">2 · RENAME</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Pop a pool account → rename via <strong>IG Web API (~0.4s)</strong>.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">3 · 2FA</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Accounts Center → email re-auth solved from the <strong>stored inbox</strong> → key.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">4 · REGISTER</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Submit key → enter bot code → <strong>Registered</strong> → account consumed.</div></div>' +
        '</div>' +
      '</div>' +

      /* ---- settings ---- */
      '<div class="card-panel creator-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#4ade80;"></i> Pool Drain Settings</h3>' +
          '<span style="font-size:.72rem;color:var(--text-muted);">Task: <strong>Taskly 2FA</strong> · Bot: <strong>@Taskl1_bot</strong></span>' +
        '</div>' +
        '<div class="creator-grid">' +
          '<div class="creator-field"><label>Parallel</label>' +
            '<input id="t2fa-conc" class="form-control" type="number" min="1" max="10" value="6" title="Concurrent creators. Capped by the number of enabled Telegram profiles."></div>' +
          '<div class="creator-field"><label>Target (0 = \u221e)</label>' +
            '<input id="t2fa-target" class="form-control" type="number" min="0" value="0"></div>' +
          '<div class="creator-field creator-field--switch"><label>Headless</label>' +
            '<label class="switch" title="Run browsers headless (recommended)"><input type="checkbox" id="t2fa-headless" checked><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch"><label>Auto-consume</label>' +
            '<label class="switch" title="Always on: a used pooled account is removed after submit"><input type="checkbox" checked disabled><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="creator-service-note" style="margin-top:.6rem;">' +
          '<i class="fa-solid fa-circle-info" style="color:#4ade80;"></i> ' +
          'Only Telegram profiles and the IG pool are used. Requires at least one logged-in TG profile and a non-empty IG Creator pool.' +
        '</div>' +
      '</div>' +

      /* ---- live log ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-dim);"><input type="checkbox" id="t2fa-autoscroll" checked> Auto-scroll</label>' +
            '<button id="t2fa-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="t2fa-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="t2fa-log" class="log-container" style="height:260px;overflow-y:auto;background:#060910;border:1px solid var(--border-color);' +
          'border-radius:8px;padding:.75rem;font-family:var(--font-mono);font-size:.78rem;white-space:pre-wrap;"></div>' +
      '</div>';

    wire();
  }

  function append(line) {
    var entry = '[' + new Date().toLocaleTimeString() + '] ' + line;
    state.log.push(entry);
    if (state.log.length > MAX_LOG) state.log = state.log.slice(-400);
    var el = $('t2fa-log');
    if (!el) return;
    el.textContent = state.log.join('\n');
    var auto = $('t2fa-autoscroll');
    if (!auto || auto.checked) el.scrollTop = el.scrollHeight;
  }

  function post(url, body) {
    append('> POST ' + url + ' ' + JSON.stringify(body || {}));
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        append('< ' + JSON.stringify(j));
        if (j && (j.error || j.status === 'ERROR')) toast(j.error || 'Request failed', 'error', 12000);
        setTimeout(refresh, 400);
        return j;
      })
      .catch(function (e) { append('! ' + e); toast('Request failed: ' + e, 'error', 12000); });
  }

  function start() {
    var btn = $('t2fa-start');
    if (btn) btn.disabled = true;
    fetch('/api/tg/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (btn) btn.disabled = false;
        if (!s) throw new Error('status unavailable');
        var pool = (s.pool && s.pool.accounts) || [];
        var enabled = pool.filter(function (p) { return p.enabled !== false; });
        var connected = enabled.filter(function (p) { return p.logged_in === true; }).length;
        if (!pool.length) { toast('No Telegram account is connected. Add one in TG Manager first.', 'error', 14000); return; }
        if (!enabled.length) { toast('Every Telegram profile is disabled. Enable at least one.', 'error', 14000); return; }
        if (!connected) { toast('No logged-in Telegram profile. Log one in, then start.', 'error', 14000); return; }
        var avail = s.ig_pool_available || 0;
        if (!avail) { toast('IG Creator pool is empty — nothing to drain.', 'error', 14000); return; }
        var conc = parseInt(($('t2fa-conc') || {}).value || 1, 10);
        var target = parseInt(($('t2fa-target') || {}).value || 0, 10);
        append('> start (pool=' + avail + ', tg=' + connected + '/' + enabled.length +
               ', parallel=' + conc + ', target=' + (target || '∞') +
               ', ' + (state.headless ? 'headless' : 'visible') + ')');
        post('/api/tg/start', {
          concurrency: conc,
          target: target,
          headless: state.headless,
          captcha: 'extension',
          tg_task: 'Taskly 2FA',
          tg_bot: 'taskly',
          add_email: false,
          use_ig_pool: true
        });
      })
      .catch(function (e) { if (btn) btn.disabled = false; toast('Could not verify the pool: ' + e, 'error', 12000); });
  }

  function stop() { post('/api/tg/stop', {}); }

  function setRunning(running, cfg) {
    state.running = !!running;
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = 0;

    var badge = $('t2fa-badge'), title = $('t2fa-title'), sub = $('t2fa-sub');
    var startBtn = $('t2fa-start'), stopBtn = $('t2fa-stop');
    if (badge) {
      badge.textContent = running ? 'LIVE' : 'IDLE';
      badge.style.background = running ? 'rgba(74,222,128,.16)' : '#1e293b';
      badge.style.color = running ? '#4ade80' : '#94a3b8';
      badge.style.borderColor = running ? 'rgba(74,222,128,.4)' : '#334155';
    }
    if (title) title.textContent = running ? 'POOL DRAIN RUNNING' : 'POOL DRAIN STOPPED';
    if (sub && cfg) {
      sub.textContent = running
        ? ('Taskly 2FA · parallel ' + (cfg.concurrency || '-') + ' · ' +
           ((cfg.tg_task || 'Taskly 2FA')) + ' · ' + (cfg.headless ? 'headless' : 'visible'))
        : 'Ready. Reuses pooled IG accounts — no Meta.';
    }
    if (startBtn) startBtn.style.display = running ? 'none' : 'inline-flex';
    if (stopBtn) stopBtn.style.display = running ? 'inline-flex' : 'none';
    var kpi = $('t2fa-kpi-status');
    if (kpi) { kpi.textContent = running ? 'LIVE' : 'IDLE'; kpi.style.color = running ? '#4ade80' : '#f59e0b'; }
    if (kpi && kpi.nextElementSibling) kpi.nextElementSibling.textContent = running ? 'draining the IG pool' : 'idle';
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('t2fa-timer');
    if (!el) return;
    if (!state.running || !state.startedAt) { el.textContent = '00:00:00'; return; }
    var s = Math.floor((Date.now() - state.startedAt) / 1000);
    el.textContent = pad(Math.floor(s / 3600)) + ':' + pad(Math.floor((s % 3600) / 60)) + ':' + pad(s % 60);
  }

  function refresh() {
    fetch('/api/tg/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) return;
        setRunning(s.running, s.engine || null);
        state.pool = s.ig_pool_available || 0;
        state.submitted = s.tg_submitted_taskly2fa || 0;
        var p = $('t2fa-kpi-pool'); if (p) p.textContent = String(state.pool);
        var sub = $('t2fa-kpi-submitted'); if (sub) sub.textContent = String(state.submitted);
        var c = $('t2fa-kpi-conc'); if (c) c.textContent = String((s.engine && s.engine.concurrency) || 0);
      })
      .catch(function () {});
  }

  function handleEvent(d) {
    if (!d) return;
    if (d.pipeline && d.pipeline !== 'telegram') return;
    var bot = d.tg_bot ? String(d.tg_bot).toLowerCase() : null;
    if (bot && bot !== 'taskly') return;
    var msg = d.message ||
      (d.type === 'slot_event' && d.detail ? ('[Slot ' + (d.slot_id || '?') + '] ' + d.detail) : null);
    if (msg) append(String(msg));
    if (d.type === 'loop_stopped') { append('[engine] loop stopped' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : '')); refresh(); }
  }

  function wire() {
    if ($('t2fa-start')) $('t2fa-start').addEventListener('click', start);
    if ($('t2fa-stop')) $('t2fa-stop').addEventListener('click', stop);
    if ($('t2fa-headless')) $('t2fa-headless').addEventListener('change', function () { state.headless = this.checked; });
    if ($('t2fa-conc')) {
      try { var saved = localStorage.getItem('nova_t2fa_parallel'); if (saved) $('t2fa-conc').value = saved; } catch (e) {}
      $('t2fa-conc').addEventListener('change', function () {
        try { localStorage.setItem('nova_t2fa_parallel', this.value); } catch (e) {}
      });
    }
    if ($('t2fa-clear')) $('t2fa-clear').addEventListener('click', function () {
      state.log = []; var el = $('t2fa-log'); if (el) el.textContent = '';
    });
    if ($('t2fa-copy')) $('t2fa-copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(state.log.join('\n')); toast('Log copied', 'success'); } catch (e) {}
    });
  }

  function boot() {
    root = $('tg-taskly2fa-root');
    if (!root) return;
    shell();
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 4000);
    if (tick) clearInterval(tick);
    tick = setInterval(tickTimer, 1000);
    try {
      if (!window.__t2faEs) {
        window.__t2faEs = new EventSource('/api/meta-insta/events');
        window.__t2faEs.onmessage = function (ev) {
          try {
            var d = JSON.parse(ev.data);
            if (d && d.type === 'batch' && Array.isArray(d.items)) {
              for (var i = 0; i < d.items.length; i++) { try { handleEvent(d.items[i]); } catch (e) {} }
              return;
            }
            handleEvent(d);
          } catch (e) {}
        };
      }
    } catch (e) {}
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
