"""mem_guard.py — /proc/meminfo memory guard for the engine.

Why this exists
---------------
Chromium is the memory sink: each automation browser is a whole process tree
(~10 processes, several hundred MB), and a run holds creators + retained
"inspection" browsers + warm Telegram trees at once. When demand passes RAM +
swap the kernel OOM-killer (or systemd-oomd's GNOME "Application Stopped —
memory nearly full" force-stop) kills a process outright — observed
2026-09-19, made worse by stacked engines (now fixed by the engine lock).

What it does
------------
Two layers, both cheap and /proc-based (no dependencies):

* ``available_mb()`` / ``total_mb()`` — read the kernel's own ``MemAvailable``.
* ``watch(stop_event, log)`` — a daemon watchdog. Under ``LOW_FREE_MB`` it
  *sheds* reclaimable Chromium (retained inspection browsers + warm Telegram
  pools) and keeps going; under ``MIN_FREE_MB`` it requests a **graceful stop**
  so the engine tears its own browsers down instead of being SIGKILLed.

The Node dashboard has a matching pre-flight (``Engine._ramGuard``) that
refuses a start below a hard floor and otherwise clamps the requested parallel
creator count to what the free RAM can hold.

Nothing here ever raises into the run: a failed read just skips the check.
"""
from __future__ import annotations

import os
import threading

_MEMINFO = "/proc/meminfo"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


def _read_kb(key: str):
    try:
        with open(_MEMINFO, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith(key + ":"):
                    return int(line.split()[1])
    except Exception:
        pass
    return None


def total_mb():
    if os.name == "nt":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys // (1024 * 1024))
        except Exception:
            pass
    kb = _read_kb("MemTotal")
    return None if kb is None else kb // 1024


def available_mb():
    """Kernel/OS estimate of allocatable RAM (MB), or None if unreadable."""
    if os.name == "nt":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullAvailPhys // (1024 * 1024))
        except Exception:
            pass
    kb = _read_kb("MemAvailable")
    if kb is not None:
        return kb // 1024
    free = _read_kb("MemFree")
    swap = _read_kb("SwapFree")
    if free is None and swap is None:
        return None
    return ((free or 0) + (swap or 0)) // 1024


def check_ram_safe(reserve_mb: int = 3000) -> bool:
    """Return True if available memory is above reserve_mb."""
    avail = available_mb()
    if avail is None or DISABLED:
        return True
    return avail >= reserve_mb


# ---- knobs (env-overridable) ---------------------------------------------
LOW_FREE_MB = _env_int("ENGINE_LOW_FREE_MB", 2500)       # below -> shed browsers
MIN_FREE_MB = _env_int("ENGINE_MIN_FREE_MB", 1200)       # below -> graceful stop
CHECK_SECS = _env_int("ENGINE_MEM_CHECK_SECS", 15)
RESERVE_MB = _env_int("ENGINE_MEM_RESERVE_MB", 0)          # 0 = auto (~20% of RAM, 1200-3000)
PER_BROWSER_MB = _env_int("ENGINE_MEM_PER_BROWSER_MB", 0)          # 0 = auto (mode-aware)
PER_BROWSER_MB_HEADLESS = _env_int("ENGINE_MEM_PER_BROWSER_HEADLESS_MB", 320)
PER_BROWSER_MB_HEADED = _env_int("ENGINE_MEM_PER_BROWSER_HEADED_MB", 800)
DISABLED = os.environ.get("ENGINE_MEM_GUARD", "1") == "0"


def _per_browser_mb(headless: bool = False) -> int:
    """Per-browser RAM estimate. Headless Chromium is far lighter than headed,
    so a single flat number either wasted capacity (headless) or over-committed
    (headed). Override with ENGINE_MEM_PER_BROWSER_MB."""
    if PER_BROWSER_MB:
        return PER_BROWSER_MB
    return PER_BROWSER_MB_HEADLESS if headless else PER_BROWSER_MB_HEADED


def _effective_reserve_mb() -> int:
    """OS/user reserve.

    ``MemAvailable`` already excludes what the OS and user apps are using, so a
    large *extra* reserve double-counts and refused to start even one browser on
    low-end machines. Keep ~20% of physical RAM, clamped to [1200, 3000] MB.
    Override with ``ENGINE_MEM_RESERVE_MB``.
    """
    if RESERVE_MB:
        return RESERVE_MB
    total = total_mb()
    if not total:
        return 2000
    return min(2500, max(1000, int(total * 0.15)))


def ram_concurrency_cap(requested: int, headless: bool = False):
    """Clamp parallel creators to what free RAM can hold.

    Returns ``(cap, note)``. ``cap == 0`` means "refuse to start" (even one
    browser will not fit). A non-empty ``note`` explains a clamp/refusal.
    Mirrors the Node pre-flight ``Engine._ramGuard`` so a CLI run is covered too.
    """
    avail = available_mb()
    if avail is None or DISABLED:
        return requested, ""
    reserve = _effective_reserve_mb()
    per = _per_browser_mb(headless)
    floor = reserve + per
    if avail < floor:
        return 0, f"only {avail} MB RAM available (need >= {floor} MB)"
    cap = max(1, (avail - reserve) // per)
    if requested > cap:
        # Clamp by default: over-committing RAM crashes Chromium mid-run
        # ("Connection closed while reading from the driver") and loses the
        # whole batch. A visible clamp is far safer than a silent OOM kill.
        # Set ENGINE_ALLOW_OVERCOMMIT=1 to force the requested count anyway.
        if os.environ.get("ENGINE_ALLOW_OVERCOMMIT", "0") == "1":
            return requested, (f"WARNING: {requested} browsers requested but only {avail} MB "
                               f"free (suggests ~{cap}) - continuing (ENGINE_ALLOW_OVERCOMMIT=1)")
        return cap, (f"RAM Guard: reducing concurrency {requested} -> {cap} "
                     f"({avail} MB free, ~{per} MB/browser, reserve {reserve} MB). "
                     f"Set ENGINE_ALLOW_OVERCOMMIT=1 to force the requested count.")
    return requested, ""


def _shed(log, aggressive=False) -> None:
    """Free reclaimable Chromium.

    Inspection browsers are ALWAYS safe to close (they exist only for manual
    inspection). The warm Telegram pools are dropped only when ``aggressive``
    (CRITICAL) — an active cycle may still be driving one of those browsers, so
    closing them at the first sign of pressure would fail a live task.
    """
    try:
        from pipelines.telegram import tg_worker          # same module instance
        tg_worker.close_inspectors("memory pressure", log)
    except Exception:
        pass
    if aggressive:
        try:
            from tg_bot import PooledTelegramBot
            from mtproto_bot import MtprotoPooledBot
            PooledTelegramBot.drop_all()                   # warm TG Chromium trees
            MtprotoPooledBot.drop_all()                    # warm MTProto clients
        except Exception:
            pass


def watch(stop_event, log=print) -> None:
    """Daemon loop: shed at LOW, request graceful stop at MIN. Never raises."""
    if DISABLED:
        return
    state = "ok"
    while not stop_event.is_set():
        avail = available_mb()
        if avail is not None:
            try:
                if avail < MIN_FREE_MB:
                    log(f"[mem] CRITICAL — only {avail} MB free (< {MIN_FREE_MB}); "
                        f"shedding browsers and stopping gracefully before the OOM killer.")
                    _shed(log, aggressive=True)
                    stop_event.set()
                    return
                if avail < LOW_FREE_MB:
                    if state != "low":
                        log(f"[mem] LOW — {avail} MB free (< {LOW_FREE_MB}); "
                            f"shedding inspection/warm browsers.")
                        _shed(log)
                        state = "low"
                else:
                    state = "ok"
            except Exception:
                pass
        try:
            stop_event.wait(CHECK_SECS)
        except Exception:
            return


def start_watchdog(stop_event, log=print):
    """Start the watchdog thread (no-op when disabled). Returns the thread."""
    if DISABLED:
        return None
    t = threading.Thread(target=watch, args=(stop_event, log), name="mem-guard", daemon=True)
    t.start()
    return t
