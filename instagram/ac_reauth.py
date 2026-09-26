"""Accounts Center email challenges + re-authentication.

Split out of the former 2082-line ``instagram/password.py`` (2026-09-25) so the
AC **re-auth** rules live apart from navigation and from the password form. The
problem that motivated the split: ``_ac_reauth`` used to fill the *form's*
Current-password field and press Enter when it met the 2-3 input Change-password
form, so callers re-ran it 5x (~13s dead) — a guard bug that is invisible when
2000 lines share one file.

Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides the
run._MetaInstagramRunner helpers (and the navigation mixin it calls).
"""
from __future__ import annotations

import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_config import Urls  # noqa: E402
try:
    from .helpers import IGDeadEnd
except ImportError:  # pragma: no cover - top-level import path
    from instagram.helpers import IGDeadEnd  # type: ignore


class IgAcReauthMixin:
    """Email-challenge solving, form-vs-prompt detection, and AC re-auth."""

    def _ac_solve_email_challenge(self, p, timeout: int = 60) -> bool:
        """Handle Accounts Center email security challenge ('Check your email - Enter the code we sent to...')."""
        targets = [p] + list(getattr(p, "frames", []))
        body_low = ""
        for tgt in targets:
            try:
                body_low += " " + (tgt.evaluate("() => document.body.innerText || ''") or "").lower()
            except Exception:
                pass

        # Check if choice method screen is showing ("Choose a way to confirm" / "Confirm it's you")
        if any(k in body_low for k in ("choose a way to confirm", "how do you want to confirm", "confirm it's you", "confirm that it's you")):
            for sel in (
                'div[role="radio"]:has-text("Email")',
                'button:has-text("Email")',
                'div[role="button"]:has-text("Email")',
                'div:has-text("Email")',
            ):
                try:
                    opt = p.locator(sel).first
                    if opt.count() and opt.is_visible():
                        self._tap_or_click(p, opt, timeout=3000)
                        break
                except Exception:
                    pass
            for sel in ('button:has-text("Continue")', '[role="button"]:has-text("Continue")', 'button:has-text("Next")'):
                try:
                    btn = p.locator(sel).first
                    if btn.count() and btn.is_visible():
                        self._tap_or_click(p, btn, timeout=3000)
                        p.wait_for_timeout(1200)
                        break
                except Exception:
                    pass
            body_low = ""
            for tgt in targets:
                try:
                    body_low += " " + (tgt.evaluate("() => document.body.innerText || ''") or "").lower()
                except Exception:
                    pass

        if not any(k in body_low for k in ("check your email", "enter the code we sent", "enter code we sent", "get a new code", "sent a code to", "enter the 6-digit code")):
            return False

        self.log('<font color="#FFA500"><b>[✉️] Accounts Center email security challenge detected ("Check your email").</b></font>')

        fetcher = getattr(self, "fetch_code", None)
        code = None
        if callable(fetcher):
            for attempt in range(3):
                wait_sec = 45 if attempt == 0 else 60
                try:
                    # Guide Scenario 2: the AC challenge is ALWAYS subject
                    # "Authenticate your profile" (noreply@account.meta.com),
                    # newest first, 8-digit — never a stale/foreign code.
                    try:
                        code = fetcher("instagram", timeout=wait_sec,
                                       subject_hint="authenticate your profile",
                                       prefer_len=8)
                    except TypeError:
                        code = fetcher("instagram", timeout=wait_sec)
                except TypeError:
                    code = fetcher("instagram")
                except Exception as exc:
                    self.log(f'[ac] fetch_code error: {exc}')
                if code:
                    break
                # "Get a new code" is gated per CHALLENGE LIFETIME (instance
                # timestamp, not per solver call): _ac_reauth re-invokes this
                # solver every round, and a per-call "once" still regenerates
                # codes faster than delivery (observed 2026-09-19: 4 sends in
                # ~4 min, each invalidating the last — death spiral). At most
                # one resend per 5 minutes, and only when no Authenticate
                # mail exists yet.
                import time as _time
                if _time.time() - getattr(self, "_ac_new_code_at", 0) < 300:
                    continue
                try:
                    inbox = getattr(self, "mail", None)
                    has_auth = False
                    if inbox is not None and not inbox.is_closed():
                        has_auth = "authenticate your profile" in (
                            inbox.evaluate("() => document.body.innerText || ''") or "").lower()
                    else:
                        has_auth = True  # unknown — don't regenerate blindly
                except Exception:
                    has_auth = True
                if has_auth:
                    continue
                try:
                    for sel in (
                        'button:has-text("Get a new code")',
                        '[role="button"]:has-text("Get a new code")',
                        'a:has-text("Get a new code")',
                        'div:has-text("Get a new code")',
                    ):
                        gnc = p.locator(sel).first
                        if gnc.count() and gnc.is_visible():
                            self._tap_or_click(p, gnc, timeout=3000)
                            self._ac_new_code_at = _time.time()
                            p.wait_for_timeout(1200)
                            # Verify the tap actually FIRED a send (resend
                            # timer / "sent" notice) — a no-op tap must not
                            # start a blind fetch-wait.
                            try:
                                dlg = (p.inner_text("body") or "").lower()
                                sent = ("we sent" in dlg or "sent a new code" in dlg
                                        or "resend" in dlg or "new code" in dlg)
                            except Exception:
                                sent = False
                            self.log('[🔁] No Authenticate mail yet — clicked "Get a new code" '
                                     f'(send confirmed: {sent})…')
                            break
                except Exception:
                    pass

        if not code:
            self.log('[⚠️] Failed to fetch Accounts Center email security code.')
            return False

        self.log(f'<font color="#00FF00"><b>[✉️] Entering Accounts Center security code: {code}</b></font>')
        # NOTE: no bring_to_front() here — in headed mode raising the window
        # steals the user's OS focus on every challenge. Re-enable explicitly
        # with INSTA_ALLOW_FOCUS=1 if a flow ever needs it.
        if os.environ.get("INSTA_ALLOW_FOCUS", "") == "1":
            try:
                p.bring_to_front()
                p.wait_for_timeout(500)
            except Exception:
                pass

        filled = False
        for tgt in targets:
            for sel in (
                'input[placeholder*="Code" i]',
                'input[name="code"]',
                'input[name="verificationCode"]',
                'input[name="confirmationCode"]',
                'input[name="security_code"]',
                'input[inputmode="numeric"]',
                'input[type="text"]',
                'input[type="tel"]',
                'input',
            ):
                try:
                    inp = tgt.locator(sel).first
                    if inp.count() and inp.is_visible():
                        inp.click(force=True, timeout=3000)
                        inp.fill(str(code))
                        p.wait_for_timeout(200)
                        if inp.input_value() == str(code):
                            filled = True
                            self.log(f'[ac] filled security code into {sel}')
                            break
                        # Retry with evaluate
                        tgt.evaluate("""({sel, val}) => {
                            const el = document.querySelector(sel);
                            if (el) {
                                el.value = val;
                                el.dispatchEvent(new Event('input', {bubbles: true}));
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                            }
                        }""", {"sel": sel, "val": str(code)})
                        p.wait_for_timeout(200)
                        filled = True
                        break
                except Exception:
                    continue
            if filled:
                break

        if not filled:
            self.log('[⚠️] Could not find code input on "Check your email" dialog.')
            return False

        if filled:
            try:
                p.keyboard.press("Enter")
                p.wait_for_timeout(1000)
            except Exception:
                pass

        p.wait_for_timeout(500)

        clicked = False
        for tgt in targets:
            for sel in (
                'button:has-text("Continue")',
                '[role="button"]:has-text("Continue")',
                'div[role="button"]:has-text("Continue")',
                'button:has-text("Confirm")',
                '[role="button"]:has-text("Confirm")',
                'div[role="button"]:has-text("Confirm")',
                'button:has-text("Next")',
                '[role="button"]:has-text("Next")',
                'div[role="button"]:has-text("Next")',
                'button[type="submit"]',
                'input[type="submit"]',
            ):
                try:
                    btn = tgt.locator(sel).first
                    if btn.count() and btn.is_visible():
                        if not self._tap_or_click(p, btn, timeout=4000):
                            btn.click(force=True, timeout=4000)
                        clicked = True
                        self.log(f'[ac] clicked "{sel}" on email security dialog')
                        break
                except Exception:
                    continue
            if clicked:
                break

        for _ in range(16):
            p.wait_for_timeout(500)
            try:
                cur = (p.inner_text("body") or "").lower()
            except Exception:
                cur = ""
            if not any(k in cur for k in ("check your email", "enter the code we sent", "enter code we sent")):
                clicked = True
                break

        self.log(f'[ac] email security challenge result: filled={filled}, clicked={clicked}')
        return filled and clicked

    def _dismiss_extra_protection_upsell(self, p) -> bool:
        """Close the post-password "Set up extra protection for your Meta
        Account" upsell modal.

        This modal has ONLY an X (no "Get started") — it must be dismissed,
        never "started". Returns True when such a modal was found+closed.
        """
        try:
            body = (p.inner_text("body") or "")
        except Exception:
            return False
        if "Set up extra protection for your Meta Account" not in body:
            return False
        # NEVER close the 2FA section itself: on the two_factor page the X is
        # the page close button, not an upsell dismiss. Closing it bounced the
        # flow out to /password_and_security/ and forced a full 2FA re-entry
        # (observed run #4: 14:12:18 dismiss -> 14:12:22 "2FA bounced out").
        if "two_factor" in (p.url or ""):
            return False
        # Real 2FA intro carries a "Get started" control — that one is handled
        # by the 2FA flow, not here. IG renders it as div[role=button], so the
        # old `button:has-text(...)` guard missed it and closed the intro.
        try:
            gs = p.get_by_text("Get started", exact=False).first
            if gs.count() and gs.is_visible():
                return False
        except Exception:
            pass
        self.log('[ac] Dismissing "extra protection" upsell (X only)…')
        for sel in ('[aria-label="Close"]', 'button:has-text("Close")',
                    'svg[aria-label="Close"]'):
            try:
                el = p.locator(sel).first
                if el.count() and el.is_visible():
                    el.click(force=True, timeout=2000)
                    p.wait_for_timeout(1500)
                    return True
            except Exception:
                continue
        try:
            p.keyboard.press("Escape")
            p.wait_for_timeout(1000)
        except Exception:
            pass
        return True

    def _ac_pw_form_open(self, p) -> bool:
        """True when the Accounts Center Change-password form is on screen.

        The form has 2-3 password inputs and a "Current password" field; a real
        re-auth prompt has a single password input. Distinguishing them matters:
        `_ac_reauth` used to fill the form's Current-password field and press
        Enter, so the caller's retry loop ran it 5x back-to-back (~13s dead) even
        though the form was already the target (observed 2026-09-19, run #4).
        """
        try:
            if self._visible(p, "textbox", "Current password") is not None:
                return True
        except Exception:
            pass
        try:
            return p.locator('input[type="password"]').count() >= 2
        except Exception:
            return False

    def _ac_security_challenge(self, p, password: Optional[str] = None) -> bool:
        """Unified entry point: handles email security challenge or password re-auth."""
        return self._ac_reauth(p, password=password)

    def _ac_reauth(self, p, password: Optional[str] = None) -> bool:
        """Handle Accounts Center re-authentication dialogs (Email OTP or Password)."""
        solved_any = False
        for _ in range(3):
            # 1. First check and solve email OTP challenge if present
            if self._ac_solve_email_challenge(p):
                solved_any = True
                # Poll for the challenge to clear / the form to appear instead of
                # a blind 3s freeze after typing the OTP.
                for _ in range(12):
                    p.wait_for_timeout(250)
                    try:
                        low = (p.inner_text("body") or "").lower()
                    except Exception:
                        low = ""
                    if not any(k in low for k in ("check your email", "enter the code we sent",
                                                  "enter code we sent", "get a new code",
                                                  "sent a code to", "enter the 6-digit code")):
                        break
                    if (p.locator('input[type="password"]').count() >= 2
                            or p.get_by_text("Current password", exact=False).count() > 0):
                        break
                continue

            # 2. Check for password re-auth prompt
            targets = [p] + list(getattr(p, "frames", []))
            body_low = ""
            for tgt in targets:
                try:
                    body_low += " " + (tgt.evaluate("() => document.body.innerText || ''") or "").lower()
                except Exception:
                    pass

            has_pwd_prompt = any(k in body_low for k in ("please enter your password", "let us know it's you", "enter your password", "fxreauth", "reauth"))

            pwd_input = None
            for tgt in targets:
                for sel in (
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[autocomplete="current-password"]',
                ):
                    try:
                        el = tgt.locator(sel).first
                        if el.count() and el.is_visible():
                            pwd_input = el
                            break
                    except Exception:
                        pass
                if pwd_input:
                    break

            if not has_pwd_prompt and not pwd_input:
                break
            # The Change-password form is the TARGET, not a challenge. Filling
            # its Current-password field and pressing Enter does nothing but
            # make the caller retry ~5x (run #4: ~13s of dead loops).
            if self._ac_pw_form_open(p):
                break

            pwd = password or self.password
            filled = False
            active_input = None
            if pwd_input:
                try:
                    if os.environ.get("INSTA_ALLOW_FOCUS", "") == "1":
                        try:
                            p.bring_to_front()
                        except Exception:
                            pass
                    pwd_input.click(force=True, timeout=3000)
                    pwd_input.fill(pwd)
                    filled = True
                    active_input = pwd_input
                except Exception as exc:
                    self.log(f'[ac] password fill error: {exc}')
            elif has_pwd_prompt:
                for tgt in targets:
                    for sel in ('input[type="password"]', 'input[type="text"]', 'input'):
                        try:
                            el = tgt.locator(sel).first
                            if el.count() and el.is_visible():
                                el.click(force=True, timeout=3000)
                                el.fill(pwd)
                                filled = True
                                active_input = el
                                break
                        except Exception:
                            continue
                    if filled:
                        break

            if active_input is not None:
                try:
                    active_input.press("Enter")
                    p.wait_for_timeout(1000)
                except Exception:
                    pass

            clicked = False
            for tgt in targets:
                for sel in (
                    'button:has-text("Continue")',
                    '[role="button"]:has-text("Continue")',
                    'div[role="button"]:has-text("Continue")',
                    'button:has-text("Confirm")',
                    '[role="button"]:has-text("Confirm")',
                    'div[role="button"]:has-text("Confirm")',
                    'button:has-text("Next")',
                    '[role="button"]:has-text("Next")',
                    'div[role="button"]:has-text("Next")',
                    'button:has-text("Log in")',
                    '[role="button"]:has-text("Log in")',
                    'div[role="button"]:has-text("Log in")',
                    'button:has-text("Submit")',
                    '[role="button"]:has-text("Submit")',
                    'button[type="submit"]',
                    'input[type="submit"]',
                ):
                    try:
                        b = tgt.locator(sel).first
                        if b.count() and b.is_visible():
                            if not self._tap_or_click(p, b, timeout=4000):
                                b.click(force=True, timeout=4000)
                            clicked = True
                            break
                    except Exception:
                        continue
                if clicked:
                    break

            for _ in range(16):
                p.wait_for_timeout(500)
                try:
                    cur = (p.inner_text("body") or "").lower()
                except Exception:
                    cur = ""
                if not any(k in cur for k in ("please enter your password", "enter your password", "confirm it's you")):
                    clicked = True
                    break

            self.log(f'[ac] password reauth filled={filled} continue={clicked}')
            if filled:
                solved_any = True
            else:
                break

        return solved_any
