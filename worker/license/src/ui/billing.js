/** NEW — Per-user money editor modal, opened from the license list. */

export function billingHtml() {
  return `
  <!-- 4. MONEY MODAL -->
  <div id="moneyModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm hidden">
    <div class="glass-card w-full max-w-lg p-6 rounded-2xl border border-white/10 shadow-2xl relative">
      <div class="flex justify-between items-center mb-1 pb-3 border-b border-white/10">
        <div>
          <h3 class="text-lg font-bold text-white">Money Tracker</h3>
          <p class="text-xs text-slate-400" id="moneyWho"></p>
          <p class="text-[11px] text-slate-500 mt-0.5">Fee = what you charge for the month. Save as Unpaid while due, Paid when received.</p>
        </div>
        <button onclick="closeMoneyModal()" class="text-slate-400 hover:text-white text-lg leading-none">&times;</button>
      </div>

      <form id="moneyForm" class="space-y-4 text-xs pt-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Month</label>
            <input type="month" id="mMonth" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-indigo-500">
          </div>
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Monthly fee (BDT)</label>
            <input type="number" id="mAmount" min="0" step="any" placeholder="e.g. 500" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Status</label>
            <select id="mStatus" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-indigo-500">
              <option value="PAID">Paid</option>
              <option value="UNPAID" selected>Unpaid</option>
              <option value="FREE_TOKEN">Free token</option>
            </select>
          </div>
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Method</label>
            <input type="text" id="mMethod" value="Cash" placeholder="bKash, Cash…" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
          </div>
        </div>

        <div>
          <label class="block text-slate-400 font-semibold mb-1">Notes</label>
          <input type="text" id="mNotes" placeholder="TrxID, remarks…" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
        </div>

        <div class="flex justify-between items-center gap-3 border-t border-white/10 pt-4">
          <button type="button" id="mDelete" onclick="delMoneyEntry()" class="px-4 py-2 bg-transparent border border-red-500/40 text-red-400 rounded-xl hover:bg-red-500/10">Delete entry</button>
          <div class="flex gap-3">
            <button type="button" onclick="closeMoneyModal()" class="px-4 py-2 bg-dark-900 text-slate-300 rounded-xl hover:bg-slate-800">Cancel</button>
            <button type="submit" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-600/30">Save</button>
          </div>
        </div>
        <div id="moneyMsg" class="text-xs text-slate-400"></div>
      </form>

      <div class="mt-4 pt-4 border-t border-white/10">
        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">History</div>
        <div id="moneyHistory" class="space-y-1.5 max-h-44 overflow-y-auto custom-scrollbar text-xs"></div>
      </div>
    </div>
  </div>
`;
}
