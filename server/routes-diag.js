/**
 * server/routes-diag.js — read-only diagnostics and session logs.
 *
 * GET /api/diag/reasons            → in-memory failure-reason histogram
 * GET /api/logs                    → {dir, logs:[{name,size,mtime}]} newest first
 * GET /api/logs/latest?pipeline=X  → newest run log for X (or any)
 * GET /api/logs/file?name=<file>   → text/plain download of one log
 */
const path = require('path');
const diag = require('./diag');
const runlog = require('./runlog');

function handleDiagRoutes(req, res, urlObj, pathname, ctx) {
  const { sendJson } = ctx;

  if (pathname === '/api/diag/reasons' && req.method === 'GET') {
    sendJson(req, res, diag.snapshot());
    return true;
  }
  if (pathname === '/api/logs' && req.method === 'GET') {
    sendJson(req, res, { dir: runlog.LOG_DIR, logs: runlog.list() });
    return true;
  }
  if (pathname === '/api/logs/latest' && req.method === 'GET') {
    sendJson(req, res, { latest: runlog.latest(urlObj.searchParams.get('pipeline') || null) });
    return true;
  }
  if (pathname === '/api/logs/file' && req.method === 'GET') {
    const r = runlog.read(urlObj.searchParams.get('name'));
    if (!r) {
      sendJson(req, res, { ok: false, error: 'log not found' }, 404);
      return true;
    }
    res.writeHead(200, {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': `attachment; filename="${path.basename(r.path)}"`,
    });
    res.end(r.content);
    return true;
  }
  return false;
}

module.exports = handleDiagRoutes;
