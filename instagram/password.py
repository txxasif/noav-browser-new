"""Password provisioning: change the account password + reset-by-email link.

Split out of the former 2082-line ``instagram/password.py`` (2026-09-25), which
mixed three unrelated concerns. This module now holds ONLY the public password
API (``ig_set_password`` / ``ig_change_password`` / ``ig_reset_password``);
navigation lives in :mod:`instagram.ac_nav` and re-auth in
:mod:`instagram.ac_reauth`.

Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides the
run._MetaInstagramRunner helpers.
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


class IgPasswordMixin:
    """Change/reset the Instagram account password (passwords are a hard gate)."""

    def ig_change_password(self, new_password: str, current_password: Optional[str] = None) -> bool:
        """Legacy alias: delegates to ig_set_password using the Meta profile row."""
        return self.ig_set_password(new_password, current_password=current_password)

    def ig_set_password(self, new_password: str, current_password: Optional[str] = None) -> bool:
        """Change the password on the **Meta** account row in Accounts Center:
        Current ← Meta password (or current_password), New ← new_password.
        This directly updates the login password across both Meta & Instagram without
        needing external email reset links.
        """
        p = self._ig_tab()
        # Diagnostic (2026-09-20): the password stage was the top STRICT stop in
        # a live run, but the caller only saw "failed". Record WHICH path bailed
        # so the dashboard/log can distinguish a flaky AC form (code) from an
        # unsolvable email re-auth or a genuine IG rejection (external).
        self._pw_fail_reason = None
        curr = (current_password or self.password or "").strip()
        new_password = (new_password or "").strip()
        if not new_password:
            self.log('[⚠️] Password change skipped: new password missing.')
            return False
        if new_password == curr:
            self.log('[✓] Target password is already identical to current password — skipping Change Password form.')
            return True
        import time as _time
        _pw_t0 = _time.time()
        self.log('[🔑] Setting password via Accounts Center (Meta profile row)…')
        self._ac_section("/password_and_security/", "Password and security")
        self._try_click(p, "Change password", timeout=8000)

        def _challenge_present() -> bool:
            try:
                low = (p.inner_text("body") or "").lower()
            except Exception:
                return False
            return any(k in low for k in ("check your email", "enter the code we sent",
                                          "enter code we sent", "get a new code",
                                          "sent a code to", "enter the 6-digit code"))

        # Poll (challenge OR password form) instead of a blind 3s sleep —
        # whichever renders first wins.
        for _ in range(14):
            p.wait_for_timeout(250)
            if _challenge_present():
                break
            try:
                if (p.locator('input[type="password"]').count() >= 2
                        or p.get_by_text("Current password", exact=False).count() > 0):
                    break
            except Exception:
                pass

        _unsolved_rounds = 0
        for _ in range(3):
            if not self._ac_reauth(p, password=curr):
                break
            # Delivery either arrives in the first solver pass or never
            # (3/3 delivered in-window, 3/3 suppressed for 15+ min). A second
            # unsolved round means re-running the full 3-minute fetch again
            # for nothing — abort the stage instead of grinding past TTL.
            if _challenge_present():
                _unsolved_rounds += 1
                if _unsolved_rounds >= 2:
                    raise RuntimeError(
                        "Email challenge unsolved after 2 rounds (no Authenticate mail) — aborting password stage")
            else:
                _unsolved_rounds = 0
            p.wait_for_timeout(1200)

        def _form_open() -> bool:
            """Guide rule: password inputs visible ⇒ selection is FINISHED."""
            if self._visible(p, "textbox", "Current password") is not None:
                return True
            try:
                return p.locator('input[type="password"]').count() >= 2
            except Exception:
                return False

        # Guide STRICT PROHIBITION: NEVER click the top profile/account card
        # ("... 2 profiles >") — it navigates away and kills the form. If the
        # inputs are already visible, skip ALL account choosing and fill.
        # Account rows are only touched when the form is NOT open yet (the AC
        # account-chooser variant precedes the form on some layouts).
        has_curr, pw_inputs = False, None
        if _form_open():
            self.log('[🔑] Change-password form already open — bypassing account card…')
            has_curr = self._visible(p, "textbox", "Current password") is not None
            try:
                pw_inputs = p.locator('input[type="password"]')
            except Exception:
                pw_inputs = None
        else:
            # Choose the META account row (sets credentials for the whole identity).
            # AC sometimes bounces back to IG settings/consent — re-enter once.
            for _entry in range(2):
                if _form_open():
                    break
                if not self._ac_choose_account(p, prefer_instagram=False):
                    meta_label = f"{self.name} Meta"
                    for label in (meta_label, self.name, "Meta"):
                        if self._try_click(p, label, timeout=4000):
                            self.log(f'[🔑] chose account: {label}')
                            break
                # The email OTP was usually solved above. Only re-auth when a
                # challenge is ACTUALLY showing, and STOP the instant the
                # password form opens — the old code slept 3s + 3x2.5s (~20s)
                # even when the form was already on screen.
                for _ in range(8):
                    if _form_open():
                        break
                    if _challenge_present():
                        if not self._ac_reauth(p, password=curr):
                            break
                        if _challenge_present():
                            _unsolved_rounds += 1
                            if _unsolved_rounds >= 2:
                                raise RuntimeError(
                                    "Email challenge unsolved after 2 rounds (no Authenticate mail) — aborting password stage")
                        else:
                            _unsolved_rounds = 0
                    p.wait_for_timeout(700)

                has_curr = self._visible(p, "textbox", "Current password") is not None
                try:
                    pw_inputs = p.locator('input[type="password"]')
                    pw_count = pw_inputs.count()
                except Exception:
                    pw_count = 0
                if has_curr or pw_count > 0:
                    break
                if _entry == 0:
                    self.log('[🔄] Change-password form bounced out of Accounts Center — re-entering…')
                    self._ac_section("/password_and_security/", "Password and security")
                    self._try_click(p, "Change password", timeout=8000)
                    p.wait_for_timeout(800)  # outer loop polls _form_open()

        if not has_curr and (pw_inputs is None or pw_inputs.count() == 0):
            self._pw_fail_reason = "form_not_found"
            self.log(f'[⚠️] change-password form not found (url={p.url}) | {self._page_tail(p)}')
            if _time.time() - _pw_t0 > 300:
                self._pw_fail_reason = "form_timeout"
                raise RuntimeError(
                    "Password stage exceeded 5 min with no form (email challenge likely unsolvable)")
            return False

        import re

        # Fill Current Password
        filled_curr = False
        for sel in (
            'input[name="current_password"]',
            'input[aria-label*="Current password" i]',
            'input[placeholder*="Current password" i]',
        ):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    self._clean_fill(p, el, curr, timeout=6000)
                    filled_curr = True
                    break
            except Exception:
                pass
        if not filled_curr:
            try:
                el = p.get_by_label(re.compile(r"Current password", re.I)).first
                if el.count() > 0 and el.is_visible():
                    self._clean_fill(p, el, curr, timeout=6000)
                    filled_curr = True
            except Exception:
                pass
        if not filled_curr and has_curr:
            filled_curr = self._try_fill(p, "Current password", curr, timeout=6000)
        elif not filled_curr and pw_inputs and pw_inputs.count() >= 3:
            try:
                pw_inputs.nth(0).fill(curr)
                filled_curr = True
            except Exception:
                pass

        # Fill New Password
        filled_new = False
        for sel in (
            'input[name="new_password"]',
            'input[aria-label*="New password" i]',
            'input[placeholder*="New password" i]',
        ):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    self._clean_fill(p, el, new_password, timeout=6000)
                    filled_new = True
                    break
            except Exception:
                pass
        if not filled_new:
            try:
                el = p.get_by_label(re.compile(r"^New password", re.I)).first
                if el.count() > 0 and el.is_visible():
                    self._clean_fill(p, el, new_password, timeout=6000)
                    filled_new = True
            except Exception:
                pass
        if not filled_new:
            filled_new = self._try_fill(p, "New password", new_password, timeout=6000)
        elif not filled_new and pw_inputs and pw_inputs.count() >= 2:
            try:
                idx = 1 if (has_curr or pw_inputs.count() >= 3) else 0
                pw_inputs.nth(idx).fill(new_password)
                filled_new = True
            except Exception:
                pass

        # Fill Re-type new password
        filled_retype = False
        for sel in (
            'input[name="new_password_confirm"]',
            'input[aria-label*="Re-type" i]',
            'input[placeholder*="Re-type" i]',
            'input[aria-label*="Confirm" i]',
            'input[placeholder*="Confirm" i]',
        ):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    self._clean_fill(p, el, new_password, timeout=6000)
                    filled_retype = True
                    break
            except Exception:
                pass
        if not filled_retype:
            try:
                el = p.get_by_label(re.compile(r"Re-type|Confirm", re.I)).first
                if el.count() > 0 and el.is_visible():
                    self._clean_fill(p, el, new_password, timeout=6000)
                    filled_retype = True
            except Exception:
                pass
        if not filled_retype:
            filled_retype = self._try_fill(p, "Re-type new password", new_password, timeout=6000)
        elif not filled_retype and pw_inputs and pw_inputs.count() >= 3:
            try:
                pw_inputs.nth(2).fill(new_password)
                filled_retype = True
            except Exception:
                pass

        # -- Verify the three fields ACTUALLY hold the intended values BEFORE
        # submitting. React-controlled AC inputs can swallow fill/typing
        # (reproduced live via MCP 2026-09-21): the field stays empty, the submit
        # button is a no-op, and the stage reports not_confirmed. Re-inject the
        # exact value via the native setter; abort only if a field truly won't
        # hold. This does NOT change which value goes in which field
        # (0 = current/old, 1 = new, 2 = re-type/new).
        try:
            _n = pw_inputs.count() if pw_inputs is not None else 0
        except Exception:
            _n = 0
        if _n >= 1:
            _targets = []
            if has_curr:
                _targets.append((0, curr))
                if _n >= 2:
                    _targets.append((1, new_password))
                if _n >= 3:
                    _targets.append((2, new_password))
            else:
                _targets.append((0, new_password))
                if _n >= 2:
                    _targets.append((1, new_password))
            _bad = []
            for _idx, _want in _targets:
                try:
                    _el = pw_inputs.nth(_idx)
                    if _el.input_value() == _want:
                        continue
                    try:
                        _el.fill(_want, timeout=4000)
                    except Exception:
                        pass
                    if _el.input_value() != _want:
                        self._react_set_value(_el, _want)
                    if _el.input_value() != _want:
                        _bad.append(_idx)
                except Exception:
                    pass
            if _bad:
                self._pw_fail_reason = "fill_not_landed"
                self.log(f'[⚠️] Change-password fields {_bad} did not hold their values — aborting submit.')
                return False

        # Click submit button at bottom of form
        submitted = False
        for btn_sel in (
            '[role="button"]:has-text("Change password")',
            'button:has-text("Change password")',
            '[role="button"]:has-text("Save")',
            'button:has-text("Save")',
            'button[type="submit"]',
        ):
            try:
                btn = p.locator(btn_sel).last
                if btn.count() and btn.is_visible():
                    self._human_click(p, btn, 6000)
                    submitted = True
                    break
            except Exception:
                pass
        if not submitted:
            submitted = self._try_click(p, "Change password", timeout=8000)

        if submitted:
            # Success toast ("Meta Account password updated") can take
            # 10-20s to render — poll instead of judging one snapshot.
            success_markers = (
                "password updated",
                "password saved",
                "changes saved",
                "meta account password updated",
            )
            error_markers = ("incorrect", "invalid", "wrong", "doesn't match",
                             "does not match", "try again", "something went wrong")
            body = ""
            # Poll at 500ms (was a blind 2000ms step): the "Meta Account
            # password updated" toast usually renders in well under a second,
            # so the old granularity added 2-6s of pure wait to every change.
            for _poll in range(40):
                p.wait_for_timeout(500)
                body = self._page_tail(p, 800).lower()
                if any(k in body for k in error_markers):
                    break
                if any(k in body for k in success_markers):
                    break
                try:
                    if ("password_and_security" in (p.url or "")
                            and p.locator('input[type="password"]').count() == 0):
                        break
                except Exception:
                    pass
            # Submitting the new password can trigger a Two-Step-Verification
            # EMAIL re-auth ("Check your email — Enter the code we sent to …").
            # The old code never solved it: it polled 20s for a success toast,
            # found none, and reported "not confirmed" (observed 2026-09-20:
            # stuck until the TG task TTL cancelled it — a burned Meta account).
            # Solve the challenge here, then re-poll for the success toast.
            if _challenge_present():
                self.log('[🔐] Password change asked for email re-auth — fetching the code…')
                try:
                    self._ac_reauth(p, password=curr)
                except Exception as exc:
                    self.log(f'[ac] password re-auth error: {exc}')
                for _poll in range(40):
                    p.wait_for_timeout(500)
                    body = self._page_tail(p, 800).lower()
                    if any(k in body for k in error_markers):
                        break
                    if any(k in body for k in success_markers):
                        break
                    try:
                        if ("password_and_security" in (p.url or "")
                                and p.locator('input[type="password"]').count() == 0
                                and not _challenge_present()):
                            break
                    except Exception:
                        pass
            self.log(f'[ac] change-pass result: {self._page_tail(p, 300)}')

            # Check 1: "New password must be different from current password." (Image 1)
            # This confirms the account's active password is ALREADY new_password!
            if "must be different" in body:
                self.log('[✓] Accounts Center: New password is already active on this account. Dismissing modal…')
                self.password = new_password
                try:
                    close_btn = p.locator('button[aria-label*="Close" i], svg[aria-label*="Close" i], [aria-label*="Close" i]').first
                    if close_btn.count() and close_btn.is_visible():
                        close_btn.click(force=True, timeout=2000)
                except Exception:
                    try:
                        p.keyboard.press("Escape")
                    except Exception:
                        pass
                p.wait_for_timeout(1500)
                return True

            # Check 2: Form validation / credential rejection errors
            # NOTE: define has_error here — line ~1662 uses it, and the old code
            # referenced an undefined name, so that path always raised
            # `NameError: name 'has_error' is not defined` (a failed password
            # stage -> strict cleanup -> TG task cancelled; seen live 2026-09-19).
            has_error = any(k in body for k in ("incorrect", "invalid", "wrong", "doesn't match", "does not match", "try again", "something went wrong"))
            if has_error:
                self._pw_fail_reason = "rejected"
                self.log(f'[⚠️] change rejected (url={p.url})')
                return False

            # Check 3: Success messages or form dismissal.
            # NOTE: do NOT gate on mere presence of [role="alert"] — AC pages
            # always carry assertive live-regions, which made every success
            # (incl. the "Meta Account password updated" toast) report
            # "not confirmed". Error text above already returned False.
            if (
                "password updated" in body
                or "password saved" in body
                or "changes saved" in body
                or "meta account password updated" in body
                or ("password_and_security" in (p.url or "") and p.locator('input[type="password"]').count() == 0)
            ):
                self.password = new_password
                self.log('<font color="#00FF00"><b>[✔] Password set (Meta account).</b></font>')
                self._dismiss_extra_protection_upsell(p)
                return True

            if not has_error and p.locator('input[type="password"]').count() == 0:
                self.password = new_password
                self.log('<font color="#00FF00"><b>[✔] Password set (Meta account assumed).</b></font>')
                self._dismiss_extra_protection_upsell(p)
                return True

        self._pw_fail_reason = "not_confirmed"
        self.log(f'[⚠️] Change password not confirmed (url={p.url}) | {self._page_tail(p)}')
        return False

    def _read_reset_link_from_mail(self, timeout: int = 180) -> Optional[str]:
        """Poll the mail.td tab for the Instagram password-reset link."""
        mail = getattr(self, "mail", None) or self.page
        end = time.time() + timeout
        self.log('[✉️] Waiting for Instagram reset email in mail.td…')
        while time.time() < end and self.w.is_running:
            try:
                mail.get_by_text("Reset your password", exact=False).first.click(timeout=3000)
                mail.wait_for_timeout(2500)
            except Exception:
                pass
            try:
                links = mail.evaluate(
                    """() => { const out = [];
                        for (const a of document.querySelectorAll('a')) if (a.href) out.push(a.href);
                        for (const f of document.querySelectorAll('iframe')) {
                          try { f.contentDocument.querySelectorAll('a').forEach(a => a.href && out.push(a.href)); } catch (e) {}
                        }
                        return out; }"""
                )
                for href in links or []:
                    if "password/reset/confirm" in href:
                        self.log('[🔗] Found Instagram reset link in email.')
                        return href
            except Exception:
                pass
            mail.wait_for_timeout(3000)
        return None

    def ig_reset_password(self, new_password: str) -> bool:
        """Set a standalone Instagram password via reset email link."""
        p = self._ig_tab()
        self.log('[🔑] Instagram: setting a standalone password via reset link…')
        self._ac_section("/password_and_security/", "Password and security")
        self._try_click(p, "Change password", timeout=8000)
        p.wait_for_timeout(3000)
        for _ in range(4):
            if not self._ac_reauth(p):
                break
            p.wait_for_timeout(2500)
        self._ac_choose_account(p)
        p.wait_for_timeout(2500)
        for _ in range(3):
            if not self._ac_reauth(p):
                break
            p.wait_for_timeout(2500)
        forgot = (
            self._try_click(p, "Forgot your password?", timeout=8000)
            or self._try_click(p, "Forgot your password?", role="link", timeout=6000)
            or self._try_click(p, "Forgot password?", timeout=6000)
        )
        if not forgot:
            self.log(f'[⚠️] "Forgot your password?" not found (url={p.url}) | {self._page_tail(p)}')
            return False
        p.wait_for_timeout(4000)
        link = self._read_reset_link_from_mail()
        if not link:
            self.log('[⚠️] reset link not found in mail.td.')
            return False
        self.log('[🔗] reset link found; opening in an isolated context…')
        browser = self.w.playwright.chromium.launch(headless=self.w.is_headless)
        try:
            ctx = browser.new_context()
            rp = ctx.new_page()
            rp.goto(link, wait_until="domcontentloaded", timeout=60000)
            rp.wait_for_timeout(4000)
            for _ in range(2):
                if self._try_fill(rp, "New password", new_password, timeout=8000):
                    self._try_click(rp, "Continue", timeout=8000)
                    rp.wait_for_timeout(7000)
                elif self._try_fill(rp, "Enter new password", new_password, timeout=6000):
                    self._try_click(rp, "Continue", timeout=8000)
                    rp.wait_for_timeout(7000)
                else:
                    break
            self.password = new_password
            self.log('<font color="#00FF00"><b>[✔] Standalone password set.</b></font>')
            return True
        except Exception as exc:  # noqa: BLE001
            self.log(f'[⚠️] reset failed: {exc}')
            return False
        finally:
            try:
                browser.close()
            except Exception:
                pass
