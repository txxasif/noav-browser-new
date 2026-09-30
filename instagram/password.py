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
        p = self._ig_tab()

        # When 2FA runs first (e.g. FastPay flow), Accounts Center is still on the
        # two_factor subpage. Because _ac_in_section matches /password_and_security/
        # for both, _ac_section would otherwise treat two_factor as already arrived
        # and the "Change password" row would never be found.
        if "two_factor" in (p.url or ""):
            self.log('[pwd] On a 2FA sub-page — returning to section list for Change password…')
            try:
                self._ac_leave_subpage(p)
            except Exception:
                pass
            p.wait_for_timeout(1500)
            p = self._ig_tab()

        self._ac_section("/password_and_security/", "Password and security")
        p = self._ig_tab()
        if "two_factor" in (p.url or ""):
            try:
                self._ac_leave_subpage(p)
            except Exception:
                pass
            p.wait_for_timeout(1200)
            p = self._ig_tab()

        try:
            for page in self.w.context.pages:
                if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                    self.insta_page = page
                    p = page
                    break
        except Exception:
            pass

        def _challenge_present() -> bool:
            targets = [p] + list(getattr(p, "frames", []))
            for tgt in targets:
                try:
                    low = (tgt.evaluate("() => document.body.innerText || ''") or "").lower()
                    if any(k in low for k in ("check your email", "enter the code we sent",
                                              "enter code we sent", "get a new code",
                                              "sent a code to", "enter the 6-digit code",
                                              "enter the 8-digit code")):
                        return True
                except Exception:
                    pass
            return False

        def _form_open() -> bool:
            """True ONLY when real password input fields are visible and no challenge modal covers them."""
            if _challenge_present():
                return False
            try:
                for sel in (
                    'input[name="new_password"]',
                    'input[aria-label*="New password" i]',
                ):
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        return True
            except Exception:
                pass
            try:
                vis_pw = [el for el in p.locator('input[type="password"]').all() if el.is_visible()]
                if len(vis_pw) >= 2:
                    return True
            except Exception:
                pass
            return False

        # Step 1: Click "Change password" from the Password & Security menu
        clicked_pw = False
        for _entry in range(4):
            if _form_open() or _challenge_present():
                break
            for sel_pw in (
                'div[role="button"][aria-label*="Change password" i]',
                'div[role="button"]:has-text("Change password")',
                'div[role="link"]:has-text("Change password")',
                'a[href*="password/change"]',
                'a:has-text("Change password")',
                'button:has-text("Change password")',
            ):
                try:
                    el = p.locator(sel_pw).first
                    if el.count() > 0 and el.is_visible():
                        self._tap_or_click(p, el)
                        clicked_pw = True
                        break
                except Exception:
                    pass
            if not clicked_pw:
                self._try_click(p, "Change password", timeout=3000)
            p.wait_for_timeout(1500)
            if _form_open() or _challenge_present():
                break

        # Step 2: Patiently resolve Account Chooser and/or Email OTP challenge until form is genuinely open
        self.log('[🔑] Navigating to Change Password form (handling account selection & OTP challenges)…')
        t_max = _time.time() + 90.0
        while _time.time() < t_max:
            if self._is_ig_dead_end_chooser(p):
                raise IGDeadEnd("IG saved-account chooser detected during password change (session dropped) — aborting immediately")

            # A. If email challenge is present, solve it calmly
            if _challenge_present():
                self.log('[✉️] Accounts Center OTP challenge detected ("Check your email") — solving…')
                self._ac_reauth(p, password=curr)
                p.wait_for_timeout(2500)
                continue

            # B. If password change form is open, we are done transitioning!
            if _form_open():
                break

            # C. If account selection screen is visible, choose Meta account
            meta_btn = None
            try:
                name_cand = p.locator(f'div[role="button"]:has-text("{self.name}")').first if self.name else None
                if name_cand is not None and name_cand.count() > 0 and name_cand.is_visible():
                    meta_btn = name_cand
                elif getattr(self, "email", None):
                    email_cand = p.locator(f'div[role="button"]:has-text("{self.email}")').first
                    if email_cand.count() > 0 and email_cand.is_visible():
                        meta_btn = email_cand
                if meta_btn is None:
                    loc = p.locator('div[role="button"]:has-text("Meta"), button:has-text("Meta")')
                    for i in range(min(loc.count(), 6)):
                        cand = loc.nth(i)
                        if not cand.is_visible():
                            continue
                        t = (cand.inner_text() or cand.get_attribute("aria-label") or "").lower()
                        if any(bad in t for bad in ("learn more", "control how your account works", "emails from meta", "security checkup", "meta pay", "back to", "about meta", "about", "help", "article", "meta accounts are")):
                            continue
                        href = (cand.get_attribute("href") or "").lower()
                        if "help" in href or cand.locator('a[href*="help"]').count() > 0:
                            continue
                        meta_btn = cand
                        break
            except Exception:
                pass

            if meta_btn is not None:
                self.log('[🔑] Selecting Meta account row in Accounts Center…')
                try:
                    self._tap_or_click(p, meta_btn)
                except Exception:
                    meta_btn.click(force=True, timeout=2000)
                p.wait_for_timeout(2500)
                # Close any stray help tab opened by misclick
                try:
                    for extra_p in list(p.context.pages):
                        if extra_p != p and "help" in (extra_p.url or "").lower():
                            self.log(f'[ac] Closing stray help tab: {extra_p.url[:60]}…')
                            extra_p.close()
                except Exception:
                    pass
                continue

            if self._ac_choose_account(p, prefer_instagram=False):
                self.log('[🔑] Account chosen via _ac_choose_account.')
                p.wait_for_timeout(2500)
                # Close any stray help tab opened by misclick
                try:
                    for extra_p in list(p.context.pages):
                        if extra_p != p and "help" in (extra_p.url or "").lower():
                            self.log(f'[ac] Closing stray help tab: {extra_p.url[:60]}…')
                            extra_p.close()
                except Exception:
                    pass
                continue

            # D. If still on the list, re-tap "Change password"
            cur_url = p.url or ""
            if "password/change" not in cur_url and not _form_open():
                try:
                    pw_row = p.locator('div[role="button"]:has-text("Change password")').first
                    if pw_row.count() > 0 and pw_row.is_visible():
                        self._tap_or_click(p, pw_row)
                except Exception:
                    pass

            p.wait_for_timeout(1000)

        # Allow 1.5s modal settlement so React DOM finishes mounting
        p.wait_for_timeout(1500)

        # Re-check if any trailing challenge appeared
        if _challenge_present():
            self.log('[✉️] Solving trailing email security challenge…')
            self._ac_reauth(p, password=curr)
            p.wait_for_timeout(2000)

        # Step 3: Locate form inputs
        curr_inp = None
        for sel in (
            "input[name=\"current_password\"]",
            "input[aria-label*=\"Current password\" i]",
            "input[placeholder*=\"Current password\" i]",
        ):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    curr_inp = el
                    break
            except Exception:
                pass

        new_inp = None
        for sel in (
            "input[name=\"new_password\"]",
            "input[aria-label*=\"New password\" i]",
            "input[placeholder*=\"New password\" i]",
        ):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    new_inp = el
                    break
            except Exception:
                pass

        retype_inp = None
        for sel in (
            "input[name=\"new_password_confirm\"]",
            "input[aria-label*=\"Re-type\" i]",
            "input[placeholder*=\"Re-type\" i]",
            "input[aria-label*=\"Confirm\" i]",
            "input[placeholder*=\"Confirm\" i]",
        ):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    retype_inp = el
                    break
            except Exception:
                pass

        # Positional fallback if specific selectors missed
        try:
            vis_pws = [el for el in p.locator('input[type="password"]').all() if el.is_visible()]
        except Exception:
            vis_pws = []

        if len(vis_pws) >= 3:
            if curr_inp is None: curr_inp = vis_pws[0]
            if new_inp is None: new_inp = vis_pws[1]
            if retype_inp is None: retype_inp = vis_pws[2]
        elif len(vis_pws) == 2:
            if new_inp is None: new_inp = vis_pws[0]
            if retype_inp is None: retype_inp = vis_pws[1]

        # Verify mandatory new password inputs exist!
        if new_inp is None or retype_inp is None:
            self._pw_fail_reason = "form_not_found"
            self.log(f'[⚠️] Change-password form inputs not found (url={p.url}) | {self._page_tail(p)}')
            return False

        # Step 4: Type fields with calm, human pacing and verify every value
        def _safe_type_field(el, val, name):
            if el is None:
                return False
            try:
                el.scroll_into_view_if_needed(timeout=3000)
                el.click(force=True, timeout=3000)
                p.wait_for_timeout(300)
                el.fill("")
                p.wait_for_timeout(200)
                el.press_sequentially(val, delay=45)
                p.wait_for_timeout(300)
                if el.input_value() != val:
                    self._react_set_value(el, val)
                    p.wait_for_timeout(200)
                el.evaluate("""e => {
                    e.dispatchEvent(new Event('input', {bubbles: true}));
                    e.dispatchEvent(new Event('change', {bubbles: true}));
                    e.dispatchEvent(new Event('blur', {bubbles: true}));
                }""")
                p.wait_for_timeout(300)
                matched = (el.input_value() == val)
                self.log(f"[🔑] {name} typed (len={len(val)}, match={matched})")
                return matched
            except Exception as e:
                self.log(f"[⚠️] Error typing {name}: {e}")
                return False

        if curr_inp is not None:
            if not _safe_type_field(curr_inp, curr, "Current password"):
                self.log("[⚠️] Failed to fill Current password — aborting.")
                return False
            p.wait_for_timeout(600)

        if not _safe_type_field(new_inp, new_password, "New password"):
            self.log("[⚠️] Failed to fill New password — aborting.")
            return False
        p.wait_for_timeout(600)

        if not _safe_type_field(retype_inp, new_password, "Re-type new password"):
            self.log("[⚠️] Failed to fill Re-type new password — aborting.")
            return False
        p.wait_for_timeout(800)

        # Step 5: Locate the real submit button (must be positioned below retype input)
        submit_btn = None
        retype_box = None
        try:
            retype_box = retype_inp.bounding_box()
        except Exception:
            pass

        for btn_sel in (
            'button:has-text("Change password")',
            'button[type="submit"]',
            'div[role="button"]:has-text("Change password")',
            'button:has-text("Save")',
            '[role="button"]:has-text("Save")',
        ):
            try:
                for cand in p.locator(btn_sel).all():
                    if not cand.is_visible():
                        continue
                    if retype_box:
                        try:
                            c_box = cand.bounding_box()
                            if c_box and c_box['y'] < retype_box['y'] - 10:
                                continue  # Above form inputs -> header/menu item, skip!
                        except Exception:
                            pass
                    submit_btn = cand
                    break
            except Exception:
                pass
            if submit_btn is not None:
                break

        if submit_btn is None:
            self._pw_fail_reason = "submit_btn_not_found"
            self.log('[⚠️] Submit button not found on change password form.')
            return False

        # Step 6: Wait calmly for button to become enabled (up to 15s)
        self.log('[🔑] Waiting for "Change password" button to become enabled…')
        btn_enabled = False
        for wait_i in range(30):
            aria_dis = submit_btn.get_attribute("aria-disabled")
            is_dis = submit_btn.is_disabled()
            if aria_dis != "true" and not is_dis:
                btn_enabled = True
                break
            p.wait_for_timeout(500)
            if wait_i in (4, 10, 18):
                try:
                    for el in (curr_inp, new_inp, retype_inp):
                        if el and el.count():
                            el.evaluate("e => { e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur', {bubbles: true})); }")
                except Exception:
                    pass

        if not btn_enabled:
            body = self._page_tail(p, 600).lower()
            if "must be different" in body:
                self.log('[✓] Accounts Center: New password is already active on this account.')
                self.password = new_password
                self._dismiss_contact_modal(p)
                return True
            self._pw_fail_reason = "submit_btn_disabled"
            self.log('[⚠️] "Change password" button remained disabled — refusing to click blindly.')
            return False

        # Step 7: Submit the form
        self.log('[🔑] "Change password" button is enabled! Submitting…')
        submitted = False
        try:
            if self._tap_or_click(p, submit_btn, 4000):
                submitted = True
        except Exception:
            pass

        if not submitted:
            try:
                submit_btn.click(force=True, timeout=3000)
                submitted = True
            except Exception:
                pass

        try:
            submit_btn.evaluate("el => el.click()")
            submitted = True
        except Exception:
            pass

        try:
            retype_inp.press("Enter")
        except Exception:
            pass

        if not submitted:
            self._pw_fail_reason = "submit_click_failed"
            self.log('[⚠️] Failed to click "Change password" button.')
            return False

        # Step 8: Verify outcome calmly
        success_markers = (
            "password updated",
            "password saved",
            "changes saved",
            "meta account password updated",
        )
        error_markers = ("incorrect", "invalid", "wrong", "doesn't match",
                         "does not match", "try again", "something went wrong")
        body = ""
        for _poll in range(40):
            p.wait_for_timeout(500)
            body = self._page_tail(p, 800).lower()
            if any(k in body for k in error_markers):
                break
            if any(k in body for k in success_markers):
                break
            try:
                # If form inputs disappeared and not challenge, form submitted successfully
                if not new_inp.is_visible() and not _challenge_present():
                    break
            except Exception:
                pass

            # If inputs are still visible after 3s and 7s, re-tap submit button to ensure click was received
            if _poll in (6, 14):
                try:
                    if new_inp.is_visible() and not _challenge_present():
                        self.log("[🔑] Re-triggering Change password submission…")
                        self._tap_or_click(p, submit_btn, 2000)
                        submit_btn.evaluate("el => el.click()")
                        retype_inp.press("Enter")
                except Exception:
                    pass

        # Handle post-submit email re-auth if requested
        if _challenge_present():
            self.log('[🔐] Password change asked for email re-auth — fetching the code…')
            try:
                self._ac_reauth(p, password=curr)
            except Exception as exc:
                self.log(f"[ac] password re-auth error: {exc}")
            for _poll in range(40):
                p.wait_for_timeout(500)
                body = self._page_tail(p, 800).lower()
                if any(k in body for k in error_markers):
                    break
                if any(k in body for k in success_markers):
                    break
                try:
                    if not new_inp.is_visible() and not _challenge_present():
                        break
                except Exception:
                    pass

        self.log(f"[ac] change-pass result: {self._page_tail(p, 300)}")

        # Check for errors
        if any(k in body for k in error_markers):
            self._pw_fail_reason = "rejected"
            self.log(f"[⚠️] Password change rejected by Instagram (url={p.url}): {body[:150]}")
            return False

        # Check for verified success: either success text or form confirmed closed
        form_closed = False
        try:
            form_closed = not new_inp.is_visible()
        except Exception:
            form_closed = True

        if any(k in body for k in success_markers) or form_closed:
            self.password = new_password
            self.log('<font color="#00FF00"><b>[✔] Password set (Meta account).</b></font>')
            self._dismiss_extra_protection_upsell(p)
            p.wait_for_timeout(1000)
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
