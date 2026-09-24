/**
 * Meta Creator — License Activation Client & Security Gate (public/js/nova-license.js)
 * Interacts with server /api/license/* endpoints and Cloudflare Workers D1 authority.
 */

window.isSoftwareLicensed = false;

async function licenseFetch(apiPath, opts = {}) {
  const curPort = Number(window.location.port || '3070');
  const ports = [curPort, 3070, 3050, 3000];
  const uniquePorts = [...new Set(ports.filter(Boolean))];
  const attempts = [apiPath];
  for (const pt of uniquePorts) {
    if (pt !== curPort) attempts.push(`http://127.0.0.1:${pt}${apiPath}`);
  }

  let lastErr = null;
  let firstRes = null;
  for (const url of attempts) {
    try {
      const res = await fetch(url, opts);
      if (!firstRes) firstRes = { res, url };
      if (res.ok || res.status === 400 || res.status === 403) {
        return { res, url };
      }
      lastErr = new Error(`HTTP ${res.status} from ${url}`);
    } catch (e) {
      lastErr = e;
    }
  }
  if (firstRes) return firstRes;
  const err = new Error(`Could not reach Meta Creator backend. Server offline or unreachable.`);
  err.cause = lastErr;
  throw err;
}

function setLicenseAlertBox(msg, type = 'none') {
  const box = document.getElementById('license-alert-box');
  if (!box) return;
  if (type === 'none' || !msg) {
    box.style.display = 'none';
    box.innerHTML = '';
    return;
  }
  box.style.display = 'block';
  if (type === 'error') {
    box.style.background = 'rgba(239, 68, 68, 0.15)';
    box.style.border = '1px solid rgba(239, 68, 68, 0.35)';
    box.style.color = '#fca5a5';
    box.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${escapeLicenseHtml(msg)}`;
  } else if (type === 'warning') {
    box.style.background = 'rgba(245, 158, 11, 0.15)';
    box.style.border = '1px solid rgba(245, 158, 11, 0.35)';
    box.style.color = '#fcd34d';
    box.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${escapeLicenseHtml(msg)}`;
  } else if (type === 'success') {
    box.style.background = 'rgba(16, 185, 129, 0.15)';
    box.style.border = '1px solid rgba(16, 185, 129, 0.35)';
    box.style.color = '#6ee7b7';
    box.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${escapeLicenseHtml(msg)}`;
  }
}

function escapeLicenseHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function openLicenseModal() {
  const modal = document.getElementById('modal-license-activation');
  if (modal) {
    if (typeof openModal === 'function') {
      openModal(modal);
    } else {
      modal.classList.add('active');
      modal.style.display = 'flex';
    }
    const input = document.getElementById('license-key-input');
    if (input) setTimeout(() => input.focus(), 100);
  }
}

function closeLicenseModal() {
  const modal = document.getElementById('modal-license-activation');
  if (modal) {
    if (typeof closeModal === 'function') {
      closeModal(modal);
    } else {
      modal.classList.remove('active');
      modal.style.display = 'none';
    }
  }
}

// Global License Guard
window.novaRequireLicense = function(message = '') {
  if (window.isSoftwareLicensed) {
    return true;
  }
  const alertMsg = message || 'Active license key required to execute this operation.';
  if (typeof showToast === 'function') {
    showToast(alertMsg, 'error');
  }
  setLicenseAlertBox(alertMsg, 'error');
  openLicenseModal();
  return false;
};

async function checkLicenseStatusOnLoad() {
  const hwidModal = document.getElementById('license-hwid-display-modal');
  const subStatus = document.getElementById('sidebar-sub-status');
  const userPlan = document.getElementById('sidebar-user-plan');
  const userExpiry = document.getElementById('sidebar-user-expiry');
  const sidebarBtn = document.getElementById('sidebar-license-btn');
  const navLicense = document.getElementById('nav-item-license');
  const btnActivate = document.getElementById('btn-activate-license');
  const keyInput = document.getElementById('license-key-input');
  const btnCopyHwid = document.getElementById('btn-copy-hwid');

  // Bind Sidebar clicks to open Activation Modal
  if (sidebarBtn && !sidebarBtn.dataset.licBound) {
    sidebarBtn.dataset.licBound = 'true';
    sidebarBtn.style.cursor = 'pointer';
    sidebarBtn.addEventListener('click', openLicenseModal);
  }
  if (navLicense && !navLicense.dataset.licBound) {
    navLicense.dataset.licBound = 'true';
    navLicense.style.cursor = 'pointer';
    navLicense.addEventListener('click', openLicenseModal);
  }

  // Bind Activation Button and Enter key
  if (btnActivate && !btnActivate.dataset.licBound) {
    btnActivate.dataset.licBound = 'true';
    btnActivate.addEventListener('click', handleActivateLicenseSubmit);
  }
  if (keyInput && !keyInput.dataset.licBound) {
    keyInput.dataset.licBound = 'true';
    keyInput.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') handleActivateLicenseSubmit();
    });
  }

  // Bind 1-click HWID copy button
  if (btnCopyHwid && !btnCopyHwid.dataset.licBound) {
    btnCopyHwid.dataset.licBound = 'true';
    btnCopyHwid.addEventListener('click', () => {
      const hwidText = hwidModal ? hwidModal.innerText.trim() : '';
      if (hwidText && hwidText !== 'Detecting...') {
        navigator.clipboard.writeText(hwidText).then(() => {
          if (typeof showToast === 'function') showToast('HWID copied to clipboard!', 'success');
        }).catch(() => {});
      }
    });
  }

  try {
    const { res } = await licenseFetch('/api/license/status');
    const data = await res.json();

    if (data && data.hwid && hwidModal) {
      hwidModal.innerText = data.hwid;
    }

    // Developer Override Mode
    if (data && data.devMode === true) {
      window.isSoftwareLicensed = true;
      closeLicenseModal();
      if (subStatus) {
        subStatus.textContent = 'DEV MODE';
        subStatus.style.background = 'rgba(99, 102, 241, 0.15)';
        subStatus.style.color = '#a5b4fc';
      }
      if (userPlan) userPlan.textContent = 'Dev Override';
      if (userExpiry) userExpiry.textContent = 'Active (Source run)';
      return;
    }

    if (data && data.isValid && data.license) {
      window.isSoftwareLicensed = true;
      closeLicenseModal();

      const lic = data.license;
      const type = (lic.license_type || 'MONTHLY').toUpperCase();
      const isLifetime = type === 'LIFETIME' || !lic.expires_at || lic.expires_at === 'LIFETIME' || lic.expires_at === 'NEVER';
      const expDate = lic.expires_at ? new Date(lic.expires_at) : null;
      const remDays = expDate ? Math.max(0, Math.ceil((expDate - new Date()) / (1000 * 60 * 60 * 24))) : 0;

      if (subStatus) {
        subStatus.textContent = data.isOfflineGrace ? 'OFFLINE GRACE' : 'ACTIVE';
        subStatus.style.background = data.isOfflineGrace ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)';
        subStatus.style.color = data.isOfflineGrace ? '#fcd34d' : '#34d399';
      }
      if (userPlan) {
        userPlan.textContent = isLifetime ? 'Lifetime License' : `${type} Plan`;
        userPlan.style.color = '#4ade80';
      }
      if (userExpiry) {
        userExpiry.textContent = isLifetime ? 'Never Expires' : `${remDays} days remaining`;
      }
      setLicenseAlertBox('', 'none');
    } else {
      window.isSoftwareLicensed = false;
      const statusText = (data && data.status) ? data.status : 'UNLICENSED';

      if (subStatus) {
        subStatus.textContent = statusText;
        subStatus.style.background = 'rgba(239, 68, 68, 0.15)';
        subStatus.style.color = '#f87171';
      }
      if (userPlan) {
        userPlan.textContent = 'No Active Plan';
        userPlan.style.color = '#f87171';
      }
      if (userExpiry) {
        userExpiry.textContent = 'Click to activate';
      }

      if (statusText === 'EXPIRED' || statusText === 'REVOKED' || statusText === 'HWID_MISMATCH') {
        setLicenseAlertBox(data.message || `License error: ${statusText}`, 'error');
        openLicenseModal();
      } else {
        setLicenseAlertBox('', 'none');
      }
    }
  } catch (e) {
    console.warn('[License Manager] Initial check error:', e.message);
  }
}

async function handleActivateLicenseSubmit() {
  const keyInput = document.getElementById('license-key-input');
  const btnActivate = document.getElementById('btn-activate-license');
  const key = (keyInput ? keyInput.value : '').trim();

  if (!key) {
    const err = 'Please enter a valid license key.';
    setLicenseAlertBox(err, 'error');
    if (typeof showToast === 'function') showToast(err, 'error');
    return;
  }

  if (btnActivate) {
    btnActivate.disabled = true;
    btnActivate.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Activating License...';
  }

  try {
    const { res } = await licenseFetch('/api/license/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ licenseKey: key })
    });
    const data = await res.json();

    if (data && data.isValid) {
      window.isSoftwareLicensed = true;
      closeLicenseModal();
      setLicenseAlertBox('', 'none');
      if (typeof showToast === 'function') showToast('License activated successfully!', 'success');
      await checkLicenseStatusOnLoad();
    } else {
      window.isSoftwareLicensed = false;
      const msg = (data && data.message) || 'Invalid, expired, or revoked license key.';
      setLicenseAlertBox(msg, 'error');
      if (typeof showToast === 'function') showToast(msg, 'error');
    }
  } catch (err) {
    const errMsg = 'Error connecting to license server: ' + err.message;
    setLicenseAlertBox(errMsg, 'error');
    if (typeof showToast === 'function') showToast(errMsg, 'error');
  } finally {
    if (btnActivate) {
      btnActivate.disabled = false;
      btnActivate.innerHTML = '<i class="fa-solid fa-shield-check"></i> Activate License';
    }
  }
}

// Auto-run on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    checkLicenseStatusOnLoad();
  }, 100);
});
