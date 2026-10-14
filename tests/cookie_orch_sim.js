const o = require(process.cwd() + '/server/cookie-orchestrator.js');
const calls = [];
let running = null;                 // the user's / cookie run currently holding the slot
let stock = true, minutes = 30, hourN = 12;
const slot = { get config() { return running; }, set config(v) { running = v; }, get proc() { return running ? {} : null; }, set proc(v) { if (!v) running = null; } };
o.ctx = { slot: () => slot, writeSettings() {}, readSettings: () => ({}), getAccounts: () => Array.from({length: 5}, () => ({ platform: 'Meta+Instagram', cookies: 'x'.repeat(30), status: 'Created', mail_tokens: { mailfish_api: true } })),
  resolveScript: () => 'x', ROOT_DIR: '/tmp/nonexistent-orch', runPythonJson: async () => ({ ok: true, available: stock, reason: stock ? 'ok' : 'soldout' }), PYTHON_BIN: 'python3' };
o.enabled = true;
o._minutesIntoHour = () => minutes;
o._nowHour = () => 'h' + hourN;
o.startEngine = (cfg) => { calls.push('start:' + cfg.tg_task); running = cfg; };
o.stopCurrentEngine = async () => { calls.push('stop:' + (running && running.tg_task)); running = null; };
o._releaseTgLeases = async () => { calls.push('release'); };
o._log = () => {};
const paygo2fa = { tg_bot: 'paygo', tg_task: 'PayGo 2FA', use_ig_pool: true };
const reset = () => { calls.length = 0; o._lastProbe = 0; o._restoredUntil = 0; o._preemptedHour = null; o._parked = null; o.avail = { taskly: null, paygo: null }; o.reason = { taskly: '', paygo: '' }; o.hourKey = null; };
const check = (name, cond) => console.log((cond ? 'PASS ' : 'FAIL ') + name + '  ' + JSON.stringify(calls));
(async () => {
  // a) mid-hour, other bot running, Taskly has stock -> hands off
  reset(); running = { ...paygo2fa }; minutes = 30; stock = true; await o.tick(); await o.tick();
  check('mid-hour: running bot is left alone', calls.length === 0 && running.tg_task === 'PayGo 2FA');
  // b) :02 refill, stock available -> park PayGo, start Taskly right away
  reset(); running = { ...paygo2fa }; minutes = 2; hourN++; stock = true; await o.tick();
  check(':02 with stock: parks and starts Taskly now', calls.join() === 'stop:PayGo 2FA,release,start:Taskly Cookie' && o._parked && o._parked.tg_task === 'PayGo 2FA');
  // c) Taskly reports sold out -> stop, release, resume PayGo, no more checks this hour
  o.avail.taskly = false; o.reason.taskly = 'soldout'; calls.length = 0; await o.tick();
  check('sold out: stop + release + PayGo resumes', calls.join() === 'stop:Taskly Cookie,release,start:PayGo 2FA');
  calls.length = 0; o._restoredUntil = 0; minutes = 8; await o.tick(); await o.tick();
  check('after that: no re-park, no more probing this hour', calls.length === 0 && running.tg_task === 'PayGo 2FA');
  // d) next :00 -> takes over again
  hourN++; minutes = 1; stock = true; calls.length = 0; o._restoredUntil = 0; await o.tick();
  check('next :00: takes over again', calls.join() === 'stop:PayGo 2FA,release,start:Taskly Cookie');
  // e) :03 refill but Taskly has no stock -> PayGo goes straight back
  reset(); running = { ...paygo2fa }; minutes = 3; hourN++; stock = false; await o.tick();
  check(':03 no stock: PayGo is put straight back', calls.join() === 'stop:PayGo 2FA,release,start:PayGo 2FA');
  // f) nothing running at :00 -> Taskly starts immediately, no grace
  reset(); running = null; minutes = 1; hourN++; stock = true; await o.tick();
  check('idle at :00: Taskly starts at once', calls.join() === 'start:Taskly Cookie');
})();
(async () => {
  await new Promise(r => setTimeout(r, 300));
  // g) Auto-Mine switched OFF while Taskly runs with PayGo parked -> drain stops, PayGo resumes
  reset(); running = { ...paygo2fa }; minutes = 2; hourN += 10; stock = true; o.enabled = true; await o.tick();
  calls.length = 0; o.toggle(false); await new Promise(r => setTimeout(r, 100));
  check('OFF with a parked bot: Taskly drain stops, bot resumes', calls.join() === 'stop:Taskly Cookie,release,start:PayGo 2FA');
  // h) OFF: tick does nothing (no probing / no takeover) even at :00
  calls.length = 0; minutes = 1; hourN++; await o.tick();
  check('OFF: nothing happens at :00', calls.length === 0 && running.tg_task === 'PayGo 2FA');
})();
