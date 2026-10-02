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
    'view-tg-manager': '#/manager',
    'view-guide': '#/guide',
    'view-tg-taskly2fa': '#/taskly2fa',
    'view-tg-fastpay2fa': '#/fastpay2fa',
    'view-tg-paygopool': '#/paygopool',
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

  if (typeof initMetaInsta === 'function') {
    try {
      initMetaInsta();
    } catch (e) {
      console.error('[initMetaInsta error]', e);
    }
  }
});
