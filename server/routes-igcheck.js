'use strict';
/**
 * IG Checker + IG Creator full Backup/Restore APIs.
 *
 *   POST /api/ig-check            {usernames[], delay_ms?} -> {results[]} (cap 50)
 *   POST /api/ig-check-stream     {usernames[], delay_ms?} -> NDJSON live feed
 *   POST /api/ig-mark-dead        {usernames[]} -> marks saved rows Failed
 *   GET  /api/meta-insta/export-full?kind=ig&exclude_damaged=1 -> full-backup CSV
 *   POST /api/meta-insta/import-full {csv_text, exclude_damaged, skip_existing, limit, order}
 *
 * Checker ported from Nova Browser (pyserver/insta.py + js/nova-insta.js):
 * public REST profile lookup with HTML fallback — no login, no cookies.
 * "Damaged" == status Failed/Banned, extra 'Dead:*', or attempts >= 3
 * (same test as ig_backup.is_damaged, surfaced in the Backup modal).
 */
const os = require('os');

const BATCH_MAX = 50;
const STREAM_MAX = 100;

function readBody(req, limitBytes) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > limitBytes) {
        reject(new Error('request too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    req.on('error', reject);
  });
}

function cleanUsernames(list) {
  const out = [];
  const seen = new Set();
  for (const raw of (Array.isArray(list) ? list : [])) {
    const u = String(raw == null ? '' : raw).trim().replace(/^@+/, '').toLowerCase();
    if (!u || seen.has(u)) continue;
    seen.add(u);
    out.push(u);
  }
  return out;
}

async function requireLicense(ctx, req, res) {
  let lic;
  try {
    lic = await ctx.licenseMgr.validateOrActivateLicense(null, false);
  } catch (e) {
    ctx.sendJson(req, res, { status: 'ERROR', error: 'License validation failed: ' + e.message }, 500);
    return null;
  }
  if (!lic || !lic.isValid) {
    ctx.sendJson(req, res, {
      status: 'UNLICENSED',
      error: 'Active license key required to use IG Checker.',
    }, 403);
    return null;
  }
  return lic;
}

module.exports = function handleIgCheck(req, res, urlObj, pathname, ctx) {
  const { fs, path, spawn, ROOT_DIR, PYTHON_BIN, runPythonJson, resolveScript, sendJson, loadAccounts, backupUserData } = ctx;

  // ---- POST /api/ig-check (single batch, JSON) ----
  if (pathname === '/api/ig-check' && req.method === 'POST') {
    (async () => {
      if (!await requireLicense(ctx, req, res)) return;
      let body;
      try {
        body = JSON.parse(await readBody(req, 256 * 1024));
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Invalid JSON body.' }, 400);
        return;
      }
      const usernames = cleanUsernames(body.usernames).slice(0, BATCH_MAX);
      if (!usernames.length) {
        sendJson(req, res, { status: 'ERROR', error: 'Provide at least one username.' }, 400);
        return;
      }
      const delayMs = Math.min(5000, Math.max(300, Number(body.delay_ms) || 600));
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_check.py',
        ['--usernames-json', JSON.stringify(usernames), '--delay-ms', String(delayMs)], 180000);
      if (!r || !Array.isArray(r.results)) {
        sendJson(req, res, { status: 'ERROR', error: 'Checker failed: ' + ((r && r.error) || 'no output') }, 500);
        return;
      }
      sendJson(req, res, { status: 'SUCCESS', results: r.results });
    })();
    return true;
  }

  // ---- POST /api/ig-check-stream (NDJSON live feed, Nova parity) ----
  if (pathname === '/api/ig-check-stream' && req.method === 'POST') {
    (async () => {
      if (!await requireLicense(ctx, req, res)) return;
      let body;
      try {
        body = JSON.parse(await readBody(req, 256 * 1024));
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Invalid JSON body.' }, 400);
        return;
      }
      const usernames = cleanUsernames(body.usernames).slice(0, STREAM_MAX);
      if (!usernames.length) {
        sendJson(req, res, { status: 'ERROR', error: 'Provide at least one username.' }, 400);
        return;
      }
      const delayMs = Math.min(5000, Math.max(300, Number(body.delay_ms) || 800));
      let child;
      try {
        child = spawn(PYTHON_BIN, [
          resolveScript(path.join(ROOT_DIR, 'ig_check.py')),
          '--usernames-json', JSON.stringify(usernames),
          '--delay-ms', String(delayMs),
          '--ndjson',
        ], { cwd: ROOT_DIR, windowsHide: true, env: Object.assign({}, process.env, { PYTHONUNBUFFERED: '1', PYTHONUTF8: '1' }) });
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Failed to start checker: ' + e.message }, 500);
        return;
      }
      res.writeHead(200, {
        'Content-Type': 'application/x-ndjson; charset=utf-8',
        'Cache-Control': 'no-cache, no-store',
        'Connection': 'keep-alive',
      });
      let buf = '';
      child.stdout.on('data', (d) => {
        buf += d.toString('utf-8');
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (line.trim()) { try { res.write(line + '\n'); } catch (e) {} }
        }
      });
      child.stderr.on('data', () => {});
      child.on('close', () => {
        if (buf.trim()) { try { res.write(buf.trim() + '\n'); } catch (e) {} }
        try { res.end(); } catch (e) {}
      });
      req.on('close', () => { try { child.kill('SIGKILL'); } catch (e) {} });
    })();
    return true;
  }

  // ---- POST /api/ig-mark-dead {usernames[]} ----
  // Flags saved IG rows whose live check came back not_found so the pool
  // drain never picks them again (status Failed + 'Dead: ig-check …' note).
  if (pathname === '/api/ig-mark-dead' && req.method === 'POST') {
    (async () => {
      if (!await requireLicense(ctx, req, res)) return;
      let body;
      try {
        body = JSON.parse(await readBody(req, 256 * 1024));
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Invalid JSON body.' }, 400);
        return;
      }
      const usernames = cleanUsernames(body.usernames).slice(0, STREAM_MAX);
      if (!usernames.length) {
        sendJson(req, res, { status: 'ERROR', error: 'Provide at least one username.' }, 400);
        return;
      }
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_backup.py',
        ['mark-dead', '--usernames-json', JSON.stringify(usernames)], 60000);
      if (!r || !r.ok) {
        sendJson(req, res, { status: 'ERROR', error: 'Could not flag accounts: ' + ((r && r.error) || 'no output') }, 500);
        return;
      }
      try { ctx.broadcastEvent({ type: 'accounts_reset' }); } catch (e) {}
      sendJson(req, res, { status: 'SUCCESS', marked: r.marked || [], already_damaged: r.already_damaged || [], missing: r.missing || [] });
    })();
    return true;
  }

  // ---- GET /api/meta-insta/export-full (full-backup CSV, same schema as import) ----
  if (pathname === '/api/meta-insta/export-full' && req.method === 'GET') {
    (async () => {
      const kindRaw = String(urlObj.searchParams.get('kind') || 'ig').toLowerCase();
      const kind = kindRaw === 'meta' ? 'meta' : (kindRaw === 'all' ? 'all' : 'ig');
      const excludeDamaged = urlObj.searchParams.get('exclude_damaged') === '1';
      const tmp = path.join(os.tmpdir(), `ig_full_backup_${Date.now()}.csv`);
      const args = ['--kind', kind, '--out', tmp];
      if (excludeDamaged) args.push('--exclude-damaged');
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_backup.py', ['export'].concat(args), 120000);
      if (!r || !r.ok) {
        sendJson(req, res, { status: 'ERROR', error: 'Export failed: ' + ((r && r.error) || 'no output') }, 500);
        return;
      }
      const suffix = excludeDamaged ? '_clean' : '_full';
      res.writeHead(200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="instagram_backup${suffix}.csv"`,
      });
      const stream = fs.createReadStream(tmp);
      stream.on('close', () => { try { fs.unlinkSync(tmp); } catch (e) {} });
      stream.pipe(res);
    })();
    return true;
  }

  // ---- POST /api/meta-insta/xlsx-to-csv {xlsx_base64} -> {csv_text, rows} ----
  // Lets the Import modal accept the .xlsx backups older builds produced: the
  // sheet is converted to the standard full-backup CSV and then follows the
  // exact same preview/import path as a .csv file.
  if (pathname === '/api/meta-insta/xlsx-to-csv' && req.method === 'POST') {
    (async () => {
      let body;
      try {
        body = JSON.parse(await readBody(req, 80 * 1024 * 1024));
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Invalid body: ' + e.message }, 400);
        return;
      }
      const b64 = String((body && body.xlsx_base64) || '');
      if (!b64) {
        sendJson(req, res, { status: 'ERROR', error: 'Empty file: nothing to read.' }, 400);
        return;
      }
      const tmp = path.join(os.tmpdir(), `ig_xlsx_import_${Date.now()}.xlsx`);
      try {
        fs.writeFileSync(tmp, Buffer.from(b64, 'base64'));
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Could not stage upload: ' + e.message }, 500);
        return;
      }
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_backup.py', ['xlsx2csv', '--file', tmp], 120000);
      try { fs.unlinkSync(tmp); } catch (e) {}
      if (!r || !r.ok) {
        sendJson(req, res, { status: 'ERROR', error: 'Could not read the .xlsx: ' + ((r && r.error) || 'no output') }, 400);
        return;
      }
      sendJson(req, res, { status: 'SUCCESS', csv_text: r.csv_text, rows: r.rows });
    })();
    return true;
  }

  // ---- POST /api/meta-insta/import-full {csv_text, exclude_damaged, skip_existing, limit, order} ----
  if (pathname === '/api/meta-insta/import-full' && req.method === 'POST') {
    (async () => {
      let body;
      try {
        body = JSON.parse(await readBody(req, 60 * 1024 * 1024));
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Invalid body: ' + e.message }, 400);
        return;
      }
      const csvText = String((body && body.csv_text) || '');
      if (!csvText.trim()) {
        sendJson(req, res, { status: 'ERROR', error: 'Empty file: nothing to import.' }, 400);
        return;
      }
      const excludeDamaged = body.exclude_damaged !== false;
      const skipExisting = body.skip_existing !== false;
      const limit = Math.max(0, parseInt(body.limit || 0, 10) || 0);
      const order = String(body.order || 'newest').toLowerCase() === 'oldest' ? 'oldest' : 'newest';
      const tmp = path.join(os.tmpdir(), `ig_full_import_${Date.now()}.csv`);
      try {
        fs.writeFileSync(tmp, csvText, 'utf-8');
      } catch (e) {
        sendJson(req, res, { status: 'ERROR', error: 'Could not stage upload: ' + e.message }, 500);
        return;
      }
      try { backupUserData('import'); } catch (e) {}
      const args = ['--file', tmp, '--limit', String(limit), '--order', order];
      if (excludeDamaged) args.push('--exclude-damaged');
      if (skipExisting) args.push('--skip-existing');
      else args.push('--no-skip-existing');
      const r = await runPythonJson(PYTHON_BIN, ROOT_DIR, 'ig_backup.py', ['import'].concat(args), 300000);
      try { fs.unlinkSync(tmp); } catch (e) {}
      if (!r || !r.ok) {
        sendJson(req, res, { status: 'ERROR', error: 'Import failed: ' + ((r && (r.error || (r.errors || []).join('; '))) || 'no output') }, 500);
        return;
      }
      try { ctx.broadcastEvent({ type: 'accounts_reset' }); } catch (e) {}
      sendJson(req, res, Object.assign({ status: 'SUCCESS' }, r));
    })();
    return true;
  }

  return false;
};
