// Settings page (#/settings): user-supplied API keys, saved via /api/meta-insta/mail-mode.
(function () {
  function $(id) { return document.getElementById(id); }
  function post(body) {
    return fetch('/api/meta-insta/mail-mode', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body) }).then(function (r) { return r.json(); });
  }
  function show(j) {
    var st = $('set-mailfish-status');
    if (st) st.textContent = j && j.has_key ? 'Key saved (' + j.key_hint + ')' : 'No key set \u2014 new accounts use the free web inbox.';
  }
  function load() { fetch('/api/meta-insta/mail-mode').then(function (r) { return r.json(); }).then(show).catch(function () {}); }
  document.addEventListener('click', function (ev) {
    var t = ev.target && ev.target.closest && ev.target.closest('button');
    if (!t) return;
    if (t.id === 'set-mailfish-save') {
      var inp = $('set-mailfish-key');
      if (!inp.value.trim()) return;
      post({ api_key: inp.value }).then(function (j) { inp.value = ''; show(j); });
    } else if (t.id === 'set-mailfish-clear') {
      post({ api_key: '' }).then(show);
    }
  });
  window.addEventListener('nova:view-changed', function (e) { if (e.detail && e.detail.viewId === 'view-settings') load(); });
})();
