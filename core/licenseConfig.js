/**
 * Meta Creator — Centralized License Configuration (core/licenseConfig.js)
 * Defines authoritative Cloudflare Worker license server endpoints,
 * cryptographic constants, timeouts, and offline grace rules.
 */

const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');

module.exports = {
  appName: 'Meta Creator',
  appVersion: '1.0.0',

  app: {
    name: 'Meta Creator',
    version: '1.0.0'
  },

  updates: {
    enabled: true,
    feedUrl: process.env.UPDATE_FEED_URL || 'https://raw.githubusercontent.com/ahasifff/meta-creator-release/main/latest.json',
    requestTimeoutMs: 10000
  },

  dirs: {
    base: ROOT_DIR,
    licenseData: path.join(ROOT_DIR, 'license_data'),
  },

  files: {
    licenseCache: path.join(ROOT_DIR, 'license_data', 'license_data.json'),
    machineSeed: path.join(ROOT_DIR, 'license_data', 'machine_id.node'),
    licenseConfig: path.join(ROOT_DIR, 'license_data', 'license_config.json'),
  },

  license: {
    // Cloudflare Workers + D1 License Authority
    defaultServerUrl: 'https://nova-license.ahasiffff.workers.dev',
    requestTimeoutMs: 10000,
    // 3-Minute Smart Micro-Cache for low-latency requests
    microCacheMinutes: 3,
    // 72-Hour Verified Offline Grace Period
    gracePeriodHours: 72,
    // ASYMMETRIC LICENSE SIGNING (RSA-2048 / PKCS#1 v1.5 / SHA-256).
    // The Cloudflare Worker signs each ACTIVE license with its PRIVATE key
    // (Worker secret `LICENSE_SIGNING_KEY`); this client ONLY verifies with the
    // PUBLIC key below. No signing secret ships in the app, so a license cache
    // cannot be forged client-side. Replacing this key requires the matching
    // private key on the server.
    licensePublicKey: `-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3gjzxA5Jf/zQTMkFaBKX
UzkJONNB6AAZ7jjdGwnQgn4NqHOosPgMipfGVNiBQtCwy4ic6Qhuj7WgSqDe8k6K
ztT9Shc+CJkK9xSIe5OeEz21Y3Wad9dAOYqmT9llDIxSP69Rle67k4NuwBYvIbdk
aWO30TYhLAk1IRp5DkfXCNlyu/QBfHUPEvr/FF5gRMVVTQhQyD2Dxr6T4lL4Him3
dy6/fxZhNxyBKH935X8WNd9nI1Knqj2Lt0rqLcqiIZPI8MuB9yXZrv87iOZKH+M6
J2USAxZVGYPzn1JzwWzQ1YWSLSuBqabxuF6i77hfpdXinEHkBA/icuYbphq20p1d
kQIDAQAB
-----END PUBLIC KEY-----
`,
    // Dev override (META_DEV_MODE/SKIP_LICENSE env) is disabled in shipped
    // builds. Set true locally only for development.
    allowDevOverride: false,
  }
};
