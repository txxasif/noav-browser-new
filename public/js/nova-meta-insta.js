/**
 * Nova Browser UI — Creator workspaces.
 *
 * The dashboard exposes two independent workspaces built from ONE factory:
 *   • Meta Creator       (mode = "meta")    → Meta-only accounts
 *   • Instagram Creator  (mode = "meta-ig") → Meta account + Instagram join
 *
 * Each workspace owns its controls, stats, results table, pagination and log.
 * Shared concerns (accounts state, SSE stream, delete/edit modals, global
 * password, license) live in initMetaInsta() so both stay in sync without
 * duplicating work.
 */

const MI_WORKSPACE_DEFS = {
  meta: {
    kind: 'meta',
    mode: 'meta',
    title: 'Meta Account Creator',
    subtitle: 'Create Meta (Facebook) accounts in an anti-detect browser. No Instagram join.',
    accent: '#0081fb',
    icon: 'fa-brands fa-meta',
    countLabel: 'Meta Accounts',
    countSub: 'Meta-only accounts created',
    savedSub: 'JSON + CSV + TXT',
    usernameLabel: 'New username (optional)',
    usernamePlaceholder: 'leave empty = auto',
    startLabel: 'Start Creating Meta',
    flowHint: 'Flow: Meta signup → verify → save credentials.',
  },
  ig: {
    kind: 'ig',
    mode: 'meta-ig',
    title: 'Instagram Account Creator',
    subtitle: 'Create a Meta account, then join Instagram in the same anti-detect session.',
    accent: '#f472b6',
    icon: 'fa-brands fa-instagram',
    countLabel: 'Instagram Accounts',
    countSub: 'Accounts with an Instagram session',
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
    ['password', 'Password'], ['created', 'Created'], ['actions', 'Actions'],
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
        <button type="button" class="btn btn-secondary btn-sm" data-role="export-csv"><i class="fa-solid fa-file-csv"></i> Export CSV</button>
        <button type="button" class="btn btn-secondary btn-sm" data-role="export-txt"><i class="fa-solid fa-file-lines"></i> Export TXT</button>
        <button type="button" class="btn btn-secondary btn-sm" data-role="clear"><i class="fa-solid fa-trash-can"></i> Clear</button>
        <button type="button" class="btn btn-secondary btn-sm" data-role="deep-clean" title="Delete orphaned session files, cookies and dead creator profiles (keeps saved accounts)"><i class="fa-solid fa-broom"></i> Deep Clean</button>
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
        <input type="number" class="form-control" data-role="concurrency" min="1" max="50" value="1">
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
          <label class="creator-option" title="Visual challenge first via in-browser YOLOv5 ONNX AI extension, automatic fallback to Audio STT">
            <input type="radio" name="mi-captcha-${k}" value="extension" checked>
            <i class="fa-solid fa-eye" style="color: var(--accent-green);"></i> Visual AI (JA) <span class="creator-option-hint">(→ Audio fallback)</span>
          </label>
          <label class="creator-option" title="Audio challenge first via Whisper / Vosk speech recognition, automatic fallback to Visual AI">
            <input type="radio" name="mi-captcha-${k}" value="audio">
            <i class="fa-solid fa-headphones" style="color: var(--accent-purple);"></i> Audio (Whisper) <span class="creator-option-hint">(→ Visual fallback)</span>
          </label>
        </div>
        <div class="creator-service-note">Visual AI is the default; audio is used automatically if the visual solver stalls.</div>
      </div>

      <div class="creator-engine-card">
        <div class="creator-engine-icon" style="background: linear-gradient(135deg, ${def.accent}, #0064e0);">
          <i class="${def.icon}"></i>
        </div>
        <div class="creator-engine-text">
          <div class="creator-engine-title">
            Meta Anti-Detect Core
            <span class="creator-engine-badge"><span class="creator-engine-dot"></span> Ready</span>
          </div>
          <div class="creator-engine-sub">JA Visual AI (YOLOv5 ONNX) • Mobile Fingerprint • Offline Engine</div>
        </div>
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
  </div>`;
}

function initMetaInsta() {
  const mounts = document.querySelectorAll('.creator-mount');
  if (!mounts.length) return;

  // ---------------------------------------------------------------------------
  // Shared state + data layer (one poll / one SSE for both workspaces)
  // ---------------------------------------------------------------------------
  const state = {
    accounts: [],
    running: false,
    activeMode: null,
    engineOk: true,
    listeners: new Set(),
  };

  function isIgAccount(a) {
    // Instagram workspace = anything that went through the IG join (parked as
    // Created/Submitted/Verified). Meta workspace = MetaCreated only.
    return String((a && a.status) || '') !== 'MetaCreated';
  }

  function notify() {
    state.listeners.forEach((fn) => { try { fn(); } catch (e) {} });
  }

  let refreshInFlight = null;
  function refreshShared() {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      try {
        // Fetch status + accounts in parallel (halves poll latency).
        const [s, acc] = await Promise.all([
          fetch('/api/meta-insta/status').then((r) => r.json()),
          fetch('/api/meta-insta/accounts').then((r) => r.json()),
        ]);
        state.running = Boolean(s.running);
        state.engineOk = s.engineOk !== false;
        if (s.mode === 'meta' || s.mode === 'meta-ig') state.activeMode = s.mode;
        if (!state.running) state.activeMode = null;
        else if (!state.activeMode) state.activeMode = 'meta';
        state.accounts = (acc && acc.accounts) || [];
      } catch (e) {
        state.running = false;
      } finally {
        refreshInFlight = null;
      }
      notify();
    })();
    return refreshInFlight;
  }

  // ---------------------------------------------------------------------------
  // Shared delete-confirm modal (promise based)
  // ---------------------------------------------------------------------------
  const confirmDeleteModal = document.getElementById('modal-metainsta-confirm-delete');
  const deleteModalTitle = document.getElementById('metainsta-delete-modal-title');
  const deleteModalMsg = document.getElementById('metainsta-delete-modal-msg');
  const deleteModalSub = document.getElementById('metainsta-delete-modal-sub');
  const deleteModalTargetBox = document.getElementById('metainsta-delete-modal-target-box');
  const deleteModalTargetText = document.getElementById('metainsta-delete-modal-target-text');
  const deleteModalBtnSubmit = document.getElementById('btn-metainsta-confirm-delete-submit');
  let pendingDeleteResolver = null;

  function showDeleteConfirmModal({ title, message, subtext, targetHtml, confirmText = 'Confirm Delete' } = {}) {
    return new Promise((resolve) => {
      if (!confirmDeleteModal) {
        resolve(window.confirm(message || 'Are you sure you want to delete?'));
        return;
      }
      if (pendingDeleteResolver) pendingDeleteResolver(false);
      pendingDeleteResolver = resolve;

      if (deleteModalTitle) deleteModalTitle.textContent = title || 'Delete Account';
      if (deleteModalMsg) deleteModalMsg.textContent = message || 'Are you sure you want to delete this account?';
      if (deleteModalSub) deleteModalSub.textContent = subtext || 'This action cannot be undone.';
      if (deleteModalTargetText) deleteModalTargetText.innerHTML = targetHtml || '';
      if (deleteModalTargetBox) deleteModalTargetBox.style.display = targetHtml ? 'block' : 'none';
      if (deleteModalBtnSubmit) deleteModalBtnSubmit.innerHTML = `<i class="fa-solid fa-trash-can"></i> ${confirmText}`;
      openModal(confirmDeleteModal);
    });
  }

  function resolveDeleteConfirm(value) {
    if (pendingDeleteResolver) {
      const res = pendingDeleteResolver;
      pendingDeleteResolver = null;
      res(value);
    }
  }

  if (deleteModalBtnSubmit) {
    deleteModalBtnSubmit.addEventListener('click', () => {
      resolveDeleteConfirm(true);
      if (confirmDeleteModal) closeModal(confirmDeleteModal);
    });
  }
  if (confirmDeleteModal) {
    confirmDeleteModal.querySelectorAll('[data-close], .close-modal').forEach((b) => {
      b.addEventListener('click', () => resolveDeleteConfirm(false));
    });
    confirmDeleteModal.addEventListener('click', (e) => {
      if (e.target === confirmDeleteModal) resolveDeleteConfirm(false);
    });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && confirmDeleteModal && confirmDeleteModal.classList.contains('active')) {
      resolveDeleteConfirm(false);
    }
  });

  // ---------------------------------------------------------------------------
  // Shared edit-account modal
  // ---------------------------------------------------------------------------
  const editModal = document.getElementById('modal-metainsta-edit');
  const editForm = document.getElementById('form-metainsta-edit');
  if (editForm) {
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
          await refreshShared();
        } else {
          showToast(r.error || 'Update failed.', 'error');
        }
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Shared global password modal
  // ---------------------------------------------------------------------------
  const gpStatus = document.getElementById('global-pass-status');
  const gpModal = document.getElementById('modal-global-password');
  const gpForm = document.getElementById('form-global-password');
  const gpInput = document.getElementById('input-global-password');
  const gpBtn = document.getElementById('nav-item-global-pass');

  function renderGlobalPassStatus(pass) {
    if (!gpStatus) return;
    const isSet = Boolean(pass);
    gpStatus.textContent = isSet ? 'Set' : 'Not set';
    gpStatus.style.background = isSet ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)';
    gpStatus.style.color = isSet ? '#34d399' : '#94a3b8';
  }

  async function loadGlobalPass() {
    try {
      const r = await (await fetch('/api/meta-insta/settings')).json();
      const pass = (r && r.globalPassword) || '';
      if (gpInput) gpInput.value = pass;
      renderGlobalPassStatus(pass);
    } catch (e) {}
  }

  if (gpBtn && gpModal) {
    gpBtn.addEventListener('click', async () => { await loadGlobalPass(); openModal(gpModal); });
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
          renderGlobalPassStatus(pass);
          closeModal(gpModal);
          showToast(pass ? 'Global password saved.' : 'Global password cleared — auto passwords.', 'success');
        } else {
          showToast((r && r.error) || 'Could not save global password.', 'error');
        }
      } catch (err) {
        showToast('Could not save global password: ' + err.message, 'error');
      }
    });
  }
  loadGlobalPass();

  // ---------------------------------------------------------------------------
  // Build one workspace per mount
  // ---------------------------------------------------------------------------
  const workspaces = [];
  mounts.forEach((mount) => {
    const kind = mount.getAttribute('data-kind') === 'ig' ? 'ig' : 'meta';
    mount.innerHTML = miCreatorPanelHtml(MI_WORKSPACE_DEFS[kind]);
    workspaces.push(createCreatorWorkspace(mount, MI_WORKSPACE_DEFS[kind], state, {
      isIgAccount,
      refreshShared,
      showDeleteConfirmModal,
      editModal,
      subscribe: (fn) => { state.listeners.add(fn); return () => state.listeners.delete(fn); },
    }));
  });

  // ---------------------------------------------------------------------------
  // Shared SSE stream — routes log lines to the active workspace
  // ---------------------------------------------------------------------------
  function activeWorkspace() {
    let ws = workspaces.find((w) => w.def.mode === state.activeMode);
    if (!ws) {
      const visible = workspaces.find((w) => w.root.closest('.view-panel')?.classList.contains('active'));
      ws = visible || workspaces[0];
    }
    return ws;
  }

  let es = null;
  function handleSseEvent(d) {
    const ws = activeWorkspace();
    if (d.type === 'log') {
      if (ws) ws.appendLog(d.message || '');
    } else if (d.type === 'loop_started') {
      state.running = true;
      state.activeMode = d.mode === 'meta-ig' ? 'meta-ig' : 'meta';
      if (ws) ws.appendLog(`[engine] Started ${d.concurrency || ''} session(s).`);
      notify();
    } else if (d.type === 'loop_stopped') {
      state.running = false;
      state.activeMode = null;
      if (ws) ws.appendLog('[engine] Stopped.');
      refreshShared();
    } else if (d.type === 'status') {
      state.running = Boolean(d.running);
      if (d.mode) state.activeMode = d.mode;
      if (!state.running) state.activeMode = null;
      else if (!state.activeMode) state.activeMode = 'meta';
      notify();
    } else if (d.type === 'slot_event') {
      if (ws) {
        ws.appendLog(`[Slot #${d.slot_id}] ${d.status}: ${d.detail || ''}`);
        ws.setProgress(d);
      }
    } else if (d.type === 'account_created') {
      if (ws) ws.appendLog(`[✔] Created: ${d.account?.instagram_username || d.account?.email || d.email || ''}`);
      refreshShared();
    } else if (d.type === 'license_invalid') {
      state.running = false;
      if (ws) ws.appendLog(`[License Error] ${d.message || 'Active license required.'}`);
      showToast(d.message || 'Active license required.', 'error');
      if (typeof requireLicense === 'function') requireLicense(d.message || 'Active license required to run the creator.');
      refreshShared();
    } else if (d.type === 'account_updated' || d.type === 'accounts_reset' || d.type === 'account_deleted') {
      refreshShared();
    }
  }

  function connectSse() {
    try { if (es) es.close(); } catch (e) {}
    es = new EventSource('/api/meta-insta/events');
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        // Server coalesces log/slot_event bursts into one 'batch' frame.
        if (d && d.type === 'batch' && Array.isArray(d.items)) {
          for (const item of d.items) {
            try { handleSseEvent(item); } catch (err) { /* keep the batch going */ }
          }
          return;
        }
        handleSseEvent(d);
      } catch (err) {
        const ws = activeWorkspace();
        if (ws) ws.appendLog(e.data);
      }
    };
    es.onerror = () => { /* browser auto-reconnects */ };
  }

  refreshShared();
  connectSse();
  // Poll as a safety net only: skip while the tab is hidden and refresh
  // immediately when it becomes visible again. SSE keeps live runs fresh.
  setInterval(() => { if (!document.hidden) refreshShared(); }, 10000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshShared(); });

  // Warn the user (once) if the engine files are missing.
  if (workspaces[0] && !workspaces[0].logHasContent()) {
    workspaces[0].appendLog('[system] Creator engine ready. Pick a workspace, set Parallel + Target and click Start.');
  }
}

/**
 * Build and wire a single creator workspace inside `root`.
 * Returns { def, root, appendLog, setProgress, logHasContent }.
 */
function createCreatorWorkspace(root, def, state, shared) {
  const q = (role) => root.querySelector(`[data-role="${role}"]`);
  const els = {
    conc: q('concurrency'),
    target: q('target'),
    headless: q('headless'),
    username: q('username'),
    btnStart: q('start'),
    btnStop: q('stop'),
    btnExportCsv: q('export-csv'),
    btnExportTxt: q('export-txt'),
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

  const ALL_COLS = ['id', 'uname', 'name', 'email', 'password', 'created', 'actions'];
  const STORAGE_KEY_COLS = `nova_metainsta_cols_${def.kind}`;

  let page = 1;
  let currentSort = 'newest';

  // --- columns ---------------------------------------------------------------
  function getStoredVisibleCols() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_COLS);
      if (stored) {
        const arr = JSON.parse(stored);
        if (Array.isArray(arr) && arr.length > 0) {
          const known = arr.filter((c) => ALL_COLS.includes(c));
          return [...known, ...ALL_COLS.filter((c) => !known.includes(c))];
        }
      }
    } catch (e) {}
    return ALL_COLS.slice();
  }
  function saveVisibleCols(cols) {
    try { localStorage.setItem(STORAGE_KEY_COLS, JSON.stringify(cols)); } catch (e) {}
  }
  function applyColumnVisibility() {
    const visible = getStoredVisibleCols();
    if (!els.table) return;
    ALL_COLS.forEach((col) => {
      els.table.classList.toggle(`hide-col-${col}`, !visible.includes(col));
      const cb = root.querySelector(`.metainsta-col-cb[data-col="${col}"]`);
      if (cb) cb.checked = visible.includes(col);
    });
  }
  function getVisibleColCount() {
    return getStoredVisibleCols().length || 1;
  }
  applyColumnVisibility();

  // --- logging ---------------------------------------------------------------
  // Batched rendering: worker logs arrive in bursts (one SSE line per slot
  // stdout line). Appending each line synchronously to a growing text node
  // reflowed the whole terminal and froze the UI at high Parallel. We buffer
  // lines and flush once per animation frame, and cap the DOM to N rows.
  const LOG_MAX_LINES = 600;
  let logQueue = [];
  let logRaf = null;
  function appendLog(line) {
    if (!els.log) return;
    logQueue.push(line);
    if (logRaf) return;
    logRaf = requestAnimationFrame(flushLog);
  }
  function flushLog() {
    logRaf = null;
    if (!els.log || logQueue.length === 0) return;
    const auto = els.autoScroll ? els.autoScroll.checked : true;
    const frag = document.createDocumentFragment();
    for (const l of logQueue) {
      const row = document.createElement('div');
      row.textContent = l;
      frag.appendChild(row);
    }
    logQueue = [];
    els.log.appendChild(frag);
    while (els.log.childElementCount > LOG_MAX_LINES) els.log.removeChild(els.log.firstChild);
    if (auto) els.log.scrollTop = els.log.scrollHeight;
  }
  function logHasContent() {
    return Boolean(els.log && (els.log.textContent || '').trim());
  }
  function setProgress(d) {
    if (els.progressLabel && d.detail) els.progressLabel.textContent = `Slot #${d.slot_id} — ${d.status}: ${d.detail}`;
  }

  // --- stats -----------------------------------------------------------------
  function myAccounts() {
    return state.accounts.filter((a) => (def.kind === 'ig') === shared.isIgAccount(a));
  }
  function updateStats() {
    const mine = myAccounts();
    if (els.statTotal) els.statTotal.textContent = String(mine.length);
    if (els.statCreated) els.statCreated.textContent = String(mine.length);
    if (els.badgeAll) els.badgeAll.textContent = String(mine.length);

    // Sidebar badges
    const badgeMeta = document.getElementById('metainsta-badge-meta');
    const badgeIg = document.getElementById('metainsta-badge-ig');
    if (badgeMeta) badgeMeta.textContent = String(state.accounts.filter((a) => !shared.isIgAccount(a)).length);
    if (badgeIg) badgeIg.textContent = String(state.accounts.filter((a) => shared.isIgAccount(a)).length);

    const isMine = state.activeMode === def.mode;
    const runningHere = state.running && isMine;
    const busyElsewhere = state.running && !isMine;

    if (els.statRunning) {
      els.statRunning.textContent = runningHere ? 'RUNNING' : (busyElsewhere ? 'BUSY' : 'IDLE');
      els.statRunning.style.color = runningHere ? 'var(--accent-green)' : (busyElsewhere ? '#fcd34d' : 'var(--text-muted)');
    }
    if (els.state) {
      els.state.textContent = runningHere ? 'RUNNING' : (busyElsewhere ? 'OTHER WORKSPACE ACTIVE' : 'IDLE');
      els.state.style.color = runningHere ? 'var(--accent-green)' : (busyElsewhere ? '#fcd34d' : 'var(--text-muted)');
    }
    if (els.btnStart) {
      els.btnStart.disabled = !state.engineOk || busyElsewhere;
      els.btnStart.style.display = runningHere ? 'none' : 'inline-flex';
      els.btnStart.title = !state.engineOk ? 'Mining engine not installed on this machine'
        : busyElsewhere ? 'The other workspace is currently running.' : '';
    }
    if (els.btnStop) els.btnStop.style.display = runningHere ? 'inline-flex' : 'none';
    if (els.progressBox) els.progressBox.style.display = runningHere ? 'block' : 'none';
    if (els.engineHint) els.engineHint.style.display = state.engineOk ? 'none' : 'inline';
  }

  // --- sorting / filtering ---------------------------------------------------
  function updateSortIndicators() {
    const icons = {
      'sort-icon-id': '⇅', 'sort-icon-uname': '⇅', 'sort-icon-name': '⇅',
      'sort-icon-email': '⇅', 'sort-icon-created': '⇅',
    };
    const active = {
      'sort-icon-id': { color: '', opacity: '0.4' },
      'sort-icon-uname': { color: '', opacity: '0.4' },
      'sort-icon-name': { color: '', opacity: '0.4' },
      'sort-icon-email': { color: '', opacity: '0.4' },
      'sort-icon-created': { color: '', opacity: '0.4' },
    };
    const mark = (id, char) => { icons[id] = char; active[id] = { color: 'var(--accent-purple)', opacity: '1' }; };
    if (currentSort === 'newest') { mark('sort-icon-id', '▼'); mark('sort-icon-created', '▼'); }
    else if (currentSort === 'oldest') { mark('sort-icon-id', '▲'); mark('sort-icon-created', '▲'); }
    else if (currentSort === 'uname_asc') mark('sort-icon-uname', '▲');
    else if (currentSort === 'uname_desc') mark('sort-icon-uname', '▼');
    else if (currentSort === 'name_asc') mark('sort-icon-name', '▲');
    else if (currentSort === 'email_asc') mark('sort-icon-email', '▲');

    for (const [role, char] of Object.entries(icons)) {
      const el = q(role);
      if (el) {
        el.textContent = char;
        el.style.color = active[role].color;
        el.style.opacity = active[role].opacity;
      }
    }
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

  function comboOf(a) {
    const u = a.instagram_username || a.username || '';
    const p = a.password || '';
    return a.twofa_secret ? `${u}|${p}|${a.twofa_secret}` : `${u}|${p}`;
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
      els.resultsList.innerHTML = `
        <tr><td colspan="${getVisibleColCount()}"><div class="insta-empty-state">
          <i class="fa-solid fa-wand-magic-sparkles" style="font-size: 2rem; color: var(--text-muted); opacity: 0.5; margin-bottom: 0.5rem;"></i>
          <p>No accounts yet. Set Parallel + Target and click <strong>${def.startLabel}</strong>.</p>
        </div></td></tr>`;
    } else {
      els.resultsList.innerHTML = slice.map((a, i) => {
        const n = start + i + 1;
        const u = a.instagram_username || a.username || '';
        const masked = (a.password || '').replace(/.(?=.{3})/g, '•');
        return `
        <tr>
          <td data-col="id" style="color: var(--text-muted); font-variant-numeric: tabular-nums;" title="Original Order: #${a._origIndex}">${n}</td>
          <td data-col="uname" class="mono"><span>${escapeHtml(u || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copyuname="${a.id}" title="Copy username" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-copy"></i></button></td>
          <td data-col="name">${escapeHtml(a.name || '—')}</td>
          <td data-col="email" class="mono"><span>${escapeHtml(a.email || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copyemail="${a.id}" title="Copy email" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-copy"></i></button></td>
          <td data-col="password" class="mono"><span title="Use Copy for the full combo">${escapeHtml(masked || '—')}</span> <button type="button" class="btn btn-secondary btn-sm" data-copypass="${a.id}" title="Copy password" style="padding: 0.15rem 0.45rem;"><i class="fa-solid fa-copy"></i></button></td>
          <td data-col="created" style="color: var(--text-muted); font-size: 0.78rem; white-space: nowrap;">${escapeHtml(a.created_at || '—')}</td>
          <td data-col="actions"><div class="metainsta-actions">
            <button type="button" class="btn btn-primary btn-sm" data-open-meta="${a.id}" title="Open persisted Meta session (auth.meta.com)${a.metaPersisted === false ? ' — no persisted profile, cookies only' : ''}"><i class="fa-brands fa-meta"></i> Meta</button>
            ${((a.mail_provider || 'mailtd') !== 'mailtd' || a.mailPersisted === false) ? '' : `<button type="button" class="btn btn-secondary btn-sm" data-open-mail="${a.id}" title="Open persisted mail inbox (mail.td)"><i class="fa-solid fa-envelope"></i> Mail</button>`}
            <button type="button" class="btn btn-secondary btn-sm" data-copy="${a.id}" title="Copy uname|pass|token"><i class="fa-solid fa-copy"></i></button>
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

  // Single delegated click handler for the results table — one listener for the
  // whole tbody instead of ~7 per row on every render (less GC, faster paint).
  let rowsDelegated = false;
  function wireRowButtons() {
    if (rowsDelegated || !els.resultsList) return;
    rowsDelegated = true;
    els.resultsList.addEventListener('click', (ev) => {
      const btn = ev.target.closest('button[data-del],button[data-copy],button[data-copypass],button[data-copyuname],button[data-copyemail],button[data-cookie],button[data-edit],button[data-open-meta],button[data-open-mail]');
      if (!btn) return;
      const d = btn.dataset;
      if (d.del !== undefined) { handleDelete(d.del); return; }
      if (d.copy !== undefined) { handleCopy(d.copy); return; }
      if (d.copypass !== undefined) { handleCopyField(d.copypass, 'password'); return; }
      if (d.copyuname !== undefined) { handleCopyField(d.copyuname, 'username'); return; }
      if (d.copyemail !== undefined) { handleCopyField(d.copyemail, 'email'); return; }
      if (d.cookie !== undefined) { handleCookieExport(d.cookie, btn); return; }
      if (d.edit !== undefined) { handleEdit(d.edit); return; }
      if (d.openMeta !== undefined) { openMetaInstaAccount(d.openMeta, 'meta'); return; }
      if (d.openMail !== undefined) { openMetaInstaAccount(d.openMail, 'mail'); return; }
    });
  }

  async function handleDelete(id) {
    const a = findAccount(id);
    const uname = (a && (a.instagram_username || a.username)) || 'Unknown';
    const email = (a && a.email) || 'N/A';
    const name = (a && a.name) || '';
    const targetHtml = `
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div><strong style="color: var(--text-main);">Username:</strong> <span style="color: #60a5fa;">@${escapeHtml(uname)}</span></div>
        <div><strong style="color: var(--text-main);">Email:</strong> <span>${escapeHtml(email)}</span></div>
        ${name ? `<div><strong style="color: var(--text-main);">Name:</strong> <span>${escapeHtml(name)}</span></div>` : ''}
        <div style="font-size: 0.72rem; color: var(--text-dim); margin-top: 3px;"><strong>Record ID:</strong> ${escapeHtml(id)}</div>
      </div>`;
    const confirmed = await shared.showDeleteConfirmModal({
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
        body: JSON.stringify({ id }),
      });
      if (res.ok) {
        showToast(`Account @${uname} deleted`, 'success');
        appendLog(`[storage] Deleted account @${uname} (${id}).`);
      } else {
        showToast('Failed to delete account', 'error');
      }
    } catch (err) {
      showToast('Error deleting account: ' + err.message, 'error');
    }
    await shared.refreshShared();
  }

  function handleCopy(id) {
    const a = findAccount(id);
    if (!a) return;
    navigator.clipboard.writeText(comboOf(a)).then(() => showToast('Copied uname|pass|token!', 'success'));
  }

  function handleCopyField(id, field) {
    const a = findAccount(id);
    if (!a) return;
    let value = '';
    if (field === 'password') value = a.password || '';
    else if (field === 'username') value = a.instagram_username || a.username || '';
    else value = a.email || '';
    navigator.clipboard.writeText(value).then(() => showToast(`${field.charAt(0).toUpperCase() + field.slice(1)} copied!`, 'success'));
  }

  async function handleCookieExport(id, btn) {
    const a = findAccount(id);
    btn.disabled = true;
    try {
      const r = await (await fetch(`/api/meta-insta/cookies?id=${encodeURIComponent(id)}`)).json();
      if (!r || r.status !== 'SUCCESS' || !Array.isArray(r.cookies) || r.cookies.length === 0) {
        showToast('No saved cookies for this account.', 'warning');
        return;
      }
      const uname = (a && (a.instagram_username || a.username)) || id;
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

  function handleEdit(id) {
    const a = findAccount(id);
    if (!a || !shared.editModal) return;
    document.getElementById('metainsta-edit-id').value = a.id;
    document.getElementById('metainsta-edit-username').value = a.instagram_username || a.username || '';
    const passEl = document.getElementById('metainsta-edit-password');
    passEl.value = '';
    passEl.placeholder = 'Leave empty to keep current';
    document.getElementById('metainsta-edit-email').value = a.email || '';
    document.getElementById('metainsta-edit-name').value = a.name || '';
    openModal(shared.editModal);
  }

  /** Open one persisted site (Meta or mail) — separate clicks, separate sessions. */
  async function openMetaInstaAccount(id, site) {
    site = site === 'mail' ? 'mail' : 'meta';
    if (!requireLicense('Active license key required to open browser profiles.')) return;
    const flightKey = `meta-open:${id}:${site}`;
    if (typeof tryClaimLaunch === 'function' && !tryClaimLaunch(flightKey)) {
      showToast('This session is already opening — please wait.', 'info');
      return;
    }
    try {
      showToast(`Loading persisted ${site === 'mail' ? 'mail inbox' : 'Meta session'}...`, 'info');
      let data;
      try {
        data = await (await fetch('/api/meta-insta/open', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, site }),
        })).json();
      } catch (e) {
        showToast(`Failed to load account: ${e.message}`, 'error');
        return;
      }
      if (!data || data.status !== 'SUCCESS') {
        showToast((data && data.error) || 'Account not found.', 'error');
        return;
      }
      const cookies = Array.isArray(data.cookies) ? data.cookies : [];
      const url = data.url || (site === 'mail' ? 'https://mail.td/' : 'https://auth.meta.com/');
      let profile = typeof findProfileById === 'function' ? findProfileById(data.profileId) : null;
      if (!profile) {
        profile = FingerprintGenerator.generateProfile({
          name: data.profileName || 'Meta account',
          type: 'ANDROID_MOBILE',
          customUrl: url,
        });
        profile.id = data.profileId;
      }
      profile.name = data.profileName || profile.name;
      profile.cookies = cookies;
      profile.customUrl = url;
      ProfileManager.saveProfile(profile);
      if (typeof renderProfiles === 'function') renderProfiles();
      const extra = data.seeded ? 'persisted profile restored, ' : (data.persisted ? '' : 'no persisted profile, cookies only, ');
      showToast(`Opening ${profile.name} (${extra}${cookies.length} cookies, ${site} tab)...`, 'info');
      const out = await (await fetch('/api/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile: { ...profile, forceMobile: true }, url: [url], isSiteLauncher: false }),
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

  // --- controls --------------------------------------------------------------
  els.btnStart.addEventListener('click', async () => {
    if (!requireLicense('Active license key required to create accounts.')) return;
    if (state.running) {
      showToast(state.activeMode === def.mode ? 'This workspace is already running.' : 'The other workspace is running — stop it first.', 'info');
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
        state.running = true;
        state.activeMode = def.mode;
        showToast(r.message || 'Creator started.', 'success');
        appendLog(`[controller] ${r.message || 'started'}`);
      } else {
        if (r.status === 'UNLICENSED' && typeof requireLicense === 'function') {
          requireLicense(r.error || 'Active license key required to create accounts.');
        }
        showToast(r.error || 'Failed to start.', 'error');
        appendLog(`[controller] ${r.error || 'start failed'}`);
      }
    } finally {
      els.btnStart.disabled = false;
    }
    await shared.refreshShared();
  });

  let stopBusy = false;
  els.btnStop.addEventListener('click', async () => {
    if (stopBusy) return;
    if (!state.running) {
      showToast('Engine is not running.', 'info');
      return;
    }
    stopBusy = true;
    try {
      await fetch('/api/meta-insta/stop', { method: 'POST' });
      state.running = false;
      state.activeMode = null;
      appendLog('[controller] Stop requested.');
    } finally {
      stopBusy = false;
    }
    await shared.refreshShared();
  });

  if (els.btnExportCsv) els.btnExportCsv.addEventListener('click', () => { window.location = `/api/meta-insta/export?format=csv&kind=${def.kind}`; });
  if (els.btnExportTxt) els.btnExportTxt.addEventListener('click', () => { window.location = `/api/meta-insta/export?format=txt&kind=${def.kind}`; });

  if (els.btnClear) {
    els.btnClear.addEventListener('click', async () => {
      const count = state.accounts.length;
      const confirmed = await shared.showDeleteConfirmModal({
        title: 'Clear All Accounts',
        message: `Are you sure you want to clear ALL ${count} accounts?`,
        subtext: 'This affects both the Meta and Instagram workspaces. A snapshot is saved in backups/ first.',
        targetHtml: count > 0 ? `<div><strong style="color: #f87171;">Warning:</strong> You are about to clear <strong style="color:#fff;">${count}</strong> registered account(s).</div>` : '',
        confirmText: 'Clear All Accounts',
      });
      if (!confirmed) return;
      await fetch('/api/meta-insta/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: 'CLEAR' }),
      });
      showToast('All accounts cleared', 'info');
      appendLog('[tracking] All accounts cleared.');
      page = 1;
      await shared.refreshShared();
    });
  }

  if (els.btnClearLog && els.log) els.btnClearLog.addEventListener('click', () => { els.log.textContent = ''; });
  if (els.btnCopyLog && els.log) {
    els.btnCopyLog.addEventListener('click', () => {
      const text = Array.from(els.log.children).map((c) => c.textContent).join('\n');
      navigator.clipboard.writeText(text).then(() => showToast('Log copied!', 'success'));
    });
  }

  if (els.btnDeepClean) {
    els.btnDeepClean.addEventListener('click', async () => {
      if (state.running) {
        showToast('Stop the engine before deep cleaning.', 'warning');
        return;
      }
      const confirmed = await shared.showDeleteConfirmModal({
        title: 'Deep Clean',
        message: 'Remove orphaned sessions, cookies and dead creator profiles?',
        subtext: 'Keeps all saved accounts and their files. Nova browser profiles are never touched.',
        targetHtml: '',
        confirmText: 'Deep Clean',
      });
      if (!confirmed) return;
      try {
        const r = await (await fetch('/api/meta-insta/cleanup', { method: 'POST' })).json();
        if (r.status === 'SUCCESS') {
          const rem = r.removed || {};
          const summary = `sessions=${rem.sessions || 0}, cookies=${rem.cookies || 0}, profiles=${rem.profiles || 0}`;
          showToast(`Deep clean done (${summary}).`, 'success');
          appendLog(`[cleanup] Removed: ${summary}.`);
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
      link.download = def.kind === 'ig' ? 'ig_combo.txt' : 'meta_combo.txt';
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
        saveVisibleCols(checked.map((c) => c.getAttribute('data-col')));
        applyColumnVisibility();
        const emptyTd = els.resultsList.querySelector('.insta-empty-state')?.closest('td');
        if (emptyTd) emptyTd.setAttribute('colspan', String(getVisibleColCount()));
      });
    });
    if (els.btnColsReset) {
      els.btnColsReset.addEventListener('click', (e) => {
        e.stopPropagation();
        saveVisibleCols(ALL_COLS);
        applyColumnVisibility();
        const emptyTd = els.resultsList.querySelector('.insta-empty-state')?.closest('td');
        if (emptyTd) emptyTd.setAttribute('colspan', String(getVisibleColCount()));
      });
    }
  }

  // React to shared state changes. Coalesced to one paint per animation frame
  // (multiple SSE events + polls in the same tick collapse into a single
  // render), and only the visible workspace repaints its table.
  let dirty = false;
  let paintRaf = null;
  function isVisible() {
    const panel = root.closest('.view-panel');
    return !panel || panel.classList.contains('active');
  }
  function repaint() {
    renderResults();
    dirty = false;
  }
  function schedulePaint() {
    if (paintRaf) return;
    paintRaf = requestAnimationFrame(() => {
      paintRaf = null;
      updateStats();
      if (isVisible()) repaint();
      else dirty = true;
    });
  }

  shared.subscribe(schedulePaint);

  document.querySelectorAll('.nav-item[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (dirty && isVisible()) repaint();
    });
  });

  // Initial paint
  updateStats();
  renderResults();

  return { def, root, appendLog, setProgress, logHasContent };
}
