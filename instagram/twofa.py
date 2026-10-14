"""TOTP 2FA key scraping & verification (page-scrape, never clipboard). Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides run._MetaInstagramRunner helpers."""
from __future__ import annotations

import os
import random
import sys
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_config import TWOFA_KEY_RE, Urls  # noqa: E402

try:  # package-relative first, then flat (engine imports both ways)
    from .helpers import IGDeadEnd
except ImportError:  # pragma: no cover
    from instagram.helpers import IGDeadEnd  # type: ignore


class IgTwofaMixin:
    """TOTP 2FA key scraping & verification (page-scrape, never clipboard)."""

    def ig_scrape_2fa_key(self, page) -> Optional[str]:
        """Read the Base32 2FA key from page text, input elements, data attributes, or QR payload.
        Mirrors APK Instatool (eo.java:270) carrier extraction and reveal mechanisms.
        """
        import re

        # Only the key screen carries a key. Seen live (2026-10-12): the intro heading "Set up extra
        # protection for your Meta Account" passed the loose text filter below (letters only, spaces
        # removed = a valid base32 string), so a junk "key" was sent to the bot and every code was
        # then rejected. On Accounts Center, refuse to scrape anywhere else.
        try:
            _is_ac = "accountscenter.instagram.com" in (page.url or "")
        except Exception:
            _is_ac = False
        if _is_ac:
            try:
                _bl = (page.evaluate("() => document.body.innerText || ''") or "").lower()
            except Exception:
                _bl = ""
            if not any(m in _bl for m in ("copy key", "instructions for setup",
                                          "scan this barcode", "download an authentication app")):
                return None

        def _is_valid_key(s: str) -> bool:
            if not s:
                return False
            clean = re.sub(r"[\s\u00a0]+", "", s).upper()
            if not (16 <= len(clean) <= 64):
                return False
            if not re.fullmatch(r"[A-Z2-7]+", clean):
                return False
            ui_words = ("AUTHENTICATOR", "GOOGLEAUTH", "DUOMOBILE", "DOWNLOADAN",
                        "AUTHENTICATIONAPP", "INSTRUCTIONSFOR", "BARCODEORQR",
                        "PASSWORDAND", "TWOFACTOR", "SECURITYCODE", "ACCOUNTSCENTER",
                        "INSTAGRAM", "YOURCODEFROMYOUR")
            if any(w in clean for w in ui_words):
                return False
            return True

        # 1. Comprehensive carrier extraction (text, input values, data-clipboard-text, code, pre)
        try:
            candidates = page.evaluate(r"""() => {
                const results = [];
                for (const el of document.querySelectorAll('[data-clipboard-text], [data-copy-text]')) {
                    const c = el.getAttribute('data-clipboard-text') || el.getAttribute('data-copy-text') || '';
                    if (c) results.push(c);
                }
                for (const el of document.querySelectorAll('input, textarea')) {
                    const val = el.value || '';
                    if (val && val.length >= 16 && (el.readOnly || el.disabled || el.type === 'text' || !el.type)) {
                        results.push(val);
                    }
                }
                for (const el of document.querySelectorAll('code, pre, kbd, [role="textbox"]')) {
                    const t = el.innerText || el.textContent || '';
                    if (t) results.push(t);
                }
                for (const el of document.querySelectorAll('span, div, p, li')) {
                    const t = (el.innerText || '').trim();
                    if (t.length >= 16 && t.length <= 96 && /^[A-Z2-7\s\u00a0]+$/.test(t)) {
                        results.push(t);
                    }
                }
                return results;
            }""") or []

            for cand in candidates:
                if re.search(r"[a-z]", str(cand)):
                    continue            # a real key is upper-case; words/headings never are
                cand_clean = re.sub(r"[\s\u00a0]+", "", str(cand)).upper()
                if _is_valid_key(cand_clean):
                    return cand_clean
        except Exception:
            pass

        # 2. Regex match for space-separated groups from page text (e.g. 'RAPQ K7VM RJF7 3CDC')
        try:
            text = page.evaluate("() => document.body.innerText || ''")
            m = TWOFA_KEY_RE.search(text or "")
            if m:
                cleaned = re.sub(r"[\s\u00a0]+", "", m.group(0)).upper()
                if _is_valid_key(cleaned):
                    return cleaned
        except Exception:
            pass

        # 3. Continuous 16 to 64 character Base32 string from body text
        try:
            text = page.evaluate("() => document.body.innerText || ''")
            for m in re.finditer(r"\b([A-Z2-7]{16,64})\b", text or ""):
                val = m.group(1).strip()
                if _is_valid_key(val):
                    return val
        except Exception:
            pass

        # 4. Barcode / QR image extraction: inspect element attributes for otpauth payload
        try:
            qr_uri = page.evaluate(r"""() => {
                for (const el of document.querySelectorAll('img, svg, div, a')) {
                    const s = (el.getAttribute('src') || el.getAttribute('data-uri') || el.getAttribute('href') || '');
                    if (s.includes('otpauth://') && s.includes('secret=')) return s;
                }
                const body = document.body.innerHTML || '';
                const m = body.match(/otpauth:\/\/([^"'\s<>]+)/);
                return m ? m[0] : null;
            }""")
            if qr_uri:
                m_sec = re.search(r"secret=([A-Za-z2-7]+)", qr_uri)
                if m_sec and _is_valid_key(m_sec.group(1)):
                    return m_sec.group(1).strip().upper()
        except Exception:
            pass

        # 5. Reveal trigger (APK parity eo.java:270): key might be hidden behind QR
        try:
            for phrase in (
                "can't scan it", "can't scan", "cannot scan", "copy setup key",
                "copy the key", "copy key", "set up manually", "setup manually",
                "enter setup key", "enter key manually", "or enter manually"
            ):
                rev = page.locator(f'[role="button"]:has-text("{phrase}"), button:has-text("{phrase}"), a:has-text("{phrase}")').first
                if rev.count() > 0 and rev.is_visible():
                    self._tap_or_click(page, rev, timeout=1500)
                    page.wait_for_timeout(800)
                    break
        except Exception:
            pass

        return None

    def _ac_recover_transient(self, p, max_attempts: int = 2) -> bool:
        """Detect and recover from Accounts Center / Instagram 'Something went wrong' / 'This page isn't available right now' / 'Reload page' / 'This content is no longer available'."""
        if self._recover_something_went_wrong(p, max_attempts=max_attempts):
            return True
        try:
            if self._dismiss_scraping_warning(p):
                return True
        except Exception:
            pass
        low = self._page_tail(p, 400).lower()
        if "isn't available" in low or "reload page" in low or "technical error" in low or "no longer available" in low or "something went wrong" in low:
            self.log('[ac] Accounts Center transient error persists — taking Way Out escape…')
            return self._way_out_escape(p)
        return False

    _AC_TWO_FACTOR_URL = "https://accountscenter.instagram.com/password_and_security/two_factor/"

    def _ac_dismiss_toast(self, p) -> bool:
        """Close Accounts Center's snackbar ("Meta Account password updated"). It floats over the
        dialog's primary button and swallows the first click on it (seen live via the DevTools MCP,
        2026-10-12: Get started needed a second try until the toast was closed)."""
        try:
            return bool(p.evaluate("""() => {
                const alerts = [...document.querySelectorAll('[role="alert"]')]
                    .filter(a => /updated|saved|changed/i.test(a.textContent || ''));
                for (const a of alerts) {
                    let n = a;
                    for (let i = 0; i < 5 && n; i++, n = n.parentElement) {
                        const b = [...n.querySelectorAll('[role="button"],button')].find(x =>
                            /close/i.test((x.getAttribute('aria-label') || '') + (x.textContent || ''))
                            && !x.closest('[role="dialog"]'));
                        if (b) { b.click(); return true; }
                    }
                }
                return false;
            }"""))
        except Exception:
            return False

    def _ig_2fa_open_code_screen(self, p) -> bool:
        """Open the empty "Enter code" screen BEFORE the bot is asked for its code.

        PayGo starts verifying the account the moment it sends the one-time code and only
        accepts if Instagram's 2FA is already on ~30 s later. Seen live (2026-10-12): the
        report was accepted when the code went in within seconds, and rejected ("You did not
        set up 2FA") when opening this screen after the code made the confirm take too long."""
        sel = ('input[placeholder*="code" i], input[aria-label*="code" i], '
               'input[name="verificationCode"], input[type="text"]')
        try:
            if p.locator(sel).first.is_visible():
                return True
            if self._try_click(p, "Enter code", timeout=4000):
                for _ in range(16):
                    p.wait_for_timeout(250)
                    if p.locator(sel).first.is_visible():
                        return True
        except Exception:
            pass
        return False

    def _ig_2fa_direct_begin(self) -> Optional[str]:
        """The 2FA entry exactly as driven by hand through the DevTools MCP: open the two-factor
        page by URL (it loads with the live session, no Accounts Center bounce), close the toast,
        Get started -> Authentication app -> Continue, then read the 4x4 key. Every transition is
        verified and retried; the email challenge is solved if it shows up."""
        p = self._ig_tab()
        for attempt in range(2):
            try:
                p.goto(self._AC_TWO_FACTOR_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:  # noqa: BLE001
                self.log(f'[2fa] direct entry load note: {str(exc)[:80]}')
            p.wait_for_timeout(1500)
            if "accountscenter.instagram.com" not in (p.url or ""):
                self.log(f'[2fa] direct entry left Accounts Center (url={(p.url or "")[:80]}) — giving up on the direct route')
                return None
            if self._is_ig_dead_end_chooser(p):
                raise IGDeadEnd("IG saved-account chooser detected during 2FA entry (session dropped) — aborting immediately")
            for _step in range(16):
                self._ac_dismiss_toast(p)
                try:
                    low = (p.inner_text("body", timeout=2500) or "").lower()
                except Exception:
                    low = ""
                key = self.ig_scrape_2fa_key(p)
                if key:
                    self._ig_2fa_open_code_screen(p)
                    return key
                if "check your email" in low or "enter the code we sent" in low or "two step verification" in low:
                    self._ac_reauth(p)
                    p.wait_for_timeout(900)
                    continue
                if "choose an account" in low:
                    # "Choose an account to set up two-factor authentication": the INSTAGRAM row
                    # (the bot logs into Instagram, not into the Meta AI profile).
                    if not self._ac_pick_profile_row(p, "instagram"):
                        try:
                            self._ac_choose_account(p, prefer_instagram=True)
                        except Exception:
                            pass
                    p.wait_for_timeout(300)
                    continue
                if self._visible(p, "radio", "Authentication app") is not None:
                    self._try_click(p, "Authentication app", role="radio", timeout=2000)
                    self._try_click(p, "Continue", timeout=4000)
                elif self._visible(p, "button", "Get started") is not None:
                    self._try_click(p, "Get started", timeout=4000)
                p.wait_for_timeout(1200)
            self.log(f'[2fa] direct entry attempt {attempt + 1}/2 did not reach the key — {self._page_tail(p, 160)}')
        return None

    def ig_2fa_begin(self) -> Optional[str]:
        """Start 2FA setup, capture the base32 key, leave the 'Enter code' screen open."""
        p = self._ig_tab()
        self.log('[🔐] Instagram: starting 2FA (Authentication app)…')
        try:
            names = [c["name"] for c in self.w.context.cookies(Urls.IG_HOME)]
            self.log(f'[ac] ig cookies: {sorted(set(names))}')
        except Exception as exc:  # noqa: BLE001
            self.log(f'[ac] cookie dump failed: {exc}')

        try:
            _direct = self._ig_2fa_direct_begin()
        except IGDeadEnd:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log(f'[2fa] direct entry error: {str(exc)[:100]}')
            _direct = None
        if _direct:
            self.insta_secret = _direct
            self.log('<font color="#00FF00"><b>[🔑] 2FA key captured.</b></font>')
            return _direct
        if os.environ.get("PAYGO_SLOW_WALK", "0") != "1":
            self.log('[⚠️] 2FA: the direct entry did not reach the key — giving up on this account '
                     '(no section walk; PAYGO_SLOW_WALK=1 re-enables it).')
            return None
        self.log('[2fa] direct entry did not reach the key — falling back to the section walk')

        self._ac_section("/password_and_security/", "Password and security")
        p = self._ig_tab()

        if "accountscenter.instagram.com" not in (p.url or ""):
            self.log(f'[⚠️] 2FA setup halted: Not inside Accounts Center (url={p.url})')
            return None

        # The 2FA step must land on the TWO-FACTOR sub-page, NEVER the password
        # sub-page. _ac_in_section() batches both under /password_and_security/,
        # so an Accounts Center already sitting on password/change satisfies the
        # section check — and the 2FA step would open the CHANGE-PASSWORD modal
        # first (observed 2026-09-28). Back out to the section list and re-enter
        # so 2FA runs before any password form.
        if ("password_and_security" in (p.url or "")
                and "two_factor" not in (p.url or "")):
            self.log('[2fa] On a password sub-page — returning to the section list '
                     'so 2FA opens FIRST (not the password modal)…')
            try:
                self._ac_leave_subpage(p)
            except Exception:
                pass
            p.wait_for_timeout(1500)
            p = self._ig_tab()

        # Right after a password change the app often drops us on the AC HOME
        # (the "Meta Account" overview). _ac_section can return there without
        # having entered the section, and the 2FA entry loop then finds no
        # "Two-factor authentication" row and stalls. Walk home ->
        # "Login and security" explicitly and wait for the sub-list.
        if ("password_and_security" not in (p.url or "")
                and "login_and_security" not in (p.url or "")
                and "two_factor" not in (p.url or "")):
            self.log('[2fa] On Accounts Center home — entering "Login and security"…')
            for _ in range(3):
                if self._try_click(p, "Login and security", timeout=4000):
                    break
                p.wait_for_timeout(400)
            for _ in range(12):
                p.wait_for_timeout(250)
                if ("login_and_security" in (p.url or "")
                        or p.get_by_text("Two-factor authentication", exact=False).count() > 0
                        or p.get_by_text("Password and security", exact=False).count() > 0):
                    break

        # Bounce recovery (observed live): the section nav can land on the
        # profile /name/ page instead of password_and_security. One Back +
        # one section re-entry recovers; hammering the same route escalates
        # bot scoring, so exactly one retry.
        if "/name/" in (p.url or "") and "password_and_security" not in (p.url or ""):
            self.log('[🔄] 2FA section bounced to /name/ — backing out and re-entering once…')
            try:
                for b_sel in ('[aria-label="Back"]', 'button:has(svg[aria-label="Back"])', 'button[aria-label="Back"]'):
                    b_el = p.locator(b_sel).first
                    if b_el.count() > 0 and b_el.is_visible():
                        self._tap_or_click(p, b_el)
                        p.wait_for_timeout(2500)
                        break
                self._ac_section("/password_and_security/", "Password and security")
                p = self._ig_tab()
            except IGDeadEnd:
                raise
            except Exception as exc:
                self.log(f'[⚠️] 2FA bounce recovery note: {exc}')
                p = self._ig_tab()
            if "/name/" in (p.url or "") and "password_and_security" not in (p.url or ""):
                self.log(f'[⚠️] 2FA setup halted: section bounce persisted (url={p.url})')
                return None

        # If on Accounts Center home, navigate into Password and security. Already on a
        # Login-and-security page counts as in: one section entry, not a second click.
        if ("password_and_security" not in (p.url or "")
                and "login_and_security" not in (p.url or "")):
            self.log(f'[2fa] On AC root ({p.url[:60]}); clicking Password and security…')
            for sec_sel in (
                'a[href*="password_and_security"]',
                'a:has-text("Password and security")',
                'a:has-text("Login and security")',
                '[role="button"]:has-text("Password and security")',
                '[role="button"]:has-text("Login and security")',
                '[role="link"]:has-text("Password and security")',
                '[role="link"]:has-text("Login and security")',
            ):
                try:
                    el = p.locator(sec_sel).first
                    if el.count() > 0 and el.is_visible():
                        self._tap_or_click(p, el)
                        p.wait_for_timeout(3000)
                        break
                except Exception:
                    pass

        if "login_activity" in (p.url or ""):
            self.log('[2fa] On login_activity instead of password_and_security; tapping Back…')
            for b_sel in ('svg[aria-label="Back"]', '[aria-label="Back"]', 'button:has(svg[aria-label="Back"])', 'button[aria-label="Back"]'):
                try:
                    b_el = p.locator(b_sel).first
                    if b_el.count() > 0 and b_el.is_visible():
                        self._tap_or_click(p, b_el)
                        p.wait_for_timeout(2500)
                        break
                except Exception:
                    pass

        for _entry in range(3):
            clicked_2fa = (
                self._try_click(p, "Two-factor authentication", timeout=4000)
                or self._try_click(p, "Two-factor authentication", role="link", timeout=3000)
            )
            if not clicked_2fa:
                for sel_2fa in (
                    'a[href*="two_factor"]',
                    'a:has-text("Two-factor authentication")',
                    'div[role="button"]:has-text("Two-factor authentication")',
                    'div[role="link"]:has-text("Two-factor authentication")',
                    'button:has-text("Two-factor authentication")',
                    '[aria-label*="Two-factor authentication" i]',
                ):
                    try:
                        el = p.locator(sel_2fa).first
                        if el.count() > 0 and el.is_visible():
                            self._tap_or_click(p, el)
                            clicked_2fa = True
                            break
                    except Exception:
                        pass
            # VERIFY the tap navigated (the Login-and-security list absorbs
            # taps without navigating when still hydrating).
            reached = False
            for _ in range(12):
                p.wait_for_timeout(500)
                try:
                    if "two_factor" in (p.url or ""):
                        reached = True
                        break
                except Exception:
                    pass
            if reached:
                break
            self.log(f'[2fa] entry tap {_entry + 1}/3 stayed on list — re-locating…')
            try:
                self._dismiss_ig_sheets(p)
            except Exception:
                pass

        if not reached:
            self.log(f'[⚠️] 2FA entry not found (url={p.url}) | {self._page_tail(p)}')
            return None
        p.wait_for_timeout(1200)
        if self._is_ig_dead_end_chooser(p):
            raise IGDeadEnd("IG saved-account chooser detected during 2FA entry (session dropped) — aborting immediately")
        self._ac_recover_transient(p)
        self.log(f'[2fa] entry open (url={(p.url or "")[:90]}) | {self._page_tail(p, 160)}')

        # Chooser can appear IMMEDIATELY after the 2FA entry ("across apps,
        # devices…") hiding Get started behind it — pick the Instagram row now.
        try:
            self._ac_choose_account(p, prefer_instagram=True)
            p.wait_for_timeout(2000)
        except Exception:
            pass

        # Intro screen if present ("Set up extra protection" / "Get started").
        # CAUTION: the post-password upsell shares the same heading but has
        # ONLY an X (no "Get started") — close that one, never "start" it.
        try:
            self._dismiss_extra_protection_upsell(p)
        except Exception:
            pass
        if self._try_click(p, "Get started", timeout=3000):
            self.log('[ac] Clicked "Get started" on 2FA intro.')
            # 2FA setup triggers the SAME "Two Step Verification / Check your
            # email — Enter the code we sent to …" re-auth as a password change
            # (verified live via MCP 2026-09-20: Get started → Check your email).
            # Poll for the challenge OR the method list before acting, then the
            # `_ac_reauth` loop below solves the emailed code via
            # `_ac_solve_email_challenge` (8-digit "Authenticate your profile").
            for _ in range(12):
                p.wait_for_timeout(400)
                try:
                    low = (p.inner_text("body") or "").lower()
                except Exception:
                    low = ""
                if ("check your email" in low or "enter the code we sent" in low
                        or "two step verification" in low
                        or self._visible(p, "radio", "Authentication app") is not None):
                    break

        # A profile chooser can reappear AFTER the intro — but only act when the
        # 2FA UI is NOT already visible. (Removed the duplicate unconditional
        # chooser here and two duplicate `_ac_recover_transient` calls: the page
        # was already recovered above, and the first chooser ran at the top.)
        try:
            if (self._visible(p, "button", "Get started") is None
                    and self._visible(p, "radio", "Authentication app") is None):
                self._ac_choose_account(p)
        except Exception:
            pass
        p.wait_for_timeout(600)
        # Only re-auth while a challenge is actually showing — the old loop slept
        # 4x2.5s (~10s) regardless, which is why the click felt "late".
        for _ in range(2):
            if not self._ac_reauth(p):
                break
            p.wait_for_timeout(900)

        # "Authentication app" radio / tile (intro screen first: "Get started")
        if not (self._try_click(p, "Authentication app", role="radio", timeout=3000) or self._try_click(p, "Authentication app", timeout=3000)):
            self._try_click(p, "Get started", timeout=3000)
            p.wait_for_timeout(1200)
            if not self._try_click(p, "Authentication app", role="radio", timeout=3000):
                self._try_click(p, "Authentication app", timeout=3000)
        self._try_click(p, "Continue", timeout=8000)

        secret = None
        for _scrape in range(12):
            p = self._ig_tab()
            # Bounce-out recovery (observed live 2026-09-19): the scrape loop
            # can land back on password_and_security/ (section reload / reauth
            # navigation). Scraping that DOM for 12 rounds always yields "key
            # not found" — re-enter two_factor instead of scraping dead DOM.
            if "two_factor" not in (p.url or ""):
                self.log(f'[🔄] 2FA bounced out ({(p.url or "")[:80]}) — re-entering two_factor…')
                try:
                    self._ac_section("/password_and_security/", "Password and security")
                    p = self._ig_tab()
                except IGDeadEnd:
                    raise
                except Exception:
                    p = self._ig_tab()
                re_reached = False
                for _re in range(2):
                    if self._try_click(p, "Two-factor authentication", timeout=4000):
                        pass
                    for _ in range(5):
                        p.wait_for_timeout(2000)
                        try:
                            if "two_factor" in (p.url or ""):
                                re_reached = True
                                break
                        except Exception:
                            pass
                    if re_reached:
                        break
                if not re_reached:
                    p.wait_for_timeout(2500)
                    continue
                try:
                    self._ac_choose_account(p, prefer_instagram=True)
                except Exception:
                    pass
                if self._try_click(p, "Get started", timeout=3000):
                    p.wait_for_timeout(2500)
                if self._try_click(p, "Authentication app", role="radio", timeout=3000) or self._try_click(p, "Authentication app", timeout=3000):
                    self._try_click(p, "Continue", timeout=4000)
                    p.wait_for_timeout(2500)
                continue
            self._ac_recover_transient(p)
            self._ac_reauth(p)              # handle "For your security…" or "Check your email"
            p.wait_for_timeout(900)
            secret = self.ig_scrape_2fa_key(p)
            if secret:
                break
            # Every 4th miss the page is showing stale content (e.g. password-
            # form residue after a change) — reload the section once instead
            # of scraping the same dead DOM for the whole budget.
            if _scrape in (3, 7) and "two_factor" in (p.url or ""):
                self.log('[🔄] 2FA content stale — reloading section…')
                try:
                    p.reload(wait_until="domcontentloaded", timeout=30000)
                    p.wait_for_timeout(4000)
                except Exception:
                    pass
            # If a section reload dropped us back on the 2FA INTRO (has "Get
            # started", no method radio), re-enter it — otherwise the loop
            # scrapes the intro DOM until the budget dies ("key not found").
            if self._try_click(p, "Get started", timeout=2000):
                self.log('[ac] Re-entered 2FA intro after reload.')
                p.wait_for_timeout(2500)
            # If still on or returned to "Authentication app" radio after reauth:
            if self._try_click(p, "Authentication app", role="radio", timeout=2000) or self._try_click(p, "Authentication app", timeout=2000):
                self._try_click(p, "Continue", timeout=4000)
            else:
                self._try_click(p, "Continue", timeout=3000)

        if not secret:
            self.log(f'[⚠️] 2FA key not found (url={p.url}) | {self._page_tail(p)}')
            return None

        self.insta_secret = secret
        self.log('<font color="#00FF00"><b>[🔑] 2FA key captured.</b></font>')
        # Do NOT open the "Enter code" screen here: the caller must first submit
        # the key to the Telegram bot and receive the 6-digit code. Opening it now
        # left the screen sitting with Next disabled while the bot round-trip ran
        # (observed: "went to the 2FA submit screen without a code").
        return secret

    def ig_2fa_confirm(self, code: Any) -> bool:
        """Enter the 6-digit code (from Telegram bot or pyotp) and confirm."""
        p = self._ig_tab()
        # Never open/fill the submit screen with no code (that is exactly the
        # "went to the 2FA submit screen without a code" stall).
        if not code:
            self.log('[⚠️] 2FA confirm called with no code — not opening the submit screen.')
            return False
        # The key/QR screen stays open until now — open the "Enter code" step ONLY
        # once we actually hold a code, so Next is never left disabled.
        try:
            _code_sel = ('input[placeholder*="code" i], input[aria-label*="code" i], '
                         'input[name="verificationCode"], input[type="text"]')
            if not p.locator(_code_sel).first.is_visible():
                if self._try_click(p, "Enter code", timeout=8000):
                    for _ in range(12):
                        p.wait_for_timeout(250)
                        if p.locator(_code_sel).first.is_visible():
                            break
        except Exception:
            pass
        filled = False
        for sel in (
            'input[placeholder*="code" i]',
            'input[aria-label*="code" i]',
            'input[name="verificationCode"]',
            'input[type="text"]',
        ):
            try:
                inp = p.locator(sel).first
                if inp.count() and inp.is_visible():
                    # PayGo verifies ~30 s after it sends the code, so every second counts here:
                    # one plain fill (what worked by hand), slow typing only as a fallback.
                    try:
                        inp.fill(str(code), timeout=3000)
                    except Exception:
                        self._tap_or_click(p, inp, timeout=2000)
                        inp.press_sequentially(str(code), delay=random.randint(40, 80))
                    # Verify the value actually landed (React controlled inputs
                    # sometimes swallow fill) — the #1 cause of "code didn't submit".
                    try:
                        if inp.input_value() != str(code):
                            inp.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", str(code))
                    except Exception:
                        pass
                    filled = True
                    try:
                        inp.press("Enter")
                    except Exception:
                        pass
                    break
            except Exception:
                pass
        if not filled:
            filled = self._try_fill(p, "Enter code", code, timeout=8000)

        if filled:
            self._try_click(p, "Next", timeout=8000) or self._try_click(p, "Continue", timeout=8000)
        on = False
        # Poll fast instead of a blind 6s sleep + 5x1.5s (~14s). The "2FA is on"
        # panel usually appears within ~1s of a successful submit.
        for _ in range(16):
            p.wait_for_timeout(500)
            try:
                body_txt = (p.inner_text("body") or "").lower()
                # Fast rejection detection (APK parity: eo.java:262)
                if any(err in body_txt for err in (
                    "code is incorrect", "incorrect code", "wrong code",
                    "isn't right", "isn't correct", "couldn't verify",
                    "could not verify", "does not match", "doesn't match",
                    "please check the code", "try again"
                )):
                    self.log(f'[⚠️] 2FA code rejected by Instagram ("{code}") — fast fail for retry.')
                    return False

                if ("two-factor authentication is on" in body_txt or "authentication is on" in body_txt
                        or "authentication is set up" in body_txt or "two-factor authentication is set up" in body_txt
                        or "backup codes" in body_txt):
                    on = True
                    break
                if p.get_by_text("Two-factor authentication is on", exact=False).first.is_visible():
                    on = True
                    break
            except Exception:
                pass

        if on:
            for b_sel in ('button:has-text("Done")', 'div[role="button"]:has-text("Done")', 'button:has-text("Close")', '[aria-label="Close"]', 'button:has-text("backup codes")'):
                try:
                    b = p.locator(b_sel).first
                    if b.count() > 0 and b.is_visible():
                        self._tap_or_click(p, b)
                        p.wait_for_timeout(2000)
                        break
                except Exception:
                    pass
        self.log('<font color="#00FF00"><b>[✔] 2FA enabled.</b></font>' if on else '[⚠️] 2FA confirmation not detected.')
        return on

    def ig_enable_2fa(self) -> Optional[str]:
        """In IG creator, just scrape/copy the 2FA secret key from Accounts Center and return it."""
        secret = self.ig_2fa_begin()
        if not secret:
            return None
        self.log('<font color="#00FF00"><b>[🔑] 2FA key copied (confirmation skipped).</b></font>')
        return secret
