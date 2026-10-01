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
import threading
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import HERE, _MONTHS  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import HERE, _MONTHS  # noqa: E402
try:
    from .resource_runtime import active_profiles, should_prune  # type: ignore
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from resource_runtime import active_profiles, should_prune  # type: ignore  # noqa: E402

# Auto-generated profile directory prefixes. ONLY these are eligible for
# pruning; anything else in profiles/ is left strictly alone.
#   insta_      -> engine/eng_mix_launch._launch ("insta_<slot>_<time_ns>")
#   test_meta_  -> test harness profiles
# The old filter matched "insta_" alone, so test-harness profiles were
# invisible to pruning and accumulated forever (observed 2026-10-01: 4
# test_meta_* dirs, ~160 MB, three days old, never reclaimed).
_PROFILE_PREFIXES = ("insta_", "test_meta_")

# ── Identity pools ───────────────────────────────────────────────────────
# The launcher used to read FIRST_NAMES/LAST_NAMES off `instaauto_core` with a
# ONE-ELEMENT fallback (["Alex"] / ["Smith"]). That module is not importable in
# this build, so the fallback ALWAYS won: every account ever created was named
# "Alex Smith" with a username of "alex.smith<1234>" — 1570/1570 identical
# (verified 2026-10-01). That is a textbook automation signature and is very
# likely feeding IG's checkpoint_required bans.
#
# These pools are deliberately broad and multi-origin so accounts do not
# cluster, and stay ASCII (IG usernames allow only [A-Za-z0-9._]).
_FIRST_NAMES = (
    "Liam", "Noah", "Ethan", "Mason", "Logan", "Lucas", "Aiden", "Owen",
    "Dylan", "Wyatt", "Carter", "Julian", "Levi", "Miles", "Ezra", "Nolan",
    "Emma", "Olivia", "Ava", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia",
    "Harper", "Evelyn", "Abigail", "Ella", "Scarlett", "Grace", "Chloe",
    "Zoe", "Nora", "Lily", "Hazel", "Aurora", "Willow", "Ivy", "Ruby",
    "Mateo", "Diego", "Santiago", "Alejandro", "Adrian", "Rafael", "Emilio",
    "Camila", "Valentina", "Sofia", "Lucia", "Elena", "Mariana", "Daniela",
    "Carlos", "Andres", "Javier", "Miguel", "Tomas", "Bruno", "Nicolas",
    "Aisha", "Fatima", "Zara", "Yusuf", "Omar", "Amir", "Layla", "Noor",
    "Aditi", "Ananya", "Priya", "Rohan", "Arjun", "Vikram", "Neha", "Kavya",
    "Hana", "Yuki", "Ren", "Sakura", "Mei", "Jin", "Sora", "Aiko",
    "Nadia", "Ivana", "Marko", "Petra", "Lena", "Jonas", "Felix", "Greta",
    "Amara", "Kwame", "Zainab", "Chidi", "Thabo", "Nia", "Sipho", "Ayanda",
)

_LAST_NAMES = (
    "Anderson", "Bennett", "Carter", "Dawson", "Ellis", "Fletcher", "Greene",
    "Harrington", "Ingram", "Jefferson", "Keller", "Lambert", "Marshall",
    "Nelson", "Osborne", "Parker", "Quinn", "Reeves", "Sullivan", "Turner",
    "Underwood", "Vaughn", "Wallace", "Whitaker", "Yates", "Zimmerman",
    "Alvarez", "Bautista", "Castillo", "Delgado", "Espinoza", "Fuentes",
    "Gutierrez", "Herrera", "Ibarra", "Jimenez", "Lozano", "Mendoza",
    "Navarro", "Ochoa", "Paredes", "Quintero", "Ramirez", "Salazar",
    "Trejo", "Uribe", "Valencia", "Zamora", "Rosales", "Cordero",
    "Khan", "Ahmed", "Hassan", "Rahman", "Farooq", "Ansari", "Qureshi",
    "Sharma", "Patel", "Reddy", "Iyer", "Nair", "Chowdhury", "Bhatt",
    "Novak", "Petrov", "Kovac", "Sokolov", "Ivanov", "Marchetti", "Rossi",
    "Dubois", "Laurent", "Moreau", "Schmidt", "Fischer", "Weber", "Hoffmann",
    "Okafor", "Mensah", "Abebe", "Nkosi", "Diallo", "Mwangi", "Boateng",
    "Tanaka", "Nakamura", "Sato", "Kim", "Park", "Nguyen", "Tran", "Chen",
)

_ALNUM = re.compile(r"[^a-z0-9]")


def _slug(s: str, limit: int = 14) -> str:
    """Lowercase, ASCII-only, alnum — safe for an IG username component."""
    return _ALNUM.sub("", str(s or "").lower())[:limit]


def _make_username(first: str, last: str) -> str:
    """Build an IG-valid username from a real name, in one of several shapes.

    Validated against ``tg_support._is_valid_ig_username``:
    ``^(?!.*\\.\\.)(?!^\\.)(?!.*\\.$)[a-zA-Z0-9._]{1,30}$`` — 1-30 chars, only
    letters/digits/./_, no leading/trailing dot, no doubled dot.

    The old single format (``first.last<1234>``) is what made 1570 accounts
    share one shape; mixing shapes removes that constant.
    """
    f, l = _slug(first), _slug(last)
    if not f:
        f, l = "user", (l or "ig")
    n = random.randint(1, 9999)
    shapes = (
        f"{f}.{l}{n}",
        f"{f}_{l}{n}",
        f"{f}{l}{n}",
        f"{f}{n}{l[:3]}",
        f"{l}.{f}{n}",
        f"{f}{l[:1]}{n}",
        f"{f[:9]}{l[:9]}{random.randint(10, 99)}",
    )
    u = random.choice(shapes)
    # Belt-and-braces against the documented regex.
    u = u.strip("._")
    while ".." in u:
        u = u.replace("..", ".")
    if len(u) > 30:
        u = u[:30].strip("._")
    if not u:
        u = f"user{random.randint(10000, 99999)}"
    return u

_CHROME_VERSION_CACHE: dict[str, str] = {}
_CHROME_VERSION_LOCK = threading.Lock()


class EngineBaseMixin:
    def __init__(self, worker):
        self.w = worker
        self.core = sys.modules.get("instaauto_core")
        self.page = None
        self.mail = None
        self.email = None
        self.password = worker.password or ("Pass#" + str(random.randint(100000, 999999)))
        # Real pools with a real fallback. The old code read these off
        # `instaauto_core` (never importable here) and fell back to a SINGLE
        # name each, so every account was "Alex Smith" / "alex.smith<1234>".
        # Prefer the core's pools when they genuinely exist and are non-empty.
        _fn = getattr(self.core, "FIRST_NAMES", None) or _FIRST_NAMES
        _ln = getattr(self.core, "LAST_NAMES", None) or _LAST_NAMES
        self.first = random.choice(_fn)
        self.last = random.choice(_ln)
        self.name = f"{self.first} {self.last}"
        self.meta_name = self.name
        self.username = _make_username(self.first, self.last)
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
        """Return the browser build, probing each executable only once.

        The Windows probe starts a short-lived PowerShell process.  Running it
        once per slot creates a burst of PowerShell/Chrome work during a
        parallel start, so cache the immutable result per executable path.
        """
        import subprocess
        try:
            exe = str(w.playwright.chromium.executable_path)
            cache_key = os.path.normcase(os.path.abspath(exe))
        except Exception:
            return "124.0.6367.82"

        with _CHROME_VERSION_LOCK:
            cached = _CHROME_VERSION_CACHE.get(cache_key)
            if cached:
                return cached
            version = None
            try:
                if os.name == "nt":
                    # The executable path comes from the bundled Playwright
                    # tree, but quote it because Windows paths may contain
                    # spaces or apostrophes.
                    safe_exe = exe.replace("'", "''")
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
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
                if match:
                    version = match.group(1)
            except Exception:
                pass
            if not version:
                version = "124.0.6367.82"
            _CHROME_VERSION_CACHE[cache_key] = version
            return version

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
                # Only a REAL text field may receive Control+A. A Bloks/React
                # wrapper div with tabindex also satisfies `activeElement === el`,
                # but Control+A on it selects the WHOLE DOCUMENT — the blue
                # "everything highlighted" login screen (observed 2026-09-27),
                # and the field never receives the value so Log in stays dead.
                focused = bool(locator.evaluate(
                    "el => document.activeElement === el && "
                    "(el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')"))
            except Exception:
                focused = False
            if focused:
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(50)
            else:
                # Never leave a stray document-wide selection behind.
                try:
                    page.evaluate("() => { const s = window.getSelection && window.getSelection(); "
                                  "if (s && s.rangeCount) s.removeAllRanges(); }")
                except Exception:
                    pass
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

    def _prune_profiles(self, base, keep=None):
        """Keep the newest profile dirs without racing active slots.

        Profile pruning used to run a full directory/database scan for every
        slot.  On a 10–20 slot start that creates unnecessary I/O and, on
        Windows, the old ``/proc``-only live-process check could not protect a
        currently running profile.  Throttle the scan, protect the in-process
        registry, and use a short minimum age before removing an unreferenced
        directory.
        """
        def _live_holder(d):
            # Linux Chromium exposes SingletonLock as a symlink.  Windows
            # does not provide an equivalent /proc-style check, so the
            # registry below is the authoritative protection there.
            if os.name == "nt":
                return False
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
            keep = int(os.environ.get("INSTA_PROFILE_KEEP", "20")) if keep is None else int(keep)
            keep = max(1, min(keep, 200))
        except (TypeError, ValueError):
            keep = 20
        try:
            prune_interval = max(0.0, float(os.environ.get("INSTA_PROFILE_PRUNE_INTERVAL", "30")))
        except (TypeError, ValueError):
            prune_interval = 30.0
        try:
            min_age = max(0.0, float(os.environ.get("INSTA_PROFILE_MIN_AGE_SEC", "300")))
        except (TypeError, ValueError):
            min_age = 300.0

        base_key = os.path.normcase(os.path.abspath(base))
        if not should_prune("profiles:" + base_key, prune_interval):
            return

        try:
            now = time.time()
            protected = active_profiles()
            keep_dirs = set()
            try:
                import store as _store
                for _r in _store.list_all():
                    _pd = (_r or {}).get("profile_dir")
                    if _pd:
                        keep_dirs.add(os.path.normcase(os.path.abspath(_pd)))
            except Exception:
                pass

            candidates = []
            for name in os.listdir(base):
                # Auto-generated profile dirs ONLY: `insta_<slot>_<ns>` from the
                # launcher and `test_meta_*` from the test harness. The old
                # filter matched `insta_` alone, so every test-harness profile
                # was invisible to pruning and accumulated FOREVER (observed
                # 2026-10-01: 4 test_meta_* dirs, ~160 MB, three days old, still
                # present). Anything not matching one of these prefixes is left
                # strictly alone -- pruning must never touch a user-named dir.
                if not name.startswith(_PROFILE_PREFIXES):
                    continue
                path = os.path.join(base, name)
                if not os.path.isdir(path):
                    continue
                normalized = os.path.normcase(os.path.abspath(path))
                if normalized in protected or normalized in keep_dirs or _live_holder(path):
                    continue
                try:
                    # A profile younger than the grace period may belong to a
                    # just-starting slot whose context has not registered yet.
                    if now - os.path.getmtime(path) < min_age:
                        continue
                except OSError:
                    continue
                candidates.append(path)

            candidates.sort(key=lambda d: os.path.getmtime(d), reverse=True)
            for old in candidates[keep:]:
                shutil.rmtree(old, ignore_errors=True)
        except Exception:
            pass

