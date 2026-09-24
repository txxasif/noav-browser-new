#!/usr/bin/env python3
"""virtual_display.py — isolate headed automation windows on a private X display.

WHY THIS EXISTS
---------------
On a Wayland desktop the engine forces ``--ozone-platform=x11`` on every headed
window (needed so ``--window-position`` tiling works; see
``engine/eng_mix_launch.py`` and ``warm_pool.py``). X11 / XWayland clients are
allowed to activate their own top-level window, and Chromium does exactly that
whenever:

  * the page's focused element changes — Playwright's ``click()`` / ``fill()`` /
    ``type()`` focus DOM inputs, so every automation action re-activates the
    window, and
  * a popup / tab / dialog opens (Instagram Accounts Center, reCAPTCHA
    extension, Telegram bot).

The result is that the OS focus (and therefore the user's keystrokes) jumps to
the automation window mid-typing. Wayland-native windows cannot do this — the
compositor alone owns focus — but forcing X11 reintroduces the problem.

Running the headed windows on a **dedicated X server** means no automation
window can steal focus from the user's real desktop.

BACKENDS
--------
  * ``xephyr`` (preferred when installed) — a *nested* X server shown as a single
    normal window on your real desktop. You can **watch and interact** with all
    automation windows inside it, and nested clients still cannot activate the
    host window, so your desktop focus is never stolen.
  * ``xvfb`` — a fully headless X server (no window at all). Use when no display
    is available (SSH/CI) or Xephyr is not installed. Watch via VNC.

  Select with ``AUTOMATION_DISPLAY_BACKEND=auto|xephyr|xvfb`` (default ``auto``:
  Xephyr if installed and a real display exists, otherwise Xvfb).

BEHAVIOUR
---------
  * Enabled by default for the engine process. Disable with ``AUTOMATION_XVFB=0``.
  * Display number comes from ``AUTOMATION_DISPLAY`` (default ``:99``).
  * Reuses an already-running display on that number, so the Telegram + Nitro
    engine processes (and dashboard-booted Genymotion VMs) share one display.
  * Best-effort: if no backend can start, the original ``DISPLAY`` is kept and a
    warning is printed — automation never breaks.

QUICK COMMANDS
--------------
    python virtual_display.py status                 # backend + liveness
    python virtual_display.py ensure                 # start it now
    python virtual_display.py watch                  # live view window (no install)
    python virtual_display.py peek [out.png]         # grab a frame (needs ffmpeg)
    python virtual_display.py stop                   # stop the private X server

    # Interactive view of a headless Xvfb display (any VNC client):
    sudo apt install x11vnc xserver-xephyr
    x11vnc -display :99 -localhost -nopw -forever    # then VNC to localhost:5900

ENV
---
    AUTOMATION_XVFB          "0" to disable isolation entirely (default: on)
    AUTOMATION_DISPLAY       X display number (default: ":99")
    AUTOMATION_DISPLAY_BACKEND  auto | xephyr | xvfb (default: auto)
    AUTOMATION_SCREEN        geometry (default: "1920x1080x24"; Xephyr uses WxH)
    AUTOMATION_REAL_DISPLAY  host display Xephyr embeds into (default: current DISPLAY)
    AUTOMATION_VNC           "1" to also spawn x11vnc on localhost (default: off)
    AUTOMATION_VNC_PORT      x11vnc port (default: 5900)
"""
from __future__ import annotations

import atexit
import os
import shutil
import stat
import subprocess
import sys
import threading
import time

_LOCK = threading.Lock()
_STARTED_BY_US: str | None = None
_BACKEND_IN_USE: str | None = None
_VNC_STARTED = False


def _enabled() -> bool:
    return os.environ.get("AUTOMATION_XVFB", "1").strip().lower() not in (
        "0", "false", "no", "off", "",
    )


def _display_number(display: str) -> str:
    """``:99`` / ``:99.0`` / ``localhost:99`` → ``99`` ("" if unparseable)."""
    d = (display or "").rsplit(":", 1)[-1].split(".", 1)[0]
    return d if d.isdigit() else ""


def _socket_path(number: str) -> str:
    return f"/tmp/.X11-unix/X{number}"


def _display_alive(display: str) -> bool:
    num = _display_number(display)
    if not num:
        return False
    try:
        return stat.S_ISSOCK(os.stat(_socket_path(num)).st_mode)
    except OSError:
        return False


def _which(name: str) -> str | None:
    return shutil.which(name)


def _target_display() -> str:
    return os.environ.get("AUTOMATION_DISPLAY", ":99")


def _real_display() -> str:
    """The user's actual desktop display (what Xephyr embeds into)."""
    explicit = os.environ.get("AUTOMATION_REAL_DISPLAY", "").strip()
    if explicit:
        return explicit
    current = (os.environ.get("DISPLAY") or "").strip()
    if current and _display_number(current) != _display_number(_target_display()):
        return current
    return ":0"


def _choose_backend() -> str:
    want = os.environ.get("AUTOMATION_DISPLAY_BACKEND", "auto").strip().lower()
    if want in ("xephyr", "xvfb"):
        return want
    # auto: prefer a visible nested server when we can actually show a window.
    if _which("Xephyr") and _display_alive(_real_display()):
        return "xephyr"
    return "xvfb"


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _spawn_vnc(display: str) -> None:
    global _VNC_STARTED
    if _VNC_STARTED:
        return
    if os.environ.get("AUTOMATION_VNC", "0").strip().lower() not in ("1", "true", "yes", "on"):
        return
    vnc = _which("x11vnc")
    if not vnc:
        _log("[🖥️] AUTOMATION_VNC=1 but x11vnc is not installed — "
             f"install it to watch {display} (sudo apt install x11vnc).")
        return
    port = os.environ.get("AUTOMATION_VNC_PORT", "5900")
    try:
        subprocess.Popen(
            [vnc, "-display", display, "-localhost", "-nopw", "-forever",
             "-quiet", "-rfbport", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _VNC_STARTED = True
        _log(f"[🖥️] Remote view ready → vnc://localhost:{port} (display {display})")
    except Exception as exc:  # noqa: BLE001 — never break automation
        _log(f"[🖥️] x11vnc failed to start ({exc}); windows still run on {display}.")


def _launch_xvfb(target: str, geom: str) -> subprocess.Popen:
    xvfb = _which("Xvfb") or "Xvfb"
    return subprocess.Popen(
        [xvfb, target, "-screen", "0", geom, "-nolisten", "tcp",
         "-ac", "+extension", "GLX", "+extension", "RANDR", "+render", "-noreset"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _geom_size(geom: str) -> str:
    parts = (geom or "1920x1080x24").split("x")
    return f"{parts[0]}x{parts[1]}" if len(parts) >= 2 else "1920x1080"


def _launch_xephyr(target: str, geom: str) -> subprocess.Popen:
    xephyr = _which("Xephyr") or "Xephyr"
    # Xephyr geometry is WxH (depth is inherited from the host display). Keep the
    # argument list to well-established options only so an unknown flag cannot
    # kill the nested server; embed it into the user's real display.
    env = dict(os.environ)
    env["DISPLAY"] = _real_display()
    return subprocess.Popen(
        [xephyr, target, "-screen", _geom_size(geom),
         "-title", "MetaAuto AI — automation (isolated)",
         "-ac", "-noreset"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=env, start_new_session=True,
    )


def ensure_virtual_display(display: str | None = None) -> str | None:
    """Route ``DISPLAY`` to a private X server so windows never steal desktop focus.

    Returns the display in use (e.g. ``":99"``) when isolation is active, or
    ``None`` when disabled / unavailable (the original ``DISPLAY`` is left
    untouched). Idempotent and safe to call from any thread.
    """
    global _STARTED_BY_US, _BACKEND_IN_USE

    if not _enabled():
        return None

    target = display or _target_display()
    if not _display_number(target):
        _log(f"[🖥️] AUTOMATION_DISPLAY {target!r} is not a valid X display — keeping {os.environ.get('DISPLAY')!r}.")
        return None

    with _LOCK:
        if _display_alive(target):  # started by us, a sibling, or the user
            _apply_display(target)
            return target

        geom = os.environ.get("AUTOMATION_SCREEN", "1920x1080x24")

        def _try(backend: str):
            if backend == "xephyr":
                if not _which("Xephyr"):
                    return None, None
                return _launch_xephyr(target, geom), (
                    "nested window on your desktop — watch & interact without stealing focus")
            if not _which("Xvfb"):
                return None, None
            return _launch_xvfb(target, geom), (
                "headless (install xserver-xephyr for a visible window, or "
                "AUTOMATION_VNC=1 with x11vnc)")

        # Try the preferred backend, then fall back to the other one.
        preferred = _choose_backend()
        order = [preferred] + [b for b in ("xephyr", "xvfb") if b != preferred]
        if not _which("Xephyr") and not _which("Xvfb"):
            _log("[🖥️] Neither Xephyr nor Xvfb is installed — headed windows stay on "
                 "the real desktop. Install: sudo apt install xvfb xserver-xephyr")
            return None

        for backend in order:
            try:
                proc, human = _try(backend)
            except Exception as exc:  # noqa: BLE001
                _log(f"[🖥️] {backend} failed to launch ({exc}); trying the other backend…")
                continue
            if proc is None:
                continue
            deadline = time.time() + 10.0
            while time.time() < deadline:
                if _display_alive(target):
                    _STARTED_BY_US = target
                    _BACKEND_IN_USE = backend
                    _apply_display(target)
                    _log(f"[🖥️] Automation display ready: {target} via {backend} — {human}.")
                    _spawn_vnc(target)
                    return target
                if proc.poll() is not None:
                    break
                time.sleep(0.25)
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            _log(f"[🖥️] {backend} did not come up on {target}; trying the other backend…")

        _log(f"[🖥️] No X backend could start on {target}; keeping "
             f"{os.environ.get('DISPLAY')!r} so automation still runs.")
        return None



def _apply_display(display: str) -> None:
    os.environ["DISPLAY"] = display
    if display == _target_display():
        os.environ.pop("XAUTHORITY", None)


def stop_virtual_display(display: str | None = None) -> bool:
    """Stop the private X server on ``display`` (default ``$AUTOMATION_DISPLAY/:99``)."""
    target = display or _target_display()
    if not _display_number(target):
        return False
    for pat in (f"Xvfb {target}", f"Xephyr {target}"):
        try:
            subprocess.run(["pkill", "-f", pat], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    for _ in range(20):
        if not _display_alive(target):
            return True
        time.sleep(0.1)
    return not _display_alive(target)


def peek(out_path: str = "/tmp/meta_auto_display.png") -> str | None:
    """Grab one frame from the private display (needs ffmpeg). Returns the path."""
    if not _which("ffmpeg"):
        _log("[🖥️] ffmpeg not found — cannot grab a frame.")
        return None
    target = _target_display()
    if not _display_alive(target):
        _log(f"[🖥️] Display {target} is not running; start it with `python virtual_display.py ensure`.")
        return None
    geom = os.environ.get("AUTOMATION_SCREEN", "1920x1080x24")
    size = geom.split("x", 2)[0] + "x" + geom.split("x", 2)[1] if geom.count("x") >= 1 else "1920x1080"
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "x11grab",
             "-video_size", size, "-i", target, "-frames:v", "1", "-y", out_path],
            check=True, timeout=30,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"[🖥️] ffmpeg grab failed: {exc}")
        return None
    _log(f"[🖥️] Frame saved: {out_path}")
    return out_path


def watch(timeout: int | None = None) -> int:
    """Open a live view of the private display in a window on the real desktop.

    Uses ffmpeg's ``xv`` output (view-only, no input forwarding). Runs until the
    window is closed (or ``timeout`` seconds). Zero extra install required.
    """
    if not _which("ffmpeg"):
        _log("[🖥️] ffmpeg not found — cannot open a live view.")
        return 1
    target = _target_display()
    if not _display_alive(target):
        _log(f"[🖥️] Display {target} is not running; start it with `python virtual_display.py ensure`.")
        return 1
    size = _geom_size(os.environ.get("AUTOMATION_SCREEN", "1920x1080x24"))
    env = dict(os.environ)
    env["DISPLAY"] = _real_display()
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
           "-f", "x11grab", "-video_size", size, "-i", target,
           "-pix_fmt", "yuv420p",
           "-f", "xv", "MetaAuto AI — automation (live)"]
    if timeout:
        cmd = cmd[:1] + ["-t", str(timeout)] + cmd[1:]
    _log(f"[🖥️] Opening live view of {target} (close the window to stop)…")
    try:
        return subprocess.run(cmd, env=env).returncode
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001
        _log(f"[🖥️] Live view failed: {exc}")
        return 1


def status() -> dict:
    target = _target_display()
    return {
        "enabled": _enabled(),
        "target_display": target,
        "backend_preference": os.environ.get("AUTOMATION_DISPLAY_BACKEND", "auto"),
        "backend_in_use": _BACKEND_IN_USE,
        "xvfb_installed": bool(_which("Xvfb")),
        "xephyr_installed": bool(_which("Xephyr")),
        "x11vnc_installed": bool(_which("x11vnc")),
        "ffmpeg_installed": bool(_which("ffmpeg")),
        "running": _display_alive(target),
        "real_display": _real_display(),
        "current_display": os.environ.get("DISPLAY"),
    }


def _main(argv: list[str]) -> int:
    if not argv or argv[0] == "status":
        import json
        print(json.dumps(status(), indent=2))
        return 0
    if argv[0] == "ensure":
        d = ensure_virtual_display()
        print(d if d else f"(disabled/unavailable; DISPLAY={os.environ.get('DISPLAY')})")
        return 0 if d else 1
    if argv[0] == "peek":
        return 0 if peek(argv[1] if len(argv) > 1 else "/tmp/meta_auto_display.png") else 1
    if argv[0] == "watch":
        t = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else None
        return watch(t)
    if argv[0] == "stop":
        ok = stop_virtual_display(argv[1] if len(argv) > 1 else None)
        print("stopped" if ok else "not running / failed to stop")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
