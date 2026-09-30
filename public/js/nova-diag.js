// ============================================================================
// NOVA DIAG & RUN LOGS — Live Failure Reasons & Persistent Session Logs
// ----------------------------------------------------------------------------
// Sibling parity with meta_auto_ai:
// 1. Polls /api/diag/reasons (every 10s) and renders normalized failure
//    histogram + reason=<code> tags.
// 2. Polls /api/logs (every 15s) and renders downloadable run logs from logs/.
// 3. Updates all mounted panels across all views (TG Classic, Meta, IG).
// ============================================================================

(function () {
  'use strict';

  function esc(s) {
    return String(s || '').replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '(': '&lt;', '>': '&gt;', '"': '&quot;' }[c] || c;
    });
  }

  var NovaDiag = {
    renderHtml: function (prefix) {
      var p = prefix ? String(prefix) + '-' : '';
      return '' +
        '<!-- Failure Reasons (live diag) -->' +
        '<div class="card-panel diag-card" style="margin-top:1rem;padding:0;overflow:hidden;">' +
          '<details class="diag-details" id="' + p + 'diag-details">' +
            '<summary style="padding:0.75rem 1rem;display:flex;align-items:center;justify-content:space-between;cursor:pointer;list-style:none;user-select:none;">' +
              '<div style="display:flex;align-items:center;gap:0.5rem;">' +
                '<i class="fa-solid fa-triangle-exclamation" style="color:#fb7185;font-size:0.9rem;"></i>' +
                '<span style="font-size:0.88rem;font-weight:600;color:var(--text-main);">Failure Reasons (live)</span>' +
                '<span style="margin-left:4px;padding:2px 8px;border-radius:4px;font-size:0.68rem;font-weight:700;background:rgba(244,63,94,0.15);color:#fda4af;border:1px solid rgba(244,63,94,0.3);">' +
                  'total <span data-role="diag-total">0</span>' +
                '</span>' +
              '</div>' +
              '<div style="display:flex;align-items:center;gap:0.75rem;">' +
                '<span data-role="diag-updated" style="font-size:0.68rem;font-family:var(--font-mono);color:var(--text-muted);">no data yet</span>' +
                '<i class="fa-solid fa-chevron-down diag-chevron" style="color:var(--text-muted);font-size:0.75rem;transition:transform 0.2s;"></i>' +
              '</div>' +
            '</summary>' +
            '<div style="padding:0.75rem 1rem;border-top:1px solid var(--border-color);">' +
              '<div data-role="diag-reasons" style="display:flex;flex-direction:column;gap:4px;">' +
                '<div style="font-size:0.75rem;color:var(--text-muted);font-style:italic;padding:4px 0;">No failures recorded yet.</div>' +
              '</div>' +
              '<div style="margin-top:0.75rem;">' +
                '<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-muted);margin-bottom:6px;">' +
                  'Password reasons <span style="text-transform:none;color:var(--text-dim);">(reason=…)</span>' +
                '</div>' +
                '<div data-role="diag-pass">' +
                  '<span style="font-size:0.75rem;color:var(--text-muted);font-style:italic;">none</span>' +
                '</div>' +
              '</div>' +
            '</div>' +
          '</details>' +
        '</div>' +

        '<!-- Session Logs (persistent run logs) -->' +
        '<div class="card-panel diag-card" style="margin-top:0.75rem;padding:0;overflow:hidden;">' +
          '<details class="diag-details" id="' + p + 'logs-details" open>' +
            '<summary style="padding:0.75rem 1rem;display:flex;align-items:center;justify-content:space-between;cursor:pointer;list-style:none;user-select:none;">' +
              '<div style="display:flex;align-items:center;gap:0.5rem;">' +
                '<i class="fa-solid fa-file-lines" style="color:#38bdf8;font-size:0.9rem;"></i>' +
                '<span style="font-size:0.88rem;font-weight:600;color:var(--text-main);">Session Logs</span>' +
                '<span style="margin-left:4px;padding:2px 8px;border-radius:4px;font-size:0.68rem;font-weight:700;background:rgba(56,189,248,0.15);color:#7dd3fc;border:1px solid rgba(56,189,248,0.3);">' +
                  'last <span data-role="log-count">0</span>' +
                '</span>' +
              '</div>' +
              '<div style="display:flex;align-items:center;gap:0.75rem;">' +
                '<a data-role="log-latest" href="#" target="_blank" style="font-size:0.68rem;font-family:var(--font-mono);color:#38bdf8;text-decoration:none;display:none;">' +
                  '<i class="fa-solid fa-download"></i> download latest' +
                '</a>' +
                '<i class="fa-solid fa-chevron-down diag-chevron" style="color:var(--text-muted);font-size:0.75rem;transition:transform 0.2s;"></i>' +
              '</div>' +
            '</summary>' +
            '<div style="padding:0.75rem 1rem;border-top:1px solid var(--border-color);">' +
              '<div style="font-size:0.68rem;font-family:var(--font-mono);color:var(--text-muted);margin-bottom:8px;">' +
                'dir: <span data-role="log-dir">logs/</span>' +
              '</div>' +
              '<div data-role="log-list" style="display:flex;flex-direction:column;gap:3px;max-height:220px;overflow-y:auto;">' +
                '<div style="font-size:0.75rem;color:var(--text-muted);font-style:italic;padding:4px 0;">No run logs yet.</div>' +
              '</div>' +
            '</div>' +
          '</details>' +
        '</div>';
    },

    refreshReasons: function () {
      fetch('/api/diag/reasons')
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          NovaDiag.renderReasons(data || {});
        })
        .catch(function () {});
    },

    renderReasons: function (s) {
      var reasons = s.reasons || {};
      var pass = s.password_reasons || {};

      var updatedText = s.updated
        ? ('updated ' + new Date(s.updated).toLocaleTimeString())
        : 'no data yet';
      document.querySelectorAll('[data-role="diag-updated"]').forEach(function (el) {
        el.textContent = updatedText;
      });

      var totalText = String(s.total || 0);
      document.querySelectorAll('[data-role="diag-total"]').forEach(function (el) {
        el.textContent = totalText;
      });

      var entries = Object.keys(reasons)
        .map(function (k) { return [k, reasons[k]]; })
        .sort(function (a, b) { return b[1] - a[1]; });
      var max = entries.length ? entries[0][1] : 0;

      var reasonsHtml = '';
      if (!entries.length) {
        reasonsHtml = '<div style="font-size:0.75rem;color:var(--text-muted);font-style:italic;padding:4px 0;">No failures recorded yet.</div>';
      } else {
        reasonsHtml = entries.map(function (item) {
          var k = item[0];
          var v = item[1];
          var pct = max ? Math.max(4, Math.round((v / max) * 100)) : 0;
          return '<div style="display:flex;align-items:center;gap:8px;padding:2px 0;">' +
            '<div style="width:210px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.75rem;color:var(--text-main);" title="' + esc(k) + '">' + esc(k) + '</div>' +
            '<div style="flex:1;height:8px;background:rgba(255,255,255,0.06);border-radius:999px;overflow:hidden;">' +
              '<div style="height:100%;background:rgba(244,63,94,0.75);border-radius:999px;width:' + pct + '%;"></div>' +
            '</div>' +
            '<div style="width:42px;text-align:right;font-size:0.75rem;font-family:var(--font-mono);color:#fda4af;">' + v + '</div>' +
          '</div>';
        }).join('');
      }
      document.querySelectorAll('[data-role="diag-reasons"]').forEach(function (el) {
        el.innerHTML = reasonsHtml;
      });

      var passEntries = Object.keys(pass)
        .map(function (k) { return [k, pass[k]]; })
        .sort(function (a, b) { return b[1] - a[1]; });

      var passHtml = '';
      if (!passEntries.length) {
        passHtml = '<span style="font-size:0.75rem;color:var(--text-muted);font-style:italic;">none</span>';
      } else {
        passHtml = passEntries.map(function (item) {
          var k = item[0];
          var v = item[1];
          return '<span style="display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:4px;border:1px solid var(--border-color);background:rgba(255,255,255,0.03);font-size:0.68rem;font-family:var(--font-mono);color:var(--text-dim);margin:0 4px 4px 0;">' +
            '<span style="color:var(--text-main);">' + esc(k) + '</span>' +
            '<b style="color:var(--accent-amber);">' + v + '</b>' +
          '</span>';
        }).join('');
      }
      document.querySelectorAll('[data-role="diag-pass"]').forEach(function (el) {
        el.innerHTML = passHtml;
      });
    },

    refreshLogs: function () {
      fetch('/api/logs')
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          NovaDiag.renderLogs(data || {});
        })
        .catch(function () {});
    },

    renderLogs: function (s) {
      var dirName = (s.dir || 'logs') + '/';
      document.querySelectorAll('[data-role="log-dir"]').forEach(function (el) {
        el.textContent = dirName;
      });

      var logs = s.logs || [];
      document.querySelectorAll('[data-role="log-count"]').forEach(function (el) {
        el.textContent = String(logs.length);
      });

      var latestUrl = logs.length ? ('/api/logs/file?name=' + encodeURIComponent(logs[0].name)) : '#';
      document.querySelectorAll('[data-role="log-latest"]').forEach(function (el) {
        if (logs.length) {
          el.href = latestUrl;
          el.style.display = 'inline-block';
        } else {
          el.style.display = 'none';
        }
      });

      var listHtml = '';
      if (!logs.length) {
        listHtml = '<div style="font-size:0.75rem;color:var(--text-muted);font-style:italic;padding:4px 0;">No run logs yet.</div>';
      } else {
        listHtml = logs.map(function (l) {
          var kb = Math.max(1, Math.round((l.size || 0) / 1024));
          var when = '';
          try { when = new Date(l.mtime).toLocaleString(); } catch (e) { when = ''; }
          return '<div style="display:flex;align-items:center;gap:8px;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.03);">' +
            '<a href="/api/logs/file?name=' + encodeURIComponent(l.name) + '" target="_blank" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.75rem;color:#7dd3fc;text-decoration:none;" title="' + esc(l.name) + '">' +
              '<i class="fa-solid fa-file-lines" style="margin-right:6px;opacity:0.75;"></i>' + esc(l.name) +
            '</a>' +
            '<span style="font-size:0.68rem;color:var(--text-muted);white-space:nowrap;">' + esc(when) + '</span>' +
            '<span style="width:55px;text-align:right;font-size:0.68rem;font-family:var(--font-mono);color:var(--text-dim);white-space:nowrap;">' + kb + ' KB</span>' +
          '</div>';
        }).join('');
      }
      document.querySelectorAll('[data-role="log-list"]').forEach(function (el) {
        el.innerHTML = listHtml;
      });
    },

    init: function () {
      this.refreshReasons();
      this.refreshLogs();
      setInterval(function () {
        if (document.querySelector('.diag-details[open]')) {
          NovaDiag.refreshReasons();
        }
      }, 15000);
      setInterval(function () {
        if (document.querySelector('.diag-details[open]')) {
          NovaDiag.refreshLogs();
        }
      }, 30000);
    }
  };

  window.NovaDiag = NovaDiag;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      NovaDiag.init();
    });
  } else {
    NovaDiag.init();
  }
})();
