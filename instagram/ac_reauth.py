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

    def _ac_inbox_has_auth_mail(self) -> bool:
        """True when the mailbox already holds an "Authenticate your profile" mail.

        Reads the mail.td REST API (the message LIST) instead of the page DOM:
        the list page has no body text, so a DOM phrase check is almost always
        False and caused a resend ("Get a new code") on nearly every solve —
        which invalidates the code already in flight. Returns True (do NOT
        resend) when the answer is unknown, so a transient read failure can
        never trigger a destructive resend.
        """
        try:
            mail = getattr(self, "mail", None)
            if mail is None or mail.is_closed():
                return True  # unknown — never regenerate blindly
            res = mail.evaluate("""async () => {
                try {
                    const id = localStorage.getItem('tempmail_account_id') || '';
                    const token = localStorage.getItem('tempmail_token') || '';
                    if (!id || !token) return null;
                    const r = await fetch('/api/accounts/' + id + '/messages?page=1',
                        {headers: {Authorization: 'Bearer ' + token}});
                    if (!r.ok) return null;
                    const j = await r.json();
                    const msgs = (j && j.messages) || [];
                    return msgs.some(m => {
                        const blob = ((m.subject || '') + ' ' + (m.from || '') + ' ' + (m.sender || '')).toLowerCase();
                        return blob.indexOf('authenticate') !== -1;
                    });
                } catch (e) { return null; }
            }""")
            if res is None:
                return True  # unknown — don't resend
            return bool(res)
        except Exception:
            return True

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
                        if "emails from meta" in (opt.inner_text() or "").lower():
                            continue
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
                                       subject_hint="authenticate your profile|authenticate|security code|meta account code|instagram|security",
                                       prefer_len=None)
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
                # one resend per 5 minutes, and only when the inbox REST API
                # shows NO "Authenticate your profile" mail at all.
                #
                # The old test read the mail page's ``document.body.innerText``.
                # The mail.td LIST page carries no message body, so the phrase
                # "authenticate your profile" is almost never in that DOM — so
                # it re-sent on nearly every solve. Two sends ~10s apart were
                # observed live on the same challenge, and the resend is what
                # makes a just-fetched code fail with "This code doesn't work".
                import time as _time
                if _time.time() - getattr(self, "_ac_new_code_at", 0) < 300:
                    continue
                if self._ac_inbox_has_auth_mail():
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

        # Locate candidate code inputs (strictly targeting the active topmost dialog first)
        target_inps = []
        active_dlg = None
        try:
            for dlg_sel in (
                'div[role="dialog"]:has-text("Check your email")',
                'div[role="dialog"]:has-text("Two Step Verification")',
                'div[role="dialog"]',
            ):
                cand_dlg = p.locator(dlg_sel).last
                if cand_dlg.count() and cand_dlg.is_visible():
                    active_dlg = cand_dlg
                    break
        except Exception:
            pass

        if active_dlg is not None:
            try:
                for cand in active_dlg.locator('input:not([type="password"]):not([type="submit"]):not([type="checkbox"])').all():
                    if cand.is_visible():
                        target_inps.append(cand)
            except Exception:
                pass

        if not target_inps:
            try:
                for cand in p.get_by_label("Code", exact=True).all():
                    if cand.is_visible():
                        target_inps.append(cand)
            except Exception:
                pass

        if not target_inps:
            try:
                for cand in p.locator('label:has-text("Code") ~ input, div:has(> label:has-text("Code")) input:not([type="password"]), input:has(+ label:has-text("Code"))').all():
                    if cand.is_visible():
                        target_inps.append(cand)
            except Exception:
                pass

        if not target_inps:
            for tgt in targets:
                for sel in (
                    'input[placeholder*="Code" i]:not([type="password"])',
                    'input[aria-label*="Code" i]:not([type="password"])',
                    'input[name="code"]',
                    'input[name="verificationCode"]',
                    'input[name="confirmationCode"]',
                    'input[name="security_code"]',
                    'input[inputmode="numeric"]:not([type="password"])',
                    'input[autocomplete="one-time-code"]',
                ):
                    try:
                        for cand in tgt.locator(sel).all():
                            if cand.is_visible():
                                target_inps.append(cand)
                    except Exception:
                        pass
                if target_inps:
                    break

        if not target_inps:
            self.log('[⚠️] Could not find code input on "Check your email" dialog.')
            return False

        # Fill the code into candidate input elements (topmost/active dialog first)
        filled = False
        primary_inp = target_inps[-1]  # The latest/active input
        for inp in target_inps:
            try:
                inp.click(force=True, timeout=2000)
                p.wait_for_timeout(100)
                inp.fill("")
                p.wait_for_timeout(100)
                # Use sequential typing so React/Bloks native key listeners trigger state change
                inp.press_sequentially(str(code), delay=40)
                p.wait_for_timeout(200)
                if inp.input_value() != str(code):
                    inp.evaluate("""(el, val) => {
                        el.focus();
                        const proto = HTMLInputElement.prototype;
                        const d = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (d && d.set) { d.set.call(el, val); } else { el.value = val; }
                        const tracker = el._valueTracker;
                        if (tracker) { tracker.setValue(''); }
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }""", str(code))
                p.wait_for_timeout(200)
                filled = True
                self.log(f'[ac] filled security code into dialog input (val={inp.input_value()})')
            except Exception as exc:
                self.log(f'[⚠️] Error filling security code: {exc}')

        # Click submit / continue inside the active dialog
        clicked = False
        btn = None
        btn_containers = []
        if active_dlg is not None:
            btn_containers.append(active_dlg)
        btn_containers.extend(targets)

        for container in btn_containers:
            for sel in (
                'div[role="button"]:has-text("Continue")',
                'button:has-text("Continue")',
                '[role="button"]:has-text("Continue")',
                'div[role="button"]:has-text("Confirm")',
                'button:has-text("Confirm")',
                '[role="button"]:has-text("Confirm")',
                'div[role="button"]:has-text("Next")',
                'button:has-text("Next")',
            ):
                try:
                    cand = container.locator(sel).last
                    if cand.count() and cand.is_visible():
                        btn = cand
                        break
                except Exception:
                    continue
            if btn is not None:
                break

        if btn is not None:
            # Wait for button to become enabled (aria-disabled clears or is not true)
            for wait_i in range(16):
                if btn.get_attribute("aria-disabled") != "true" and not btn.is_disabled():
                    break
                p.wait_for_timeout(250)
                if wait_i in (4, 8):
                    for inp in target_inps:
                        try:
                            inp.evaluate("e => { e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur', {bubbles: true})); }")
                        except Exception:
                            pass

            try:
                if self._tap_or_click(p, btn, timeout=3000):
                    clicked = True
                    self.log('[ac] clicked Continue button on email security dialog')
            except Exception:
                pass

            if not clicked:
                try:
                    btn.click(force=True, timeout=3000)
                    clicked = True
                    self.log('[ac] force clicked Continue button')
                except Exception:
                    pass

            try:
                btn.evaluate("""el => {
                    el.removeAttribute('aria-disabled');
                    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, view: window}));
                    el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, view: window}));
                    el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                }""")
                clicked = True
            except Exception:
                pass

            try:
                primary_inp.press("Enter")
            except Exception:
                pass

        # Verify dialog actually closed / dismissed (wait up to 25s for Meta backend to verify and dismiss)
        dialog_closed = False
        for poll_i in range(50):
            p.wait_for_timeout(500)
            is_open = False
            try:
                cur = (p.inner_text("body") or "").lower()
                # If password was already updated, challenge is obsolete and completed!
                if any(m in cur for m in ("password updated", "password saved", "meta account password updated")):
                    self.log('[ac] Password confirmed updated during email challenge — dismissing dialog…')
                    try:
                        self._dismiss_contact_modal(p)
                    except Exception:
                        pass
                    return True

                if any(k in cur for k in ("enter the code we sent", "check your email", "enter code we sent")):
                    is_open = True
            except Exception:
                is_open = False
            if not is_open:
                dialog_closed = True
                p.wait_for_timeout(1000)
                break

            # If Meta rejected the code ("This code doesn't work"), request a fresh code and retry
            if "this code doesn't work" in cur or "try a new one" in cur:
                if poll_i in (2, 6):
                    self.log('[⚠️] Meta rejected email code ("This code doesn\'t work") — requesting fresh code…')
                    try:
                        gnc = p.locator('button:has-text("Get a new code"), [role="button"]:has-text("Get a new code"), a:has-text("Get a new code")').first
                        if gnc.count() and gnc.is_visible():
                            self._tap_or_click(p, gnc, timeout=2000)
                            p.wait_for_timeout(1500)
                            # Fetch new code
                            new_c = None
                            if callable(fetcher):
                                try:
                                    new_c = fetcher("instagram", timeout=25,
                                                    subject_hint="authenticate your profile|authenticate|security code|meta account code|instagram|security",
                                                    prefer_len=None)
                                except Exception:
                                    pass
                            if new_c and new_c != code:
                                self.log(f'[ac] Entering new code after rejection: {new_c}')
                                code = new_c
                                for inp in target_inps:
                                    try:
                                        inp.click(force=True, timeout=1000)
                                        inp.fill("")
                                        inp.press_sequentially(str(new_c), delay=40)
                                    except Exception:
                                        pass
                                if btn is not None:
                                    self._tap_or_click(p, btn, timeout=2000)
                                    primary_inp.press("Enter")
                    except Exception as exc:
                        self.log(f'[⚠️] Error recovering from rejected code: {exc}')

            # If dialog remains open after 3s and 7s, re-trigger submit
            elif poll_i in (6, 14) and btn is not None:
                try:
                    if btn.is_visible():
                        self.log('[ac] Re-triggering Continue button on email security dialog…')
                        self._tap_or_click(p, btn, timeout=2000)
                        btn.evaluate("el => el.click()")
                        primary_inp.press("Enter")
                except Exception:
                    pass

        self.log(f'[ac] email security challenge result: filled={filled}, clicked={clicked}, closed={dialog_closed}')
        return filled and dialog_closed

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
                self.log('[ac] Email security challenge solved and dismissed.')
                # Poll for the change-password form to appear
                for _ in range(12):
                    p.wait_for_timeout(250)
                    if (p.locator('input[type="password"]').count() >= 2
                            or p.get_by_text("Current password", exact=False).count() > 0):
                        break
                break

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
