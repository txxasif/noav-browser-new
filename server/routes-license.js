'use strict';
/** License Management APIs (/api/license/*). See server.js dispatch. */
module.exports = function handleLicense(req, res, urlObj, pathname, ctx) {
  const { licenseMgr } = ctx;

  // =========================================================================
  // License Management APIs (/api/license/*)
  // =========================================================================

  // 1. GET /api/license/status
  if (pathname === '/api/license/status' && req.method === 'GET') {
    const force = urlObj.searchParams.get('force') === 'true';
    licenseMgr.validateOrActivateLicense(null, force).then(result => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch(err => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    });
    return true;
  }

  // 2. POST /api/license/activate
  if (pathname === '/api/license/activate' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body || '{}');
        const key = (payload.licenseKey || payload.key || '').trim();
        if (!key) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ERROR', message: 'License key is required.' }));
          return;
        }
        const result = await licenseMgr.validateOrActivateLicense(key, true);
        res.writeHead(result.isValid ? 200 : 400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
      }
    });
    return true;
  }

  // 3. POST /api/license/validate
  if (pathname === '/api/license/validate' && req.method === 'POST') {
    licenseMgr.validateOrActivateLicense(null, true).then(result => {
      res.writeHead(result.isValid ? 200 : 400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch(err => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    });
    return true;
  }

  // 4. POST /api/license/deactivate
  if (pathname === '/api/license/deactivate' && req.method === 'POST') {
    licenseMgr.deactivateLicense().then(result => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch(err => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ERROR', message: err.message }));
    });
    return true;
  }
  return false;
};
