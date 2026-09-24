/**
 * Original dashboard client logic, verbatim except showDashboard()
 * also refreshes the billing tab when present.
 */

export function licenseScript() {
  return `
    var allLicenses = [];
    var token = sessionStorage.getItem('Nova_admin_token') || '';

    function showToast(msg, type) {
      var c = document.getElementById('toastContainer');
      var t = document.createElement('div');
      var isErr = type === 'error';
      t.className = 'px-4 py-3 rounded-xl text-xs font-semibold shadow-2xl pointer-events-auto transition transform duration-300 translate-y-0 flex items-center gap-2 ' +
        (isErr ? 'bg-red-500 text-white' : 'bg-indigo-600 text-white shadow-indigo-500/30');
      t.textContent = msg;
      c.appendChild(t);
      setTimeout(function() {
        t.style.opacity = '0';
        setTimeout(function() { t.remove(); }, 300);
      }, 3000);
    }

    function copyKey(key) {
      navigator.clipboard.writeText(key);
      showToast('Copied ' + key + ' to clipboard!');
    }

    // Attach form submit listeners
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('generateForm').addEventListener('submit', submitGenerate);
    document.getElementById('licenseTableBody').addEventListener('click', handleTableClick);

    async function handleLogin(e) {
      e.preventDefault();
      var pwdInput = document.getElementById('adminPasswordInput');
      var pwd = pwdInput ? pwdInput.value.trim() : '';
      var errBox = document.getElementById('loginError');
      errBox.classList.add('hidden');

      if (!pwd) {
        errBox.textContent = 'Please enter master password.';
        errBox.classList.remove('hidden');
        return;
      }

      try {
        var res = await fetch('/api/admin/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pwd })
        });
        var data = await res.json();
        if (res.ok && data.success) {
          token = data.token;
          sessionStorage.setItem('Nova_admin_token', token);
          showDashboard();
          showToast('Welcome to Nova Cloud Console!');
        } else {
          errBox.textContent = data.message || 'Incorrect password.';
          errBox.classList.remove('hidden');
        }
      } catch (err) {
        errBox.textContent = 'Server communication error: ' + err.message;
        errBox.classList.remove('hidden');
      }
    }

    function showDashboard() {
      document.getElementById('loginView').classList.add('hidden');
      document.getElementById('dashboardView').classList.remove('hidden');
      loadLicenses();
      if (typeof loadBilling === 'function') loadBilling();
      try { if (typeof routeFromHash === 'function' && location.hash === '#/money') routeFromHash(); } catch (e) {}
    }

    function logout() {
      token = '';
      sessionStorage.removeItem('Nova_admin_token');
      document.getElementById('loginView').classList.remove('hidden');
      document.getElementById('dashboardView').classList.add('hidden');
    }

    async function loadLicenses() {
      try {
        var res = await fetch('/api/admin/licenses', {
          headers: { 'Authorization': 'Bearer ' + token }
        });
        if (res.status === 401) return logout();
        var data = await res.json();
        allLicenses = data.licenses || [];

        var elTotal = document.getElementById('statTotal');
        var elActive = document.getElementById('statActive');
        var elRevoked = document.getElementById('statRevoked');
        var elTrials = document.getElementById('statTrials');

        if (elTotal) elTotal.textContent = allLicenses.length;
        if (elActive) elActive.textContent = allLicenses.filter(function(l) { return l.status === 'ACTIVE'; }).length;
        if (elRevoked) elRevoked.textContent = allLicenses.filter(function(l) { return l.status === 'REVOKED'; }).length;
        if (elTrials) elTrials.textContent = data.trialCount || 0;

        applyFilters();
      } catch (e) {
        console.error('Failed to load licenses:', e);
      }
    }

    var licPage = 1;
    var PER_PAGE = 10;

    /* Shared pager: renderPager('licPager', page, pages, 'setLicPage') */
    function renderPager(elId, page, pages, goFn, total) {
      var el = document.getElementById(elId);
      if (!el) return;
      if (!pages || pages < 1) pages = 1;
      if (page < 1) page = 1;
      if (page > pages) page = pages;
      var nums = '';
      var start = Math.max(1, Math.min(page - 2, pages - 4));
      var end = Math.min(pages, start + 4);
      for (var n = start; n <= end; n++) {
        nums += '<button onclick="' + goFn + '(' + n + ')" class="min-w-[28px] px-2 py-1 rounded-lg ' +
          (n === page ? 'bg-indigo-600 text-white font-bold' : 'bg-dark-900 text-slate-300 hover:bg-slate-800 border border-slate-700/60') + '">' + n + '</button>';
      }
      el.innerHTML =
        '<span>' + total + ' item' + (total === 1 ? '' : 's') + ' · page ' + page + ' of ' + pages + '</span>' +
        '<span class="flex items-center gap-1.5">' +
        '<button onclick="' + goFn + '(' + (page - 1) + ')" ' + (page <= 1 ? 'disabled' : '') +
        ' class="px-2.5 py-1 rounded-lg bg-dark-900 border border-slate-700/60 disabled:opacity-40">‹ Prev</button>' +
        nums +
        '<button onclick="' + goFn + '(' + (page + 1) + ')" ' + (page >= pages ? 'disabled' : '') +
        ' class="px-2.5 py-1 rounded-lg bg-dark-900 border border-slate-700/60 disabled:opacity-40">Next ›</button>' +
        '</span>';
    }

    function setLicPage(n) {
      var pages = Math.max(1, Math.ceil((window._filtered || []).length / PER_PAGE));
      licPage = Math.max(1, Math.min(n, pages));
      renderTable(window._filtered || []);
    }

    function applyFilters() {
      licPage = 1;
      var q = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      var sf = document.getElementById('statusFilter').value;
      var pfEl = document.getElementById('payFilter');
      var pf = pfEl ? pfEl.value : 'ALL';

      var filtered = allLicenses.filter(function(l) {
        var matchesQuery = !q ||
          (l.license_key || '').toLowerCase().includes(q) ||
          (l.customer_name || '').toLowerCase().includes(q) ||
          (l.customer_phone || '').toLowerCase().includes(q) ||
          (l.hwid || '').toLowerCase().includes(q);

        var matchesStatus = sf === 'ALL' || l.status === sf;

        var paySt = 'NONE';
        try { paySt = (typeof billMap !== 'undefined' && billMap[l.license_key]) ? billMap[l.license_key].payment_status : 'NONE'; } catch (e) {}
        var matchesPay = pf === 'ALL' || paySt === pf;
        return matchesQuery && matchesStatus && matchesPay;
      });

      renderTable(filtered);
    }

    function renderTable(list) {
      var tbody = document.getElementById('licenseTableBody');
      if (!tbody) return;
      window._filtered = list || [];
      if (!list || list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-10 text-slate-500">No matching licenses found.</td></tr>';
        renderPager('licPager', 1, 1, 'setLicPage', 0);
        return;
      }
      var pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
      if (licPage > pages) licPage = pages;
      var slice = list.slice((licPage - 1) * PER_PAGE, licPage * PER_PAGE);

      var rows = '';
      for (var i = 0; i < slice.length; i++) {
        var l = slice[i];
        var isActive = l.status === 'ACTIVE';
        var key = l.license_key || '';
        var cust = l.customer_name || '<span class="text-slate-500">Unassigned</span>';
        var phone = l.customer_phone || '-';
        var plan = l.plan || 'Pro';
        var hwidSnippet = l.hwid ? l.hwid.slice(0, 16) + '...' : '';
        var expText = l.expires_at ? new Date(l.expires_at).toLocaleDateString() : '<span class="text-slate-500">On 1st activation</span>';

        rows += '<tr class="table-row-hover transition">';
        rows += '<td class="px-5 py-4"><div class="flex items-center gap-2">';
        rows += '<span class="font-mono font-semibold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-1 rounded-lg">' + key + '</span>';
        rows += '<button data-action="copy" data-key="' + key + '" title="Copy Key" class="text-slate-500 hover:text-white p-1 rounded transition">';
        rows += '<svg class="w-3.5 h-3.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>';
        rows += '</button></div></td>';
        rows += '<td class="px-5 py-4"><div class="font-semibold text-slate-200">' + cust + '</div><div class="text-[11px] text-slate-500 font-mono">' + phone + '</div></td>';
        rows += '<td class="px-5 py-4"><span class="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-md text-[11px] border border-slate-700">' + plan + '</span></td>';

        if (l.hwid) {
          rows += '<td class="px-5 py-4"><div class="flex items-center gap-2"><span class="font-mono text-emerald-400 text-[11px] bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">' + hwidSnippet + '</span><button data-action="unbind_hwid" data-key="' + key + '" title="Unbind HWID (Reset Machine)" class="text-amber-400 hover:text-amber-300 p-1 text-[11px] hover:underline">Reset</button></div></td>';
        } else {
          rows += '<td class="px-5 py-4"><span class="text-slate-500 italic">Unbound (Ready for first PC)</span></td>';
        }

        rows += '<td class="px-5 py-4 text-slate-400 text-[11px]">' + expText + '</td>';
        rows += '<td class="px-5 py-4"><span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ' + (isActive ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20') + '"><span class="w-1.5 h-1.5 rounded-full ' + (isActive ? 'bg-emerald-400 animate-pulse' : 'bg-red-400') + '"></span><span>' + l.status + '</span></span></td>';
        rows += billingCell(key);

        rows += '<td class="px-5 py-4 text-right"><div class="flex items-center justify-end gap-1.5">';
        rows += '<button data-action="money" data-key="' + key + '" class="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-[11px] font-medium transition">Money</button>';
        if (isActive) {
          rows += '<button data-action="revoke" data-key="' + key + '" class="px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg text-[11px] font-medium transition">Revoke</button>';
        } else {
          rows += '<button data-action="activate" data-key="' + key + '" class="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-[11px] font-medium transition">Re-activate</button>';
        }
        rows += '<button data-action="delete" data-key="' + key + '" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-red-400 rounded-lg text-[11px] font-medium transition">Delete</button>';
        rows += '</div></td>';
        rows += '</tr>';
      }

      tbody.innerHTML = rows;
      renderPager('licPager', licPage, pages, 'setLicPage', list.length);
    }

    function billingCell(key) {
      var entry = null;
      try { entry = (typeof billMap !== 'undefined' && billMap[key]) || null; } catch (e) {}
      if (!entry) return '<td class="px-5 py-4"><span class="text-slate-600">—</span></td>';
      var st = entry.payment_status || 'UNPAID';
      var cls = st === 'PAID' ? 'paid-txt' : (st === 'FREE_TOKEN' ? 'text-purple-400 font-bold' : 'unpaid-txt');
      var amt = (entry.amount == null || entry.amount === '') ? '' : ' · ' + entry.amount;
      return '<td class="px-5 py-4"><span class="' + cls + '">' + st + '</span><span class="text-slate-500 text-[11px]">' + amt + '</span></td>';
    }

    function handleTableClick(e) {
      var btn = e.target.closest('button[data-action]');
      if (!btn) return;
      var action = btn.dataset.action;
      var key = btn.dataset.key;
      if (action === 'copy') {
        copyKey(key);
      } else if (action === 'money') {
        if (typeof openMoneyModal === 'function') openMoneyModal(key);
      } else if (action) {
        doAction(action, key);
      }
    }

    async function doAction(action, licenseKey) {
      if (action === 'delete' && !confirm('Are you sure you want to permanently delete this license: ' + licenseKey + '?')) return;
      try {
        var res = await fetch('/api/admin/action', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          },
          body: JSON.stringify({ action: action, licenseKey: licenseKey })
        });
        var data = await res.json();
        if (res.ok && data.success) {
          showToast('Updated ' + licenseKey);
          loadLicenses();
        } else {
          showToast(data.message || 'Action failed', 'error');
        }
      } catch (err) {
        showToast('Action failed: ' + err.message, 'error');
      }
    }

    function openGenerateModal() {
      document.getElementById('generateModal').classList.remove('hidden');
    }

    function closeGenerateModal() {
      document.getElementById('generateModal').classList.add('hidden');
    }

    async function submitGenerate(e) {
      e.preventDefault();
      var name = document.getElementById('genName').value.trim();
      var phone = document.getElementById('genPhone').value.trim();
      var plan = document.getElementById('genPlan').value;
      var qty = parseInt(document.getElementById('genQty').value, 10) || 1;

      try {
        var res = await fetch('/api/admin/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          },
          body: JSON.stringify({
            customer_name: name,
            customer_phone: phone,
            plan: plan,
            quantity: qty
          })
        });
        var data = await res.json();
        if (res.ok && data.success) {
          closeGenerateModal();
          showToast('Generated ' + data.keys.length + ' key(s) successfully!');
          loadLicenses();
        } else {
          showToast(data.message || 'Failed to generate keys', 'error');
        }
      } catch (err) {
        showToast('Failed to generate keys: ' + err.message, 'error');
      }
    }

    if (token) {
      showDashboard();
    }
`;
}
