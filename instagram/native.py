"""IG NATIVE email signup for bot-issued tasks (Taskly 2FA).

Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides the
run._MetaInstagramRunner helpers (same-session invariant unchanged).

Flow (learned live 2026-09-28 on Taskly "📱 Create Inst (2FA)"):
  bot First name/Login/Password/Email (Email ordered async after Start) ->
  instagram.com/ front page -> "Create new account"/"Sign up" taps ->
  phone wall -> "Sign up with email" escape -> email -> Next -> bot Get-code
  key -> 6-digit code -> Next -> name/username/password/birthday details ->
  feed.

  Front-door entry is LOAD-BEARING (learned 2026-09-28): deep-linking
  straight to /accounts/signup/email/ gets its email codes REJECTED
  ("invalid or expired") while the identical steps driven click-by-click
  from the homepage validate fine. Never URL-jump past the front door here.

No Meta account, no temp mailbox: the email AND its code both come from the
bot. Code-freshness (the 2026-09-28 failure): the bot's mailbox can hold an
OLDER code from a previous use — IG rejects it ("invalid or has expired").
So: wait for delivery before the first Get-code press, and on a rejection
re-press Get code for a FRESH read (max 3 codes), never hammer Next.
"""
from __future__ import annotations

import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_config import Urls  # noqa: E402
try:
    from .helpers import IGDeadEnd
except ImportError:
    from instagram.helpers import IGDeadEnd  # type: ignore

IG_HOME = Urls.IG_HOME
IG_LOGIN = Urls.IG_LOGIN


def _random_adult_dob() -> tuple:
    """Random adult birthday (year, month-index-1..12, day)."""
    return (random.randint(1992, 2001), random.randint(1, 12), random.randint(1, 28))


class IgNativeMixin:
    """IG native email signup with bot-issued credentials."""

    def ig_signup_native(self, email, first_name, login, password,
                         request_code=None, max_codes: int = 3, dob=None) -> str:
        """Run native signup; return the IG username live on the feed.

        ``request_code`` — zero-arg callable returning a fresh 6-digit email
        code from the bot (each call re-presses Get code). Raises on phone
        wall without escape, human checkpoint, TTL-safe bounds left to caller.
        """
        p = self._ig_tab()
        self.log('[🌐] IG native signup: front-door entry (homepage taps, no deep link)…')
        # Front door only: homepage -> "Create new account"/"Sign up" taps.
        # A deep jump straight to the signup URL gets its email codes rejected
        # ("invalid or expired") while click-through validates fine — so a
        # failed entry FAILS LOUD instead of silently deep-linking.
        entered = self._native_front_door(p)
        if not entered:
            raise RuntimeError("native signup front-door entry blocked (no Sign up control)")

        dob = dob or _random_adult_dob()
        codes_tried = 0
        tried_codes = set()
        email_sent = False
        email_taps = 0
        deadline = time.time() + 300  # hard bound: one signup attempt, 5 min
        _last_key = ""
        _beat = time.time()

        while time.time() < deadline and self._native_running():
            try:
                low = (p.inner_text("body") or "").lower()
            except Exception:
                low = ""
            url = p.url or ""
            # Heartbeat: the waits below are silent by design (bot delivery,
            # React hydration) — narrate the current screen so a healthy run
            # is never mistaken for a stuck one.
            _key = (url[-40:] + "|" + low[:60]).replace("\n", " ")
            if _key != _last_key:
                _last_key = _key
                _beat = time.time()
                self.log(f'[🌐] native signup @ {_key[:100]}')
            elif time.time() - _beat >= 30:
                _beat = time.time()
                self.log(f'[🌐] native signup still working @ {_key[:100]}')

            # --- human verification checkpoint (terminal dead end) -----------
            if ("confirm you're human" in low or "suspect automated" in low
                    or "accounts/suspended" in (url or "").lower()):
                self.log('[🛡️] "Confirm you\'re human" / suspended checkpoint detected — dead end; exiting.')
                raise IGDeadEnd("Instagram 'Confirm you\'re human' checkpoint — dead end")
            if self._native_phone_walled(p, low):
                raise IGDeadEnd("Instagram phone wall without email escape — dead end")
            if self._native_live(p, low, url):
                self.log('[✔] IG native signup live.')
                return self._native_settle(p)

            # --- phone wall WITH the email escape ----------------------------
            if "what's your mobile number" in low and "sign up with email" in low:
                self._tap_text(p, ("Sign up with email",))
                p.wait_for_timeout(2500)
                continue
            # --- email -------------------------------------------------------
            # Order matters: fill -> tap Next FIRST (IG sends the code on
            # Next), THEN the delivery wait. Waiting before the tap left a
            # filled form staring at an enabled Next for 25s (operator
            # report 2026-09-28).
            if self._native_on_email(low):
                if not email_sent:
                    if not self._fill_first(p, ('input[name="email"]', 'input[type="email"]',
                                                'input[inputmode="email"]', 'input[autocomplete="email"]',
                                                'input[type="text"]'), email):
                        self._try_fill(p, "Email", email, timeout=6000)
                    email_sent = True
                if email_taps < 2:
                    email_taps += 1
                    self._tap_text(p, ("Next",))
                    if email_taps == 1:
                        # Delivery window: the bot reads a SHARED mailbox —
                        # give IG time to deliver before the first Get-code
                        # press, or the bot returns someone else's/previous
                        # code ("invalid or expired").
                        self.log('[✉️] Email submitted — waiting 25s for IG delivery before Get-code…')
                        p.wait_for_timeout(25000)
                p.wait_for_timeout(2500)
                continue
            # --- code --------------------------------------------------------
            if "enter the confirmation code" in low or "confirmation code" in low:
                if codes_tried >= max_codes:
                    raise RuntimeError("email code rejected 3× (stale mailbox?) — refusing to hammer Next")
                if self._native_code_rejected(low):
                    self.log('[⚠️] IG rejected the code ("invalid or expired") — fetching a FRESH one…')
                if request_code is None:
                    raise RuntimeError("no code source (bot Get-code) for native signup")
                # Freshness rule: the bot's shared mailbox can re-issue the
                # SAME (someone else's/previous) code — never submit a code
                # twice. A duplicate means newer mail hasn't landed yet: wait
                # 20s and re-press (bounded; then abort, don't burn TTL).
                fresh = ""
                for _gp in range(3):
                    c = (request_code() or "").strip()
                    if re.fullmatch(r"\d{6}", c or "") and c not in tried_codes:
                        fresh = c
                        break
                    self.log(f'[⚠️] bot re-issued {"nothing" if not c else "a repeat code"} — '
                             f'waiting 20s for newer mail (try {_gp + 1}/3)…')
                    p.wait_for_timeout(20000)
                if not fresh:
                    raise RuntimeError("bot keeps returning the same/old code — mailbox race, aborting")
                tried_codes.add(fresh)
                codes_tried += 1
                inp_loc = None
                for sel in ('input[name="confirmationCode"]', 'input[inputmode="numeric"]',
                            'input[type="tel"]', 'input[name="email_confirmation_code"]', 'input[type="text"]'):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            inp_loc = el
                            break
                    except Exception:
                        continue
                if inp_loc:
                    if hasattr(self, "_human_type"):
                        self._human_type(inp_loc, fresh)
                    else:
                        self._clean_fill(p, inp_loc, fresh, timeout=6000)
                    try:
                        inp_loc.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", fresh)
                    except Exception:
                        pass
                    try:
                        inp_loc.press("Enter")
                    except Exception:
                        pass
                else:
                    self._fill_first(p, ('input[name="confirmationCode"]', 'input[inputmode="numeric"]',
                                         'input[type="tel"]', 'input[type="text"]'), fresh)
                if hasattr(self, "_human_pause"):
                    self._human_pause(0.2, 0.4)
                self._tap_text(p, ("Next", "Continue"))
                self.log(f'[✉️] Confirmation code {fresh} submitted — waiting for screen to advance…')
                for _sec in range(25):
                    p.wait_for_timeout(1000)
                    try:
                        cur_low = (p.inner_text("body") or "").lower()
                    except Exception:
                        cur_low = ""
                    if any(s in cur_low for s in ("what's your name", "create a username",
                                                 "password", "birthday", "birth date",
                                                 "save your login info", "agree to instagram")):
                        self.log(f'[✔] Screen advanced past confirmation code in {_sec + 1}s.')
                        break
                    if self._native_code_rejected(cur_low):
                        self.log('[⚠️] IG explicitly rejected the confirmation code.')
                        break
                    if _sec in (6, 12, 18):
                        self._tap_text(p, ("Next", "Continue"))
                continue
            # --- name --------------------------------------------------------
            if "what's your name" in low:
                fn_val = first_name or "Alex Smith"
                if not self._fill_first(p, ('input[name="fullName"]', 'input[placeholder*="Name" i]',
                                            'input[type="text"]'), fn_val):
                    self._try_fill(p, "Full name", fn_val, timeout=5000)
                self._tap_text(p, ("Next",))
                p.wait_for_timeout(3000)
                continue
            # --- username (task REQUIRES the bot login — never keep a suggestion)
            if "create a username" in low or "add a username" in low:
                self._native_set_username(p, login)
                p.wait_for_timeout(2500)
                self._tap_text(p, ("Next",))
                p.wait_for_timeout(3500)
                continue
            # --- password ----------------------------------------------------
            if self._native_on_password(low):
                self._fill_first(p, ('input[type="password"]', 'input[name="password"]'), password)
                self._tap_text(p, ("Next",))
                p.wait_for_timeout(3500)
                continue
            # --- birthday ----------------------------------------------------
            if "birthday" in low or "birth date" in low or "birthdate" in low:
                self._native_set_dob(p, dob)
                self._tap_text(p, ("Next",))
                p.wait_for_timeout(3500)
                continue
            # --- consent -----------------------------------------------------
            if "agree to instagram" in low or "allow the following" in low:
                self._tap_text(p, ("I agree", "Allow and continue"))
                p.wait_for_timeout(5000)
                continue
            # --- save-login modal --------------------------------------------
            if "save your login info" in low or "save login info" in low:
                self._tap_text(p, ("Not now", "Save"))
                p.wait_for_timeout(2000)
                continue
            # --- optional add-phone (has Skip; NOT the wall) ------------------
            if "add phone number" in low and "adding your number" in low:
                self._tap_text(p, ("Skip",))
                p.wait_for_timeout(2000)
                continue
            p.wait_for_timeout(2000)

        raise RuntimeError("native signup loop exhausted without reaching the feed")

    # -- helpers (screen predicates + micro-actions) -------------------------
    def _native_front_door(self, p) -> bool:
        """Walk homepage -> signup taps; True once a signup screen shows."""
        for entry in (IG_HOME, IG_LOGIN):
            try:
                p.goto(entry, wait_until="domcontentloaded", timeout=60000)
                p.wait_for_timeout(3000)
            except Exception:
                continue
            for _ in range(4):
                try:
                    low = (p.inner_text("body") or "").lower()
                except Exception:
                    low = ""
                if ("what's your mobile number" in low or "what's your email" in low
                        or "enter the confirmation code" in low
                        or "enter the email where you can be contacted" in low):
                    return True
                # Cookie wall first (it covers the entry buttons).
                if not self._tap_text(p, ("Allow all cookies", "Only allow essential cookies")):
                    if self._tap_text(p, ("Create new account", "Sign up")):
                        self.log('[➡️] Native signup: tapped front-door entry.')
                    else:
                        p.wait_for_timeout(2000)
                        continue
                p.wait_for_timeout(3000)
        return False

    def _native_running(self) -> bool:
        try:
            w = getattr(self, "w", None)
            return bool(getattr(w, "is_running", True))
        except Exception:
            return True

    def _native_live(self, p, low: str, url: str) -> bool:
        try:
            names = {c.get("name") for c in self.w.context.cookies()}
        except Exception:
            names = set()
        if "sessionid" not in names:
            return False
        # If on human check or challenge page, not live yet
        if hasattr(self, "_has_human_check") and self._has_human_check(p):
            return False
        u = (url or "").lower()
        if "challenge" in u or "checkpoint" in u:
            return False
        return ("suggested for you" in low or "accounts/registered" in url
                or "/accounts/signup" not in url)

    def _native_phone_walled(self, p, low: str) -> bool:
        """Mandatory wall = phone screen with NO email escape."""
        return ("what's your mobile number" in low
                and "sign up with email" not in low)

    def _native_on_email(self, low: str) -> bool:
        return ("what's your email" in low or "enter the email where you can be contacted" in low)

    def _native_code_rejected(self, low: str) -> bool:
        return ("invalid or has expired" in low or "invalid or expired" in low
                or "wrong code" in low or "incorrect" in low)

    def _native_on_password(self, low: str) -> bool:
        return ("create a password" in low or "choose a password" in low
                or "set a password" in low)

    def _tap_text(self, p, names) -> bool:
        """Tap the first visible control whose exact text matches.

        Scans button/div[role=button]/a: the front-door "Sign up" entry and
        the registered-cards Back control both render as plain links.
        """
        want = {str(n).lower() for n in names}
        try:
            for loc in (p.locator("button"), p.locator('div[role="button"]'), p.locator("a")):
                try:
                    btns = loc.all()
                except Exception:
                    continue
                for b in btns:
                    try:
                        if (b.inner_text() or "").strip().lower() in want and b.is_visible():
                            if hasattr(self, "_human_pause"):
                                self._human_pause(0.2, 0.4)
                            if self._tap_or_click(p, b):
                                if hasattr(self, "_human_pause"):
                                    self._human_pause(0.2, 0.5)
                                return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def _fill_first(self, p, selectors, value) -> bool:
        for sel in selectors:
            try:
                el = p.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    if hasattr(self, "_human_type"):
                        self._human_type(el, str(value))
                    else:
                        self._clean_fill(p, el, str(value), timeout=6000)
                    return True
            except Exception:
                continue
        return False

    def _native_set_username(self, p, login: str) -> None:
        cur = ""
        try:
            u = p.get_by_role("textbox", name=re.compile("username", re.I)).first
            if u.count() > 0 and u.is_visible():
                try:
                    cur = u.input_value() or ""
                except Exception:
                    cur = ""
                if cur.strip().lower() != login.strip().lower():
                    if hasattr(self, "_human_type"):
                        self._human_type(u, login)
                    else:
                        self._clean_fill(p, u, login, timeout=8000)
                    self._dispatch_react_events(p, u)
                    self.log(f'[📝] Native signup username set to bot login "{login}" (was suggestion "{cur}").')
                return
        except Exception:
            pass
        self._fill_first(p, ('input[name="username"]', 'input[placeholder*="Username" i]'), login)

    def _native_set_dob(self, p, dob) -> None:
        """Set a Bloks ``input[type=date]`` the way its shadow segments listen.

        The segments reject programmatic clicks AND synthetic value sets (the
        parent carries ``pointer-events: none``; a JS-set value leaves the
        "0 years old" label and Next answers "wrong info"). Trusted arrow keys
        DO move the segments — but focus/segment order is unreliable, so every
        pass READS ``input.value``, computes the signed per-segment delta, and
        steps exactly that far, verifying afterwards (max 3 passes). Learned
        live 2026-09-28: blind arrow counts walk the date the wrong way.
        """
        import datetime as _dt
        want_y, want_m, want_d = int(dob[0]), int(dob[1]), int(dob[2])
        try:
            field = p.locator('input[type="date"]').first
            if field.count() == 0 or not field.is_visible():
                return
        except Exception:
            return
        for _pass in range(3):
            try:
                cur = (field.input_value() or "")[:10]
                cy, cm, cd = [int(x) for x in cur.split("-")]
            except Exception:
                return
            if (cy, cm, cd) == (want_y, want_m, want_d):
                break
            self.log(f'[🎂] Birthday now {cur} → want {want_y}-{want_m:02d}-{want_d:02d} (pass {_pass + 1}).')
            try:
                field.click(timeout=3000)
            except Exception:
                pass
            p.wait_for_timeout(300)
            # Month (Home = first segment), then day, then year — each call
            # re-reads and steps the short way round, verifying afterwards.
            self._native_step_segment(p, "Home", want_m, 1, 12, short=False)
            self._native_step_segment(p, None, want_d, 1, 31, short=False)
            self._native_step_segment(p, None, want_y, 1876, 2027, short=True)
            p.wait_for_timeout(400)
        try:
            cur = (field.input_value() or "")[:10]
        except Exception:
            cur = "?"
        self.log(f'[🎂] Native signup birthday set {cur}.')

    def _native_step_segment(self, p, home_key, want: int, lo: int, hi: int, short: bool) -> None:
        """Move the focused date segment to ``want`` (wrap-aware, verified)."""
        span = hi - lo + 1
        for _ in range(3):
            try:
                cur = (p.locator('input[type="date"]').first.input_value() or "")[:10]
                y, m, d = [int(x) for x in cur.split("-")]
            except Exception:
                return
            cur_v = (m if span == 12 else d) if not short else y
            if cur_v == want:
                return
            if home_key:
                try:
                    p.keyboard.press(home_key)
                except Exception:
                    pass
            # Step the short way round the wrap.
            fwd = (want - cur_v) % span
            key = "ArrowUp" if fwd <= span // 2 else "ArrowDown"
            steps = fwd if fwd <= span // 2 else span - fwd
            try:
                for _ in range(min(steps, span)):
                    p.keyboard.press(key)
                    p.wait_for_timeout(random.randint(70, 140))
                # Advance focus to the next segment for the following call.
                if not short:
                    p.keyboard.press("ArrowRight")
            except Exception:
                return

    def _native_settle(self, p) -> str:
        """Modal-first settle, then Back-out of the registered cards (never Skip)."""
        try:
            low = (p.inner_text("body") or "").lower()
        except Exception:
            low = ""
        if "save your login info" in low or "save login info" in low:
            self._tap_text(p, ("Not now", "Save"))
            p.wait_for_timeout(2000)
        try:
            if "/accounts/registered" in (p.url or ""):
                for sel in ('nav a[href="/"]', 'a[aria-label="Back"]', 'a:has-text("Back")'):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible() \
                                and "instagram" not in (el.inner_text() or "").lower():
                            if self._tap_or_click(p, el):
                                p.wait_for_timeout(4000)
                                break
                    except Exception:
                        continue
        except Exception:
            pass
        try:
            self.ig_dismiss_onboarding()
        except Exception:
            pass
        try:
            tail = self._page_tail(p, 300)
        except Exception:
            tail = ""
        self.log(f'[🏠] Native account on feed ({(p.url or "")[:60]}… | {tail[:80]})')
        return self._native_whoami(p)

    def _native_whoami(self, p) -> str:
        """Best-effort own-username read (profile link); "" when unknown."""
        for sel in ('a[href^="/"][aria-label*="profile" i]', 'nav a:last-child'):
            try:
                el = p.locator(sel).first
                if el.count() > 0:
                    href = (el.get_attribute("href") or "").strip("/")
                    if href and "/" not in href and "." not in href:
                        return href
            except Exception:
                continue
        return ""
