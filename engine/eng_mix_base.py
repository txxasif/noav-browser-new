"""engine.eng_mix_base — identity, logging & human-like input primitives.

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
    from .eng_constants import HERE, _MONTHS  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import HERE, _MONTHS  # noqa: E402

class EngineBaseMixin:
    def __init__(self, worker):
        self.w = worker
        self.core = sys.modules.get("instaauto_core")
        self.page = None
        self.mail = None
        self.email = None
        self.password = worker.password or ("Pass#" + str(random.randint(100000, 999999)))
        self.first = random.choice(getattr(self.core, "FIRST_NAMES", ["Alex"]))
        self.last = random.choice(getattr(self.core, "LAST_NAMES", ["Smith"]))
        self.name = f"{self.first} {self.last}"
        self.meta_name = self.name
        self.username = f"{self.first.lower()}.{self.last.lower()}{random.randint(100, 9999)}"
        self.dob_month = random.choice(_MONTHS)
        self.dob_day = str(random.randint(1, 28))
        self.dob_year = str(random.randint(1985, 1999))
        self.selfie_path = None
        for _name in ("selfie.png", "selfie.jpg", "selfie.jpeg", "Pasted image.png"):
            for _base in (HERE, os.path.join(HERE, "..")):
                _p = os.path.join(_base, _name)
                if os.path.exists(_p):
                    self.selfie_path = _p
                    break
            if self.selfie_path:
                break
        self._vosk_model = None
        self._whisper_model = None
        self._ocr_engine = None

    # -- logging / playwright helpers --------------------------------------
    def log(self, msg):
        self.w.log_signal.emit(msg)

    def _detect_chrome_version(self, w):
        """Return the real browser build without launching a GUI on Windows.

        Chrome for Testing's Windows executable does not reliably implement
        ``chrome.exe --version`` as a console command: it opens a temporary
        Chrome-for-Testing window, exits, and leaves the restore bubble behind.
        That probe also runs immediately before the real persistent context,
        which made headed starts look like an extra browser was flashing.

        On Windows read the PE version resource through PowerShell instead. On
        POSIX retain the cheap executable ``--version`` probe.
        """
        import subprocess
        try:
            exe = w.playwright.chromium.executable_path
            if os.name == "nt":
                # The executable path comes from the bundled Playwright tree,
                # but quote it anyway because Windows paths may contain spaces.
                safe_exe = str(exe).replace("'", "''")
                ps = (
                    "$ErrorActionPreference='Stop'; "
                    f"(Get-Item -LiteralPath '{safe_exe}').VersionInfo.ProductVersion"
                )
                out = subprocess.check_output(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                    text=True,
                    timeout=10,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                out = subprocess.check_output([exe, "--version"], text=True, timeout=20)
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
            if m:
                return m.group(1)
        except Exception:
            pass
        return "124.0.6367.82"

    # -- human-like interaction -------------------------------------------
    def _pause(self, page, lo=0.4, hi=1.4):
        page.wait_for_timeout(int(random.uniform(lo, hi) * 1000))

    def _human_click(self, page, locator, timeout=25000):
        box = locator.bounding_box(timeout=timeout)
        if not box:
            locator.click(timeout=timeout)
            return
        x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        page.mouse.move(x, y, steps=random.randint(8, 20))
        page.wait_for_timeout(random.randint(50, 160))
        page.mouse.click(x, y)

    def _react_set_value(self, locator, text) -> bool:
        """Force a (React-controlled) input to hold ``text`` via the native setter.

        Playwright's ``fill`` — and even char-by-char ``keyboard.type`` — can be
        swallowed by React's synthetic value tracking on styled inputs (Accounts
        Center): the DOM keeps the empty/old value, the form's submit button
        stays disabled, and the submit silently no-ops. Reproduced live via MCP
        2026-09-21 (2FA "Enter code" left ``Next`` disabled; the Change-password
        fields only took with the native setter). Calling the prototype value
        setter + dispatching input/change/blur makes React's onChange fire.
        """
        try:
            locator.evaluate(
                """(el, v) => {
                    const proto = (el instanceof HTMLTextAreaElement)
                        ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                    const d = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (d && d.set) { d.set.call(el, v); } else { el.value = v; }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }""",
                text,
            )
            return True
        except Exception:
            return False

    def _clean_fill(self, page, locator, text, timeout=25000):
        """Clear + fill ``text`` and return True only when it ACTUALLY landed.

        React-controlled Accounts Center fields could swallow ``fill`` and the
        char-typing, leaving the field empty and the submit disabled — the old
        code returned True regardless, so the password stage reported
        ``not_confirmed`` and the account was parked (reproduced live via MCP
        2026-09-21). We now verify and re-inject the exact value via the native
        setter before returning. The value written is always exactly ``text``,
        so callers' semantics (current vs new password) are unchanged.
        """
        def _val():
            try:
                return locator.input_value()
            except Exception:
                return None

        try:
            self._human_click(page, locator, timeout)
            page.wait_for_timeout(random.randint(80, 180))
            # Only send keyboard CLEAR keys when the field is actually FOCUSED.
            # A stray Control+A on an unfocused page selects the WHOLE document
            # (the visible text highlights — looks like it is "copying the page
            # text"; observed 2026-09-21), and the char-typing would then land on
            # the document instead of the field.
            focused = False
            try:
                locator.focus(timeout=2000)
                focused = bool(locator.evaluate("el => document.activeElement === el"))
            except Exception:
                focused = False
            if focused:
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(50)
            try:
                locator.fill("")
            except Exception:
                pass
            page.wait_for_timeout(50)
            if focused:
                for ch in text:
                    page.keyboard.type(ch, delay=random.randint(30, 70))
            else:
                # Not focused → never type into the void; set the value directly.
                try:
                    locator.fill(text, timeout=timeout)
                except Exception:
                    pass
            page.wait_for_timeout(100)
        except Exception:
            try:
                locator.fill(text, timeout=timeout)
            except Exception:
                pass

        # Verify and re-inject until the value sticks (max 2 rounds).
        for _ in range(2):
            if _val() == text:
                return True
            try:
                locator.fill(text, timeout=timeout)
            except Exception:
                pass
            if _val() == text:
                return True
            self._react_set_value(locator, text)
            page.wait_for_timeout(random.randint(60, 140))
        return _val() == text

    def _human_type(self, page, locator, text, timeout=25000):
        return self._clean_fill(page, locator, text, timeout=timeout)

    def _prune_profiles(self, base, keep=20):
        """Keep the newest profile dirs; remove older ones to bound disk use.

        Never prune a dir still referenced by an account record (per-account
        IG profiles must survive for Nova-parity reuse on open/resume), and
        never prune a dir holding a LIVE browser (its SingletonLock points
        at a running Chromium pid) — deleting it mid-run orphans the session
        and makes the live profile unclonable for inspection.
        """
        def _live_holder(d):
            try:
                tgt = os.readlink(os.path.join(d, "SingletonLock"))
            except Exception:
                return False
            import re as _re
            m = _re.search(r"-(\d+)$", tgt or "")
            if not m:
                return False
            try:
                with open(f"/proc/{m.group(1)}/cmdline", "rb") as fh:
                    cmd = fh.read().decode("utf-8", "replace")
                return "chrome" in cmd.lower() and d in cmd
            except Exception:
                return False
        try:
            keep_dirs = set()
            try:
                import store as _store
                for _r in _store.list_all():
                    _pd = (_r or {}).get("profile_dir")
                    if _pd:
                        keep_dirs.add(os.path.abspath(_pd))
            except Exception:
                pass
            dirs = [os.path.join(base, d) for d in os.listdir(base)
                    if d.startswith("insta_")]
            dirs = [d for d in dirs if os.path.isdir(d)
                    and os.path.abspath(d) not in keep_dirs
                    and not _live_holder(d)]
            dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
            for old in dirs[keep:]:
                shutil.rmtree(old, ignore_errors=True)
        except Exception:
            pass

