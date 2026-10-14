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
  // PayGo Cookie is not part of Auto-Mine: when Taskly is exhausted for the hour the previous run resumes.
];

const PROBE_TTL_MS = 20000;    // re-probe availability at most every 20s
const SWITCH_GUARD_MS = 15000; // let a freshly started drain boot before re-eval
const PREEMPT_WINDOW_MIN = 10; // Taskly may take over a running bot only in the first minutes of an hour (stock refill)
const STOP_GRACE_MS = 240000;    // sold out: accounts already mid-cycle may finish this long before the engine is force-killed
const PREEMPT_GRACE_MS = 30000; // :00 refill / target switch: Taskly is time-critical, so a shorter window
const RESTORE_HOLD_MS = 60000; // after resuming a parked run, don't park it again for a minute (no flapping)

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
    this._parked = null;   // the user's run config, held while a cookie drain has the slot
    this._restoredUntil = 0;
    this._preemptedHour = null; // hour key of the last :00 takeover attempt (once per hour)
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
    // Sold-out is a fact about THIS hour; keep it across restarts so a fresh process does not
    // re-try (and disrupt a running job to re-learn) a task that is already known sold out.
    const saved = s.auto_cookie_state;
    if (saved && saved.hour === this.hourKey && saved.avail) {
      this.avail = Object.assign({ taskly: null, paygo: null }, saved.avail);
      this.reason = Object.assign({ taskly: '', paygo: '' }, saved.reason || {});
    }
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
      this._log('Auto-Mine OFF — no more automatic switching.');
      this._disableCleanup().catch(() => {});
    } else {
      this.state = 'monitoring';
      for (const id of Object.keys(this.avail)) {
        if (!(this.avail[id] === false && this.reason[id] === 'soldout')) { this.avail[id] = null; this.reason[id] = ''; }
      }
      this._lastProbe = 0;
      this._silencePaygoAuto();
      this._log('Auto-Mine ON — Taskly Cookie takes priority at every :00; other bots resume when it is exhausted.');
    }
    return this.getStatus();
  }

  // Switching Auto-Mine OFF while it has a bot paused: end the Taskly drain it started, free the Telegram
  // profiles and resume that bot, so the user's run is not lost. With nothing paused the drain (if any)
  // keeps running; it is then an ordinary run the user stops by hand.
  async _disableCleanup() {
    if (this.current && this._parked) {
      await this.stopCurrentEngine(PREEMPT_GRACE_MS);
      this.current = null;
      await this._releaseTgLeases();
    }
    await this._restoreParked();
  }

  _persist() {
    try {
      if (this.ctx && this.ctx.writeSettings) {
        this.ctx.writeSettings({ auto_cookie_state: { hour: this.hourKey, avail: this.avail, reason: this.reason } });
      }
    } catch (e) {}
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
      // an IG-Creator-style record that actually carries a usable cookie string. Every mail mode counts
      // (store.py drain_ok no longer filters by mode; INSTA_DRAIN_MODE_FILTER=1 restores it).
      const n = accs.filter(a =>
        (a.platform === 'Meta+Instagram' || a.cookies) &&
        (a.status === 'Created' || !a.status) &&
        a.cookies && String(a.cookies).length > 20
      ).length;
      this.pool = n;
      return n;
    } catch (e) { this.pool = 0; return 0; }
  }

  _minutesIntoHour() {
    const n = new Date();
    return n.getMinutes() + n.getSeconds() / 60;
  }

  // Free every Telegram profile lease (data/tg_accounts.json) after an engine was stopped, so the next
  // run - the resumed bot or the Taskly drain - never waits on a profile a dead worker still "holds".
  // Inspection holds (dashboard windows) are left alone.
  async _releaseTgLeases() {
    try {
      const fs = require('fs');
      const f = path.join(this.ctx.ROOT_DIR, 'data', 'tg_accounts.json');
      if (!fs.existsSync(f)) return;
      const raw = JSON.parse(fs.readFileSync(f, 'utf8'));
      const list = Array.isArray(raw) ? raw : (raw.accounts || []);
      let changed = 0;
      for (const a of list) {
        if (a.status !== 'busy') continue;
        if (/inspect/i.test(String(a.lease_note || ''))) continue;
        a.status = 'idle'; a.busy_bot = null; a.leased_at = null; a.lease_note = null;
        delete a.lease_pid; delete a.probe_pid;
        changed++;
      }
      if (changed) {
        fs.writeFileSync(f, JSON.stringify(raw, null, 2), 'utf8');
        this._log(`🔓 Released ${changed} Telegram profile lease(s).`);
      }
    } catch (e) {}
  }

  _secondsToNextHour() {
    const now = new Date();
    const next = new Date(now);
    next.setHours(now.getHours() + 1, 0, 0, 0);
    return Math.max(0, Math.floor((next.getTime() - now.getTime()) / 1000));
  }

  _desired() {
    // The preferred target (first in TARGETS) may be tried while its stock is unknown.
    // A fallback target must be CONFIRMED available by a probe first: while a drain holds
    // every profile the probe reports busy, and starting a blind fallback burns the hour.
    for (let i = 0; i < TARGETS.length; i++) {
      const t = TARGETS[i];
      if (this.avail[t.id] === false) continue;
      if (i > 0 && this.avail[t.id] !== true) continue;
      return t;
    }
    return null;
  }

  async tick() {
    if (!this.enabled || !this.ctx) return;
    // A graceful stop is in progress (the tick fires every 5s): do not start a second one.
    if (this._stopPromise) { this.state = 'draining'; return; }

    // :00 rollover — counters reset, Taskly leads again.
    const hk = this._nowHour();
    if (hk !== this.hourKey) {
      this.hourKey = hk;
      this.avail = { taskly: null, paygo: null };
      this.reason = { taskly: '', paygo: '' };
      this._lastProbe = 0;
      this._switchGuardUntil = 0;                          // the refill is the moment to work: no grace period
      this._log('⏰ :00 rollover — counters reset; Taskly leads again.');
      this._persist();
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
        // Sold out only blocks NEW bot tasks (they fail at task selection and cost nothing). Accounts that
        // already started a task are mid-follow/2FA/cookie: killing the engine wastes them and leaves their
        // bot task stuck. Stop gracefully (no new cycles, in-flight ones finish); force-kill only after
        // STOP_GRACE_MS.
        this._log('🛑 Taskly Cookie exhausted for this hour — no new tasks; letting in-flight accounts finish, then releasing the Telegram profiles (no more checks until the next :00).');
        this.state = 'draining';
        await this.stopCurrentEngine(STOP_GRACE_MS);
        this.current = null;
        await this._releaseTgLeases();
      }
      await this._restoreParked();
      return;
    }

    // Running the preferred target already → done.
    if (this.current === want.id) { this.state = 'running'; return; }

    // A non-cookie run (the user's) holds the slot. Taskly Cookie has priority, but ONLY at the hourly
    // refill: in the first minutes after :00 it parks that run, reads the stock, and either takes the
    // slot (the run resumes when Taskly is exhausted) or puts the run straight back when Taskly has
    // nothing. Outside that window the running bot is left completely alone - no probing, no pausing -
    // until the next :00 (or a manual "Start Now").
    if (cur && !this.current) {
      if (this.pool <= 0 || Date.now() < this._restoredUntil) { this.state = 'monitoring'; return; }
      const inWindow = this._minutesIntoHour() < PREEMPT_WINDOW_MIN;
      if (!(inWindow || forced) || this.avail[want.id] === false || this._preemptedHour === this.hourKey) {
        this.state = 'monitoring';
        return;
      }
      this._preemptedHour = this.hourKey;
      this._parked = Object.assign({}, cur);
      this._log(`⏸ :00 refill — pausing ${cur.tg_task || 'current run'} (${cur.tg_bot}); ${want.label} has priority.`);
      await this.stopCurrentEngine(PREEMPT_GRACE_MS);
      await this._releaseTgLeases();
      this._lastProbe = 0;
      await this.probeAll();
      if (this.avail[want.id] !== true) {
        this.state = 'monitoring';
        this._log(`↩ ${want.label} has no stock (${this.reason[want.id] || 'unknown'}) — resuming ${cur.tg_task || 'the previous run'}.`);
        await this._restoreParked();
        return;
      }
      this._switchGuardUntil = 0;                 // start immediately
    }

    // Guard: let a freshly started drain boot / an in-flight task finish.
    if (Date.now() < this._switchGuardUntil) { this.state = 'switching'; return; }

    // A different COOKIE drain is running → switch to the preferred one.
    if (this.current) {
      this._log(`🔁 ${this.current} exhausted (${this.reason[this.current] || 'limit'}) → switching to ${want.id}.`);
      await this.stopCurrentEngine(PREEMPT_GRACE_MS);
      this.current = null;
    }

    // No drainable account yet: WAIT and re-check — this tick runs every 5s and
    // picks the account up the moment the IG Creator has produced one.
    if (this.pool <= 0) {
      this.state = 'pool_empty';
      this._log(`⏳ IG Creator pool empty (0 usable cookies). Waiting for the IG Creator to create accounts — auto-starts ${want.label} as soon as one is ready.`);
      await this._restoreParked();
      return;
    }

    this._log(`▶️ Starting ${want.label} (conc=${this.concurrency}, pool=${this.pool}).`);
    this.state = 'switching';
    await this.startTarget(want);
    this._switchGuardUntil = Date.now() + SWITCH_GUARD_MS;
  }

  // Resume the run that was parked for the cookie drain (no-op while a cookie drain runs).
  async _restoreParked() {
    if (!this._parked || this.current) return;
    const cfg = this._parked;
    this._parked = null;
    this._restoredUntil = Date.now() + RESTORE_HOLD_MS;
    this._log(`▶️ Cookie drain finished — resuming ${cfg.tg_task || 'the previous run'} (${cfg.tg_bot}).`);
    this.startEngine(cfg);
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
    // While an engine runs, its workers hold the Telegram session files. A probe is a
    // second process on the same account, which SQLite reports as "database is locked".
    // The running drain reports sold-out itself (see the stdout handler), so skip here.
    const slot = this._slot();
    if (slot && slot.proc) { this._lastProbe = Date.now(); return; }
    this._probing = true;
    try {
      for (const t of TARGETS) {
        // Sold out for this hour (the drain saw 0/N): a later probe must not clear it.
        // The :00 rollover in tick() resets the flag.
        if (this.avail[t.id] === false && this.reason[t.id] === 'soldout') continue;
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
      this._persist();
    } finally {
      this._probing = false;
    }
  }

  async probeOne(t) {
    const script = this.ctx.resolveScript ? this.ctx.resolveScript('tg_task_probe.py')
      : path.join(this.ctx.ROOT_DIR, 'tg_task_probe.py');
    const args = ['--bot', t.bot, '--task', t.task];   // runPythonJson puts the script path first itself
    try {
      const res = await this.ctx.runPythonJson(this.ctx.PYTHON_BIN, this.ctx.ROOT_DIR, script, args, 45000);
      return res || null;
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e).slice(0, 80) };
    }
  }

  async startTarget(t) {
    // API-mode switch from the Taskly Cookie page (saved server-side so auto-start honours it).
    const st = (this.ctx.readSettings && this.ctx.readSettings()) || {};
    const cfg = {
      ig_api: st.cookie_ig_api === true,
      ig_api_mock: st.cookie_ig_api === true,   // this task only ever submits a MOCK 2FA key
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

  // Graceful by default: data/stop_tg.flag makes the worker stop starting new cycles while in-flight ones
  // finish ("Graceful stop requested — allowing in-flight tasks to finish..."); the worker then exits by
  // itself. Only if it is still alive after graceMs is the whole process tree killed (worker + Chromium +
  // Playwright driver — killing just the worker leaves the driver writing to a dead pipe: EPIPE spam).
  stopCurrentEngine(graceMs = STOP_GRACE_MS) {
    if (this._stopPromise) return this._stopPromise;
    const slot = this._slot();
    if (!slot || !slot.proc) return Promise.resolve();
    const proc = slot.proc;
    proc.__preemptKilled = true;
    try {
      const fs = require('fs');
      fs.mkdirSync(path.join(this.ctx.ROOT_DIR, 'data'), { recursive: true });
      fs.writeFileSync(path.join(this.ctx.ROOT_DIR, 'data', 'stop_tg.flag'), '1', 'utf8');
    } catch (e) {}
    const killTree = (sig) => {
      try {
        if (process.platform === 'win32') {
          if (this.ctx.killProcessGroup) this.ctx.killProcessGroup(proc);
          else proc.kill();
        } else {
          try { process.kill(-proc.pid, sig); } catch (e) { proc.kill(sig); }
        }
      } catch (e) {}
    };
    this._stopPromise = new Promise(resolve => {
      let done = false;
      let graceTimer = null, forceTimer = null;
      const finish = () => {
        if (done) return;
        done = true;
        clearTimeout(graceTimer); clearTimeout(forceTimer);
        slot.proc = null; slot.config = null;
        this._stopPromise = null;
        resolve();
      };
      proc.once('close', finish);
      proc.once('exit', finish);
      graceTimer = setTimeout(() => {
        this._log('⚠️ Engine still running after the graceful-stop window — force-stopping it.');
        killTree('SIGTERM');
        forceTimer = setTimeout(() => { killTree('SIGKILL'); finish(); }, 8000);
      }, Math.max(0, graceMs));
    });
    return this._stopPromise;
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
        // A running drain holds every TG profile, so the probe reports busy and
        // never sees the stock state. Trust the drain's own verdict: every creator
        // reports the task unavailable (sold out, hidden or unoffered) → this target
        // is done for the hour. The worker repeats that line each retry, so this is
        // applied once per hour (avail stays false until the :00 reset).
        const miss = String(data).match(/Task unavailable on ALL[^\n]*\(reason=(soldout|hidden|unoffered)\)/i)
          // NOT the per-creator "[task_unavailable:x]" tag: one creator missing the task (menu glitch,
          // orphan task, session reset) must not stop the drain while the others still see it. The
          // worker prints "Task unavailable on ALL n creator(s)" once every creator agrees.
          || (/available this hour: 0\//i.test(String(data)) ? ['', 'soldout'] : null);
        if (this.current && miss && this.avail[this.current] !== false) {
          const why = miss[1].toLowerCase();
          this.avail[this.current] = false;
          this.reason[this.current] = why;
          this._log(`🚫 ${this.current} unavailable for every creator (${why}) — stopping it for this hour.`);
          this._persist();
        }
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
    // Keep the process handle: the stop route clears it once the worker is really dead. Dropping it here
    // let Auto-Mine start a second engine seconds later while the stopped one was still finishing in-flight
    // tasks (two workers on the same Telegram sessions: "wrong session ID", "database is locked").
    const slot = this._slot();
    if (slot) { slot.config = null; }
    this.current = null;
    if (this.enabled) this.state = 'monitoring';
  }
}

module.exports = new CookieOrchestrator();
