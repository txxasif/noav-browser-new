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

  // Sidebar View Switcher
  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      const viewId = item.getAttribute('data-view');
      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
      const targetPanel = document.getElementById(viewId);
      if (targetPanel) targetPanel.classList.add('active');
    });
  });
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
