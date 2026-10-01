/**
 * PayGo Auto-Mining & Preemption Orchestrator
 *
 * Monitors PayGoBot hourly stock refills via fast MTProto probing without holding
 * TG profiles. When stock refills, it saves the currently running bot's state,
 * stops it gracefully, starts PayGo IG Pool Drain, and automatically restores the
 * previous bot once PayGo hits its hourly limit.
 */
const path = require('path');
const fs = require('fs');

class PayGoOrchestrator {
  constructor() {
    this.ctx = null;
    this.enabled = false;
    this.state = 'idle'; // 'idle' | 'monitoring' | 'paygo_running' | 'restoring'
    this.lastProbe = null;
    this.nextProbeTime = 0;
    this.savedJob = null;
    this.isPayGoActive = false;
    this.activePayGoProc = null;
    this._lastPreemptedHour = null;
    this.timer = null;
    this._probing = false;
    this._paygoStartSubmissions = 0;
    this._restoreTimer = null;
  }

  init(ctx) {
    this.ctx = ctx;
    const settings = ctx.readSettings ? ctx.readSettings() : {};
    this.enabled = !!settings.auto_paygo_refill;
    this.concurrency = parseInt(settings.auto_paygo_concurrency || 6, 10);
    if (this.enabled) {
      this.state = 'monitoring';
      this.nextProbeTime = Date.now() + 3000; // fast initial probe
    }

    if (this.timer) clearInterval(this.timer);
    this.timer = setInterval(() => this.tick(), 5000); // 5s tick for responsive auto-drain
    this.setupAccountWatcher();
    console.log(`[PayGo-Auto] Orchestrator initialized (enabled=${this.enabled}, concurrency=${this.concurrency})`);
  }

  setupAccountWatcher() {
    try {
      if (!this.ctx || !this.ctx.ROOT_DIR) return;
      const accFile = path.join(this.ctx.ROOT_DIR, 'data', 'accounts.json');
      if (fs.existsSync(accFile)) {
        fs.watchFile(accFile, { interval: 2000 }, (curr, prev) => {
          if (curr.mtimeMs !== prev.mtimeMs) {
            this.onAccountCreated();
          }
        });
      }
    } catch (e) {}
  }

  async onAccountCreated(evt) {
    if (!this.enabled || this.isPayGoActive) return;

    // Check if PayGo is currently known to be in limit / sold out this hour
    const now = new Date();
    const hourKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}-${now.getHours()}`;
    if (this._lastPreemptedHour === hourKey && this.lastProbe && this.lastProbe.stock === 0) {
      // Sold out this hour: keep the new account safe in pool for the next hour rollover
      return;
    }

    const availPool = this.getAvailableIgAccountsCount();
    if (availPool <= 0) return;

    // If we have verified that PayGo stock is available:
    if (this.lastProbe && this.lastProbe.available && (this.lastProbe.stock === null || this.lastProbe.stock > 0)) {
      console.log(`[PayGo-Auto] ⚡ New account created (${availPool} ready in pool)! Draining to PayGoBot...`);
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({
          type: 'log',
          pipeline: 'telegram',
          engine: 'tg',
          message: `⚡ [Auto-PayGo] Fresh account created (${availPool} ready in pool). Draining to PayGoBot...`,
        });
      }
      await this.preemptAndStartPayGo();
      return;
    }

    // If stock status is unknown or hasn't been probed yet, probe now to check if tasks are available
    if (!this._probing) {
      this._probing = true;
      try {
        await this.runProbe(false);
      } catch (e) {}
      finally {
        this._probing = false;
        this.broadcastStatus();
      }
    }
  }

  getPayGoSubmissions() {
    try {
      if (!this.ctx || !this.ctx.ROOT_DIR) return 0;
      const p = path.join(this.ctx.ROOT_DIR, 'data', 'tg_stats.json');
      if (fs.existsSync(p)) {
        const d = JSON.parse(fs.readFileSync(p, 'utf-8'));
        return parseInt(d.paygo || 0, 10);
      }
    } catch (e) {}
    return 0;
  }

  getAvailableIgAccountsCount() {
    try {
      if (this.ctx && this.ctx.getAccounts) {
        const allAccs = this.ctx.getAccounts() || [];
        return allAccs.filter(a =>
          (a.platform === 'Meta+Instagram' || a.cookies) &&
          (a.status === 'Created' || !a.status) &&
          a.cookies && a.cookies.length > 20
        ).length;
      }
    } catch (e) {}
    return 0;
  }

  getStatus() {
    let waitSec = 0;
    if (this.lastProbe && this.lastProbe.wait_seconds != null) {
      const elapsed = Math.floor((Date.now() - (this.lastProbe.checked_at ? this.lastProbe.checked_at * 1000 : Date.now())) / 1000);
      waitSec = Math.max(0, this.lastProbe.wait_seconds - elapsed);
    } else {
      const now = new Date();
      const nextHour = new Date(now);
      nextHour.setHours(now.getHours() + 1, 0, 0, 0);
      waitSec = Math.max(0, Math.floor((nextHour.getTime() - now.getTime()) / 1000));
    }

    return {
      enabled: this.enabled,
      state: this.state,
      concurrency: this.concurrency,
      stock: this.lastProbe ? this.lastProbe.stock : null,
      max_stock: 5700,
      available: this.lastProbe ? !!this.lastProbe.available : false,
      wait_seconds: waitSec,
      next_probe_in: Math.max(0, Math.floor((this.nextProbeTime - Date.now()) / 1000)),
      previous_bot: this.savedJob ? this.savedJob.tg_bot : null,
      is_paygo_active: this.isPayGoActive,
      ig_pool_available: this.getAvailableIgAccountsCount(),
    };
  }

  toggle(enabled, concurrency) {
    this.enabled = !!enabled;
    if (concurrency != null && !isNaN(concurrency)) {
      this.concurrency = Math.max(1, Math.min(10, parseInt(concurrency, 10)));
    }
    if (this.ctx && this.ctx.writeSettings) {
      this.ctx.writeSettings({
        auto_paygo_refill: this.enabled,
        auto_paygo_concurrency: this.concurrency,
      });
    }
    if (this.enabled) {
      this.state = this.isPayGoActive ? 'paygo_running' : 'monitoring';
      this.nextProbeTime = Date.now() + 1000;
    } else {
      this.state = 'idle';
      this.savedJob = null;
    }
    this.broadcastStatus();
    return this.getStatus();
  }

  broadcastStatus() {
    if (!this.ctx || !this.ctx.broadcastEvent) return;
    this.ctx.broadcastEvent({
      type: 'paygo_auto_status',
      pipeline: 'telegram',
      engine: 'tg',
      status: this.getStatus(),
    });
  }

  notifyUserStopped() {
    console.log('[PayGo-Auto] User requested manual stop. Halting active PayGo tasks and canceling restores.');
    if (this._restoreTimer) {
      clearTimeout(this._restoreTimer);
      this._restoreTimer = null;
    }
    this.isPayGoActive = false;
    this.activePayGoProc = null;
    this.savedJob = null;
    this.state = this.enabled ? 'monitoring' : 'idle';
    this.broadcastStatus();
  }

  notifyLoopStopped(deadProc) {
    if (!this.isPayGoActive) return;
    if (deadProc && deadProc.__preemptKilled) {
      console.log('[PayGo-Auto] Ignoring process exit from preempted bot.');
      return;
    }
    if (deadProc && this.activePayGoProc && deadProc !== this.activePayGoProc) {
      console.log('[PayGo-Auto] Ignoring process exit from non-PayGo process.');
      return;
    }
    this.isPayGoActive = false;
    this.activePayGoProc = null;

    const endSubmissions = this.getPayGoSubmissions();
    const tasksSubmitted = Math.max(0, endSubmissions - (this._paygoStartSubmissions || 0));
    const now = new Date();
    const min = now.getMinutes();
    const inGraceWindow = (min >= 0 && min < 5);
    const hourKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}-${now.getHours()}`;

    console.log(`[PayGo-Auto] PayGo stopped. Tasks submitted: ${tasksSubmitted}. inGraceWindow=${inGraceWindow} (min=${min})`);

    // DELAYED REFILL HANDLING:
    // If PayGo exited with 0 tasks submitted during the first 5 minutes (:00-:05),
    // the bot's refill cron hasn't landed yet! Do NOT sleep 59 minutes and miss it!
    if (tasksSubmitted === 0 && inGraceWindow) {
      console.log('[PayGo-Auto] PayGo stock was 0 at :00 (refill delayed). Grace window active (:00-:05) — rapid probing every 15s.');
      this._lastPreemptedHour = null; // Do NOT lock this hour!
      this.state = 'monitoring';
      this.nextProbeTime = Date.now() + 15000;
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({
          type: 'log',
          pipeline: 'telegram',
          engine: 'tg',
          message: `⏳ [Auto-PayGo] PayGo stock was 0/5700 at :00 (bot refill delayed). Grace window active (:00-:05) — probing every 15s until stock arrives...`,
        });
      }
      this.broadcastStatus();
      return;
    }

    // Either tasks were drained (> 0), OR grace window has expired (min >= 5).
    this._lastPreemptedHour = hourKey;
    this.state = 'restoring';

    const hasJobToRestore = !!(this.savedJob && this.savedJob.tg_bot && this.savedJob.tg_bot !== 'paygo');

    if (hasJobToRestore && this.enabled) {
      const jobToRestore = this.savedJob;
      this.savedJob = null;

      console.log(`[PayGo-Auto] PayGo cycle completed (${tasksSubmitted} tasks submitted). Restoring previous bot: ${jobToRestore.tg_bot}`);
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({
          type: 'log',
          pipeline: 'telegram',
          engine: 'tg',
          message: `⚡ [Auto-PayGo] PayGo finished (${tasksSubmitted} tasks submitted). Restoring previous bot: ${jobToRestore.tg_bot}...`,
        });
      }

      if (this._restoreTimer) clearTimeout(this._restoreTimer);
      this._restoreTimer = setTimeout(() => {
        this._restoreTimer = null;
        if (jobToRestore && this.enabled && !this.isPayGoActive) {
          console.log(`[PayGo-Auto] Restoring previous bot: ${jobToRestore.tg_bot} (${jobToRestore.tg_task})`);
          this.startEngine(jobToRestore);
        }
        this.state = this.enabled ? 'monitoring' : 'idle';
        const waitSec = this.calculateSecondsToNextHour();
        this.nextProbeTime = Date.now() + Math.max(30000, (waitSec - 25) * 1000);
        this.broadcastStatus();
      }, 3000);
    } else {
      this.savedJob = null;
      if (this._restoreTimer) {
        clearTimeout(this._restoreTimer);
        this._restoreTimer = null;
      }
      console.log(`[PayGo-Auto] PayGo cycle completed (${tasksSubmitted} tasks submitted). No previous bot to restore.`);
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({
          type: 'log',
          pipeline: 'telegram',
          engine: 'tg',
          message: `⚡ [Auto-PayGo] PayGo finished (${tasksSubmitted} tasks submitted). Engine is idle.`,
        });
      }
      this.state = this.enabled ? 'monitoring' : 'idle';
      const waitSec = this.calculateSecondsToNextHour();
      this.nextProbeTime = Date.now() + Math.max(30000, (waitSec - 25) * 1000);
      this.broadcastStatus();
    }
  }

  calculateSecondsToNextHour() {
    const now = new Date();
    const nextHour = new Date(now);
    nextHour.setHours(now.getHours() + 1, 0, 0, 0);
    return Math.max(5, Math.floor((nextHour.getTime() - now.getTime()) / 1000));
  }

  async tick() {
    if (!this.enabled || this._probing || this.isPayGoActive) return;

    const now = new Date();
    const min = now.getMinutes();
    const sec = now.getSeconds();
    const waitSec = this.calculateSecondsToNextHour();
    const slot = this.ctx.slot('tg');
    const isBotRunning = !!(slot && slot.proc);
    const hourKey = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}-${now.getHours()}`;
    const inGraceWindow = (min >= 0 && min < 5);

    // If grace window expired (min >= 5) and we were holding savedJob waiting for a delayed refill:
    if (!inGraceWindow && this.savedJob && !isBotRunning) {
      if (this.savedJob.tg_bot && this.savedJob.tg_bot !== 'paygo') {
        console.log(`[PayGo-Auto] Grace window expired (:05) with no stock refill. Restoring previous bot: ${this.savedJob.tg_bot}`);
        const jobToRestore = this.savedJob;
        this.savedJob = null;
        this._lastPreemptedHour = hourKey;
        if (this.ctx.broadcastEvent) {
          this.ctx.broadcastEvent({
            type: 'log',
            pipeline: 'telegram',
            engine: 'tg',
            message: `⚡ [Auto-PayGo] Refill grace window expired (:05) with no stock. Restoring previous bot (${jobToRestore.tg_bot}) until next hour...`,
          });
        }
        this.startEngine(jobToRestore);
        this.nextProbeTime = Date.now() + Math.max(30000, (waitSec - 25) * 1000);
        this.broadcastStatus();
        return;
      } else {
        this.savedJob = null;
      }
    }

    // CONTINUOUS POOL DRAIN: Listen to creator and drain whenever PayGo tasks are available
    const isPayGoStockActive = this.lastProbe && this.lastProbe.available && (this.lastProbe.stock === null || this.lastProbe.stock > 0);
    const poolCount = this.getAvailableIgAccountsCount();
    if (isPayGoStockActive && poolCount > 0 && !this.isPayGoActive) {
      console.log(`[PayGo-Auto] ⚡ PayGo stock is active (${this.lastProbe.stock != null ? this.lastProbe.stock : 'available'}) & ${poolCount} account(s) ready in pool. Starting drain...`);
      await this.preemptAndStartPayGo();
      this.broadcastStatus();
      return;
    }

    // 1. Mandatory top-of-hour preemption:
    // Window: 25 seconds before :00 (waitSec <= 25) OR within the first 60 seconds of the hour (:00)
    const isTopOfHour = (waitSec <= 25) || (min === 0 && sec <= 60);
    if (isTopOfHour && this._lastPreemptedHour !== hourKey) {
      this._lastPreemptedHour = hourKey;
      console.log(`[PayGo-Auto] Hourly refill window reached (:00)! ${isBotRunning ? 'Preempting active bot' : 'Starting'} for PayGo...`);
      await this.preemptAndStartPayGo();
      this.broadcastStatus();
      return;
    }

    // 2. Rapid polling during grace window (:00-:05) if stock wasn't drained yet:
    // Catches delayed refills at 1:01, 1:02, 1:03, 1:04 AM without waiting for the next hour!
    if (inGraceWindow && this._lastPreemptedHour !== hourKey) {
      if (Date.now() < this.nextProbeTime) {
        this.broadcastStatus();
        return;
      }
      this._probing = true;
      try {
        await this.runProbe(true /* inGrace */);
      } catch (e) {
        this.nextProbeTime = Date.now() + 15000;
      } finally {
        this._probing = false;
        this.broadcastStatus();
      }
      return;
    }

    // 3. Opportunistic in-between checking (outside grace window):
    // If another bot is running, check if at least one TG account is currently idle/free.
    const hasIdleAccount = this.ctx.readTgPool
      ? this.ctx.readTgPool().some(a => a.enabled !== false && a.logged_in === true && a.status === 'idle')
      : false;

    if (isBotRunning && !hasIdleAccount) {
      // All TG accounts are currently busy in other bot cycles.
      // Zero-contention: do not block active workers, continue clock countdown to :00.
      this.broadcastStatus();
      return;
    }

    // When an account is free (or no bot is running): probe stock if cooldown passed
    if (Date.now() < this.nextProbeTime) {
      this.broadcastStatus();
      return;
    }

    this._probing = true;
    try {
      await this.runProbe(false);
    } catch (e) {
      this.nextProbeTime = Date.now() + 45000;
    } finally {
      this._probing = false;
      this.broadcastStatus();
    }
  }

  async runProbe(inGrace = false) {
    const script = this.ctx.resolveScript ? this.ctx.resolveScript('tg_paygo_probe.py') : path.join(this.ctx.ROOT_DIR, 'tg_paygo_probe.py');
    const args = inGrace ? ['--timeout', '3.0'] : [];
    const res = await this.ctx.runPythonJson(this.ctx.PYTHON_BIN, this.ctx.ROOT_DIR, script, args, 30000);

    if (!res || !res.ok) {
      this.nextProbeTime = Date.now() + (inGrace ? 15000 : 30000);
      return;
    }

    this.lastProbe = res;
    console.log(`[PayGo-Auto] Probe: available=${res.available}, stock=${res.stock}, wait_sec=${res.wait_seconds}`);

    if (res.available) {
      // Stock available! Preempt and start PayGo!
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({
          type: 'log',
          pipeline: 'telegram',
          engine: 'tg',
          message: `🎉 [Auto-PayGo] PayGo stock refilled (${res.stock != null ? res.stock : 'available'}/5700)! Launching PayGo pool drain...`,
        });
      }
      await this.preemptAndStartPayGo();
    } else {
      // Calculate next check
      const now = new Date();
      const min = now.getMinutes();
      if (min >= 0 && min < 5) {
        // In the first 5 minutes of the hour, probe rapidly every 15s to catch delayed refills (e.g. 1:02 AM)
        this.nextProbeTime = Date.now() + 15000;
      } else {
        const wait = res.wait_seconds || 60;
        if (wait <= 40) {
          // Less than 40s to refill: check frequently (every 10s)
          this.nextProbeTime = Date.now() + 10000;
        } else {
          // Probe ~25s before stated refill or next hour
          this.nextProbeTime = Date.now() + Math.max(15000, (wait - 25) * 1000);
        }
      }
    }
  }

  async preemptAndStartPayGo() {
    if (this._restoreTimer) {
      clearTimeout(this._restoreTimer);
      this._restoreTimer = null;
    }

    const availPool = this.getAvailableIgAccountsCount();
    if (availPool <= 0) {
      console.log('[PayGo-Auto] PayGo refill detected, but 0 IG Creator accounts in pool to drain.');
      if (this.ctx && this.ctx.broadcastEvent) {
        this.ctx.broadcastEvent({
          type: 'log',
          pipeline: 'telegram',
          engine: 'tg',
          message: '⚠️ [Auto-PayGo] PayGo stock is available, but IG Creator pool has 0 accounts. Leaving active bot running (run Meta Creator to populate pool).',
        });
      }
      return false;
    }

    this._paygoStartSubmissions = this.getPayGoSubmissions();
    const slot = this.ctx.slot('tg');
    const runningProc = slot ? slot.proc : null;
    const runningConfig = slot ? slot.config : null;

    // CRITICAL: Always reset savedJob. Only store a previous job if
    // a DIFFERENT bot (e.g. taskly, fastpay) was genuinely running.
    this.savedJob = null;

    if (runningProc && runningConfig) {
      // If already running PayGo with IG pool, don't preempt itself
      if (runningConfig.tg_bot === 'paygo' && runningConfig.use_ig_pool) {
        this.isPayGoActive = true;
        this.state = 'paygo_running';
        return;
      }

      // Only save if it was genuinely a DIFFERENT bot (e.g. Taskly or FastPay).
      // Never save PayGo to restore itself!
      if (runningConfig.tg_bot && runningConfig.tg_bot !== 'paygo') {
        this.savedJob = Object.assign({}, runningConfig);
        console.log(`[PayGo-Auto] Preempting ${runningConfig.tg_bot} (${runningConfig.tg_task}) for PayGo refill.`);
        if (this.ctx.broadcastEvent) {
          this.ctx.broadcastEvent({
            type: 'log',
            pipeline: 'telegram',
            engine: 'tg',
            message: `⚡ [Auto-PayGo] PayGo stock refilled! Pausing ${runningConfig.tg_bot} to drain PayGo pool...`,
          });
        }
      }

      // Stop current running bot and properly AWAIT its exit
      await this.stopCurrentEngine();
      await new Promise(r => setTimeout(r, 1000));
    }

    // Launch PayGo
    this.isPayGoActive = true;
    this.state = 'paygo_running';
    const conc = this.concurrency || (this.savedJob ? (this.savedJob.concurrency || 6) : 6);
    const headless = this.savedJob ? (this.savedJob.headless !== false) : true;

    this.startEngine({
      tg_bot: 'paygo',
      tg_task: '📱 Create Inst (Cookies)',
      use_ig_pool: true,
      concurrency: conc,
      headless: headless,
      target: 0,
      delay: 8,
      captcha: 'extension',
    }, true /* isPayGo */);
  }

  async stopCurrentEngine() {
    const slot = this.ctx.slot('tg');
    if (!slot || !slot.proc) return;
    const proc = slot.proc;
    proc.__preemptKilled = true;

    return new Promise(resolve => {
      let done = false;
      const finish = () => {
        if (!done) {
          done = true;
          slot.proc = null;
          slot.config = null;
          resolve();
        }
      };

      proc.once('close', finish);
      proc.once('exit', finish);

      // Force kill safety timer after 6 seconds
      const forceTimer = setTimeout(() => {
        try {
          if (process.platform !== 'win32') {
            try { process.kill(-proc.pid, 'SIGKILL'); } catch (e) {}
          } else {
            try { proc.kill('SIGKILL'); } catch (e) {}
          }
        } catch (e) {}
        finish();
      }, 6000);

      try {
        if (process.platform !== 'win32') {
          try { process.kill(-proc.pid, 'SIGTERM'); } catch (e) { proc.kill('SIGTERM'); }
        } else {
          proc.kill();
        }
      } catch (e) {
        clearTimeout(forceTimer);
        finish();
      }
    });
  }

  startEngine(cfg, isPayGo = false) {
    if (!this.ctx) return;
    const slot = this.ctx.slot('tg');
    if (slot.proc) {
      console.log('[PayGo-Auto] Cannot start engine: slot already has a running process');
      return;
    }

    const args = [
      this.ctx.resolveScript('worker.py'),
      '--concurrency', String(cfg.concurrency || 6),
      '--target', String(cfg.target || 0),
      '--delay', String(cfg.delay || 8),
      '--mail', 'mailtd',
      '--captcha', cfg.captcha || 'extension',
      '--mode', 'meta',
      '--coupled',
      '--tg-task', cfg.tg_task || '📱 Create Inst (Cookies)',
      '--tg-bot', cfg.tg_bot || 'paygo',
    ];
    if (cfg.twofa !== false) args.push('--twofa');

    let addEmail = (cfg.add_email === true || cfg.add_email === 'true');
    if (cfg.tg_bot === 'taskly' && /2fa/i.test(cfg.tg_task) && !/no.mail/i.test(cfg.tg_task) && !/cookie/i.test(cfg.tg_task)) {
      addEmail = false;
    }
    if (addEmail) args.push('--add-email');

    if (/cookie/i.test(cfg.tg_task)) args.push('--cookie');
    if (cfg.use_ig_pool) args.push('--use-ig-pool');
    if (cfg.headless) args.push('--headless');

    slot.config = cfg;
    try {
      const isWin = process.platform === 'win32';
      const fs = require('fs');
      const browsersDir = fs.existsSync(path.join(this.ctx.ROOT_DIR, '_internal', 'ms-playwright'))
        ? path.join(this.ctx.ROOT_DIR, '_internal', 'ms-playwright')
        : path.join(this.ctx.ROOT_DIR, 'engine', 'ms-playwright');

      const env = Object.assign({}, process.env, {
        PYTHONUNBUFFERED: '1',
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
        PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH || browsersDir,
      });

      if (this.ctx.resetWorkerBuffer) {
        this.ctx.resetWorkerBuffer('tg');
      }

      slot.proc = require('child_process').spawn(this.ctx.PYTHON_BIN, args, {
        cwd: this.ctx.ROOT_DIR,
        windowsHide: true,
        detached: !isWin,
        env,
      });

      if (isPayGo) {
        this.activePayGoProc = slot.proc;
      }

      const currentSpawned = slot.proc;

      slot.proc.stdout.on('data', data => {
        for (const line of this.ctx.feedWorkerStdout(data)) {
          this.ctx.consumeWorkerLine(line, 'tg');
        }
      });
      slot.proc.stderr.on('data', data => {
        const text = data.toString('utf-8').trim();
        if (text && !/socket\.send\(\)/i.test(text)) {
          this.ctx.broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg', message: `[STDERR] ${text}` });
        }
      });
      slot.proc.on('close', code => {
        this.ctx.flushWorkerBuffer();
        this.ctx.broadcastEvent({ type: 'log', pipeline: 'telegram', engine: 'tg', message: `[engine] TG worker exited (code ${code})` });
        this.ctx.broadcastEvent({ type: 'loop_stopped', pipeline: 'telegram', engine: 'tg', exit_code: code });
        if (slot.proc === currentSpawned) slot.proc = null;
        if (isPayGo) {
          this.notifyLoopStopped(currentSpawned);
        }
      });

      console.log(`[PayGo-Auto] Engine spawned: ${this.ctx.PYTHON_BIN} ${args.join(' ')}`);
      this.ctx.broadcastEvent({
        type: 'log',
        pipeline: 'telegram',
        engine: 'tg',
        message: `⚡ [Auto-PayGo] Started ${cfg.tg_bot} (${cfg.tg_task}) with parallel=${cfg.concurrency}`,
      });
    } catch (e) {
      console.error('[PayGo-Auto] Engine spawn failed:', e);
      slot.proc = null;
      slot.config = null;
    }
  }
}

module.exports = new PayGoOrchestrator();
