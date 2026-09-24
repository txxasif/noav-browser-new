/** Admin auth + license key generator. Behavior unchanged from original. */

export const DEFAULT_ADMIN_PASSWORD = 'tarek123';

export function checkAdminAuth(request, env) {
  const adminPass = (env.ADMIN_PASSWORD || DEFAULT_ADMIN_PASSWORD).trim();
  const authHeader = request.headers.get('Authorization') || '';
  const adminKeyHeader = request.headers.get('X-Admin-Key') || '';
  const token = authHeader.replace('Bearer ', '').trim();
  return token === adminPass || adminKeyHeader === adminPass;
}

export function generateKey() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const segment = () =>
    Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  return `NOVA-${segment()}-${segment()}-${segment()}`;
}
