/**
 * Nova Browser UI — Mr Follower.
 * Gives the oldest IG-list accounts their 5 follows (API / browser / API-then-browser) and
 * returns them to the list. Drives follow_maker.py through /api/followmaker/*.
 * Same visual language as the cookie panels: KPI cards, status banner, settings, auto card, console.
 */
function initFollowMaker() {
  var root = document.getElementById('fm-root');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var KEY = 'fm-config-v2';
  var lastLogT = 0;
  var startedAt = 0;
  var running = false;
  var busy = false;
  var stopping = false;

  function card(label, id, sub, color) {
    return '<div class="insta-stat-card" style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:12px;padding:14px;">' +
      '<div class="insta-stat-label" style="color:var(--text-dim);">' + label + '</div>' +
      '<div class="insta-stat-value" id="' + id + '" style="color:' + (color || 'var(--text-main)') + ';">0</div>' +
      '<div class="insta-stat-sub" style="color:var(--text-muted);">' + sub + '</div></div>';
  }
  function field(label, inner, title) {
    return '<div class="creator-field"' + (title ? ' title="' + title + '"' : '') + '><label>' + label + '</label>' + inner + '</div>';
  }
  function sw(label, id, checked, title) {
    return '<div class="creator-field creator-field--switch"><label>' + label + '</label>' +
      '<label class="switch" title="' + title + '"><input type="checkbox" id="' + id + '"' + (checked ? ' checked' : '') + '><span class="slider"></span></label></div>';
  }

  root.innerHTML =
    '<div class="page-title-box"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;">' +
      '<div><h2><i class="fa-solid fa-user-plus" style="color:#f472b6;"></i> Mr Follower</h2>' +
      '<p>Takes the oldest IG-list accounts that still owe follows, gives each its 5 follows and puts it back in the list marked as having 5 follows. While it works on an account, nothing else can use it.</p></div>' +
      '<span class="tg-bot-badge"><i class="fa-solid fa-user-plus" style="color:#f472b6;"></i> IG list · 5 follows</span>' +
    '</div></div>' +

    '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;">' +
      card('NEEDS FOLLOWS', 'fm-k-wait', 'in the IG list, old enough', '#a5b4fc') +
      card('FOLLOWING NOW', 'fm-k-busy', 'locked while being followed', '#38bdf8') +
      card('HAS 5 FOLLOWS', 'fm-k-done', 'ready for the drains', '#4ade80') +
      card('THIS RUN', 'fm-k-run', '0 follows made', '#f0abfc') +
      card('NEXT ACCOUNT IN', 'fm-k-next', 'until one is old enough', '#fbbf24') +
    '</div>' +

    '<div style="margin-top:.9rem;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem;' +
      'background:linear-gradient(180deg,#111726,#0d1117);border:1px solid var(--border-color);border-radius:12px;padding:14px 16px;">' +
      '<div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">' +
        '<span id="fm-badge" style="padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;background:#1e293b;color:#94a3b8;border:1px solid #334155;">IDLE</span>' +
        '<span id="fm-title" style="font-weight:700;color:var(--text-main);font-size:.95rem;">MR FOLLOWER STOPPED</span>' +
        '<span id="fm-sub" style="font-size:.78rem;color:var(--text-muted);border-left:1px solid var(--border-color);padding-left:.75rem;">Ready.</span>' +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:1rem;">' +
        '<div style="text-align:right;"><div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-weight:600;">Execution Time</div>' +
        '<div id="fm-timer" style="font-size:1rem;font-weight:700;font-family:var(--font-mono);color:var(--text-main);">00:00:00</div></div>' +
        '<button id="fm-start" type="button" class="btn btn-primary"><i class="fa-solid fa-play"></i> Start</button>' +
        '<button id="fm-stop" type="button" class="btn btn-danger" style="display:none;"><i class="fa-solid fa-stop"></i> Stop</button>' +
      '</div>' +
    '</div>' +

    '<div class="card-panel creator-panel" style="margin-top:1rem;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.9rem;">' +
        '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-sliders" style="color:#f472b6;"></i> Settings</h3></div>' +
      '<div class="creator-grid">' +
        field('Follow method',
          '<select id="fm-mode" class="form-control"><option value="auto">API, then browser</option><option value="api">API only</option><option value="browser">Browser only</option></select>',
          'API = fast private-API follow. Browser = real browser with the stored cookies. API, then browser = API first, browser only for what is still missing.') +
        field('Parallel', '<input id="fm-creators" class="form-control" type="number" min="1" max="20" value="2" title="Accounts followed at the same time.">') +
        field('Target (0 = ∞)', '<input id="fm-limit" class="form-control" type="number" min="0" value="0" title="Stop after this many accounts.">') +
        field('Follows per account', '<input id="fm-follows" class="form-control" type="number" min="1" max="20" value="5">') +
        field('Only older than (min)', '<input id="fm-minage" class="form-control" type="number" min="0" value="10" title="Accounts younger than this are left alone.">') +
        field('Skip older than (min, 0 = off)', '<input id="fm-maxage" class="form-control" type="number" min="0" value="0" title="Accounts older than this are left alone (IG suspends old ones).">') +
      '</div>' +
      '<div class="creator-service-note" style="margin-top:.6rem;"><i class="fa-solid fa-circle-info" style="color:#f472b6;"></i> ' +
        'Oldest account first. A finished account returns to the IG list with its follow count; a failed one is retried later and dropped after 3 tries.</div>' +
    '</div>' +

    '<div class="card-panel" style="margin-top:1rem;">' +
      '<div class="paygo-feature-card paygo-feature-automine" style="flex-direction:column;align-items:stretch;">' +
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:1.25rem;width:100%;">' +
          '<div class="paygo-feature-main"><div class="paygo-feature-icon"><i class="fa-solid fa-rotate"></i></div>' +
            '<div class="paygo-feature-text"><div class="paygo-feature-title">AUTO-FOLLOW<span class="paygo-feature-badge automine-badge">Runs continuously</span></div>' +
            '<div class="paygo-feature-desc">While on, Mr Follower keeps running: when no account is old enough yet it waits, checks again at the interval below, and follows each new account as soon as it passes the minimum age. Off = it stops when nothing is left.</div></div></div>' +
          '<div class="paygo-feature-controls"><span id="fm-auto-pill" class="paygo-status-pill">Auto Off</span>' +
            '<label class="switch" title="Run continuously and wait for accounts"><input type="checkbox" id="fm-auto"><span class="slider"></span></label></div>' +
        '</div>' +
        '<div class="paygo-automine-config"><div class="paygo-automine-slots"><span><i class="fa-solid fa-stopwatch" style="color:var(--accent-cyan);"></i> Check every (s):</span>' +
          '<input id="fm-interval" class="form-control paygo-conc-input" type="number" min="5" max="3600" value="30"></div>' +
          '<div class="paygo-automine-explainer"><i class="fa-solid fa-circle-info"></i><span id="fm-auto-state">Turn on and press Start, or flip the switch while running to restart in auto mode.</span></div></div>' +
      '</div>' +
    '</div>' +

    '<div class="card-panel" style="margin-top:1rem;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem;">' +
        '<h3 class="panel-header" style="margin:0;"><i class="fa-solid fa-terminal"></i> Console</h3>' +
        '<div style="display:flex;gap:.5rem;align-items:center;">' +
          '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--text-dim);"><input type="checkbox" id="fm-autoscroll" checked> Auto-scroll</label>' +
          '<button id="fm-copy" type="button" class="btn btn-secondary btn-sm">Copy Log</button>' +
          '<button id="fm-clear" type="button" class="btn btn-secondary btn-sm">Clear Log</button></div></div>' +
      '<div id="fm-log" class="log-container" style="height:300px;overflow-y:auto;background:#060910;border:1px solid var(--border-color);border-radius:8px;padding:.75rem;font-family:var(--font-mono);font-size:.78rem;white-space:pre-wrap;"></div>' +
    '</div>';

  function cfg() {
    return {
      mode: $('fm-mode').value,
      creators: Number($('fm-creators').value) || 1,
      limit: Number($('fm-limit').value) || 0,
      follows: Number($('fm-follows').value) || 5,
      min_age_min: Number($('fm-minage').value) || 0,
      max_age_min: Number($('fm-maxage').value) || 0,
      auto: $('fm-auto').checked,
      interval: Number($('fm-interval').value) || 30,
      on_fail: 'dead',
      visible: false,
    };
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(cfg())); } catch (e) { /* ignore */ } }
  try {
    var sv = JSON.parse(localStorage.getItem(KEY) || '{}');
    if (sv.mode) $('fm-mode').value = sv.mode;
    ['creators', 'limit', 'follows', 'interval'].forEach(function (k) { if (sv[k] !== undefined) $('fm-' + k).value = sv[k]; });
    if (sv.min_age_min !== undefined) $('fm-minage').value = sv.min_age_min;
    if (sv.max_age_min !== undefined) $('fm-maxage').value = sv.max_age_min;
    if (sv.auto) $('fm-auto').checked = true;
  } catch (e) { /* storage unavailable */ }

  function fmtWait(sec) {
    sec = Math.max(0, parseInt(sec || 0, 10));
    var m = Math.floor(sec / 60), s = sec % 60;
    return m + 'm ' + (s < 10 ? '0' + s : s) + 's';
  }
  function two(n) { return n < 10 ? '0' + n : '' + n; }

  function esc(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function lineColor(m) {
    if (/dead|error|failed|only \d/i.test(m)) return '#f87171';
    if (/has \d+\/\d+ follows|back in the IG list/i.test(m)) return '#4ade80';
    if (/waiting|checking again/i.test(m)) return '#fbbf24';
    return '#cbd5e1';
  }

  function render(d) {
    var s = d.stats || {};
    running = !!d.running;
    startedAt = d.startedAt || 0;
    $('fm-k-wait').textContent = s.waiting != null ? s.waiting : 0;
    $('fm-k-busy').textContent = s.in_progress != null ? s.in_progress : 0;
    $('fm-k-done').textContent = s.done != null ? s.done : 0;
    $('fm-k-run').textContent = (s.ok || 0) + ' ok / ' + ((s.failed || 0) + (s.partial || 0) + (s.dead || 0)) + ' failed';
    $('fm-k-run').nextElementSibling.textContent = (s.follows || 0) + ' follows made';
    $('fm-k-next').textContent = s.next_eligible_s != null ? fmtWait(s.next_eligible_s) : '—';

    var badge = $('fm-badge');
    if (running) {
      badge.textContent = d.config && d.config.auto ? 'AUTO' : 'RUNNING';
      badge.style.cssText += ';background:rgba(16,185,129,.18);color:#34d399;border-color:rgba(16,185,129,.4);';
      $('fm-title').textContent = 'MR FOLLOWER RUNNING';
      var c = d.config || {};
      $('fm-sub').textContent = (c.creators || 1) + ' parallel · ' + ({ api: 'API only', browser: 'Browser only', auto: 'API, then browser' }[c.mode] || '') +
        ' · older than ' + (c.min_age_min || 0) + ' min';
    } else {
      badge.textContent = 'IDLE';
      badge.style.cssText += ';background:#1e293b;color:#94a3b8;border-color:#334155;';
      $('fm-title').textContent = 'MR FOLLOWER STOPPED';
      $('fm-sub').textContent = 'Ready.';
    }
    if (!running) stopping = false;
    $('fm-start').style.display = running ? 'none' : '';
    $('fm-stop').style.display = running ? '' : 'none';
    $('fm-stop').innerHTML = stopping
      ? '<i class="fa-solid fa-skull-crossbones"></i> Force stop'
      : '<i class="fa-solid fa-stop"></i> Stop';
    $('fm-stop').title = stopping
      ? 'Kill the runner now. Accounts being followed are returned to the list.'
      : 'Finish the accounts being followed, then stop.';
    var pill = $('fm-auto-pill');
    var autoOn = running && d.config && d.config.auto;
    pill.textContent = autoOn ? 'Auto On' : 'Auto Off';
    pill.style.color = autoOn ? '#34d399' : '';
    if (running && d.config && !busy && !stopping) { $('fm-auto').checked = !!d.config.auto; }
    $('fm-auto-state').textContent = autoOn
      ? (s.next_eligible_s != null ? 'Waiting — next account is old enough in ' + fmtWait(s.next_eligible_s) + '.' : 'Checking for accounts that are old enough.')
      : 'Turn on and press Start, or flip the switch while running to restart in auto mode.';

    var box = $('fm-log');
    var fresh = (d.logs || []).filter(function (l) { return l.t > lastLogT; });
    if (fresh.length) {
      var stick = $('fm-autoscroll').checked;
      fresh.forEach(function (l) {
        var div = document.createElement('div');
        div.style.color = lineColor(l.m);
        div.textContent = new Date(l.t).toLocaleTimeString() + '  ' + l.m;
        box.appendChild(div);
        lastLogT = Math.max(lastLogT, l.t);
      });
      while (box.childNodes.length > 600) box.removeChild(box.firstChild);
      if (stick) box.scrollTop = box.scrollHeight;
    }
  }

  function poll() {
    fetch('/api/followmaker/status', { cache: 'no-store' })
      .then(function (r) { return r.json(); }).then(render).catch(function () { /* restarting */ });
  }

  function post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); });
  }
  function start() {
    if (busy) return Promise.resolve();
    busy = true;
    save();
    return post('/api/followmaker/start', cfg()).then(function (d) {
      if (d.status !== 'SUCCESS') $('fm-sub').textContent = d.error || 'Could not start.';
      lastLogT = 0; $('fm-log').innerHTML = '';
      poll();
    }).then(function () { busy = false; }, function () { busy = false; });
  }
  function stop(force) {
    stopping = true;
    $('fm-sub').textContent = force ? 'Force stopping…'
      : 'Stopping — the accounts being followed finish first (click Force stop to kill now).';
    $('fm-stop').innerHTML = '<i class="fa-solid fa-skull-crossbones"></i> Force stop';
    return post('/api/followmaker/stop', { force: !!force }).then(poll);
  }
  function waitStopped(msLeft) {
    return fetch('/api/followmaker/status', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.running || msLeft <= 0) return d;
      return new Promise(function (res) { setTimeout(res, 1500); }).then(function () { return waitStopped(msLeft - 1500); });
    });
  }

  $('fm-start').addEventListener('click', start);
  $('fm-stop').addEventListener('click', function () { stop(stopping); });
  // Flipping Auto does what it says: ON starts continuous mode, OFF stops it.
  $('fm-auto').addEventListener('change', function () {
    save();
    var on = $('fm-auto').checked;
    if (on && !running) { start(); return; }
    if (!on && running) { stop(false); return; }
    if (on && running) {                        // running without auto: restart in auto mode
      busy = true;
      stop(false).then(function () { return waitStopped(120000); }).then(function () {
        busy = false; stopping = false; return start();
      });
    }
  });
  ['fm-mode', 'fm-creators', 'fm-limit', 'fm-follows', 'fm-minage', 'fm-maxage', 'fm-interval']
    .forEach(function (id) { $(id).addEventListener('change', save); });
  $('fm-copy').addEventListener('click', function () {
    var t = Array.prototype.map.call($('fm-log').childNodes, function (n) { return n.textContent; }).join('\n');
    if (navigator.clipboard) navigator.clipboard.writeText(t);
  });
  $('fm-clear').addEventListener('click', function () { $('fm-log').innerHTML = ''; });

  setInterval(function () {
    if (running && startedAt) {
      var sec = Math.floor((Date.now() - startedAt) / 1000);
      $('fm-timer').textContent = two(Math.floor(sec / 3600)) + ':' + two(Math.floor(sec / 60) % 60) + ':' + two(sec % 60);
    }
  }, 1000);
  setInterval(function () {
    var view = $('view-follow-maker');
    if (running || (view && view.classList.contains('active'))) poll();
  }, 2000);
  poll();
}
