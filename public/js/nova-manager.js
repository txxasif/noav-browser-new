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

  function botLogo(id) { return id === 'paygo' ? 'paygo' : (id === 'fastpay' ? 'fastpay' : 'taskly'); }

  function botCard(b) {
    var busyTxt = b.busy_other ? (b.busy_other + ' busy elsewhere') : '';
    var botColor = b.id === 'paygo' ? '#f59e0b' : (b.id === 'fastpay' ? '#10b981' : '#229ED9');
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
          '<label class="switch" title="' + (a.enabled ? 'Disable (stops receiving tasks)' : 'Enable for tasks') + '">' +
            '<input type="checkbox" data-tgm-enable="' + esc(a.id) + '"' + (a.enabled ? ' checked' : '') +
            (a.status === 'busy' ? ' disabled' : '') + '><span class="slider"></span></label>' +
          '<button type="button" class="btn-icon-danger" data-tgm-del="' + esc(a.id) + '"' +
            ' title="Remove this profile and its session"><i class="fa-solid fa-trash-can"></i></button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }

  function renderBalances(b) {
    var wrap = $('tgm-bal-wrap');
    if (!wrap) return;
    if (!b || !b.accounts) { wrap.style.display = 'block'; wrap.innerHTML = '<div class="creator-option-hint">' + esc((b && b.error) || 'no result') + '</div>'; return; }
    var rows = b.accounts.map(function (a) {
      var t = (a.bots || []).filter(function (x) { return x.target === 'taskly'; })[0];
      var p = (a.bots || []).filter(function (x) { return x.target === 'paygo'; })[0];
      var f = (a.bots || []).filter(function (x) { return x.target === 'fastpay'; })[0];
      var money = function (x) { return x && x.ok ? '$' + Number(x.amount || 0).toFixed(2) : '\u2014'; };
      var fMoney = function (x) {
        if (!x || !x.ok) return '\u2014';
        var s = '$' + Number(x.amount || 0).toFixed(2);
        if (x.pending) {
          s += ' <span class="badge-pill" style="margin-left:5px;font-size:10px;padding:1px 5px;background:rgba(234,179,8,0.12);color:#eab308;border:1px solid rgba(234,179,8,0.25);" title="Pending Balance: $' + Number(x.pending).toFixed(2) + '">+' + Number(x.pending).toFixed(2) + ' pend</span>';
        }
        return s;
      };
      return '<tr><td>' + esc(a.id || '?') + (a.error ? ' <span class="creator-option-hint">' + esc(a.error) + '</span>' : '') +
        '</td><td class="r">' + money(t) + '</td><td class="r">' + money(p) + '</td><td class="r">' + fMoney(f) + '</td>' +
        '<td class="r">$' + Number(a.total || 0).toFixed(2) + '</td></tr>';
    }).join('');
    var T = b.totals || {};
    var fpTot = '$' + Number(T.fastpay || 0).toFixed(2);
    if (T.fastpay_pending) {
      fpTot += ' <span style="font-size:10px;color:#eab308;font-weight:500;">(+$' + Number(T.fastpay_pending).toFixed(2) + ' pend)</span>';
    }
    var T = b.totals || {};
    var fpTot = '$' + Number(T.fastpay || 0).toFixed(2);
    if (T.fastpay_pending) {
      fpTot += ' <span style="font-size:10px;color:#eab308;font-weight:500;">(+$' + Number(T.fastpay_pending).toFixed(2) + ' pend)</span>';
    }
    var stamp = '';
    if (b.elapsed_s != null) {
      stamp = ' <span class="creator-option-hint" style="margin-left:6px;">'
        + (b.cached ? 'cached' : 'read in ' + Number(b.elapsed_s).toFixed(1) + 's') + '</span>';
    }
    wrap.style.display = 'block';
    wrap.innerHTML = '<div style="margin-bottom:0.6rem;font-weight:600;font-size:0.85rem;color:var(--text-main);"><i class="fa-solid fa-wallet" style="color:#229ed9;margin-right:6px;"></i> Account Balances' + stamp + '</div>' +
      '<table class="tgm-bal"><thead><tr><th>Account</th><th class="r">Taskly</th><th class="r">PayGo</th><th class="r">FastPay <span style="font-size:10px;font-weight:normal;opacity:0.65;">(Avail + Pend)</span></th><th class="r">Total</th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
      '<tfoot><tr style="font-weight:700;"><td>TOTAL</td><td class="r">$' + Number(T.taskly || 0).toFixed(2) +
      '</td><td class="r">$' + Number(T.paygo || 0).toFixed(2) + '</td><td class="r">' + fpTot + '</td><td class="r">$' + Number(T.grand || 0).toFixed(2) +
      '</td></tr></tfoot></table>';
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
    wireRows();
  }

  function wireRows() {
    document.querySelectorAll('[data-tgm-enable]').forEach(function (b) {
      b.addEventListener('change', function () { toggle(b.dataset.tgmEnable, b.checked); });
    });
    document.querySelectorAll('[data-tgm-del]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!confirm('Remove ' + b.dataset.tgmDel + ' and its session?')) return;
        action('/api/tg/accounts/remove', { id: b.dataset.tgmDel }, b.dataset.tgmDel + ' removed');
      });
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
    if (enabled.indexOf('fastpay') === -1) {
      var fp = document.querySelector('.nav-sub[data-view="view-tg-classic"][data-bot="fastpay"]');
      if (fp) fp.style.display = 'none';
    }
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

  function checkBalances() {
    var btn = $('tgm-bal');
    if (btn) btn.disabled = true;
    var wrap = $('tgm-bal-wrap');
    if (wrap) { wrap.style.display = 'block'; wrap.innerHTML = '<div class="creator-option-hint">Reading balances\u2026</div>'; }
    fetch('/api/tg/manager/balance', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      .then(function (r) { return r.json(); })
      .then(function (b) { renderBalances(b); })
      .catch(function (e) { renderBalances({ error: String(e) }); })
      .finally(function () { if (btn) btn.disabled = false; });
  }

  function wire() {
    if ($('tgm-refresh')) $('tgm-refresh').addEventListener('click', refresh);
    if ($('tgm-bal')) $('tgm-bal').addEventListener('click', checkBalances);
    if ($('tgm-add')) $('tgm-add').addEventListener('click', function () {
      if (typeof window.openMtprotoModal === 'function') { window.openMtprotoModal(); return; }
      toast('Add-account modal unavailable.', 'error');
    });
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
      '</div>';
    wire();
  }

  function boot() {
    root = $('tg-manager-root');
    if (!root) return;
    shell();
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 8000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
