/**
 * Nova Browser — Self-update engine (check, download, verify, stage, apply).
 *
 * Flow: checkForUpdates() compares the release feed against the running
 * version -> startDownload() streams the per-OS binary with progress ->
 * verifyAndStage() checks SHA-256 and parks it next to the exe as `.new` ->
 * applyStagedUpdate() writes a platform updater script, spawns it detached,
 * and the caller exits; the updater waits for our death, rotates
 * current->.prev / .new->current, relaunches, and self-deletes.
 *
 * Data safety: only the executable file is ever moved. profiles_data,
 * license files, and the per-user HWID seed are never touched, so an
 * update cannot deactivate or wipe a machine.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const https = require('https');
const crypto = require('crypto');
const { spawn } = require('child_process');
const config = require('./licenseConfig');

const DOWNLOAD_STATE = {
  IDLE: 'idle',
  DOWNLOADING: 'downloading',
  VERIFYING: 'verifying',
  READY: 'ready',
  ERROR: 'error',
};

// --- version helpers (no deps) ---------------------------------------------

function parseVersion(value) {
  const parts = String(value || '')
    .trim()
    .replace(/^[vV]/, '')
    .split('.')
    .map((p) => parseInt(p, 10));
  if (parts.length === 0 || parts.some((n) => Number.isNaN(n) || n < 0)) return null;
  while (parts.length < 3) parts.push(0);
  return parts.slice(0, 3);
}

/** -1 if a<b, 0 if equal, 1 if a>b. Unknown shapes compare as equal (safe). */
function compareVersions(a, b) {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  if (!pa || !pb) return 0;
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] < pb[i] ? -1 : 1;
  }
  return 0;
}

function currentPlatformKey() {
  return process.platform === 'win32' ? 'win-x64' : 'linux-x64';
}

// --- feed fetch (redirect-following, timeout-guarded) -----------------------

function fetchJson(feedUrl, timeoutMs) {
  return new Promise((resolve, reject) => {
    const hop = (targetUrl, redirectsLeft) => {
      let url;
      try {
        url = new URL(targetUrl);
      } catch (e) {
        reject(new Error('Invalid update feed URL.'));
        return;
      }
      const mod = url.protocol === 'https:' ? https : http;
      const req = mod.get(
        {
          hostname: url.hostname,
          port: url.port || (url.protocol === 'https:' ? 443 : 80),
          path: url.pathname + url.search,
          headers: { 'User-Agent': 'NovaBrowser-Updater', Accept: 'application/json' },
        },
        (res) => {
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            res.resume();
            if (redirectsLeft <= 0) {
              reject(new Error('Update feed redirected too many times.'));
              return;
            }
            hop(new URL(res.headers.location, url).toString(), redirectsLeft - 1);
            return;
          }
          if (res.statusCode !== 200) {
            res.resume();
            reject(new Error(`Update feed answered HTTP ${res.statusCode}.`));
            return;
          }
          let body = '';
          res.on('data', (c) => {
            body += c.toString();
            if (body.length > 1024 * 1024) req.destroy(); // manifest must be tiny
          });
          res.on('end', () => {
            try {
              resolve(JSON.parse(body));
            } catch (e) {
              reject(new Error('Update feed returned invalid JSON.'));
            }
          });
        }
      );
      req.setTimeout(timeoutMs, () => {
        try { req.destroy(); } catch (e) {}
        reject(new Error('Update feed timed out.'));
      });
      req.on('error', (err) => reject(err));
    };
    hop(feedUrl, 5);
  });
}

/**
 * Checks the release feed. Never throws: network problems resolve to
 * { updateAvailable: false, error } so the dashboard simply stays quiet.
 */
async function checkForUpdates(options = {}) {
  const currentVersion = config.app.version;
  // Updates disabled: completely silence all update checks and notifications
  if ((config.updates && config.updates.enabled === false) || (!options.force && !process.pkg && process.env.ENABLE_DEV_UPDATE_CHECK !== '1')) {
    return {
      currentVersion,
      updateAvailable: false,
      update: null,
      disabled: true,
      checkedAt: new Date().toISOString(),
    };
  }
  const feedUrl = options.feedUrl || config.updates.feedUrl;
  if (!feedUrl) {
    return {
      currentVersion,
      updateAvailable: false,
      update: null,
      disabled: true,
      checkedAt: new Date().toISOString(),
    };
  }
  const timeoutMs = options.timeoutMs || config.updates.requestTimeoutMs;
  try {
    const manifest = await fetchJson(feedUrl, timeoutMs);
    const platform = options.platform || currentPlatformKey();
    const file = manifest && manifest.files ? manifest.files[platform] : null;
    if (!manifest || !manifest.version || !file || !file.url || !file.sha256) {
      return { currentVersion, updateAvailable: false, update: null, checkedAt: new Date().toISOString(), error: 'Update feed is malformed.' };
    }
    if (compareVersions(manifest.version, currentVersion) <= 0) {
      return { currentVersion, updateAvailable: false, update: null, checkedAt: new Date().toISOString() };
    }
    return {
      currentVersion,
      updateAvailable: true,
      update: {
        version: String(manifest.version).replace(/^[vV]/, ''),
        notes: manifest.notes || '',
        url: file.url,
        sha256: String(file.sha256).toLowerCase(),
        size: file.size || 0,
        // Windows: one-click Setup download (no staging, no auto-restart).
        // The dashboard Download button fetches this plain file instead.
        setupUrl: manifest.files && manifest.files['win-setup'] && manifest.files['win-setup'].url
          ? manifest.files['win-setup'].url : null,
        setupSize: manifest.files && manifest.files['win-setup'] ? (manifest.files['win-setup'].size || 0) : 0,
      },
      checkedAt: new Date().toISOString(),
    };
  } catch (err) {
    return { currentVersion, updateAvailable: false, update: null, checkedAt: new Date().toISOString(), error: err.message };
  }
}

// --- download job (single-flight, progress-reporting) -----------------------

const downloadJob = {
  state: DOWNLOAD_STATE.IDLE,
  version: null,
  url: null,
  sha256: null,
  filePath: null,
  received: 0,
  total: 0,
  error: null,
};

function downloadDir(version) {
  const dir = path.join(os.tmpdir(), `nova-update-${version}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function downloadToFile(fileUrl, destPath, timeoutMs, onProgress) {
  return new Promise((resolve, reject) => {
    const hop = (targetUrl, redirectsLeft) => {
      let url;
      try {
        url = new URL(targetUrl);
      } catch (e) {
        reject(new Error('Invalid download URL.'));
        return;
      }
      const mod = url.protocol === 'https:' ? https : http;
      const req = mod.get(
        {
          hostname: url.hostname,
          port: url.port || (url.protocol === 'https:' ? 443 : 80),
          path: url.pathname + url.search,
          headers: { 'User-Agent': 'NovaBrowser-Updater' },
        },
        (res) => {
          if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
            res.resume();
            if (redirectsLeft <= 0) {
              reject(new Error('Download redirected too many times.'));
              return;
            }
            hop(new URL(res.headers.location, url).toString(), redirectsLeft - 1);
            return;
          }
          if (res.statusCode !== 200) {
            res.resume();
            reject(new Error(`Download answered HTTP ${res.statusCode}.`));
            return;
          }
          const total = parseInt(res.headers['content-length'] || '0', 10) || 0;
          onProgress(0, total);
          const out = fs.createWriteStream(destPath);
          let received = 0;
          res.on('data', (c) => {
            received += c.length;
            onProgress(received, total);
          });
          res.on('error', (err) => {
            try { out.destroy(); } catch (e) {}
            reject(err);
          });
          out.on('error', (err) => reject(err));
          out.on('finish', () => resolve({ received, total }));
          req.setTimeout(timeoutMs, () => {
            try { req.destroy(); } catch (e) {}
            try { out.destroy(); } catch (e) {}
            reject(new Error('Download timed out.'));
          });
          res.pipe(out);
        }
      );
      req.on('error', (err) => reject(err));
    };
    hop(fileUrl, 5);
  });
}

function getDownloadProgress() {
  return {
    state: downloadJob.state,
    version: downloadJob.version,
    received: downloadJob.received,
    total: downloadJob.total,
    error: downloadJob.error,
  };
}

function startDownload(update, options = {}) {
  if (!update || !update.url || !update.sha256 || !update.version) {
    throw new Error('Invalid update descriptor.');
  }
  if (downloadJob.state === DOWNLOAD_STATE.DOWNLOADING) {
    return { started: false, reason: 'already-downloading' };
  }
  downloadJob.state = DOWNLOAD_STATE.DOWNLOADING;
  downloadJob.version = update.version;
  downloadJob.url = update.url;
  downloadJob.sha256 = String(update.sha256).toLowerCase();
  downloadJob.received = 0;
  downloadJob.total = 0;
  downloadJob.error = null;
  downloadJob.filePath = path.join(downloadDir(update.version), `nova-browser-update${process.platform === 'win32' ? '.exe' : ''}`);

  const timeoutMs = options.timeoutMs || 0; // 0 = no overall timeout, stream-driven
  downloadToFile(
    update.url,
    downloadJob.filePath,
    timeoutMs,
    (received, total) => {
      downloadJob.received = received;
      downloadJob.total = total;
    }
  ).then(
    () => {
      if (downloadJob.state === DOWNLOAD_STATE.DOWNLOADING) {
        downloadJob.state = DOWNLOAD_STATE.VERIFYING;
        verifyStagedFile()
          .then((ok) => {
            downloadJob.state = ok ? DOWNLOAD_STATE.READY : DOWNLOAD_STATE.ERROR;
            if (!ok) downloadJob.error = 'Checksum mismatch — download discarded, current install untouched.';
          })
          .catch((err) => {
            downloadJob.state = DOWNLOAD_STATE.ERROR;
            downloadJob.error = err.message;
          });
      }
    },
    (err) => {
      downloadJob.state = DOWNLOAD_STATE.ERROR;
      downloadJob.error = err.message;
    }
  );
  return { started: true, version: update.version };
}

function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath);
    stream.on('error', reject);
    stream.on('data', (c) => hash.update(c));
    stream.on('end', () => resolve(hash.digest('hex')));
  });
}

async function verifyStagedFile() {
  if (!downloadJob.filePath || !fs.existsSync(downloadJob.filePath)) return false;
  const actual = await sha256File(downloadJob.filePath);
  return actual.toLowerCase() === downloadJob.sha256;
}

// --- staging + apply ---------------------------------------------------------

function currentExePath() {
  // In dev (node server.js) there is no packaged exe to replace.
  if (!process.pkg) return null;
  return process.execPath;
}

function stagedPaths(exePath) {
  const dir = path.dirname(exePath);
  const ext = path.extname(exePath);
  const stem = path.basename(exePath, ext);
  return {
    dir,
    currentPath: exePath,
    newPath: path.join(dir, `${stem}.new${ext}`),
    prevPath: path.join(dir, `${stem}.prev${ext}`),
    updaterPath: path.join(dir, `nova-updater-${process.pid}${process.platform === 'win32' ? '.bat' : '.sh'}`),
  };
}

/**
 * Moves the verified download next to the running exe as `.new`.
 * Refuses downgrades/reinstalls of the same version. Throws on problems.
 */
function installStagedUpdate(targetVersion) {
  const exePath = currentExePath();
  if (!exePath) {
    throw new Error('Self-update applies to packaged builds only; in dev, pull the code instead.');
  }
  if (downloadJob.state !== DOWNLOAD_STATE.READY || !downloadJob.filePath) {
    throw new Error('No verified download staged. Download first.');
  }
  if (targetVersion && compareVersions(targetVersion, config.app.version) <= 0) {
    throw new Error(`Refusing update to ${targetVersion}: not newer than running ${config.app.version}.`);
  }
  const paths = stagedPaths(exePath);
  fs.copyFileSync(downloadJob.filePath, paths.newPath);
  return { staged: true, version: downloadJob.version, newPath: paths.newPath };
}

/** Removes a crashed update's residue at boot. Never touches live files. */
function cleanupStaleUpdateFiles(exePath) {
  try {
    if (!exePath || !fs.existsSync(exePath)) return;
    const dir = path.dirname(exePath);
    for (const entry of fs.readdirSync(dir)) {
      if (/^nova-updater-\d+\.(bat|sh)$/.test(entry)) {
        try { fs.unlinkSync(path.join(dir, entry)); } catch (e) {}
      }
    }
  } catch (e) {
    // boot hygiene must never fail startup
  }
}

function quoteWin(p) {
  return `"${p}"`;
}

/**
 * Writes the platform updater script. The script waits for our pid to die,
 * performs the file moves, relaunches, and deletes itself. Pure file
 * content — fully unit-testable without running anything.
 */
function buildUpdaterScript({ platform, pid, moves, launchPath, updaterPath }) {
  let script;
  if (platform === 'win32') {
    const lines = ['@echo off', 'setlocal', `set "PID=${pid}"`, ':wait_loop'];
    lines.push(`tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL`);
    lines.push('if not errorlevel 1 ( timeout /t 1 /nobreak >NUL & goto wait_loop )');
    for (const move of moves) {
      lines.push(`if exist ${quoteWin(move.from)} move /Y ${quoteWin(move.from)} ${quoteWin(move.to)} >NUL`);
    }
    lines.push(`start "" ${quoteWin(launchPath)}`);
    lines.push(`del ${quoteWin(updaterPath)}`);
    script = lines.join('\r\n') + '\r\n';
  } else {
    const lines = ['#!/bin/sh', `PID=${pid}`];
    lines.push('while kill -0 "$PID" 2>/dev/null; do sleep 0.5; done');
    for (const move of moves) {
      lines.push(`mv -f ${JSON.stringify(move.from)} ${JSON.stringify(move.to)}`);
    }
    lines.push(`chmod +x ${JSON.stringify(launchPath)}`);
    lines.push(`nohup ${JSON.stringify(launchPath)} >/dev/null 2>&1 &`);
    lines.push('rm -f -- "$0"');
    script = lines.join('\n') + '\n';
  }
  fs.writeFileSync(updaterPath, script, { mode: 0o755 });
  try { fs.chmodSync(updaterPath, 0o755); } catch (e) {}
  return updaterPath;
}

/**
 * Spawns the updater detached and returns; the caller MUST exit promptly
 * afterwards so the updater observes our death and proceeds.
 */
function spawnUpdater(updaterPath) {
  if (process.platform === 'win32') {
    const child = spawn('cmd.exe', ['/d', '/s', '/c', updaterPath], {
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    });
    child.unref();
  } else {
    const child = spawn('/bin/sh', [updaterPath], { detached: true, stdio: 'ignore' });
    child.unref();
  }
  return { spawned: true };
}

/**
 * Full apply: rotate current->.prev and .new->current via the updater, then
 * the caller exits. Throws when there is nothing staged or not packaged.
 */
function applyStagedUpdate() {
  const exePath = currentExePath();
  if (!exePath) {
    throw new Error('Self-update applies to packaged builds only; in dev, pull the code instead.');
  }
  const paths = stagedPaths(exePath);
  if (!fs.existsSync(paths.newPath)) {
    throw new Error('No staged update found. Download and install first.');
  }
  const moves = [
    { from: paths.currentPath, to: paths.prevPath },
    { from: paths.newPath, to: paths.currentPath },
  ];
  buildUpdaterScript({
    platform: process.platform,
    pid: process.pid,
    moves,
    launchPath: paths.currentPath,
    updaterPath: paths.updaterPath,
  });
  spawnUpdater(paths.updaterPath);
  return { applyInitiated: true, version: downloadJob.version };
}

/** True when a previous-generation binary exists to roll back to. */
function rollbackAvailable() {
  const exePath = currentExePath();
  if (!exePath) return false;
  return fs.existsSync(stagedPaths(exePath).prevPath);
}

/**
 * Rolls back: current->.new (stash), .prev->current, relaunch. Same
 * wait-for-death dance through the updater. Throws when no .prev exists.
 */
function applyRollback() {
  const exePath = currentExePath();
  if (!exePath) {
    throw new Error('Self-update applies to packaged builds only.');
  }
  const paths = stagedPaths(exePath);
  if (!fs.existsSync(paths.prevPath)) {
    throw new Error('No previous version available to roll back to.');
  }
  const moves = [
    { from: paths.currentPath, to: paths.newPath },
    { from: paths.prevPath, to: paths.currentPath },
  ];
  buildUpdaterScript({
    platform: process.platform,
    pid: process.pid,
    moves,
    launchPath: paths.currentPath,
    updaterPath: paths.updaterPath,
  });
  spawnUpdater(paths.updaterPath);
  return { rollbackInitiated: true };
}

module.exports = {
  DOWNLOAD_STATE,
  parseVersion,
  compareVersions,
  currentPlatformKey,
  checkForUpdates,
  startDownload,
  getDownloadProgress,
  verifyStagedFile,
  installStagedUpdate,
  cleanupStaleUpdateFiles,
  buildUpdaterScript,
  spawnUpdater,
  applyStagedUpdate,
  rollbackAvailable,
  applyRollback,
  currentExePath,
  stagedPaths,
};
