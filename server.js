/**
 * Meta Creator — Node.js Backend Server (Nova Browser Parity)
 * Dedicated Meta Account Creation Engine & Nova API Integration
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { spawn, execSync } = require('child_process');

// Snapshot the user's account data before ANY destructive operation. Cheap
// (store.db is ~256 KB) and keeps the last few snapshots so a mis-click or a
// stray POST can never silently destroy created accounts again.
function backupUserData(reason) {
  try {
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const dir = path.join(ROOT_DIR, 'backups', `backup_${ts}_${reason}`);
    fs.mkdirSync(dir, { recursive: true });
    const rels = ['data/store.db', 'data/accounts.json', 'data/accounts.csv', 'accounts.txt'];
    let copied = 0;
    for (const rel of rels) {
      const src = path.join(ROOT_DIR, rel);
      if (fs.existsSync(src)) { fs.copyFileSync(src, path.join(dir, path.basename(rel))); copied++; }
    }
    // Keep the newest 20 snapshots.
    try {
      const root = path.join(ROOT_DIR, 'backups');
      const all = fs.readdirSync(root).filter(n => n.startsWith('backup_')).sort();
      for (const old of all.slice(0, Math.max(0, all.length - 20))) {
        fs.rmSync(path.join(root, old), { recursive: true, force: true });
      }
    } catch (e) {}
    return copied ? dir : null;
  } catch (e) {
    return null;
  }
}

// Global password + misc dashboard settings, persisted so they survive restarts
// (data/settings.json). The password is only ever sent to the worker via env.
function settingsFilePath() {
  return path.join(ROOT_DIR, 'data', 'settings.json');
}
function readSettings() {
  try {
    const p = settingsFilePath();
    if (!fs.existsSync(p)) return {};
    const j = JSON.parse(fs.readFileSync(p, 'utf-8'));
    return (j && typeof j === 'object') ? j : {};
  } catch (e) { return {}; }
}
function writeSettings(patch) {
  const cur = readSettings();
  const next = Object.assign({}, cur, patch || {});
  const p = settingsFilePath();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = `${p}.tmp.${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(next, null, 2), 'utf-8');
  try {
    fs.renameSync(tmp, p);
  } catch (e) {
    // Windows can hold the destination briefly (AV/indexer) — write directly.
    try { fs.writeFileSync(p, JSON.stringify(next, null, 2), 'utf-8'); } catch (e2) {}
    try { fs.unlinkSync(tmp); } catch (e3) {}
  }
  return next;
}
function storedGlobalPassword() {
  return String(readSettings().globalPassword || '').trim().slice(0, 128);
}

const PORT = parseInt(process.env.PORT || '3070', 10);
const ROOT_DIR = __dirname;
// Cookie exports written by the Python engine: <ROOT>/cookies/cookies_<id>.txt
// (JSON array, Nova parity: served per-account with count, like /api/export-cookies).
function cookieFileFor(id) {
  const safe = String(id == null ? '' : id).replace(/[^A-Za-z0-9_@.\-]/g, '');
  if (!safe) return null;
  return path.join(ROOT_DIR, 'cookies', `cookies_${safe}.txt`);
}
function resolvePublicDir() {
  const candidates = [
    path.join(__dirname, 'public'),
    path.join(process.cwd(), 'public'),
    path.resolve('public'),
    path.join(path.dirname(process.execPath), 'public'),
  ];
  for (const dir of candidates) {
    try {
      if (fs.existsSync(path.join(dir, 'index.html'))) {
        return dir;
      }
    } catch (e) {}
  }
  return path.join(__dirname, 'public');
}
const PUBLIC_DIR = resolvePublicDir();
const DATA_DIR = path.join(ROOT_DIR, 'data');
const ACCOUNTS_JSON = path.join(DATA_DIR, 'accounts.json');
const ACCOUNTS_CSV = path.join(DATA_DIR, 'accounts.csv');
const ACCOUNTS_TXT = path.join(ROOT_DIR, 'accounts.txt');

// Detect best Python binary
function getPythonBin() {
  if (process.env.PYTHON_BIN && fs.existsSync(process.env.PYTHON_BIN)) return process.env.PYTHON_BIN;
  // Windows bundled runtime (_internal or runtime/python)
  const winInternal = path.join(ROOT_DIR, '_internal', 'python.exe');
  if (fs.existsSync(winInternal)) return winInternal;
  const winInternalW = path.join(ROOT_DIR, '_internal', 'pythonw.exe');
  if (fs.existsSync(winInternalW)) return winInternalW;
  const winRuntime = path.join(ROOT_DIR, 'runtime', 'python', 'python.exe');
  if (fs.existsSync(winRuntime)) return winRuntime;
  const localVenv = path.join(ROOT_DIR, '.venv', 'bin', 'python');
  if (fs.existsSync(localVenv)) return localVenv;
  const metaAiVenv = path.join(ROOT_DIR, '..', 'meta_auto_ai', '.venv', 'bin', 'python');
  if (fs.existsSync(metaAiVenv)) return metaAiVenv;
  const instaVenv = path.join(ROOT_DIR, '..', 'InstaAuto-Linux', '.venv', 'bin', 'python');
  if (fs.existsSync(instaVenv)) return instaVenv;
  return process.platform === 'win32' ? 'python.exe' : 'python3';
}

const PYTHON_BIN = getPythonBin();

// Send JSON with gzip when the client accepts it. /api/meta-insta/accounts
// is ~1.5 MB with 812 accounts (fetched every 10s poll) — gzip cuts it to
// ~150-200 KB with zero frontend changes.
function sendJson(req, res, obj, statusCode) {
  try {
    const body = Buffer.from(JSON.stringify(obj));
    const ae = String((req && req.headers && req.headers['accept-encoding']) || '');
    if (ae.includes('gzip') && body.length > 1024) {
      try {
        const gz = zlib.gzipSync(body);
        res.writeHead(statusCode || 200, { 'Content-Type': 'application/json', 'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding' });
        res.end(gz);
        return;
      } catch (e) {}
    }
    res.writeHead(statusCode || 200, { 'Content-Type': 'application/json' });
    res.end(body);
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
  }
}

const LicenseManager = require('./core/licenseManager');
const licenseMgr = new LicenseManager();
const updateManager = require('./core/updateManager');
const licenseConfig = require('./core/licenseConfig');

// Clean up stale update files if any
try {
  updateManager.cleanupStaleUpdateFiles(process.pkg ? process.execPath : null);
} catch (e) {}

let activeLoopProcess = null;
let currentLoopConfig = { concurrency: 1, headless: true, target: 0, delay: 4, mail: 'mailtd', captcha: 'extension', mode: 'meta' };
const sseClients = new Set();

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const recentLogs = [];
const MAX_RECENT_LOGS = 150;

// Coalesce high-volume events (log / slot_event) into one SSE frame every
// ~80 ms. With 10 slots the worker emits hundreds of lines/sec; one write per
// line made the browser dispatch hundreds of EventSource messages per second.
const sseBatch = [];
let sseBatchTimer = null;
const SSE_BATCH_MS = 80;

function writeSse(payload) {
  for (const client of sseClients) {
    try {
      client.write(payload);
    } catch (err) {
      sseClients.delete(client);
    }
  }
}

function flushSseBatch() {
  sseBatchTimer = null;
  if (!sseBatch.length) return;
  const items = sseBatch.splice(0, sseBatch.length);
  const payload = items.length === 1
    ? `data: ${JSON.stringify(items[0])}\n\n`
    : `data: ${JSON.stringify({ type: 'batch', items })}\n\n`;
  writeSse(payload);
}

function broadcastEvent(data) {
  if (data.type === 'log' || data.type === 'slot_event' || data.type === 'account_created' || data.type === 'status') {
    recentLogs.push(data);
    if (recentLogs.length > MAX_RECENT_LOGS) recentLogs.shift();
  }
  if (data.type === 'log' || data.type === 'slot_event') {
    sseBatch.push(data);
    if (!sseBatchTimer) sseBatchTimer = setTimeout(flushSseBatch, SSE_BATCH_MS);
    return;
  }
  // Control events (status, account_created, loop_*) flush pending logs first
  // so ordering is preserved, then go out immediately.
  if (sseBatchTimer) {
    clearTimeout(sseBatchTimer);
    sseBatchTimer = null;
    flushSseBatch();
  }
  writeSse(`data: ${JSON.stringify(data)}\n\n`);
}

// accounts.json is read by both /status and /accounts on every poll cycle.
// Cache the parsed array keyed by (mtime,size) so a poll reads it once and
// only re-parses after the engine actually writes new accounts.
let _accountsCache = { mtimeMs: -1, size: -1, data: null };
function getAccounts() {
  let st;
  try {
    st = fs.statSync(ACCOUNTS_JSON);
  } catch (e) {
    _accountsCache = { mtimeMs: -1, size: -1, data: null };
    return [];
  }
  if (_accountsCache.data && _accountsCache.mtimeMs === st.mtimeMs && _accountsCache.size === st.size) {
    return _accountsCache.data;
  }
  try {
    const raw = fs.readFileSync(ACCOUNTS_JSON, 'utf-8');
    const data = JSON.parse(raw);
    _accountsCache = { mtimeMs: st.mtimeMs, size: st.size, data };
    return data;
  } catch (e) {
    return [];
  }
}

function storeDbExists() {
  try { return fs.existsSync(path.join(DATA_DIR, 'store.db')); } catch (e) { return false; }
}

/**
 * Run a Python snippet with an argv array (no shell → safe for install paths
 * containing spaces, e.g. "C:\Users\John Smith\MetaCreator"). Never throws and
 * never blocks the event loop. Resolves { ok, code, error }.
 */
function runPython(code, timeoutMs = 30000) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(PYTHON_BIN, ['-c', code], {
        cwd: ROOT_DIR,
        windowsHide: true,
        stdio: ['ignore', 'ignore', 'pipe'],
      });
    } catch (e) {
      resolve({ ok: false, code: -1, error: e.message });
      return;
    }
    let errText = '';
    let settled = false;
    const done = (result) => { if (!settled) { settled = true; resolve(result); } };
    const timer = setTimeout(() => {
      try { child.kill('SIGKILL'); } catch (e) {}
      done({ ok: false, code: -1, error: `python timed out after ${timeoutMs}ms` });
    }, timeoutMs);
    if (child.stderr) child.stderr.on('data', (d) => { errText += d.toString('utf-8'); });
    child.on('error', (e) => { clearTimeout(timer); done({ ok: false, code: -1, error: e.message }); });
    child.on('close', (code) => {
      clearTimeout(timer);
      done({ ok: code === 0, code, error: errText.trim().slice(-500) });
    });
  });
}

// Dedupe concurrent sync requests (status + accounts can fire together).
let syncInFlight = null;
function syncFilesFromStore() {
  if (syncInFlight) return syncInFlight;
  syncInFlight = runPython('import store; store.sync_files()').then((r) => {
    syncInFlight = null;
    if (!r.ok) {
      console.warn(`[MetaCreator] accounts.json/csv/txt rebuild from store.db failed: ${r.error}`);
    }
    return r.ok;
  });
  return syncInFlight;
}

/**
 * Best-effort account load: accounts.json first, and when it is empty/missing
 * (fresh install, interrupted write, update over an old folder) rebuild it from
 * SQLite store.db before answering — so stored accounts restore on first load
 * instead of only appearing after mining starts.
 */
async function loadAccounts() {
  let accounts = getAccounts();
  if (accounts.length === 0 && storeDbExists()) {
    await syncFilesFromStore();
    accounts = getAccounts();
  }
  return accounts;
}

function killProcessGroup(proc, signal = 'SIGTERM') {
  if (!proc || !proc.pid) return;
  if (process.platform === 'win32') {
    try {
      execSync(`taskkill /pid ${proc.pid} /T /F`, { stdio: 'ignore' });
    } catch (e) {}
    return;
  }
  try {
    process.kill(-proc.pid, signal);
  } catch (e) {
    try {
      proc.kill(signal);
    } catch (e2) {}
  }
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.csv': 'text/csv; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8'
};

// Static asset cache (gzip + ETag), keyed by absolute path.
const STATIC_CACHE = new Map();

const server = http.createServer((req, res) => {
  const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = urlObj.pathname;

  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // =========================================================================
  // License Management APIs (/api/license/*)
  // =========================================================================

  // 1. GET /api/license/status
  if (pathname === '/api/license/status' && req.method === 'GET') {
    const force = urlObj.searchParams.get('force') === 'true';
    licenseMgr.validateOrActivateLicense(null, force).then(result => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch(err => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    });
    return;
  }

  // 2. POST /api/license/activate
  if (pathname === '/api/license/activate' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body || '{}');
        const key = (payload.licenseKey || payload.key || '').trim();
        if (!key) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', message: 'License key is required.' }));
          return;
        }
        const result = await licenseMgr.validateOrActivateLicense(key, true);
        res.writeHead(result.isValid ? 200 : 400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
      }
    });
    return;
  }

  // 3. POST /api/license/validate
  if (pathname === '/api/license/validate' && req.method === 'POST') {
    licenseMgr.validateOrActivateLicense(null, true).then(result => {
      res.writeHead(result.isValid ? 200 : 400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch(err => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    });
    return;
  }

  // 4. POST /api/license/deactivate
  if (pathname === '/api/license/deactivate' && req.method === 'POST') {
    licenseMgr.deactivateLicense().then(result => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch(err => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    });
    return;
  }

  // =========================================================================
  // Self-Update APIs (/api/updates/*) — Nova Parity
  // =========================================================================

  // 1. GET /api/updates/status
  if (pathname === '/api/updates/status' && req.method === 'GET') {
    if (licenseConfig.updates && licenseConfig.updates.enabled === false) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', currentVersion: licenseConfig.app.version, updateAvailable: false, disabled: true }));
      return;
    }
    const force = urlObj.searchParams.get('force') === 'true';
    const now = Date.now();
    if (force || !global.__metaUpdateStatus || now - (global.__metaUpdateStatus.at || 0) > (licenseConfig.updates.checkIntervalMs || 60000)) {
      updateManager.checkForUpdates().then(result => {
        global.__metaUpdateStatus = { at: now, result };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'SUCCESS', ...result }));
      }).catch(e => {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
      });
    } else {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', ...global.__metaUpdateStatus.result }));
    }
    return;
  }

  // 2. POST /api/updates/download
  if (pathname === '/api/updates/download' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body || '{}');
        const update = data.update;
        if (!update || !update.url || !update.sha256 || !update.version) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Update descriptor required (check status first).' }));
          return;
        }
        const out = updateManager.startDownload(update);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'SUCCESS', ...out }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
      }
    });
    return;
  }

  // 3. GET /api/updates/download/progress
  if (pathname === '/api/updates/download/progress' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', ...updateManager.getDownloadProgress() }));
    return;
  }

  // 4. POST /api/updates/install
  if (pathname === '/api/updates/install' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const data = JSON.parse(body || '{}');
        const out = updateManager.installStagedUpdate(data.version);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'SUCCESS', ...out }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
      }
    });
    return;
  }

  // 5. POST /api/updates/apply
  if (pathname === '/api/updates/apply' && req.method === 'POST') {
    try {
      const out = updateManager.applyStagedUpdate();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', ...out, note: 'Server is exiting to apply the update.' }));
      setTimeout(() => process.exit(0), 800);
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
    }
    return;
  }

  // 6. GET /api/updates/rollback-available
  if (pathname === '/api/updates/rollback-available' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', available: updateManager.rollbackAvailable() }));
    return;
  }

  // 7. POST /api/updates/rollback
  if (pathname === '/api/updates/rollback' && req.method === 'POST') {
    try {
      const out = updateManager.applyRollback();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', ...out, note: 'Server is exiting to roll back.' }));
      setTimeout(() => process.exit(0), 800);
    } catch (e) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
    }
    return;
  }

  // =========================================================================
  // Nova Browser Meta APIs (/api/meta-insta/*)
  // =========================================================================

  // 1. GET /api/meta-insta/status (also /api/status)
  if ((pathname === '/api/meta-insta/status' || pathname === '/api/status') && req.method === 'GET') {
    (async () => {
      const accounts = await loadAccounts();
      sendJson(req, res, {
        status: 'SUCCESS',
        tool: 'meta-insta',
        running: !!activeLoopProcess,
        engineOk: true,
        concurrency: currentLoopConfig.concurrency,
        total_accounts: accounts.length,
        created: accounts.length,
        mode: currentLoopConfig.mode,
        state: activeLoopProcess ? 'RUNNING' : 'IDLE'
      });
    })();
    return;
  }

  // 2. GET /api/meta-insta/accounts (also /api/accounts)
  if ((pathname === '/api/meta-insta/accounts' || pathname === '/api/accounts') && req.method === 'GET') {
    (async () => {
      const accounts = await loadAccounts();
      sendJson(req, res, {
        status: 'SUCCESS',
        accounts: accounts
      });
    })();
    return;
  }

  // 2b. GET /api/meta-insta/cookies?id= — per-account saved-cookie export (Nova parity)
  if (pathname === '/api/meta-insta/cookies' && req.method === 'GET') {
    (async () => {
      const id = String(urlObj.searchParams.get('id') || '').trim();
      if (!id) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'query param id is required' }));
        return;
      }
      const accounts = await loadAccounts();
      const acc = accounts.find(a => String(a.id) === id);
      if (!acc) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'account not found' }));
        return;
      }
      let cookies = [];
      try {
        const f = cookieFileFor(acc.id);
        if (f && fs.existsSync(f)) {
          const parsed = JSON.parse(fs.readFileSync(f, 'utf-8'));
          if (Array.isArray(parsed)) cookies = parsed;
        }
      } catch (e) { cookies = []; }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'SUCCESS',
        id: acc.id,
        username: acc.instagram_username || acc.username || '',
        count: cookies.length,
        cookies: cookies
      }));
    })();
    return;
  }

  // 2c. GET /api/meta-insta/export-combo?kind=meta|ig — bulk combo download.
  // meta: `email|password` lines only, nothing else.
  // ig: `username|password|name=value; ...` lines (Nova combo shape).
  if (pathname === '/api/meta-insta/export-combo' && req.method === 'GET') {
    (async () => {
      const kind = (urlObj.searchParams.get('kind') || '').trim().toLowerCase() === 'ig' ? 'ig' : 'meta';
      const accounts = await loadAccounts();
      const isIg = (a) => String((a && a.status) || '') !== 'MetaCreated';
      const lines = [];
      for (const a of accounts) {
        if (kind === 'ig' ? !isIg(a) : isIg(a)) continue;
        if (kind === 'meta') {
          if (!a.email || !a.password) continue;
          lines.push(`${a.email}|${a.password}`);
        } else {
          const u = a.instagram_username || a.username || '';
          if (!u || !a.password) continue;
          let header = '';
          try {
            const f = cookieFileFor(a.id);
            if (f && fs.existsSync(f)) {
              const parsed = JSON.parse(fs.readFileSync(f, 'utf-8'));
              if (Array.isArray(parsed)) {
                header = parsed.filter((c) => c && c.name).map((c) => `${c.name}=${c.value == null ? '' : c.value}`).join('; ');
              }
            }
          } catch (e) {}
          lines.push(`${u}|${a.password}|${header}`);
        }
      }
      const fname = kind === 'ig' ? 'ig_combo.txt' : 'meta_combo.txt';
      res.writeHead(200, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': `attachment; filename="${fname}"`
      });
      res.end(lines.join('\n'));
    })();
    return;
  }

  // 2d. GET/POST /api/meta-insta/settings — dashboard settings (global password)
  if (pathname === '/api/meta-insta/settings') {
    if (req.method === 'GET') {
      const s = readSettings();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', globalPassword: String(s.globalPassword || '') }));
      return;
    }
    if (req.method === 'POST') {
      let b = '';
      req.on('data', c => { b += c; });
      req.on('end', () => {
        let pass = '';
        try { pass = String((JSON.parse(b || '{}') || {}).globalPassword || '').trim().slice(0, 128); } catch (e) {}
        if (pass && pass.length < 6) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Password must be at least 6 characters (or empty for auto).' }));
          return;
        }
        try {
          writeSettings({ globalPassword: pass });
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'SUCCESS', globalPassword: pass }));
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
        }
      });
      return;
    }
  }

  // 3. GET /api/meta-insta/events (also /api/events) - SSE stream
  if ((pathname === '/api/meta-insta/events' || pathname === '/api/events') && req.method === 'GET') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });
    res.write(': connected\n\n');
    sseClients.add(res);

    // Replay recent activity so terminal immediately displays logs on connection or page refresh
    for (const item of recentLogs) {
      try {
        res.write(`data: ${JSON.stringify(item)}\n\n`);
      } catch (e) {}
    }

    req.on('close', () => {
      sseClients.delete(res);
    });
    return;
  }

  // 4. POST /api/meta-insta/start (also /api/loop/start)
  if ((pathname === '/api/meta-insta/start' || pathname === '/api/loop/start') && req.method === 'POST') {
    if (activeLoopProcess) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'Meta creator is already actively running.' }));
      return;
    }

    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      let opts = { concurrency: 1, target: 0, delay: 4, headless: true, mail: 'mailtd', captcha: 'extension' };
      try {
        if (body) opts = Object.assign(opts, JSON.parse(body));
      } catch (e) {}

      // License Gate: Ensure machine has active license before starting automation
      const licCheck = await licenseMgr.validateOrActivateLicense(null, false);
      if (!licCheck.isValid) {
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'UNLICENSED',
          error: `Active license required to start Meta Creator (${licCheck.status}: ${licCheck.message || 'Please activate in Subscription.'})`,
          hwid: licCheck.hwid
        }));
        return;
      }

      // The dashboard value is authoritative.  There is no RAM pre-flight,
      // automatic reduction, or watchdog in the creator runtime: the user
      // explicitly controls the number of browser slots.
      const requestedConcurrency = Number.parseInt(opts.concurrency, 10);
      if (!Number.isFinite(requestedConcurrency) || requestedConcurrency < 1 || requestedConcurrency > 50) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ERROR',
          error: 'Parallel must be a whole number from 1 to 50. No automatic RAM reduction is applied.'
        }));
        return;
      }
      const concurrency = requestedConcurrency;
      const headless = opts.headless !== false;
      const target = parseInt(opts.target || 0, 10);
      const delay = Math.max(1, parseInt(opts.delay || 4, 10));
      const mail = 'mailtd';
      const captcha = opts.captcha_mode || opts.captcha || 'extension';
      const mode = (opts.mode === 'meta-ig') ? 'meta-ig' : 'meta';
      // Global password: request override, else the saved dashboard setting.
      // Passed via env (never argv) so it can't leak into logs or `ps`.
      const newPassword = String(opts.new_password || storedGlobalPassword() || '').trim().slice(0, 128);
      // Optional fixed username (workspace field). Also env-only.
      const newUsername = String(opts.new_username || '').trim().slice(0, 64);

      currentLoopConfig = { concurrency, headless, target, delay, mail, captcha, mode };

      const args = [
        path.join(ROOT_DIR, 'worker.py'),
        '--concurrency', String(concurrency),
        '--target', String(target),
        '--delay', String(delay),
        '--mail', mail,
        '--captcha', captcha,
        '--mode', mode
      ];
      if (headless) args.push('--headless');

      console.log(`[MetaCreator] Starting worker loop: ${PYTHON_BIN} ${args.join(' ')}`);

      const isWin = process.platform === 'win32';
      const defaultBrowsersPath = fs.existsSync(path.join(ROOT_DIR, '_internal', 'ms-playwright'))
        ? path.join(ROOT_DIR, '_internal', 'ms-playwright')
        : path.join(ROOT_DIR, 'engine', 'ms-playwright');

      try {
        activeLoopProcess = spawn(PYTHON_BIN, args, {
          cwd: ROOT_DIR,
          detached: !isWin,
          windowsHide: true,
          env: Object.assign({}, process.env, {
            PYTHONUNBUFFERED: '1',
            // Force UTF-8 for the worker's stdout/stderr. On Windows the pipe
            // to Node otherwise uses the locale code page and non-ASCII log
            // characters (—, emoji) arrive mangled as "�".
            PYTHONUTF8: '1',
            PYTHONIOENCODING: 'utf-8',
            PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH || defaultBrowsersPath,
            ...(newPassword ? { META_NEW_PASSWORD: newPassword } : {}),
            ...(newUsername ? { META_NEW_USERNAME: newUsername } : {})
          })
        });
      } catch (spawnErr) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Failed to spawn worker: ' + spawnErr.message }));
        return;
      }

      broadcastEvent({
        type: 'status',
        running: true,
        concurrency,
        target,
        headless,
        mode
      });

      activeLoopProcess.stdout.on('data', data => {
        const lines = data.toString('utf-8').split('\n');
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith('__EVENT__')) {
            try {
              const evt = JSON.parse(trimmed.slice(9));
              broadcastEvent(evt);
              if (evt.type === 'account_created') {
                broadcastEvent({ type: 'account_created', account: evt.account || evt });
              }
            } catch (e) {}
          } else {
            console.log(`[Worker] ${trimmed}`);
            broadcastEvent({ type: 'log', message: trimmed });
          }
        }
      });

      activeLoopProcess.stderr.on('data', data => {
        const text = data.toString('utf-8').trim();
        if (!text) return;
        // Playwright's node driver spews this whenever a browser/driver socket
        // closes (e.g. on Stop, or a crashed browser). It's noise, not
        // actionable — don't flood the dashboard with it.
        if (/socket\.send\(\) raised exception\.?/i.test(text)) return;
        console.error(`[Worker STDERR] ${text}`);
        broadcastEvent({ type: 'log', message: `[STDERR] ${text}` });
      });

      activeLoopProcess.on('close', code => {
        console.log(`[MetaCreator] Loop process exited with code ${code}`);
        broadcastEvent({ type: 'loop_stopped', exit_code: code });
        broadcastEvent({ type: 'status', running: false });
        activeLoopProcess = null;
      });

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', message: `Meta creator started with ${concurrency} concurrent windows.` }));
    });
    return;
  }

  // 5. POST /api/meta-insta/stop (also /api/loop/stop)
  if ((pathname === '/api/meta-insta/stop' || pathname === '/api/loop/stop') && req.method === 'POST') {
    if (activeLoopProcess) {
      killProcessGroup(activeLoopProcess, 'SIGINT');
      const proc = activeLoopProcess;
      setTimeout(() => {
        if (activeLoopProcess === proc) {
          killProcessGroup(proc, 'SIGKILL');
          activeLoopProcess = null;
        }
      }, 3000);
    }
    broadcastEvent({ type: 'loop_stopped', message: 'Engine stopped by user request.' });
    broadcastEvent({ type: 'status', running: false });
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', message: 'Engine stopped.' }));
    return;
  }

  // 6. POST /api/meta-insta/reset (also /api/accounts/reset)
  if ((pathname === '/api/meta-insta/reset' || pathname === '/api/accounts/reset') && req.method === 'POST') {
    let resetBody = '';
    req.on('data', c => { resetBody += c; });
    req.on('end', async () => {
      // Destructive: require an explicit confirmation token so a stray POST
      // (or a stale tab) can never wipe created accounts.
      let confirm = '';
      try { confirm = String((JSON.parse(resetBody || '{}') || {}).confirm || ''); } catch (e) {}
      if (confirm !== 'CLEAR') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Confirmation required: POST {"confirm":"CLEAR"} to wipe accounts.' }));
        return;
      }
      const backupDir = backupUserData('reset');
      if (storeDbExists()) {
        const r = await runPython('import store; store._write([])');
        if (!r.ok) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Could not clear the account database: ' + r.error }));
          return;
        }
      } else {
        try {
          fs.writeFileSync(ACCOUNTS_JSON, '[]', 'utf-8');
          fs.writeFileSync(ACCOUNTS_CSV, 'email,password,username\n', 'utf-8');
          fs.writeFileSync(ACCOUNTS_TXT, '', 'utf-8');
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
          return;
        }
      }
      broadcastEvent({ type: 'accounts_reset' });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'SUCCESS',
        message: 'Accounts database reset to 0.',
        backup: backupDir || null
      }));
    });
    return;
  }

  // 7. POST /api/meta-insta/delete (also /api/delete)
  if ((pathname === '/api/meta-insta/delete' || pathname === '/api/delete') && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let id = null;
      try {
        const parsed = JSON.parse(body);
        id = parsed.id;
      } catch (e) {}

      if (!id) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Account ID is required.' }));
        return;
      }

      if (storeDbExists()) {
        // SQLite is the source of truth — it MUST be deleted, otherwise the row
        // resurrects on the next accounts.json rebuild.
        const safeId = String(id).replace(/'/g, "''");
        const r = await runPython(`import store; store.delete_record('${safeId}')`);
        if (!r.ok) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Could not delete account from the database: ' + r.error }));
          return;
        }
        broadcastEvent({ type: 'account_deleted', id });
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'SUCCESS', deleted: 1 }));
        return;
      }

      const before = getAccounts();
      const after = before.filter(a => String(a.id) !== String(id));
      fs.writeFileSync(ACCOUNTS_JSON, JSON.stringify(after, null, 2), 'utf-8');
      broadcastEvent({ type: 'account_deleted', id });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', deleted: before.length - after.length }));
    });
    return;
  }

  // 8. POST /api/meta-insta/update
  if (pathname === '/api/meta-insta/update' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      try {
        const data = JSON.parse(body || '{}');
        if (!data.id) throw new Error('id required');
        const patch = data.patch || data;
        const before = getAccounts();
        const idx = before.findIndex(a => String(a.id) === String(data.id));
        if (idx === -1) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Account not found' }));
          return;
        }
        const updated = Object.assign({}, before[idx], patch);

        if (storeDbExists()) {
          // Apply to SQLite first (it regenerates accounts.json/csv/txt), and
          // fail loudly instead of writing a JSON edit that the next sync would revert.
          const pyId = JSON.stringify(String(data.id));
          const pyPatch = JSON.stringify(JSON.stringify(patch));
          const r = await runPython(`import store, json; store.update_account(${pyId}, json.loads(${pyPatch}))`);
          if (!r.ok) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ERROR', error: 'Could not update account in the database: ' + r.error }));
            return;
          }
        } else {
          before[idx] = updated;
          fs.writeFileSync(ACCOUNTS_JSON, JSON.stringify(before, null, 2), 'utf-8');
        }
        broadcastEvent({ type: 'account_updated', account: updated });
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'SUCCESS', account: updated }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
      }
    });
    return;
  }

  // 9. POST /api/meta-insta/cleanup
  if (pathname === '/api/meta-insta/cleanup' && req.method === 'POST') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', removed: 0 }));
    return;
  }

  // 10. GET /api/meta-insta/export (also /api/export)
  if ((pathname.startsWith('/api/meta-insta/export') || pathname === '/api/export') && req.method === 'GET') {
    const format = (urlObj.searchParams.get('format') || 'csv').toLowerCase();
    const kind = (urlObj.searchParams.get('kind') || '').toLowerCase() === 'ig' ? 'ig' : 'meta';
    (async () => {
      await syncFilesFromStore();

      if (format === 'txt') {
        if (fs.existsSync(ACCOUNTS_TXT)) {
          res.writeHead(200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="meta_accounts.txt"'
          });
          fs.createReadStream(ACCOUNTS_TXT).pipe(res);
        } else {
          const accounts = getAccounts();
          const txt = accounts.map(a => `${a.instagram_username || a.username || a.email}:${a.password || ''}`).join('\n');
          res.writeHead(200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="meta_accounts.txt"'
          });
          res.end(txt);
        }
        return;
      }

      if (kind === 'ig') {
        const accounts = getAccounts();
        const isIg = (a) => String((a && a.status) || '') !== 'MetaCreated'
          && (a && (a.instagram_username || String(a.platform || '').match(/Instagram/i)));
        const rows = ['username,password,cookies,combo'];
        const csvCell = (value) => {
          const text = String(value == null ? '' : value);
          return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
        };
        for (const a of accounts) {
          if (!isIg(a)) continue;
          const username = a.instagram_username || a.username || '';
          const password = a.password || '';
          if (!username || !password) continue;
          let cookieHeader = '';
          try {
            const f = cookieFileFor(a.id);
            if (f && fs.existsSync(f)) {
              const parsed = JSON.parse(fs.readFileSync(f, 'utf8'));
              if (Array.isArray(parsed)) {
                cookieHeader = parsed.filter(c => c && c.name)
                  .map(c => `${c.name}=${c.value == null ? '' : c.value}`).join('; ');
              }
            }
          } catch (e) {}
          const combo = `${username}|${password}|${cookieHeader}`;
          rows.push([username, password, cookieHeader, combo].map(csvCell).join(','));
        }
        res.writeHead(200, {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': 'attachment; filename="instagram_accounts.csv"'
        });
        res.end(rows.join('\r\n') + '\r\n');
        return;
      }

      if (fs.existsSync(ACCOUNTS_CSV) && fs.statSync(ACCOUNTS_CSV).size > 0) {
        res.writeHead(200, {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': 'attachment; filename="meta_accounts.csv"'
        });
        fs.createReadStream(ACCOUNTS_CSV).pipe(res);
      } else {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('No CSV data available yet.');
      }
    })();
    return;
  }

  // 11. POST /api/meta-insta/open (also /api/account/open)
  if ((pathname === '/api/meta-insta/open' || pathname === '/api/account/open') && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let id = null;
      let site = 'meta';
      try {
        const parsed = JSON.parse(body || '{}');
        id = parsed.id;
        site = (parsed.site || parsed.platform || 'meta').toLowerCase();
      } catch (e) {}

      const accounts = await loadAccounts();
      const acc = accounts.find(a => String(a.id) === String(id));
      const targetUrl = site === 'mail' ? 'https://mail.td/' : 'https://auth.meta.com/';

      const isWin = process.platform === 'win32';
      try {
        if (isWin) {
          execSync(`start "" "${targetUrl}"`, { stdio: 'ignore' });
        } else {
          execSync(`xdg-open "${targetUrl}" 2>/dev/null || sensible-browser "${targetUrl}" 2>/dev/null || true`, { stdio: 'ignore' });
        }
      } catch (e) {}

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'SUCCESS',
        ok: true,
        url: targetUrl,
        profileId: `meta_${id}`,
        profileName: `Meta — ${(acc && acc.name) || (acc && acc.email) || id}`,
        cookies: []
      }));
    });
    return;
  }

  // 12. POST /api/launch (fallback handler for UI browser launch)
  if (pathname === '/api/launch' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', () => {
      let targetUrl = 'https://auth.meta.com/';
      try {
        const parsed = JSON.parse(body || '{}');
        if (parsed.targetUrl) targetUrl = parsed.targetUrl;
        else if (Array.isArray(parsed.url) && parsed.url[0]) targetUrl = parsed.url[0];
        else if (typeof parsed.url === 'string') targetUrl = parsed.url;
      } catch (e) {}

      const isWin = process.platform === 'win32';
      try {
        if (isWin) {
          execSync(`start "" "${targetUrl}"`, { stdio: 'ignore' });
        } else {
          execSync(`xdg-open "${targetUrl}" 2>/dev/null || sensible-browser "${targetUrl}" 2>/dev/null || true`, { stdio: 'ignore' });
        }
      } catch (e) {}

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', ok: true }));
    });
    return;
  }

  // Any unhandled API requests MUST return JSON 404, never fall through to static HTML
  if (pathname.startsWith('/api/') || pathname === '/api') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ERROR', error: `API route not found: ${pathname}` }));
    return;
  }

  // --- Static Files ---
  let safeRel = (pathname === '/' || !pathname) ? 'index.html' : pathname.replace(/^\/+/, '');
  safeRel = path.normalize(safeRel).replace(/^(\.\.[\/\\])+/, '');
  let filePath = path.join(PUBLIC_DIR, safeRel);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }

  const ext = path.extname(filePath).toLowerCase();

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      if (safeRel === 'index.html') {
        const fallbacks = [
          path.join(__dirname, 'public', 'index.html'),
          path.join(process.cwd(), 'public', 'index.html'),
          path.join(ROOT_DIR, 'public', 'index.html'),
          path.join(path.dirname(process.execPath), 'public', 'index.html')
        ];
        for (const fb of fallbacks) {
          try {
            if (fs.existsSync(fb) && fs.statSync(fb).isFile()) {
              res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
              fs.createReadStream(fb).pipe(res);
              return;
            }
          } catch (e) {}
        }
      }
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end(`404 Not Found: ${pathname}`);
      return;
    }

    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    // Static asset cache: gzip once and revalidate with an ETag, so a reload
    // gets a 304 instead of re-downloading the 2k-line CSS / JS.
    const isText = /^(text\/|application\/(javascript|json))/.test(contentType) || ext === '.svg';
    const etag = `W/"${stats.mtimeMs}-${stats.size}"`;
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('ETag', etag);
    if (req.headers['if-none-match'] === etag) {
      res.writeHead(304);
      res.end();
      return;
    }
    let cached = STATIC_CACHE.get(filePath);
    if (!cached || cached.mtimeMs !== stats.mtimeMs || cached.size !== stats.size) {
      let gzip = null;
      if (isText && stats.size > 1024) {
        try { gzip = zlib.gzipSync(fs.readFileSync(filePath)); } catch (e) { gzip = null; }
      }
      cached = { mtimeMs: stats.mtimeMs, size: stats.size, gzip };
      STATIC_CACHE.set(filePath, cached);
    }
    if (cached.gzip && String(req.headers['accept-encoding'] || '').includes('gzip')) {
      res.writeHead(200, { 'Content-Type': contentType, 'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding' });
      res.end(cached.gzip);
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType });
    fs.createReadStream(filePath).pipe(res);
  });
});

// Graceful shutdown
function handleShutdown() {
  console.log('\n[MetaCreator] Shutting down server...');
  if (activeLoopProcess) {
    killProcessGroup(activeLoopProcess, 'SIGKILL');
    activeLoopProcess = null;
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

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[MetaCreator] Nova Meta UI active on http://localhost:${PORT}`);
  console.log(`[MetaCreator] Python interpreter: ${PYTHON_BIN}`);
});
