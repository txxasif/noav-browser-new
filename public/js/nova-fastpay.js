/* nova-fastpay.js — FastPay Bot page (Instagram 2FA payout).
 *
 * Same interface as the Taskly/PayGo TG Classic page: 4 KPI cards, a
 * LiveEngineBanner (IDLE/RUNNING + execution timer + Start/Stop), Creator
 * Settings, and a live SSE log. The bot is scoped by the page, so the only
 * Task option is FastPay's own payout task (mirrors tg_tasks.TASKS["fastpay"]).
 *
 * Unlike the creator bots there is NO Telegram-profile picker: the runner
 * leases a logged-in session itself (server /api/tg/fastpay/claim, profile=auto).
 */
(function () {
  'use strict';

  var root = null, timer = null, tick = null;
  var state = { running: false, startedAt: null, status: {} };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function toast(m, k) { if (typeof window.showToast === 'function') window.showToast(m, k); }
  function logLine(line) {
    var el = $('fastpay-log');
    if (!el) return;
    el.textContent += '[' + new Date().toLocaleTimeString() + '] ' + line + '\n';
    el.scrollTop = el.scrollHeight;
  }

  function statCard(label, id, sub) {
    return '<div class="insta-stat-card" style="background:var(--bg-card);' +
             'border:1px solid var(--border-color);border-radius:var(--radius-md);' +
             'padding:14px 16px;position:relative;overflow:hidden;">' +
      '<div style="position:absolute;left:0;top:0;bottom:0;width:3px;' +
             'background:#22c55e;opacity:.9;"></div>' +
      '<div class="insta-stat-label" style="color:var(--text-dim);">' + esc(label) + '</div>' +
      '<div class="insta-stat-value" id="' + id + '" style="color:var(--text-main);">0</div>' +
      '<div class="insta-stat-sub" style="color:var(--text-muted);">' + esc(sub) + '</div></div>';
  }

  // Same building blocks as nova-tg.js (tgField / tgSwitch / tgInfo) so the
  // Payout Settings grid is field-for-field identical to Creator Settings.
  function tgField(label, control, hint) {
    return '<div class="creator-field"><label>' + label + '</label>' + control +
      (hint ? '<div class="creator-option-hint">' + hint + '</div>' : '') + '</div>';
  }
  function tgSwitch(label, swId, checked, lblId, lblText, hint, disabled) {
    return '<div class="creator-field"><label>' + label + '</label>' +
      '<div class="tg-settings-check">' +
        '<label class="switch" title="' + esc(hint) + '">' +
          '<input type="checkbox" id="' + swId + '"' + (checked ? ' checked' : '') +
          (disabled ? ' disabled' : '') + '>' +
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
  // Fields that cannot act on a payout run (no browser, no Meta/IG, no captcha,
  // no email). Rendered for interface parity with the other two bots, but
  // disabled and labelled so the operator is never misled.
  var NA_HINT = 'Not used \u2014 FastPay is a payout bot (no browser / Meta / IG / captcha)';

  function shell() {
    root.innerHTML =
      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('FASTPAY - ACCOUNTS WITH KEY', 'fastpay-kpi-keys', 'submittable 2FA secrets') +
        statCard('FASTPAY - PAID', 'fastpay-kpi-paid', 'payout claimed') +
        statCard('FASTPAY - PENDING', 'fastpay-kpi-pending', 'not yet submitted') +
        statCard('FASTPAY - EARNED', 'fastpay-kpi-earned', 'est. $0.024 per account') +
      '</div>' +

      /* ---- LiveEngineBanner ---- */
      '<div id="fastpay-liveBanner" class="bg-[#111726]/80 rounded-xl border border-slate-800 p-4 flex flex-wrap items-center justify-between gap-4" style="margin-top:1rem;">' +
        '<div class="flex items-center space-x-4 flex-wrap gap-y-2">' +
          '<div class="flex items-center space-x-2">' +
            '<span id="fastpay-badge" class="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-400 border border-slate-700 tracking-wider">IDLE</span>' +
            '<span id="fastpay-title" class="font-bold text-white text-sm tracking-wide">FASTPAY ENGINE STOPPED</span>' +
          '</div>' +
          '<div id="fastpay-sub" class="text-xs text-slate-400 border-l border-slate-800 pl-4 hidden md:block">' +
            'Idle. Submits each account\u2019s 2FA key to @FastPay2025_bot for payout.</div>' +
        '</div>' +
        '<div class="flex items-center space-x-4">' +
          '<div class="text-right">' +
            '<div class="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Execution Time</div>' +
            '<div id="fastpay-timer" class="text-base font-mono font-bold text-white">00:00:00</div>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="fastpay-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start FastPay</button>' +
            '<button id="fastpay-stop" type="button" class="btn btn-danger" style="display:none;" title="Stop the payout run"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- settings ---- */
      '<div class="card-panel creator-panel tg-settings" style="margin-top:1.25rem;">' +
        '<div class="card-top" style="margin-bottom:1rem;">' +
          '<div>' +
            '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#22c55e;"></i> Payout Settings</h3>' +
            '<div class="panel-desc" style="margin:0;">Applies to the next FastPay start.</div>' +
          '</div>' +
          '<span class="tg-bot-badge"><img src="img/bot_logo/fastpay.png" width="20" height="20" ' +
            'style="border-radius:50%;object-fit:cover;" onerror="this.style.display=\'none\'" alt=""> FastPay Bot</span>' +
        '</div>' +
        '<div class="creator-service creator-task-service" style="margin-bottom:0.9rem;">' +
          '<div class="creator-service-title"><i class="fa-solid fa-list-check" style="color:#22c55e;"></i> SELECT TASK</div>' +
          '<div class="creator-options">' +
            '<label class="creator-option" title="Instagram 2FA — create + payout" style="cursor:pointer;">' +
              '<input type="radio" name="fastpay-task-radio" value="Instagram 2FA" checked> ' +
              '<i class="fa-brands fa-instagram" style="color:#22c55e;"></i> Instagram 2FA ' +
              '<span class="creator-option-hint">(create + payout)</span>' +
            '</label>' +
          '</div>' +
          '<div class="creator-service-note">FastPay task — creates account with bot-issued credentials and submits 2FA key for payout.</div>' +
          '<input type="hidden" id="fastpay-task" value="Instagram 2FA">' +
        '</div>' +
        '<div class="tg-settings-grid">' +
          tgField('Parallel creators',
            '<input id="fastpay-conc" class="form-control" type="number" min="1" max="10" value="1">',
            '1&ndash;10 simultaneous payout runners') +
          tgField('Target goal',
            '<input id="fastpay-target" class="form-control" type="number" min="0" value="0">',
            '0 = every pending account') +
          tgSwitch('Visible window', 'fastpay-vis-sw', false, 'fastpay-vis-lbl', 'N/A',
            NA_HINT, true) +
          tgSwitch('Extra email after 2FA + password', 'fastpay-adde-sw', false, 'fastpay-adde-lbl', 'N/A',
            NA_HINT, true) +
          tgInfo('Mail inbox', 'mail.td', 'Not used \u2014 payout never creates an account') +
          tgInfo('Captcha solver', 'N/A', 'Not used \u2014 no browser in a payout run') +
        '</div>' +
      '</div>' +

      /* ---- log ---- */
      '<div class="card-panel" style="margin-top:1.25rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Payout Log (SSE)</h3>' +
          '<button id="fastpay-refresh" type="button" class="btn btn-secondary btn-sm"><i class="fa-solid fa-rotate"></i> Refresh</button>' +
        '</div>' +
        '<div id="fastpay-log" class="log-container" style="height:260px;overflow-y:auto;' +
          'background:#060910;border:1px solid var(--border-color);border-radius:8px;padding:0.75rem;' +
          'font-family:var(--font-mono);font-size:0.78rem;white-space:pre-wrap;"></div>' +
      '</div>';

    wire();
  }

  function setRunning(running) {
    state.running = !!running;
    var badge = $('fastpay-badge'), title = $('fastpay-title'), sub = $('fastpay-sub');
    var start = $('fastpay-start'), stop = $('fastpay-stop');
    if (badge) {
      badge.textContent = running ? 'RUNNING' : 'IDLE';
      badge.style.background = running ? 'var(--accent-green)' : 'var(--bg-input)';
      badge.style.color = running ? '#04140d' : 'var(--text-dim)';
      badge.style.borderColor = running ? 'var(--accent-green)' : 'var(--border-color)';
    }
    if (title) title.textContent = running ? 'FASTPAY ENGINE RUNNING' : 'FASTPAY ENGINE STOPPED';
    if (sub) sub.textContent = running
      ? 'Submitting 2FA keys \u2014 the bot returns each TOTP and pays on Confirm.'
      : 'Idle. Submits each account\u2019s 2FA key to @FastPay2025_bot for payout.';
    if (start) { start.style.display = running ? 'none' : ''; start.disabled = !!running; }
    if (stop) stop.style.display = running ? '' : 'none';
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = null;
  }

  function kpi(id, v) { var e = $(id); if (e) e.textContent = String(v == null ? 0 : v); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('fastpay-timer'); if (!el) return;
    var base = state.startedAt;
    if (!base) { el.textContent = '00:00:00'; return; }
    var t = Math.max(0, Math.floor((Date.now() - base) / 1000));
    el.textContent = pad(Math.floor(t / 3600)) + ':' + pad(Math.floor(t / 60) % 60) + ':' + pad(t % 60);
  }

  function refresh() {
    if (!root) return;
    fetch('/api/tg/fastpay/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) return;
        state.status = s;
        setRunning(!!s.running);
        kpi('fastpay-kpi-keys', s.keys);
        kpi('fastpay-kpi-paid', s.paid);
        kpi('fastpay-kpi-pending', s.pending);
        var earned = (s.paid || 0) * (s.rate || 0.024);
        kpi('fastpay-kpi-earned', '$' + earned.toFixed(2));
      })
      .catch(function () {});
  }

  function start() {
    var parallel = Math.max(1, Math.min(10, parseInt(($('fastpay-conc') || {}).value || 1, 10) || 1));
    var target = Math.max(0, parseInt(($('fastpay-target') || {}).value || 0, 10) || 0);
    logLine('> payout start (parallel=' + parallel +
            ', target=' + (target > 0 ? target : 'all pending') + ')');
    fetch('/api/tg/fastpay/claim', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parallel: parallel, target: target }),
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        logLine('< ' + JSON.stringify(j));
        if (j && j.error) { logLine('! ' + j.error); toast(j.error, 'error', 12000); }
      })
      .catch(function (e) { logLine('! ' + e); })
      .finally(function () { refresh(); });
  }

  function stop() {
    logLine('> payout stop requested');
    fetch('/api/tg/fastpay/stop', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (j) { logLine('< ' + JSON.stringify(j)); })
      .catch(function (e) { logLine('! ' + e); })
      .finally(function () { refresh(); });
  }

  function wire() {
    if ($('fastpay-start')) $('fastpay-start').addEventListener('click', start);
    if ($('fastpay-stop')) $('fastpay-stop').addEventListener('click', stop);
    if ($('fastpay-refresh')) $('fastpay-refresh').addEventListener('click', refresh);
  }

  function boot() {
    root = $('fastpay-root');
    if (!root) return;
    shell();
    refresh();
    try {
      if (!window.__fastpayEs) {
        window.__fastpayEs = new EventSource('/api/meta-insta/events');
        window.__fastpayEs.onmessage = function (ev) {
          try {
            var d = JSON.parse(ev.data);
            if (d && d.pipeline && d.pipeline !== 'telegram') return;
            if (d && d.message && /\[fastpay\]|FastPay/i.test(String(d.message))) logLine(String(d.message));
            else if (d && d.type === 'fastpay_done') {
              logLine('[engine] FastPay run finished' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : ''));
              refresh();
            }
          } catch (e) {}
        };
      }
    } catch (e) {}
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 8000);
    if (tick) clearInterval(tick);
    tick = setInterval(tickTimer, 1000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
