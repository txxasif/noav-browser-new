// Builds dist/worker.js (single-file dashboard deploy) from src/* modules.
// Usage: node scripts/build-worker.js   (writes ../dist/worker.js)
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const order = [
  'src/http.js',
  'src/auth.js',
  'src/db.js',
  'src/api/license.js',
  'src/api/admin.js',
  'src/api/payments.js',
  'src/ui/head.js',
  'src/ui/licenses.js',
  'src/ui/money.js',
  'src/ui/billing.js',
  'src/ui/modal.js',
  'src/ui/client-licenses.js',
  'src/ui/client-billing.js',
  'src/ui/shell.js',
  'src/index.js',
];

let out = [
  '/**',
  ' * nova-license — bundled single-file build for dashboard paste deploy.',
  ' * Generated from worker/license/src/* modules. Do not hand-edit; edit modules,',
  ' * rebuild with `node scripts/build-worker.js`, then paste dist/worker.js.',
  ' */',
  '',
].join('\n');

for (const p of order) {
  const lines = readFileSync(join(root, p), 'utf8').split('\n');
  const kept = [];
  let inImport = false;
  for (const line of lines) {
    if (!inImport && /^import[\s]/.test(line)) {
      inImport = !line.includes(';');
      continue;
    }
    if (inImport) {
      if (line.includes(';')) inImport = false;
      continue;
    }
    kept.push(line);
  }
  let src = kept.join('\n');
  src = src.replace('export default {', 'const __worker_export__ = {');
  src = src.replace(/^export (async function|function|const) /gm, '$1 ');
  out += `\n/* ===== ${p} ===== */\n` + src;
}
out += '\nexport default __worker_export__;\n';

mkdirSync(join(root, 'dist'), { recursive: true });
writeFileSync(join(root, 'dist', 'worker.js'), out);
console.log('wrote dist/worker.js', Buffer.byteLength(out), 'bytes');
