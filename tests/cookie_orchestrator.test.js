// Run: node tests/cookie_orchestrator.test.js
// Covers the Auto-Mine rules that decide whether a USER's run may be preempted.
const assert = require('assert');
const orch = require('../server/cookie-orchestrator');

function fresh(settings, job, pool) {
  const written = {};
  const slot = { proc: job ? { pid: 1 } : null, config: job || null };
  orch.ctx = null;
  orch.enabled = false;
  orch.current = null;
  orch._parked = null;
  orch._restoredUntil = 0;
  orch._switchGuardUntil = 0;
  orch._lastProbe = Date.now();           // no probe during the test
  orch.avail = { taskly: null, paygo: null };
  orch.reason = { taskly: '', paygo: '' };
  const calls = { stopped: 0, started: [] };
  const ctx = {
    readSettings: () => Object.assign({}, settings),
    writeSettings: (o) => Object.assign(written, o),
    slot: () => slot,
    getAccounts: () => Array.from({ length: pool }, () => ({ status: 'Created', cookies: 'x'.repeat(40) })),
    broadcastEvent: () => {},
  };
  orch.init(ctx);
  clearInterval(orch.timer);              // drive ticks by hand
  orch.stopCurrentEngine = async () => { calls.stopped++; slot.proc = null; slot.config = null; };
  orch.startTarget = async (t) => { calls.started.push(t.id); orch.current = t.id; };
  orch.probeAll = async () => {};
  orch.enabled = true;
  return { ctx, slot, calls, written };
}

const PAYGO_2FA = { use_ig_pool: true, tg_bot: 'paygo', tg_task: 'PayGo 2FA' };

(async () => {
  // 1. user's PayGo 2FA run + Taskly stock UNKNOWN -> must NOT be parked
  let t = fresh({}, PAYGO_2FA, 5);
  await orch.tick();
  assert.strictEqual(t.calls.stopped, 0, 'unknown stock must not kill the user run');
  assert.deepStrictEqual(t.calls.started, []);
  assert.ok(t.slot.proc, 'user run still alive');

  // 2. Taskly CONFIRMED available -> the cookie drain may take the slot
  t = fresh({}, PAYGO_2FA, 5);
  orch.avail.taskly = true;
  await orch.tick();
  assert.strictEqual(t.calls.stopped, 1, 'confirmed stock parks the user run');
  assert.deepStrictEqual(t.calls.started, ['taskly']);

  // 3. Taskly known sold out -> user run left alone
  t = fresh({}, PAYGO_2FA, 5);
  orch.avail.taskly = false; orch.reason.taskly = 'soldout';
  await orch.tick();
  assert.strictEqual(t.calls.stopped, 0);
  assert.deepStrictEqual(t.calls.started, []);

  // 4. nothing running + unknown stock -> the preferred drain is still tried
  t = fresh({}, null, 5);
  await orch.tick();
  assert.deepStrictEqual(t.calls.started, ['taskly']);

  // 5. sold-out verdict survives a restart within the same hour
  const hour = orch._nowHour();
  t = fresh({ auto_cookie_state: { hour, avail: { taskly: false, paygo: null }, reason: { taskly: 'soldout', paygo: '' } } }, PAYGO_2FA, 5);
  assert.strictEqual(orch.avail.taskly, false, 'restored after restart');
  assert.strictEqual(orch.reason.taskly, 'soldout');
  // ...and turning Auto-Mine off/on must not forget it
  orch.toggle(true);
  assert.strictEqual(orch.avail.taskly, false, 'toggle keeps this hour\'s sold-out');

  // 6. a saved state from ANOTHER hour is ignored
  t = fresh({ auto_cookie_state: { hour: 'old-hour', avail: { taskly: false, paygo: null }, reason: { taskly: 'soldout', paygo: '' } } }, null, 5);
  assert.strictEqual(orch.avail.taskly, null);

  // 7. persisted when a verdict is recorded
  t = fresh({}, null, 5);
  orch.avail.taskly = false; orch.reason.taskly = 'soldout';
  orch._persist();
  assert.strictEqual(t.written.auto_cookie_state.avail.taskly, false);
  assert.strictEqual(t.written.auto_cookie_state.hour, orch.hourKey);

  console.log('cookie orchestrator: all checks passed');
  process.exit(0);
})().catch((e) => { console.error(e); process.exit(1); });
