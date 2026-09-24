"""Instagram authentication & direct login. Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides run._MetaInstagramRunner helpers."""
from __future__ import annotations

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_config import Urls  # noqa: E402
try:
    from .helpers import IGDeadEnd
except ImportError:  # pragma: no cover - top-level import path
    from instagram.helpers import IGDeadEnd  # type: ignore


class IgLoginMixin:
    """Instagram authentication & direct login."""

    def ig_login(self):
        """Open Instagram and log in with the Meta email/password."""
        p = self._ig_tab()
        self.log('[🌐] Instagram: opening login…')
        p.goto(Urls.IG_LOGIN, wait_until="domcontentloaded", timeout=60000)
        # Poll for the login form instead of a blind 3.5s sleep (faster when the
        # form is already rendered; still bounded to the same ~3.2s max).
        for _ in range(8):
            try:
                if p.locator('input[name="username"], input[autocomplete="username"], input[type="text"]').first.is_visible():
                    break
            except Exception:
                pass
            p.wait_for_timeout(400)
        self._require_ig_rendered(p, "Instagram login")

        # 1. Cookie banners & sheets
        for bt in ("Allow all cookies", "Only allow essential cookies", "Decline optional cookies", "Allow"):
            if self._try_click(p, bt, timeout=3000):
                p.wait_for_timeout(1000)
                break
        self._dismiss_ig_sheets(p)

        # 1b. Check if Instagram immediately prompts with active Meta session (Continue as [Name])
        for sel in (
            'button:has-text("Continue as")',
            'div[role="button"]:has-text("Continue as")',
            '[aria-label*="Continue as" i]',
        ):
            try:
                cont_btn = p.locator(sel).first
                if cont_btn.count() > 0 and cont_btn.is_visible():
                    txt = (cont_btn.inner_text() or "").strip()
                    if "facebook" not in txt.lower():
                        self.log(f'[➡️] Found active Meta session prompt: "{txt}". Tapping…')
                        try:
                            cont_btn.tap(timeout=3000)
                        except Exception:
                            cont_btn.click(force=True, timeout=3000)
                        p.wait_for_timeout(4000)
                        return
            except Exception:
                pass

        # 2. Fill Email / Username
        filled_email = False
        for nm in (
            "Username, email or mobile number",
            "Mobile number, username or email",
            "Phone number, username, or email",
            "username",
            "email",
        ):
            if self._try_fill(p, nm, self.email, timeout=6000):
                filled_email = True
                break
        if not filled_email:
            for sel in ('input[name="username"]', 'input[type="text"]', 'input[autocomplete="username"]', 'input[aria-label*="email" i]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        self._clean_fill(p, el, self.email, timeout=6000)
                        filled_email = True
                        break
                except Exception:
                    pass
        self.log(f'[✉️] IG login email filled: {self.email}')

        # 3. Fill Password
        filled_pwd = False
        for nm in ("Password", "password"):
            if self._try_fill(p, nm, self.password, timeout=6000):
                filled_pwd = True
                break
        if not filled_pwd:
            for sel in ('input[name="password"]', 'input[type="password"]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        self._clean_fill(p, el, self.password, timeout=6000)
                        filled_pwd = True
                        break
                except Exception:
                    pass

        # 3b. Force-enable the Log in button: without synced React state it
        # stays dimmed and the tap lands on a disabled button (the stall).
        try:
            p.evaluate("""() => {
              document.querySelectorAll('input').forEach(el => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
              });
            }""")
        except Exception:
            pass

        # 4. Blur input and trigger submit on Log in button
        try:
            p.evaluate("document.activeElement && document.activeElement.blur()")
        except Exception:
            pass

        # 5. Tap submit / Log in button
        if not self._click_ig_login_btn(p):
            try:
                p.keyboard.press("Enter")
            except Exception:
                pass

        # 6. Verify submission & handle stuck login
        for attempt in range(10):
            p.wait_for_timeout(2500)

            # Fast fail checks: account rejected or phone wall -> quit immediately
            _tail = self._page_tail(p, 400).lower()
            if "can't find account" in _tail or p.get_by_text("Can't find account", exact=False).count() > 0:
                # Dynamic route (fresh Meta, no IG profile yet): the dialog
                # offers Sign up — that IS the onboarding entry. Click through
                # and return "needs_join" so the caller proceeds to the Meta
                # link card + join wizard instead of killing the whole run.
                # Returns None (old behavior: raise) only when no signup path.
                joined = False
                for sel in (
                    'button:has-text("Sign up")',
                    'div[role="button"]:has-text("Sign up")',
                    'button:has-text("Create new account")',
                    'div[role="button"]:has-text("Create new account")',
                ):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            self._tap_or_click(p, el) if hasattr(self, "_tap_or_click") else el.click(force=True, timeout=4000)
                            joined = True
                            break
                    except Exception:
                        continue
                if joined:
                    self.log('[➡️] Instagram: fresh Meta (no IG profile) — routed to Sign up / join wizard.')
                    p.wait_for_timeout(4000)
                    return "needs_join"
                self.log('[❌] Instagram: "Can\'t find account" detected — Meta account not recognized. Quitting immediately.')
                raise RuntimeError("Instagram: Can't find account (Meta credentials invalid or rejected)")

            if "what's your mobile number" in _tail or p.get_by_text("What's your mobile number", exact=False).count() > 0:
                self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting immediately.')
                raise RuntimeError("Instagram: Phone number verification required (What's your mobile number)")

            # Wrong password -> fail fast with a clear error (no blind rounds).
            if "password was incorrect" in _tail or "incorrect password" in _tail:
                self.log('[❌] Instagram: wrong password rejected. Quitting immediately.')
                raise RuntimeError("Instagram: incorrect password (login rejected)")

            if (
                p.get_by_text("No Instagram account found", exact=False).count() > 0
                or p.get_by_text("No Instagram profile found", exact=False).count() > 0
                or "no instagram profile found" in _tail
                or p.get_by_text("Meta Horizon", exact=False).count() > 0
                or "sessionid" in self._ig_cookie_names()
                or "/accounts/login" not in p.url
            ):
                break

            # DEAD END: the bare saved-account chooser (profile named after the
            # email local part + "Use another profile"/"Create new account")
            # means the Meta join failed. Abort instead of tapping "Continue"
            # into a session that will never link.
            try:
                if self._is_ig_dead_end_chooser(p):
                    raise IGDeadEnd("IG saved-account chooser with the bare email profile — Meta join failed")
            except IGDeadEnd:
                raise
            except Exception:
                pass

            # One-tap prompt check
            try:
                _tail = self._page_tail(p, 300)
                if ("Continue as" in _tail or ("Continue" in _tail and "Use another profile" in _tail)):
                    for c_sel in (
                        'button:has-text("Continue as")',
                        'div[role="button"]:has-text("Continue as")',
                        'button:has-text("Continue")',
                        'div[role="button"]:has-text("Continue")',
                    ):
                        c_btn = p.locator(c_sel).first
                        if c_btn.count() > 0 and c_btn.is_visible():
                            try:
                                c_btn.tap(timeout=3000)
                            except Exception:
                                c_btn.click(force=True, timeout=3000)
                            self.log('[➡️] Tapped "Continue" (one-tap login).')
                            p.wait_for_timeout(3000)
                            break
                    continue
            except Exception:
                pass

            # Stalled on /accounts/login: swipe down + re-tap Log In (manual recovery parity)
            if attempt in (1, 3, 5, 7):
                self.log('[➡️] Login sheet stalled — swiping down and re-tapping Log In…')
                try:
                    self._swipe_down(p)
                except Exception:
                    pass
                p.wait_for_timeout(800)
                try:
                    p.keyboard.press("Enter")
                except Exception:
                    pass
                self._click_ig_login_btn(p)
                p.wait_for_timeout(2000)

            # If still stuck after several rounds on login screen, refresh page
            if attempt == 7:
                self.log('[⚠️] Log in screen stalled — refreshing to trigger active Meta session…')
                try:
                    p.goto(Urls.IG_LOGIN, wait_until="domcontentloaded", timeout=30000)
                    p.wait_for_timeout(3000)
                    self._dismiss_ig_sheets(p)
                except Exception:
                    pass

        p.wait_for_timeout(2000)
        self.log('[➡️] Instagram credentials submitted.')

    def ig_direct_login(self, username: str, password: str, twofa_secret: Optional[str] = None) -> bool:
        """Log directly into Instagram web without touching Meta.
        Handles: credentials input, 2FA code generation (TOTP via pyotp),
        and dismissing the 'Save your login info?' prompt.
        """
        p = self._ig_tab()
        self.log(f'[🌐] Instagram direct login for user: {username}…')
        p.goto(Urls.IG_LOGIN, wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(3000)
        self._require_ig_rendered(p, "Instagram login")
        self._dismiss_ig_sheets(p)

        # 1. Fill username / email
        filled_user = False
        for sel in ('input[name="username"]', 'input[type="text"]', 'input[autocomplete="username"]', 'input[aria-label*="username" i]'):
            try:
                el = p.locator(sel).first
                if el.count() and el.is_visible():
                    self._clean_fill(p, el, username, timeout=6000)
                    filled_user = True
                    break
            except Exception:
                pass
        if not filled_user:
            self._try_fill(p, "Username", username, timeout=6000)

        # 2. Fill password
        filled_pw = False
        for sel in ('input[name="password"]', 'input[type="password"]'):
            try:
                el = p.locator(sel).first
                if el.count() and el.is_visible():
                    self._clean_fill(p, el, password, timeout=6000)
                    filled_pw = True
                    break
            except Exception:
                pass
        if not filled_pw:
            self._try_fill(p, "Password", password, timeout=6000)

        # 2b. Force-enable the submit control: mobile Bloks renders Log in as
        # div[role="button"] (no <button>), and React state can leave it dimmed.
        try:
            p.evaluate("""() => {
              document.querySelectorAll('input').forEach(el => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
              });
            }""")
        except Exception:
            pass

        # 3. Submit (div[role="button"] FIRST: Bloks mobile has no <button>)
        try:
            p.keyboard.press("Enter")
        except Exception:
            pass
        for btn_sel in ('div[role="button"]:has-text("Log in")', 'div[role="button"]:has-text("Log In")',
                        'button[type="submit"]', 'button:has-text("Log in")', 'button:has-text("Log In")'):
            try:
                btn = p.locator(btn_sel).first
                if btn.count() and btn.is_visible():
                    btn.click(force=True, timeout=3000)
                    break
            except Exception:
                pass

        # 3b. Stuck-sheet + Meta-link dialog recovery (same as ig_login):
        # the login POST may hang on spinner, land on the
        # "No Instagram account found" sheet, render a one-tap
        # "Continue as <user>" screen (restored session recognized!), or drop
        # into an unfinished join wizard — handle all three inline.
        for attempt in range(8):
            p.wait_for_timeout(2500)
            if "sessionid" in self._ig_cookie_names() or "/accounts/login" not in p.url:
                break
            try:
                _tail = self._page_tail(p, 300)
                # (i) One-tap "Continue as <user>" — session IS valid, just tap it.
                if ("Continue as" in _tail or ("Continue" in _tail and "Use another profile" in _tail)):
                    if self._try_click(p, f"Continue as {username}", timeout=4000):
                        self.log(f'[➡️] Tapped "Continue as {username}".')
                    elif self._try_click(p, "Continue", timeout=4000):
                        self.log('[➡️] Tapped "Continue" (one-tap login).')
                    p.wait_for_timeout(3000)
                    continue
                # (ii) Unfinished join wizard (fresh account) — complete it here.
                if "What's your name?" in _tail or "Create a username" in _tail:
                    self.log('[➡️] Landed in join wizard; completing it inline.')
                    try:
                        self.ig_complete_join()
                    except Exception:
                        pass
                    continue
            except Exception:
                pass
            # Fast fail check: account rejected, wrong password, or phone wall
            if "can't find account" in _tail or p.get_by_text("Can't find account", exact=False).count() > 0:
                self.log('[❌] Instagram: "Can\'t find account" detected — quitting direct login.')
                return False
            if "password was incorrect" in _tail or "incorrect password" in _tail:
                self.log('[❌] Instagram: wrong password rejected — quitting direct login.')
                return False
            if "what's your mobile number" in _tail or p.get_by_text("What's your mobile number", exact=False).count() > 0:
                self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected — quitting direct login.')
                return False

            if (
                p.get_by_text("No Instagram account found", exact=False).count() > 0
                or p.get_by_text("No Instagram profile found", exact=False).count() > 0
                or "no instagram profile found" in _tail
                or p.get_by_text("Meta Horizon", exact=False).count() > 0
                or p.locator('div[role="dialog"]').count() > 0
            ):
                try:
                    self.ig_click_meta_card()
                except Exception:
                    pass
                break
            if attempt > 0:
                try:
                    self._swipe_down(p)
                except Exception:
                    pass
                p.wait_for_timeout(1000)
            try:
                p.keyboard.press("Enter")
                self._click_ig_login_btn(p)
            except Exception:
                pass
        p.wait_for_timeout(3000)

        # 4. Handle 2FA prompt if present
        tail = self._page_tail(p, 400).lower()
        if (
            any(w in tail for w in ("two-factor", "security code", "enter the 6-digit code", "login code", "verification code"))
            or p.locator('input[name="verificationCode"], input[placeholder*="Security Code" i]').count() > 0
        ):
            self.log('[🔐] Instagram 2FA checkpoint detected.')
            secret = twofa_secret or getattr(self, "insta_secret", None)
            if not secret:
                self.log('[⚠️] No 2FA secret available for direct login!')
                return False
            import pyotp
            totp_code = pyotp.TOTP(secret).now()
            self.log(f'[🔑] Submitting TOTP code: {totp_code}')
            code_filled = False
            for sel in (
                'input[name="verificationCode"]',
                'input[placeholder*="Security Code" i]',
                'input[aria-label*="Security Code" i]',
                'input[type="tel"]',
                'input[type="text"]',
            ):
                try:
                    inp = p.locator(sel).first
                    if inp.count() and inp.is_visible():
                        inp.fill(totp_code)
                        code_filled = True
                        break
                except Exception:
                    pass
            if code_filled:
                for btn_sel in ('button[type="submit"]', 'button:has-text("Confirm")', 'button:has-text("Next")', 'button:has-text("Continue")'):
                    try:
                        b = p.locator(btn_sel).first
                        if b.count() and b.is_visible():
                            b.click(force=True, timeout=4000)
                            break
                    except Exception:
                        pass
                p.wait_for_timeout(4000)

        # 5. Dismiss "Save your login info?"
        self._try_click(p, "Save info", role="button", timeout=3000) or self._try_click(p, "Not now", role="button", timeout=3000)
        self.ig_dismiss_onboarding()

        logged_in = "sessionid" in self._ig_cookie_names()
        if not logged_in:
            # Name the blocker so failures are diagnosable, not opaque.
            try:
                tail = self._page_tail(p, 300).lower()
                self.log(f'[⚠️] Direct login stuck at url={p.url} | tail={self._page_tail(p, 160)}')
                if "codeentry" in (p.url or "") or "enter the code we sent" in tail or "check your email" in tail:
                    self.log('[⚠️] Direct login hit an EMAIL-code checkpoint (temp inbox gone — unrecoverable downstream).')
                elif any(w in tail for w in ("sorry, your password was incorrect", "password was incorrect")):
                    self.log('[⚠️] Direct login rejected: incorrect password.')
            except Exception:
                pass
        self.log(f'[🌐] Direct login result: logged_in={logged_in}')
        return logged_in
