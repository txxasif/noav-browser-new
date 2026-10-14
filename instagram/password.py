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

    _AC_CHALLENGE_WORDS = ("check your email", "enter the code we sent", "enter code we sent",
                           "get a new code", "sent a code to", "enter the 6-digit code",
                           "enter the 8-digit code")

    def ig_ac_preauth(self, current_password: str, max_wait: float = 300.0) -> bool:
        """Clear Accounts Center's "Check your email" challenge BEFORE the bot task starts.

        Touching the Change-password form's Current password field makes Meta send an
        email OTP, which can take seconds to minutes to arrive. Once one code is
        accepted, Meta does not ask again for the next few minutes (observed live
        2026-10-12: the follow-up password change needed no code). Doing the wait here,
        before the PayGo task timer starts, keeps the real task window for the steps
        that must happen inside it. Best-effort: returns False instead of raising, and
        the normal password step still handles a challenge if one appears later.
        """
        if not current_password:
            return False
        p = self._ig_tab()
        try:
            # Old flow (direct): the change-password form is opened by URL, as before.
            p.goto("https://accountscenter.instagram.com/password_and_security/password/change/",
                   referer="https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            inp = p.locator('input[type="password"]').first
            inp.wait_for(state="visible", timeout=20000)
            inp.click(force=True, timeout=3000)
            inp.fill("")
            inp.fill(current_password)   # one step: the challenge dialog must not steal focus mid-typing
        except Exception as exc:
            self.log(f"[⚠️] AC pre-auth: could not open the change-password form ({str(exc)[:80]}).")
            return False

        def _challenge_up() -> bool:
            try:
                body = (p.inner_text("body") or "").lower()
            except Exception:
                return False
            return any(w in body for w in self._AC_CHALLENGE_WORDS)

        p.wait_for_timeout(1500)
        if not _challenge_up():
            self.log("[🔐] AC pre-auth: no email challenge shown (already verified).")
            return True
        self.log("[🔐] AC pre-auth: email challenge shown — solving it before the bot task starts…")
        end = time.time() + max_wait
        while time.time() < end and _challenge_up():
            try:
                self._ac_reauth(p, password=current_password)
            except Exception as exc:
                self.log(f"[ac] pre-auth re-auth error: {str(exc)[:80]}")
            p.wait_for_timeout(2000)
        solved = not _challenge_up()
        self.log("[🔐] AC pre-auth: " + ("verified — the password step will not need a code."
                                       if solved else "challenge still open (timed out)."))
        return solved

    def _ac_pick_profile_row(self, p, which: str) -> bool:
        """Click one row of Accounts Center's "Choose an account…" list.

        Rows are buttons named "Profile picture, <user> <user> Instagram" and
        "Profile picture, <user> <user> Muse, Meta AI and more". Seen live (DevTools MCP,
        2026-10-12): the password change belongs on the META row (the stored password is accepted
        there and no email challenge comes up; the Instagram row answers "Invalid credentials"),
        while 2FA belongs on the INSTAGRAM row, because the bot logs into Instagram.
        ``which`` is "meta" or "instagram"."""
        import re as _re
        try:
            rows = p.get_by_role("button", name=_re.compile(r"^profile picture,", _re.I))
            n = rows.count()
            for i in range(n):
                row = rows.nth(i)
                if not row.is_visible():
                    continue
                label = (row.get_attribute("aria-label") or row.inner_text() or "").strip().lower()
                is_ig = label.endswith("instagram")
                if (which == "instagram") == is_ig:
                    row.click(timeout=4000)
                    self.log(f'[ac] chose the {which} row: "{label[:50]}"')
                    return True
        except Exception as exc:  # noqa: BLE001
            self.log(f'[ac] profile row pick note: {str(exc)[:70]}')
        return False

    _AC_PW_FORM_URL = "https://accountscenter.instagram.com/password_and_security/password/change/"

    _AC_CONTACT_URL = "https://accountscenter.instagram.com/youraccount/contact_points/"

    def ig_link_email_fast(self, email: str, code_fetcher=None, budget: float = 150.0) -> str:
        """Link the bot-issued email, driven exactly like the DevTools MCP runs.

        contact page -> "Add new contact (info)" -> "Add email" -> "Enter email" (+ tick the Instagram
        account when the dialog lists accounts) -> Next -> "Enter your confirmation code" -> the code
        comes from the bot's 📥 Get code (``code_fetcher``) -> Next -> "You've added your email to the
        accounts selected". Returns "linked", "in_use" ("The email address you entered is already in
        use" — the bot reuses mailboxes, so this is normal and the caller just carries on to 2FA) or
        "failed". Never raises on a UI miss.
        """
        import re as _re
        import time as _time
        p = self._ig_tab()
        email = (email or "").strip()
        if not email:
            return "failed"
        self.log(f'[✉️] Linking the bot email {email}…')
        try:
            p.goto(self._AC_CONTACT_URL, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:  # noqa: BLE001
            self.log(f'[✉️] contact page load note: {str(exc)[:70]}')

        def _btn(pattern, scope=None):
            try:
                root = scope or p
                b = root.get_by_role("button", name=_re.compile(pattern, _re.I)).first
                return b if b.count() and b.is_visible() else None
            except Exception:
                return None

        deadline = _time.time() + budget
        typed = False
        code_sent = False
        code_entered_at = 0.0
        while _time.time() < deadline:
            if "accountscenter.instagram.com" not in (p.url or ""):
                return "failed"
            try:
                body = (p.inner_text("body", timeout=2500) or "").lower().replace("\u2019", "'")
            except Exception:
                body = ""

            if "added your email" in body or "contact information update results" in body:
                self.log('[✉️] Bot email linked.')
                try:
                    c = _btn(r"^close$", p.locator('div[role="dialog"]'))
                    if c is not None:
                        c.click(timeout=2000)
                except Exception:
                    pass
                return "linked"
            if "already in use" in body or "already linked" in body or "already associated" in body:
                self.log('[✉️] The bot email is already in use elsewhere — carrying on to 2FA.')
                return "in_use"

            if any(k in body for k in ("check your email", "enter the code we sent", "two step verification")):
                try:
                    self._ac_reauth(p)
                except IGDeadEnd:
                    raise
                except Exception:
                    pass
                continue

            code_box = None
            try:
                cb = p.get_by_role("textbox", name=_re.compile(r"confirmation code", _re.I)).first
                if cb.count() and cb.is_visible():
                    code_box = cb
            except Exception:
                pass
            if code_box is not None:
                if not code_sent and code_fetcher is not None:
                    code = None
                    try:
                        code = code_fetcher()
                    except Exception as exc:  # noqa: BLE001
                        self.log(f'[✉️] bot code fetch error: {str(exc)[:70]}')
                    code_sent = True
                    if not code:
                        self.log('[✉️] No confirmation code from the bot — carrying on to 2FA.')
                        return "failed"
                    try:
                        code_box.fill(str(code), timeout=3000)
                        nxt = _btn(r"^next$", p.locator('div[role="dialog"]'))
                        if nxt is not None:
                            nxt.click(timeout=4000)
                        code_entered_at = _time.time()
                        self.log(f'[✉️] Confirmation code entered ({code}).')
                    except Exception as exc:  # noqa: BLE001
                        self.log(f'[✉️] code entry note: {str(exc)[:70]}')
                p.wait_for_timeout(400)
                continue

            email_box = None
            try:
                eb = p.get_by_role("textbox", name=_re.compile(r"^enter email$", _re.I)).first
                if eb.count() and eb.is_visible():
                    email_box = eb
            except Exception:
                pass
            if email_box is not None:
                dlg = p.locator('div[role="dialog"]')
                if not typed:
                    try:
                        email_box.fill(email, timeout=3000)
                        typed = True
                    except Exception:
                        pass
                # "Choose accounts for this email": tick the Instagram account (the bot logs into it)
                try:
                    # the checkbox's name ("<user> Instagram") comes from its <label>, so select by
                    # accessible name — reading attributes finds nothing
                    ig_box = dlg.get_by_role("checkbox", name=_re.compile(r"instagram", _re.I)).first
                    if ig_box.count() and not ig_box.is_checked():
                        try:
                            ig_box.check(timeout=2500)
                        except Exception:
                            ig_box.click(force=True, timeout=2000)
                except Exception:
                    pass
                nxt = _btn(r"^next$", dlg)
                if nxt is not None:
                    try:
                        if nxt.is_enabled():
                            nxt.click(timeout=4000)
                            p.wait_for_timeout(600)
                    except Exception:
                        pass
                p.wait_for_timeout(300)
                continue

            if code_sent and code_entered_at and _time.time() - code_entered_at > 5:
                if not any(k in body for k in ("isn't right", "incorrect", "try again", "invalid", "expired",
                                               "something went wrong", "couldn't")):
                    seen_local = email.split("@")[0].lower() in body
                    self.log('[✉️] Confirmation accepted — the dialog closed'
                             + (' and the account row shows the bot email.' if seen_local else '.'))
                    return "linked"
            add_email = _btn(r"^add email$")
            if add_email is not None:
                try:
                    add_email.click(timeout=3000)
                except Exception:
                    pass
                p.wait_for_timeout(400)
                continue
            add_new = _btn(r"^add new contact")
            if add_new is not None:
                try:
                    add_new.click(timeout=3000)
                except Exception:
                    pass
                p.wait_for_timeout(400)
                continue
            p.wait_for_timeout(300)

        self.log('[✉️] Email link did not finish in time — carrying on to 2FA.')
        return "failed"

    def _ac_solve_challenge_fast(self, p, budget: float = 170.0) -> bool:
        """Solve Accounts Center's "Check your email" challenge in a tight loop (seen live via the
        DevTools MCP: dialog "Two Step Verification", textbox "Code", button "Continue", link
        "Get a new code"). The code is read from the account inbox through ``self.fetch_code``; if no
        mail shows up within ~45 s the code is re-sent once, then once more, and after ``budget``
        seconds the account is given up on (Instagram occasionally never delivers — the old solver
        sat there for 2+ minutes). Returns True when the dialog closed with a code accepted."""
        import re as _re
        import time as _time
        fetcher = getattr(self, "fetch_code", None)
        if not callable(fetcher):
            return False
        end = _time.time() + budget
        hint = "authenticate your profile|authenticate|security code|meta account code|instagram|security"
        resends = 0
        while _time.time() < end:
            dlg = p.locator('div[role="dialog"]')
            try:
                box = dlg.get_by_role("textbox", name=_re.compile(r"^code$", _re.I)).first
                if not (box.count() and box.is_visible()):
                    return True            # the dialog is gone: solved (or never there)
            except Exception:
                return True
            code = None
            try:
                # Seen live: the challenge mail lands anywhere from ~10 s to ~50 s after it opens, and
                # sometimes never; resending early did not speed it up. Wait properly first
                # (90 s), then ONE resend + 50 s, then give the account up (a resend can invalidate a code in flight).
                wait_s = (90, 50)[min(resends, 1)]
                try:
                    code = fetcher("instagram", timeout=wait_s,
                                   subject_hint=hint, prefer_len=None)
                except TypeError:
                    code = fetcher("instagram", timeout=wait_s)
            except Exception as exc:  # noqa: BLE001
                self.log(f'[ac] fetch_code error: {str(exc)[:70]}')
            if not code:
                if resends >= 1 or _time.time() >= end:
                    break
                try:
                    resend = dlg.get_by_role("button", name=_re.compile(r"get a new code", _re.I)).first
                    if not (resend.count() and resend.is_visible()):
                        resend = dlg.get_by_role("link", name=_re.compile(r"get a new code", _re.I)).first
                    resend.click(timeout=3000)
                    resends += 1
                    self.log(f'[✉️] No email yet — asked Instagram for a new code ({resends}/1).')
                except Exception as exc:  # noqa: BLE001
                    self.log(f'[ac] resend note: {str(exc)[:60]}')
                    break
                continue
            try:
                box.fill(str(code), timeout=3000)
                dlg.get_by_role("button", name=_re.compile(r"^continue$", _re.I)).last.click(timeout=4000)
                self.log(f'[✉️] Challenge code entered ({code}).')
            except Exception as exc:  # noqa: BLE001
                self.log(f'[ac] challenge entry note: {str(exc)[:70]}')
            # wait for the dialog to close (accepted) or show an error (try the next code)
            t_end = _time.time() + 20
            while _time.time() < t_end:
                p.wait_for_timeout(400)
                try:
                    if not (box.count() and box.is_visible()):
                        return True
                except Exception:
                    return True
        self.log('[⚠️] The email challenge could not be solved (no code delivered).')
        return False

    def ig_set_password_fast(self, new_password: str, current_password: Optional[str] = None) -> Optional[bool]:
        """Change the password the way it was driven by hand through the DevTools MCP.

        One navigation (the change-password URL loads with the live session), then a state loop that
        reacts to whatever screen is showing — no section walking, no fixed sleeps:
          chooser ("Choose an account…")  -> pick the Instagram profile
          "Check your email" challenge    -> solve it; the form stays open afterwards, so submit again
          form                            -> fill current/new/re-type once, press "Change password"
          toast "Meta Account password updated" -> done
          "You can't make this change at the moment" -> new-device block (no retry can pass)
          "Invalid credentials"/"incorrect" -> the stored current password is wrong
        Returns True (changed), False (definitively failed, ``_pw_fail_reason`` set) or None (could not
        operate the form at all and nothing was submitted — the caller may fall back to the old walk).
        """
        import re as _re
        import time as _time
        p = self._ig_tab()
        self._pw_fail_reason = None
        curr = (current_password or self.password or "").strip()
        new_password = (new_password or "").strip()
        if not new_password:
            self.log('[⚠️] Password change skipped: new password missing.')
            return False
        if new_password == curr:
            self.log('[✓] Target password is already identical to current password — skipping Change Password form.')
            return True

        self.log('[🔑] Changing the password (direct form)…')
        if not (p.url or "").startswith(self._AC_PW_FORM_URL):
            try:
                p.goto(self._AC_PW_FORM_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:  # noqa: BLE001
                self.log(f'[🔑] change-password URL load note: {str(exc)[:80]}')

        def _field(pattern):
            try:
                loc = p.get_by_role("textbox", name=_re.compile(pattern, _re.I)).first
                return loc if loc.count() and loc.is_visible() else None
            except Exception:
                return None

        def _set(loc, val) -> bool:
            try:
                loc.fill(val, timeout=4000)
                if loc.input_value() != val:
                    self._react_set_value(loc, val)
                return loc.input_value() == val
            except Exception:
                return False

        deadline = _time.time() + 150
        idle_since = _time.time()
        reloads = 0
        refills = 0
        filled = False
        submits = 0
        cleared = 0          # email challenges solved so far
        need_resubmit = False
        last_submit = 0.0
        while _time.time() < deadline:
            if "accountscenter.instagram.com" not in (p.url or ""):
                self.log(f'[🔑] left Accounts Center (url={(p.url or "")[:70]})')
                return None if not submits else False
            try:
                body = (p.inner_text("body", timeout=2500) or "").lower().replace("\u2019", "'")
            except Exception:
                body = ""

            if "password updated" in body or "you changed your meta password" in body:
                self.password = new_password
                self.log('<font color="#00FF00"><b>[✔] Password set (Meta account).</b></font>')
                return True
            if "can't make this change at the moment" in body:
                self._pw_fail_reason = "device_block"
                self.log('[🚫] Meta blocked the password change ("can\'t make this change at the moment" — '
                         'new-device check). Stopping this account; no retry.')
                return False
            if submits and ("invalid credentials" in body or "current password is incorrect" in body):
                self._pw_fail_reason = "rejected"
                self.log('[⚠️] Password change rejected: the stored current password is wrong.')
                return False
            if self._is_ig_dead_end_chooser(p):
                raise IGDeadEnd("IG saved-account chooser detected during password change (session dropped) — aborting immediately")

            # 1) email challenge
            if any(k in body for k in ("check your email", "enter the code we sent", "enter code we sent")):
                self.log('[✉️] Email challenge — solving…')
                idle_since = _time.time()
                cleared += 1
                if cleared > 3:
                    self._pw_fail_reason = "otp_not_accepted"
                    return False
                if not self._ac_solve_challenge_fast(p):
                    self._pw_fail_reason = "otp_not_delivered"
                    return False
                need_resubmit = bool(submits)     # the form stays open and is NOT submitted by the code
                continue

            # 2) real account chooser -> the META row for a password change
            if "choose an account" in body:
                idle_since = _time.time()
                if not self._ac_pick_profile_row(p, "meta"):
                    try:
                        self._ac_choose_account(p, prefer_instagram=False)
                    except Exception:
                        pass
                p.wait_for_timeout(300)
                continue

            # 3) the form
            cur_f = _field(r"^current password")
            new_f = _field(r"^new password")
            re_f = _field(r"re-type")
            if new_f is not None and re_f is not None:
                idle_since = _time.time()
                # The dialog can come back EMPTY (it re-renders after a submit or a challenge). Seen
                # live: the old loop still believed it was filled and kept pressing a disabled button.
                try:
                    _emptied = (new_f.input_value() == "")
                except Exception:
                    _emptied = False
                if filled and _emptied:
                    if refills >= 4:
                        self._pw_fail_reason = "form_keeps_resetting"
                        self.log('[⚠️] The change-password form keeps resetting — giving up on this account.')
                        return False
                    refills += 1
                    filled = False
                    need_resubmit = False
                    last_submit = 0.0
                    self.log(f'[🔑] The form was reset (fields empty) — filling it again ({refills}/4).')
                if not filled:
                    ok_c = True if cur_f is None else _set(cur_f, curr)
                    ok_n = _set(new_f, new_password)
                    ok_r = _set(re_f, new_password)
                    self.log(f'[🔑] form filled (current={ok_c}, new={ok_n}, retype={ok_r})')
                    if not (ok_c and ok_n and ok_r):
                        self._pw_fail_reason = "type_failed"
                        return None if not submits else False
                    filled = True
                if submits == 0 or need_resubmit or (_time.time() - last_submit > 12 and "being validated" not in body):
                    btn = p.locator('div[role="dialog"]').get_by_role("button", name=_re.compile(r"^change password$", _re.I)).last
                    try:
                        if not btn.is_enabled():
                            p.wait_for_timeout(400)
                            continue
                        btn.click(timeout=5000)
                        submits += 1
                        last_submit = _time.time()
                        need_resubmit = False
                        self.log(f'[🔑] "Change password" pressed (#{submits})')
                    except Exception as exc:  # noqa: BLE001
                        self.log(f'[🔑] submit click note: {str(exc)[:70]}')
                p.wait_for_timeout(300)
                continue

            # 4) still on the Login and security list: open the form
            try:
                row = p.get_by_role("button", name=_re.compile(r"^change password$", _re.I)).first
                if row.count() and row.is_visible() and "re-type" not in body:
                    row.click(timeout=3000)
                    idle_since = _time.time()
            except Exception:
                pass
            # Nothing recognisable for a few seconds (the page sat idle while the bot task started and
            # went stale / blank): load the form again instead of waiting out the whole budget.
            if _time.time() - idle_since > 6 and reloads < 3 and not submits:
                reloads += 1
                self.log(f'[🔑] no known screen for 6 s — reloading the change-password form ({reloads}/3)')
                try:
                    p.goto(self._AC_PW_FORM_URL, wait_until="domcontentloaded", timeout=45000)
                except Exception:
                    pass
                idle_since = _time.time()
            p.wait_for_timeout(300)

        self._pw_fail_reason = "not_confirmed" if submits else "form_not_found"
        self.log(f'[⚠️] Password change not confirmed ({self._pw_fail_reason}) | {self._page_tail(p, 160)}')
        return False if submits else None

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
        _fast = self.ig_set_password_fast(new_password, curr)
        if _fast is not None or os.environ.get("PAYGO_SLOW_WALK", "0") != "1":
            # No fallback to the old section walk (it went through the Instagram feed and
            # Settings and was the source of the extra page loads): a miss fails the account.
            if _fast is None:
                self._pw_fail_reason = self._pw_fail_reason or "form_not_found"
            return bool(_fast)
        self.log('[🔑] Direct form could not be operated — falling back to the section walk.')
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
            try:
                body_all = (p.inner_text("body") or "").lower()
                if any(m in body_all for m in ("password updated", "password saved", "meta account password updated")):
                    return False
            except Exception:
                pass
            challenge_words = ("check your email", "enter the code we sent",
                               "enter code we sent", "get a new code",
                               "sent a code to", "enter the 6-digit code",
                               "enter the 8-digit code")
            # The "Check your email" card is not always a role=dialog/aria-modal
            # (the pool drain screenshot shows it as a plain card), so the page
            # body is checked as well — otherwise the OTP is never requested.
            try:
                if any(k in (p.inner_text("body") or "").lower() for k in challenge_words):
                    return True
            except Exception:
                pass
            for sel in (
                'div[role="dialog"]',
                'div[aria-modal="true"]',
            ):
                try:
                    for cand in p.locator(sel).all():
                        if cand.is_visible():
                            txt = (cand.inner_text() or "").lower()
                            if any(k in txt for k in challenge_words):
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
        meta_row_done = False
        while _time.time() < t_max:
            # Meta's new-device check ("You can't make this change at the moment"): no code
            # or retry helps. Stop this account now instead of clicking through to the form.
            try:
                _body = (p.inner_text("body") or "").lower().replace("\u2019", "'")
            except Exception:
                _body = ""
            if "can't make this change at the moment" in _body:
                self._pw_fail_reason = "device_block"
                self.log('[🚫] Meta blocked the password change ("can\'t make this change at the moment" — '
                         'new-device check). Stopping this account; no retry.')
                return False
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

            # C. If account selection screen is visible, choose Meta account.
            #    Learned live (DevTools MCP + the engine log, 2026-10-12): the header row of the
            #    CHANGE-PASSWORD dialog ("Meta symbol <email> 2 profiles") looks like an account row,
            #    but tapping it opens the profile list ("In this Meta Account") and the form is never
            #    reached. Only act on a REAL chooser ("Choose an account…"); while the form dialog is
            #    loading, just wait.
            try:
                _bl = (p.inner_text("body") or "").lower()
            except Exception:
                _bl = ""
            _in_form = any(k in _bl for k in ("current password", "re-type new password",
                                              "log out of other devices", "forgot your password"))
            _chooser = ("choose an account" in _bl or "select an account" in _bl)
            if "in this meta account" in _bl and not _chooser:
                # Landed on the profile list by mistake: go straight back to the change form.
                self.log('[🔑] On the profile list ("In this Meta Account") — returning to the Change password form…')
                try:
                    p.goto("https://accountscenter.instagram.com/password_and_security/password/change/",
                           wait_until="domcontentloaded", timeout=45000)
                except Exception:
                    pass
                p.wait_for_timeout(1500)
                continue
            _allow_pick = _chooser and not _in_form
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

            if not _allow_pick:
                meta_btn = None
            # The Meta account row was already opened once: tapping it again just
            # re-renders the same "Meta Account" page (the 90 s stall). Fall through
            # to "Login and security" → "Change password" instead.
            if meta_btn is not None and meta_row_done:
                meta_btn = None
            if meta_btn is not None:
                self.log('[🔑] Selecting Meta account row in Accounts Center…')
                try:
                    self._tap_or_click(p, meta_btn)
                except Exception:
                    meta_btn.click(force=True, timeout=2000)
                meta_row_done = True
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

            if _allow_pick and self._ac_choose_account(p, prefer_instagram=False):
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
                    elif meta_row_done:
                        # On the Meta Account page: "Change password" lives under "Login and security".
                        sec_row = p.locator('div[role="button"]:has-text("Login and security")').first
                        if sec_row.count() > 0 and sec_row.is_visible():
                            self.log('[🔑] Opening "Login and security" to reach Change password…')
                            self._tap_or_click(p, sec_row)
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
        def _safe_type_field(el, val, name, atomic=False):
            if el is None:
                return False
            try:
                # Scroll is BEST-EFFORT. A force-click + fill work WITHOUT it, and
                # a ``scroll_into_view_if_needed`` "element not stable" timeout used
                # to ABORT the whole password change (observed live 2026-10-03:
                # "Error typing Current password: Locator.scroll_into_view_if_needed:
                # Timeout 1445ms exceeded." → "Failed to fill Current password —
                # aborting", reason=unknown). The field WAS present; only the
                # smooth-scroll animation had not settled. Never let a cosmetic
                # scroll kill the step.
                try:
                    el.scroll_into_view_if_needed(timeout=1200)
                except Exception:
                    pass
                el.click(force=True, timeout=3000)
                p.wait_for_timeout(300)
                el.fill("")
                p.wait_for_timeout(200)
                if atomic:
                    # Touching the Current password field opens the "Two Step
                    # Verification / Check your email" dialog. Typing key by key
                    # lets that dialog steal focus mid-password, so the TAIL of
                    # the password lands in the Code box ("3#$#$"). Set it in one
                    # step instead.
                    el.fill(val)
                else:
                    el.press_sequentially(val, delay=35)
                p.wait_for_timeout(200)
                # Unconditionally invoke React native setter so synthetic state always updates
                self._react_set_value(el, val)
                p.wait_for_timeout(200)
                el.evaluate("""e => {
                    e.dispatchEvent(new Event('input', {bubbles: true}));
                    e.dispatchEvent(new Event('change', {bubbles: true}));
                    e.dispatchEvent(new Event('blur', {bubbles: true}));
                }""")
                p.wait_for_timeout(200)
                matched = (el.input_value() == val)
                self.log(f"[🔑] {name} typed (len={len(val)}, match={matched})")
                return matched
            except Exception as e:
                self.log(f"[⚠️] Error typing {name}: {e}")
                return False

        if curr_inp is not None:
            if not _safe_type_field(curr_inp, curr, "Current password", atomic=True):
                self._pw_fail_reason = "type_current_failed"
                self.log("[⚠️] Failed to fill Current password — aborting.")
                return False
            p.wait_for_timeout(1200)
            # The email challenge opens right after the current password is
            # entered — solve it NOW, before typing the new password, or the
            # next keystrokes go into the Code box.
            if _challenge_present():
                self.log('[✉️] Email challenge opened right after Current password — solving it before the new password…')
                try:
                    self._ac_reauth(p, password=curr)
                except Exception as exc:
                    self.log(f"[ac] early re-auth error: {exc}")
                p.wait_for_timeout(1500)

        if not _safe_type_field(new_inp, new_password, "New password"):
            self._pw_fail_reason = "type_new_failed"
            self.log("[⚠️] Failed to fill New password — aborting.")
            return False
        p.wait_for_timeout(600)

        if not _safe_type_field(retype_inp, new_password, "Re-type new password"):
            self._pw_fail_reason = "type_retype_failed"
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
        success_found = False
        for _poll in range(40):
            p.wait_for_timeout(500)
            body = (p.inner_text("body") or "").lower()
            if any(k in body for k in error_markers):
                break
            if any(k in body for k in success_markers):
                success_found = True
                break
            try:
                # If form inputs disappeared and not challenge, form submitted successfully
                if not new_inp.is_visible() and not _challenge_present():
                    success_found = True
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

        # Handle post-submit email re-auth ONLY if success was NOT already confirmed and challenge is present
        if not success_found and _challenge_present():
            self.log('[🔐] Password change asked for email re-auth — fetching the code…')
            try:
                self._ac_reauth(p, password=curr)
            except Exception as exc:
                self.log(f"[ac] password re-auth error: {exc}")
            # Learned live via the DevTools MCP (2026-10-12): once the emailed code is accepted the
            # dialog closes but the form stays open and the change is NOT submitted — press
            # "Change password" a second time.
            try:
                p.wait_for_timeout(1200)
                if new_inp.is_visible() and not _challenge_present():
                    self.log('[🔑] Challenge cleared — submitting "Change password" again…')
                    self._tap_or_click(p, submit_btn, 3000)
                    submit_btn.evaluate("el => el.click()")
            except Exception:
                pass
            for _poll in range(40):
                p.wait_for_timeout(500)
                body = (p.inner_text("body") or "").lower()
                if any(k in body for k in error_markers):
                    break
                if any(k in body for k in success_markers):
                    success_found = True
                    break
                try:
                    if not new_inp.is_visible() and not _challenge_present():
                        success_found = True
                        break
                except Exception:
                    pass

        self.log(f"[ac] change-pass result: {self._page_tail(p, 300)}")

        # Check for errors only if success was not found
        if not success_found and any(k in body for k in error_markers):
            self._pw_fail_reason = "rejected"
            self.log(f"[⚠️] Password change rejected by Instagram (url={p.url}): {body[:150]}")
            return False

        # Check for verified success: either success text or form confirmed closed
        form_closed = False
        try:
            form_closed = not new_inp.is_visible()
        except Exception:
            form_closed = True

        if success_found or any(k in body for k in success_markers) or form_closed:
            self.password = new_password
            self.log('<font color="#00FF00"><b>[✔] Password set (Meta account).</b></font>')
            # Dismiss any lingering modal / dialog overlay so next steps proceed unblocked
            try:
                self._dismiss_contact_modal(p)
            except Exception:
                pass
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
        if getattr(self, "mail_provider", "") == "guerrilla" and getattr(self, "email", ""):
            # API inbox: no mail tab to click through — read the message HTML over HTTP.
            import html as _html
            import re as _re
            from core import guerrilla_api
            self.log('[✉️] Waiting for Instagram reset email in Guerrilla Mail…')
            while time.time() < end and self.w.is_running:
                for m in guerrilla_api.list_messages(self.email, getattr(self, "_guerrilla_sid", "")):
                    blob = _html.unescape((m.get("html") or "") + " " + (m.get("text") or ""))
                    hit = _re.search(r"https?://[^\s\"'<>]*password/reset/confirm[^\s\"'<>]*", blob)
                    if hit:
                        self.log('[🔗] Found Instagram reset link in email.')
                        return hit.group(0)
                time.sleep(3)
            return None
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
