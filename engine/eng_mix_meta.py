"""engine.eng_mix_meta — meta.ai low-fraud entry funnel + GetStarted helpers.

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
    from .eng_constants import _META_AI_URL  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _META_AI_URL  # noqa: E402

# Adaptive meta.ai funnel gate (shared across slots in this process).
# When the funnel keeps failing ("did not leave meta.ai" — IP throttled), skip
# it for a cooldown so we don't burn ~10-20s per slot on a doomed path.
_funnel_fail_streak = 0
_funnel_cooldown_until = 0.0
_FUNNEL_FAIL_LIMIT = 3
_FUNNEL_COOLDOWN_SECS = 120

class EngineMetaMixin:
    def _try_wait_combo(self, page, name, timeout=8000):
        end = time.time() + timeout / 1000.0
        while time.time() < end:
            if self._visible(page, "combobox", name) is not None:
                return True
            page.wait_for_timeout(500)
        return False

    def _prefill_getstarted_password(self, page):
        """Fill the unlabeled password field of the 'Get started on Meta AI'
        screen (DOB + password share one screen; Next stalls until filled).
        No-op on any other screen. Returns True when a password is in place.
        """
        try:
            pinp = page.locator('input[type="password"]').first
            if not pinp.is_visible():
                return False
            if self._try_fill(page, "New password", self.password, timeout=4000):
                return True
            if self._try_fill(page, "Password", self.password, timeout=4000):
                return True
            self._clean_fill(page, pinp, self.password)
            self.log('[🔑] Filled password on the Get started screen.')
            return True
        except Exception:
            return False

    def meta_ai_signup_funnel(self, page):
        """Adaptive wrapper around the meta.ai low-fraud funnel.

        Skips the funnel for a cooldown after repeated failures (throttled IP),
        then delegates to :meth:`_meta_ai_signup_funnel_inner`.
        """
        global _funnel_fail_streak, _funnel_cooldown_until
        if time.time() < _funnel_cooldown_until:
            self.log('[⏭️] meta.ai funnel cooling down after repeated throttles — using the direct auth entry.')
            return False
        ok = self._meta_ai_signup_funnel_inner(page)
        if ok:
            _funnel_fail_streak = 0
            _funnel_cooldown_until = 0.0
        else:
            _funnel_fail_streak += 1
            if _funnel_fail_streak >= _FUNNEL_FAIL_LIMIT:
                _funnel_cooldown_until = time.time() + _FUNNEL_COOLDOWN_SECS
                self.log(f'[⏭️] meta.ai funnel failed {_funnel_fail_streak}x — pausing it for '
                         f'{_FUNNEL_COOLDOWN_SECS}s (direct auth entry meanwhile).')
        return ok

    def _meta_ai_signup_funnel_inner(self, page):
        """PC low-fraud entry: meta.ai -> Sign up modal -> Use mobile number or email address.

        Returns True when the email step is reached (caller skips the legacy
        "Use mobile number or email" click block), False to use the legacy
        ``auth.meta.com`` path unchanged. Never raises.
        """
        try:
            self.log('[🌐] Trying meta.ai entry funnel (low-fraud path)…')
            page.goto(_META_AI_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # 1. Handle cookie consent banners if present
            for btn_text in [
                "Allow all cookies", "Allow essential and optional cookies",
                "Only allow essential cookies", "Decline optional cookies", "Allow"
            ]:
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    pass

            # 2. Find and click "Sign up" on the dialog/modal or page
            signed = False
            for _ in range(4):
                # Check for explicit dialog modal first (highest priority)
                try:
                    dialog = page.locator('div[role="dialog"]').first
                    if dialog.count() > 0 and dialog.is_visible():
                        # NEVER match "Sign up with Instagram/Facebook": those
                        # are different products and navigating to them is the
                        # "Sign up bounces to instagram.com" bug.
                        sign_btn = dialog.locator(
                            'button:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook")), '
                            '[role="button"]:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook")), '
                            'a:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook")), '
                            'div:has-text("Sign up"):not(:has-text("Instagram")):not(:has-text("Facebook"))'
                        ).first
                        if sign_btn.count() > 0 and sign_btn.is_visible():
                            try:
                                href = sign_btn.get_attribute("href")
                                if href and href.startswith("http"):
                                    if self._is_ig_or_fb_url(href):
                                        self.log('[⚠️] "Sign up" link points to Instagram/Facebook — skipping (want Meta signup).')
                                    else:
                                        page.goto(href)
                                        signed = True
                                        break
                            except Exception:
                                pass
                            try:
                                sign_btn.tap(timeout=3000)
                                signed = True
                                break
                            except Exception:
                                try:
                                    sign_btn.click(force=True, timeout=3000)
                                    signed = True
                                    break
                                except Exception:
                                    self._human_click(page, sign_btn, 3000)
                                    signed = True
                                    break
                except Exception:
                    pass

                # Fallback to accessible role or text across the page
                for name in ("Sign up", "Sign Up"):
                    try:
                        if self._try_click(page, name, timeout=3000):
                            signed = True
                            break
                    except Exception:
                        pass
                if signed:
                    break

                try:
                    hit = page.evaluate("""() => {
                        const all = document.querySelectorAll('a, button, div[role="button"], span, div');
                        for (const el of all) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            const r = el.getBoundingClientRect();
                            if ((t === 'sign up' || t === 'sign in to get started') && r.width > 0 && r.height > 0) {
                                if (t === 'sign up') {
                                    const h = el.getAttribute('href') || (el.querySelector('a') ? el.querySelector('a').getAttribute('href') : null);
                                    if (h && h.startsWith('http')) {
                                        if (/instagram\\.com|facebook\\.com|fb\\.com/i.test(h)) { return false; }
                                        window.location.href = h; return true;
                                    }
                                    el.click(); return true;
                                }
                            }
                        }
                        return false;
                    }""")
                    if hit:
                        signed = True
                        break
                except Exception:
                    pass
                page.wait_for_timeout(1500)

            if not signed:
                self.log('[⚠️] Could not locate "Sign up" on meta.ai modal; falling back to direct auth entry.')
                return False

            self.log('[✅] Clicked "Sign up" on meta.ai modal; awaiting auth step…')
            reached_step = False
            # meta.ai's "Sign up" is a <button> with no href: it can open the
            # auth step IN PLACE (no URL change). Waiting the full 12s for a
            # redirect then re-loading meta.ai wasted ~18s EVERY run. Poll every
            # 600ms and accept either a real redirect OR the same-page method
            # chooser / email field as success.
            for _ in range(12):
                page.wait_for_timeout(600)
                cur = page.url or ""
                if "meta.ai" not in cur:
                    # Meta sometimes bounces the signup to Instagram (aymh
                    # redirect-cycle / IP gating). That is NOT the Meta auth
                    # step — bounce back and let the caller retry instead of
                    # walking the run into an Instagram session.
                    if self._is_ig_bounce_url(cur):
                        self.log('[⚠️] Sign-up redirected to Instagram — returning to the Meta entry.')
                        try:
                            page.goto(_META_AI_URL, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(2500)
                        except Exception:
                            pass
                        return False
                    if "auth.meta.com" in cur or "facebook.com" in cur:
                        reached_step = True
                        break
                try:
                    if (page.get_by_text("Use mobile number or email", exact=False).first.is_visible()
                            or page.get_by_text("Continue with email", exact=False).first.is_visible()
                            or page.locator('input[type="email"], input[name*="email" i]').first.is_visible()):
                        reached_step = True
                        break
                except Exception:
                    pass
            if not reached_step:
                self.log('[⚠️] meta.ai click did not leave meta.ai (throttled); falling back to direct auth entry.')
                return False

            # 3. Handle method selection on auth.meta.com redirect ("Use mobile number or email address" / "Continue with email")
            method_clicked = False
            for _ in range(6):
                # Check if remembered profile chooser appeared ("Use another profile" / "Use another account")
                for prof_sel in [
                    'button:has-text("Use another profile")',
                    'div[role="button"]:has-text("Use another profile")',
                    'button:has-text("Use another account")',
                    'div[role="button"]:has-text("Use another account")',
                    'button:has-text("Log into another account")',
                    'div[role="button"]:has-text("Log into another account")',
                ]:
                    try:
                        prof_el = page.locator(prof_sel).first
                        if prof_el.count() and prof_el.is_visible():
                            self.log('[🔄] Profile chooser detected on redirect — clicking "Use another profile"…')
                            self._human_click(page, prof_el, 3000)
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass

                for sel in [
                    'div[role="button"]:has-text("Use mobile number or email")',
                    'button:has-text("Use mobile number or email")',
                    'div:has-text("Use mobile number or email address")',
                    'div[role="button"]:has-text("Use email")',
                    'button:has-text("Use email")',
                    'button:has-text("Continue with email")',
                    'div[role="button"]:has-text("Continue with email")',
                ]:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible():
                            self._human_click(page, el, 3000)
                            method_clicked = True
                            break
                    except Exception:
                        pass
                if method_clicked:
                    break

                for name in (
                    "Use mobile number or email address", "Use mobile number or email",
                    "Continue with email", "Use email"
                ):
                    try:
                        if self._try_click(page, name, timeout=2500):
                            method_clicked = True
                            break
                    except Exception:
                        pass
                if method_clicked:
                    break
                page.wait_for_timeout(1000)

            page.wait_for_timeout(2000)

            # 4. Probe for the email input field (email-specific ONLY — the
            # meta.ai chat composer is a generic input and false-positived here).
            for _ in range(6):
                # Never accept an Instagram page as the Meta email step.
                if self._is_ig_bounce_url(page.url):
                    self.log('[⚠️] Meta funnel landed on Instagram — aborting Meta entry.')
                    return False
                try:
                    probe = page.locator(
                        'input[type="email"], input[name*="email" i], input[name*="contact" i], '
                        'input[autocomplete="email"], input[inputmode="email"]'
                    ).first
                    if probe.is_visible():
                        self.log('[✅] meta.ai funnel reached the email step.')
                        return True
                except Exception:
                    pass
                page.wait_for_timeout(1000)

            self.log('[⚠️] meta.ai funnel did not expose email field within expected timeout.')
            return False
        except Exception as exc:
            self.log(f'[⚠️] meta.ai funnel failed: {exc}')
            return False

