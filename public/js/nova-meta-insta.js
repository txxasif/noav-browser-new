/**
 * Nova Browser UI — Meta Creator Workspace.
 *
 * Dedicated Meta & Instagram Account Creation Engine.
 * Supports independent concurrent execution for Meta-only and Meta->IG pipelines.
 */

// =============================================================================
// 1. CONFIGURATION & CONSTANTS
// =============================================================================

const MI_WORKSPACE_DEFS = {
  meta: {
    kind: 'meta',
    mode: 'meta',
    title: 'Meta Account Creator',
    subtitle: 'Create Meta accounts in an anti-detect browser.',
    accent: '#0081fb',
    icon: 'fa-brands fa-meta',
    countLabel: 'Accounts Created',
    countSub: 'Accounts created',
    savedSub: 'JSON + CSV + TXT + Cookies',
    usernameLabel: 'Account username (optional)',
    usernamePlaceholder: 'leave empty = auto',
    startLabel: 'Start Creator',
    flowHint: 'Flow: Meta signup → selfie verify → save credentials (Meta-only, no Instagram join).',
  },
  ig: {
    kind: 'ig',
    mode: 'meta-ig',
    title: 'Instagram Creator',
    subtitle: 'Create Instagram accounts (via Meta signup) in an anti-detect browser.',
    accent: '#f472b6',
    icon: 'fa-brands fa-instagram',
    countLabel: 'Instagram Accounts',
    countSub: 'Instagram accounts created',
    savedSub: 'JSON + CSV + TXT + cookies',
    usernameLabel: 'Instagram username (optional)',
    usernamePlaceholder: 'leave empty = auto',
    startLabel: 'Start Creating Instagram',
    flowHint: 'Flow: Meta signup → verify → join Instagram → save credentials + cookies.',
  },
};

const MI_MAIL_PROVIDERS = [
  { value: 'mailtd', icon: 'fa-solid fa-inbox', color: 'var(--accent-green)', label: 'mail.td', hint: '(only provider)' },
];

const MI_ALL_COLS = ['id', 'uname', 'name', 'email', 'password', 'cookies', 'health', 'created', 'actions'];

// Health pill for one account row. Mirrors ig_backup.is_damaged()
// (Failed/Banned, 'Dead:…' note, or 3+ failed submits) so the list shows
// exactly what "Leave out damaged" will skip.
function miIsDamaged(a) {
  const status = String((a && a.status) || '');
  const extra = String((a && a.extra) || '');
  const deadReason = (a && (a.dead_reason || (a.extra && a.extra.dead_reason))) || '';
  const attempts = parseInt((a && a.attempts) || 0, 10) || 0;
  return status === 'Failed' || status === 'Banned' || extra.indexOf('Dead:') === 0 || Boolean(deadReason) || attempts >= 3;
}

function miHealthBadge(a) {
  const status = String((a && a.status) || '');
  if (miIsDamaged(a)) {
    return '<span class="badge-pill bg-rose" title="Failed / banned / dead session — skipped by “Leave out damaged”">Damaged</span>';
  }
  if (status.indexOf('Submitting') === 0) {
    return '<span class="badge-pill" style="background: rgba(245,158,11,.15); color: #fbbf24;" title="Claimed by a running drain">Busy</span>';
  }
  if (status.indexOf('Submitted') === 0 || (a && (a.tg_submitted || a.nitro_submitted || a.coinsta_submitted))) {
    return '<span class="badge-pill" style="background: rgba(56,189,248,.15); color: #38bdf8;" title="Already submitted to a bot">Used</span>';
  }
  if (status === 'MetaCreated') {
    return '<span class="badge-pill bg-muted" title="Meta-only (no Instagram joined)">Meta</span>';
  }
  return '<span class="badge-pill bg-emerald" title="Healthy">OK</span>';
}

// Minimal CSV parser (quoted commas + escaped quotes) for the import preview.
function miParseCsvPreview(text) {
  const rows = [];
  let cur = [''];
  let inQ = false;
  const s = String(text || '').replace(/^\uFEFF/, '');
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQ) {
      if (c === '"') {
        if (s[i + 1] === '"') { cur[cur.length - 1] += '"'; i++; }
        else inQ = false;
      } else {
        cur[cur.length - 1] += c;
      }
    } else if (c === '"') {
      inQ = true;
    } else if (c === ',') {
      cur.push('');
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++;
      rows.push(cur);
      cur = [''];
    } else {
      cur[cur.length - 1] += c;
    }
  }
  if (cur.length > 1 || (cur.length === 1 && cur[0] !== '')) rows.push(cur);
  if (!rows.length) return { header: [], rows: [] };
  const header = rows[0].map((h) => h.trim());
  return { header, rows: rows.slice(1).filter((r) => r.some((cell) => String(cell).trim() !== '')) };
}

function miRowIsDamaged(header, row) {
  const idx = (name) => header.indexOf(name);
  const at = (name) => {
    const i = idx(name);
    return i === -1 ? '' : String(row[i] == null ? '' : row[i]);
  };
  const status = at('status');
  if (status === 'Failed' || status === 'Banned') return true;
  const attempts = parseInt(at('attempts') || '0', 10) || 0;
  if (attempts >= 3) return true;
  return false;
}

// =============================================================================
// 2. TEMPLATE BUILDERS (HTML GENERATORS)
// =============================================================================

function miMailOptionsHtml(kind) {
  return MI_MAIL_PROVIDERS.map((m, i) => `
    <label class="creator-option">
      <input type="radio" name="mi-mail-${kind}" value="${m.value}" ${i === 0 ? 'checked' : ''}>
      <i class="${m.icon}" style="color: ${m.color};"></i> ${m.label}${m.hint ? ` <span class="creator-option-hint">${m.hint}</span>` : ''}
    </label>`).join('');
}

function miCreatorPanelHtml(def) {
  const k = def.kind;
  const cols = [
    ['id', '# (Index)'], ['uname', 'Username'], ['name', 'Name'], ['email', 'Email'],
    ['password', 'Password'], ['cookies', 'Cookies'], ['health', 'Health'], ['created', 'Created'], ['actions', 'Actions'],
  ];
  const colMenu = cols.map(([col, label]) => `
    <label class="creator-col-option">
      <input type="checkbox" class="metainsta-col-cb" data-col="${col}" checked> ${label}
    </label>`).join('');

  return `
  <div class="page-title-box">
    <div class="page-title-row">
      <div>
        <h2><i class="${def.icon}" style="color: ${def.accent};"></i> ${def.title}</h2>
        <p>${def.subtitle}</p>
      </div>
      <div class="page-title-actions">
        <button type="button" class="btn btn-secondary btn-sm" data-role="export-full" title="Save this list to a CSV file (passwords, cookies, mail sessions, 2FA)"><i class="fa-solid fa-download"></i> Export</button>
        <button type="button" class="btn btn-sm" data-role="import-open" title="Add accounts from a CSV file exported earlier" style="background: transparent; border: 1px solid transparent; color: var(--text-dim);"><i class="fa-solid fa-upload"></i> Import</button>
        ${k === 'ig' ? `<button type="button" class="btn btn-secondary btn-sm" data-role="check-health" title="Live-check saved Instagram accounts now (public profile lookup, no login) — dead ones get flagged Damaged after your OK"><i class="fa-solid fa-heart-pulse" style="color: var(--accent-green);"></i> Check health</button>` : ''}
        ${k === 'ig' ? `<button type="button" class="btn btn-secondary btn-sm" data-role="purge-damaged" title="Delete only the damaged rows (Failed / Banned / dead session / 3+ failed submits) — healthy accounts stay"><i class="fa-solid fa-user-slash" style="color: #f87171;"></i> Remove damaged</button>` : ''}
        <button type="button" class="btn btn-secondary btn-sm" data-role="clear" title="Delete EVERY account in THIS list — saved data is gone (files on disk stay)"><i class="fa-solid fa-trash-can"></i> Clear list</button>
        <button type="button" class="btn btn-secondary btn-sm" data-role="deep-clean" title="Delete orphaned session files, cookies and dead browser profiles from DISK — your saved account list is NOT touched. Stop the engine first."><i class="fa-solid fa-broom"></i> Clean files</button>
      </div>
    </div>
  </div>

  <div class="insta-stats-grid">
    <div class="insta-stat-card">
      <span class="insta-stat-label">${def.countLabel}</span>
      <span class="insta-stat-value" data-role="stat-total">0</span>
      <span class="insta-stat-sub">${def.countSub}</span>
    </div>
    <div class="insta-stat-card">
      <span class="insta-stat-label" style="color: var(--accent-green);">Engine State</span>
      <span class="insta-stat-value" style="color: var(--accent-green);" data-role="stat-running">IDLE</span>
      <span class="insta-stat-sub" data-role="state">IDLE</span>
    </div>
    <div class="insta-stat-card">
      <span class="insta-stat-label" style="color: var(--accent-cyan);">Saved</span>
      <span class="insta-stat-value" style="color: var(--accent-cyan);" data-role="stat-created">0</span>
      <span class="insta-stat-sub">${def.savedSub}</span>
    </div>
  </div>

  <div class="card-panel creator-panel">
    <div class="creator-grid">
      <div class="creator-field">
        <label>Parallel</label>
        <input type="number" class="form-control" data-role="concurrency" min="1" value="1">
      </div>
      <div class="creator-field">
        <label>Target (0 = ∞)</label>
        <input type="number" class="form-control" data-role="target" min="0" value="0">
      </div>
      <div class="creator-field creator-field--switch">
        <label>Headless</label>
        <label class="switch" title="Run browsers headless (no visible window)">
          <input type="checkbox" data-role="headless" checked>
          <span class="slider"></span>
        </label>
      </div>
      ${k === 'ig' ? `
      <div class="creator-field creator-field--switch">
        <label>2FA Key</label>
        <label class="switch" title="Extract and save 2FA secret key for Instagram accounts (disabled by default)">
          <input type="checkbox" data-role="twofa">
          <span class="slider"></span>
        </label>
      </div>
      <div class="creator-field creator-field--switch">
        <label>Follow (5)</label>
        <label class="switch" title="Follow 5 suggested profiles after creating the account (required by the PayGo cookie task). The count is saved on the account, so the PayGo cookie pool drain skips its own follow step for accounts that already followed 5. Off = the follow step is skipped entirely.">
          <input type="checkbox" data-role="follow" checked>
          <span class="slider"></span>
        </label>
      </div>` : ''}
      <div class="creator-field creator-field--wide">
        <label>${def.usernameLabel}</label>
        <input type="text" class="form-control" data-role="username" placeholder="${def.usernamePlaceholder}">
      </div>
    </div>

    <div class="creator-services">
      <div class="creator-service">
        <div class="creator-service-title"><i class="fa-solid fa-envelope" style="color: var(--accent-cyan);"></i> Mail Inbox</div>
        <div class="creator-options">${miMailOptionsHtml(k)}</div>
        <div class="creator-service-note">mail.td is the only enabled mailbox provider.</div>
      </div>

      <div class="creator-service">
        <div class="creator-service-title"><i class="fa-solid fa-shield-halved" style="color: var(--accent-purple);"></i> Captcha Solver</div>
        <div class="creator-options">
          <label class="creator-option" title="Visual challenge solver via in-browser YOLOv5 ONNX AI extension">
            <input type="radio" name="mi-captcha-${k}" value="extension" checked>
            <i class="fa-solid fa-eye" style="color: var(--accent-green);"></i> Visual AI (JA) <span class="creator-option-hint">(YOLOv5 ONNX)</span>
          </label>
        </div>
        <div class="creator-service-note">Visual AI (YOLOv5 ONNX) is the only enabled solver — fast &amp; lightweight.</div>
      </div>
    </div>

    <div data-role="progress-box" style="display: none; margin-top: 1rem;">
      <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.35rem;">
        <span data-role="progress-label" style="color: var(--text-dim);">Creating accounts...</span>
        <span data-role="progress-pct" style="font-weight: 700; color: var(--accent-purple);"></span>
      </div>
      <div class="insta-progress-track">
        <div data-role="progress-bar" class="insta-progress-fill" style="width: 100%;"></div>
      </div>
    </div>

    <div class="creator-actions">
      <button type="button" class="btn btn-primary" data-role="start"><i class="fa-solid fa-play"></i> ${def.startLabel}</button>
      <button type="button" class="btn btn-danger" data-role="stop" style="display: none;"><i class="fa-solid fa-stop"></i> Stop</button>
      <span data-role="engine-hint" class="creator-hint" style="display: none; color: #f87171;">Mining engine not installed on this machine.</span>
      <span class="creator-hint">${def.flowHint}</span>
    </div>
  </div>

  <div class="card-panel" style="margin-top: 1.25rem;">
    <div class="insta-results-header">
      <div class="insta-tab-row">
        <button type="button" class="insta-tab active">
          <span>Created Accounts</span>
          <span class="badge-pill bg-muted" data-role="badge-all">0</span>
        </button>
      </div>
      <div class="creator-results-tools">
        <div class="creator-sort">
          <span style="font-size: 0.75rem; color: var(--text-dim);"><i class="fa-solid fa-arrow-down-short-wide"></i></span>
          <select class="form-control" data-role="sort" style="font-size: 0.8rem; padding: 0.35rem 0.6rem; width: auto;" title="Sort accounts">
            <option value="newest" selected>⬇️ Newest First</option>
            <option value="oldest">⬆️ Oldest First</option>
            <option value="uname_asc">🔤 Username (A-Z)</option>
            <option value="uname_desc">🔤 Username (Z-A)</option>
            <option value="name_asc">👤 Name (A-Z)</option>
            <option value="email_asc">✉️ Email (A-Z)</option>
          </select>
        </div>
        <select class="form-control" data-role="per-page" style="font-size: 0.8rem; padding: 0.35rem 0.6rem; width: auto;">
          <option value="10" selected>10 / page</option>
          <option value="25">25 / page</option>
          <option value="50">50 / page</option>
          <option value="100">100 / page</option>
        </select>

        <button type="button" class="btn btn-secondary btn-sm" data-role="combo" style="display: flex; align-items: center; gap: 6px; padding: 0.35rem 0.65rem;" title="Download combos for this workspace">
          <i class="fa-solid fa-file-export" style="color: var(--accent-green);"></i>
          <span>Combo</span>
        </button>

        <div class="dropdown-wrapper" style="position: relative;">
          <button type="button" class="btn btn-secondary btn-sm" data-role="col-toggle" style="display: flex; align-items: center; gap: 6px; padding: 0.35rem 0.65rem;" title="Show or hide table columns">
            <i class="fa-solid fa-table-columns" style="color: var(--accent-cyan);"></i>
            <span>Columns</span>
            <i class="fa-solid fa-chevron-down" style="font-size: 0.65rem; opacity: 0.7;"></i>
          </button>
          <div data-role="col-menu" class="creator-col-menu" style="display: none;">
            <div class="creator-col-menu-head">
              <span>Columns</span>
              <button type="button" data-role="cols-reset">Reset All</button>
            </div>
            ${colMenu}
          </div>
        </div>

        <div style="min-width: 170px;">
          <input type="text" class="form-control" data-role="search" placeholder="Filter results..." style="font-size: 0.8rem; padding: 0.35rem 0.75rem;">
        </div>
      </div>
    </div>

    <div class="table-wrap">
      <table class="metainsta-table">
        <thead>
          <tr>
            <th style="cursor: pointer; user-select: none;" data-role="th" data-sort="newest" data-col="id" title="Click to toggle Newest/Oldest"># <span data-role="sort-icon-id" style="font-size: 0.72rem; color: var(--accent-purple); margin-left: 2px;">▼</span></th>
            <th style="cursor: pointer; user-select: none;" data-role="th" data-sort="uname_asc" data-col="uname" title="Click to sort by Username">Uname <span data-role="sort-icon-uname" style="font-size: 0.72rem; opacity: 0.4; margin-left: 2px;">⇅</span></th>
            <th style="cursor: pointer; user-select: none;" data-role="th" data-sort="name_asc" data-col="name" title="Click to sort by Name">Name <span data-role="sort-icon-name" style="font-size: 0.72rem; opacity: 0.4; margin-left: 2px;">⇅</span></th>
            <th style="cursor: pointer; user-select: none;" data-role="th" data-sort="email_asc" data-col="email" title="Click to sort by Email">Email <span data-role="sort-icon-email" style="font-size: 0.72rem; opacity: 0.4; margin-left: 2px;">⇅</span></th>
            <th data-col="password">Password</th>
            <th data-col="cookies">Cookies</th>
            <th data-col="health" title="OK = healthy · Damaged = Failed/Banned/dead session (skipped by “Leave out damaged”) · Busy = claimed by a running drain · Used = already submitted">Health</th>
            <th style="cursor: pointer; user-select: none;" data-role="th" data-sort="newest" data-col="created" title="Click to sort by Creation Time">Created <span data-role="sort-icon-created" style="font-size: 0.72rem; opacity: 0.4; margin-left: 2px;">⇅</span></th>
            <th data-col="actions" style="text-align: right;">Actions</th>
          </tr>
        </thead>
        <tbody data-role="results"></tbody>
      </table>
    </div>

    <div data-role="pagination" class="metainsta-pagination"></div>
  </div>

  <div class="card-panel" style="margin-top: 1.25rem;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
      <h3 class="panel-header" style="margin: 0;"><i class="fa-solid fa-terminal"></i> Live Engine Log (SSE)</h3>
      <div style="display: flex; gap: 0.5rem; align-items: center;">
        <label style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; color: var(--text-dim);">
          <input type="checkbox" data-role="autoscroll" checked> Auto-scroll
        </label>
        <button type="button" class="btn btn-secondary btn-sm" data-role="copy-log">Copy Log</button>
        <button type="button" class="btn btn-secondary btn-sm" data-role="clear-log">Clear Log</button>
      </div>
    </div>
    <div data-role="log" class="log-container" style="height: 220px; overflow-y: auto; background: #060910; border: 1px solid var(--border-color); border-radius: 8px; padding: 0.75rem; font-family: var(--font-mono); font-size: 0.78rem; white-space: pre-wrap;"></div>
  </div>
  ${window.NovaDiag ? NovaDiag.renderHtml(def.kind, def.kind) : ''}`;
}

// =============================================================================
// 3. SHARED MODAL MANAGERS
// =============================================================================

const MiModals = {
  confirmDelete: null,
  pendingDeleteResolver: null,

  initDeleteConfirm() {
    const modal = document.getElementById('modal-metainsta-confirm-delete');
    const title = document.getElementById('metainsta-delete-modal-title');
    const msg = document.getElementById('metainsta-delete-modal-msg');
    const sub = document.getElementById('metainsta-delete-modal-sub');
    const targetBox = document.getElementById('metainsta-delete-modal-target-box');
    const targetText = document.getElementById('metainsta-delete-modal-target-text');
    const btnSubmit = document.getElementById('btn-metainsta-confirm-delete-submit');

    const resolve = (val) => {
      if (this.pendingDeleteResolver) {
        const fn = this.pendingDeleteResolver;
        this.pendingDeleteResolver = null;
        fn(val);
      }
    };

    if (btnSubmit) {
      btnSubmit.addEventListener('click', () => {
        resolve(true);
        if (modal) closeModal(modal);
      });
    }

    if (modal) {
      modal.querySelectorAll('[data-close], .close-modal').forEach((b) => {
        b.addEventListener('click', () => resolve(false));
      });
      modal.addEventListener('click', (e) => {
        if (e.target === modal) resolve(false);
      });
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
        resolve(false);
      }
    });

    this.confirmDelete = ({ title: t, message: m, subtext: s, targetHtml: th, confirmText = 'Confirm Delete' } = {}) => {
      return new Promise((res) => {
        if (!modal) {
          res(window.confirm(m || 'Are you sure you want to delete?'));
          return;
        }
        if (this.pendingDeleteResolver) this.pendingDeleteResolver(false);
        this.pendingDeleteResolver = res;

        if (title) title.textContent = t || 'Delete Account';
        if (msg) msg.textContent = m || 'Are you sure you want to delete this account?';
        if (sub) sub.textContent = s || 'This action cannot be undone.';
        if (targetText) targetText.innerHTML = th || '';
        if (targetBox) targetBox.style.display = th ? 'block' : 'none';
        if (btnSubmit) btnSubmit.innerHTML = `<i class="fa-solid fa-trash-can"></i> ${confirmText}`;
        openModal(modal);
      });
    };
  },

  initEditAccount(onSaved) {
    const editModal = document.getElementById('modal-metainsta-edit');
    const editForm = document.getElementById('form-metainsta-edit');
    if (!editForm) return editModal;

    editForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = document.getElementById('metainsta-edit-id').value;
      const patch = {
        username: document.getElementById('metainsta-edit-username').value.trim(),
        password: document.getElementById('metainsta-edit-password').value.trim(),
        email: document.getElementById('metainsta-edit-email').value.trim(),
        name: document.getElementById('metainsta-edit-name').value.trim(),
      };
      try {
        const r = await (await fetch('/api/meta-insta/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, patch }),
        })).json();
        if (r.status === 'SUCCESS') {
          showToast('Account updated.', 'success');
          closeModal(editModal);
          if (typeof onSaved === 'function') await onSaved();
        } else {
          showToast(r.error || 'Update failed.', 'error');
        }
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
    return editModal;
  },

  initGlobalPassword() {
    const gpStatus = document.getElementById('global-pass-status');
    const gpModal = document.getElementById('modal-global-password');
    const gpForm = document.getElementById('form-global-password');
    const gpInput = document.getElementById('input-global-password');
    const gpBtn = document.getElementById('nav-item-global-pass');

    function renderStatus(pass) {
      if (!gpStatus) return;
      const isSet = Boolean(pass);
      gpStatus.textContent = isSet ? 'Set' : 'Not set';
      gpStatus.style.background = isSet ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)';
      gpStatus.style.color = isSet ? '#34d399' : '#94a3b8';
    }

    async function load() {
      try {
        const r = await (await fetch('/api/meta-insta/settings')).json();
        const pass = (r && r.globalPassword) || '';
        if (gpInput) gpInput.value = pass;
        renderStatus(pass);
      } catch (e) {}
    }

    if (gpBtn && gpModal) {
      gpBtn.addEventListener('click', async () => { await load(); openModal(gpModal); });
    }
    if (gpForm) {
      gpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pass = ((gpInput && gpInput.value) || '').trim();
        try {
          const r = await (await fetch('/api/meta-insta/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ globalPassword: pass }),
          })).json();
          if (r && r.status === 'SUCCESS') {
            renderStatus(pass);
            closeModal(gpModal);
            showToast(pass ? 'Global password saved.' : 'Global password cleared (auto-generated passwords will be used).', 'success');
          } else {
            showToast((r && r.error) || 'Failed to save password.', 'error');
          }
        } catch (err) {
          showToast(err.message, 'error');
        }
      });
    }
    load();
  },
};

// =============================================================================
// 4. BROWSER PROFILE LAUNCHER (Nova Browser Parity)
// =============================================================================

async function miLaunchAccount(id, site, account) {
  site = site === 'mail' ? 'mail' : 'meta';
  if (!requireLicense('Active license key required to open browser profiles.')) return;
  const flightKey = `meta-open:${id}:${site}`;
  if (typeof tryClaimLaunch === 'function' && !tryClaimLaunch(flightKey)) {
    showToast('This session is already opening — please wait.', 'info');
    return;
  }
  try {
    const data = await (await fetch(`/api/meta-insta/prepare-launch?id=${encodeURIComponent(id)}&site=${site}`)).json();
    if (data.status !== 'SUCCESS') {
      showToast(data.error || 'Failed to prepare browser session.', 'error');
      return;
    }
    const url = data.url;
    const cookies = Array.isArray(data.cookies) ? data.cookies : [];
    let profile = typeof ProfileManager !== 'undefined' && ProfileManager.getProfile ? ProfileManager.getProfile(data.profileId) : null;
    if (!profile && typeof FingerprintGenerator !== 'undefined') {
      profile = FingerprintGenerator.generateProfile({
        name: data.profileName || 'Meta account',
        type: 'ANDROID_MOBILE',
        customUrl: url,
      });
      profile.id = data.profileId;
    }
    if (profile) {
      profile.name = data.profileName || profile.name;
      profile.cookies = cookies;
      profile.customUrl = url;
      if (typeof ProfileManager !== 'undefined' && ProfileManager.saveProfile) ProfileManager.saveProfile(profile);
    }
    if (typeof renderProfiles === 'function') renderProfiles();
    const extra = data.seeded ? 'persisted profile restored, ' : (data.persisted ? '' : 'no persisted profile, cookies only, ');
    showToast(`Opening ${(profile && profile.name) || 'session'} (${extra}${cookies.length} cookies, ${site} tab)...`, 'info');
    const out = await (await fetch('/api/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile: { ...(profile || {}), forceMobile: true }, url: [url], isSiteLauncher: false }),
    })).json();
    if (out.status === 'SUCCESS') {
      showToast(site === 'mail' ? 'Mail inbox opened in persisted session!' : 'Meta session opened in persisted session!', 'success');
    } else {
      showToast(out.error || out.message || 'Browser failed to launch.', 'error');
    }
    if (typeof syncActiveSessions === 'function') syncActiveSessions();
  } catch (e) {
    showToast(`Open failed: ${e.message}`, 'error');
  } finally {
    if (typeof freeLaunch === 'function') freeLaunch(flightKey);
  }
}

// =============================================================================
// 5. BATCHED LOG STREAM (RAF-Throttled)
// =============================================================================

function createLogStream(logEl, autoScrollEl) {
  const MAX_LINES = 600;
  let queue = [];
  let rafId = null;

  function flush() {
    rafId = null;
    if (!logEl || queue.length === 0) return;
    const auto = autoScrollEl ? autoScrollEl.checked : true;
    const frag = document.createDocumentFragment();
    for (const line of queue) {
      const row = document.createElement('div');
      row.textContent = line;
      frag.appendChild(row);
    }
    queue = [];
    logEl.appendChild(frag);
    while (logEl.childElementCount > MAX_LINES) logEl.removeChild(logEl.firstChild);
    if (auto) logEl.scrollTop = logEl.scrollHeight;
  }

  return {
    append(line) {
      if (!logEl) return;
      queue.push(line);
      if (!rafId) rafId = requestAnimationFrame(flush);
    },
    clear() {
      if (logEl) logEl.textContent = '';
      queue = [];
    },
    hasContent() {
      return Boolean(logEl && (logEl.textContent || '').trim());
    },
  };
}

// =============================================================================
// 6. WORKSPACE INSTANCE FACTORY (Single Workspace Controller)
// =============================================================================

function createCreatorWorkspace(root, def, state, shared) {
  const q = (role) => root.querySelector(`[data-role="${role}"]`);
  const els = {
    conc: q('concurrency'),
    target: q('target'),
    headless: q('headless'),
    twofa: q('twofa'),
    follow: q('follow'),
    username: q('username'),
    btnStart: q('start'),
    btnStop: q('stop'),
    btnExportFull: q('export-full'),
    btnImportOpen: q('import-open'),
    btnPurge: q('purge-damaged'),
    btnCheckHealth: q('check-health'),
    btnClear: q('clear'),
    btnDeepClean: q('deep-clean'),
    statTotal: q('stat-total'),
    statRunning: q('stat-running'),
    statCreated: q('stat-created'),
    state: q('state'),
    progressBox: q('progress-box'),
    progressBar: q('progress-bar'),
    progressLabel: q('progress-label'),
    progressPct: q('progress-pct'),
    resultsList: q('results'),
    pager: q('pagination'),
    perPage: q('per-page'),
    sort: q('sort'),
    search: q('search'),
    log: q('log'),
    btnClearLog: q('clear-log'),
    btnCopyLog: q('copy-log'),
    autoScroll: q('autoscroll'),
    badgeAll: q('badge-all'),
    engineHint: q('engine-hint'),
    table: root.querySelector('.metainsta-table'),
    btnColToggle: q('col-toggle'),
    colMenu: q('col-menu'),
    btnColsReset: q('cols-reset'),
    combo: q('combo'),
  };

  const STORAGE_KEY_COLS = `nova_metainsta_cols_${def.kind}`;
  let page = 1;
  let currentSort = 'newest';

  // --- Logger ---
  const logger = createLogStream(els.log, els.autoScroll);

  // --- Column Visibility ---
  function getVisibleCols() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_COLS);
      if (stored) {
        const arr = JSON.parse(stored);
        if (Array.isArray(arr) && arr.length > 0) {
          const known = arr.filter((c) => MI_ALL_COLS.includes(c));
          return [...known, ...MI_ALL_COLS.filter((c) => !known.includes(c))];
        }
      }
    } catch (e) {}
    return MI_ALL_COLS.slice();
  }

  function applyColumnVisibility() {
    const visible = getVisibleCols();
    if (!els.table) return;
    MI_ALL_COLS.forEach((col) => {
      els.table.classList.toggle(`hide-col-${col}`, !visible.includes(col));
      const cb = root.querySelector(`.metainsta-col-cb[data-col="${col}"]`);
      if (cb) cb.checked = visible.includes(col);
    });
  }
  applyColumnVisibility();

  // --- Stats & Badges ---
  function myAccounts() {
    return state.accounts.filter((a) => (a.target || '') !== 'telegram' && ((def.kind === 'ig') === shared.isIgAccount(a)));
  }

  function updateStats() {
    const mine = myAccounts();
    if (els.statTotal) els.statTotal.textContent = String(mine.length);
    if (els.statCreated) els.statCreated.textContent = String(mine.length);
    if (els.badgeAll) els.badgeAll.textContent = String(mine.length);

    // Sidebar badges
    const badgeMeta = document.getElementById('metainsta-badge-meta');
    const badgeIg = document.getElementById('metainsta-badge-ig');
    const isMeta = (a) => a && (a.target || '') !== 'telegram' && String(a.status || '') === 'MetaCreated';
    if (badgeMeta) badgeMeta.textContent = String(state.accounts.filter(isMeta).length);
    if (badgeIg) badgeIg.textContent = String(state.accounts.filter(shared.isIgAccount).length);

    const runningHere = def.kind === 'meta' ? state.meta_running : state.ig_running;

    if (els.statRunning) {
      els.statRunning.textContent = runningHere ? 'RUNNING' : 'IDLE';
      els.statRunning.style.color = runningHere ? 'var(--accent-green)' : 'var(--text-muted)';
    }
    if (els.state) {
      els.state.textContent = runningHere ? 'RUNNING' : 'IDLE';
      els.state.style.color = runningHere ? 'var(--accent-green)' : 'var(--text-muted)';
    }
    if (els.btnStart) {
      els.btnStart.disabled = !state.engineOk;
      els.btnStart.style.display = runningHere ? 'none' : 'inline-flex';
      els.btnStart.title = !state.engineOk ? 'Mining engine not installed on this machine' : '';
    }
    if (els.btnStop) els.btnStop.style.display = runningHere ? 'inline-flex' : 'none';
    if (els.progressBox) els.progressBox.style.display = runningHere ? 'block' : 'none';
    if (els.engineHint) els.engineHint.style.display = state.engineOk ? 'none' : 'inline';
  }

  // --- Sorting & Filtering ---
  function updateSortIndicators() {
    const icons = { 'sort-icon-id': '⇅', 'sort-icon-uname': '⇅', 'sort-icon-name': '⇅', 'sort-icon-email': '⇅', 'sort-icon-created': '⇅' };
    const mark = (id, char) => {
      const el = q(id);
      if (el) { el.textContent = char; el.style.color = 'var(--accent-purple)'; el.style.opacity = '1'; }
    };
    for (const [id, char] of Object.entries(icons)) {
      const el = q(id);
      if (el) { el.textContent = char; el.style.color = ''; el.style.opacity = '0.4'; }
    }
    if (currentSort === 'newest') { mark('sort-icon-id', '▼'); mark('sort-icon-created', '▼'); }
    else if (currentSort === 'oldest') { mark('sort-icon-id', '▲'); mark('sort-icon-created', '▲'); }
    else if (currentSort === 'uname_asc') mark('sort-icon-uname', '▲');
    else if (currentSort === 'uname_desc') mark('sort-icon-uname', '▼');
    else if (currentSort === 'name_asc') mark('sort-icon-name', '▲');
    else if (currentSort === 'email_asc') mark('sort-icon-email', '▲');
  }

  function getProcessedAccounts() {
    const query = ((els.search && els.search.value) || '').toLowerCase().trim();
    let list = myAccounts().map((a, idx) => ({ ...a, _origIndex: idx + 1 }));
    if (query) {
      list = list.filter((a) => `${a.instagram_username || ''} ${a.username || ''} ${a.email || ''} ${a.name || ''}`.toLowerCase().includes(query));
    }
    const sortVal = (els.sort && els.sort.value) || currentSort || 'newest';
    list.sort((a, b) => {
      if (sortVal === 'newest' || sortVal === 'oldest') {
        const tA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const tB = b.created_at ? new Date(b.created_at).getTime() : 0;
        if (tA && tB && tA !== tB) return sortVal === 'newest' ? tB - tA : tA - tB;
        return sortVal === 'newest' ? (b._origIndex || 0) - (a._origIndex || 0) : (a._origIndex || 0) - (b._origIndex || 0);
      }
      if (sortVal === 'uname_asc') return (a.instagram_username || a.username || '').toLowerCase().localeCompare((b.instagram_username || b.username || '').toLowerCase());
      if (sortVal === 'uname_desc') return (b.instagram_username || b.username || '').toLowerCase().localeCompare((a.instagram_username || a.username || '').toLowerCase());
      if (sortVal === 'name_asc') return (a.name || '').toLowerCase().localeCompare((b.name || '').toLowerCase());
      if (sortVal === 'email_asc') return (a.email || '').toLowerCase().localeCompare((b.email || '').toLowerCase());
      return 0;
    });
    return list;
  }

  function perPageCount() {
    return Math.max(1, parseInt((els.perPage && els.perPage.value) || '10', 10) || 10);
  }

  function renderResults() {
    updateSortIndicators();
    const filtered = getProcessedAccounts();
    const total = filtered.length;
    const pp = perPageCount();
    const pages = Math.max(1, Math.ceil(total / pp));
    if (page > pages) page = pages;
    if (page < 1) page = 1;
    const start = (page - 1) * pp;
    const slice = filtered.slice(start, start + pp);

    if (slice.length === 0) {
      const colCount = getVisibleCols().length || 1;
      els.resultsList.innerHTML = `
        <tr><td colspan="${colCount}"><div class="insta-empty-state">
          <i class="fa-solid fa-wand-magic-sparkles" style="font-size: 2rem; color: var(--text-muted); opacity: 0.5; margin-bottom: 0.5rem;"></i>
          <p>No accounts yet. Set Parallel + Target and click <strong>${def.startLabel}</strong>.</p>
        </div></td></tr>`;
    } else {
      els.resultsList.innerHTML = slice.map((a, i) => {
        const n = start + i + 1;
        const u = a.instagram_username || a.username || '';
        const masked = (a.password || '').replace(/.(?=.{3})/g, '•');
        const cVal = a.cookies || a.cookie || '';
        return `
        <tr>
          <td data-col="id" style="color: var(--text-muted); font-variant-numeric: tabular-nums;" title="Original Order: #${a._origIndex}">${n}</td>
          <td data-col="uname" class="mono"><span>${escapeHtml(u || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copyuname="${a.id}" title="Copy username" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-copy"></i></button></td>
          <td data-col="name">${escapeHtml(a.name || '—')}</td>
          <td data-col="email" class="mono"><span>${escapeHtml(a.email || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copyemail="${a.id}" title="Copy email" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-copy"></i></button></td>
          <td data-col="password" class="mono"><span title="Use Copy for the full combo">${escapeHtml(masked || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copypass="${a.id}" title="Copy password" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-copy"></i></button></td>
          <td data-col="cookies" class="mono"><span title="${escapeHtml(cVal || '—')}">${escapeHtml(cVal.slice(0, 20) + (cVal.length > 20 ? '…' : '') || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copyrawcookie="${a.id}" title="Copy cookies string" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-cookie"></i></button></td>
          <td data-col="health">${miHealthBadge(a)}</td>
          <td data-col="created" style="color: var(--text-muted); font-size: 0.78rem; white-space: nowrap;">${escapeHtml(a.created_at || '—')}</td>
          <td data-col="actions"><div class="metainsta-actions">
            <button type="button" class="btn btn-primary btn-sm" data-open-meta="${a.id}" title="Open persisted Meta session (auth.meta.com)${a.metaPersisted === false ? ' — no persisted profile, cookies only' : ''}"><i class="fa-brands fa-meta"></i> Meta</button>
            ${((a.mail_provider || 'mailtd') !== 'mailtd' || a.mailPersisted === false) ? '' : `<button type="button" class="btn btn-secondary btn-sm" data-open-mail="${a.id}" title="Open persisted mail inbox (mail.td)"><i class="fa-solid fa-envelope"></i> Mail</button>`}
            <button type="button" class="btn btn-secondary btn-sm" data-copy="${a.id}" title="Copy uname|pass|email|cookie"><i class="fa-solid fa-copy"></i></button>
            ${(a.twofa_secret || a.twofa_key || a.totp_secret) ? `<button type="button" class="btn btn-secondary btn-sm" data-copy2fa="${a.id}" title="Copy 2FA Key: ${escapeHtml(a.twofa_secret || a.twofa_key || a.totp_secret)}" style="color: #60a5fa;"><i class="fa-solid fa-key"></i></button>` : ''}
            <button type="button" class="btn btn-secondary btn-sm" data-cookie="${a.id}" title="Export saved browser cookies (JSON)"><i class="fa-solid fa-cookie-bite"></i></button>
            <button type="button" class="btn btn-secondary btn-sm" data-edit="${a.id}" title="Edit stored fields"><i class="fa-solid fa-pen"></i></button>
            <button type="button" class="btn btn-secondary btn-sm" data-del="${a.id}" title="Delete account" style="color: #f87171;"><i class="fa-solid fa-xmark"></i></button>
          </div></td>
        </tr>`;
      }).join('');
    }

    renderPagination(total, pages);
    wireRowButtons();
  }

  function renderPagination(total, pages) {
    if (!els.pager) return;
    const pp = perPageCount();
    const from = total === 0 ? 0 : (page - 1) * pp + 1;
    const to = Math.min(total, page * pp);
    let nums = [];
    if (pages <= 7) {
      for (let i = 1; i <= pages; i++) nums.push(i);
    } else {
      const set = new Set([1, 2, page - 1, page, page + 1, pages - 1, pages]);
      nums = [...set].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
    }
    let html = `<span>Showing ${from}–${to} of ${total}</span><div class="metainsta-page-btns">`;
    html += `<button type="button" class="btn btn-secondary btn-sm" data-pg="prev" ${page <= 1 ? 'disabled' : ''}>‹ Prev</button>`;
    let last = 0;
    for (const n of nums) {
      if (n - last > 1) html += `<span style="color: var(--text-muted);">…</span>`;
      html += `<button type="button" class="btn btn-sm ${n === page ? 'btn-primary' : 'btn-secondary'}" data-pg="${n}">${n}</button>`;
      last = n;
    }
    html += `<button type="button" class="btn btn-secondary btn-sm" data-pg="next" ${page >= pages ? 'disabled' : ''}>Next ›</button></div>`;
    els.pager.innerHTML = html;
    els.pager.querySelectorAll('[data-pg]').forEach((b) => {
      b.addEventListener('click', () => {
        const v = b.getAttribute('data-pg');
        if (v === 'prev' && page > 1) page -= 1;
        else if (v === 'next') page += 1;
        else page = parseInt(v, 10) || 1;
        renderResults();
      });
    });
  }

  function findAccount(id) {
    return state.accounts.find((x) => String(x.id) === String(id));
  }

  // --- Table Action Button Delegation ---
  let rowsDelegated = false;
  function wireRowButtons() {
    if (rowsDelegated || !els.resultsList) return;
    rowsDelegated = true;
    els.resultsList.addEventListener('click', async (ev) => {
      const btn = ev.target.closest('button[data-del],button[data-copy],button[data-copy2fa],button[data-copypass],button[data-copyuname],button[data-copyemail],button[data-copyrawcookie],button[data-cookie],button[data-edit],button[data-open-meta],button[data-open-mail]');
      if (!btn) return;
      const d = btn.dataset;
      const id = d.del || d.copy || d.copy2fa || d.copypass || d.copyuname || d.copyemail || d.copyrawcookie || d.cookie || d.edit || d.openMeta || d.openMail;
      const a = findAccount(id);
      if (!a) return;

      if (d.del !== undefined) return handleDelete(a);
      if (d.copy !== undefined) {
        const combo = `${a.instagram_username || a.username || ''}|${a.password || ''}|${a.email || ''}|${a.cookies || a.cookie || ''}`;
        return navigator.clipboard.writeText(combo).then(() => showToast('Copied uname|pass|email|cookie!', 'success'));
      }
      if (d.copy2fa !== undefined) {
        const k2 = a.twofa_secret || a.twofa_key || a.totp_secret || '';
        return k2 ? navigator.clipboard.writeText(k2).then(() => showToast('2FA Key copied!', 'success')) : showToast('No 2FA Key found.', 'warning');
      }
      if (d.copypass !== undefined) return navigator.clipboard.writeText(a.password || '').then(() => showToast('Password copied!', 'success'));
      if (d.copyuname !== undefined) return navigator.clipboard.writeText(a.instagram_username || a.username || '').then(() => showToast('Username copied!', 'success'));
      if (d.copyemail !== undefined) return navigator.clipboard.writeText(a.email || '').then(() => showToast('Email copied!', 'success'));
      if (d.copyrawcookie !== undefined) {
        return (a.cookies || a.cookie) ? navigator.clipboard.writeText(a.cookies || a.cookie).then(() => showToast('Cookies copied!', 'success')) : showToast('No cookies found.', 'warning');
      }
      if (d.cookie !== undefined) return handleCookieExport(a, btn);
      if (d.edit !== undefined) return handleEdit(a);
      if (d.openMeta !== undefined) return miLaunchAccount(a.id, 'meta', a);
      if (d.openMail !== undefined) return miLaunchAccount(a.id, 'mail', a);
    });
  }

  async function handleDelete(a) {
    const uname = a.instagram_username || a.username || 'Unknown';
    const email = a.email || 'N/A';
    const targetHtml = `
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div><strong style="color: var(--text-main);">Username:</strong> <span style="color: #60a5fa;">@${escapeHtml(uname)}</span></div>
        <div><strong style="color: var(--text-main);">Email:</strong> <span>${escapeHtml(email)}</span></div>
        ${a.name ? `<div><strong style="color: var(--text-main);">Name:</strong> <span>${escapeHtml(a.name)}</span></div>` : ''}
        <div style="font-size: 0.72rem; color: var(--text-dim); margin-top: 3px;"><strong>Record ID:</strong> ${escapeHtml(a.id)}</div>
      </div>`;
    const confirmed = await MiModals.confirmDelete({
      title: 'Delete Account',
      message: `Delete account @${uname}?`,
      subtext: 'This permanently removes the account credentials, 2FA secret, and cookie session files.',
      targetHtml,
      confirmText: 'Delete Account',
    });
    if (!confirmed) return;
    try {
      const res = await fetch('/api/meta-insta/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: a.id }),
      });
      if (res.ok) {
        showToast(`Account @${uname} deleted`, 'success');
        logger.append(`[storage] Deleted account @${uname} (${a.id}).`);
      } else {
        showToast('Failed to delete account', 'error');
      }
    } catch (err) {
      showToast('Error deleting account: ' + err.message, 'error');
    }
    await shared.refreshShared();
  }

  async function handleCookieExport(a, btn) {
    btn.disabled = true;
    try {
      const r = await (await fetch(`/api/meta-insta/cookies?id=${encodeURIComponent(a.id)}`)).json();
      if (!r || r.status !== 'SUCCESS' || !Array.isArray(r.cookies) || r.cookies.length === 0) {
        showToast('No saved cookies for this account.', 'warning');
        return;
      }
      const uname = a.instagram_username || a.username || a.id;
      const blob = new Blob([JSON.stringify(r.cookies, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `cookies_${uname}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      showToast(`Exported ${r.cookies.length} cookies.`, 'success');
    } catch (e) {
      showToast('Cookie export failed: ' + e.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  function handleEdit(a) {
    if (!shared.editModal) return;
    document.getElementById('metainsta-edit-id').value = a.id;
    document.getElementById('metainsta-edit-username').value = a.instagram_username || a.username || '';
    const passEl = document.getElementById('metainsta-edit-password');
    passEl.value = '';
    passEl.placeholder = 'Leave empty to keep current';
    document.getElementById('metainsta-edit-email').value = a.email || '';
    document.getElementById('metainsta-edit-name').value = a.name || '';
    openModal(shared.editModal);
  }

  // --- Engine Controls (Start / Stop) ---
  els.btnStart.addEventListener('click', async () => {
    if (!requireLicense('Active license key required to create accounts.')) return;
    const isRunning = def.kind === 'meta' ? state.meta_running : state.ig_running;
    if (isRunning) {
      showToast('This workspace is already running.', 'info');
      return;
    }
    if (els.btnStart.disabled) return;
    els.btnStart.disabled = true;
    try {
      const mailRadio = root.querySelector(`input[name="mi-mail-${def.kind}"]:checked`);
      const captchaRadio = root.querySelector(`input[name="mi-captcha-${def.kind}"]:checked`);
      const body = {
        concurrency: parseInt(els.conc.value, 10) || 2,
        target: parseInt(els.target.value, 10) || 0,
        delay: 4,
        headless: Boolean(els.headless && els.headless.checked),
        twofa: Boolean(els.twofa && els.twofa.checked),
        // Follow step toggle (IG workspace only). Absent element -> keep the
        // default (enabled) so Meta-only workspaces are unaffected.
        follow: els.follow ? Boolean(els.follow.checked) : true,
        new_username: (els.username.value || '').trim() || undefined,
        mail_provider: (mailRadio && mailRadio.value) || 'mailtd',
        captcha_mode: (captchaRadio && captchaRadio.value) || 'extension',
        mode: def.mode,
      };
      let r;
      try {
        r = await (await fetch('/api/meta-insta/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })).json();
      } catch (e) {
        showToast(e.message, 'error');
        return;
      }
      if (r.status === 'SUCCESS') {
        if (def.kind === 'meta') state.meta_running = true;
        else state.ig_running = true;
        state.running = state.meta_running || state.ig_running;
        showToast(r.message || 'Creator started.', 'success');
        logger.append(`[controller] ${r.message || 'started'}`);
      } else {
        if (r.status === 'UNLICENSED' && typeof requireLicense === 'function') {
          requireLicense(r.error || 'Active license key required to create accounts.');
        }
        showToast(r.error || 'Failed to start.', 'error');
        logger.append(`[controller] ${r.error || 'start failed'}`);
      }
    } finally {
      els.btnStart.disabled = false;
    }
    await shared.refreshShared();
  });

  let stopBusy = false;
  els.btnStop.addEventListener('click', async () => {
    if (stopBusy) return;
    const runningHere = def.kind === 'meta' ? state.meta_running : state.ig_running;
    if (!runningHere) {
      showToast('Engine is not running.', 'info');
      return;
    }
    stopBusy = true;
    try {
      await fetch('/api/meta-insta/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: def.kind, mode: def.mode }),
      });
      if (def.kind === 'meta') state.meta_running = false;
      else state.ig_running = false;
      state.running = state.meta_running || state.ig_running;
      logger.append('[controller] Stop requested.');
    } finally {
      stopBusy = false;
    }
    await shared.refreshShared();
  });

  // --- Export and Utility Actions ---
  // NOTE: legacy per-format exports (CSV/TXT/XLSX buttons) were removed from
  // the UI — Export (full backup) + Import is the only path. Backend routes stay.

  // --- Import / Export (Meta + IG): one CSV both ways, cookies + mail
  // session + 2FA included, "leave out damaged" for both directions, plus
  // import how-many / newest-or-oldest. The modal lives once in index.html
  // and is wired once; each panel's button selects the active kind (export
  // scope + preview scope) before opening it.
  window.__miLoggers = window.__miLoggers || {};
  window.__miLoggers[def.kind] = logger;

  if (els.btnExportFull || els.btnImportOpen) {
    const openBackupModal = (tab) => {
      window.__miBackupKind = def.kind;
      const showImport = tab === 'import';
      const title = document.getElementById('ig-backup-kind-title');
      if (title) title.textContent = def.kind === 'meta' ? 'Meta' : 'IG';
      const action = document.getElementById('ig-backup-action-title');
      if (action) action.textContent = showImport ? 'Import' : 'Export';
      const pe = document.getElementById('ig-backup-pane-export');
      const pi = document.getElementById('ig-backup-pane-import');
      if (pe) pe.style.display = showImport ? 'none' : 'flex';
      if (pi) pi.style.display = showImport ? 'flex' : 'none';
      const list = state.accounts.filter((a) => (a.target || '') !== 'telegram' && ((def.kind === 'ig') === shared.isIgAccount(a)));
      const cnt = document.getElementById('ig-backup-count');
      if (cnt) cnt.textContent = `${list.length} account(s) in this list right now`;
      const dlbl = document.getElementById('ig-backup-download-label');
      if (dlbl) dlbl.textContent = `Export ${list.length} account(s)`;
      window.__miStagedText = '';
      const fi = document.getElementById('ig-backup-file-input');
      if (fi) fi.value = '';
      const badge = document.getElementById('ig-backup-file-badge');
      if (badge) { badge.style.display = 'none'; badge.innerHTML = ''; }
      const pv = document.getElementById('ig-backup-preview');
      if (pv) pv.textContent = '';
      const bi = document.getElementById('btn-ig-backup-import');
      if (bi) bi.disabled = true;
      openModal(document.getElementById('modal-ig-backup'));
    };
    if (els.btnExportFull) els.btnExportFull.addEventListener('click', () => openBackupModal('export'));
    if (els.btnImportOpen) els.btnImportOpen.addEventListener('click', () => openBackupModal('import'));
  }

  if (!window.__miBackupWired) {
    window.__miBackupWired = true;
    window.__miBackupKind = window.__miBackupKind || 'ig';
    window.__miStagedText = '';
    const modal = () => document.getElementById('modal-ig-backup');
    const cbExclude = () => document.getElementById('ig-backup-exclude-damaged');
    const btnDownload = () => document.getElementById('btn-ig-backup-download');
    const fileInput = () => document.getElementById('ig-backup-file-input');
    const preview = () => document.getElementById('ig-backup-preview');
    const cbSkip = () => document.getElementById('ig-backup-skip-existing');
    const btnImport = () => document.getElementById('btn-ig-backup-import');
    const miKindLabel = () => ((window.__miBackupKind || 'ig') === 'meta' ? 'Meta' : 'Instagram');
    const miBackupSay = (msg) => {
      const L = window.__miLoggers[window.__miBackupKind || 'ig'];
      if (L) L.append(msg);
    };

    if (btnDownload()) {
      btnDownload().addEventListener('click', () => {
        const k = window.__miBackupKind || 'ig';
        const ex = cbExclude() && cbExclude().checked ? '1' : '0';
        window.location = `/api/meta-insta/export-full?kind=${k}&exclude_damaged=${ex}`;
        showToast(ex === '1' ? `Exporting your ${miKindLabel()} accounts (damaged left out)…` : `Exporting your ${miKindLabel()} accounts…`, 'success');
      });
    }

    const refreshBackupPreview = () => {
      const pv = preview();
      const bi = btnImport();
      const staged = window.__miStagedText || '';
      if (!staged) {
        if (pv) pv.textContent = '';
        if (bi) bi.disabled = true;
        return;
      }
      try {
        const parsed = miParseCsvPreview(staged);
        const hasUser = parsed.header.includes('username') || parsed.header.includes('instagram_username');
        if (!hasUser) {
          if (pv) pv.innerHTML = '<span style="color: #f87171;">Not a Meta Creator backup — username columns missing.</span>';
          window.__miStagedText = '';
          if (bi) bi.disabled = true;
          return;
        }
        const rows = parsed.rows;
        const damaged = rows.filter((r) => miRowIsDamaged(parsed.header, r)).length;
        const k = window.__miBackupKind || 'ig';
        const mine = new Set(state.accounts
          .filter((a) => (a.target || '') !== 'telegram' && ((k === 'ig') === shared.isIgAccount(a)))
          .map((a) => String(a.instagram_username || a.username || '').toLowerCase()));
        const ui = parsed.header.indexOf('instagram_username') !== -1 ? 'instagram_username' : 'username';
        const uidx = parsed.header.indexOf(ui);
        const dup = rows.filter((r) => mine.has(String(r[uidx] || '').toLowerCase())).length;
        const names = rows.slice(0, 5)
          .map((r) => String(r[uidx] || '').trim()).filter(Boolean);
        const chips = names.map((n) => `<span class="badge-pill bg-muted" style="margin: 0 2px;">${escapeHtml(n)}</span>`).join('') +
          (rows.length > 5 ? ` <span style="color: var(--text-dim);">+${rows.length - 5} more</span>` : '');
        if (pv) {
          pv.innerHTML =
            `<strong style="color: var(--text-main);">${rows.length} row(s)</strong>` +
            ` · <span style="color: #f87171;">${damaged} damaged</span>` +
            ` · <span style="color: #a5b4fc;">${dup} already in list</span>` +
            (chips ? `<br><span style="color: var(--text-dim);">Starts with:</span> ${chips}` : '') +
            ((cbExclude() && cbExclude().checked && damaged)
              ? `<br>“Leave out damaged” is ON — ~${rows.length - damaged} will import.` : '');
        }
        if (bi) bi.disabled = false;
      } catch (e) {
        if (pv) pv.textContent = 'Could not read this file: ' + e.message;
        window.__miStagedText = '';
        if (bi) bi.disabled = true;
      }
    };

    const stageBackupFile = (f) => {
      window.__miStagedText = '';
      if (btnImport()) btnImport().disabled = true;
      const badge = document.getElementById('ig-backup-file-badge');
      if (!f) {
        if (preview()) preview().textContent = '';
        if (badge) { badge.style.display = 'none'; badge.innerHTML = ''; }
        return;
      }
      if (badge) {
        badge.style.display = 'inline-flex';
        badge.innerHTML = `<span><i class="fa-solid fa-file-csv"></i> ${escapeHtml(f.name)}</span>`;
      }
      const reader = new FileReader();
      reader.onload = (ev) => {
        window.__miStagedText = String(ev.target.result || '');
        refreshBackupPreview();
      };
      reader.readAsText(f);
    };

    if (fileInput()) {
      fileInput().addEventListener('change', () => {
        stageBackupFile(fileInput().files && fileInput().files[0]);
      });
    }

    const dz = document.getElementById('ig-backup-dropzone');
    if (dz) {
      dz.addEventListener('click', () => { if (fileInput()) fileInput().click(); });
      ['dragover', 'dragenter'].forEach((evName) => {
        dz.addEventListener(evName, (e) => { e.preventDefault(); dz.classList.add('dragover'); });
      });
      ['dragleave', 'drop'].forEach((evName) => {
        dz.addEventListener(evName, (e) => { e.preventDefault(); dz.classList.remove('dragover'); });
      });
      dz.addEventListener('drop', (e) => {
        const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) stageBackupFile(f);
      });
    }

    const rePreview = () => refreshBackupPreview();
    if (cbExclude()) cbExclude().addEventListener('change', rePreview);

    if (btnImport()) {
      btnImport().addEventListener('click', async () => {
        if (!window.__miStagedText) return;
        const btn = btnImport();
        const idleHtml = '<i class="fa-solid fa-upload"></i> <span id="ig-backup-import-label">Import accounts</span>';
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Importing…';
        try {
          const r = await (await fetch('/api/meta-insta/import-full', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              csv_text: window.__miStagedText,
              exclude_damaged: Boolean(cbExclude() && cbExclude().checked),
              skip_existing: Boolean(cbSkip() && cbSkip().checked),
            }),
          })).json();
          if (r.status === 'SUCCESS') {
            const parts = [];
            if (r.imported) parts.push(`${r.imported} imported`);
            if (r.updated) parts.push(`${r.updated} updated`);
            if (r.skipped_existing) parts.push(`${r.skipped_existing} already in list`);
            if (r.skipped_damaged) parts.push(`${r.skipped_damaged} damaged skipped`);
            showToast(`Import done — ${parts.join(' · ') || 'nothing to import'}.`, 'success');
            miBackupSay(`[import] ${miKindLabel()}: ${parts.join(', ') || 'no changes'}.`);
            closeModal(modal());
          } else {
            showToast(r.error || 'Import failed.', 'error');
          }
        } catch (e) {
          showToast('Import failed: ' + e.message, 'error');
        } finally {
          btn.innerHTML = idleHtml;
          btn.disabled = !window.__miStagedText;
        }
        await shared.refreshShared();
      });
    }
  }

  if (els.btnClear) {
    els.btnClear.addEventListener('click', async () => {
      const kindName = def.kind === 'meta' ? 'Meta' : 'Instagram';
      const count = myAccounts().length;
      const confirmed = await MiModals.confirmDelete({
        title: `Clear ${kindName} Accounts`,
        message: `Are you sure you want to clear ${count} ${kindName} account(s)?`,
        subtext: 'Only this workspace\u2019s list will be deleted. A snapshot is saved in backups/ first.',
        targetHtml: (count > 0
          ? `<div style="margin-bottom: 0.6rem;"><strong style="color: #f87171;">Warning:</strong> You are about to clear <strong style="color:#fff;">${count}</strong> ${kindName} account(s).</div>`
          : '') +
          `<label style="display: flex; gap: 0.5rem; align-items: center; font-size: 0.82rem; cursor: pointer; color: var(--text-main);">
            <input type="checkbox" id="mi-clear-also-all" style="accent-color: #dc2626;">
            Also wipe the other workspace (delete EVERYTHING)
          </label>`,
        confirmText: `Clear ${kindName} Accounts`,
      });
      if (!confirmed) return;
      const wipeAll = Boolean(document.getElementById('mi-clear-also-all') && document.getElementById('mi-clear-also-all').checked);
      if (wipeAll) {
        await fetch('/api/meta-insta/reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ confirm: 'CLEAR' }),
        });
        showToast('All accounts cleared', 'info');
        logger.append('[tracking] All accounts cleared (both workspaces).');
      } else {
        const r = await (await fetch('/api/meta-insta/clear-kind', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: def.kind, confirm: 'CLEAR' }),
        })).json();
        if (r.status === 'SUCCESS') {
          showToast(`Cleared ${r.deleted} ${kindName} account(s)`, 'info');
          logger.append(`[tracking] Cleared ${r.deleted} ${kindName} account(s).`);
        } else {
          showToast(r.error || 'Clear failed.', 'error');
          logger.append('[tracking] Clear failed: ' + (r.error || 'unknown error'));
        }
      }
      page = 1;
      await shared.refreshShared();
    });
  }

  if (els.btnCheckHealth) {
    let checking = false;
    els.btnCheckHealth.addEventListener('click', async () => {
      if (checking) return;
      const rows = myAccounts().filter((a) => String(a.instagram_username || a.username || '').trim());
      if (!rows.length) {
        showToast('No Instagram accounts to check.', 'info');
        return;
      }
      const names = [...new Set(rows.map((a) => String(a.instagram_username || a.username).trim().replace(/^@+/, '').toLowerCase()))];
      const go = await MiModals.confirmDelete({
        title: 'Check Account Health',
        message: `Live-check ${names.length} Instagram account(s) now?`,
        subtext: 'Public profile lookup, no login — safe while the engine runs. Dead ones are flagged Damaged (pool skips them) after your OK. Roughly 1 min per 70 accounts; progress shows in the log.',
        confirmText: 'Check now',
      });
      if (!go) return;
      checking = true;
      els.btnCheckHealth.disabled = true;
      const dead = [];
      let blocked = 0, errors = 0, done = 0;
      try {
        for (let i = 0; i < names.length; i += 50) {
          const batch = names.slice(i, i + 50);
          let r = null;
          try {
            r = await (await fetch('/api/ig-check', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ usernames: batch, delay_ms: 600 }),
            })).json();
          } catch (e) { errors += batch.length; continue; }
          if (!r || r.status !== 'SUCCESS' || !Array.isArray(r.results)) { errors += batch.length; continue; }
          for (const res of r.results) {
            if (res.status === 'not_found') dead.push(res.username);
            else if (res.status === 'blocked') blocked++;
            else if (res.status !== 'active') errors++;
          }
          done += batch.length;
          logger.append(`[health] Checked ${done}/${names.length}… ${dead.length} dead so far.`);
        }
      } finally {
        checking = false;
        els.btnCheckHealth.disabled = false;
      }
      logger.append(`[health] Done: ${done} checked, ${dead.length} dead, ${blocked} rate-limited, ${errors} errors.`);
      if (blocked && !dead.length && !errors) {
        showToast('Instagram rate-limited the check — wait a few minutes and retry.', 'error');
        return;
      }
      if (!dead.length) {
        showToast(done ? `All ${done} checked accounts are alive${blocked || errors ? ` (${blocked} limited, ${errors} errors)` : ''}.` : 'Check finished with no results.', done ? 'success' : 'info');
        return;
      }
      const sample = dead.slice(0, 8).map((u) => `@${u}`).join(', ') + (dead.length > 8 ? `, +${dead.length - 8} more` : '');
      const flag = await MiModals.confirmDelete({
        title: 'Flag Dead Accounts',
        message: `Flag ${dead.length} dead account(s) as Damaged?`,
        subtext: 'Pool drains skip them and backups can exclude them. A snapshot is saved in backups/ first.',
        targetHtml: `<div style="font-size: 0.8rem; color: var(--text-dim); word-break: break-all;">${escapeHtml(sample)}</div>`,
        confirmText: 'Flag damaged',
      });
      if (!flag) return;
      const m = await (await fetch('/api/ig-mark-dead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usernames: dead }),
      })).json();
      if (m.status === 'SUCCESS') {
        showToast(`Flagged ${(m.marked || []).length} dead account(s)`, 'success');
        logger.append(`[health] Flagged ${(m.marked || []).length} dead account(s).`);
      } else {
        showToast(m.error || 'Flag failed.', 'error');
        logger.append('[health] Flag failed: ' + (m.error || 'unknown error'));
      }
      page = 1;
      await shared.refreshShared();
    });
  }

  if (els.btnPurge) {
    els.btnPurge.addEventListener('click', async () => {
      const bad = myAccounts().filter((a) => miIsDamaged(a));
      if (!bad.length) {
        showToast('No damaged accounts — this list is already clean.', 'success');
        return;
      }
      const names = bad.slice(0, 8).map((a) => `@${a.instagram_username || a.username || '?'}`).join(', ') +
        (bad.length > 8 ? `, +${bad.length - 8} more` : '');
      const confirmed = await MiModals.confirmDelete({
        title: 'Remove Damaged Accounts',
        message: `Delete ${bad.length} damaged Instagram account(s)?`,
        subtext: 'Only rows marked Damaged in the Health column (Failed / Banned / dead session / 3+ failed submits). Healthy accounts stay. A snapshot is saved in backups/ first.',
        targetHtml: `<div style="font-size: 0.8rem; color: var(--text-dim); word-break: break-all;">${escapeHtml(names)}</div>`,
        confirmText: 'Remove Damaged',
      });
      if (!confirmed) return;
      const r = await (await fetch('/api/meta-insta/purge-damaged', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'ig', confirm: 'CLEAR' }),
      })).json();
      if (r.status === 'SUCCESS') {
        showToast(r.removed ? `Removed ${r.removed} damaged account(s)` : 'Nothing to remove — list is clean', r.removed ? 'success' : 'info');
        logger.append(`[tracking] Removed ${r.removed || 0} damaged account(s).`);
      } else {
        showToast(r.error || 'Remove failed.', 'error');
        logger.append('[tracking] Remove damaged failed: ' + (r.error || 'unknown error'));
      }
      page = 1;
      await shared.refreshShared();
    });
  }

  if (els.btnClearLog) els.btnClearLog.addEventListener('click', () => logger.clear());
  if (els.btnCopyLog && els.log) {
    els.btnCopyLog.addEventListener('click', () => {
      const text = Array.from(els.log.children).map((c) => c.textContent).join('\n');
      navigator.clipboard.writeText(text).then(() => showToast('Log copied!', 'success'));
    });
  }

  if (els.btnDeepClean) {
    els.btnDeepClean.addEventListener('click', async () => {
      if (state.meta_running || state.ig_running) {
        showToast('Stop the engine before deep cleaning.', 'warning');
        return;
      }
      const confirmed = await MiModals.confirmDelete({
        title: 'Clean files',
        message: 'Remove orphaned sessions, cookies and dead creator profiles from disk?',
        subtext: 'Your saved account list is NOT touched. Nova browser profiles are never touched.',
        targetHtml: '',
        confirmText: 'Clean files',
      });
      if (!confirmed) return;
      try {
        const r = await (await fetch('/api/meta-insta/cleanup', { method: 'POST' })).json();
        if (r.status === 'SUCCESS') {
          const rem = r.removed || {};
          const summary = `sessions=${rem.sessions || 0}, cookies=${rem.cookies || 0}, profiles=${rem.profiles || 0}`;
          showToast(`Deep clean done (${summary}).`, 'success');
          logger.append(`[cleanup] Removed: ${summary}.`);
        } else {
          showToast(r.error || 'Deep clean failed.', 'error');
        }
      } catch (e) {
        showToast(e.message, 'error');
      }
      await shared.refreshShared();
    });
  }

  if (els.search) els.search.addEventListener('input', debounce(() => { page = 1; renderResults(); }, 200));
  if (els.perPage) els.perPage.addEventListener('change', () => { page = 1; renderResults(); });
  if (els.sort) els.sort.addEventListener('change', () => { currentSort = els.sort.value; page = 1; renderResults(); });

  root.querySelectorAll('[data-role="th"]').forEach((th) => {
    th.addEventListener('click', () => {
      const base = th.getAttribute('data-sort');
      if (base === 'newest') currentSort = currentSort === 'newest' ? 'oldest' : 'newest';
      else if (base === 'uname_asc') currentSort = currentSort === 'uname_asc' ? 'uname_desc' : 'uname_asc';
      else currentSort = currentSort === base ? 'newest' : base;
      if (els.sort) els.sort.value = currentSort;
      page = 1;
      renderResults();
    });
  });

  if (els.combo) {
    els.combo.addEventListener('click', () => {
      const link = document.createElement('a');
      link.href = `/api/meta-insta/export-combo?kind=${def.kind}`;
      link.download = `${def.kind}_combo.txt`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      showToast(`Exporting ${def.kind === 'ig' ? 'Instagram' : 'Meta'} combos…`, 'success');
    });
  }

  // Column visibility dropdown
  if (els.btnColToggle && els.colMenu) {
    els.btnColToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = els.colMenu.style.display === 'flex';
      els.colMenu.style.display = open ? 'none' : 'flex';
    });
    document.addEventListener('click', (e) => {
      if (els.colMenu && !els.colMenu.contains(e.target) && e.target !== els.btnColToggle && !els.btnColToggle.contains(e.target)) {
        els.colMenu.style.display = 'none';
      }
    });
    root.querySelectorAll('.metainsta-col-cb').forEach((cb) => {
      cb.addEventListener('change', () => {
        const checked = Array.from(root.querySelectorAll('.metainsta-col-cb:checked'));
        if (checked.length === 0) {
          cb.checked = true;
          showToast('At least one column must remain visible', 'warning');
          return;
        }
        localStorage.setItem(STORAGE_KEY_COLS, JSON.stringify(checked.map((c) => c.getAttribute('data-col'))));
        applyColumnVisibility();
        const emptyTd = els.resultsList.querySelector('.insta-empty-state')?.closest('td');
        if (emptyTd) emptyTd.setAttribute('colspan', String(getVisibleCols().length || 1));
      });
    });
    if (els.btnColsReset) {
      els.btnColsReset.addEventListener('click', (e) => {
        e.stopPropagation();
        localStorage.setItem(STORAGE_KEY_COLS, JSON.stringify(MI_ALL_COLS));
        applyColumnVisibility();
        const emptyTd = els.resultsList.querySelector('.insta-empty-state')?.closest('td');
        if (emptyTd) emptyTd.setAttribute('colspan', String(getVisibleCols().length || 1));
      });
    }
  }

  // Reactive updates
  let dirty = false;
  let paintRaf = null;
  function isVisible() {
    const panel = root.closest('.view-panel');
    return !panel || panel.classList.contains('active');
  }
  function schedulePaint() {
    if (paintRaf) return;
    paintRaf = requestAnimationFrame(() => {
      paintRaf = null;
      updateStats();
      if (isVisible()) { renderResults(); dirty = false; }
      else dirty = true;
    });
  }

  shared.subscribe(schedulePaint);

  function handleActivation() {
    if (isVisible()) {
      updateStats();
      renderResults();
      shared.refreshShared();
    } else {
      dirty = true;
    }
  }

  window.addEventListener('nova:view-changed', handleActivation);
  window.addEventListener('hashchange', () => requestAnimationFrame(handleActivation));

  const panelEl = root.closest('.view-panel');
  if (panelEl && typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.attributeName === 'class' && panelEl.classList.contains('active')) handleActivation();
      }
    });
    observer.observe(panelEl, { attributes: true, attributeFilter: ['class'] });
  }

  document.querySelectorAll('.nav-item[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => setTimeout(handleActivation, 30));
  });

  // Initial render
  updateStats();
  renderResults();

  return {
    def,
    root,
    appendLog: (line) => logger.append(line),
    setProgress: (d) => {
      if (els.progressLabel && d.detail) els.progressLabel.textContent = `Slot #${d.slot_id} — ${d.status}: ${d.detail}`;
    },
    logHasContent: () => logger.hasContent(),
  };
}

// =============================================================================
// 7. MAIN COORDINATOR & SSE (Entry: initMetaInsta)
// =============================================================================

function initMetaInsta() {
  const mounts = document.querySelectorAll('.creator-mount');
  if (!mounts.length) return;

  const state = {
    accounts: [],
    meta_running: false,
    ig_running: false,
    running: false,
    activeMode: null,
    engineOk: true,
    listeners: new Set(),
  };

  function isIgAccount(a) {
    if (!a || (a.target || '') === 'telegram') return false;
    return String(a.status || '') !== 'MetaCreated';
  }

  function notify() {
    state.listeners.forEach((fn) => { try { fn(); } catch (e) {} });
  }

  let refreshInFlight = null;
  function refreshShared() {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      try {
        const [s, acc] = await Promise.all([
          fetch('/api/meta-insta/status').then((r) => r.json()),
          fetch('/api/meta-insta/accounts').then((r) => r.json()),
        ]);
        state.meta_running = Boolean(s.meta_running !== undefined ? s.meta_running : (s.running && s.mode === 'meta'));
        state.ig_running = Boolean(s.ig_running !== undefined ? s.ig_running : (s.running && s.mode === 'meta-ig'));
        state.running = state.meta_running || state.ig_running;
        state.engineOk = s.engineOk !== false;
        if (s.mode === 'meta' || s.mode === 'meta-ig') state.activeMode = s.mode;
        state.accounts = ((acc && acc.accounts) || [])
          .filter((a) => String((a && a.target) || '') !== 'telegram');
      } catch (e) {
        state.running = false;
        state.meta_running = false;
        state.ig_running = false;
      } finally {
        refreshInFlight = null;
      }
      notify();
    })();
    return refreshInFlight;
  }

  // Initialize shared modals
  MiModals.initDeleteConfirm();
  const editModal = MiModals.initEditAccount(refreshShared);
  MiModals.initGlobalPassword();

  // Mount workspaces
  const workspaces = [];
  mounts.forEach((mount) => {
    const kind = mount.getAttribute('data-kind') || 'meta';
    if (!MI_WORKSPACE_DEFS[kind]) return;
    mount.innerHTML = miCreatorPanelHtml(MI_WORKSPACE_DEFS[kind]);
    workspaces.push(createCreatorWorkspace(mount, MI_WORKSPACE_DEFS[kind], state, {
      isIgAccount,
      refreshShared,
      editModal,
      subscribe: (fn) => { state.listeners.add(fn); return () => state.listeners.delete(fn); },
    }));
  });

  if (window.NovaDiag) {
    NovaDiag.refreshReasons();
    NovaDiag.refreshLogs();
  }

  function activeWorkspace() {
    let ws = workspaces.find((w) => w.def.mode === state.activeMode);
    if (!ws) {
      const visible = workspaces.find((w) => w.root.closest('.view-panel')?.classList.contains('active'));
      ws = visible || workspaces[0];
    }
    return ws;
  }

  // SSE Event Stream
  let es = null;
  function handleSseEvent(d) {
    if (d && (d.pipeline === 'telegram' || d.engine === 'tg')) return;

    const targetWs = (d.engine === 'ig' || d.mode === 'meta-ig')
      ? workspaces.find((w) => w.def.kind === 'ig')
      : (d.engine === 'meta' || d.mode === 'meta' || d.mode === 'meta-only')
        ? workspaces.find((w) => w.def.kind === 'meta')
        : activeWorkspace();

    if (d.type === 'log') {
      if (targetWs) targetWs.appendLog(d.message || '');
    } else if (d.type === 'loop_started') {
      const mode = d.mode === 'meta-ig' ? 'meta-ig' : 'meta';
      if (mode === 'meta-ig') state.ig_running = true;
      else state.meta_running = true;
      state.running = state.meta_running || state.ig_running;
      if (targetWs) targetWs.appendLog(`[engine] Started ${d.concurrency || ''} session(s).`);
      notify();
    } else if (d.type === 'loop_stopped') {
      if (d.engine === 'ig' || d.mode === 'meta-ig') state.ig_running = false;
      else if (d.engine === 'meta' || d.mode === 'meta' || d.mode === 'meta-only') state.meta_running = false;
      else {
        state.meta_running = false;
        state.ig_running = false;
      }
      state.running = state.meta_running || state.ig_running;
      if (targetWs) targetWs.appendLog('[engine] Stopped.');
      refreshShared();
    } else if (d.type === 'status') {
      if (d.engine === 'ig' || d.mode === 'meta-ig') {
        state.ig_running = Boolean(d.running);
      } else if (d.engine === 'meta' || d.mode === 'meta' || d.mode === 'meta-only') {
        state.meta_running = Boolean(d.running);
      } else if (d.meta_running !== undefined || d.ig_running !== undefined) {
        if (d.meta_running !== undefined) state.meta_running = Boolean(d.meta_running);
        if (d.ig_running !== undefined) state.ig_running = Boolean(d.ig_running);
      } else {
        state.running = Boolean(d.running);
      }
      state.running = state.meta_running || state.ig_running;
      notify();
    } else if (d.type === 'slot_event') {
      if (targetWs) {
        targetWs.appendLog(`[Slot #${d.slot_id}] ${d.status}: ${d.detail || ''}`);
        targetWs.setProgress(d);
      }
      if (d.status === 'closed' || d.status === 'error') refreshShared();
    } else if (d.type === 'account_created') {
      if (targetWs) targetWs.appendLog(`[✔] Created: ${d.account?.username || d.account?.email || d.email || ''}`);
      refreshShared();
    } else if (d.type === 'license_invalid') {
      state.running = false;
      state.meta_running = false;
      state.ig_running = false;
      if (targetWs) targetWs.appendLog(`[License Error] ${d.message || 'Active license required.'}`);
      showToast(d.message || 'Active license required.', 'error');
      if (typeof requireLicense === 'function') requireLicense(d.message || 'Active license required to run the creator.');
      refreshShared();
    } else if (d.type === 'account_updated' || d.type === 'accounts_reset' || d.type === 'account_deleted') {
      refreshShared();
    }
  }

  function connectSse() {
    // Shared SSE hub (nova-core.js): one stream per page. Falls back to a
    // private stream only if the hub is unavailable (stale cached core).
    try {
      if (!window.__miEsShared && typeof window.__novaEsSubscribe === 'function') {
        window.__miEsShared = true;
        window.__novaEsSubscribe(handleSseEvent);
        return;
      }
      if (typeof window.__novaEsSubscribe !== 'function') {
        try { if (es) es.close(); } catch (e) {}
        es = new EventSource('/api/meta-insta/events');
        es.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d && d.type === 'batch' && Array.isArray(d.items)) {
              for (const item of d.items) {
                try { handleSseEvent(item); } catch (err) {}
              }
              return;
            }
            handleSseEvent(d);
          } catch (err) {
            const ws = activeWorkspace();
            if (ws) ws.appendLog(e.data);
          }
        };
        es.onerror = () => {};
      }
    } catch (e) {}
  }

  refreshShared();
  connectSse();
  setInterval(() => { if (!document.hidden) refreshShared(); }, 10000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshShared(); });

  if (workspaces[0] && !workspaces[0].logHasContent()) {
    workspaces[0].appendLog('[system] Creator engine ready. Pick a workspace, set Parallel + Target and click Start.');
  }
}
