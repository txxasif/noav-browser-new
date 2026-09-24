"""
meta_auto_ai — Telegram Taskly-bot client
=========================================
Drives the **Taskly Bot** on Telegram Web for task submission using a
**persistent profile** (``telegram_profile/``). Log in once with
``python tg_login.py``; every run reuses that session.
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_config import (  # noqa: E402
    TELEGRAM_PROFILES_DIR,
    TELEGRAM_URL,
    TG_BOT_NAME,
    TG_BOTS,
    TG_DEFAULT_TASK,
)
from tg_fingerprint import for_profile, launch_kwargs, apply_to_context, proxy_for  # noqa: E402


# ==============================================================================
# SECTION 0: BOT-REPLY CLASSIFICATION (submit verdict)
# ==============================================================================
# The bot's reply after "Account registered" is a REPORT VERDICT. Rejection must
# be checked FIRST: the rejection text contains the word "registered"
# ("...was registered without an email address"), so the old accept-only check
# recorded a rejected report as Submitted — a false positive that burned the
# account and polluted the ledger (observed 2026-09-20).
_REPORT_REJECT_HITS = (
    "report rejected", "report has been rejected", "report was rejected",
    "was rejected", "rejected because", "report was not accepted",
    "report rejected:",
)
_REPORT_ACCEPT_HITS = (
    "report has been received", "report has been accepted",
    "task completed", "please wait", "action completed", "registered",
)


def classify_report_reply(body: str) -> str:
    """Return 'rejected' | 'accepted' | 'unknown' for the bot's submit reply."""
    low = (body or "").lower()
    if any(p in low for p in _REPORT_REJECT_HITS):
        return "rejected"
    if any(p in low for p in _REPORT_ACCEPT_HITS):
        return "accepted"
    return "unknown"


# ==============================================================================
# SECTION 1: LIFECYCLE, MOBILE PROFILE & AUTH STATE
# ==============================================================================
class TelegramTasklyBot:
    """Drives Telegram Task Bots (Taskly Bot / PayGoBot) on Telegram Web for task submission.

    Uses a **persistent profile** (``telegram_profile/``) so the Telegram session
    survives between runs. Log in once with::

        python tg_login.py          # scan the QR, then close

    Then every automation run reuses that session to:
      open bot → 📋 Tasks → pick task → ▶️ Start → send the 2FA key →
      read the one-time code → ✅ Account registered.
    """

    def __init__(self, profile_dir=None, bot_name=None, bot_target="taskly", headless=False, log=print):
        self.profile_dir = profile_dir or os.path.join(TELEGRAM_PROFILES_DIR, "tg_1")
        if bot_target and bot_target in TG_BOTS:
            self.bot_target = bot_target
        elif bot_name and "paygo" in str(bot_name).lower():
            self.bot_target = "paygo"
        else:
            self.bot_target = "taskly"

        cfg = TG_BOTS.get(self.bot_target, TG_BOTS["taskly"])
        self.bot_name = bot_name or cfg["name"]
        self.peer_id = cfg["peer_id"]
        self.bot_url = cfg["url"]
        self.headless = headless
        self.log = log
        self._pw = None
        self.ctx = None
        self.page = None
        self.creds = {}          # {first_name, login, password}
        self.one_time_code = None
        self._attached = False

    def attach(self, ctx, fresh_page=False) -> None:
        """Attach an externally created (warm) context instead of launching.

        Used by the persistent profile pool: each submit gets a FRESH
        isolated context; the browser process underneath is reused.
        ``fresh_page=True`` (two-tab multiplexing) always mints a new page
        so two bot submits never share one.
        """
        self.ctx = ctx
        self._attached = True
        try:
            if fresh_page:
                self.page = ctx.new_page()
            else:
                pages = list(ctx.pages)
                self.page = pages[0] if pages else ctx.new_page()
        except Exception as exc:
            self.page = None
            raise RuntimeError(f"Failed to create page on attached context: {exc}") from exc

    # -- lifecycle ------------------------------------------------------
    def start(self):
        if getattr(self, "_attached", False) or self.ctx is not None:
            # Warm path: context supplied by the pool; just (re)open the chat.
            if self.page is None or self.page.is_closed():
                if self.ctx is None:
                    raise RuntimeError("Cannot start attached bot without context")
                self.page = self.ctx.new_page()
            self.page.goto(self.bot_url, wait_until="domcontentloaded", timeout=60000)
            self.page.wait_for_timeout(4500)
            if not self._logged_in():
                raise RuntimeError(
                    "Telegram profile is not logged in. Run `python tg_login.py`, "
                    "scan the QR code, then retry the automation.")
            self.log(f"[tg] Telegram session ready for {self.bot_name} (profile {os.path.basename(self.profile_dir)}).")
            return self
        # Cold start path: verify profile directory lock is not held by another process
        import warm_pool as _wp
        holder = _wp.lock_holder_alive(self.profile_dir)
        if holder:
            raise RuntimeError(
                f"Cannot launch persistent context: profile {self.profile_dir} is already locked by live pid {holder}"
            )
        _wp.kill_profile_tree(self.profile_dir)
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        channel = "chrome" if (os.path.isfile("/usr/bin/google-chrome") or os.path.isfile("/usr/bin/google-chrome-stable")) else None
        _args = ["--no-first-run", "--no-default-browser-check",
                 "--disable-blink-features=AutomationControlled"]
        if not self.headless:
            # Tile RIGHT; IG/Meta browsers tile LEFT (eng_mix_launch).
            # INSTA_UI_MODE=new (default): Wayland-native visible window — the
            # compositor owns focus, so the bot cannot steal the user's typing.
            # "isolated": force x11 + --window-position for the private display.
            if os.environ.get("INSTA_UI_MODE", "new").strip().lower() in ("new", "desktop", "wayland"):
                _args += ["--window-size=1000,950"]
            else:
                _args += ["--window-size=1000,950", "--window-position=520,0",
                          "--ozone-platform=x11"]
        # Per-profile device identity (tg_fingerprint.py): every Telegram profile
        # used to share one hard-coded UA from one IP, so Telegram linked them and
        # invalidated sessions. Stable for the life of the profile.
        ident = for_profile(self.profile_dir)
        kw = dict(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            args=_args,
        )
        kw.update(launch_kwargs(ident))
        px = proxy_for(self.profile_dir)
        if px:
            kw["proxy"] = px
        if channel:
            kw["channel"] = channel
        self.ctx = self._pw.chromium.launch_persistent_context(**kw)
        apply_to_context(self.ctx, ident)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.goto(self.bot_url, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(4500)
        if not self._logged_in():
            raise RuntimeError(
                "Telegram profile is not logged in. Run `python tg_login.py`, "
                "scan the QR code, then retry the automation.")
        self.log(f"[tg] Telegram session ready for {self.bot_name} (profile {os.path.basename(self.profile_dir)}).")
        return self

    def _logged_in(self):
        try:
            body = (self.page.inner_text("body") or "").lower()
            return not ("log in to telegram" in body or "log in by qr" in body)
        except Exception:
            return False

    def logged_in(self):
        """Public live login probe (thread-safe entrypoints call this).

        Returns True/False when a page is available, else None so callers can
        tell "definitely logged out" apart from "could not check" — a locked
        or just-recycled profile must NOT be mistaken for a dead session.
        """
        try:
            if self.page is None or self.page.is_closed():
                return None
        except Exception:
            return None
        return self._logged_in()

    def close(self):
        try:
            if self.ctx:
                self.ctx.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass


    # ==========================================================================
    # SECTION 2: LOW-LEVEL DOM INTERACTION & REPLY KEYBOARD CONTROLS
    # ==========================================================================
    def _is_keyboard_visible(self):
        """True if a reply keyboard is currently shown.

        Broadened (2026-09-21): the old check only knew a few button words
        (Balance/Tasks/Start/Cancel/Create Inst), so a keyboard showing
        "Account registered"/"Report"/etc. was mis-read as HIDDEN — then
        `_reveal_keyboard()` clicked the "Show bot keyboard" toggle, which
        HIDES an already-visible keyboard. That is how the final submit key
        vanished at the end of a cycle (mark_registered found no reply key).
        """
        try:
            # Generic: any reply-markup container/button present and visible.
            gen = self.page.locator(".reply-markup, [class*='reply-markup']")
            if gen.count() > 0 and gen.first.is_visible():
                return True
            loc = self.page.locator("button:has-text('Balance'), button:has-text('Tasks'), button:has-text('Start'), button:has-text('Cancel'), button:has-text('Create Inst')")
            return loc.count() > 0 and loc.first.is_visible()
        except Exception:
            return False

    def _reveal_keyboard(self):
        if self._is_keyboard_visible():
            return True
        for sel in ('button[title="Show bot keyboard"]',
                    'button[aria-label="Show bot keyboard"]',
                    'button[description="Show bot keyboard"]',
                    'button:has-text("Show bot keyboard")',
                    'button[title="Show keyboard"]'):
            try:
                b = self.page.locator(sel).first
                if b.is_visible():
                    # Short fuse: a dead toggle (post-expiry empty keyboard)
                    # never becomes clickable — never burn the 30s default.
                    try:
                        b.click(timeout=3000)
                    except Exception:
                        try:
                            b.click(force=True, timeout=3000)
                        except Exception:
                            continue
                    self.page.wait_for_timeout(800)
                    return True
            except Exception:
                pass
        return False

    def _click(self, text, timeout=6000, exact=False):
        """Click a control, strictly preferring buttons/reply keyboard."""
        self._reveal_keyboard()
        # 1. Try button with text
        try:
            loc = self.page.locator(f"button:has-text('{text}')")
            if loc.count() > 0 and loc.last.is_visible():
                loc.last.click(timeout=timeout)
                self.page.wait_for_timeout(1200)
                return True
        except Exception:
            pass
        # 2. Try role button or general button class
        try:
            loc = self.page.locator(f"[role='button']:has-text('{text}'), .MxtWMmBK:has-text('{text}')")
            if loc.count() > 0 and loc.last.is_visible():
                loc.last.click(timeout=timeout)
                self.page.wait_for_timeout(1200)
                return True
        except Exception:
            pass
        # 3. Fallback to get_by_text with short timeout
        try:
            el = self.page.get_by_text(text, exact=exact).last
            if el.is_visible():
                el.click(timeout=2000)
                self.page.wait_for_timeout(1200)
                return True
        except Exception:
            pass
        return False

    def _focus_composer(self):
        # 1. Try direct page.focus
        for sel in ('#editable-message-text', '.ProseMirror', 'div[contenteditable="true"]', '[role="textbox"][contenteditable="true"]', '.input-message-input'):
            try:
                self.page.focus(sel, timeout=1500)
                return True
            except Exception:
                pass
        # 2. Try click with force=True
        for sel in ('#editable-message-text', '.ProseMirror', 'div[contenteditable="true"]', '.input-message-input'):
            try:
                el = self.page.locator(sel).first
                if el.count() > 0:
                    el.click(force=True, timeout=1500)
                    return True
            except Exception:
                pass
        # 3. DOM focus fallback
        try:
            return bool(self.page.evaluate("""() => {
                const el = document.querySelector('#editable-message-text, .ProseMirror, div[contenteditable="true"], .input-message-input');
                if (el) { el.focus(); return true; }
                return false;
            }"""))
        except Exception:
            return False

    def _send(self):
        for sel in ('button[title="Send Message"]', 'button[aria-label="Send Message"]',
                    '.btn-send', 'button.btn-send', 'button.send'):
            try:
                b = self.page.locator(sel).first
                if b.is_visible():
                    b.click(force=True, timeout=2000)
                    self.page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass
        try:
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(1500)
            return True
        except Exception:
            return False


    # ==========================================================================
    # SECTION 3: BOT NAVIGATION, CHAT DISCOVERY & MENU STATE RECOVERY
    # ==========================================================================
    def _is_chat_open(self) -> bool:
        """Check if target bot chat is currently rendered and active."""
        try:
            p = self.page
            if self.peer_id not in (p.url or ""):
                return False
            # Check for standard Telegram Web active chat container elements
            for sel in (
                ".MessageList",
                ".messages-container",
                ".middle-column-footer",
                ".input-message-input",
                "[contenteditable='true']",
                "#editable-message-text",
                "button[description*='keyboard' i]",
                "button[title*='keyboard' i]",
                "button[aria-label*='keyboard' i]",
                ".chat-info",
                ".ChatInfo",
                ".top-bar-title",
            ):
                try:
                    if p.locator(sel).count() > 0:
                        return True
                except Exception:
                    pass
            # Also check if reply buttons or actions are visible
            try:
                if p.locator("button:has-text('Tasks'), button:has-text('Balance'), button:has-text('Cancel'), button:has-text('Start')").count() > 0:
                    return True
            except Exception:
                pass
            return False
        except Exception:
            return False

    def open_bot(self):
        """Open the target bot chat (Taskly Bot or PayGoBot) from any starting point."""
        # 0. Check if Telegram is actually logged in or sitting on login / QR code screen
        try:
            body = (self.page.inner_text("body") or "").lower()
            if any(term in body for term in ("log in to telegram by qr code", "log in by phone number", "scan this code with your phone")):
                self.log(f"[tg] ❌ Telegram account ({os.path.basename(self.profile_dir)}) is NOT logged in! Please log in first via Dashboard → Telegram Accounts.")
                return False
        except Exception:
            pass

        # 1. If already inside the target bot chat
        if self._is_chat_open():
            return True

        # 2. Fast direct hash navigation (works instantly in Telegram Web A single-page app)
        try:
            if self.peer_id not in (self.page.url or ""):
                self.log(f"[tg] Navigating directly to {self.bot_name} ({self.bot_url})…")
                self.page.goto(self.bot_url, wait_until="domcontentloaded", timeout=15000)
            for _ in range(6):
                self.page.wait_for_timeout(1000)
                if self._is_chat_open():
                    return True
        except Exception:
            pass

        # 3. If stuck inside a channel or other chat, click the Back button to return to chat list
        for sel in ('button[title="Back"]', 'button[aria-label="Back"]', 'button[description="Back"]', '.back-button', 'button.tgico-back'):
            try:
                b = self.page.locator(sel).first
                if b.count() > 0 and b.is_visible():
                    try:
                        b.click(timeout=5000)
                    except Exception:
                        b.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        # 4. Click Bot directly in the chat list (instant, no page reload)
        for sel in (
            f"a[href*='{self.peer_id}']",
            f".ListItem:has-text('{self.bot_name}')",
            f".chat-list .ListItem:has-text('{self.bot_name}')",
            f"a:has-text('{self.bot_name}')",
            f"text='{self.bot_name}'",
        ):
            try:
                el = self.page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.click(force=True)
                    for _ in range(5):
                        self.page.wait_for_timeout(800)
                        if self._is_chat_open():
                            return True
            except Exception:
                pass

        # 5. Try searching for the bot via search input
        bot_search_term = "tasklyBux_bot" if self.bot_target == "taskly" else "PayGoBot"
        for s_sel in (
            "#telegram-search-input",
            "input.input-field-input",
            ".input-search input",
            "input[placeholder*='Search' i]",
        ):
            try:
                search_input = self.page.locator(s_sel).first
                if search_input.count() > 0 and search_input.is_visible():
                    try:
                        search_input.click(timeout=5000)
                    except Exception:
                        search_input.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(500)
                    self.page.keyboard.press("Control+A")
                    self.page.keyboard.press("Backspace")
                    search_input.fill(bot_search_term)
                    self.page.wait_for_timeout(1500)
                    for item_sel in (
                        f".search-section .ListItem:has-text('{self.bot_name}')",
                        f".chat-list .ListItem:has-text('{self.bot_name}')",
                        f".ListItem:has-text('{self.bot_name}')",
                        f"a[href*='{self.peer_id}']",
                    ):
                        item = self.page.locator(item_sel).first
                        if item.count() > 0 and item.is_visible():
                            item.click(force=True)
                            for _ in range(5):
                                self.page.wait_for_timeout(800)
                                if self._is_chat_open():
                                    return True
                    break
            except Exception:
                pass

        # 6. Fallback URL navigation with proper hydration wait
        try:
            target_url = self.bot_url
            self.page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            for _ in range(8):
                self.page.wait_for_timeout(1000)
                if self._is_chat_open():
                    return True
        except Exception:
            pass

        self.log(f"[tg] could not open {self.bot_name} chat.")
        return False

    def _stable_click(self, el, timeout=3000) -> bool:
        """Scroll into view, require the box to sit still, then click.

        Returns False when the element is jumping (caller retries on a fresh
        pass) instead of clicking a moving target.
        """
        try:
            try:
                el.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            try:
                b1 = el.bounding_box()
                self.page.wait_for_timeout(300)
                b2 = el.bounding_box()
                if b1 and b2 and (abs(b1["x"] - b2["x"]) > 3 or abs(b1["y"] - b2["y"]) > 3):
                    return False
            except Exception:
                pass
            try:
                el.click(timeout=timeout)
            except Exception:
                el.click(force=True, timeout=timeout)
            return True
        except Exception:
            return False

    def _try_click_any(self, selectors, timeout=3000):
        """Click the newest matching button, robust to chat re-renders.

        Telegram Web virtualizes/re-renders on every incoming message, so a
        button can literally jump mid-click ("struggling"). Strategy per
        selector: up to 3 fresh passes on the NEWEST visible match (skip the
        pass while it jumps); only when the newest never settles, fall back
        to older stable duplicates. Old expired-task buttons are a last
        resort, never the first pick.
        """
        for sel in selectors:
            for _attempt in range(3):
                try:
                    loc = self.page.locator(sel)
                    n = loc.count()
                    if not n:
                        break
                    el = loc.nth(n - 1)
                    if el.count() and el.is_visible():
                        if self._stable_click(el, timeout=timeout):
                            return True
                except Exception:
                    pass
                try:
                    self.page.wait_for_timeout(600)
                except Exception:
                    break
            try:
                loc = self.page.locator(sel)
                n = loc.count()
                for idx in range(n - 2, max(n - 5, -1), -1):
                    try:
                        el = loc.nth(idx)
                        if el.count() and el.is_visible():
                            if self._stable_click(el, timeout=timeout):
                                return True
                    except Exception:
                        continue
            except Exception:
                pass
        return False

    def _is_at_main_menu(self):
        """Check if reply keyboard displays the root main menu buttons."""
        try:
            has_tasks = (
                self.page.locator("button:has-text('Tasks')").count() > 0
                and self.page.locator("button:has-text('Tasks')").first.is_visible()
            )
            has_other = (
                (self.page.locator("button:has-text('Balance')").count() > 0 and self.page.locator("button:has-text('Balance')").first.is_visible())
                or (self.page.locator("button:has-text('Profile')").count() > 0 and self.page.locator("button:has-text('Profile')").first.is_visible())
                or (self.page.locator("button:has-text('Withdraw')").count() > 0 and self.page.locator("button:has-text('Withdraw')").first.is_visible())
            )
            return bool(has_tasks and has_other)
        except Exception:
            return False

    def _inspect(self, max_msgs: int = 8, max_btns: int = 30):
        """Read-only snapshot: reply-keyboard buttons + recent chat messages.

        Never clicks or sends anything. Used for audits and learning new
        bots' task layouts (e.g. PayGoBot recon).
        """
        try:
            self._reveal_keyboard()
        except Exception:
            pass
        try:
            buttons = self.page.evaluate("""() => Array.from(document.querySelectorAll('button'))
                .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
                .map(e => (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 60))
                .filter(Boolean).slice(0, 60)""") or []
        except Exception:
            buttons = []
        try:
            texts = self.page.evaluate("""(n) => {
                const items = Array.from(document.querySelectorAll('.MessageList [class*=text]'));
                const seen = items.length ? items : Array.from(document.querySelectorAll('.MessageList > div')).slice(-n);
                return seen.slice(-n).map(e => (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 300)).filter(Boolean);
            }""", max_msgs) or []
        except Exception:
            texts = []
        return {"buttons": buttons[:max_btns], "messages": texts[-max_msgs:]}

    def _button_signature(self):
        """Visible reply-keyboard buttons as one string (change detector)."""
        try:
            return self.page.evaluate("""() => Array.from(document.querySelectorAll('button'))
                .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
                .map(e => (e.innerText || '').trim().replace(/\\s+/g, ' ')).join('|')""") or ""
        except Exception:
            return ""

    def _wait_keyboard_settled(self, min_wait=1000, max_wait=5000):
        """Wait for the reply keyboard to stop re-rendering after a click.

        Telegram Web re-renders the button set with every bot reply; acting
        mid-render clicks stale/wrong buttons (visible 'jumping'). Waits at
        least min_wait, then until the button signature is identical across
        two consecutive 500ms polls (or max_wait). Returns the signature.
        """
        import time as _time
        try:
            self.page.wait_for_timeout(min_wait)
        except Exception:
            pass
        end = _time.time() + max(0, (max_wait - min_wait)) / 1000.0
        prev = self._button_signature()
        while _time.time() < end:
            try:
                self.page.wait_for_timeout(500)
            except Exception:
                break
            cur = self._button_signature()
            if cur and cur == prev:
                return cur
            prev = cur
        return prev

    def _wait_keyboard_labels(self, timeout=10000):
        """Wait until the reply keyboard hydrates with real labels.

        Telegram renders the keyboard container FIRST (empty buttons) and
        paints labels ~1-2s later. Matching during that window refuses on
        empty buttons — or worse, clicks one. Returns True once at least one
        visible `button.MxtWMmBK` carries non-empty text.
        """
        import time as _time
        end = _time.time() + timeout / 1000.0
        while _time.time() < end:
            try:
                n = self.page.evaluate("""() => Array.from(document.querySelectorAll('button.MxtWMmBK'))
                    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0
                        && (e.innerText || '').trim().length > 0; }).length""")
                if n and int(n) > 0:
                    return True
            except Exception:
                pass
            try:
                self.page.wait_for_timeout(500)
            except Exception:
                break
        return False

    def _log_pick(self, locator, want_name):
        """Evidence log: exact button text (+ icon) about to be clicked + full keyboard."""
        try:
            btn = locator.first
            txt = (btn.inner_text() or "").strip().replace("\n", " ")[:80]
            icons = btn.evaluate("""(el) => Array.from(el.querySelectorAll('img'))
                .map(i => i.getAttribute('alt') || i.getAttribute('src') || '')
                .filter(Boolean).join(',').slice(0, 60)""")
            txt = f"{txt} [icons: {icons}]"
        except Exception:
            txt = "?"
        try:
            snap = [s[:40] for s in self._button_signature().split("|") if s][:12]
        except Exception:
            snap = []
        self.log(f"[tg] Picking button: '{txt}' (want {want_name}); keyboard: {snap}")

    def _confirm_pick(self, want_name):
        """Post-click: fixed settle + log the bot's reply (task attribution)."""
        self.page.wait_for_timeout(2500)
        self.log(f"[tg] Selected task: {want_name}")
        try:
            msgs = self._inspect(max_msgs=2).get("messages") or []
            if msgs:
                self.log(f"[tg] Bot reply: '{msgs[-1][:180]}'")
        except Exception:
            pass
        return True

    def reset_to_main_menu(self, timeout=30):
        """Intelligently escape from ANY random/stale/broken bot state and return to the root main menu.
        Handles:
          - Stale/expired tasks ('Time's up! Task cancelled.' -> 'Return to main menu')
          - Active tasks or task previews ('Cancel' / '❌ Cancel' -> 'Return to main menu')
          - Submenus (Withdraw, Tasks, Video instruction -> 'Cancel')
          - Dead-end submenus without Cancel (e.g. Language -> sends '/start')
          - Collapsed keyboard (automatically clicks 'Show bot keyboard')
          - Stray channels / other chats (navigates back to Taskly Bot)
        """
        self.log("[tg] Ensuring clean main menu state…")

        # 1. Must be inside the bot chat! If not, do NOT blindly check buttons or send /start!
        if not self.open_bot():
            self.log(f"[tg] ⚠️ Cannot reset menu: {self.bot_name} chat could not be opened.")
            return False

        import time as _time
        end = _time.time() + timeout

        # Initial check & settle: give the reply keyboard up to 2.5s to render if already at main menu
        for _ in range(5):
            self._reveal_keyboard()
            if self._is_at_main_menu():
                self.log("[tg] Clean main menu verified.")
                return True
            self.page.wait_for_timeout(500)

        _t0 = _beat = _time.time()
        while _time.time() < end:
            if _time.time() - _beat >= 10:
                self.log(f"[tg] …still resetting menu ({int(_time.time() - _t0)}s)…")
                _beat = _time.time()
            # Expand keyboard if collapsed
            self._reveal_keyboard()

            # Check if already at Root Main Menu
            if self._is_at_main_menu():
                self.log("[tg] Clean main menu verified.")
                return True

            # Priority 1: Check for 'Return to main menu' (from cancelled/expired tasks)
            if self._try_click_any([
                "button:has-text('Return to main menu')",
                "button:has-text('main menu')",
                "button:has-text('⬅️ Return to main menu')",
            ]):
                self.log("[tg] Clicked 'Return to main menu'.")
                # Settle-aware wait: same 4s budget, but never acts mid-render.
                self._wait_keyboard_settled(1000, 4000)
                self._reveal_keyboard()
                if self._is_at_main_menu():
                    self.log("[tg] Clean main menu verified.")
                    return True
                # If 'Return to main menu' did not yield main menu, fall through to Cancel / /start

            # Priority 2: Check for 'Cancel' / '❌ Cancel' (clears active tasks & submenus)
            # BUT never Cancel a task that is already SUBMITTED / under review
            # ("Your report has been received! Please wait.") — cancelling the
            # review screen can void the submission (observed 2026-09-21: an
            # accepted report was cancelled ~4s later by this reset). Fall
            # through to /start, which is non-destructive.
            try:
                _msgs = self._inspect(max_msgs=2).get("messages") or []
                _tail = (_msgs[-1] if _msgs else "").lower()
            except Exception:
                _tail = ""
            _submitted = any(k in _tail for k in (
                "report has been received", "report has been accepted",
                "please wait", "review time", "under review"))
            if _submitted:
                self.log("[tg] Task already SUBMITTED (under review) — refusing to Cancel.")
            elif self._try_click_any([
                "button:has-text('Cancel')",
                "button:has-text('❌ Cancel')",
            ]):
                self.log("[tg] Clicked 'Cancel' button.")
                # Same 7s budget, settle-aware: lets the bot finish processing
                # the cancellation before anything else is touched.
                self._wait_keyboard_settled(1500, 7000)
                self._reveal_keyboard()
                # If Cancel yielded 'Return to main menu' (e.g. PayGo / old task previews), click it
                if self._try_click_any([
                    "button:has-text('Return to main menu')",
                    "button:has-text('main menu')",
                ], timeout=1000):
                    self._wait_keyboard_settled(1000, 4000)
                    self._reveal_keyboard()
                if self._is_at_main_menu():
                    self.log("[tg] Clean main menu verified.")
                    return True
                continue

            # Priority 3: Check for 'Back' / '⬅️ Back'
            if not _submitted and self._try_click_any([
                "button:has-text('Back')",
                "button:has-text('⬅️ Back')",
            ]):
                self.log("[tg] Clicked 'Back' button.")
                self._wait_keyboard_settled(1000, 5000)
                self._reveal_keyboard()
                if self._is_at_main_menu():
                    self.log("[tg] Clean main menu verified.")
                    return True
                continue

            # Priority 4: Dead-end submenus (e.g. Language) -> only send /start if composer is accessible
            if self._focus_composer():
                self.log("[tg] No cancel button found; sending /start to reset bot session…")
                self.page.keyboard.type("/start", delay=20)
                self._send()
                self._wait_keyboard_settled(1500, 8000)
                self._reveal_keyboard()
                self._try_click_any([
                    "button:has-text('Return to main menu')",
                    "button:has-text('main menu')",
                ], timeout=1000)
                if self._is_at_main_menu():
                    self.log("[tg] Clean main menu verified.")
                    return True
                break
            else:
                self.log("[tg] ⚠️ Bot chat composer not accessible; checking bot status…")
                if not self.open_bot():
                    return False
                self.page.wait_for_timeout(2000)
                self._reveal_keyboard()
                if self._is_at_main_menu():
                    return True

            self.page.wait_for_timeout(1000)

        self.log("[tg] ⚠️ Could not reset to main menu within timeout.")
        return False

    def cancel_task(self):
        """Explicitly cancel whatever task or submenu is in progress and return to main menu."""
        self.log("[tg] Explicitly cancelling current task…")
        return self.reset_to_main_menu()

    # ==========================================================================
    # SECTION 4: TASKLY BOT WORKFLOW & 2FA KEY SUBMISSION
    # ==========================================================================
    def _choose_paygo_fire_task(self) -> bool:
        """Click ONLY the 🔥 Create Inst (2FA) button on PayGo, never the 📱 mobile one.

        PayGo renders two same-text buttons; they differ only by emoji
        (img alt 🔥 vs 📱 in innerHTML). Strict requirement:
        - Icon: 🔥 (Fire / 1f525)
        - Text: Create Inst (2FA)
        Never click 📱 or any other task.
        """
        want_name = "🔥 Create Inst (2FA)"
        self._reveal_keyboard()
        self._wait_keyboard_labels(8000)

        # Check if already visible on task screen
        target = self.page.locator("button.MxtWMmBK:has(img[src*='1f525'], img[alt='🔥']):has-text('Create Inst (2FA)')")
        if target.count() > 0 and target.first.is_visible():
            self._log_pick(target, want_name)
            try:
                target.first.click(timeout=8000)
            except Exception:
                target.first.click(force=True, timeout=5000)
            return self._confirm_pick(want_name)

        for attempt in range(3):
            self.log(f"[tg] PayGo fire pick attempt {attempt + 1}/3…")
            self._reveal_keyboard()
            btn_tasks = self.page.locator("button:has-text('Tasks')")
            if btn_tasks.count() == 0 or not btn_tasks.last.is_visible():
                self.reset_to_main_menu()
                btn_tasks = self.page.locator("button:has-text('Tasks')")

            if btn_tasks.count() > 0 and btn_tasks.last.is_visible():
                try:
                    btn_tasks.last.click(timeout=8000)
                except Exception:
                    btn_tasks.last.click(force=True, timeout=5000)
            else:
                self._click("Tasks", timeout=3000)
            self.page.wait_for_timeout(1500)
            self._reveal_keyboard()
            self._wait_keyboard_labels(8000)

            target = self.page.locator("button.MxtWMmBK:has(img[src*='1f525'], img[alt='🔥']):has-text('Create Inst (2FA)')")
            try:
                target.first.wait_for(state="visible", timeout=6000)
                self._log_pick(target, want_name)
                try:
                    target.first.click(timeout=8000)
                except Exception:
                    target.first.click(force=True, timeout=5000)
                return self._confirm_pick(want_name)
            except Exception:
                self.log(f"[tg] PayGo fire option not visible after attempt {attempt + 1}.")
            self.page.wait_for_timeout(1000)

        self.log(f"[tg] ❌ PayGo fire task button not found ({want_name}).")
        return False

    def _answer_taskly_confirm(self) -> bool:
        """Answer Taskly's ownership/human confirmation gate (one YES max).

        Observed 2026-09-19 (tg_2): pressing Tasks shows ONLY
        "YES, IT'S ME" / "NO, IT'S NOT ME!" with no task rows at all — the
        account is gated behind a confirmation question. Preconditions are
        strict: no task rows visible AND a YES-style button visible. Answers
        YES once (confirms the legitimate session owner), settles, and
        reports whether task rows appeared. Never loops, never answers NO.
        """
        try:
            has_tasks = self.page.locator(
                "button:has-text('Create Inst'), button:has-text('Cookies')").count() > 0
            if has_tasks:
                return True
            yes = self.page.locator(
                "button:has-text(\"YES, IT'S ME\"), button:has-text('YES')").first
            if yes.count() == 0 or not yes.is_visible():
                return False
            self.log("[tg] Taskly confirmation gate found (YES/NO, no tasks) — answering YES once…")
            try:
                yes.click(timeout=8000)
            except Exception:
                yes.click(force=True, timeout=5000)
            self._wait_keyboard_settled(1500, 8000)
            self._reveal_keyboard()
            has_tasks = self.page.locator(
                "button:has-text('Create Inst'), button:has-text('Cookies')").count() > 0
            self.log(f"[tg] Confirm gate answered; task rows now: {has_tasks}")
            return has_tasks
        except Exception as exc:
            self.log(f"[tg] confirm-gate note: {exc}")
            return False

    def _choose_taskly_nomail_task(self) -> bool:
        """Click ONLY the 🔥 Create Inst (No mail) button on Taskly.

        Taskly lists several tasks (🔥 No mail vs 📱 2FA vs Cookies).
        Strict requirement:
        - Icon: 🔥 (fire / 1f525)
        - Text: Create Inst (No mail) — full text, never a bare
          "Create Inst" substring that could match another row.
        No fallback to any other task: a missing No-mail button fails loudly
        instead of silently starting the wrong task.
        """
        want_name = "🔥 Create Inst (No mail)"
        self._reveal_keyboard()
        self._wait_keyboard_labels(8000)
        sel = "button.MxtWMmBK:has(img[src*='1f525'], img[alt='🔥']):has-text('Create Inst (No mail)')"

        # 1. Quick check: is the No-mail task button already visible?
        target = self.page.locator(sel)
        if target.count() > 0 and target.first.is_visible():
            self._log_pick(target, want_name)
            try:
                target.first.click(timeout=8000)
            except Exception:
                target.first.click(force=True, timeout=5000)
            return self._confirm_pick(want_name)

        # 2. Open the Tasks submenu and select
        for attempt in range(3):
            self.log(f"[tg] No-mail pick attempt {attempt + 1}/3…")
            self._reveal_keyboard()

            target = self.page.locator(sel)
            if target.count() > 0 and target.first.is_visible():
                self._log_pick(target, want_name)
                try:
                    target.first.click(timeout=8000)
                except Exception:
                    target.first.click(force=True, timeout=5000)
                return self._confirm_pick(want_name)

            btn_tasks = self.page.locator("button:has-text('Tasks')")
            if btn_tasks.count() == 0 or not btn_tasks.last.is_visible():
                # Only reset to main menu if we are truly not at the Tasks submenu
                has_sub = self.page.locator("button:has-text('Create Inst'), button:has-text('Cookies')").count() > 0
                if not has_sub:
                    self.log("[tg] Tasks button missing — resetting to main menu…")
                    self.reset_to_main_menu()
                    btn_tasks = self.page.locator("button:has-text('Tasks')")

            if btn_tasks.count() > 0 and btn_tasks.last.is_visible():
                self.log("[tg] Clicking Tasks button…")
                try:
                    btn_tasks.last.click(timeout=8000)
                except Exception:
                    btn_tasks.last.click(force=True, timeout=5000)
                self.page.wait_for_timeout(1500)
                self._reveal_keyboard()
            self._wait_keyboard_labels(8000)

            # Confirmation gate (tg_2 2026-09-19): Tasks opens a YES/NO
            # ownership question with zero task rows. Answer YES once, then
            # scan for the No-mail option below.
            try:
                if (self.page.locator(sel).count() == 0
                        and self.page.locator(
                            "button:has-text('Create Inst'), button:has-text('Cookies')").count() == 0):
                    self._answer_taskly_confirm()
            except Exception:
                pass

            # Wait for the No-mail option — full text + emoji, nothing else
            target = self.page.locator(sel)
            try:
                target.first.wait_for(state="visible", timeout=4000)
                self._log_pick(target, want_name)
                try:
                    target.first.click(timeout=8000)
                except Exception:
                    target.first.click(force=True, timeout=5000)
                return self._confirm_pick(want_name)
            except Exception:
                self.log(f"[tg] No-mail option not visible after attempt {attempt + 1}.")
            self.page.wait_for_timeout(1000)

        # Failure diagnosis dump
        try:
            btns = self.page.locator("button").all()
            seen = [b.inner_text().strip().replace("\n", " ")[:40] for b in btns if b.is_visible()]
            self.log(f"[tg] Taskly visible buttons: {seen}")
        except Exception:
            pass
        self.log(f"[tg] ❌ Taskly No-mail task button not found ({want_name}); refusing any other task.")
        return False

    def choose_task(self, task=TG_DEFAULT_TASK):
        """📋 Tasks → choose the task from the reply keyboard with full auto-recovery."""
        # Per-bot label mapping (e.g. PayGo calls it "Create Inst (2FA)").
        task = TG_BOTS.get(self.bot_target, {}).get("task_aliases", {}).get(task, task)
        clean_task = task.split("(")[0].strip()

        # 1. Verify bot chat is open
        if not self.open_bot():
            self.log(f"[tg] ❌ Cannot choose task: {self.bot_name} chat is not open.")
            return False

        # 1b. PayGo shows two "Create Inst (2FA)" buttons: 🔥 (wanted) and
        # 📱 mobile-logo (must never be picked). Disambiguate by emoji.
        if self.bot_target == "paygo" and "Create Inst" in task:
            if self._choose_paygo_fire_task():
                return True
            # Never fall through to generic :has-text pick for PayGo:
            # it matches the 📱 mobile-logo button (.last in DOM order).
            self.log("[tg] ❌ PayGo fire task not selectable; refusing mobile fallback.")
            return False

        # 1c. Taskly: ONLY the 🔥 Create Inst (No mail) button may ever be
        # clicked — never 2FA, never Cookies, never a bare-text match.
        if self.bot_target == "taskly" and "Create Inst" in task:
            if self._choose_taskly_nomail_task():
                return True
            self.log("[tg] ❌ Taskly No-mail task not selectable; refusing any other task.")
            return False

        # 2. Reset state to root main menu first
        if not self.reset_to_main_menu():
            self.log("[tg] ⚠️ Main menu reset incomplete, attempting to proceed...")

        # 2. Check if target task button is ALREADY visible in reply keyboard
        loc_task = self.page.locator(f"button:has-text('{clean_task}')")
        if loc_task.count() > 0 and loc_task.last.is_visible():
            self.log(f"[tg] Task button '{clean_task}' already visible, clicking it...")
            loc_task.last.click(force=True, timeout=3000)
            self.page.wait_for_timeout(2500)
            return True

        # 3. Click 'Tasks' button
        self.log("[tg] Clicking Tasks button...")
        btn_tasks = self.page.locator("button:has-text('Tasks')")
        if btn_tasks.count() > 0 and btn_tasks.last.is_visible():
            btn_tasks.last.click(force=True, timeout=3000)
        else:
            self._click("Tasks", timeout=3000)

        # 4. Wait up to 5s for task options to appear (event-driven)
        try:
            self.page.wait_for_function(
                """(t) => Array.from(document.querySelectorAll('button'))
                    .some(e => { const r = e.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                            (e.innerText || '').includes(t); })""",
                arg=clean_task, timeout=5000)
        except Exception:
            pass
        self._reveal_keyboard()
        loc_task = self.page.locator(f"button:has-text('{clean_task}')")
        if loc_task.count() > 0 and loc_task.last.is_visible():
            loc_task.last.click(force=True, timeout=3000)
            self.page.wait_for_timeout(2500)
            self.log(f"[tg] Selected task: {clean_task}")
            return True

        # 5. Retry once with hard reset if task was not found
        self.log(f"[tg] Task '{clean_task}' not found; retrying with /start reset…")
        self.reset_to_main_menu()
        btn_tasks = self.page.locator("button:has-text('Tasks')")
        if btn_tasks.count() > 0 and btn_tasks.last.is_visible():
            btn_tasks.last.click(force=True, timeout=3000)
            self.page.wait_for_timeout(2500)
            self._reveal_keyboard()
            loc_task = self.page.locator(f"button:has-text('{clean_task}')")
            if loc_task.count() > 0 and loc_task.last.is_visible():
                loc_task.last.click(force=True, timeout=3000)
                self.page.wait_for_timeout(2500)
                self.log(f"[tg] Selected task: {clean_task}")
                return True

        # Fallback click
        if self._click(task, timeout=4000) or self._click(clean_task, timeout=4000):
            self.page.wait_for_timeout(2500)
            return True

        self.log(f"[tg] task '{task}' not found.")
        return False

    def start_task(self):
        """Click ▶️ Start and parse the fresh credentials the bot provides.

        Handles:
        1. Anti-flood rate limit cooldowns ("You are making requests too often. Please wait 5 sec.")
        2. Inspecting the latest message bubbles from bottom-to-top to ensure credentials belong
           to THIS task, never reading stale credentials from previous cancelled tasks in chat history.
        3. Splitting by cancellation markers ("Action cancelled", "Time's up!
           Task cancelled.") so old/expired tasks are discarded — NEVER parsed
           as fresh creds (expired-task creds reuse = submitting an old login).
        """
        # Any-case cancellation markers. NOTE: "Time's up! Task cancelled."
        # (bot TTL expiry, ~8 min) does NOT contain "Action cancelled", so it
        # needs its own markers — otherwise the dead task's Login/Password
        # is returned as if fresh.
        _CANCEL_RES = ("Action cancelled", "Action canceled", "Time's up",
                       "Time’s up", "Task cancelled", "Task canceled",
                       "Please select a task")
        for attempt in range(4):
            self._reveal_keyboard()
            start_btn = self.page.locator("button:has-text('Start')")
            if start_btn.count() > 0 and start_btn.last.is_visible():
                start_btn.last.click(force=True, timeout=3000)
            else:
                self._click("Start", timeout=8000)

            # Poll for bot response (up to 15 seconds)
            deadline = time.time() + 15.0
            rate_limited = False
            wait_sec = 5
            found_creds = None

            while time.time() < deadline:
                self.page.wait_for_timeout(600)

                # Method 1: Inspect DOM message bubbles from newest (bottom) to oldest (top)
                try:
                    res = self.page.evaluate("""(marks) => {
                        const bubbles = Array.from(document.querySelectorAll(
                            '.MessageList .message-content, .MessageList .text-content, .messages-container .text-content, .Message .text-content, .message-content, .text-content'
                        ));
                        const low = marks.map(m => m.toLowerCase());
                        for (let i = bubbles.length - 1; i >= 0; i--) {
                            const txt = (bubbles[i].innerText || '').trim();
                            if (!txt) continue;
                            const tl = txt.toLowerCase();
                            if (txt.includes('too often') || /wait \\d+ sec/i.test(txt)) {
                                return { type: 'rate_limited', text: txt };
                            }
                            if (low.some(m => tl.includes(m))) {
                                return { type: 'cancelled', text: txt };
                            }
                            if (/Login:\\s*.+/i.test(txt) && /Password:\\s*\\S+/i.test(txt)) {
                                return { type: 'credentials', text: txt };
                            }
                        }
                        return null;
                    }""", list(_CANCEL_RES))
                    if res:
                        if res.get("type") == "rate_limited":
                            rate_limited = True
                            m = re.search(r"(\d+)\s*sec", res.get("text", ""))
                            if m:
                                wait_sec = int(m.group(1))
                            break
                        elif res.get("type") == "credentials":
                            txt_c = res.get("text", "")
                            m_login = re.search(r"Login:\s*(.*?)(?=\s*Password:|\n|\r|$)", txt_c)
                            m_pwd = re.search(r"Password:\s*([A-Za-z0-9_!@#$%^&*+=?-]+)", txt_c)
                            m_name = re.search(r"First name:\s*(.*?)(?=\s*Login:|\n|\r|$)", txt_c)
                            if m_login and m_pwd:
                                found_creds = {
                                    "first_name": m_name.group(1).strip() if m_name else "",
                                    "login": m_login.group(1).strip(),
                                    "password": m_pwd.group(1).strip(),
                                }
                                break
                        elif res.get("type") == "cancelled":
                            # Cancellation message currently at bottom of chat; keep waiting for Start response
                            pass
                except Exception:
                    pass

                # Method 2: Inspect body text strictly after the LAST cancellation
                # marker (any variant incl. TTL expiry) — never parse across it.
                if not found_creds and not rate_limited:
                    try:
                        raw_body = self.page.inner_text("body") or ""
                        parts = re.split(
                            r"Action cancelled|Action canceled|Time.s up!?[\s\S]{0,40}?Task cancelled|Task cancelled|Task canceled|Please select a task",
                            raw_body, flags=re.IGNORECASE)
                        active_tail = parts[-1] if parts else raw_body

                        if "too often" in active_tail.lower() or ("wait" in active_tail.lower() and "sec" in active_tail.lower()):
                            rate_limited = True
                            m = re.search(r"(\d+)\s*sec", active_tail)
                            if m:
                                wait_sec = int(m.group(1))
                            break

                        matches = list(re.finditer(
                            r"(?:First name:\s*(?P<name>[^\n\r]+?)\s*)?"
                            r"Login:\s*(?P<login>.*?)\s*"
                            r"Password:\s*(?P<pwd>[A-Za-z0-9_!@#$%^&*+=?-]+)",
                            active_tail
                        ))
                        if matches:
                            latest = matches[-1]
                            l_name = latest.group("name") or ""
                            l_login = latest.group("login") or ""
                            l_pwd = latest.group("pwd") or ""
                            if l_login and l_pwd:
                                found_creds = {
                                    "first_name": l_name.strip(),
                                    "login": l_login.strip(),
                                    "password": l_pwd.strip(),
                                }
                                break
                    except Exception:
                        pass

            if rate_limited:
                cooldown = max(5, wait_sec) + 1.5
                self.log(f"[tg] ⏳ Taskly anti-flood: bot requested waiting {wait_sec}s. Sleeping {cooldown:.1f}s before retrying Start (attempt {attempt + 1}/4)…")
                time.sleep(cooldown)
                continue

            if found_creds and found_creds.get("login") and found_creds.get("password"):
                self.creds = found_creds
                self.log(f"[tg] task started → {self.creds}")
                return self.creds

        self.log("[tg] ❌ Could not obtain fresh task credentials from bot (timed out / rate limited).")
        return {"first_name": "", "login": "", "password": ""}

    def submit_2fa_key(self, key, allow_local_fallback=True):
        """Send the 2FA base32 key and read the one-time code the bot returns.

        Optimized:
        - Instant text injection via insert_text (no character-by-character typing lag)
        - Sub-second reactive polling (checks every 200ms instead of 1.2s)
        - Local TOTP fallback only if allow_local_fallback=True (strict submit
          passes False so a silent bot raises instead of faking success)
        """
        clean_key = str(key or "").strip()
        focused = False
        for _ in range(3):
            if self._focus_composer():
                focused = True
                break
            self.page.wait_for_timeout(300)
        if not focused:
            raise RuntimeError("Telegram composer not found")

        # Instant text insertion without 15ms-per-char typing delay
        try:
            self.page.keyboard.insert_text(clean_key)
        except Exception:
            self.page.keyboard.type(clean_key, delay=5)

        self._send()
        self.log(f"[tg] 2FA key submitted to {self.bot_name}; waiting for one-time code…")

        # Fast polling: check every 250ms for up to 10 seconds
        deadline = time.time() + 10.0
        while time.time() < deadline:
            self.page.wait_for_timeout(250)

            # 1. Direct check on code entity tag in DOM
            try:
                code_el = self.page.locator(".text-entity-code, code").last
                if code_el.count() > 0 and code_el.is_visible():
                    c_txt = code_el.inner_text().strip()
                    if re.match(r"^\d{6}$", c_txt):
                        self.one_time_code = c_txt
                        self.log(f"[tg] ⚡ One-time code from bot DOM: {self.one_time_code}")
                        return self.one_time_code
            except Exception:
                pass

            # 2. Check input/textbox elements (Telegram Web A renders copyable code as readonly input)
            try:
                inputs = self.page.locator("input, textarea")
                for i in range(inputs.count()):
                    val = inputs.nth(i).input_value().strip()
                    if re.match(r"^\d{6}$", val):
                        self.one_time_code = val
                        self.log(f"[tg] ⚡ One-time code from bot input: {self.one_time_code}")
                        return self.one_time_code
            except Exception:
                pass

            # 3. Text body regex search
            try:
                txt = self.page.inner_text("body") or ""
                m = re.search(r"(?:code|код|your one-time code)[:\s]*(\d{6})", txt, re.IGNORECASE) or re.search(r"Your one-time code:\s*(\d{6})", txt) or re.search(r"\b(\d{6})\b", txt[::-1][:250][::-1])
                if m:
                    self.one_time_code = m.group(1)
                    self.log(f"[tg] ⚡ One-time code from bot text: {self.one_time_code}")
                    return self.one_time_code
            except Exception:
                pass

        # 4. Strict: no local fallback — bot must reply, else fail loudly.
        if not allow_local_fallback:
            raise RuntimeError("Telegram bot did not return a one-time code")
        # 4. Fallback to local TOTP generation so submit flow NEVER stalls
        try:
            import pyotp
            totp = pyotp.TOTP(clean_key).now()
            self.one_time_code = totp
            self.log(f"[tg] ⚡ Telegram bot response delayed; used instant local TOTP: {self.one_time_code}")
            return self.one_time_code
        except Exception:
            raise RuntimeError("Telegram bot did not return a one-time code")

    def _chat_tail(self):
        """(bubble_count, last_message_text) for the bot chat — a CHANGE detector.

        Used so a verdict is read from the NEW reply only. The previous task's
        rejection ("Report rejected ... was registered without an email
        address") stays in the chat history, so classifying the whole body is
        wrong.
        """
        try:
            res = self.page.evaluate("""() => {
                const items = Array.from(document.querySelectorAll('.MessageList [class*=text]'));
                const seen = items.length ? items : Array.from(document.querySelectorAll('.MessageList > div'));
                const last = seen.length ? (seen[seen.length - 1].innerText || '').trim() : '';
                return { count: seen.length, last };
            }""")
            return res or {"count": 0, "last": ""}
        except Exception:
            return {"count": 0, "last": ""}

    def mark_registered(self):
        """Click the register/confirm reply key to submit the task.

        NEVER taps Cancel/Back/Return, and never an unrelated menu key. The old
        loose fallback tapped the first non-destructive reply key — which was
        "Balance" — doing nothing useful, then reading a STALE verdict. The old
        verdict read also classified the WHOLE chat body, so the PREVIOUS
        report's rejection ("...was registered without an email address") was
        returned as the CURRENT verdict and an accepted report was refused
        (observed 2026-09-20). We now snapshot the chat, tap, and classify ONLY
        the new reply.
        """
        # Make sure we're in the bot chat and its reply keyboard is shown — the
        # register key is a REPLY key, absent if the chat is closed or the
        # keyboard collapsed (observed 2026-09-21: mark_registered burned ~36 s
        # and never found it while the task itself was fine).
        try:
            self.open_bot()
        except Exception:
            pass
        self._reveal_keyboard()
        # Snapshot BEFORE tapping so we can tell the new reply from history.
        before = self._chat_tail()
        before_count = int(before.get("count") or 0)
        before_last = str(before.get("last") or "")

        clicked = False
        for label in ("✅ Account registered", "Account registered", "Register",
                      "Register account", "✅ Register", "Confirm registration",
                      "✅ Confirm", "Confirm", "Done"):
            if self._click(label, timeout=3000):
                clicked = True
                self.log(f"[tg] tapped register key: {label}")
                break
        if not clicked:
            # Restricted fallback: only a reply key that is ITSELF a
            # register/confirm action. Never Cancel/Back/Return, and never an
            # unrelated menu key (the old code tapped "Balance" here).
            try:
                keys = self.page.locator(
                    ".reply-markup-button, button.MxtWMmBK, [class*='reply-markup'] button")
                for i in range(keys.count()):
                    t = (keys.nth(i).inner_text() or "").strip()
                    low = t.lower()
                    if not t or any(bad in low for bad in ("cancel", "back", "return", "menu", "stop")):
                        continue
                    if ("regist" in low) or ("confirm" in low):
                        keys.nth(i).click(timeout=4000)
                        self.log(f"[tg] tapped register-like keyboard key: {t[:40]}")
                        clicked = True
                        break
            except Exception:
                pass
        if not clicked:
            # Robust last resort: read EVERY visible button (some builds render
            # the reply keyboard outside `.reply-markup`) and match a
            # register/confirm action. Log the keyboard so a miss is diagnosable.
            try:
                btns = self._inspect(max_msgs=2, max_btns=80).get("buttons") or []
                vis = [b for b in btns if b]
                self.log(f"[tg] register key not found among labels; visible buttons: {vis[:20]}")
                for b in vis:
                    low = (b or "").lower()
                    if any(bad in low for bad in ("cancel", "back", "return", "menu", "stop")):
                        continue
                    if ("regist" in low) or ("confirm" in low) or (low.strip() == "done"):
                        try:
                            el = self.page.get_by_text(b, exact=True).last
                            if el.is_visible():
                                el.click(timeout=3000)
                                self.log(f"[tg] tapped register key from keyboard list: {b[:40]}")
                                clicked = True
                                break
                        except Exception:
                            pass
            except Exception:
                pass
        if not clicked:
            self.log("[tg] register key not found (refusing to press Cancel or an unrelated key).")
            return False

        # Poll for a NEW message after the tap — never classify the whole body,
        # which still holds the previous report's verdict.
        verdict = "unknown"
        new_text = ""
        for _ in range(16):
            self.page.wait_for_timeout(500)
            now = self._chat_tail()
            now_count = int(now.get("count") or 0)
            now_last = str(now.get("last") or "")
            if now_count > before_count:
                new_text = now_last
            elif now_last and now_last != before_last:
                new_text = now_last
            if not new_text:
                continue
            verdict = classify_report_reply(new_text)
            if verdict != "unknown":
                break

        if verdict == "rejected":
            self.log(f"[tg] ❌ bot REJECTED the report — NOT recording Submitted | '{new_text[:160]}'")
            return False
        if verdict == "accepted":
            self.log("[tg] submitted=True (verdict=accepted)")
            return True
        # No usable NEW reply yet. Do NOT fall back to the stale chat history —
        # report unconfirmed instead of a false rejection.
        self.log("[tg] no fresh verdict after register tap — treating as UNCONFIRMED (not rejected).")
        return False


# ==============================================================================
# SECTION 5: THREAD-SAFE BACKGROUND TASKLY BOT WORKER
# ==============================================================================
class ThreadedTelegramBot:
    """Runs TelegramTasklyBot in its own thread to avoid Playwright sync-in-asyncio conflict."""

    def __init__(self, profile_dir=None, bot_name=None, bot_target="taskly", headless=True, log=print):
        self.profile_dir = profile_dir
        self.bot_target = bot_target
        cfg = TG_BOTS.get(bot_target, TG_BOTS["taskly"])
        self.bot_name = bot_name or cfg["name"]
        self.peer_id = cfg["peer_id"]
        self.headless = headless
        self.log = log
        self._q_in = queue.Queue()
        self._q_out = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        bot = TelegramTasklyBot(profile_dir=self.profile_dir, bot_name=self.bot_name,
                                bot_target=self.bot_target,
                                headless=self.headless, log=self.log)
        while True:
            cmd, args, kwargs = self._q_in.get()
            if cmd == "close":
                bot.close()
                self._q_out.put(True)
                break
            try:
                fn = getattr(bot, cmd)
                res = fn(*args, **kwargs)
                self._q_out.put((True, res))
            except Exception as e:
                self._q_out.put((False, e))

    def _call(self, cmd, *args, **kwargs):
        self._q_in.put((cmd, args, kwargs))
        try:
            ok, res = self._q_out.get(timeout=180)
        except queue.Empty:
            raise RuntimeError(f"Telegram bot thread hung on '{cmd}' (180s)")
        if not ok:
            raise res
        return res

    def start(self):
        return self._call("start")

    def logged_in(self):
        """Live login state from the owner thread (True/False/None)."""
        try:
            return self._call("logged_in")
        except Exception:
            return None

    def open_bot(self):
        return self._call("open_bot")

    def choose_task(self, task=TG_DEFAULT_TASK):
        return self._call("choose_task", task)

    def start_task(self):
        return self._call("start_task")

    def submit_2fa_key(self, key, allow_local_fallback=True):
        return self._call("submit_2fa_key", key, allow_local_fallback=allow_local_fallback)

    def mark_registered(self):
        return self._call("mark_registered")

    def reset_to_main_menu(self, timeout=30):
        return self._call("reset_to_main_menu", timeout=timeout)

    def cancel_task(self):
        return self._call("cancel_task")

    def close(self):
        self._q_in.put(("close", (), {}))
        try:
            return self._q_out.get(timeout=30)
        except queue.Empty:
            return False


# ==============================================================================
# SECTION 6: PERSISTENT WARM PROFILE POOL (submitter fast path)
# ==============================================================================
_WARM_IDLE_SECS = 600  # close processes idle longer than this
# Hard cap on warm TG browsers held at once. Each warm worker is a WHOLE
# Chromium tree (~300-800 MB), so an unbounded pool (one per leased profile) is
# a RAM sink on a large pool. Least-recently-used are evicted first.
_WARM_MAX = max(1, int(os.environ.get("TG_WARM_MAX", "6")))


def _warm_owner_loop(q_in, q_out, profile_dir, headless, key, log):
    """Owner thread: ONE warm browser process per profile, one PAGE per bot.

    Two-tab mode: a Taskly and a PayGo submit run concurrently as separate
    TelegramTasklyBot clients (own page each) multiplexed over this single
    queue. All Playwright use stays in this thread; commands run FIFO, so no
    two commands ever interleave mid-execution.
    """
    import warm_pool as _wp
    clients = {}
    wb = None

    def _client(target):
        tgt = target or "taskly"
        bot = clients.get(tgt)
        if bot is None:
            bot = TelegramTasklyBot(profile_dir=profile_dir, bot_target=tgt,
                                    headless=headless, log=log)
            clients[tgt] = bot
        return bot

    def _drop_page(bot):
        try:
            if bot.page is not None and not bot.page.is_closed():
                bot.page.close()
        except Exception:
            pass
        bot.page = None

    while True:
        cmd, target, args, kwargs = q_in.get()
        if cmd == "shutdown":
            for _b in list(clients.values()):
                try:
                    _drop_page(_b)
                except Exception:
                    pass
                _b.ctx = None
            clients.clear()
            try:
                _wp.release_process("tg", key, headless, user_data_dir=profile_dir)
            except Exception:
                pass
            try:
                q_out.put(True)
            except Exception:
                pass
            break
        if cmd == "open":
            try:
                bot = _client(target)
                bot.log = kwargs.get("log", bot.log)
                wb = _wp.get("tg", key, headless, user_data_dir=profile_dir)
                ctx = wb.new_account_context()
                if bot.page is not None and not bot.page.is_closed() and getattr(bot, "ctx", None) is ctx and bot._is_chat_open():
                    bot.one_time_code = None
                    bot.creds = {}
                    q_out.put((True, True))
                    continue
                _drop_page(bot)
                bot.attach(ctx, fresh_page=True)
                # Tab hygiene: close stray pages (about:blank leftovers), so
                # each TG browser shows exactly ONE tab and never multiplies.
                try:
                    for _p in list(ctx.pages):
                        if _p != bot.page and not _p.is_closed():
                            _p.close()
                except Exception:
                    pass
                bot.one_time_code = None
                bot.creds = {}
                bot.start()  # attached mode: goto + login check only
                q_out.put((True, True))
            except Exception as e:
                try:
                    _drop_page(_client(target))
                    _client(target).ctx = None
                except Exception:
                    pass
                q_out.put((False, e))
            continue
        if cmd == "close_submit":
            try:
                bot = _client(target)
                _drop_page(bot)
            except Exception:
                pass
            try:
                if wb is not None:
                    wb.note_result(bool(kwargs.get("ok", True)))
            except Exception:
                pass
            q_out.put((True, True))
            continue
        try:
            bot = _client(target)
            fn = getattr(bot, cmd)
            res = fn(*args, **kwargs)
            q_out.put((True, res))
        except Exception as e:
            q_out.put((False, e))


class PooledTelegramBot:
    """Submitter-facing warm bot: ONE owner thread per TG profile dir.

    De-overloaded: the pool key is the profile dir ONLY (not dir+headless).
    A Visible↔Background flip shuts down the opposite-mode owner first —
    two Chromiums on one profile dir fight over SingletonLock and render a
    blank/logged-out profile on both sides ("opened but TG isn't showing").

    Every submit runs multiplexed over this single queue (taskly/paygo own
    pages); ``close(ok=True)`` only drops the page, the process persists.
    Same method surface as the legacy ThreadedTelegramBot (kept only for
    core/telegram.py linked mode).
    """

    _pool = {}
    _pool_lock = threading.Lock()

    def __init__(self, profile_dir=None, bot_name=None, bot_target="taskly", headless=True, log=print):
        self.profile_dir = profile_dir
        self.bot_target = bot_target
        cfg = TG_BOTS.get(bot_target, TG_BOTS["taskly"])
        self.bot_name = bot_name or cfg["name"]
        self.headless = bool(headless)
        self.log = log
        # Single owner per PROFILE DIR. Headless flips recycle the owner.
        self._key = profile_dir
        self._reap_idle()
        with PooledTelegramBot._pool_lock:
            ent = PooledTelegramBot._pool.get(self._key)
            if ent is not None and ent.get("headless") != self.headless:
                # Mode flip: shut down the opposite-mode owner BEFORE
                # launching, otherwise both hold the same SingletonLock.
                try:
                    PooledTelegramBot._pool.pop(self._key, None)
                except Exception:
                    pass
                try:
                    ent["q_in"].put(("shutdown", None, (), {}))
                    ent["thread"].join(timeout=5)
                except Exception:
                    pass
                ent = None
            if ent is None or not ent["thread"].is_alive():
                q_in: queue.Queue = queue.Queue()
                q_out: queue.Queue = queue.Queue()
                t = threading.Thread(
                    target=_warm_owner_loop,
                    args=(q_in, q_out, profile_dir, bool(headless),
                          os.path.basename(profile_dir or ""), log),
                    daemon=True)
                t.start()
                ent = {"thread": t, "q_in": q_in, "q_out": q_out,
                       "last_used": time.time(), "headless": bool(headless)}
                PooledTelegramBot._pool[self._key] = ent
            ent["last_used"] = time.time()
            ent["log"] = log
        self._ent = ent

    @staticmethod
    def _reap_idle() -> None:
        """Shut down warm workers that are idle > _WARM_IDLE_SECS, or beyond the
        _WARM_MAX count cap (least-recently-used first). Each warm worker is a
        whole Chromium tree, so an unbounded pool is a RAM sink."""
        victims = []
        with PooledTelegramBot._pool_lock:
            now = time.time()
            for k, ent in list(PooledTelegramBot._pool.items()):
                try:
                    idle = now - float(ent.get("last_used", now))
                except Exception:
                    idle = 0
                if idle > _WARM_IDLE_SECS:
                    victims.append((k, ent))
                    del PooledTelegramBot._pool[k]
            # Count cap: evict the least-recently-used beyond _WARM_MAX.
            if _WARM_MAX > 0 and len(PooledTelegramBot._pool) > _WARM_MAX:
                order = sorted(PooledTelegramBot._pool.items(),
                               key=lambda kv: float(kv[1].get("last_used", 0) or 0))
                for k, ent in order[:len(PooledTelegramBot._pool) - _WARM_MAX]:
                    victims.append((k, ent))
                    PooledTelegramBot._pool.pop(k, None)
        for _k, ent in victims:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=15)
            except Exception:
                pass

    def _call(self, cmd, *args, **kwargs):
        ent = self._ent
        ent["last_used"] = time.time()
        ent["q_in"].put((cmd, self.bot_target, args, kwargs))
        try:
            ok, res = ent["q_out"].get(timeout=180)
        except queue.Empty:
            raise RuntimeError(f"Telegram bot thread hung on '{cmd}' (180s)")
        if not ok:
            raise res
        return res

    def start(self):
        return self._call("open", log=self.log)

    def open(self):
        return self.start()

    def logged_in(self):
        """Live login state from the owner thread (True/False/None)."""
        try:
            return self._call("logged_in")
        except Exception:
            return None

    def open_bot(self):
        return self._call("open_bot")

    def choose_task(self, task=TG_DEFAULT_TASK):
        return self._call("choose_task", task)

    def start_task(self):
        return self._call("start_task")

    def submit_2fa_key(self, key, allow_local_fallback=True):
        return self._call("submit_2fa_key", key, allow_local_fallback=allow_local_fallback)

    def mark_registered(self):
        return self._call("mark_registered")

    def reset_to_main_menu(self, timeout=30):
        return self._call("reset_to_main_menu", timeout=timeout)

    def cancel_task(self):
        return self._call("cancel_task")

    def close(self, ok=True):
        try:
            return self._call("close_submit", ok=ok)
        except Exception:
            return False

    @classmethod
    def drop_profile(cls, profile_dir: str, headless: Optional[bool] = None) -> None:
        """Shut down and remove any pooled workers for this profile.

        ``headless`` is accepted for backward compat but ignored: the pool
        holds ONE owner per profile dir, so a drop always frees the lock.
        """
        if not profile_dir:
            return
        with cls._pool_lock:
            # Current key shape is the bare dir; also match legacy
            # (dir, headless) tuple keys from older runtimes.
            keys = [k for k in list(cls._pool.keys())
                    if k == profile_dir or (isinstance(k, tuple) and k and k[0] == profile_dir)]
            ents = [cls._pool.pop(k) for k in keys]
        for ent in ents:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=5)
            except Exception:
                pass

    @classmethod
    def drop_all(cls) -> None:
        """Shut down and remove all pooled workers."""
        with cls._pool_lock:
            ents = list(cls._pool.values())
            cls._pool.clear()
        for ent in ents:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=5)
            except Exception:
                pass


