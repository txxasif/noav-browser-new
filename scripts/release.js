#!/usr/bin/env node
/**
 * Meta Creator — Automated Release & Distribution Manager
 * =======================================================
 * Usage:
 *   node scripts/release.js --version 1.0.1 --notes "Bugfixes and engine performance improvements"
 *   node scripts/release.js --version 1.0.1 --no-push
 *
 * Responsibilities:
 *   1. Validate semantic version bump.
 *   2. Stamp version in package.json and core/licenseConfig.js.
 *   3. Run python3 build_windows_dist.py to synchronize source & build portable Windows ZIP.
 *   4. Generate dist/latest.json update manifest with SHA-256 and size.
 *   5. Optionally publish GitHub release via `gh` CLI.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const DEFAULT_RELEASE_REPO = process.env.RELEASE_REPO || 'ahasifff/nova-browser-release';

function fail(message) {
  console.error(`\x1b[31m[release] ERROR: ${message}\x1b[0m`);
  process.exit(1);
}

function parseArgs(argv) {
  const out = { version: null, notes: '', repo: DEFAULT_RELEASE_REPO, noPush: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--version') out.version = argv[++i];
    else if (argv[i] === '--notes') out.notes = argv[++i];
    else if (argv[i] === '--repo') out.repo = argv[++i];
    else if (argv[i] === '--no-push') out.noPush = true;
  }
  return out;
}

function parseVersion(value) {
  const parts = String(value || '')
    .trim()
    .replace(/^[vV]/, '')
    .split('.')
    .map(p => parseInt(p, 10));
  if (parts.length === 0 || parts.some(n => Number.isNaN(n) || n < 0)) return null;
  while (parts.length < 3) parts.push(0);
  return parts.slice(0, 3);
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.version || !parseVersion(args.version)) {
    fail('Usage: node scripts/release.js --version X.Y.Z --notes "..." [--repo owner/name] [--no-push]');
  }
  const version = parseVersion(args.version).join('.');

  const pkgPath = path.join(ROOT, 'package.json');
  const pkg = readJson(pkgPath);
  const current = parseVersion(pkg.version);
  if (!current) fail(`Cannot parse current package.json version (${pkg.version})`);

  const nv = version.split('.').map(Number);
  const isNewer =
    nv[0] > current[0] ||
    (nv[0] === current[0] && (nv[1] > current[1] || (nv[1] === current[1] && nv[2] > current[2])));
  const isSame = nv[0] === current[0] && nv[1] === current[1] && nv[2] === current[2];
  if (!isNewer && !isSame) {
    fail(`Specified version ${version} is not newer than or equal to current version ${pkg.version}`);
  }

  console.log(`\x1b[36m====================================================================\x1b[0m`);
  console.log(`  Meta Creator Release Pipeline: v${pkg.version} -> v${version}`);
  console.log(`\x1b[36m====================================================================\x1b[0m\n`);

  // 1. Stamp version in package.json
  pkg.version = version;
  fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');
  console.log(`[*] Version stamped in package.json: ${version}`);

  // 2. Stamp version in core/licenseConfig.js
  const configPath = path.join(ROOT, 'core', 'licenseConfig.js');
  if (fs.existsSync(configPath)) {
    let cfgSrc = fs.readFileSync(configPath, 'utf8');
    cfgSrc = cfgSrc.replace(/appVersion:\s*'[^']+'/, `appVersion: '${version}'`);
    cfgSrc = cfgSrc.replace(/version:\s*'[^']+'/, `version: '${version}'`);
    fs.writeFileSync(configPath, cfgSrc, 'utf8');
    console.log(`[*] Version stamped in core/licenseConfig.js: ${version}`);
  }

  // 3. Run automated Windows distribution builder
  console.log(`\n[*] Running Windows distribution builder (build_windows_dist.py)...`);
  const buildRes = spawnSync('python3', [path.join(ROOT, 'build_windows_dist.py')], {
    cwd: ROOT,
    stdio: 'inherit'
  });
  if (buildRes.status !== 0) {
    fail('build_windows_dist.py failed with non-zero exit status');
  }

  // 4. Verify distribution artifact
  const distDir = path.join(ROOT, '..', '..', 'win', 'meta_creator', 'dist');
  const zipName = 'MetaCreator-Windows-Portable.zip';
  const zipPath = path.join(distDir, zipName);
  if (!fs.existsSync(zipPath)) {
    fail(`Distribution artifact not found at ${zipPath}`);
  }

  const zipSha256 = sha256File(zipPath);
  const zipSize = fs.statSync(zipPath).size;
  console.log(`\n[✅] Distribution ZIP verified:`);
  console.log(`     Path:   ${zipPath}`);
  console.log(`     Size:   ${(zipSize / (1024 * 1024)).toFixed(2)} MB`);
  console.log(`     SHA256: ${zipSha256}`);

  // 5. Generate latest.json manifest for updateManager
  const manifest = {
    version: version,
    notes: args.notes || `Meta Creator release v${version}`,
    date: new Date().toISOString().slice(0, 10),
    files: {
      'win-x64': {
        url: `https://github.com/${args.repo}/releases/download/v${version}/${zipName}`,
        sha256: zipSha256,
        size: zipSize
      },
      'win-portable': {
        url: `https://github.com/${args.repo}/releases/download/v${version}/${zipName}`,
        sha256: zipSha256,
        size: zipSize
      }
    }
  };

  const localDistDir = path.join(ROOT, 'dist');
  try { fs.mkdirSync(localDistDir, { recursive: true }); } catch (e) {}
  const manifestPath = path.join(localDistDir, 'latest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  console.log(`[*] Generated update manifest: ${manifestPath}`);

  // Also copy latest.json to windows dist
  const winManifestPath = path.join(distDir, 'latest.json');
  fs.writeFileSync(winManifestPath, JSON.stringify(manifest, null, 2) + '\n');

  // 6. GitHub Release publication
  let uploaded = false;
  try {
    const authCheck = spawnSync('gh', ['auth', 'status'], { stdio: 'pipe' });
    if (authCheck.status === 0 || process.env.GH_TOKEN || process.env.GITHUB_TOKEN) {
      console.log(`\n[*] Publishing release v${version} to GitHub repo: ${args.repo}...`);
      const ghRes = spawnSync(
        'gh',
        [
          'release', 'create', `v${version}`,
          '--repo', args.repo,
          '--title', `Meta Creator v${version}`,
          '--notes', args.notes || `Meta Creator v${version}`,
          zipPath,
          manifestPath
        ],
        { stdio: 'inherit' }
      );
      if (ghRes.status === 0) {
        uploaded = true;
        console.log(`[✅] GitHub release published: https://github.com/${args.repo}/releases/tag/v${version}`);
      }
    }
  } catch (e) {
    uploaded = false;
  }

  if (!uploaded) {
    console.log(`\n[ℹ️] GitHub release command to run manually (when ready):`);
    console.log(`    gh release create v${version} ${zipPath} ${manifestPath} --title "Meta Creator v${version}" --notes "${args.notes || 'Meta Creator v' + version}"\n`);
  }

  // 7. Git commit if requested
  if (args.noPush) {
    console.log('[*] --no-push flag supplied; skipping git commit & push.');
  } else {
    try {
      console.log('[*] Committing release files locally...');
      spawnSync('git', ['add', 'package.json', 'core/licenseConfig.js'], { cwd: ROOT, stdio: 'pipe' });
      spawnSync('git', ['commit', '-m', `release: Meta Creator v${version}`], { cwd: ROOT, stdio: 'pipe' });
      console.log('[✅] Git commit completed.');
    } catch (e) {}
  }

  console.log(`\n\x1b[32m====================================================================\x1b[0m`);
  console.log(`  Meta Creator v${version} Build & Release Complete!`);
  console.log(`\x1b[32m====================================================================\x1b[0m\n`);
}

main();
