'use strict';
/**
 * Mr Follower — gives pooled IG Creator accounts their 5 follows and returns them to the list.
 *
 *   GET  /api/followmaker/status  -> {running, config, stats, logs[], auto}
 *   POST /api/followmaker/start   {creators, limit, follows, min_age_min, max_age_min, mode, auto, interval, visible}
 *   POST /api/followmaker/stop    graceful: the current accounts finish, then it exits
 *
 * One child process (follow_maker.py) at a time. stdout goes to a ring buffer the panel polls;
 * "__STATS__{json}" lines carry the counters.
 *
 * AUTO mode is hands-off: the setting is saved to disk, the runner is restarted if it crashes
 * (with a growing back-off) and it is started again when the dashboard restarts. Only an explicit
 * Stop turns it off.
 */
const fs = require('fs');
const path = require('path');
const baseCtx = require('./context');

const LOG_MAX = 400;
const STATE_FILE = path.join(baseCtx.ROOT_DIR, '.followmaker_state.json');
const RESUME_DELAY_MS = 8000;

let child = null;
let config = null;
let stats = {};
let logs = [];
let startedAt = 0;
let wantAuto = false;     // auto is switched on and nobody pressed Stop
let restarts = 0;
let restartTimer = null;

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => { size += c.length; if (size > 64 * 1024) { reject(new Error('too large')); req.destroy(); return; } chunks.push(c); });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    req.on('error', reject);
  });
}

function clamp(v, lo, hi, dflt) {
  const n = Number(v);
  if (!Number.isFinite(n)) return dflt;
  return Math.min(hi, Math.max(lo, n));
}

function pushLine(line) {
  if (!line) return;
  if (line.startsWith('__STATS__')) {
    try { stats = JSON.parse(line.slice(9)); } catch (e) { /* ignore */ }
    return;
  }
  logs.push({ t: Date.now(), m: line });
  if (logs.length > LOG_MAX) logs = logs.slice(-LOG_MAX);
}

function normalise(body) {
  body = body || {};
  return {
    creators: clamp(body.creators, 1, 20, 1),
    limit: clamp(body.limit, 0, 100000, 0),
    follows: clamp(body.follows, 1, 20, 5),
    min_age_min: clamp(body.min_age_min, 0, 100000, 10),
    max_age_min: clamp(body.max_age_min, 0, 100000, 0),
    mode: ['api', 'browser', 'auto'].includes(body.mode) ? body.mode : 'auto',
    on_fail: ['dead', 'delete', 'retry'].includes(body.on_fail) ? body.on_fail : 'dead',
    auto: !!body.auto,
    interval: clamp(body.interval, 5, 3600, 30),
    visible: !!body.visible,
  };
}

function saveState() {
  try {
    if (wantAuto && config) fs.writeFileSync(STATE_FILE, JSON.stringify({ auto: true, config }), 'utf-8');
    else if (fs.existsSync(STATE_FILE)) fs.unlinkSync(STATE_FILE);
  } catch (e) { /* read-only install: auto still works for this session */ }
}

function startChild(cfg) {
  if (child) return { ok: false, error: 'Mr Follower is already running.' };
  const { spawn, ROOT_DIR, PYTHON_BIN, resolveScript } = baseCtx;
  config = cfg;
  const argv = [
    resolveScript(path.join(ROOT_DIR, 'follow_maker.py')),
    '--creators', String(cfg.creators), '--limit', String(cfg.limit),
    '--follows', String(cfg.follows), '--min-age-min', String(cfg.min_age_min),
    '--max-age-min', String(cfg.max_age_min), '--mode', cfg.mode, '--on-fail', cfg.on_fail, '--interval', String(cfg.interval),
  ];
  if (cfg.auto) argv.push('--auto');
  if (cfg.visible) argv.push('--visible');
  stats = {}; startedAt = Date.now();
  let proc;
  try {
    proc = spawn(PYTHON_BIN, argv, {
      cwd: ROOT_DIR, windowsHide: true,
      env: Object.assign({}, process.env, { PYTHONUNBUFFERED: '1', PYTHONUTF8: '1' }),
    });
  } catch (e) {
    return { ok: false, error: 'Failed to start: ' + e.message };
  }
  child = proc;
  let buf = '';
  const feed = (d) => {
    buf += d.toString('utf-8');
    const lines = buf.split('\n');
    buf = lines.pop();
    lines.forEach((l) => pushLine(l.replace(/\r$/, '')));
  };
  proc.stdout.on('data', feed);
  proc.stderr.on('data', feed);
  const onEnd = (why) => {
    if (child !== proc) return;
    pushLine('[Mr Follower] process ended (' + why + ').');
    child = null;
    releaseClaims();
    scheduleRestart(Date.now() - startedAt);
  };
  proc.on('exit', (code) => onEnd(code));
  proc.on('error', (e) => onEnd(e.message));
  return { ok: true };
}

// Whatever way the runner ended (stop, force-kill, crash), give every locked account back.
function releaseClaims() {
  try {
    const { spawn, ROOT_DIR, PYTHON_BIN, resolveScript } = baseCtx;
    const p = spawn(PYTHON_BIN, [resolveScript(path.join(ROOT_DIR, 'follow_maker.py')), '--release-only'],
      { cwd: ROOT_DIR, windowsHide: true, env: Object.assign({}, process.env, { PYTHONUTF8: '1' }) });
    let out = '';
    p.stdout.on('data', (d) => { out += d.toString('utf-8'); });
    p.on('exit', () => { if (out.trim()) pushLine(out.trim().split('\n').pop()); });
  } catch (e) { /* the next start releases them anyway */ }
}

// Auto mode only: bring the runner back after a crash. Back-off grows with quick repeat crashes.
function scheduleRestart(uptimeMs) {
  if (!wantAuto || restartTimer) return;
  restarts = uptimeMs > 5 * 60 * 1000 ? 1 : restarts + 1;
  const delay = Math.min(300, 15 * restarts) * 1000;
  pushLine('[Mr Follower] auto mode: restarting in ' + Math.round(delay / 1000) + 's.');
  restartTimer = setTimeout(() => {
    restartTimer = null;
    if (wantAuto && !child) startChild(config);
  }, delay);
}

function stopAll(force) {
  wantAuto = false;
  restarts = 0;
  if (restartTimer) { clearTimeout(restartTimer); restartTimer = null; }
  saveState();
  if (child) {
    pushLine(force ? '[Mr Follower] FORCE STOP — killing the runner now.'
      : '[Mr Follower] stop requested — current accounts finish first.');
    try { child.kill(force ? 'SIGKILL' : 'SIGTERM'); } catch (e) { /* already gone */ }
  }
}

// Dashboard restarted while auto was on: carry on without anyone touching it.
setTimeout(() => {
  try {
    if (!fs.existsSync(STATE_FILE)) return;
    const st = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    if (!st || !st.auto || !st.config || child) return;
    wantAuto = true;
    pushLine('[Mr Follower] auto mode was on — resuming.');
    startChild(normalise(st.config));
  } catch (e) { /* unreadable state: stay off */ }
}, RESUME_DELAY_MS).unref();

process.on('exit', () => { try { if (child) child.kill('SIGTERM'); } catch (e) { /* ignore */ } });

module.exports = function handleFollowMaker(req, res, urlObj, pathname, ctx) {
  const { sendJson } = ctx;

  if (pathname === '/api/followmaker/status' && req.method === 'GET') {
    sendJson(req, res, { status: 'SUCCESS', running: !!child, auto: wantAuto, config, stats, logs: logs.slice(-200), startedAt });
    return true;
  }

  if (pathname === '/api/followmaker/start' && req.method === 'POST') {
    (async () => {
      let body = {};
      try { body = JSON.parse((await readBody(req)) || '{}'); } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Invalid JSON body.' }, 400); return;
      }
      if (child) { sendJson(req, res, { status: 'ERROR', error: 'Mr Follower is already running.' }, 409); return; }
      const cfg = normalise(body);
      wantAuto = cfg.auto;
      restarts = 0;
      logs = [];
      const r = startChild(cfg);
      if (!r.ok) { wantAuto = false; sendJson(req, res, { status: 'ERROR', error: r.error }, 500); return; }
      saveState();
      sendJson(req, res, { status: 'SUCCESS', config: cfg });
    })();
    return true;
  }

  if (pathname === '/api/followmaker/stop' && req.method === 'POST') {
    (async () => {
      let body = {};
      try { body = JSON.parse((await readBody(req)) || '{}'); } catch (e) { /* no body */ }
      stopAll(!!body.force);
      sendJson(req, res, { status: 'SUCCESS', running: !!child });
    })();
    return true;
  }

  return false;
};
