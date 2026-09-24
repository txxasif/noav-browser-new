"""engine.eng_mix_ig — Instagram link/join, result save & finish.

Verbatim slice from ``engine/run.py`` ``_MetaInstagramRunner`` (no logic change).
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
    from .eng_constants import _IG_LOGIN_URL  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _IG_LOGIN_URL  # noqa: E402

class EngineIgMixin:
    def instagram(self):
        self.log('[🌐] Opening Instagram in the same browser session…')
        # Open in a new tab in the same context so the Meta session page stays active and warm
        try:
            p = self.w.context.new_page()
            self.insta_page = p
        except Exception:
            p = self.page

        p.goto(_IG_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(3000)

        # 1. Handle cookie consent banners
        for btn_text in ["Allow all cookies", "Only allow essential cookies", "Decline optional cookies", "Allow"]:
            try:
                btn = p.get_by_role("button", name=btn_text).first
                if btn.is_visible():
                    btn.click()
                    p.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # 2. Check if Instagram immediately prompts with active Meta session (Continue as [Name])
        try:
            cont_btn = p.locator('button:has-text("Continue as"), div[role="button"]:has-text("Continue as")').first
            if cont_btn.is_visible():
                txt = (cont_btn.inner_text() or "").strip()
                if "facebook" not in txt.lower():
                    self.log(f'[+] Detected active Meta session prompt: "{txt}"! Clicking…')
                    cont_btn.click()
                    p.wait_for_timeout(5000)
        except Exception:
            pass

        # 3. Fill Meta credentials cleanly if on login screen
        if "login" in p.url.lower():
            user_field = None
            for nm in ("Mobile number, username or email", "Username, email or mobile number", "username", "email"):
                if self._try_fill(p, nm, self.email, timeout=6000):
                    user_field = nm
                    break
            if not user_field:
                try:
                    inp = p.locator('input[name="username"], input[aria-label*="email" i], input[type="text"]').first
                    if inp.is_visible():
                        self._clean_fill(p, inp, self.email, timeout=6000)
                except Exception:
                    pass

            pwd_filled = False
            for nm in ("Password", "password"):
                if self._try_fill(p, nm, self.password, timeout=6000):
                    pwd_filled = True
                    break
            if not pwd_filled:
                try:
                    pinp = p.locator('input[name="password"], input[type="password"]').first
                    if pinp.is_visible():
                        self._clean_fill(p, pinp, self.password, timeout=6000)
                except Exception:
                    pass

            self.log(f'[+] Submitting Instagram login with Meta email: {self.email}…')
            try:
                p.keyboard.press("Enter")
            except Exception:
                pass
            submitted = False
            for btn_sel in (
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Log In")',
                'div[role="button"]:has-text("Log in")',
                'div[role="button"]:has-text("Log In")',
                '[aria-label="Log in"]',
            ):
                try:
                    btn = p.locator(btn_sel).first
                    if btn.count() > 0 and btn.is_visible():
                        try:
                            self._human_click(p, btn, 6000)
                        except Exception:
                            btn.click(force=True, timeout=4000)
                        submitted = True
                        break
                except Exception:
                    pass
            if not submitted:
                if not self._try_click(p, "Log in", timeout=10000):
                    self._try_click(p, "Log In", timeout=6000)
            p.wait_for_timeout(7000)

        # 4. Handle "Your Meta Account currently doesn't have an Instagram profile" dialog
        self._dialog_choose_meta_account(p)

        # 5. Instagram signup with the Meta account if prompted
        if self._try_click(p, "Sign up for Instagram", timeout=6000):
            p.wait_for_timeout(6000)
        self._ig_signup_form(p)

    def _dialog_choose_meta_account(self, p):
        self.log('[+] Checking for Meta Account linking dialog…')
        for _ in range(4):
            try:
                meta_cards = p.locator('div[role="dialog"] button, div[role="button"]:has(svg), div[role="button"]:has-text("Continue as"), div[role="button"]:has-text("Allow"), button:has-text("Allow"), button:has-text("Create account")').all()
                for c in meta_cards:
                    c_text = (c.inner_text() or "").lower()
                    if any(bad in c_text for bad in ["can't find", "try another", "error", "forgot password", "back"]):
                        continue
                    if self.email.lower() in c_text or "continue as" in c_text or "allow" in c_text or "create" in c_text or "yes" in c_text:
                        self.log(f'[+] Found Meta Account Linking prompt: "{c_text[:40]}"! Clicking…')
                        c.click()
                        p.wait_for_timeout(4000)
                        break
            except Exception:
                pass

            try:
                allow_btn = p.locator('button:has-text("Allow and continue"), button:has-text("Continue"), div[role="button"]:has-text("Allow and continue"), button:has-text("Yes, finish adding")').first
                if allow_btn.is_visible():
                    self.log('[+] Clicking "Allow and continue" to link Meta account to Instagram…')
                    allow_btn.click()
                    p.wait_for_timeout(6000)
            except Exception:
                pass
            p.wait_for_timeout(1500)

    def _ig_confirm_code(self, p, timeout=45000):
        for nm in ("Confirmation code", "Code"):
            try:
                loc = p.get_by_role("textbox", name=nm).first
                loc.wait_for(state="visible", timeout=timeout)
            except Exception:
                continue
            code = self.fetch_code("instagram", timeout=240)
            if not code:
                self.log('[⚠️] Instagram code not received.')
                return False
            loc.fill(code)
            if not self._try_click(p, "Next", timeout=10000):
                self._try_click(p, "Continue", timeout=6000)
            p.wait_for_timeout(8000)
            self.log('<font color="#00FF00"><b>[✔] Instagram code accepted.</b></font>')
            return True
        return False

    def _ig_signup_form(self, p):
        # Mobile phone-signup -> switch to email
        self._try_click(p, "Sign up with email", timeout=5000)
        p.wait_for_timeout(2000)

        # Desktop-style "Get started on Instagram with a Meta Account"
        if self._try_fill(p, "Mobile number or email", self.email, timeout=8000):
            self._try_fill(p, "Password", self.password, timeout=8000)
            try:
                self._combo(p, "Select Month", self.dob_month)
                self._combo(p, "Select Day", str(int(self.dob_day)))
                self._combo(p, "Select Year", self.dob_year)
            except Exception as exc:
                self.log(f'[⚠️] Birthday: {exc}')
            self._try_fill(p, "Name", self.name, timeout=5000)
            try:
                ub = p.get_by_role("combobox", name="Username").first
                self._human_click(p, ub, 10000)
                p.keyboard.press("Control+A")
                p.keyboard.press("Backspace")
                self._human_type(p, ub, self.username, 8000)
            except Exception:
                pass
            self._try_click(p, "Submit", timeout=10000)
            p.wait_for_timeout(6000)
            self._ig_confirm_code(p)
            self._handle_human(p, timeout=900)
            return

        # Mobile step-by-step: "What's your email?"
        if self._try_fill(p, "Email", self.email, timeout=8000):
            self._try_click(p, "Next", timeout=8000)
            p.wait_for_timeout(5000)
            self._ig_confirm_code(p)
            if not self._try_fill(p, "Password", self.password, timeout=25000):
                self._try_fill(p, "New password", self.password, timeout=8000)
            self._try_click(p, "Next", timeout=10000)
            p.wait_for_timeout(5000)
            if (self._try_wait_combo(p, "Select Month", timeout=12000)
                    or self._try_wait_combo(p, "Month", timeout=3000)):
                try:
                    self._combo(p, "Select Month", self.dob_month)
                    self._combo(p, "Select Day", str(int(self.dob_day)))
                    self._combo(p, "Select Year", self.dob_year)
                except Exception:
                    pass
                self._try_click(p, "Next", timeout=10000)
                p.wait_for_timeout(4000)
            if self._try_fill(p, "Full name", self.name, timeout=10000):
                self._try_click(p, "Next", timeout=10000)
                p.wait_for_timeout(4000)
            if self._try_fill(p, "Username", self.username, timeout=10000):
                self._try_click(p, "Next", timeout=10000)
                p.wait_for_timeout(4000)
            self._try_click(p, "I agree", timeout=10000)
            p.wait_for_timeout(6000)
            self._handle_human(p, timeout=900)
            return

        self.log('[⚠️] Instagram signup form not recognised — check the browser window.')

    # -- persistence --------------------------------------------------------
    def save_result(self):
        try:
            line = (f"Email: {self.email} | Username: {self.username} | "
                    f"Password: {self.password} | Date: "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            acc_file = getattr(self.core, "ACCOUNTS_FILE", os.path.join(HERE, "accounts.txt"))
            with open(acc_file, "a", encoding="utf-8") as f:
                f.write(line)
            self.log(f'<font color="#00FF00"><b>[🎉] Account saved: {self.username}'
                     f' | {self.password}</b></font>')
        except Exception as exc:
            self.log(f'[⚠️] Could not save account: {exc}')
        try:
            cookies_dir = getattr(self.core, "COOKIES_DIR", os.path.join(HERE, "cookies"))
            os.makedirs(cookies_dir, exist_ok=True)
            cookies = self.w.context.cookies()
            fn = os.path.join(
                cookies_dir,
                f"cookies_{self.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            self.log(f'<font color="#00FF00"><b>[🍪] Cookies saved: {fn}</b></font>')
        except Exception:
            pass

    def finish(self):
        try:
            self.w._cleanup_browser_resources()
        except Exception:
            try:
                self.w.context.close()
            except Exception:
                pass
            try:
                self.w.playwright.stop()
            except Exception:
                pass
        # Keep the profile warm (like Nova) so cookies / trust persist across runs.
        try:
            self.w.status_signal.emit("stopped")
        except Exception:
            pass



def run_meta_instagram(worker):
    try:
        from . import _MetaInstagramRunner  # package mode
    except ImportError:  # top-level `import run` mode (ENGINE_DIR on sys.path)
        from engine import _MetaInstagramRunner  # noqa: E402
    r = _MetaInstagramRunner(worker)
    try:
        worker.status_signal.emit("running")
        worker.log_signal.emit(
            f'[+] Slot {worker.slot_id} Meta→Instagram engine initialized.')
        time.sleep(random.uniform(2, 6))   # human-ish pacing before start
        r._launch()
        r.open_mailtd()
        r.meta_signup()
        r.instagram()
        r.save_result()
    except Exception as exc:  # noqa: BLE001
        worker.log_signal.emit(
            f'<font color="#FF4D4D"><b>[❌] Meta→Instagram error: {exc}</b></font>')
        try:
            worker.status_signal.emit("error")
        except Exception:
            pass
    finally:
        r.finish()
