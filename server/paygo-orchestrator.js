/**
 * PayGo Auto-Mining & Preemption Orchestrator
 *
 * Monitors PayGoBot hourly stock refills via fast MTProto probing without holding
 * TG profiles. When stock refills, it saves the currently running bot's state,
 * stops it gracefully, starts PayGo IG Pool Drain, and automatically restores the
 * previous bot once PayGo hits its hourly limit.
 */
const path = require('path');

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
    this.timer = setInterval(() => this.tick(), 10000);
    console.log(`[PayGo-Auto] Orchestrator initialized (enabled=${this.enabled}, concurrency=${this.concurrency})`);
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
    this.state = 'restoring';

    console.log('[PayGo-Auto] PayGo cycle completed or hourly limit reached.');
    if (this.ctx && this.ctx.broadcastEvent) {
      this.ctx.broadcastEvent({
        type: 'log',
        pipeline: 'telegram',
        engine: 'tg',
        message: '⚡ [Auto-PayGo] PayGo finished/limited. Restoring previous bot...',
      });
    }

    // Schedule restore of previous bot after 3 seconds
    const jobToRestore = this.savedJob;
    this.savedJob = null;

    setTimeout(() => {
      if (jobToRestore && this.enabled) {
        console.log(`[PayGo-Auto] Restoring previous bot: ${jobToRestore.tg_bot} (${jobToRestore.tg_task})`);
        this.startEngine(jobToRestore);
      }
      this.state = this.enabled ? 'monitoring' : 'idle';
      const waitSec = this.calculateSecondsToNextHour();
      this.nextProbeTime = Date.now() + Math.max(30000, (waitSec - 25) * 1000);
      this.broadcastStatus();
    }, 3000);
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

    // 2. Opportunistic in-between checking:
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
      await this.runProbe();
    } catch (e) {
      this.nextProbeTime = Date.now() + 45000;
    } finally {
      this._probing = false;
      this.broadcastStatus();
    }
  }

  async runProbe() {
    const script = this.ctx.resolveScript ? this.ctx.resolveScript('tg_paygo_probe.py') : path.join(this.ctx.ROOT_DIR, 'tg_paygo_probe.py');
    const res = await this.ctx.runPythonJson(this.ctx.PYTHON_BIN, this.ctx.ROOT_DIR, script, [], 30000);

    if (!res || !res.ok) {
      this.nextProbeTime = Date.now() + 30000;
      return;
    }

    this.lastProbe = res;
    console.log(`[PayGo-Auto] Probe: available=${res.available}, stock=${res.stock}, wait_sec=${res.wait_seconds}`);

    if (res.available) {
      // Stock available! Preempt and start PayGo!
      await this.preemptAndStartPayGo();
    } else {
      // Calculate next check
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

  async preemptAndStartPayGo() {
    const slot = this.ctx.slot('tg');
    const runningProc = slot ? slot.proc : null;
    const runningConfig = slot ? slot.config : null;

    if (runningProc && runningConfig) {
      // If already running PayGo with IG pool, don't preempt itself
      if (runningConfig.tg_bot === 'paygo' && runningConfig.use_ig_pool) {
        this.isPayGoActive = true;
        this.state = 'paygo_running';
        return;
      }

      // Snapshot running configuration
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
