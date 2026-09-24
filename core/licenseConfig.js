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
    fallbackHmacSecret:
      process.env.HMAC_SECRET ||
      '8F19B23E86FBFF4984993F89AEF3D883183451F127C69A8A0359861B3149D0BC',
  }
};
