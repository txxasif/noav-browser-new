/**
 * Money dashboard + per-user money modal.
 * R&D: inline row editing (Enter saves + advances), bulk mark-paid,
 * previous-month amounts as placeholders, shared pager, hash routing.
 */

export function billingScript() {
  return `
    var billMap = {};
    var billMonth = '';
    var moneyKey = '';
    var ledgerRows = [];
    var prevMap = {};
    var ledgerPage = 1;

    var NAV_ON = 'text-left px-4 py-2.5 rounded-xl transition flex items-center gap-3 bg-indigo-600/20 text-white border border-indigo-500/30';
    var NAV_OFF = 'text-left px-4 py-2.5 rounded-xl transition flex items-center gap-3 text-slate-400 hover:text-white hover:bg-white/5 border border-transparent';

    function escHtml(s) {
      return String(s == null ? '' : s).replace(/[&<>"]/g, function(c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
    }

    function billFetch(path, opts) {
      opts = opts || {};
      opts.headers = Object.assign({ 'Authorization': 'Bearer ' + token }, opts.headers || {});
      return fetch(path, opts).then(function(res) {
        if (res.status === 401) { logout(); throw new Error('unauthorized'); }
        return res.json();
      });
    }

    function currentYM() {
      var d = new Date();
      return d.toISOString().slice(0, 7);
    }

    function prevYM(ym) {
      var y = parseInt(ym.slice(0, 4), 10), m = parseInt(ym.slice(5, 7), 10) - 1;
      if (m < 1) { m = 12; y--; }
      return y + '-' + (m < 10 ? '0' + m : m);
    }

    /* ---------- views + sidebar ---------- */

    function showView(which) {
      var toMoney = which === 'money';
      document.getElementById('viewLicenses').classList.toggle('hidden', toMoney);
      document.getElementById('viewMoney').classList.toggle('hidden', !toMoney);
      var nL = document.getElementById('navLicenses');
      var nM = document.getElementById('navMoney');
      if (nL) nL.className = toMoney ? NAV_OFF : NAV_ON;
      if (nM) nM.className = toMoney ? NAV_ON : NAV_OFF;
      try {
        if (('#/' + which) !== location.hash) location.hash = '#/' + which;
      } catch (e) {}
      toggleSidebar(false);
      if (toMoney) loadMoney();
    }

    function toggleSidebar(force) {
      var sb = document.getElementById('sidebar');
      var bd = document.getElementById('sideBackdrop');
      if (!sb) return;
      var show = typeof force === 'boolean' ? force : !sb.classList.contains('open');
      sb.classList.toggle('open', show);
      if (bd) bd.classList.toggle('hidden', !show);
    }

    function routeFromHash() {
      try {
        showView(location.hash === '#/money' ? 'money' : 'licenses');
      } catch (e) {}
    }

    /* ---------- money data ---------- */

    function syncMonthInputs(from) {
      var m1 = document.getElementById('billMonthFilter');
      var m2 = document.getElementById('moneyMonth');
      if (from === 'money' && m1 && m2) m1.value = m2.value;
      if (from === 'bill' && m1 && m2) m2.value = m1.value;
    }

    async function loadBilling() {
      var input = document.getElementById('billMonthFilter');
      if (!input) return;
      if (!input.value) input.value = currentYM();
      syncMonthInputs('bill');
      await loadMoney();
    }

    async function loadMoney() {
      var input = document.getElementById('moneyMonth') || document.getElementById('billMonthFilter');
      if (!input) return;
      if (!input.value) input.value = currentYM();
      syncMonthInputs(input.id === 'moneyMonth' ? 'money' : 'bill');
      billMonth = input.value;
      var lbl = document.getElementById('billMonthLabel');
      if (lbl) lbl.textContent = '(' + billMonth + ')';
      var kpiM = document.getElementById('kpiMonth');
      if (kpiM) kpiM.textContent = billMonth;
      var msg = document.getElementById('moneyMsg');
      try {
        var data = await billFetch('/api/admin/payments?month=' + encodeURIComponent(billMonth));
        billMap = {};
        (data.rows || []).forEach(function(r) {
          if (r.billing_month) billMap[r.license_key] = r;
        });
        renderMoneyKpis(data.rows || []);
        var pm = prevYM(billMonth);
        var prev = await billFetch('/api/admin/payments?month=' + encodeURIComponent(pm));
        prevMap = {};
        (prev.rows || []).forEach(function(r) {
          if (r.billing_month) prevMap[r.license_key] = r;
        });
        ledgerRows = data.rows || [];
        ledgerPage = 1;
        renderLedger();
        var s = await billFetch('/api/admin/payments/summary');
        if (s.success) renderTrend(s.months || []);
        if (msg) msg.textContent = '';
      } catch (e) {
        console.error('Money load failed:', e);
        if (msg) msg.textContent = 'Load failed.';
      }
      applyFilters();
    }

    function renderMoneyKpis(rows) {
      // Business rule: Amount = monthly fee charged. PAID = cash received.
      // Outstanding = UNPAID fees only (FREE_TOKEN waived, unrecorded = no entry yet).
      var collected = 0, outstanding = 0, unpaidN = 0, unrec = 0;
      rows.forEach(function(r) {
        if (r.billing_month) {
          var amt = Number(r.amount || 0);
          if (r.payment_status === 'PAID') collected += amt;
          else if (r.payment_status === 'UNPAID') { outstanding += amt; unpaidN++; }
        } else {
          unrec++;
        }
      });
      var elC = document.getElementById('kpiCollected');
      var elO = document.getElementById('kpiOutstanding');
      var elU = document.getElementById('kpiUnpaidCount');
      var elN = document.getElementById('kpiUnrecorded');
      var elR = document.getElementById('kpiRate');
      if (elC) elC.textContent = collected;
      if (elO) elO.textContent = outstanding;
      if (elU) elU.textContent = unpaidN;
      if (elN) elN.textContent = unrec;
      var denom = collected + outstanding;
      if (elR) elR.textContent = denom > 0 ? Math.round((collected / denom) * 100) + '%' : '–';
      renderDonut(collected, outstanding);
    }

    function renderDonut(collected, outstanding) {
      var el = document.getElementById('donutWrap');
      if (!el) return;
      var total = collected + outstanding;
      var r = 30, c = 2 * Math.PI * r;
      var frac = total > 0 ? collected / total : 0;
      var col = frac >= 0.7 ? '#34d399' : (frac >= 0.4 ? '#fbbf24' : '#f87171');
      el.innerHTML =
        '<svg width="76" height="76" viewBox="0 0 76 76" role="img" aria-label="Collection rate">' +
        '<circle cx="38" cy="38" r="' + r + '" fill="none" stroke="#232f48" stroke-width="10"/>' +
        '<circle cx="38" cy="38" r="' + r + '" fill="none" stroke="' + col + '" stroke-width="10"' +
        ' stroke-linecap="round" stroke-dasharray="' + (frac * c).toFixed(1) + ' ' + c.toFixed(1) + '"' +
        ' transform="rotate(-90 38 38)"/>' +
        '<text x="38" y="43" text-anchor="middle" fill="#f1f5f9" font-size="14" font-weight="800">' +
        (total > 0 ? Math.round(frac * 100) + '%' : '–') + '</text></svg>';
    }

    function renderTrend(months) {
      var bars = document.getElementById('trendBars');
      var labels = document.getElementById('trendLabels');
      if (!bars || !labels) return;
      var max = 0;
      months.forEach(function(m) { max = Math.max(max, Number(m.collected || 0)); });
      var bh = '', lh = '';
      months.forEach(function(m) {
        var v = Number(m.collected || 0);
        var h = max > 0 ? Math.max(6, Math.round((v / max) * 60)) : 6;
        var short = String(m.billing_month || '').slice(5);
        bh += '<div class="flex-1 rounded-t-md" title="' + escHtml(m.billing_month) + ': ' + v + ' BDT"' +
          ' style="height:' + h + 'px;background:linear-gradient(to top,#059669,#34d399)"></div>';
        lh += '<div class="flex-1 text-center text-[10px] text-slate-500">' + escHtml(short) + '</div>';
      });
      bars.innerHTML = bh;
      labels.innerHTML = lh;
    }

    /* ---------- inline ledger ---------- */

    function ledgerFiltered() {
      var q = ((document.getElementById('moneySearch') || {}).value || '').toLowerCase().trim();
      var st = (document.getElementById('moneyStatus') || {}).value || 'ALL';
      return (ledgerRows || []).filter(function(r) {
        var paySt = r.billing_month ? r.payment_status : 'NONE';
        if (st !== 'ALL' && paySt !== st) return false;
        if (!q) return true;
        return ((r.username || '') + ' ' + (r.customer_name || '') + ' ' + (r.license_key || '')).toLowerCase().includes(q);
      });
    }

    function setLedgerPage(n) {
      var pages = Math.max(1, Math.ceil(ledgerFiltered().length / 10));
      ledgerPage = Math.max(1, Math.min(n, pages));
      renderLedger();
    }

    function renderLedger() {
      var tbody = document.getElementById('ledgerBody');
      if (!tbody) return;
      var list = ledgerFiltered();
      var pages = Math.max(1, Math.ceil(list.length / 10));
      if (ledgerPage > pages) ledgerPage = pages;
      var slice = list.slice((ledgerPage - 1) * 10, ledgerPage * 10);
      var html = '';
      slice.forEach(function(r, k) {
        var i = (ledgerPage - 1) * 10 + k;
        var st = r.billing_month ? r.payment_status : 'UNPAID';
        var recorded = Boolean(r.billing_month);
        var fee = recorded ? Number(r.amount || 0) : Number((prevMap[r.license_key] || {}).amount || 0);
        var feeTxt = recorded ? (fee + ' BDT') : (fee ? (fee + ' ↩ last') : '—');
        var who = r.username || r.customer_name || r.license_key;
        var btn;
        if (st === 'PAID') {
          btn = '<button onclick="toggleLedger(' + i + ')" class="px-4 py-1.5 bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 rounded-lg text-[11px] font-bold transition">PAID ✓</button>';
        } else if (st === 'FREE_TOKEN') {
          btn = '<button onclick="toggleLedger(' + i + ')" class="px-4 py-1.5 bg-purple-500/15 text-purple-300 border border-purple-500/40 rounded-lg text-[11px] font-bold transition">FREE</button>';
        } else {
          btn = '<button onclick="toggleLedger(' + i + ')" class="px-4 py-1.5 bg-white/5 text-slate-400 border border-slate-700 rounded-lg text-[11px] font-bold hover:border-red-500/50 hover:text-red-300 transition">UNPAID</button>';
        }
        html += '<tr class="table-row-hover transition">';
        html += '<td class="px-5 py-3"><div class="font-semibold text-slate-200">' + escHtml(who) + '</div>' +
          '<div class="text-[10px] text-slate-500 font-mono">' + escHtml(r.license_key) + '</div></td>';
        html += '<td class="px-5 py-3"><span class="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-md text-[11px] border border-slate-700">' + escHtml(r.plan || '') + '</span></td>';
        html += '<td class="px-5 py-3">' + btn + '</td>';
        html += '<td class="px-5 py-3 text-slate-300 font-mono">' + escHtml(feeTxt) + '</td>';
        html += '<td class="px-5 py-3 text-right"><button onclick="openMoneyModal(\\'' + escHtml(r.license_key) + '\\')" class="px-3 py-1.5 bg-dark-900 hover:bg-slate-800 text-slate-300 border border-slate-700/60 rounded-lg text-[11px] font-semibold transition">Edit</button></td>';
        html += '</tr>';
      });
      tbody.innerHTML = html || '<tr><td colspan="5" class="text-center py-10 text-slate-500">No matching users.</td></tr>';
      if (typeof renderPager === 'function') renderPager('ledgerPager', ledgerPage, pages, 'setLedgerPage', list.length);
    }

    async function toggleLedger(i) {
      var r = ledgerFiltered()[i];
      if (!r) return;
      var cur = r.billing_month ? r.payment_status : 'UNPAID';
      var next = cur === 'PAID' ? 'UNPAID' : 'PAID';
      var msg = document.getElementById('moneyMsg');
      var entry = {
        license_key: r.license_key,
        billing_month: billMonth,
        amount: r.billing_month ? Number(r.amount || 0) : Number((prevMap[r.license_key] || {}).amount || 0),
        payment_status: next,
        payment_method: (r.billing_month && r.payment_method) || 'Cash',
        notes: (r.billing_month && r.notes) || ''
      };
      try {
        var res = await billFetch('/api/admin/payments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(entry)
        });
        if (res.success) {
          if (msg) msg.textContent = (next === 'PAID' ? 'Paid ✓ ' : 'Unpaid · ') + (r.username || r.license_key).slice(-12);
          await reloadMoneyQuiet();
        } else if (msg) {
          msg.textContent = 'Error: ' + (res.message || 'failed');
        }
      } catch (err) {
        if (msg) msg.textContent = 'Save failed: ' + err.message;
      }
    }

    async function reloadMoneyQuiet() {
      try {
        var data = await billFetch('/api/admin/payments?month=' + encodeURIComponent(billMonth));
        billMap = {};
        (data.rows || []).forEach(function(r) {
          if (r.billing_month) billMap[r.license_key] = r;
        });
        ledgerRows = data.rows || [];
        renderMoneyKpis(ledgerRows);
        renderLedger();
        var s = await billFetch('/api/admin/payments/summary');
        if (s.success) renderTrend(s.months || []);
      } catch (e) {}
      applyFilters();
    }

    async function bulkMarkPaid() {
      var list = ledgerFiltered();
      if (!list.length) return;
      if (!confirm('Mark ' + list.length + ' visible row(s) as PAID for ' + billMonth + '? Amounts save as shown (blank keeps last month or 0).')) return;
      var msg = document.getElementById('moneyMsg');
      var done = 0;
      for (var k = 0; k < list.length; k++) {
        var r = list[k];
        var amt = r.billing_month ? Number(r.amount || 0) : Number((prevMap[r.license_key] || {}).amount || 0);
        try {
          await billFetch('/api/admin/payments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              license_key: r.license_key,
              billing_month: billMonth,
              amount: amt,
              payment_status: 'PAID',
              payment_method: (r.billing_month && r.payment_method) || 'Cash',
              notes: (r.billing_month && r.notes) || ''
            })
          });
          done++;
        } catch (e) {}
      }
      if (msg) msg.textContent = 'Marked ' + done + '/' + list.length + ' paid ✓';
      await reloadMoneyQuiet();
    }

    /* ---------- per-user money modal ---------- */

    async function openMoneyModal(key) {
      moneyKey = key;
      var lic = null;
      try {
        lic = (allLicenses || []).filter(function(l) { return l.license_key === key; })[0] || null;
      } catch (e) {}
      document.getElementById('moneyWho').textContent =
        ((lic && (lic.username || lic.customer_name)) || key) + ' · ' + ((lic && lic.plan) || '');
      document.getElementById('mMonth').value = billMonth || currentYM();
      document.getElementById('mAmount').value = '';
      document.getElementById('mStatus').value = 'UNPAID';
      document.getElementById('mMethod').value = 'Cash';
      document.getElementById('mNotes').value = '';
      document.getElementById('moneyMsg').textContent = '';
      document.getElementById('moneyModal').classList.remove('hidden');
      await prefillMoneyEntry();
      await loadMoneyHistory();
    }

    function closeMoneyModal() {
      document.getElementById('moneyModal').classList.add('hidden');
      moneyKey = '';
    }

    async function prefillMoneyEntry() {
      try {
        var data = await billFetch('/api/admin/payments/history?license_key=' + encodeURIComponent(moneyKey));
        var cur = (data.rows || []).filter(function(r) { return r.billing_month === document.getElementById('mMonth').value; })[0];
        if (cur) {
          document.getElementById('mAmount').value = cur.amount == null ? '' : cur.amount;
          document.getElementById('mStatus').value = cur.payment_status || 'UNPAID';
          document.getElementById('mMethod').value = cur.payment_method || 'Cash';
          document.getElementById('mNotes').value = cur.notes || '';
        }
      } catch (e) {}
    }

    async function loadMoneyHistory() {
      var box = document.getElementById('moneyHistory');
      try {
        var data = await billFetch('/api/admin/payments/history?license_key=' + encodeURIComponent(moneyKey));
        var rows = data.rows || [];
        if (!rows.length) {
          box.innerHTML = '<div class="text-slate-500">No entries yet.</div>';
          return;
        }
        box.innerHTML = rows.map(function(r) {
          var cls = r.payment_status === 'PAID' ? 'paid-txt' : (r.payment_status === 'FREE_TOKEN' ? 'text-purple-400 font-bold' : 'unpaid-txt');
          return '<div class="flex items-center justify-between gap-2 bg-white/[0.03] border border-white/5 rounded-lg px-3 py-2">' +
            '<span class="font-mono text-slate-300">' + escHtml(r.billing_month) + '</span>' +
            '<span class="' + cls + '">' + escHtml(r.payment_status) + '</span>' +
            '<span class="text-slate-300">' + escHtml(r.amount) + ' BDT</span>' +
            '<button onclick="jumpMoneyMonth(\\'' + escHtml(r.billing_month) + '\\')" class="text-indigo-400 hover:text-indigo-300 hover:underline">Edit</button>' +
            '</div>';
        }).join('');
      } catch (e) {
        box.innerHTML = '<div class="text-slate-500">History unavailable.</div>';
      }
    }

    async function jumpMoneyMonth(month) {
      document.getElementById('mMonth').value = month;
      await prefillMoneyEntry();
    }

    async function submitMoney(e) {
      e.preventDefault();
      var entry = {
        license_key: moneyKey,
        billing_month: document.getElementById('mMonth').value,
        amount: Number(document.getElementById('mAmount').value || 0),
        payment_status: document.getElementById('mStatus').value,
        payment_method: document.getElementById('mMethod').value || 'Cash',
        notes: document.getElementById('mNotes').value || ''
      };
      try {
        var r = await billFetch('/api/admin/payments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(entry)
        });
        if (r.success) {
          document.getElementById('moneyMsg').textContent = 'Saved ✓';
          await loadMoneyHistory();
          await reloadMoneyQuiet();
        } else {
          document.getElementById('moneyMsg').textContent = 'Error: ' + (r.message || 'failed');
        }
      } catch (err) {
        document.getElementById('moneyMsg').textContent = 'Save failed: ' + err.message;
      }
    }

    async function delMoneyEntry() {
      var month = document.getElementById('mMonth').value;
      if (!moneyKey || !month) return;
      if (!confirm('Delete the ' + month + ' entry for this user?')) return;
      try {
        var d = await billFetch('/api/admin/payments?license_key=' + encodeURIComponent(moneyKey) + '&billing_month=' + encodeURIComponent(month), { method: 'DELETE' });
        if (d.success) {
          document.getElementById('moneyMsg').textContent = 'Deleted ✓';
          await loadMoneyHistory();
          await reloadMoneyQuiet();
        }
      } catch (err) {
        document.getElementById('moneyMsg').textContent = 'Delete failed: ' + err.message;
      }
    }

    (function initBilling() {
      var f = document.getElementById('moneyForm');
      if (f) f.addEventListener('submit', submitMoney);
      var mf = document.getElementById('moneyMonth');
      var bf = document.getElementById('billMonthFilter');
      if (mf && !mf.value) mf.value = currentYM();
      if (bf && !bf.value) bf.value = mf ? mf.value : currentYM();
      try {
        if (typeof window.addEventListener === 'function') window.addEventListener('hashchange', routeFromHash);
      } catch (e) {}
      try {
        if (token) {
          routeFromHash();
          if (!document.getElementById('dashboardView').classList.contains('hidden')) loadBilling();
        }
      } catch (e) {}
    })();
`;
}
