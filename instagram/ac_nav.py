"""Accounts Center in-app navigation (UI clicks only, never URL jumps).

Split out of the former 2082-line ``instagram/password.py`` (2026-09-25). All
entry here is click-driven per invariant #18: a direct-URL jump into Accounts
Center is forbidden, section labels are tried "Login and security" first, and
sub-pages are stepped back to the section root before the next hop.

Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides the
run._MetaInstagramRunner helpers and the re-auth mixin it calls.
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


class IgAcNavMixin:
    """In-app Accounts Center navigation, section reach, and sub-page hygiene."""

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
        # NO re-login retry. A login wall or the saved-account chooser means
        # Instagram already dropped the session — that IS the dead end. Quit so
        # the slot closes and opens a NEW task (operator decision 2026-09-28:
        # "no retry login; if that page comes it's a dead end").
        if self._is_ig_dead_end_chooser(p):
            raise IGDeadEnd(
                "IG saved-account chooser (logged out — session dropped) — dead end")
        if "/accounts/login" in (p.url or ""):
            raise IGDeadEnd(
                f"IG login wall — session dropped ({(p.url or '')[:80]})")
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
                        # FAST bail: a login wall / chooser is terminal — quit
                        # now, do not grind the retries.
                        if self._walled_or_chooser(p):
                            raise IGDeadEnd(
                                "IG login wall/chooser during AC nav (fast dead end)")
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
                            if self._walled_or_chooser(p):
                                raise IGDeadEnd(
                                    "IG login wall/chooser during AC nav (fast dead end)")
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
                            # FAST bail: a login wall / chooser is terminal.
                            if self._walled_or_chooser(p):
                                raise IGDeadEnd(
                                    "IG login wall/chooser during AC nav (fast dead end)")
                            cur_url = p.url or ""
                            if "/accounts/settings" in cur_url or p.locator(
                                    'a[href*="accountscenter"], [aria-label*="Accounts Center" i]').count() > 0:
                                settings_reached = True
                                break
                    except IGDeadEnd:
                        raise
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
        # Referenced by CLASS NAME (not self) because it is a staticmethod — it
        # must name the mixin that actually owns these members, which is this
        # one since the AC split (it was IgPasswordMixin before 2026-09-25).
        for alias in IgAcNavMixin._AC_PATH_ALIASES:
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
        cur = IgAcNavMixin._ac_norm_path(cur_path)
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
                # FAST bail: a login wall / chooser is terminal — quit now.
                if self._walled_or_chooser(p):
                    raise IGDeadEnd(
                        "IG login wall/chooser during AC nav (fast dead end)")
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

    # The terminal dead state for a fresh account (IG runbook obs. #1): until
    # the "Confirm you're human to use your profile" checkpoint is cleared, IG
    # gives "Can't find account" and every later AC step fails. It is NOT
    # solvable offline, so we STOP here — but only AFTER trying to reach
    # Accounts Center, never before.
    _HUMAN_CONFIRM_MARKERS = (
        "confirm you're human", "confirm you\u2019re human", "confirm you are human",
    )

    def _walled_or_chooser(self, p) -> bool:
        """FAST dead-end probe: login wall, saved-account chooser, or the
        logged-out "Remove profile" surface.

        Checked inside the Step 1/2 retry loops so the cycle quits the MOMENT
        Instagram bounces to /accounts/login (e.g. the ``__coig_login=1`` login
        wall) or shows a logged-out account surface — instead of burning
        ~60-90s on 3 profile taps + 3 gear taps + a reload + a direct
        /accounts/settings/ goto first (operator report 2026-09-28: "it takes
        time to quit — make it fast").
        """
        try:
            if self._is_ig_dead_end_chooser(p):
                return True
            if "/accounts/login" in (p.url or ""):
                return True
            # Logged-out "Remove profile" sheet: a saved profile + a red
            # "Remove profile" action + the "Learn more … remove it" copy.
            t = (p.inner_text("body") or "").lower()
            if "remove profile" in t and "learn more" in t:
                return True
        except Exception:
            pass
        return False

    def _is_human_confirm_page(self, p) -> bool:
        """True on Instagram's 'Confirm you're human to use your profile' page."""
        try:
            t = (p.inner_text("body") or "").lower()
        except Exception:
            return False
        return any(m in t for m in self._HUMAN_CONFIRM_MARKERS)

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

        # If not in Accounts Center, navigate via in-app UI clicks (Profile ->
        # Gear -> Accounts Center). RETRY instead of quitting: a transient miss
        # (half-rendered SPA, a gear not yet in the DOM, "Something went wrong")
        # must NOT abort the whole task. Keep pushing toward Accounts Center
        # until we ARRIVE — or we hit a TRUE dead state: the
        # "Confirm you're human to use your profile" checkpoint (terminal, per
        # the IG runbook) or an unrecoverable login wall.
        if "accountscenter.instagram.com" not in (p.url or ""):
            for _try in range(3):
                if self._is_human_confirm_page(p):
                    self.log("[🛡️] Human confirm page encountered during AC nav — attempting captcha solve…")
                    if hasattr(self, "_solve_captcha_ordered"):
                        self._solve_captcha_ordered(p)
                    if self._is_human_confirm_page(p):
                        raise IGDeadEnd(
                            "Instagram 'Confirm you're human to use your profile' checkpoint "
                            "— terminal dead state (not solvable offline)")
                self._recover_something_went_wrong(p, max_attempts=2)
                try:
                    self._ac_navigate_in_app(p, section_path=section_path, label=label)
                except IGDeadEnd:
                    raise
                except Exception as exc:
                    self.log(f'[ac] in-app navigation note (try {_try + 1}/3): {exc}')
                # Arrived? (Accounts Center can open in a new tab.)
                for page in self.w.context.pages:
                    if not page.is_closed() and "accountscenter.instagram.com" in (page.url or ""):
                        self.insta_page = page
                        p = page
                        break
                if "accountscenter.instagram.com" in (p.url or ""):
                    break
                if _try < 2:
                    self.log(f'[ac] Not in Accounts Center yet (try {_try + 1}/3) '
                             '— retrying navigation (not quitting)…')
                    p.wait_for_timeout(1500)

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

        # Terminal dead states — NO retry login (operator decision 2026-09-28:
        # "no retry login; if that page comes it's a dead end"). The session is
        # already gone, so quit and move to the NEXT account:
        #   * the saved-account chooser  (logged out, saved account offered)
        #   * /accounts/login            (login wall)
        #   * "Confirm you're human"     (not solvable offline)
        if self._is_human_confirm_page(p):
            self.log("[🛡️] Human confirm page encountered — attempting captcha solve…")
            if hasattr(self, "_solve_captcha_ordered"):
                self._solve_captcha_ordered(p)
            if self._is_human_confirm_page(p):
                raise IGDeadEnd(
                    "Instagram 'Confirm you're human to use your profile' checkpoint "
                    "— terminal dead state (not solvable offline)")
        if self._is_ig_dead_end_chooser(p):
            raise IGDeadEnd(
                "IG saved-account chooser (logged out — session dropped) — dead end")
        if "/accounts/login" in (p.url or ""):
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
                    # Ensure no lingering dialog overlays block navigation
                    if p.locator('div[role="dialog"]').count() > 0:
                        try:
                            getattr(self, "_dismiss_contact_modal", lambda *a: None)(p)
                        except Exception:
                            pass
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
                        self.log(f'[ac] Section tap {_nav + 1}/2 missed "{clean_path}" (still at {cur_path[:80]}) — attempting direct navigation…')
                        try:
                            # Direct URL navigation bypasses nested subpages / stalled root lists
                            p.goto(f"https://accountscenter.instagram.com/{clean_path}/", wait_until="domcontentloaded", timeout=15000)
                            p.wait_for_timeout(1500)
                            cur_path = (p.url or "").split("?")[0].rstrip("/")
                            if self._ac_in_section(cur_path, clean_path):
                                reached = True
                                break
                        except Exception:
                            pass
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
            # The "Confirm you're human to use your profile" checkpoint is the
            # other TERMINAL state (not solvable offline) — name it explicitly
            # so the caller stops there instead of retrying forever.
            if self._is_human_confirm_page(p):
                self.log("[🛡️] Human confirm page encountered — attempting captcha solve…")
                if hasattr(self, "_solve_captcha_ordered"):
                    self._solve_captcha_ordered(p)
                if self._is_human_confirm_page(p):
                    raise IGDeadEnd(
                        "Instagram 'Confirm you're human to use your profile' checkpoint "
                        "— terminal dead state (not solvable offline)")
            _dead = False
            try:
                _names = self._ig_cookie_names()
                # Only a NON-EMPTY cookie jar missing sessionid proves the session
                # dropped; an empty list can just be a failed query.
                _dead = bool(_names) and "sessionid" not in _names
            except Exception:
                pass
            # A loaded IG surface (feed / bottom nav) means we ARE logged in —
            # the missing cookie is a false negative, not a dropped session.
            if _dead and self._ig_logged_in_ui(p):
                _dead = False
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
        meta_original_name = f"{getattr(self, 'first', '')} {getattr(self, 'last', '')}".strip()
        if not prefer_instagram:
            if meta_original_name:
                candidates.extend([
                    f"{meta_original_name} · Meta",
                    f"{meta_original_name}, Meta",
                    f"{meta_original_name} Meta",
                    meta_original_name,
                ])
            if self.name and self.name != meta_original_name:
                candidates.extend([
                    f"{self.name} · Meta",
                    f"{self.name}, Meta",
                    f"{self.name} Meta",
                    self.name,
                ])
        for name in candidates:
            if self._try_click(p, name, timeout=4000) or self._try_click(p, name, role="button", timeout=3000):
                self.log(f'[ac] chose account row: "{name}"')
                p.wait_for_timeout(3000)
                return True
        if prefer_instagram:
            try:
                loc = p.locator('div[role="button"]:has-text("Instagram"), button:has-text("Instagram")')
                for i in range(min(loc.count(), 6)):
                    btn = loc.nth(i)
                    if not btn.is_visible():
                        continue
                    t = (btn.inner_text() or btn.get_attribute("aria-label") or "").lower()
                    if any(bad in t for bad in ("back to instagram settings", "login and security", "password and security")):
                        continue
                    if not self._tap_or_click(p, btn):
                        self._human_click(p, btn, 5000)
                    self.log(f'[ac] chose Instagram account row ({t[:40]}...)')
                    p.wait_for_timeout(3000)
                    return True
            except Exception:
                pass
        else:
            try:
                loc = p.locator('div[role="button"]:has-text("Meta"), button:has-text("Meta")')
                for i in range(min(loc.count(), 6)):
                    btn = loc.nth(i)
                    if not btn.is_visible():
                        continue
                    t = (btn.inner_text() or btn.get_attribute("aria-label") or "").lower()
                    if any(bad in t for bad in ("emails from meta", "security checkup", "meta pay", "back to")):
                        continue
                    if not self._tap_or_click(p, btn):
                        self._human_click(p, btn, 5000)
                    self.log(f'[ac] chose Meta account row ({t[:40]}...)')
                    p.wait_for_timeout(3000)
                    return True
            except Exception:
                pass
        return False
