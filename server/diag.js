/**
 * server/diag.js — live failure-reason histogram (read-only).
 *
 * Fed from every python engine stdout line by server/context.js (consumeWorkerLine).
 * Normalizes free-text failures into a small fixed set of categories.
 * Pure in-memory counters: nothing is persisted, nothing is spawned or killed.
 */

const CATEGORIES = [
  { key: 'no TG profile slot', test: [/No Telegram profile slot available/i] },
  { key: 'accounts center unreachable', test: [/Could not reach Accounts Center/i] },
  { key: 'mobile number required', test: [/Mobile number required/i, /What'?s your mobile number/i] },
  { key: 'password change failed', test: [/password change (failed|rejected|error|stalled|timed out)/i, /\[⚠️\].*password change/i] },
  { key: 'registration not confirmed', test: [/registration not confirmed/i, /bot REJECTED/i] },
  { key: 'could not select task', test: [/Could not select task/i] },
  { key: 'could not retrieve 2fa secret key', test: [/could not retrieve 2fa secret key/i, /2fa secret key/i] },
  { key: 'rendered blank', test: [/rendered blank/i, /rate-limited/i, /rate limited/i] },
];

const STRICT_RE = /STRICT stop/i;
const REASON_CODE_RE = /\breason\s*=\s*([A-Za-z0-9_.-]+)/gi;

const state = {
  reasons: Object.create(null),
  passwordReasons: Object.create(null),
  updatedAt: null,
};

function _bump(bag, key) {
  bag[key] = (bag[key] || 0) + 1;
}

/**
 * Observe one raw stdout line. Never throws (callers are hot stdout handlers).
 * @param {string} line
 * @returns {string|null} the category counted, or null when nothing matched.
 */
function observe(line) {
  if (!line) return null;
  const t = String(line);
  try {
    let hit = null;
    for (const cat of CATEGORIES) {
      if (cat.test.some((re) => re.test(t))) { hit = cat.key; break; }
    }
    if (!hit && STRICT_RE.test(t)) hit = 'other';
    if (hit) _bump(state.reasons, hit);

    // reason=<code> tokens are orthogonal to the category tally.
    let m;
    REASON_CODE_RE.lastIndex = 0;
    while ((m = REASON_CODE_RE.exec(t)) !== null) {
      _bump(state.passwordReasons, m[1].toLowerCase());
    }

    if (hit) state.updatedAt = Date.now();
    return hit;
  } catch (e) {
    return null;
  }
}

/** Immutable snapshot for GET /api/diag/reasons. */
function snapshot() {
  const reasons = {};
  let total = 0;
  for (const k of Object.keys(state.reasons)) {
    reasons[k] = state.reasons[k];
    total += state.reasons[k];
  }
  return {
    updated: state.updatedAt ? new Date(state.updatedAt).toISOString() : null,
    total,
    reasons,
    password_reasons: Object.assign({}, state.passwordReasons),
  };
}

module.exports = { observe, snapshot, CATEGORIES };
