"""engine.eng_mix_signup — legacy auth.meta.com signup wizard.

Verbatim slice from ``engine/run.py`` ``_MetaInstagramRunner`` (no logic change).
Mixed into :class:`engine._MetaInstagramRunner`; ``self`` provides the other
engine helpers (same browser session invariant unchanged). Zero local-repo
dependencies (``store`` only via function-local lazy import).
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import _META_AI_APEX, _META_AI_URL  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _META_AI_APEX, _META_AI_URL  # noqa: E402

class EngineSignupMixin:
    @staticmethod
    def _sanitize_display_name(name: str, fallback: str = "Alex") -> str:
        """Strip non-display characters (math symbols like ×, emojis, digits, symbols) keeping valid name letters and spaces."""
        if not name:
            return fallback
        import unicodedata
        s = str(name)
        if not any(unicodedata.category(c).startswith("L") for c in s):
            return fallback
        leetspeak = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"}
        chars = []
        for ch in s:
            if ch in leetspeak:
                chars.append(leetspeak[ch])
                continue
            cat = unicodedata.category(ch)
            if cat.startswith("L"):
                chars.append(ch)
            elif ch in ("'", "-"):
                chars.append(ch)
            else:
                chars.append(" ")
        cleaned = re.sub(r"\s+", " ", "".join(chars)).strip()
        cleaned = cleaned.strip("-' ")
        if len(cleaned) < 2:
            return fallback
        if cleaned.islower():
            cleaned = cleaned.title()
        return cleaned

    def meta_signup(self):
        p = self.page
        if getattr(self, "name", None):
            self.name = self._sanitize_display_name(self.name)
        self.log('[🌐] Opening Meta account signup…')

        # Low-fraud funnel first; meta.ai modal entry on retry (never a bare
        # auth.meta.com goto — that renders a different registration variant
        # without the modal waterfall/state).
        try:
            funnel_ok = self.meta_ai_signup_funnel(p)
        except Exception:
            funnel_ok = False

        if not funnel_ok:
            # Retry through the same modal entry the funnel uses (www, then
            # apex) so the block below clicks modal "Sign up" like manual.
            landed = False
            for entry_url in (_META_AI_URL, _META_AI_APEX):
                try:
                    p.goto(entry_url, wait_until="domcontentloaded", timeout=60000)
                    p.wait_for_timeout(3000)
                except Exception:
                    continue
                try:
                    cur_u = (p.url or "").lower()
                    body = (p.inner_text("body") or "").lower()
                except Exception:
                    continue
                if "meta.ai" in cur_u and (
                    "sign in to get started" in body
                    or "where should we start" in body
                    or "what can i do for you" in body
                    or "sign up" in body
                ):
                    landed = True
                    break
                self.log('[⚠️] meta.ai entry did not render the modal; trying alternate entry…')
            if not landed:
                if "meta.ai" in (p.url or ""):
                    raise RuntimeError("Meta entry stalled on meta.ai (IP throttled) — cooldown or retry")
                self.log('[⚠️] meta.ai entries did not render; continuing anyway (fail-fast below will judge).')

        if funnel_ok:
            clicked_email_btn = True
        else:
            # Check if the page is rendering the Meta AI modal (as in media_1789619105619.png)
            for _ in range(3):
                tail = (p.inner_text("body") or "").lower()
                if "sign in to get started" in tail or "log in or sign up to ask meta ai" in tail or "where should we start" in tail:
                    self.log('[🌐] Detected "Sign in to get started" modal — clicking "Sign up"…')
                    clicked_modal_signup = False
                    for sel in (
                        'div[role="dialog"] button:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                        'div[role="dialog"] [role="button"]:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                        'div[role="dialog"] a:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                        'div[role="dialog"] div:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                        'button:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                        'div[role="button"]:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                        'a:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))',
                    ):
                        try:
                            el = p.locator(sel).first
                            if el.count() > 0 and el.is_visible():
                                try:
                                    href = el.get_attribute("href")
                                    if href and href.startswith("http"):
                                        if self._is_ig_or_fb_url(href):
                                            self.log('[⚠️] "Sign up" link points to Instagram/Facebook — skipping (want Meta signup).')
                                        else:
                                            p.goto(href)
                                            clicked_modal_signup = True
                                            break
                                except Exception:
                                    pass
                                if not self._tap_or_click(p, el):
                                    el.click(force=True)
                                clicked_modal_signup = True
                                self.log(f'[✔] Clicked modal "Sign up" via {sel}')
                                break
                        except Exception:
                            pass
                    if not clicked_modal_signup:
                        try:
                            p.evaluate("""() => {
                                for (const el of document.querySelectorAll('button, div[role="button"], a, span')) {
                                    if ((el.innerText || '').trim().toLowerCase() === 'sign up') {
                                        el.click(); return true;
                                    }
                                }
                                return false;
                            }""")
                        except Exception:
                            pass
                    p.wait_for_timeout(3500)
                    if self._is_ig_bounce_url(p.url):
                        self.log('[⚠️] "Sign up" bounced to Instagram — returning to the Meta entry.')
                        try:
                            p.goto(_META_AI_URL, wait_until="domcontentloaded", timeout=60000)
                            p.wait_for_timeout(2500)
                        except Exception:
                            pass
                        continue
                else:
                    break

            # A Meta signup must never continue on an Instagram page.
            if self._is_ig_bounce_url(p.url):
                raise RuntimeError(
                    "Meta signup bounced to Instagram (IP throttled / Meta gating) — "
                    "cooldown 5-10 min, lower creators to 1-2, retry")

            # Click "Use mobile number or email" (strictly ignore Facebook / Instagram buttons)
            self.log('[🌐] Selecting "Use mobile number or email"…')
            clicked_email_btn = False
        for _attempt in range(6):
            for sel in [
                'div[role="button"]:has-text("Use mobile number or email")',
                'button:has-text("Use mobile number or email")',
                'div[role="button"]:has-text("Use email")',
                'button:has-text("Use email")',
                '[aria-label*="mobile number or email" i]',
            ]:
                try:
                    el = p.locator(sel).first
                    if el.is_visible():
                        self._human_click(p, el, 4000)
                        clicked_email_btn = True
                        break
                except Exception:
                    pass
            if clicked_email_btn:
                break
            # Fallback by accessible role
            for btn_name in ["Use mobile number or email", "Use mobile number or email address", "Use email"]:
                if self._try_click(p, btn_name, timeout=2000):
                    clicked_email_btn = True
                    break
            if clicked_email_btn:
                break
            p.wait_for_timeout(1000)
        p.wait_for_timeout(2500)

        # Fill email
        filled_email = False
        for field_name in ["Mobile number or email", "Mobile number or email address", "Email", "mobile number"]:
            if self._try_fill(p, field_name, self.email, timeout=6000):
                filled_email = True
                break
        if not filled_email:
            try:
                inp = p.locator('input[type="email"], input[name*="email" i], input[name*="contact" i], input[autocomplete="email"], input[aria-label*="email" i], input[aria-label*="mobile" i], input[placeholder*="email" i]').first
                if inp.is_visible():
                    self._clean_fill(p, inp, self.email)
                    filled_email = True
            except Exception:
                pass
        if filled_email:
            self.log(f'[📧] Filled Meta email: {self.email}')
        else:
            self.log('[⚠️] Could not verify email field was populated.')

        # Strictly click Continue (exclude Facebook and Instagram buttons)
        clicked_continue = False
        try:
            continue_btn = p.locator('button:has-text("Continue"):not(:has-text("Facebook")):not(:has-text("Instagram")), div[role="button"]:has-text("Continue"):not(:has-text("Facebook")):not(:has-text("Instagram"))').first
            if continue_btn.is_visible():
                self._human_click(p, continue_btn, 6000)
                clicked_continue = True
        except Exception:
            pass
        if not clicked_continue:
            self._try_click(p, "Continue", timeout=6000)
        p.wait_for_timeout(4000)

        # Mobile: "Create a new Meta account?"
        self._try_click(p, "Create new account", timeout=6000)
        p.wait_for_timeout(2000)

        # Fail fast: after the email step Meta must render the next screen.
        # Throttled IPs hang here on a blank spinner; abort now instead of
        # sleepwalking through name/DOB/password into a doomed code wait.
        advanced = False
        for _ in range(10):
            # Abort the moment Meta bounces to Instagram — do not wait out the
            # full stall window on an Instagram error page.
            if self._is_ig_bounce_url(p.url):
                raise RuntimeError(
                    "Meta signup bounced to Instagram (IP throttled / Meta gating) — "
                    "cooldown 5-10 min, lower creators to 1-2, retry")
            try:
                tail = (p.inner_text("body") or "").lower()
            except Exception:
                tail = ""
            if any(k in tail for k in ("first name", "surname", "select day",
                                       "date of birth", "get started on meta",
                                       "we'll create your meta account", "save login info",
                                       "edit your meta", "i already have an account",
                                       "new password", "confirmation code",
                                       "create a new meta account", "save your login",
                                       "finish creating", "not now", "i agree",
                                       "key points you should know", "password")):
                advanced = True
                break
            p.wait_for_timeout(2000)
        if not advanced:
            try:
                tail = (p.inner_text("body") or "").strip().replace("\n", " ")[:160]
            except Exception:
                tail = ""
            raise RuntimeError(
                f"Meta signup stalled after email (page: '{tail}' / {p.url}) — "
                "likely throttled: cooldown, lower concurrency, retry")

        # Mobile: "What's your name?"
        if self._try_fill(p, "First name", self.first, timeout=20000):
            self.log(f'[⌨️] Name: {self.name}')
            filled_last = False
            for ln_field in ("Last name", "Surname", "last_name", "lastName"):
                if self._try_fill(p, ln_field, self.last, timeout=4000):
                    filled_last = True
                    break
            if not filled_last:
                try:
                    inputs = p.locator('input[type="text"]').all()
                    if len(inputs) >= 2:
                        self._clean_fill(p, inputs[1], self.last)
                except Exception:
                    pass
            self._advance(p, ["Next"], "textbox", "First name")
            p.wait_for_timeout(2000)

        # Date of birth
        if self._try_wait_combo(p, "Select day", timeout=15000):
            self.log(f'[🎂] DOB: {self.dob_year}-{self.dob_month}-{self.dob_day}')
            for _attempt in range(3):
                try:
                    self._combo(p, "Select day", self.dob_day)
                    self._combo(p, "Select month", self.dob_month)
                    self._combo(p, "Select year", self.dob_year)
                except Exception as exc:
                    self.log(f'[⚠️] DOB: {exc}')
                y_text = p.evaluate("""() => {
                    const el = document.querySelector('div[role="combobox"][aria-label*="year" i]');
                    return el ? (el.innerText || '') : '';
                }""")
                if self.dob_year in y_text or ("2026" not in y_text and len(y_text) > 0):
                    self.log(f'[🎂] DOB confirmed: {y_text.replace(chr(10), " ")}')
                    break
                p.wait_for_timeout(1000)
            # New "Get started" funnel: password lives on the SAME screen and
            # Next goes nowhere until it is filled — pre-fill before advancing.
            self._prefill_getstarted_password(p)
            self._advance(p, ["Next"], "combobox", "Select day")
            p.wait_for_timeout(2000)

        # Password (mobile "New password"; desktop "Password";
        # "Get started" funnel: unlabeled input filled directly)
        self.log('[🔑] Setting password…')
        if not self._try_fill(p, "New password", self.password, timeout=20000):
            if not self._try_fill(p, "Password", self.password, timeout=15000):
                self._prefill_getstarted_password(p)
        if not self._advance(p, ["Next", "Continue"], "textbox", "New password"):
            self._advance(p, ["Next", "Continue"], "textbox", "Password")
        p.wait_for_timeout(3000)
        self.log('[➡️] Password submitted.')

        # Mobile: "Save your login info?"
        if not self._try_click(p, "Not now", timeout=6000):
            self._try_click(p, "Save", timeout=4000)
        p.wait_for_timeout(3000)

        # Mobile: "Finish creating your Meta account"
        self._try_click(p, "Create account", timeout=8000)
        p.wait_for_timeout(5000)

        # Desktop-only: Meta AI username/name screen ("Edit your Meta AI details")
        has_details = False
        name_input = None
        for sel in (
            'input[aria-label*="Name (optional)" i]',
            'input[placeholder*="Name (optional)" i]',
            'input[name*="name" i]',
        ):
            try:
                inp = p.locator(sel).first
                if inp.count() > 0 and inp.is_visible():
                    name_input = inp
                    has_details = True
                    break
            except Exception:
                pass
        if not has_details:
            name_input = self._visible(p, "textbox", "Name (optional)") or self._visible(p, "textbox", "Name")
            if name_input is not None:
                has_details = True

        if has_details:
            # Name is optional: ALWAYS leave it blank and just Confirm. Filling
            # it buys nothing (IG takes the bot's name later) and triggers
            # "Display Name Has Invalid Characters" rejections + slow retries.
            self.log('[⌨️] Meta AI details: leaving optional Name blank, continuing…')
            try:
                cur = name_input.input_value()
            except Exception:
                cur = ""
            if cur:
                try:
                    name_input.click()
                    p.keyboard.press("Control+A")
                    p.keyboard.press("Backspace")
                    name_input.fill("")
                except Exception:
                    pass

            # Avatar upload. Probe first: some details variants carry no
            # photo picker, and expect_file_chooser would burn 10s waiting.
            try:
                _probe = p.locator('input[type="file"], button[aria-label*="photo" i], button[aria-label*="avatar" i], button[aria-label*="camera" i], button[aria-label*="profile picture" i]').first
                _has_picker = _probe.count() > 0 and _probe.is_visible()
            except Exception:
                _has_picker = False
            if _has_picker:
                try:
                    _sp = getattr(self, "selfie_path", None)
                    if _sp and os.path.exists(_sp):
                        with p.expect_file_chooser(timeout=8000) as _fc:
                            if not (
                                self._try_click(p, "Add profile photo", timeout=3000)
                                or self._try_click(p, "Add a profile photo", timeout=2000)
                                or self._try_click(p, "Edit", timeout=2000)
                            ):
                                try:
                                    if _probe.count() > 0 and _probe.is_visible():
                                        _probe.click(force=True, timeout=3000)
                                except Exception:
                                    pass
                        _fc.value.set_files(_sp)
                        p.wait_for_timeout(2500)
                        self.log('[🖼️] Details avatar uploaded.')
                except Exception as _exc:  # noqa: BLE001
                    self.log(f'[⚠️] Details avatar skipped: {_exc}')

            self._try_click(p, "Confirm", timeout=8000)
            p.wait_for_timeout(2500)

            # Detect and dynamically resolve errors on Meta AI details screen ("Display Name Has Invalid Characters" / Username)
            for check_attempt in range(4):
                body_tail = ""
                try:
                    body_tail = (p.inner_text("body") or "").lower()
                except Exception:
                    pass

                has_name_err = (
                    "display name has invalid characters" in body_tail
                    or "invalid characters" in body_tail
                )
                has_uname_err = (
                    "username" in body_tail
                    and ("not available" in body_tail or "invalid" in body_tail or "already taken" in body_tail)
                )

                if has_name_err:
                    self.log(f'[⚠️] Meta AI details: "Display Name Has Invalid Characters" detected (attempt {check_attempt + 1}/4) — clearing optional name field…')
                    try:
                        p.evaluate("""() => {
                            const err = Array.from(document.querySelectorAll('*')).find(el => 
                                (el.innerText || '').toLowerCase().includes('display name has invalid characters')
                            );
                            if (err) {
                                const parent = err.closest('div, form, label') || err.parentElement;
                                const inps = parent ? Array.from(parent.querySelectorAll('input')) : [];
                                for (const inp of inps) {
                                    inp.value = '';
                                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                                }
                            }
                            for (const inp of document.querySelectorAll('input')) {
                                const l = (inp.getAttribute('aria-label') || inp.placeholder || inp.name || '').toLowerCase();
                                if (l.includes('name') && !l.includes('user')) {
                                    inp.value = '';
                                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                                }
                            }
                        }""")
                    except Exception:
                        pass

                    try:
                        curr_name_inp = (
                            p.locator('input[aria-label*="Name" i], input[placeholder*="Name" i], input[name*="name" i]').first
                            if p.locator('input[aria-label*="Name" i], input[placeholder*="Name" i], input[name*="name" i]').count() > 0
                            else name_input
                        )
                        if curr_name_inp:
                            curr_name_inp.click()
                            p.keyboard.press("Control+A")
                            p.keyboard.press("Backspace")
                            curr_name_inp.fill("")
                            self.name = ""
                    except Exception:
                        pass

                    p.wait_for_timeout(1000)
                    self._try_click(p, "Confirm", timeout=6000)
                    p.wait_for_timeout(2500)

                    # If clearing name still doesn't resolve after 2 attempts, cancel task and swap
                    if check_attempt >= 2:
                        swap_hook = getattr(self, "_on_credentials_rejected", None) or getattr(self, "_on_username_taken", None)
                        if callable(swap_hook):
                            cur_uname = getattr(self, "username", "") or getattr(self, "new_username", "")
                            self.log('[⚠️] Meta AI details name error persistent — canceling task and getting fresh credentials…')
                            replacement = swap_hook("meta_display_name_rejected", cur_uname)
                            if replacement:
                                self.name = getattr(self, "name", "")
                                p.wait_for_timeout(1000)
                                self._try_click(p, "Confirm", timeout=6000)
                                p.wait_for_timeout(2500)
                    continue

                if has_uname_err:
                    self.log('[⚠️] Meta AI details: Username rejected on screen — requesting swap…')
                    swap_hook = getattr(self, "_on_credentials_rejected", None) or getattr(self, "_on_username_taken", None)
                    if callable(swap_hook):
                        cur_uname = getattr(self, "username", "") or getattr(self, "new_username", "")
                        replacement = swap_hook("meta_username_rejected", cur_uname)
                        if replacement:
                            try:
                                uname_inp = p.locator('input[aria-label*="Username" i], input[placeholder*="Username" i]').first
                                if uname_inp.is_visible():
                                    self._clean_fill(p, uname_inp, replacement)
                                    self._try_click(p, "Confirm", timeout=6000)
                                    p.wait_for_timeout(2500)
                                    continue
                            except Exception:
                                pass
                    break

                # If Confirm or details title is still visible, retry click
                try:
                    conf_btn = p.locator('button:has-text("Confirm"), div[role="button"]:has-text("Confirm")').first
                    if conf_btn.count() > 0 and conf_btn.is_visible():
                        self._tap_or_click(p, conf_btn, timeout=2000)
                        p.wait_for_timeout(2000)
                    else:
                        break
                except Exception:
                    break

        # Confirmation code
        self.log('[📨] Waiting for the email code screen…')
        cb = None
        deadline = time.time() + 60
        _last_beat = 0.0
        while time.time() < deadline and self.w.is_running:
            cb = (self._visible(p, "textbox", "Confirmation code")
                  or self._visible(p, "textbox", "Code"))
            if cb is not None:
                break
            # Heartbeat: log the live screen every ~10s so a slow/odd Meta
            # screen is VISIBLE in the log (and the run is not mistaken for a
            # hang). This is where signup stalled with no output before.
            if time.time() - _last_beat >= 10:
                _last_beat = time.time()
                try:
                    self.log(f'[📨] still waiting for code screen — url={(p.url or "")[:80]} | {self._page_tail(p, 120)}')
                except Exception:
                    pass
            p.wait_for_timeout(2000)
        if cb is None:
            raise RuntimeError("Meta confirmation code screen not found")
        code = self.fetch_code("meta", timeout=240)
        if not code:
            raise RuntimeError("Meta confirmation code not received")
        try:
            self.meta_code = code
        except Exception:
            pass
        self._human_type(p, cb, code, timeout=10000)
        if not self._advance(p, ["Next", "Continue"], "textbox", "Confirmation code"):
            self._advance(p, ["Next", "Continue"], "textbox", "Code")
        p.wait_for_timeout(6000)
        self.log('<font color="#00FF00"><b>[✔] Meta account confirmed.</b></font>')

        # Immediate persistence: save Meta account credentials immediately upon confirmation
        # so credentials are safe in SQLite, JSON, CSV and TXT even if downstream steps encounter issues.
        try:
            if hasattr(self, "save_ai_result"):
                self.save_ai_result(status="MetaCreated")
        except Exception as _save_err:
            self.log(f'[⚠️] Early store notice: {_save_err}')

        # Post-confirm: settle the redirect, then verify human ONLY on an
        # actual checkpoint redirect. A clean landing on meta.ai logged-in
        # home ("Where should we start?", composer, no sign-in modal) means
        # success — skip verification entirely (downstream
        # ensure_meta_verified re-checks anyway).
        try:
            try:
                self._poll_checkpoint_settled(p, timeout=20)
            except Exception:
                p.wait_for_timeout(4000)
            cur_url = (p.url or "").lower()
            try:
                cur_body = (p.inner_text("body") or "").lower()
            except Exception:
                cur_body = ""
            on_checkpoint = (
                "checkpoints" in cur_url or self._has_human_check(p)
            )
            if not on_checkpoint:
                meta_home = "meta.ai" in cur_url and (
                    "where should we start" in cur_body
                    or "what can i do for you" in cur_body
                    or "ask meta ai" in cur_body
                )
                modal_gone = ("sign in to get started" not in cur_body
                              and "log in or sign up to ask meta ai" not in cur_body)
                if meta_home and modal_gone:
                    self.log('<font color="#00FF00"><b>[✔] Meta session live on meta.ai — deferring to the checkpoint pass (human verification + selfie).</b></font>')
                    return
            # If a clean Continue/Next button is present (excluding Facebook/Instagram), advance
            try:
                cont_btn = p.locator('button:has-text("Continue"):not(:has-text("Facebook")):not(:has-text("Instagram")), div[role="button"]:has-text("Continue"):not(:has-text("Facebook")):not(:has-text("Instagram")), button:has-text("Next"):not(:has-text("Facebook")):not(:has-text("Instagram"))').first
                if cont_btn.is_visible():
                    self._human_click(p, cont_btn, 6000)
                    p.wait_for_timeout(3000)
            except Exception:
                pass
            if "checkpoints" in (p.url or "").lower() or self._has_human_check(p):
                self.log('[🌐] Meta human verification checkpoint detected (redirect)…')
                self._meta_selfie_checkpoint(p, timeout=300)
            else:
                self.log('[✔] No checkpoint visible yet — the checkpoint pass will drive human verification + selfie.')
        except Exception as exc:
            self.log(f'[⚠️] Meta checkpoint step: {exc}')

