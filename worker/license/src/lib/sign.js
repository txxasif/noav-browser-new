/**
 * Server-side license signing — RSA-2048 / PKCS#1 v1.5 / SHA-256.
 *
 * The PRIVATE key lives ONLY as a Cloudflare Worker secret
 * (`LICENSE_SIGNING_KEY`, PKCS#8 PEM). The matching PUBLIC key is embedded in
 * the desktop clients (`core/licenseConfig.js`, `core/license_mgr.py`) purely
 * for verification. Because the clients can only verify, a license cache minted
 * on a user's machine can never validate — only this Worker can produce a
 * signature.
 *
 * Canonical message (must match the clients byte-for-byte):
 *   `${license_key}||${status}||${expires_at||'LIFETIME'}||${last_validated_at}||${hwid}`
 */

let _keyPromise = null;

function pemToDer(pem) {
  const b64 = String(pem).replace(/-----[^-]+-----/g, '').replace(/\s+/g, '');
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}

async function getKey(env) {
  if (_keyPromise) return _keyPromise;
  const secret = env && env.LICENSE_SIGNING_KEY;
  if (!secret) return null;
  _keyPromise = crypto.subtle.importKey(
    'pkcs8',
    pemToDer(secret),
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  return _keyPromise;
}

export function licenseBody(lic) {
  return `${lic.license_key}||${lic.status}||${lic.expires_at || 'LIFETIME'}||${lic.last_validated_at}||${lic.hwid}`;
}

export async function signLicense(env, lic) {
  const key = await getKey(env);
  if (!key) return null; // misconfigured -> client fails closed
  const sig = await crypto.subtle.sign(
    { name: 'RSASSA-PKCS1-v1_5' },
    key,
    new TextEncoder().encode(licenseBody(lic)),
  );
  const bytes = new Uint8Array(sig);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

/** Stamp last_validated_at, then attach the server signature. */
export async function withSignature(env, license) {
  license.last_validated_at = new Date().toISOString();
  const signature = await signLicense(env, license);
  if (signature) license.signature = signature;
  return license;
}
