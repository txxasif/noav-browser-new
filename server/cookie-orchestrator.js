/**
 * Cookie Auto-Mine Orchestrator
 *
 * Alternates the TWO Instagram "cookie" pool-drains for maximum throughput,
 * keyed to the bots' HOURLY stock refill (:00):
 *
 *   1. Taskly  "🍪 Create Inst (No mail)"      (tg_bot=taskly, label "Taskly Cookie")
 *   2. PayGo   "📱 Create Inst (Cookies)"       (tg_bot=paygo,  label "📱 Create Inst (Cookies)")
 *
 * Priority is Taskly first. When Taskly is SOLD OUT for the hour (or its cookie
 * menu is HIDDEN by the admin) it switches to PayGo; when PayGo is also
 * exhausted/hidden it waits for the next hour. On the :00 rollover both counters
 * reset and Taskly leads again.
 *
 * Availability is read over MTProto by tg_task_probe.py — choose_task() only, so
 * it NEVER presses Start, creates no task and costs nothing (invariant 29/30).
 *
 * Scope: ONLY these two cookie tasks. Any other running bot is left alone.
 */
const path = require('path');
const { buildTgWorkerArgs } = require('./tg-start');
const paygoOrchestrator = require('./paygo-orchestrator');

// Priority order (first = preferred).
const TARGETS = [
  { id: 'taskly', bot: 'taskly', task: 'Taskly Cookie', label: 'Taskly Cookie (No mail)' },
  { id: 'paygo', bot: 'paygo', task: '📱 Create Inst (Cookies)', label: 'PayGo Cookie' },
];

const PROBE_TTL_MS = 20000;    // re-probe availability at most every 20s
const SWITCH_GUARD_MS = 15000; // let a freshly started drain boot before re-eval
const HOUR_GRACE_MS = 90000;   // at :00 let an in-flight task finish before switching

class CookieOrchestrator {
  constructor() {
    this.ctx = null;
    this.enabled = false;
    this.concurrency = 6;
    this.headless = true;
    this.state = 'idle'; // idle | monitoring | running | switching | waiting
    this.avail = { taskly: null, paygo: null }; // null unknown | true | false
    this.reason = { taskly: '', paygo: '' };
    this.hourKey = null;
    this.current = null;   // target id a cookie drain is running (or null)
    this.timer = null;
    this._probing = false;
    this._lastProbe = 0;
    this._switchGuardUntil = 0;
    this._hourGraceUntil = 0;
    this._logTail = [];
    this.lastError = '';
    this.pool = 0;             // IG Creator accounts currently drainable
    this._forcedAt = 0;        // last manual "Start Now" press
    this._lastLogMsg = '';     // throttle repeated identical log lines
    this._lastLogAt = 0;
  }

  init(ctx) {
    this.ctx = ctx;
    const s = ctx.readSettings ? ctx.readSettings() : {};
    this.enabled = !!s.auto_cookie_mine;
    this.concurrency = parseInt(s.auto_cookie_concurrency || 6, 10);
    this.headless = s.auto_cookie_headless !== false;
    this.hourKey = this._nowHour();
    if (this.timer) clearInterval(this.timer);
    this.timer = setInterval(() => this.tick().catch(() => {}), 5000);
    if (this.enabled) this._silencePaygoAuto();
    console.log(`[Cookie-Auto] initialized (enabled=${this.enabled}, conc=${this.concurrency})`);
  }

  // The two toggles were merged into one (Cookie Auto-Mine). When it is on we
  // must not also let the legacy PayGo-only scheduler run, or the two would
  // fight over the single TG slot.
  _silencePaygoAuto() {
    try {
      if (paygoOrchestrator && paygoOrchestrator.enabled) {
        if (typeof paygoOrchestrator.toggle === 'function') paygoOrchestrator.toggle(false);
        else paygoOrchestrator.enabled = false;
      }
      if (this.ctx && this.ctx.writeSettings) this.ctx.writeSettings({ auto_paygo_refill: false });
    } catch (e) {}
  }

  toggle(on, concurrency) {
    this.enabled = !!on;
    if (concurrency != null) this.concurrency = parseInt(concurrency || 6, 10);
    try {
      this.ctx.writeSettings({ auto_cookie_mine: this.enabled, auto_cookie_concurrency: this.concurrency });
    } catch (e) {}
    if (!this.enabled) {
      this.state = 'idle';
      this._log('Auto-Mine OFF.');
    } else {
      this.state = 'monitoring';
      this.avail = { taskly: null, paygo: null };
      this._lastProbe = 0;
      this._silencePaygoAuto();
      this._log('Auto-Mine ON — Taskly Cookie leads, PayGo Cookie fallback (hourly :00).');
    }
    return this.getStatus();
  }

  getStatus() {
    return {
      enabled: this.enabled,
      state: this.state,
      concurrency: this.concurrency,
      current: this.current,
      target: this.current ? (TARGETS.find(t => t.id === this.current) || {}).label : null,
      avail: this.avail,
      reason: this.reason,
      pool: this.pool || 0,
      wait_seconds: this._secondsToNextHour(),
      hour: this.hourKey,
      last_error: this.lastError,
      log_tail: this._logTail.slice(-6),
    };
  }

  _log(msg) {
    const now = Date.now();
    // Collapse identical repeated lines (e.g. the pool-empty wait) to once/60s.
    if (msg === this._lastLogMsg && now - this._lastLogAt < 60000) return;
    this._lastLogMsg = msg;
    this._lastLogAt = now;
    const line = `[Cookie-Auto] ${msg}`;
    console.log(line);
    this._logTail.push(msg);
    if (this._logTail.length > 40) this._logTail.shift();
    try {
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg', message: `🍪 ${line}` });
      }
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({ type: 'cookie_auto_status', status: this.getStatus() });
      }
    } catch (e) {}
  }

  _nowHour() {
    const n = new Date();
    return `${n.getFullYear()}-${n.getMonth()}-${n.getDate()}-${n.getHours()}`;
  }

  _slot() { return this.ctx ? this.ctx.slot('tg') : null; }

  _currentJob() {
    const slot = this._slot();
    return slot ? slot.config : null;
  }

  _isCookieJob(cfg) {
    if (!cfg || !cfg.use_ig_pool) return false;
    const task = String(cfg.tg_task || '');
    const bot = String(cfg.tg_bot || '').toLowerCase();
    if (/2fa/i.test(task)) return false;
    if (bot === 'taskly' && /taskly cookie/i.test(task)) return true;
    if (bot === 'paygo' && /cookie|🍪/i.test(task)) return true;
    return false;
  }

  _cookieTargetOf(cfg) {
    if (!this._isCookieJob(cfg)) return null;
    const bot = String(cfg.tg_bot || '').toLowerCase();
    return (TARGETS.find(t => t.bot === bot) || {}).id || null;
  }

  _poolCount() {
    try {
      const accs = this.ctx.getAccounts() || [];
      // Same strict filter the PayGo orchestrator uses for a drainable account:
      // an IG-Creator-style record that actually carries a usable cookie string.
      const n = accs.filter(a =>
        (a.platform === 'Meta+Instagram' || a.cookies) &&
        (a.status === 'Created' || !a.status) &&
        a.cookies && String(a.cookies).length > 20
      ).length;
      this.pool = n;
      return n;
    } catch (e) { this.pool = 0; return 0; }
  }

  _secondsToNextHour() {
    const now = new Date();
    const next = new Date(now);
    next.setHours(now.getHours() + 1, 0, 0, 0);
    return Math.max(0, Math.floor((next.getTime() - now.getTime()) / 1000));
  }

  _desired() {
    // First target that is NOT confirmed unavailable (unknown counts as available).
    for (const t of TARGETS) {
      if (this.avail[t.id] !== false) return t;
    }
    return null;
  }

  async tick() {
    if (!this.enabled || !this.ctx) return;

    // :00 rollover — counters reset, Taskly leads again.
    const hk = this._nowHour();
    if (hk !== this.hourKey) {
      this.hourKey = hk;
      this.avail = { taskly: null, paygo: null };
      this.reason = { taskly: '', paygo: '' };
      this._lastProbe = 0;
      this._switchGuardUntil = Date.now() + HOUR_GRACE_MS; // let the in-flight task finish
      this._log('⏰ :00 rollover — counters reset; Taskly leads again.');
    }

    // A manual "Start Now" press ignores the hour grace / switch guard once.
    const forced = this._forcedAt > 0 && Date.now() - this._forcedAt < 30000;
    if (forced) { this._switchGuardUntil = 0; this._forcedAt = 0; }

    const cur = this._currentJob();
    this.current = this._cookieTargetOf(cur);

    // Keep the drainable-pool count fresh on every tick (5s). The IG Creator
    // fills this pool in the background; we simply re-read it and start the
    // moment it is non-empty — no extra action needed.
    this.pool = this._poolCount();

    // Probe availability (throttled).
    if (!this._probing && Date.now() - this._lastProbe > PROBE_TTL_MS) {
      await this.probeAll();
    }

    const want = this._desired();
    if (!want) {
      this.state = 'waiting';
      if (this.current) {
        this._log('🛑 Both cookie tasks sold out / hidden — stopping the drain; waiting for the next hour (:00).');
        await this.stopCurrentEngine();
        this.current = null;
      }
      return;
    }

    // Running the preferred target already → done.
    if (this.current === want.id) { this.state = 'running'; return; }

    // A non-cookie bot is running (user's own) — do not touch it.
    if (cur && !this.current) { this.state = 'monitoring'; return; }

    // Guard: let a freshly started drain boot / an in-flight task finish.
    if (Date.now() < this._switchGuardUntil) { this.state = 'switching'; return; }

    // A different COOKIE drain is running → switch to the preferred one.
    if (this.current) {
      this._log(`🔁 ${this.current} exhausted (${this.reason[this.current] || 'limit'}) → switching to ${want.id}.`);
      await this.stopCurrentEngine();
      this.current = null;
    }

    // No drainable account yet: WAIT and re-check — this tick runs every 5s and
    // picks the account up the moment the IG Creator has produced one.
    if (this.pool <= 0) {
      this.state = 'pool_empty';
      this._log(`⏳ IG Creator pool empty (0 usable cookies). Waiting for the IG Creator to create accounts — auto-starts ${want.label} as soon as one is ready.`);
      return;
    }

    this._log(`▶️ Starting ${want.label} (conc=${this.concurrency}, pool=${this.pool}).`);
    this.state = 'switching';
    await this.startTarget(want);
    this._switchGuardUntil = Date.now() + SWITCH_GUARD_MS;
  }

  // Manual "Start Now": probe + launch the preferred drain immediately,
  // ignoring the :00 grace and switch guard (sold-out is still respected).
  forceTick() {
    this._forcedAt = Date.now();
    this._lastProbe = 0; // force a fresh availability probe
    this.pool = this._poolCount();
    this.tick().catch(() => {});
    return this.getStatus();
  }

  async probeAll() {
    this._probing = true;
    try {
      for (const t of TARGETS) {
        const r = await this.probeOne(t);
        if (r && r.ok && !r.busy) {
          this.avail[t.id] = !!r.available;
          this.reason[t.id] = r.reason || (r.available ? 'ok' : 'hidden');
        } else if (r && r.busy) {
          // All TG profiles leased (a drain is running) — keep last known value.
        } else {
          this.avail[t.id] = null;
          this.reason[t.id] = (r && r.error) ? String(r.error).slice(0, 80) : 'probe-failed';
        }
      }
      this._lastProbe = Date.now();
    } finally {
      this._probing = false;
    }
  }

  async probeOne(t) {
    const script = this.ctx.resolveScript ? this.ctx.resolveScript('tg_task_probe.py')
      : path.join(this.ctx.ROOT_DIR, 'tg_task_probe.py');
    const args = [script, '--bot', t.bot, '--task', t.task];
    try {
      const res = await this.ctx.runPythonJson(this.ctx.PYTHON_BIN, this.ctx.ROOT_DIR, script, args, 45000);
      return res || null;
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e).slice(0, 80) };
    }
  }

  async startTarget(t) {
    const cfg = {
      tg_bot: t.bot,
      tg_task: t.task,
      use_ig_pool: true,
      cookie_2fa: true,          // follow 5 + (mock) 2FA + cookie submit
      concurrency: this.concurrency,
      headless: this.headless,
      target: 0,
      delay: 8,
      captcha: 'extension',
    };
    this.startEngine(cfg);
    this.current = t.id;
  }

  async stopCurrentEngine() {
    const slot = this._slot();
    if (!slot || !slot.proc) return;
    const proc = slot.proc;
    proc.__preemptKilled = true;
    return new Promise(resolve => {
      let done = false;
      const finish = () => { if (!done) { done = true; slot.proc = null; slot.config = null; resolve(); } };
      proc.once('close', finish);
      proc.once('exit', finish);
      const forceTimer = setTimeout(() => {
        try {
          if (process.platform !== 'win32') { try { process.kill(-proc.pid, 'SIGKILL'); } catch (e) {} }
          else { try { proc.kill('SIGKILL'); } catch (e) {} }
        } catch (e) {}
        finish();
      }, 8000);
      try {
        if (process.platform !== 'win32') {
          try { process.kill(-proc.pid, 'SIGTERM'); } catch (e) { proc.kill('SIGTERM'); }
        } else { proc.kill(); }
      } catch (e) { finish(); }
    });
  }

  startEngine(cfg) {
    if (!this.ctx) return;
    const slot = this._slot();
    if (!slot) return;
    if (slot.proc) { console.log('[Cookie-Auto] slot busy — not starting'); return; }
    const args = buildTgWorkerArgs(cfg, this.ctx.resolveScript('worker.py'));
    slot.config = cfg;
    try {
      const fs = require('fs');
      const isWin = process.platform === 'win32';
      const browsersDir = fs.existsSync(path.join(this.ctx.ROOT_DIR, '_internal', 'ms-playwright'))
        ? path.join(this.ctx.ROOT_DIR, '_internal', 'ms-playwright')
        : path.join(this.ctx.ROOT_DIR, 'engine', 'ms-playwright');
      const env = Object.assign({}, process.env, {
        PYTHONUNBUFFERED: '1', PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8',
        PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH || browsersDir,
      });
      if (this.ctx.resetWorkerBuffer) this.ctx.resetWorkerBuffer('tg');
      slot.proc = require('child_process').spawn(this.ctx.PYTHON_BIN, args, {
        cwd: this.ctx.ROOT_DIR, windowsHide: true, detached: !isWin, env,
      });
      slot.proc.stdout.on('data', data => {
        for (const line of this.ctx.feedWorkerStdout(data, 'tg')) this.ctx.consumeWorkerLine(line, 'tg');
      });
      slot.proc.stderr.on('data', data => {
        const text = data.toString('utf-8').trim();
        if (text && !/socket\.send\(\)/i.test(text)) {
          this.ctx.broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg', message: `[STDERR] ${text}` });
        }
      });
      slot.proc.on('close', () => this.notifyLoopStopped(slot.proc));
    } catch (e) {
      this.lastError = String((e && e.message) || e).slice(0, 120);
      console.log(`[Cookie-Auto] startEngine failed: ${this.lastError}`);
    }
  }

  notifyLoopStopped(proc) {
    if (proc && proc.__preemptKilled) return; // our own stop
    const slot = this._slot();
    if (slot && slot.proc === proc) { slot.proc = null; slot.config = null; }
    this.current = null;
    // The drain ended by itself (pool empty / crashed) — the next tick re-evaluates.
  }

  notifyUserStopped() {
    const slot = this._slot();
    if (slot) { slot.proc = null; slot.config = null; }
    this.current = null;
    if (this.enabled) this.state = 'monitoring';
  }
}

module.exports = new CookieOrchestrator();
