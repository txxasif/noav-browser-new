/**
 * Money dashboard view: KPIs, donut, trend, fast inline ledger with pager.
 * R&D notes: inline editing beats modals for monthly bulk entry; Enter saves
 * and advances; last month's amount pre-fills as placeholder; bulk marks all.
 */

export function moneyHtml() {
  return `
    <!-- MONEY VIEW -->
    <div id="viewMoney" class="hidden">
    <main class="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-8 w-full space-y-6">
      <!-- HOW ENTRY WORKS -->
      <div class="glass-card p-4 md:p-5 rounded-2xl border border-indigo-500/25 flex flex-col md:flex-row md:items-center gap-2 md:gap-6 text-xs md:text-sm">
        <span class="font-bold text-white whitespace-nowrap">How entry works</span>
        <span class="text-slate-300"><b class="text-white">1.</b> Pick the month.</span>
        <span class="text-slate-300"><b class="text-white">2.</b> Tap a user to flip <b class="text-emerald-400">Paid</b> ↔ <b class="text-red-400">Unpaid</b> — saves instantly.</span>
        <span class="text-slate-300"><b class="text-white">3.</b> Fee, method, notes live under <b class="text-white">Edit</b>.</span>
      </div>
      <!-- MONEY KPI ROW -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5 relative overflow-hidden">
          <div class="absolute -top-10 -right-10 w-32 h-32 bg-emerald-500/15 rounded-full blur-2xl pointer-events-none"></div>
          <div class="text-xs font-medium uppercase tracking-wider text-emerald-400 mb-1">Collected <span id="kpiMonth" class="text-slate-500"></span></div>
          <div class="text-2xl md:text-3xl font-extrabold text-emerald-400 font-mono" id="kpiCollected">0</div>
          <div class="text-xs text-slate-500 mt-1">BDT marked Paid</div>
        </div>

        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5 relative overflow-hidden">
          <div class="absolute -top-10 -right-10 w-32 h-32 bg-red-500/15 rounded-full blur-2xl pointer-events-none"></div>
          <div class="text-xs font-medium uppercase tracking-wider text-red-400 mb-1">Outstanding dues</div>
          <div class="text-2xl md:text-3xl font-extrabold text-red-400 font-mono" id="kpiOutstanding">0</div>
          <div class="text-xs text-slate-500 mt-1"><span id="kpiUnpaidCount">0</span> users Unpaid · <span id="kpiUnrecorded">0</span> not entered</div>
        </div>

        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5 flex items-center gap-4">
          <div id="donutWrap" class="shrink-0"></div>
          <div>
            <div class="text-xs font-medium uppercase tracking-wider text-slate-400 mb-1">Collection rate</div>
            <div class="text-xl md:text-2xl font-extrabold text-white font-mono" id="kpiRate">–</div>
            <div class="text-xs text-slate-500 mt-1">paid vs recorded dues</div>
          </div>
        </div>

        <div class="glass-card p-4 md:p-5 rounded-2xl border border-white/5">
          <div class="text-xs font-medium uppercase tracking-wider text-slate-400 mb-2">Last 6 months</div>
          <div id="trendBars" class="flex items-end gap-2 h-16"></div>
          <div id="trendLabels" class="flex gap-2 mt-1"></div>
        </div>
      </div>

      <!-- MONEY FILTER + BULK BAR -->
      <div class="glass-card p-4 rounded-2xl flex flex-col md:flex-row md:items-center gap-3">
        <div class="relative w-full md:w-72">
          <svg class="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" id="moneySearch" oninput="renderLedger()" placeholder="Search user, key..." class="w-full bg-dark-900/90 border border-slate-700/60 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500">
        </div>
        <div class="flex items-center gap-2 md:gap-3 flex-wrap">
          <input type="month" id="moneyMonth" onchange="loadMoney()" title="Billing month" class="bg-dark-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-emerald-500">
          <select id="moneyStatus" onchange="renderLedger()" title="Payment status" class="bg-dark-900 border border-slate-700/60 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none focus:border-emerald-500">
            <option value="ALL">All</option>
            <option value="PAID">Paid</option>
            <option value="UNPAID">Unpaid</option>
            <option value="FREE_TOKEN">Free token</option>
            <option value="NONE">Not recorded</option>
          </select>
          <button onclick="bulkMarkPaid()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-xl text-xs font-semibold transition">Mark all listed paid</button>
          <span id="moneyMsg" class="text-xs text-slate-400"></span>
        </div>
      </div>

      <!-- LEDGER TABLE -->
      <div class="glass-card rounded-2xl overflow-hidden border border-white/5">
        <div class="overflow-x-auto custom-scrollbar">
          <table class="w-full text-left text-xs min-w-[640px]">
            <thead class="bg-dark-900/90 text-slate-400 uppercase tracking-wider font-semibold border-b border-white/5">
              <tr>
                <th class="px-5 py-3.5">User</th>
                <th class="px-5 py-3.5">Plan</th>
                <th class="px-5 py-3.5">Payment</th>
                <th class="px-5 py-3.5">Fee</th>
                <th class="px-5 py-3.5 text-right">Edit</th>
              </tr>
            </thead>
            <tbody id="ledgerBody" class="divide-y divide-white/5 font-medium">
              <tr><td colspan="5" class="text-center py-10 text-slate-500">Loading ledger…</td></tr>
            </tbody>
          </table>
        </div>
        <div id="ledgerPager" class="flex items-center justify-between px-5 py-3 border-t border-white/5 text-xs text-slate-400"></div>
      </div>

      <p class="text-xs text-slate-500">Tap a user's button to flip Paid ↔ Unpaid — it saves instantly. Fee/method/notes live under <b>Edit</b>. <b>Mark all listed paid</b> settles every filtered row at once.</p>
    </main>
    </div>
    </div>
`;
}
