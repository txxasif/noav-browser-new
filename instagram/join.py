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
                    raise IGDeadEnd("IG saved-account chooser with the bare email profile — Meta join failed")
            except IGDeadEnd:
                raise
            except Exception:
                pass

            # Fast-fail checks: account rejected or phone wall -> quit immediately without waiting
            _tail = self._page_tail(p, 400).lower()
            if "can't find account" in _tail or p.get_by_text("Can't find account", exact=False).count() > 0:
                self.log('[❌] Instagram: "Can\'t find account" dialog — Meta credentials not recognized. Quitting immediately.')
                raise RuntimeError("Instagram: Can't find account (Meta credentials rejected)")

            if "what's your mobile number" in _tail or p.get_by_text("What's your mobile number", exact=False).count() > 0:
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
        """Complete the Meta-to-Instagram join wizard (Full Name, Username, Consent)."""
        p = self._ig_tab()

        # Fast-fail check: phone wall or account rejection -> quit immediately
        _tail = self._page_tail(p, 400).lower()
        if "what's your mobile number" in _tail or p.get_by_text("What's your mobile number", exact=False).count() > 0:
            self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting immediately.')
            raise RuntimeError("Instagram: Mobile number required (What's your mobile number)")
        if "can't find account" in _tail or p.get_by_text("Can't find account", exact=False).count() > 0:
            self.log('[❌] Instagram: "Can\'t find account" detected. Quitting immediately.')
            raise RuntimeError("Instagram: Can't find account")

        # 1. "What's your name?" (prefer TG bot first_name)
        desired_name = (self.tg_creds.get("first_name") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "name", None)
        name_input = None
        for _ in range(5):
            for sel in ('input[name="fullName"]', 'input[name="name"]', 'input[aria-label*="name" i]', 'input[placeholder*="name" i]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        name_input = el
                        break
                except Exception:
                    pass
            if name_input or self._visible(p, "textbox", "Full name") is not None or self._visible(p, "textbox", "Name") is not None:
                break
            tail = self._page_tail(p, 300).lower()
            if "username" in tail or "agree" in tail or "allow" in tail:
                break
            p.wait_for_timeout(1500)

        if name_input or self._visible(p, "textbox", "Full name") is not None or self._visible(p, "textbox", "Name") is not None:
            # IG rejects names > 29 UTF-16 units; the Taskly first_name can be
            # long/styled. Never stall on the NAME — substitute a random valid
            # one (operator 2026-09-21).
            nm = desired_name
            if not nm or _ig_name_too_long(nm):
                nm = _random_ig_name()
                self.log(f'[📝] Name {desired_name!r} missing/too long — using random "{nm}".')
            if nm:
                self.log(f'[📝] Setting Full name during onboarding: "{nm}"')
                if name_input:
                    self._clean_fill(p, name_input, nm, timeout=6000)
                    self._dispatch_react_events(p, name_input)
                else:
                    if not self._try_fill(p, "Full name", nm, timeout=4000):
                        self._try_fill(p, "Name", nm, timeout=4000)
                self.name = nm
            # If the field still shows a length error, refill with a random name.
            try:
                _ntail = self._page_tail(p, 300).lower()
            except Exception:
                _ntail = ""
            if "under 30 characters" in _ntail or "enter a name" in _ntail:
                nm = _random_ig_name()
                self.log(f'[📝] Name rejected by IG — retrying with random "{nm}".')
                if name_input:
                    self._clean_fill(p, name_input, nm, timeout=6000)
                    self._dispatch_react_events(p, name_input)
                else:
                    self._try_fill(p, "Full name", nm, timeout=4000)
                self.name = nm
            # Ensure we advance beyond the Name screen
            for _ in range(4):
                for sel in ('button:has-text("Next")', 'div[role="button"]:has-text("Next")', '[aria-label="Next"]'):
                    try:
                        btn = p.locator(sel).first
                        if btn.count() > 0 and btn.is_visible() and not btn.is_disabled():
                            btn.scroll_into_view_if_needed(timeout=2000)
                            self._tap_or_click(p, btn)
                            break
                    except Exception:
                        pass
                p.wait_for_timeout(2000)
                tail = self._page_tail(p, 300).lower()
                if "what's your name" not in tail:
                    break
                try:
                    (name_input or p.get_by_role("textbox", name="Full name").first).press("Enter")
                except Exception:
                    pass

        # 2. "Create a username for Instagram" (prefer TG bot login)
        desired_user = (self.tg_creds.get("login") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "new_username", None)
        user_input = None
        for _ in range(5):
            for sel in ('input[name="username"]', 'input[aria-label*="Username" i]', 'input[placeholder*="Username" i]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        user_input = el
                        break
                except Exception:
                    pass
            if user_input or self._visible(p, "textbox", "Username") is not None:
                break
            tail = self._page_tail(p, 300).lower()
            if "agree" in tail or "allow" in tail or "password" in tail:
                break
            p.wait_for_timeout(1500)

        if user_input or self._visible(p, "textbox", "Username") is not None:
            if desired_user:
                self.log(f'[📝] Setting Username during onboarding: "{desired_user}"')
                if user_input:
                    self._clean_fill(p, user_input, desired_user, timeout=8000)
                    self._dispatch_react_events(p, user_input)
                else:
                    self._try_fill(p, "Username", desired_user, timeout=8000)
                self.ig_username = desired_user
            else:
                try:
                    self.ig_username = (
                        user_input.input_value() if user_input else p.get_by_role("textbox", name="Username").first.input_value()
                    )
                except Exception:
                    self.ig_username = self.username

            # Wait for Instagram's debounced availability/format check, then handle
            # rejections WITHOUT killing the run:
            #   taken   -> "is not available" / "isn't available"
            #   invalid -> "Usernames can only include numbers, letters…" ("only include")
            # A TG-task hook (runner._on_username_taken) may cancel the bot task
            # and supply a fresh login; the field is refilled in place and the
            # check re-runs. Without a hook (or when it gives up) we fall back
            # to clicking an IG suggestion as before.
            for _urej in range(4):
                p.wait_for_timeout(2500)
                tail = self._page_tail(p, 400).lower()
                taken = "not available" in tail or "isn't available" in tail or "already taken" in tail
                invalid = any(x in tail for x in (
                    "only include", "only use", "can only", "can't contain",
                    "can't use", "invalid character", "must be between", "valid username"
                ))
                if not taken and not invalid:
                    break
                reason = "invalid" if invalid else "taken"
                self.log(f'[⚠️] Username "{self.ig_username}" rejected by Instagram ({reason}).')
                hook = getattr(self, "_on_username_taken", None)
                new_login = None
                if callable(hook):
                    try:
                        new_login = hook(reason, self.ig_username)
                    except Exception as exc:
                        self.log(f'[⚠️] username hook error: {exc}')
                if new_login:
                    self.log(f'[🔁] Retrying username screen with fresh TG login: "{new_login}"')
                    desired_user = new_login
                    self.ig_username = new_login
                    if user_input:
                        self._clean_fill(p, user_input, new_login, timeout=8000)
                        self._dispatch_react_events(p, user_input)
                    else:
                        self._try_fill(p, "Username", new_login, timeout=8000)
                    continue
                self.log(f'[⚠️] No fresh login available; selecting suggestion…')
                break

            # Check if "not available" or invalid format appeared
            tail = self._page_tail(p, 400).lower()
            if "not available" in tail or "isn't available" in tail or "already taken" in tail or any(x in tail for x in (
                "only include", "only use", "can only", "can't contain",
                "can't use", "invalid character", "must be between", "valid username"
            )):
                self.log(f'[⚠️] Username "{self.ig_username}" is not available/valid on Instagram. Selecting suggestion…')
                picked = p.evaluate("""(badUser) => {
                    const allEls = Array.from(document.querySelectorAll('*'));
                    const candidates = allEls.filter(el => {
                        if (!el.innerText) return false;
                        const t = el.innerText.trim();
                        if (t.includes('\\n') || t.includes(' ') || t.toLowerCase() === badUser.toLowerCase()) return false;
                        if (t.toLowerCase().includes('available') || t.toLowerCase().includes('username') || t.toLowerCase().includes('next') || t.toLowerCase().includes('create')) return false;
                        return /^[a-zA-Z0-9._]{3,30}$/.test(t);
                    });
                    for (const c of candidates) {
                        const r = c.getBoundingClientRect();
                        if (r.width > 20 && r.height > 15) {
                            c.click();
                            return c.innerText.trim();
                        }
                    }
                    return null;
                }""", str(self.ig_username or desired_user or ""))
                if picked:
                    self.log(f'[💡] Clicked Instagram username suggestion: "{picked}"')
                    self.ig_username = picked
                else:
                    # Fallback: parse suggested username tokens directly from body text
                    body_txt = p.inner_text("body") or ""
                    prefix = (desired_user or "")[:4]
                    all_tokens = re.findall(rf"\b{prefix}[a-zA-Z0-9._]+\b", body_txt)
                    valid_suggs = [t for t in all_tokens if t.lower() != (desired_user or "").lower() and "available" not in t.lower()]
                    if valid_suggs:
                        chosen = valid_suggs[0]
                        self.log(f'[💡] Selected Instagram username from suggestions list: "{chosen}"')
                        if user_input:
                            self._clean_fill(p, user_input, chosen, timeout=6000)
                            self._dispatch_react_events(p, user_input)
                        self.ig_username = chosen
                    else:
                        # Append digits if no suggestions found
                        rnd_user = f"{(desired_user or 'user')[:18]}{random.randint(10, 99)}"
                        self.log(f'[💡] Appending digits to username: "{rnd_user}"')
                        if user_input:
                            self._clean_fill(p, user_input, rnd_user, timeout=6000)
                            self._dispatch_react_events(p, user_input)
                        self.ig_username = rnd_user
                p.wait_for_timeout(2000)

            # Loop to click Next and advance beyond the Username screen
            for _ in range(5):
                tail = self._page_tail(p, 300).lower()
                if "create a username" not in tail and "add a username" not in tail:
                    break
                try:
                    p.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                except Exception:
                    pass
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
                if not clicked_next and user_input:
                    try:
                        user_input.press("Enter")
                    except Exception:
                        pass
                p.wait_for_timeout(2500)

        # 2b. "Create a password" if prompted during onboarding
        desired_pw = (self.tg_creds.get("password") if hasattr(self, "tg_creds") and self.tg_creds else None) or getattr(self, "new_password", None) or getattr(self, "password", None)
        for sel in ('input[name="password"]', 'input[type="password"]', 'input[aria-label*="Password" i]', 'input[placeholder*="Password" i]'):
            try:
                pw_el = p.locator(sel).first
                if pw_el.count() > 0 and pw_el.is_visible():
                    self.log(f'[🔑] Setting password during onboarding: {"*" * len(desired_pw or "")}')
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
                    p.wait_for_timeout(4000)
                    self.password = desired_pw
                    break
            except Exception:
                pass

        # 3. Consent & Terms: "Agree to Instagram's terms and policies" / "Allow and continue"
        for _ in range(6):
            clicked_step = False
            tail = self._page_tail(p, 400).lower()

            # (a) "Agree to Instagram's terms and policies" -> "I agree"
            if "agree to instagram" in tail or "terms and policies" in tail or "i agree" in tail:
                for sel in (
                    'div[role="button"]:has-text("I agree")',
                    'button:has-text("I agree")',
                    '[aria-label="I agree"]',
                    'div[role="button"]:has-text("Agree")',
                    'button:has-text("Agree")',
                ):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        self.log('[✔] Instagram: "I agree" (terms and policies) clicked.')
                        clicked_step = True
                        p.wait_for_timeout(4000)
                        break

            # (b) "To create an Instagram account with your Meta account, allow the following" -> "Allow and continue"
            if "allow the following" in tail or "allow and continue" in tail:
                for sel in (
                    'div[role="button"]:has-text("Allow and continue")',
                    'button:has-text("Allow and continue")',
                    '[aria-label="Allow and continue"]',
                ):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        self.log('[✔] Instagram: "Allow and continue" clicked.')
                        clicked_step = True
                        p.wait_for_timeout(4000)
                        break

            if not clicked_step:
                p.wait_for_timeout(1500)

        # 4. Wait for full session (sessionid)
        ok = False
        deadline = time.time() + 60
        while time.time() < deadline and self.w.is_running:
            if "sessionid" in self._ig_cookie_names():
                ok = True
                break
            tail = self._page_tail(p, 400).lower()
            if "what's your mobile number" in tail or p.get_by_text("What's your mobile number", exact=False).count() > 0:
                self.log('[❌] Instagram: "What\'s your mobile number?" phone wall detected. Quitting immediately.')
                raise RuntimeError("Instagram: Mobile number required (What's your mobile number)")
            if "can't find account" in tail or p.get_by_text("Can't find account", exact=False).count() > 0:
                self.log('[❌] Instagram: "Can\'t find account" dialog detected. Quitting immediately.')
                raise RuntimeError("Instagram: Can't find account")
            if "agree to instagram" in tail or "terms and policies" in tail or "i agree" in tail:
                for sel in (
                    'div[role="button"]:has-text("I agree")',
                    'button:has-text("I agree")',
                    '[aria-label="I agree"]',
                    'div[role="button"]:has-text("Agree")',
                    'button:has-text("Agree")',
                ):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        self.log('[✔] Instagram: "I agree" clicked.')
                        p.wait_for_timeout(3000)
                        break
            if "allow the following" in tail or "allow and continue" in tail:
                for sel in (
                    'div[role="button"]:has-text("Allow and continue")',
                    'button:has-text("Allow and continue")',
                ):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        p.wait_for_timeout(3000)
                        break
            # Interstitial "Get the Instagram app" -> strictly click "Skip"
            if "get the instagram app" in tail or "open instagram" in tail:
                for sel in ('a:has-text("Skip")', 'button:has-text("Skip")', 'div[role="button"]:has-text("Skip")', '[aria-label="Skip"]'):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        self.log('[✔] Instagram: clicked "Skip" on "Get the Instagram app".')
                        p.wait_for_timeout(2500)
                        break
            # Interstitial "Save your login info" -> click "Not now" or "Save"
            if "save your login info" in tail or "save login info" in tail:
                for sel in ('button:has-text("Not now")', 'div[role="button"]:has-text("Not now")', 'button:has-text("Save")'):
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self._tap_or_click(p, btn)
                        self.log('[✔] Instagram: dismissed "Save your login info".')
                        p.wait_for_timeout(2000)
                        break
            if "something went wrong" in tail:
                self._recover_something_went_wrong(p, max_attempts=1)
            p.wait_for_timeout(2000)
        if not ok:
            ok = self._ensure_ig_session(p)

        self.ig_username = self.ig_username or self.username
        if ok:
            self.log(f'<font color="#00FF00"><b>[✔] Instagram account created (session) ({self.ig_username}).</b></font>')
        else:
            self.log(f'[⚠️] Instagram join incomplete (url={p.url}) | {self._page_tail(p)}')
            raise RuntimeError(f"Instagram onboarding did not complete: no sessionid cookie (url={p.url})")

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

    def ig_dismiss_onboarding(self):
        """Dismiss post-login onboarding prompts ('Save info', 'Not now', 'Skip', Facebook friend sync)."""
        p = self._ig_tab()
        # Fast path: if it's already settled, do NOT run a single dismissal pass.
        try:
            if self._ig_settled(p):
                self.log('[🏠] Instagram already settled — skipping onboarding passes.')
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
                    raise IGDeadEnd("IG saved-account chooser with the bare email profile — Meta join failed")
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
                "save your login info", "save info", "add profile photo", "add photo",
                "welcome to instagram", "see who is on instagram",
                "add instagram to your home screen", "home screen", "add to home screen",
                "get the instagram app", "open instagram",
                "turn on notifications", "notifications"
            )
            has_onboarding_overlay = any(k in body_text for k in onboarding_keywords)

            has_modal = False
            try:
                d = p.locator('[role="dialog"], div[aria-modal="true"]').first
                if d.count() > 0 and d.is_visible():
                    has_modal = True
            except Exception:
                pass

            if "get the instagram app" in body_text or "open instagram" in body_text:
                screen_key = "getapp"
            elif "save your login info" in body_text or "save login info" in body_text:
                screen_key = "saveinfo"
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
                return

            dismissed = False

            # (A) "Get the Instagram app" interstitial screen (Screenshot 2)
            # Strictly click "Skip", never click "Open Instagram"
            if "get the instagram app" in body_text or "open instagram" in body_text:
                self.log('[+] "Get the Instagram app" screen detected — strictly clicking Skip…')
                for skip_sel in (
                    'a:has-text("Skip")',
                    'button:has-text("Skip")',
                    'div[role="button"]:has-text("Skip")',
                    'span:has-text("Skip")',
                    '[aria-label="Skip"]',
                ):
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

            # (B) "Save your login info to Instagram?" bottom sheet modal (Screenshot 3)
            if "save your login info" in body_text or "save login info" in body_text:
                self.log('[+] "Save your login info" dialog detected — clicking Not now / Save…')
                for sn_sel in (
                    'button:has-text("Not now")',
                    'div[role="button"]:has-text("Not now")',
                    '[aria-label="Not now"]',
                    'button:has-text("Save")',
                    'div[role="button"]:has-text("Save")',
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
                if dismissed:
                    continue

            # (C) "Add Instagram to your Home screen?" modal (Screenshot 4)
            if "home screen" in body_text or has_modal:
                self.log('[+] Modal dialog detected ("Add to Home screen" / promo) — clicking Cancel…')
                try:
                    p.evaluate("""() => {
                        for (const el of document.querySelectorAll('button, div[role="button"], a, span, div[tabindex]')) {
                            const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                            if (t === 'cancel') {
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

            # (D) Facebook connect / sync prompts — strictly skip
            if "facebook" in body_text:
                self.log('[+] Facebook connect prompt detected — actively skipping…')
                for skip_sel in (
                    'div[role="button"]:has-text("Skip")',
                    'button:has-text("Skip")',
                    'a:has-text("Skip")',
                    'span:has-text("Skip")',
                    '[aria-label="Skip"]',
                    'div[role="button"]:has-text("Not now")',
                    'button:has-text("Not now")',
                ):
                    try:
                        btn = p.locator(skip_sel).first
                        if btn.count() > 0 and btn.is_visible():
                            self._tap_or_click(p, btn)
                            self.log(f'[+] Dismissed Facebook prompt via "{skip_sel}".')
                            p.wait_for_timeout(1500)
                            dismissed = True
                            break
                    except Exception:
                        pass
                if dismissed:
                    continue

            # (E) Standard onboarding buttons
            for label in ("Skip", "Not now", "Cancel", "Save", "Dismiss", "Done"):
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

        self.log('[🏠] Instagram session ready.')
