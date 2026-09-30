/**
 * server/runlog.js — persistent per-run engine logs (read-only storage).
 *
 * Writes FULL stdout+stderr to
 *   logs/<pipeline>_<YYYYMMDD_HHMMSS>.log
 * and refreshes
 *   logs/latest_<pipeline>.log
 *   logs/latest.txt
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const LOG_DIR = process.env.META_LOG_DIR || path.join(ROOT, 'logs');
const KEEP = Math.max(5, parseInt(process.env.META_LOG_KEEP || '40', 10) || 40);
const MAX_BYTES = Math.max(1, parseInt(process.env.META_LOG_MAX_MB || '25', 10) || 25) * 1024 * 1024;

function ensureDir() {
  try { fs.mkdirSync(LOG_DIR, { recursive: true }); } catch (e) { /* ignore */ }
}

function _stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function _hhmmss() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** Open a new run log for `pipeline`. Returns a handle for line()/end(). */
function start(pipeline, meta) {
  // Continuous stdout/stderr disk logging is dev-only (opt-in via META_ENABLE_RUNLOG=1 or META_DEBUG=1).
  // Disabled by default to prevent heavy disk I/O bottlenecks and disk bloat on low-end machines.
  if (process.env.META_ENABLE_RUNLOG !== '1' && process.env.META_DEBUG !== '1') {
    return null;
  }
  ensureDir();
  const file = path.join(LOG_DIR, `${pipeline}_${_stamp()}.log`);
  let stream = null;
  try { stream = fs.createWriteStream(file, { flags: 'a' }); } catch (e) { stream = null; }
  const h = { pipeline, file, stream, bytes: 0, closed: false };
  const header = [
    '# meta_creator run log',
    `# pipeline: ${pipeline}`,
    `# started:  ${new Date().toISOString()}`,
    `# argv:     ${JSON.stringify((meta && meta.argv) || [])}`,
    `# cwd:      ${process.cwd()}`,
    '# ----',
    '',
  ].join('\n');
  try {
    if (stream) stream.write(header);
    fs.writeFileSync(path.join(LOG_DIR, `latest_${pipeline}.log`), header + `# see: ${file}\n`);
    fs.writeFileSync(path.join(LOG_DIR, 'latest.txt'), file + '\n');
  } catch (e) { /* ignore */ }
  prune();
  return h;
}

function line(h, text) {
  if (!h || !h.stream || h.closed) return;
  try {
    const raw = String(text == null ? '' : text);
    const stamped = raw.split('\n')
      .map((l) => (l ? `[${_hhmmss()}] ${l}\n` : '\n'))
      .join('');
    h.stream.write(stamped);
    h.bytes += Buffer.byteLength(stamped);
    if (h.bytes > MAX_BYTES) {
      h.stream.write(`\n# log capped at ${Math.round(MAX_BYTES / 1048576)} MB\n`);
      h.closed = true;
      try { h.stream.end(); } catch (e) { /* ignore */ }
    }
  } catch (e) { /* hot path — never throw */ }
}

function end(h) {
  if (!h || h.closed) return;
  h.closed = true;
  try { h.stream.end(); } catch (e) { /* ignore */ }
}

function prune() {
  try {
    const files = fs.readdirSync(LOG_DIR)
      .filter((f) => /\.log$/.test(f) && !f.startsWith('latest'))
      .map((f) => {
        let t = 0;
        try { t = fs.statSync(path.join(LOG_DIR, f)).mtimeMs; } catch (e) { /* ignore */ }
        return { f, t };
      })
      .sort((a, b) => b.t - a.t);
    for (const s of files.slice(KEEP)) {
      try { fs.unlinkSync(path.join(LOG_DIR, s.f)); } catch (e) { /* ignore */ }
    }
  } catch (e) { /* ignore */ }
}

/** Newest-first list of run logs (excludes the latest_* pointers). */
function list() {
  ensureDir();
  try {
    return fs.readdirSync(LOG_DIR)
      .filter((f) => /\.log$/.test(f) && !f.startsWith('latest'))
      .map((f) => {
        const st = fs.statSync(path.join(LOG_DIR, f));
        return { name: f, size: st.size, mtime: st.mtimeMs };
      })
      .sort((a, b) => b.mtime - a.mtime);
  } catch (e) {
    return [];
  }
}

function latest(pipeline) {
  const l = list().filter((x) => !pipeline || x.name.startsWith(pipeline + '_'));
  return l.length ? l[0] : null;
}

/** Read one log by basename (path-traversal guarded). */
function read(name) {
  const base = path.basename(String(name || ''));
  if (!/^[A-Za-z0-9_.-]+\.log$/.test(base)) return null;
  const p = path.join(LOG_DIR, base);
  if (!p.startsWith(LOG_DIR + path.sep)) return null;
  try { return { path: p, content: fs.readFileSync(p, 'utf-8') }; } catch (e) { return null; }
}

module.exports = { start, line, end, prune, list, latest, read, LOG_DIR, KEEP, MAX_BYTES };
