/**
 * server/diag.js — live failure-reason histogram (read-only), PER ROUTE.
 *
 * Fed from every python engine stdout line by server/context.js
 * (consumeWorkerLine), which passes a `route` derived from the engine slot:
 *   meta | ig | taskly | paygo | fastpay | taskly2fa | fastpay2fa | paygo_pool
 *   | paygo2fa | paygocookie
 * Normalizes free-text failures into a small fixed set of categories.
 * Pure in-memory counters: nothing is persisted, nothing is spawned or killed.
 */

const CATEGORIES = [
  { key: 'no TG profile slot', test: [/No Telegram profile slot available/i] },
  { key: 'accounts center unreachable', test: [/Could not reach Accounts Center/i] },
  { key: 'mobile number required', test: [/Mobile number required/i, /What'?s your mobile number/i] },
  { key: 'password change failed', test: [/password change (failed|rejected|error|stalled|timed out)/i, /\[⚠️\].*password change/i] },
  { key: 'registration not confirmed', test: [/registration not confirmed/i, /bot REJECTED/i] },
  { key: 'could not select task', test: [/Could not select task/i, /task .* not found/i] },
  { key: 'could not retrieve 2fa secret key', test: [/could not retrieve 2fa secret key/i, /2fa secret key/i] },
  { key: 'rendered blank', test: [/rendered blank/i, /rate-limited/i, /rate limited/i] },
  // --- dead ends introduced with the PayGo cookie 2FA/follow work ---
  // Order matters (first match wins): the specific toast/gate first, then the
  // session-dead probes, then the generic pooled dead-end wrapper.
  { key: 'follow dead end (failed to load)', test: [/Failed to Load/i, /follow .*dead end/i] },
  { key: 'email risky contactpoint (dead end)', test: [/email_risky_contactpoint/i, /email may not be secure/i] },
  { key: 'IG session dead (login wall / visitor)', test: [/login wall\/chooser/i, /visitor view/i, /public visitor profile/i, /visitor moderation sheet/i, /session is logged out/i, /saved-account chooser/i] },
  { key: 'pooled IG dead end', test: [/pooled IG dead end/i, /DEAD END \(/i, /\bdead end\b/i] },
];


const STRICT_RE = /STRICT stop/i;
const REASON_CODE_RE = /\breason\s*=\s*([A-Za-z0-9_.-]+)/gi;

const state = {
  // route -> { reasons: {key:count}, passwordReasons: {code:count} }
  routes: Object.create(null),
  updatedAt: null,
};

function _bump(bag, key) {
  bag[key] = (bag[key] || 0) + 1;
}

function _bag(route) {
  const r = String(route || 'unknown');
  if (!state.routes[r]) {
    state.routes[r] = { reasons: Object.create(null), passwordReasons: Object.create(null) };
  }
  return state.routes[r];
}

/**
 * Observe one raw stdout line for a route. Never throws.
 * @param {string} line
 * @param {string} [route]  meta|ig|taskly|paygo|fastpay|taskly2fa|fastpay2fa
 * @returns {string|null} the category counted, or null when nothing matched.
 */
function observe(line, route) {
  if (!line) return null;
  const t = String(line);
  const bag = _bag(route);
  try {
    let hit = null;
    for (const cat of CATEGORIES) {
      if (cat.test.some((re) => re.test(t))) { hit = cat.key; break; }
    }
    if (!hit && STRICT_RE.test(t)) hit = 'other';
    if (hit) _bump(bag.reasons, hit);

    // reason=<code> tokens are orthogonal to the category tally.
    let m;
    REASON_CODE_RE.lastIndex = 0;
    while ((m = REASON_CODE_RE.exec(t)) !== null) {
      _bump(bag.passwordReasons, m[1].toLowerCase());
    }

    if (hit) state.updatedAt = Date.now();
    return hit;
  } catch (e) {
    return null;
  }
}

function _merge(bags) {
  const reasons = Object.create(null);
  const passwordReasons = Object.create(null);
  for (const b of bags) {
    for (const k of Object.keys(b.reasons)) reasons[k] = (reasons[k] || 0) + b.reasons[k];
    for (const k of Object.keys(b.passwordReasons)) passwordReasons[k] = (passwordReasons[k] || 0) + b.passwordReasons[k];
  }
  let total = 0;
  for (const k of Object.keys(reasons)) total += reasons[k];
  return { reasons, passwordReasons, total };
}

/** Immutable snapshot for GET /api/diag/reasons[?route=]. */
function snapshot(route) {
  const updated = state.updatedAt ? new Date(state.updatedAt).toISOString() : null;
  if (route) {
    const b = state.routes[String(route)];
    const m = b ? _merge([b]) : { reasons: {}, passwordReasons: {}, total: 0 };
    return { route: String(route), updated, total: m.total,
             reasons: m.reasons, password_reasons: m.passwordReasons };
  }
  const m = _merge(Object.values(state.routes));
  const routes = {};
  for (const r of Object.keys(state.routes)) {
    const mm = _merge([state.routes[r]]);
    routes[r] = { total: mm.total, reasons: mm.reasons, password_reasons: mm.passwordReasons };
  }
  return { updated, total: m.total, reasons: m.reasons, password_reasons: m.passwordReasons, routes };
}

module.exports = { observe, snapshot, CATEGORIES };
