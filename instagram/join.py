"""Meta-link card dispatch, join wizard & onboarding dismissal. Mixed into MetaInstaRunner via InstagramFlowMixin; ``self`` provides run._MetaInstagramRunner helpers."""
from __future__ import annotations

import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from .helpers import IGDeadEnd
except ImportError:  # pragma: no cover - top-level import path
    from instagram.helpers import IGDeadEnd  # type: ignore

from ai_config import Urls  # noqa: E402


# Valid fallback display names — IG rejects names > 29 UTF-16 units
# ("Enter a name under 30 characters") and the Taskly first_name can be
# long/styled/gothic. Operator decision 2026-09-21: never stall the join on the
# NAME; substitute a random valid one.
_RANDOM_IG_NAMES = (
    "Alex Smith", "Maria Lopez", "David Brown", "Sara Miller", "John Carter",
    "Nina Patel", "Lucas Moore", "Emma Wilson", "Daniel Reed", "Laura Diaz",
)


def _random_ig_name() -> str:
    return random.choice(_RANDOM_IG_NAMES)


def _ig_name_too_long(s: str) -> bool:
    """IG counts **UTF-16 code units** (styled/astral letters = 2 each)."""
    try:
        return (len((s or "").encode("utf-16-le")) // 2) > 29
    except Exception:
        return len(s or "") > 29


class IgJoinMixin:
    """Meta-link card dispatch, join wizard & onboarding dismissal."""

    # Instagram's "What's your mobile number?" phone wall: the join landed on
    # the NATIVE signup branch (/accounts/signup/phone/) instead of the
    # Meta-linked wizard. A "recover by redirecting to login" attempt was tried
    # and REMOVED — measured 2026-09-23 (telegram_20260923_010221): 242 attempts,
    # 0 found the Meta-link dialog, i.e. pure overhead. The wall is a trust
    # signal, not a navigation one; abort immediately as before.
    def _phone_wall_present(self, p) -> bool:
        try:
            txt = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if "what's your mobile number" in txt:
                return True
            return p.get_by_text("What's your mobile number", exact=False).count() > 0
        except Exception:
            return False

    def ig_click_meta_card(self):
        """Handle the Meta-link dialog and click the `<Name>, Meta Horizon` card."""
        p = self._ig_tab()
        deadline = time.time() + 90
        n = 0
        while time.time() < deadline and self.w.is_running:
            if "sessionid" in self._ig_cookie_names() or "/accounts/login" not in p.url:
                return

            # DEAD END (ops): the bare saved-account chooser — profile named
            # after the email local part + "Use another profile"/"Create new
            # account" — means the Meta join never linked. Abort IMMEDIATELY
            # instead of swiping/re-tapping Log in for the full 90s.
            try:
                if self._is_ig_dead_end_chooser(p):
                    raise IGDeadEnd("IG saved-account chooser (logged out — session dropped) — dead end")
            except IGDeadEnd:
                raise
            except Exception:
                pass

            # Fast-fail checks: account rejected or phone wall -> quit immediately without waiting
            _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if "can't find account" in _text or p.get_by_text("Can't find account", exact=False).count() > 0:
                # Dynamic route: if the dialog offers Sign up / Create new account, click it to open the Meta link card!
                clicked_signup = False
                for loc in (
                    p.get_by_role("button", name="Sign up"),
                    p.get_by_text("Sign up", exact=True),
                    p.locator('button:has-text("Sign up")'),
                    p.locator('div[role="button"]:has-text("Sign up")'),
                    p.locator('span:has-text("Sign up")'),
                    p.get_by_role("button", name="Create new account"),
                    p.get_by_text("Create new account", exact=True),
                    p.locator('button:has-text("Create new account")'),
                    p.locator('div[role="button"]:has-text("Create new account")'),
                ):
                    try:
                        el = loc.first
                        if el.count() > 0 and el.is_visible():
                            try:
                                el.click(timeout=3000)
                            except Exception:
                                el.click(force=True, timeout=3000)
                            clicked_signup = True
                            self.log('[➡️] Clicked "Sign up" on "Can\'t find account" modal to open Meta link card.')
                            p.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass
                if not clicked_signup:
                    self.log('[❌] Instagram: "Can\'t find account" dialog — Meta credentials not recognized. Quitting immediately.')
                    raise RuntimeError("Instagram: Can't find account (Meta credentials rejected)")

            if self._phone_wall_present(p):
                self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting immediately.')
                raise RuntimeError("Instagram: Mobile number required (What's your mobile number)")

            if (
                self._visible(p, "button", "Find account") is not None
                or self._visible(p, "button", "Find another account") is not None
                or p.get_by_text("No Instagram account found", exact=False).count() > 0
                or p.get_by_text("No Instagram profile found", exact=False).count() > 0
                or p.locator('button:has-text("Find another account"), div[role="button"]:has-text("Find another account")').count() > 0
                or (self.email and p.get_by_text(self.email, exact=False).count() > 0)
                or p.get_by_text("Meta Horizon", exact=False).count() > 0
                or p.locator('[aria-label*="Meta Horizon"]').count() > 0
                or p.locator('button:has-text("Meta Horizon"), div[role="button"]:has-text("Meta Horizon")').count() > 0
            ):
                break
            p.wait_for_timeout(1500)
            n += 1
            # Modal may stall until swipe down + second Log in tap; mirror manual recovery
            if n % 2 == 0:
                try:
                    self._swipe_down(p)
                except Exception:
                    pass
                p.wait_for_timeout(800)
                try:
                    p.keyboard.press("Enter")
                    if self._click_ig_login_btn(p):
                        self.log('[🔗] Meta dialog missing — swiped down and re-tapped Log in.')
                except Exception:
                    pass

        self.log('[🔗] Instagram: Meta link dialog — clicking the Meta profile card…')
        clicked = False

        # Gather candidate name variations (prevent Telegram task name collision)
        names_to_try: list[str] = []
        meta_name = getattr(self, "meta_name", None)
        if meta_name and meta_name not in names_to_try:
            names_to_try.append(meta_name)
        if self.name and self.name not in names_to_try:
            names_to_try.append(self.name)
        first_name = getattr(self, "first", None)
        if first_name and first_name not in names_to_try:
            names_to_try.append(first_name)
        full_first_last = f"{getattr(self, 'first', '')} {getattr(self, 'last', '')}".strip()
        if full_first_last and full_first_last not in names_to_try:
            names_to_try.append(full_first_last)

        cand_patterns: list[str] = []
        for nm in names_to_try:
            cand_patterns.append(f"{nm}, Meta Horizon")
            cand_patterns.append(f"{nm} · Meta Horizon")
            cand_patterns.append(f"{nm} Meta Horizon")
        cand_patterns.append("Meta Horizon")
        for nm in names_to_try:
            cand_patterns.append(nm)

        click_deadline = time.time() + 15
        while time.time() < click_deadline and not clicked and self.w.is_running:
            # 0. Modern mobile bottom sheet: "View Meta account details for <email> (<name>)"
            for sel in (
                'button:has-text("View Meta account details")',
                'div[role="button"]:has-text("View Meta account details")',
                '[role="button"]:has-text("View Meta account details")',
                'button:has-text("View Meta account")',
                'div[role="button"]:has-text("View Meta account")',
            ):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        el.scroll_into_view_if_needed(timeout=2000)
                        if self._tap_or_click(p, el):
                            clicked = True
                            self.log(f'[🔗] Clicked Meta account details button: "{sel}"')
                            break
                except Exception:
                    pass
            if clicked:
                break

            # 1. Direct card match by email (exact, visible on modern card, e.g. media_1789618282467.png)
            if self.email:
                for sel in (
                    f'div[role="dialog"] div[role="button"]:has-text("{self.email}")',
                    f'div[role="dialog"] button:has-text("{self.email}")',
                    f'div[role="dialog"] [tabindex="0"]:has-text("{self.email}")',
                    f'div[role="button"]:has-text("{self.email}")',
                    f'button:has-text("{self.email}")',
                    f'[role="button"]:has-text("{self.email}")',
                ):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            el.scroll_into_view_if_needed(timeout=2000)
                            if self._tap_or_click(p, el):
                                clicked = True
                                self.log(f'[🔗] Clicked Meta card container via email: "{sel}"')
                                break
                    except Exception:
                        pass
                if not clicked:
                    try:
                        el = p.get_by_text(self.email, exact=False).first
                        if el.count() > 0 and el.is_visible():
                            el.scroll_into_view_if_needed(timeout=2000)
                            if self._tap_or_click(p, el):
                                clicked = True
                                self.log(f'[🔗] Clicked Meta card via email text: "{self.email}"')
                                break
                    except Exception:
                        pass

            # 2. Match by candidate name variations
            if not clicked:
                for nm in names_to_try:
                    for sel in (
                        f'div[role="dialog"] div[role="button"]:has-text("{nm}")',
                        f'div[role="dialog"] button:has-text("{nm}")',
                        f'div[role="dialog"] [tabindex="0"]:has-text("{nm}")',
                        f'div[role="button"]:has-text("{nm}")',
                        f'button:has-text("{nm}")',
                        f'[role="button"]:has-text("{nm}")',
                    ):
                        try:
                            el = p.locator(sel).first
                            if el.count() > 0 and el.is_visible():
                                el.scroll_into_view_if_needed(timeout=2000)
                                if self._tap_or_click(p, el):
                                    clicked = True
                                    self.log(f'[🔗] Clicked Meta card by name: "{nm}"')
                                    break
                        except Exception:
                            pass
                    if clicked:
                        break

            # 3. DOM geometry extraction: find interactive card inside dialog below "OR"
            if not clicked:
                try:
                    coords = p.evaluate('''() => {
                        const dialog = document.querySelector('div[role="dialog"]') || document.body;
                        const items = Array.from(dialog.querySelectorAll('button, div[role="button"], [tabindex="0"], div[role="link"], a'));
                        for (const item of items) {
                            const txt = (item.innerText || '').trim();
                            const low = txt.toLowerCase();
                            if (
                                low.includes('find another account') ||
                                low.includes('find account') ||
                                low === 'cancel' ||
                                low === 'close' ||
                                low === 'or'
                            ) {
                                continue;
                            }
                            const rect = item.getBoundingClientRect();
                            if (rect.width > 50 && rect.height > 20) {
                                return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: txt};
                            }
                        }
                        return null;
                    }''')
                    if coords and "x" in coords and "y" in coords:
                        card_txt = (coords.get("text") or "").replace("\n", " ")[:50]
                        self.log(f'[🔗] Found dialog card via DOM geometry: "{card_txt}" at ({coords["x"]}, {coords["y"]})')
                        try:
                            p.touchscreen.tap(coords["x"], coords["y"])
                            clicked = True
                        except Exception:
                            try:
                                p.mouse.click(coords["x"], coords["y"])
                                clicked = True
                            except Exception:
                                pass
                except Exception:
                    pass

            # 4. Try explicit name + Meta Horizon combinations
            if not clicked:
                for cand in cand_patterns:
                    try:
                        for sel in (
                            f'button:has-text("{cand}")',
                            f'div[role="button"]:has-text("{cand}")',
                            f'[role="button"]:has-text("{cand}")',
                            f'div[role="dialog"] [tabindex="0"]:has-text("{cand}")',
                        ):
                            el = p.locator(sel).first
                            if el.count() > 0 and el.is_visible():
                                el.scroll_into_view_if_needed(timeout=2000)
                                if self._tap_or_click(p, el):
                                    clicked = True
                                    self.log(f'[🔗] Clicked Meta card: "{cand}"')
                                    break
                        if clicked:
                            break
                    except Exception:
                        pass

            # 5. Generic dialog card option that is NOT Find account or cancel
            if not clicked:
                for sel in (
                    'div[role="dialog"] div[role="button"]:not(:has-text("Find")):not(:has-text("Cancel"))',
                    'div[role="dialog"] button:not(:has-text("Find")):not(:has-text("Cancel"))',
                    'div[role="dialog"] [tabindex="0"]:not(:has-text("Find"))',
                ):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            el.scroll_into_view_if_needed(timeout=2000)
                            if self._tap_or_click(p, el):
                                clicked = True
                                self.log(f'[🔗] Clicked primary card in dialog via "{sel}"')
                                break
                    except Exception:
                        pass

            if not clicked:
                p.wait_for_timeout(1000)

        if not clicked:
            self.log('[⚠️] Meta card not found in dialog.')
        p.wait_for_timeout(5000)

    def ig_complete_join(self):
        """Complete the Meta-to-Instagram join wizard (Full Name, Username, Consent, Terms)."""
        p = self._ig_tab()

        # Fast-fail check: phone wall or account rejection -> quit immediately
        _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
        if self._phone_wall_present(p):
            self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting immediately.')
            raise RuntimeError("Instagram: Mobile number required (What's your mobile number)")
        if "can't find account" in _text or p.get_by_text("Can't find account", exact=False).count() > 0:
            self.log('[❌] Instagram: "Can\'t find account" detected. Quitting immediately.')
            raise RuntimeError("Instagram: Can't find account")

        # 1. "What's your name?" (prefer TG bot first_name)
        desired_name = (self.tg_creds.get("first_name") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "name", None)
        name_input = None
        for _ in range(6):
            _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if "what's your name" in _text or "full name" in _text:
                for sel in ('input[name="fullName"]', 'input[name="name"]', 'input[aria-label*="name" i]', 'input[placeholder*="name" i]'):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            name_input = el
                            break
                    except Exception:
                        pass
                if not name_input:
                    try:
                        tb = p.get_by_role("textbox", name="Full name").first
                        if tb.count() > 0 and tb.is_visible():
                            name_input = tb
                    except Exception:
                        pass
                if name_input:
                    break
            elif "create a username" in _text or "username" in _text or "allow the following" in _text or "terms and policies" in _text:
                break
            p.wait_for_timeout(1000)

        if name_input or p.get_by_role("textbox", name="Full name").count() > 0:
            nm = desired_name
            if not nm or _ig_name_too_long(nm):
                nm = _random_ig_name()
                self.log(f'[📝] Name {desired_name!r} missing/too long — using random "{nm}".')
            if nm:
                self.log(f'[📝] Setting Full name during onboarding: "{nm}"')
                target_inp = name_input or p.get_by_role("textbox", name="Full name").first
                try:
                    self._human_type(target_inp, nm)
                    self._dispatch_react_events(p, target_inp)
                except Exception:
                    self._clean_fill(p, target_inp, nm, timeout=6000)
                self.name = nm

            # Advance beyond Name screen
            for _ in range(5):
                clicked_next = False
                for sel in ('button:has-text("Next")', 'div[role="button"]:has-text("Next")', '[aria-label="Next"]'):
                    try:
                        btn = p.locator(sel).first
                        if btn.count() > 0 and btn.is_visible() and not btn.is_disabled():
                            btn.scroll_into_view_if_needed(timeout=2000)
                            self._tap_or_click(p, btn)
                            clicked_next = True
                            break
                    except Exception:
                        pass
                p.wait_for_timeout(2000)
                _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
                if "what's your name" not in _text:
                    break
                if not clicked_next and name_input:
                    try:
                        name_input.press("Enter")
                    except Exception:
                        pass

        # 2. "Create a username" (prefer TG bot login / desired username)
        desired_user = (self.tg_creds.get("login") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "new_username", None)
        user_input = None
        for _ in range(6):
            _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if "create a username" in _text or "add a username" in _text:
                for sel in ('input[name="username"]', 'input[aria-label*="Username" i]', 'input[placeholder*="Username" i]'):
                    try:
                        el = p.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            user_input = el
                            break
                    except Exception:
                        pass
                if not user_input:
                    try:
                        tb = p.get_by_role("textbox", name="Username").first
                        if tb.count() > 0 and tb.is_visible():
                            user_input = tb
                    except Exception:
                        pass
                if user_input:
                    break
            elif "allow the following" in _text or "agree to instagram" in _text or "terms and policies" in _text:
                break
            p.wait_for_timeout(1000)

        if user_input or p.get_by_role("textbox", name="Username").count() > 0:
            target_user_inp = user_input or p.get_by_role("textbox", name="Username").first

            def _check_username_rejected() -> tuple[bool, str]:
                _t = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 800)).lower()
                taken_markers = (
                    "is not available", "isn't available", "already taken", "not available",
                    "already exists", "using the same username", "try another", "choose another",
                    "already in use", "user with that username", "another account is using",
                    "not able to use this username", "username unavailable"
                )
                invalid_markers = (
                    "only include", "only use", "can only", "can't contain",
                    "can't use", "invalid character", "must be between", "valid username"
                )
                if any(x in _t for x in taken_markers):
                    return True, "taken"
                if any(x in _t for x in invalid_markers):
                    return True, "invalid"
                try:
                    if target_user_inp.count() and target_user_inp.get_attribute("aria-invalid") == "true":
                        return True, "aria_invalid"
                except Exception:
                    pass
                return False, ""

            # Attempt setting username (up to 8 attempts via fresh TG tasks, keeping Meta session intact)
            for uname_attempt in range(8):
                cand_user = (self.tg_creds.get("login") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "new_username", None) or self.username or "user"
                self.log(f'[📝] Setting Username during onboarding (attempt {uname_attempt + 1}/8): "{cand_user}"')

                # Fill input cleanly
                try:
                    target_user_inp.click(force=True, timeout=3000)
                    target_user_inp.fill("")
                    p.wait_for_timeout(200)
                    self._human_type(target_user_inp, cand_user)
                    self._dispatch_react_events(p, target_user_inp)
                except Exception:
                    self._clean_fill(p, target_user_inp, cand_user, timeout=8000)
                self.ig_username = cand_user

                # Wait for Instagram availability check to resolve
                p.wait_for_timeout(3000)

                rejected, reason = _check_username_rejected()

                if not rejected:
                    # Attempt to advance via Next button
                    clicked_next = False
                    for sel in ('button:has-text("Next")', 'div[role="button"]:has-text("Next")', '[aria-label="Next"]'):
                        try:
                            btn = p.locator(sel).first
                            if btn.count() > 0 and btn.is_visible() and not btn.is_disabled():
                                btn.scroll_into_view_if_needed(timeout=2000)
                                self._tap_or_click(p, btn)
                                clicked_next = True
                                break
                        except Exception:
                            pass
                    if not clicked_next:
                        try:
                            target_user_inp.press("Enter")
                        except Exception:
                            pass

                    # Verify if screen advanced
                    for _ in range(8):
                        p.wait_for_timeout(500)
                        _cur_t = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
                        if "create a username" not in _cur_t and "add a username" not in _cur_t:
                            break
                        rejected, reason = _check_username_rejected()
                        if rejected:
                            break

                _cur_t = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
                if "create a username" not in _cur_t and "add a username" not in _cur_t:
                    self.log(f'[✔] Username "{self.ig_username}" accepted by Instagram.')
                    break

                # Username rejected / could not advance: cancel TG task and get fresh one (ignoring first name)
                reason = reason or "taken"
                self.log(f'[⚠️] Username "{self.ig_username}" rejected by Instagram ({reason}) — canceling TG task to get replacement username (first name ignored)…')
                hook = getattr(self, "_on_username_taken", None)
                new_login = None
                if callable(hook):
                    try:
                        new_login = hook(reason, self.ig_username)
                    except Exception as exc:
                        self.log(f'[⚠️] Error requesting replacement TG task: {exc}')

                if new_login:
                    self.log(f'[🔁] Replacement TG task received with login="{new_login}". Retrying username field…')
                    p.wait_for_timeout(1500)
                    continue
                else:
                    self.log('[⚠️] TG bot replacement task not returned — mutating username with fresh suffix…')
                    base = re.sub(r'[\d_]+$', '', self.ig_username or "user") or "user"
                    fresh_uname = f"{base}_{random.randint(100, 99999)}"
                    if hasattr(self, "tg_creds") and isinstance(self.tg_creds, dict) and "login" in self.tg_creds:
                        self.tg_creds["login"] = fresh_uname
                    self.new_username = fresh_uname
                    self.username = fresh_uname
                    p.wait_for_timeout(1500)

        # 2b. "Create a password" if prompted during onboarding
        desired_pw = (self.tg_creds.get("password") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "new_password", None) or getattr(self, "password", None)
        for sel in ('input[name="password"]', 'input[type="password"]', 'input[aria-label*="Password" i]', 'input[placeholder*="Password" i]'):
            try:
                pw_el = p.locator(sel).first
                if pw_el.count() > 0 and pw_el.is_visible():
                    self.log(f'[🔑] Setting password during onboarding: {"*" * len(desired_pw or "")}')
                    try:
                        self._human_type(pw_el, desired_pw)
                        self._dispatch_react_events(p, pw_el)
                    except Exception:
                        self._clean_fill(p, pw_el, desired_pw, timeout=6000)
                    for sel_btn in ('button:has-text("Next")', 'div[role="button"]:has-text("Next")', '[aria-label="Next"]'):
                        try:
                            b = p.locator(sel_btn).first
                            if b.count() > 0 and b.is_visible() and not b.is_disabled():
                                b.scroll_into_view_if_needed(timeout=2000)
                                self._tap_or_click(p, b)
                                break
                        except Exception:
                            pass
                    p.wait_for_timeout(3000)
                    self.password = desired_pw
                    break
            except Exception:
                pass

        # 3. Meta Account Linking: "To create an Instagram account with your Meta account, allow the following"
        for _ in range(8):
            _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if "allow the following" in _text or "allow and continue" in _text or p.locator('button:has-text("Allow and continue"), div[role="button"]:has-text("Allow and continue")').count() > 0:
                for sel in (
                    'div[role="button"]:has-text("Allow and continue")',
                    'button:has-text("Allow and continue")',
                    '[aria-label="Allow and continue"]',
                ):
                    try:
                        btn = p.locator(sel).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.scroll_into_view_if_needed(timeout=2000)
                            self._tap_or_click(p, btn)
                            self.log('[✔] Instagram: "Allow and continue" clicked.')
                            p.wait_for_timeout(3500)
                            break
                    except Exception:
                        pass
                break
            elif "agree to instagram" in _text or "terms and policies" in _text or "i agree" in _text:
                break
            p.wait_for_timeout(1000)

        # 4. Terms & Policies: "Agree to Instagram's terms and policies" -> "I agree"
        for _ in range(8):
            _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if "agree to instagram" in _text or "terms and policies" in _text or "i agree" in _text or p.locator('button:has-text("I agree"), div[role="button"]:has-text("I agree")').count() > 0:
                for sel in (
                    'div[role="button"]:has-text("I agree")',
                    'button:has-text("I agree")',
                    '[aria-label="I agree"]',
                    'div[role="button"]:has-text("Agree")',
                    'button:has-text("Agree")',
                ):
                    try:
                        btn = p.locator(sel).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.scroll_into_view_if_needed(timeout=2000)
                            self._tap_or_click(p, btn)
                            self.log('[✔] Instagram: "I agree" clicked. Waiting for backend provisioning…')
                            # Instagram shows a loading spinner on "I agree" for ~8-15s
                            p.wait_for_timeout(6000)
                            break
                    except Exception:
                        pass
                break
            elif "/accounts/registered" in (p.url or "") or "sessionid" in self._ig_cookie_names():
                break
            p.wait_for_timeout(1000)

        # 5. Handle Post-Terms Transition (wait for provisioning to complete, dismiss Save modal, leave registered cards)
        ok = False
        deadline = time.time() + 60
        while time.time() < deadline and self.w.is_running:
            if "sessionid" in self._ig_cookie_names():
                ok = True
                break

            _text = (self._page_text(p) if hasattr(self, "_page_text") else self._page_tail(p, 600)).lower()
            if self._phone_wall_present(p):
                self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting immediately.')
                raise RuntimeError("Instagram: Mobile number required (What's your mobile number)")
            if "can't find account" in _text or p.get_by_text("Can't find account", exact=False).count() > 0:
                self.log('[❌] Instagram: "Can\'t find account" dialog detected. Quitting immediately.')
                raise RuntimeError("Instagram: Can't find account")

            # Check if still showing "I agree" or "Allow and continue"
            if "allow the following" in _text or "allow and continue" in _text:
                for sel in ('button:has-text("Allow and continue")', 'div[role="button"]:has-text("Allow and continue")'):
                    try:
                        b = p.locator(sel).first
                        if b.count() > 0 and b.is_visible():
                            self._tap_or_click(p, b)
                            p.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass
            if "agree to instagram" in _text or "terms and policies" in _text or "i agree" in _text:
                for sel in ('button:has-text("I agree")', 'div[role="button"]:has-text("I agree")'):
                    try:
                        b = p.locator(sel).first
                        if b.count() > 0 and b.is_visible():
                            self._tap_or_click(p, b)
                            p.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass

            # Modal: "Save your login info" / "Save your password"
            if "save your login info" in _text or "save login info" in _text or "save your password" in _text:
                for sel in ('button:has-text("Not now")', 'div[role="button"]:has-text("Not now")', '[aria-label="Not now"]'):
                    try:
                        sn_btn = p.locator(sel).first
                        if sn_btn.count() > 0 and sn_btn.is_visible():
                            self._tap_or_click(p, sn_btn)
                            self.log('[✔] Instagram: dismissed "Save your login info" (clicked "Not now").')
                            p.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass

            # /accounts/registered/ cards: click top-left Back button
            if "/accounts/registered" in (p.url or ""):
                clicked_back = False
                for back_sel in (
                    '[aria-label="Back"]',
                    'nav a[href="/"]',
                    'a[aria-label="Back"]',
                    'button[aria-label="Back"]',
                    'a:has-text("Back")',
                    'svg[aria-label="Back"]',
                ):
                    try:
                        b = p.locator(back_sel).first
                        if b.count() > 0 and b.is_visible():
                            if self._tap_or_click(p, b):
                                self.log(f'[✔] Clicked Back on registered cards via "{back_sel}".')
                                clicked_back = True
                                p.wait_for_timeout(2500)
                                break
                    except Exception:
                        pass
                if not clicked_back:
                    try:
                        p.goto(Urls.IG_HOME, wait_until="domcontentloaded", timeout=15000)
                        p.wait_for_timeout(2000)
                    except Exception:
                        pass

            # Interstitial "Get the Instagram app"
            if "get the instagram app" in _text or "open instagram" in _text:
                for sel in ('[aria-label="Back"]', 'button[aria-label="Back"]', 'a[aria-label="Back"]', 'a:has-text("Skip")', 'button:has-text("Skip")'):
                    try:
                        b = p.locator(sel).first
                        if b.count() > 0 and b.is_visible():
                            self._tap_or_click(p, b)
                            p.wait_for_timeout(1800)
                            break
                    except Exception:
                        pass

            # Optional "Add phone number"
            if "add phone number" in _text or "adding your number will help" in _text:
                for sel in ('a:has-text("Skip")', 'button:has-text("Skip")', 'div[role="button"]:has-text("Skip")'):
                    try:
                        b = p.locator(sel).first
                        if b.count() > 0 and b.is_visible():
                            self._tap_or_click(p, b)
                            p.wait_for_timeout(1200)
                            break
                    except Exception:
                        pass

            if "something went wrong" in _text:
                self._recover_something_went_wrong(p, max_attempts=1)

            p.wait_for_timeout(2000)

        if not ok:
            ok = self._ensure_ig_session(p)

        self.ig_username = self.ig_username or self.username
        if ok:
            self.log(f'<font color="#00FF00"><b>[✔] Instagram account created (session) ({self.ig_username}).</b></font>')
        else:
            self.log(f'[⚠️] Instagram join: no sessionid cookie yet (url={p.url}) '
                     '— continuing (Instagram will redirect if unusable).')

    def _ig_settled(self, p) -> bool:
        """True when the mobile feed is ready: bottom nav present, no onboarding
        overlay/modal. Used to skip dismissal passes entirely when the session
        is already clean (saves ~10-20s of pointless Skip passes)."""
        try:
            nav = False
            for sel in ('[aria-label="Profile"]', '[aria-label="Home"]', '[aria-label="Search"]',
                        '[aria-label="Explore"]', 'nav a[href="/"]', 'nav a:last-child',
                        'footer a:last-child', 'svg[aria-label="Home"]', 'svg[aria-label="Profile"]'):
                try:
                    e = p.locator(sel).first
                    if e.count() > 0 and e.is_visible():
                        nav = True
                        break
                except Exception:
                    continue
            if not nav:
                return False
            body = (p.inner_text("body") or "").lower()
            if any(k in body for k in (
                "find facebook friends", "connect to facebook", "sync contacts",
                "save your login info", "save info", "add profile photo",
                "welcome to instagram", "add to home screen", "get the instagram app",
                "turn on notifications",
            )):
                return False
            d = p.locator('[role="dialog"], div[aria-modal="true"]').first
            if d.count() > 0 and d.is_visible():
                return False
            return True
        except Exception:
            return False

    def ig_dismiss_onboarding(self, follow: bool = True):
        """Dismiss post-login onboarding prompts, meta_creator-style:

        1. 'Save your password' / 'Save your login info' -> 'Not now'.
        2. On the /accounts/registered/ onboarding cards ('Connect to Facebook',
           'Add a profile photo') -> click the TOP-LEFT BACK button to enter the
           feed directly. This is the whole point of the port: the old code
           hammered "Skip" pass after pass on the same card (4+ identical Skip
           taps — the most bot-like thing in the whole flow) and IG kept serving
           the same card. Back leaves it in ONE tap, like a real user.
        3. 'Add Instagram to your Home screen?' -> 'Cancel'.
        4. (DISABLED 2026-09-28) was: follow ~2 suggested profiles on the feed.
           The `ig_follow_suggested` implementation is kept but NOT called — see
           the re-enable note at the end of this method.

        Skip remains only for the 'Get the Instagram app' interstitial, where
        Back is not offered.

        ``follow=False`` suppresses step 4. The direct-login path
        (``instagram/login.py``) passes False on purpose: that call happens
        BEFORE the Meta card is joined, so the account has no feed and no
        suggestions yet — following there would burn the one-shot follow pass
        (``_ig_follow_done``) and the real post-join call would skip it.
        """
        p = self._ig_tab()
        # Fast path: if it's already settled, do NOT run a single dismissal pass.
        try:
            if self._ig_settled(p):
                self.log('[🏠] Instagram already settled — skipping onboarding passes.')
                if follow:
                    try:
                        self.ig_follow_suggested()
                    except Exception:
                        pass
                return
        except Exception:
            pass
        self.log('[🏠] Instagram: starting post-registration onboarding dismissal…')

        way_out_escapes = 0
        # Same-screen circuit breaker: hammering an identical overlay pass
        # after pass is bot-like AND slow (log showed 4+ identical Skip taps).
        # After 3 consecutive passes on the same screen, Escape once and stop
        # instead of clicking a 4th time.
        last_screen_key = ""
        same_screen_hits = 0
        for _ in range(8):
            # 0. Detect accidental Facebook redirect and recover immediately
            cur_url = p.url or ""
            if "facebook.com" in cur_url:
                self.log(f'[⚠️] Detected navigation to Facebook ({cur_url[:60]}); returning to Instagram…')
                try:
                    p.goto(Urls.IG_HOME, wait_until="domcontentloaded", timeout=30000)
                    p.wait_for_timeout(3000)
                except Exception:
                    pass

            # 1. Fast sheet/interstitial dismissal via JS. NOTE: this already
            # runs `_recover_something_went_wrong` internally (helpers.py) —
            # do NOT call it again here (was a double recovery every pass).
            self._dismiss_ig_sheets(p)

            # 2b. Dead-end guard: the bare saved-account chooser means the Meta
            # join failed — discard this account (creator closes + next).
            try:
                if self._is_ig_dead_end_chooser(p):
                    raise IGDeadEnd("IG saved-account chooser (logged out — session dropped) — dead end")
            except IGDeadEnd:
                raise
            except Exception:
                pass

            # 3. Check if bottom navigation or home feed is fully rendered
            has_bottom_nav = False
            for nav_sel in ('[aria-label="Profile"]', '[aria-label="Home"]', 'nav a:last-child', 'footer a:last-child'):
                try:
                    n_el = p.locator(nav_sel).first
                    if n_el.count() > 0 and n_el.is_visible():
                        has_bottom_nav = True
                        break
                except Exception:
                    pass

            try:
                body_text = (p.inner_text("body") or "").lower()
            except Exception:
                body_text = ""

            # Guide "Way Out": trapped/challenged screens are escaped (max 2),
            # never hammered in place. Past that, fail fast with the state.
            if ("we suspect automated behavior" in body_text or "scraping_warning" in cur_url
                    or "something went wrong" in body_text):
                if way_out_escapes < 2:
                    way_out_escapes += 1
                    self._way_out_escape(p)
                    continue
                raise RuntimeError(
                    f"Instagram trapped after Way Out escapes (url={p.url}) | {self._page_tail(p)}")

            onboarding_keywords = (
                "find facebook friends", "connect to facebook", "sync contacts",
                "save your login info", "save info", "save your password", "add profile photo", "add photo",
                "welcome to instagram", "see who is on instagram",
                "add instagram to your home screen", "home screen", "add to home screen",
                "get the instagram app", "open instagram",
                "turn on notifications",
                "add phone number"
            )
            has_onboarding_overlay = any(k in body_text for k in onboarding_keywords)

            has_modal = False
            try:
                d = p.locator('[role="dialog"], div[aria-modal="true"]').first
                if d.count() > 0 and d.is_visible():
                    has_modal = True
            except Exception:
                pass

            # Carousel pin (fixed 2026-09-28): /accounts/registered/ renders
            # ALL cards' text at once, so whole-body keywords pinned this key
            # to "getapp" while the bot correctly advanced card-to-card — a
            # false Escape+break after 3 passes. On the registered path, key
            # on the visible card heading instead (Connect / photo / getapp /
            # phone each have a distinct h1), so real progress resets the
            # counter. Everywhere else the keyword chain below is unchanged.
            _card_head = ""
            if "/accounts/registered" in cur_url:
                try:
                    _h = p.locator('main h1, h1').first
                    if _h.count() > 0 and _h.is_visible():
                        _card_head = (_h.inner_text() or "").strip().lower()[:48]
                except Exception:
                    pass
            if "save your login info" in body_text or "save login info" in body_text or "save your password" in body_text:
                screen_key = "saveinfo"
            elif _card_head:
                screen_key = "card:" + _card_head
            elif "get the instagram app" in body_text or "open instagram" in body_text:
                screen_key = "getapp"
            elif "add phone number" in body_text:
                screen_key = "addphone"
            elif "home screen" in body_text:
                screen_key = "homescreen"
            elif "find facebook friends" in body_text or "connect to facebook" in body_text:
                screen_key = "fbconnect"
            else:
                screen_key = "other" if (has_modal or not has_bottom_nav) else "clean"
            if screen_key != "clean" and screen_key == last_screen_key:
                same_screen_hits += 1
            else:
                same_screen_hits = 0
            last_screen_key = screen_key
            if same_screen_hits >= 3:
                self.log(f'[⚠️] Onboarding stuck on "{screen_key}" 3 passes — Escape once, moving on…')
                try:
                    p.keyboard.press("Escape")
                    p.wait_for_timeout(1500)
                except Exception:
                    pass
                break

            if has_bottom_nav and not has_onboarding_overlay and not has_modal:
                self.log('[🏠] Bottom navigation detected with no onboarding overlay. Instagram session ready.')
                break

            dismissed = False

            # (B) "Save your login info to Instagram?" / "Save your password" bottom sheet / modal.
            # MUST RUN BEFORE (A0) registered card handling: the modal appears OVER
            # /accounts/registered/ cards and blocks pointer events to the Back link.
            if "save your login info" in body_text or "save login info" in body_text or "save your password" in body_text:
                self.log('[+] "Save your login info / password" dialog detected — clicking Not now / Save…')
                for sn_sel in (
                    'button:has-text("Not now")',
                    'div[role="button"]:has-text("Not now")',
                    'span:has-text("Not now")',
                    '[aria-label="Not now"]',
                    'button:has-text("Save")',
                    'div[role="button"]:has-text("Save")',
                    'button:has-text("Save info")',
                ):
                    try:
                        sn_btn = p.locator(sn_sel).first
                        if sn_btn.count() > 0 and sn_btn.is_visible():
                            self._tap_or_click(p, sn_btn)
                            self.log(f'[✔] Dismissed "Save your login info" via "{sn_sel}".')
                            p.wait_for_timeout(1500)
                            dismissed = True
                            break
                    except Exception:
                        pass
                if not dismissed:
                    try:
                        js_not_now = p.evaluate("""() => {
                            for (const el of document.querySelectorAll('button, div[role="button"], span, a')) {
                                const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                                if (t === 'not now' || t === 'save' || t === 'save info') {
                                    el.click(); return true;
                                }
                            }
                            return false;
                        }""")
                        if js_not_now:
                            self.log('[✔] Dismissed "Save your login info" via JS.')
                            p.wait_for_timeout(1500)
                            dismissed = True
                    except Exception:
                        pass
                if dismissed:
                    continue

            # (C) "Add Instagram to your Home screen?" modal / generic dialogs
            # MUST RUN BEFORE (A0) so any modal backdrop blocking the page is cleared.
            if "home screen" in body_text or has_modal:
                self.log('[+] Modal dialog detected ("Add to Home screen" / promo) — clicking Cancel / Not now…')
                try:
                    p.evaluate("""() => {
                        for (const el of document.querySelectorAll('button, div[role="button"], a, span, div[tabindex]')) {
                            const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                            if (t === 'cancel' || t === 'not now' || t === 'close' || t === 'dismiss') {
                                el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                                el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                try { el.click(); } catch(e) {}
                                const modal = el.closest('[role="dialog"], div[aria-modal="true"], ._a9-v');
                                if (modal) {
                                    modal.style.display = 'none';
                                    try { modal.remove(); } catch(e) {}
                                }
                                break;
                            }
                        }
                        const backdrops = document.querySelectorAll('div[style*="position: fixed"], div[style*="position: absolute"], ._a9-z, div[tabindex="-1"]');
                        for (const b of backdrops) {
                            const r = b.getBoundingClientRect();
                            if (r.width > 300 && r.height > 500) {
                                b.style.pointerEvents = 'none';
                                try { b.remove(); } catch(e) {}
                            }
                        }
                    }""")
                    dismissed = True
                except Exception:
                    pass

                for c_sel in (
                    'button:has-text("Cancel")',
                    'div[role="button"]:has-text("Cancel")',
                    'div:text-is("Cancel")',
                    'span:text-is("Cancel")',
                    'button:has-text("Not now")',
                    'div[role="button"]:has-text("Not now")',
                    '[aria-label="Close"]',
                ):
                    try:
                        c_btn = p.locator(c_sel).first
                        if c_btn.count() > 0 and c_btn.is_visible():
                            c_btn.click(force=True, timeout=500)
                            self.log(f'[+] Dismissed modal via "{c_sel}".')
                            dismissed = True
                            break
                    except Exception:
                        pass

                if not dismissed:
                    try:
                        p.keyboard.press("Escape")
                    except Exception:
                        pass

                if dismissed:
                    p.wait_for_timeout(400)
                    continue

            # (A0) /accounts/registered/ onboarding cards ('Connect to Facebook',
            # 'Add a profile photo'): click the TOP-LEFT BACK button to go
            # straight to the feed. Runs once modals are cleared.
            getapp = ("get the instagram app" in body_text or "open instagram" in body_text)
            has_back_link = False
            for _bsel in ('nav a[href="/"]', 'a[aria-label="Back"]', 'a:has-text("Back")'):
                try:
                    _bel = p.locator(_bsel).first
                    if _bel.count() > 0 and _bel.is_visible():
                        _bt = (_bel.inner_text() or "").strip().lower()
                        if "instagram" not in _bt:
                            has_back_link = True
                            break
                except Exception:
                    pass
            is_card = (
                "/accounts/registered" in cur_url
                or (not has_bottom_nav and (
                    "connect to facebook" in body_text
                    or "find facebook friends" in body_text
                    or "add a profile photo" in body_text)))
            is_card = is_card and (has_back_link or not getapp)
            if is_card:
                self.log('[⬅️] Onboarding card detected — clicking top-left Back (never Skip here)…')
                clicked_back = False
                for back_sel in (
                    '[aria-label="Back"]',
                    'button[aria-label="Back"]',
                    'a[aria-label="Back"]',
                    'a[href="/"]',
                    'a:has-text("Back")',
                    'button:has-text("Back")',
                    'svg[aria-label="Back"]',
                    'a[href="https://www.instagram.com/"]',
                ):
                    try:
                        b_el = p.locator(back_sel).first
                        if b_el.count() > 0 and b_el.is_visible():
                            if self._tap_or_click(p, b_el):
                                self.log(f'[✔] Clicked top-left Back via "{back_sel}" — entering the feed.')
                                clicked_back = True
                                p.wait_for_timeout(2500)
                                if "/accounts/registered" in (p.url or ""):
                                    self.log('[⚠️] Back did not leave the card — trying the next control…')
                                    clicked_back = False
                                break
                    except Exception:
                        pass
                if not clicked_back:
                    try:
                        p.goto(Urls.IG_HOME, wait_until="domcontentloaded", timeout=15000)
                        self.log('[⬅️] No working Back control — loaded the feed directly.')
                        clicked_back = True
                        p.wait_for_timeout(2000)
                    except Exception:
                        pass
                if clicked_back:
                    last_screen_key = ""
                    same_screen_hits = 0
                    continue

            # (A) "Get the Instagram app" interstitial screen
            if "get the instagram app" in body_text or "open instagram" in body_text:
                self.log('[+] "Get the Instagram app" screen — trying top-left Back, else Skip…')
                for back_sel in ('[aria-label="Back"]', 'button[aria-label="Back"]',
                                 'a[aria-label="Back"]', 'svg[aria-label="Back"]'):
                    try:
                        b = p.locator(back_sel).first
                        if b.count() > 0 and b.is_visible():
                            if self._tap_or_click(p, b):
                                self.log(f'[⬅️] Clicked Back on "Get the Instagram app" via "{back_sel}" — entering the feed.')
                                p.wait_for_timeout(1800)
                                dismissed = True
                                break
                    except Exception:
                        pass
                for skip_sel in (
                    'a:has-text("Skip")',
                    'button:has-text("Skip")',
                    'div[role="button"]:has-text("Skip")',
                    'span:has-text("Skip")',
                    '[aria-label="Skip"]',
                ):
                    if dismissed:
                        break
                    try:
                        b = p.locator(skip_sel).first
                        if b.count() > 0 and b.is_visible():
                            self._tap_or_click(p, b)
                            self.log(f'[✔] Clicked Skip on "Get the Instagram app" via "{skip_sel}".')
                            p.wait_for_timeout(1500)
                            dismissed = True
                            break
                    except Exception:
                        pass
                if not dismissed:
                    try:
                        js_skip = p.evaluate("""() => {
                            for (const el of document.querySelectorAll('a, button, div[role="button"], span')) {
                                if ((el.innerText || el.textContent || '').trim().toLowerCase() === 'skip') {
                                    el.click(); return true;
                                }
                            }
                            return false;
                        }""")
                        if js_skip:
                            self.log('[✔] Clicked Skip on "Get the Instagram app" via JS.')
                            p.wait_for_timeout(1500)
                            dismissed = True
                    except Exception:
                        pass
                if dismissed:
                    continue

            # (E) Standard onboarding buttons
            for label in ("Not now", "Cancel", "Save", "Skip", "Dismiss", "Done"):
                try:
                    b = p.locator(f'button:has-text("{label}"), div[role="button"]:has-text("{label}")').first
                    if b.count() > 0 and b.is_visible():
                        txt = (b.inner_text() or "").lower()
                        if "facebook" in txt:
                            continue
                        self._tap_or_click(p, b)
                        self.log(f'[+] Dismissed onboarding screen: "{label}".')
                        p.wait_for_timeout(1500)
                        dismissed = True
                        break
                except Exception:
                    pass
                if dismissed:
                    break

            if not dismissed:
                break

        # 5. Natural feed settle and suggested profiles warm-up
        if follow:
            try:
                self._touch_scroll(p, dy=random.randint(320, 520))
                self._human_pause(1.5, 3.0)
                self.ig_follow_suggested()
            except IGDeadEnd:
                raise
            except Exception as exc:
                self.log(f'[⚠️] Note on feed warm-up: {exc}')
        self.log('[🏠] Instagram session ready.')

    def ig_follow_suggested(self, max_follows: int = 2, humanize: bool = False):
        """Follow ~2 suggested accounts on the home feed, right after login.

        ── CURRENTLY DISABLED (2026-09-28, operator request) ─────────────────
        This method is KEPT INTACT but is no longer CALLED. To bring the follow
        step back, re-add the two calls in ``ig_dismiss_onboarding`` — each one
        is marked with a "FOLLOW STEP DISABLED" note showing the exact lines.
        Nothing else needs to change; this implementation is untouched.
        ──────────────────────────────────────────────────────────────────────

        Ported verbatim-in-spirit from the verified meta_creator flow
        (``meta_creator/instagram/join.py::ig_follow_suggested``): a real new
        account follows a couple of people before it ever touches settings, and
        driving a brand-new IG account STRAIGHT into Accounts Center is its
        strongest automation tell (observed 2026-09-21: the AC route bounced to
        /accounts/login/?__coig_login=1, API require_login). So this is the
        warm-up that replaced the old feed-SCROLL settle — following, not
        scrolling.

        Selector strategy is meta_creator's: find `…:has-text("Follow")` and
        require the label to be EXACTLY "Follow", so "Following" / "Follow back"
        / "Unfollow" rows are never tapped. Best-effort by design (invariant
        #20: no duplicate guards, no second gate) — it never raises and never
        blocks the flow; a renamed rail just means 0 follows.

        Tunables: INSTA_FOLLOW_AFTER_LOGIN=0 disables, INSTA_FOLLOW_COUNT
        overrides the count (default 2).
        """
        if str(os.environ.get("INSTA_FOLLOW_AFTER_LOGIN", "1")).strip().lower() in (
                "0", "false", "no", "off"):
            self.log('[👥] Post-login follow pass disabled (INSTA_FOLLOW_AFTER_LOGIN=0).')
            return 0
        # ig_dismiss_onboarding() can be called twice per cycle (once at the end
        # of the direct-login helper, once by the pipeline after the Meta card).
        # The flag is set only once the pass is actually viable — a bail-out on
        # "no sessionid" must NOT burn it, or the real post-join call would skip
        # the follow entirely.
        if getattr(self, "_ig_follow_done", False):
            self.log('[👥] Follow pass already ran this cycle — skipping the duplicate.')
            return 0
        try:
            max_follows = int(os.environ.get("INSTA_FOLLOW_COUNT", "") or max_follows or 2)
        except Exception:
            max_follows = 2
        if max_follows <= 0:
            return 0
        try:
            # `_ig_tab()` itself can raise (page/browser closed), so it lives
            # INSIDE the try: this step is best-effort and must never abort the
            # cycle (invariant #20).
            p = self._ig_tab()
            # Operator decision (2026-09-27): do NOT gate the follow pass on the
            # sessionid cookie. "Just follow." The old `sessionid` check skipped
            # the warm-up on accounts that were still perfectly usable, and the
            # only state that should stop us is Instagram REDIRECTING to its
            # "Confirm you're human to use your profile" checkpoint — which is
            # detected right after this pass (and in tg_coupled) as a dead end.
            # The tap is best-effort either way: on a dead page it simply does
            # nothing and the check that follows reports the real reason.
            if "instagram.com" not in (p.url or ""):
                self.log(f'[👥] Not on Instagram ({p.url}) — skipping the follow pass.')
                return 0
            self._ig_follow_done = True
            self.ig_followed_count = 0
            p.wait_for_timeout(1500)

            # Any lingering "Add to Home screen"-style dialog goes first.
            for cancel_sel in ('button:has-text("Cancel")', 'div[role="button"]:has-text("Cancel")',
                               '[aria-label="Cancel"]'):
                try:
                    c_btn = p.locator(cancel_sel).first
                    if c_btn.count() > 0 and c_btn.is_visible():
                        self._tap_or_click(p, c_btn)
                        self.log('[+] Dismissed a lingering modal via Cancel (follow pass).')
                        p.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            followed = 0
            # Light warm-up only — a real user pauses a beat. NO big scrolls:
            # follow from the FIRST suggested profile and continue to the next.
            if humanize:
                self._human_pause(0.3, 0.8)
            _empty = 0
            for _ in range(10):
                if followed >= max_follows:
                    break
                tapped = False
                # Collect visible EXACT-"Follow" buttons IN ORDER. Playwright's
                # :has-text is a substring match, so "Follow" also selects
                # "Following" / "Follow back" — the exact-label test is the filter.
                cands = []
                for sel in ('button:has-text("Follow"):not(:has-text("Following"))',
                            'div[role="button"]:has-text("Follow"):not(:has-text("Following"))',
                            'a[role="button"]:has-text("Follow"):not(:has-text("Following"))'):
                    try:
                        btns = p.locator(sel)
                        cnt = btns.count()
                    except Exception:
                        continue
                    for i in range(cnt):
                        try:
                            btn = btns.nth(i)
                            if not btn.is_visible():
                                continue
                            if (btn.inner_text() or "").strip() != "Follow":
                                continue
                            cands.append(btn)
                        except Exception:
                            pass
                for btn in cands:
                    if followed >= max_follows:
                        break
                    try:
                        if not btn.is_visible():
                            continue
                        btn.scroll_into_view_if_needed(timeout=2000)
                        if not self._tap_or_click(p, btn):
                            continue
                        # Dead-end guard: a "Failed to Load." toast right after a
                        # Follow tap means the account is broken — abort and let
                        # the caller jump to the NEXT account.
                        p.wait_for_timeout(random.uniform(700, 1300))
                        try:
                            _tail = (p.inner_text("body") or "").lower()
                        except Exception:
                            _tail = ""
                        if "failed to load" in _tail:
                            raise IGDeadEnd("follow 'Failed to Load' toast — dead end")
                        tapped = True
                        followed += 1
                        self.log(f'[👥] Followed suggested profile ({followed}/{max_follows}).')
                        # Short pause only — enough for IG to flip the button to
                        # "Following" server-side — then continue to the next.
                        p.wait_for_timeout(random.uniform(500, 900))
                        break
                    except IGDeadEnd:
                        raise
                    except Exception:
                        pass
                if not tapped:
                    # Next row may be just below the fold: ONE small nudge, then
                    # re-collect. If TWO consecutive passes find NO Follow button
                    # at all, there is nothing more to follow — end the pass EARLY
                    # instead of scrolling through the whole loop (the "stuck
                    # after 2 follows" case).
                    _empty += 1
                    if _empty >= 2:
                        self.log('[👥] No more suggested Follow buttons — ending the follow pass early.')
                        break
                    try:
                        self._touch_scroll(p, dy=random.randint(160, 340))
                    except Exception:
                        pass
                    p.wait_for_timeout(random.uniform(350, 700))
                else:
                    _empty = 0

            self.log(f'[👥] Follow pass complete: followed {followed} suggested account(s).')
            try:
                self.ig_followed_count = int(followed)
            except Exception:
                pass
            return followed
        except IGDeadEnd:
            # A "Failed to Load." toast is a genuine dead end — let the caller
            # close/purge and move to the next account. Do NOT swallow it.
            raise
        except Exception as exc:
            self.log(f'[⚠️] Note on follow suggested: {exc}')
            return 0
