/* nova-manager.js — Telegram Manager page.
 *
 * Connect + lease + monitor every Telegram profile across the bots. Talks to
 * tg.manager via /api/tg/manager/*. A profile leased by one bot is shown as
 * "busy in <bot>" and locked to it until released (mutual exclusion).
 */
(function () {
  'use strict';

  var root = null, timer = null;
  var state = { bots: [], accounts: [], counts: {}, enabled: [] };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function toast(m, k) { if (typeof window.showToast === 'function') window.showToast(m, k); }

  function botLogo(id) { return id === 'paygo' ? 'paygo' : 'taskly'; }

  function botCard(b) {
    var busyTxt = b.busy_other ? (b.busy_other + ' busy elsewhere') : '';
    var botColor = b.id === 'paygo' ? '#f59e0b' : '#229ED9';
    var flowLabel = (b.flows || []).join('/') || '2fa';
    var taskChips = (b.tasks || []).map(function (t) {
      return '<span class="tgm-task-chip">' + esc(t) + '</span>';
    }).join(' ');
    return '<div class="tgm-bot" style="--bot-accent:' + botColor + ';">' +
      '<div class="tgm-bot-top">' +
        '<div class="tgm-bot-identity">' +
          '<img src="img/bot_logo/' + botLogo(b.id) + '.png" class="tgm-bot-avatar" onerror="this.style.display=\'none\'" alt="">' +
          '<div>' +
            '<h4 class="tgm-bot-name">' + esc(b.name) + '</h4>' +
            '<div class="tgm-bot-handle">@' + esc(b.username) + '</div>' +
          '</div>' +
        '</div>' +
        '<span class="tgm-flow-badge" style="border-color:' + botColor + '40;color:' + botColor + ';background:' + botColor + '18;">' +
          esc(flowLabel.toUpperCase()) +
        '</span>' +
      '</div>' +
      '<div class="tgm-metrics">' +
        '<div class="tgm-metric"><span class="tgm-m-num">' + (b.free || 0) + '</span><span class="tgm-m-lbl">Free</span></div>' +
        '<div class="tgm-metric"><span class="tgm-m-num">' + (b.connected || 0) + '</span><span class="tgm-m-lbl">Connected</span></div>' +
        '<div class="tgm-metric"><span class="tgm-m-num">' + (b.tasks ? b.tasks.length : 0) + '</span><span class="tgm-m-lbl">Tasks</span></div>' +
      '</div>' +
      (taskChips ? '<div class="tgm-tasks-wrap">' + taskChips + (busyTxt ? '<span class="tgm-busy-tag">\u00b7 ' + esc(busyTxt) + '</span>' : '') + '</div>' : '') +
    '</div>';
  }

  function acctRow(a) {
    var avatarCls = !a.logged_in ? 'dead' : (a.status === 'busy' ? 'busy' : (!a.enabled ? 'off' : ''));
    var statusPill = '';
    if (a.status === 'busy') {
      statusPill = '<span class="profile-status-badge badge-warn">Busy' +
        (a.busy_bot ? ' \u00b7 ' + esc(a.busy_bot) : '') + '</span>';
    } else if (!a.logged_in) {
      statusPill = '<span class="profile-status-badge badge-rose">Offline</span>';
    } else if (!a.enabled) {
      statusPill = '<span class="profile-status-badge badge-inactive">Disabled</span>';
    }
    // "ready button remove it": no status pill shown when account is ready

    var meta = [];
    if (a.phone) meta.push('<span class="tgm-phone"><i class="fa-solid fa-phone" style="font-size:0.62rem;opacity:0.7;margin-right:3px;"></i>' + esc(a.phone) + '</span>');
    meta.push(esc((a.mode || 'web').toUpperCase()));
    meta.push((a.tasks_done || 0) + ' tasks');
    return '<div class="tgm-acct' + (a.status === 'busy' ? ' tgm-busy' : '') + '">' +
      '<div class="tgm-acct-top">' +
        '<div class="tgm-avatar ' + avatarCls + '" title="' + esc(a.mode || 'mtproto') + '"><i class="fa-brands fa-telegram"></i></div>' +
        '<div class="tgm-acct-info">' +
          '<div class="tgm-acct-title">' +
            '<strong>' + esc(a.label || a.id) + '</strong>' +
            '<span class="badge-pill">' + esc(a.id) + '</span>' +
            statusPill +
          '</div>' +
          '<div class="tgm-acct-meta">' + meta.join(' <span style="opacity:0.35;">\u00b7</span> ') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="tgm-acct-footer">' +
        '<div class="tgm-acct-status-wrap">' +
          '<span class="tgm-status-lbl">' + (a.enabled ? 'Enabled' : 'Disabled') + '</span>' +
        '</div>' +
        '<div class="tgm-acct-actions">' +
          '<button type="button" data-tgm-wd="' + esc(a.id) + '" title="Withdraw from ' + esc(a.id) + '"' +
            ' style="background:rgba(74,222,128,.12);color:#4ade80;border:1px solid rgba(74,222,128,.4);border-radius:7px;padding:4px 10px;font-size:0.72rem;font-weight:600;display:inline-flex;align-items:center;gap:5px;cursor:pointer;">' +
            '<i class="fa-solid fa-money-bill-transfer"></i> Withdraw</button>' +
          '<label class="switch" title="' + (a.enabled ? 'Disable (stops receiving tasks)' : 'Enable for tasks') + '">' +
            '<input type="checkbox" data-tgm-enable="' + esc(a.id) + '"' + (a.enabled ? ' checked' : '') +
            (a.status === 'busy' ? ' disabled' : '') + '><span class="slider"></span></label>' +
          '<button type="button" class="btn-icon-danger" data-tgm-del="' + esc(a.id) + '"' +
            ' title="Remove this profile and its session"><i class="fa-solid fa-trash-can"></i></button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }

  // ---- Live balances (Taskly + PayGo) --------------------------------------
  // Balances stream in per account: each row fills the moment its account is read,
  // so the table is useful right away instead of after the whole pool.
  var balState = { rows: {}, total: 0, done: 0, running: false, ctrl: null };

  function money(x) { return x && x.ok ? '$' + Number(x.amount || 0).toFixed(2) : null; }
  function pendTxt(x) { return x && x.ok && x.pending ? '<span class="tgm-pend">+' + Number(x.pending).toFixed(2) + ' pend</span>' : ''; }
  function cellFor(x, err) {
    if (x && x.ok) return '<span class="tgm-amt">' + money(x) + '</span>' + pendTxt(x);
    if (err) return '<span class="tgm-na" title="' + esc(err) + '">—</span>';
    return '<span class="tgm-na">—</span>';
  }
  function balRow(a) {
    var bots = a.bots || [];
    var t = bots.filter(function (x) { return x.target === 'taskly'; })[0];
    var p = bots.filter(function (x) { return x.target === 'paygo'; })[0];
    var total = (t && t.ok ? Number(t.amount || 0) : 0) + (p && p.ok ? Number(p.amount || 0) : 0);
    var st = a.busy ? '<span class="profile-status-badge badge-warn">Busy</span>'
      : (a.ok === false ? '<span class="profile-status-badge badge-rose">Error</span>'
      : (a.ok ? '<span class="profile-status-badge badge-ok">Read</span>'
      : '<span class="profile-status-badge badge-inactive">Waiting</span>'));
    return '<tr data-bal-row="' + esc(a.id) + '">' +
      '<td><div class="tgm-acct"><strong>' + esc(a.name || a.id) + '</strong><span class="tgm-id">' + esc(a.id) + '</span></div></td>' +
      '<td>' + st + '</td>' +
      '<td class="r">' + cellFor(t, a.error) + '</td>' +
      '<td class="r">' + cellFor(p, a.error) + '</td>' +
      '<td class="r tgm-tot">' + (a.ok || a.bots ? '$' + total.toFixed(2) : '—') + '</td></tr>';
  }

  function renderBalTable() {
    var wrap = $('tgm-bal-wrap');
    if (!wrap) return;
    var list = Object.keys(balState.rows).map(function (k) { return balState.rows[k]; });
    list.sort(function (x, y) { return String(x.name || x.id).localeCompare(String(y.name || y.id)); });
    var tTaskly = 0, tPaygo = 0;
    list.forEach(function (a) {
      (a.bots || []).forEach(function (x) {
        if (!x.ok) return;
        if (x.target === 'taskly') tTaskly += Number(x.amount || 0);
        if (x.target === 'paygo') tPaygo += Number(x.amount || 0);
      });
    });
    var pct = balState.total ? Math.round(balState.done / balState.total * 100) : 0;
    var running = balState.running;
    wrap.style.display = 'block';
    wrap.innerHTML =
      '<div class="tgm-balhead">' +
        '<div class="tgm-stats">' +
          '<div class="tgm-stat"><span>Taskly total</span><strong>$' + tTaskly.toFixed(2) + '</strong></div>' +
          '<div class="tgm-stat"><span>PayGo total</span><strong>$' + tPaygo.toFixed(2) + '</strong></div>' +
          '<div class="tgm-stat grand"><span>Grand total</span><strong>$' + (tTaskly + tPaygo).toFixed(2) + '</strong></div>' +
          '<div class="tgm-stat"><span>Accounts read</span><strong>' + balState.done + ' / ' + balState.total + '</strong></div>' +
        '</div>' +
        '<div class="tgm-progress"><div style="width:' + pct + '%"></div></div>' +
      '</div>' +
      '<div class="tgm-tablewrap"><table class="tgm-bal"><thead><tr>' +
        '<th>Account</th><th>Status</th><th class="r">Taskly</th><th class="r">PayGo</th><th class="r">Total</th>' +
      '</tr></thead><tbody>' +
        (list.map(balRow).join('') || '<tr><td colspan="6" class="tgm-empty">' + (running ? 'Reading accounts…' : 'Pick accounts and press Check balances.') + '</td></tr>') +
      '</tbody></table></div>';
  }

  // Read every profile's balance, live.
  function checkBalances() {
    var btn = $('tgm-bal');
    var ids = [];
    if (balState.ctrl) { try { balState.ctrl.abort(); } catch (e) {} }
    balState.ctrl = new AbortController();
    balState.rows = {};
    balState.done = 0;
    balState.total = (balState.pool && balState.pool.length) || 0;
    balState.running = true;
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Reading…'; }
    renderBalTable();
    fetch('/api/tg/manager/balance_stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}), signal: balState.ctrl.signal,
    }).then(function (r) {
      if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
      var reader = r.body.getReader(), dec = new TextDecoder('utf-8'), buf = '';
      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) return;
          buf += dec.decode(chunk.value, { stream: true });
          var lines = buf.split('\n'); buf = lines.pop();
          lines.forEach(function (ln) {
            if (!ln.trim()) return;
            var m; try { m = JSON.parse(ln); } catch (e) { return; }
            if (m.type === 'total') balState.total = m.count;
            else if (m.type === 'account' && m.account) {
              balState.rows[m.account.id] = m.account;
              balState.done = m.done;
              renderBalTable();
            }
          });
          return pump();
        });
      }
      return pump();
    }).catch(function (e) {
      if (e && e.name === 'AbortError') return;
      toast('Balance read failed: ' + e, 'error');
    }).finally(function () {
      balState.running = false;
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-wallet"></i> Check balances'; }
      renderBalTable();
    });
  }

  function acctRow(a) {
    var avatarCls = !a.logged_in ? 'dead' : (a.status === 'busy' ? 'busy' : (!a.enabled ? 'off' : ''));
    var statusPill = '';
    if (a.status === 'busy') {
      statusPill = '<span class="profile-status-badge badge-warn">Busy' +
        (a.busy_bot ? ' \u00b7 ' + esc(a.busy_bot) : '') + '</span>';
    } else if (!a.logged_in) {
      statusPill = '<span class="profile-status-badge badge-rose">Offline</span>';
    } else if (!a.enabled) {
      statusPill = '<span class="profile-status-badge badge-inactive">Disabled</span>';
    }
    // "ready button remove it": no status pill shown when account is ready

    var meta = [];
    if (a.phone) meta.push('<span class="tgm-phone"><i class="fa-solid fa-phone" style="font-size:0.62rem;opacity:0.7;margin-right:3px;"></i>' + esc(a.phone) + '</span>');
    meta.push(esc((a.mode || 'web').toUpperCase()));
    meta.push((a.tasks_done || 0) + ' tasks');
    return '<div class="tgm-acct' + (a.status === 'busy' ? ' tgm-busy' : '') + '">' +
      '<div class="tgm-acct-top">' +
        '<div class="tgm-avatar ' + avatarCls + '" title="' + esc(a.mode || 'mtproto') + '"><i class="fa-brands fa-telegram"></i></div>' +
        '<div class="tgm-acct-info">' +
          '<div class="tgm-acct-title">' +
            '<strong>' + esc(a.label || a.id) + '</strong>' +
            '<span class="badge-pill">' + esc(a.id) + '</span>' +
            statusPill +
          '</div>' +
          '<div class="tgm-acct-meta">' + meta.join(' <span style="opacity:0.35;">\u00b7</span> ') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="tgm-acct-footer">' +
        '<div class="tgm-acct-status-wrap">' +
          '<span class="tgm-status-lbl">' + (a.enabled ? 'Enabled' : 'Disabled') + '</span>' +
        '</div>' +
        '<div class="tgm-acct-actions">' +
          '<button type="button" data-tgm-wd="' + esc(a.id) + '" title="Withdraw from ' + esc(a.id) + '"' +
            ' style="background:rgba(74,222,128,.12);color:#4ade80;border:1px solid rgba(74,222,128,.4);border-radius:7px;padding:4px 10px;font-size:0.72rem;font-weight:600;display:inline-flex;align-items:center;gap:5px;cursor:pointer;">' +
            '<i class="fa-solid fa-money-bill-transfer"></i> Withdraw</button>' +
          '<label class="switch" title="' + (a.enabled ? 'Disable (stops receiving tasks)' : 'Enable for tasks') + '">' +
            '<input type="checkbox" data-tgm-enable="' + esc(a.id) + '"' + (a.enabled ? ' checked' : '') +
            (a.status === 'busy' ? ' disabled' : '') + '><span class="slider"></span></label>' +
          '<button type="button" class="btn-icon-danger" data-tgm-del="' + esc(a.id) + '"' +
            ' title="Remove this profile and its session"><i class="fa-solid fa-trash-can"></i></button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }


  function render() {
    var bots = $('tgm-bots');
    if (bots) bots.innerHTML = (state.bots || []).map(botCard).join('') ||
      '<div class="creator-option-hint">No bots in this build.</div>';
    var acc = $('tgm-accounts');
    if (acc) acc.innerHTML = (state.accounts || []).map(acctRow).join('') || '<div class="creator-option-hint">No Telegram profiles yet \u2014 use Connect account.</div>';
    var c = $('tgm-counts');
    if (c && state.counts) c.textContent = state.counts.total + ' profiles \u00b7 ' + state.counts.connected +
      ' connected \u00b7 ' + state.counts.free + ' free \u00b7 ' + state.counts.busy + ' busy';
    var idle = $('tgm-start-idle');
    if (idle && state.counts) idle.innerHTML = '<i class="fa-solid fa-circle" style="color:#4ade80;font-size:.5rem;vertical-align:middle;"></i> ' +
      state.counts.free + ' idle profile(s) will receive it';
    wireRows();
  }

  function wireRows() {
    document.querySelectorAll('[data-tgm-enable]').forEach(function (b) {
      b.addEventListener('change', function () { toggle(b.dataset.tgmEnable, b.checked); });
    });
    document.querySelectorAll('[data-tgm-del]').forEach(function (b) {
      b.addEventListener('click', function () {
        var id = b.dataset.tgmDel;
        wdConfirm({
          title: 'Remove profile',
          confirmText: 'Remove',
          message: 'Remove <strong>' + esc(id) + '</strong> and its Telegram session? This cannot be undone.',
        }).then(function (okc) {
          if (okc) action('/api/tg/accounts/remove', { id: id }, id + ' removed');
        });
      });
    });
    document.querySelectorAll('[data-tgm-wd]').forEach(function (b) {
      b.addEventListener('click', function () { openWithdrawModal(b.dataset.tgmWd); });
    });
  }

  function refresh() {
    fetch('/api/tg/manager/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s || !s.ok) return;
        state.bots = s.bots || [];
        state.accounts = s.accounts || [];
        state.counts = s.counts || {};
        state.enabled = s.enabled_bots || [];
        applyBuildGating();
        render();
      })
      .catch(function () {});
  }

  // Ship only the bots this BUILD selected: hide disabled sidebar sub-items
  // and their bot option in the TG panel.
  function applyBuildGating() {
    var enabled = state.enabled || [];
    document.querySelectorAll('.nav-sub[data-bot]').forEach(function (el) {
      var b = el.getAttribute('data-bot');
      el.style.display = enabled.length && enabled.indexOf(b) === -1 ? 'none' : '';
    });
    var sel = $('tg-bot');
    if (sel) {
      Array.prototype.slice.call(sel.options).forEach(function (o) {
        o.hidden = enabled.length > 0 && enabled.indexOf(o.value) === -1;
      });
    }
  }

  function toggle(id, on) {
    action('/api/tg/accounts/toggle', { id: id, enabled: !!on }, id + (on ? ' enabled' : ' disabled'));
  }
  function action(url, body, okMsg) {
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && (j.ok || j.status === 'SUCCESS')) { if (okMsg) toast(okMsg, 'success'); }
        else toast((j && j.error) || 'action failed', 'error');
        refresh();
      })
      .catch(function (e) { toast('' + e, 'error'); });
  }

  function sendStart() {
    var bot = startBot;
    var label = CHIP_LABELS[bot] || bot;
    wdConfirm({
      title: 'Send /start',
      message: 'Send <b>/start</b> to <b>' + esc(label) + '</b> from every idle, connected Telegram account? Busy accounts are skipped.',
      confirmText: 'Send'
    }).then(function (okc) {
      if (!okc) return;
      var btn = $('tgm-start');
      if (btn) btn.disabled = true;
      if ($('tgm-start-result')) { $('tgm-start-result').style.display = 'flex'; $('tgm-start-result').innerHTML = '<span class="creator-option-hint"><i class="fa-solid fa-spinner fa-spin"></i> Sending…</span>'; }
      toast('Sending /start…', 'info');
      fetch('/api/tg/manager/send_start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot: bot }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j || !j.ok) { toast((j && j.error) || 'send /start failed', 'error'); return; }
          var msg = '/start sent: ' + j.sent + ' ok · ' + j.failed + ' failed · ' + j.skipped + ' skipped';
          toast(msg, j.failed ? 'error' : 'success');
          showStartResult(j);
          refresh();
        })
        .catch(function (e) { toast('' + e, 'error'); })
        .finally(function () { if (btn) btn.disabled = false; });
    });
  }



  // ---- Withdraw (USDT BEP-20) -------------------------------------------
  function loadWithdraw() {
    fetch('/api/tg/wallet', { cache: 'no-store' }).then(function (r) { return r.json(); })
      .then(function (j) { if ($('tgm-wd-wallet')) $('tgm-wd-wallet').value = (j && j.wallet) || ''; })
      .catch(function () {});
    fetch('/api/tg/freeze', { cache: 'no-store' }).then(function (r) { return r.json(); })
      .then(function (j) {
        var on = !!(j && j.frozen);
        if ($('tgm-wd-freeze-sw')) $('tgm-wd-freeze-sw').checked = on;
        var pill = $('tgm-wd-freeze-pill');
        if (pill) {
          pill.textContent = on ? 'FROZEN' : 'Live';
          pill.style.color = on ? '#f87171' : '#4ade80';
          pill.style.borderColor = on ? 'rgba(248,113,113,.4)' : 'rgba(74,222,128,.4)';
        }
      })
      .catch(function () {});
  }

  function saveWallet(inputId) {
    var el = $(inputId || 'tgm-wd-wallet');
    var w = ((el || {}).value || '').trim();
    fetch('/api/tg/wallet', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ wallet: w }) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.status === 'SUCCESS') {
          toast('Wallet saved', 'success');
          if ($('tgm-wd-wallet')) $('tgm-wd-wallet').value = w;
        } else toast((j && j.error) || 'save failed', 'error');
      })
      .catch(function (e) { toast('' + e, 'error'); });
  }

  function wdClose() {
    var m = $('tgm-wd-modal');
    if (!m) return;
    if (typeof window.closeModal === 'function') window.closeModal(m);
    else { m.classList.remove('active'); m.style.display = 'none'; }
  }

  var _confirmResolve = null;
  function wdConfirm(opts) {
    return new Promise(function (resolve) {
      opts = opts || {};
      var m = $('tgm-confirm-modal');
      if (!m) { resolve(window.confirm(String(opts.message || '').replace(/<[^>]+>/g, ''))); return; }
      if (typeof opts.message === 'string') { var msgEl = $('tgm-confirm-msg'); if (msgEl) msgEl.innerHTML = opts.message; }
      var te = $('tgm-confirm-title');
      if (te) te.innerHTML = '<i class="fa-solid fa-circle-question" style="color:#f59e0b;"></i> ' + (opts.title || 'Confirm');
      var okb = $('tgm-confirm-ok'); if (okb) okb.textContent = opts.confirmText || 'OK';
      var cb = $('tgm-confirm-cancel'); if (cb) cb.textContent = opts.cancelText || 'Cancel';
      _confirmResolve = resolve;
      if (typeof window.openModal === 'function') window.openModal(m);
      else { m.classList.add('active'); m.style.display = 'flex'; }
      if (!m.dataset.cWired) {
        m.dataset.cWired = '1';
        m.querySelectorAll('[data-close], .close-modal').forEach(function (b) {
          b.addEventListener('click', function () { _confirmDone(false); });
        });
        m.addEventListener('click', function (e) { if (e.target === m) _confirmDone(false); });
        if ($('tgm-confirm-cancel')) $('tgm-confirm-cancel').addEventListener('click', function () { _confirmDone(false); });
        if ($('tgm-confirm-ok')) $('tgm-confirm-ok').addEventListener('click', function () { _confirmDone(true); });
        document.addEventListener('keydown', function (e) {
          if (e.key === 'Escape' && m.classList.contains('active')) _confirmDone(false);
        });
      }
    });
  }
  function _confirmDone(val) {
    var m = $('tgm-confirm-modal');
    if (m) {
      if (typeof window.closeModal === 'function') window.closeModal(m);
      else { m.classList.remove('active'); m.style.display = 'none'; }
    }
    var r = _confirmResolve; _confirmResolve = null;
    if (r) r(!!val);
  }

  function openWithdrawModal(id) {
    var m = $('tgm-wd-modal');
    if (!m) return;
    var t = $('tgm-wd-acct'); if (t) t.textContent = id;
    var res = $('tgm-wd-result'); if (res) res.textContent = '';
    try {
      if (typeof window.openModal === 'function') window.openModal(m);
      else { m.classList.add('active'); m.style.display = 'flex'; }
    } catch (e) { m.classList.add('active'); m.style.display = 'flex'; }
    // initModalDismiss (nova-core) runs at DOMContentLoaded BEFORE this modal is
    // built, so its [data-close]/backdrop/Escape handlers never attach to it —
    // bind them here, exactly once.
    if (!m.dataset.wdWired) {
      m.dataset.wdWired = '1';
      m.querySelectorAll('[data-close], .close-modal').forEach(function (b) {
        b.addEventListener('click', function () { wdClose(); });
      });
      m.addEventListener('click', function (e) { if (e.target === m) wdClose(); });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && m.classList.contains('active')) wdClose();
      });
    }
    fetch('/api/tg/wallet', { cache: 'no-store' }).then(function (r) { return r.json(); })
      .then(function (j) { if ($('tgm-wd-wallet')) $('tgm-wd-wallet').value = (j && j.wallet) || ''; })
      .catch(function () {});
    var rows = $('tgm-wd-rows');
    if (rows) rows.innerHTML = '<div class="creator-option-hint">Reading balances\u2026 (opens each TG session)</div>';
    fetch('/api/tg/manager/balance', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      .then(function (r) { return r.json(); })
      .then(function (b) {
        var acc = ((b && b.accounts) || []).filter(function (a) { return a.id === id; })[0] || {};
        var byBot = {};
        (acc.bots || []).forEach(function (x) { byBot[x.target] = x; });
        renderWithdrawRowsTP(id, byBot);
      })
      .catch(function (e) {
        // Balance read can fail (e.g. a profile is leased by the engine). Still
        // render the withdraw rows (balance shows "—") so the user can proceed.
        try { renderWithdrawRowsTP(id, {}); } catch (e2) {}
        var r = $('tgm-wd-rows');
        if (r && !r.querySelector('[data-wd-go]')) r.innerHTML = '<div class="creator-option-hint">balance error: ' + esc('' + e) + '</div>';
      });
  }


  // Withdraw rows for Taskly + PayGo only (FastPay is no longer offered).
  function renderWithdrawRowsTP(id, byBot) {
    var rows = $('tgm-wd-rows');
    if (!rows) return;
    var specs = { paygo: { cur: '$', min: 0.20, def: '0.20', step: '0.01', label: 'PayGo' },
                  taskly: { cur: '$', min: 0.20, def: '0.20', step: '0.01', label: 'Taksly' } };
    rows.innerHTML = ['taskly', 'paygo'].map(function (bot) {
      var sp = specs[bot];
      var x = byBot[bot];
      var bal = (x && x.ok) ? Number(x.amount || 0) : null;
      var balTxt = (bal == null) ? '\u2014' : (sp.cur + bal.toFixed(2));
      var enough = (bal == null) || (bal >= sp.min);
      var pad = enough ? '' : 'opacity:.45;pointer-events:none;';
      return '<div class="tgm-wd-row" style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;' + pad + '">' +
        '<strong style="min-width:70px;">' + sp.label + '</strong>' +
        '<span class="tgm-amt">' + balTxt + '</span>' +
        '<input type="number" class="form-control" data-wd-amt="' + bot + '" min="' + sp.min + '" step="' + sp.step + '" value="' + sp.def + '" style="width:110px;">' +
        '<button type="button" class="btn btn-sm btn-primary" data-wd-go="' + bot + '" data-wd-id="' + esc(id) + '">Withdraw</button>' +
        '</div>';
    }).join('');
    rows.querySelectorAll('[data-wd-go]').forEach(function (btn) {
      btn.addEventListener('click', function () { doWithdraw(id, btn.getAttribute('data-wd-go')); });
    });
  }

  function doWithdraw(id, bot) {
    var w = (($('tgm-wd-wallet') || {}).value || '').trim();
    var inp = document.querySelector('[data-wd-amt="' + bot + '"]');
    var amt = parseFloat((inp && inp.value) || '0') || 0;
    var res = $('tgm-wd-result');
    if (!/^0x[a-fA-F0-9]{40}$/.test(w)) {
      toast('Enter a valid BEP-20 address (0x + 40 hex).', 'error');
      var wi = $('tgm-wd-wallet'); if (wi) wi.focus();
      return;
    }
    var min = 0.20;
    var cur = '$';
    if (amt < min) { toast('Amount must be \u2265 ' + cur + min, 'error'); return; }
    var botName = bot.charAt(0).toUpperCase() + bot.slice(1);
    wdConfirm({
      title: 'Confirm withdrawal',
      confirmText: 'Withdraw',
      message:
        'Withdraw <strong>' + cur + amt + '</strong> from <strong>' + esc(id) + '</strong> (' + botName + ')' +
        '<div style="margin-top:8px;padding:8px;background:var(--bg-card);border:1px solid var(--border-color);border-radius:8px;font-family:var(--font-mono);font-size:0.76rem;word-break:break-all;">' + esc(w) + '</div>' +
        '<div style="margin-top:10px;color:#f59e0b;"><i class="fa-solid fa-lock"></i> Telegram will be <strong>FROZEN</strong> for exclusive access during the withdrawal.</div>'
    }).then(function (okc) {
      if (!okc) return;
      var btn = document.querySelector('[data-wd-go="' + bot + '"]');
      if (btn) btn.disabled = true;
      if (res) res.textContent = 'Withdrawing ' + cur + amt + ' from ' + id + ' (' + bot + ')\u2026 TG frozen (this can take ~20-40s).';
      fetch('/api/tg/withdraw', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot: bot, amount: amt, wallet: w, tg_id: id }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j && j.status === 'SUCCESS') { toast('Withdrawal successful', 'success'); if (res) res.textContent = '\u2705 ' + (j.message || 'Withdrawal successful'); }
          else { var msg = (j && (j.error || j.message)) || 'withdraw failed'; toast(msg, 'error'); if (res) res.textContent = '\u26a0\ufe0f ' + msg; }
        })
        .catch(function (e) { toast('' + e, 'error'); if (res) res.textContent = '\u26a0\ufe0f ' + e; })
        .finally(function () { if (btn) btn.disabled = false; loadWithdraw(); });
    });
  }

  function wire() {
    if ($('tgm-refresh')) $('tgm-refresh').addEventListener('click', refresh);
    if ($('tgm-bal')) $('tgm-bal').addEventListener('click', checkBalances);
    if ($('tgm-start')) $('tgm-start').addEventListener('click', sendStart);
    document.querySelectorAll('#tgm-start-chips .tgm-chip').forEach(function (c) {
      c.addEventListener('click', function () { pickStartBot(c.dataset.bot); });
    });
    if ($('tgm-add')) $('tgm-add').addEventListener('click', function () {
      if (typeof window.openMtprotoModal === 'function') { window.openMtprotoModal(); return; }
      toast('Add-account modal unavailable.', 'error');
    });
    if ($('tgm-wd-freeze-sw')) $('tgm-wd-freeze-sw').addEventListener('change', function () {
      var on = this.checked;
      fetch('/api/tg/freeze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ frozen: on }) })
        .then(function (r) { return r.json(); })
        .then(function () { toast(on ? 'TG frozen \u2014 exclusive access' : 'TG unfrozen', 'success'); loadWithdraw(); })
        .catch(function (e) { toast('' + e, 'error'); });
    });
    if ($('tgm-wd-save')) $('tgm-wd-save').addEventListener('click', function () { saveWallet('tgm-wd-wallet'); });
  }

  var startBot = 'all';
  function chip(bot, icon, label, color, on) {
    return '<button type="button" class="tgm-chip" data-bot="' + bot + '" style="display:flex;align-items:center;gap:.5rem;padding:.55rem .95rem;' +
      'border-radius:10px;border:1px solid ' + (on ? color : 'var(--border-color)') + ';background:' + (on ? 'rgba(255,255,255,.06)' : 'var(--bg-card)') + ';' +
      'color:var(--text-main);font-weight:600;cursor:pointer;transition:all .15s;">' +
      '<i class="' + icon + '" style="color:' + color + ';"></i>' + label + '</button>';
  }
  var CHIP_COLORS = { all: '#a5b4fc', taskly: '#229ED9', paygo: '#4ade80' };
  var CHIP_LABELS = { all: 'All bots', taskly: 'Taksly Bot', paygo: 'PayGo Bot' };
  function pickStartBot(bot) {
    startBot = bot;
    document.querySelectorAll('#tgm-start-chips .tgm-chip').forEach(function (c) {
      var on = c.dataset.bot === bot;
      c.style.borderColor = on ? CHIP_COLORS[c.dataset.bot] : 'var(--border-color)';
      c.style.background = on ? 'rgba(255,255,255,.06)' : 'var(--bg-card)';
    });
    if ($('tgm-start-label')) $('tgm-start-label').textContent = CHIP_LABELS[bot].replace(' Bot', '');
  }
  // Result panel: totals, then one line per account with the bot(s) it reached.
  function showStartResult(j) {
    var box = $('tgm-start-result');
    if (!box) return;
    function pill(n, label, color) {
      return '<span style="padding:.3rem .7rem;border-radius:999px;font-size:.8rem;font-weight:700;border:1px solid ' + color + '55;color:' + color + ';background:' + color + '14;">' + n + ' ' + label + '</span>';
    }
    var accts = (j.accounts || []).map(function (a) {
      var st = a.skipped ? '<span style="color:#94a3b8;">skipped — ' + esc(a.skipped) + '</span>'
        : (a.error ? '<span style="color:#f87171;">' + esc(a.error) + '</span>'
        : (a.bots || []).map(function (b) {
            return '<span style="margin-right:8px;color:' + (b.ok ? '#4ade80' : '#f87171') + ';">' +
              (b.ok ? '\u2713' : '\u2717') + ' ' + esc(b.name || b.target) +
              (b.ok ? '' : ' (' + esc(b.error || 'failed') + ')') + '</span>';
          }).join(''));
      return '<div style="display:flex;gap:.6rem;align-items:baseline;padding:.35rem 0;border-top:1px solid var(--border-color);font-size:.8rem;">' +
        '<strong style="min-width:150px;color:var(--text-main);">' + esc(a.name || a.id) + '</strong><span>' + st + '</span></div>';
    }).join('');
    box.style.display = 'block';
    box.innerHTML =
      '<div style="display:flex;gap:.5rem;flex-wrap:wrap;">' +
        pill(j.sent, 'reached', '#4ade80') + pill(j.skipped, 'skipped', '#94a3b8') +
        pill(j.failed, 'failed', j.failed ? '#f87171' : '#64748b') +
        '<span class="creator-option-hint" style="align-self:center;">' + (j.elapsed_s != null ? j.elapsed_s + 's' : '') + '</span></div>' +
      '<div style="max-height:260px;overflow:auto;margin-top:.6rem;">' + accts + '</div>';
  }

  function shell() {
    root.innerHTML =
      '<div class="tgm-bots" id="tgm-bots"></div>' +
      '<div class="card-panel">' +
        '<div class="card-top" style="margin-bottom:0.75rem;">' +
          '<div><strong style="display:flex;align-items:center;gap:8px;font-size:0.95rem;"><i class="fa-brands fa-telegram" style="color:#229ed9;"></i> Telegram Profiles</strong>' +
          '<div class="creator-option-hint" id="tgm-counts" style="margin-top:2px;">\u2026</div></div>' +
          '<div class="button-row" style="display:flex;gap:8px;align-items:center;">' +
            '<button id="tgm-add" type="button" class="btn btn-sm btn-primary"><i class="fa-solid fa-plus"></i> Connect account</button>' +
            '<button id="tgm-bal" type="button" class="btn btn-sm btn-secondary"><i class="fa-solid fa-wallet"></i> Check Balances</button>' +
            '<button id="tgm-refresh" type="button" class="btn btn-sm btn-secondary"><i class="fa-solid fa-rotate"></i> Refresh</button>' +
          '</div>' +
        '</div>' +
        '<div id="tgm-accounts" class="tgm-grid"></div>' +
        '<div id="tgm-bal-wrap" style="display:none;margin-top:1.25rem;padding-top:1rem;border-top:1px solid var(--border-color);"></div>' +
      '</div>' +

      /* ---- Send /start (own card, bottom) ---- */
      '<div class="card-panel" id="tgm-start-card" style="margin-top:1rem;">' +
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:.9rem;">' +
          '<div><strong style="display:flex;align-items:center;gap:8px;font-size:.95rem;"><i class="fa-solid fa-paper-plane" style="color:#38bdf8;"></i> Send /start</strong>' +
          '<div class="creator-option-hint" style="margin-top:2px;">Wakes the bot menu from every idle, connected Telegram profile. Busy profiles are skipped.</div></div>' +
          '<span id="tgm-start-idle" class="tg-bot-badge">\u2026</span>' +
        '</div>' +
        '<div id="tgm-start-chips" style="display:flex;gap:.6rem;flex-wrap:wrap;">' +
          chip('all', 'fa-solid fa-layer-group', 'All bots', '#a5b4fc', true) +
          chip('taskly', 'fa-solid fa-bolt', 'Taksly', '#229ED9') +
          chip('paygo', 'fa-solid fa-coins', 'PayGo', '#4ade80') +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:1rem;margin-top:1rem;flex-wrap:wrap;">' +
          '<button id="tgm-start" type="button" class="btn btn-primary"><i class="fa-solid fa-paper-plane"></i> Send "/start" to <span id="tgm-start-label">All bots</span></button>' +
          '<div id="tgm-start-result" style="display:none;gap:.5rem;flex-wrap:wrap;"></div>' +
        '</div>' +
      '</div>' +

      /* ---- Withdraw dialog (per account) ---- */
      '<div id="tgm-wd-modal" class="modal-overlay">' +
        '<div class="modal-box" style="max-width:560px;width:92%;">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;padding:0.9rem 1rem;border-bottom:1px solid var(--border-color);">' +
            '<strong><i class="fa-solid fa-money-bill-transfer" style="color:#22c55e;"></i> Withdraw \u00b7 <span id="tgm-wd-acct">\u2014</span></strong>' +
            '<button type="button" class="btn-icon-danger" data-close="tgm-wd-modal" title="Close"><i class="fa-solid fa-xmark"></i></button>' +
          '</div>' +
          '<div style="padding:1rem;">' +
            '<div class="creator-field" style="margin-bottom:0.9rem;"><label>BEP-20 wallet address</label>' +
              '<div style="display:flex;gap:0.5rem;">' +
                '<input id="tgm-wd-wallet" class="form-control" placeholder="0x\u2026 (40 hex chars)" autocomplete="off" spellcheck="false">' +
                '<button id="tgm-wd-save" type="button" class="btn btn-sm btn-secondary" style="white-space:nowrap;"><i class="fa-solid fa-floppy-disk"></i> Save</button>' +
              '</div></div>' +
            '<div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:0.9rem;">' +
              '<label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;">' +
                '<span class="switch" title="Freeze TG: no other code can lease a profile while frozen"><input type="checkbox" id="tgm-wd-freeze-sw"><span class="slider"></span></span>' +
                '<span style="font-size:0.8rem;color:var(--text-main);">Freeze TG (exclusive access)</span>' +
              '</label>' +
              '<span id="tgm-wd-freeze-pill" class="badge-pill">\u2014</span>' +
            '</div>' +
            '<div id="tgm-wd-rows" style="display:flex;flex-direction:column;gap:0.6rem;"><div class="creator-option-hint">Reading balances\u2026</div></div>' +
            '<div id="tgm-wd-result" class="creator-option-hint" style="margin-top:0.7rem;"></div>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- Confirm dialog (replaces window.confirm) ---- */
      '<div id="tgm-confirm-modal" class="modal-overlay">' +
        '<div class="modal-box modal-box--sm" style="max-width:440px;width:92%;">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;padding:0.9rem 1rem;border-bottom:1px solid var(--border-color);">' +
            '<strong id="tgm-confirm-title" style="font-size:0.95rem;"><i class="fa-solid fa-circle-question" style="color:#f59e0b;"></i> Confirm</strong>' +
            '<button type="button" class="btn-icon-danger" data-close="tgm-confirm-modal" title="Close"><i class="fa-solid fa-xmark"></i></button>' +
          '</div>' +
          '<div id="tgm-confirm-msg" style="padding:1rem;font-size:0.85rem;color:var(--text-main);line-height:1.55;"></div>' +
          '<div style="display:flex;justify-content:flex-end;gap:0.5rem;padding:0.9rem 1rem;border-top:1px solid var(--border-color);">' +
            '<button type="button" class="btn btn-secondary" id="tgm-confirm-cancel">Cancel</button>' +
            '<button type="button" class="btn btn-primary" id="tgm-confirm-ok">OK</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    wire();
  }

  function boot() {
    root = $('tg-manager-root');
    if (!root) return;
    shell();
    loadWithdraw();
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 8000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
