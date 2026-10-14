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
import secrets
import shutil
import sys
import time
import urllib.parse
import urllib.request

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import _MAILTD_URL  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _MAILTD_URL  # noqa: E402
try:
    from .eng_constants import CF_MAIL_ADMIN_TOKEN, CF_MAIL_DOMAIN, CF_MAIL_WORKER, YAMIN_MAIL_API, YAMIN_AUTH_KEY, YAMIN_DOMAINS  # package import
except ImportError:
    from eng_constants import CF_MAIL_ADMIN_TOKEN, CF_MAIL_DOMAIN, CF_MAIL_WORKER, YAMIN_MAIL_API, YAMIN_AUTH_KEY, YAMIN_DOMAINS  # noqa: E402

class EngineMailMixin:
    @staticmethod
    def _mailtd_address_from_page(page):
        """Read the current mailbox address from the current mail.td UI.

        mail.td renders the address in a dedicated ``code`` element.  The
        old implementation searched the entire body for an e-mail pattern;
        that is fragile because the page also contains support/footer text and
        initially renders only a pending placeholder.  Read the address card
        first, then use visible e-mail inputs as a compatibility fallback.
        """
        pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        try:
            values = page.locator(
                'code[class*="CredentialCard_addr"], '
                '[class*="CredentialCard_addr"], '
                'input[type="email"], input[name*="address" i], '
                '[data-address], [data-email]'
            ).evaluate_all(
                """els => els.flatMap(el => [
                    el.innerText || '', el.textContent || '',
                    el.value || '', el.getAttribute('data-address') || '',
                    el.getAttribute('data-email') || '',
                    el.getAttribute('aria-label') || ''
                ])"""
            )
            for value in values:
                m = re.search(pattern, str(value or ""))
                if m:
                    return m.group(0)
        except Exception:
            pass
        return None

    # mail.td says "no" through its API reply. That is final for this attempt, so the caller stops waiting at
    # once and the provider chain moves on: HTTP 429 / 403 on /api/accounts (rate limit) or
    # {"error": "ops_quota_exceeded"} (free-plan monthly quota).
    # NOT used: a 200 {"status": "retry"} (the proof-of-work asking for a higher difficulty) and the page text —
    # a live check showed "Operations used up" in the page text while a mailbox was being created normally.
    @staticmethod
    def _mailtd_limit_reason(responses, page_text=""):
        """'' while mail.td is merely slow; otherwise a short reason string for the log."""
        for r in responses or []:
            status = int(r.get("status") or 0)
            body = str(r.get("body") or "")
            if "ops_quota_exceeded" in body:
                return f"free-plan quota used up (HTTP {status})"
            if status in (429, 403):
                return f"rate limited (HTTP {status} {body[:80]})"
        return ""

    def _mailtd_limit_now(self, page, responses):
        return self._mailtd_limit_reason(responses)

    def open_mailtd(self):
        # A reused runner must never accidentally reuse the previous cycle's
        # address while the new mail.td page is still initializing.
        self.email = None
        self.mail = self.w.context.new_page()
        # Record every mailbox-creation reply (also the page's own automatic one) so a limit is seen at once.
        _early = []

        def _on_early(response):
            try:
                if "/api/accounts" in response.url and response.request.method == "POST":
                    _early.append({"status": response.status, "body": response.text()[:300]})
            except Exception:
                pass
        try:
            self.mail.on("response", _on_early)
        except Exception:
            pass
        self.mail.goto(_MAILTD_URL, wait_until="domcontentloaded", timeout=60000)
        self.mail.wait_for_timeout(4000)

        # Normally the page mints an inbox during idle time.  In an automated
        # context mail.td intentionally suppresses that auto-mint, leaving the
        # address card as ``·········``.  In that case explicitly click New.
        for _ in range(20):
            addr = self._mailtd_address_from_page(self.mail)
            if addr:
                self.email = addr
                break
            _why = self._mailtd_limit_now(self.mail, _early)
            if _why:
                self.log(f"[⚠️] mail.td refused a new mailbox: {_why} — not waiting any longer.")
                raise RuntimeError(f"mail.td limit: {_why}")
            self.mail.wait_for_timeout(1000)
        try:
            self.mail.remove_listener("response", _on_early)
        except Exception:
            pass

        if not self.email:
            self.log("[📧] mail.td has no address yet; requesting a new mailbox…")
            addr = self.new_mailtd_address(timeout=75)
            if addr:
                self.email = addr

        if not self.email:
            raise RuntimeError("could not read mail.td address")
        self.log(f'<font color="#00FF00"><b>[📧] Meta inbox: {self.email}</b></font>')

    def new_mailtd_address(self, timeout: int = 40):
        """Create a fresh mailbox through mail.td's live proof-of-work flow.

        mail.td suppresses automatic mailbox creation for automated contexts.
        On a fresh page the primary action is labeled ``Get an address``; after
        an address exists, the refresh action is labeled ``New``.  The page
        must perform the proof-of-work itself, so this method deliberately
        clicks the UI instead of recreating mailbox creation over HTTP.
        """
        mail = getattr(self, "mail", None) or getattr(self, "page", None)
        if mail is None:
            return None

        old = (getattr(self, "email", "") or "").strip().lower()
        # Snapshot the CURRENT mailbox's API context (account id + token) BEFORE
        # clicking "New". fetch_code() reads these LIVE from localStorage, so if
        # they have not switched to the new mailbox by the time the OTP is polled,
        # the lookup hits the OLD inbox and the extra email NEVER completes
        # (observed 2026-09-28 on the FastPay/Taskly extra-email step).
        try:
            old_ctx = self._mailtd_api_ctx() or {}
        except Exception:
            old_ctx = {}
        create_responses = []

        def on_response(response):
            if "/api/accounts" not in response.url:
                return
            try:
                method = response.request.method
            except Exception:
                method = "?"
            if method != "POST":
                return
            try:
                body = response.text()
            except Exception as exc:
                body = f"<response body unavailable: {exc}>"
            item = {"status": response.status, "body": body[:500]}
            create_responses.append(item)
            try:
                self.log(
                    f"[📧] mail.td create response: HTTP {response.status} "
                    f"{body[:300]}"
                )
            except Exception:
                pass

        mail.on("response", on_response)
        selectors = [
            'button:has-text("Get an address")',
            'button:has-text("New")',
            'button:has-text("↻ New")',
            'button[aria-label*="address" i]',
            'button[aria-label*="new" i]',
        ]
        if old:
            # For an already-created inbox, prefer the refresh action over the
            # initial/empty-state action.
            selectors = [
                'button:has-text("New")',
                'button:has-text("↻ New")',
                'button[aria-label*="new" i]',
                'button:has-text("Get an address")',
            ]

        clicked = False
        try:
            seen = set()
            for selector in selectors:
                if selector in seen:
                    continue
                seen.add(selector)
                try:
                    locator = mail.locator(selector).first
                    if locator.count() and locator.is_visible():
                        locator.click(timeout=10000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                # The localized/mangled glyphs in some Windows console output
                # do not affect the DOM, but the primary button class is stable.
                try:
                    locator = mail.locator("button.cSolid").first
                    if locator.count() and locator.is_visible():
                        locator.click(timeout=10000)
                        clicked = True
                except Exception:
                    pass

            if not clicked:
                try:
                    self.log("[⚠️] mail.td: no mailbox creation action was available")
                except Exception:
                    pass
                return None

            end = time.time() + max(5, timeout)
            while time.time() < end:
                mail.wait_for_timeout(1000)
                addr = self._mailtd_address_from_page(mail)
                if not addr:
                    _why = self._mailtd_limit_now(mail, create_responses)
                    if _why:
                        try:
                            self.log(f"[⚠️] mail.td refused a new mailbox: {_why} — not waiting any longer.")
                        except Exception:
                            pass
                        return None
                if addr:
                    addr = addr.lower()
                    if addr != old:
                        try:
                            self.log(
                                f'<font color="#00FF00"><b>[📧] Extra temp mailbox: {addr}</b></font>'
                            )
                        except Exception:
                            pass
                        # Wait until mail.td PERSISTS the new mailbox's
                        # token/account id. fetch_code() reads them live; a stale
                        # token points the OTP lookup at the OLD inbox, so the
                        # extra email is never confirmed ("doesn't complete").
                        self._wait_mailtd_ctx_switch(old_ctx, timeout=20)
                        return addr

            if create_responses:
                try:
                    self.log(
                        "[⚠️] mail.td mailbox creation finished without an address; "
                        f"last API response: {create_responses[-1]}"
                    )
                except Exception:
                    pass
            return None
        finally:
            try:
                mail.remove_listener("response", on_response)
            except Exception:
                pass

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

    def _pick_code(self, text, keyword, stale, prefer_len=None):
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
        if prefer_len == 8:
            pats = [
                r"(?:code|verification|verify|confirm|otp|authenticate|identity)[^\d]{0,60}(\d{8})(?!\d)",
                r"\b(\d{8})\b",
            ]
        elif (keyword or "").lower() == "meta" or prefer_len == 6:
            pats = [
                r"(?:code|verification|verify|confirm|otp)[^\d]{0,60}(\d{6})(?!\d)",
                r"\b(\d{6})\b",
            ]
        else:
            pats = [
                r"(?:code|verification|verify|confirm|otp|authenticate|identity)[^\d]{0,60}(\d{8}|\d{6})",
                r"\b(\d{8})\b",
                r"\b(\d{6})\b",
            ]
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

    def _wait_mailtd_ctx_switch(self, old_ctx, timeout=20):
        """Block until mail.td's stored mailbox id/token differ from ``old_ctx``.

        ``new_mailtd_address()`` returns as soon as the on-page ADDRESS changes,
        but the mail.td SPA persists the new mailbox's credential a moment later.
        ``fetch_code`` reads the credential LIVE, so returning early made the OTP
        lookup hit the OLD inbox — the extra email was minted but NEVER confirmed
        ("doesn't complete"). Best-effort, hard-capped.
        """
        old_id = str((old_ctx or {}).get("id") or "")
        old_tok = str((old_ctx or {}).get("token") or "")
        end = time.time() + max(1, timeout)
        while time.time() < end:
            try:
                ctx = self._mailtd_api_ctx() or {}
            except Exception:
                ctx = {}
            cid, ctok = str(ctx.get("id") or ""), str(ctx.get("token") or "")
            if cid and (cid != old_id or (ctok and old_tok and ctok != old_tok)):
                try:
                    self.log(f'[📧] mail.td mailbox switched (id={cid[:8]}…) — '
                             'the extra-email OTP will be read from the NEW inbox.')
                except Exception:
                    pass
                return True
            try:
                self.mail.wait_for_timeout(500)
            except Exception:
                time.sleep(0.5)
        try:
            self.log('[⚠️] mail.td did not persist the new mailbox in time — the '
                     'extra-email OTP may be read from the OLD inbox.')
        except Exception:
            pass
        return False

    def _mailtd_api_code(self, keyword, timeout, stale, subject_hint=None, prefer_len=None):
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

            # Sort newest messages first so we never match an old email's code.
            # mail.td returns ``created_at`` (snake_case, ISO-8601 with offset) —
            # NOT camelCase. Listing only ``createdAt``/``updatedAt`` fell through
            # to ``id`` (a UUID), so the order was ARBITRARY and an OLD code could
            # be returned (the "This code doesn't work" stale-code class). Check
            # every known spelling before falling back to id.
            try:
                msgs = sorted(
                    msgs,
                    key=lambda m: str(m.get("created_at") or m.get("createdAt")
                                      or m.get("updated_at") or m.get("updatedAt")
                                      or m.get("id") or ""),
                    reverse=True,
                )
            except Exception:
                pass

            for msg in msgs:
                mid = msg.get("id")
                subject = str(msg.get("subject") or "").lower()
                sender = str(msg.get("from") or "").lower()

                # If subject_hint is specified, skip messages that don't match
                if subject_hint:
                    hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                    if not any(h in subject or h in sender for h in hints):
                        continue

                # Body is in the detail endpoint — fetch it for the candidate message
                text = seen.get(mid)
                if text is None and mid:
                    try:
                        detail = self.mail.evaluate("""async ({id, mid, token}) => {
                            try {
                                const r = await fetch('/api/accounts/' + id + '/messages/' + mid,
                                    {headers: {Authorization: 'Bearer ' + token}});
                                if (!r.ok) return '';
                                const j = await r.json();
                                return [j.subject || '', j.html_body || '', j.text_body || '', j.text || '', j.body || ''].join(' ');
                            } catch (e) { return ''; }
                        }""", {"id": ctx["id"], "mid": mid, "token": ctx["token"]})
                        text = detail or " ".join(self._flatten_values(msg))
                    except Exception:
                        text = " ".join(self._flatten_values(msg))
                    seen[mid] = text

                code = self._pick_code(text or "", keyword, stale, prefer_len=prefer_len)
                if code:
                    self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (API): {code} (subject: {subject[:40]})</b></font>')
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

    def fetch_code(self, keyword, timeout=240, subject_hint=None, prefer_len=None, **kwargs):
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
            api_code = self._mailtd_api_code(
                kw,
                timeout=min(timeout, 60),
                stale=stale,
                subject_hint=subject_hint,
                prefer_len=prefer_len,
            )
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

    # -- Cloudflare catch-all provider (no browser tab) --------------------
    _CF_FIRST_NAMES = (
        "alex", "sarah", "daniel", "emma", "liam", "olivia", "noah", "ava",
        "ethan", "mia", "lucas", "chloe", "james", "grace", "owen", "zoe",
    )
    _CF_LAST_NAMES = (
        "miller", "smith", "clark", "davis", "wilson", "brown", "taylor", "moore",
        "jackson", "martin", "lee", "walker", "hall", "allen", "young", "king",
    )

    def new_mailcf_address(self, timeout: int = 10):
        """Generate a natural-looking address on the Cloudflare catch-all domain."""
        first = random.choice(self._CF_FIRST_NAMES)
        last = random.choice(self._CF_LAST_NAMES)
        addr = f"{first}.{last}.{random.randint(10, 999)}@{CF_MAIL_DOMAIN}"
        self.email = addr
        self.mail_token = secrets.token_urlsafe(24)
        self._register_mailcf(addr, self.mail_token)
        return addr

    def _register_mailcf(self, addr: str, token: str) -> None:
        """Tell the Worker which read token belongs to this address (needs CF_MAIL_ADMIN_TOKEN)."""
        if not CF_MAIL_ADMIN_TOKEN:
            self.log("[⚠️] CF_MAIL_ADMIN_TOKEN not set; mailbox read token not registered.")
            return
        req = urllib.request.Request(
            f"{CF_MAIL_WORKER}/register",
            data=json.dumps({"email": addr, "token": token}).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CF_MAIL_ADMIN_TOKEN}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as exc:
            self.log(f"[⚠️] Could not register mailbox read token for {addr}: {exc}")

    def open_mailcf(self):
        """Allocate an address only: no page, no browser tab, no RAM cost."""
        self.mail = None
        self.new_mailcf_address()
        self.log(f"[📧] Cloudflare Catch-All allocated: {self.email} (zero browser tab overhead)")
        return self.email

    def fetch_code_cf(self, keyword: str = "meta", timeout: int = 180, subject_hint=None, prefer_len=None):
        """Poll the OTP Worker over HTTP until the code for self.email arrives."""
        url = f"{CF_MAIL_WORKER}?email={urllib.parse.quote(self.email)}"
        start = time.time()
        while time.time() - start < timeout:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8", "replace"))
            except Exception:
                data = {}
            code = data.get("code") if isinstance(data, dict) else None
            if code:
                self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (Cloudflare Worker): {code}</b></font>')
                return str(code)
            time.sleep(2.5)
        raise RuntimeError(f"{keyword.capitalize()} confirmation code not received on Cloudflare Worker within {timeout}s")

    # -- tempmail.fish browser provider ------------------------------------
    def open_mailfish(self):
        """Open a fresh tempmail.fish inbox in the current browser context."""
        self.email = None
        self.mail = self.w.context.new_page()
        self.mail.goto("https://tempmail.fish/", wait_until="domcontentloaded", timeout=60000)
        self.mail.wait_for_timeout(3000)

        # 1. Read address from #emailInput or localStorage
        for _ in range(25):
            try:
                inp = self.mail.locator("#emailInput").first
                if inp.count() and inp.is_visible():
                    val = (inp.input_value() or "").strip().lower()
                    if "@" in val and "." in val:
                        self.email = val
                        break
            except Exception:
                pass
            try:
                raw = self.mail.evaluate("() => localStorage.getItem('email')")
                if raw:
                    import json
                    val = str(json.loads(raw) if raw.startswith('"') else raw).strip().lower()
                    if "@" in val and "." in val:
                        self.email = val
                        break
            except Exception:
                pass
            self.mail.wait_for_timeout(1000)

        # 2. If no address appeared, trigger New Email
        if not self.email:
            self.log("[📧] tempmail.fish has no address yet; clicking New Email…")
            addr = self.new_mailfish_address(timeout=30)
            if addr:
                self.email = addr

        if not self.email:
            raise RuntimeError("could not read tempmail.fish address")

        self.log(f'<font color="#00FF00"><b>[📧] Meta inbox (tempmail.fish): {self.email}</b></font>')

    def new_mailfish_address(self, timeout: int = 30):
        """Generate a fresh mailbox on tempmail.fish by clicking New Email."""
        mail = getattr(self, "mail", None)
        if mail is None:
            return None

        old = (getattr(self, "email", "") or "").strip().lower()

        try:
            btn = mail.locator('button:has-text("New Email")').first
            if btn.count() and btn.is_visible():
                btn.click(timeout=10000)
        except Exception:
            pass

        end = time.time() + max(5, timeout)
        while time.time() < end:
            mail.wait_for_timeout(1000)
            try:
                inp = mail.locator("#emailInput").first
                if inp.count() and inp.is_visible():
                    val = (inp.input_value() or "").strip().lower()
                    if "@" in val and "." in val and val != old:
                        self.email = val
                        self.log(f'<font color="#00FF00"><b>[📧] Fresh tempmail.fish address: {val}</b></font>')
                        return val
            except Exception:
                pass
            try:
                raw = mail.evaluate("() => localStorage.getItem('email')")
                if raw:
                    import json
                    val = str(json.loads(raw) if raw.startswith('"') else raw).strip().lower()
                    if "@" in val and "." in val and val != old:
                        self.email = val
                        self.log(f'<font color="#00FF00"><b>[📧] Fresh tempmail.fish address: {val}</b></font>')
                        return val
            except Exception:
                pass
        return None

    def fetch_code_mailfish(self, keyword: str = "meta", timeout: int = 240, subject_hint=None, prefer_len=None):
        """Poll incoming messages from the tempmail.fish browser tab."""
        if not getattr(self, "mail", None) or self.mail.is_closed():
            self.log("[⚠️] tempmail.fish tab is closed; reopening…")
            self.open_mailfish()

        stale = set(getattr(self, "_seen_codes", None) or set())
        last_beat = time.time()
        end = time.time() + timeout

        self.log(f"[📧] Waiting for {keyword} email on tempmail.fish ({self.email})…")

        while time.time() < end:
            msgs = []
            try:
                msgs = self.mail.evaluate("""async (email) => {
                    try {
                        let rawKey = localStorage.getItem("authKey") || "";
                        let authKey = rawKey.startsWith('"') ? JSON.parse(rawKey) : rawKey;
                        let r = await fetch("https://api.tempmail.fish/emails/emails?emailAddress=" + encodeURIComponent(email), {
                            headers: authKey ? {"Authorization": authKey} : {}
                        });
                        if (!r.ok) return [];
                        return await r.json();
                    } catch (e) {
                        return [];
                    }
                }""", self.email)
            except Exception:
                msgs = []

            if not isinstance(msgs, list):
                msgs = []

            for msg in msgs:
                if not isinstance(msg, dict):
                    continue
                subject = str(msg.get("subject") or "").lower()
                sender = str(msg.get("from") or msg.get("sender") or "").lower()

                if subject_hint:
                    hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                    if not any(h in subject or h in sender for h in hints):
                        continue

                text = " ".join([
                    subject,
                    str(msg.get("body") or ""),
                    str(msg.get("text") or ""),
                    str(msg.get("html") or ""),
                    str(msg.get("content") or ""),
                    " ".join(self._flatten_values(msg))
                ])

                code = self._pick_code(text, keyword, stale, prefer_len=prefer_len)
                if code:
                    self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (tempmail.fish): {code} (subject: {subject[:40]})</b></font>')
                    try:
                        used = getattr(self, "_used_email_codes", None) or set()
                        used.add(code)
                        self._used_email_codes = used
                    except Exception:
                        pass
                    return code

            # Also check DOM text in case message rendered directly
            try:
                dom_text = self._mail_text()
                code = self._pick_code(dom_text or "", keyword, stale, prefer_len=prefer_len)
                if code:
                    self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (tempmail.fish DOM): {code}</b></font>')
                    try:
                        used = getattr(self, "_used_email_codes", None) or set()
                        used.add(code)
                        self._used_email_codes = used
                    except Exception:
                        pass
                    return code
            except Exception:
                pass

            if time.time() - last_beat >= 15:
                last_beat = time.time()
                try:
                    self.log(f'[📧] tempmail.fish: {len(msgs)} message(s), no {keyword} code yet…')
                except Exception:
                    pass

            self.mail.wait_for_timeout(2000)

        raise RuntimeError(f"{keyword.capitalize()} confirmation code not received on tempmail.fish within {timeout}s")

    # -- yamin.bd APK provider ---------------------------------------------
    YAMIN_MAIL_API = YAMIN_MAIL_API
    YAMIN_AUTH_KEY = YAMIN_AUTH_KEY
    YAMIN_DOMAINS = YAMIN_DOMAINS

    def open_yamin(self):
        """Allocate an address only: zero browser tab overhead (yamin.bd API)."""
        self.mail = None
        self.new_yamin_address()
        self.log(f'[📧] Yamin Mailbox allocated: {self.email} (zero browser tab overhead)')
        return self.email

    def new_yamin_address(self, timeout: int = 10):
        """Generate a natural-looking address on Yamin domains (epicz.xyz only)."""
        domains = getattr(self, "YAMIN_DOMAINS", ("epicz.xyz",))
        domain = random.choice(domains)
        first = random.choice(self._CF_FIRST_NAMES)
        last = random.choice(self._CF_LAST_NAMES)
        user = f"{first}.{last}.{random.randint(100, 9999)}"
        self.email = f"{user}@{domain}"
        self.yamin_user = user
        self.yamin_domain = domain
        return self.email

    def fetch_code_yamin(self, keyword: str = "instagram", timeout: int = 180, subject_hint=None, prefer_len=None):
        """Poll email.yamin.bd over HTTP until the code for self.email arrives."""
        email = getattr(self, "email", "") or ""
        if "@" in email:
            user, domain = email.split("@", 1)
        else:
            user = getattr(self, "yamin_user", "")
            domain = getattr(self, "yamin_domain", "epicz.xyz")

        base_url = getattr(self, "YAMIN_MAIL_API", "https://email.yamin.bd")
        auth_key = getattr(self, "YAMIN_AUTH_KEY", "yamin12134@!")
        headers = {
            "Authorization": auth_key,
            "X-Api-Key": auth_key,
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36",
        }

        list_url = f"{base_url}/?action=getMessages&user={urllib.parse.quote(user)}&domain={urllib.parse.quote(domain)}"
        start = time.time()
        self.log(f"[📧] Polling Yamin API for {keyword} code: {user}@{domain}...")

        while time.time() - start < timeout:
            try:
                req = urllib.request.Request(list_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    messages = json.loads(resp.read().decode("utf-8", "replace"))
            except Exception:
                messages = []

            if isinstance(messages, list) and len(messages) > 0:
                candidate_ids = []
                for m in messages:
                    if not isinstance(m, dict):
                        continue
                    mid = str(m.get("id") or "").strip()
                    if not mid:
                        continue
                    m_from = str(m.get("from") or "").lower()
                    if any(k in m_from for k in ("meta.com", "instagram", "facebook")) or not candidate_ids:
                        candidate_ids.append((m.get("timestamp") or 0, mid))

                candidate_ids.sort(key=lambda x: x[0], reverse=True)

                for _, mid in candidate_ids:
                    read_url = f"{base_url}/?action=readMessage&user={urllib.parse.quote(user)}&domain={urllib.parse.quote(domain)}&id={urllib.parse.quote(mid)}"
                    try:
                        r_req = urllib.request.Request(read_url, headers=headers)
                        with urllib.request.urlopen(r_req, timeout=10) as r_resp:
                            msg_body = json.loads(r_resp.read().decode("utf-8", "replace"))
                    except Exception:
                        msg_body = {}

                    if isinstance(msg_body, dict):
                        extracted = str(msg_body.get("code_extracted") or "").strip()
                        if extracted and re.match(r"^\d{6,8}$", extracted):
                            self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (Yamin API): {extracted}</b></font>')
                            return extracted

                        html = str(msg_body.get("htmlBody") or msg_body.get("body") or "")
                        if html:
                            clean = re.sub(r'(?is)<(style|script)[^>]*>.*?</\1>', ' ', html)
                            text = re.sub(r'<[^>]+>', ' ', clean)
                            m_code = re.search(r'(?i)code[^0-9]{0,80}?\b(\d{6,8})\b', text)
                            if not m_code:
                                m_code = re.search(r'\b(\d{6})\b', text)
                            if m_code:
                                code = m_code.group(1)
                                self.log(f'<font color="#00FF00"><b>[📧] {keyword} code (Yamin HTML parse): {code}</b></font>')
                                return code

            time.sleep(2.5)

        raise RuntimeError(f"{keyword.capitalize()} confirmation code not received on Yamin Mail API within {timeout}s")

    # -- steps --------------------------------------------------------------
