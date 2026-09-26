/* nova-tg.js — TG Classic panel (Meta -> Instagram -> Taskly/PayGo submit).
 *
 * Rewritten clean: the earlier version was patched by successive regex edits
 * and its shell HTML ended up malformed (a stray </div> from removing the old
 * inline add-form). Uses meta_creator's own class vocabulary (card-panel,
 * btn/btn-sm/btn-primary/btn-secondary, creator-field, insta-stat-*, form-control,
 * badge-pill/active/inactive) — all verified present in styles.css.
 *
 * Mirrors meta_auto_ai's TG tab: 4 KPI cards, Creator Settings, mail/captcha/
 * task/bot, a Telegram Profiles list, and a Balances TABLE
 * (Account | Taskly | PayGo | Total + TOTAL row).
 */
(function () {
  'use strict';

  var root = null, timer = null;
  var state = { running: false, igMode: null, pool: [], log: [], cfg: { headless: true } };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function $(id) { return document.getElementById(id); }

  // Toasts — used for operator-actionable conditions (e.g. a pooled account
  // that never joined the selected bot, so its task can never be claimed).
  function toast(msg, kind, ms) {
    var host = $('tg-toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'tg-toast-host';
      host.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;' +
        'display:flex;flex-direction:column;gap:8px;max-width:380px;';
      document.body.appendChild(host);
    }
    var c = kind === 'error' ? 'var(--accent-red)'
          : kind === 'warn'  ? 'var(--accent-amber)'
          : 'var(--accent-green)';
    var el = document.createElement('div');
    el.style.cssText = 'background:var(--bg-card);border:1px solid var(--border-color);' +
      'border-left:3px solid ' + c + ';border-radius:var(--radius-sm);padding:10px 12px;' +
      'color:var(--text-main);font-size:12px;line-height:1.45;box-shadow:0 8px 24px rgba(0,0,0,.45);';
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(function () { try { host.removeChild(el); } catch (e) {} }, ms || 9000);
  }

  function statCard(label, id, sub) {
    // TG accent = --accent-purple, the same one meta_auto_ai's TG tab uses.
    return '<div class="insta-stat-card" style="background:var(--bg-card);' +
             'border:1px solid var(--border-color);border-radius:var(--radius-md);' +
             'padding:14px 16px;position:relative;overflow:hidden;">' +
      '<div style="position:absolute;left:0;top:0;bottom:0;width:3px;' +
             'background:var(--accent-purple);opacity:.9;"></div>' +
      '<div class="insta-stat-label" style="color:var(--text-dim);">' + esc(label) + '</div>' +
      '<div class="insta-stat-value" id="' + id + '" style="color:var(--text-main);">0</div>' +
      '<div class="insta-stat-sub" style="color:var(--text-muted);">' + esc(sub) + '</div></div>';
  }

  // Creator-settings building blocks. The ported panel rendered Mail/Captcha
  // as bare text (looked like empty inputs) and its switch columns used a fixed
  // height + justify-end, so they never lined up with the inputs. These keep
  // every column: label -> control -> hint, with the control on the same
  // vertical grid.
  function tgField(label, control, hint) {
    return '<div class="creator-field"><label>' + label + '</label>' + control +
      (hint ? '<div class="creator-option-hint">' + hint + '</div>' : '') + '</div>';
  }
  function tgSwitch(label, swId, checked, lblId, lblText, hint) {
    return '<div class="creator-field"><label>' + label + '</label>' +
      '<div class="tg-settings-check">' +
        '<label class="switch" title="' + esc(hint) + '">' +
          '<input type="checkbox" id="' + swId + '"' + (checked ? ' checked' : '') + '>' +
          '<span class="slider"></span></label>' +
        '<span class="creator-option-hint" id="' + lblId + '">' + esc(lblText) + '</span>' +
      '</div>' +
      '<div class="creator-option-hint">' + hint + '</div>' +
    '</div>';
  }
  function tgInfo(label, val, sub) {
    return '<div class="creator-field"><label>' + label + '</label>' +
      '<div class="tg-settings-info">' +
        '<div class="tg-settings-info-val">' + val + '</div>' +
        '<div class="tg-settings-info-sub">' + sub + '</div>' +
      '</div></div>';
  }

  function shell() {
    root.innerHTML =
      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('TG - TOTAL ACCOUNTS', 'tg-kpi-total', 'created for Telegram') +
        statCard('TG - PARKED READY', 'tg-kpi-parked', 'created, not submitted') +
        statCard('TG - SUBMITTING', 'tg-kpi-submitting', 'in flight now') +
        statCard('TG - SUBMITTED', 'tg-kpi-submitted', 'task accepted') +
      '</div>' +

      /* ---- Telegram profiles + balances table ---- */
      '<div class="card-panel" style="margin-top:1rem;">' +
        '<div class="card-top">' +
          '<div><strong>Telegram Profiles</strong>' +
          '<div class="creator-option-hint">MTProto logins \u2014 the accounts that submit created accounts</div>' +
          '<div class="creator-option-hint" id="tg-pool-sum">0 / 0 &middot; 0 ready</div></div>' +
          '<div class="button-row">' +
            '<button id="tg-enable-all" class="btn btn-sm btn-secondary">Select All</button>' +
            '<button id="tg-disable-all" class="btn btn-sm btn-secondary">Deselect All</button>' +
            '<button id="tg-add-toggle" class="btn btn-sm btn-primary">+ Add MTProto</button>' +
            '<button id="tg-bal" class="btn btn-sm btn-secondary">Get Balances</button>' +
            '<button id="tg-refresh" class="btn btn-sm btn-secondary">Refresh</button>' +
          '</div>' +
        '</div>' +

        '<div id="tg-bal-wrap" style="display:none;margin-top:12px;">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">' +
            '<strong>Balances</strong>' +
            '<button id="tg-bal-hide" class="btn btn-sm btn-secondary">Hide</button>' +
          '</div>' +
          '<table style="width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums;">' +
            '<thead><tr style="text-align:left;color:var(--text-dim);font-size:11px;text-transform:uppercase;letter-spacing:.05em;">' +
              '<th style="padding:4px 6px;">Account</th>' +
              '<th style="padding:4px 6px;text-align:right;">Taskly</th>' +
              '<th style="padding:4px 6px;text-align:right;">PayGo</th>' +
              '<th style="padding:4px 6px;text-align:right;">Total</th>' +
            '</tr></thead>' +
            '<tbody id="tg-bal-body"></tbody>' +
            '<tfoot><tr style="font-weight:700;border-top:1px solid var(--border-color);">' +
              '<td style="padding:6px;">TOTAL</td>' +
              '<td id="tg-bal-t-taskly" style="padding:6px;text-align:right;">&mdash;</td>' +
              '<td id="tg-bal-t-paygo" style="padding:6px;text-align:right;">&mdash;</td>' +
              '<td id="tg-bal-t-grand" style="padding:6px;text-align:right;">$0.00</td>' +
            '</tr></tfoot>' +
          '</table>' +
        '</div>' +

        '<div id="tg-pool" class="mt-2.5"></div>' +
      '</div>' +

      /* LiveEngineBanner — COPIED from meta_auto_ai/public/index.html */
      '<div id="tg-liveBanner" class="bg-[#111726]/80 rounded-xl border border-slate-800 p-4 flex flex-wrap items-center justify-between gap-4" style="margin-top:1rem;">' +
        '<div class="flex items-center space-x-4 flex-wrap gap-y-2">' +
          '<div class="flex items-center space-x-2">' +
            '<span id="tg-badge" class="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-400 border border-slate-700 tracking-wider">IDLE</span>' +
            '<span id="tg-title" class="font-bold text-white text-sm tracking-wide">TG ENGINE STOPPED</span>' +
          '</div>' +
          '<div id="tg-sub" class="text-xs text-slate-400 border-l border-slate-800 pl-4 hidden md:block">' +
            'Idle. Creators will make accounts for Telegram only.</div>' +
        '</div>' +
        '<div class="flex items-center space-x-4">' +
          '<div class="text-right">' +
            '<div class="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Execution Time</div>' +
            '<div id="tg-timer" class="text-base font-mono font-bold text-white">00:00:00</div>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="tg-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start TG Engine</button>' +
            '<button id="tg-stop" type="button" class="btn btn-danger" style="display:none;" title="Stop the engine and every running creator"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

/* ---- creator settings ---- */
      '<div class="card-panel creator-panel tg-settings">' +
        '<div class="card-top" style="margin-bottom:1rem;">' +
          '<div>' +
            '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:var(--accent-purple);"></i> Creator Settings</h3>' +
            '<div class="panel-desc" style="margin:0;">Applies to the next TG engine start.</div>' +
          '</div>' +
          '<span class="badge-pill bg-muted">Applies on next start</span>' +
        '</div>' +
        '<div class="tg-settings-grid">' +
          tgField('Parallel creators',
            '<input id="tg-conc" class="form-control" type="number" min="1" max="10" value="1">',
            '1&ndash;10 simultaneous creators') +
          tgField('Target goal',
            '<input id="tg-target" class="form-control" type="number" min="0" value="0">',
            '0 = run until stopped') +
          tgField('Task name',
            '<input id="tg-task" class="form-control" value="Create Inst (No mail)">',
            'Submitted for every completed account') +
          tgField('Mining bot',
            '<select id="tg-bot" class="form-control">' +
              '<option value="taskly">Taskly Bot</option>' +
              '<option value="paygo">PayGo Bot</option>' +
            '</select>',
            'Each completed account is submitted to this bot only.') +
          tgSwitch('Visible window', 'tg-vis-sw', true, 'tg-vis-lbl', 'Visible',
            'On = a real browser window opens. Off = background.') +
          tgSwitch('Extra email after 2FA + password', 'tg-adde-sw', true, 'tg-adde-lbl', 'On',
            'Fresh mail.td email before the task registers.') +
          tgInfo('Mail inbox', 'mail.td', 'Only enabled provider') +
          tgInfo('Captcha solver', 'Visual AI &rarr; Audio fallback', 'Audio used if Visual AI stalls') +
        '</div>' +
      '</div>' +

      /* ---- console ---- */
      '<div class="card-panel" style="margin-top:1.25rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:0.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:0.4rem;font-size:0.78rem;color:var(--text-dim);">' +
              '<input type="checkbox" id="tg-autoscroll" checked> Auto-scroll</label>' +
            '<button id="tg-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="tg-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="tg-log" class="log-container" style="height:220px;overflow-y:auto;background:#060910;' +
          'border:1px solid var(--border-color);border-radius:8px;padding:0.75rem;' +
          'font-family:var(--font-mono);font-size:0.78rem;white-space:pre-wrap;"></div>' +
      '</div>';

    wire();
  }

  function setWindow(headless) {
    state.cfg.headless = headless;                       // headless=true -> window OFF
    var sw = $('tg-vis-sw');
    if (sw) sw.checked = !headless;                      // switch ON = visible
    var lbl = $('tg-vis-lbl');
    if (lbl) lbl.textContent = headless ? 'Background' : 'Visible';
  }

  var addEmail = true;
  function setAddEmail(on) {
    addEmail = on;
    var sw = $('tg-adde-sw'); if (sw) sw.checked = on;
    var lbl = $('tg-adde-lbl'); if (lbl) lbl.textContent = on ? 'On' : 'Off';
  }

  // Pool preflight for Start. The coupled cycle creates a Meta account BEFORE
  // leasing a Telegram profile, so an empty/disabled/logged-out pool must be
  // refused here — otherwise we burn a Meta account and only then hit
  // "No Telegram profile is logged in".
  function poolState(rows) {
    var list = rows || [];
    var enabled = list.filter(function (p) { return p.enabled !== false; });
    return {
      total: list.length,
      enabled: enabled.length,
      connected: enabled.filter(function (p) { return p.logged_in === true; }).length,
    };
  }

  function startEngine() {
    var btn = $('tg-start');
    var bot = ($('tg-bot') || {}).value || 'taskly';
    var botName = bot === 'paygo' ? 'PayGo' : 'Taskly';
    if (btn) btn.disabled = true;
    fetch('/api/tg/status').then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (btn) btn.disabled = false;
        if (!s) throw new Error('status unavailable');
        var st = poolState(s.pool && s.pool.accounts);
        if (!st.total) {
          toast('No Telegram account is connected. Click "+ Add MTProto" to log one in, then start.', 'error', 14000);
          append('! start blocked \u2014 no Telegram profile in the pool');
        } else if (!st.enabled) {
          toast('Every Telegram profile is disabled. Enable at least one, then start.', 'error', 14000);
          append('! start blocked \u2014 no enabled Telegram profile');
        } else if (!st.connected) {
          toast('No connected Telegram account for ' + botName + '. Log in (or re-enable) a profile, then start.', 'error', 14000);
          append('! start blocked \u2014 no logged-in Telegram profile for ' + botName);
        } else {
          append('> start (' + st.connected + ' connected \u00b7 ' + botName +
                 ', parallel=' + (($('tg-conc') || {}).value || '?') +
                 ', target=' + (($('tg-target') || {}).value || '?') +
                 ', ' + (state.cfg.headless ? 'background' : 'visible') +
                 ', add_email=' + addEmail + ')');
          post('/api/tg/start', {
            concurrency: parseInt(($('tg-conc') || {}).value || 5, 10),
            target: parseInt(($('tg-target') || {}).value || 0, 10),
            headless: state.cfg.headless,
            tg_task: ($('tg-task') || {}).value || 'Create Inst (No mail)',
            tg_bot: bot,
            add_email: addEmail,
          });
        }
      })
      .catch(function (e) {
        if (btn) btn.disabled = false;
        toast('Could not verify the Telegram pool: ' + e, 'error', 12000);
        append('! start blocked \u2014 ' + e);
      });
  }

  function wire() {
    if ($('tg-start')) $('tg-start').addEventListener('click', startEngine);
    if ($('tg-stop')) $('tg-stop').addEventListener('click', function () { post('/api/tg/stop', {}); });
    if ($('tg-vis-sw')) $('tg-vis-sw').addEventListener('change', function () { setWindow(!$('tg-vis-sw').checked); });
    if ($('tg-adde-sw')) $('tg-adde-sw').addEventListener('change', function () { addEmail = !!$('tg-adde-sw').checked; if ($('tg-adde-lbl')) $('tg-adde-lbl').textContent = addEmail ? 'On' : 'Off'; });
    if ($('tg-refresh')) $('tg-refresh').addEventListener('click', refresh);
    if ($('tg-clear')) $('tg-clear').addEventListener('click', function () { state.log = []; paintLog(); });
    if ($('tg-copy')) $('tg-copy').addEventListener('click', function () {
      var txt = state.log.join('\n');
      try {
        if (navigator.clipboard) navigator.clipboard.writeText(txt);
        else { var t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand('copy'); document.body.removeChild(t); }
        toast('Log copied.', 'ok', 2500);
      } catch (e) { toast('Copy failed: ' + e, 'error'); }
    });
    if ($('tg-bal-hide')) $('tg-bal-hide').addEventListener('click', function () {
      if ($('tg-bal-wrap')) $('tg-bal-wrap').style.display = 'none';
    });
    if ($('tg-add-toggle')) $('tg-add-toggle').addEventListener('click', function () { mtReset(); mtOpen(); });
    if ($('mtOpenGuide')) $('mtOpenGuide').addEventListener('click', function () {
      mtClose();
      var nav = document.querySelector('.nav-item[data-view="view-guide"]');
      if (nav) nav.click();
      var scroller = document.querySelector('.content-scroll');
      if (scroller) scroller.scrollTop = 0;
    });
    if ($('tg-enable-all')) $('tg-enable-all').addEventListener('click', function () { tgEnableAll(true); });
    if ($('tg-disable-all')) $('tg-disable-all').addEventListener('click', function () { tgEnableAll(false); });

    if ($('tg-bal')) $('tg-bal').addEventListener('click', onBalances);
  }

  /* ---------------- Balances (BOTH bots) ---------------- */
  function onBalances() {
    append('> balances (a .session serves one client; leased accounts are skipped)');
    fetch('/api/tg/mtproto/balance_all', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: '{}' })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var accts = (j && j.accounts) || [];
        var NUM = function (b) {
          if (!b || !b.ok) return null;
          var n = parseFloat(String(b.balance == null ? '' : b.balance).replace(/[^0-9.\-]/g, ''));
          return isNaN(n) ? null : n;
        };
        var fmt = function (n) { return n == null ? '\u2014' : '$' + n.toFixed(2); };
        var okCount = 0, tT = 0, tP = 0, tG = 0;

        var body = $('tg-bal-body');
        if (body) body.innerHTML = accts.map(function (a) {
          var bots = a.bots || [];
          var taskly = bots.filter(function (b) { return b.target === 'taskly'; })[0];
          var paygo  = bots.filter(function (b) { return b.target === 'paygo';  })[0];
          var nT = NUM(taskly), nP = NUM(paygo);
          if (taskly && taskly.ok) okCount++;
          if (nT != null) tT += nT;
          if (nP != null) tP += nP;
          var rowTotal = (nT || 0) + (nP || 0);
          tG += rowTotal;
          var warn = bots.filter(function (b) { return !b.ok; })
                         .map(function (b) { return '\u26a0 ' + (b.error || b.name); }).join('; ');
          return '<tr style="border-top:1px solid var(--border-color);">' +
            '<td style="padding:5px 6px;">' + esc(a.id || '?') +
              (warn ? '<div class="creator-option-hint" style="font-size:10px;">' + esc(warn) + '</div>' : '') +
            '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + (taskly && taskly.ok ? fmt(nT) : '\u26a0') + '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + (paygo  && paygo.ok  ? fmt(nP) : '\u26a0') + '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + fmt(rowTotal) + '</td>' +
          '</tr>';
        }).join('') || '<tr><td colspan="4" class="creator-option-hint" style="padding:8px;">' +
          'No MTProto accounts yet \u2014 use <b>+ Add MTProto</b>.</td></tr>';

        if ($('tg-bal-t-taskly')) $('tg-bal-t-taskly').textContent = fmt(tT);
        if ($('tg-bal-t-paygo'))  $('tg-bal-t-paygo').textContent  = fmt(tP);
        if ($('tg-bal-t-grand'))  $('tg-bal-t-grand').textContent  = '$' + tG.toFixed(2);
        if ($('tg-bal-wrap')) $('tg-bal-wrap').style.display = 'block';

        // Distinguish a real $0.00 from a FAILED read.
        if (!accts.length) append('! no MTProto accounts in the pool \u2014 add one first');
        else if (!okCount) append('! balance read FAILED for every account \u2014 NOT a zero balance');
        else {
          var t = (j && j.totals) || {};
          append('Taskly $' + Number(t.taskly || 0).toFixed(2) + ' \u00b7 PayGo $'
               + Number(t.paygo || 0).toFixed(2) + ' \u00b7 TOTAL $' + Number(t.grand || 0).toFixed(2)
               + '   (' + okCount + '/' + accts.length + ' accounts read)');
        }
        if (j && j.error) append('! ' + j.error);
      })
      .catch(function (e) { append('! ' + e); });
  }

  /* ---------------- pool actions ---------------- */
  function tgAction(url, body, okMsg) {
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.ok) { if (okMsg) append('* ' + okMsg); }
        else { toast((j && j.error) || 'action failed', 'error'); append('! ' + ((j && j.error) || 'action failed')); }
        refresh();
      })
      .catch(function (e) { toast('' + e, 'error'); });
  }
  function tgToggle(id, on)  { tgAction('/api/tg/accounts/toggle', { id: id, enabled: on }, id + (on ? ' enabled' : ' disabled')); }
  function tgEnableAll(on)   { tgAction('/api/tg/pool/enable_all', { enabled: on }, on ? 'all profiles enabled' : 'all profiles disabled'); }
  function tgRemove(id) {
    if (!confirm('Remove ' + id + ' and its session file? This cannot be undone.')) return;
    tgAction('/api/tg/accounts/remove', { id: id }, id + ' removed');
  }

  /* ---------------- pool ---------------- */
  function renderPool(rows) {
    state.pool = rows || [];
    var el = $('tg-pool'), sum = $('tg-pool-sum');
    var ready = state.pool.filter(function (p) { return p.logged_in; }).length;
    var busy = state.pool.filter(function (p) { return p.status === 'busy'; }).length;
    if (sum) sum.textContent = ready + ' / ' + state.pool.length + ' \u00b7 ' + ready +
      ' ready \u00b7 ' + busy + ' in use';
    if (!el) return;
    if (!state.pool.length) {
      el.innerHTML = '<div class="creator-option-hint">No profiles yet. Use <b>+ Add MTProto</b> above.</div>';
      return;
    }
    el.innerHTML = state.pool.map(function (p) {
      var label = p.label || p.id;
      // Don't repeat the id when the label already contains it (e.g. "TG tg_1").
      var showId = String(label) !== String(p.id) && String(label).indexOf(String(p.id)) === -1;
      var busy = p.status === 'busy';
      var statusPill = !p.logged_in
        ? '<span class="profile-status-badge badge-inactive">Not logged in</span>'
        : busy
          ? '<span class="profile-status-badge" style="background:rgba(245,158,11,.18);color:var(--accent-amber);border:1px solid rgba(245,158,11,.35);">In use</span>'
          : '<span class="profile-status-badge badge-active">Ready</span>';
      var metaBits = [];
      if (p.phone) metaBits.push(esc(p.phone));
      metaBits.push(esc(busy ? 'in use' : (p.status || 'idle')));
      metaBits.push((p.tasks_done || 0) + ' tasks');
      return '<div class="tg-profile-row">' +
        '<div class="tg-profile-main">' +
          '<span class="tg-profile-avatar"><i class="fa-brands fa-telegram"></i></span>' +
          '<div class="tg-profile-info">' +
            '<div class="tg-profile-title">' +
              '<strong>' + esc(label) + '</strong>' +
              (showId ? '<span class="badge-pill">' + esc(p.id) + '</span>' : '') +
              '<span class="badge-pill">' + esc((p.mode || 'web').toUpperCase()) + '</span>' +
              statusPill +
            '</div>' +
            '<div class="tg-profile-meta">' + metaBits.join(' \u00b7 ') + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="tg-profile-actions">' +
          '<span class="creator-option-hint">' + (p.enabled ? 'Enabled' : 'Disabled') + '</span>' +
          '<label class="switch" title="' + (p.enabled ? 'Disable \u2014 stops receiving tasks' : 'Enable for tasks') + '">' +
            '<input type="checkbox" data-tg-enable="' + esc(p.id) + '"' + (p.enabled ? ' checked' : '') + '>' +
            '<span class="slider"></span>' +
          '</label>' +
          '<button type="button" class="btn btn-sm btn-danger" data-tg-del="' + esc(p.id) + '"' +
            ' title="Remove this profile and its session"><i class="fa-solid fa-trash-can"></i></button>' +
        '</div>' +
      '</div>';
    }).join('');

    if (el.querySelectorAll) {
      el.querySelectorAll('[data-tg-enable]').forEach(function (b) {
        b.addEventListener('change', function () { tgToggle(b.dataset.tgEnable, b.checked); });
      });
      el.querySelectorAll('[data-tg-del]').forEach(function (b) {
        b.addEventListener('click', function () { tgRemove(b.dataset.tgDel); });
      });
    }
  }

  /* ---------------- engine state ---------------- */
  function setStatus(running, igMode) {
    state.running = running; state.igMode = igMode || null;
    var badge = $('tg-badge'), title = $('tg-title'), sub = $('tg-sub'), start = $('tg-start');
    if (badge) {
      badge.textContent = running ? 'RUNNING' : 'IDLE';
      badge.style.background = running ? 'var(--accent-green)' : 'var(--bg-input)';
      badge.style.color = running ? '#04140d' : 'var(--text-dim)';
      badge.style.borderColor = running ? 'var(--accent-green)' : 'var(--border-color)';
    }
    if (title) title.textContent = running ? 'TG ENGINE RUNNING' : 'TG ENGINE STOPPED';
    if (sub) sub.textContent = running
      ? 'Creators are running \u2014 one browser per task, coupled cycle.'
      : 'Idle. Creators will make accounts for Telegram only.';
    // Instagram-Creator behaviour: exactly ONE action button is visible —
    // Start when idle, Stop when running. Never both at once.
    var stopBtn = $('tg-stop');
    if (start)   start.style.display   = running ? 'none' : '';
    if (stopBtn) stopBtn.style.display = running ? '' : 'none';
    if (start) start.disabled = !!running;
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = null;
  }

  function kpi(id, v) { var e = $(id); if (e) e.textContent = String(v == null ? 0 : v); }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('tg-timer'); if (!el) return;
    var base = state.startedAt;
    if (!base) { el.textContent = '00:00:00'; return; }
    var t = Math.max(0, Math.floor((Date.now() - base) / 1000));
    el.textContent = pad(Math.floor(t / 3600)) + ':' + pad(Math.floor(t / 60) % 60) + ':' + pad(t % 60);
  }

  function refresh() {
    if (!root) return;
    fetch('/api/tg/status').then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) { setStatus(false, null); return; }
        setStatus(!!s.running, s.ig_mode);
        renderPool(s.pool && s.pool.accounts ? s.pool.accounts : s.pool);
        kpi('tg-kpi-total', s.tg_total != null ? s.tg_total : s.total_accounts);
        kpi('tg-kpi-parked', s.tg_pending);
        kpi('tg-kpi-submitted', s.tg_submitted);
        kpi('tg-kpi-submitting', s.running ? (s.concurrency || 0) : 0);
      })
      .catch(function () { setStatus(false, null); });
  }

  /* ---------------- log ---------------- */
  function append(line) {
    state.log.push('[' + new Date().toLocaleTimeString() + '] ' + line);
    if (state.log.length > 400) state.log = state.log.slice(-300);
    paintLog();
  }
  function paintLog() {
    var el = $('tg-log');
    if (!el) return;
    el.textContent = state.log.join('\n');
    var auto = $('tg-autoscroll');
    if (!auto || auto.checked) el.scrollTop = el.scrollHeight;
  }
  function post(url, body) {
    append('> POST ' + url);
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        append('< ' + JSON.stringify(j));
        if (j && (j.error || j.status === 'ERROR')) toast(j.error || 'Request failed', 'error', 12000);
        refresh();
      })
      .catch(function (e) { append('! ' + e); toast('Request failed: ' + e, 'error', 12000); });
  }

  /* ---------------- MTProto modal ---------------- */
  function mtOpen()  { if ($('mtprotoModal')) { $('mtprotoModal').classList.add('active'); $('mtprotoModal').style.display = 'flex'; } }
  function mtClose() { if ($('mtprotoModal')) { $('mtprotoModal').classList.remove('active'); $('mtprotoModal').style.display = 'none'; } }
  function mtMsg(t)  { if ($('mtStatus')) $('mtStatus').textContent = t || ''; }
  function mtReset() {
    if ($('mtCodeWrap')) $('mtCodeWrap').style.display = 'none';
    if ($('mtVerify')) $('mtVerify').style.display = 'none';
    mtMsg('');
  }
  function mtLoadCreds() {
    fetch('/api/tg/mtproto/credentials').then(function (r) { return r.json(); })
      .then(function (j) {
        var need = !(j && j.has_credentials);
        if ($('mtCredsWrap')) $('mtCredsWrap').style.display = 'block';
        if ($('mtCredsStatus')) {
          $('mtCredsStatus').textContent = need
            ? 'No credentials saved yet \u2014 fill these in (one pair works for all accounts).'
            : ('Using saved credentials (api_id ' + (j.api_id || '?') + ', hash ' +
               (j.api_hash_masked || '****') + ', source: ' + (j.source || 'file') +
               '). One pair serves every account.');
        }
      }).catch(function () {});
  }
  function mtWire() {
    if (!$('mtprotoModal') || $('mtprotoModal').dataset.wired) return;
    $('mtprotoModal').dataset.wired = '1';
    if ($('mtCancel')) $('mtCancel').addEventListener('click', mtClose);
    if ($('mtEditCreds')) $('mtEditCreds').addEventListener('click', function () {
      var w = $('mtCredsWrap'); if (w) w.style.display = (w.style.display === 'none') ? 'block' : 'none';
    });
    if ($('mtSaveCreds')) $('mtSaveCreds').addEventListener('click', function () {
      var apiId = ($('mtApiId').value || '').trim(), apiHash = ($('mtApiHash').value || '').trim();
      if (!apiId || !apiHash) { if ($('mtCredsStatus')) $('mtCredsStatus').textContent = 'Both api_id and api_hash are required.'; return; }
      fetch('/api/tg/mtproto/credentials', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_id: apiId, api_hash: apiHash }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if ($('mtCredsStatus')) $('mtCredsStatus').textContent = j && j.ok ? '\u2713 Saved.' : ('\u2717 ' + ((j && j.error) || 'failed'));
          if (j && j.ok) { append('* API credentials saved'); mtLoadCreds(); }
        });
    });
    if ($('mtSendCode')) $('mtSendCode').addEventListener('click', function () {
      var phone = ($('mtPhone').value || '').trim();
      if (!phone) { mtMsg('Enter the phone number with country code.'); return; }
      mtMsg('Requesting code\u2026');
      fetch('/api/tg/mtproto/send_code', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: phone, label: ($('mtLabel').value || '').trim() || undefined }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j && j.phone_code_hash) {
            window.__tgPending = j;
            if ($('mtCodeWrap')) $('mtCodeWrap').style.display = 'block';
            if ($('mtVerify')) $('mtVerify').style.display = 'inline-block';
            if ($('mtStep')) $('mtStep').textContent = 'code sent';
            mtMsg('Code sent inside Telegram. Enter it below' + (j.need_password ? ' and the 2FA password.' : '.'));
          } else { mtMsg('\u2717 ' + ((j && j.error) || 'could not send code')); }
        }).catch(function (e) { mtMsg('\u2717 ' + e); });
    });
    if ($('mtVerify')) $('mtVerify').addEventListener('click', function () {
      var code = ($('mtCode').value || '').trim();
      if (!code) { mtMsg('Enter the login code.'); return; }
      mtMsg('Verifying\u2026');
      fetch('/api/tg/mtproto/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: ($('mtPhone').value || '').trim(), code: code,
          phone_code_hash: (window.__tgPending || {}).phone_code_hash,
          password: ($('mtPassword').value || '') || undefined }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          // NOTE: the key is need_password (single 's') — matches tg_login_mtproto.py.
          if (j && j.need_password && !($('mtPassword').value || '').trim()) {
            mtMsg('This account has 2FA \u2014 enter the password and press Verify again.'); return;
          }
          if (j && j.ok) { mtMsg('\u2713 Account added to the pool.'); append('* MTProto account added'); setTimeout(function () { mtClose(); refresh(); }, 900); }
          else { mtMsg('\u2717 ' + ((j && j.error) || 'verify failed')); }
        }).catch(function (e) { mtMsg('\u2717 ' + e); });
    });
  }

  function boot() {
    root = $('tg-classic-root');
    if (!root) return;
    shell(); setWindow(false); setAddEmail(true); mtWire(); mtLoadCreds(); refresh();
    try {
      if (!window.__tgEs) {
        window.__tgEs = new EventSource('/api/meta-insta/events');
        window.__tgEs.onmessage = function (ev) {
          try {
            var d = JSON.parse(ev.data);
            if (d && d.pipeline && d.pipeline !== 'telegram') return;
            if (d && d.message) {
              append(String(d.message));
              // Actionable conditions -> toast, so they aren't missed in a long log.
              var m = String(d.message);
              if (/not a member|join the bot|start the bot|has not joined|no such bot|BOT not|chat not found/i.test(m))
                toast('A pooled account has not joined the selected bot — open that Telegram account and press /start on the bot, then retry.', 'warn', 15000);
              else if (/not logged in|session.*revoked|AUTH_KEY_UNREGISTERED/i.test(m))
                toast('A Telegram session is dead — disable that profile or log in again.', 'error', 15000);
            }
            else if (d && d.type === 'loop_stopped') {
              append('[engine] loop stopped' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : ''));
              refresh();
            }
          } catch (e) {}
        };
      }
    } catch (e) {}
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 5000);
    if (!window.__tgTick) window.__tgTick = setInterval(tickTimer, 1000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
