/** Admin page head: styles, toast container, login screen. Verbatim from original. */

export function headHtml() {
  return `<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <title>Nova Cloud — Enterprise License Authority</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace']
          },
          colors: {
            brand: { 50: '#eef2ff', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca' },
            dark: { 950: '#07090e', 900: '#0c1017', 850: '#111722', 800: '#172033', 700: '#232f48' }
          }
        }
      }
    };
  </script>
  <style>
    body { background-color: #07090e; color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif; }
    .glass-card { background: rgba(17, 23, 34, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glow-effect { box-shadow: 0 0 35px -5px rgba(99, 102, 241, 0.25); }
    .table-row-hover:hover { background-color: rgba(255, 255, 255, 0.03); }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: #0c1017; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #232f48; border-radius: 9999px; }
    .hidden { display: none !important; }
    .paid-txt { color: #34d399; font-weight: 700; }
    .unpaid-txt { color: #f87171; font-weight: 700; }
    /* Sidebar visibility is plain CSS (not variant-dependent): drawer on
       mobile, fixed visible rail on desktop. JS toggles .open on mobile. */
    #sidebar { display: none; }
    #sidebar.open { display: flex; }
    @media (min-width: 768px) {
      #sidebar { display: flex !important; transform: none !important; }
      #sideBackdrop { display: none !important; }
    }
    @media (max-width: 767px) {
      #sidebar { transform: translateX(-100%); transition: transform .25s ease; }
      #sidebar.open { transform: none; }
    }
  </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-indigo-500 selection:text-white">

  <!-- TOAST CONTAINER -->
  <div id="toastContainer" class="fixed top-6 right-6 z-50 flex flex-col gap-2 pointer-events-none"></div>

  <!-- 1. LOGIN SCREEN -->
  <div id="loginView" class="min-h-screen flex items-center justify-center p-4">
    <div class="glass-card glow-effect w-full max-w-md p-8 rounded-2xl border border-white/10 relative overflow-hidden">
      <div class="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none"></div>
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 mb-4 shadow-inner">
          <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
        </div>
        <h2 class="text-2xl font-bold tracking-tight text-white">Nova Cloud Authority</h2>
        <p class="text-sm text-slate-400 mt-1">Enterprise Licensing & Machine Binding Console</p>
      </div>

      <form id="loginForm" class="space-y-4">
        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Admin Security Key</label>
          <div class="relative">
            <input type="password" id="adminPasswordInput" class="w-full bg-dark-900 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition" placeholder="Enter master password..." required autofocus>
          </div>
        </div>

        <div id="loginError" class="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs hidden"></div>

        <button type="submit" id="btnLoginSubmit" class="w-full bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold py-3 px-4 rounded-xl text-sm transition-all shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2">
          <span>Authenticate & Access</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
        </button>
      </form>

      <div class="mt-8 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
        Cloudflare Edge D1 • 100,000 req/day quota
      </div>
    </div>
  </div>
`;
}
