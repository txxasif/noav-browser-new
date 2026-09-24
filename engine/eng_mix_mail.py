"""engine.eng_mix_mail — browser-driven mail.td inbox & code fetch.

Verbatim slice from ``engine/run.py`` ``_MetaInstagramRunner`` (no logic change).
Mixed into :class:`engine._MetaInstagramRunner`; ``self`` provides the other
engine helpers (same browser session invariant unchanged). Zero local-repo
dependencies (``store`` only via function-local lazy import).
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import _MAILTD_URL  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _MAILTD_URL  # noqa: E402

class EngineMailMixin:
    def open_mailtd(self):
        self.mail = self.w.context.new_page()
        self.mail.goto(_MAILTD_URL, wait_until="domcontentloaded", timeout=60000)
        self.mail.wait_for_timeout(4000)
        for _ in range(20):
            txt = self.mail.evaluate("() => document.body.innerText")
            m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", txt)
            if m:
                self.email = m.group(0)
                break
            self.mail.wait_for_timeout(1000)
        if not self.email:
            raise RuntimeError("could not read mail.td address")
        self.log(f'<font color="#00FF00"><b>[📧] Meta inbox: {self.email}</b></font>')

    def new_mailtd_address(self, timeout: int = 40):
        """Create a FRESH mail.td address via the page's "↻ New" button.

        The page is proof-of-work gated, so this must run in the live browser.
        Returns the new address (lowercased), or None on failure. Tokens are
        read later from the live page's localStorage by ``_mailtd_api_ctx`` so
        ``fetch_code`` automatically serves the NEW mailbox.
        """
        mail = getattr(self, "mail", None) or getattr(self, "page", None)
        if mail is None:
            return None
        old = (getattr(self, "email", "") or "").strip().lower()
        clicked = False
        for sel in ('button:has-text("↻ New")', 'button:has-text("New")',
                    '[aria-label*="New" i]'):
            try:
                el = mail.locator(sel).first
                if el.count() and el.is_visible():
                    el.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            return None
        end = time.time() + max(5, timeout)
        while time.time() < end:
            mail.wait_for_timeout(1000)
            try:
                txt = mail.evaluate("() => document.body.innerText") or ""
            except Exception:
                continue
            m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", txt)
            if m:
                addr = m.group(0).lower()
                if addr != old:
                    self.log(f'<font color="#00FF00"><b>[📧] Extra temp mailbox: {addr}</b></font>')
                    return addr
        return None

    def _mail_text(self):
        return self.mail.evaluate(
            "() => { let t = document.body.innerText || '';"
            " for (const f of document.querySelectorAll('iframe')) {"
            "  try { if (f.contentDocument) t += '\\n' + (f.contentDocument.body.innerText || ''); } catch (e) {} }"
            " return t; }")

    # -- mail.td REST API fast path ---------------------------------------
    @staticmethod
    def _flatten_values(obj, out=None, depth=0):
        """Every string value inside a nested JSON object (schema-proof code hunt)."""
        if out is None:
            out = []
        if depth > 8:
            return out
        if isinstance(obj, str):
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                EngineMailMixin._flatten_values(v, out, depth + 1)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                EngineMailMixin._flatten_values(v, out, depth + 1)
        return out

    def _pick_code(self, text, keyword, stale):
        """Extract the confirmation code from mail text (shared by API + DOM).

        Meta signup mails carry 6 digits; Meta/IG security mails
        ("Authenticate your profile") carry 8 — so 8-digit is preferred for
        non-meta keywords. Skips year-like 6-digit values and already-used codes.
        """
        clean = re.sub(r"#[0-9a-fA-F]{6}", " ", text or "")
        # Messages arrive as HTML (mail.td `html_body`): strip tags and unescape
        # entities so the digits are readable by the regexes below.
        try:
            import html as _html
            clean = _html.unescape(re.sub(r"<[^>]+>", " ", clean))
        except Exception:
            pass
        if (keyword or "").lower() == "meta":
            pats = [r"(?:code|verification|verify|confirm|otp)[^\d]{0,60}(\d{6})(?!\d)",
                    r"\b(\d{6})\b"]
        else:
            pats = [r"(?:code|verification|verify|confirm|otp|authenticate|identity)[^\d]{0,60}(\d{8}|\d{6})",
                    r"\b(\d{8})\b",
                    r"\b(\d{6})\b"]
        for pat in pats:
            for m in re.finditer(pat, clean, re.IGNORECASE):
                g = m.group(1)
                if len(g) == 6 and 2000 <= int(g) <= 2035:
                    continue
                if g in stale:
                    continue
                return g
        return None

    def _mailtd_api_ctx(self):
        """(id, token) for the mail.td REST API from the live mail page, or None."""
        try:
            mail = getattr(self, "mail", None)
            if mail is None or mail.is_closed():
                return None
            ctx = mail.evaluate("""() => ({
                id: localStorage.getItem('tempmail_account_id') || '',
                token: localStorage.getItem('tempmail_token') || '',
            })""")
            if ctx and ctx.get("id") and ctx.get("token"):
                return ctx
        except Exception:
            pass
        return None

    def _mailtd_api_code(self, keyword, timeout, stale):
        """Poll mail.td's REST API for the OTP — no Refresh/row clicks/DOM reads.

        The LIST endpoint returns only metadata (id/sender/subject/preview) — the
        message BODY (the actual code) is only in the DETAIL endpoint
        ``GET /api/accounts/{id}/messages/{mid}`` (``html_body``). So each new
        message is expanded once via detail and cached. The fetch runs inside the
        live mail page so Cloudflare is satisfied. Returns the code, or None.
        """
        ctx = self._mailtd_api_ctx()
        if not ctx:
            return None
        end = time.time() + timeout
        last_beat = 0.0
        seen = {}  # message id -> full text (list + detail body), expanded once
        while time.time() < end and self.w.is_running:
            try:
                res = self.mail.evaluate("""async ({id, token}) => {
                    try {
                        const r = await fetch('/api/accounts/' + id + '/messages?page=1',
                            {headers: {Authorization: 'Bearer ' + token}});
                        if (!r.ok) return {status: r.status, messages: []};
                        const j = await r.json();
                        return {status: 200, messages: (j && j.messages) || []};
                    } catch (e) { return {status: -1, messages: []}; }
                }""", {"id": ctx["id"], "token": ctx["token"]})
            except Exception:
                return None
            msgs = res.get("messages") or []
            for msg in msgs:
                mid = msg.get("id")
                text = seen.get(mid)
                if text is None:
                    text = " ".join(self._flatten_values(msg))
                    if not self._pick_code(text, keyword, stale) and mid:
                        # Body is ONLY in the detail endpoint.
                        try:
                            body = self.mail.evaluate("""async ({id, mid, token}) => {
                                try {
                                    const r = await fetch('/api/accounts/' + id + '/messages/' + mid,
                                        {headers: {Authorization: 'Bearer ' + token}});
                                    if (!r.ok) return '';
                                    const j = await r.json();
                                    return [j.html_body || '', j.text_body || '', j.text || '', j.body || ''].join(' ');
                                } catch (e) { return ''; }
                            }""", {"id": ctx["id"], "mid": mid, "token": ctx["token"]})
                            if body:
                                text = text + " " + body
                        except Exception:
                            pass
                    seen[mid] = text
                code = self._pick_code(text, keyword, stale)
                if code:
                    self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (API): {code}</b></font>')
                    return code
            # Heartbeat: never poll silently (a silent wait looks like a hang and
            # gets the run killed). Message count tells "no mail" from "mail but
            # unparsed" — the latter means the provider schema changed.
            if time.time() - last_beat >= 15:
                last_beat = time.time()
                try:
                    self.log(f'[📧] mail.td API: {len(msgs)} message(s), no {keyword} code yet…')
                except Exception:
                    pass
            # mail.td free API rate limit is 1 req/s — poll at 1.5s for margin.
            self.mail.wait_for_timeout(1500)
        return None

    def fetch_code(self, keyword, timeout=240):
        end = time.time() + timeout
        last_refresh = 0.0
        kw_in = (keyword or "").strip().lower()
        # Empty keyword (legacy password.py fallback) must NOT match everything:
        # default to instagram so row-click and code search stay scoped.
        kw = kw_in or "instagram"
        # Never reuse the Meta OTP when fetching a later (IG) code from the
        # same mail.td tab — the Meta mail stays visible and its code would
        # otherwise be returned again ("mixed up" codes). Persistent used-set
        # also skips already-tried "Authenticate your profile" codes across
        # retries (inbox stacks several of them).
        stale = set()
        try:
            stale.add(str(getattr(self, "meta_code", None) or ""))
        except Exception:
            pass
        try:
            used = getattr(self, "_used_email_codes", None) or set()
            stale |= set(str(x) for x in used)
        except Exception:
            pass
        stale.discard("")
        # If the mailbox tab is gone (closed/navigated), reopen mail.td rather
        # than silently looping on a dead page until timeout — the #1 cause of
        # "it can't go to mail and grab the OTP".
        try:
            if getattr(self, "mail", None) is None or self.mail.is_closed():
                self.log('[📧] Mail tab missing — reopening mail.td…')
                self.open_mailtd()
        except Exception as exc:
            self.log(f'[⚠️] Mail tab unavailable and could not reopen: {exc}')
            return None
        # Fast path: mail.td REST API (Bearer token, no DOM clicking). Falls
        # through to the DOM scraper if the API is unavailable/challenged.
        try:
            api_code = self._mailtd_api_code(kw, timeout=min(timeout, 60), stale=stale)
            if api_code:
                try:
                    used = getattr(self, "_used_email_codes", None) or set()
                    used.add(api_code)
                    self._used_email_codes = used
                except Exception:
                    pass
                return api_code
        except Exception as exc:
            self.log(f'[i] mail.td API fast path failed ({exc}); using DOM…')

        last_log = 0.0
        while time.time() < end and self.w.is_running:
            # 0. If an email DETAIL is open (back-arrow + Delete header, no
            # inbox list in DOM), go BACK to the list first — otherwise we
            # keep re-reading the same stale open mail forever.
            try:
                in_detail = self.mail.evaluate("""() => {
                    const hasList = !!document.querySelector('ul[class*="Mailbox_list"]');
                    if (hasList) return false;
                    const t = (document.body.innerText || '');
                    return t.includes('Confirm your email') || t.includes('Authenticate your profile');
                }""")
            except Exception:
                in_detail = False
            if in_detail:
                try:
                    back = self.mail.locator('button:has-text("←"), button:has-text("Back"), [aria-label*="Back" i]').first
                    if back.count() and back.is_visible():
                        back.click(timeout=2000)
                    else:
                        self.mail.evaluate("""() => {
                            const btns = Array.from(document.querySelectorAll('button'));
                            const b = btns.find(x => ((x.innerText || x.textContent) || '').trim() === '←' || ((x.getAttribute('aria-label') || '').toLowerCase().includes('back')));
                            if (b) b.click(); else if (btns.length) btns[0].click();
                        }""")
                except Exception:
                    pass
                self.mail.wait_for_timeout(1200)
                continue
            # Periodic Refresh (new mail.td UI: <button class="tBtn">Refresh</button>)
            now = time.time()
            if now - last_refresh >= 3.0:
                last_refresh = now
                try:
                    self.mail.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const ref = btns.find(b => (b.innerText || b.textContent || '').trim().toLowerCase() === 'refresh');
                        if (ref) ref.click();
                    }""")
                except Exception:
                    pass
            try:
                # Pushed origin/asif code only searched 'button' for "meta".
                # New mail.td renders rows as <li> inside ul[class*="Mailbox_list"]
                # (verified in page HTML) — buttons are only Copy/New/Custom/
                # History/Refresh/Delete, none contain "meta", so nothing was
                # ever clicked, the Meta detail never opened, and the 6-digit
                # code stayed hidden behind the list preview.
                self.mail.evaluate(
                    """(kw) => {
                        const k = (kw || 'instagram').toLowerCase();
                        const has = (el, s) => (((el.innerText || el.textContent) || '').toLowerCase().includes(s));
                        // 1. Direct: inbox <li> rows (skip the empty placeholder).
                        // mail.td lists NEWEST first. For instagram/2FA the rows
                        // read "Meta <noreply@account.meta.com> Authenticate your
                        // profile" — no "instagram" word — so take rows[0].
                        try {
                            const list = document.querySelector('ul[class*="Mailbox_list"]');
                            if (list) {
                                const rows = Array.from(list.querySelectorAll('li'))
                                    .filter(li => !(li.className || '').includes('empty') && ((li.innerText || li.textContent || '').trim().length > 0));
                                if (rows.length) {
                                    let row = null;
                                    if (k === 'meta') {
                                        row = rows.find(li => has(li, k) && (has(li, 'confirm') || has(li, 'notification@') || has(li, 'meta')))
                                            || rows.find(li => has(li, k) || has(li, 'confirm your email'));
                                    } else {
                                        row = rows.find(li => has(li, 'authenticate') || has(li, 'two-factor') || has(li, 'verification'))
                                            || rows.find(li => has(li, k))
                                            || rows[0];
                                    }
                                    if (row) { row.click(); return true; }
                                }
                            }
                        } catch (e) {}
                        // 2. Fallback: deepest (smallest-text) element with keyword —
                        // avoids clicking a huge outer container that does nothing.
                        try {
                            const els = Array.from(document.querySelectorAll('li, [role="button"], button, div'))
                                .filter(x => { const t = ((x.innerText || x.textContent) || '').toLowerCase(); return t.includes(k) || t.includes('confirm your email'); });
                            els.sort((a, b) => (((a.innerText || '').length) - ((b.innerText || '').length)));
                            if (els.length) { els[0].click(); return true; }
                        } catch (e) {}
                        return false;
                    }""", kw)
            except Exception:
                pass
            # Playwright-level fallback: click the newest row directly
            # (React/Next.js sometimes ignores synthetic evaluate clicks).
            # Instagram 2FA rows never contain the word "instagram".
            try:
                rows = self.mail.locator('ul[class*="Mailbox_list"] li')
                row = None
                if kw == "meta":
                    row = rows.filter(has_text="Meta").first
                else:
                    for _sel in ("Authenticate", "verification", "Meta"):
                        try:
                            cand = rows.filter(has_text=_sel).first
                            if cand.count() and cand.is_visible():
                                row = cand
                                break
                        except Exception:
                            continue
                    if row is None:
                        row = rows.first
                if row is not None and row.count() and row.is_visible():
                    row.click(timeout=2000)
            except Exception:
                pass
            self.mail.wait_for_timeout(800)
            try:
                txt = self._mail_text()
            except Exception:
                txt = ""
            # Strip CSS hex colors (#00FF00 etc.) so they never match as codes.
            # Length matters: Meta SIGNUP mails carry 6 digits, but Meta/IG
            # SECURITY mails ("Authenticate your profile", "modify settings")
            # carry 8 ("01993003" — slicing 6 off it submits a wrong code).
            # So: meta -> 6-digit first; instagram/security -> 8-digit first.
            found = self._pick_code(txt, kw, stale)
            if found:
                self.log(f'<font color="#00FF00"><b>[📧] {keyword} code: {found}</b></font>')
                try:
                    used = getattr(self, "_used_email_codes", None) or set()
                    used.add(found)
                    self._used_email_codes = used
                except Exception:
                    pass
                return found
            if time.time() - last_log >= 15.0:
                last_log = time.time()
                try:
                    self.log(f'[📧] Still waiting for the {keyword} mail — no matching code yet…')
                except Exception:
                    pass
            self.mail.wait_for_timeout(900)
        return None

    # -- steps --------------------------------------------------------------
