'use strict';
/** Nova Browser Meta APIs (/api/meta-insta/*) + TG Classic start runs here. */
module.exports = function handleMeta(req, res, urlObj, pathname, ctx) {
  const { fs, path, spawn, execSync, ROOT_DIR, ACCOUNTS_JSON, ACCOUNTS_CSV, ACCOUNTS_TXT, PYTHON_BIN, licenseMgr, slot, reapDeadEngine, broadcastEvent, consumeWorkerLine, sendJson, loadAccounts, getAccounts, storeDbExists, runPython, syncFilesFromStore, cookieFileFor, readSettings, writeSettings, storedGlobalPassword, killProcessGroup, sseClients, recentLogs, resetWorkerBuffer, feedWorkerStdout, flushWorkerBuffer } = ctx;

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
        running: reapDeadEngine(),
        engineOk: true,
        // slot().config is nulled on /stop, so these MUST be guarded —
        // an unguarded read crashed the server on the first status poll after
        // any stop ("Cannot read properties of null (reading 'concurrency')").
        concurrency: (slot().config || {}).concurrency || 1,
        total_accounts: accounts.length,
        created: accounts.length,
        mode: (slot().config || {}).mode || 'meta',
        state: slot().proc ? 'RUNNING' : 'IDLE'
      });
    })();
    return true;
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

    // Replay recent activity so terminal immediately displays logs on connection or page refresh
    for (const item of recentLogs) {
      try {
        res.write(`data: ${JSON.stringify(item)}\n\n`);
      } catch (e) {}
    }

    req.on('close', () => {
      sseClients.delete(res);
    });
    return true;
  }
  if ((pathname === '/api/meta-insta/start' || pathname === '/api/loop/start') && req.method === 'POST') {
    if (reapDeadEngine() || slot().inFlight) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'Meta creator is already actively running.' }));
      return true;
    }

    slot().inFlight = true;
    const releaseStart = () => { slot().inFlight = false; };
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('aborted', releaseStart);
    req.on('end', async () => {
      let opts = { concurrency: 1, target: 0, delay: 4, headless: true, mail: 'mailtd', captcha: 'extension', start_stagger_ms: null };
      try {
        if (body) opts = Object.assign(opts, JSON.parse(body));
      } catch (e) {}

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
      if (!Number.isInteger(requestedConcurrency) || requestedConcurrency < 1 || requestedConcurrency > 50) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ERROR',
          error: 'Parallel must be a whole number from 1 to 50. No automatic RAM reduction is applied.'
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
      // Dashboard workspaces: 'meta' = Meta-only, 'meta-ig' = full Meta -> IG join.
      // slot().config + status events keep the dashboard-facing mode ('meta'),
      // but the worker only treats 'meta-only' as Meta-only, so translate here.
      const mode = (opts.mode === 'meta-ig') ? 'meta-ig' : 'meta';
      const workerMode = (mode === 'meta-ig') ? 'meta-ig' : 'meta-only';
      // Global password: request override, else the saved dashboard setting.
      // Passed via env (never argv) so it can't leak into logs or `ps`.
      const newPassword = String(opts.new_password || storedGlobalPassword() || '').trim().slice(0, 128);
      // Optional fixed username (workspace field). Also env-only.
      const newUsername = String(opts.new_username || '').trim().slice(0, 64);

      slot().config = { concurrency, headless, target, delay, mail, captcha, mode, start_stagger_ms: startStaggerMs };

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
      if (startStaggerMs !== null) args.push('--start-stagger-ms', String(startStaggerMs));

      console.log(`[MetaCreator] Starting worker loop: ${PYTHON_BIN} ${args.join(' ')}`);

      const isWin = process.platform === 'win32';
      const defaultBrowsersPath = fs.existsSync(path.join(ROOT_DIR, '_internal', 'ms-playwright'))
        ? path.join(ROOT_DIR, '_internal', 'ms-playwright')
        : path.join(ROOT_DIR, 'engine', 'ms-playwright');

      try {
        resetWorkerBuffer();
        slot().proc = spawn(PYTHON_BIN, args, {
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
        releaseStart();
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

      const rlHandle = ctx.runlog ? ctx.runlog.start(mode === 'meta' ? 'metainsta' : 'instagram', { argv: args }) : null;
      slot().runlog = rlHandle;

      slot().proc.stdout.on('data', data => {
        if (rlHandle && ctx.runlog) ctx.runlog.line(rlHandle, data);
        // Child-process stdout is a byte stream; a JSON event can be split
        // across chunks. Keep the partial line instead of dropping/corrupting
        // it during a high-volume parallel run.
        for (const line of feedWorkerStdout(data)) consumeWorkerLine(line);
      });

      slot().proc.stderr.on('data', data => {
        if (rlHandle && ctx.runlog) ctx.runlog.line(rlHandle, data);
        const text = data.toString('utf-8').trim();
        if (!text) return;
        // Playwright's node driver spews this whenever a browser/driver socket
        // closes (e.g. on Stop, or a crashed browser). It's noise, not
        // actionable — don't flood the dashboard with it.
        if (/socket\.send\(\) raised exception\.?/i.test(text)) return;
        console.error(`[Worker STDERR] ${text}`);
        broadcastEvent({ type: 'log', message: `[STDERR] ${text}` });
      });

      slot().proc.on('error', spawnErr => {
        console.error(`[MetaCreator] Worker process error: ${spawnErr.message}`);
        broadcastEvent({ type: 'log', message: `[Worker] ${spawnErr.message}` });
        releaseStart();
        if (rlHandle && ctx.runlog) ctx.runlog.end(rlHandle);
        if (slot().proc) slot().proc = null;
      });

      slot().proc.on('close', code => {
        flushWorkerBuffer();
        if (rlHandle && ctx.runlog) ctx.runlog.end(rlHandle);
        console.log(`[MetaCreator] Loop process exited with code ${code}`);
        broadcastEvent({ type: 'loop_stopped', exit_code: code });
        broadcastEvent({ type: 'status', running: false });
        slot().proc = null;
        slot().inFlight = false;
      });

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', message: `Meta creator started with ${concurrency} concurrent windows.` }));
      releaseStart();
    });
    return true;
  }
  // 5. POST /api/meta-insta/stop (also /api/loop/stop)
  if ((pathname === '/api/meta-insta/stop' || pathname === '/api/loop/stop') && req.method === 'POST') {
    if (slot().inFlight && !slot().proc) {
      res.writeHead(409, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'Start is still being initialized; try Stop again in a moment.' }));
      return true;
    }
    if (slot().proc) {
      killProcessGroup(slot().proc, 'SIGINT');
      const proc = slot().proc;
      setTimeout(() => {
        if (slot().proc === proc) {
          killProcessGroup(proc, 'SIGKILL');
          slot().proc = null;
        }
      }, 3000);
    }
    broadcastEvent({ type: 'loop_stopped', message: 'Engine stopped by user request.' });
    broadcastEvent({ type: 'status', running: false });
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', message: 'Engine stopped.' }));
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
  return false;
};
