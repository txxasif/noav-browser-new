/* nova-paygopool.js — "PayGo Cookie" panel (POOL DRAIN mode).
 *
 * A NEW, self-contained page that runs PayGoBot's "📱 Create Inst (Cookies)"
 * task the POOL-DRAIN way: it reuses a PRE-CREATED Instagram account from the
 * IG Creator pool — rename via the direct Web API (~0.4s), export the IG cookie
 * header, POST it to PayGo, then Confirm. NO Meta signup, NO fresh IG creation.
 * The pooled account is consumed (removed) after each submit.
 *
 * It is deliberately separate from the PayGo Bot panel (nova-tg.js): same
 * classes/CSS vocabulary, its own root (#tg-paygopool-root), its own SSE log
 * buffer, its own Start/Stop + Auto-Mine. The engine call is
 *   /api/tg/start { tg_task:"📱 Create Inst (Cookies)", tg_bot:"paygo",
 *                   use_ig_pool:true }
 * → worker.py → run_cookie_cycle (pool path) → own counter `paygo_pool`,
 * route tag `paygo_pool`.
 */
(function () {
  'use strict';

  var root = null, timer = null, tick = null;
  var state = {
    running: false,
    headless: true,
    cookie2fa: true,
    pool: 0,
    submitted: 0,
    stock: null,
    startedAt: 0
  };
  var MAX_LOG = 500;
  var BOT_ID = 'paygo';
  var TASK = '📱 Create Inst (Cookies)';
  var ROUTE = 'paygo_pool';

  function $(id) { return document.getElementById(id); }

  // Shared helpers (nova-pool-panel.js).
  var toast = NovaPoolPanel.toast;
  var statCard = NovaPoolPanel.statCard;
  var buf = NovaPoolPanel.logBuffer(MAX_LOG);

  function shell() {
    root.innerHTML =
      /* ---- hero ---- */
      '<div class="page-title-box" style="margin-bottom:1rem;">' +
        '<div class="page-title-row" style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap;">' +
          '<div>' +
            '<h2 style="margin:0;display:flex;align-items:center;gap:.5rem;">' +
              '<img src="img/bot_logo/paygo.png" width="28" height="28" alt="PayGo" style="border-radius:8px;object-fit:cover;box-shadow:0 0 0 1px rgba(255,255,255,.1);"> PayGo Cookie' +
              '<span class="nav-pill nav-pill--tool" style="background:rgba(245,158,11,.15);color:#fbbf24;">POOL DRAIN</span>' +
            '</h2>' +
            '<p style="margin:.35rem 0 0;">Runs PayGo <strong>📱 Create Inst (Cookies)</strong> from the ' +
              '<strong>IG Creator pool</strong> — reuses an existing Instagram account (rename via direct Web API, export its ' +
              'IG cookie, submit to PayGo). <u>No Meta signup, no fresh IG creation.</u> Each pooled account is consumed once.</p>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="pgp-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start Pool Drain</button>' +
            '<button id="pgp-stop" type="button" class="btn btn-danger" style="display:none;"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('IG CREATOR POOL', 'pgp-kpi-pool', 'available accounts ready to drain', '#a5b4fc') +
        statCard('SUBMITTED (PayGo Cookie)', 'pgp-kpi-submitted', 'cookie task accepted', '#4ade80') +
        statCard('PARALLEL SLOTS', 'pgp-kpi-conc', 'concurrent creators', '#38bdf8') +
        statCard('ENGINE', 'pgp-kpi-status', 'idle', '#f59e0b') +
      '</div>' +

      /* ---- PayGo radar bar: hourly stock · IG pool · separate pool counter ---- */
      '<div class="paygo-radar-bar" style="display:flex;">' +
        '<div class="paygo-radar-metric">' +
          '<span class="paygo-radar-label"><i class="fa-solid fa-bolt" style="color:#34d399;"></i> HOURLY STOCK:</span>' +
          '<span id="pgp-radar-stock" class="paygo-radar-badge stock-closed"><i class="fa-solid fa-hourglass-half"></i> Checking…</span>' +
        '</div>' +
        '<div class="paygo-radar-metric">' +
          '<span class="paygo-radar-label"><i class="fa-solid fa-database" style="color:#a5b4fc;"></i> IG CREATOR POOL:</span>' +
          '<span id="pgp-radar-pool" class="paygo-radar-badge pool-count">0 Accounts Ready</span>' +
        '</div>' +
        '<div class="paygo-radar-metric">' +
          '<span class="paygo-radar-label"><i class="fa-solid fa-circle-check" style="color:#34d399;"></i> SUBMITTED (POOL):</span>' +
          '<span id="pgp-radar-submitted" class="paygo-radar-badge stock-open">0</span>' +
        '</div>' +
      '</div>' +

      /* ---- live banner ---- */
      '<div id="pgp-banner" style="margin-top:0.9rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem;' +
        'background:linear-gradient(180deg,#111726,#0d1117);border:1px solid var(--border-color);border-radius:12px;padding:14px 16px;">' +
        '<div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">' +
          '<span id="pgp-badge" style="padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;background:#1e293b;color:#94a3b8;border:1px solid #334155;">IDLE</span>' +
          '<span id="pgp-title" style="font-weight:700;color:var(--text-main);font-size:.95rem;">POOL DRAIN STOPPED</span>' +
          '<span id="pgp-sub" style="font-size:.78rem;color:var(--text-muted);border-left:1px solid var(--border-color);padding-left:.75rem;">Ready. Reuses pooled IG accounts — no Meta.</span>' +
        '</div>' +
        '<div style="text-align:right;">' +
          '<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:600;">Execution Time</div>' +
          '<div id="pgp-timer" style="font-size:1rem;font-weight:700;font-family:var(--font-mono);color:var(--text-main);">00:00:00</div>' +
        '</div>' +
      '</div>' +

      /* ---- pipeline ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<h3 class="panel-header" style="margin:0 0 .6rem;"><i class="fa-solid fa-diagram-project" style="color:#f59e0b;"></i> Pipeline</h3>' +
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">1 · TASK CREDS</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Lease TG → select <strong>Create Inst (Cookies)</strong> → PayGo issues the target login.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">2 · RENAME</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Pop a pool account → rename via <strong>IG Web API (~0.4s)</strong>.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">3 · COOKIE EXPORT</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Build the IG cookie header (<strong>sessionid gate</strong>).</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">4 · SUBMIT + CONFIRM</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">POST the cookie → <strong>Account registered</strong> → account consumed.</div></div>' +
        '</div>' +
      '</div>' +

      /* ---- settings ---- */
      '<div class="card-panel creator-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#f59e0b;"></i> Pool Drain Settings</h3>' +
          '<span class="tg-bot-badge" id="pgp-bot-badge">' +
            '<img src="img/bot_logo/paygo.png" width="18" height="18" style="border-radius:50%;object-fit:cover;" onerror="this.style.display=\'none\'"> PayGo Bot · Cookie task' +
          '</span>' +
        '</div>' +
        '<div class="creator-grid">' +
          '<div class="creator-field"><label>Parallel</label>' +
            '<input id="pgp-conc" class="form-control" type="number" min="1" max="10" value="6" title="Concurrent creators. Capped by the number of enabled Telegram profiles."></div>' +
          '<div class="creator-field"><label>Target (0 = \u221e)</label>' +
            '<input id="pgp-target" class="form-control" type="number" min="0" value="0"></div>' +
          '<div class="creator-field creator-field--switch"><label>Headless</label>' +
            '<label class="switch" title="Run browsers headless (recommended)"><input type="checkbox" id="pgp-headless" checked><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch"><label>2FA + Cookie</label>' +
            '<label class="switch" title="ON (default for this task) = rename + follow 5 + MOCK 2FA key + cookie submit (the browser does the follow via the stored session — no login). OFF = legacy rename + submit the stored cookie (no browser, no 2FA, no follow)."><input type="checkbox" id="pgp-cookie2fa" checked><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch"><label>API mode</label>' +
            '<label class="switch" title="ON = BROWSERLESS IG private-API path: rename, follow 5 (random from the fixed operator list), REAL 2FA, password, email and cookie all via the API. Follow falls back to the browser (session reuse, no login) when IG blocks the raw API login. OFF = the existing browser logic (default)."><input type="checkbox" id="pgp-igapi"><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch" id="pgp-igapimock-wrap" style="display:none;"><label>Mock 2FA</label>' +
            '<label class="switch" title="API mode only. ON = submit a MOCK 2FA key and skip the real 2FA enable. OFF (default) = REAL 2FA via the API."><input type="checkbox" id="pgp-igapimock"><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch"><label>Auto-consume</label>' +
            '<label class="switch" title="Always on: a used pooled account is removed after submit"><input type="checkbox" checked disabled><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="creator-service-note" style="margin-top:.6rem;">' +
          '<i class="fa-solid fa-circle-info" style="color:#f59e0b;"></i> ' +
          'Only Telegram profiles and the IG pool are used. Requires at least one logged-in TG profile and a non-empty IG Creator pool.' +
        '</div>' +
      '</div>' +

      /* ---- live log ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-dim);"><input type="checkbox" id="pgp-autoscroll" checked> Auto-scroll</label>' +
            '<button id="pgp-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="pgp-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="pgp-log" class="log-container" style="height:260px;overflow-y:auto;background:#060910;border:1px solid var(--border-color);' +
          'border-radius:8px;padding:.75rem;font-family:var(--font-mono);font-size:.78rem;white-space:pre-wrap;"></div>' +
      '</div>' +

      /* ---- route-scoped failure reasons + session logs (bottom, like other panels) ---- */
      (window.NovaDiag ? NovaDiag.renderHtml('pgp', 'paygo_pool') : '');

    wire();
  }

  function append(line) {
    buf.push(line);
    var el = $('pgp-log');
    if (!el) return;
    el.textContent = buf.text();
    var auto = $('pgp-autoscroll');
    if (!auto || auto.checked) el.scrollTop = el.scrollHeight;
  }

  function post(url, body) { return NovaPoolPanel.postJson(url, body, append, refresh); }

  function start() {
    var btn = $('pgp-start');
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
        var conc = parseInt(($('pgp-conc') || {}).value || 1, 10);
        var target = parseInt(($('pgp-target') || {}).value || 0, 10);
        var c2fa = $('pgp-cookie2fa') ? $('pgp-cookie2fa').checked : false;
        var apiOn = $('pgp-igapi') ? $('pgp-igapi').checked : false;
        var apiMockOn = $('pgp-igapimock') ? $('pgp-igapimock').checked : false;
        state.cookie2fa = c2fa;
        append('> start (pool=' + avail + ', tg=' + connected + '/' + enabled.length +
               ', parallel=' + conc + ', target=' + (target || '∞') +
               ', ' + (state.headless ? 'headless' : 'visible') +
               ', 2fa+cookie=' + (c2fa ? 'ON' : 'OFF') +
               ', api=' + (apiOn ? (apiMockOn ? 'MOCK-2FA' : 'REAL-2FA') : 'OFF') + ')');
        var _doPost = function () { post('/api/tg/start', {
          concurrency: conc,
          target: target,
          headless: state.headless,
          captcha: 'extension',
          tg_task: TASK,
          tg_bot: BOT_ID,
          add_email: false,
          use_ig_pool: true,
          cookie_2fa: c2fa,
          ig_api: apiOn,
          ig_api_mock: (apiOn && apiMockOn)
        }); };
        if (typeof window.__tgTaskCheck === 'function') {
          window.__tgTaskCheck(BOT_ID, TASK, append).then(function (pre) {
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

  // Attribution: the single TG engine slot may be running a DIFFERENT bot. Only
  // claim "LIVE" when the active engine is genuinely the PayGo POOL drain.
  function setRunning(running, cfg) {
    state.running = !!running;
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = 0;

    cfg = cfg || {};
    var activeBot = cfg.tg_bot ? String(cfg.tg_bot).toLowerCase() : null;
    var cfgTask = String(cfg.tg_task || '');
    // The NEW "PayGo 2FA" pool shares tg_bot='paygo' + use_ig_pool — it is a
    // DIFFERENT task, so it must not light this page up (and vice versa).
    var isMine = !!(running && activeBot === BOT_ID && cfg.use_ig_pool
                    && !/paygo\s*2fa/i.test(cfgTask));
    var isOther = !!(running && activeBot && !isMine);
    var otherName = activeBot === 'fastpay' ? 'FastPay' : activeBot === 'taskly' ? 'Taskly'
      : activeBot === 'paygo' ? (/paygo\s*2fa/i.test(cfgTask) ? 'PayGo 2FA' : 'PayGo') : (activeBot || '');

    var badge = $('pgp-badge'), title = $('pgp-title'), sub = $('pgp-sub');
    var startBtn = $('pgp-start'), stopBtn = $('pgp-stop');
    if (badge) {
      badge.textContent = isMine ? 'LIVE' : (isOther ? (otherName.toUpperCase() + ' RUNNING') : 'IDLE');
      badge.style.background = isMine ? 'rgba(245,158,11,.18)' : (isOther ? 'rgba(245,158,11,.2)' : '#1e293b');
      badge.style.color = isMine ? '#fbbf24' : (isOther ? '#fbbf24' : '#94a3b8');
      badge.style.borderColor = (isMine || isOther) ? 'rgba(245,158,11,.4)' : '#334155';
    }
    if (title) {
      title.textContent = isMine ? 'POOL DRAIN RUNNING'
        : isOther ? (otherName.toUpperCase() + ' IS RUNNING · PayGo POOL IDLE')
        : 'POOL DRAIN STOPPED';
    }
    if (sub) {
      sub.textContent = isMine
        ? ('PayGo Cookie · parallel ' + (cfg.concurrency || '-') + ' · ' + (cfg.headless ? 'headless' : 'visible'))
        : isOther
          ? ('⚡ ' + otherName + ' is running (one engine at a time). Stop it from its own page.')
          : 'Ready. Reuses pooled IG accounts — no Meta.';
    }
    state.isMine = isMine;
    if (startBtn) startBtn.style.display = running ? 'none' : 'inline-flex';
    if (stopBtn) {
      // Stop is PER-TASK: only this page's own engine. Never stop another task.
      stopBtn.style.display = isMine ? 'inline-flex' : 'none';
      stopBtn.title = 'Stop the PayGo pool drain';
    }
    var kpi = $('pgp-kpi-status');
    if (kpi) {
      kpi.textContent = isMine ? 'LIVE' : (isOther ? otherName.toUpperCase() : 'IDLE');
      kpi.style.color = (isMine || isOther) ? '#fbbf24' : '#f59e0b';
    }
    if (kpi && kpi.nextElementSibling) kpi.nextElementSibling.textContent = isMine ? 'draining the IG pool' : (isOther ? (otherName + ' is running') : 'idle');
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('pgp-timer');
    if (!el) return;
    if (!state.running || !state.startedAt) { el.textContent = '00:00:00'; return; }
    var s = Math.floor((Date.now() - state.startedAt) / 1000);
    el.textContent = pad(Math.floor(s / 3600)) + ':' + pad(Math.floor((s % 3600) / 60)) + ':' + pad(s % 60);
  }

  function updateRadar(s) {
    var stockEl = $('pgp-radar-stock');
    if (stockEl) {
      var st = (s && typeof s.paygo_stock === 'number') ? s.paygo_stock : null;
      if (st == null) { stockEl.className = 'paygo-radar-badge stock-closed'; stockEl.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> Checking…'; }
      else if (st > 0) { stockEl.className = 'paygo-radar-badge stock-open'; stockEl.innerHTML = '<i class="fa-solid fa-bolt"></i> ' + st + '/5700'; }
      else { stockEl.className = 'paygo-radar-badge stock-closed'; stockEl.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> Sold out — refills at :00'; }
    }
    var poolEl = $('pgp-radar-pool'); if (poolEl) poolEl.textContent = state.pool + ' Accounts Ready';
    var subEl = $('pgp-radar-submitted'); if (subEl) subEl.textContent = String(state.submitted);
  }

  function refresh() {
    fetch('/api/tg/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) return;
        setRunning(s.running, s.engine || null);
        state.pool = s.ig_pool_available || 0;
        state.submitted = s.tg_submitted_paygo_pool || 0;
        state.stock = (typeof s.paygo_stock === 'number') ? s.paygo_stock : null;
        var p = $('pgp-kpi-pool'); if (p) p.textContent = String(state.pool);
        var sub = $('pgp-kpi-submitted'); if (sub) sub.textContent = String(state.submitted);
        var c = $('pgp-kpi-conc'); if (c) c.textContent = String((s.engine && s.engine.concurrency) || 0);
        updateRadar(s);
      })
      .catch(function () {});
  }

  function handleEvent(d) {
    if (!d) return;
    // Route-scoped: this panel only shows the paygo_pool route.
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
    if ($('pgp-start')) $('pgp-start').addEventListener('click', start);
    if ($('pgp-stop')) $('pgp-stop').addEventListener('click', stop);
    if ($('pgp-headless')) $('pgp-headless').addEventListener('change', function () { state.headless = this.checked; });
    if ($('pgp-cookie2fa')) {
      try { if (localStorage.getItem('nova_pgp_cookie2fa') === '1') { $('pgp-cookie2fa').checked = true; state.cookie2fa = true; } } catch (e) {}
      $('pgp-cookie2fa').addEventListener('change', function () {
        state.cookie2fa = this.checked;
        try { localStorage.setItem('nova_pgp_cookie2fa', this.checked ? '1' : '0'); } catch (e) {}
      });
    }
    if ($('pgp-igapi')) {
      try { if (localStorage.getItem('nova_pgp_igapi') === '1') $('pgp-igapi').checked = true; } catch (e) {}
      var pgpSyncMock = function () {
        var w = $('pgp-igapimock-wrap');
        if (w) w.style.display = $('pgp-igapi').checked ? '' : 'none';
      };
      $('pgp-igapi').addEventListener('change', function () {
        try { localStorage.setItem('nova_pgp_igapi', this.checked ? '1' : '0'); } catch (e) {}
        pgpSyncMock();
      });
      pgpSyncMock();
    }
    if ($('pgp-igapimock')) {
      try { if (localStorage.getItem('nova_pgp_igapimock') === '1') $('pgp-igapimock').checked = true; } catch (e) {}
      $('pgp-igapimock').addEventListener('change', function () {
        try { localStorage.setItem('nova_pgp_igapimock', this.checked ? '1' : '0'); } catch (e) {}
      });
    }
    if ($('pgp-conc')) {
      try { var saved = localStorage.getItem('nova_pgp_parallel'); if (saved) $('pgp-conc').value = saved; } catch (e) {}
      $('pgp-conc').addEventListener('change', function () {
        try { localStorage.setItem('nova_pgp_parallel', this.value); } catch (e) {}
      });
    }
    if ($('pgp-clear')) $('pgp-clear').addEventListener('click', function () {
      buf.clear(); var el = $('pgp-log'); if (el) el.textContent = '';
    });
    if ($('pgp-copy')) $('pgp-copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(buf.text()); toast('Log copied', 'success'); } catch (e) {}
    });
  }

  function boot() {
    root = $('tg-paygopool-root');
    if (!root) return;
    shell();
    if (window.NovaDiag) { NovaDiag.refreshReasons(); NovaDiag.refreshLogs(); }
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 4000);
    if (tick) clearInterval(tick);
    tick = setInterval(tickTimer, 1000);
    // Shared SSE hub (nova-core.js): one stream per page.
    NovaPoolPanel.subscribe(handleEvent, 'pgp');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
