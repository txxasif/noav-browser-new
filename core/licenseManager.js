/**
 * Meta Creator — Software License Manager Client (core/licenseManager.js)
 * Authoritative License Connector for Cloudflare Workers + D1 License Backend.
 *
 * Remote License Server is the Authoritative Source of Truth:
 * https://nova-license.ahasiffff.workers.dev
 *
 * Local license_data/license_data.json is strictly a temporary signed cache
 * for a 72-hour offline grace period protected by HMAC-SHA256 tamper detection.
 */

const crypto = require('crypto');
const os = require('os');
const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');
const config = require('./licenseConfig');

const DEFAULT_LICENSE_SERVER_URL = config.license.defaultServerUrl;
const LICENSE_REQUEST_TIMEOUT_MS = config.license.requestTimeoutMs;
const LICENSE_MICRO_CACHE_MINUTES = config.license.microCacheMinutes;

const IGNORED_INTERFACE_PATTERNS = [
  /vpn/i,
  /nox/i,
  /virtual/i,
  /veth/i,
  /tun/i,
  /tap/i,
  /wireguard/i,
  /hyper-v/i,
  /vmware/i,
  /npcap/i,
  /loopback/i,
  /wsl/i,
  /docker/i,
  /br-[a-f0-9]+/i,
  /virbr/i,
];

/**
 * Resolves the per-user, per-machine directory for the HWID seed.
 * Checks both NovaBrowser (for ecosystem parity) and MetaCreator.
 */
function resolveUserSeedDir() {
  if (process.platform === 'win32') {
    const roaming = process.env.APPDATA ||
      (process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Roaming') : null);
    if (roaming) {
      const novaPath = path.join(roaming, 'NovaBrowser');
      if (fs.existsSync(path.join(novaPath, 'machine_id.node'))) return novaPath;
      return path.join(roaming, 'MetaCreator');
    }
  } else {
    const xdg = process.env.XDG_CONFIG_HOME ||
      (typeof os.homedir === 'function' ? path.join(os.homedir(), '.config') : null);
    if (xdg) {
      const novaPath = path.join(xdg, 'nova-browser');
      if (fs.existsSync(path.join(novaPath, 'machine_id.node'))) return novaPath;
      return path.join(xdg, 'meta-creator');
    }
  }
  return null;
}

function readSeedFile(filePath) {
  try {
    if (filePath && fs.existsSync(filePath)) {
      const seed = fs.readFileSync(filePath, 'utf8').trim();
      if (seed && seed.length >= 16) return seed;
    }
  } catch (e) {}
  return null;
}

function chmodPrivate(targetPath, mode) {
  try { fs.chmodSync(targetPath, mode); } catch (e) {}
}

function writeSeedFile(filePath, seed) {
  try {
    if (!filePath) return false;
    fs.mkdirSync(path.dirname(filePath), { recursive: true, mode: 0o700 });
    chmodPrivate(path.dirname(filePath), 0o700);
    fs.writeFileSync(filePath, seed, { encoding: 'utf8', mode: 0o600 });
    chmodPrivate(filePath, 0o600);
    return true;
  } catch (e) {
    return false;
  }
}

let _cachedStableOSId = null;
function getStableOSId() {
  if (_cachedStableOSId !== null) return _cachedStableOSId;
  // Stable machine id: survives Wi-Fi toggles, USB NICs, hostname changes.
  // Linux: /etc/machine-id or /var/lib/dbus/machine-id. Windows: MachineGuid.
  try {
    for (const f of ['/etc/machine-id', '/var/lib/dbus/machine-id']) {
      try {
        if (fs.existsSync(f)) {
          const v = fs.readFileSync(f, 'utf8').trim().toLowerCase();
          if (v && v.length >= 8) { _cachedStableOSId = v; return v; }
        }
      } catch (e) {}
    }
    if (process.platform === 'win32') {
      try {
        const { execFileSync } = require('child_process');
        const out = execFileSync('reg', ['query', 'HKLM\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'], { encoding: 'utf8', timeout: 3000 });
        const m = String(out || '').match(/MachineGuid\s+REG_SZ\s+(\S+)/i);
        if (m && m[1]) { _cachedStableOSId = m[1].trim().toLowerCase(); return _cachedStableOSId; }
      } catch (e) {}
    }
  } catch (e) {}
  _cachedStableOSId = '';
  return '';
}

function getLocalSeed(licenseDir, legacySeedFilePath, userSeedFilePath) {
  let localSeed = readSeedFile(legacySeedFilePath);
  if (localSeed) {
    if (userSeedFilePath && !readSeedFile(userSeedFilePath)) {
      writeSeedFile(userSeedFilePath, localSeed);
    }
  } else {
    localSeed = readSeedFile(userSeedFilePath);
  }
  if (!localSeed) {
    localSeed = crypto.randomBytes(16).toString('hex');
    if (!writeSeedFile(userSeedFilePath, localSeed)) {
      writeSeedFile(legacySeedFilePath, localSeed);
    }
  }
  return localSeed;
}

function formatHwid(hashHex) {
  const h = String(hashHex).toUpperCase();
  return `HWID-${h.substring(0, 4)}-${h.substring(4, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}`;
}

class LicenseManager {
  constructor(baseDir = null) {
    const base = baseDir || config.dirs.base;
    this.licenseDir = path.join(base, 'license_data');
    this.cacheFilePath = path.join(this.licenseDir, 'license_data.json');
    this.legacySeedFilePath = path.join(this.licenseDir, 'machine_id.node');
    this.seedFilePath = this.legacySeedFilePath;
    const userSeedDir = resolveUserSeedDir();
    this.userSeedFilePath = userSeedDir ? path.join(userSeedDir, 'machine_id.node') : null;
    this.configFilePath = path.join(this.licenseDir, 'license_config.json');

    this.gracePeriodHours = config.license.gracePeriodHours;
    this.isValidating = false;

    this.remoteApiBase = this.getRemoteApiUrl();
  }

  getRemoteApiUrl() {
    if (process.env.REMOTE_LICENSE_API_URL) {
      return process.env.REMOTE_LICENSE_API_URL.replace(/\/$/, '');
    }
    try {
      if (fs.existsSync(this.configFilePath)) {
        const conf = JSON.parse(fs.readFileSync(this.configFilePath, 'utf8'));
        if (conf && conf.serverUrl) {
          return conf.serverUrl.replace(/\/$/, '');
        }
      }
    } catch (e) {}
    return DEFAULT_LICENSE_SERVER_URL;
  }

  ensureLicenseDir() {
    if (!fs.existsSync(this.licenseDir)) {
      try { fs.mkdirSync(this.licenseDir, { recursive: true, mode: 0o700 }); } catch (e) {}
    }
  }

  getLegacyMachineFingerprint() {
    this.ensureLicenseDir();
    const localSeed = getLocalSeed(this.licenseDir, this.legacySeedFilePath, this.userSeedFilePath);
    let physicalMacs = [];
    try {
      const netInterfaces = os.networkInterfaces();
      for (const k in netInterfaces) {
        if (IGNORED_INTERFACE_PATTERNS.some((pat) => pat.test(k))) continue;
        for (const net of netInterfaces[k]) {
          if (net.mac && net.mac !== '00:00:00:00:00:00' && !net.internal) physicalMacs.push(net.mac);
        }
      }
    } catch (e) { physicalMacs = []; }
    let cpuModels = '';
    let username = '';
    try { cpuModels = os.cpus().map((c) => c.model).join(','); } catch (e) {}
    try { username = os.userInfo().username; } catch (e) {}
    const rawInfo = [os.hostname(), os.arch(), os.platform(), cpuModels, os.totalmem(), username, physicalMacs.sort().join(','), localSeed].join('||');
    return formatHwid(crypto.createHash('sha256').update(rawInfo).digest('hex'));
  }

  getMachineFingerprint() {
    // Authoritative stable HWID formula: seed + stable OS id + CPU + arch + platform
    this.ensureLicenseDir();
    const localSeed = getLocalSeed(this.licenseDir, this.legacySeedFilePath, this.userSeedFilePath);
    let cpuModels = '';
    try { cpuModels = os.cpus().map((c) => c.model).join(','); } catch (e) {}
    const rawInfo = [localSeed, getStableOSId(), cpuModels, os.arch(), os.platform()].join('||');
    return formatHwid(crypto.createHash('sha256').update(rawInfo).digest('hex'));
  }

  requestRemoteApi(pathStr, method = 'POST', payload = null) {
    return new Promise((resolve, reject) => {
      const targetUrl = this.getRemoteApiUrl() + pathStr;
      const url = new URL(targetUrl);
      const postData = payload ? JSON.stringify(payload) : null;
      const isHttps = url.protocol === 'https:';
      const httpModule = isHttps ? https : http;

      const options = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname,
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'User-Agent': `${config.appName}/${config.appVersion}`
        },
        timeout: LICENSE_REQUEST_TIMEOUT_MS
      };

      if (postData) {
        options.headers['Content-Length'] = Buffer.byteLength(postData);
      }

      const req = httpModule.request(options, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk.toString());
        res.on('end', () => {
          try {
            const parsed = JSON.parse(body);
            resolve({ statusCode: res.statusCode, data: parsed });
          } catch (e) {
            resolve({ statusCode: res.statusCode, data: { status: 'ERROR', message: body } });
          }
        });
      });

      req.on('error', (err) => {
        reject(err);
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Network timeout connecting to License Server at ' + this.getRemoteApiUrl()));
      });

      if (postData) req.write(postData);
      req.end();
    });
  }

  licenseBody(dataObj) {
    return `${dataObj.license_key}||${dataObj.status}||${dataObj.expires_at || 'LIFETIME'}||${dataObj.last_validated_at}||${dataObj.hwid}`;
  }

  // Verify a SERVER-signed license with the shipped PUBLIC key (RSA-2048,
  // PKCS#1 v1.5, SHA-256). The client never signs, so a locally minted cache
  // can never pass — only the Cloudflare Worker (private key) can produce a
  // valid signature.
  verifyLicenseSignature(dataObj) {
    if (!dataObj || !dataObj.signature) return false;
    const pub = config.license.licensePublicKey;
    if (!pub) return false;
    try {
      return crypto.verify(
        'sha256',
        Buffer.from(this.licenseBody(dataObj), 'utf8'),
        pub,
        Buffer.from(String(dataObj.signature), 'base64')
      );
    } catch (e) { return false; }
  }

  getSavedLicenseCache() {
    try {
      if (fs.existsSync(this.cacheFilePath)) {
        const raw = fs.readFileSync(this.cacheFilePath, 'utf8');
        const cache = JSON.parse(raw);
        if (cache && cache.signature) {
          if (this.verifyLicenseSignature(cache)) {
            return cache;
          } else {
            console.warn('[LicenseManager] TAMPER DETECTED: Cache signature mismatch. Clearing corrupted cache.');
            this.clearLicenseCache();
            return null;
          }
        }
      }
    } catch (e) {
      console.error('[LicenseManager] Error reading cache:', e.message);
    }
    return null;
  }

  saveLicenseCache(cacheObj) {
    try {
      const dir = path.dirname(this.cacheFilePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
      chmodPrivate(dir, 0o700);
      // Store EXACTLY as received — the signature is server-issued. The client
      // must never (re)sign, or the cache could be forged.
      fs.writeFileSync(this.cacheFilePath, JSON.stringify(cacheObj, null, 2), { encoding: 'utf8', mode: 0o600 });
      chmodPrivate(this.cacheFilePath, 0o600);
    } catch (e) {
      console.error('[LicenseManager] Error saving cache:', e.message);
    }
  }

  clearLicenseCache() {
    try {
      if (fs.existsSync(this.cacheFilePath)) {
        fs.unlinkSync(this.cacheFilePath);
      }
    } catch (e) {}
  }

  async validateOrActivateLicense(inputKey = null, forceRemote = false) {
    // Check developer bypass environment flag (disabled in shipped builds;
    // set config.license.allowDevOverride = true for local development only).
    if (config.license.allowDevOverride === true &&
        (process.env.META_DEV_MODE === '1' || process.env.SKIP_LICENSE === '1')) {
      return {
        status: 'ACTIVE',
        isValid: true,
        devMode: true,
        message: 'Running in developer override mode.',
        hwid: this.getMachineFingerprint(),
        license: {
          license_key: 'DEV-MODE-OVERRIDE',
          status: 'ACTIVE',
          license_type: 'DEVELOPER',
          expires_at: 'NEVER'
        }
      };
    }

    if (this.isValidating) {
      const cache = this.getSavedLicenseCache();
      if (cache && cache.status === 'ACTIVE') {
        return { status: 'ACTIVE', isValid: true, license: cache, hwid: this.getMachineFingerprint() };
      }
    }

    this.isValidating = true;
    try {
      const hwid = this.getMachineFingerprint();
      const cache = this.getSavedLicenseCache();
      const keyToValidate = (inputKey || (cache ? cache.license_key : '')).trim().toUpperCase();

      // Micro-cache check (bypassed if explicit key provided or forceRemote is true)
      if (!forceRemote && !inputKey && cache && cache.status === 'ACTIVE' && cache.last_validated_at) {
        const isExpiredLocally = (cache.expires_at && cache.expires_at !== 'LIFETIME' && cache.expires_at !== 'NEVER')
          ? new Date() > new Date(cache.expires_at)
          : false;

        if (!isExpiredLocally) {
          const lastValidTime = new Date(cache.last_validated_at).getTime();
          const ageMinutes = (Date.now() - lastValidTime) / (1000 * 60);
          if (ageMinutes >= 0 && ageMinutes < LICENSE_MICRO_CACHE_MINUTES) {
            return {
              status: 'ACTIVE',
              isValid: true,
              license: cache,
              hwid,
              fromLocalCache: true
            };
          }
        }
      }

      if (!keyToValidate) {
        this.clearLicenseCache();
        return {
          status: 'UNLICENSED',
          message: 'No active license found. Please enter your license key to activate.',
          isValid: false,
          hwid
        };
      }

      // STEP 1: Attempt Authoritative Remote Validation via Cloudflare Workers
      try {
        const endpoint = inputKey ? '/api/license/activate' : '/api/license/validate';
        let previousHwid = null;
        try {
          const legacy = this.getLegacyMachineFingerprint();
          if (legacy && legacy !== hwid) previousHwid = legacy;
        } catch (e) {}
        const payload = {
          licenseKey: keyToValidate,
          hwid,
          ...(previousHwid ? { previousHwid } : {}),
          hostname: os.hostname(),
          platform: process.platform
        };

        const res = await this.requestRemoteApi(endpoint, 'POST', payload);
        const data = res ? res.data : null;

        const serverActive = Boolean(
          data && data.isValid && data.license && data.license.status === 'ACTIVE'
        );
        if (serverActive && this.verifyLicenseSignature(data.license)) {
          // Server signed hwid + last_validated_at; store exactly as received.
          this.saveLicenseCache(data.license);

          return {
            status: 'ACTIVE',
            message: data.message || 'License validated successfully.',
            isValid: true,
            license: data.license,
            hwid
          };
        } else if (serverActive) {
          // Server claimed ACTIVE but returned no verifiable signature. Never
          // surface its success text as if it were one — that produced
          // "License activated successfully!" rendered in the ERROR box.
          this.clearLicenseCache();
          return {
            status: 'UNTRUSTED_SIGNATURE',
            message: 'The license server did not return a valid signature. '
              + 'The licensing authority must be updated (deploy the signing key) '
              + 'before activation can succeed.',
            isValid: false,
            hwid
          };
        } else {
          const isHwidMismatch = Boolean(
            data && (data.status === 'HWID_MISMATCH' || data.code === 'HWID_MISMATCH' || (data.message && data.message.includes('HWID')))
          );
          if (!isHwidMismatch) {
            this.clearLicenseCache();
          }
          return {
            status: (data && data.status) ? data.status : 'INVALID',
            message: (data && data.message) ? data.message : 'License is invalid or suspended.',
            isValid: false,
            hwid
          };
        }
      } catch (netErr) {
        // STEP 2: Fallback to Verified Offline Grace Period if cache exists and signature valid
        console.warn('[LicenseManager] Remote API unreachable. Checking Offline Grace:', netErr.message);
        if (cache) {
          const offlineCheck = this.checkOfflineGracePeriod(cache, hwid);
          if (offlineCheck.isValid) return offlineCheck;
        }
        return {
          status: 'OFFLINE_UNREACHABLE',
          message: `License server unreachable (${netErr.message}). Internet connection required.`,
          isValid: false,
          hwid
        };
      }
    } finally {
      this.isValidating = false;
    }
  }

  checkOfflineGracePeriod(cache, currentHwid) {
    if (!cache || !cache.license_key || !cache.last_validated_at) {
      return { status: 'OFFLINE_NO_CACHE', message: 'Internet connection required for initial activation.', isValid: false, hwid: currentHwid };
    }

    let legacyHwid = null;
    try { legacyHwid = this.getLegacyMachineFingerprint(); } catch (e) {}
    if (cache.hwid && cache.hwid !== currentHwid && cache.hwid !== legacyHwid) {
      // The signature binds this cache to its original HWID and cannot be
      // re-signed client-side, so a mismatch is simply invalid.
      return { status: 'HWID_MISMATCH', message: 'Hardware fingerprint mismatch.', isValid: false, hwid: currentHwid };
    }

    if (cache.expires_at && cache.expires_at !== 'LIFETIME' && cache.expires_at !== 'NEVER') {
      if (new Date() > new Date(cache.expires_at)) {
        this.clearLicenseCache();
        return { status: 'EXPIRED', message: 'License has expired.', isValid: false, hwid: currentHwid };
      }
    }

    const lastValid = new Date(cache.last_validated_at);
    const now = new Date();
    const diffHours = (now - lastValid) / (1000 * 60 * 60);

    if (diffHours <= this.gracePeriodHours) {
      const remainingGraceHours = Math.max(0, Math.round(this.gracePeriodHours - diffHours));
      return {
        status: 'ACTIVE_OFFLINE_GRACE',
        message: `Running in Offline Grace Period (${remainingGraceHours}h remaining). Please connect to internet soon.`,
        isValid: true,
        license: cache,
        hwid: currentHwid,
        isOfflineGrace: true
      };
    }

    this.clearLicenseCache();
    return {
      status: 'OFFLINE_GRACE_EXPIRED',
      message: 'Offline grace period expired. Internet connection required to re-verify license.',
      isValid: false,
      hwid: currentHwid
    };
  }

  async deactivateLicense() {
    const cache = this.getSavedLicenseCache();
    const hwid = this.getMachineFingerprint();
    if (cache && cache.license_key) {
      try {
        await this.requestRemoteApi('/api/license/deactivate', 'POST', {
          licenseKey: cache.license_key,
          hwid
        });
      } catch (e) {}
    }
    this.clearLicenseCache();
    return { success: true, message: 'Device deactivated successfully.' };
  }
}

module.exports = LicenseManager;
