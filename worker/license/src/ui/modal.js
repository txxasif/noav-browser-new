/** Generate-keys modal markup. Verbatim from original. */

export function modalHtml() {
  return `
  <!-- 3. GENERATE KEYS MODAL -->
  <div id="generateModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm hidden">
    <div class="glass-card w-full max-w-lg p-6 rounded-2xl border border-white/10 shadow-2xl relative">
      <div class="flex justify-between items-center mb-5 pb-3 border-b border-white/10">
        <h3 class="text-lg font-bold text-white">Generate License Keys</h3>
        <button onclick="closeGenerateModal()" class="text-slate-400 hover:text-white text-lg leading-none">&times;</button>
      </div>

      <form id="generateForm" class="space-y-4 text-xs">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Customer Name (Optional)</label>
            <input type="text" id="genName" placeholder="e.g. Asif Ahmed" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
          </div>
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Customer Phone (Optional)</label>
            <input type="text" id="genPhone" placeholder="e.g. 017XXXXXXXX" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Plan</label>
            <select id="genPlan" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-indigo-500">
              <option value="3 Days Trial Pass">3 Days Trial / Pass (3 Days)</option>
              <option value="1 Month Pro" selected>1 Month Pro (30 Days)</option>
              <option value="3 Months Pro">3 Months Pro (90 Days)</option>
              <option value="1 Year VIP">1 Year VIP (365 Days)</option>
              <option value="Lifetime Elite">Lifetime Elite</option>
            </select>
          </div>
          <div>
            <label class="block text-slate-400 font-semibold mb-1">Quantity (1 - 100)</label>
            <input type="number" id="genQty" min="1" max="100" value="1" class="w-full bg-dark-900 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-indigo-500" required>
          </div>
        </div>

        <div class="pt-4 flex justify-end gap-3 border-t border-white/10">
          <button type="button" onclick="closeGenerateModal()" class="px-4 py-2 bg-dark-900 text-slate-300 rounded-xl hover:bg-slate-800">Cancel</button>
          <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-600/30">Issue Keys</button>
        </div>
      </form>
    </div>
  </div>
`;
}
