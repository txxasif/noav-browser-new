'use strict';
// --- Minimal OpenXML XLSX builder (zero-dependency, Node built-in zlib) ---
const _crcTable = new Uint32Array(256);
for (let i = 0; i < 256; i++) {
  let c = i;
  for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
  _crcTable[i] = c >>> 0;
}
function _crc32(buf) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) c = _crcTable[(c ^ buf[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
function _zipEntries(entries, zlibMod) {
  const localParts = [];
  const cdParts = [];
  let offset = 0;
  const zl = zlibMod || require('zlib');
  for (const entry of entries) {
    const nameBuf = Buffer.from(entry.name, 'utf-8');
    const uncompressed = Buffer.isBuffer(entry.data) ? entry.data : Buffer.from(entry.data, 'utf-8');
    const compressed = zl.deflateRawSync(uncompressed);
    const crc = _crc32(uncompressed);

    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(0x04034b50, 0);
    localHeader.writeUInt16LE(20, 4);
    localHeader.writeUInt16LE(0, 6);
    localHeader.writeUInt16LE(8, 8);
    localHeader.writeUInt16LE(0, 10);
    localHeader.writeUInt16LE(0, 12);
    localHeader.writeUInt32LE(crc, 14);
    localHeader.writeUInt32LE(compressed.length, 18);
    localHeader.writeUInt32LE(uncompressed.length, 22);
    localHeader.writeUInt16LE(nameBuf.length, 26);
    localHeader.writeUInt16LE(0, 28);
    localParts.push(localHeader, nameBuf, compressed);

    const cdHeader = Buffer.alloc(46);
    cdHeader.writeUInt32LE(0x02014b50, 0);
    cdHeader.writeUInt16LE(20, 4);
    cdHeader.writeUInt16LE(20, 6);
    cdHeader.writeUInt16LE(0, 8);
    cdHeader.writeUInt16LE(8, 10);
    cdHeader.writeUInt16LE(0, 12);
    cdHeader.writeUInt16LE(0, 14);
    cdHeader.writeUInt32LE(crc, 16);
    cdHeader.writeUInt32LE(compressed.length, 20);
    cdHeader.writeUInt32LE(uncompressed.length, 24);
    cdHeader.writeUInt16LE(nameBuf.length, 28);
    cdHeader.writeUInt16LE(0, 30);
    cdHeader.writeUInt16LE(0, 32);
    cdHeader.writeUInt16LE(0, 34);
    cdHeader.writeUInt16LE(0, 36);
    cdHeader.writeUInt32LE(0, 38);
    cdHeader.writeUInt32LE(offset, 42);
    cdParts.push(cdHeader, nameBuf);

    offset += localHeader.length + nameBuf.length + compressed.length;
  }
  const cdOffset = offset;
  const cdBuf = Buffer.concat(cdParts);
  const cdSize = cdBuf.length;

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(cdSize, 12);
  eocd.writeUInt32LE(cdOffset, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([...localParts, cdBuf, eocd]);
}
function _escapeXml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\x27/g, '&apos;');
}
function _colName(idx) {
  let name = '';
  let n = idx;
  while (n >= 0) {
    name = String.fromCharCode((n % 26) + 65) + name;
    n = Math.floor(n / 26) - 1;
  }
  return name;
}
function buildXlsx(rows, zlibMod) {
  let sheetDataXml = '';
  for (let r = 0; r < rows.length; r++) {
    const rowNum = r + 1;
    sheetDataXml += `<row r="${rowNum}">`;
    const row = rows[r];
    for (let c = 0; c < row.length; c++) {
      const cellRef = `${_colName(c)}${rowNum}`;
      const val = _escapeXml(row[c]);
      sheetDataXml += `<c r="${cellRef}" t="inlineStr"><is><t>${val}</t></is></c>`;
    }
    sheetDataXml += `</row>`;
  }

  const contentTypesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`;

  const rootRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;

  const workbookXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>`;

  const workbookRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`;

  const sheet1Xml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>${sheetDataXml}</sheetData>
</worksheet>`;

  return _zipEntries([
    { name: '[Content_Types].xml', data: contentTypesXml },
    { name: '_rels/.rels', data: rootRelsXml },
    { name: 'xl/_rels/workbook.xml.rels', data: workbookRelsXml },
    { name: 'xl/workbook.xml', data: workbookXml },
    { name: 'xl/worksheets/sheet1.xml', data: sheet1Xml },
  ], zlibMod);
}

/** Nova Browser Meta APIs (/api/meta-insta/*) + TG Classic start runs here. */
module.exports = function handleMeta(req, res, urlObj, pathname, ctx) {
  const { fs, path, zlib, spawn, execSync, ROOT_DIR, ACCOUNTS_JSON, ACCOUNTS_CSV, ACCOUNTS_TXT, PYTHON_BIN, licenseMgr, slot, reapDeadEngine, broadcastEvent, consumeWorkerLine, sendJson, loadAccounts, getAccounts, storeDbExists, runPython, runPythonJson, syncFilesFromStore, cookieFileFor, readSettings, writeSettings, storedGlobalPassword, killProcessGroup, sseClients, recentLogs, resetWorkerBuffer, feedWorkerStdout, flushWorkerBuffer, backupUserData } = ctx;

  // =========================================================================
  // Nova Browser Meta APIs (/api/meta-insta/*)
  // =========================================================================

  // 1. GET /api/meta-insta/status (also /api/status)
  if ((pathname === '/api/meta-insta/status' || pathname === '/api/status') && req.method === 'GET') {
    (async () => {
      const allAccounts = await loadAccounts();
      const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
      const metaRunning = reapDeadEngine('meta');
      const igRunning = reapDeadEngine('ig');
      const metaSlot = slot('meta');
      const igSlot = slot('ig');
      sendJson(req, res, {
        status: 'SUCCESS',
        tool: 'meta-insta',
        running: metaRunning || igRunning,
        meta_running: metaRunning,
        ig_running: igRunning,
        engineOk: true,
        meta: {
          running: metaRunning,
          concurrency: (metaSlot.config || {}).concurrency || 1,
          mode: 'meta',
          state: metaSlot.proc ? 'RUNNING' : 'IDLE',
        },
        ig: {
          running: igRunning,
          concurrency: (igSlot.config || {}).concurrency || 1,
          mode: 'meta-ig',
          state: igSlot.proc ? 'RUNNING' : 'IDLE',
        },
        concurrency: ((metaRunning ? metaSlot.config : igSlot.config) || {}).concurrency || 1,
        total_accounts: accounts.length,
        created: accounts.length,
        mode: metaRunning ? 'meta' : (igRunning ? 'meta-ig' : 'meta'),
        state: (metaRunning || igRunning) ? 'RUNNING' : 'IDLE'
      });
    })();
    return true;
  }

  // 2. GET /api/meta-insta/accounts (also /api/accounts)
  if ((pathname === '/api/meta-insta/accounts' || pathname === '/api/accounts') && req.method === 'GET') {
    (async () => {
      const allAccounts = await loadAccounts();
      const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
      sendJson(req, res, {
        status: 'SUCCESS',
        accounts: accounts
      });
    })();
    return true;
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
    return true;
  }

  // 2c. GET /api/meta-insta/export-combo?kind=meta|ig — bulk combo download.
  // meta: `email|password` lines only, nothing else.
  // ig: `username|password|name=value; ...` lines (Nova combo shape).
  if (pathname === '/api/meta-insta/export-combo' && req.method === 'GET') {
    (async () => {
      const kind = (urlObj.searchParams.get('kind') || '').trim().toLowerCase() === 'ig' ? 'ig' : 'meta';
      const allAccounts = await loadAccounts();
      const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
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
    return true;
  }

  // 2c2. GET /api/meta-insta/export-xlsx — 2FA accounts XLSX export (Telegram Bot format: Username, Password, 2FA Key)
  if (pathname === '/api/meta-insta/export-xlsx' && req.method === 'GET') {
    (async () => {
      await syncFilesFromStore();
      const allAccounts = await loadAccounts();
      const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
      const isIg = (a) => String((a && a.status) || '') !== 'MetaCreated';
      const rows = [];
      for (const a of accounts) {
        if (!isIg(a)) continue;
        const key = String(a.twofa_secret || a.twofa_key || a.totp_secret || '').trim();
        if (!key) continue;
        const username = a.instagram_username || a.username || '';
        const password = a.password || '';
        rows.push([username, password, key]);
      }
      const xlsxBuf = buildXlsx(rows, zlib);
      res.writeHead(200, {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': 'attachment; filename="instagram_accounts_2fa.xlsx"'
      });
      res.end(xlsxBuf);
    })();
    return true;
  }

  // 2d. GET/POST /api/meta-insta/settings — dashboard settings (global password)
  if (pathname === '/api/meta-insta/settings') {
    if (req.method === 'GET') {
      const s = readSettings();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', globalPassword: String(s.globalPassword || '') }));
      return true;
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
      return true;
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

    // Replay recent activity so terminal immediately displays logs on connection or page refresh.
    //
    // Marked `replay: true` ON PURPOSE: the client shows these for continuity,
    // but must NOT re-raise operator ALERTS from them. Without the marker every
    // page refresh / SSE reconnect re-delivered the last 150 events and
    // re-fired their toasts — so an old "Telegram session is dead" kept
    // reappearing long after the condition cleared (observed 2026-10-01:
    // restarting the server did not stop the toasts because the replay put the
    // old lines back on the wire).
    for (const item of recentLogs) {
      try {
        res.write(`data: ${JSON.stringify(Object.assign({}, item, { replay: true }))}\n\n`);
      } catch (e) {}
    }

    req.on('close', () => {
      sseClients.delete(res);
    });
    return true;
  }
  if ((pathname === '/api/meta-insta/start' || pathname === '/api/loop/start') && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      let opts = { concurrency: 1, target: 0, delay: 4, headless: true, mail: 'mailtd', captcha: 'extension', start_stagger_ms: null };
      try {
        if (body) opts = Object.assign(opts, JSON.parse(body));
      } catch (e) {}

      // Dashboard workspaces: 'meta' = Meta-only, 'meta-ig' = full Meta -> IG join.
      const mode = (opts.mode === 'meta-ig') ? 'meta-ig' : 'meta';
      const targetSlot = (mode === 'meta-ig') ? 'ig' : 'meta';
      const currentSlot = slot(targetSlot);

      if (reapDeadEngine(targetSlot) || currentSlot.inFlight) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ERROR',
          error: `${targetSlot === 'ig' ? 'Instagram' : 'Meta'} creator is already actively running.`
        }));
        return;
      }

      currentSlot.inFlight = true;
      const releaseStart = () => { currentSlot.inFlight = false; };

      // License Gate: Ensure machine has active license before starting automation
      let licCheck;
      try {
        licCheck = await licenseMgr.validateOrActivateLicense(null, false);
      } catch (licenseErr) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'License validation failed: ' + licenseErr.message }));
        releaseStart();
        return;
      }
      if (!licCheck.isValid) {
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'UNLICENSED',
          error: `Active license required to start Meta Creator (${licCheck.status}: ${licCheck.message || 'Please activate in Subscription.'})`,
          hwid: licCheck.hwid
        }));
        releaseStart();
        return;
      }

      // The dashboard value is authoritative.  There is no RAM pre-flight,
      // automatic reduction, or watchdog in the creator runtime: the user
      // explicitly controls the number of browser slots.
      const requestedConcurrency = Number(opts.concurrency);
      if (!Number.isInteger(requestedConcurrency) || requestedConcurrency < 1) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ERROR',
          error: 'Parallel must be a whole number of 1 or more. No automatic RAM reduction is applied.'
        }));
        releaseStart();
        return;
      }
      const concurrency = requestedConcurrency;
      const headless = opts.headless !== false;
      const target = parseInt(opts.target || 0, 10);
      const delay = Math.max(1, parseInt(opts.delay || 4, 10));
      let startStaggerMs = null;
      if (opts.start_stagger_ms !== undefined && opts.start_stagger_ms !== null && String(opts.start_stagger_ms).trim() !== '') {
        startStaggerMs = Number(opts.start_stagger_ms);
        if (!Number.isInteger(startStaggerMs) || startStaggerMs < 0 || startStaggerMs > 10000) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            status: 'ERROR',
            error: 'start_stagger_ms must be a whole number from 0 to 10000.'
          }));
          releaseStart();
          return;
        }
      }
      const mail = 'mailtd';
      const captcha = opts.captcha_mode || opts.captcha || 'extension';
      // Worker expects 'meta-only' for Meta-only, 'meta-ig' for Meta -> IG
      const workerMode = (mode === 'meta-ig') ? 'meta-ig' : 'meta-only';
      // 2FA Key extraction: strictly enabled only for IG Creator when explicitly checked
      const twofa = (mode === 'meta-ig') && Boolean(opts.twofa);
      // Follow step: the account follows 5 suggested profiles after joining
      // (recorded as `followed` on the account so the PayGo pool can skip it).
      // Dashboard switch; default ON (unchanged behaviour for older clients).
      const follow = opts.follow !== false;
      // Follow transport: 'ui' (browser, default), 'api' (private API), or 'multi' (multi-insta engine)
      const sw = (v) => (v === true ? '1' : '0');
      const rawMode = String(opts.follow_mode || '').toLowerCase();
      const followMode = (rawMode === 'api' || rawMode === 'multi' || rawMode === 'multi_insta') ? rawMode : 'ui';
      // Global password: request override, else the saved dashboard setting.
      const newPassword = String(opts.new_password || storedGlobalPassword() || '').trim().slice(0, 128);
      // Optional fixed username (workspace field). Also env-only.
      const newUsername = String(opts.new_username || '').trim().slice(0, 64);

      currentSlot.config = { concurrency, headless, target, delay, mail, captcha, mode, start_stagger_ms: startStaggerMs, twofa, follow, follow_mode: followMode };

      const args = [
        path.join(ROOT_DIR, 'worker.py'),
        '--concurrency', String(concurrency),
        '--target', String(target),
        '--delay', String(delay),
        '--mail', mail,
        '--captcha', captcha,
        '--mode', workerMode
      ];
      if (headless) args.push('--headless');
      if (twofa) args.push('--twofa');
      if (startStaggerMs !== null) args.push('--start-stagger-ms', String(startStaggerMs));

      console.log(`[MetaCreator] Starting ${targetSlot} worker loop: ${PYTHON_BIN} ${args.join(' ')}`);

      const isWin = process.platform === 'win32';
      const defaultBrowsersPath = fs.existsSync(path.join(ROOT_DIR, '_internal', 'ms-playwright'))
        ? path.join(ROOT_DIR, '_internal', 'ms-playwright')
        : path.join(ROOT_DIR, 'engine', 'ms-playwright');

      try {
        resetWorkerBuffer(targetSlot);
        currentSlot.proc = spawn(PYTHON_BIN, args, {
          cwd: ROOT_DIR,
          detached: !isWin,
          windowsHide: true,
          env: Object.assign({}, process.env, {
            PYTHONUNBUFFERED: '1',
            PYTHONUTF8: '1',
            PYTHONIOENCODING: 'utf-8',
            PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH || defaultBrowsersPath,
            // Follow switch -> the engine's documented follow tunables. "0"
            // makes ig_follow_suggested() a no-op (step skipped entirely);
            // otherwise it follows 5 (the count PayGo's cookie task mandates).
            INSTA_FOLLOW_AFTER_LOGIN: follow ? '1' : '0',
            INSTA_FOLLOW_COUNT: follow ? '5' : '0',
            INSTA_FOLLOW_MODE: followMode,
            INSTA_API_BIO: sw(opts.api_bio),
            INSTA_API_AVATAR: sw(opts.api_avatar),
            INSTA_API_POST: sw(opts.api_post),
            ...(newPassword ? { META_NEW_PASSWORD: newPassword } : {}),
            ...(newUsername ? { META_NEW_USERNAME: newUsername } : {})
          })
        });
      } catch (spawnErr) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: `Failed to spawn ${targetSlot} worker: ` + spawnErr.message }));
        releaseStart();
        return;
      }

      broadcastEvent({
        type: 'status',
        pipeline: 'meta',
        engine: targetSlot,
        running: true,
        concurrency,
        target,
        headless,
        mode,
        twofa,
        follow
      });
      broadcastEvent({
        type: 'loop_started',
        pipeline: 'meta',
        engine: targetSlot,
        concurrency,
        mode
      });

      const rlHandle = ctx.runlog ? ctx.runlog.start(mode === 'meta' ? 'metainsta' : 'instagram', { argv: args, route: mode === 'meta' ? 'meta' : 'ig' }) : null;
      currentSlot.runlog = rlHandle;

      currentSlot.proc.stdout.on('data', data => {
        if (rlHandle && ctx.runlog) ctx.runlog.line(rlHandle, data);
        for (const line of feedWorkerStdout(data, targetSlot)) consumeWorkerLine(line, targetSlot);
      });

      currentSlot.proc.stderr.on('data', data => {
        if (rlHandle && ctx.runlog) ctx.runlog.line(rlHandle, data);
        const text = data.toString('utf-8').trim();
        if (!text) return;
        if (/socket\.send\(\) raised exception\.?/i.test(text)) return;
        console.error(`[${targetSlot.toUpperCase()} STDERR] ${text}`);
        broadcastEvent({ type: 'log', pipeline: 'meta', engine: targetSlot, message: `[STDERR] ${text}` });
      });

      currentSlot.proc.on('error', spawnErr => {
        console.error(`[MetaCreator] ${targetSlot} worker process error: ${spawnErr.message}`);
        broadcastEvent({ type: 'log', pipeline: 'meta', engine: targetSlot, message: `[Worker] ${spawnErr.message}` });
        releaseStart();
        if (rlHandle && ctx.runlog) ctx.runlog.end(rlHandle);
        if (currentSlot.proc) currentSlot.proc = null;
      });

      currentSlot.proc.on('close', code => {
        flushWorkerBuffer(targetSlot);
        if (rlHandle && ctx.runlog) ctx.runlog.end(rlHandle);
        console.log(`[MetaCreator] ${targetSlot} loop process exited with code ${code}`);
        broadcastEvent({ type: 'loop_stopped', pipeline: 'meta', engine: targetSlot, exit_code: code, mode });
        broadcastEvent({ type: 'status', pipeline: 'meta', engine: targetSlot, running: false, mode });
        currentSlot.proc = null;
        currentSlot.inFlight = false;
      });

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', message: `${targetSlot === 'ig' ? 'Instagram' : 'Meta'} creator started with ${concurrency} concurrent windows.` }));
      releaseStart();
    });
    return true;
  }
  // 5. POST /api/meta-insta/stop (also /api/loop/stop)
  if ((pathname === '/api/meta-insta/stop' || pathname === '/api/loop/stop') && req.method === 'POST') {
    let stopBody = '';
    req.on('data', chunk => { stopBody += chunk; });
    req.on('end', () => {
      let opts = {};
      try { if (stopBody) opts = JSON.parse(stopBody); } catch (e) {}
      const kind = (opts.kind || urlObj.searchParams.get('kind') || (opts.mode === 'meta-ig' ? 'ig' : (opts.mode === 'meta' ? 'meta' : ''))).trim();

      const stopSlot = (targetName) => {
        const s = slot(targetName);
        if (!s) return;
        if (s.inFlight && !s.proc) {
          s.inFlight = false;
        }
        if (s.proc) {
          killProcessGroup(s.proc, 'SIGINT');
          const proc = s.proc;
          setTimeout(() => {
            if (s.proc === proc) {
              killProcessGroup(proc, 'SIGKILL');
              s.proc = null;
            }
          }, 3000);
        }
        broadcastEvent({ type: 'loop_stopped', pipeline: 'meta', engine: targetName, message: `${targetName === 'ig' ? 'Instagram' : 'Meta'} engine stopped by user request.` });
        broadcastEvent({ type: 'status', pipeline: 'meta', engine: targetName, running: false, mode: targetName === 'ig' ? 'meta-ig' : 'meta' });
      };

      if (kind === 'meta' || kind === 'ig') {
        stopSlot(kind);
      } else {
        stopSlot('meta');
        stopSlot('ig');
        stopSlot('metainsta');
      }

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', message: `${kind ? (kind === 'ig' ? 'Instagram' : 'Meta') : 'Engine'} stopped.` }));
    });
    return true;
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
    return true;
  }

  // 6b. POST /api/meta-insta/purge-damaged {kind: 'meta'|'ig', confirm:'CLEAR'}
  // Deletes only DAMAGED rows in one workspace list (Failed/Banned, dead
  // session, or 3+ failed submits). Healthy rows and Telegram pool rows are
  // never touched.
  if (pathname === '/api/meta-insta/purge-damaged' && req.method === 'POST') {
    let purgeBody = '';
    req.on('data', c => { purgeBody += c; });
    req.on('end', async () => {
      let kind = 'ig';
      let confirm = '';
      try {
        const parsed = JSON.parse(purgeBody || '{}');
        if (parsed.kind === 'meta') kind = 'meta';
        confirm = String(parsed.confirm || '');
      } catch (e) {}
      if (confirm !== 'CLEAR') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Confirmation required: POST {"kind":"ig"|"meta","confirm":"CLEAR"}.' }));
        return;
      }
      const backupDir = backupUserData('purge-damaged-' + kind);
      if (storeDbExists()) {
        const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_backup.py', ['purge-damaged', '--kind', kind], 120000);
        if (!r || !r.ok) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Could not remove damaged accounts: ' + ((r && r.error) || 'no output') }));
          return;
        }
        broadcastEvent({ type: 'accounts_reset' });
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'SUCCESS',
          kind,
          removed: r.removed || 0,
          backup: backupDir || null
        }));
        return;
      }
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'Account database not found.' }));
    });
    return true;
  }
  // 6c. POST /api/meta-insta/clear-kind {kind: 'meta'|'ig', confirm:'CLEAR'}
  // Deletes only one workspace list (Meta-only rows or IG-joined rows).
  // Telegram pool rows are never touched.
  if (pathname === '/api/meta-insta/clear-kind' && req.method === 'POST') {
    let clearBody = '';
    req.on('data', c => { clearBody += c; });
    req.on('end', async () => {
      let kind = 'ig';
      let confirm = '';
      try {
        const parsed = JSON.parse(clearBody || '{}');
        if (parsed.kind === 'meta') kind = 'meta';
        confirm = String(parsed.confirm || '');
      } catch (e) {}
      if (confirm !== 'CLEAR') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Confirmation required: POST {"kind":"ig"|"meta","confirm":"CLEAR"}.' }));
        return;
      }
      const backupDir = backupUserData('clear-' + kind);
      if (storeDbExists()) {
        const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_backup.py', ['clear-kind', '--kind', kind], 120000);
        if (!r || !r.ok) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', error: 'Could not clear the list: ' + ((r && r.error) || 'no output') }));
          return;
        }
        broadcastEvent({ type: 'accounts_reset' });
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'SUCCESS',
          kind,
          deleted: r.deleted || 0,
          backup: backupDir || null
        }));
        return;
      }
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'Account database not found.' }));
    });
    return true;
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
    return true;
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
    return true;
  }

  // 9. POST /api/meta-insta/cleanup
  if (pathname === '/api/meta-insta/cleanup' && req.method === 'POST') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', removed: 0 }));
    return true;
  }

  // 10. GET /api/meta-insta/export (also /api/export)
  if ((pathname.startsWith('/api/meta-insta/export') || pathname === '/api/export') && req.method === 'GET') {
    const format = (urlObj.searchParams.get('format') || 'csv').toLowerCase();
    const kind = (urlObj.searchParams.get('kind') || '').toLowerCase() === 'ig' ? 'ig' : 'meta';
    (async () => {
      await syncFilesFromStore();

      if (format === 'xlsx') {
        const allAccounts = await loadAccounts();
        const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
        const isIg = (a) => String((a && a.status) || '') !== 'MetaCreated';
        const rows = [];
        for (const a of accounts) {
          if (!isIg(a)) continue;
          const key = String(a.twofa_secret || a.twofa_key || a.totp_secret || '').trim();
          if (!key) continue;
          const username = a.instagram_username || a.username || '';
          const password = a.password || '';
          rows.push([username, password, key]);
        }
        const xlsxBuf = buildXlsx(rows, zlib);
        res.writeHead(200, {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': 'attachment; filename="instagram_accounts_2fa.xlsx"'
        });
        res.end(xlsxBuf);
        return;
      }

      if (format === 'txt') {
        if (fs.existsSync(ACCOUNTS_TXT)) {
          res.writeHead(200, {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename="meta_accounts.txt"'
          });
          fs.createReadStream(ACCOUNTS_TXT).pipe(res);
        } else {
          const allAccounts = getAccounts();
          const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
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
        const allAccounts = getAccounts();
        const accounts = allAccounts.filter(a => (a.target || '') !== 'telegram');
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
    return true;
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
    return true;
  }

  // 12. POST /api/multi-insta/follow — run multi_insta.exe engine follow pipeline for testing
  if (pathname === '/api/multi-insta/follow' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let opts = {};
      try {
        opts = JSON.parse(body || '{}');
      } catch (e) {}
      const targetFollows = Math.max(1, Math.min(20, parseInt(opts.count || opts.target || 5, 10)));
      const isHeadless = Boolean(opts.headless);
      const args = [path.join(ROOT_DIR, 'multi_insta_engine.py'), '--target', String(targetFollows)];
      if (isHeadless) args.push('--headless');
      if (opts.pool) {
        args.push('--pool', String(parseInt(opts.pool, 10) || 1));
      } else if (opts.account_id || opts.id || opts.account) {
        args.push('--account', String(opts.account_id || opts.id || opts.account));
      } else if (opts.cookie) {
        args.push('--cookie', String(opts.cookie));
      } else {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Must provide account_id, cookie, or pool' }));
        return;
      }

      console.log(`[MultiInsta] Running follow engine test: ${PYTHON_BIN} ${args.join(' ')}`);
      const proc = spawn(PYTHON_BIN, args, { cwd: ROOT_DIR });
      let stdout = '';
      let stderr = '';
      proc.stdout.on('data', d => { stdout += d.toString(); });
      proc.stderr.on('data', d => { stderr += d.toString(); });
      proc.on('close', code => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: code === 0 ? 'SUCCESS' : 'ERROR',
          code,
          stdout,
          stderr
        }));
      });
    });
    return true;
  }

  return false;
};

