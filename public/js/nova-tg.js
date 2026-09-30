/* nova-tg.js — TG Classic panel (Meta -> Instagram -> Taskly/PayGo submit).
 *
 * Rewritten clean: the earlier version was patched by successive regex edits
 * and its shell HTML ended up malformed (a stray </div> from removing the old
 * inline add-form). Uses meta_creator's own class vocabulary (card-panel,
 * btn/btn-sm/btn-primary/btn-secondary, creator-field, insta-stat-*, form-control,
 * badge-pill/active/inactive) — all verified present in styles.css.
 *
 * Mirrors meta_auto_ai's TG tab: 4 KPI cards, Creator Settings, mail/captcha/
 * task/bot, a Telegram Profiles list, and a Balances TABLE
 * (Account | Taskly | PayGo | Total + TOTAL row).
 */
(function () {
  'use strict';

  var root = null, timer = null;
  var state = { running: false, igMode: null, bot: 'taskly', pool: [], log: [], cfg: { headless: true } };
  var botLogs = { taskly: [], paygo: [], fastpay: [] };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function $(id) { return document.getElementById(id); }

  // Cookie tasks (PayGo "Create Inst (Cookies)") verify via the exported IG
  // cookie and have NO 2FA/password/email step (see tg_flows.py). The
  // "Extra email" toggle therefore does not apply to them.
  function isCookieTask(task) { return /cookie/i.test(String(task || '')); }
  // Native Taskly-2FA (📱 Create Inst (2FA)) has NO mailbox step at all —
  // bot email + bot code — so extra-email is meaningless for it too.
  function isNativeTask(task) {
    var t = String(task || '');
    return /2fa/i.test(t) && !/no.mail/i.test(t) && !/cookie/i.test(t);
  }

  // The page IS the bot (set by the TG submenu) — there is no "Mining bot"
  // picker on a page that is already scoped to a bot.
  var BOT_META = {
    // Taskly migrated to @Taskl1_bot (display "Taksly Bot") on 2026-09-30 — the
    // old @tasklyBux_bot is ToS-banned/dead.
    taskly: { name: 'Taksly Bot', logo: 'taskly',
      tasks: [['📱 Create Inst (2FA)', '📱 Create Inst (2FA) — 2FA flow'],
              ['🍪 Create Inst (No mail)', '🍪 Create Inst (No mail) — 2FA + cookie flow'],
              ['🔥 Create Inst (No mail)', '🔥 Create Inst (No mail) — 2FA flow']] },
    paygo: { name: 'PayGo Bot', logo: 'paygo',
      tasks: [['📱 Create Inst (Cookies)', '📱 Create Inst (Cookies) — cookie flow']] },
    fastpay: { name: 'FastPay Bot', logo: 'fastpay',
      tasks: [['Instagram 2FA', 'Instagram 2FA — create + payout']] },
  };

  var TASK_NOTES = {
    '📱 Create Inst (2FA)': 'Native Taskly 2FA task — email and code come directly from the bot; no extra mailbox required.',
    '🍪 Create Inst (No mail)': 'Taskly Cookie + 2FA task — creates account, sets 2FA, and exports session cookie for verification.',
    '🔥 Create Inst (No mail)': 'Taskly No-mail task — 2FA flow with direct password setting.',
    '📱 Create Inst (Cookies)': 'PayGo cookie task — registers via Meta, joins Instagram, and submits exported session cookie.',
    'Instagram 2FA': 'FastPay task — creates account with bot-issued credentials and submits 2FA key for payout.'
  };

  function updateTaskNote(taskVal, rawLabel) {
    var noteEl = $('tg-task-note');
    if (!noteEl) return;
    if (TASK_NOTES[taskVal]) {
      noteEl.textContent = TASK_NOTES[taskVal];
    } else if (rawLabel && rawLabel.indexOf(' — ') !== -1) {
      noteEl.textContent = 'Selected task flow: ' + rawLabel.split(' — ')[1];
    } else {
      noteEl.textContent = 'Active task: ' + (taskVal || 'Default flow');
    }
  }

  function renderTaskOptions(bot) {
    var hidden = $('tg-task');
    var container = $('tg-task-options');
    var list = (BOT_META[bot] || BOT_META.taskly).tasks;
    if (!container) return;

    var keep = hidden ? hidden.value : '';
    var valid = false;
    for (var j = 0; j < list.length; j++) {
      if (list[j][0] === keep) valid = true;
    }
    var currentVal = valid ? keep : (list[0] ? list[0][0] : '');
    if (hidden) hidden.value = currentVal;

    var html = '';
    var selectedRawLabel = '';
    for (var i = 0; i < list.length; i++) {
      var val = list[i][0];
      var rawLabel = list[i][1] || val;
      var parts = rawLabel.split(' — ');
      var title = parts[0] || val;
      var hint = parts[1] ? ' (' + parts[1] + ')' : '';
      var isChecked = (val === currentVal) ? ' checked' : '';
      if (val === currentVal) selectedRawLabel = rawLabel;

      var iconHtml = '';
      if (val.indexOf('Instagram') === 0) {
        iconHtml = '<i class="fa-brands fa-instagram" style="color:var(--accent-purple);"></i> ';
      }

      html += '<label class="creator-option" title="' + esc(rawLabel) + '" style="cursor:pointer;">' +
        '<input type="radio" name="tg-task-radio" value="' + esc(val) + '"' + isChecked + '> ' +
        iconHtml + esc(title) +
        (hint ? ' <span class="creator-option-hint">' + esc(hint) + '</span>' : '') +
      '</label>';
    }
    container.innerHTML = html;
    updateTaskNote(currentVal, selectedRawLabel);

    var radios = container.querySelectorAll('input[name="tg-task-radio"]');
    for (var r = 0; r < radios.length; r++) {
      (function (radio) {
        radio.addEventListener('change', function () {
          if (this.checked) {
            if (hidden) {
              hidden.value = this.value;
              try { hidden.dispatchEvent(new Event('change')); } catch (e) { applyFlowGuards(); }
            }
            var matchingLabel = '';
            for (var k = 0; k < list.length; k++) {
              if (list[k][0] === this.value) { matchingLabel = list[k][1]; break; }
            }
            updateTaskNote(this.value, matchingLabel);
            applyFlowGuards();
          }
        });
      })(radios[r]);
    }
  }

  function updateBotBadge(bot) {
    var el = $('tg-bot-badge');
    if (!el) return;
    var m = BOT_META[bot] || BOT_META.taskly;
    el.innerHTML = '<img src="img/bot_logo/' + m.logo + '.png" width="20" height="20" ' +
      'style="border-radius:50%;object-fit:cover;" onerror="this.style.display=\'none\'" alt=""> ' +
      esc(m.name);
  }

  // Cookie tasks have no email step (tg_flows.py) — grey out + disable the
  // toggle so the operator is not misled; it is also ignored server-side.
  // Same for the native 2FA task (bot email+code, no mailbox at all).
  function applyFlowGuards() {
    var isPayGo = (state.bot === 'paygo');
    var igPoolField = $('tg-igpool-field');
    var igPoolSw = $('tg-igpool-sw');
    var autoSw = $('tg-paygo-auto-sw');
    var cardPool = $('tg-paygo-card-pool');
    var cardAuto = $('tg-paygo-card-automine');

    if (igPoolField) {
      igPoolField.style.display = isPayGo ? 'flex' : 'none';
      if (!isPayGo && igPoolSw) {
        igPoolSw.checked = false;
      }
    }

    if (cardPool && igPoolSw) {
      if (igPoolSw.checked) cardPool.classList.add('is-active');
      else cardPool.classList.remove('is-active');
    }
    if (cardAuto && autoSw) {
      if (autoSw.checked) cardAuto.classList.add('is-active');
      else cardAuto.classList.remove('is-active');
    }

    if (igPoolSw && !igPoolSw.dataset.cardWired) {
      igPoolSw.dataset.cardWired = '1';
      igPoolSw.addEventListener('change', function () {
        if (cardPool) {
          if (igPoolSw.checked) cardPool.classList.add('is-active');
          else cardPool.classList.remove('is-active');
        }
      });
    }

    var isIgPoolActive = isPayGo && !!(igPoolSw && igPoolSw.checked);

    var task = ($('tg-task') || {}).value || '';
    var cookie = isCookieTask(task);
    var native = isNativeTask(task);
    var offAdde = isIgPoolActive || cookie || native;

    var swAdde = $('tg-adde-sw');
    var fieldAdde = $('tg-adde-field') || (swAdde ? swAdde.closest('.creator-field') : null);
    if (swAdde) {
      swAdde.disabled = offAdde;
      swAdde.title = isIgPoolActive
        ? 'Disabled: Draining from IG Creator accounts pool'
        : (cookie
          ? 'Not used by the Cookie task — it verifies via the exported IG cookie.'
          : (native ? 'Not used by the native 2FA task — email + code come from the bot.' : 'Fresh mail.td email before the task registers.'));
    }
    if (fieldAdde) {
      fieldAdde.style.display = offAdde ? 'none' : 'flex';
      fieldAdde.style.opacity = offAdde ? '0.4' : '1';
    }

    // When IG Creator Accounts is chosen, disable the rest, leaving ONLY headless and ON/OFF:
    var concInput = $('tg-conc');
    var targetInput = $('tg-target');
    var concField = concInput ? concInput.closest('.creator-field') : null;
    var targetField = targetInput ? targetInput.closest('.creator-field') : null;
    var taskSection = document.querySelector('.creator-task-service');
    var servicesPanel = document.querySelector('.creator-services');

    // Parallel and Target stay enabled so users can drain pool in parallel with N slots
    if (concInput) concInput.disabled = false;
    if (concField) concField.style.opacity = '1';

    if (targetInput) targetInput.disabled = false;
    if (targetField) targetField.style.opacity = '1';

    if (taskSection) {
      taskSection.style.opacity = isIgPoolActive ? '0.4' : '1';
      taskSection.style.pointerEvents = isIgPoolActive ? 'none' : 'auto';
    }

    if (servicesPanel) {
      servicesPanel.style.opacity = isIgPoolActive ? '0.25' : '1';
      servicesPanel.style.pointerEvents = isIgPoolActive ? 'none' : 'auto';
      servicesPanel.style.filter = isIgPoolActive ? 'grayscale(0.85)' : 'none';
      var serviceInputs = servicesPanel.querySelectorAll('input');
      for (var s = 0; s < serviceInputs.length; s++) {
        serviceInputs[s].disabled = isIgPoolActive;
      }
    }

    // Only headless and ON/OFF remain enabled
    var headlessSw = $('tg-headless-sw');
    if (headlessSw) {
      headlessSw.disabled = false;
    }

    var autoSw = $('tg-paygo-auto-sw');
    var autoConc = $('tg-paygo-auto-conc');
    if (autoSw && !autoSw.dataset.wired) {
      autoSw.dataset.wired = '1';
      autoSw.addEventListener('change', function () {
        var conc = parseInt((autoConc && autoConc.value) || 6, 10);
        post('/api/tg/paygo-auto/toggle', { enabled: autoSw.checked, concurrency: conc })
          .then(function (j) { if (j && j.status) updatePayGoAutoUI(j.status); });
      });
    }
    if (autoConc && !autoConc.dataset.wired) {
      autoConc.dataset.wired = '1';
      autoConc.addEventListener('change', function () {
        var conc = Math.max(1, Math.min(10, parseInt(autoConc.value || 6, 10)));
        autoConc.value = conc;
        post('/api/tg/paygo-auto/toggle', { enabled: autoSw ? autoSw.checked : true, concurrency: conc })
          .then(function (j) { if (j && j.status) updatePayGoAutoUI(j.status); });
      });
    }

    if (isIgPoolActive) {
      var noteEl = $('tg-task-note');
      if (noteEl) {
        noteEl.textContent = '⚡ IG Creator Accounts Pool active: Fast copy-paste username change & cookie submission into PayGo. Zero browser creation.';
      }
    }
  }

  // Called by the sidebar submenu: switch this page to a bot.
  window.__setTgBot = function (bot) {
    bot = BOT_META[bot] ? bot : 'taskly';
    state.bot = bot;
    renderTaskOptions(bot);
    updateBotBadge(bot);
    applyFlowGuards();
    state.log = (botLogs[bot] || []).slice();
    paintLog();
    refresh();  // re-scope the per-bot KPIs immediately (don't wait 5s)
  };

  // Shared Add-MTProto modal (owned here) — the TG Manager opens it.
  window.openMtprotoModal = function () { mtReset(); mtOpen(); };

  // ---- IP-throttle banner ------------------------------------------------
  // The engine emits {"type":"throttle","scope":"ip","seconds":N,…} when
  // Meta/Instagram rate-limit the WHOLE IP (not one account). That is not
  // something the user can click away — show a big, unmissable banner with the
  // concrete remedy (switch to mobile data / wait / keep creators at 1).
  // ---- Throttle banner disabled (user requested no throttle banner or cooldown) ----
  function hideThrottleBanner() {
    var el = document.getElementById("tg-throttle-banner");
    if (el) el.remove();
  }
  function showThrottleBanner() { hideThrottleBanner(); }
  window.__tgShowThrottle = hideThrottleBanner;
  hideThrottleBanner();

  // Toasts — used for operator-actionable conditions (e.g. a pooled account
  // that never joined the selected bot, so its task can never be claimed).
  function toast(msg, kind, ms) {
    var host = $('tg-toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'tg-toast-host';
      host.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;' +
        'display:flex;flex-direction:column;gap:8px;max-width:380px;';
      document.body.appendChild(host);
    }
    var c = kind === 'error' ? 'var(--accent-red)'
          : kind === 'warn'  ? 'var(--accent-amber)'
          : 'var(--accent-green)';
    var el = document.createElement('div');
    el.style.cssText = 'background:var(--bg-card);border:1px solid var(--border-color);' +
      'border-left:3px solid ' + c + ';border-radius:var(--radius-sm);padding:10px 12px;' +
      'color:var(--text-main);font-size:12px;line-height:1.45;box-shadow:0 8px 24px rgba(0,0,0,.45);';
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(function () { try { host.removeChild(el); } catch (e) {} }, ms || 9000);
  }

  function statCard(label, id, sub, subId) {
    // TG accent = --accent-purple, the same one meta_auto_ai's TG tab uses.
    return '<div class="insta-stat-card" style="background:var(--bg-card);' +
             'border:1px solid var(--border-color);border-radius:var(--radius-md);' +
             'padding:14px 16px;position:relative;overflow:hidden;">' +
      '<div style="position:absolute;left:0;top:0;bottom:0;width:3px;' +
             'background:var(--accent-purple);opacity:.9;"></div>' +
      '<div class="insta-stat-label" style="color:var(--text-dim);">' + esc(label) + '</div>' +
      '<div class="insta-stat-value" id="' + id + '" style="color:var(--text-main);">0</div>' +
      '<div class="insta-stat-sub"' + (subId ? ' id="' + subId + '"' : '') +
             ' style="color:var(--text-muted);">' + esc(sub) + '</div></div>';
  }

  function shell() {
    root.innerHTML =
      /* ---- KPIs ---- */
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">' +
        statCard('TG - TOTAL ACCOUNTS', 'tg-kpi-total', 'created for Telegram') +
        statCard('TG - PARKED READY', 'tg-kpi-parked', 'created, not submitted') +
        statCard('TG - SUBMITTING', 'tg-kpi-submitting', 'in flight now') +
        statCard('TG - SUBMITTED', 'tg-kpi-submitted', 'task accepted', 'tg-kpi-submitted-sub') +
      '</div>' +

      /* LiveEngineBanner — COPIED from meta_auto_ai/public/index.html */
      '<div id="tg-liveBanner" class="bg-[#111726]/80 rounded-xl border border-slate-800 p-4 flex flex-wrap items-center justify-between gap-4" style="margin-top:1rem;">' +
        '<div class="flex items-center space-x-4 flex-wrap gap-y-2">' +
          '<div class="flex items-center space-x-2">' +
            '<span id="tg-badge" class="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-400 border border-slate-700 tracking-wider">IDLE</span>' +
            '<span id="tg-title" class="font-bold text-white text-sm tracking-wide">TG ENGINE STOPPED</span>' +
          '</div>' +
          '<div id="tg-sub" class="text-xs text-slate-400 border-l border-slate-800 pl-4 hidden md:block">' +
            'Idle. Creators will make accounts for Telegram only.</div>' +
        '</div>' +
        '<div class="flex items-center space-x-4">' +
          '<div class="text-right">' +
            '<div class="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Execution Time</div>' +
            '<div id="tg-timer" class="text-base font-mono font-bold text-white">00:00:00</div>' +
          '</div>' +
          '<div class="creator-actions" style="display:flex;gap:.5rem;align-items:center;">' +
            '<button id="tg-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start TG Engine</button>' +
            '<button id="tg-stop" type="button" class="btn btn-danger" style="display:none;" title="Stop the engine and every running creator"><i class="fa-solid fa-stop"></i> Stop</button>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- creator settings ---- */
      '<div class="card-panel creator-panel tg-settings">' +
        '<div class="card-top" style="margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;">' +
          '<div>' +
            '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:var(--accent-purple);"></i> Creator Settings</h3>' +
            '<div class="panel-desc" style="margin:0;">Applies to the next TG engine start.</div>' +
          '</div>' +
          '<span class="tg-bot-badge" id="tg-bot-badge"></span>' +
        '</div>' +
        '<div class="paygo-modules-container" id="tg-igpool-field" style="display:none;">' +
          '<div class="paygo-feature-card paygo-feature-pool" id="tg-paygo-card-pool">' +
            '<div class="paygo-feature-main">' +
              '<div class="paygo-feature-icon">' +
                '<i class="fa-solid fa-bolt"></i>' +
              '</div>' +
              '<div class="paygo-feature-text">' +
                '<div class="paygo-feature-title">' +
                  'DRAIN FROM IG CREATOR ACCOUNTS' +
                  '<span class="paygo-feature-badge pool-badge">Instant Drain</span>' +
                '</div>' +
                '<div class="paygo-feature-desc">' +
                  'Fast direct API username update in ~0.4s &amp; cookie submission into PayGo. Zero browser creation overhead.' +
                '</div>' +
              '</div>' +
            '</div>' +
            '<div class="paygo-feature-controls">' +
              '<label class="switch" title="Drain pre-created accounts directly from the IG Creator list (PayGo only)">' +
                '<input type="checkbox" id="tg-igpool-sw">' +
                '<span class="slider"></span>' +
              '</label>' +
            '</div>' +
          '</div>' +
          '<div class="paygo-feature-card paygo-feature-automine" id="tg-paygo-card-automine" style="flex-direction:column;align-items:stretch;">' +
            '<div style="display:flex;align-items:center;justify-content:space-between;gap:1.25rem;width:100%;">' +
              '<div class="paygo-feature-main">' +
                '<div class="paygo-feature-icon">' +
                  '<i class="fa-solid fa-clock-rotate-left"></i>' +
                '</div>' +
                '<div class="paygo-feature-text">' +
                  '<div class="paygo-feature-title">' +
                    'AUTO-MINE ON HOURLY REFILL (:00)' +
                    '<span class="paygo-feature-badge automine-badge">Autonomous Scheduler</span>' +
                  '</div>' +
                  '<div class="paygo-feature-desc">' +
                    'Zero-contention background engine: auto-preempts running bot at :00, drains PayGo at max speed, then restores previous task.' +
                  '</div>' +
                '</div>' +
              '</div>' +
              '<div class="paygo-feature-controls">' +
                '<span id="tg-paygo-auto-pill" class="paygo-status-pill">Auto-Mine Off</span>' +
                '<label class="switch" title="Auto-Mine PayGo: When stock refills, pauses running bot, drains PayGo pool, then resumes previous bot">' +
                  '<input type="checkbox" id="tg-paygo-auto-sw">' +
                  '<span class="slider"></span>' +
                '</label>' +
              '</div>' +
            '</div>' +
            '<div class="paygo-automine-config" id="tg-paygo-auto-config-row">' +
              '<div class="paygo-automine-slots">' +
                '<span><i class="fa-solid fa-users-gear" style="color:var(--accent-cyan);"></i> Auto-Mine Parallel Slots:</span>' +
                '<input id="tg-paygo-auto-conc" class="form-control paygo-conc-input" type="number" min="1" max="10" value="6" title="Number of parallel creators spawned when PayGo refills">' +
                '<span style="font-size:0.72rem;color:var(--text-muted);">(parallel drain slots at :00)</span>' +
              '</div>' +
              '<div class="paygo-automine-explainer">' +
                '<i class="fa-solid fa-circle-info"></i>' +
                '<span><strong>Autonomous Mode:</strong> Runs on its own at :00 — <u>no need to click Start</u>. (If you start Taskly/FastPay manually, it will auto-pause at :00, drain, and resume).</span>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="creator-service creator-task-service" style="margin-bottom:0.9rem;">' +
          '<div class="creator-service-title"><i class="fa-solid fa-list-check" style="color:var(--accent-purple);"></i> SELECT TASK</div>' +
          '<div class="creator-options" id="tg-task-options"></div>' +
          '<div class="creator-service-note" id="tg-task-note"></div>' +
          '<input type="hidden" id="tg-task" value="">' +
        '</div>' +
        '<div class="creator-grid">' +
          '<div class="creator-field">' +
            '<label>Parallel</label>' +
            '<input id="tg-conc" class="form-control" type="number" min="1" max="10" value="1">' +
          '</div>' +
          '<div class="creator-field">' +
            '<label>Target (0 = \u221e)</label>' +
            '<input id="tg-target" class="form-control" type="number" min="0" value="0">' +
          '</div>' +
          '<div class="creator-field creator-field--switch">' +
            '<label>Headless</label>' +
            '<label class="switch" title="Run browsers headless (no visible window)">' +
              '<input type="checkbox" id="tg-headless-sw" checked>' +
              '<span class="slider"></span>' +
            '</label>' +
          '</div>' +
          '<div class="creator-field creator-field--switch" id="tg-adde-field">' +
            '<label>Extra Email</label>' +
            '<label class="switch" title="Fresh mail.td email before task registration">' +
              '<input type="checkbox" id="tg-adde-sw" checked>' +
              '<span class="slider"></span>' +
            '</label>' +
          '</div>' +
        '</div>' +
        '<div class="creator-services" id="tg-services-panel">' +
          '<div class="creator-service">' +
            '<div class="creator-service-title"><i class="fa-solid fa-envelope" style="color:var(--accent-cyan);"></i> MAIL INBOX</div>' +
            '<div class="creator-options">' +
              '<label class="creator-option">' +
                '<input type="radio" name="tg-mail" value="mailtd" checked> ' +
                '<i class="fa-solid fa-inbox" style="color:var(--accent-green);"></i> mail.td ' +
                '<span class="creator-option-hint">(only provider)</span>' +
              '</label>' +
            '</div>' +
            '<div class="creator-service-note">mail.td is the only enabled mailbox provider.</div>' +
          '</div>' +
          '<div class="creator-service">' +
            '<div class="creator-service-title"><i class="fa-solid fa-shield-halved" style="color:var(--accent-purple);"></i> CAPTCHA SOLVER</div>' +
            '<div class="creator-options">' +
              '<label class="creator-option" title="Visual challenge first via in-browser YOLOv5 ONNX AI extension, automatic fallback to Audio STT">' +
                '<input type="radio" name="tg-captcha" value="extension" checked> ' +
                '<i class="fa-solid fa-eye" style="color:var(--accent-green);"></i> Visual AI (JA) ' +
                '<span class="creator-option-hint">(\u2192 Audio fallback)</span>' +
              '</label>' +
              '<label class="creator-option" title="Audio challenge first via Whisper / Vosk speech recognition, automatic fallback to Visual AI">' +
                '<input type="radio" name="tg-captcha" value="audio"> ' +
                '<i class="fa-solid fa-headphones" style="color:var(--accent-purple);"></i> Audio (Whisper) ' +
                '<span class="creator-option-hint">(\u2192 Visual fallback)</span>' +
              '</label>' +
            '</div>' +
            '<div class="creator-service-note">Visual AI is the default; audio is used automatically if the visual solver stalls.</div>' +
          '</div>' +
        '</div>' +
      '</div>' +

      /* ---- console ---- */
      '<div class="card-panel" style="margin-top:1.25rem;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">' +
          '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>' +
          '<div style="display:flex;gap:0.5rem;align-items:center;">' +
            '<label style="display:flex;align-items:center;gap:0.4rem;font-size:0.78rem;color:var(--text-dim);">' +
              '<input type="checkbox" id="tg-autoscroll" checked> Auto-scroll</label>' +
            '<button id="tg-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
            '<button id="tg-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button>' +
          '</div>' +
        '</div>' +
        '<div id="tg-log" class="log-container" style="height:220px;overflow-y:auto;background:#060910;' +
          'border:1px solid var(--border-color);border-radius:8px;padding:0.75rem;' +
          'font-family:var(--font-mono);font-size:0.78rem;white-space:pre-wrap;"></div>' +
      '</div>' +

      /* ---- failure reasons & session logs (meta_auto_ai parity) ---- */
      (window.NovaDiag ? NovaDiag.renderHtml('tg') : '');

    wire();
    if (window.NovaDiag) {
      NovaDiag.refreshReasons();
      NovaDiag.refreshLogs();
    }
  }

  function setWindow(headless) {
    state.cfg.headless = !!headless;
    var sw = $('tg-headless-sw');
    if (sw) sw.checked = !!headless;
  }

  var addEmail = true;
  function setAddEmail(on) {
    addEmail = !!on;
    var sw = $('tg-adde-sw');
    if (sw) sw.checked = !!on;
  }

  // Pool preflight for Start. The coupled cycle creates a Meta account BEFORE
  // leasing a Telegram profile, so an empty/disabled/logged-out pool must be
  // refused here — otherwise we burn a Meta account and only then hit
  // "No Telegram profile is logged in".
  function poolPreflight(rows) {
    var list = rows || [];
    var enabled = list.filter(function (p) { return p.enabled !== false; });
    return {
      total: list.length,
      enabled: enabled.length,
      connected: enabled.filter(function (p) { return p.logged_in === true; }).length,
    };
  }

  function startEngine() {
    var btn = $('tg-start');
    var bot = state.bot || 'taskly';
    var botName = bot === 'paygo' ? 'PayGo' : bot === 'fastpay' ? 'FastPay' : 'Taskly';
    if (btn) btn.disabled = true;
    // no-store: the pool is a live read. A cached (stale/empty) status here used
    // to block Start with "no profile in the pool" while the card above showed
    // a Ready profile.
    fetch('/api/tg/status', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (btn) btn.disabled = false;
        if (!s) throw new Error('status unavailable');
        var list = (s.pool && s.pool.accounts) || null;
        // Fall back to the pool the refresh loop last saw if this read came back
        // empty — never block Start on one empty read.
        if (!list || !list.length) list = state.pool || [];
        var st = poolPreflight(list);
        if (!st.total) {
          toast('No Telegram account is connected. Click "+ Add MTProto" to log one in, then start.', 'error', 14000);
          append('! start blocked \u2014 no Telegram profile in the pool');
        } else if (!st.enabled) {
          toast('Every Telegram profile is disabled. Enable at least one, then start.', 'error', 14000);
          append('! start blocked \u2014 no enabled Telegram profile');
        } else if (!st.connected) {
          toast('No connected Telegram account for ' + botName + '. Log in (or re-enable) a profile, then start.', 'error', 14000);
          append('! start blocked \u2014 no logged-in Telegram profile for ' + botName);
        } else {
          var task = ($('tg-task') || {}).value ||
            ((BOT_META[bot] || BOT_META.taskly).tasks[0] || [''])[0];
          var isIgPool = (bot === 'paygo') && !!($('tg-igpool-sw') && $('tg-igpool-sw').checked);
          var effConc = parseInt(($('tg-conc') || {}).value || 1, 10);
          var effTarget = parseInt(($('tg-target') || {}).value || 0, 10);
          var effAddEmail = (isIgPool || isCookieTask(task) || isNativeTask(task)) ? false : addEmail;
          var captchaEl = document.querySelector('input[name="tg-captcha"]:checked');
          var captchaChoice = captchaEl ? captchaEl.value : 'extension';
          append('> start (' + st.connected + ' connected \u00b7 ' + botName +
                 (isIgPool ? ' [POOL DRAIN: IG Creator Accounts]' : '') +
                 ', parallel=' + effConc +
                 ', target=' + effTarget +
                 ', ' + (state.cfg.headless ? 'headless' : 'visible') +
                 ', captcha=' + captchaChoice +
                 ', add_email=' + effAddEmail + ')');
          post('/api/tg/start', {
            concurrency: effConc,
            target: effTarget,
            headless: state.cfg.headless,
            captcha: captchaChoice,
            tg_task: task,
            tg_bot: bot,
            add_email: effAddEmail,
            use_ig_pool: isIgPool,
          });
        }
      })
      .catch(function (e) {
        if (btn) btn.disabled = false;
        toast('Could not verify the Telegram pool: ' + e, 'error', 12000);
        append('! start blocked \u2014 ' + e);
      });
  }

  function wire() {
    if ($('tg-start')) $('tg-start').addEventListener('click', startEngine);
    if ($('tg-stop')) $('tg-stop').addEventListener('click', function () { post('/api/tg/stop', {}); });
    window.__setTgBot(state.bot);
    if ($('tg-task')) $('tg-task').addEventListener('change', applyFlowGuards);
    if ($('tg-igpool-sw')) $('tg-igpool-sw').addEventListener('change', applyFlowGuards);
    if ($('tg-conc')) $('tg-conc').addEventListener('input', function () { setStatus(state.running, state.igMode); });
    if ($('tg-headless-sw')) $('tg-headless-sw').addEventListener('change', function () { setWindow($('tg-headless-sw').checked); });
    if ($('tg-adde-sw')) $('tg-adde-sw').addEventListener('change', function () { addEmail = !!$('tg-adde-sw').checked; });
    if ($('tg-refresh')) $('tg-refresh').addEventListener('click', refresh);
    if ($('tg-clear')) $('tg-clear').addEventListener('click', function () { state.log = []; paintLog(); });
    if ($('tg-copy')) $('tg-copy').addEventListener('click', function () {
      var txt = state.log.join('\n');
      try {
        if (navigator.clipboard) navigator.clipboard.writeText(txt);
        else { var t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand('copy'); document.body.removeChild(t); }
        toast('Log copied.', 'ok', 2500);
      } catch (e) { toast('Copy failed: ' + e, 'error'); }
    });
    if ($('tg-bal-hide')) $('tg-bal-hide').addEventListener('click', function () {
      if ($('tg-bal-wrap')) $('tg-bal-wrap').style.display = 'none';
    });
    if ($('tg-add-toggle')) $('tg-add-toggle').addEventListener('click', function () { mtReset(); mtOpen(); });
    if ($('mtOpenGuide')) $('mtOpenGuide').addEventListener('click', function () {
      mtClose();
      var nav = document.querySelector('.nav-item[data-view="view-guide"]');
      if (nav) nav.click();
      var scroller = document.querySelector('.content-scroll');
      if (scroller) scroller.scrollTop = 0;
    });
    if ($('tg-enable-all')) $('tg-enable-all').addEventListener('click', function () { tgEnableAll(true); });
    if ($('tg-disable-all')) $('tg-disable-all').addEventListener('click', function () { tgEnableAll(false); });

    if ($('tg-bal')) $('tg-bal').addEventListener('click', onBalances);
  }

  /* ---------------- Balances (BOTH bots) ---------------- */
  function onBalances() {
    append('> balances (a .session serves one client; leased accounts are skipped)');
    fetch('/api/tg/mtproto/balance_all', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: '{}' })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var accts = (j && j.accounts) || [];
        var NUM = function (b) {
          if (!b || !b.ok) return null;
          var n = parseFloat(String(b.balance == null ? '' : b.balance).replace(/[^0-9.\-]/g, ''));
          return isNaN(n) ? null : n;
        };
        var fmt = function (n) { return n == null ? '\u2014' : '$' + n.toFixed(2); };
        var okCount = 0, tT = 0, tP = 0, tF = 0, tG = 0;

        var body = $('tg-bal-body');
        if (body) body.innerHTML = accts.map(function (a) {
          var bots = a.bots || [];
          var taskly = bots.filter(function (b) { return b.target === 'taskly'; })[0];
          var paygo  = bots.filter(function (b) { return b.target === 'paygo';  })[0];
          var fastpay = bots.filter(function (b) { return b.target === 'fastpay'; })[0];
          var nT = NUM(taskly), nP = NUM(paygo), nF = NUM(fastpay);
          if (taskly && taskly.ok) okCount++;
          if (paygo  && paygo.ok)  okCount++;
          if (fastpay && fastpay.ok) okCount++;
          if (nT != null) tT += nT;
          if (nP != null) tP += nP;
          if (nF != null) tF += nF;
          var rowTotal = (nT || 0) + (nP || 0) + (nF || 0);
          tG += rowTotal;
          var warn = bots.filter(function (b) { return !b.ok; })
                         .map(function (b) { return '\u26a0 ' + (b.error || b.name); }).join('; ');
          return '<tr style="border-top:1px solid var(--border-color);">' +
            '<td style="padding:5px 6px;">' + esc(a.id || '?') +
              (warn ? '<div class="creator-option-hint" style="font-size:10px;">' + esc(warn) + '</div>' : '') +
            '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + (taskly && taskly.ok ? fmt(nT) : '\u26a0') + '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + (paygo  && paygo.ok  ? fmt(nP) : '\u26a0') + '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + (fastpay && fastpay.ok ? (fmt(nF) + (fastpay.pending ? ' <span style="font-size:10px;color:#eab308;" title="Pending: $' + Number(fastpay.pending).toFixed(2) + '">(+$' + Number(fastpay.pending).toFixed(2) + ' pend)</span>' : '')) : '\u26a0') + '</td>' +
            '<td style="padding:5px 6px;text-align:right;">' + fmt(rowTotal) + '</td>' +
          '</tr>';
        }).join('') || '<tr><td colspan="5" class="creator-option-hint" style="padding:8px;">' +
          'No MTProto accounts yet \u2014 use <b>+ Add MTProto</b>.</td></tr>';

        var t = (j && j.totals) || {};
        if ($('tg-bal-t-taskly')) $('tg-bal-t-taskly').textContent = fmt(tT);
        if ($('tg-bal-t-paygo'))  $('tg-bal-t-paygo').textContent  = fmt(tP);
        if ($('tg-bal-t-fastpay')) $('tg-bal-t-fastpay').textContent = fmt(tF) + (t.fastpay_pending ? ' (+$' + Number(t.fastpay_pending).toFixed(2) + ')' : '');
        if ($('tg-bal-t-grand'))  $('tg-bal-t-grand').textContent  = '$' + tG.toFixed(2);
        if ($('tg-bal-wrap')) $('tg-bal-wrap').style.display = 'block';

        // Distinguish a real $0.00 from a FAILED read.
        if (!accts.length) append('! no MTProto accounts in the pool \u2014 add one first');
        else if (!okCount) append('! balance read FAILED for every account \u2014 NOT a zero balance');
        else {
          var fpMsg = 'FastPay $' + Number(t.fastpay || 0).toFixed(2) + (t.fastpay_pending ? ' [+$' + Number(t.fastpay_pending).toFixed(2) + ' pend]' : '');
          append('Taskly $' + Number(t.taskly || 0).toFixed(2) + ' · PayGo $'
               + Number(t.paygo || 0).toFixed(2) + ' · ' + fpMsg
               + ' · TOTAL $' + Number(t.grand || 0).toFixed(2)
               + '   (' + okCount + '/' + accts.length + ' accounts read)');
        }
        if (j && j.error) append('! ' + j.error);
      })
      .catch(function (e) { append('! ' + e); });
  }

  /* ---------------- pool actions ---------------- */
  function tgAction(url, body, okMsg) {
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.ok) { if (okMsg) append('* ' + okMsg); }
        else { toast((j && j.error) || 'action failed', 'error'); append('! ' + ((j && j.error) || 'action failed')); }
        refresh();
      })
      .catch(function (e) { toast('' + e, 'error'); });
  }
  function tgToggle(id, on)  { tgAction('/api/tg/accounts/toggle', { id: id, enabled: on }, id + (on ? ' enabled' : ' disabled')); }
  function tgEnableAll(on)   { tgAction('/api/tg/pool/enable_all', { enabled: on }, on ? 'all profiles enabled' : 'all profiles disabled'); }
  function tgRemove(id) {
    if (!confirm('Remove ' + id + ' and its session file? This cannot be undone.')) return;
    tgAction('/api/tg/accounts/remove', { id: id }, id + ' removed');
  }

  /* Pool state for one profile CARD (mirrors meta_auto_ai's poolState).
     Named profileState — NOT poolState: the Start preflight already owns that
     name above. Two same-named declarations meant the later one won, so the
     preflight silently got this function's shape (total === undefined) and
     blocked every start. */
  function profileState(p) {
    if (p.status === 'busy') return { key: 'busy', label: 'In use', cls: 'badge-warn' };
    if (p.enabled === false) return { key: 'disabled', label: 'Disabled', cls: 'badge-inactive' };
    if (!p.logged_in) return { key: 'nosess', label: 'No session', cls: 'badge-rose' };
    return { key: 'idle', label: 'Ready', cls: 'badge-active' };
  }

  function tgEdit(id) {
    var cur = null;
    for (var i = 0; i < state.pool.length; i++) {
      if (state.pool[i].id === id) { cur = state.pool[i]; break; }
    }
    cur = cur || {};
    var name = window.prompt('Display name for ' + id + ':', cur.name || cur.label || '');
    if (name === null) return;
    var phone = window.prompt('Phone number for ' + id + ':', cur.phone || '');
    if (phone === null) return;
    tgAction('/api/tg/accounts/update', { id: id, name: name, phone: phone }, id + ' updated');
  }

  function tgBalanceOne(id) {
    append('> balance ' + id + ' (Taskly + PayGo + FastPay)');
    fetch('/api/tg/mtproto/balance', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.ok) {
          toast((j && j.error) || ('balance failed for ' + id), 'error', 12000);
          append('! balance ' + id + ': ' + ((j && j.error) || 'failed'));
          return;
        }
        var parts = ((j && j.bots) || []).map(function (b) {
          return (b.name || b.target) + ' ' + (b.ok ? (b.balance || '?') : ('\u26a0 ' + (b.error || 'n/a')));
        });
        append('= ' + id + ': ' + (parts.join(' | ') || 'ok'));
      })
      .catch(function (e) { append('! balance ' + id + ': ' + e); });
  }

  function renderPool(rows) {
    state.pool = rows || [];
    var el = $('tg-pool'), sum = $('tg-pool-sum');
    var ready = state.pool.filter(function (p) { return p.logged_in; }).length;
    var busy = state.pool.filter(function (p) { return p.status === 'busy'; }).length;
    if (sum) sum.textContent = state.pool.length + (state.pool.length === 1 ? ' profile' : ' profiles') +
      ' \u00b7 ' + ready + ' ready \u00b7 ' + busy + ' in use';
    if (!el) return;
    if (!state.pool.length) {
      el.innerHTML = '<div class="creator-option-hint">No profiles yet. Use <b>+ Add MTProto</b> above.</div>';
      return;
    }
    el.innerHTML = state.pool.map(function (p) {
      var st = profileState(p);
      // Prefer the editable display name ("Asif BL"); fall back to the stored
      // auto-label minus its trailing mode suffix ("TG tg_1 · MTProto").
      var display = p.name ||
        String(p.label || p.id).replace(/\s*[·|]\s*(mtproto|web)\s*$/i, '').trim() || String(p.id);
      var isMt = (p.mode || 'mtproto') === 'mtproto';
      var modePill = isMt
        ? '<span class="tg-mode-pill tg-mode-mtproto" title="Logged in over MTProto (Telethon) \u2014 no browser"><i class="fa-solid fa-bolt"></i>MTProto</span>'
        : '<span class="tg-mode-pill tg-mode-web" title="Logged in via Telegram Web (browser)"><i class="fa-solid fa-globe"></i>Web</span>';
      var busyLock = p.status === 'busy';
      var off = p.enabled === false;
      var sub = p.phone
        ? '<span class="tg-profile-phone">' + esc(p.phone) + '</span>'
        : '<span>' + esc(p.status || 'idle') + ' \u00b7 ' + (p.tasks_done || 0) + ' tasks</span>';
      var dis = busyLock ? ' disabled title="Release the profile first"' : '';
      return '<div class="tg-profile-row' + (off ? ' is-off' : '') + (busyLock ? ' is-busy' : '') + '">' +
        '<div class="tg-profile-main">' +
          '<span class="tg-profile-avatar"><i class="fa-brands fa-telegram"></i></span>' +
          '<div class="tg-profile-info">' +
            '<div class="tg-profile-title">' +
              '<strong>' + esc(display) + '</strong>' +
              '<span class="tg-profile-id">' + esc(p.id) + '</span>' +
              modePill +
              '<span class="profile-status-badge ' + st.cls + '" title="' + esc(st.label) + '">' + esc(st.label) + '</span>' +
            '</div>' +
            '<div class="tg-profile-meta">' + sub + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="tg-profile-actions">' +
          '<label class="switch" title="' + (off ? 'Disabled \u2014 click to enable for tasks' : 'Enabled \u2014 click to disable for tasks') + '">' +
            '<input type="checkbox" data-tg-enable="' + esc(p.id) + '"' + (off ? '' : ' checked') + '>' +
            '<span class="slider"></span>' +
          '</label>' +
          '<button type="button" class="tg-icon-btn" data-tg-edit="' + esc(p.id) + '"' +
            ' title="Edit name / phone"><i class="fa-solid fa-pencil"></i></button>' +
          '<button type="button" class="tg-icon-btn tg-icon-btn-indigo" data-tg-bal="' + esc(p.id) + '"' + dis +
            ' title="Get balance (Taskly + PayGo + FastPay)"><i class="fa-solid fa-wallet"></i></button>' +
          '<button type="button" class="tg-icon-btn tg-icon-btn-danger" data-tg-del="' + esc(p.id) + '"' + dis +
            ' title="Remove this profile and its session"><i class="fa-solid fa-trash-can"></i></button>' +
        '</div>' +
      '</div>';
    }).join('');

    if (el.querySelectorAll) {
      el.querySelectorAll('[data-tg-enable]').forEach(function (b) {
        b.addEventListener('change', function () { tgToggle(b.dataset.tgEnable, b.checked); });
      });
      el.querySelectorAll('[data-tg-edit]').forEach(function (b) {
        b.addEventListener('click', function () { tgEdit(b.dataset.tgEdit); });
      });
      el.querySelectorAll('[data-tg-bal]').forEach(function (b) {
        b.addEventListener('click', function () { tgBalanceOne(b.dataset.tgBal); });
      });
      el.querySelectorAll('[data-tg-del]').forEach(function (b) {
        b.addEventListener('click', function () { tgRemove(b.dataset.tgDel); });
      });
    }
  }

  /* ---------------- engine state ---------------- */
  function setStatus(running, igMode, activeBot, engineCfg) {
    state.running = running; state.igMode = igMode || null;
    var badge = $('tg-badge'), title = $('tg-title'), sub = $('tg-sub'), start = $('tg-start');
    var bot = state.bot || 'taskly';
    var isCurrentBotRunning = running && (activeBot === bot);
    var isOtherBotRunning = running && activeBot && (activeBot !== bot);
    var botName = bot === 'paygo' ? 'PayGo' : bot === 'fastpay' ? 'FastPay' : 'Taskly';
    var activeBotName = activeBot === 'paygo' ? 'PayGo' : activeBot === 'fastpay' ? 'FastPay' : (activeBot ? 'Taskly' : '');
    var isIgPool = (bot === 'paygo') && !!($('tg-igpool-sw') && $('tg-igpool-sw').checked);
    var effConc = parseInt(($('tg-conc') || {}).value || 1, 10);
    var runningConc = (engineCfg && engineCfg.concurrency) || effConc;
    var pSt = window.__paygoAutoStatus;

    if (badge) {
      if (isCurrentBotRunning) {
        badge.textContent = 'RUNNING';
        badge.style.background = 'var(--accent-green)';
        badge.style.color = '#04140d';
        badge.style.borderColor = 'var(--accent-green)';
      } else if (isOtherBotRunning) {
        badge.textContent = activeBotName.toUpperCase() + ' RUNNING';
        badge.style.background = 'rgba(245, 158, 11, 0.2)';
        badge.style.color = '#fbbf24';
        badge.style.borderColor = 'rgba(245, 158, 11, 0.45)';
      } else if (pSt && pSt.enabled) {
        badge.textContent = 'AUTO-MINE ARMED';
        badge.style.background = 'rgba(245, 158, 11, 0.2)';
        badge.style.color = '#fbbf24';
        badge.style.borderColor = 'rgba(245, 158, 11, 0.45)';
      } else {
        badge.textContent = 'IDLE';
        badge.style.background = 'var(--bg-input)';
        badge.style.color = 'var(--text-dim)';
        badge.style.borderColor = 'var(--border-color)';
      }
    }
    if (title) {
      if (isCurrentBotRunning) {
        title.textContent = isIgPool ? 'PAYGO POOL DRAIN RUNNING' : ('TG ENGINE RUNNING (' + botName.toUpperCase() + ')');
      } else if (isOtherBotRunning) {
        title.textContent = botName.toUpperCase() + ' (IDLE · ' + activeBotName.toUpperCase() + ' RUNNING)';
      } else if (pSt && pSt.enabled) {
        title.textContent = 'AUTO-MINE ARMED (STANDBY)';
      } else {
        title.textContent = 'TG ENGINE STOPPED';
      }
    }
    if (sub) {
      if (isCurrentBotRunning) {
        sub.textContent = isIgPool
          ? ('Instant account drain active (' + runningConc + ' parallel slots). Direct IG Web API & cookie submit.')
          : ('Creators are running (' + runningConc + ' parallel slots) — one browser per task, coupled cycle.');
      } else if (isOtherBotRunning) {
        sub.textContent = '⚡ ' + activeBotName + ' is currently running in the background (' + runningConc + ' parallel slots). Only one Telegram bot can run at a time. Stop ' + activeBotName + ' to start ' + botName + '.';
      } else if (pSt && pSt.enabled) {
        var m = Math.floor(pSt.wait_seconds / 60);
        var s = pSt.wait_seconds % 60;
        var sStr = s < 10 ? '0' + s : s;
        sub.textContent = 'Armed for :00 refill (in ' + m + 'm ' + sStr + 's). Will auto-launch ' + (pSt.concurrency || 6) + ' parallel slots. (Click Start below if you want to run ' + botName + ' in the meantime).';
      } else {
        sub.textContent = 'Idle. Click Start below to launch ' + botName + ' creators.';
      }
    }
    // Dynamic Action Buttons
    var stopBtn = $('tg-stop');
    if (start) {
      if (isCurrentBotRunning) {
        start.style.display = 'none';
        start.disabled = true;
      } else if (isOtherBotRunning) {
        start.style.display = '';
        start.disabled = true;
        start.innerHTML = '<i class="fa-solid fa-lock"></i> Start Blocked (' + activeBotName + ' Active)';
      } else {
        start.style.display = '';
        start.disabled = false;
        if (isIgPool) {
          start.innerHTML = '<i class="fa-solid fa-bolt"></i> Start PayGo Pool Drain (Manual · ' + effConc + ' Slots)';
        } else {
          start.innerHTML = '<i class="fa-solid fa-play"></i> Start ' + botName + ' Engine (' + effConc + ' Slots)';
        }
      }
    }
    if (stopBtn) {
      if (isCurrentBotRunning) {
        stopBtn.style.display = '';
        stopBtn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop ' + botName;
      } else {
        stopBtn.style.display = 'none';
      }
    }
    if (running && !state.startedAt) state.startedAt = Date.now();
    if (!running) state.startedAt = null;
  }

  function kpi(id, v) { var e = $(id); if (e) e.textContent = String(v == null ? 0 : v); }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function tickTimer() {
    var el = $('tg-timer'); if (!el) return;
    var base = state.startedAt;
    if (!base) { el.textContent = '00:00:00'; return; }
    var t = Math.max(0, Math.floor((Date.now() - base) / 1000));
    el.textContent = pad(Math.floor(t / 3600)) + ':' + pad(Math.floor(t / 60) % 60) + ':' + pad(t % 60);
  }

  function refresh() {
    if (!root) return;
    fetch('/api/tg/status', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) { setStatus(false, null, null, null); return; }
        // Follow the build manifest: a single-bot build (e.g. --bots fastpay)
        // must not stay on a 'taskly' that was never shipped.
        var eb = s.enabled_bots || [];
        if (eb.length && eb.indexOf(state.bot) === -1) {
          state.bot = eb[0];
          renderTaskOptions(state.bot);
          updateBotBadge(state.bot);
          applyFlowGuards();
        }
        var activeBot = (s.running && s.engine && s.engine.tg_bot) ? s.engine.tg_bot : null;
        setStatus(!!s.running, s.ig_mode, activeBot, s.engine);
        renderPool(s.pool && s.pool.accounts ? s.pool.accounts : s.pool);
        // ALL KPIs are PER BOT — Taskly, PayGo and FastPay never share a number.
        // (Unassigned parked records count toward every bot: any submitter can
        // claim them. Falls back to the combined counters against an old server.)
        var bot = state.bot || 'taskly';
        var tot = bot === 'paygo' ? s.tg_total_paygo
                : bot === 'fastpay' ? s.tg_total_fastpay
                : s.tg_total_taskly;
        kpi('tg-kpi-total', tot == null ? (s.tg_total != null ? s.tg_total : s.total_accounts) : tot);
        var pen = bot === 'paygo' ? s.tg_pending_paygo
                : bot === 'fastpay' ? s.tg_pending_fastpay
                : s.tg_pending_taskly;
        kpi('tg-kpi-parked', pen == null ? s.tg_pending : pen);
        // SUBMITTED is PER BOT — Taskly, PayGo and FastPay never share a number.
        var sub = bot === 'paygo' ? s.tg_submitted_paygo
                : bot === 'fastpay' ? s.tg_submitted_fastpay
                : s.tg_submitted_taskly;
        kpi('tg-kpi-submitted', sub == null ? s.tg_submitted : sub);
        var subEl = $('tg-kpi-submitted-sub');
        if (subEl) {
          var botName = bot === 'paygo' ? 'PayGo' : bot === 'fastpay' ? 'FastPay' : 'Taskly';
          subEl.textContent = botName + ' task accepted';
        }
        // SUBMITTING = in-flight slots, but only when the RUNNING bot is this page's bot.
        var runBot = s.engine && s.engine.tg_bot ? String(s.engine.tg_bot).toLowerCase() : null;
        // Refresh PayGo Auto-Mining status
        fetch('/api/tg/paygo-auto/status', { cache: 'no-store' })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (j) { if (j && j.status) updatePayGoAutoUI(j.status); })
          .catch(function () {});
      })
      .catch(function () { setStatus(false, null); });
  }

  function updatePayGoAutoUI(st) {
    if (!st) return;
    window.__paygoAutoStatus = st;
    var sw = $('tg-paygo-auto-sw');
    var autoConc = $('tg-paygo-auto-conc');
    var pill = $('tg-paygo-auto-pill');
    var cardAuto = $('tg-paygo-card-automine');

    if (sw && document.activeElement !== sw) sw.checked = !!st.enabled;
    if (autoConc && document.activeElement !== autoConc && st.concurrency) {
      autoConc.value = st.concurrency;
    }
    if (cardAuto) {
      if (st.enabled || st.is_paygo_active) cardAuto.classList.add('is-active');
      else cardAuto.classList.remove('is-active');
    }
    var concDisplay = st.concurrency || 6;
    if (pill) {
      if (st.is_paygo_active) {
        pill.textContent = '⚡ Active (Draining ' + concDisplay + ' Slots)';
        pill.style.background = 'rgba(16,185,129,0.18)';
        pill.style.borderColor = 'rgba(16,185,129,0.4)';
        pill.style.color = '#34d399';
        pill.style.fontWeight = '700';
      } else if (st.enabled) {
        var m = Math.floor(st.wait_seconds / 60);
        var s = st.wait_seconds % 60;
        var sStr = s < 10 ? '0' + s : s;
        if (state.running) {
          pill.textContent = '🛡️ Preempting in ' + m + 'm ' + sStr + 's (' + concDisplay + ' slots)';
        } else {
          pill.textContent = '⏳ Armed: Refill in ' + m + 'm ' + sStr + 's (' + concDisplay + ' slots)';
        }
        pill.style.background = 'rgba(245,158,11,0.14)';
        pill.style.borderColor = 'rgba(245,158,11,0.35)';
        pill.style.color = '#fbbf24';
        pill.style.fontWeight = '600';
      } else {
        pill.textContent = 'Auto-Mine Off';
        pill.style.background = 'rgba(255,255,255,0.04)';
        pill.style.borderColor = 'rgba(255,255,255,0.08)';
        pill.style.color = 'var(--text-muted)';
        pill.style.fontWeight = '600';
      }
    }
    if (!state.running) {
      setStatus(false, state.igMode);
    }
  }

  /* ---------------- log ---------------- */
  function append(line, bot) {
    var b = (bot && botLogs[bot]) ? bot : (state.bot || 'taskly');
    if (!botLogs[b]) botLogs[b] = [];
    var entry = '[' + new Date().toLocaleTimeString() + '] ' + line;
    botLogs[b].push(entry);
    if (botLogs[b].length > 400) botLogs[b] = botLogs[b].slice(-300);

    // If this log entry belongs to the currently active bot tab, repaint
    if (b === state.bot) {
      state.log = botLogs[b];
      paintLog();
    }
  }
  function paintLog() {
    var el = $('tg-log');
    if (!el) return;
    el.textContent = (botLogs[state.bot] || []).join('\n');
    var auto = $('tg-autoscroll');
    if (!auto || auto.checked) el.scrollTop = el.scrollHeight;
  }
  function post(url, body) {
    append('> POST ' + url, state.bot);
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        append('< ' + JSON.stringify(j), state.bot);
        if (j && (j.error || j.status === 'ERROR')) toast(j.error || 'Request failed', 'error', 12000);
        refresh();
      })
      .catch(function (e) { append('! ' + e, state.bot); toast('Request failed: ' + e, 'error', 12000); });
  }

  /* ---------------- MTProto modal ---------------- */
  function mtOpen()  { if ($('mtprotoModal')) { $('mtprotoModal').classList.add('active'); $('mtprotoModal').style.display = 'flex'; } }
  function mtClose() { if ($('mtprotoModal')) { $('mtprotoModal').classList.remove('active'); $('mtprotoModal').style.display = 'none'; } }
  function mtMsg(t)  { if ($('mtStatus')) $('mtStatus').textContent = t || ''; }
  function mtReset() {
    if ($('mtCodeWrap')) $('mtCodeWrap').style.display = 'none';
    if ($('mtVerify')) $('mtVerify').style.display = 'none';
    mtMsg('');
  }
  function mtLoadCreds() {
    fetch('/api/tg/mtproto/credentials').then(function (r) { return r.json(); })
      .then(function (j) {
        var need = !(j && j.has_credentials);
        if ($('mtCredsWrap')) $('mtCredsWrap').style.display = 'block';
        if ($('mtCredsStatus')) {
          $('mtCredsStatus').textContent = need
            ? 'No credentials saved yet \u2014 fill these in (one pair works for all accounts).'
            : ('Using saved credentials (api_id ' + (j.api_id || '?') + ', hash ' +
               (j.api_hash_masked || '****') + ', source: ' + (j.source || 'file') +
               '). One pair serves every account.');
        }
      }).catch(function () {});
  }
  function mtWire() {
    if (!$('mtprotoModal') || $('mtprotoModal').dataset.wired) return;
    $('mtprotoModal').dataset.wired = '1';
    if ($('mtCancel')) $('mtCancel').addEventListener('click', mtClose);
    if ($('mtEditCreds')) $('mtEditCreds').addEventListener('click', function () {
      var w = $('mtCredsWrap'); if (w) w.style.display = (w.style.display === 'none') ? 'block' : 'none';
    });
    if ($('mtSaveCreds')) $('mtSaveCreds').addEventListener('click', function () {
      var apiId = ($('mtApiId').value || '').trim(), apiHash = ($('mtApiHash').value || '').trim();
      if (!apiId || !apiHash) { if ($('mtCredsStatus')) $('mtCredsStatus').textContent = 'Both api_id and api_hash are required.'; return; }
      fetch('/api/tg/mtproto/credentials', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_id: apiId, api_hash: apiHash }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if ($('mtCredsStatus')) $('mtCredsStatus').textContent = j && j.ok ? '\u2713 Saved.' : ('\u2717 ' + ((j && j.error) || 'failed'));
          if (j && j.ok) { append('* API credentials saved', state.bot); mtLoadCreds(); }
        });
    });
    if ($('mtSendCode')) $('mtSendCode').addEventListener('click', function () {
      var phone = ($('mtPhone').value || '').trim();
      if (!phone) { mtMsg('Enter the phone number with country code.'); return; }
      mtMsg('Requesting code\u2026');
      fetch('/api/tg/mtproto/send_code', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: phone, label: ($('mtLabel').value || '').trim() || undefined }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j && j.phone_code_hash) {
            window.__tgPending = j;
            if ($('mtCodeWrap')) $('mtCodeWrap').style.display = 'block';
            if ($('mtVerify')) $('mtVerify').style.display = 'inline-block';
            if ($('mtStep')) $('mtStep').textContent = 'code sent';
            mtMsg('Code sent inside Telegram. Enter it below' + (j.need_password ? ' and the 2FA password.' : '.'));
          } else { mtMsg('\u2717 ' + ((j && j.error) || 'could not send code')); }
        }).catch(function (e) { mtMsg('\u2717 ' + e); });
    });
    if ($('mtVerify')) $('mtVerify').addEventListener('click', function () {
      var code = ($('mtCode').value || '').trim();
      if (!code) { mtMsg('Enter the login code.'); return; }
      mtMsg('Verifying\u2026');
      fetch('/api/tg/mtproto/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: ($('mtPhone').value || '').trim(), code: code,
          phone_code_hash: (window.__tgPending || {}).phone_code_hash,
          password: ($('mtPassword').value || '') || undefined }) })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          // NOTE: the key is need_password (single 's') — matches tg_login_mtproto.py.
          if (j && j.need_password && !($('mtPassword').value || '').trim()) {
            mtMsg('This account has 2FA \u2014 enter the password and press Verify again.'); return;
          }
          if (j && j.ok) { mtMsg('\u2713 Account added to the pool.'); append('* MTProto account added', state.bot); setTimeout(function () { mtClose(); refresh(); }, 900); }
          else { mtMsg('\u2717 ' + ((j && j.error) || 'verify failed')); }
        }).catch(function (e) { mtMsg('\u2717 ' + e); });
    });
  }

  function handleTgEvent(d) {
    if (!d) return;
    if (d && (d.pipeline === 'meta' || d.engine === 'metainsta' || d.engine === 'meta' || d.engine === 'ig')) return;
    if (d && d.pipeline && d.pipeline !== 'telegram') return;
    if (d && d.type === 'throttle') {
      hideThrottleBanner();
      return;
    }

    var targetBot = (d && d.tg_bot) ? String(d.tg_bot).toLowerCase() : null;
    if (!targetBot && (d.message || d.detail)) {
      var mLower = String(d.message || d.detail || '').toLowerCase();
      if (mLower.indexOf('[fastpay') !== -1 || mLower.indexOf('fastpay') !== -1) targetBot = 'fastpay';
      else if (mLower.indexOf('[paygo') !== -1 || mLower.indexOf('paygo') !== -1) targetBot = 'paygo';
      else if (mLower.indexOf('[taskly') !== -1 || mLower.indexOf('taskly') !== -1) targetBot = 'taskly';
    }
    if (!targetBot && state.running && state.engine && state.engine.tg_bot) {
      targetBot = String(state.engine.tg_bot).toLowerCase();
    }
    if (!targetBot) targetBot = state.bot || 'taskly';

    var msg = d.message || (d.type === 'slot_event' && d.detail ? ('[Slot ' + (d.slot_id || '?') + '] ' + d.detail) : null);
    if (msg) {
      append(String(msg), targetBot);
      var m = String(msg);
      if (/not a member|join the bot|start the bot|has not joined|no such bot|BOT not|chat not found/i.test(m))
        toast('A pooled account has not joined the selected bot — open that Telegram account and press /start on the bot, then retry.', 'warn', 15000);
      else if (/not logged in|session.*revoked|AUTH_KEY_UNREGISTERED/i.test(m))
        toast('A Telegram session is dead — disable that profile or log in again.', 'error', 15000);
    }
    else if (d.type === 'loop_stopped') {
      append('[engine] loop stopped' + (d.exit_code != null ? ' (code ' + d.exit_code + ')' : ''), targetBot);
      refresh();
    }
    else if (d.type === 'paygo_auto_status' && d.status) {
      updatePayGoAutoUI(d.status);
    }
  }

  function boot() {
    root = $('tg-classic-root');
    if (!root) return;
    shell(); setWindow(false); setAddEmail(true); mtWire(); mtLoadCreds(); refresh();
    try {
      if (!window.__tgEs) {
        window.__tgEs = new EventSource('/api/meta-insta/events');
        window.__tgEs.onmessage = function (ev) {
          try {
            var d = JSON.parse(ev.data);
            if (d && d.type === 'batch' && Array.isArray(d.items)) {
              for (var i = 0; i < d.items.length; i++) {
                try { handleTgEvent(d.items[i]); } catch (e) {}
              }
              return;
            }
            handleTgEvent(d);
          } catch (e) {}
        };
      }
    } catch (e) {}
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 5000);
    if (!window.__tgTick) window.__tgTick = setInterval(tickTimer, 1000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
