/**
 * Dashboard shell: responsive sidebar + two views (Licenses, Money).
 * Sidebar is a fixed drawer on desktop, slide-over on mobile.
 */

export function dashboardHtml() {
  return `
  <!-- 2. MAIN CONSOLE DASHBOARD -->
  <div id="dashboardView" class="hidden min-h-screen flex flex-col md:flex-row">
    <!-- MOBILE TOPBAR -->
    <div class="md:hidden flex items-center justify-between px-4 py-3 border-b border-white/10 bg-dark-950/90 sticky top-0 z-40">
      <div class="flex items-center gap-2">
        <button onclick="toggleSidebar()" class="text-slate-300 hover:text-white p-2 -ml-2" aria-label="Menu">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
        <span class="font-bold text-white">Nova Cloud</span>
      </div>
      <button onclick="openGenerateModal()" class="bg-indigo-600 text-white text-xs font-semibold px-3 py-2 rounded-xl">+ Keys</button>
    </div>

    <!-- SIDEBAR BACKDROP (mobile) -->
    <div id="sideBackdrop" onclick="toggleSidebar(false)" class="hidden fixed inset-0 bg-black/60 z-40 md:hidden"></div>

    <!-- SIDEBAR -->
    <aside id="sidebar" class="fixed md:sticky top-0 z-50 md:z-auto h-screen w-64 shrink-0 bg-dark-950/95 border-r border-white/10 flex-col p-5 gap-6 transition-transform">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white font-black text-base shadow-lg shadow-indigo-500/25">N</div>
        <div>
          <h1 class="text-base font-bold text-white tracking-tight">Nova Cloud</h1>
          <p class="text-xs text-slate-400">Global License Hub</p>
        </div>
      </div>

      <nav class="flex flex-col gap-1 text-sm font-semibold">
        <button onclick="showView('licenses')" id="navLicenses" class="text-left px-4 py-2.5 rounded-xl transition flex items-center gap-3">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a3 3 0 11-3-3m3 3a3 3 0 10-3 3m3-3L4 18l3 3 11-11z" transform="rotate(90 12 12)"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.6 2A9 9 0 1112 3a9 9 0 018.6 9z"/></svg>
          Licenses
        </button>
        <button onclick="showView('money')" id="navMoney" class="text-left px-4 py-2.5 rounded-xl transition flex items-center gap-3">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.7 0-3 .9-3 2s1.3 2 3 2 3 .9 3 2-1.3 2-3 2m0-8c1.1 0 2.1.4 2.6 1M12 8V7m0 10v1m9-8a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Money Dashboard
        </button>
      </nav>

      <div class="mt-auto flex flex-col gap-2">
        <button onclick="openGenerateModal()" class="hidden md:flex bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition items-center justify-center gap-2 shadow-lg shadow-indigo-600/25">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          <span>Generate Keys</span>
        </button>
        <button onclick="logout()" class="text-slate-400 hover:text-white hover:bg-white/5 border border-slate-800 text-xs font-semibold px-3 py-2.5 rounded-xl transition">
          Sign Out
        </button>
        <p class="text-[10px] text-slate-600 text-center">v0.2 D1 · Edge Console</p>
      </div>
    </aside>

    <!-- CONTENT -->
    <div class="flex-1 min-w-0">
    <!-- LICENSES VIEW -->
    <div id="viewLicenses">
    <main class="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-8 flex-1 w-full space-y-6">
    <div id="licenseSection" class="space-y-6">
      <!-- ANALYTICS CARDS -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5">
          <div class="text-xs font-medium uppercase tracking-wider text-slate-400 mb-1">Total Licenses</div>
          <div class="text-2xl md:text-3xl font-extrabold text-white font-mono" id="statTotal">0</div>
          <div class="text-xs text-slate-500 mt-1">Issued in database</div>
        </div>

        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5">
          <div class="text-xs font-medium uppercase tracking-wider text-emerald-400 mb-1">Active</div>
          <div class="text-2xl md:text-3xl font-extrabold text-emerald-400 font-mono" id="statActive">0</div>
          <div class="text-xs text-slate-500 mt-1">Validated & running</div>
        </div>

        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5">
          <div class="text-xs font-medium uppercase tracking-wider text-purple-400 mb-1">Trials</div>
          <div class="text-2xl md:text-3xl font-extrabold text-purple-400 font-mono" id="statTrials">0</div>
          <div class="text-xs text-slate-500 mt-1">3-Day hardware trials</div>
        </div>

        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5">
          <div class="text-xs font-medium uppercase tracking-wider text-red-400 mb-1">Revoked</div>
          <div class="text-2xl md:text-3xl font-extrabold text-red-400 font-mono" id="statRevoked">0</div>
          <div class="text-xs text-slate-500 mt-1">Blocked access</div>
        </div>
      </div>

      <!-- FILTER & SEARCH BAR -->
      <div class="glass-card p-4 rounded-2xl flex flex-col md:flex-row md:items-center gap-3">
        <div class="relative w-full md:w-72">
          <svg class="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" id="searchInput" oninput="applyFilters()" placeholder="Search key, customer, phone, HWID..." class="w-full bg-dark-900/90 border border-slate-700/60 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
        </div>

        <div class="flex items-center gap-2 md:gap-3 flex-wrap">
          <select id="statusFilter" onchange="applyFilters()" class="bg-dark-900 border border-slate-700/60 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500">
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">Active Only</option>
            <option value="REVOKED">Revoked Only</option>
          </select>
          <input type="month" id="billMonthFilter" onchange="loadBilling()" title="Billing month" class="bg-dark-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500">
          <select id="payFilter" onchange="applyFilters()" title="Payment status" class="bg-dark-900 border border-slate-700/60 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500">
            <option value="ALL">All Payments</option>
            <option value="PAID">Paid</option>
            <option value="UNPAID">Unpaid</option>
            <option value="FREE_TOKEN">Free token</option>
            <option value="NONE">Not recorded</option>
          </select>
          <button onclick="loadLicenses()" class="bg-dark-900 hover:bg-slate-800 border border-slate-700/60 text-slate-300 hover:text-white px-4 py-2.5 rounded-xl text-xs font-medium transition flex items-center gap-2">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <!-- TABLE CARD -->
      <div class="glass-card rounded-2xl overflow-hidden border border-white/5">
        <div class="overflow-x-auto custom-scrollbar">
          <table class="w-full text-left text-xs min-w-[900px]">
            <thead class="bg-dark-900/90 text-slate-400 uppercase tracking-wider font-semibold border-b border-white/5">
              <tr>
                <th class="px-5 py-3.5">License Key</th>
                <th class="px-5 py-3.5">Customer / Phone</th>
                <th class="px-5 py-3.5">Plan</th>
                <th class="px-5 py-3.5">HWID Machine Binding</th>
                <th class="px-5 py-3.5">Expires At</th>
                <th class="px-5 py-3.5">Status</th>
                <th class="px-5 py-3.5">Billing <span id="billMonthLabel" class="text-slate-500 normal-case"></span></th>
                <th class="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody id="licenseTableBody" class="divide-y divide-white/5 font-medium">
              <tr><td colspan="8" class="text-center py-10 text-slate-500">Loading licenses from Cloudflare D1...</td></tr>
            </tbody>
          </table>
        </div>
        <div id="licPager" class="flex items-center justify-between px-5 py-3 border-t border-white/5 text-xs text-slate-400"></div>
      </div>
    </div>
    </main>
    </div>
`;
}
