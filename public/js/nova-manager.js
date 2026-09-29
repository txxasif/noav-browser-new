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
    var busyTxt = b.busy_other ? (' \u00b7 ' + b.busy_other + ' busy elsewhere') : '';
    return '<div class="tgm-bot">' +
      '<h4><img src="img/bot_logo/' + botLogo(b.id) + '.png" width="22" height="22" ' +
        'style="border-radius:50%;object-fit:cover;" onerror="this.style.display=\'none\'" alt=""> ' +
        esc(b.name) + '</h4>' +
      '<div class="tgm-sub">@' + esc(b.username) + (b.flows ? ' \u00b7 ' + esc(b.flows.join('/')) : '') + '</div>' +
      '<div class="tgm-metrics">' +
        '<div class="tgm-metric"><b>' + (b.free || 0) + '</b>free</div>' +
        '<div class="tgm-metric"><b>' + (b.connected || 0) + '</b>connected</div>' +
        '<div class="tgm-metric"><b>' + (b.tasks ? b.tasks.length : 0) + '</b>tasks</div>' +
      '</div>' +
      '<div class="tgm-sub" style="margin-top:6px;">' + esc((b.tasks || []).join(' \u00b7 ')) + busyTxt + '</div>' +
    '</div>';
  }

  function acctRow(a) {
    var dot = !a.logged_in ? 'dead' : (!a.enabled ? 'off' : (a.status === 'busy' ? 'busy' : ''));
    var statusPill = a.status === 'busy'
      ? '<span class="profile-status-badge" style="background:rgba(245,158,11,.18);color:var(--accent-amber);border:1px solid rgba(245,158,11,.35);">Busy' +
        (a.busy_bot ? ' \u00b7 ' + esc(a.busy_bot) : '') + '</span>'
      : (a.logged_in
          ? '<span class="profile-status-badge badge-active">Ready</span>'
          : '<span class="profile-status-badge badge-inactive">Not logged in</span>');
    var meta = [];
    if (a.phone) meta.push(esc(a.phone));
    meta.push(esc((a.mode || 'web').toUpperCase()));
    meta.push((a.tasks_done || 0) + ' tasks');
    return '<div class="tgm-acct' + (a.status === 'busy' ? ' tgm-busy' : '') + '">' +
      '<div class="tgm-acct-main">' +
        '<span class="tgm-dot ' + dot + '"></span>' +
        '<div><div class="tgm-acct-title"><strong>' + esc(a.label || a.id) + '</strong>' +
          '<span class="badge-pill">' + esc(a.id) + '</span>' + statusPill + '</div>' +
          '<div class="tgm-acct-meta">' + meta.join(' \u00b7 ') + '</div></div>' +
      '</div>' +
      '<div class="tgm-acct-actions">' +
        '<span class="creator-option-hint">' + (a.enabled ? 'Enabled' : 'Disabled') + '</span>' +
        '<label class="switch" title="' + (a.enabled ? 'Disable (stops receiving tasks)' : 'Enable for tasks') + '">' +
          '<input type="checkbox" data-tgm-enable="' + esc(a.id) + '"' + (a.enabled ? ' checked' : '') +
          (a.status === 'busy' ? ' disabled' : '') + '><span class="slider"></span></label>' +
        '<button type="button" class="btn btn-sm btn-danger" data-tgm-del="' + esc(a.id) + '"' +
          ' title="Remove this profile and its session"><i class="fa-solid fa-trash-can"></i></button>' +
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
      var money = function (x) { return x && x.ok ? '$' + Number(x.amount || 0).toFixed(2) : '\u2014'; };
      return '<tr><td>' + esc(a.id || '?') + (a.error ? ' <span class="creator-option-hint">' + esc(a.error) + '</span>' : '') +
        '</td><td class="r">' + money(t) + '</td><td class="r">' + money(p) + '</td>' +
        '<td class="r">$' + Number(a.total || 0).toFixed(2) + '</td></tr>';
    }).join('');
    var T = b.totals || {};
    wrap.style.display = 'block';
    wrap.innerHTML = '<strong>Balances</strong>' +
      '<table class="tgm-bal"><thead><tr><th>Account</th><th class="r">Taskly</th><th class="r">PayGo</th><th class="r">Total</th></tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
      '<tfoot><tr style="font-weight:700;"><td>TOTAL</td><td class="r">$' + Number(T.taskly || 0).toFixed(2) +
      '</td><td class="r">$' + Number(T.paygo || 0).toFixed(2) + '</td><td class="r">$' + Number(T.grand || 0).toFixed(2) +
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
        '<div class="card-top" style="margin-bottom:0.6rem;">' +
          '<div><strong>Telegram Profiles</strong>' +
          '<div class="creator-option-hint" id="tgm-counts">\u2026</div></div>' +
          '<div class="button-row">' +
            '<button id="tgm-add" type="button" class="btn btn-sm btn-primary"><i class="fa-solid fa-plus"></i> Connect account</button>' +
            '<button id="tgm-bal" type="button" class="btn btn-sm btn-secondary"><i class="fa-solid fa-wallet"></i> Check Balances</button>' +
            '<button id="tgm-refresh" type="button" class="btn btn-sm btn-secondary"><i class="fa-solid fa-rotate"></i> Refresh</button>' +
          '</div>' +
        '</div>' +
        '<div id="tgm-accounts"></div>' +
        '<div id="tgm-bal-wrap" style="display:none;margin-top:1rem;"></div>' +
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
