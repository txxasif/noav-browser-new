'use strict';
/** Static files + API 404 fallback (must run last). */
module.exports = function handleStatic(req, res, urlObj, pathname, ctx) {
  const { fs, path, zlib, ROOT_DIR, PUBLIC_DIR } = ctx;

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.csv': 'text/csv; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8'
};

// Static asset cache (gzip + ETag), keyed by absolute path.
const STATIC_CACHE = new Map();
  // 12. POST /api/launch (fallback handler for UI browser launch)
  if (pathname === '/api/launch' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; });
    req.on('end', () => {
      let targetUrl = 'https://auth.meta.com/';
      try {
        const parsed = JSON.parse(body || '{}');
        if (parsed.targetUrl) targetUrl = parsed.targetUrl;
        else if (Array.isArray(parsed.url) && parsed.url[0]) targetUrl = parsed.url[0];
        else if (typeof parsed.url === 'string') targetUrl = parsed.url;
      } catch (e) {}

      const isWin = process.platform === 'win32';
      try {
        if (isWin) {
          execSync(`start "" "${targetUrl}"`, { stdio: 'ignore' });
        } else {
          execSync(`xdg-open "${targetUrl}" 2>/dev/null || sensible-browser "${targetUrl}" 2>/dev/null || true`, { stdio: 'ignore' });
        }
      } catch (e) {}

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'SUCCESS', ok: true }));
    });
    return true;
  }

  // Any unhandled API requests MUST return JSON 404, never fall through to static HTML
  if (res.headersSent) return true;
  if (pathname.startsWith('/api/') || pathname === '/api') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ERROR', error: `API route not found: ${pathname}` }));
    return true;
  }
  // --- Static Files ---
  let safeRel = (pathname === '/' || !pathname) ? 'index.html' : pathname.replace(/^\/+/, '');
  safeRel = path.normalize(safeRel).replace(/^(\.\.[\/\\])+/, '');
  let filePath = path.join(PUBLIC_DIR, safeRel);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }

  const ext = path.extname(filePath).toLowerCase();

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      if (safeRel === 'index.html') {
        const fallbacks = [
          path.join(ROOT_DIR, 'public', 'index.html'),
          path.join(process.cwd(), 'public', 'index.html'),
          path.join(ROOT_DIR, 'public', 'index.html'),
          path.join(path.dirname(process.execPath), 'public', 'index.html')
        ];
        for (const fb of fallbacks) {
          try {
            if (fs.existsSync(fb) && fs.statSync(fb).isFile()) {
              res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
              fs.createReadStream(fb).pipe(res);
              return;
            }
          } catch (e) {}
        }
      }
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end(`404 Not Found: ${pathname}`);
      return;
    }

    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    // Static asset cache: gzip once and revalidate with an ETag, so a reload
    // gets a 304 instead of re-downloading the 2k-line CSS / JS.
    const isText = /^(text\/|application\/(javascript|json))/.test(contentType) || ext === '.svg';
    const etag = `W/"${stats.mtimeMs}-${stats.size}"`;
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('ETag', etag);
    if (req.headers['if-none-match'] === etag) {
      res.writeHead(304);
      res.end();
      return;
    }
    let cached = STATIC_CACHE.get(filePath);
    if (!cached || cached.mtimeMs !== stats.mtimeMs || cached.size !== stats.size) {
      let gzip = null;
      if (isText && stats.size > 1024) {
        try { gzip = zlib.gzipSync(fs.readFileSync(filePath)); } catch (e) { gzip = null; }
      }
      cached = { mtimeMs: stats.mtimeMs, size: stats.size, gzip };
      STATIC_CACHE.set(filePath, cached);
    }
    if (cached.gzip && String(req.headers['accept-encoding'] || '').includes('gzip')) {
      res.writeHead(200, { 'Content-Type': contentType, 'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding' });
      res.end(cached.gzip);
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType });
    fs.createReadStream(filePath).pipe(res);
  });
  return true;
};
