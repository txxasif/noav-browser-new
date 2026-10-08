'use strict';

/**
 * Shared TG worker launch construction.
 *
 * Both the `/api/tg/start` route (server/routes-tg.js) and the PayGo auto-mining
 * orchestrator (server/paygo-orchestrator.js) spawn `worker.py` with the same
 * flag set. This module is the single source of truth for that argv list and for
 * the runlog/diagnostics route tag, so the two call sites cannot drift.
 */

// Stable route tag for a TG run, mirroring the id consumed by runlog/diag.
// taskly2fa | tasklycookie | fastpay2fa | paygo2fa | paygocookie | paygo_pool | else tgBot
function tgRouteOf(tgBot, tgTask, useIgPool) {
  const bot = tgBot;
  const task = String(tgTask == null ? '' : tgTask);
  if (bot === 'taskly' && /taskly\s*2fa|pool\s*2fa/i.test(task)) return 'taskly2fa';
  if (bot === 'taskly' && /taskly cookie/i.test(task)) return 'tasklycookie';
  if (bot === 'fastpay' && /fastpay\s*2fa|fastpay_pool/i.test(task)) return 'fastpay2fa';
  if (bot === 'paygo' && /paygo\s*2fa/i.test(task) && !/normal/i.test(task)) return 'paygo2fa';
  if (bot === 'paygo' && /paygo cookie/i.test(task)) return 'paygocookie';
  if (bot === 'paygo' && useIgPool) return 'paygo_pool';
  return bot;
}

/**
 * Build the worker.py argv list for a TG run.
 *
 * @param {object} cfg   Resolved launch config (the same shape stored on the
 *                       engine slot: concurrency/target/delay/captcha/tg_task/
 *                       tg_bot/twofa/use_ig_pool/cookie_2fa/headless; plus
 *                       add_email where the caller tracks it).
 * @param {string} workerScript  Absolute path to worker.py (resolved by the caller).
 * @returns {string[]} argv, ready for spawn().
 */
function buildTgWorkerArgs(cfg, workerScript) {
  const c = cfg || {};
  const tgTask = c.tg_task || '📱 Create Inst (Cookies)';
  const tgBot = c.tg_bot || 'paygo';

  const args = [
    workerScript,
    '--concurrency', String(c.concurrency || 6),
    '--target', String(c.target || 0),
    '--delay', String(c.delay || 8),
    '--mail', 'mailtd',
    '--captcha', c.captcha || 'extension',
    '--mode', 'meta',
    '--coupled',
    '--tg-task', tgTask,
    '--tg-bot', tgBot,
  ];
  if (c.twofa !== false) args.push('--twofa');

  // Belt-and-braces with the dashboard guard: the native Taskly-2FA flow has no
  // mailbox step (bot email+code), so --add-email must never reach the worker
  // for it even if a stale client sends true.
  let addEmail = (c.add_email === true || c.add_email === 'true');
  if (tgBot === 'taskly' && /2fa/i.test(tgTask) && !/no.mail/i.test(tgTask) && !/cookie/i.test(tgTask)) {
    addEmail = false;
  }
  if (addEmail) args.push('--add-email');

  // Cookie-family tasks. NOTE: Taskly's label is "🍪 Create Inst (No mail)" —
  // no ASCII "cookie", only 🍪 — so match that marker too (same class of bug
  // as the old registry substring match).
  if (/cookie|🍪/i.test(tgTask)) args.push('--cookie');
  if (c.use_ig_pool) args.push('--use-ig-pool');
  // Cookie pool account SOURCE: 'meta' drains the Meta Creator list (IG login ->
  // join -> follow -> cookie) instead of the IG Creator pool. Default 'ig'.
  if (c.use_ig_pool && c.account_source === 'meta') args.push('--account-source', 'meta');
  // NEW PayGo cookies protocol: only when EXPLICITLY enabled (default = legacy
  // browserless drain). Truthy strings accepted (forms/orchestrator callers).
  const _isTrue = v => (v === true || v === 'true');
  if (c.use_ig_pool && /cookie|🍪/i.test(tgTask) && _isTrue(c.cookie_2fa)) args.push('--cookie-2fa');
  // Browserless IG private-API path (opt-in; default = the existing browser
  // logic). Handles rename/email/2FA/password/follow/cookie via the API.
  if (_isTrue(c.ig_api)) args.push('--ig-api');
  // API-mode-only: submit a MOCK 2FA key instead of enabling real 2FA.
  if (_isTrue(c.ig_api) && _isTrue(c.ig_api_mock)) args.push('--ig-api-mock');
  // Cookie-bot failover: try bots in dashboard priority order, first available wins.
  if (/cookie|🍪/i.test(tgTask) && _isTrue(c.fallback)) args.push('--tg-fallback');
  // Fleet chain (universal page): ordered pairs tried across runners.
  if (Array.isArray(c.fleet) && c.fleet.length) {
    try { args.push('--tg-fleet-json', JSON.stringify(c.fleet.slice(0, 8))); } catch (e) {}
  }
  if (c.headless) args.push('--headless');

  return args;
}

module.exports = { buildTgWorkerArgs, tgRouteOf };
