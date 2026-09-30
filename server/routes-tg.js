const paygoOrchestrator = require('./paygo-orchestrator');
let _orchestratorInit = false;

module.exports = function handleTg(req, res, urlObj, pathname, ctx) {
  if (!_orchestratorInit) {
    _orchestratorInit = true;
    paygoOrchestrator.init(ctx);
  }
  const { fs, path, spawn, ROOT_DIR, PYTHON_BIN, licenseMgr, slot, reapDeadEngine, broadcastEvent, consumeWorkerLine, sendJson, runPythonJson, resolveScript, loadAccounts, readTgPool, tgPoolUsable, readEnabledBots, defaultBot, storedGlobalPassword, resetWorkerBuffer, feedWorkerStdout, flushWorkerBuffer, fastpayCount, fastpayList, fastpayAdd, fastpayRemove } = ctx;

  // ---- TG balance: single-flight + short TTL cache ------------------------
  // A .session file serves ONE Telethon client at a time. Two concurrent
  // `tg_balance.py` processes would both try to open all six session files and
  // collide with "database is locked" (observed 2026-09-30: two workers were
  // running and a double-clicked button produced "database is locked" rows).
  // So the server runs AT MOST ONE balance reader, shares it with every caller
  // that asks while it is in flight, and answers a re-click inside BAL_TTL_MS
  // straight from cache. `?fresh=1` bypasses the TTL (still serialized).
  const BAL_TTL_MS = 30000;
  let _balCache = null;      // { at, data }
  let _balInFlight = null;   // shared Promise
  let _balLock = Promise.resolve();   // mutex: no two readers, ever

  function withBalLock(fn) {
    const run = _balLock.then(() => fn());
    _balLock = run.then(() => {}, () => {});
    return run;
  }

  async function balanceAll(fresh) {
    if (!fresh && _balCache && (Date.now() - _balCache.at) < BAL_TTL_MS) {
      return { data: Object.assign({}, _balCache.data, { cached: true }), logged: false };
    }
    if (_balInFlight) return { data: await _balInFlight, logged: false };
    _balInFlight = withBalLock(async () => {
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_balance.py',
        ['--all', '--json'], 300000);
      const data = r || { ok: false, error: 'no result' };
      if (data.ok) _balCache = { at: Date.now(), data };
      return data;
    });
    try {
      return { data: await _balInFlight, logged: true };
    } finally {
      _balInFlight = null;
    }
  }

  function logBalances(r) {
    try {
      const t = (r && r.totals) || {};
      const parts = [];
      if (t.taskly != null) parts.push('Taskly $' + Number(t.taskly || 0).toFixed(2));
      if (t.paygo != null) parts.push('PayGo $' + Number(t.paygo || 0).toFixed(2));
      if (t.fastpay != null) parts.push('FastPay $' + Number(t.fastpay || 0).toFixed(2));
      const secs = (r && r.elapsed_s != null) ? (' in ' + r.elapsed_s + 's') : '';
      broadcastEvent({ type: 'log', pipeline: 'telegram',
        message: '[tg] Balances (' + ((r && r.count) || 0) + ' accounts): '
          + parts.join(' · ') + ' · TOTAL $' + Number(t.grand || 0).toFixed(2) + secs });
    } catch (e) {}
  }

  // ---- TG balance (both bots: Taskly + PayGo) ----
  // Reads the 💰 Balance key from the account's Telethon session. A .session
  // file serves ONE client at a time, so this is refused while the account is
  // leased by a worker.
  if (pathname === '/api/tg/mtproto/balance' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const id = String(b.id || '').trim();
      if (!id) { sendJson(req, res, { ok: false, error: 'id required' }, 400); return; }
      const r = await withBalLock(() => runPythonJson(PYTHON_BIN, ROOT_DIR,
        'tg_balance.py', ['--id', id, '--json'], 120000));
      sendJson(req, res, r || { ok: false, error: 'no result' }, r && r.ok ? 200 : 500);
    });
    return true;
  }

  if (pathname === '/api/tg/mtproto/balance_all' && req.method === 'POST') {
    (async () => {
      const fresh = urlObj.searchParams.get('fresh') === '1';
      const { data, logged } = await balanceAll(fresh);
      if (logged) logBalances(data);
      sendJson(req, res, data, data && data.ok ? 200 : 500);
    })();
    return true;
  }
  // =============== end TG balance ===============

  // ---- TG pool: enable/disable + remove (per-profile task switch) ----
  // tg_accounts.acquire() already skips enabled:false, so disabling just stops
  // the profile receiving tasks; the session and profile dir are untouched.
  if (pathname === '/api/tg/accounts/toggle' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const id = String(b.id || '').trim();
      if (!id) { sendJson(req, res, { ok: false, error: 'id required' }, 400); return; }
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_toggle.py',
        ['--id', id, '--enabled', b.enabled ? '1' : '0'], 60000);
      sendJson(req, res, r || { ok: false, error: 'no result' }, r && r.ok ? 200 : 400);
    });
    return true;
  }
  if (pathname === '/api/tg/accounts/remove' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const id = String(b.id || '').trim();
      if (!id) { sendJson(req, res, { ok: false, error: 'id required' }, 400); return; }
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_toggle.py',
        ['--id', id, '--remove'], 60000);
      sendJson(req, res, r || { ok: false, error: 'no result' }, r && r.ok ? 200 : 400);
    });
    return true;
  }
  if (pathname === '/api/tg/accounts/update' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const id = String(b.id || '').trim();
      if (!id) { sendJson(req, res, { ok: false, error: 'id required' }, 400); return; }
      const args = ['--id', id];
      if (b.enabled !== undefined) args.push('--enabled', b.enabled ? '1' : '0');
      if (b.name !== undefined) args.push('--name', String(b.name));
      if (b.phone !== undefined) args.push('--phone', String(b.phone));
      if (args.length <= 2) { sendJson(req, res, { ok: false, error: 'nothing to update' }, 400); return; }
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_toggle.py', args, 60000);
      sendJson(req, res, r || { ok: false, error: 'no result' }, r && r.ok ? 200 : 400);
    });
    return true;
  }
  if (pathname === '/api/tg/pool/enable_all' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_toggle.py',
        ['--all', b.enabled ? '1' : '0'], 120000);
      sendJson(req, res, r || { ok: false, error: 'no result' }, r && r.ok ? 200 : 400);
    });
    return true;
  }
  // =============== end TG pool controls ===============

  // ---- MTProto API credentials (data/tg_mtproto.json) ----
  // Step 0 of Add-MTProto: one api_id/api_hash pair works for ALL accounts (it
  // identifies the app, not the account). GET reports whether it is present;
  // POST saves it. Never returned to the client in full (hash masked).
  if (pathname === '/api/tg/mtproto/credentials' && req.method === 'GET') {
    try {
      const f = path.join(ROOT_DIR, 'data', 'tg_mtproto.json');
      let cfg = {};
      if (fs.existsSync(f)) { try { cfg = JSON.parse(fs.readFileSync(f, 'utf8')) || {}; } catch (e) {} }
      const envId = process.env.TG_API_ID || '';
      const envHash = process.env.TG_API_HASH || '';
      const apiId = String(cfg.api_id || envId || '');
      const apiHash = String(cfg.api_hash || envHash || '');
      sendJson(req, res, {
        ok: true,
        has_credentials: !!(apiId && apiHash),
        api_id: apiId || null,
        api_hash_masked: apiHash ? (apiHash.slice(0, 4) + '\u2026' + apiHash.slice(-4)) : null,
        source: cfg.api_id ? 'file' : (envId ? 'env' : 'none'),
      });
    } catch (e) {
      sendJson(req, res, { ok: false, error: String(e.message || e) }, 500);
    }
    return true;
  }

  if (pathname === '/api/tg/mtproto/credentials' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const apiId = String(b.api_id || '').trim();
      const apiHash = String(b.api_hash || '').trim();
      if (!apiId || !/^\d+$/.test(apiId)) {
        sendJson(req, res, { ok: false, error: 'api_id must be a number (from my.telegram.org)' }, 400); return;
      }
      if (!apiHash || apiHash.length < 16) {
        sendJson(req, res, { ok: false, error: 'api_hash looks too short (32 hex chars expected)' }, 400); return;
      }
      try {
        const dir = path.join(ROOT_DIR, 'data');
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const f = path.join(dir, 'tg_mtproto.json');
        fs.writeFileSync(f, JSON.stringify({ api_id: Number(apiId), api_hash: apiHash }, null, 2));
        try { fs.chmodSync(f, 0o600); } catch (e) {}
        sendJson(req, res, { ok: true, message: 'API credentials saved to data/tg_mtproto.json' });
      } catch (e) {
        sendJson(req, res, { ok: false, error: 'could not save credentials: ' + e.message }, 500);
      }
    });
    return true;
  }
  // =============== end MTProto credentials ===============

  // ---- TG account ADD (MTProto / Telethon) ----
  // Spawns tg_login_mtproto.py with the JSON payload on STDIN so the login code
  // and (if 2FA) the password NEVER appear in `ps` argv. The script prints ONE
  // JSON line; we relay it verbatim. `needs_password:true` means 2FA is on and
  // the UI must prompt, then call /api/tg/mtproto/verify again with `password`.
  function runTgLogin(mode, payload) {
    return new Promise((resolve) => {
      let child;
      // api_id/api_hash arrive as _api_id/_api_hash (they are set once per
      // account, not per-login). Pass them via ENV so they never appear in
      // `ps` argv, then drop the underscore keys before writing stdin.
      const env = Object.assign({}, process.env, { PYTHONUNBUFFERED: '1', PYTHONUTF8: '1' });
      if (payload && payload._api_id) env.TG_API_ID = String(payload._api_id);
      if (payload && payload._api_hash) env.TG_API_HASH = String(payload._api_hash);
      const stdinPayload = Object.assign({}, payload || {});
      delete stdinPayload._api_id;
      delete stdinPayload._api_hash;
      try {
        child = spawn(PYTHON_BIN, [resolveScript('tg_login_mtproto.py'), mode], {
          cwd: ROOT_DIR, windowsHide: true, env,
        });
      } catch (e) { resolve({ ok: false, error: 'spawn failed: ' + e.message }); return; }
      let out = '', err = '';
      const t = setTimeout(() => { try { child.kill('SIGKILL'); } catch (e) {} resolve({ ok: false, error: 'timeout' }); }, 180000);
      child.stdout.on('data', d => { out += d.toString(); });
      child.stderr.on('data', d => { err += d.toString(); });
      child.on('error', e => { clearTimeout(t); resolve({ ok: false, error: String(e.message || e) }); });
      child.on('close', () => {
        clearTimeout(t);
        const line = out.trim().split('\n').filter(Boolean).pop() || '';
        try { resolve(JSON.parse(line)); }
        catch (e) { resolve({ ok: false, error: (err || out || 'no output').trim().slice(0, 400) }); }
      });
      try { child.stdin.write(JSON.stringify(stdinPayload)); child.stdin.end(); }
      catch (e) { /* child already gone */ }
    });
  }

  if ((pathname === '/api/tg/mtproto/send_code' || pathname === '/api/tg/mtproto/verify')
      && req.method === 'POST') {
    const mode = pathname.endsWith('send_code') ? '--send-code' : '--verify';
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', async () => {
      let payload = {};
      try { payload = JSON.parse(body || '{}'); } catch (e) {}
      const res1 = await runTgLogin(mode, payload);
      sendJson(req, res, res1);
    });
    return true;
  }
  // =============== end TG account ADD ===============

  // ================= TG Classic (/api/tg/*) =================
  // Meta -> Instagram -> Taskly submit. Runs worker.py --coupled (one browser
  // per task). Shares the accounts ledger with Meta/IG; TG profiles come from
  // data/tg_accounts.json.
  if (pathname === '/api/tg/pool' && req.method === 'GET') {
    sendJson(req, res, { status: 'SUCCESS', accounts: readTgPool() });
    return true;
  }

  // ---- FastPay Bot: Instagram-2FA payout runner (tg_fastpay.py) ----
  // Submits every ledger account's twofa_secret to @FastPay2025_bot and claims
  // the payout. Refuses while the TG Classic engine holds the sessions.
  if (pathname === '/api/tg/fastpay/status' && req.method === 'GET') {
    (async () => {
      let accounts = [];
      try { accounts = await loadAccounts(); } catch (e) {}
      const withKey = accounts.filter(a => String(a.twofa_secret || '').trim());
      const paid = withKey.filter(a => a.fastpay_paid).length;
      const keys = withKey.length;
      sendJson(req, res, { ok: true, keys, paid, pending: keys - paid,
                           total: accounts.length,
                           rate: 0.024,
                           running: fastpayCount() > 0, pool: readTgPool() });
    })();
    return true;
  }
  if (pathname === '/api/tg/fastpay/claim' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', () => {
      if (fastpayCount()) {
        sendJson(req, res, { ok: false, error: 'A FastPay run is already in progress.' }, 400);
        return;
      }
      if (slot().proc) {
        sendJson(req, res, { ok: false,
          error: 'TG Classic engine is running — stop it first (the sessions are leased).' }, 400);
        return;
      }
      (async () => {
        let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
        const parallel = Math.max(1, Math.min(10, parseInt(b.parallel, 10) || 1));
        const target = Math.max(0, parseInt(b.target, 10) || 0);

        // Pending work = ledger accounts with a key that are not yet paid, in a
        // stable order (target applies before splitting, like TG Classic).
        let accounts = [];
        try { accounts = await loadAccounts(); } catch (e) {}
        let pending = accounts
          .filter(a => String(a.twofa_secret || '').trim() && !a.fastpay_paid)
          .map(a => String(a.id));
        if (target > 0) pending = pending.slice(0, target);
        if (!pending.length) {
          sendJson(req, res, { ok: false,
            error: 'No pending accounts with a 2FA key to pay.' }, 400);
          return;
        }

        const usable = readTgPool().filter(a => a.enabled !== false && a.logged_in === true
          && a.status !== 'busy').map(a => a.id);
        if (!usable.length) {
          sendJson(req, res, { ok: false,
            error: 'No idle logged-in Telegram profile to drive the bot.' }, 400);
          return;
        }
        const n = Math.min(parallel, usable.length);
        const profiles = usable.slice(0, n);

        // Split the pending ids into n disjoint chunks.
        const chunks = profiles.map(() => []);
        pending.forEach((id, i) => chunks[i % n].push(id));

        const started = [];
        for (let i = 0; i < n; i++) {
          if (!chunks[i].length) continue;
          const args = [resolveScript('tg_fastpay.py'),
            '--profile', profiles[i], '--ids', chunks[i].join(',')];
          let proc;
          try {
            proc = spawn(PYTHON_BIN, args,
              { cwd: ROOT_DIR, windowsHide: true,
                env: Object.assign({}, process.env, {
                  PYTHONUNBUFFERED: '1', PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }) });
          } catch (e) {
            broadcastEvent({ type: 'log', pipeline: 'telegram',
              message: '[fastpay] spawn failed on ' + profiles[i] + ': ' + e.message });
            continue;
          }
          const tag = profiles[i];
          fastpayAdd(proc, tag);
          started.push(tag + '(' + chunks[i].length + ')');
          let buf = '';
          proc.stdout.on('data', d => {
            buf += d.toString('utf-8');
            const lines = buf.split('\n');
            buf = lines.pop() || '';
            lines.forEach(l => { if (l.trim())
              broadcastEvent({ type: 'log', pipeline: 'telegram', message: '[' + tag + '] ' + l }); });
          });
          proc.stderr.on('data', d => {
            const t = d.toString('utf-8').trim();
            if (t) broadcastEvent({ type: 'log', pipeline: 'telegram',
              message: '[' + tag + '][stderr] ' + t });
          });
          proc.on('close', code => {
            if (buf.trim()) broadcastEvent({ type: 'log', pipeline: 'telegram', message: buf });
            broadcastEvent({ type: 'log', pipeline: 'telegram',
              message: '[fastpay] ' + tag + ' finished (code ' + code + ')' });
            fastpayRemove(proc);
            if (!fastpayCount()) broadcastEvent({ type: 'fastpay_done', exit_code: code });
          });
        }
        if (!fastpayCount()) {
          sendJson(req, res, { ok: false, error: 'Failed to spawn tg_fastpay.py' }, 500);
          return;
        }
        broadcastEvent({ type: 'log', pipeline: 'telegram',
          message: '[fastpay] started ' + fastpayCount() + ' runner(s): ' +
            started.join(', ') + ' — ' + pending.length + ' pending key(s)' });
        sendJson(req, res, { ok: true, started: true, profiles: started,
          pending: pending.length });
      })();
    });
    return true;
  }
  if (pathname === '/api/tg/fastpay/stop' && req.method === 'POST') {
    if (!fastpayCount()) {
      sendJson(req, res, { ok: true, stopped: false, message: 'No FastPay run in progress.' });
    } else {
      const n = fastpayCount();
      fastpayList().forEach(x => { try { x.proc.kill('SIGTERM'); } catch (e) {} });
      sendJson(req, res, { ok: true, stopped: true, message: 'FastPay stop requested (' + n + ').' });
    }
    return true;
  }

  // ---- TG Manager: lease/mutual-exclusion + readiness + balance ----
  if (pathname === '/api/tg/manager/status' && req.method === 'GET') {
    (async () => {
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_manager_cli.py',
        ['--mode', 'summary'], 45000);
      sendJson(req, res, r || { ok: false, error: 'no result' });
    })();
    return true;
  }
  if (pathname === '/api/tg/manager/bots' && req.method === 'GET') {
    (async () => {
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'tg_manager_cli.py',
        ['--mode', 'bots'], 45000);
      sendJson(req, res, r || { ok: false, error: 'no result' });
    })();
    return true;
  }
  if (pathname === '/api/tg/manager/balance' && req.method === 'POST') {
    (async () => {
      const fresh = urlObj.searchParams.get('fresh') === '1';
      const { data, logged } = await balanceAll(fresh);
      if (logged) logBalances(data);
      sendJson(req, res, data || { ok: false, error: 'no result' });
    })();
    return true;
  }

  function readTgStats() {
    try {
      const f = path.join(ROOT_DIR, 'data', 'tg_stats.json');
      if (fs.existsSync(f)) {
        const d = JSON.parse(fs.readFileSync(f, 'utf-8'));
        if (d && typeof d === 'object') return d;
      }
    } catch (e) {}
    return { total: 0, submitted: 0, taskly: 0, paygo: 0, fastpay: 0 };
  }

  if (pathname === '/api/tg/status' && req.method === 'GET') {
    (async () => {
      const stats = readTgStats();
      const subTaskly = stats.taskly || 0;
      const subPaygo = stats.paygo || 0;
      const subFastpay = stats.fastpay || 0;
      const submitted = stats.submitted != null ? stats.submitted : (subTaskly + subPaygo + subFastpay);
      const total = stats.total != null ? stats.total : submitted;
      sendJson(req, res, {
        status: 'SUCCESS',
        tool: 'tg-classic',
        running: reapDeadEngine(),
        pipeline: 'telegram',
        ig_mode: slot().proc ? 'classic' : null,
        engine: slot().config || null,
        // KPIs the TG panel renders (same shape as meta_auto_ai's tg tab)
        total_accounts: total,
        tg_total: total,
        tg_pending: 0,
        tg_submitted: submitted,
        // Per-bot breakdown (independent counters)
        tg_submitted_taskly: subTaskly,
        tg_submitted_paygo: subPaygo,
        tg_submitted_fastpay: subFastpay,
        tg_total_taskly: subTaskly,
        tg_total_paygo: subPaygo,
        tg_total_fastpay: subFastpay,
        tg_pending_taskly: 0,
        tg_pending_paygo: 0,
        tg_pending_fastpay: 0,
        tg_paid_fastpay: subFastpay,
        // Bots this build ships — the panel defaults its bot/task to these.
        enabled_bots: readEnabledBots(),
        concurrency: (slot().config || {}).concurrency || 0,
        pool: { accounts: readTgPool() },
      });
    })();
    return true;
  }

  if (pathname === '/api/tg/start' && req.method === 'POST') {
    if (reapDeadEngine() || slot().inFlight) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'An engine is already running.' }));
      return true;
    }
    slot().inFlight = true;
    const releaseStartTg = () => { slot().inFlight = false; };
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('aborted', releaseStartTg);
    req.on('end', async () => {
      let opts = { concurrency: 3, target: 0, delay: 4, headless: true,
                   captcha: 'extension', tg_task: '🔥 Create Inst (No mail)',
                   tg_bot: 'taskly', add_email: false, twofa: true };
      try { if (body) opts = Object.assign(opts, JSON.parse(body)); } catch (e) {}

      // License gate — same contract as the Meta/IG start route.
      let licCheck;
      try {
        licCheck = await licenseMgr.validateOrActivateLicense(null, false);
      } catch (licenseErr) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'License validation failed: ' + licenseErr.message }));
        releaseStartTg(); return;
      }
      if (!licCheck.isValid) {
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'No valid license for this machine.' }));
        releaseStartTg(); return;
      }

      const concurrency = Math.max(1, Math.min(parseInt(opts.concurrency || 3, 10) || 3, 10));
      const target = Math.max(0, parseInt(opts.target || 0, 10) || 0);
      const delay = Math.max(1, parseInt(opts.delay || 4, 10) || 4);
      const headless = opts.headless !== false;
      const captcha = opts.captcha || 'extension';
      const tgTask = String(opts.tg_task || '🔥 Create Inst (No mail)').slice(0, 80);
      const tgBot = readEnabledBots().includes(String(opts.tg_bot))
        ? String(opts.tg_bot) : defaultBot();
      const newPassword = String(opts.new_password || storedGlobalPassword() || '').trim().slice(0, 128);
      const newUsername = String(opts.new_username || '').trim().slice(0, 64);

      // Refuse a start that can never lease a profile (see tgPoolUsable). The
      // frontend preflight shows the toast; this is the authoritative guard.
      if (!tgPoolUsable()) {
        releaseStartTg();
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR',
          error: 'No logged-in Telegram profile. Add or log in a profile (and enable it) before starting TG Classic.' }));
        return;
      }

      const useIgPool = (tgBot === 'paygo') && (opts.use_ig_pool === true || opts.use_ig_pool === 'true');

      slot().config = { concurrency, headless, target, delay, captcha,
                        coupled: true, tg_task: tgTask, tg_bot: tgBot,
                        twofa: opts.twofa !== false, use_ig_pool: useIgPool };

      const args = [
        resolveScript('worker.py'),
        '--concurrency', String(concurrency),
        '--target', String(target),
        '--delay', String(delay),
        '--mail', 'mailtd',
        '--captcha', captcha,
        '--mode', 'meta',
        '--coupled',
        '--tg-task', tgTask,
        '--tg-bot', tgBot,
      ];
      if (opts.twofa !== false) args.push('--twofa');
      // Belt-and-braces with the dashboard guard: the native Taskly-2FA flow
      // has no mailbox step (bot email+code), so --add-email must never reach
      // the worker for it even if a stale client sends true.
      let addEmail = (opts.add_email === true || opts.add_email === 'true');
      if (tgBot === 'taskly' && /2fa/i.test(tgTask) && !/no.mail/i.test(tgTask) && !/cookie/i.test(tgTask)) {
        addEmail = false;
      }
      if (addEmail) args.push('--add-email');
      // PayGo Cookies task runs a different engine flow (no 2FA leg: Meta ->
      // TG creds -> IG join + follow -> cookie export -> cookie submit).
      if (/cookie/i.test(tgTask)) args.push('--cookie');
      if (useIgPool) args.push('--use-ig-pool');
      if (headless) args.push('--headless');

      console.log(`[MetaCreator] Starting TG Classic: ${PYTHON_BIN} ${args.join(' ')}`);
      const isWinTg = process.platform === 'win32';
      const browsersTg = fs.existsSync(path.join(ROOT_DIR, '_internal', 'ms-playwright'))
        ? path.join(ROOT_DIR, '_internal', 'ms-playwright')
        : path.join(ROOT_DIR, 'engine', 'ms-playwright');
      try {
        resetWorkerBuffer();
        slot().proc = spawn(PYTHON_BIN, args, {
          cwd: ROOT_DIR,
          detached: !isWinTg,
          windowsHide: true,
          env: Object.assign({}, process.env, {
            PYTHONUNBUFFERED: '1',
            PYTHONUTF8: '1',
            PYTHONIOENCODING: 'utf-8',
            PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH || browsersTg,
            ...(newPassword ? { META_NEW_PASSWORD: newPassword } : {}),
            ...(newUsername ? { META_NEW_USERNAME: newUsername } : {})
          })
        });
      } catch (spawnErr) {
        releaseStartTg();
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', error: 'Failed to spawn TG worker: ' + spawnErr.message }));
        return;
      }

      const rlHandle = ctx.runlog ? ctx.runlog.start('telegram', { argv: args }) : null;
      slot().runlog = rlHandle;

      // Stream the worker's output. WITHOUT this the child's stdout/stderr is
      // discarded and the TG console stays empty even when the worker dies
      // instantly (e.g. a bad kwarg) — you see "started" and no browser tab.
      slot().proc.stdout.on('data', data => {
        if (rlHandle && ctx.runlog) ctx.runlog.line(rlHandle, data);
        for (const line of feedWorkerStdout(data)) consumeWorkerLine(line, 'tg');
      });
      slot().proc.stderr.on('data', data => {
        if (rlHandle && ctx.runlog) ctx.runlog.line(rlHandle, data);
        const text = data.toString('utf-8').trim();
        if (!text) return;
        if (/socket\.send\(\) raised exception\.?/i.test(text)) return;
        console.error(`[TG Worker STDERR] ${text}`);
        broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg', message: `[STDERR] ${text}` });
      });
      slot().proc.on('error', err => {
        broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg', message: `[Worker] ${err.message}` });
        if (rlHandle && ctx.runlog) ctx.runlog.end(rlHandle);
        if (slot().proc) slot().proc = null;
      });
      const procRef = slot().proc;
      slot().proc.on('close', code => {
        flushWorkerBuffer();
        if (rlHandle && ctx.runlog) ctx.runlog.end(rlHandle);
        console.log(`[TG] loop process exited with code ${code}`);
        broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg',
          message: `[engine] TG worker exited (code ${code})` });
        broadcastEvent({ type: 'loop_stopped', pipeline: 'telegram', engine: 'tg', exit_code: code });
        if (slot().proc === procRef) slot().proc = null;
        if (!procRef || !procRef.__preemptKilled) {
          paygoOrchestrator.notifyLoopStopped(procRef);
        }
      });
      releaseStartTg();
      sendJson(req, res, { status: 'SUCCESS', message: 'TG Classic engine started.', config: slot().config });
    });
    return true;
  }

  if (pathname === '/api/tg/stop' && req.method === 'POST') {
    try {
      if (slot().proc) {
        const isWinStop = process.platform === 'win32';
        if (!isWinStop) {
          try { process.kill(-slot().proc.pid, 'SIGTERM'); }
          catch (e) { try { slot().proc.kill('SIGTERM'); } catch (e2) {} }
        } else {
          try { slot().proc.kill(); } catch (e2) {}
        }
        slot().proc = null;
      }
      slot().config = null;
      broadcastEvent({ type: 'loop_stopped', pipeline: 'telegram', engine: 'tg', message: 'TG Classic engine stopped by user request.' });
      sendJson(req, res, { status: 'SUCCESS', message: 'TG Classic engine stopped.' });
      paygoOrchestrator.notifyUserStopped();
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', error: 'Stop failed: ' + e.message }));
    }
    return true;
  }

  // ---- PayGo Auto-Mining & Preemption Routes ----
  if (pathname === '/api/tg/paygo-auto/status' && req.method === 'GET') {
    sendJson(req, res, { ok: true, status: paygoOrchestrator.getStatus() });
    return true;
  }

  if (pathname === '/api/tg/paygo-auto/toggle' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', () => {
      let b = {}; try { b = JSON.parse(body || '{}'); } catch (e) {}
      const st = paygoOrchestrator.toggle(b.enabled, b.concurrency);
      sendJson(req, res, { ok: true, status: st });
    });
    return true;
  }
  // =============== end TG Classic ===============
  return false;
};
