/**
 * Nova Browser UI — IG Checker workspace.
 *
 * Bulk-verify Instagram usernames live (public REST lookup + HTML fallback,
 * no login) and flag dead ones in the saved IG Creator list so the pool
 * drain never picks them again. Ported from Nova Browser's nova-insta.js.
 */

function initIgChecker() {
  const inputText = document.getElementById('igcheck-input-text');
  const inputCount = document.getElementById('igcheck-input-count');
  const dropzone = document.getElementById('igcheck-dropzone');
  const fileInput = document.getElementById('igcheck-file-input');
  const fileBadge = document.getElementById('igcheck-file-badge');
  const btnStart = document.getElementById('btn-igcheck-start');
  const btnStop = document.getElementById('btn-igcheck-stop');
  const btnLoadList = document.getElementById('btn-igcheck-load-list');
  const btnMarkDead = document.getElementById('btn-igcheck-mark-dead');
  const speedSelect = document.getElementById('igcheck-speed-select');
  const progressBox = document.getElementById('igcheck-progress-box');
  const progressBar = document.getElementById('igcheck-progress-bar');
  const progressLabel = document.getElementById('igcheck-progress-label');
  const progressPct = document.getElementById('igcheck-progress-pct');

  const statTotal = document.getElementById('igcheck-stat-total');
  const statActive = document.getElementById('igcheck-stat-active');
  const statNotFound = document.getElementById('igcheck-stat-notfound');
  const statVerified = document.getElementById('igcheck-stat-verified');

  const badgeActive = document.getElementById('igcheck-badge-active');
  const badgeNotFound = document.getElementById('igcheck-badge-notfound');
  const badgeAll = document.getElementById('igcheck-badge-all');

  const resultsList = document.getElementById('igcheck-results-list');
  const searchResults = document.getElementById('igcheck-search-results');
  const btnExportActiveCsv = document.getElementById('btn-igcheck-export-active-csv');
  const btnCopyActive = document.getElementById('btn-igcheck-copy-active');
  const btnClear = document.getElementById('btn-igcheck-clear');

  let isChecking = false;
  let abortController = null;
  let uploadedCsvRows = [];
  let uploadedCsvFileName = '';
  let checkResults = [];
  let currentFilterTab = 'active';

  if (!inputText || !btnStart) return;

  function formatNumber(n) {
    if (n === undefined || n === null) return '—';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
    return n.toLocaleString();
  }

  function updateInputCount() {
    const names = getUsernamesFromInput();
    if (inputCount) inputCount.textContent = `${names.length} names`;
  }

  inputText.addEventListener('input', updateInputCount);

  function getUsernamesFromInput() {
    if (uploadedCsvRows.length > 0) {
      return uploadedCsvRows.map((row) => {
        const firstCol = row.split(',')[0].trim().replace(/^@/, '').toLowerCase();
        return firstCol;
      }).filter((u) => u.length > 0);
    }
    return inputText.value
      .split(/[\r\n,]+/)
      .map((u) => u.trim().replace(/^@/, '').toLowerCase())
      .filter((u) => u.length > 0);
  }

  // --- Load usernames straight from the saved IG Creator list ---
  if (btnLoadList) {
    btnLoadList.addEventListener('click', async () => {
      try {
        const r = await (await fetch('/api/meta-insta/accounts')).json();
        const accs = (r && r.accounts) || [];
        const names = accs
          .filter((a) => (a.target || '') !== 'telegram' && String(a.status || '') !== 'MetaCreated')
          .map((a) => String(a.instagram_username || a.username || '').trim().replace(/^@/, ''))
          .filter(Boolean);
        const uniq = [...new Set(names.map((n) => n.toLowerCase()))];
        if (!uniq.length) {
          showToast('No Instagram accounts in the list yet.', 'info');
          return;
        }
        clearUploadedFile();
        inputText.value = uniq.join('\n');
        updateInputCount();
        showToast(`Loaded ${uniq.length} username(s) from your IG list.`, 'success');
      } catch (e) {
        showToast('Could not load the IG list: ' + e.message, 'error');
      }
    });
  }

  // --- Dropzone & File Input ---
  if (dropzone) {
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFile(e.dataTransfer.files[0]);
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFile(e.target.files[0]);
      }
    });
  }

  function handleFile(file) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target.result || '';
      const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
      uploadedCsvRows = lines;
      uploadedCsvFileName = file.name;

      fileBadge.style.display = 'inline-flex';
      fileBadge.innerHTML = `<span><i class="fa-solid fa-file-csv"></i> ${escapeHtml(file.name)} (${lines.length} lines)</span> <button type="button" id="btn-igcheck-remove-csv" style="background:none; border:none; color:#f87171; cursor:pointer; font-size:12px; margin-left:4px;"><i class="fa-solid fa-xmark"></i></button>`;

      inputText.disabled = true;
      inputText.placeholder = `[File loaded: ${file.name} with ${lines.length} usernames]`;
      inputText.value = '';
      updateInputCount();

      const btnRemove = document.getElementById('btn-igcheck-remove-csv');
      if (btnRemove) {
        btnRemove.addEventListener('click', (evt) => {
          evt.stopPropagation();
          clearUploadedFile();
        });
      }
    };
    reader.readAsText(file);
  }

  function clearUploadedFile() {
    uploadedCsvRows = [];
    uploadedCsvFileName = '';
    if (fileBadge) {
      fileBadge.style.display = 'none';
      fileBadge.innerHTML = '';
    }
    if (fileInput) fileInput.value = '';
    inputText.disabled = false;
    inputText.placeholder = 'cristiano\nleomessi\ninstagram\nsample_username';
    updateInputCount();
  }

  // --- Tabs ---
  document.querySelectorAll('#view-ig-checker .insta-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#view-ig-checker .insta-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      currentFilterTab = tab.getAttribute('data-tab');
      renderResults();
    });
  });

  if (searchResults) {
    searchResults.addEventListener('input', debounce(() => {
      renderResults();
    }, 200));
  }

  // --- Start / Stop Checking ---
  btnStart.addEventListener('click', async () => {
    if (isChecking) return;

    if (!requireLicense('Active license key required to use IG Checker.')) return;

    const usernames = getUsernamesFromInput();
    if (usernames.length === 0) {
      showToast('Paste usernames, upload a CSV, or load your IG list first.', 'error');
      return;
    }

    isChecking = true;
    btnStart.style.display = 'none';
    btnStop.style.display = 'inline-flex';
    progressBox.style.display = 'block';
    progressBar.style.width = '0%';
    progressPct.textContent = '0%';
    progressLabel.textContent = `Preparing to check ${usernames.length} usernames...`;

    checkResults = [];
    updateStats();
    renderResults();

    abortController = new AbortController();
    const delay = parseInt((speedSelect && speedSelect.value) || '800', 10) || 800;

    try {
      const response = await fetch('/api/ig-check-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usernames, delay_ms: delay }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const msg = JSON.parse(line);
            if (msg.type === 'total') {
              statTotal.textContent = msg.count;
            } else if (msg.type === 'result') {
              checkResults.push(msg.result);
              updateStats();
              if (msg.progress) {
                const pct = Math.round((msg.progress.done / msg.progress.total) * 100);
                progressBar.style.width = `${pct}%`;
                progressPct.textContent = `${pct}%`;
                progressLabel.textContent = `Checking ${msg.progress.done} / ${msg.progress.total} (@${msg.result.username})`;
              }
              requestRenderResults();
            } else if (msg.type === 'done') {
              progressLabel.textContent = `Completed checking ${checkResults.length} accounts.`;
            }
          } catch (jsonErr) {}
        }
      }

      renderResults();

      showToast(`Check complete! ${checkResults.filter((r) => r.status === 'active').length} active account(s) found.`, 'success');
    } catch (err) {
      if (err.name === 'AbortError') {
        progressLabel.textContent = 'Checking stopped by user.';
        showToast('IG check stopped.', 'info');
      } else {
        progressLabel.textContent = `Error: ${err.message}`;
        showToast(err.message, 'error');
      }
    } finally {
      isChecking = false;
      btnStart.style.display = 'inline-flex';
      btnStop.style.display = 'none';
      updateStats();
    }
  });

  btnStop.addEventListener('click', () => {
    if (abortController) {
      abortController.abort();
    }
  });

  // --- Mark damaged (not_found) as Failed in the saved list ---
  if (btnMarkDead) {
    btnMarkDead.addEventListener('click', async () => {
      const dead = checkResults.filter((r) => r.status === 'not_found').map((r) => r.username);
      if (!dead.length) {
        showToast('No damaged accounts in the current results.', 'info');
        return;
      }
      if (!requireLicense('Active license key required.')) return;
      btnMarkDead.disabled = true;
      try {
        const r = await (await fetch('/api/ig-mark-dead', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ usernames: dead }),
        })).json();
        if (r.status === 'SUCCESS') {
          const n = (r.marked || []).length;
          showToast(
            n ? `Flagged ${n} damaged account(s) — pool will skip them, backups can exclude them.` : 'Those accounts were already flagged.',
            n ? 'success' : 'info'
          );
        } else {
          showToast(r.error || 'Flagging failed.', 'error');
        }
      } catch (e) {
        showToast('Flagging failed: ' + e.message, 'error');
      } finally {
        btnMarkDead.disabled = false;
      }
    });
  }

  function updateStats() {
    const activeCount = checkResults.filter((r) => r.status === 'active').length;
    const notFoundCount = checkResults.filter((r) => r.status === 'not_found').length;
    const verifiedCount = checkResults.filter((r) => r.isVerified).length;

    statActive.textContent = activeCount;
    statNotFound.textContent = notFoundCount;
    statVerified.textContent = verifiedCount;
    statTotal.textContent = checkResults.length;

    badgeActive.textContent = activeCount;
    badgeNotFound.textContent = notFoundCount;
    badgeAll.textContent = checkResults.length;

    const hasActive = activeCount > 0;
    const hasDead = notFoundCount > 0;
    btnExportActiveCsv.disabled = !hasActive;
    btnCopyActive.disabled = !hasActive;
    if (btnMarkDead) btnMarkDead.disabled = !hasDead;
  }

  let renderToken = 0;
  let renderQueued = false;
  function requestRenderResults() {
    if (renderQueued) return;
    renderQueued = true;
    setTimeout(() => {
      renderQueued = false;
      renderResults();
    }, 400);
  }

  const RENDER_CHUNK_ROWS = 120;

  function renderResults() {
    renderQueued = false;
    const myToken = ++renderToken;
    const query = ((searchResults && searchResults.value) || '').toLowerCase().trim();

    const filtered = checkResults.filter((r) => {
      const matchesTab =
        currentFilterTab === 'all' ? true :
        (currentFilterTab === 'active' ? r.status === 'active' : r.status !== 'active');

      const matchesQuery = !query ||
        r.username.toLowerCase().includes(query) ||
        (r.fullName && r.fullName.toLowerCase().includes(query)) ||
        (r.bio && r.bio.toLowerCase().includes(query));

      return matchesTab && matchesQuery;
    });

    if (filtered.length === 0) {
      resultsList.innerHTML = `
        <div class="insta-empty-state">
          <i class="fa-solid fa-magnifying-glass" style="font-size: 2rem; color: var(--text-muted); opacity: 0.5; margin-bottom: 0.5rem;"></i>
          <p>No accounts match the current filter.</p>
        </div>
      `;
      return;
    }

    const rows = filtered.map((r) => {
      if (r.status === 'active') {
        const showPic = r.hasProfilePic && !!r.profilePicUrl;
        return `
          <div class="insta-card">
            <div class="insta-card-avatar-box">
              ${showPic ? `
                <img src="${r.profilePicUrl}" alt="${escapeHtml(r.username)}" class="insta-card-avatar" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="insta-card-avatar-fallback" style="display:none;">${escapeHtml(r.username.charAt(0).toUpperCase())}</div>
              ` : `
                <div class="insta-card-avatar-fallback">${escapeHtml(r.username.charAt(0).toUpperCase())}</div>
              `}
              <div class="insta-card-pic-dot ${showPic ? 'has-pic' : 'no-pic'}" title="${showPic ? 'Has profile photo' : 'Default photo'}"></div>
            </div>

            <div class="insta-card-content">
              <div class="insta-card-header">
                <a href="https://instagram.com/${escapeHtml(r.username)}" target="_blank" rel="noopener noreferrer" class="insta-card-username">
                  @${escapeHtml(r.username)}
                </a>
                ${r.isVerified ? '<span class="insta-badge-verified" title="Verified Account"><i class="fa-solid fa-circle-check"></i></span>' : ''}
                ${r.isPrivate ? '<span class="insta-badge-private"><i class="fa-solid fa-lock"></i> Private</span>' : ''}
                <span class="badge-pill bg-emerald" style="margin-left: auto;">Active</span>
              </div>

              ${r.fullName ? `<div class="insta-card-fullname">${escapeHtml(r.fullName)}</div>` : ''}
              ${r.bio ? `<div class="insta-card-bio">${escapeHtml(r.bio)}</div>` : ''}

              <div class="insta-card-stats">
                <div class="insta-stat-pill">
                  <span class="insta-stat-num">${formatNumber(r.followers)}</span>
                  <span class="insta-stat-k">Followers</span>
                </div>
                <div class="insta-stat-pill">
                  <span class="insta-stat-num">${formatNumber(r.following)}</span>
                  <span class="insta-stat-k">Following</span>
                </div>
                <div class="insta-stat-pill">
                  <span class="insta-stat-num">${formatNumber(r.posts)}</span>
                  <span class="insta-stat-k">Posts</span>
                </div>
                <div class="insta-stat-pill" style="margin-left: auto;">
                  <a href="https://instagram.com/${escapeHtml(r.username)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Visit
                  </a>
                </div>
              </div>
            </div>
          </div>
        `;
      }
      return `
        <div class="insta-row-inactive">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="width: 8px; height: 8px; border-radius: 50%; background: #ef4444; display: inline-block;"></span>
            <a href="https://instagram.com/${escapeHtml(r.username)}" target="_blank" rel="noopener noreferrer">@${escapeHtml(r.username)}</a>
            <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(r.details || r.message || 'Account not found')}</span>
          </div>
          <span class="badge-pill bg-rose">Damaged</span>
        </div>
      `;
    });

    resultsList.innerHTML = rows.slice(0, RENDER_CHUNK_ROWS).join('');
    let nextRow = RENDER_CHUNK_ROWS;
    const pumpRows = () => {
      if (myToken !== renderToken) return;
      if (nextRow >= rows.length) return;
      resultsList.insertAdjacentHTML('beforeend', rows.slice(nextRow, nextRow + RENDER_CHUNK_ROWS).join(''));
      nextRow += RENDER_CHUNK_ROWS;
      if (nextRow < rows.length) setTimeout(pumpRows, 0);
    };
    if (nextRow < rows.length) setTimeout(pumpRows, 0);
  }

  // --- Export Active CSV ---
  btnExportActiveCsv.addEventListener('click', () => {
    const activeUsernames = new Set(
      checkResults.filter((r) => r.status === 'active').map((r) => r.username.toLowerCase())
    );

    if (activeUsernames.size === 0) {
      showToast('No active accounts to export.', 'error');
      return;
    }

    let csvContent = '';
    let exportFileName = 'instagram_active_accounts.csv';

    if (uploadedCsvRows.length > 0) {
      const filteredRows = uploadedCsvRows.filter((row) => {
        const u = row.split(',')[0].trim().replace(/^@/, '').toLowerCase();
        return activeUsernames.has(u);
      });
      csvContent = filteredRows.join('\n');
      exportFileName = uploadedCsvFileName ? `active_${uploadedCsvFileName}` : 'active_accounts.csv';
    } else {
      const headers = ['Username', 'Status', 'Verified', 'Private', 'Followers', 'Following', 'Posts', 'Full Name', 'Bio'];
      const rows = checkResults
        .filter((r) => r.status === 'active')
        .map((r) => [
          `"${r.username}"`,
          `"active"`,
          r.isVerified ? 'true' : 'false',
          r.isPrivate ? 'true' : 'false',
          r.followers !== undefined ? r.followers : '',
          r.following !== undefined ? r.following : '',
          r.posts !== undefined ? r.posts : '',
          `"${(r.fullName || '').replace(/"/g, '""')}"`,
          `"${(r.bio || '').replace(/"/g, '""')}"`,
        ].join(','));
      csvContent = [headers.join(','), ...rows].join('\n');
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = exportFileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Exported ${activeUsernames.size} active account(s) to ${exportFileName}!`, 'success');
  });

  // --- Copy Active to Clipboard ---
  btnCopyActive.addEventListener('click', () => {
    const activeList = checkResults
      .filter((r) => r.status === 'active')
      .map((r) => `@${r.username}`)
      .join('\n');

    if (!activeList) {
      showToast('No active accounts to copy.', 'error');
      return;
    }

    navigator.clipboard.writeText(activeList).then(() => {
      showToast(`Copied ${checkResults.filter((r) => r.status === 'active').length} active username(s)!`, 'success');
    });
  });

  // --- Clear All ---
  btnClear.addEventListener('click', () => {
    if (isChecking && abortController) abortController.abort();
    checkResults = [];
    inputText.value = '';
    clearUploadedFile();
    progressBox.style.display = 'none';
    progressBar.style.width = '0%';
    statTotal.textContent = '0';
    statActive.textContent = '0';
    statNotFound.textContent = '0';
    statVerified.textContent = '0';
    badgeActive.textContent = '0';
    badgeNotFound.textContent = '0';
    badgeAll.textContent = '0';
    btnExportActiveCsv.disabled = true;
    btnCopyActive.disabled = true;
    if (btnMarkDead) btnMarkDead.disabled = true;
    renderResults();
    showToast('Cleared IG Checker workspace.', 'info');
  });
}
