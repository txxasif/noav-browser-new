"""Tab lifecycle, sheet suppression, render guard, session handshake. Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides run._MetaInstagramRunner helpers."""
from __future__ import annotations

import os
import random
import sys
import time
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_config import AI_DIR, Urls  # noqa: E402


class IGDeadEnd(Exception):
    """Unrecoverable Instagram state — e.g. the bare saved-account chooser that
    appears after a failed Meta join (profile named after the email local part,
    plus 'Use another profile' / 'Create new account'). Ops guidance: treat it
    as a DEAD END — close the browser and move to the next account instead of
    parking a broken record."""


class IgHelpersMixin:
    """Tab lifecycle, sheet suppression, render guard, session handshake."""

    def _ig_tab(self):
        """Reuse the Instagram tab, or open it in the SAME context (same session)."""
        page = getattr(self, "insta_page", None)
        try:
            if page is not None and not page.is_closed():
                return page
        except Exception:
            pass
        page = self.w.context.new_page()
        self.insta_page = page
        return page

    def _page_tail(self, p, n: int = 220) -> str:
        """Fetch the normalized tail of the visible page body text for telemetry and checks."""
        try:
            return (p.inner_text("body") or "").replace("\n", " ")[-n:]
        except Exception:
            return ""

    def _click_ig_login_btn(self, p) -> bool:
        """Find and tap the Instagram Log In button across both Bloks (div[role=button]) and HTML."""
        for sel in (
            'div[role="button"]:has-text("Log in")',
            'div[role="button"]:has-text("Log In")',
            '[aria-label="Log in"]',
            '[aria-label="Log In"]',
            'button[type="submit"]',
            'button:has-text("Log in")',
            'button:has-text("Log In")',
        ):
            try:
                btn = p.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    try:
                        btn.tap(timeout=3000)
                        return True
                    except Exception:
                        try:
                            btn.click(force=True, timeout=3000)
                            return True
                        except Exception:
                            self._human_click(p, btn, 4000)
                            return True
            except Exception:
                pass
        return False

    def _tap_or_click(self, p, loc, timeout: int = 4000) -> bool:
        """Attempt touch tap, forced click, or human mouse click on a locator."""
        try:
            loc.tap(timeout=timeout)
            return True
        except Exception:
            pass
        try:
            loc.click(force=True, timeout=timeout)
            return True
        except Exception:
            pass
        try:
            self._human_click(p, loc, timeout=timeout)
            return True
        except Exception:
            return False

    def _human_pause(self, lo: float = 0.25, hi: float = 0.9) -> None:
        """Short jittered idle between UI actions (anti-mechanization).

        The Accounts Center flow used to fire profile → gear → Meta card
        back-to-back (~1.2 s each) — a strong automation tell. A human pauses
        and moves between taps; this injects that jitter. It is NOT a state wait
        (use the poll helpers for that) — only cadence de-mechanization.
        """
        try:
            time.sleep(random.uniform(lo, hi))
        except Exception:
            pass

    def _touch_scroll(self, p, dy: int = 420) -> None:
        """Non-disruptive touch scroll DOWN the content (NOT pull-to-refresh).

        ``_swipe_down`` is a pull-DOWN refresh gesture — using it as a "settle"
        reloaded the page and disrupted the subsequent Accounts Center
        navigation (observed 2026-09-21: Step 1/2 taps stopped navigating after
        the settle). This drags UP instead (content scrolls down), which is what
        a human browsing the feed does.
        """
        vp = p.viewport_size or {"width": 393, "height": 852}
        cx = int(vp.get("width", 393) / 2)
        y0, y1 = 620, max(220, 620 - abs(dy))
        try:
            cdp = p.context.new_cdp_session(p)
            cdp.send("Input.dispatchTouchEvent",
                     {"type": "touchStart", "touchPoints": [{"x": cx, "y": y0}]})
            for y in range(y0, y1, -60):
                cdp.send("Input.dispatchTouchEvent",
                         {"type": "touchMove", "touchPoints": [{"x": cx, "y": y}]})
            cdp.send("Input.dispatchTouchEvent",
                     {"type": "touchEnd", "touchPoints": []})
        except Exception:
            try:
                p.mouse.wheel(0, abs(dy))
            except Exception:
                pass

    def _swipe_down(self, p) -> None:
        """Pull-down swipe gesture (touch drag + mouse drag + wheel nudge)
        to trigger mobile sheet rendering / refresh when Instagram CAA login stalls.
        """
        vp = p.viewport_size or {"width": 393, "height": 852}
        cx = int(vp.get("width", 393) / 2)
        y0, y1 = 250, 580

        # 1. Real touch drag via CDP session
        try:
            cdp = p.context.new_cdp_session(p)
            cdp.send("Input.dispatchTouchEvent", {
                "type": "touchStart",
                "touchPoints": [{"x": cx, "y": y0}],
            })
            steps = 10
            for i in range(1, steps + 1):
                cur_y = y0 + int((y1 - y0) * i / steps)
                cdp.send("Input.dispatchTouchEvent", {
                    "type": "touchMove",
                    "touchPoints": [{"x": cx, "y": cur_y}],
                })
                p.wait_for_timeout(30)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            try:
                cdp.detach()
            except Exception:
                pass
        except Exception:
            pass

        # 2. Mouse drag (for desktop Chromium touch emulation)
        try:
            p.mouse.move(cx, y0)
            p.mouse.down()
            steps = 8
            for i in range(1, steps + 1):
                cur_y = y0 + int((y1 - y0) * i / steps)
                p.mouse.move(cx, cur_y)
                p.wait_for_timeout(25)
            p.mouse.up()
        except Exception:
            pass

        # 3. Wheel nudge fallback
        try:
            p.mouse.wheel(0, 200)
            p.wait_for_timeout(200)
            p.mouse.wheel(0, -100)
        except Exception:
            pass

    def _dispatch_react_events(self, page, locator):
        """Dispatch explicit synthetic React events (input, change, blur) to synchronize Fiber tree."""
        try:
            locator.evaluate("""(el) => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }""")
        except Exception:
            pass

    def _dump_dom_discovery(self, p, tag: str = "discovery") -> dict:
        """Capture screenshot and interactive DOM nodes to screens/ for telemetry and discovery."""
        screens = os.path.join(AI_DIR, "screens")
        os.makedirs(screens, exist_ok=True)
        shot_path = os.path.join(screens, f"{tag}.png")
        try:
            p.screenshot(path=shot_path)
        except Exception:
            pass
        dom_info = {}
        try:
            dom_info = p.evaluate("""() => {
                const nodes = [];
                for (const el of document.querySelectorAll('button, a, div[role="button"], input, h1, h2, [role="dialog"]')) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        nodes.push({
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.textContent || '').trim().slice(0, 80),
                            role: el.getAttribute('role') || '',
                            aria: el.getAttribute('aria-label') || '',
                        });
                    }
                }
                return {
                    url: window.location.href,
                    title: document.title,
                    nodes: nodes.slice(0, 30)
                };
            }""")
            self.log(f'[🔍] DOM discovery ({tag}): url={dom_info.get("url")} | {len(dom_info.get("nodes", []))} interactive elements. Screenshot: screens/{tag}.png')
        except Exception as exc:
            self.log(f'[⚠️] DOM discovery note: {exc}')
        return dom_info

    def _way_out_escape(self, p, cooldown: int = 15) -> bool:
        """Guide "Way Of Getting Out": escape a trapped/challenged IG screen.

        NEVER hammer the broken modal in place (Reload loops, repeated
        Dismiss + instant retry). Instead: tap the native bottom-nav Profile
        tab if visible, else hard-redirect to the Instagram root, then cool
        down so the anti-bot score decays. Caller re-enters cleanly via
        Settings afterwards. Returns True when an escape was executed.
        """
        try:
            tail = (p.inner_text("body") or "").lower()
        except Exception:
            tail = ""
        url = p.url or ""
        is_scraping = "we suspect automated behavior" in tail or "scraping_warning" in url
        is_sww = "something went wrong" in tail or "page could not be loaded" in tail
        is_unavail = "isn't available right now" in tail or "technical error" in tail
        is_no_longer = "no longer available" in tail or "content you requested cannot be displayed" in tail

        if not (is_scraping or is_sww or is_unavail or is_no_longer):
            return False
        self.log('[🚪] Way Out: trapped/challenged screen — escaping instead of hammering…')
        if is_scraping:
            try:
                btn = p.locator('button:has-text("Dismiss")').first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(force=True, timeout=2000)
            except Exception:
                try:
                    p.keyboard.press("Escape")
                except Exception:
                    pass
        elif is_no_longer:
            # "This content is no longer available" modal: close via X (top-
            # right), expanding selector coverage; if the dead page persists
            # underneath, browser-Back once to restore the previous section
            # instead of a full Way Out + cooldown.
            closed = False
            for sel in ('button[aria-label*="Close" i]', 'div[aria-label*="Close" i]',
                        'span[aria-label*="Close" i]', 'svg[aria-label*="Close" i]',
                        '[aria-label*="Close" i]', '[role="dialog"] button:has(svg)',
                        'button:has-text("×")', 'div:has-text("×")'):
                try:
                    close_btn = p.locator(sel).first
                    if close_btn.count() > 0 and close_btn.is_visible():
                        try:
                            close_btn.click(timeout=2000)
                        except Exception:
                            close_btn.click(force=True, timeout=2000)
                        closed = True
                        break
                except Exception:
                    continue
            if not closed:
                try:
                    p.keyboard.press("Escape")
                except Exception:
                    pass
            p.wait_for_timeout(2500)
            try:
                dead = "no longer available" in (p.inner_text("body") or "").lower()
            except Exception:
                dead = False
            if dead:
                self.log('[🔙] Dead page persists after X — browser Back once…')
                try:
                    p.go_back(wait_until="domcontentloaded", timeout=20000)
                    p.wait_for_timeout(3000)
                except Exception:
                    pass

        # Dismiss any bottom sheets or "Use the app" banner that might block bottom nav
        try:
            self._dismiss_ig_sheets(p)
        except Exception:
            pass

        escaped = False
        user = getattr(self, "ig_username", None) or getattr(self, "username", None)
        prof_selectors = [
            'a[href*="/"][role="link"]:has(svg[aria-label*="Profile" i])',
            'svg[aria-label*="Profile" i]',
            '[aria-label="Profile"]',
            'a:has([aria-label="Profile"])',
            'a[role="link"]:has(img[alt*="profile picture" i])',
            'nav a:last-child',
            'footer a:last-child',
        ]
        if user:
            prof_selectors.insert(0, f'a[href*="/{user}/"]')
        for sel in prof_selectors:
            try:
                tab = p.locator(sel).first
                if tab.count() > 0 and tab.is_visible():
                    tab.click(force=True, timeout=3000)
                    escaped = True
                    break
            except Exception:
                pass
        if not escaped:
            try:
                p.goto(Urls.IG_HOME, wait_until="commit", timeout=30000)
                escaped = True
            except Exception:
                try:
                    p.goto(Urls.IG_HOME, wait_until="domcontentloaded", timeout=30000)
                    escaped = True
                except Exception:
                    pass
        try:
            p.wait_for_timeout(cooldown * 1000)
        except Exception:
            pass
        return escaped

    def _ig_relogin_if_needed(self, p, timeout: int = 45) -> bool:
        """Re-login when bounced to the IG login wall mid-flow (session drop).

        Fresh accounts occasionally lose their session between steps and land
        on `/accounts/login/?next=…settings…`. We own the creds
        (Meta email + current password), so log straight back in instead of
        failing the whole task. Bounded; returns True with a live sessionid.
        """
        try:
            url = p.url or ""
            tail = (p.inner_text("body") or "").lower()
        except Exception:
            return False
        # Cookie-first: a live sessionid means logged in regardless of what
        # the page text suggests (avoids false "log in"-substring walls on
        # healthy sessions that would wrongly fail fast downstream).
        try:
            if "sessionid" in self._ig_cookie_names():
                return True
        except Exception:
            pass
        if "/accounts/login" not in url and "log in" not in tail:
            return "sessionid" in self._ig_cookie_names()
        self.log('[🔑] Login wall mid-flow — re-logging in with account creds…')

        def _fill_login_form() -> bool:
            """Fill the IG identifier + password using the same discovery as
            ig_login (accessible names, then CSS fallbacks). Returns True
            when at least the identifier landed."""
            filled = False
            for nm in ("Username, email or mobile number",
                       "Mobile number, username or email",
                       "Phone number, username, or email",
                       "username", "email"):
                try:
                    if self._try_fill(p, nm, self.email, timeout=4000):
                        filled = True
                        break
                except Exception:
                    pass
            if not filled:
                for sel in ('input[name="username"]', 'input[type="text"]',
                            'input[autocomplete="username"]',
                            'input[aria-label*="email" i]'):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            self._clean_fill(p, el, self.email, timeout=6000)
                            filled = True
                            break
                    except Exception:
                        pass
            pw_filled = False
            try:
                if self._try_fill(p, "Password", self.password, timeout=4000):
                    pw_filled = True
            except Exception:
                pass
            if not pw_filled:
                for sel in ('input[name="password"]', 'input[type="password"]'):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            self._clean_fill(p, el, self.password, timeout=6000)
                            pw_filled = True
                            break
                    except Exception:
                        pass
            return filled

        def _form_present() -> bool:
            try:
                if p.locator('input[type="password"]').count() > 0:
                    return True
            except Exception:
                pass
            try:
                if self._visible(p, "textbox", "Password") is not None:
                    return True
            except Exception:
                pass
            return False

        try:
            # One-tap "Continue as" (same-session Meta SSO remnant) restores
            # the session with zero typing — try it before the password form.
            for sel in ('button:has-text("Continue as")',
                        'div[role="button"]:has-text("Continue as")'):
                try:
                    cont = p.locator(sel).first
                    if cont.count() > 0 and cont.is_visible():
                        if "facebook" not in (cont.inner_text() or "").lower():
                            self.log('[🔑] Re-login via one-tap "Continue as"…')
                            self._tap_or_click(p, cont)
                            p.wait_for_timeout(4000)
                            if "sessionid" in self._ig_cookie_names():
                                self.log('[✔] Re-login restored sessionid (one-tap).')
                                return True
                            break
                except Exception:
                    pass
            if not _form_present():
                # Logged-out public page (e.g. /<user>/ visitor view) has no
                # login form — go to the IG login page in-session and fill
                # there instead of burning 45s polling cookies on a dead page
                # (observed 2026-09-19: two 46s stalls, session never restored).
                self.log('[🔑] No login form on this page — opening IG login…')
                try:
                    p.goto(Urls.IG_LOGIN, wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:
                    self.log(f'[🔑] login goto note: {exc}')
                # Poll for form hydration (slow loads render fields late) —
                # the old code checked once after 3.5s and wrongly gave up.
                for _ in range(8):
                    p.wait_for_timeout(2000)
                    if _form_present():
                        break
                    try:
                        if "sessionid" in self._ig_cookie_names():
                            self.log('[✔] Re-login restored sessionid (post-goto).')
                            return True
                    except Exception:
                        pass
            if not _form_present():
                self.log('[⚠️] Re-login aborted: no login form found (session dead).')
                return False
            if not _fill_login_form():
                self.log('[⚠️] Re-login aborted: login fields unfillable.')
                return False
            if not self._click_ig_login_btn(p):
                try:
                    p.keyboard.press("Enter")
                except Exception:
                    pass
        except Exception:
            pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                if "sessionid" in self._ig_cookie_names():
                    self.log('[✔] Re-login restored sessionid.')
                    return True
            except Exception:
                pass
            try:
                p.wait_for_timeout(2000)
            except Exception:
                break
        restored = "sessionid" in self._ig_cookie_names()
        self.log('[✔] Re-login restored sessionid.' if restored
                 else '[⚠️] Re-login did NOT restore sessionid (downstream AC nav will fail).')
        return restored

    def _chooser_relogin(self, p) -> bool:
        """Recover the saved-account chooser (dropped session) by re-logging in.

        The chooser — bare profile + "Use another profile" + "Create new
        account" on an ``/accounts/`` route — means the ``sessionid`` was
        invalidated (IG ``require_login`` hold), NOT that the Meta join failed.
        During the Accounts Center phase we own the creds, so we can re-login
        instead of raising ``IGDeadEnd`` (observed 2026-09-21: a Reload on the
        AC route landed here and the run dead-ended). Bounded: returns False
        when it cannot clear the chooser, so the caller can still dead-end.
        """
        try:
            tail = (p.inner_text("body") or "").lower()
            url = (p.url or "").lower()
        except Exception:
            return False
        if "use another profile" not in tail and "create new account" not in tail:
            return False
        if not any(k in url for k in ("/accounts/", "/accounts/login",
                                      "accountscenter.instagram.com")):
            return False

        def _sid() -> bool:
            try:
                return "sessionid" in self._ig_cookie_names()
            except Exception:
                return False

        def _chooser_gone() -> bool:
            try:
                return "use another profile" not in (p.inner_text("body") or "").lower()
            except Exception:
                return False

        self.log('[🔑] Saved-account chooser (session dropped) — re-logging in with owned creds…')

        # 1. One-tap: click the account row / Continue (may restore with no typing).
        for sel in ('button:has-text("Continue")',
                    'div[role="button"]:has-text("Continue")',
                    '[role="button"]:has-text("Continue")'):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    self._tap_or_click(p, el)
                    p.wait_for_timeout(3500)
                    break
            except Exception:
                pass

        # 2. If a password form appeared, fill the owned password + submit.
        try:
            has_pw = p.locator('input[type="password"]').count() > 0
        except Exception:
            has_pw = False
        if has_pw:
            for sel in ('input[name="password"]', 'input[type="password"]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        self._clean_fill(p, el, self.password, timeout=6000)
                        break
                except Exception:
                    pass
            if not self._click_ig_login_btn(p):
                try:
                    p.keyboard.press("Enter")
                except Exception:
                    pass
            for _ in range(15):
                try:
                    p.wait_for_timeout(1000)
                except Exception:
                    break
                if _sid() and _chooser_gone():
                    break

        if _sid() and _chooser_gone():
            self.log('[✔] Chooser cleared — session restored.')
            return True

        # 3. Fallback: full login via "Use another profile".
        self.log('[🔑] Chooser one-tap insufficient — full login fallback…')
        for sel in ('button:has-text("Use another profile")',
                    'div[role="button"]:has-text("Use another profile")',
                    '[role="button"]:has-text("Use another profile")'):
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    self._tap_or_click(p, el)
                    p.wait_for_timeout(3000)
                    break
            except Exception:
                pass
        try:
            return bool(self._ig_relogin_if_needed(p, timeout=45))
        except Exception:
            return False

    def _is_email_risky_screen(self, p) -> bool:
        """True for IG's "Your email may not be secure" contact-point gate.

        Served at ``/accounts/update_risky_contactpoint/`` ("The email address
        associated with your account may be at risk. Add a different email…").
        There is **no Skip** — the only way through is to add a different email.
        Observed 2026-09-21 (mail.td's nqmo.com/qabq.com domains get flagged).
        """
        try:
            tail = (p.inner_text("body") or "").lower()
            url = (p.url or "").lower()
        except Exception:
            return False
        if "update_risky_contactpoint" in url:
            return True
        if "email may not be secure" in tail:
            return True
        # NOTE: do NOT match the bare phrase "update email address" — the
        # Accounts Center contact-info UI legitimately shows it, so it
        # false-positived and would dead-end healthy accounts mid email-link.
        return "email address associated with your account" in tail and "at risk" in tail

    def _is_ig_dead_end_chooser(self, p) -> bool:
        """True for the Instagram saved-account chooser that means the Meta join
        silently failed: 'Use another profile' + 'Create new account' on an
        instagram.com/accounts/ page, with the bare profile named after the
        email local part (e.g. lxwf3r for lxwf3r@nqmo.com). DEAD END."""
        try:
            tail = (p.inner_text("body") or "").lower()
            url = (p.url or "").lower()
        except Exception:
            return False
        if "use another profile" not in tail or "create new account" not in tail:
            return False
        if "instagram.com/accounts/" not in url and "/accounts/login" not in url:
            return False
        local = (getattr(self, "email", "") or "").split("@")[0].lower()
        return bool(local) and local in tail

    def _recover_something_went_wrong(self, p, max_attempts: int = 3) -> bool:
        """Detect Instagram 'Something went wrong' / 'Reload page' screens.

        Guide rule: ONE Reload attempt max — hammering the broken chunk in
        place never resets it and only burns rate limit. If the screen
        persists, take the Way Out (Profile tab or IG root + cooldown)
        instead of further reloads.
        """
        recovered = False
        for attempt in range(max_attempts):
            try:
                cur_tail = (p.inner_text("body") or "").lower()
            except Exception:
                cur_tail = ""

            is_sww = (
                "something went wrong" in cur_tail
                and ("reload page" in cur_tail or "issue and the page could not be loaded" in cur_tail)
            ) or (
                "isn't available right now" in cur_tail and ("reload page" in cur_tail or "technical error" in cur_tail)
            ) or (
                "no longer available" in cur_tail or "content you requested cannot be displayed" in cur_tail
            )

            if not is_sww:
                try:
                    r_btn = p.locator('button:has-text("Reload page"), div[role="button"]:has-text("Reload page"), a:has-text("Reload page")').first
                    if r_btn.count() > 0 and r_btn.is_visible():
                        is_sww = True
                except Exception:
                    pass

            if not is_sww:
                break

            # If it's "no longer available" (modal with close 'X', no reload button), escape immediately
            if "no longer available" in cur_tail or "content you requested cannot be displayed" in cur_tail:
                self.log('[⚠️] "This content is no longer available" detected — taking the Way Out…')
                self._dump_dom_discovery(p, tag="no_longer_available_escape")
                self._way_out_escape(p)
                recovered = True
                break

            _url_low = (p.url or "").lower()
            _ac_route = any(k in _url_low for k in (
                "accountscenter.instagram.com", "/accounts/settings",
                "/password_and_security", "/two_factor", "/account_overview",
                "/accounts/edit", "/profiles/"))
            if attempt >= 1 or _ac_route:
                # Guide: never hammer Reload. And NEVER reload a challenged
                # Accounts Center route: the reload lands on
                # /accounts/scraping_warning/ and can invalidate the session
                # (observed 2026-09-21: Reload -> bot-check -> saved-account
                # chooser -> dead end). Escape instead.
                if _ac_route and attempt == 0:
                    self.log('[⚠️] "Something went wrong" on an Accounts Center route — Way Out (no Reload).')
                else:
                    self.log(f'[⚠️] Error screen persists after reload — taking the Way Out…')
                self._dump_dom_discovery(p, tag="something_went_wrong_escape")
                self._way_out_escape(p)
                try:
                    cur_tail = (p.inner_text("body") or "").lower()
                    recovered = "something went wrong" not in cur_tail and "isn't available" not in cur_tail
                except Exception:
                    recovered = True
                break

            self.log(f'[⚠️] Instagram "Something went wrong" screen detected — single Reload attempt…')
            self._dump_dom_discovery(p, tag=f"something_went_wrong_{attempt+1}")
            clicked_reload = False
            try:
                btn = p.locator('button:has-text("Reload page"), div[role="button"]:has-text("Reload page"), a:has-text("Reload page")').first
                if btn.count() > 0 and btn.is_visible():
                    if not self._tap_or_click(p, btn, timeout=3000):
                        btn.click(force=True, timeout=2000)
                    clicked_reload = True
            except Exception:
                pass

            if not clicked_reload:
                try:
                    clicked_reload = p.evaluate("""() => {
                        for (const el of document.querySelectorAll('button, div[role="button"], a, span')) {
                            if ((el.innerText || el.textContent || '').trim().toLowerCase() === 'reload page') {
                                el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                                el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                except Exception:
                    pass

            if not clicked_reload:
                try:
                    p.reload(wait_until="domcontentloaded", timeout=30000)
                    clicked_reload = True
                except Exception:
                    pass

            p.wait_for_timeout(3500)
            recovered = True

        return recovered

    def _dismiss_ig_sheets(self, p) -> bool:
        """Dismiss unwanted mobile bottom-sheet drawers, promo dialogs ('Add to Home screen'),
        'Get the Instagram app' interstitial ('Skip'), or 'Save your login info' bottom sheet.
        Optimized to execute in single-pass JS without burning long locator timeouts.
        """
        dismissed = False

        # 1. Comprehensive single-pass JS evaluation (< 10ms execution time)
        try:
            js_res = p.evaluate("""() => {
                const bodyText = (document.body.innerText || '').toLowerCase();

                function fireClick(el) {
                    el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                    el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    try { el.click(); } catch(e) {}
                }

                function cleanBackdrops() {
                    // NON-DESTRUCTIVE (2026-09-21): never remove() app-shell-sized
                    // nodes here. IG's route/app container is a large
                    // `div[tabindex="-1"]`, so removing it nuked the header (and
                    // the profile settings gear) — a prime suspect for "Accounts
                    // Center unreachable" (Step 2 could not find the gear).
                    // Disabling pointer events is enough to let taps through.
                    const backdrops = document.querySelectorAll('div[style*="position: fixed"], div[style*="position: absolute"], ._a9-z, div[tabindex="-1"]');
                    for (const b of backdrops) {
                        const r = b.getBoundingClientRect();
                        if (r.width > 300 && r.height > 500) {
                            b.style.pointerEvents = 'none';
                        }
                    }
                }

                // (A) "Get the Instagram app" interstitial screen (Screenshot 2)
                // Never click "Open Instagram"; strictly click "Skip"
                if (bodyText.includes("get the instagram app") || bodyText.includes("turn on notifications, read comments and discover reels")) {
                    for (const el of document.querySelectorAll('a, button, div[role="button"], span')) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (t === 'skip') {
                            fireClick(el);
                            cleanBackdrops();
                            return 'clicked_skip_get_app';
                        }
                    }
                }

                // (B) "Save your login info to Instagram?" bottom sheet modal (Screenshot 3)
                if (bodyText.includes("save your login info") || bodyText.includes("save login info")) {
                    // Prefer "Not now", fallback to "Save"
                    for (const el of document.querySelectorAll('button, div[role="button"], a, span, div[tabindex]')) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (t === 'not now') {
                            fireClick(el);
                            cleanBackdrops();
                            return 'clicked_not_now_save_login';
                        }
                    }
                    for (const el of document.querySelectorAll('button, div[role="button"], a, span, div[tabindex]')) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (t === 'save') {
                            fireClick(el);
                            cleanBackdrops();
                            return 'clicked_save_login';
                        }
                    }
                }

                // (C) "Add Instagram to your Home screen?" modal dialog (Screenshot 4)
                // Extremely fast dismissal: click Cancel, remove modal from DOM immediately, unblock backdrops
                if (bodyText.includes("home screen") || bodyText.includes("add instagram to your home")) {
                    for (const el of document.querySelectorAll('button, div[role="button"], a, span, div[tabindex]')) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (t === 'cancel') {
                            fireClick(el);
                            const modal = el.closest('[role="dialog"], div[aria-modal="true"], ._a9-v');
                            if (modal) {
                                modal.style.display = 'none';
                                try { modal.remove(); } catch(e) {}
                            }
                            cleanBackdrops();
                            return 'clicked_cancel_home_screen';
                        }
                    }
                }

                // (D) Any standard dialogs / bottom sheets with Cancel / Not now / Skip / Close / Dismiss
                const dialogs = document.querySelectorAll('[role="dialog"], div[aria-modal="true"], ._a9-v, div[data-bloks-name]');
                for (const d of dialogs) {
                    const candidates = Array.from(d.querySelectorAll('button, div[role="button"], div, span, a, div[tabindex]'));
                    for (const el of candidates) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (t === 'cancel' || t === 'not now' || t === 'skip' || t === 'close' || t === 'dismiss') {
                            fireClick(el);
                            try { d.remove(); } catch(e) {}
                            cleanBackdrops();
                            return 'clicked_dialog_' + t;
                        }
                    }
                }

                // (E) Clean up orphaned fixed backdrops preventing clicks on bottom navigation
                const backdrops = document.querySelectorAll('div[style*="position: fixed"], div[style*="position: absolute"], ._a9-z, div[tabindex="-1"]');
                let unblocked = false;
                for (const b of backdrops) {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 300 && rect.height > 500) {
                        const hasVisibleDialog = document.querySelector('[role="dialog"]:not([aria-hidden="true"]), div[aria-modal="true"]');
                        if (!hasVisibleDialog) {
                            // pointerEvents only — never remove() the app shell
                            // (see cleanBackdrops note above).
                            b.style.pointerEvents = 'none';
                            unblocked = true;
                        }
                    }
                }
                if (unblocked) {
                    return 'unblocked_backdrops';
                }

                // (F) "Use the app" floating bottom banner (Screenshot 22-27-26)
                if (bodyText.includes("use the app")) {
                    for (const el of document.querySelectorAll('button, div[role="button"], span, a, svg')) {
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (aria === 'close' || aria === 'dismiss' || t === '✕' || t === '×') {
                            fireClick(el);
                            cleanBackdrops();
                            return 'clicked_close_use_app_banner';
                        }
                    }
                    const banner = Array.from(document.querySelectorAll('div')).find(x => {
                        const s = (x.innerText || '').toLowerCase();
                        return s.includes('use the app') && s.length < 50;
                    });
                    if (banner) {
                        const c = banner.closest('div[style*="position: fixed"], div[style*="bottom"]') || banner;
                        c.style.display = 'none';
                        try { c.remove(); } catch(e) {}
                        return 'removed_use_app_banner';
                    }
                }

                return null;
            }""")
            if js_res:
                self.log(f'[+] _dismiss_ig_sheets: JS action "{js_res}".')
                p.wait_for_timeout(400)
                dismissed = True
        except Exception:
            pass

        # 2. Fast Playwright locator fallback (short timeouts, strictly avoiding slow loops)
        if not dismissed:
            fast_selectors = (
                '[role="dialog"] button:has-text("Cancel")',
                '[role="dialog"] button:has-text("Not now")',
                'button:has-text("Cancel")',
                'div[role="button"]:has-text("Cancel")',
                'button:has-text("Not now")',
                'div[role="button"]:has-text("Not now")',
                'button:has-text("Skip")',
                'a:has-text("Skip")',
                'div:has-text("Use the app") button[aria-label*="Close" i]',
                'div:has-text("Use the app") [aria-label*="Close" i]',
            )
            for sel in fast_selectors:
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        el.click(force=True, timeout=500)
                        self.log(f'[+] _dismiss_ig_sheets: dismissed via locator "{sel}".')
                        dismissed = True
                        p.wait_for_timeout(400)
                        break
                except Exception:
                    pass

        try:
            p.keyboard.press("Escape")
        except Exception:
            pass

        # 3. Check for "Something went wrong" / "Reload page"
        if self._recover_something_went_wrong(p, max_attempts=1):
            dismissed = True

        return dismissed

    def _dismiss_scraping_warning(self, p) -> bool:
        """Dismiss Instagram's bot-check interstitial + cool down.

        Live-observed (2026-09-17): direct Accounts Center nav can land on
        ``instagram.com/accounts/scraping_warning/`` — "We suspect automated
        behavior on your account" with a Dismiss button. It is a WARNING, not
        a suspension (feed/session keep working); hammering AC behind it only
        extends scrutiny, so dismiss once and back off.
        """
        try:
            tail = (p.inner_text("body") or "").lower()
        except Exception:
            tail = ""
        if "we suspect automated behavior" not in tail and "scraping_warning" not in (p.url or ""):
            return False
        self.log('[⚠️] Instagram bot-check interstitial (scraping_warning) — dismissing, cooling down.')
        dismissed = False
        for sel in ('button:has-text("Dismiss")', '[role="button"]:has-text("Dismiss")',
                    'div:has-text("Dismiss")', '[aria-label*="Dismiss" i]'):
            try:
                btn = p.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    try:
                        btn.click(timeout=3000)
                    except Exception:
                        btn.click(force=True, timeout=3000)
                    dismissed = True
                    break
            except Exception:
                continue
        if not dismissed:
            try:
                p.keyboard.press("Escape")
            except Exception:
                pass
        p.wait_for_timeout(3000)
        # Verify the interstitial actually left; a stale Dismiss tap leaves it up.
        def _still() -> bool:
            try:
                return "we suspect automated behavior" in (p.inner_text("body") or "").lower()
            except Exception:
                return False
        if _still():
            self.log('[⚠️] Scraping warning still present after Dismiss — one retry…')
            try:
                btn = p.locator('button:has-text("Dismiss"), [role="button"]:has-text("Dismiss")').first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(force=True, timeout=3000)
            except Exception:
                pass
            p.wait_for_timeout(2000)
        if _still():
            # Hand off to the caller (Way Out) instead of burning another 15s
            # here — avoids the double-Dismiss + double cooldown (observed
            # 2026-09-21). Return the TRUE outcome so callers can act on it.
            self.log('[⚠️] Scraping warning persists after Dismiss — handing to Way Out.')
            return False
        # Cleared: cool down so the anti-bot score decays.
        p.wait_for_timeout(15000)
        return True

    def _require_ig_rendered(self, page, what: str = "Instagram page") -> None:
        """Fail fast when IG serves a blank shell (mobile bootstrap GraphQL
        1675004 rate limit after heavy creator runs). Without this, every
        downstream locator burns through long timeouts on a page that will
        never render.
        """
        try:
            tail = (page.inner_text("body") or "").strip()
        except Exception:
            tail = ""
        if len(tail) >= 20:
            return
        page.wait_for_timeout(12000)
        try:
            tail = (page.inner_text("body") or "").strip()
        except Exception:
            tail = ""
        if len(tail) < 20:
            raise RuntimeError(
                f"{what} rendered blank (IG bootstrap rate-limited). "
                "Cooldown a few hours, lower creators to 1-2, then retry.")

    def _ig_cookie_names(self) -> List[str]:
        """Fetch all current cookie names for instagram.com."""
        try:
            return [c["name"] for c in self.w.context.cookies(Urls.IG_HOME)]
        except Exception:
            return []

    def _ensure_ig_session(self, p, timeout: int = 90) -> bool:
        """Make sure the Instagram context is actually logged in (sessionid)."""
        end = time.time() + timeout
        while time.time() < end and self.w.is_running:
            if "sessionid" in self._ig_cookie_names():
                return True
            tail = self._page_tail(p).lower()

            # Fast fail check: account rejected or phone wall
            if "can't find account" in tail or p.get_by_text("Can't find account", exact=False).count() > 0:
                self.log('[❌] Instagram: "Can\'t find account" detected. Quitting session check.')
                return False
            if "what's your mobile number" in tail or p.get_by_text("What's your mobile number", exact=False).count() > 0:
                self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting session check.')
                return False

            # "Continue as <user>" saved-account chooser
            self._try_click(p, "Continue", timeout=2500)

            # Email confirmation code screen
            if (
                "check your email" in tail
                or "enter the code" in tail
                or self._visible(p, "textbox", "Enter code") is not None
                or self._visible(p, "textbox", "Confirmation code") is not None
            ):
                code = self.fetch_code("instagram", timeout=120)
                if code:
                    for nm in ("Enter code", "Confirmation code", "Code"):
                        if self._try_fill(p, nm, code, timeout=6000):
                            break
                    if not self._try_click(p, "Continue", timeout=6000):
                        self._try_click(p, "Next", timeout=6000)

            # Login form (identifier + password)
            if self._visible(p, "textbox", "Password") is not None:
                self._try_fill(p, "Mobile number, username or email", self.email)
                self._try_fill(p, "Username, email or mobile number", self.email)
                self._try_fill(p, "Password", self.password)
                if not self._click_ig_login_btn(p):
                    if not self._try_click(p, "Log in", timeout=6000):
                        self._try_click(p, "Log In", timeout=6000)

            # Consent & Terms: "Agree to Instagram's terms and policies" / "I agree"
            if "agree to instagram" in tail or "terms and policies" in tail or "i agree" in tail:
                for sel in ('button:has-text("I agree")', 'div[role="button"]:has-text("I agree")', '[aria-label="I agree"]', 'button:has-text("Agree")', 'div[role="button"]:has-text("Agree")'):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        p.wait_for_timeout(3000)
                        break
            if "allow the following" in tail or "allow and continue" in tail:
                self._try_click(p, "Allow and continue", timeout=4000)

            p.wait_for_timeout(2500)

        return "sessionid" in self._ig_cookie_names()
