/**
 * Meta Creator — Node.js Backend Server (Nova Browser Parity)
 * Dedicated Meta Account Creation Engine & Nova API Integration
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { spawn, execSync } = require('child_process');
const diag = require('./diag');
const runlog = require('./runlog');

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
// ---------------- TG Classic helpers ----------------
// The TG profile pool lives in data/tg_accounts.json (registered by
// tg_login*.py / the dashboard). Read-only here; never mutate from the server.
// Bots this BUILD ships (written by `build_windows_dist.py --bots …` as
// tg/enabled_bots.json). Falls back to all bots in a dev tree / no manifest.
// Used so a single-bot build (e.g. --bots fastpay) does not fall back to a
// hardcoded 'taskly' that was never shipped.
const ALL_BOTS = ['taskly', 'paygo', 'fastpay'];
function readEnabledBots() {
  try {
    const f = path.join(ROOT_DIR, 'tg', 'enabled_bots.json');
    if (fs.existsSync(f)) {
      const ids = (JSON.parse(fs.readFileSync(f, 'utf8')).bots || []).filter(b => ALL_BOTS.includes(b));
      if (ids.length) return ids;
    }
  } catch (e) {}
  return ALL_BOTS.slice();
}
function defaultBot() { return readEnabledBots()[0] || 'taskly'; }

function readTgPool() {
  try {
    const f = path.join(ROOT_DIR, 'data', 'tg_accounts.json');
    if (!fs.existsSync(f)) return [];
    const raw = JSON.parse(fs.readFileSync(f, 'utf8'));
    const rows = Array.isArray(raw) ? raw : (raw.accounts || []);
    return (Array.isArray(rows) ? rows : Object.values(rows)).map(a => ({
      id: a.id,
      label: a.label || a.name || a.id,
      name: a.name || null,
      phone: a.phone || null,
      mode: a.mode || 'web',
      enabled: a.enabled !== false,
      proxy: a.proxy || null,
      status: a.status || 'idle',
      logged_in: a.logged_in === true,
      tasks_done: a.tasks_done || 0,
    }));
  } catch (e) { return []; }
}

// Pre-flight for /api/tg/start: true when at least one pool profile is enabled
// AND logged in. The coupled cycle creates the Meta account BEFORE leasing a
// Telegram profile, so an empty/disabled/logged-out pool must be refused up
// front instead of burning a Meta account and then failing.
function tgPoolUsable() {
  try {
    return readTgPool().some(a => a.enabled !== false && a.logged_in === true);
  } catch (e) { return false; }
}

function storedGlobalPassword() {
  return String(readSettings().globalPassword || '').trim().slice(0, 128);
}

const PORT = parseInt(process.env.PORT || '3070', 10);
const ROOT_DIR = path.join(__dirname, '..');  // server/ module: project root is one up
// Cookie exports written by the Python engine: <ROOT>/cookies/cookies_<id>.txt
// (JSON array, Nova parity: served per-account with count, like /api/export-cookies).
function cookieFileFor(id) {
  const safe = String(id == null ? '' : id).replace(/[^A-Za-z0-9_@.\-]/g, '');
  if (!safe) return null;
  return path.join(ROOT_DIR, 'cookies', `cookies_${safe}.txt`);
}
function resolvePublicDir() {
  const candidates = [
    path.join(ROOT_DIR, 'public'),
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
  return path.join(ROOT_DIR, 'public');
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

// Extension-agnostic script resolution: finds .py or .pyc on disk.
function resolveScript(script) {
  const p = path.isAbsolute(script) ? script : path.join(ROOT_DIR, script);
  if (fs.existsSync(p)) return p;
  if (p.endsWith('.py') && fs.existsSync(p + 'c')) return p + 'c';
  if (p.endsWith('.pyc') && fs.existsSync(p.slice(0, -1))) return p.slice(0, -1);
  return p;
}

// Send JSON with gzip when the client accepts it. /api/meta-insta/accounts
// is ~1.5 MB with 812 accounts (fetched every 10s poll) — gzip cuts it to
// ~150-200 KB with zero frontend changes.
// Run a python helper and parse its final stdout line as JSON.
function runPythonJson(pythonBin, rootDir, script, args, timeoutMs) {
  return new Promise((resolve) => {
    let child;
    const targetScript = resolveScript(path.isAbsolute(script) ? script : path.join(rootDir, script));
    try {
      child = spawn(pythonBin, [targetScript].concat(args || []), {
        cwd: rootDir, windowsHide: true,
        env: Object.assign({}, process.env, { PYTHONUNBUFFERED: '1', PYTHONUTF8: '1' }),
      });
    } catch (e) { resolve({ ok: false, error: 'spawn failed: ' + e.message }); return; }
    let out = '', err = '';
    const t = setTimeout(() => { try { child.kill('SIGKILL'); } catch (e) {} resolve({ ok: false, error: 'timeout' }); }, timeoutMs || 120000);
    child.stdout.on('data', d => { out += d.toString(); });
    child.stderr.on('data', d => { err += d.toString(); });
    child.on('error', e => { clearTimeout(t); resolve({ ok: false, error: String(e.message || e) }); });
    child.on('close', () => {
      clearTimeout(t);
      const line = out.trim().split('\n').filter(Boolean).pop() || '';
      try { resolve(JSON.parse(line)); }
      catch (e) { resolve({ ok: false, error: (err || out || 'no output').trim().slice(0, 400) }); }
    });
  });
}

// Self-heal a STALE engine handle. If a worker hung/crashed without firing
// 'close' (or Node missed it), slot().proc stays truthy and every Start
// is refused until the whole app is restarted — the "everything shows BUSY and
// nothing runs" wedge. A Node ChildProcess exposes exitCode once it has exited,
// so reap on every status/guard read.
function reapDeadEngine(name) {
  const target = slot(name);
  try {
    if (target.proc && target.proc.exitCode !== null) {
      console.log('[MetaCreator] Reaping stale engine handle (' + (name || activeEngine) + ', exitCode=' + target.proc.exitCode + ')');
      target.proc = null;
      target.config = null;
    }
  } catch (e) {}
  return !!target.proc;
}

function sendJson(req, res, obj, statusCode) {
  try {
    const body = Buffer.from(JSON.stringify(obj));
    const ae = String((req && req.headers && req.headers['accept-encoding']) || '');
    // Every API response is no-store: these are live reads of the engine/pool
    // and MUST never be served from the browser cache. Without this, a cached
    // (stale or empty) /api/tg/status could paint a populated pool while the
    // Start preflight read the cached empty copy and blocked with
    // "no Telegram profile in the pool".
    const baseHeaders = {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
      'Pragma': 'no-cache',
      'Expires': '0',
    };
    if (ae.includes('gzip') && body.length > 1024) {
      try {
        const gz = zlib.gzipSync(body);
        res.writeHead(statusCode || 200, Object.assign({}, baseHeaders, { 'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding' }));
        res.end(gz);
        return;
      } catch (e) {}
    }
    res.writeHead(statusCode || 200, baseHeaders);
    res.end(body);
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ERROR', error: e.message }));
  }
}

const LicenseManager = require('../core/licenseManager');
const licenseMgr = new LicenseManager();
const updateManager = require('../core/updateManager');
const licenseConfig = require('../core/licenseConfig');

// Clean up stale update files if any
try {
  updateManager.cleanupStaleUpdateFiles(process.pkg ? process.execPath : null);
} catch (e) {}

// Per-pipeline engine slots. Meta Creator (meta-only) and Instagram Creator
// (meta-ig) have independent slots so both can run concurrently and independently.
// metainsta is maintained as a backward-compatible alias.
const engineSlots = {
  meta:      { proc: null, inFlight: false, config: null, runlog: null },
  ig:        { proc: null, inFlight: false, config: null, runlog: null },
  metainsta: { proc: null, inFlight: false, config: null, runlog: null },
  tg:        { proc: null, inFlight: false, config: null, runlog: null },
};
// Which slot the CURRENT request context operates on.
let activeEngine = 'metainsta';
function setEngine(name) {
  if (name === 'tg' || name === 'meta' || name === 'ig' || name === 'metainsta') {
    activeEngine = name;
  } else {
    activeEngine = 'metainsta';
  }
}
function slot(name) {
  if (name && engineSlots[name]) return engineSlots[name];
  return engineSlots[activeEngine];
}
// FastPay payout runner process (tg_fastpay.py). Separate from the TG Classic
// engine slot: it must not run while that engine holds the sessions.
// Each slot's config starts as null and is populated by its own start route;
// every read already guards with (slot().config || {}). The old single
// object literal is gone on purpose — a shared default is what made the
// Meta/IG tabs report TG's settings.
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
  if (data.type === 'account_created') {
    try {
      const paygoOrchestrator = require('./paygo-orchestrator');
      if (paygoOrchestrator && paygoOrchestrator.enabled) {
        paygoOrchestrator.onAccountCreated(data);
      }
    } catch (e) {}
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

function consumeWorkerLine(line, engineName = null) {
  const trimmed = String(line || '').trim();
  if (!trimmed) return;
  diag.observe(trimmed);
  const eng = engineName || activeEngine || 'metainsta';
  const pipeline = (eng === 'tg') ? 'telegram' : 'meta';
  const currentBot = (eng === 'tg' && engineSlots.tg && engineSlots.tg.config) ? engineSlots.tg.config.tg_bot : null;
  const tag = (eng === 'tg') ? `[TG:${currentBot || 'bot'}]` : (eng === 'ig' ? '[IG]' : '[Meta]');
  if (trimmed.startsWith('__EVENT__')) {
    try {
      const evt = JSON.parse(trimmed.slice(9));
      if (!evt.pipeline) evt.pipeline = pipeline;
      if (!evt.engine) evt.engine = eng;
      if (currentBot && !evt.tg_bot) evt.tg_bot = currentBot;
      broadcastEvent(evt);
    } catch (e) {}
  } else {
    console.log(`${tag} ${trimmed}`);
    const evt = { type: 'log', message: trimmed, pipeline, engine: eng };
    if (currentBot) evt.tg_bot = currentBot;
    broadcastEvent(evt);
  }
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

// Worker stdout line-buffers, isolated per engine slot so concurrent runs don't interleave.
const _workerBuffers = {
  meta: '',
  ig: '',
  metainsta: '',
  tg: '',
};
function resetWorkerBuffer(eng = null) {
  if (eng && _workerBuffers[eng] !== undefined) _workerBuffers[eng] = '';
  else { for (const k in _workerBuffers) _workerBuffers[k] = ''; }
}
function feedWorkerStdout(data, eng = null) {
  const k = (eng && _workerBuffers[eng] !== undefined) ? eng : (activeEngine || 'metainsta');
  _workerBuffers[k] = (_workerBuffers[k] || '') + String(data == null ? '' : data.toString('utf-8'));
  const lines = _workerBuffers[k].split('\n');
  _workerBuffers[k] = lines.pop() || '';
  return lines;
}
function flushWorkerBuffer(eng = null) {
  const k = (eng && _workerBuffers[eng] !== undefined) ? eng : (activeEngine || 'metainsta');
  if (_workerBuffers[k]) {
    consumeWorkerLine(_workerBuffers[k], k);
    _workerBuffers[k] = '';
  }
}

// FastPay payout runner procs (tg_fastpay.py). Separate from the TG Classic
// engine slot: they must not run while that engine holds the sessions.
let _fastpayProcs = [];
function fastpayCount() { return _fastpayProcs.length; }
function fastpayList() { return _fastpayProcs; }
function fastpayAdd(proc, tag) { _fastpayProcs.push({ proc, tag }); }
function fastpayRemove(proc) {
  _fastpayProcs = _fastpayProcs.filter(x => x.proc !== proc);
  return _fastpayProcs.length;
}

module.exports = {
  fs, path, zlib, spawn, execSync,
  ROOT_DIR, PUBLIC_DIR, DATA_DIR, ACCOUNTS_JSON, ACCOUNTS_CSV, ACCOUNTS_TXT, PORT,
  PYTHON_BIN, ALL_BOTS,
  readEnabledBots, defaultBot, readTgPool, tgPoolUsable, storedGlobalPassword,
  backupUserData, readSettings, writeSettings, cookieFileFor,
  runPythonJson, resolveScript, reapDeadEngine, sendJson,
  licenseMgr, updateManager, licenseConfig,
  engineSlots, setEngine, slot,
  sseClients, recentLogs, broadcastEvent, consumeWorkerLine,
  getAccounts, storeDbExists, runPython, syncFilesFromStore, loadAccounts,
  killProcessGroup,
  resetWorkerBuffer, feedWorkerStdout, flushWorkerBuffer,
  fastpayCount, fastpayList, fastpayAdd, fastpayRemove,
  diag, runlog,
};
