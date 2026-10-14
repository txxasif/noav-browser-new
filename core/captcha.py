from __future__ import annotations

import os
from urllib.parse import urlparse
import random
import re
import sys
import time

from ai_config import AI_DIR, run  # noqa: E402


class MetaCheckpointBlocked(RuntimeError):
    """Meta refused the signup at the human-verification checkpoint.

    The screen reads "Confirm that you're human" with a **Try again later**
    button and "Your computer or network may be sending automated queries … we
    can't process your request right now" (auth.meta.com/checkpoint…).

    This is an IP/NETWORK-level block, NOT a solvable captcha: there is nothing
    to solve, and the reCAPTCHA widget is disabled. Retrying, re-solving or
    re-uploading just parks the slot on a dead screen and burns the account
    (observed 2026-09-26). Terminal for this account — raise so the cycle closes
    the browser and moves to the next one, i.e. the same close-and-move-on
    semantics as IGDeadEnd (invariant 17). The real cure is a clean egress
    (per-account proxy) and a non-temp mail domain (invariant 17), not a retry.
    """


# Markers unique to the "we refused you" checkpoint, as opposed to a normal
# solvable reCAPTCHA. 'try again later' alone is too generic on its own, so it
# is always paired with the automated-queries wording.
_META_IP_BLOCK_MARKERS = (
    "may be sending automated queries",
    "we can't process your request right now",
    "we cannot process your request right now",
    "can't process your request at the moment",
    "cannot process your request at the moment",
    "sending automated queries",
    "unusual traffic",
)


def _meta_ip_blocked(page_or_body, url: str = "") -> bool:
    """True for Meta's or Google's terminal 'automated queries' / 'try again later' refusal."""
    if hasattr(page_or_body, "frames"):
        page = page_or_body
        u = (getattr(page, "url", None) or "").lower()
        try:
            frames = [page] + list(page.frames)
        except Exception:
            frames = [page]
        seen = set()
        for f in frames:
            if id(f) in seen:
                continue
            seen.add(id(f))
            try:
                b = (f.evaluate("() => document.body ? document.body.innerText : ''") or "").lower()
            except Exception:
                continue
            if any(m in b for m in _META_IP_BLOCK_MARKERS):
                if ("confirm that you're human" in b or "checkpoint" in u or "try again later" in b or "queries" in b):
                    return True
        return False

    b = (page_or_body or "").lower()
    u = (url or "").lower()
    if not any(m in b for m in _META_IP_BLOCK_MARKERS):
        return False
    return ("confirm that you're human" in b
            or "checkpoint" in u
            or "try again later" in b)


_COOKIE_CHOICE_BUTTONS = ("Decline optional cookies", "Only allow essential cookies",
                          "Allow essential and optional cookies", "Allow all cookies")


class CaptchaMixin:
    def _dismiss_cookie_choice(self, page) -> bool:
        """EU only: Meta's logged-in cookie page ("Allow the use of cookies from Meta?",
        auth.meta.com/privacy/consent/?flow=user_cookie_choice_v2) comes right after the signup code
        and BEFORE the human check. Everywhere else the URL test below is a plain string compare, so
        the non-EU flow pays nothing. Returns True when a choice was made."""
        try:
            parsed = urlparse(page.url or "")
        except Exception:
            return False
        if "/privacy/consent" not in (parsed.path or "").lower():
            return False
        for nm in _COOKIE_CHOICE_BUTTONS:
            try:
                btn = page.get_by_role("button", name=nm, exact=True).first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=4000)
                    break
            except Exception:
                continue
        else:
            return False
        self.log('[🍪] Meta cookie-choice page (EU) — declined optional cookies.')
        for _ in range(12):                         # leave the consent page, ~6s max
            page.wait_for_timeout(500)
            try:
                if "/privacy/consent" not in (urlparse(page.url or "").path or "").lower():
                    break
            except Exception:
                break
        return True

    def _dismiss_save_login_info(self, page) -> bool:
        """Dismiss the 'Save your login info?' modal on auth.meta.com.

        This modal appears after Meta signup or login (seen on auth.meta.com/?rcs=...):
        'Save your login info? We'll save the login info for <username> so that you won't need to enter it next time.'
        Offers 'Save' (blue primary button), 'Not now' (secondary button), and an 'X' close button.
        Dismissing it allows the flow to cleanly proceed to /language or meta.ai.
        """
        try:
            has_prompt = False
            if hasattr(page, "evaluate"):
                has_prompt = bool(page.evaluate("""() => {
                    const t = (document.body ? document.body.innerText : '').toLowerCase();
                    if (t.includes('save your login info') || t.includes('save login info')) return true;
                    for (const d of document.querySelectorAll('[role="dialog"], [aria-modal="true"]')) {
                        const dt = (d.innerText || '').toLowerCase();
                        if (dt.includes('save your login info') || dt.includes('save login info') || dt.includes('save your login')) {
                            return true;
                        }
                    }
                    return false;
                }"""))
            elif hasattr(page, "inner_text"):
                body_t = (page.inner_text("body") or "").lower()
                has_prompt = "save your login info" in body_t or "save login info" in body_t
        except Exception:
            has_prompt = False

        if not has_prompt:
            return False

        self.log('[💾] "Save your login info?" dialog detected — dismissing…')

        # 1. Try Playwright locators for Save or Not now
        for btn_text in ("Save", "Not now"):
            for sel in (
                f'button:has-text("{btn_text}")',
                f'div[role="button"]:has-text("{btn_text}")',
                f'span:has-text("{btn_text}")',
            ):
                try:
                    loc = page.locator(sel)
                    for i in range(loc.count()):
                        btn = loc.nth(i)
                        if btn.is_visible():
                            btn.click(timeout=3000, delay=50)
                            self.log(f'[💾] Clicked "{btn_text}" on save login prompt.')
                            time.sleep(1.0)
                            return True
                except Exception:
                    pass

        # 2. Try JS evaluate click (including dispatching mouse/pointer events)
        try:
            if hasattr(page, "evaluate"):
                res = page.evaluate("""() => {
                    const isTarget = (t) => {
                        const s = (t || '').trim().toLowerCase();
                        return s === 'save' || s === 'not now';
                    };
                    const dialogs = document.querySelectorAll('[role="dialog"], [aria-modal="true"], div');
                    for (const d of dialogs) {
                        const dt = (d.innerText || '').toLowerCase();
                        if (dt.includes('save your login info') || dt.includes('save login info')) {
                            for (const b of d.querySelectorAll('button, div[role="button"], span')) {
                                if (isTarget(b.innerText)) {
                                    b.scrollIntoView({block: 'center'});
                                    ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(evt => {
                                        try { b.dispatchEvent(new MouseEvent(evt, {bubbles: true, cancelable: true, view: window})); } catch(e) {}
                                    });
                                    try { b.click(); } catch(e) {}
                                    return (b.innerText || '').trim();
                                }
                            }
                            const x = d.querySelector('[aria-label="Close"], [aria-label="close"]');
                            if (x) {
                                try { x.click(); return 'Close'; } catch(e) {}
                            }
                        }
                    }
                    for (const b of document.querySelectorAll('button, div[role="button"]')) {
                        if (isTarget(b.innerText)) {
                            b.click();
                            return (b.innerText || '').trim();
                        }
                    }
                    return null;
                }""")
                if res:
                    self.log(f'[💾] Clicked "{res}" via JS on save login prompt.')
                    time.sleep(1.0)
                    return True
        except Exception:
            pass

        return False

    @staticmethod
    def _needs_meta_relogin(p) -> bool:
        """True while Meta shows the account chooser or the "Check your email" login screen. Those are
        not a verified account: the next attempt must log in again before moving on to Instagram."""
        try:
            if "auth.meta.com" not in (p.url or "").lower():
                return False
            body = (p.inner_text("body") or "").lower()
        except Exception:
            return False
        return ("log in with your meta account" in body or "use another account" in body
                or ("check your email" in body and "enter the code we sent" in body))

    def _meta_login_challenge(self, p) -> bool:
        """Meta sometimes asks the account to log in again right after signup / the human check:
        the chooser ("Continue as <name>") is followed by "Check your email - enter the code we
        sent to ..." with a Code box, "Log in" and "Enter password instead". Prefer the password
        (known, instant) over waiting for another email; fall back to the inbox code.
        Returns True when that screen was seen and handled."""
        try:
            if "auth.meta.com" not in (p.url or "").lower():
                return False
            body = (p.inner_text("body") or "").lower()
        except Exception:
            return False
        if "check your email" not in body or not (
                "enter the code we sent" in body or "enter password instead" in body):
            return False
        self.log('[🔐] Meta asks to log in again (email code screen).')
        pw = getattr(self, "password", None)
        if pw and self._try_click(p, "Enter password instead", timeout=4000):
            for _ in range(10):                       # wait (<=3s) for the password box
                try:
                    if p.locator('input[type="password"]').first.is_visible():
                        break
                except Exception:
                    pass
                p.wait_for_timeout(300)
            filled = False
            try:
                box = p.locator('input[type="password"]').first
                if box.is_visible():
                    box.fill(pw, timeout=4000)
                    filled = True
            except Exception:
                pass
            if filled or self._try_fill(p, "Password", pw, timeout=4000):
                self.log('[🔐] Logging in again with the password…')
                self._try_click(p, "Log in", timeout=5000)
                self._poll_checkpoint_settled(p, timeout=10)
                self._dismiss_save_login_info(p)
                return True
        # fallback: read the new code from the inbox
        try:
            code = self.fetch_code("meta", timeout=90)
        except Exception:
            code = None
        if code:
            self.log('[🔐] Logging in again with the emailed code…')
            if not self._try_fill(p, "Code", str(code), timeout=5000):
                try:
                    p.locator('input').first.fill(str(code), timeout=4000)
                except Exception:
                    pass
            self._try_click(p, "Log in", timeout=5000)
            self._poll_checkpoint_settled(p, timeout=10)
            self._dismiss_save_login_info(p)
        else:
            self.log('[⚠️] Meta login code not received and no password option — leaving it to the next attempt.')
        return True

    def _has_human_check(self, page) -> bool:
        """True if the page is on an Instagram/Meta human checkpoint or challenge screen."""
        try:
            # PATH only: the EU cookie-choice page (/privacy/consent/?...referrer=...checkpoints...)
            # carries "checkpoints" in its QUERY and is not a human check.
            u = (urlparse(page.url or "").path or "").lower()
            if "accounts/suspended" in u or "checkpoint" in u or "challenge" in u:
                return True
        except Exception:
            pass
        try:
            body = (page.inner_text("body") or "").lower()
            if any(m in body for m in (
                "confirm you're human",
                "confirm that you're human",
                "can't read this text",
                "hear this code",
                "upload a verification selfie",
                "enter the code from the image",
                "suspect automated",
            )):
                return True
        except Exception:
            pass
        return False

    # -------------------------------------------------------------------------
    # NEW WAY: 100% exact parity with PC tool (PC_USER_WORK_FREE.exe SingleProfileWorker)
    # -------------------------------------------------------------------------

    def _pc_navigate_with_retry(self, page, url: str, timeout: int = 60000, retries: int = 3) -> bool:
        for attempt in range(retries):
            if hasattr(self, "_is_running") and not self._is_running:
                return False
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                return True
            except Exception as e:
                self.log(f"⚠ Nav attempt {attempt + 1}/{retries} failed: {str(e)[:60]}")
                time.sleep(1.5)
                try:
                    page.goto(url, wait_until="commit", timeout=timeout)
                    return True
                except Exception:
                    pass
        return False

    def _pc_wait_for_dom_ready(self, page, timeout: int = 25000) -> bool:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout, 8000))
        except Exception:
            pass
        deadline = time.time() + 2
        while time.time() < deadline:
            if hasattr(self, "_is_running") and not self._is_running:
                break
            try:
                ok = page.evaluate("""() => {
                    if (!document.body) return false;
                    return (document.body.innerText || '').length > 10;
                }""")
                if ok:
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False

    def _pc_wait_for_text_visible(self, page, text: str, timeout: int = 20000, poll: float = 0.5, exact: bool = False) -> bool:
        deadline = time.time() + (timeout / 1000.0)
        while time.time() < deadline:
            if hasattr(self, "_is_running") and not self._is_running:
                return False
            try:
                found = page.evaluate("""(args) => {
                    const [text, exact] = args;
                    const all = document.querySelectorAll('span, button, div[role="button"], a, div[role="menuitem"], div[role="option"], li');
                    for (const el of all) {
                        const t = (el.innerText || '').trim();
                        const match = exact ? (t === text) : (t === text || t.startsWith(text));
                        if (match) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.width < 600 && r.height < 200) {
                                return true;
                            }
                        }
                    }
                    return false;
                }""", [text, exact])
                if found:
                    return True
            except Exception:
                pass
            time.sleep(poll)
        return False

    def _pc_check_captcha_present(self, page) -> dict:
        try:
            info = page.evaluate("""() => {
                const info = {present: false, type: 'none'};
                const html = (document.documentElement.innerHTML || '').toLowerCase();
                if (html.includes('hcaptcha.com/1/api.js') ||
                    html.includes('new hcaptcha') ||
                    document.querySelector('iframe[src*="hcaptcha.com"]') ||
                    document.querySelector('div.h-captcha') ||
                    document.querySelector('[class*="hcaptcha"][class*="widget"]')) {
                    info.present = true;
                    info.type = 'hcaptcha';
                    return info;
                }
                if (document.querySelector('iframe[src*="google.com/recaptcha"]') ||
                    document.querySelector('iframe[src*="recaptcha/api2"]') ||
                    document.querySelector('div.g-recaptcha') ||
                    html.includes('recaptcha/api.js')) {
                    info.present = true;
                    info.type = 'recaptcha';
                    return info;
                }
                if (document.querySelector('iframe[src*="challenges.cloudflare.com"]') ||
                    document.querySelector('div.cf-turnstile')) {
                    info.present = true;
                    info.type = 'cloudflare';
                    return info;
                }
                const puzzleImgs = document.querySelectorAll('img[src*="captcha"], img[alt*="captcha" i]');
                for (const img of puzzleImgs) {
                    const r = img.getBoundingClientRect();
                    if (r.width > 80 && r.height > 40) {
                        info.present = true;
                        info.type = 'puzzle_captcha';
                        return info;
                    }
                }
                const iframes = document.querySelectorAll('iframe');
                for (const ifr of iframes) {
                    const src = (ifr.src || '').toLowerCase();
                    if (src.includes('captcha') || src.includes('turnstile') ||
                        src.includes('challenge-platform')) {
                        const r = ifr.getBoundingClientRect();
                        if (r.width > 100 && r.height > 50) {
                            info.present = true;
                            info.type = 'iframe_captcha';
                            return info;
                        }
                    }
                }
                return info;
            }""")
            if isinstance(info, dict):
                return info
        except Exception:
            pass
        return {"present": False, "type": "none"}

    def _pc_wait_for_captcha_solve(self, page, timeout: int = 300) -> bool:
        self.log(f"🧩 CAPTCHA — waiting up to {timeout}s")
        start = time.time()
        poll = 0
        initial_url = getattr(page, "url", "") or ""
        last_log = 0
        while (time.time() - start) < timeout:
            if hasattr(self, "_is_running") and not self._is_running:
                return False
            poll += 1
            elapsed = int(time.time() - start)
            try:
                status = self._pc_check_captcha_present(page)
                if not status.get("present"):
                    self.log(f"✓ Captcha SOLVED in {elapsed}s!")
                    time.sleep(0.5)
                    return True
            except Exception:
                pass
            try:
                if (getattr(page, "url", "") or "") != initial_url:
                    self.log(f"✓ URL changed at {elapsed}s")
                    time.sleep(0.5)
                    return True
            except Exception:
                pass
            if (elapsed - last_log) >= 30:
                remaining = timeout - elapsed
                self.log(f"⏳ Captcha wait... {elapsed}s / {remaining}s left")
                last_log = elapsed
            time.sleep(0.8)
        self.log(f"✗ Captcha NOT solved in {timeout}s")
        return False

    def _pc_detect_auth_page(self, page) -> dict:
        try:
            info = page.evaluate("""() => {
                const result = {type: 'unknown', hints: []};
                const url = (window.location.href || '').toLowerCase();
                const allText = (document.body.innerText || '').toLowerCase();
                if (url.includes('meta.ai/?') || url.includes('meta.ai/home') ||
                    url.includes('meta.ai/chat') || url.includes('meta.ai/prompt')) {
                    result.type = 'success';
                    return result;
                }
                const fileInputs = document.querySelectorAll('input[type="file"]');
                let hasFileInput = fileInputs.length > 0;
                const uploadTexts = ['upload', 'add photo', 'add picture', 'change photo',
                                     'choose file', 'select photo', 'profile picture',
                                     'add a photo', 'add an image', 'add profile photo'];
                for (const el of document.querySelectorAll('span, button, div, label, p, h1, h2')) {
                    const t = (el.innerText || '').trim().toLowerCase();
                    for (const ut of uploadTexts) {
                        if (t === ut || t.includes(ut)) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && t.length < 60) {
                                result.type = 'image_upload';
                                return result;
                            }
                        }
                    }
                }
                if (hasFileInput) {
                    const previewImgs = document.querySelectorAll('img[src^="blob:"], img[src^="data:image"]');
                    for (const pi of previewImgs) {
                        const r = pi.getBoundingClientRect();
                        if (r.width > 40 && r.height > 40) {
                            result.type = 'image_upload';
                            return result;
                        }
                    }
                }
                if (allText.includes("confirm that you're human") ||
                    allText.includes("confirm that you are human") ||
                    allText.includes("verify you're human") ||
                    allText.includes("verify you are human") ||
                    allText.includes("let us know you're not a robot") ||
                    allText.includes("we need to confirm you're human") ||
                    allText.includes("help us confirm") ||
                    allText.includes('security check')) {
                    result.type = 'human_check';
                    return result;
                }
                const loginSpans = Array.from(document.querySelectorAll('span, button, div[role="button"]'))
                    .filter(el => (el.innerText || '').trim() === 'Log in');
                for (const sp of loginSpans) {
                    const r = sp.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        result.type = 'login_page';
                        return result;
                    }
                }
                if (allText.includes('choose an account') ||
                    allText.includes('select an account') ||
                    allText.includes('pick an account') ||
                    allText.includes('continue as') ||
                    allText.includes('your accounts')) {
                    result.type = 'account_select';
                    return result;
                }
                const accountCandidates = [];
                const selectors = [
                    '[role="button"][tabindex="0"]',
                    '[data-testid*="account"]',
                    'a[href*="account"]',
                    'div[role="link"]'
                ];
                for (const sel of selectors) {
                    for (const item of document.querySelectorAll(sel)) {
                        const text = (item.innerText || '').trim();
                        const rect = item.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 &&
                            text.length > 3 && text.length < 200) {
                            if (text.includes('@') || /^[A-Z][a-z]/.test(text) ||
                                text.includes('Facebook') || text.includes('Instagram')) {
                                accountCandidates.push(item);
                            }
                        }
                    }
                }
                if (accountCandidates.length >= 2) {
                    result.type = 'account_select';
                    return result;
                }
                if (allText.includes('save your login info') || allText.includes('save login info')) {
                    result.type = 'save_login_info';
                    return result;
                }
                const continueBtns = Array.from(document.querySelectorAll('span, button, div[role="button"]'))
                    .filter(el => {
                        const t = (el.innerText || '').trim();
                        return t === 'Continue' || t === 'Next' || t === 'Confirm';
                    });
                for (const cb of continueBtns) {
                    const r = cb.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.width < 500) {
                        result.type = 'profile_continue';
                        return result;
                    }
                }
                if (allText.includes('log out') || allText.includes('logout')) {
                    result.type = 'success';
                    return result;
                }
                return result;
            }""")
            if isinstance(info, dict):
                return info
        except Exception:
            pass
        return {"type": "unknown", "hints": []}

    def _pc_click_first_account(self, page) -> bool:
        try:
            result = page.evaluate("""() => {
                const candidates = [];
                const selectors = [
                    '[role="button"][tabindex="0"]',
                    '[data-testid*="account"]',
                    'a[href*="account"]',
                    'div[role="link"]'
                ];
                for (const sel of selectors) {
                    for (const item of document.querySelectorAll(sel)) {
                        const text = (item.innerText || '').trim();
                        const rect = item.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 &&
                            text.length > 3 && text.length < 300) {
                            if (text.includes('@') || /^[A-Z][a-z]/.test(text) ||
                                text.includes('Facebook') || text.includes('Instagram')) {
                                candidates.push({
                                    el: item, text: text.slice(0, 50),
                                    top: rect.top, left: rect.left
                                });
                            }
                        }
                    }
                }
                if (candidates.length === 0) return {ok: false};
                candidates.sort((a, b) => {
                    if (Math.abs(a.top - b.top) < 20) return a.left - b.left;
                    return a.top - b.top;
                });
                const first = candidates[0];
                first.el.scrollIntoView({block: 'center'});
                let clickTarget = first.el;
                let cur = first.el;
                for (let i = 0; i < 5 && cur; i++) {
                    const role = cur.getAttribute && cur.getAttribute('role');
                    if (role === 'button' || role === 'link' ||
                        cur.tagName === 'BUTTON' || cur.tagName === 'A') {
                        clickTarget = cur;
                    }
                    cur = cur.parentElement;
                }
                const r = clickTarget.getBoundingClientRect();
                const cx = r.x + r.width / 2;
                const cy = r.y + r.height / 2;
                ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t => {
                    try {
                        const ev = t.startsWith('pointer')
                            ? new PointerEvent(t, {bubbles: true, cancelable: true, view: window,
                                clientX: cx, clientY: cy, pointerId: 1, pointerType: 'mouse', isPrimary: true})
                            : new MouseEvent(t, {bubbles: true, cancelable: true, view: window,
                                clientX: cx, clientY: cy});
                        clickTarget.dispatchEvent(ev);
                    } catch(e) {}
                });
                try { clickTarget.click(); } catch(e) {}
                return {ok: true, text: first.text, total: candidates.length};
            }""")
            if result and result.get("ok"):
                self.log(f"✓ Account clicked: '{result.get('text', '')[:50]}'")
                return True
        except Exception:
            pass

        try:
            for sel in ('[role="button"][tabindex="0"]', '[data-testid*="account"]', 'div[role="link"]', 'a[href*="account"]'):
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        first = loc.first
                        try:
                            first.scroll_into_view_if_needed(timeout=2000)
                        except Exception:
                            pass
                        time.sleep(0.4)
                        first.click(timeout=3000, force=True)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _pc_click_continue_button(self, page) -> bool:
        all_texts = ['Continue', 'Next', 'Confirm', 'Submit', 'OK', 'Got it', 'Allow', 'Accept', 'I agree', 'Save', 'Not now']
        for txt in all_texts:
            try:
                loc = page.locator(f'span:has-text("{txt}")').last
                if loc.count() > 0 and loc.is_visible(timeout=600):
                    loc.click(timeout=3000, delay=50)
                    return True
            except Exception:
                pass
            try:
                loc = page.locator(f'button:has-text("{txt}")').first
                if loc.count() > 0 and loc.is_visible(timeout=500):
                    loc.click(timeout=3000, delay=50)
                    return True
            except Exception:
                pass
            try:
                loc = page.locator(f'div[role="button"]:has-text("{txt}")').first
                if loc.count() > 0 and loc.is_visible(timeout=500):
                    loc.click(timeout=3000, delay=50)
                    return True
            except Exception:
                pass

        for txt in ('Continue', 'Next', 'Confirm', 'Submit', 'Save', 'Not now'):
            try:
                clicked = page.evaluate("""(text) => {
                    const all = document.querySelectorAll('span, button, div[role="button"], a');
                    for (const el of all) {
                        const t = (el.innerText || '').trim();
                        if (t === text) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.width < 500) {
                                el.scrollIntoView({block: 'center'});
                                el.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }""", txt)
                if clicked:
                    return True
            except Exception:
                pass

        try:
            clicked = page.evaluate("""() => {
                const btns = document.querySelectorAll('button, div[role="button"]');
                for (const btn of btns) {
                    const r = btn.getBoundingClientRect();
                    if (r.width < 60 || r.height < 25) continue;
                    if (r.width > 500 || r.height > 150) continue;
                    const style = window.getComputedStyle(btn);
                    const bg = style.backgroundColor;
                    const isBlue = bg.includes('rgb(0,') || bg.includes('rgb(24,') || 
                                   bg.includes('rgb(59,') || bg.includes('rgb(70,');
                    if (isBlue) {
                        const text = (btn.innerText || '').trim();
                        if (text.length > 0 && text.length < 40) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if clicked:
                return True
        except Exception:
            pass

        return False

    def _pc_click_text_button(self, page, text: str) -> bool:
        try:
            loc = page.locator(f'span:has-text("{text}")').last
            if loc.count() > 0 and loc.is_visible(timeout=1200):
                loc.click(timeout=3000, delay=50)
                return True
        except Exception:
            pass
        try:
            clicked = page.evaluate("""(text) => {
                const all = document.querySelectorAll('span, button, div[role="button"]');
                for (const el of all) {
                    const t = (el.innerText || '').trim();
                    if (t === text) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            el.click();
                            return true;
                        }
                    }
                }
                return false;
            }""", text)
            return bool(clicked)
        except Exception:
            return False

    def _pc_handle_human_check(self, page, max_attempts: int = 8) -> bool:
        self.log("🧑 Human check page — starting handler")
        for attempt in range(max_attempts):
            if hasattr(self, "_is_running") and not self._is_running:
                return False
            page_info = self._pc_detect_auth_page(page)
            current_type = page_info.get("type", "unknown")
            if current_type != "human_check":
                self.log(f"   ✓ Page changed to '{current_type}' — done")
                return True
            self.log(f"   [Attempt {attempt + 1}/{max_attempts}] Still on human check")
            cap = self._pc_check_captcha_present(page)
            if cap.get("present"):
                self.log(f"   🧩 Captcha widget detected: {cap.get('type')}")
                solved = self._pc_wait_for_captcha_solve(page, timeout=300)
                if not solved:
                    return False
                time.sleep(1.2)
                continue

            btn_texts = [
                'Continue', 'Next', 'Confirm', 'Yes, continue', 'Submit', 'OK',
                'Got it', 'Verify', "I'm not a robot", 'I am human',
                'I am not a robot', 'Start verification'
            ]
            for btn_text in btn_texts:
                if hasattr(self, "_is_running") and not self._is_running:
                    break
                try:
                    loc = page.locator(f'span:has-text("{btn_text}")').last
                    if loc.count() > 0 and loc.is_visible(timeout=500):
                        try:
                            loc.scroll_into_view_if_needed(timeout=1200)
                        except Exception:
                            pass
                        time.sleep(0.15)
                        loc.click(timeout=3000, delay=50)
                        self.log(f"   ✓ Clicked '{btn_text}' (span)")
                        break
                except Exception:
                    pass
                try:
                    loc = page.locator(f'button:has-text("{btn_text}")').first
                    if loc.count() > 0 and loc.is_visible(timeout=500):
                        try:
                            loc.scroll_into_view_if_needed(timeout=1200)
                        except Exception:
                            pass
                        time.sleep(0.15)
                        loc.click(timeout=3000, delay=50)
                        self.log(f"   ✓ Clicked '{btn_text}' (button)")
                        break
                except Exception:
                    pass
                try:
                    loc = page.locator(f'div[role="button"]:has-text("{btn_text}")').first
                    if loc.count() > 0 and loc.is_visible(timeout=500):
                        try:
                            loc.scroll_into_view_if_needed(timeout=1200)
                        except Exception:
                            pass
                        time.sleep(0.15)
                        loc.click(timeout=3000, delay=50)
                        self.log(f"   ✓ Clicked '{btn_text}' (div[role=button])")
                        break
                except Exception:
                    pass
            time.sleep(1.5)
        return False

    def _pc_upload_random_image(self, page) -> bool:
        self.log("→ [Upload] Starting...")
        img_dirs = [
            os.path.join(AI_DIR, "img"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img"),
            os.path.join(AI_DIR, "selfies"),
        ]
        img_dir = None
        for d in img_dirs:
            if os.path.isdir(d):
                img_dir = d
                break
        if not img_dir:
            self.log("⚠ No images directory found")
            return False

        valid_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
        images = []
        try:
            for f in os.listdir(img_dir):
                if f.lower().endswith(valid_exts):
                    full = os.path.join(img_dir, f)
                    if os.path.isfile(full):
                        images.append(full)
        except Exception:
            return False

        if not images:
            self.log("⚠ No images in img/ folder")
            return False

        chosen_image = random.choice(images)
        chosen_name = os.path.basename(chosen_image)
        self.log(f"→ Random image: {chosen_name}")

        file_input = None
        deadline = time.time() + 25
        while time.time() < deadline:
            if hasattr(self, "_is_running") and not self._is_running:
                break
            try:
                loc = page.locator('input[type="file"]')
                if loc.count() > 0:
                    file_input = loc.first
                    break
            except Exception:
                pass
            time.sleep(0.3)

        if not file_input:
            return False

        try:
            file_input.set_input_files(chosen_image, timeout=20000)
            self.log("✓ File set")
            time.sleep(1.5)

            has_preview = False
            try:
                has_preview = page.evaluate("""() => {
                    const imgs = document.querySelectorAll('img');
                    for (const img of imgs) {
                        const src = img.src || '';
                        if (src.startsWith('blob:') || src.startsWith('data:image')) {
                            const r = img.getBoundingClientRect();
                            if (r.width > 30 && r.height > 30) return true;
                        }
                    }
                    return false;
                }""")
            except Exception:
                pass

            if has_preview:
                self.log("✓ Preview detected")
            else:
                time.sleep(1.0)

            try:
                self._pc_wait_for_text_visible(page, "Continue", timeout=20000)
            except Exception:
                pass
            time.sleep(0.5)

            url_before = ""
            try:
                url_before = page.url or ""
            except Exception:
                pass

            if not self._pc_click_continue_button(page):
                return False

            self.log("✓ Continue clicked")
            self._image_uploaded_and_continued = True

            try:
                page.wait_for_load_state("networkidle", timeout=25000)
            except Exception:
                pass

            deadline = time.time() + 25
            while time.time() < deadline:
                if hasattr(self, "_is_running") and not self._is_running:
                    break
                try:
                    if (page.url or "") != url_before:
                        break
                except Exception:
                    pass
                time.sleep(0.4)

            time.sleep(2.0)
            return True
        except Exception as e:
            self.log(f"✗ Upload err: {str(e)[:80]}")
            return False

    def _pc_try_image_upload_if_present(self, page) -> None:
        try:
            has_input = page.evaluate("""() => {
                const inputs = document.querySelectorAll('input[type="file"]');
                return inputs.length > 0;
            }""")
            if has_input:
                self._pc_upload_random_image(page)
        except Exception:
            pass

    def _pc_check_success(self, page):
        try:
            return page.evaluate("""() => {
                const url = window.location.href.toLowerCase();
                if (url.includes('meta.ai/?') || 
                    url.includes('meta.ai/home') ||
                    url.includes('meta.ai/chat') ||
                    url.includes('/success') ||
                    url.includes('/welcome') ||
                    url.includes('/done')) {
                    return 'url';
                }
                const all = document.querySelectorAll('span, div, h1, h2, p');
                for (const el of all) {
                    const t = (el.innerText || '').trim();
                    if (t.length > 0 && t.length < 100) {
                        const lower = t.toLowerCase();
                        if (lower === 'welcome' || 
                            lower.includes("you're all set") ||
                            lower.includes('account created')) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) return 'text';
                        }
                    }
                }
                const hasSignup = document.querySelector(
                    'input[inputmode="email"], input[type="password"], input[inputmode="numeric"]'
                );
                const hasMainUI = document.querySelector(
                    'textarea, [contenteditable="true"], [role="textbox"], nav, header'
                );
                if (hasMainUI && !hasSignup) return 'ui';
                return null;
            }""")
        except Exception:
            return None

    def _pc_check_final_url_for_save(self, page) -> bool:
        try:
            current_url = (getattr(page, "url", "") or "").lower()
            self.log(f"🔍 Checking final URL: {current_url[:100]}")
            if "auth.meta.com/language" in current_url:
                return True
            return False
        except Exception as e:
            self.log(f"⚠ URL check err: {str(e)[:60]}")
            return False

    def _pc_post_otp_flow(self, page) -> Any:
        self.log("→ Post-OTP: auth.meta.com...")
        self._pc_navigate_with_retry(page, "https://auth.meta.com", timeout=60000, retries=3)
        self.log("✓ auth.meta.com loaded")
        self._pc_wait_for_dom_ready(page, timeout=25000)
        last_url = ""
        last_dom_sig = ""
        same_count = 0
        reload_count = 0
        for step_iter in range(15):
            if hasattr(self, "_is_running") and not self._is_running:
                return None
            try:
                current_url = getattr(page, "url", "") or ""
            except Exception:
                current_url = ""

            cap = self._pc_check_captcha_present(page)
            if cap.get("present"):
                self.log(f"🧩 Captcha widget: {cap.get('type')}")
                solved = self._pc_wait_for_captcha_solve(page, timeout=300)
                if not solved:
                    return "CAPTCHA_FAILED"
                time.sleep(1.0)

            if self._dismiss_save_login_info(page):
                time.sleep(1.0)
                continue

            if self._pc_check_success(page):
                self.log("✅ Success")
                return True

            try:
                dom_sig = page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input').length;
                    const buttons = document.querySelectorAll('button, div[role="button"]').length;
                    return `${inputs}_${buttons}_${document.title}`;
                }""")
            except Exception:
                dom_sig = "unknown"

            if current_url == last_url and dom_sig == last_dom_sig:
                same_count += 1
            else:
                same_count = 0
                last_url = current_url
                last_dom_sig = dom_sig

            if same_count >= 15 and reload_count < 3:
                self.log(f"🔄 Stuck {same_count} cycles — reloading...")
                try:
                    page.reload(timeout=40000, wait_until="domcontentloaded")
                    self._pc_wait_for_dom_ready(page, timeout=20000)
                except Exception:
                    pass
                same_count = 0
                reload_count += 1
                time.sleep(1.0)
                continue

            self.log(f"→ [Step {step_iter + 1}] URL: {current_url[:60]}")
            page_info = self._pc_detect_auth_page(page)
            page_type = page_info.get("type", "unknown")

            if page_type == "success":
                return True
            if page_type == "save_login_info":
                if self._dismiss_save_login_info(page):
                    time.sleep(1.5)
                    continue
            if page_type == "human_check":
                if self._pc_handle_human_check(page, max_attempts=8):
                    continue
                time.sleep(2.0)
                continue
            if page_type == "account_select":
                if self._pc_click_first_account(page):
                    time.sleep(1.5)
                    continue
                if self._pc_click_continue_button(page):
                    time.sleep(1.5)
                    continue
            elif page_type == "login_page":
                if self._pc_click_text_button(page, "Log in"):
                    time.sleep(1.5)
                    continue
                if self._pc_click_text_button(page, "Continue"):
                    time.sleep(1.5)
                    continue
            elif page_type == "image_upload":
                return "IMAGE_UPLOAD"
            elif page_type == "profile_continue":
                if self._pc_click_continue_button(page):
                    time.sleep(1.5)
                    continue

            # Fallbacks exactly as in PC tool:
            if self._pc_click_continue_button(page):
                time.sleep(1.2)
                continue
            if self._pc_wait_for_text_visible(page, "Log in", timeout=1200, exact=True):
                self._pc_click_text_button(page, "Log in")
                time.sleep(1.2)
                continue
            if self._pc_click_first_account(page):
                time.sleep(1.5)
                continue
            time.sleep(0.9)

        if self._pc_check_success(page):
            return True
        return None

    def _meta_new_way_shortcut(self, p) -> bool:
        """New way (1:1 parity with PC tool PC_USER_WORK_FREE.exe):
        Runs the full post-OTP state machine on auth.meta.com:
        - navigates to https://auth.meta.com
        - solves captchas & human verification
        - resolves account chooser ('Continue as...', 'Choose an account')
        - handles profile continuations ('Continue', 'Next', 'Confirm')
        - handles image upload prompts using img/ folder
        - recovers from stuck cycles via reload
        - verifies final success when settled on auth.meta.com/language or meta.ai
        """
        self.log('[🆕] New way (PC tool flow): starting post-OTP flow on auth.meta.com…')
        try:
            # If the page object is a mock or lacks evaluate (e.g., unit test), support basic fallback
            if not hasattr(p, "evaluate"):
                try:
                    p.goto("https://auth.meta.com", wait_until="domcontentloaded", timeout=45000)
                except Exception as exc:
                    self.log(f'[🆕] Navigation failed ({str(exc)[:60]}) — using normal checks.')
                    return False
                u = (getattr(p, "url", "") or "").lower()
                if "checkpoint" in u or self._has_human_check(p):
                    return False
                return bool("language" in u and self._wait_meta_provisioned(p, timeout=20))

            res = self._pc_post_otp_flow(p)
            if res == "CAPTCHA_FAILED":
                self.log('[🆕] New way: Captcha solve failed in post-OTP flow — using normal checks.')
                return False
            if res == "IMAGE_UPLOAD":
                upload_ok = self._pc_upload_random_image(p)
                if upload_ok:
                    res2 = self._pc_post_otp_flow(p)
                    if res2 == "CAPTCHA_FAILED":
                        return False
            time.sleep(0.8)
            self._pc_try_image_upload_if_present(p)
            try:
                p.wait_for_load_state("networkidle", timeout=25000)
            except Exception:
                pass
            time.sleep(2.0)
            self._dismiss_save_login_info(p)

            # Terminal IP/network check
            if _meta_ip_blocked(p):
                raise MetaCheckpointBlocked(
                    'Meta human-verification checkpoint refused the request '
                    '("Try again later" / "sending automated queries").'
                )

            # Check final URL, settled status, or direct success
            cur_url = (getattr(p, "url", "") or "").lower()
            is_success = (
                self._pc_check_final_url_for_save(p)
                or bool(self._pc_check_success(p))
                or (res is True)
                or ("auth.meta.com" in cur_url and "checkpoint" not in cur_url and self._wait_meta_provisioned(p, timeout=15))
            )

            if is_success and not self._has_human_check(p):
                self.log('<font color="#00FF00"><b>[🆕] New way: Meta account settled & verified via PC tool flow.</b></font>')
                return True

            self.log('[🆕] New way: post-OTP did not settle — using the normal checks.')
            return False
        except MetaCheckpointBlocked:
            raise
        except Exception as exc:
            self.log(f'[🆕] New-way error ({str(exc)[:80]}) — using the normal checks.')
            return False

    def ensure_meta_verified(self, timeout: int = 600) -> bool:
        """Human verification, done intentionally like before.

        Called right after Meta signup/login success: visits the checkpoint
        front door on purpose and solves reCAPTCHA + selfie until clear.
        Only after this returns does the flow move to Instagram.
        """
        p = self.page
        per = max(120, timeout // 4)
        # EXPERIMENTAL "new way" (dashboard: Meta method = New way): try the PC tool's shortcut first. When it is
        # not conclusive the unchanged checks below run, exactly as in the old way.
        if str(os.environ.get("INSTA_META_FLOW", "old")).strip().lower() == "new":
            try:
                if self._meta_new_way_shortcut(p):
                    return True
            except Exception as exc:
                self.log(f'[🆕] New-way shortcut error ({str(exc)[:80]}) — using the normal checks.')
        for attempt in range(1, 5):
            self.log(f'[🛡️] Meta human verification — attempt {attempt}')
            self._dismiss_cookie_choice(p)
            self._dismiss_save_login_info(p)
            cur_url = (p.url or "").lower()
            cur_body = ""
            try:
                cur_body = (p.inner_text("body") or "").lower()
            except Exception:
                pass

            # Terminal IP/network block — bail BEFORE attempting to solve, or we
            # park the slot on a dead screen and burn the account. Raises so the
            # cycle closes the browser and moves on (IGDeadEnd semantics).
            if _meta_ip_blocked(p) or _meta_ip_blocked(cur_body, cur_url):
                raise MetaCheckpointBlocked(
                    'Meta human-verification checkpoint refused the request '
                    '("Try again later" / "sending automated queries") — an '
                    'IP/network block, not a solvable captcha. Closing the '
                    'browser and moving to the next account.')

            # Already clear on meta.ai with no active human check/checkpoint.
            is_meta_ai_success = (
                any(x in cur_url for x in ("meta.ai/?", "meta.ai/home", "meta.ai/chat", "meta.ai/prompt"))
                and "error=" not in cur_url
                and "sign in to get started" not in cur_body
            )
            has_checkpoint = self._has_human_check(p) or "confirm" in cur_body or "checkpoints" in cur_url
            if is_meta_ai_success and not has_checkpoint:
                self.log('<font color="#00FF00"><b>[✔] Meta session authenticated on meta.ai naturally.</b></font>')
                return True

            # If on a checkpoint or attempt > 1 with no meta.ai success, check auth.meta.com
            if attempt > 1 or (not is_meta_ai_success and "checkpoints" not in cur_url and not has_checkpoint and "auth.meta.com" not in cur_url):
                try:
                    p.goto(run._META_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
                    p.wait_for_timeout(4000)
                except Exception:
                    pass

            try:
                cur_body = (p.inner_text("body") or "").lower()
            except Exception:
                pass
            cur_url = (p.url or "").lower()

            # Account chooser ("Log in with your Meta Account"): click the
            # saved account row FIRST — human verification comes after it
            # (live 2026-09-17). The row shows a MASKED email, so match any
            # @ row except "Use another account".
            if "log in with your meta account" in cur_body or "use another account" in cur_body:
                self.log('[🌐] Meta account chooser — clicking the saved account row…')
                try:
                    hit = p.evaluate("""() => {
                        const els = [...document.querySelectorAll('button, div[role="button"], a')];
                        for (const el of els) {
                            const t = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
                            const r = el.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) continue;
                            if (t.includes('use another account')) continue;
                            if (t.includes('@')) { el.click(); return true; }
                        }
                        return false;
                    }""")
                except Exception:
                    hit = False
                if not hit and getattr(self, "email", None):
                    # Unmasked variant: try our full email as button text.
                    hit = self._try_click(p, self.email, timeout=4000)
                p.wait_for_timeout(4000)
                self._poll_checkpoint_settled(p, timeout=8)
                try:
                    cur_body = (p.inner_text("body") or "").lower()
                except Exception:
                    pass
                cur_url = (p.url or "").lower()

            # "Check your email" re-login (shown after the chooser, or on its own).
            if self._meta_login_challenge(p):
                try:
                    cur_body = (p.inner_text("body") or "").lower()
                except Exception:
                    pass
                cur_url = (p.url or "").lower()

            # Stuck-checkpoint guard: auth.meta.com/checkpoint… that only ever
            # renders grey placeholder bars (skeleton) — no reCAPTCHA, no
            # Continue. Nothing to solve and nothing to click, so the 4 retries
            # just burn the whole 600s window. Wait ~12s for real controls; if
            # none appear, dead-end now (close + next account).
            if "checkpoint" in cur_url or "checkpoint" in cur_body or "checkpoints" in cur_url:
                _ready = False
                for _ in range(12):
                    try:
                        _n = p.evaluate("""() => {
                            const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
                            const btns = Array.from(document.querySelectorAll('button, div[role="button"]')).filter(vis);
                            const inps = Array.from(document.querySelectorAll('input')).filter(vis);
                            return btns.length + inps.length;
                        }""")
                    except Exception:
                        _n = 1
                    if _n:
                        _ready = True
                        break
                    p.wait_for_timeout(1000)
                if not _ready and self._has_human_check(p) is False and "confirm" not in cur_body:
                    self.log('[🛡️] Meta checkpoint is a stuck skeleton (no controls rendered in 12s) '
                             '— dead end; closing and moving to the next account.')
                    raise MetaCheckpointBlocked(
                        "Meta checkpoint rendered no controls (stuck loading skeleton) — "
                        "dead end, not a solvable captcha")

            if self._has_human_check(p) or "confirm" in cur_body or "checkpoints" in cur_url:
                self._try_click(p, "Continue", timeout=8000)
                self._poll_checkpoint_settled(p, timeout=8)
                # reCAPTCHA audio + selfie + Continue. The selfie result GATES:
                # an upload that never cleared must not ride on into Instagram
                # (Meta answers with the phone wall and burns the account).
                selfie_ok = self._meta_selfie_checkpoint(p, timeout=per)
                self._try_click(p, "Continue", timeout=8000)
                self._poll_checkpoint_settled(p, timeout=8)
                if selfie_ok is False and self.w.is_running:
                    raise RuntimeError(
                        "Meta selfie checkpoint never accepted the upload "
                        "(file sent, prompt never cleared) — NOT verified, "
                        "closing and moving to the next account instead of "
                        "driving an unverified account into Instagram")
                # Early exit: as soon as the human check is gone we are DONE.
                # The old code also required "checkpoints" to leave the URL, so
                # it ran attempts 2-4 (each re-entering the selfie checkpoint)
                # for ~23s AFTER the selfie had already been accepted.
                if not self._has_human_check(p) and not self._needs_meta_relogin(p):
                    self.log('<font color="#00FF00"><b>[✔] Meta human verification cleared.</b></font>')
                    self._maybe_accept_meta_terms(p)
                    self._wait_meta_provisioned(p, timeout=45)
                    return True
            if (not self._has_human_check(p) and "checkpoints" not in (p.url or "")
                    and not self._needs_meta_relogin(p)):
                self.log('<font color="#00FF00"><b>[✔] Meta human verification cleared.</b></font>')
                self._maybe_accept_meta_terms(p)
                self._wait_meta_provisioned(p, timeout=45)
                return True
            p.wait_for_timeout(3000)
        self.log('[⚠️] Meta human verification still pending.')
        return not self._has_human_check(p)

    def _recaptcha_anchor_checked(self, anchor):
        """Return True for both ARIA and Google checkbox state variants."""
        if anchor is None:
            return False
        try:
            cb = anchor.locator("#recaptcha-anchor").first
            if cb.count() == 0:
                return False
            try:
                aria = (cb.get_attribute("aria-checked") or "").strip().lower()
                if aria == "true":
                    return True
                if aria == "false":
                    return False
            except Exception:
                pass
            return bool(cb.evaluate("""el => {
                const aria = (el.getAttribute('aria-checked') || '').trim().toLowerCase();
                if (aria === 'true') return true;
                if (aria === 'false') return false;
                const root = el.closest('.recaptcha-checkbox') || el.parentElement || el;
                const cls = (root.className || '').toLowerCase();
                if (cls.includes('recaptcha-checkbox-unchecked') || cls.includes('rc-anchor-checkbox-noglow')) return false;
                if (cls.includes('recaptcha-checkbox-checked')) return true;
                const state = [cls, root.getAttribute('data-state') || '',
                               root.getAttribute('aria-label') || ''].join(' ').toLowerCase();
                if (state.includes('unchecked')) return false;
                return /(^|\\s|-)checked(\\s|$)/.test(state) || /(^|\\s|-)verified(\\s|$)/.test(state);
            }"""))
        except Exception:
            return False

    def _captcha_order(self):
        """Solver order: Visual AI (JA YOLOv5 ONNX) only. Audio STT/Whisper removed for CPU/RAM performance."""
        if os.environ.get("INSTA_ENABLE_AUDIO_CAPTCHA", "0") == "1":
            return ("audio", "extension") if getattr(self, "captcha_mode", "extension") == "audio" else ("extension", "audio")
        return ("extension",)

    def _extension_available(self):
        """True when the Visual AI extension directory is present."""
        try:
            from ai_config import CAPTCHA_EXT_DIR
            return bool(CAPTCHA_EXT_DIR and os.path.isdir(CAPTCHA_EXT_DIR))
        except Exception:
            return False

    def _extension_active(self):
        """True when the JA extension is actually RUNNING in this browser.

        Headless shell (Background mode) silently ignores --load-extension,
        so the extension directory can exist while nothing runs. Since we
        launch with --disable-extensions-except, ANY running extension
        worker must be ours.
        """
        try:
            ctx = getattr(getattr(self, "w", None), "context", None)
            if ctx is None:
                return False
            urls = [w.url for w in list(ctx.service_workers) + list(ctx.background_pages)]
            return any((u or "").startswith("chrome-extension://") for u in urls)
        except Exception:
            return False

    def _wait_for_extension_solve(self, page, timeout=90):
        """Skip Visual immediately when the extension isn't running.

        Without this, every Background-mode checkpoint burns 45s waiting
        for an extension that headless shell can never load, before
        falling back to Audio STT anyway.
        """
        if not self._extension_active():
            self.log("[🧩] Visual AI extension not active in this browser context.")
            return False
        return super()._wait_for_extension_solve(page, timeout=timeout)

    def _solve_captcha_ordered(self, page):
        """Try solvers in dashboard order; True when the check clears."""
        for solver in self._captcha_order():
            try:
                if not self._has_human_check(page):
                    return True
            except Exception:
                return True
            try:
                if solver == "extension":
                    if not self._extension_available():
                        continue
                    try:
                        _vt = float(os.environ.get("INSTA_VISUAL_CAPTCHA_TIMEOUT", "25") or 25)
                    except Exception:
                        _vt = 25.0
                    if self._wait_for_extension_solve(page, timeout=_vt):
                        return True
                    if "audio" in self._captcha_order():
                        self.log("[⚠️] Visual AI did not finish; falling back to Audio STT…")
                    else:
                        self.log("[⚠️] Visual AI did not finish in time.")
                elif solver == "audio":
                    self._in_extension_fallback = ("extension" in self._captcha_order())
                    if self._solve_recaptcha_audio(page, tries=2):
                        return True
                    self.log("[⚠️] Audio STT did not finish.")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[⚠️] {solver} solver error: {exc}")
        # Also try image captcha if present
        try:
            if self._solve_image_captcha(page):
                return True
        except Exception as exc:
            self.log(f"[⚠️] Image captcha error in ordered solver: {exc}")
        return False

    def _solve_image_captcha(self, page, max_attempts: int = 3) -> bool:
        """OCR Instagram/Meta 'enter the code from the image' captcha with RapidOCR."""
        try:
            if not page.get_by_text("Enter the code from the image", exact=False).is_visible():
                return False
        except Exception:
            return False
        try:
            ocr_engine = self._ensure_ocr()
        except Exception as exc:
            if os.environ.get("META_DEBUG"):
                self.log(f'[debug] OCR engine unavailable: {exc}')
            return False

        for attempt in range(max_attempts):
            best, best_area = None, 0
            try:
                for img in page.locator("img").all():
                    try:
                        box = img.bounding_box()
                        if box and box["width"] > 60 and box["height"] > 30:
                            area = box["width"] * box["height"]
                            if area > best_area:
                                best, best_area = img, area
                    except Exception:
                        pass
            except Exception:
                pass

            if best is None:
                try:
                    if not page.get_by_text("Enter the code from the image", exact=False).is_visible():
                        return True
                except Exception:
                    pass
                return False

            try:
                shot = best.screenshot()
            except Exception as exc:
                self.log(f'[⚠️] Could not capture captcha screenshot: {exc}')
                return False

            try:
                from engine.eng_mix_audio import _OCR_INFER_LOCK, HERE
                png = os.path.join(HERE, f"captcha_img_{attempt}.png")
                with open(png, "wb") as f:
                    f.write(shot)
                with _OCR_INFER_LOCK:
                    result, _ = ocr_engine(png)
            except Exception as exc:
                self.log(f'[⚠️] RapidOCR inference error: {exc}')
                return False

            # Direct recognizer with multi-padding bounding box crop
            # Instagram captchas are 6 characters with blank side margins and thin scratch lines
            candidates = []
            try:
                import cv2
                img_arr = cv2.imread(png)
                if img_arr is not None:
                    gray = cv2.cvtColor(img_arr, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
                    pts = cv2.findNonZero(thresh)
                    if pts is not None and hasattr(ocr_engine, "text_recognizer"):
                        x, y, w, h = cv2.boundingRect(pts)
                        for pad in (5, 2, 8, 0, 10):
                            x0 = max(0, x - pad)
                            y0 = max(0, y - pad)
                            w0 = min(img_arr.shape[1] - x0, w + 2 * pad)
                            h0 = min(img_arr.shape[0] - y0, h + 2 * pad)
                            crop = img_arr[y0:y0 + h0, x0:x0 + w0]
                            rec_res, _ = ocr_engine.text_recognizer(crop)
                            if rec_res and rec_res[0] and rec_res[0][0]:
                                cand = "".join(c for c in str(rec_res[0][0]) if c.isalnum())
                                conf = float(rec_res[0][1]) if len(rec_res[0]) > 1 else 0.5
                                candidates.append((len(cand) == 6, conf, cand))
            except Exception as ocr_crop_exc:
                self.log(f'[⚠️] OCR crop note: {ocr_crop_exc}')

            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
                best_cand = candidates[0]
                result = [[None, best_cand[2], best_cand[1]]]
            elif not result and hasattr(ocr_engine, "text_recognizer"):
                try:
                    rec_res, _ = ocr_engine.text_recognizer(img_arr)
                    if rec_res and rec_res[0] and rec_res[0][0]:
                        cand = "".join(c for c in str(rec_res[0][0]) if c.isalnum())
                        score = float(rec_res[0][1]) if len(rec_res[0]) > 1 else 0.5
                        result = [[None, cand, score]]
                except Exception:
                    pass

            code = "".join(t[1] for t in result).replace(" ", "").strip() if result else ""

            # Instagram captcha is 6 characters. If < 6 characters and we have attempts left,
            # refresh the image rather than submitting a guaranteed-rejected code!
            if (not code or len(code) < 6) and attempt < (max_attempts - 1):
                self.log(f'[⚠️] Decoded code "{code}" incomplete (<6 chars, attempt {attempt + 1}/{max_attempts}) — refreshing image…')
                for rel_sel in (
                    'a:has-text("can\'t read this text")',
                    'button:has-text("can\'t read this text")',
                    '[role="button"]:has-text("can\'t read this text")',
                    'button[aria-label*="new code" i]',
                    'button[aria-label*="reload" i]',
                    'a:has-text("Try another code")',
                    'button:has-text("Try another code")',
                ):
                    try:
                        r = page.locator(rel_sel).first
                        if r.count() > 0 and r.is_visible():
                            r.click()
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass
                continue

            if not code:
                self.log(f'[⚠️] RapidOCR detected no text in captcha (attempt {attempt + 1}/{max_attempts})')
                continue

            self.log(f'[🤖] RapidOCR decoded image captcha: "{code}" (attempt {attempt + 1}/{max_attempts})')

            input_box = None
            try:
                for inp in page.locator("input:visible").all():
                    try:
                        t = (inp.get_attribute("type") or "text").lower()
                        if t not in ("hidden", "submit", "button", "checkbox", "radio", "image", "file"):
                            input_box = inp
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            if input_box is None:
                try:
                    for tb in page.get_by_role("textbox").all():
                        if tb.is_visible():
                            input_box = tb
                            break
                except Exception:
                    pass

            if input_box is None:
                for sel in (
                    'input:not([type="hidden"])',
                    'input[type="text"]',
                    'input',
                    'textarea',
                    '[contenteditable="true"]',
                ):
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            input_box = el
                            break
                    except Exception:
                        continue

            if input_box is None:
                self.log('[⚠️] Image captcha input element not found')
                return False

            try:
                input_box.click(timeout=3000)
            except Exception:
                pass
            try:
                input_box.fill(code, timeout=3000)
            except Exception:
                pass
            try:
                if hasattr(self, "_human_type"):
                    self._human_type(input_box, code)
            except Exception:
                pass
            try:
                input_box.evaluate(
                    "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
                    code,
                )
            except Exception:
                pass
            try:
                input_box.press("Enter", timeout=3000)
            except Exception as fill_exc:
                self.log(f'[⚠️] Note on typing captcha code: {fill_exc}')

            # Tap submission buttons (Next, Continue, Submit, Confirm)
            tapped = False
            for btn_name in ("Next", "Continue", "Submit", "Confirm"):
                for btn_sel in (
                    f'button:has-text("{btn_name}")',
                    f'[role="button"]:has-text("{btn_name}")',
                    f'input[type="submit"][value*="{btn_name}" i]',
                    'button[type="submit"]',
                ):
                    try:
                        b = page.locator(btn_sel).first
                        if b.count() > 0 and b.is_visible():
                            b.click(timeout=3000)
                            tapped = True
                            break
                    except Exception:
                        pass
                if tapped:
                    break

            for _wait in range(8):
                page.wait_for_timeout(1000)
                try:
                    body_now = (page.inner_text("body") or "").lower()
                except Exception:
                    body_now = ""
                # Screen has transitioned if none of the captcha prompts remain
                captcha_active = any(k in body_now for k in (
                    "can't read this text",
                    "hear this code",
                    "enter the code from the image",
                    "enter the code",
                ))
                if not captcha_active:
                    self.log(f'[✔] Image captcha submitted and screen transitioned! URL: {page.url}')
                    return True
                if any(err in body_now for err in ("incorrect code", "try again", "wrong code", "invalid code")):
                    self.log(f'[⚠️] Captcha code "{code}" was rejected; retrying with refreshed image…')
                    break

        return False

    # -- selfie upload -----------------------------------------------------
    # Core owns the selfie path (CaptchaMixin wins over the engine mixin). The
    # engine copy gated success on a preview / enabled Continue, which Meta
    # renders asynchronously, so good uploads were reported as failed.

    def _selfie_path(self):
        """Selfie image: ``self.selfie_path``, else a pick from selfies/ or img/."""
        path = getattr(self, "selfie_path", None)
        if not path or not os.path.exists(path):
            try:
                from ai_config import get_random_selfie
                path = get_random_selfie()
                self.selfie_path = path
            except Exception:
                path = None
        return path if path and os.path.exists(path) else None

    def _selfie_file_inputs(self, page, per_frame=4):
        """Every ``input[type=file]`` in every frame, hidden ones included.

        Keeps up to ``per_frame`` inputs per frame: a decoy input ahead of the
        real dropzone used to hide the real one.
        """
        try:
            frames = list(page.frames)
        except Exception:
            frames = [page]
        out = []
        for fr in frames:
            try:
                loc = fr.locator('input[type="file"]')
                out.extend(loc.nth(i) for i in range(min(loc.count(), per_frame)))
            except Exception:
                continue
        return out

    def _upload_selfie(self, page):
        """Send the selfie to the checkpoint. True once the browser has attached
        the file to a real file input, the page's file chooser, or CDP.

        True means only "sent". The caller decides whether Meta accepted it:
        it waits for Continue (_wait_selfie_continue) and checks the prompt
        cleared. Returning False here is reserved for "no path accepted the file".
        """
        path = self._selfie_path()
        if not path:
            self.log('[⚠️] No selfie image found — put "selfie.png" next to run.py '
                     'or images in selfies/.')
            return False
        name = os.path.basename(path)

        # The React dropzone mounts a beat after the heading: wait up to ~4s.
        for _ in range(8):
            if self._selfie_file_inputs(page, per_frame=1):
                break
            page.wait_for_timeout(500)

        # 1) Set the file directly on each input, in every frame.
        for inp in self._selfie_file_inputs(page):
            try:
                try:
                    inp.set_input_files(path, timeout=20000)
                except Exception:
                    # Some builds only accept the file once the input is shown.
                    inp.evaluate("el => { el.style.display='block'; el.style.visibility='visible'; el.style.opacity=1; }")
                    inp.set_input_files(path, timeout=20000)
                self.log(f'<font color="#00FF00"><b>[🖼️] Selfie sent: {name}</b></font>')
                return True
            except Exception as exc:
                self.log(f'[i] file input rejected the selfie ({exc}); trying next path…')

        # 2) Click the page's upload control and answer the file chooser it opens.
        for sel in (
            'button:has-text("Upload Image")',
            '[role="button"]:has-text("Upload Image")',
            'label:has-text("Upload Image")',
            'div:has-text("Upload Image")',
            'span:has-text("Upload Image")',
            'text=Upload Image',
            'button:has-text("Upload")',
        ):
            try:
                loc = page.locator(sel).last
                if loc.count() == 0 or not loc.is_visible():
                    continue
                try:
                    with page.expect_file_chooser(timeout=8000) as fc:
                        try:
                            loc.click(timeout=6000)
                        except Exception:
                            loc.evaluate("el => el.click()")
                    fc.value.set_files(path)
                except Exception:
                    box = loc.bounding_box()
                    if not box:
                        continue
                    with page.expect_file_chooser(timeout=8000) as fc:
                        page.mouse.click(box["x"] + box["width"] / 2,
                                         box["y"] + box["height"] / 2)
                    fc.value.set_files(path)
                self.log(f'<font color="#00FF00"><b>[🖼️] Selfie sent via chooser: {name}</b></font>')
                return True
            except Exception:
                continue

        # 3) CDP last resort: sets the file on inputs the locator API cannot reach
        # (shadow DOM).
        try:
            if self._cdp_set_file_input(page, path):
                self.log(f'<font color="#00FF00"><b>[🖼️] Selfie sent (CDP): {name}</b></font>')
                return True
        except Exception:
            pass

        self.log('[⚠️] Selfie upload failed — no file input accepted the image. '
                 'Meta may have changed the checkpoint UI; upload manually in the window.')
        return False

    def _wait_selfie_continue(self, page, timeout=30) -> bool:
        """Wait until Meta enables Continue after processing the selfie, then click it.

        Meta enables Continue only once the image is processed, several seconds
        after the file is attached. A click on the disabled button did nothing, the
        prompt never cleared, and the caller re-uploaded every 5s. True if clicked.
        """
        end = time.time() + timeout
        while time.time() < end and self.w.is_running:
            if self._checkpoint_action(page, names=("Continue",), require_enabled=True) is not None:
                if self._click_checkpoint_action(page, "Continue", timeout=3000):
                    return True
                return self._try_click(page, "Continue", timeout=4000)
            page.wait_for_timeout(500)
        return False

    def _meta_selfie_checkpoint(self, page, timeout=900):
        """Checkpoint flow with dashboard-ordered solvers (ordered).

        Overrides the engine version so the attempt order follows the
        dashboard captcha choice (chosen first, the other on fallback)
        instead of the engine's fixed audio-first sequence.

        The selfie upload is RETRIED until the checkpoint accepts the image
        (a single transient failure must not wedge the run — the old code
        uploaded once and then spun on a disabled Continue), and the generic
        file-input photo checkpoint is handled too (engine helpers).

        Returns True when no selfie was required or the upload was ACCEPTED
        (prompt gone). Returns False when a selfie upload was attempted but
        the checkpoint never cleared — the caller must NOT drive the account
        onward (Meta answers with the phone wall). Never raises for Stop:
        when the worker is stopping the result is untrusted, so True.
        """
        end = time.time() + timeout
        uploaded = False
        accepted = False
        saw_selfie = False
        uploaded_ever = False
        last_attempt = 0.0
        first_attempt_done = False

        def _cleared() -> bool:
            """True once the selfie prompt is gone — i.e. the checkpoint PASSED."""
            try:
                return not page.get_by_text("Upload a verification selfie",
                                            exact=False).first.is_visible()
            except Exception:
                return True

        while time.time() < end and self.w.is_running:
            try:
                if page.get_by_text("Upload a verification selfie",
                                    exact=False).first.is_visible():
                    saw_selfie = True
                    # Attempt IMMEDIATELY the first time (no 5s throttle), then
                    # retry every 5s so a single transient miss can't wedge.
                    due = (not first_attempt_done) or (time.time() - last_attempt) > 5
                    if not uploaded and due:
                        last_attempt = time.time()
                        first_attempt_done = True
                        uploaded = bool(self._upload_selfie(page))
                        uploaded_ever = uploaded_ever or uploaded
                    if uploaded:
                        self._wait_selfie_continue(page, timeout=30)
                        self._poll_checkpoint_settled(page, timeout=8)
                        # 'uploaded' only means a file was SENT. Confirm the
                        # checkpoint actually advanced before believing it —
                        # otherwise we drive an unverified account onward and
                        # Meta answers with the phone wall. Re-arm the latch so
                        # a genuine retry (re-upload) can still happen.
                        if _cleared():
                            accepted = True
                            # The prompt is gone, but the account may not be
                            # PROVISIONED yet — the IG join downstream is what
                            # suffers if we leave now. Wait for the real
                            # post-signup state (auth.meta.com/language +
                            # accountId); returns instantly if already there.
                            self._wait_meta_provisioned(page, timeout=45)
                        else:
                            uploaded = False
                        continue
                    else:
                        page.wait_for_timeout(1500)
                    continue
            except Exception:
                pass
            # NOTE: no break here — falling through is required so the generic
            # file-input photo checkpoint and the captcha branch still run.
            # 'accepted' is set by _cleared() inside the selfie branch above.
            # PC post-OTP photo checkpoint: generic file-input variant of the
            # selfie screen (no "Upload a verification selfie" text).
            try:
                if self._try_image_upload_if_present(page):
                    saw_selfie = True
                    uploaded = True
                    uploaded_ever = True
                    self._wait_selfie_continue(page, timeout=30)
                    self._poll_checkpoint_settled(page, timeout=8)
                    continue
            except Exception:
                pass
            if self._has_human_check(page):
                if _meta_ip_blocked(page):
                    raise MetaCheckpointBlocked(
                        'Meta human-verification checkpoint refused the request '
                        '("Try again later" / "sending automated queries") — an '
                        'IP/network block, not a solvable captcha. Closing the '
                        'browser and moving to the next account.')
                solved = self._solve_captcha_ordered(page)
                if solved or not self._has_human_check(page):
                    clicked = False
                    if hasattr(self, "_click_checkpoint_action"):
                        clicked = self._click_checkpoint_action(page, "Continue", timeout=3000)
                    if not clicked:
                        self._try_click(page, "Continue", timeout=4000)
                    self._poll_checkpoint_settled(page, timeout=10)
                    continue
                if _meta_ip_blocked(page):
                    raise MetaCheckpointBlocked(
                        'Meta human-verification checkpoint refused the request '
                        '("Try again later" / "sending automated queries") — an '
                        'IP/network block, not a solvable captcha. Closing the '
                        'browser and moving to the next account.')
                self._poll_checkpoint_settled(page, timeout=5)
                continue
            break
        if accepted:
            self.log('<font color="#00FF00"><b>[VERIFIED] Verification selfie '
                     'accepted — checkpoint cleared.</b></font>')
        elif uploaded:
            self.log('<font color="#FFA500"><b>[⚠️] Selfie file was sent but the '
                     'checkpoint never cleared (Continue did not take) — treating '
                     'as NOT verified.</b></font>')
        else:
            self.log('[⚠️] Selfie checkpoint ended without a confirmed upload.')
        if not self.w.is_running:
            return True
        if not saw_selfie:
            # No selfie UI ever appeared — nothing to gate on.
            return True
        if not accepted and uploaded_ever:
            # The clear may have landed via a later Continue (captcha leg)
            # after the last _cleared() check — re-evaluate once now.
            try:
                accepted = _cleared()
            except Exception:
                accepted = False
        return accepted

    def _wait_meta_provisioned(self, page, timeout: int = 90) -> bool:
        """Poll until Meta has actually finished creating the account.

        Why this exists (2026-09-26): after the selfie checkpoint was accepted we
        clicked "Create account" and then slept a FIXED 4s before moving on to
        Instagram. Meta provisions the account (and settles the profile/IG
        linkage) asynchronously, so a 4s blind wait means the IG join routinely
        starts against a half-built account — the most plausible trigger for the
        intermittent "What's your mobile number?" wall (IGDeadEnd burns the
        whole account). This is invariant 19 applied to the one place that still
        had a blind sleep.

        GROUND TRUTH for the settled state (captured from the real post-signup
        page, do NOT guess this again): the account is created ON auth.meta.com
        and lands on **/language** — FRLXAuthSettingsController /
        FRLAuthSettingsRoot.react — carrying a real identity:

            "page_uri":"https://auth.meta.com/language"
            "accountId":"1271284112744162"  "accountName":"opossum_deer_4700"
            "isFetaAccount":true  "has_meta_ai_profile":true
            OCSession + OCSessionToken  (a live session, i.e. really signed in)

        NOTE the page never leaves auth.meta.com on this path, so a
        "did we reach facebook.com" test can NEVER pass here — it just burns the
        full timeout on every account. The URL is the cheap primary signal; the
        accountId is read once, only after the URL matches, purely to log proof.

        Returns True on a settled signal. On timeout it returns False and the
        caller continues anyway — an optimisation, never a new gate that can
        fail an account.
        """
        import re as _re
        import time as _t
        deadline = _t.time() + max(15, int(timeout or 90))
        lang_first_seen = None
        while _t.time() < deadline:
            try:
                url = str(page.url or '')
                # Primary (cheap, decisive): the settings page on the auth host.
                if 'auth.meta.com' in url and ('/language' in url or '/settings' in url):
                    if lang_first_seen is None:
                        lang_first_seen = _t.time()
                    try:
                        html = page.content() or ''
                    except Exception:
                        html = ''
                    m = _re.search(r'"accountId":"(\d+)"', html)
                    nm = _re.search(r'"accountName":"([^"]+)"', html)
                    if m:
                        self.log(f'[⏱️] Meta provisioned — accountId={m.group(1)}'
                                 + (f' name={nm.group(1)!r}' if nm else '')
                                 + ' (auth.meta.com/language, session live)')
                        return True
                    # Give React up to 5s to populate accountId before accepting bare page
                    if (_t.time() - lang_first_seen) > 5:
                        self.log('[⏱️] Meta provisioned — reached auth.meta.com/language '
                                 '(no accountId in HTML yet, session settled).')
                        return True
                # Secondary: some builds do continue into the product surface.
                if 'facebook.com' in url and 'auth.meta.com' not in url:
                    self.log(f'[⏱️] Meta provisioned (left auth host): {url[:90]}')
                    return True
            except Exception:
                pass
            page.wait_for_timeout(700)
        self.log('[⏱️] Meta provision wait timed out — continuing anyway '
                 '(optimisation only, not a gate).')
        return False

    def _maybe_accept_meta_terms(self, page) -> bool:
        """Handle Meta's mid-flow dialogs ('Create account', 'Not now', 'I agree')."""
        if self._dismiss_cookie_choice(page):
            return True
        try:
            # 1. "Finish creating your Meta account" -> "Create account" button
            btn = page.get_by_role("button", name="Create account").first
            if btn.is_visible():
                btn.click()
                self.log('<font color="#00FF00"><b>[✔] Meta: clicked "Create account".</b></font>')
                # Was a fixed 4s blind sleep — the account was then driven into
                # Instagram possibly before Meta finished provisioning it.
                self._wait_meta_provisioned(page)
                return True
        except Exception:
            pass

        try:
            # 2. "Save your login info?" -> "Not now"
            btn = page.get_by_role("button", name="Not now").first
            if btn.is_visible():
                btn.click()
                self.log('[✔] Meta: clicked "Not now".')
                page.wait_for_timeout(3000)
                return True
        except Exception:
            pass

        try:
            # 3. New signup consent page ('To sign up, read and agree to our terms' → 'I agree')
            if (page.get_by_text("read and agree to our terms", exact=False).count() > 0
                    or page.get_by_text("Key points you should know", exact=False).count() > 0):
                for nm in ("I agree", "Agree"):
                    try:
                        btn = page.get_by_role("button", name=nm).first
                        if btn.is_visible():
                            btn.click()
                            self.log('<font color="#00FF00"><b>[✔] Meta: accepted new '
                                     'terms ("I agree").</b></font>')
                            page.wait_for_timeout(4500)
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False
