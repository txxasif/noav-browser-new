/* nova-paygocookie.js — "PayGo Cookie" panel (CLASSIC, Meta → IG).

 * A self-contained page that runs PayGoBot's "📱 Create Inst (Cookies)" task the
 * CLASSIC way (like Taskly Bot / FastPay Bot): it CREATES the account from
 * scratch — Meta signup → IG join with the bot username → 2FA (wait for the
 * email OTP, submit the key, confirm the code) → follow 5 (mandatory) → export
 * the IG cookie → submit to PayGo → Confirm. NO pool, NO reuse.
 *
 * Engine call:
 *   /api/tg/start { tg_task:"PayGo Cookie", tg_bot:"paygo",
 *                   use_ig_pool:false }
 * → worker.py → run_cookie_cycle (cookie_2fa flow) → counter `paygo`,
 * route tag `paygocookie`.
 *
 * The "2FA + Cookie" switch sends the plain "📱 Create Inst (Cookies)" task
 * instead (cookie flow, no 2FA) if PayGo ever reverts the task.
 */
(function () {
  'use strict';

  var root = null, timer = null, tick = null;
  var state = {
    running: false,
    headless: true,
    twofa: true,
    submitted: 0,
    total: 0,
    startedAt: 0,
    log: []
  };
  var MAX_LOG = 500;
  var BOT_ID = 'paygo';
  var TASK_2FA = 'PayGo Cookie';                 // → tg_tasks.COOKIES_2FA (cookie_2fa)
  var TASK_PLAIN = '📱 Create Inst (Cookies)';   // → tg_tasks.COOKIES (cookie)
  var ROUTE = 'paygocookie';

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

  function shell() {
    root.innerHTML =
      /* ---- hero ---- */
      '<div class="page-title-box" style="margin-bottom:1rem;">' +
        '<div class="page-title-row" style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap;">' +
          '<div>' +
            '<h2 style="margin:0;display:flex;align-items:center;gap:.5rem;">' +
              '<img src="img/bot_logo/paygo.png" width="28" height="28" alt="PayGo" style="border-radius:8px;object-fit:cover;box-shadow:0 0 0 1px rgba(255,255,255,.1);"> PayGo Cookie' +
              '<span class="nav-pill nav-pill--tool" style="background:rgba(245,158,11,.15);color:#fbbf24;">CLASSIC</span>' +
            '</h2>' +
            '<p style="margin:.35rem 0 0;">Creates the account <strong>from scratch</strong> for PayGo <strong>📱 Create Inst (Cookies)</strong>: ' +
              'Meta signup → Instagram join → <strong>2FA</strong> (wait email OTP → submit key → confirm code) → <strong>follow 5</strong> → export IG cookie → submit → Confirm.</p>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="pgc-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start</button>' +
            '<button id="pgc-stop" type="button" class="btn btn-danger" style="display:none;"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('SUBMITTED (PayGo Cookie)', 'pgc-kpi-submitted', 'cookie task accepted', '#4ade80') +
        statCard('TOTAL ACCOUNTS', 'pgc-kpi-total', 'created + submitted', '#a5b4fc') +
        statCard('PARALLEL SLOTS', 'pgc-kpi-conc', 'concurrent creators', '#38bdf8') +
        statCard('ENGINE', 'pgc-kpi-status', 'idle', '#f59e0b') +
      '</div>' +

      /* ---- live banner ---- */
      '<div id="pgc-banner" style="margin-top:0.9rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem;' +
        'background:linear-gradient(180deg,#111726,#0d1117);border:1px solid var(--border-color);border-radius:12px;padding:14px 16px;">' +
        '<div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">' +
          '<span id="pgc-badge" style="padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;background:#1e293b;color:#94a3b8;border:1px solid #334155;">IDLE</span>' +
          '<span id="pgc-title" style="font-weight:700;color:var(--text-main);font-size:.95rem;">PAYGO COOKIE STOPPED</span>' +
          '<span id="pgc-sub" style="font-size:.78rem;color:var(--text-muted);border-left:1px solid var(--border-color);padding-left:.75rem;">Ready. Creates Meta → Instagram → cookie.</span>' +
        '</div>' +
        '<div style="text-align:right;">' +
          '<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:600;">Execution Time</div>' +
          '<div id="pgc-timer" style="font-size:1rem;font-weight:700;font-family:var(--font-mono);color:var(--text-main);">00:00:00</div>' +
        '</div>' +
      '</div>' +

      /* ---- pipeline ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<h3 class="panel-header" style="margin:0 0 .6rem;"><i class="fa-solid fa-diagram-project" style="color:#f59e0b;"></i> Pipeline</h3>' +
        '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;">' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">1 · META</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Create Meta + verify, then lease TG → select <strong>Create Inst (Cookies)</strong> → PayGo issues the login.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">2 · IG JOIN</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Join Instagram with the bot username + password.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">3 · 2FA</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Enable 2FA (wait email OTP) → submit key → confirm bot code.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">4 · FOLLOW 5</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Follow 5 suggested accounts (human-like, random).</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">5 · COOKIE</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Export IG cookie → submit → <strong>Account registered</strong>.</div></div>' +
        '</div>' +
      '</div>' +

      /* ---- settings ---- */
      '<div class="card-panel creator-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#f59e0b;"></i> Settings</h3>' +
          '<span class="tg-bot-badge" id="pgc-bot-badge">' +
            '<img src="img/bot_logo/paygo.png" width="18" height="18" style="border-radius:50%;object-fit:cover;" onerror="this.style.display=\'none\'"> PayGo Bot · Cookie task' +
          '</span>' +
        '</div>' +
        '<div class="creator-grid">' +
          '<div class="creator-field"><label>Parallel</label>' +
            '<input id="pgc-conc" class="form-control" type="number" min="1" max="10" value="4" title="Concurrent creators. Capped by the number of enabled Telegram profiles."></div>' +
          '<div class="creator-field"><label>Target (0 = \u221e)</label>' +
            '<input id="pgc-target" class="form-control" type="number" min="0" value="0"></div>' +
          '<div class="creator-field creator-field--switch"><label>Headless</label>' +
            '<label class="switch" title="Run browsers headless (recommended)"><input type="checkbox" id="pgc-headless" checked><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch"><label>2FA + Cookie</label>' +
            '<label class="switch" title="NEW PayGo protocol: enable 2FA (wait for the email OTP), submit the key, confirm the bot code, follow 5, THEN submit the cookie. Turn OFF to run the plain cookie-only flow if PayGo changes back."><input type="checkbox" id="pgc-twofa" checked><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="creator-service-note" style="margin-top:.6rem;">' +
          '<i class="fa-solid fa-circle-info" style="color:#f59e0b;"></i> ' +
          'Creates the account from scratch (Meta → Instagram). Requires at least one logged-in TG profile.' +
        '</div>' +
      '</div>' +

      /* ---- live log ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-dim);"><input type="checkbox" id="pgc-autoscroll" checked> Auto-scroll</label>' +
            '<button id="pgc-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="pgc-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="pgc-log" class="log-container" style="height:260px;overflow-y:auto;background:#060910;border:1px solid var(--border-color);' +
          'border-radius:8px;padding:.75rem;font-family:var(--font-mono);font-size:.78rem;white-space:pre-wrap;"></div>' +
      '</div>' +

      /* ---- route-scoped failure reasons + session logs ---- */
      (window.NovaDiag ? NovaDiag.renderHtml('pgc', 'paygocookie') : '');

    wire();
  }

  function append(line) {
    var entry = '[' + new Date().toLocaleTimeString() + '] ' + line;
    state.log.push(entry);
    if (state.log.length > MAX_LOG) state.log = state.log.slice(-400);
    var el = $('pgc-log');
    if (!el) return;
    el.textContent = state.log.join('\n');
    var auto = $('pgc-autoscroll');
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
    var btn = $('pgc-start');
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
        var conc = parseInt(($('pgc-conc') || {}).value || 1, 10);
        var target = parseInt(($('pgc-target') || {}).value || 0, 10);
        var c2fa = $('pgc-twofa') ? $('pgc-twofa').checked : true;
        state.twofa = c2fa;
        var task = c2fa ? TASK_2FA : TASK_PLAIN;
        append('> start (task=' + task + ', tg=' + connected + '/' + enabled.length +
               ', parallel=' + conc + ', target=' + (target || '∞') +
               ', ' + (state.headless ? 'headless' : 'visible') +
               ', 2fa+cookie=' + (c2fa ? 'ON' : 'OFF') + ')');
        var _doPost = function () { post('/api/tg/start', {
          concurrency: conc,
          target: target,
          headless: state.headless,
          captcha: 'extension',
          tg_task: task,
          tg_bot: BOT_ID,
          add_email: false,
          use_ig_pool: false
        }); };
        if (typeof window.__tgTaskCheck === 'function') {
          window.__tgTaskCheck(BOT_ID, task, append).then(function (pre) {
            if (pre.proceed) _doPost(); else if (btn) btn.disabled = false;
          });
        } else _doPost();
      })
      .catch(function (e) { if (btn) btn.disabled = false; toast('Could not verify the pool: ' + e, 'error', 12000); });
  }

  function stop() {
    if (!state.isMine) { toast('Another task is running — stop it from its own page.', 'warn', 10000); return; }
    post('/api/tg/stop', {});
  }

  // Attribution: only claim "LIVE" when the active engine is genuinely this
  // classic PayGo cookie run (NOT the pool drain, NOT another PayGo task).
  function setRunning(running, cfg) {
    state.running = !!running;
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = 0;

    cfg = cfg || {};
    var activeBot = cfg.tg_bot ? String(cfg.tg_bot).toLowerCase() : null;
    var cfgTask = String(cfg.tg_task || '');
    var isMine = !!(running && activeBot === BOT_ID && !cfg.use_ig_pool
                    && /cookie/i.test(cfgTask) && !/paygo\s*2fa/i.test(cfgTask));
    var isOther = !!(running && activeBot && !isMine);
    var otherName = activeBot === 'fastpay' ? 'FastPay' : activeBot === 'taskly' ? 'Taskly'
      : activeBot === 'paygo' ? (cfg.use_ig_pool ? 'PayGo Pool' : (/paygo\s*2fa/i.test(cfgTask) ? 'PayGo 2FA' : 'PayGo')) : (activeBot || '');

    var badge = $('pgc-badge'), title = $('pgc-title'), sub = $('pgc-sub');
    var startBtn = $('pgc-start'), stopBtn = $('pgc-stop');
    if (badge) {
      badge.textContent = isMine ? 'LIVE' : (isOther ? (otherName.toUpperCase() + ' RUNNING') : 'IDLE');
      badge.style.background = isMine ? 'rgba(245,158,11,.18)' : (isOther ? 'rgba(245,158,11,.2)' : '#1e293b');
      badge.style.color = isMine ? '#fbbf24' : (isOther ? '#fbbf24' : '#94a3b8');
      badge.style.borderColor = (isMine || isOther) ? 'rgba(245,158,11,.4)' : '#334155';
    }
    if (title) {
      title.textContent = isMine ? 'PAYGO COOKIE RUNNING'
        : isOther ? (otherName.toUpperCase() + ' IS RUNNING · PAYGO COOKIE IDLE')
        : 'PAYGO COOKIE STOPPED';
    }
    if (sub) {
      sub.textContent = isMine
        ? ('Meta → IG → cookie · parallel ' + (cfg.concurrency || '-') + ' · ' + (cfg.headless ? 'headless' : 'visible'))
        : isOther
          ? ('⚡ ' + otherName + ' is running (one engine at a time). Stop it from its own page.')
          : 'Ready. Creates Meta → Instagram → cookie.';
    }
    state.isMine = isMine;
    if (startBtn) startBtn.style.display = running ? 'none' : 'inline-flex';
    if (stopBtn) {
      stopBtn.style.display = isMine ? 'inline-flex' : 'none';
      stopBtn.title = 'Stop the PayGo cookie run';
    }
    var kpi = $('pgc-kpi-status');
    if (kpi) {
      kpi.textContent = isMine ? 'LIVE' : (isOther ? otherName.toUpperCase() : 'IDLE');
      kpi.style.color = (isMine || isOther) ? '#fbbf24' : '#f59e0b';
    }
    if (kpi && kpi.nextElementSibling) kpi.nextElementSibling.textContent = isMine ? 'creating accounts' : (isOther ? (otherName + ' is running') : 'idle');
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('pgc-timer');
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
        state.submitted = s.tg_submitted_paygo || 0;
        state.total = s.tg_total || s.total_accounts || 0;
        var sub = $('pgc-kpi-submitted'); if (sub) sub.textContent = String(state.submitted);
        var tot = $('pgc-kpi-total'); if (tot) tot.textContent = String(state.total);
        var c = $('pgc-kpi-conc'); if (c) c.textContent = String((s.engine && s.engine.concurrency) || 0);
      })
      .catch(function () {});
  }

  function handleEvent(d) {
    if (!d) return;
    // Route-scoped: this panel only shows the paygocookie route.
    if (d.route && d.route !== ROUTE) return;
    if (d.pipeline && d.pipeline !== 'telegram') return;
    var bot = d.tg_bot ? String(d.tg_bot).toLowerCase() : null;
    if (bot && bot !== BOT_ID) return;
    var msg = d.message ||
      (d.type === 'slot_event' && d.detail ? ('[Slot ' + (d.slot_id || '?') + '] ' + d.detail) : null);
    if (msg) append(String(msg));
    if (d.type === 'loop_stopped') { append('[engine] loop stopped' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : '')); refresh(); }
  }

  function wire() {
    if ($('pgc-start')) $('pgc-start').addEventListener('click', start);
    if ($('pgc-stop')) $('pgc-stop').addEventListener('click', stop);
    if ($('pgc-headless')) $('pgc-headless').addEventListener('change', function () { state.headless = this.checked; });
    if ($('pgc-twofa')) {
      try { if (localStorage.getItem('nova_pgc_twofa') === '0') { $('pgc-twofa').checked = false; state.twofa = false; } } catch (e) {}
      $('pgc-twofa').addEventListener('change', function () {
        state.twofa = this.checked;
        try { localStorage.setItem('nova_pgc_twofa', this.checked ? '1' : '0'); } catch (e) {}
      });
    }
    if ($('pgc-conc')) {
      try { var saved = localStorage.getItem('nova_pgc_parallel'); if (saved) $('pgc-conc').value = saved; } catch (e) {}
      $('pgc-conc').addEventListener('change', function () {
        try { localStorage.setItem('nova_pgc_parallel', this.value); } catch (e) {}
      });
    }
    if ($('pgc-clear')) $('pgc-clear').addEventListener('click', function () {
      state.log = []; var el = $('pgc-log'); if (el) el.textContent = '';
    });
    if ($('pgc-copy')) $('pgc-copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(state.log.join('\n')); toast('Log copied', 'success'); } catch (e) {}
    });
  }

  function boot() {
    root = $('tg-paygocookie-root');
    if (!root) return;
    shell();
    if (window.NovaDiag) { NovaDiag.refreshReasons(); NovaDiag.refreshLogs(); }
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 4000);
    if (tick) clearInterval(tick);
    tick = setInterval(tickTimer, 1000);
    try {
      if (!window.__pgcEsShared && typeof window.__novaEsSubscribe === 'function') {
        window.__pgcEsShared = true;
        window.__novaEsSubscribe(handleEvent);
      } else if (!window.__pgcEs && typeof window.__novaEsSubscribe !== 'function') {
        window.__pgcEs = new EventSource('/api/meta-insta/events');
        window.__pgcEs.onmessage = function (ev) {
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
