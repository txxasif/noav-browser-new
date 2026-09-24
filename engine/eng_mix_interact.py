"""engine.eng_mix_interact — visible-first clicks, fills & wizard advance.

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

class EngineInteractMixin:
    @staticmethod
    def _is_ig_or_fb_url(url: str) -> bool:
        """True for Instagram/Facebook destinations. Meta signup must never
        navigate to these — clicking an IG/FB "Sign up" link is exactly the
        "Meta signup redirects to Instagram" bug."""
        u = str(url or "").lower()
        return ("instagram.com" in u) or ("facebook.com" in u) or ("fb.com" in u)

    @staticmethod
    def _is_ig_bounce_url(url: str) -> bool:
        """True when Meta bounced the auth flow to Instagram (IP gating /
        aymh redirect-cycle). Used to bounce back or abort cleanly instead of
        walking the run into an Instagram session."""
        return "instagram.com" in str(url or "").lower()

    def _visible(self, page, role, name, exact=False):
        """Return the first *visible* match (step-wizards keep hidden clones)."""
        loc = page.get_by_role(role, name=name, exact=exact)
        try:
            n = loc.count()
        except Exception:
            n = 0
        for i in range(n):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    txt = (el.inner_text() or el.get_attribute("aria-label") or "").strip().lower()
                    target = str(name).lower()
                    # CRITICAL: Never match Facebook or Instagram buttons when looking for generic actions
                    if "facebook" in txt and "facebook" not in target:
                        continue
                    if "instagram" in txt and "instagram" not in target and "instagram" not in ("log in", "sign up"):
                        continue
                    return el
            except Exception:
                continue
        return None

    def _click(self, page, name, role="button", timeout=25000):
        el = self._visible(page, role, name)
        if el is None:
            raise RuntimeError(f'no visible {role} named {name!r}')
        self._human_click(page, el, timeout)

    def _combo(self, page, name, value):
        # Native select fallback
        try:
            sel = page.locator(f'select[aria-label*="{name}" i], select[name*="{name}" i]').first
            if sel.is_visible():
                sel.select_option(label=str(value))
                self._pause(page, 0.2, 0.5)
                return
        except Exception:
            pass

        # Combobox dropdown (Meta / Instagram custom combobox)
        try:
            cb = page.locator(f'div[role="combobox"][aria-label*="{name}" i], [role="combobox"][aria-label*="{name}" i]').first
            if not cb.is_visible():
                cb = self._visible(page, "combobox", name)
            if cb is not None and cb.is_visible():
                # Fast path: open + pick the option via JS (no mouse-move). DOB
                # day/month/year are low fraud-sensitivity; the human click
                # costs ~1-2s each (3 combos) and caused the 5-56s variance.
                try:
                    if cb.evaluate("el => { try { el.focus(); } catch(e){} el.click(); return true; }"):
                        self._pause(page, 0.15, 0.35)
                        if page.evaluate("""({val}) => {
                            const valStr = String(val).trim().toLowerCase();
                            const opts = Array.from(document.querySelectorAll('[role=option]'));
                            const target = opts.find(o => (o.innerText || o.textContent || '').trim().toLowerCase() === valStr);
                            if (target) { target.scrollIntoView({block:'center'}); target.click(); return true; }
                            return false;
                        }""", {"val": str(value)}):
                            self._pause(page, 0.15, 0.3)
                            return
                except Exception:
                    pass
                self._human_click(page, cb, 8000)
                self._pause(page, 0.5, 0.9)
                selected = page.evaluate("""({val}) => {
                    const valStr = String(val).trim().toLowerCase();
                    const opts = Array.from(document.querySelectorAll('[role=option]'));
                    const target = opts.find(o => (o.innerText || o.textContent || '').trim().toLowerCase() === valStr);
                    if (target) {
                        target.scrollIntoView({block: 'center'});
                        target.click();
                        return true;
                    }
                    return false;
                }""", {"val": str(value)})
                if selected:
                    self._pause(page, 0.3, 0.6)
                    return
        except Exception:
            pass

        cb = self._visible(page, "combobox", name)
        if cb is not None:
            try:
                self._human_click(page, cb, 10000)
                self._pause(page, 0.3, 0.8)
                opt = self._visible(page, "option", str(value))
                if opt is not None:
                    self._human_click(page, opt, 6000)
                    self._pause(page, 0.2, 0.5)
                    return
                o = page.get_by_role("option", name=str(value), exact=True).first
                if o.is_visible():
                    self._human_click(page, o, 6000)
                    self._pause(page, 0.2, 0.5)
                    return
            except Exception:
                pass

        # Robust DOM fallback for Meta & Instagram comboboxes / custom selects
        page.evaluate("""({name, val}) => {
            const valStr = String(val).trim().toLowerCase();
            const nameStr = String(name).trim().toLowerCase();
            const selects = Array.from(document.querySelectorAll('select, [role=combobox]'));
            for (const s of selects) {
                const label = (s.getAttribute('aria-label') || s.getAttribute('name') || '').toLowerCase();
                if (label.includes(nameStr) || nameStr.includes(label)) {
                    if (s.tagName === 'SELECT') {
                        for (let i = 0; i < s.options.length; i++) {
                            if (s.options[i].text.toLowerCase().trim() === valStr || s.options[i].value === valStr) {
                                s.selectedIndex = i;
                                s.dispatchEvent(new Event('change', {bubbles: true}));
                                s.dispatchEvent(new Event('input', {bubbles: true}));
                                return;
                            }
                        }
                    }
                }
            }
            const options = Array.from(document.querySelectorAll('[role=option], option'));
            for (const o of options) {
                if ((o.innerText || o.textContent || '').trim().toLowerCase() === valStr) {
                    o.scrollIntoView({block: 'center'});
                    o.click();
                    return;
                }
            }
        }""", {"name": name, "val": str(value)})
        self._pause(page, 0.2, 0.5)

    def _try_click(self, page, name, role="button", timeout=8000):
        el = self._visible(page, role, name)
        if el is None:
            return False
        try:
            self._human_click(page, el, timeout)
            return True
        except Exception:
            try:
                el.click(force=True, timeout=timeout)
                return True
            except Exception:
                return False

    def _try_fill(self, page, name, value, role="textbox", timeout=8000):
        el = self._visible(page, role, name)
        if el is None:
            return False
        try:
            self._human_type(page, el, value, timeout)
            return True
        except Exception:
            try:
                el.fill(value, timeout=timeout)
                return True
            except Exception:
                return False

    def _advance(self, page, button_names, gone_role, gone_name, tries=5):
        """Click a wizard button and confirm the step actually advanced.

        React forms often eat the first click (a blur handler fires), so retry
        with a JS click / Enter fallback until the step's field disappears.
        """
        for attempt in range(tries):
            for bn in button_names:
                if self._try_click(page, bn, timeout=8000):
                    break
            page.wait_for_timeout(2500)
            if self._visible(page, gone_role, gone_name) is None:
                return True
            # Fallback 1: press Enter in the field (submits many forms)
            try:
                el = self._visible(page, gone_role, gone_name)
                if el is not None:
                    el.press("Enter", timeout=3000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            if self._visible(page, gone_role, gone_name) is None:
                return True
            # Fallback 2: JS click on the button element
            try:
                btn = self._visible(page, "button", button_names[0])
                if btn is not None:
                    btn.evaluate("e => e.click()")
            except Exception:
                pass
            page.wait_for_timeout(1500)
            if self._visible(page, gone_role, gone_name) is None:
                return True
        return False

