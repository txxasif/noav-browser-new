/* nova-tasklycookie.js — "Taskly Cookie" panel (POOL DRAIN mode).

 * A NEW, self-contained page that runs TasklyBot's "🍪 Create Inst (No mail)"
 * task the POOL-DRAIN way: it reuses a PRE-CREATED Instagram account from the
 * IG Creator pool — rename via the direct Web API (~0.4s), enable 2FA from the
 * account's STORED mail.td inbox (wait the email OTP), submit the key to Taskly,
 * confirm the returned code, export the IG cookie, submit it, then Confirm.
 * NO Meta signup, NO fresh IG creation. Each pooled account is consumed once.
 *
 * Engine call:
 *   /api/tg/start { tg_task:"Taskly Cookie", tg_bot:"taskly",
 *                   use_ig_pool:true, cookie_2fa:true }
 * → worker.py → run_cookie_cycle (pool path) → own counter
 *   `taskly_cookie_pool`, route tag `tasklycookie`.
 */
(function () {
  'use strict';

  var root = null, timer = null, tick = null;
  var state = {
    running: false,
    headless: true,
    cookie2fa: true,
    source: 'ig',          // 'ig' = IG Creator pool, 'meta' = Meta Creator list
    pool: 0,
    metaList: 0,
    submitted: 0,
    startedAt: 0
  };
  var MAX_LOG = 500;
  var BOT_ID = 'taskly';
  var TASK = 'Taskly Cookie';           // → tg_tasks.COOKIES_NOMAIL_POOL
  var ROUTE = 'tasklycookie';

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
              '<i class="fa-solid fa-cookie-bite" style="color:#4ade80;"></i> Taskly Cookie' +
              '<span class="nav-pill nav-pill--tool" style="background:rgba(74,222,128,.15);color:#4ade80;">POOL DRAIN</span>' +
            '</h2>' +
            '<p style="margin:.35rem 0 0;">Runs Taskly <strong>🍪 Create Inst (No mail)</strong> from the ' +
              '<strong>IG Creator pool</strong> — reuses an existing Instagram account (rename via direct Web API, ' +
              '<strong>2FA</strong> with the stored inbox OTP, then export + submit its IG cookie). ' +
              '<u>No Meta signup, no fresh IG creation.</u> Each pooled account is consumed once.</p>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="tcp-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start Pool Drain</button>' +
            '<button id="tcp-stop" type="button" class="btn btn-danger" style="display:none;"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;">' +
        statCard('IG CREATOR POOL', 'tcp-kpi-pool', 'available accounts ready to drain', '#a5b4fc') +
        statCard('META LIST', 'tcp-kpi-meta', 'Meta accounts ready (IG login)', '#f0abfc') +
        statCard('SUBMITTED (Taskly Cookie)', 'tcp-kpi-submitted', 'cookie task accepted', '#4ade80') +
        statCard('PARALLEL SLOTS', 'tcp-kpi-conc', 'concurrent creators', '#38bdf8') +
        statCard('ENGINE', 'tcp-kpi-status', 'idle', '#229ED9') +
      '</div>' +

      /* ---- live banner ---- */
      '<div id="tcp-banner" style="margin-top:0.9rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem;' +
        'background:linear-gradient(180deg,#111726,#0d1117);border:1px solid var(--border-color);border-radius:12px;padding:14px 16px;">' +
        '<div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">' +
          '<span id="tcp-badge" style="padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;background:#1e293b;color:#94a3b8;border:1px solid #334155;">IDLE</span>' +
          '<span id="tcp-title" style="font-weight:700;color:var(--text-main);font-size:.95rem;">POOL DRAIN STOPPED</span>' +
          '<span id="tcp-sub" style="font-size:.78rem;color:var(--text-muted);border-left:1px solid var(--border-color);padding-left:.75rem;">Ready. Reuses pooled IG accounts — no Meta.</span>' +
        '</div>' +
        '<div style="text-align:right;">' +
          '<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:600;">Execution Time</div>' +
          '<div id="tcp-timer" style="font-size:1rem;font-weight:700;font-family:var(--font-mono);color:var(--text-main);">00:00:00</div>' +
        '</div>' +
      '</div>' +

      /* ---- pipeline ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<h3 class="panel-header" style="margin:0 0 .6rem;"><i class="fa-solid fa-diagram-project" style="color:#229ED9;"></i> Pipeline</h3>' +
        '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;">' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">1 · TASK CREDS</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Lease TG → select <strong>Create Inst (No mail)</strong> → Taskly issues the target login.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">2 · RENAME</div>' +
            '<div id="tcp-step2" style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Pop a pool account → rename via <strong>IG Web API (~0.4s)</strong>.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">3 · 2FA</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Enable 2FA (wait email OTP) → submit key → confirm the bot code.</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">4 · COOKIE EXPORT</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">Build the IG cookie header (<strong>sessionid gate</strong>).</div></div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;">5 · SUBMIT + CONFIRM</div>' +
            '<div style="font-size:.82rem;color:var(--text-main);margin-top:.25rem;">POST the cookie → <strong>Account registered</strong> → account consumed.</div></div>' +
        '</div>' +
      '</div>' +

      /* ---- settings ---- */
      '<div class="card-panel creator-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#229ED9;"></i> Pool Drain Settings</h3>' +
          '<span class="tg-bot-badge" id="tcp-bot-badge">' +
            '<i class="fa-solid fa-bolt" style="color:#229ED9;"></i> Taskly Bot · Create Inst (No mail)' +
          '</span>' +
        '</div>' +
        '<div class="creator-grid">' +
          '<div class="creator-field"><label>Account source</label>' +
            '<select id="tcp-source" class="form-control" title="IG Creator pool = finished IG accounts (rename by API). Meta list = Meta Creator accounts: log in to Instagram, join with the bot username, follow, export the cookie.">' +
              '<option value="ig">IG Creator pool</option><option value="meta">Meta list (IG login)</option></select></div>' +
          '<div class="creator-field"><label>Parallel</label>' +
            '<input id="tcp-conc" class="form-control" type="number" min="1" max="10" value="6" title="Concurrent creators. Capped by the number of enabled Telegram profiles."></div>' +
          '<div class="creator-field"><label>Target (0 = \u221e)</label>' +
            '<input id="tcp-target" class="form-control" type="number" min="0" value="0"></div>' +
          '<div class="creator-field creator-field--switch"><label>Headless</label>' +
            '<label class="switch" title="Run browsers headless (recommended)"><input type="checkbox" id="tcp-headless" checked><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch" id="tcp-c2fa-wrap"><label>2FA + Cookie</label>' +
            '<label class="switch" title="ON (default for this task) = MOCK 2FA mode: rename → follow 5 → submit a MOCK 2FA key (no Accounts-Center, no OTP) → export cookie → submit. OFF = legacy rename + submit the stored cookie (no browser, no 2FA)."><input type="checkbox" id="tcp-cookie2fa" checked><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch" id="tcp-igapi-wrap"><label>API mode</label>' +
            '<label class="switch" title="ON = BROWSERLESS IG private-API path: rename, follow 5 (random from the fixed operator list), REAL 2FA, password, email and cookie all via the API — no browser. OFF = the existing browser logic (default)."><input type="checkbox" id="tcp-igapi"><span class="slider"></span></label></div>' +
          '<div class="creator-field creator-field--switch" id="tcp-igapimock-wrap" style="display:none;"><label>Mock 2FA</label>' +
            '<label class="switch" title="API mode only. ON = submit a MOCK 2FA key and skip the real 2FA enable. OFF (default) = REAL 2FA via the API."><input type="checkbox" id="tcp-igapimock"><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="creator-service-note" style="margin-top:.6rem;">' +
          '<i class="fa-solid fa-circle-info" style="color:#229ED9;"></i> ' +
          'Only Telegram profiles and the IG pool are used. Requires at least one logged-in TG profile and a non-empty IG Creator pool.' +
        '</div>' +
      '</div>' +

      /* ---- live log ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-dim);"><input type="checkbox" id="tcp-autoscroll" checked> Auto-scroll</label>' +
            '<button id="tcp-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="tcp-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="tcp-log" class="log-container" style="height:260px;overflow-y:auto;background:#060910;border:1px solid var(--border-color);' +
          'border-radius:8px;padding:.75rem;font-family:var(--font-mono);font-size:.78rem;white-space:pre-wrap;"></div>' +
      '</div>' +

      /* ---- route-scoped failure reasons + session logs ---- */
      (window.NovaDiag ? NovaDiag.renderHtml('tcp', 'tasklycookie') : '');

    wire();
  }

  function append(line) {
    buf.push(line);
    var el = $('tcp-log');
    if (!el) return;
    el.textContent = buf.text();
    var auto = $('tcp-autoscroll');
    if (!auto || auto.checked) el.scrollTop = el.scrollHeight;
  }

  function post(url, body) { return NovaPoolPanel.postJson(url, body, append, refresh); }

  function start() {
    var btn = $('tcp-start');
    if (btn) btn.disabled = true;
    fetch('/api/tg/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (btn) btn.disabled = false;
        if (!s) throw new Error('status unavailable');
        var pool = (s.pool && s.pool.accounts) || [];
        var enabled = pool.filter(function (p) { return p.enabled !== false; });
        var connected = enabled.filter(function (p) { return p.logged_in === true; }).length;
        if (!pool.length) { append('> blocked: no Telegram account connected.'); toast('No Telegram account is connected. Add one in TG Manager first.', 'error', 14000); return; }
        if (!enabled.length) { append('> blocked: every Telegram profile is disabled.'); toast('Every Telegram profile is disabled. Enable at least one.', 'error', 14000); return; }
        if (!connected) { append('> blocked: no logged-in Telegram profile.'); toast('No logged-in Telegram profile. Log one in, then start.', 'error', 14000); return; }
        var isMeta = state.source === 'meta';
        var avail = isMeta ? (s.meta_list_available || 0) : (s.ig_pool_available || 0);
        if (!avail) {
          var what = isMeta ? 'Meta list' : 'IG Creator pool';
          append('> blocked: ' + what + ' is empty (0).');
          toast(what + ' is empty — nothing to drain.', 'error', 14000);
          return;
        }
        var conc = parseInt(($('tcp-conc') || {}).value || 1, 10);
        var target = parseInt(($('tcp-target') || {}).value || 0, 10);
        var c2fa = $('tcp-cookie2fa') ? $('tcp-cookie2fa').checked : true;
        var apiOn = (state.source === 'meta') ? false : ($('tcp-igapi') ? $('tcp-igapi').checked : false);
        var apiMockOn = $('tcp-igapimock') ? $('tcp-igapimock').checked : false;
        var task = TASK;
        state.cookie2fa = c2fa;
        append('> start (' + (isMeta ? 'meta-list=' : 'pool=') + avail + ', tg=' + connected + '/' + enabled.length +
               ', parallel=' + conc + ', target=' + (target || '∞') +
               ', ' + (state.headless ? 'headless' : 'visible') +
               ', 2fa+cookie=' + (c2fa ? 'ON' : 'OFF') +
               ', api=' + (apiOn ? (apiMockOn ? 'MOCK-2FA' : 'REAL-2FA') : 'OFF') + ')');
        var _doPost = function () { post('/api/tg/start', {
          concurrency: conc,
          target: target,
          headless: state.headless,
          captcha: 'extension',
          tg_task: task,
          tg_bot: BOT_ID,
          add_email: false,
          use_ig_pool: true,
          account_source: state.source,
          cookie_2fa: c2fa,
          ig_api: apiOn,
          ig_api_mock: (apiOn && apiMockOn)
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

  // Attribution: only claim "LIVE" when the active engine is genuinely the
  // Taskly cookie POOL drain (not the Taskly 2FA pool, not the classic bot).
  function setRunning(running, cfg) {
    state.running = !!running;
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = 0;

    cfg = cfg || {};
    var activeBot = cfg.tg_bot ? String(cfg.tg_bot).toLowerCase() : null;
    var cfgTask = String(cfg.tg_task || '');
    // Taskly cookie POOL drain belongs to this page.
    var isMine = !!(running && activeBot === BOT_ID && cfg.use_ig_pool
                    && /taskly cookie/i.test(cfgTask));
    var isOther = !!(running && activeBot && !isMine);
    var otherName = activeBot === 'fastpay' ? 'FastPay' : activeBot === 'taskly' ? 'Taskly'
      : activeBot === 'paygo' ? 'PayGo' : (activeBot || '');

    var badge = $('tcp-badge'), title = $('tcp-title'), sub = $('tcp-sub');
    var startBtn = $('tcp-start'), stopBtn = $('tcp-stop');
    if (badge) {
      badge.textContent = isMine ? 'LIVE' : (isOther ? (otherName.toUpperCase() + ' RUNNING') : 'IDLE');
      badge.style.background = isMine ? 'rgba(74,222,128,.18)' : (isOther ? 'rgba(34,158,217,.2)' : '#1e293b');
      badge.style.color = isMine ? '#4ade80' : (isOther ? '#229ED9' : '#94a3b8');
      badge.style.borderColor = (isMine || isOther) ? 'rgba(74,222,128,.4)' : '#334155';
    }
    if (title) {
      title.textContent = isMine ? 'POOL DRAIN RUNNING'
        : isOther ? (otherName.toUpperCase() + ' IS RUNNING · TASKLY COOKIE IDLE')
        : 'POOL DRAIN STOPPED';
    }
    if (sub) {
      sub.textContent = isMine
        ? ('Taskly Create Inst (No mail) · parallel ' + (cfg.concurrency || '-') + ' · ' + (cfg.headless ? 'headless' : 'visible'))
        : isOther
          ? ('⚡ ' + otherName + ' is running (one engine at a time). Stop it from its own page.')
          : (state.source === 'meta' ? 'Ready. Logs Meta-list accounts in to Instagram.' : 'Ready. Reuses pooled IG accounts — no Meta.');
    }
    state.isMine = isMine;
    if (startBtn) startBtn.style.display = running ? 'none' : 'inline-flex';
    if (stopBtn) {
      stopBtn.style.display = isMine ? 'inline-flex' : 'none';
      stopBtn.title = 'Stop the Taskly cookie pool drain';
    }
    var kpi = $('tcp-kpi-status');
    if (kpi) {
      kpi.textContent = isMine ? 'LIVE' : (isOther ? otherName.toUpperCase() : 'IDLE');
      kpi.style.color = (isMine || isOther) ? '#4ade80' : '#229ED9';
    }
    if (kpi && kpi.nextElementSibling) kpi.nextElementSibling.textContent = isMine ? (state.source === 'meta' ? 'draining the Meta list' : 'draining the IG pool') : (isOther ? (otherName + ' is running') : 'idle');
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('tcp-timer');
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
        state.metaList = s.meta_list_available || 0;
        state.submitted = s.tg_submitted_taskly_cookie_pool || 0;
        var p = $('tcp-kpi-pool'); if (p) p.textContent = String(state.pool);
        var ml = $('tcp-kpi-meta'); if (ml) ml.textContent = String(state.metaList);
        var sub = $('tcp-kpi-submitted'); if (sub) sub.textContent = String(state.submitted);
        var c = $('tcp-kpi-conc'); if (c) c.textContent = String((s.engine && s.engine.concurrency) || 0);
      })
      .catch(function () {});
  }

  function handleEvent(d) {
    if (!d) return;
    // Route-scoped: this panel only shows the tasklycookie route.
    if (d.route && d.route !== ROUTE) return;
    if (d.pipeline && d.pipeline !== 'telegram') return;
    var bot = d.tg_bot ? String(d.tg_bot).toLowerCase() : null;
    if (bot && bot !== BOT_ID) return;
    var msg = d.message ||
      (d.type === 'slot_event' && d.detail ? ('[Slot ' + (d.slot_id || '?') + '] ' + d.detail) : null);
    if (msg) append(String(msg));
    if (d.type === 'loop_stopped') { append('[engine] loop stopped' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : '')); refresh(); }
  }

  // Reflect the chosen account source in the pipeline copy.
  function applySource() {
    var meta = state.source === 'meta';
    var s2 = $('tcp-step2');
    if (s2) s2.innerHTML = meta
      ? 'Claim a Meta-list account → <strong>IG login</strong> (before the task) → join with the bot username → follow.'
      : 'Pop a pool account → rename via <strong>IG Web API (~0.4s)</strong>.';
    var sub = $('tcp-sub');
    if (sub && !state.running) sub.textContent = meta
      ? 'Ready. Logs Meta-list accounts in to Instagram.'
      : 'Ready. Reuses pooled IG accounts — no Meta.';
    var sel = $('tcp-source'); if (sel && sel.value !== state.source) sel.value = state.source;
    // Meta list ignores these (it always joins + follows in the browser and
    // sends the mock 2FA key whenever the task asks for one) — hide them.
    ['tcp-c2fa-wrap', 'tcp-igapi-wrap'].forEach(function (id) {
      var w = $(id); if (w) w.style.display = meta ? 'none' : '';
    });
    var mw = $('tcp-igapimock-wrap');
    if (mw) mw.style.display = (!meta && $('tcp-igapi') && $('tcp-igapi').checked) ? '' : 'none';
  }

  function wire() {
    if ($('tcp-source')) {
      try { if (localStorage.getItem('nova_tcp_source') === 'meta') state.source = 'meta'; } catch (e) {}
      $('tcp-source').addEventListener('change', function () {
        state.source = this.value === 'meta' ? 'meta' : 'ig';
        try { localStorage.setItem('nova_tcp_source', state.source); } catch (e) {}
        applySource();
      });
      applySource();
    }
    if ($('tcp-start')) $('tcp-start').addEventListener('click', start);
    if ($('tcp-stop')) $('tcp-stop').addEventListener('click', stop);
    if ($('tcp-headless')) $('tcp-headless').addEventListener('change', function () { state.headless = this.checked; });
    if ($('tcp-igapi')) {
      try { if (localStorage.getItem('nova_tcp_igapi') === '1') $('tcp-igapi').checked = true; } catch (e) {}
      var syncMock = function () {
        var w = $('tcp-igapimock-wrap');
        if (w) w.style.display = $('tcp-igapi').checked ? '' : 'none';
      };
      $('tcp-igapi').addEventListener('change', function () {
        try { localStorage.setItem('nova_tcp_igapi', this.checked ? '1' : '0'); } catch (e) {}
        syncMock();
      });
      syncMock();
    }
    if ($('tcp-igapimock')) {
      try { if (localStorage.getItem('nova_tcp_igapimock') === '1') $('tcp-igapimock').checked = true; } catch (e) {}
      $('tcp-igapimock').addEventListener('change', function () {
        try { localStorage.setItem('nova_tcp_igapimock', this.checked ? '1' : '0'); } catch (e) {}
      });
    }
    if ($('tcp-cookie2fa')) {
      try { if (localStorage.getItem('nova_tcp_cookie2fa') === '0') { $('tcp-cookie2fa').checked = false; state.cookie2fa = false; } } catch (e) {}
      $('tcp-cookie2fa').addEventListener('change', function () {
        state.cookie2fa = this.checked;
        try { localStorage.setItem('nova_tcp_cookie2fa', this.checked ? '1' : '0'); } catch (e) {}
      });
    }
    if ($('tcp-conc')) {
      try { var saved = localStorage.getItem('nova_tcp_parallel'); if (saved) $('tcp-conc').value = saved; } catch (e) {}
      $('tcp-conc').addEventListener('change', function () {
        try { localStorage.setItem('nova_tcp_parallel', this.value); } catch (e) {}
      });
    }
    if ($('tcp-clear')) $('tcp-clear').addEventListener('click', function () {
      buf.clear(); var el = $('tcp-log'); if (el) el.textContent = '';
    });
    if ($('tcp-copy')) $('tcp-copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(buf.text()); toast('Log copied', 'success'); } catch (e) {}
    });    // Re-apply last: the saved API-mode state must not re-show Mock 2FA for Meta list.
    applySource();
  }

  function boot() {
    root = $('tg-tasklycookie-root');
    if (!root) return;
    shell();
    if (window.NovaDiag) { NovaDiag.refreshReasons(); NovaDiag.refreshLogs(); }
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 4000);
    if (tick) clearInterval(tick);
    tick = setInterval(tickTimer, 1000);
    // Shared SSE hub (nova-core.js): one stream per page.
    NovaPoolPanel.subscribe(handleEvent, 'tcp');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
