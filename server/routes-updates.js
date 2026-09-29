'use strict';
/** Self-Update APIs (/api/updates/*) — Nova Parity. */
module.exports = function handleUpdates(req, res, urlObj, pathname, ctx) {
  const { licenseConfig, updateManager } = ctx;

  // =========================================================================
  // Self-Update APIs (/api/updates/*) — Nova Parity
  // =========================================================================

  // 1. GET /api/updates/status
  if (pathname === '/api/updates/status' && req.method === 'GET') {
    if (licenseConfig.updates && licenseConfig.updates.enabled === false) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', currentVersion: licenseConfig.app.version, updateAvailable: false, disabled: true }));
      return true;
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
    return true;
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
    return true;
  }

  // 3. GET /api/updates/download/progress
  if (pathname === '/api/updates/download/progress' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', ...updateManager.getDownloadProgress() }));
    return true;
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
    return true;
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
    return true;
  }

  // 6. GET /api/updates/rollback-available
  if (pathname === '/api/updates/rollback-available' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS', available: updateManager.rollbackAvailable() }));
    return true;
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
    return true;
  }
  return false;
};
