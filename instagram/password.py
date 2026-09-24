"""Accounts Center navigation, re-auth, password provisioning & reset. Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides run._MetaInstagramRunner helpers."""
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
    """Accounts Center navigation, re-auth, password provisioning & reset."""

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

    def _ac_navigate_in_app(self, p, section_path: str = "/password_and_security/", label: str = "Password and security") -> bool:
        """Navigate naturally to Accounts Center using in-app UI clicks to avoid scraping warnings."""
        # 0. Check if current page or any open tab in context is already on Accounts Center
        try:
            for page in self.w.context.pages:
                if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                    self.insta_page = page
                    p = page
                    break
        except Exception:
            pass

        if "accountscenter.instagram.com" in (p.url or ""):
            cur_path = (p.url or "").split("?")[0].rstrip("/")
            clean_path = section_path.strip("/")
            if self._ac_in_section(cur_path, clean_path):
                self.log(f'[ac] Already within target section: {cur_path}')
                return True
            if "login_activity" in cur_path:
                self.log('[ac] Detected erroneous landing on login_activity; clicking back…')
                for back_sel in (
                    'svg[aria-label="Back"]',
                    '[aria-label="Back"]',
                    'button:has(svg[aria-label="Back"])',
                    'button[aria-label="Back"]',
                    'div[role="button"]:has(svg[aria-label="Back"])',
                ):
                    try:
                        b_el = p.locator(back_sel).first
                        if b_el.count() > 0 and b_el.is_visible():
                            self._tap_or_click(p, b_el)
                            p.wait_for_timeout(2500)
                            break
                    except Exception:
                        pass
                cur_path = (p.url or "").split("?")[0].rstrip("/")
                if self._ac_in_section(cur_path, clean_path):
                    return True

            labels = [label]
            if "password" in (section_path + label).lower():
                # NEW AC home label is "Login and security" (the old "Password
                # and security" only exists one level deeper). Try it FIRST so
                # we don't burn a click cycle + 3s on the dead label.
                labels = ["Login and security", "Password and security"]
            elif "two_factor" in section_path.lower():
                labels = ["Two-factor authentication", "Login and security", "Password and security"]
            elif "profiles" in section_path.lower():
                labels = ["Profiles"]
            elif "contact_points" in (section_path + label).lower() or "personal" in (section_path + label).lower():
                # The AC home entry is the PROFILE CARD ("Profiles and personal
                # details" / "<email> N profiles") → opens /profiles/, where the
                # "Contact info" row then opens the contact_points dialog.
                labels = ["Profiles and personal details", "Personal details",
                          "Contact info", "Contact details", "Profiles"]
            for lbl in labels:
                for sel in (
                    f'a[href*="{clean_path}"]',
                    f'a:has-text("{lbl}")',
                    f'[role="button"]:has-text("{lbl}")',
                    f'[role="link"]:has-text("{lbl}")',
                    f'button:has-text("{lbl}")',
                    f'[aria-label*="{lbl}" i]',
                ):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            self._tap_or_click(p, el)
                            p.wait_for_timeout(1200)
                            return True
                    except Exception:
                        pass
            return True

        self.log('[ac] Navigating to Accounts Center via in-app UI clicks (no URL jumps)…')
        self._dismiss_ig_sheets(p)
        # Pre-nav interstitial first: a scraping_warning / error screen makes
        # every Step tap fail loudly-but-slowly (observed 2026-09-19: ~2 min
        # burn per section call, TTL death). Dismiss it BEFORE tapping.
        try:
            if self._dismiss_scraping_warning(p):
                self.log('[ac] Scraping interstitial dismissed pre-nav; continuing…')
        except Exception:
            pass
        try:
            if self._recover_something_went_wrong(p, max_attempts=1):
                self.log('[ac] Error screen recovered pre-nav; continuing…')
        except Exception:
            pass
        # Session may have dropped mid-flow (login wall) — restore it with
        # owned creds before navigating anywhere. Fail FAST when dead: every
        # downstream tap burns TG TTL on a logged-out page (2026-09-19).
        try:
            if not self._ig_relogin_if_needed(p):
                self.log('[⚠️] AC entry failed: IG session dead, re-login failed.')
                return False
        except Exception as exc:
            self.log(f'[⚠️] AC entry failed: session check note: {exc}')
            return False

        # Check for "Connect to Facebook" page (media_1789674958994.png)
        try:
            b_txt = (p.inner_text("body") or "").lower()
            if "connect to facebook" in b_txt:
                self.log('[ac] On "Connect to Facebook" page — clicking Skip…')
                for sel in (
                    'div[role="button"]:has-text("Skip")',
                    'button:has-text("Skip")',
                    'a:has-text("Skip")',
                    'span:has-text("Skip")',
                    '[aria-label="Skip"]',
                    'div:text-is("Skip")',
                ):
                    s_el = p.locator(sel).first
                    if s_el.count() > 0 and s_el.is_visible():
                        self._tap_or_click(p, s_el)
                        p.wait_for_timeout(2000)
                        break
        except Exception:
            pass

        cur_url = p.url or ""
        # If not already on settings and not in Accounts Center:
        if "/accounts/settings" not in cur_url and "accountscenter.instagram.com" not in cur_url:
            user = getattr(self, "ig_username", None) or getattr(self, "username", None)
            is_on_profile = bool(user and f"/{user}/" in cur_url)

            # Step 1: Tap Profile icon in bottom navigation bar.
            # The feed ("Suggested for you") has no gear/AC links, so a
            # missed single tap strands the whole flow here. Retry the tap
            # (fresh locators — SPA staleness) and VERIFY the URL moved to
            # /{user}/ before continuing.
            if not is_on_profile:
                self.log('[ac] Step 1: Tapping Profile icon in bottom navigation bar…')
                self._human_pause()
                prof_selectors = []
                if user:
                    prof_selectors.extend([f'a[href*="/{user}/"]', f'a[href="/{user}/"]'])
                prof_selectors.extend([
                    '[aria-label="Profile"]',
                    'a[role="link"]:has(img[alt*="profile picture" i])',
                    'a:has([aria-label="Profile"])',
                    'nav a:last-child',
                    'footer a:last-child',
                ])
                navigated = False
                for _tap in range(3):
                    for sel in prof_selectors:
                        try:
                            el = p.locator(sel).first
                            if el.count() > 0 and el.is_visible():
                                self._tap_or_click(p, el)
                                break
                        except Exception:
                            pass
                    for _ in range(5):
                        p.wait_for_timeout(1000)
                        cur_url = p.url or ""
                        if (user and f"/{user}" in cur_url) or p.locator(
                                'a[href*="/accounts/settings/"], svg[aria-label="Options"], [aria-label="Options"]').count() > 0:
                            navigated = True
                            break
                    if navigated:
                        break
                    self.log(f'[ac] Step 1: profile tap {_tap + 1}/3 did not navigate — re-locating…')
                    try:
                        self._dismiss_ig_sheets(p)
                    except Exception:
                        pass
                if not navigated and user:
                    # Last resort: same-origin profile URL (low bot-score risk;
                    # direct ACENTER jumps are the dangerous ones, not IG pages).
                    self.log(f'[ac] Step 1: taps failed — last-resort goto profile /{user}/…')
                    try:
                        p.goto(f"https://www.instagram.com/{user}/", wait_until="domcontentloaded", timeout=30000)
                        p.wait_for_timeout(3000)
                    except Exception as exc:
                        self.log(f'[ac] Step 1 fallback note: {exc}')
                    # The fallback can land on a logged-out visitor view with a
                    # stray action sheet open (observed 2026-09-19: Block /
                    # Restrict / Cancel sheet) — clear it before gear hunting.
                    try:
                        self._dismiss_ig_sheets(p)
                    except Exception:
                        pass

                # Wait up to 10s for Profile page to load (recovering from "Something went wrong" if present)
                for _ in range(10):
                    p.wait_for_timeout(1000)
                    if self._recover_something_went_wrong(p, max_attempts=3):
                        self.log('[ac] Recovered profile page from "Something went wrong".')
                    cur_url = p.url or ""
                    if (user and f"/{user}" in cur_url) or p.locator('a[href*="/accounts/settings/"], svg[aria-label="Options"], [aria-label="Options"]').count() > 0:
                        break

            # Step 2: Tap Options/Settings gear icon at top of Profile page
            # (VERIFY arrival — observed 2026-09-19: a mis-tap on the logged-out
            # "⋯" opened Block/Restrict instead of Settings, and the flow
            # drifted into Step 3 on the wrong page for minutes).
            cur_url = p.url or ""
            if "/accounts/settings" not in cur_url:
                self.log('[ac] Step 2: Tapping Options/Settings gear icon on profile…')
                self._human_pause()
                settings_reached = self._ac_open_settings_from_profile(p)

                # Escalation (observed 2026-09-21 — ~40% of fresh accounts): the
                # gear is simply ABSENT from the profile DOM (half-rendered SPA
                # after the "Get the Instagram app" interstitial), so every tap
                # misses and Step 2 logs "did not open Settings". One reload
                # fixes a stale render; then a same-origin IG settings page (an
                # IG surface, NOT an ACENTER jump) as the last resort.
                if not settings_reached:
                    self.log('[🔄] Step 2: gear not found — reloading profile once (stale SPA render)…')
                    try:
                        p.reload(wait_until="domcontentloaded", timeout=30000)
                        for _ in range(8):
                            p.wait_for_timeout(1000)
                            if "/accounts/settings" in (p.url or "") or p.locator(
                                    'a[href*="/accounts/settings/"], svg[aria-label="Options"], [aria-label="Options"]').count() > 0:
                                break
                    except Exception as exc:
                        self.log(f'[ac] Step 2 reload note: {exc}')
                    settings_reached = self._ac_open_settings_from_profile(p)

                if not settings_reached:
                    self.log('[🔄] Step 2: gear unavailable — opening IG /accounts/settings/ directly…')
                    try:
                        p.goto("https://www.instagram.com/accounts/settings/",
                               wait_until="domcontentloaded", timeout=30000)
                        for _ in range(8):
                            p.wait_for_timeout(1000)
                            cur_url = p.url or ""
                            if "/accounts/settings" in cur_url or p.locator(
                                    'a[href*="accountscenter"], [aria-label*="Accounts Center" i]').count() > 0:
                                settings_reached = True
                                break
                    except Exception as exc:
                        self.log(f'[ac] Step 2 direct-settings note: {exc}')

                if not settings_reached:
                    self.log(f'[⚠️] AC entry failed: Settings never opened (at {cur_url[:80]})')
                    return False

        # Step 3: Tap Accounts Center link/card in settings (VERIFY arrival —
        # observed 2026-09-19: the tap was absorbed by a dead settings page
        # and the flow burned 25s+ waiting on the profile page).
        cur_url = p.url or ""
        if "accountscenter.instagram.com" not in cur_url:
            self.log('[ac] Step 3: Tapping Accounts Center / Meta Account link in settings…')
            self._human_pause()
            ac_card_selectors = (
                'a[href*="accountscenter.instagram.com"]',
                'a:has-text("Meta Account")',
                'div[role="button"]:has-text("Meta Account")',
                'div[role="link"]:has-text("Meta Account")',
                'a:has-text("Accounts Center")',
                'div[role="button"]:has-text("Accounts Center")',
                '[aria-label*="Accounts Center" i]',
                '[aria-label*="Meta Account" i]',
            )
            ac_reached = False
            for _ac in range(3):
                clicked_ac = False
                for _ in range(4):
                    for sel in ac_card_selectors:
                        try:
                            el = p.locator(sel).first
                            if el.count() > 0 and el.is_visible():
                                self._tap_or_click(p, el)
                                clicked_ac = True
                                break
                        except Exception:
                            pass
                    if clicked_ac:
                        break
                    p.wait_for_timeout(1000)
                # VERIFY: AC may open in a new tab — scan context pages.
                for _ in range(5):
                    for page in self.w.context.pages:
                        if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                            self.insta_page = page
                            p = page
                            break
                    if "accountscenter.instagram.com" in (p.url or ""):
                        ac_reached = True
                        break
                    p.wait_for_timeout(1000)
                if ac_reached:
                    break
                self.log(f'[ac] Step 3: AC tap {_ac + 1}/3 did not navigate — re-locating…')
                try:
                    self._dismiss_ig_sheets(p)
                except Exception:
                    pass
            if not ac_reached:
                self.log(f'[⚠️] AC entry failed: Accounts Center never opened (at {(p.url or "")[:80]})')
                return False

        # Wait up to 15s for Accounts Center to load on current page or in a newly opened tab
        for _ in range(15):
            for page in self.w.context.pages:
                if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                    self.insta_page = page
                    p = page
                    break
            if "accountscenter.instagram.com" in (p.url or ""):
                break
            p.wait_for_timeout(1000)

        # Check for one-tap "Continue as"
        try:
            for sel in ('button:has-text("Continue as")', 'div[role="button"]:has-text("Continue as")'):
                btn = p.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn_text = (btn.inner_text() or "").lower()
                    page_text = (p.inner_text("body") or "").lower()
                    if "facebook" in btn_text or "facebook" in page_text:
                        self.log('[ac] "Continue as" is a Facebook prompt — skipping…')
                        for skip_sel in ('button:has-text("Skip")', 'div[role="button"]:has-text("Skip")', 'a:has-text("Skip")', 'span:has-text("Skip")'):
                            s_el = p.locator(skip_sel).first
                            if s_el.count() > 0 and s_el.is_visible():
                                self._tap_or_click(p, s_el)
                                p.wait_for_timeout(2000)
                                break
                        continue
                    self._tap_or_click(p, btn)
                    # Poll for the AC section list instead of a blind 3.5s: exit
                    # as soon as the rows render ("Login and security" etc.).
                    for _ in range(14):
                        p.wait_for_timeout(250)
                        try:
                            if ("accountscenter.instagram.com" in (p.url or "")
                                    and (p.get_by_text("Login and security", exact=False).count() > 0
                                         or p.get_by_text("Password and security", exact=False).count() > 0
                                         or p.get_by_text("Personal details", exact=False).count() > 0
                                         or p.get_by_text("Two-factor authentication", exact=False).count() > 0)):
                                break
                        except Exception:
                            pass
                    break
        except Exception:
            pass

        # Step 4: Click the target section inside Accounts Center (e.g. Password and security)
        if "accountscenter.instagram.com" in (p.url or ""):
            clean_path = section_path.strip("/")
            cur_path = (p.url or "").split("?")[0].rstrip("/")
            if self._ac_in_section(cur_path, clean_path):
                self.log(f'[ac] Already at target section: {cur_path}')
                return True

            labels = [label]
            if "password" in (section_path + label).lower():
                # NEW AC home label is "Login and security" (the old "Password
                # and security" only exists one level deeper). Try it FIRST so
                # we don't burn a click cycle + 3s on the dead label.
                labels = ["Login and security", "Password and security"]
            elif "two_factor" in section_path.lower():
                labels = ["Two-factor authentication", "Login and security", "Password and security"]
            elif "profiles" in section_path.lower():
                labels = ["Profiles"]
            elif "contact_points" in (section_path + label).lower() or "personal" in (section_path + label).lower():
                # The AC home entry is the PROFILE CARD ("Profiles and personal
                # details" / "<email> N profiles") → opens /profiles/, where the
                # "Contact info" row then opens the contact_points dialog.
                labels = ["Profiles and personal details", "Personal details",
                          "Contact info", "Contact details", "Profiles"]

            for _ in range(15):
                cur_path = (p.url or "").split("?")[0].rstrip("/")
                if self._ac_in_section(cur_path, clean_path):
                    self.log(f'[ac] Successfully reached target section: {cur_path}')
                    return True
                if "login_activity" in cur_path:
                    self.log('[ac] Detected erroneous landing on login_activity; clicking back…')
                    for back_sel in ('svg[aria-label="Back"]', '[aria-label="Back"]', 'button[aria-label="Back"]'):
                        try:
                            b_el = p.locator(back_sel).first
                            if b_el.count() > 0 and b_el.is_visible():
                                self._tap_or_click(p, b_el)
                                p.wait_for_timeout(2000)
                                break
                        except Exception:
                            pass
                    continue

                clicked_sec = False
                for lbl in labels:
                    for sel in (
                        f'a[href*="{clean_path}"]',
                        f'a:has-text("{lbl}")',
                        f'[role="button"]:has-text("{lbl}")',
                        f'[role="link"]:has-text("{lbl}")',
                        f'button:has-text("{lbl}")',
                        f'[aria-label*="{lbl}" i]',
                    ):
                        try:
                            el = p.locator(sel).first
                            if el.count() > 0 and el.is_visible():
                                self._tap_or_click(p, el)
                                p.wait_for_timeout(1200)
                                clicked_sec = True
                                break
                        except Exception:
                            pass
                    if clicked_sec:
                        break
                if not clicked_sec:
                    # AC root may be showing a dead/transient screen ("no
                    # longer available") with no section links to tap —
                    # recover it instead of spinning 15 identical misses.
                    try:
                        self._dismiss_scraping_warning(p)
                    except Exception:
                        pass
                    try:
                        if self._recover_something_went_wrong(p, max_attempts=1):
                            self.log('[ac] Step 4: recovered transient AC screen, re-locating…')
                    except Exception:
                        pass
                p.wait_for_timeout(500)

            cur_path = (p.url or "").split("?")[0].rstrip("/")
            if self._ac_in_section(cur_path, clean_path):
                return True
            return False

        return False

    # Accounts Center serves the SAME section under several path prefixes.
    # `personal_info/contact_points` is the canonical path callers ask for, but
    # the live app reports `youraccount/contact_points` OR
    # `account_overview/contact_points`. A missing alias made a reached page look
    # "AC section unreachable" — the extra-email step then failed silently and
    # the account was submitted with no email (Taskly rejected it).
    _AC_PATH_ALIASES = (
        "/youraccount/contact_points",
        "/account_overview/personal_info/contact_points",
        "/account_overview/contact_points",
    )

    @staticmethod
    def _ac_norm_path(path: str) -> str:
        """Normalize an AC URL path so every alias of a section compares equal."""
        cur = (path or "").rstrip("/")
        for alias in IgPasswordMixin._AC_PATH_ALIASES:
            cur = cur.replace(alias, "/personal_info/contact_points")
        return cur

    @staticmethod
    def _ac_in_section(cur_path: str, clean_path: str) -> bool:
        """True when we are already inside the target AC section (including a
        sub-page like /password_and_security/password/change/). This is what lets
        name+username share ONE /profiles/ visit and password+2FA share ONE
        /password_and_security/ visit instead of 4 separate AC navigations."""
        cp = (clean_path or "").strip("/")
        if not cp:
            return False
        cur = IgPasswordMixin._ac_norm_path(cur_path)
        return cur.endswith("/" + cp) or ("/" + cp + "/") in (cur + "/")

    # AC home section titles, verified live 2026-09-19 on
    # accountscenter.instagram.com ("Profiles and personal details", "Password
    # and security", "Connected experiences", …). An overlay such as Contact
    # information shows only its own header ("Profiles and personal details")
    # plus its own rows, so a single-title match is NOT enough — require >= 2.
    _AC_SECTION_TITLES = (
        "Profiles and personal details", "Password and security",
        "Login and security", "Connected experiences",
        "Your information and permissions", "Ad preferences",
        "Meta Pay", "Manage accounts", "Two-factor authentication",
    )

    def _ac_section_list_visible(self, p) -> bool:
        """True when the Accounts Center home section list is on screen.

        A section opened as an overlay/dialog shows only one shared header, so
        it must not be mistaken for home (that false positive made the first
        version of ``_ac_leave_subpage`` return True without closing anything).
        """
        seen = 0
        for lbl in self._AC_SECTION_TITLES:
            try:
                loc = p.get_by_text(lbl, exact=False).first
                # MUST check visibility: the AC home rows stay in the DOM
                # behind an overlay, and count() alone matches those hidden
                # rows (that false positive made this return True without
                # closing anything).
                if loc.count() > 0 and loc.is_visible():
                    seen += 1
                    if seen >= 2:
                        return True
            except Exception:
                pass
        return False

    def _ac_leave_subpage(self, p, tries: int = 3) -> bool:
        """Return from an AC dialog/sub-page to the AC home section list.

        A section can be left open as an overlay (``?is_from_dialog=true``,
        e.g. Contact information opened from the profile gear). Its X/Back must
        be tapped BEFORE the AC home rows exist; searching for the next
        section's link while the dialog is still up always misses and then
        hard-fails with "AC section unreachable" (observed 2026-09-19: the
        email step left Contact info open, the password step wedged on it).
        """
        for _ in range(max(1, tries)):
            if self._ac_section_list_visible(p):
                return True
            clicked = False
            for sel in (
                '[aria-label="Close"]', 'button[aria-label="Close"]',
                'div[role="button"][aria-label="Close"]',
                'svg[aria-label="Close"]', '[aria-label*="Close" i]',
                '[aria-label="Back"]', 'button[aria-label="Back"]',
                'button:has(svg[aria-label="Back"])', 'svg[aria-label="Back"]',
                'div[role="button"]:has(svg[aria-label="Back"])',
                'svg[aria-label*="Back" i]',
            ):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        self._tap_or_click(p, el)
                        p.wait_for_timeout(1200)
                        clicked = True
                        break
                except Exception:
                    pass
            if not clicked:
                return False
        return self._ac_section_list_visible(p)

    def _ac_open_contact_points(self, p=None) -> bool:
        """Open Accounts Center → Contact info/points via the REAL in-app path.

        Verified live via MCP 2026-09-20 (fresh account s578dq@nqmo.com): the AC
        home has **no direct "Contact info" row** — you go through the profile
        card:

            AC home → profile card (`account_overview`) → "Default contact info"
            (the email button) → `/account_overview/contact_points/`
            → "Add or edit contact info" → "Contact info" dialog.

        The old `_ac_section("/personal_info/contact_points/")` searched the AC
        home for a section row that does not exist → false "AC section
        unreachable" (the extra-email step then failed and the task was burned).
        """
        p = p or self._ig_tab()
        cur = (p.url or "").split("?")[0].rstrip("/")
        if "contact_points" in cur:
            return True
        # 0. Return to the AC home list FIRST. After the password change the
        # page sits on /password_and_security/ (and 2FA on /two_factor/), which
        # has NO account_overview/profile-card link — clicking the card there
        # always misses and the email step never starts (observed live
        # 2026-09-20: stuck on Login and security → task cancelled).
        if "account_overview" not in cur:
            try:
                self._ac_leave_subpage(p)
                p.wait_for_timeout(1200)
                p = self._ig_tab()
            except Exception:
                pass
        # 1. AC home -> profile card (account_overview).
        if "account_overview" not in cur:
            for sel in ('a[href*="/account_overview/"]', 'a[href*="/profiles/"]'):
                try:
                    el = p.locator(sel).first
                    if el.count() and el.is_visible():
                        self._tap_or_click(p, el)
                        p.wait_for_timeout(2500)
                        break
                except Exception:
                    pass
        # 2. account_overview -> "Default contact info" (email button) -> contact_points.
        if "contact_points" not in (p.url or ""):
            for sel in (
                'a[href*="contact_points"]',
                'button:has-text("@")',
                'div[role="button"]:has-text("@")',
            ):
                try:
                    el = p.locator(sel).first
                    if el.count() and el.is_visible():
                        self._tap_or_click(p, el)
                        p.wait_for_timeout(2500)
                        break
                except Exception:
                    pass
        cur = (p.url or "").split("?")[0].rstrip("/")
        ok = "contact_points" in cur
        self.log(f'[ac] contact points open: {ok} ({cur[:90]})')
        return ok

    def _ac_open_settings_from_profile(self, p) -> bool:
        """Tap the profile settings gear and VERIFY Settings opened.

        Escalating tries: CSS selectors → non-destructive sheet dismissal →
        a raw DOM scan (`_ac_gear_js_probe`, which also logs a probe so a miss
        is diagnosable). Returns True once Settings (or an Accounts Center
        link) is reachable. Extracted from `_ac_navigate_in_app` so the reload /
        direct-page escalation can reuse it unchanged.
        """
        gear_selectors = (
            'a[href*="/accounts/settings/?entrypoint=profile"]',
            'a[href*="/accounts/settings/"]',
            'header a[href*="settings"]',
            'a[href*="accounts/settings"]',
            'a:has(svg[aria-label="Options"])',
            'svg[aria-label="Options"]',
            'button:has(svg[aria-label="Options"])',
            'button[aria-label="Options"]',
            '[aria-label="Options"]',
            '[aria-label="Settings"]',
            '[aria-label*="options" i]',
            '[aria-label*="settings" i]',
        )
        for _gear in range(3):
            clicked_gear = False
            for _ in range(4):
                for sel in gear_selectors:
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            self._tap_or_click(p, el)
                            clicked_gear = True
                            break
                    except Exception:
                        pass
                if clicked_gear:
                    break
                # Dismiss any sheet or dialog blocking the header (non-destructive).
                try:
                    self._dismiss_ig_sheets(p)
                except Exception:
                    pass
                p.wait_for_timeout(1000)
            # JS DOM scan when no CSS selector matched (also logs a probe).
            if not clicked_gear:
                clicked_gear = self._ac_gear_js_probe(p)
            # VERIFY the tap actually opened Settings (not a ⋯ sheet).
            for _ in range(5):
                p.wait_for_timeout(1000)
                cur_url = p.url or ""
                if "/accounts/settings" in cur_url or p.locator(
                        'a[href*="accountscenter"], [aria-label*="Accounts Center" i]').count() > 0:
                    return True
            self.log(f'[ac] Step 2: gear tap {_gear + 1}/3 did not open Settings — re-locating…')
            try:
                self._dismiss_ig_sheets(p)
            except Exception:
                pass
        return False

    def _ac_gear_js_probe(self, p) -> bool:
        """Find the profile settings gear via a raw DOM scan, and log a probe.

        Diagnostic + self-heal for the 2026-09-21 finding: on ~40% of fresh
        accounts the gear is absent from the rendered profile DOM (half-rendered
        SPA after the "Get the Instagram app" interstitial), so every locator
        misses and AC entry dies as "settings never opened". The probe logs what
        the header actually contains so the next miss is explainable.
        """
        try:
            res = p.evaluate(r"""() => {
                const out = {hrefs: [], labels: [], viewport: [innerWidth, innerHeight],
                             tapped: null, topRight: null,
                             hasHeader: !!document.querySelector('header')};
                document.querySelectorAll('a[href]').forEach(a => {
                    const h = a.getAttribute('href') || '';
                    if (h.includes('settings') || h.includes('accounts')) out.hrefs.push(h);
                });
                document.querySelectorAll('[aria-label]').forEach(e => {
                    const l = e.getAttribute('aria-label') || '';
                    if (/option|setting|menu|more|gear/i.test(l)) out.labels.push(l);
                });
                const a = document.querySelector('a[href*="accounts/settings"]');
                if (a) { a.click(); out.tapped = 'anchor'; return out; }
                for (const e of document.querySelectorAll('[aria-label]')) {
                    const l = (e.getAttribute('aria-label') || '').trim();
                    if (/^(options|settings)$/i.test(l)) {
                        (e.querySelector('svg') || e).click();
                        out.tapped = 'label:' + l; return out;
                    }
                }
                let best = null, bestX = -1;
                document.querySelectorAll('header a, header button, header [role="button"], header svg').forEach(e => {
                    const r = e.getBoundingClientRect();
                    if (r.top < 200 && r.width > 0 && r.height > 0 && r.left > bestX) {
                        bestX = r.left; best = e;
                    }
                });
                if (best) {
                    const r = best.getBoundingClientRect();
                    out.topRight = [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
                    best.click();
                    out.tapped = 'topright';
                }
                return out;
            }""")
            try:
                self.log(
                    f"[ac] Step 2 probe: header={res.get('hasHeader')} "
                    f"vp={res.get('viewport')} labels={res.get('labels')[:6]} "
                    f"hrefs={res.get('hrefs')[:6]} topRight={res.get('topRight')} "
                    f"tapped={res.get('tapped')}")
            except Exception:
                pass
            return bool(res.get("tapped"))
        except Exception as exc:
            self.log(f"[ac] Step 2 probe note: {exc}")
            return False

    def _ac_section(self, section_path: str = "/password_and_security/", label: str = "Password and security"):
        """Open Accounts Center reliably and navigate to a target section strictly via in-app UI clicks (no jumping)."""
        p = self._ig_tab()

        # Risky-contact-point gate up-front: DEAD END — abort BEFORE navigating,
        # never click "Update email address" (operator decision 2026-09-21).
        if self._is_email_risky_screen(p):
            raise IGDeadEnd(
                "IG email risky contact point (email_risky_contactpoint) — closing")

        # 0. Check if already in Accounts Center across any open tab
        for page in self.w.context.pages:
            if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                self.insta_page = page
                p = page
                break

        # If not in Accounts Center, navigate via in-app UI clicks (Profile -> Gear -> Accounts Center)
        if "accountscenter.instagram.com" not in (p.url or ""):
            self._recover_something_went_wrong(p, max_attempts=2)
            try:
                self._ac_navigate_in_app(p, section_path=section_path, label=label)
            except Exception as exc:
                self.log(f'[ac] in-app navigation note: {exc}')

        # Double check pages in case Accounts Center opened in new tab
        for page in self.w.context.pages:
            if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                self.insta_page = page
                p = page
                break

        # Risky-contact-point gate: IG demands a DIFFERENT email before settings/
        # AC will load (no Skip). Operator decision 2026-09-21: this is a DEAD
        # END — CLOSE the browser and move to the next account. Do NOT click
        # "Update email address" (it just hangs on the next screen).
        if self._is_email_risky_screen(p):
            raise IGDeadEnd(
                "IG email risky contact point (email_risky_contactpoint) — closing")

        # Dead-end guard: an IG login wall / saved-account chooser here means the
        # session was dropped. We own the creds, so try a bounded re-login first
        # (observed 2026-09-21: a Reload on the AC route landed on the chooser and
        # the run dead-ended); only dead-end if the re-login cannot restore it.
        if "/accounts/login" in (p.url or "") or self._is_ig_dead_end_chooser(p):
            if self._chooser_relogin(p):
                self.log('[✔] Recovered AC session via re-login — continuing.')
                p = self._ig_tab()
            else:
                raise IGDeadEnd(
                    f"IG login wall during Accounts Center navigation ({(p.url or '')[:90]})")

        # 1. One-tap interstitial ("Continue as <user>") if present
        try:
            _tail1 = (p.inner_text("body") or "")
        except Exception:
            _tail1 = ""
        if "Continue as" in _tail1 and "accountscenter.instagram.com" not in (p.url or ""):
            if "facebook" in _tail1.lower():
                self.log('[ac] "Continue as" is a Facebook prompt — skipping…')
                for skip_sel in ('button:has-text("Skip")', 'div[role="button"]:has-text("Skip")', 'a:has-text("Skip")', 'span:has-text("Skip")'):
                    try:
                        s_el = p.locator(skip_sel).first
                        if s_el.count() > 0 and s_el.is_visible():
                            self._tap_or_click(p, s_el)
                            p.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass
            else:
                for _sel in ('button:has-text("Continue as")', 'div[role="button"]:has-text("Continue as")'):
                    try:
                        _cb = p.locator(_sel).first
                        if _cb.count() > 0 and _cb.is_visible():
                            _cb.click(force=True, timeout=4000)
                            self.log('[ac] tapped one-tap "Continue as".')
                            p.wait_for_timeout(4000)
                            break
                    except Exception:
                        pass

        # 2. Go to the target section inside Accounts Center via UI click
        p = self._ig_tab()
        if "accountscenter.instagram.com" in (p.url or ""):
            cur_path = (p.url or "").split("?")[0].rstrip("/")
            clean_path = section_path.strip("/")
            if self._ac_in_section(cur_path, clean_path):
                # Already inside the section. If we're on a sub-page (e.g.
                # /password_and_security/password/change/ after a password
                # change), step Back once so the section list is visible for the
                # next step (2FA entry) — this is what lets password+2FA share
                # ONE AC navigation instead of two.
                # Only step Back when on a SUB-page of the section (e.g.
                # /password_and_security/password/change). Comparing the full
                # URL to the bare path fragment made this ALWAYS true, so it
                # clicked Back even from the section root and dropped to the AC
                # home after every password change — forcing ig_2fa_begin into a
                # full home -> Login-and-security -> 2FA re-navigation
                # (observed 2026-09-19: "2FA bounced out" x2, ~50s wasted).
                if not self._ac_norm_path(cur_path).endswith("/" + clean_path):
                    try:
                        for b_sel in ('[aria-label="Back"]', 'button:has(svg[aria-label="Back"])', 'button[aria-label="Back"]'):
                            b_el = p.locator(b_sel).first
                            if b_el.count() > 0 and b_el.is_visible():
                                self._tap_or_click(p, b_el)
                                p.wait_for_timeout(1500)
                                break
                    except Exception:
                        pass
                self.log(f'[ac] Already within target section: {cur_path}')
            else:
                # Not in the target section. A previous section may be left
                # open as an overlay (e.g. Contact information, ?is_from_dialog
                # =true). Close/back it to the AC home section list BEFORE
                # hunting for this section's row — a stale modal has no such
                # row, so every tap misses and we hard-fail "AC section
                # unreachable" (observed 2026-09-19).
                if self._ac_leave_subpage(p):
                    cur_path = (p.url or "").split("?")[0].rstrip("/")
                if "login_activity" in cur_path:
                    self.log('[ac] Detected erroneous landing on login_activity; clicking back…')
                    for back_sel in (
                        'svg[aria-label="Back"]',
                        '[aria-label="Back"]',
                        'button:has(svg[aria-label="Back"])',
                        'button[aria-label="Back"]',
                        'div[role="button"]:has(svg[aria-label="Back"])',
                    ):
                        try:
                            b_el = p.locator(back_sel).first
                            if b_el.count() > 0 and b_el.is_visible():
                                self._tap_or_click(p, b_el)
                                p.wait_for_timeout(2500)
                                break
                        except Exception:
                            pass
                    cur_path = (p.url or "").split("?")[0].rstrip("/")

                if not self._ac_in_section(cur_path, clean_path):
                    labels = [label]
                    if "password" in (section_path + label).lower():
                        labels.extend(["Login and security", "Password and security"])
                    elif "two_factor" in section_path.lower():
                        labels.extend(["Two-factor authentication", "Password and security", "Login and security"])
                    elif "profiles" in section_path.lower():
                        labels.extend(["Profiles"])
                    elif "contact_points" in (section_path + label).lower() or "personal" in (section_path + label).lower():
                        labels.extend(["Profiles and personal details", "Personal details",
                                       "Contact info", "Contact details", "Profiles"])
                    for _nav in range(2):
                        for lbl in labels:
                            for sel in (
                                f'a[href*="{clean_path}"]',
                                f'a:has-text("{lbl}")',
                                f'[role="button"]:has-text("{lbl}")',
                                f'[role="link"]:has-text("{lbl}")',
                                f'button:has-text("{lbl}")',
                                f'[aria-label*="{lbl}" i]',
                            ):
                                try:
                                    el = p.locator(sel).first
                                    if el.count() > 0 and el.is_visible():
                                        self._tap_or_click(p, el)
                                        p.wait_for_timeout(1200)
                                        break
                                except Exception:
                                    pass
                        # VERIFY the click actually navigated (AC root links
                        # hydrate lazily; a blind click often lands nowhere).
                        reached = False
                        for _ in range(16):
                            p.wait_for_timeout(500)
                            try:
                                cur_path = (p.url or "").split("?")[0].rstrip("/")
                            except Exception:
                                continue
                            if self._ac_in_section(cur_path, clean_path):
                                reached = True
                                break
                        if reached:
                            break
                        self.log(f'[ac] Section tap {_nav + 1}/2 missed "{clean_path}" (still at {cur_path[:80]}) — re-locating…')
                        # Live 2026-09-19: AC root can render "content no longer
                        # available" — re-tapping the same dead DOM never works.
                        # Recover the transient screen before the next tap.
                        try:
                            self._dismiss_scraping_warning(p)
                        except Exception:
                            pass
                        try:
                            self._recover_something_went_wrong(p, max_attempts=1)
                        except Exception:
                            pass
                    cur_path = (p.url or "").split("?")[0].rstrip("/")
                    if not self._ac_in_section(cur_path, clean_path):
                        # One Way-Out + clean re-entry before failing loud (the
                        # dead AC root sometimes revives after an escape).
                        try:
                            if self._way_out_escape(p):
                                self._ac_navigate_in_app(p, section_path=section_path, label=label)
                                for page in self.w.context.pages:
                                    if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                                        self.insta_page = page
                                        p = page
                                        break
                                cur_path = (p.url or "").split("?")[0].rstrip("/")
                                if self._ac_in_section(cur_path, clean_path):
                                    self.log(f'[ac] section "{label}" recovered via Way Out -> {p.url[:90]}')
                                else:
                                    raise RuntimeError(
                                        f"AC section unreachable: want {clean_path}, at {p.url} | {self._page_tail(p)}")
                            else:
                                raise RuntimeError(
                                    f"AC section unreachable: want {clean_path}, at {p.url} | {self._page_tail(p)}")
                        except RuntimeError:
                            raise
                        except Exception as exc:
                            raise RuntimeError(
                                f"AC section unreachable: want {clean_path}, at {p.url} | {self._page_tail(p)}") from exc
        else:
            # Guide "Way Out": in-app navigation failed — do NOT reload and
            # hammer the same failing route (escalates bot scoring). Escape to
            # a clean root, cool down, then re-enter via Settings clicks.
            self.log('[🚪] Way Out: AC entry failed — escaping to clean root before re-entering…')
            try:
                self._way_out_escape(p)
                self._ac_navigate_in_app(p, section_path=section_path, label=label)
                for page in self.w.context.pages:
                    if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                        self.insta_page = page
                        p = page
                        break
            except Exception as exc:
                self.log(f'[ac] Way Out re-entry note: {exc}')

        p = self._ig_tab()
        # Skip the guard trio when we are ALREADY inside the target section
        # (batched calls: name+username share /profiles/, password+2FA share
        # /password_and_security/). The caller runs its own reauth/recovery, so
        # re-running them here on an already-clean AC page was pure duplication.
        _cur = (p.url or "").split("?")[0].rstrip("/")
        _already = ("accountscenter.instagram.com" in (p.url or "")
                    and self._ac_in_section(_cur, section_path.strip("/")))
        if not _already:
            self._dismiss_scraping_warning(p)
            self._require_ig_rendered(p, f'Accounts Center "{label}"')
            self._ac_reauth(p)
        else:
            self.log(f'[ac] "{label}" already in section — skipping guard trio.')
        self.log(f'[ac] section "{label}" -> {p.url[:90]}')
        if "accountscenter.instagram.com" not in (p.url or ""):
            # Attribute the failure precisely: the panel lumped session loss
            # under "Accounts Center unreachable" (69× on 2026-09-21). A missing
            # sessionid means IG dropped the fresh account's session (the
            # fresh-account login wall) — a DEAD END, not a navigation bug.
            _dead = False
            try:
                _names = self._ig_cookie_names()
                # Only a NON-EMPTY cookie jar missing sessionid proves the session
                # dropped; an empty list can just be a failed query.
                _dead = bool(_names) and "sessionid" not in _names
            except Exception:
                pass
            if _dead:
                self.log('[⚠️] Could not reach Accounts Center — IG session dropped (ig login wall)')
                raise IGDeadEnd(
                    f"IG login wall (ig login wall) — session dropped (ended up at {p.url})")
            self.log(f'[⚠️] Could not reach Accounts Center (ended up at {p.url})')
            raise RuntimeError(f"Could not reach Accounts Center via in-app navigation (ended up at {p.url})")
        return p

    def _ac_open(self, url: str, marker_texts: List[str], timeout: int = 25000) -> bool:
        """Open an Accounts Center URL with session handshake and marker text validation."""
        p = self._ig_tab()
        path = ""
        if Urls.AC_BASE in url:
            path = url.replace(Urls.AC_BASE, "")
        label = marker_texts[0] if marker_texts else "Accounts Center"
        if path:
            try:
                if self._ac_navigate_in_app(p, section_path=path, label=label):
                    return True
            except Exception:
                pass

        p = self._ig_tab()
        if "accountscenter.instagram.com" not in (p.url or ""):
            try:
                self._recover_something_went_wrong(p, max_attempts=1)
                # Guide: no in-place reload hammering — escape, then re-enter.
                self._way_out_escape(p)
                self._ac_navigate_in_app(p, section_path=path, label=label)
                for page in self.w.context.pages:
                    if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                        self.insta_page = page
                        p = page
                        break
            except Exception as exc:  # noqa: BLE001
                self.log(f'[ac] entry error: {exc}')

        if "accountscenter.instagram.com" not in (p.url or ""):
            self.log(f'[ac] ⚠️ Accounts Center could not be opened via in-app UI for {url[:60]}')
            return False
        self.log(f'[ac] target url={p.url[:90]}')
        end = time.time() + timeout / 1000
        way_out_done = False
        while time.time() < end:
            try:
                low_all = (p.inner_text("body") or "").lower()
            except Exception:
                low_all = ""
            is_trap = (
                "we suspect automated behavior" in low_all
                or "scraping_warning" in (p.url or "")
                or "no longer available" in low_all
                or "isn't available right now" in low_all
                or "something went wrong" in low_all
            )
            if is_trap:
                if not way_out_done:
                    # Guide: dismiss once/close modal, then escape + cool down — never
                    # sit in a retry loop on the challenged or broken route.
                    self._dismiss_scraping_warning(p)
                    self._way_out_escape(p)
                    way_out_done = True
                    continue
                self.log('[⚠️] Error / challenge screen persists after Way Out — backing off.')
                return False
            if "accounts/login" in (p.url or "") and "next=" in (p.url or ""):
                for sel in (
                    'div[role="button"]:has-text("Continue")',
                    '[aria-label="Continue"]',
                    'button:has-text("Continue")',
                ):
                    try:
                        btn = p.locator(sel).first
                        if btn.count() and btn.is_visible():
                            self.log(f'[ac] SSO handoff detected; tapping "{sel}"…')
                            self._tap_or_click(p, btn, timeout=3000)
                            p.wait_for_timeout(4000)
                            break
                    except Exception:
                        pass
            for t in marker_texts:
                try:
                    if p.get_by_text(t, exact=False).first.is_visible():
                        return True
                except Exception:
                    pass
            p.wait_for_timeout(1200)
        return False

    def _ac_choose_account(self, p, prefer_instagram: bool = True) -> bool:
        """Choose account row in Accounts Center (Instagram <user> vs Meta <name>)."""
        ig_name = self.ig_username or self.username
        candidates = []
        if prefer_instagram and ig_name:
            candidates.extend([
                f"{ig_name} Instagram",
                f"{ig_name}, Instagram",
                f"{ig_name} · Instagram",
                ig_name,
            ])
        if not prefer_instagram and self.name:
            candidates.extend([
                f"{self.name} · Meta",
                f"{self.name}, Meta",
                f"{self.name} Meta",
                self.name,
                "Meta",
            ])
        for name in candidates:
            if self._try_click(p, name, timeout=4000) or self._try_click(p, name, role="button", timeout=3000):
                self.log(f'[ac] chose account row: "{name}"')
                p.wait_for_timeout(3000)
                return True
        if prefer_instagram:
            try:
                el = p.locator('div[role="button"]:has-text("Instagram"), button:has-text("Instagram")').first
                if el.is_visible():
                    if not self._tap_or_click(p, el):
                        self._human_click(p, el, 5000)
                    self.log('[ac] chose Instagram account row (has-text fallback)')
                    p.wait_for_timeout(3000)
                    return True
            except Exception:
                pass
        else:
            try:
                el = p.locator('div[role="button"]:has-text("Meta"), button:has-text("Meta")').first
                if el.is_visible():
                    if not self._tap_or_click(p, el):
                        self._human_click(p, el, 5000)
                    self.log('[ac] chose Meta account row (has-text fallback)')
                    p.wait_for_timeout(3000)
                    return True
            except Exception:
                pass
        return False

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
        # Headless ALWAYS: this is a background reset step. A headed launch here
        # opened a second visible Chrome window that did nothing for the user
        # (seen on Windows headed runs, never on headless Ubuntu).
        # Reuse the bundled Chromium + the standard flags so this second browser
        # never shows the "Chrome for Testing" infobar or the "Restore pages?"
        # crash bubble either.
        _reset_kw = {"headless": True}
        _nova_flags = []
        try:
            from eng_constants import _NOVA_FLAGS as _nova_flags  # type: ignore
        except Exception:
            try:
                from engine.eng_constants import _NOVA_FLAGS as _nova_flags  # type: ignore
            except Exception:
                _nova_flags = []
        if _nova_flags:
            _reset_kw["args"] = list(_nova_flags)
        try:
            _exe = getattr(self.w.playwright.chromium, "executable_path", None)
            if _exe:
                _reset_kw["executable_path"] = _exe
        except Exception:
            pass
        browser = self.w.playwright.chromium.launch(**_reset_kw)
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
