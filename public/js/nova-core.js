/** Nova Browser UI — Core helpers, theme navigation, modals, toasts. */

const $ = (id) => document.getElementById(id);

/** License gate: delegates to authoritative nova-license.js */
function requireLicense(message = '') {
  if (typeof window.novaRequireLicense === 'function') {
    return window.novaRequireLicense(message);
  }
  return Boolean(window.isSoftwareLicensed);
}

function openModal(modal) {
  if (modal) {
    modal.classList.add('active');
    modal.style.display = 'flex';
  }
}

function closeModal(modal) {
  if (modal) {
    modal.classList.remove('active');
    modal.style.display = 'none';
  }
}

function escapeHtml(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Shared debounce helper (used by filter/search inputs across Nova views). */
function debounce(fn, wait = 200) {
  let timer = null;
  return function (...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, wait);
  };
}

function showToast(message, type = 'info') {
  if (type === 'danger') type = 'error';
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type} toast-${type}`;
  let icon = 'fa-circle-info';
  if (type === 'success') icon = 'fa-circle-check';
  if (type === 'error') icon = 'fa-triangle-exclamation';
  toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

function initTheme() {
  const savedTheme = localStorage.getItem('nova_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);
}

function updateThemeIcon(theme) {
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  if (btnThemeToggle) {
    btnThemeToggle.innerHTML = theme === 'light'
      ? '<i class="fa-solid fa-sun" style="color: #f59e0b;"></i>'
      : '<i class="fa-solid fa-moon" style="color: #94a3b8;"></i>';
    btnThemeToggle.title = theme === 'light' ? 'Switch to Dark Theme' : 'Switch to Light Theme';
  }
}

function initThemeNav() {
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('nova_theme', next);
      updateThemeIcon(next);
    });
  }

  // Hash routing: every page has its own route, so each TG bot is a
  // separate deep-linkable page (back/forward + refresh keep their place).
  //   #/meta  #/ig  #/tg/taskly  #/tg/paygo  #/tg/fastpay  #/manager  #/guide
  const VIEW_ROUTES = {
    'view-meta-creator': '#/meta',
    'view-ig-creator': '#/ig',
    'view-ig-checker': '#/igcheck',
    'view-tg-manager': '#/manager',
    'view-guide': '#/guide',
    'view-tg-taskly2fa': '#/taskly2fa',
    'view-tg-tasklycookie': '#/tasklycookie',
    'view-tg-fastpay2fa': '#/fastpay2fa',
    'view-tg-paygopool': '#/paygopool',
    'view-tg-paygocookie': '#/paygocookie',
    'view-tg-paygo2fa': '#/paygo2fa',
  };

  function routeForItem(item) {
    const bot = item.getAttribute('data-bot');
    if (bot) return '#/tg/' + bot;
    return VIEW_ROUTES[item.getAttribute('data-view')] || '#/meta';
  }

  function showView(viewId, bot) {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    let item = null;
    if (bot) {
      item = document.querySelector('.nav-item[data-view="' + viewId + '"][data-bot="' + bot + '"]');
    }
    if (!item) item = document.querySelector('.nav-item[data-view="' + viewId + '"]');
    if (item) item.classList.add('active');
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    const targetPanel = document.getElementById(viewId);
    if (targetPanel) targetPanel.classList.add('active');
    // TG submenu: the page IS the bot (no picker).
    if (bot && typeof window.__setTgBot === 'function') window.__setTgBot(bot);
    try {
      window.dispatchEvent(new CustomEvent('nova:view-changed', { detail: { viewId, bot } }));
    } catch (e) {}
  }

  function applyHash() {
    const h = (window.location.hash || '').toLowerCase();
    const m = h.match(/^#\/tg\/([a-z]+)/);
    if (m) {
      const bot = m[1];
      if (document.querySelector('.nav-item[data-view="view-tg-classic"][data-bot="' + bot + '"]')) {
        showView('view-tg-classic', bot);
        return;
      }
    }
    for (const [viewId, route] of Object.entries(VIEW_ROUTES)) {
      if (h === route.toLowerCase()) {
        showView(viewId, null);
        return;
      }
    }
    // Unknown/empty hash → default route (replace: no history spam).
    if (h !== '#/meta') window.location.replace('#/meta');
    else showView('view-meta-creator', null);
  }

  // Sidebar View Switcher (route-driven)
  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      const route = routeForItem(item);
      if (window.location.hash === route) applyHash();
      else window.location.hash = route;
    });
  });
  window.addEventListener('hashchange', applyHash);

  // Collapsible TG bot submenu (parent toggles the bot list)
  const tgToggle = document.getElementById('nav-tg-toggle');
  const tgSub = document.getElementById('tg-submenu');
  if (tgToggle && tgSub) {
    tgToggle.addEventListener('click', () => {
      const collapsed = tgSub.classList.toggle('collapsed');
      tgToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });
  }

  // Guide page → back to TG Classic (route-driven so history stays coherent)
  const guideBack = document.getElementById('guide-back-tg');
  if (guideBack) {
    guideBack.addEventListener('click', () => {
      window.location.hash = '#/tg/taskly';
    });
  }
  // Deep-link on load: refresh keeps the current page/bot.
  applyHash();
}

function initModalDismiss() {
  // Close Modals (by [data-close], .modal-close, or clicking the backdrop overlay)
  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modalId = e.currentTarget.getAttribute('data-close');
      const targetModal = document.getElementById(modalId) || e.currentTarget.closest('.modal-overlay');
      if (targetModal) closeModal(targetModal);
    });
  });

  document.querySelectorAll('.modal-close, .close-modal').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modal = e.currentTarget.closest('.modal-overlay');
      if (modal) closeModal(modal);
    });
  });

  // Close modal when clicking outside modal box on overlay backdrop
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay);
      }
    });
  });

  // Close modal with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => closeModal(m));
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initThemeNav();
  initModalDismiss();

  fetch('/api/build-mode')
    .then(r => r.json())
    .then(data => {
      if (data && data.meta_only) {
        document.body.classList.add('meta-only-mode');
        if (window.location.hash !== '#/meta') {
          window.location.replace('#/meta');
        }
      } else if (data && Array.isArray(data.modules)) {
        const mods = data.modules;
        if (!mods.includes('ig')) {
          const igTab = document.querySelector('button[data-view="view-ig-creator"]');
          if (igTab) igTab.style.display = 'none';
          const igCheckTab = document.querySelector('button[data-view="view-ig-checker"]');
          if (igCheckTab) igCheckTab.style.display = 'none';
        }
        if (!mods.includes('tg')) {
          const tgToggle = document.getElementById('nav-tg-toggle');
          const tgSub = document.getElementById('tg-submenu');
          const tgmTab = document.querySelector('button[data-view="view-tg-manager"]');
          const guideTab = document.querySelector('button[data-view="view-guide"]');
          if (tgToggle) tgToggle.style.display = 'none';
          if (tgSub) tgSub.style.display = 'none';
          if (tgmTab) tgmTab.style.display = 'none';
          if (guideTab) guideTab.style.display = 'none';
        }
      }
    })
    .catch(() => {});

  if (typeof initMetaInsta === 'function') {
    try {
      initMetaInsta();
    } catch (e) {
      console.error('[initMetaInsta error]', e);
    }
  }

  if (typeof initIgChecker === 'function') {
    try {
      initIgChecker();
    } catch (e) {
      console.error('[initIgChecker error]', e);
    }
  }
});

/* Shared TG task-availability preflight: asks GET /api/tg/task-availability
   (single-lease probe, never presses Start). Resolves {proceed, probe}.
   Fail-OPEN: hidden/busy/error probes proceed — a single-account "hidden"
   is flaky (slow menu, stale lease) and the server gate + the mid-run
   all-slots gate still decide. Only soldout/unoffered/flood refuse here.
   `say` logs lines into the panel log. */
window.__tgTaskCheck = function (bot, task, say) {
  say = (typeof say === 'function') ? say : function () {};
  var ctrl = null, timer = null;
  try {
    if (typeof AbortController !== 'undefined') {
      ctrl = new AbortController();
      timer = setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, 85000);
    }
  } catch (e) {}
  var opts = { cache: 'no-store' };
  if (ctrl) opts.signal = ctrl.signal;
  say('> availability probe: ' + bot + ' / ' + task + ' ...');
  return fetch('/api/tg/task-availability?bot=' + encodeURIComponent(bot || '') + '&task=' + encodeURIComponent(task || ''), opts)
    .then(function (r) { return r.json(); })
    .then(function (j) {
      if (timer) clearTimeout(timer);
      if (j && j.ok && j.available === false && (j.reason || 'hidden') !== 'hidden') {
        say('! task unavailable (' + (j.reason || 'hidden') + ') — start refused');
        return { proceed: false, probe: j };
      }
      if (j && j.ok && j.available === false) say('< probe says hidden on one account — proceeding (fleet gate decides)');
      else if (j && j.ok) say('< task available (' + (j.reason || 'ok') + ')');
      else say('< probe inconclusive — proceeding (server gate decides)');
      return { proceed: true, probe: j };
    })
    .catch(function (e) {
      if (timer) clearTimeout(timer);
      say('< probe inconclusive (' + e + ') — proceeding');
      return { proceed: true, probe: null };
    });
};

/* Shared SSE hub: exactly ONE EventSource per page. Each panel script used to
   open its own stream (7 total), exceeding Chrome's 6-connections-per-host
   limit and starving every fetch/XHR — all status/reasons/logs/activate calls
   sat at "(pending)" with 0 bytes. Panels subscribe their single-event
   handler here; batch envelopes are unwrapped centrally. */
(function () {
  var subs = [];
  var es = null;
  function ensure() {
    if (es && es.readyState !== 2) return es; // 2 = CLOSED; otherwise reuse
    try { if (es) es.close(); } catch (e) {}
    es = new EventSource('/api/meta-insta/events');
    es.onmessage = function (ev) {
      var d = null;
      try { d = JSON.parse(ev.data); } catch (e) { return; }
      var items = (d && d.type === 'batch' && Array.isArray(d.items)) ? d.items : [d];
      for (var i = 0; i < subs.length; i++) {
        for (var j = 0; j < items.length; j++) {
          try { subs[i](items[j]); } catch (e) {}
        }
      }
    };
    es.onerror = function () {}; // silent like the panels were; browser auto-retries
    return es;
  }
  window.__novaEsSubscribe = function (fn) {
    if (typeof fn !== 'function') return function () {};
    subs.push(fn);
    try { ensure(); } catch (e) {}
    return function () {
      var k = subs.indexOf(fn);
      if (k !== -1) subs.splice(k, 1);
    };
  };
})();
