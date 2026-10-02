/* nova-paygopool.js — "PayGo Pool" panel (POOL DRAIN mode).
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
    pool: 0,
    submitted: 0,
    stock: null,
    auto: null,
    startedAt: 0,
    log: []
  };
  var MAX_LOG = 500;
  var BOT_ID = 'paygo';
  var TASK = '📱 Create Inst (Cookies)';
  var ROUTE = 'paygo_pool';

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
              '<img src="img/bot_logo/paygo.png" width="28" height="28" alt="PayGo" style="border-radius:8px;object-fit:cover;box-shadow:0 0 0 1px rgba(255,255,255,.1);"> PayGo Pool' +
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
        statCard('SUBMITTED (PayGo Pool)', 'pgp-kpi-submitted', 'cookie task accepted', '#4ade80') +
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
          '<div class="creator-field creator-field--switch"><label>Auto-consume</label>' +
            '<label class="switch" title="Always on: a used pooled account is removed after submit"><input type="checkbox" checked disabled><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="creator-service-note" style="margin-top:.6rem;">' +
          '<i class="fa-solid fa-circle-info" style="color:#f59e0b;"></i> ' +
          'Only Telegram profiles and the IG pool are used. Requires at least one logged-in TG profile and a non-empty IG Creator pool.' +
        '</div>' +

        /* ---- Auto-Mine on hourly refill (:00) ---- */
        '<div class="paygo-feature-card paygo-feature-automine" id="pgp-auto-card" style="flex-direction:column;align-items:stretch;margin-top:.9rem;">' +
          '<div style="display:flex;align-items:center;justify-content:space-between;gap:1.25rem;width:100%;">' +
            '<div class="paygo-feature-main">' +
              '<div class="paygo-feature-icon"><i class="fa-solid fa-clock-rotate-left"></i></div>' +
              '<div class="paygo-feature-text">' +
                '<div class="paygo-feature-title">AUTO-MINE ON HOURLY REFILL (:00)' +
                  '<span class="paygo-feature-badge automine-badge">Autonomous Scheduler</span>' +
                '</div>' +
                '<div class="paygo-feature-desc">Zero-contention background engine: auto-preempts the running bot at :00, drains PayGo at max speed, then restores the previous bot.</div>' +
              '</div>' +
            '</div>' +
            '<div class="paygo-feature-controls">' +
              '<span id="pgp-auto-pill" class="paygo-status-pill">Auto-Mine Off</span>' +
              '<label class="switch" title="Auto-Mine PayGo: when stock refills, pauses running bot, drains PayGo pool, then resumes previous bot">' +
                '<input type="checkbox" id="pgp-auto-sw"><span class="slider"></span>' +
              '</label>' +
            '</div>' +
          '</div>' +
          '<div class="paygo-automine-config" id="pgp-auto-config-row">' +
            '<div class="paygo-automine-slots">' +
              '<span><i class="fa-solid fa-users-gear" style="color:var(--accent-cyan);"></i> Auto-Mine Parallel Slots:</span>' +
              '<input id="pgp-auto-conc" class="form-control paygo-conc-input" type="number" min="1" max="10" value="6" title="Number of parallel creators spawned when PayGo refills">' +
              '<span style="font-size:0.72rem;color:var(--text-muted);">(parallel drain slots at :00)</span>' +
            '</div>' +
            '<div class="paygo-automine-explainer">' +
              '<i class="fa-solid fa-circle-info"></i>' +
              '<span><strong>Autonomous Mode:</strong> runs on its own at :00 — no need to click Start. If another bot is running manually, it auto-pauses at :00, drains, and resumes.</span>' +
            '</div>' +
          '</div>' +
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
    var entry = '[' + new Date().toLocaleTimeString() + '] ' + line;
    state.log.push(entry);
    if (state.log.length > MAX_LOG) state.log = state.log.slice(-400);
    var el = $('pgp-log');
    if (!el) return;
    el.textContent = state.log.join('\n');
    var auto = $('pgp-autoscroll');
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
        append('> start (pool=' + avail + ', tg=' + connected + '/' + enabled.length +
               ', parallel=' + conc + ', target=' + (target || '∞') +
               ', ' + (state.headless ? 'headless' : 'visible') + ')');
        post('/api/tg/start', {
          concurrency: conc,
          target: target,
          headless: state.headless,
          captcha: 'extension',
          tg_task: TASK,
          tg_bot: BOT_ID,
          add_email: false,
          use_ig_pool: true
        });
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
    var isMine = !!(running && activeBot === BOT_ID && cfg.use_ig_pool);
    var isOther = !!(running && activeBot && !isMine);
    var otherName = activeBot === 'fastpay' ? 'FastPay' : activeBot === 'taskly' ? 'Taskly' : (activeBot || '');

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
        ? ('PayGo Pool · parallel ' + (cfg.concurrency || '-') + ' · ' + (cfg.headless ? 'headless' : 'visible'))
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

  function refreshAuto() {
    fetch('/api/tg/paygo-auto/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var st = j && j.status ? j.status : null;
        if (!st) return;
        state.auto = st;
        var sw = $('pgp-auto-sw'); if (sw) sw.checked = !!st.enabled;
        var conc = st.concurrency || 6;
        var pill = $('pgp-auto-pill');
        if (pill) {
          if (st.is_paygo_active) {
            pill.textContent = '⚡ Active (draining ' + conc + ' slots)';
            pill.style.background = 'rgba(16,185,129,0.18)';
            pill.style.borderColor = 'rgba(16,185,129,0.4)';
            pill.style.color = '#34d399';
            pill.style.fontWeight = '700';
          } else if (st.enabled) {
            if (typeof st.wait_seconds === 'number' && st.wait_seconds >= 0) {
              var mm = Math.floor(st.wait_seconds / 60);
              var ss = st.wait_seconds % 60;
              var sStr = ss < 10 ? '0' + ss : '' + ss;
              pill.textContent = (state.running ? '🛡️ Preempting in ' : '⏳ Armed: refill in ')
                + mm + 'm ' + sStr + 's (' + conc + ' slots)';
            } else {
              pill.textContent = '⏳ Armed (' + conc + ' slots)';
            }
            pill.style.background = 'rgba(245,158,11,0.14)';
            pill.style.borderColor = 'rgba(245,158,11,0.35)';
            pill.style.color = '#fbbf24';
            pill.style.fontWeight = '600';
          } else {
            pill.textContent = 'Auto-Mine Off';
            pill.style.background = 'rgba(255,255,255,0.04)';
            pill.style.borderColor = 'rgba(255,255,255,0.08)';
            pill.style.color = 'var(--text-muted)';
            pill.style.fontWeight = '600';
          }
        }
        var concEl = $('pgp-auto-conc'); if (concEl && st.concurrency) concEl.value = st.concurrency;
      })
      .catch(function () {});
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
    refreshAuto();
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
    if ($('pgp-conc')) {
      try { var saved = localStorage.getItem('nova_pgp_parallel'); if (saved) $('pgp-conc').value = saved; } catch (e) {}
      $('pgp-conc').addEventListener('change', function () {
        try { localStorage.setItem('nova_pgp_parallel', this.value); } catch (e) {}
      });
    }
    if ($('pgp-auto-sw')) {
      $('pgp-auto-sw').addEventListener('change', function () {
        var sw = this;
        var conc = parseInt(($('pgp-auto-conc') || {}).value || 6, 10);
        post('/api/tg/paygo-auto/toggle', { enabled: sw.checked, concurrency: conc });
      });
    }
    if ($('pgp-auto-conc')) {
      $('pgp-auto-conc').addEventListener('change', function () {
        var conc = Math.max(1, Math.min(10, parseInt(this.value || 6, 10)));
        this.value = conc;
        var sw = $('pgp-auto-sw');
        post('/api/tg/paygo-auto/toggle', { enabled: sw ? sw.checked : true, concurrency: conc });
      });
    }
    if ($('pgp-clear')) $('pgp-clear').addEventListener('click', function () {
      state.log = []; var el = $('pgp-log'); if (el) el.textContent = '';
    });
    if ($('pgp-copy')) $('pgp-copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(state.log.join('\n')); toast('Log copied', 'success'); } catch (e) {}
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
    try {
      if (!window.__pgpEs) {
        window.__pgpEs = new EventSource('/api/meta-insta/events');
        window.__pgpEs.onmessage = function (ev) {
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
