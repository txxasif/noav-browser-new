/**
 * Meta Creator — Node.js Backend Server (Nova Browser Parity)
 * Dedicated Meta Account Creation Engine & Nova API Integration
 *
 * Thin entry: shared state lives in server/context.js, route groups in
 * server/routes-*.js (dispatched below in the original order).
 */

const http = require('http');
const ctx = require('./server/context');
const handleLicense = require('./server/routes-license');
const handleUpdates = require('./server/routes-updates');
const handleMeta = require('./server/routes-meta');
const handleTg = require('./server/routes-tg');
const handleDiag = require('./server/routes-diag');
const handleStatic = require('./server/routes-static');

const PORT = ctx.PORT;

const server = http.createServer((req, res) => {
  const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = urlObj.pathname;

  // Pick the engine slot ONCE per request, from the path. This MUST be here and
  // not inside individual route blocks: a status read that ran before its own
  // start-block had set it would read whichever slot the PREVIOUS request left
  // active — so /api/meta-insta/status reported TG's worker as "running".
  ctx.setEngine(pathname.indexOf('/api/tg/') === 0 ? 'tg' : 'metainsta');

  if (req.method !== 'GET' || (pathname.startsWith('/api/') && !pathname.endsWith('/status') && !pathname.endsWith('/events') && !pathname.endsWith('/accounts'))) {
    console.log(`[HTTP] ${req.method} ${pathname}`);
  }

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }


  if (res.headersSent) return;
  if (handleLicense(req, res, urlObj, pathname, ctx)) return;
  if (res.headersSent) return;
  if (handleUpdates(req, res, urlObj, pathname, ctx)) return;
  if (res.headersSent) return;
  if (handleMeta(req, res, urlObj, pathname, ctx)) return;
  if (res.headersSent) return;
  if (handleTg(req, res, urlObj, pathname, ctx)) return;
  if (res.headersSent) return;
  if (handleDiag(req, res, urlObj, pathname, ctx)) return;
  if (res.headersSent) return;
  if (handleStatic(req, res, urlObj, pathname, ctx)) return;
});

// Graceful shutdown
function handleShutdown() {
  console.log('\n[MetaCreator] Shutting down server...');
  for (const s of Object.values(ctx.engineSlots || {})) {
    if (s && s.proc) {
      try { ctx.killProcessGroup(s.proc, 'SIGKILL'); } catch (e) {}
      s.proc = null;
    }
  }
  server.close(() => {
    process.exit(0);
  });
  setTimeout(() => process.exit(0), 1000);
}

process.on('SIGINT', handleShutdown);
process.on('SIGTERM', handleShutdown);

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.warn(`[MetaCreator] Port ${PORT} is already in use. Another Meta Creator instance may already be running.`);
    process.exit(0);
  } else {
    console.error('[MetaCreator] Server error:', err);
    process.exit(1);
  }
});

// Kill engine processes ORPHANED by a previous server (crash/restart). A
// detached worker keeps its Telethon session files locked and the next engine
// dies with "database is locked" (observed 2026-09-28: an orphan held
// tg_1.session + tg_3.session across a server restart).
function killOrphanEngines() {
  try {
    if (process.platform === 'win32') return; // POSIX ps not available on Windows
    const out = ctx.execSync('ps -eo pid=,ppid=,args=', { encoding: 'utf8' });
    const rows = [];
    for (const line of out.split('\n')) {
      const m = line.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/);
      if (m) rows.push({ pid: Number(m[1]), ppid: Number(m[2]), args: m[3] });
    }
    const live = new Set(rows.map(r => r.pid));
    // Only REAL engines: argv[0] is a python interpreter AND argv names worker.py.
    const isEngine = a => /python/i.test(a) && /worker\.py\b/.test(a);
    // A worker is only legitimate if its parent is a LIVE server.js. Detached
    // workers get reparented to `systemd --user` (NOT pid 1) when the server
    // dies, so "any live parent" is wrong — the parent must be a node server.
    const isServer = a => /\bnode\b/i.test(a) && /server\.js/.test(a);
    const byPid = {};
    for (const r of rows) byPid[r.pid] = r;
    let killed = 0;
    for (const r of rows) {
      if (!isEngine(r.args)) continue;
      if (r.ppid === process.pid) continue;                 // ours
      const parent = byPid[r.ppid];
      if (parent && isServer(parent.args)) continue;        // another live server owns it
      try {
        try { process.kill(-r.pid, 'SIGKILL'); }            // whole group
        catch (e) { process.kill(r.pid, 'SIGKILL'); }
        killed++;
        console.log(`[MetaCreator] Reaped orphan engine pid=${r.pid} (parent=${r.ppid})`);
      } catch (e) {}
    }
    if (killed) console.log(`[MetaCreator] ${killed} orphan engine process(es) reaped.`);
  } catch (e) {}
}

function resetStaleTgAccounts() {
  try {
    const f = ctx.path.join(ctx.ROOT_DIR, 'data', 'tg_accounts.json');
    if (!ctx.fs.existsSync(f)) return;
    const raw = JSON.parse(ctx.fs.readFileSync(f, 'utf8'));
    let changed = false;
    const list = Array.isArray(raw) ? raw : (raw.accounts || []);
    for (const a of list) {
      if (a.status === 'busy') {
        a.status = 'idle';
        a.busy_bot = null;
        a.leased_at = null;
        changed = true;
      }
    }
    if (changed) {
      ctx.fs.writeFileSync(f, JSON.stringify(raw, null, 2), 'utf8');
      console.log('[MetaCreator] Auto-healed stale busy TG account lease(s) to idle.');
    }
  } catch (e) {}
}

server.listen(PORT, '0.0.0.0', () => {
  killOrphanEngines();
  resetStaleTgAccounts();
  console.log(`[MetaCreator] Nova Meta UI active on http://localhost:${PORT}`);
  console.log(`[MetaCreator] Python interpreter: ${ctx.PYTHON_BIN}`);
});
