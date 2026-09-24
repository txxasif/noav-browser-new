from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
import re

from ai_config import AI_DIR, Urls  # noqa: E402


class SignupMixin:
    def meta_signup(self):
        """Bundled-engine meta_signup + Meta AI consumer funnel + terms consent page interceptor."""
        p = self.page
        # Note: meta_ai_signup_funnel in bundled engine handles meta.ai navigation + modal click actively

        orig_visible = self._visible

        def visible(page, role, name):
            self._maybe_accept_meta_terms(page)
            self._maybe_resolve_meta_details_error(page)
            return orig_visible(page, role, name)

        self._visible = visible
        try:
            try:
                return super().meta_signup()
            except RuntimeError as exc:
                # Meta sometimes bounces fresh sessions straight to Instagram
                # login (aymh/redirect-cycle) when the IP is throttled after
                # parallel creators hammer auth.meta.com. Surface that clearly
                # instead of a generic "stalled" error.
                try:
                    url = (getattr(p, "url", "") or "")
                    if "instagram.com" in url and (
                        "stalled after email" in str(exc) or "bounced to Instagram" in str(exc)
                    ):
                        self.log('[⚠️] Meta bounced to Instagram login (IP throttled / Meta gating). '
                                 'Cooldown 5-10 min, lower creators to 1-2, then retry.')
                except Exception:
                    pass
                raise
        finally:
            self._visible = orig_visible

    def _install_screenshot_hooks(self):
        """Capture a screenshot at each key milestone for observability."""
        screens = os.path.join(AI_DIR, "screens")
        os.makedirs(screens, exist_ok=True)
        markers = {
            "Opening Meta account signup": "01_meta_signup",
            "Filled Meta email": "02_meta_email",
            "Name:": "03_meta_name",
            "DOB:": "04_meta_dob",
            "Setting password": "05_meta_password",
            "Waiting for the email code": "06_meta_code_wait",
            "Meta account confirmed": "07_meta_confirmed",
            "Meta human verification": "08_meta_checkpoint",
            "Selfie uploaded": "09_meta_selfie",
            "Opening Instagram": "10_ig_login",
            "No Instagram account found": "11_ig_link_dialog",
            "Instagram account created": "12_ig_created",
            "Instagram home reached": "13_ig_home",
            "starting 2FA": "14_ig_2fa",
            "2FA key captured": "15_ig_2fa_key",
            "2FA key not found": "15b_ig_2fa_fail",
            "standalone password": "16_ig_password",
            "reset link found": "17_ig_reset",
        }
        orig = self.log

        def wrapped(msg):
            orig(msg)
            plain = re.sub(r"<[^>]+>", "", str(msg))
            page = getattr(self, "insta_page", None) or self.page
            for key, tag in markers.items():
                if key in plain and page is not None:
                    try:
                        page.screenshot(path=os.path.join(screens, f"{tag}.png"))
                    except Exception:
                        pass
                    break

        self.log = wrapped

    def _maybe_resolve_meta_details_error(self, page) -> bool:
        """Resolve 'Display Name Has Invalid Characters' or stuck Meta AI details dynamically."""
        try:
            body = (page.inner_text("body") or "").lower()
            if "display name has invalid characters" in body or "invalid characters" in body:
                self.log('[⚠️] Meta signup interceptor: "Display Name Has Invalid Characters" — clearing optional name…')
                try:
                    page.evaluate("""() => {
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

                inp = page.locator('input[aria-label*="Name" i], input[placeholder*="Name" i], input[name*="name" i]').first
                if inp.count() > 0 and inp.is_visible():
                    try:
                        inp.click()
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        inp.fill("")
                    except Exception:
                        pass
                self.name = ""

                conf = page.locator('button:has-text("Confirm"), div[role="button"]:has-text("Confirm")').first
                if conf.count() > 0 and conf.is_visible():
                    conf.click()
                    page.wait_for_timeout(2000)

                # If error persists or username rejected, invoke swap hook without closing browser or TG
                body_after = (page.inner_text("body") or "").lower()
                if "invalid characters" in body_after or ("username" in body_after and ("not available" in body_after or "invalid" in body_after)):
                    swap_hook = getattr(self, "_on_credentials_rejected", None) or getattr(self, "_on_username_taken", None)
                    if callable(swap_hook):
                        cur_uname = getattr(self, "username", "") or getattr(self, "new_username", "")
                        self.log('[⚠️] Meta AI details error persistent — swapping task credentials in place (browser & TG stay open)…')
                        replacement = swap_hook("meta_details_rejected", cur_uname)
                        if replacement:
                            conf = page.locator('button:has-text("Confirm"), div[role="button"]:has-text("Confirm")').first
                            if conf.count() > 0 and conf.is_visible():
                                conf.click()
                                page.wait_for_timeout(2000)
                return True
        except Exception:
            pass
        return False
