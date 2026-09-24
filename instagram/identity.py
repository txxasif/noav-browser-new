"""Identity mutation & contact-email linkage. Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides run._MetaInstagramRunner helpers."""
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


class IgIdentityMixin:
    """Identity mutation & contact-email linkage."""

    def ig_get_display_name(self) -> Optional[str]:
        """Read the CURRENT profile display name from Accounts Center.

        Used as a quota guard: display names can only change twice per
        14 days, so callers must compare against this (never a stale
        record) before spending a change.
        """
        try:
            p = self._ig_tab()
            self._ac_open(Urls.AC_PROFILES, ["Profiles", "Name"])
            if not self._ac_choose_account(p, prefer_instagram=True):
                self._try_click(p, self.ig_username or self.username, role="button", timeout=6000)
            p.wait_for_timeout(2500)
            for sel in ('h3', '[role="heading"]'):
                try:
                    els = p.locator(sel).all()
                    for el in els[:6]:
                        try:
                            txt = (el.inner_text() or "").strip()
                        except Exception:
                            continue
                        if txt and len(txt) < 64 and "profile" not in txt.lower():
                            return txt
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def ig_change_name(self, new_name: str) -> bool:
        """Update profile name in Accounts Center (Profiles -> <Profile> -> Name)."""
        p = self._ig_tab()
        self.log(f'[🏷️] Instagram: changing name → {new_name}')
        self._ac_open(Urls.AC_PROFILES, ["Profiles", "Name"])

        # Open the profile card
        if not self._ac_choose_account(p, prefer_instagram=True):
            self._try_click(p, self.ig_username or self.username, role="button", timeout=6000)
        p.wait_for_timeout(3000)
        for _ in range(2):
            if not self._ac_reauth(p):
                break
            p.wait_for_timeout(2000)
        if not self._try_click(p, "Name", role="link", timeout=6000):
            self._try_click(p, "Name", timeout=6000)
        p.wait_for_timeout(3000)

        # Clear text button or select all + backspace
        self._try_click(p, "Clear text", role="button", timeout=2000)
        filled = False
        for sel in ('input[name="name"]', 'input[aria-label="Name"]', 'input[type="text"]', 'input'):
            try:
                inp = p.locator(sel).first
                if inp.count() > 0 and inp.is_visible():
                    inp.click()
                    p.keyboard.press("Control+A")
                    p.keyboard.press("Backspace")
                    inp.fill(new_name)
                    self._dispatch_react_events(p, inp)
                    filled = True
                    break
            except Exception:
                continue
        if not filled:
            filled = self._try_fill(p, "Name", new_name, timeout=8000)

        p.wait_for_timeout(2000)
        for btn in ("Done", "Save", "Change name"):
            if self._try_click(p, btn, timeout=6000):
                p.wait_for_timeout(4000)
                self.name = new_name
                self.log(f'<font color="#00FF00"><b>[✔] Name changed to {new_name}.</b></font>')
                return True
        self.log('[⚠️] Name change not confirmed.')
        return False

    def ig_change_username(self, new_username: str) -> bool:
        """Update username in Accounts Center (Profiles -> <Profile> -> Username)."""
        p = self._ig_tab()
        self.log(f'[🏷️] Instagram: changing username → {new_username}')
        self._ac_open(Urls.AC_PROFILES, ["Profiles", "Username"])

        # Open the profile card
        if not self._ac_choose_account(p, prefer_instagram=True):
            self._try_click(p, self.ig_username or self.username, role="button", timeout=6000)
        p.wait_for_timeout(3000)
        for _ in range(2):
            if not self._ac_reauth(p):
                break
            p.wait_for_timeout(2000)
        if not self._try_click(p, "Username", role="link", timeout=6000):
            self._try_click(p, "Username", timeout=6000)
        p.wait_for_timeout(3000)

        # Clear text button or select all + backspace
        self._try_click(p, "Clear text", role="button", timeout=2000)
        filled = False
        for sel in ('input[name="username"]', 'input[aria-label="Username"]', 'input[type="text"]', 'input'):
            try:
                inp = p.locator(sel).first
                if inp.count() > 0 and inp.is_visible():
                    inp.click()
                    p.keyboard.press("Control+A")
                    p.keyboard.press("Backspace")
                    inp.fill(new_username)
                    self._dispatch_react_events(p, inp)
                    filled = True
                    break

            except Exception:
                continue
        if not filled:
            filled = self._try_fill(p, "Username", new_username, timeout=8000)

        p.wait_for_timeout(3000)
        clicked_save = False
        for sel in (
            'button:has-text("Done")',
            '[role="button"]:has-text("Done")',
            'button:has-text("Save")',
            '[role="button"]:has-text("Save")',
            'button:has-text("Change username")',
            '[role="button"]:has-text("Change username")',
        ):
            try:
                btn = p.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    self._tap_or_click(p, btn)
                    clicked_save = True
                    break
            except Exception:
                pass
        if not clicked_save:
            for btn in ("Done", "Save", "Change username"):
                if self._try_click(p, btn, timeout=6000):
                    clicked_save = True
                    break

        if clicked_save:
            p.wait_for_timeout(5000)
            body = self._page_tail(p, 400).lower()
            if any(err in body for err in ("not available", "is not available", "please choose another")):
                self.log(f'[⚠️] Username {new_username} is not available!')
                return False
            self.ig_username = new_username
            self.log(f'<font color="#00FF00"><b>[✔] Username changed to {new_username}.</b></font>')
            return True
        self.log('[⚠️] Username change not confirmed.')
        return False

    def ig_link_email_to_instagram(self, target_email: Optional[str] = None) -> bool:
        """Ensure the account email is linked and confirmed directly on the Instagram profile.
        Essential for Telegram Taskly submissions to prevent rejection:
        'Your report was rejected because the Instagram account was registered without an email address.'
        """
        em = target_email or getattr(self, "email", None)
        if not em:
            self.log('[⚠️] ig_link_email_to_instagram: No email provided or available.')
            return False

        p = self._ig_tab()
        self.log(f'[✉️] Instagram: verifying/linking email ({em}) to Instagram profile…')

        # Risky-contact-point gate (no Skip) — DEAD END: close, never click
        # "Update email address" (operator decision 2026-09-21).
        if self._is_email_risky_screen(p):
            raise IGDeadEnd(
                "IG email risky contact point (email_risky_contactpoint) — closing")

        # Dead-end guard: a bare saved-account chooser, or a bounce to the IG
        # login wall, means the Meta join never established a real session.
        # Abort so the creator discards this account (close + next) instead of
        # parking a broken record with no linked email.
        try:
            if self._is_ig_dead_end_chooser(p) or "/accounts/login" in (p.url or ""):
                # Session dropped mid-AC (IG require_login hold), NOT necessarily
                # a failed Meta join — try to re-login with the creds we own
                # before declaring a dead end (observed 2026-09-21).
                if self._chooser_relogin(p):
                    self.log('[✔] Recovered dropped session — continuing email link.')
                    p = self._ig_tab()
                elif self._is_ig_dead_end_chooser(p):
                    raise IGDeadEnd("IG saved-account chooser with the bare email profile — Meta join failed (re-login failed)")
                else:
                    raise IGDeadEnd(f"IG session lost (login wall) at {(p.url or '')[:80]}")
        except IGDeadEnd:
            raise
        except Exception:
            pass

        # 1. Open Contact Points via the REAL in-app path (AC home → profile
        # card → Default contact info → contact_points). The old
        # _ac_section("/personal_info/contact_points/") searched the AC home for
        # a row that does not exist → false "AC section unreachable".
        self._ac_open_contact_points(p)
        for _ in range(3):
            if not self._ac_reauth(p):
                break
            p.wait_for_timeout(2000)

        body_low = self._page_tail(p, 800).lower()

        # Check if email is already listed
        if em.lower() in body_low:
            self.log(f'[✉️] Found email "{em}" in Contact info. Checking profile association…')
            # Click the email item to inspect which accounts use it
            clicked = False
            for sel in (
                f'div[role="button"]:has-text("{em}")',
                f'button:has-text("{em}")',
                f'div[aria-label*="{em}" i]',
            ):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        el.click(force=True, timeout=4000)
                        clicked = True
                        break
                except Exception:
                    pass

            if clicked:
                p.wait_for_timeout(3000)
                self._ac_reauth(p)
                tail = self._page_tail(p, 600).lower()
                ig_name = (getattr(self, "ig_username", None) or getattr(self, "username", "")).lower()

                # If Instagram is already associated
                if "instagram" in tail and (not ig_name or ig_name in tail):
                    self.log('<font color="#00FF00"><b>[✔] Email is confirmed & linked to Instagram profile.</b></font>')
                    return True

                # If Instagram is not yet associated, look for option to add/toggle Instagram
                for btn_sel in (
                    'div[role="button"]:has-text("Instagram")',
                    'button:has-text("Instagram")',
                    'input[type="checkbox"]',
                    'button:has-text("Add to")',
                ):
                    try:
                        b = p.locator(btn_sel).first
                        if b.count() and b.is_visible():
                            b.click(force=True, timeout=3000)
                            p.wait_for_timeout(1500)
                            break
                    except Exception:
                        pass

                # Save / Continue
                for done_sel in ('button:has-text("Save")', 'button:has-text("Next")', 'button:has-text("Done")'):
                    self._try_click(p, done_sel, timeout=3000)

                p.wait_for_timeout(3000)
                self.log('<font color="#00FF00"><b>[✔] Associated email with Instagram.</b></font>')
                return self._email_confirmed(p, em)

        # 2. If email is not listed or needs to be added fresh:
        self.log(f'[✉️] Adding fresh contact email: {em}…')
        # The contact_points page shows "Add or edit contact info" → opens the
        # "Contact info" dialog → "Add new contact info" → "Add email"
        # (verified live via MCP 2026-09-20). Without this first click the old
        # code never found "Add new contact".
        self._try_click(p, "Add or edit contact info", timeout=5000)
        p.wait_for_timeout(2000)
        add_clicked = (
            self._try_click(p, "Add new contact", timeout=5000)
            or self._try_click(p, "Add contact", timeout=4000)
        )
        if not add_clicked:
            try:
                el = p.locator('div[role="button"]:has-text("Add new contact"), button:has-text("Add new contact")').first
                if el.count() and el.is_visible():
                    el.click(force=True, timeout=3000)
                    add_clicked = True
            except Exception:
                pass

        if add_clicked:
            p.wait_for_timeout(2500)
            self._ac_reauth(p)
            self._try_click(p, "Add email", timeout=5000) or self._try_click(p, "Add email address", timeout=5000)
            p.wait_for_timeout(2500)

            # Fill email
            filled = False
            for sel in ('input[type="email"]', 'input[type="text"]', 'input[placeholder*="email" i]'):
                try:
                    inp = p.locator(sel).first
                    if inp.count() and inp.is_visible():
                        inp.click()
                        inp.fill(em)
                        self._dispatch_react_events(p, inp)
                        filled = True
                        break
                except Exception:
                    pass

            # Select Instagram account
            for sel in (
                'div[role="checkbox"]',
                'input[type="checkbox"]',
                'div[role="button"]:has-text("Instagram")',
                'button:has-text("Instagram")',
            ):
                try:
                    cb = p.locator(sel).first
                    if cb.count() and cb.is_visible():
                        cb.click(force=True, timeout=3000)
                        break
                except Exception:
                    pass

            p.wait_for_timeout(1500)
            self._try_click(p, "Next", timeout=6000)
            p.wait_for_timeout(4000)

            # Check if confirmation OTP is requested
            tail = self._page_tail(p, 400).lower()
            if any(k in tail for k in ("confirmation code", "enter code", "check your email")):
                self.log('[✉️] Accounts Center email verification code requested. Polling temp mail…')
                code = getattr(self, "fetch_code", lambda *a, **kw: None)("instagram", timeout=120) or getattr(self, "fetch_code", lambda *a, **kw: None)("meta", timeout=60)
                if code:
                    self.log(f'[✉️] Entering confirmation code: {code}')
                    filled = False
                    for sel in ('input[placeholder*="code" i]', 'input[name="confirmationCode"]',
                                'input[inputmode="numeric"]', 'input[type="text"]'):
                        try:
                            inp = p.locator(sel).first
                            if inp.count() and inp.is_visible():
                                inp.click(force=True, timeout=2000)
                                inp.fill(str(code))
                                # React can swallow fill (invariant 19): VERIFY the
                                # value landed, else Next submits an empty code and
                                # the email is never confirmed.
                                try:
                                    if inp.input_value() != str(code):
                                        inp.evaluate(
                                            "(el, v) => { el.value = v;"
                                            " el.dispatchEvent(new Event('input',{bubbles:true}));"
                                            " el.dispatchEvent(new Event('change',{bubbles:true})); }",
                                            str(code))
                                except Exception:
                                    pass
                                filled = True
                                break
                        except Exception:
                            pass
                    if not filled:
                        self.log('[⚠️] Email confirmation-code input not found.')
                        return False
                    self._try_click(p, "Next", timeout=6000)
                    # Poll for the app's "Email added" toast (definitive) or an
                    # error — never a blind 4s and never an optimistic success log.
                    confirmed = False
                    for _ in range(16):
                        p.wait_for_timeout(500)
                        try:
                            body = (p.inner_text("body") or "").lower()
                        except Exception:
                            body = ""
                        if "email added" in body:
                            confirmed = True
                            break
                        if any(k in body for k in ("invalid", "incorrect", "wrong",
                                                   "expired", "try again",
                                                   "didn't match", "did not match")):
                            self.log('[⚠️] Email confirmation code rejected by Accounts Center.')
                            break
                    if confirmed:
                        self.log(f'<font color="#00FF00"><b>[✔] Email {em} added (toast confirmed).</b></font>')
                        return True
                    self._try_click(p, "Close", timeout=4000)
                    return self._email_confirmed(p, em)

        self.log('[ℹ️] Email linking flow finished.')
        return self._email_confirmed(p, em)

    def ig_fix_risky_contactpoint(self, new_email: Optional[str] = None) -> bool:
        """DEPRECATED / DISABLED (operator decision 2026-09-21).

        IG's "Your email may not be secure" gate
        (``/accounts/update_risky_contactpoint/``) is a **DEAD END**: there is no
        Skip, and clicking "Update email address" just hangs on the next screen.
        Callers now raise ``IGDeadEnd('...email_risky_contactpoint...')`` so the
        browser is CLOSED and the slot moves to the next account. This method no
        longer clicks anything and always returns False (kept for API
        compatibility)."""
        self.log('[!] Risky-contactpoint gate is a dead end - not clicking Update email address.')
        return False

    def _email_confirmed(self, p, em: str, tries: int = 6) -> bool:
        """Confirm the email is in the account's contact-info LIST.

        Replaces the old optimistic ``return True``. CRITICAL (verified live
        2026-09-20): the **Default-contact-info page shows only the DEFAULT
        email**, so a newly added SECONDARY email is invisible there — the old
        check looked at that page and returned False even though the add
        succeeded ("Email added"), which raised the gate and cancelled the task.
        The full list is behind **"Add or edit contact info"**.
        """
        want = (em or "").strip().lower()
        if not want:
            return False
        for _ in range(max(1, tries)):
            try:
                p = self._ig_tab()
                body = (p.inner_text("body") or "").lower()
                if want in body:
                    self.log(f'<font color="#00FF00"><b>[✔] Email {em} confirmed in contact info.</b></font>')
                    return True
                if "email added" in body:
                    self.log(f'<font color="#00FF00"><b>[✔] "Email added" toast seen for {em}.</b></font>')
                    return True
            except Exception:
                pass
            try:
                p.wait_for_timeout(1000)
            except Exception:
                pass
        # Re-open the FULL contact-info list (Default page hides secondaries).
        try:
            self._ac_open_contact_points(p)
            p = self._ig_tab()
            for _role in ("button", "link"):
                try:
                    if self._try_click(p, "Add or edit contact info", role=_role, timeout=5000):
                        break
                except Exception:
                    pass
            p.wait_for_timeout(2500)
            body = (p.inner_text("body") or "").lower()
            if want in body:
                self.log(f'<font color="#00FF00"><b>[✔] Email {em} confirmed in contact info.</b></font>')
                return True
            self.log(f'[⚠️] Email {em} not found in the contact-info list.')
            return False
        except Exception:
            return False
