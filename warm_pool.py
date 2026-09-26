"""
meta_auto_ai — warm browser processes for TG submitters
========================================================
Launching Chromium costs ~8s; a submit needs two browsers (IG + Telegram).
Instead of launch → 1 submit → close, this pool keeps ONE browser process
per leased TG profile and mints a FRESH, fully isolated Playwright context
per account (own cookies / storage / cache, closed after use).

Isolation proof: accounts never share a context — only the empty process
shell is reused, which carries no identity websites can correlate.

Lifecycle (enforced by the pool, not callers):
  * ``get(kind, key, headless)`` → WarmBrowser (relaunches if recycled).
  * ``new_account_context(warm)`` → fresh context (stealth + fingerprint
    injected for ``ig``; plain mobile profile for ``tg``).
  * ``close_account_context(ctx)`` after every account, success or fail.
  * ``release_process(kind, key)`` on lease release → process closed.
  * Recycle (relaunch) when: uses >= ``MAX_USES`` OR RSS > ``MAX_RSS_MB``
    OR consecutive failures >= ``MAX_CONSEC_FAILS`` (circuit breaker —
    a poisoned process must not fail N submits in a row).
"""
from __future__ import annotations

import os
import threading
import time

MAX_USES = 10
MAX_RSS_MB = 800
MAX_CONSEC_FAILS = 3

_IG_MOBILE_MODEL = "SM-S928B"

_NOVA_MIN_FLAGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]

# Headed tiling: IG windows live on the LEFT half, TG windows on the RIGHT
# half, so the TG browser (booted later, after Meta) never opens on top of
# the IG onboarding the user is watching. Headless ignores these harmlessly.
# NOTE (Wayland): Chrome on ozone-Wayland ignores --window-position. All
# headed launches also pass --ozone-platform=x11 (Xwayland runs on :0), so
# tiling actually applies. Without it the windows stack and "jump".
_IG_TILE = ["--window-size=500,950", "--window-position=0,0"]
_TG_TILE = ["--window-size=1000,950", "--window-position=520,0"]
_OZONE_X11 = ["--ozone-platform=x11"]

# INSTA_UI_MODE=new (default): Wayland-native visible windows — the compositor
# owns focus, so automation cannot steal the user's keystrokes. No positioning
# (Wayland ignores --window-position). "isolated": force X11 tiling + private
# virtual display (see virtual_display.py).
_DESKTOP_MODE = os.environ.get("INSTA_UI_MODE", "new").strip().lower() in (
    "new", "desktop", "wayland",
)
_TG_TILE_HEADED = (["--window-size=1000,950"] if _DESKTOP_MODE
                   else list(_TG_TILE + _OZONE_X11))

# TG browser, simplified on purpose: plain desktop session loader. No mobile
# emulation, no stealth, no touch — the bot works identically, the layout is
# stable, and there is nothing to "jump". The Telegram session itself is
# UA-independent (verified: the same profile loads fine on desktop).
_TG_DESKTOP_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _chrome_pids() -> set:
    """PIDs of running Chromium processes (any flavor)."""
    import subprocess
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return set()
    found = set()
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and "chrome" in parts[1].lower():
            try:
                found.add(int(parts[0]))
            except Exception:
                pass
    return found


def _browser_main_pid(before: set) -> int | None:
    """Main PID of a just-launched browser: new chrome PID without --type flag."""
    import subprocess
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except Exception:
            continue
        cmd = parts[1]
        if pid in before or "chrome" not in cmd.lower() or "--type=" in cmd:
            continue
        return pid
    return None


def _rss_tree_mb(pid: int) -> int:
    """Sum RSS of a process and all descendants via /proc (no deps)."""
    total_kb = 0
    try:
        stack, seen = [int(pid)], set()
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            try:
                with open(f"/proc/{p}/status", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            total_kb += int(line.split()[1])
                            break
                task_dir = f"/proc/{p}/task"
                for tid in os.listdir(task_dir):
                    try:
                        with open(os.path.join(task_dir, tid, "children"), encoding="utf-8") as f:
                            stack.extend(int(x) for x in f.read().split())
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
    return total_kb // 1024


def _apply_ig_stealth(ctx, ua: str, chrome_full: str, log=None) -> None:
    try:
        from playwright_stealth import Stealth
        Stealth(
            navigator_user_agent_override=ua,
            navigator_platform_override="Linux armv8l",
            navigator_languages_override=("en-US", "en"),
            webgl_vendor_override="Qualcomm",
            webgl_renderer_override="Adreno (TM) 750",
        ).apply_stealth_sync(ctx)
    except Exception as exc:
        if log:
            try:
                log(f"[⚠️] Stealth skipped: {exc}")
            except Exception:
                pass
    try:
        import run as _eng
        ctx.add_init_script(_eng._build_antidetect_script(ua, chrome_full, is_mobile=True))
    except Exception as exc:
        if log:
            try:
                log(f"[⚠️] Anti-detect inject failed: {exc}")
            except Exception:
                pass


class WarmBrowser:
    """One reusable Chromium process + per-account fresh contexts.

    ``ig`` kind: plain ``launch()``; every account gets a FRESH context
    (full isolation) which the caller closes.
    ``tg`` kind (+ ``user_data_dir``): ONE persistent context bound to the
    Telegram profile dir (the session lives there by design — single tenant,
    so sharing across submits is correct). ``close_account_context`` is a
    no-op for it; the process/context persist until recycle or release.
    """

    def __init__(self, kind: str, key: str, headless: bool, user_data_dir=None):
        self.kind = kind
        self.key = key
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.lock = threading.Lock()
        self.playwright = None
        self.browser = None
        self.ctx = None  # persistent context (tg kind only)
        self.pid = None
        self.uses = 0
        self.consec_fails = 0
        self.born = time.time()
        self._launch()

    @property
    def persistent(self) -> bool:
        return self.kind == "tg" and bool(self.user_data_dir)

    # -- process lifecycle ------------------------------------------------
    def _launch(self) -> None:
        from playwright.sync_api import sync_playwright
        before = _chrome_pids()
        self.playwright = sync_playwright().start()
        channel = "chrome" if (os.path.isfile("/usr/bin/google-chrome") or os.path.isfile("/usr/bin/google-chrome-stable")) else None
        if self.persistent:
            self.browser = None
            if self.user_data_dir:
                try:
                    holder = lock_holder_alive(self.user_data_dir)
                    if not holder:
                        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
                            try:
                                os.unlink(os.path.join(self.user_data_dir, name))
                            except Exception:
                                pass
                except Exception:
                    pass
            kw = dict(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                viewport={"width": 980, "height": 880},
                user_agent=_TG_DESKTOP_UA,
                args=list(_NOVA_MIN_FLAGS) + ([] if self.headless else list(_TG_TILE_HEADED)),
                ignore_default_args=["--enable-automation"],
            )
            if channel:
                kw["channel"] = channel
            self.ctx = self.playwright.chromium.launch_persistent_context(**kw)
        else:
            kw = dict(headless=self.headless, args=list(_NOVA_MIN_FLAGS))
            if channel:
                kw["channel"] = channel
            self.browser = self.playwright.chromium.launch(**kw)
            self.ctx = None
        self.pid = _browser_main_pid(before)
        self.uses = 0
        self.consec_fails = 0
        self.born = time.time()

    def close_process(self) -> None:
        try:
            if self.ctx is not None:
                self.ctx.close()
        except Exception:
            pass
        try:
            if self.browser is not None:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright is not None:
                self.playwright.stop()
        except Exception:
            pass
        self.browser = None
        self.ctx = None
        self.pid = None

    # -- health ------------------------------------------------------------
    def rss_mb(self) -> int:
        if not self.pid:
            return 0
        try:
            return _rss_tree_mb(self.pid)
        except Exception:
            return 0

    def needs_recycle(self) -> bool:
        if self.pid:
            try:
                if not os.path.exists(f"/proc/{self.pid}"):
                    return True
            except Exception:
                pass
        if self.persistent:
            if self.ctx is None:
                return True
            try:
                if hasattr(self.ctx, "is_closed") and self.ctx.is_closed():
                    return True
            except Exception:
                pass
        elif self.browser is None:
            return True
        if self.uses >= MAX_USES:
            return True
        if self.consec_fails >= MAX_CONSEC_FAILS:
            return True
        try:
            if self.rss_mb() > MAX_RSS_MB:
                return True
        except Exception:
            pass
        return False

    def note_result(self, ok: bool) -> None:
        if ok:
            self.consec_fails = 0
        else:
            self.consec_fails += 1

    # -- per-account contexts (isolation boundary) -------------------------
    def new_account_context(self, proxy=None, log=None, model=None):
        """Context for one account.

        ``ig``: FRESH isolated context (caller closes it after use). ``model``
        pins the phone model/UA to the account's creation-time device
        (Nova parity); defaults to SM-S928B for legacy records without a pin.
        ``tg`` (persistent): the profile-bound context itself — the Telegram
        session lives there by design (single tenant), so sharing across
        submits is correct; per-submit menu reset clears chat state.
        """
        if self.persistent:
            if self.ctx is None:
                raise RuntimeError("warm TG process has no context (recycled?)")
            self.uses += 1
            return self.ctx
        # ig: mobile anti-detect, UA matched to the real browser build
        try:
            chrome_full = self.browser.version
        except Exception:
            chrome_full = "124.0.6367.82"
        major = str(chrome_full).split(".")[0]
        _ = major
        _model = model if model in ("SM-S928B", "Pixel 7", "SM-G991B", "OnePlus 12") else _IG_MOBILE_MODEL
        ua = (f"Mozilla/5.0 (Linux; Android 14; {_model}) "
              f"AppleWebKit/537.36 (KHTML, like Gecko) "
              f"Chrome/{chrome_full} Mobile Safari/537.36")
        ctx = self.browser.new_context(
            user_agent=ua,
            viewport={"width": 393, "height": 852},
            device_scale_factor=3,
            is_mobile=True, has_touch=True, proxy=proxy,
        )
        _apply_ig_stealth(ctx, ua, str(chrome_full), log=log)
        self.uses += 1
        return ctx


_pool: dict = {}
_pool_lock = threading.Lock()
# Launch reservation: ck -> threading.Event. The thread that starts a launch
# registers an event FIRST so concurrent get() calls for the same key WAIT
# instead of double-launching two Chromiums on one profile dir (the
# SingletonLock death loop: pre-warm vs slot boot racing at engine start).
_entering: dict = {}


def _shutdown_all() -> None:
    """Close every warm process at interpreter exit (no orphaned browsers)."""
    try:
        with _pool_lock:
            entries = list(_pool.values())
            _pool.clear()
        for wb in entries:
            try:
                with wb.lock:
                    wb.close_process()
            except Exception:
                pass
    except Exception:
        pass


import atexit as _atexit
_atexit.register(_shutdown_all)


def get(kind: str, key: str, headless: bool, user_data_dir=None) -> WarmBrowser:
    """Return a healthy warm process for (kind, key), relaunching as needed.

    ``user_data_dir`` is required for the persistent ``tg`` kind (the
    Telegram profile dir); it becomes part of the pool key.

    Concurrency: the first caller reserves the key and launches; concurrent
    callers wait on the reservation event (up to 150s) instead of launching
    duplicates onto the same profile dir.
    """
    import threading as _th

    ck = (kind, key, bool(headless), user_data_dir)
    # TG single-owner invariant: ONE Chromium per profile dir. The pool key
    # includes headless, so a Visible↔Background flip would otherwise launch
    # a SECOND browser on the same dir → SingletonLock fight → blank profile
    # on both sides ("opened but tg isn't showing"). Evict the opposite
    # headless entry for the same dir before reserving.
    if kind == "tg" and user_data_dir:
        try:
            with _pool_lock:
                for _ck, _wb in list(_pool.items()):
                    if len(_ck) == 4 and _ck[0] == "tg" and _ck[3] == user_data_dir and bool(_ck[2]) != bool(headless):
                        _victim = _pool.pop(_ck, None)
                        if _victim is not None:
                            try:
                                with _victim.lock:
                                    _victim.close_process()
                            except Exception:
                                pass
        except Exception:
            pass
    for _ in range(4):
        mine = False
        ev = None
        wb = None
        with _pool_lock:
            wb = _pool.get(ck)
            if wb is None:
                if ck in _entering:
                    ev = _entering[ck]  # someone else is launching: wait below
                else:
                    ev = _th.Event()
                    _entering[ck] = ev
                    mine = True  # we launch below
        if wb is not None:
            with wb.lock:
                if wb.needs_recycle():
                    try:
                        wb.close_process()
                    except Exception:
                        pass
                    wb._launch()
            return wb
        if not mine:
            # Another thread is launching this key: wait, then re-check.
            try:
                ev.wait(timeout=150)
            except Exception:
                pass
            continue
        # We hold the reservation: launch outside the pool lock.
        try:
            launched = WarmBrowser(kind, key, bool(headless), user_data_dir=user_data_dir)
        except Exception:
            with _pool_lock:
                if _entering.get(ck) is ev:
                    _entering.pop(ck, None)
                    ev.set()
            raise
        with _pool_lock:
            _pool[ck] = launched
            if _entering.get(ck) is ev:
                _entering.pop(ck, None)
                ev.set()
        return launched
    # Reservation holder died without releasing (shouldn't happen): launch anyway.
    with _pool_lock:
        _entering.pop(ck, None)
    wb = WarmBrowser(kind, key, bool(headless), user_data_dir=user_data_dir)
    with _pool_lock:
        _pool[ck] = wb
    return wb


def lock_holder_alive(user_data_dir):
    """PID holding a profile's SingletonLock, or None.

    Reads the `host-pid` symlink target and verifies /proc/<pid>/cmdline
    still references this profile dir. A lock file pointing at a dead PID
    (SIGKILLed orphan aftermath) is stale — safe to clean + relaunch.
    A live holder (engine warm browser OR the user's dashboard inspection
    window — same flags, indistinguishable) must NEVER be SIGKILLed.
    """
    import re as _re

    dur = str(user_data_dir or "")
    if not dur:
        return None
    try:
        target = os.readlink(os.path.join(dur, "SingletonLock"))
    except Exception:
        return None
    m = _re.search(r"-(\d+)$", target or "")
    if not m:
        return None
    pid = m.group(1)
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            cmd = fh.read().decode("utf-8", "replace")
    except Exception:
        return None
    if dur in cmd and ("chrome" in cmd or "chromium" in cmd):
        return int(pid)
    return None


def drop_entry(kind: str, key: str, headless: bool, user_data_dir=None) -> bool:
    """Forget a pool entry WITHOUT touching Playwright objects.

    Thread-safe eviction for failover paths running outside the owner's
    thread (calling close_process cross-thread corrupts Playwright's
    greenlet state — the phantom "Sync API inside asyncio loop" errors).
    Pair with kill_profile_tree() which reaps the OS processes.
    """
    ck = (kind, key, bool(headless), user_data_dir)
    with _pool_lock:
        return _pool.pop(ck, None) is not None


def kill_profile_tree(user_data_dir) -> int:
    """SIGTERM→SIGKILL every OS process launched on a profile dir.

    Matches Chromium's `--user-data-dir=<dir>` on the command line, so the
    user's own Chrome (different profile) is never touched. Afterwards
    removes stale Singleton lock files. Returns processes signalled.
    """
    import subprocess as _sp

    dur = str(user_data_dir or "")
    if not dur or dur in ("/", os.path.expanduser("~")):
        return 0
    flag = f"user-data-dir={dur}"
    killed = 0
    try:
        out = _sp.run(["pgrep", "-f", flag], capture_output=True, text=True, timeout=10).stdout or ""
        pids = [p for p in (x.strip() for x in out.split()) if p.isdigit() and int(p) != os.getpid()]
    except Exception:
        pids = []
    for sig in ("TERM", "KILL"):
        if not pids:
            break
        try:
            _sp.run(["kill", f"-{sig}"] + pids, timeout=10)
        except Exception:
            pass
        import time as _t

        _t.sleep(2 if sig == "TERM" else 1)
        try:
            out = _sp.run(["pgrep", "-f", flag], capture_output=True, text=True, timeout=10).stdout or ""
            pids = [p for p in (x.strip() for x in out.split()) if p.isdigit() and int(p) != os.getpid()]
        except Exception:
            pids = []
        killed += 1
    try:
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            try:
                os.unlink(os.path.join(dur, name))
            except Exception:
                pass
    except Exception:
        pass
    return killed


def release_process(kind: str, key: str, headless: bool, user_data_dir=None) -> None:
    """Close and forget a warm process (call on lease release)."""
    ck = (kind, key, bool(headless), user_data_dir)
    with _pool_lock:
        wb = _pool.pop(ck, None)
    if wb is not None:
        with wb.lock:
            try:
                wb.close_process()
            except Exception:
                pass


def close_account_context(ctx, persistent: bool = False) -> None:
    """Close a per-account context. No-op for persistent (tg) contexts,
    which belong to the warm process, not the account."""
    if persistent:
        return
    try:
        if ctx is not None:
            ctx.close()
    except Exception:
        pass
