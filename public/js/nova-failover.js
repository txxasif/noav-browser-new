/* nova-failover.js — "Cookie Fleet" UNIVERSAL page (#/failover).
 *
 * One controller for every cookie drain: pick the task (same labels as the
 * main TG Classic UI), pick Pool or Classic mode, order the bot priority, set
 * Parallel, and Start from here. The engine tries bots in priority order —
 * first available task wins; sold out (0 left) / hidden / unoffered falls to
 * the next bot automatically, no restart needed.
 *
 * Engine call:
 *   /api/tg/start { tg_task, tg_bot, use_ig_pool, cookie_2fa, fallback:true,
 *                   concurrency }
 * → worker.py --tg-fallback → run_cookie_cycle (pool or classic path).
 * Priority lives server-side: GET/POST /api/tg/cookie-priority.
 */
(function () {
  'use strict';

  var root = null, timer = null, tick = null;
  var state = {
    running: false,
    headless: true,
    chain: [],            // ordered rowKeys: the run order (1-2-3)
    catalog: [],
    bots: ['paygo', 'taskly', 'fastpay'],
    pool: 0,
    submitted: 0,
    opts: {},             // rowKey -> {c2fa: bool} per-task options
    lastStart: null,      // {bot, task} of the run started from here
    startedAt: 0
  };
  var MAX_LOG = 500;

  // Every task, grouped by bot (from /api/tg/catalog — tg_tasks.py is truth).
  // Row identity: "bot|id|mode". cookie_2fa is sent for pool-cookie rows only.
  var BOT_NAME = { paygo: 'PayGo', taskly: 'Taskly', fastpay: 'FastPay' };

  function rowKey(r) { return r.bot + '|' + r.id + '|' + r.mode; }

  function poolRows() {
    return state.catalog.filter(function (r) {
      return r.mode === 'pool' && state.bots.indexOf(r.bot) !== -1;
    });
  }

  function rowByKey(key) {
    for (var i = 0; i < state.catalog.length; i++) {
      if (rowKey(state.catalog[i]) === key) return state.catalog[i];
    }
    return null;
  }

  function chainRows() {
    // Ordered, valid, pool-only — stale keys dropped.
    var out = [];
    for (var i = 0; i < state.chain.length; i++) {
      var r = rowByKey(state.chain[i]);
      if (r && r.mode === 'pool' && state.bots.indexOf(r.bot) !== -1) out.push(r);
    }
    return out;
  }

  function $(id) { return document.getElementById(id); }

  var toast = NovaPoolPanel.toast;
  var statCard = NovaPoolPanel.statCard;
  var buf = NovaPoolPanel.logBuffer(MAX_LOG);

  function loadCatalog() {
    fetch('/api/tg/catalog', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && j.ok && Array.isArray(j.tasks) && j.tasks.length) {
          state.catalog = j.tasks;
          renderTasks();
          renderOrder();
          updateFoNote();
        }
      })
      .catch(function () {});
  }

  function shell() {
    root.innerHTML =
      '<style>' +
      '.fo-taskrow{display:flex;align-items:center;gap:.6rem;padding:.55rem .7rem;border-radius:10px;cursor:pointer;border:1px solid transparent;transition:background .12s,border-color .12s;}' +
      '.fo-taskrow:hover{background:rgba(148,163,184,.07);}' +
      '.fo-taskrow:has(input:checked){background:rgba(74,222,128,.09);border-color:rgba(74,222,128,.4);box-shadow:0 0 0 1px rgba(74,222,128,.25),0 4px 14px -6px rgba(74,222,128,.35);}' +
      '.fo-taskrow input{accent-color:#4ade80;width:15px;height:15px;flex:none;}' +
      '.fo-taskrow.picked{background:rgba(74,222,128,.09);border-color:rgba(74,222,128,.4);box-shadow:0 0 0 1px rgba(74,222,128,.25),0 4px 14px -6px rgba(74,222,128,.35);}' +
      '.fo-ord{display:inline-flex;align-items:center;justify-content:center;min-width:1.35rem;height:1.35rem;border-radius:999px;background:rgba(74,222,128,.18);border:1px solid rgba(74,222,128,.5);color:#4ade80;font-weight:800;font-size:.72rem;flex:none;}' +
      '.fo-add{display:inline-flex;align-items:center;justify-content:center;min-width:1.35rem;height:1.35rem;border-radius:999px;background:rgba(148,163,184,.1);border:1px dashed rgba(148,163,184,.4);color:var(--text-muted);font-weight:700;font-size:.8rem;flex:none;}' +
      '.fo-taskrow:hover .fo-add{border-color:#4ade80;color:#4ade80;}' +
      '.fo-taskmeta{font-size:.68rem;color:var(--text-muted);white-space:nowrap;}' +
      '.fo-price{color:#fbbf24;font-weight:700;}' +
      '.fo-pill{font-size:.62rem;font-weight:800;letter-spacing:.05em;padding:2px 8px;border-radius:999px;white-space:nowrap;}' +
      '.fo-pill-pool{background:rgba(74,222,128,.14);color:#4ade80;border:1px solid rgba(74,222,128,.35);}' +
      '.fo-pill-classic{background:rgba(245,158,11,.13);color:#fbbf24;border:1px solid rgba(245,158,11,.35);}' +
      '.fo-bothead{display:flex;align-items:center;gap:.55rem;margin:.85rem 0 .35rem;padding:.45rem .7rem;background:linear-gradient(180deg,rgba(148,163,184,.09),rgba(148,163,184,.04));border:1px solid rgba(148,163,184,.12);border-radius:9px;}' +
      '.fo-bothead:first-child{margin-top:0;}' +
      '.fo-count{font-size:.64rem;color:var(--text-muted);background:rgba(148,163,184,.12);padding:1px 8px;border-radius:999px;}' +
      '.fo-priorow{display:flex;align-items:center;gap:.5rem;padding:.35rem .4rem;border-radius:8px;}' +
      '.fo-priorow:hover{background:rgba(148,163,184,.07);}' +
      '.fo-btn{background:rgba(148,163,184,.1);border:1px solid var(--border-color);border-radius:7px;color:var(--text-main);padding:.25rem .6rem;cursor:pointer;font-size:.8rem;line-height:1.2;}' +
      '.fo-btn:hover{background:rgba(148,163,184,.22);}' +
      '.fo-grid2{display:grid;grid-template-columns:1.4fr 1fr;gap:10px;margin-bottom:10px;}' +
      '@media (max-width:900px){.fo-grid2{grid-template-columns:1fr;}}' +
      '</style>' +
      '<div class="page-title-box" style="margin-bottom:1rem;">' +
        '<div class="page-title-row" style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap;">' +
          '<div>' +
            '<h2 style="margin:0;display:flex;align-items:center;gap:.5rem;">' +
              '<i class="fa-solid fa-shuffle" style="color:#4ade80;"></i> Cookie Fleet' +
              '<span class="nav-pill nav-pill--tool" style="background:rgba(74,222,128,.15);color:#4ade80;">AUTO FAILOVER</span>' +
            '</h2>' +
            '<p style="margin:.35rem 0 0;">Universal pool controller — click pool tasks to order them <strong>1-2-3</strong>, set <strong>Parallel</strong>, Start. ' +
              'The engine runs them in order; unavailable tasks are skipped automatically, no restart needed.</p>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="fo-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start Fleet</button>' +
            '<button id="fo-stop" type="button" class="btn btn-danger" style="display:none;"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('IG CREATOR POOL', 'fo-kpi-pool', 'available accounts ready to drain', '#a5b4fc') +
        statCard('SUBMITTED (Fleet)', 'fo-kpi-submitted', 'cookie tasks accepted', '#4ade80') +
        statCard('PARALLEL SLOTS', 'fo-kpi-conc', 'concurrent creators', '#38bdf8') +
        statCard('ENGINE', 'fo-kpi-status', 'idle', '#4ade80') +
      '</div>' +

      '<div id="fo-banner" style="margin-top:0.9rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem;' +
        'background:linear-gradient(180deg,#111726,#0d1117);border:1px solid var(--border-color);border-radius:12px;padding:14px 16px;">' +
        '<div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">' +
          '<span id="fo-badge" style="padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;background:#1e293b;color:#94a3b8;border:1px solid #334155;">IDLE</span>' +
          '<span id="fo-title" style="font-weight:700;color:var(--text-main);font-size:.95rem;">FLEET STOPPED</span>' +
          '<span id="fo-sub" style="font-size:.78rem;color:var(--text-muted);border-left:1px solid var(--border-color);padding-left:.75rem;">Pick a task and press Start.</span>' +
        '</div>' +
        '<div style="text-align:right;">' +
          '<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:600;">Execution Time</div>' +
          '<div id="fo-timer" style="font-size:1rem;font-weight:700;font-family:var(--font-mono);color:var(--text-main);">00:00:00</div>' +
        '</div>' +
      '</div>' +

      '<div class="card-panel creator-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#4ade80;"></i> Fleet Controller</h3>' +
          '<span class="tg-bot-badge" id="fo-bot-badge">Cookie bots · failover</span>' +
        '</div>' +
        '<div class="fo-grid2">' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;margin-bottom:.4rem;">TASK MENU — EVERY TASK, BY BOT</div>' +
            '<div id="fo-tasks"></div>' +
          '</div>' +
          '<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;padding:12px;">' +
            '<div style="font-size:.7rem;color:var(--text-muted);font-weight:700;margin-bottom:.4rem;">RUN ORDER</div>' +
            '<div id="fo-order" style="font-size:.82rem;color:var(--text-main);"></div>' +
            '<div style="font-size:.72rem;color:var(--text-muted);margin-top:.5rem;">Click tasks left to add them in order — 1 runs first, then 2, then 3. Unavailable tasks are skipped automatically, no restart needed.</div>' +
          '</div>' +
        '</div>' +
        '<div class="creator-grid">' +
          '<div class="creator-field"><label>Parallel (all slots)</label>' +
            '<input id="fo-conc" class="form-control" type="number" min="1" max="60" value="6" title="Concurrent creators for this run. Capped by the number of enabled Telegram profiles."></div>' +
          '<div class="creator-field"><label>Target (0 = \u221e)</label>' +
            '<input id="fo-target" class="form-control" type="number" min="0" value="0"></div>' +
          '<div class="creator-field creator-field--switch"><label>Headless</label>' +
            '<label class="switch" title="Run browsers headless (recommended)"><input type="checkbox" id="fo-headless" checked><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="creator-service-note" style="margin-top:.6rem;">' +
          '<i class="fa-solid fa-circle-info" style="color:#4ade80;"></i> ' +
          'Requires at least one logged-in TG profile. Pool mode also needs a non-empty IG Creator pool (the drain waits if it empties mid-run).' +
        '</div>' +
      '</div>' +

      '<div class="card-panel" style="margin-top:1rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-dim);"><input type="checkbox" id="fo-autoscroll" checked> Auto-scroll</label>' +
            '<button id="fo-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="fo-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="fo-log" class="log-container" style="height:260px;overflow-y:auto;background:#060910;border:1px solid var(--border-color);' +
          'border-radius:8px;padding:.75rem;font-family:var(--font-mono);font-size:.78rem;white-space:pre-wrap;"></div>' +
      '</div>';

    wire();
  }

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  // Bot button labels carry emoji (📱/🍪/🔥) that render as tofu on systems
  // without an emoji font — show the bot logo + clean text instead.
  function cleanLabel(s) {
    try {
      return String(s == null ? '' : s).replace(/\p{Extended_Pictographic}/gu, '').replace(/\uFE0F/g, '').replace(/\s{2,}/g, ' ').trim();
    } catch (e) {
      return String(s == null ? '' : s).replace(/[^\x00-\x7F]+/g, '').replace(/\s{2,}/g, ' ').trim();
    }
  }

  // Task logo = the task's own leading emoji, exactly as the TG Classic
  // sidebar shows it (📱 phone, 🍪 cookie, 🔥 fire). Falls back to the bot
  // logo for labels without one (FastPay).
  function taskLogo(t) {
    var label = String((t && t.label) || '');
    var m = null;
    try {
      m = label.match(/^(\p{Extended_Pictographic}\uFE0F?)/u);
    } catch (e) { m = null; }
    if (m) return '<span style="font-size:.95rem;width:1.4rem;text-align:center;flex:none;">' + esc(m[1]) + '</span>';
    return '<img src="img/bot_logo/' + t.bot + '.png" width="18" height="18" ' +
      'style="border-radius:5px;object-fit:cover;flex:none;" onerror="this.style.display=\'none\'" alt="">';
  }

  function renderTasks() {
    var el = $('fo-tasks');
    if (!el) return;
    var html = '';
    var order = ['paygo', 'taskly', 'fastpay'];
    for (var bi = 0; bi < order.length; bi++) {
      var b = order[bi];
      if (state.bots.indexOf(b) === -1) continue;
      var rows = state.catalog.filter(function (r) { return r.bot === b && r.mode === 'pool'; });
      if (!rows.length) continue;
      html += '<div class="fo-bothead">' +
        '<img src="img/bot_logo/' + b + '.png" width="20" height="20" style="border-radius:6px;object-fit:cover;flex:none;" onerror="this.style.display=\'none\'">' +
        '<span style="font-size:.78rem;font-weight:800;color:var(--text-main);letter-spacing:.05em;">' + (BOT_NAME[b] || b).toUpperCase() + '</span>' +
        '<span class="fo-count">' + rows.length + ' pool task' + (rows.length > 1 ? 's' : '') + '</span></div>';
      for (var i = 0; i < rows.length; i++) {
        var t = rows[i], key = rowKey(t);
        var pos = state.chain.indexOf(key);
        var metas = [];
        if (t.price) metas.push('<span class="fo-price">$' + esc(t.price) + '</span>');
        if (t.follow) metas.push('<span>follow ' + t.follow + '</span>');
        html += '<div class="fo-taskrow' + (pos !== -1 ? ' picked' : '') + '" data-fo-pick="' + esc(key) + '" title="Click to ' + (pos !== -1 ? 'remove from' : 'add to') + ' the run order · ' + esc(t.label + ' · ' + t.flow + ' · ' + (t.steps || []).join(' → ')) + '">' +
          (pos !== -1
            ? '<span class="fo-ord">' + (pos + 1) + '</span>'
            : '<span class="fo-add">+</span>') +
          taskLogo(t) +
          '<span style="flex:1;font-size:.84rem;color:var(--text-main);">' + esc(cleanLabel(t.label)) +
          (metas.length ? ' <span class="fo-taskmeta">(' + metas.join(' · ') + ')</span>' : '') + '</span> ' +
          '<span class="fo-pill fo-pill-pool">POOL</span></div>';
      }
    }
    if (!html) html = '<span style="font-size:.78rem;color:var(--text-muted);">No pool tasks in this build.</span>';
    el.innerHTML = html;
    var picks = el.querySelectorAll('[data-fo-pick]');
    for (var k = 0; k < picks.length; k++) {
      picks[k].addEventListener('click', function () {
        togglePick(this.getAttribute('data-fo-pick'));
      });
    }
  }

  function togglePick(key) {
    var at = state.chain.indexOf(key);
    if (at !== -1) state.chain.splice(at, 1);
    else state.chain.push(key);
    try { localStorage.setItem('nova_fo_chain', JSON.stringify(state.chain)); } catch (e) {}
    renderTasks();
    renderOrder();
    updateFoNote();
  }

  function updateFoNote() {
    var c = chainRows();
    var badge = $('fo-bot-badge');
    if (!badge) return;
    if (!c.length) { badge.textContent = 'Pick tasks in run order (1-2-3…)'; return; }
    var r = c[0];
    badge.textContent = (BOT_NAME[r.bot] || r.bot) + ' · ' + cleanLabel(r.label) + ' · POOL' +
      (c.length > 1 ? ' → +' + (c.length - 1) + ' fallback' : '');
  }

  function syncFoInputs() {
    var h = $('fo-headless'); if (h) h.checked = !!state.headless;
  }

  function optFor(key) {
    var o = state.opts[key];
    if (!o) { o = { c2fa: true }; state.opts[key] = o; }
    return o;
  }

  function renderOrder() {
    var el = $('fo-order');
    if (!el) return;
    var c = chainRows();
    if (!c.length) {
      el.innerHTML = '<span style="color:var(--text-muted);">Nothing picked — click tasks on the left.</span>';
      return;
    }
    var html = '';
    for (var i = 0; i < c.length; i++) {
      var key = rowKey(c[i]);
      var optsHtml = '';
      if (c[i].family === 'cookie') {
        var on = optFor(key).c2fa !== false;
        optsHtml = '<label style="display:flex;align-items:center;gap:.4rem;font-size:.72rem;color:var(--text-muted);cursor:pointer;margin-left:auto;" title="ON = follow (if still owed) + MOCK 2FA key, then cookie. OFF = legacy rename + stored cookie, no browser. Browser opens ONLY when follows are still owed."><input type="checkbox" data-fo-opt="' + esc(key) + '" style="accent-color:#4ade80;"' + (on ? ' checked' : '') + '> 2FA + Cookie</label>';
      } else {
        optsHtml = '<span style="font-size:.68rem;color:var(--text-muted);margin-left:auto;">no options · runs direct</span>';
      }
      html += '<div style="display:flex;align-items:center;gap:.5rem;padding:.32rem 0;">' +
        '<span class="fo-ord">' + (i + 1) + '</span>' +
        taskLogo(c[i]) +
        '<span style="font-size:.82rem;color:var(--text-main);">' + esc(cleanLabel(c[i].label)) + '</span>' +
        '<span style="font-size:.68rem;color:var(--text-muted);">' + (BOT_NAME[c[i].bot] || c[i].bot) + '</span>' +
        optsHtml + '</div>';
    }
    el.innerHTML = html;
    var boxes = el.querySelectorAll('[data-fo-opt]');
    for (var k = 0; k < boxes.length; k++) {
      boxes[k].addEventListener('change', function () {
        optFor(this.getAttribute('data-fo-opt')).c2fa = this.checked;
        try { localStorage.setItem('nova_fo_opts', JSON.stringify(state.opts)); } catch (e) {}
      });
    }
  }

  function append(line) {
    buf.push(line);
    var el = $('fo-log');
    if (!el) return;
    el.textContent = buf.text();
    var auto = $('fo-autoscroll');
    if (!auto || auto.checked) el.scrollTop = el.scrollHeight;
  }

  function post(url, body) { return NovaPoolPanel.postJson(url, body, append, refresh); }

  function start() {
    var btn = $('fo-start');
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
        var chain = chainRows();
        if (!chain.length) { toast('Pick at least one pool task — click tasks to order them 1-2-3.', 'error', 8000); return; }
        if (!avail) { toast('IG Creator pool is empty — nothing to drain.', 'error', 14000); return; }
        var conc = parseInt(($('fo-conc') || {}).value || 1, 10);
        var target = parseInt(($('fo-target') || {}).value || 0, 10);
        var first = chain[0];
        var fleet = chain.map(function (r) {
          return { bot: r.bot, task: r.start_task, pool: true,
                   c2fa: (r.family === 'cookie') ? (optFor(rowKey(r)).c2fa !== false) : false };
        });
        state.lastStart = { bot: first.bot, task: first.start_task };
        append('> start (pool=' + avail + ', tg=' + connected + '/' + enabled.length +
               ', parallel=' + conc + ', target=' + (target || '∞') +
               ', ' + (state.headless ? 'headless' : 'visible') +
               ', chain=' + chain.map(function (r, i) {
                 var flag = (r.family === 'cookie') ? (optFor(rowKey(r)).c2fa !== false ? '[2fa]' : '[legacy]') : '';
                 return (i + 1) + '.' + r.bot + '/' + cleanLabel(r.label) + flag;
               }).join(' → ') + ')');
        var _doPost = function () { post('/api/tg/start', {
          concurrency: conc,
          target: target,
          headless: state.headless,
          captcha: 'extension',
          tg_task: first.start_task,
          tg_bot: first.bot,
          add_email: false,
          use_ig_pool: true,
          cookie_2fa: (first.family === 'cookie') && (optFor(rowKey(first)).c2fa !== false),
          fallback: true,
          fleet: fleet
        }); };
        if (typeof window.__tgTaskCheck === 'function') {
          window.__tgTaskCheck(first.bot, first.start_task, append).then(function (pre) {
            if (pre.proceed) _doPost();
            else { append('! primary unavailable — chain ON, starting anyway (engine walks 1-2-3)'); _doPost(); }
          });
        } else _doPost();
      })
      .catch(function (e) { if (btn) btn.disabled = false; toast('Could not verify the pool: ' + e, 'error', 12000); });
  }

  function stop() {
    if (!state.running || !state.isMine) { toast('Another task is running — stop it from its own page.', 'warn', 10000); return; }
    post('/api/tg/stop', {});
  }

  // Attribution: exact match on the run started from here, else any cookie
  // drain of the family (a pool page may own it).
  function setRunning(running, cfg) {
    state.running = !!running;
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) { state.startedAt = 0; state.lastStart = null; }

    cfg = cfg || {};
    var activeBot = cfg.tg_bot ? String(cfg.tg_bot).toLowerCase() : null;
    var cfgTask = String(cfg.tg_task || '');
    var directHit = !!(state.lastStart && activeBot === state.lastStart.bot && cfgTask === state.lastStart.task);
    var isCookieFam = /cookie|no.mail/i.test(cfgTask) && !/paygo\s*2fa/i.test(cfgTask);
    var famHit = !!(running && (activeBot === 'paygo' || activeBot === 'taskly')
                    && (cfg.use_ig_pool || cfg.fallback) && isCookieFam);
    var isMine = directHit || famHit;
    var isOther = !!(running && activeBot && !isMine);
    var otherName = activeBot === 'fastpay' ? 'FastPay' : activeBot === 'taskly' ? 'Taskly'
      : activeBot === 'paygo' ? 'PayGo' : (activeBot || '');

    var badge = $('fo-badge'), title = $('fo-title'), sub = $('fo-sub');
    var startBtn = $('fo-start'), stopBtn = $('fo-stop');
    if (badge) {
      badge.textContent = isMine ? 'LIVE' : (isOther ? (otherName.toUpperCase() + ' RUNNING') : 'IDLE');
      badge.style.background = isMine ? 'rgba(74,222,128,.18)' : (isOther ? 'rgba(245,158,11,.2)' : '#1e293b');
      badge.style.color = isMine ? '#4ade80' : (isOther ? '#fbbf24' : '#94a3b8');
      badge.style.borderColor = (isMine || isOther) ? 'rgba(74,222,128,.4)' : '#334155';
    }
    if (title) {
      title.textContent = isMine ? 'FLEET RUNNING'
        : isOther ? (otherName.toUpperCase() + ' IS RUNNING · FLEET IDLE')
        : 'FLEET STOPPED';
    }
    if (sub) {
      sub.textContent = isMine
        ? ('Cookie fleet · parallel ' + (cfg.concurrency || '-') + ' · ' + (cfg.headless ? 'headless' : 'visible'))
        : isOther
          ? ('⚡ ' + otherName + ' is running (one engine at a time). Stop it from its own page.')
          : 'Pick a task and press Start.';
    }
    state.isMine = isMine;
    if (startBtn) startBtn.style.display = running ? 'none' : 'inline-flex';
    if (stopBtn) {
      stopBtn.style.display = isMine ? 'inline-flex' : 'none';
      stopBtn.title = 'Stop the cookie fleet';
    }
    var kpi = $('fo-kpi-status');
    if (kpi) {
      kpi.textContent = isMine ? 'LIVE' : (isOther ? otherName.toUpperCase() : 'IDLE');
      kpi.style.color = (isMine || isOther) ? '#4ade80' : '#229ED9';
    }
    if (kpi && kpi.nextElementSibling) kpi.nextElementSibling.textContent = isMine ? 'draining' : (isOther ? (otherName + ' is running') : 'idle');
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('fo-timer');
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
        if (Array.isArray(s.enabled_bots) && s.enabled_bots.length) {
          var nb = s.enabled_bots.filter(function (b) { return b === 'paygo' || b === 'taskly' || b === 'fastpay'; });
          if (nb.length && nb.join() !== state.bots.join()) {
            state.bots = nb;
            renderTasks();
            renderOrder();
            updateFoNote();
          }
        }
        state.pool = s.ig_pool_available || 0;
        state.submitted = (s.tg_submitted_paygo_pool || 0) + (s.tg_submitted_taskly_cookie_pool || 0) +
          (s.tg_submitted_paygo2fa || 0) + (s.tg_submitted_taskly2fa || 0) + (s.tg_submitted_fastpay2fa || 0) +
          (s.tg_submitted_paygo || 0) + (s.tg_submitted_taskly || 0) + (s.tg_submitted_fastpay || 0);
        var p = $('fo-kpi-pool'); if (p) p.textContent = String(state.pool);
        var sub = $('fo-kpi-submitted'); if (sub) sub.textContent = String(state.submitted);
        var c = $('fo-kpi-conc'); if (c) c.textContent = String((s.engine && s.engine.concurrency) || 0);
      })
      .catch(function () {});
  }

  function handleEvent(d) {
    if (!d) return;
    if (d.pipeline && d.pipeline !== 'telegram') return;
    var bot = d.tg_bot ? String(d.tg_bot).toLowerCase() : null;
    if (bot && bot !== 'paygo' && bot !== 'taskly' && bot !== 'fastpay') return;
    var msg = d.message ||
      (d.type === 'slot_event' && d.detail ? ('[Slot ' + (d.slot_id || '?') + '] ' + d.detail) : null);
    if (msg) append(String(msg));
    if (d.type === 'loop_stopped') { append('[engine] loop stopped' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : '')); refresh(); }
  }

  function wire() {
    if ($('fo-start')) $('fo-start').addEventListener('click', start);
    if ($('fo-stop')) $('fo-stop').addEventListener('click', stop);
    if ($('fo-headless')) $('fo-headless').addEventListener('change', function () { state.headless = this.checked; });
    try {
      var saved = null;
      try { saved = JSON.parse(localStorage.getItem('nova_fo_chain') || 'null'); } catch (e) { saved = null; }
      if (Array.isArray(saved)) state.chain = saved.filter(function (k) { return typeof k === 'string'; }).slice(0, 8);
      var so = null;
      try { so = JSON.parse(localStorage.getItem('nova_fo_opts') || 'null'); } catch (e) { so = null; }
      if (so && typeof so === 'object') state.opts = so;
      var cn = localStorage.getItem('nova_fo_parallel'); if (cn && $('fo-conc')) $('fo-conc').value = cn;
    } catch (e) {}
    syncFoInputs();
    renderTasks();
    renderOrder();
    updateFoNote();
    if ($('fo-conc')) $('fo-conc').addEventListener('change', function () {
      try { localStorage.setItem('nova_fo_parallel', this.value); } catch (e) {}
    });
    if ($('fo-clear')) $('fo-clear').addEventListener('click', function () {
      buf.clear(); var el = $('fo-log'); if (el) el.textContent = '';
    });
    if ($('fo-copy')) $('fo-copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(buf.text()); toast('Log copied', 'success'); } catch (e) {}
    });
  }

  function boot() {
    root = $('tg-failover-root');
    if (!root) return;
    shell();
    if (window.NovaDiag) { NovaDiag.refreshReasons(); NovaDiag.refreshLogs(); }
    loadCatalog();
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 4000);
    if (tick) clearInterval(tick);
    tick = setInterval(tickTimer, 1000);
    NovaPoolPanel.subscribe(handleEvent, 'fo');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
