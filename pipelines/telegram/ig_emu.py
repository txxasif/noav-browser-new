"""pipelines/telegram/ig_emu.py — Genymotion emulator IG phase (TG-Emu route).

TG-Emu flow: Meta (browser) -> TG task creds -> **IG join + 2FA + password +
email inside a leased Genymotion device** -> TG submit (mark_registered).

Why this file exists: the browser IG surface is dying (96% phone-wall rate
+ AC unreachable/blank/password failures — all web-surface failures). The
native Instagram app surface has no phone wall, and in-app taps cannot
"render blank" or miss a URL-registry entry.

HARD RULES (mirror the fleet invariants):
  * Devices are leased 1:1 — two slots NEVER share one screen. Leases live
    in ``data/emu_leases.json`` (crash-safe: clean-on-ACQUIRE, never on
    release, so a crashed holder cannot poison the next one).
  * Hygiene is DATA-ONLY: ``pm clear com.instagram.android`` + a fresh
    ``android_id`` (~2s). Never reinstall per account; never touch the
    Nitro/Coinsta device pools (their ``pm clear`` ban is scoped to
    coinsta.app / Nitro devices — this fleet is disjoint).
  * Every step raises on failure — NEVER fake success. Success is only
    reported on positive on-screen confirmation.
  * OTP codes come from stored mail.td tokens via direct REST (LIST +
    DETAIL, invariant #16) or the REST mail providers — the Meta browser is
    already closed by then, so no live-page fetch is possible.

PILOT: the native-app screen texts below are best-effort matchers modelled
on the proven Coinsta WebView flow. The pilot capture run calibrates exact
labels/coordinates; every matcher miss is logged with the raw OCR dump.
"""

from __future__ import annotations

import json
import os
import random
import re
import secrets
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT_DIR, "data")
LEASE_PATH = os.path.join(DATA_DIR, "emu_leases.json")

IG_PACKAGE = "com.instagram.android"
# Ceiling: 3 configured VMs on this host; duty-cycle math says ~2 suffice.
EMU_MAX_DEVICES = 3
# Display size the OCR/coordinate sets are calibrated against (same as Coinsta).
EMU_DISPLAY = (570, 1164)


class EmuError(RuntimeError):
    """Any emulator-phase failure (strict: aborts the task, never submits)."""


class EmuDeadEnd(RuntimeError):
    """Dead IG session inside the emulator (mirrors IGDeadEnd semantics:
    unusable account — close out, move to the next one, never submit)."""


class EmuUsernameTaken(RuntimeError):
    """The TG bot login is taken in-app — caller swaps via a fresh TG task
    and retries the username step (same hook as the browser flow)."""

    def __init__(self, bad_login: str):
        super().__init__(f"username taken in-app: {bad_login}")
        self.bad_login = bad_login


# ============================================================================
# Device leases (crash-safe, file-backed, thread-safe)
# ============================================================================
_LEASE_LOCK = threading.Lock()


def _read_leases() -> Dict[str, Any]:
    try:
        with open(LEASE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_leases(leases: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = LEASE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(leases, fh, indent=2)
    os.replace(tmp, LEASE_PATH)


def get_emu_backend() -> str:
    """Return active backend: 'redroid' (Docker) or 'genymotion' (VM)."""
    val = (os.environ.get("EMU_BACKEND") or "").strip().lower()
    if val in ("redroid", "docker"):
        return "redroid"
    if val in ("genymotion", "gmtool", "vms"):
        return "genymotion"
    # Auto-detect: if Docker is available and redroid module/manager works, use redroid
    try:
        from nitro.redroid_manager import is_docker_available
        if is_docker_available():
            return "redroid"
    except Exception:
        pass
    return "genymotion"


def _configured_vms() -> List[Dict[str, Any]]:
    backend = get_emu_backend()
    if backend == "redroid":
        try:
            from nitro.redroid_manager import get_configured_containers
            return get_configured_containers(max_count=EMU_MAX_DEVICES)
        except Exception:
            return []
    try:
        from nitro.vms import get_configured_vms
        return get_configured_vms() or []
    except Exception:
        return []


def _configured_vm_names() -> List[str]:
    return [str(v.get("name")) for v in _configured_vms() if v.get("name")]


def _vm_record(name: str) -> Dict[str, Any]:
    for v in _configured_vms():
        if str(v.get("name")) == name:
            return v
    return {}


def _vm_state(name: str) -> str:
    return str(_vm_record(name).get("state", "")).lower()


def _live_serials() -> List[str]:
    """Serials actually connected right now (ground truth when VMs are ON)."""
    try:
        from nitro.adb import adb_cmd
        code, out, _ = adb_cmd(["devices"], timeout=10)
        if code != 0:
            return []
        serials = []
        for line in (out or "").splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials
    except Exception:
        return []


def _device_serial(name: str) -> Optional[str]:
    """ADB serial for a VM or ReDroid container name."""
    rec = _vm_record(name)
    rec_serial = str(rec.get("adb_serial") or "")
    if rec.get("backend") == "redroid" or name.startswith("tgemu_redroid_"):
        return rec_serial or None

    live = _live_serials()
    if _vm_state(name) == "on":
        if rec_serial and rec_serial in live:
            return rec_serial
        if len(live) == 1:
            return live[0]
        return rec_serial or None
    return rec_serial or (live[0] if live else None)


def acquire_emu_device(slot_id: int, max_devices: int = EMU_MAX_DEVICES,
                       boot_timeout: int = 150,
                       stop_event=None,
                       log: Callable[[str], None] = print) -> Dict[str, str]:
    """Lease one Genymotion VM for this slot (blocks until one is free).

    Boot-on-demand: an already-ON, unleased VM wins; otherwise the first OFF
    VM is started via ``start_vm(wait_for_boot=True)``. The VM stays warm
    across accounts — boot cost amortizes, never pay it per account.
    """
    max_devices = max(1, min(int(max_devices or 1), EMU_MAX_DEVICES))
    deadline = time.time() + max(60, boot_timeout + 600)
    claimed: Optional[str] = None
    while True:
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            raise EmuError("stopped while waiting for an emulator device")
        with _LEASE_LOCK:
            leases = _read_leases()
            names = _configured_vm_names()[:max_devices]
            if not names:
                backend = get_emu_backend()
                raise EmuError(f"no {backend} emulator instances configured")
            # Prefer an ON + unleased VM (zero boot wait).
            ordered = sorted(names, key=lambda n: (0 if _vm_state(n) == "on" else 1))
            for name in ordered:
                holder = (leases.get(name) or {}).get("slot")
                if holder is None:
                    leases[name] = {"slot": slot_id, "since": time.time()}
                    _write_leases(leases)
                    claimed = name
                    break
        if claimed:
            break
        time.sleep(5)
        if time.time() > deadline:
            raise EmuError("timed out waiting for a free emulator device")
    # Boot outside the lock (slow) — then verify the lease is still ours.
    try:
        if _vm_state(claimed) != "on":
            log(f"[emu] Booting {claimed} on demand…")
            r = boot_vm_by_name(claimed, timeout=boot_timeout)
            log(f"[emu] boot: {r.get('message') or r.get('error') or 'ok'}")
            if not r.get("ok"):
                raise EmuError(f"Device boot failed: {r.get('error') or r.get('message')}")
        serial = _device_serial(claimed)
        if not serial:
            raise EmuError(f"no ADB serial for {claimed} after boot")
        log(f"[emu] Leased {claimed} ({serial}) for slot {slot_id}.")
        return {"vm": claimed, "serial": serial}
    except Exception:
        with _LEASE_LOCK:
            leases = _read_leases()
            if (leases.get(claimed) or {}).get("slot") == slot_id:
                leases.pop(claimed, None)
                _write_leases(leases)
        raise


def release_emu_device(vm: str, slot_id: int) -> None:
    """Release the lease. The VM stays ON (warm for the next account)."""
    with _LEASE_LOCK:
        leases = _read_leases()
        if (leases.get(vm) or {}).get("slot") == slot_id:
            leases.pop(vm, None)
            _write_leases(leases)


def fleet_status() -> Dict[str, Any]:
    """Configured VMs/containers + live state + lease holders (dashboard fleet panel)."""
    backend = get_emu_backend()
    leases = _read_leases()
    live = _live_serials()
    devices: List[Dict[str, Any]] = []
    for v in _configured_vms():
        name = str(v.get("name") or "")
        if not name:
            continue
        rec = leases.get(name) or {}
        state = str(v.get("state", "")).lower()
        serial = str(v.get("adb_serial") or "") or None
        if state == "on" and ((serial and serial not in live) or not serial) and len(live) == 1:
            serial = live[0]
        devices.append({
            "vm": name,
            "backend": v.get("backend") or backend,
            "state": state or "unknown",
            "serial": serial,
            "leased_by": rec.get("slot"),
            "since": rec.get("since"),
            "ig_installed": _ig_installed(serial) if serial and state == "on" else False,
        })
    return {
        "ok": True,
        "backend": backend,
        "devices": devices,
        "leased": sum(1 for d in devices if d["leased_by"] is not None),
    }


def stop_vm_by_name(vm: str) -> Dict[str, Any]:
    backend = get_emu_backend()
    rec = _vm_record(vm)
    if rec.get("backend") == "redroid" or vm.startswith("tgemu_redroid_") or backend == "redroid":
        try:
            from nitro.redroid_manager import stop_container
            ok, msg = stop_container(vm)
            return {"ok": bool(ok), "vm": vm, "message": msg}
        except Exception as exc:
            return {"ok": False, "vm": vm, "error": str(exc)}
    try:
        from nitro.vms import stop_vm
        ok, msg = stop_vm(vm)
        return {"ok": bool(ok), "vm": vm, "message": msg}
    except Exception as exc:
        return {"ok": False, "vm": vm, "error": str(exc)}


def boot_vm_by_name(vm: str, timeout: int = 150) -> Dict[str, Any]:
    backend = get_emu_backend()
    rec = _vm_record(vm)
    if rec.get("backend") == "redroid" or vm.startswith("tgemu_redroid_") or backend == "redroid":
        try:
            from nitro.redroid_manager import start_container
            ok, msg = start_container(vm, wait_for_boot=True, timeout=timeout)
            return {"ok": bool(ok), "vm": vm, "message": msg}
        except Exception as exc:
            return {"ok": False, "vm": vm, "error": str(exc)}
    try:
        from nitro.vms import start_vm
        ok, msg = start_vm(vm, wait_for_boot=True, timeout=timeout)
        return {"ok": bool(ok), "vm": vm, "message": msg}
    except Exception as exc:
        return {"ok": False, "vm": vm, "error": str(exc)}


# ============================================================================
# Hygiene — data-only clean on ACQUIRE (~2s, never per-release)
# ============================================================================
def _adb_shell(serial: str, cmd: str, timeout: int = 20) -> Tuple[int, str, str]:
    from nitro.adb import adb_shell
    return adb_shell(cmd, serial=serial, timeout=timeout)


def clean_emu_device(serial: str, proxy: Optional[str] = None,
                     log: Callable[[str], None] = print) -> None:
    """Fresh identity for ONE account: wipe IG app state + rotate android_id.

    ``pm clear`` here is scoped to com.instagram.android on the TG-Emu fleet
    ONLY — it never touches coinsta.app / Nitro devices (their ban stands).
    """
    code, _, err = _adb_shell(serial, f"pm clear {IG_PACKAGE}", timeout=30)
    if code != 0:
        # Not fatal by itself (fresh VM = nothing to clear) — but log it.
        log(f"[emu] pm clear note: {err or code}")
    else:
        log("[emu] App state wiped (pm clear com.instagram.android).")
    new_id = secrets.token_hex(8)  # 16 hex chars, android_id format
    _adb_shell(serial, f"settings put secure android_id {new_id}", timeout=10)
    log("[emu] android_id rotated.")
    if proxy:
        # Best-effort: not all app traffic honours the global proxy —
        # PILOT verifies IG actually exits via it.
        _adb_shell(serial, f"settings put global http_proxy {proxy}", timeout=10)
        log(f"[emu] Proxy applied (best-effort, pilot-verified): {proxy}")
    else:
        log("[emu] No proxy bound to this lease — same-IP linkage risk. "
            "Bind per-account proxies to remove it.")


# ============================================================================
# Instagram APK preflight (ARM-only APK on x86_64 VMs)
# ============================================================================
def _ig_installed(serial: Optional[str]) -> bool:
    if not serial:
        return False
    try:
        code, out, _ = _adb_shell(serial, f"pm path {IG_PACKAGE}", timeout=10)
        return code == 0 and "package:" in (out or "")
    except Exception:
        return False


def ensure_instagram(serial: str, apk_path: Optional[str] = None,
                     log: Callable[[str], None] = print) -> None:
    """Fail loud with the pilot gate when the APK cannot be installed."""
    if _ig_installed(serial):
        log("[emu] Instagram app present.")
        return
    apk = (apk_path or os.environ.get("EMU_IG_APK") or "").strip()
    if not apk or not os.path.exists(apk):
        raise EmuError(
            "Instagram app not installed on the emulator and no APK supplied "
            "(set Emu APK path on the TG-Emu tab or EMU_IG_APK) — "
            "install once per VM: adb -s <serial> install instagram.apk")
    log(f"[emu] Installing Instagram APK ({os.path.basename(apk)})…")
    from nitro.adb import adb_cmd
    code, out, err = adb_cmd(["-s", serial, "install", "-r", apk], timeout=180)
    blob = f"{out}\n{err}"
    if code == 0 and "Success" in blob:
        log("[emu] Instagram APK installed.")
        return
    if "NO_MATCHING_ABIS" in blob:
        raise EmuError(
            "INSTALL_FAILED_NO_MATCHING_ABIS for the Instagram APK. NOTE: the "
            "stock redroid/redroid image DOES translate ARM (verified 2026-09-26: "
            "ro.dalvik.vm.native.bridge=libnb.so, ro.enable.native.bridge.exec=1, "
            "/system/lib64/libndk_translation.so present — the armeabi-v7a IG "
            "429.1.0.44.70 APK installs AND runs). If you hit this, first check "
            "the image really has ndk_translation and that the APK is not an "
            "arm64-only/odd split; only then consider an ARM-translation image "
            "or the AVD route.")
    raise EmuError(f"Instagram APK install failed: {(out or err or code)}"[:300])


# ============================================================================
# OCR / tap primitives (same pattern as coinsta_manager — proven)
# ============================================================================
_OCR_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def _invalidate_ocr(serial: str) -> None:
    _OCR_CACHE.pop(serial, None)


def _ocr(serial: str) -> List[Dict[str, Any]]:
    """Screen OCR, briefly cached per serial.

    The join loop called _text_low() (a full screencap + RapidOCR pass) and
    then _ocr() again inside the same branch — two scrapes per iteration, over
    a 70-iteration loop. Measured 2026-09-26: 11m48s just to reach the join
    card, against a 420s Taskly TTL, so the slice could not possibly fit.
    1.2s is far shorter than any tap+sleep, so a cached frame can never be
    served across an interaction.
    """
    hit = _OCR_CACHE.get(serial)
    now = time.time()
    if hit and (now - hit[0]) < 1.2:
        return hit[1]
    try:
        from nitro.ocr import inspect_screen_ocr
        toks = inspect_screen_ocr(serial) or []
    except Exception:
        toks = []
    _OCR_CACHE[serial] = (now, toks)
    return toks


def _find_account_card(serial: str) -> Optional[Tuple[int, int]]:
    """Locate the matched-Meta-account card on the 'No Instagram profile' sheet.

    The sheet has two paths: the blue "Find another account" button (which
    DISCARDS the matched account) and, below the OR divider, the matched
    account card (Meta logo + email + name + chevron) — only the card joins.
    The card is identified by its email label. None is a normal return: the
    sheet animates in and the card often renders below the fold on pass one.
    """
    for it in _ocr(serial):
        t = str(it.get("text", "")).strip().lower()
        if "@" in t and " " not in t and "." in t.split("@", 1)[-1]:
            try:
                return (int(it["x"]), int(it["y"]))
            except Exception:
                continue
    return None


def _text_low(serial: str) -> str:
    return " ".join(str(it.get("text", "")) for it in _ocr(serial)).lower()


def _tap(serial: str, x: int, y: int) -> None:
    _adb_shell(serial, f"input tap {int(x)} {int(y)}", timeout=10)


def _key(serial: str, code: int) -> None:
    _adb_shell(serial, f"input keyevent {int(code)}", timeout=10)


def _tap_text(serial: str, queries: List[str]) -> bool:
    try:
        from nitro.ocr import find_text_coord
        c = find_text_coord(_ocr(serial), queries)
    except Exception:
        c = None
    if c:
        _tap(serial, c[0], c[1])
        return True
    return False


def _fill(serial: str, placeholder: str, value: str,
          verify_fragment: Optional[str] = None) -> None:
    """Tap field -> caret to END -> clear -> type -> dismiss keyboard."""
    try:
        from nitro.ocr import find_text_coord
        c = find_text_coord(_ocr(serial), [placeholder])
    except Exception:
        c = None
    _tap(serial, *(c or (285, 400)))
    time.sleep(0.7)
    _adb_shell(serial, "input keyevent 123", timeout=10)  # MOVE_END
    time.sleep(0.15)
    _adb_shell(serial, "for i in $(seq 1 5); do input keyevent 67; done", timeout=15)
    _adb_shell(serial, "input keyevent 113", timeout=10)  # DEL x1 safety
    safe = str(value or "").replace(" ", "%s").replace("'", "")
    _adb_shell(serial, f"input text '{safe}'", timeout=30)
    time.sleep(1.0)
    _key(serial, 111)  # ESC — dismiss keyboard
    time.sleep(0.4)
    if verify_fragment:
        low = _norm(_text_low(serial))
        want = _norm(verify_fragment)
        if want and want not in low:
            # OCR cannot read emoji, fullwidth or astral-plane glyphs, so a
            # fragment like 'Ｈɨท' (from Taskly name '⛓ 💯Ｈɨท𝗱ú⛓') is
            # unverifiable BY CONSTRUCTION — observed 2026-09-26 hard-failing
            # here moments after the tap had landed correctly, killing a
            # finished account. Compare only the ASCII-comparable part, and
            # when nothing ASCII remains, warn rather than raise.
            ascii_want = "".join(c for c in want if c.isascii() and c.isalnum())
            if ascii_want:
                if ascii_want not in low:
                    raise EmuError(f"typed value did not land (field '{placeholder}')")
            else:
                print(f"[emu] note: field '{placeholder}' verification skipped "
                      f"(value {value!r} is non-ASCII, unreadable by OCR)")


def _norm(s: str) -> str:
    """OCR-tolerant fold (0/o, 1/l, 5/s, 8/b, 2/z) — same as coinsta."""
    out = []
    for ch in str(s or "").lower():
        if ch in "0o":
            out.append("o")
        elif ch in "1l":
            out.append("l")
        elif ch in "5s":
            out.append("s")
        elif ch in "8b":
            out.append("b")
        elif ch in "2z":
            out.append("z")
        elif ch.isalnum():
            out.append(ch)
    return "".join(out)


def _launch_ig(serial: str, log: Callable[[str], None]) -> None:
    """Bring the IG UI to the foreground, or the join loop OCRs the launcher.

    The LAUNCHER intent filter resolves to ``.activity.MainTabActivity`` (NOT
    ``mainactivity.MainActivity``, which does not exist). ``monkey -c LAUNCHER 1``
    looks like it works and does not: it only starts the push service
    (InappFbnsService), leaves the launcher resumed, and exits 0 — so the caller
    saw a live ``com.instagram.android`` process at ~300 MB and OCR'd the home
    screen. Launch the activity directly and require ``Status: ok``.
    """
    _adb_shell(serial, "settings put secure show_ime_with_hard_keyboard 0", timeout=10)
    _adb_shell(serial, f"am force-stop {IG_PACKAGE}", timeout=20)
    code, out, err = _adb_shell(
        serial, f"am start -W -n {IG_PACKAGE}/.activity.MainTabActivity", timeout=90)
    blob = f"{out or ''} {err or ''}"
    if "Status: ok" not in blob:
        log(f"[emu] WARN IG launch did not report ok: {blob.strip()[:200]}")
    time.sleep(3.0)


def _on_home(serial: str) -> bool:
    """Home tab bar visible = logged-in IG (PILOT-calibrated fragments)."""
    low = _text_low(serial)
    hits = sum(1 for t in ("home", "search", "reels") if t in low)
    return hits >= 2


def _dump(serial: str) -> str:
    return " | ".join(str(it.get("text", "")) for it in _ocr(serial))[:600]


# ============================================================================
# Step 1 — join Instagram with the Meta account (in-app)
# ============================================================================
def emu_join_instagram(serial: str, email: str, password: str,
                       display_name: str, username: str,
                       log: Callable[[str], None] = print) -> str:
    """Log in with Meta creds -> join IG -> name/username/consent.

    Returns the final IG handle. Raises EmuUsernameTaken (caller swaps via a
    fresh TG task and retries), EmuDeadEnd (dead session), or EmuError.
    """
    _launch_ig(serial, log)
    tried_login = False
    for step in range(70):
        low = _text_low(serial)
        if _on_home(serial):
            handle = _capture_handle(serial) or username
            log(f"[emu] IG join complete — home reached (@{handle}).")
            return handle
        # Dead session inside the app (mirrors IGDeadEnd — never submit).
        if "something went wrong" in low and "try again" in low and step > 10:
            raise EmuDeadEnd(f"IG app dead session during join: {_dump(serial)}")
        # Welcome -> Log in (NOT sign up).
        if (("log in" in low and "sign up" in low) and "password" not in low
                and "username" not in low):
            if not (_tap_text(serial, ["log in"]) or True):
                pass
            time.sleep(3.0)
            continue
        # Login form.
        if (("username" in low or "email" in low) and "password" in low
                and ("forgot" in low or "log in" in low) and not tried_login):
            _fill(serial, "Username", email, email.split("@")[0][:6])
            _fill(serial, "Password", password, None)
            _tap_text(serial, ["log in"]) or _tap(serial, 285, 714)
            tried_login = True
            log("[emu] Submitted Meta credentials on the IG Log in form.")
            time.sleep(4.0)
            continue
        # Phone wall INSIDE the app (unexpected — fail loud, do not retry).
        if "what's your mobile number" in low or "mobile number required" in low:
            raise EmuError("IG app hit the phone wall — join impossible on this build")
        # Real IG welcome screen (verified live 2026-09-26 on redroid, IG
        # 429.1.0.44.70): heading "Join Instagram" + buttons "Get started"
        # (signup) and "I already have a profile" (login). The branch above
        # only matches Coinsta's "Log in or sign up" wording, so on the real
        # screen it never fires — control falls through to join-from-Meta,
        # which sees "join instagram" in the heading, finds no @handle, and
        # taps the *heading* (not a button) for 70 steps. Must be tested
        # BEFORE that branch because the heading contains "join instagram".
        if "i already have a profile" in low:
            log("[emu] IG welcome -> 'I already have a profile' (login path).")
            _tap_text(serial, ["i already have a profile"])
            time.sleep(5.0)
            continue
        if "get started" in low and "already have a profile" not in low:
            log("[emu] IG welcome -> 'Get started'.")
            _tap_text(serial, ["get started"])
            time.sleep(5.0)
            continue
        # Join-from-Meta offer ("No Instagram profile found" or equivalent).
        if ("no instagram profile" in low or "create instagram" in low
                or "join instagram" in low):
            card = _find_account_card(serial)
            if not card:
                # The card renders below the fold as the sheet animates in.
                _adb_shell(serial, "input swipe 285 800 285 520 300", timeout=10)
                time.sleep(1.5)
                _invalidate_ocr(serial)
                card = _find_account_card(serial)
            if card:
                _tap(serial, card[0], card[1])
                log(f"[emu] Joining Instagram with the Meta account (card @ {card}).")
                time.sleep(5.0)
                continue
            # NEVER tap "Find another account" — it throws away the Meta
            # account we just matched. Wait for the card instead.
            log("[emu] Join sheet: account card not visible yet (NOT tapping "
                "'Find another account' — it discards the matched account).")
            time.sleep(3.0)
            continue
        # Name step.
        if ("what's your name" in low or "add your name" in low) and "password" not in low:
            _fill(serial, "Full name", display_name, display_name.split()[0][:4])
            _tap_text(serial, ["next", "continue"]) or _tap(serial, 285, 445)
            time.sleep(3.0)
            continue
        # Username step (bot login injected).
        if (("create a username" in low or "choose username" in low
             or ("username" in low and "password" not in low and "name" not in low))
                and not _on_home(serial)):
            low_n = _norm(low)
            if ("not available" in low or "isn't available" in low
                    or "username" in low and "taken" in low_n):
                raise EmuUsernameTaken(username)
            _fill(serial, "Username", username, username[:4])
            _tap_text(serial, ["next", "continue"]) or _tap(serial, 285, 445)
            time.sleep(3.0)
            # Re-check taken AFTER submit (the verdict screen follows the tap).
            time.sleep(1.5)
            low2 = _norm(_text_low(serial))
            if "notavailable" in low2 or "taken" in low2:
                raise EmuUsernameTaken(username)
            continue
        # Birthday (native picker — PILOT: exact labels pending).
        if "birthday" in low or "date of birth" in low:
            _tap_text(serial, ["next", "set", "done", "continue"])
            time.sleep(3.0)
            continue
        # Meta consent -> Allow (bottom strip may cover it; edges first).
        if ("allow the following" in low or "what this means" in low
                or "to create an instagram account" in low):
            for _ in range(6):
                _adb_shell(serial, "input swipe 285 900 285 250 250", timeout=10)
                time.sleep(0.6)
            for pt in ((60, 1036), (520, 1036), (285, 1000)):
                _tap(serial, *pt)
                time.sleep(2.0)
                if "agree" in _text_low(serial) or _on_home(serial):
                    break
            log("[emu] Meta consent allowed.")
            continue
        if "agree to instagram" in low or ("i agree" in low and not _on_home(serial)):
            _tap_text(serial, ["i agree"]) or _tap(serial, 285, 675)
            log("[emu] Agreed to Instagram terms.")
            time.sleep(4.0)
            continue
        # Dismiss-only prompts (never destructive).
        if "save your login info" in low or "save login info" in low:
            _tap_text(serial, ["not now", "save"]) or _tap(serial, 285, 600)
            time.sleep(2.0)
            continue
        if "turn on notifications" in low or "allow notifications" in low:
            _tap_text(serial, ["not now", "skip"]) or _tap(serial, 285, 600)
            time.sleep(2.0)
            continue
        if "add profile photo" in low or "add a photo" in low:
            _tap_text(serial, ["skip"]) or _key(serial, 4)
            time.sleep(2.0)
            continue
        if "discover people" in low or "find friends" in low or "contacts" in low:
            _tap_text(serial, ["skip", "next", "not now"]) or _tap(serial, 285, 600)
            time.sleep(2.0)
            continue
        time.sleep(2.0)
    raise EmuError(f"IG join timed out. Last screen: {_dump(serial)}")


def _capture_handle(serial: str) -> Optional[str]:
    """Best-effort @handle from the profile header (PILOT-calibrated)."""
    for it in _ocr(serial):
        t = str(it.get("text", "")).strip()
        y = int(it.get("y", 0) or 0)
        if 200 <= y <= 300 and re.fullmatch(r"@?[A-Za-z0-9._]{3,30}", t or ""):
            return t.lstrip("@")
    return None


# ============================================================================
# Step 2 — 2FA setup in-app (key via OCR; app validates the TOTP itself)
# ============================================================================
def _open_accounts_center(serial: str, log: Callable[[str], None]) -> None:
    """Profile -> menu -> Settings and privacy -> Accounts Center (PILOT)."""
    for _ in range(3):
        if "accounts center" in _text_low(serial):
            return
        low = _text_low(serial)
        if _on_home(serial):
            # Profile tab is the last tab (right edge).
            _tap(serial, 520, 1100)
            time.sleep(2.0)
        elif "profile" in low or "edit profile" in low:
            _tap(serial, 520, 120)  # hamburger (top-right, PILOT)
            time.sleep(2.0)
        elif "settings" in low or "menu" in low:
            if not _tap_text(serial, ["settings and privacy", "settings"]):
                _tap(serial, 285, 500)
            time.sleep(2.5)
        else:
            _tap_text(serial, ["accounts center"]) or _key(serial, 4)
            time.sleep(2.0)
    if "accounts center" not in _text_low(serial):
        raise EmuError(f"Accounts Center unreachable in-app: {_dump(serial)}")


def emu_setup_2fa(serial: str, fetch_otp: Callable[..., Optional[str]],
                  log: Callable[[str], None] = print) -> str:
    """Drive to Authentication-app setup; return the scraped setup key.

    The 2FA-enroll email OTP ("Check your email", 8-digit) is solved via
    fetch_otp (stored tokens, browser-free). The returned key is validated
    by the app itself when the TOTP is entered (self-correcting OCR).
    """
    _open_accounts_center(serial, log)
    for step in range(40):
        low = _text_low(serial)
        if "authentication app" in low and ("key" in low or "copy" in low or "setup" in low):
            key = _scrape_2fa_key(serial)
            if key:
                log("[emu] 2FA setup key scraped in-app.")
                return key
        if "two-factor" in low or "two factor" in low:
            if "get started" in low or "turn on" in low:
                _tap_text(serial, ["get started", "turn on"]) or _tap(serial, 285, 500)
                time.sleep(3.0)
                continue
            if not _tap_text(serial, ["authentication app", "authenticator", "setup"]):
                _tap(serial, 285, 500)
            time.sleep(3.0)
            continue
        if "check your email" in low or "enter the code" in low:
            log("[emu] 2FA enroll email challenge — fetching 8-digit code…")
            code = fetch_otp(keyword="authenticate", timeout=180, prefer_len=8)
            if not code:
                raise EmuError("2FA enroll email OTP not received")
            _fill(serial, "code", code, None)
            _tap_text(serial, ["next", "continue", "confirm", "verify"]) or _key(serial, 66)
            time.sleep(3.0)
            continue
        if "password and security" in low or "login and security" in low or "accounts center" in low:
            if not _tap_text(serial, ["two-factor authentication", "two factor"]):
                _tap(serial, 285, 500)
            time.sleep(2.5)
            continue
        if _on_home(serial):
            _open_accounts_center(serial, log)
            continue
        time.sleep(2.0)
    raise EmuError(f"2FA setup key not reached. Last screen: {_dump(serial)}")


def _scrape_2fa_key(serial: str) -> Optional[str]:
    """Longest base32-ish token on screen (spaces stripped). PILOT-tuned."""
    best = None
    for it in _ocr(serial):
        raw = re.sub(r"\s+", "", str(it.get("text", "")).upper())
        for m in re.findall(r"[A-Z2-7]{16,64}", raw):
            if best is None or len(m) > len(best):
                best = m
    return best


def emu_confirm_2fa(serial: str, code: str,
                    log: Callable[[str], None] = print) -> bool:
    """Enter the TOTP on the in-app code screen. App verdict = truth."""
    for _ in range(3):
        low = _text_low(serial)
        if "set up" in low and ("complete" in low or "success" in low or "on" in low):
            return True
        _fill(serial, "code", code, None)
        _tap_text(serial, ["next", "continue", "confirm", "verify", "done"]) or _key(serial, 66)
        time.sleep(4.0)
        low = _text_low(serial)
        if "incorrect" in low or "wrong" in low or "try again" in low:
            log("[emu] App rejected the TOTP (OCR key misread?) — caller re-scrapes.")
            return False
        if "set up" in low or "two-factor is on" in low or "backup" in low:
            log("[emu] 2FA confirmed in-app.")
            return True
    return "backup" in _text_low(serial) or "is on" in _text_low(serial)


# ============================================================================
# Step 3 — password change (2FA already ON -> direct form, no re-auth)
# ============================================================================
def emu_change_password(serial: str, current_pw: str, new_pw: str,
                        fetch_otp: Callable[..., Optional[str]],
                        log: Callable[[str], None] = print) -> bool:
    _open_accounts_center(serial, log)
    if not _tap_text(serial, ["password and security", "login and security"]):
        raise EmuError("Login-and-security section unreachable in-app")
    time.sleep(2.0)
    if not _tap_text(serial, ["change password"]):
        raise EmuError("Change-password row unreachable in-app")
    time.sleep(2.5)
    _fill(serial, "Current", current_pw, None)
    _fill(serial, "New password", new_pw, None)
    _fill(serial, "Re-type", new_pw, None)
    _tap_text(serial, ["change password", "save", "update", "done"]) or _key(serial, 66)
    time.sleep(4.0)
    low = _text_low(serial)
    if "updated" in low or "changed" in low or "success" in low:
        log("[emu] Password changed in-app.")
        return True
    if "check your email" in low or "enter the code" in low:
        log("[emu] Password email challenge — fetching code…")
        code = fetch_otp(keyword="password", timeout=180, prefer_len=6)
        if code:
            _fill(serial, "code", code, None)
            _tap_text(serial, ["next", "continue", "confirm"]) or _key(serial, 66)
            time.sleep(4.0)
            low = _text_low(serial)
            if "updated" in low or "changed" in low:
                log("[emu] Password changed in-app (after email challenge).")
                return True
    raise EmuError(f"Password change unconfirmed. Last screen: {_dump(serial)}")


# ============================================================================
# Step 4 — add + confirm email (code via stored tokens, browser-free)
# ============================================================================
def emu_add_email(serial: str, email: str,
                  fetch_otp: Callable[..., Optional[str]],
                  log: Callable[[str], None] = print) -> bool:
    _open_accounts_center(serial, log)
    for step in range(30):
        low = _text_low(serial)
        # Trust the app's own success toast/list (never the default-email page).
        if "email added" in low:
            log("[emu] 'Email added' confirmed in-app.")
            return True
        if email.split("@")[0][:10].lower() in _norm(low) and "contact" in low:
            log("[emu] Address visible in contact list.")
            return True
        if "add email" in low and ("enter" in low or "email address" in low):
            _fill(serial, "email", email, None)
            _tap_text(serial, ["next", "continue", "add"]) or _key(serial, 66)
            time.sleep(3.0)
            continue
        if "confirmation code" in low or ("enter" in low and "code" in low):
            log("[emu] Email confirmation code requested — fetching…")
            code = fetch_otp(keyword="confirm", timeout=240, prefer_len=6)
            if not code:
                raise EmuError("email confirmation code not received")
            _fill(serial, "code", code, None)
            _tap_text(serial, ["next", "continue", "confirm", "verify"]) or _key(serial, 66)
            time.sleep(4.0)
            continue
        if "contact info" in low or "contact details" in low:
            if not _tap_text(serial, ["add new contact", "add or edit", "add email", "add"]):
                _tap(serial, 285, 600)
            time.sleep(2.5)
            continue
        if "personal details" in low or "profiles" in low or "accounts center" in low:
            if not _tap_text(serial, ["contact info", "contact details", "personal details"]):
                _tap(serial, 285, 500)
            time.sleep(2.5)
            continue
        if _on_home(serial):
            _open_accounts_center(serial, log)
            continue
        time.sleep(2.0)
    raise EmuError(f"Email add unconfirmed. Last screen: {_dump(serial)}")


# ============================================================================
# Browser-free mail.td OTP (direct REST with stored tokens — pilot check:
# Cloudflare on the raw API; LIST=metadata only, DETAIL carries html_body)
# ============================================================================
def emu_fetch_mailtd_code(account_id: str, token: str, keyword: str = "meta",
                          timeout: int = 240, prefer_len: Optional[int] = None,
                          log: Callable[[str], None] = print) -> Optional[str]:
    try:
        import requests
    except Exception as exc:
        raise EmuError(f"requests unavailable for mail.td REST: {exc}")
    if not account_id or not token:
        return None
    base = "https://mail.td/api/accounts"
    head = {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"}
    seen: Dict[str, str] = {}
    end = time.time() + max(30, timeout)
    stale: set = set()
    while time.time() < end:
        try:
            r = requests.get(f"{base}/{account_id}/messages", params={"page": 1},
                             headers=head, timeout=15)
            if r.status_code in (401, 403):
                log(f"[emu] mail.td API blocked ({r.status_code}) — stored token rejected.")
                return None
            msgs = (r.json() or {}).get("messages") or []
        except Exception:
            msgs = []
        for m in msgs:
            mid = str(m.get("id") or "")
            if not mid or mid in seen:
                continue
            text = " ".join(str(v) for v in _flat(m))
            code = _pick(text, keyword, prefer_len, stale)
            if not code:
                try:
                    d = requests.get(f"{base}/{account_id}/messages/{mid}",
                                     headers=head, timeout=15).json() or {}
                    text = " ".join([d.get("html_body") or "", d.get("text_body") or "",
                                     d.get("text") or "", d.get("body") or ""])
                    code = _pick(text, keyword, prefer_len, stale)
                except Exception:
                    code = None
            seen[mid] = text
            if code:
                stale.add(code)
                log(f"[emu] mail.td code received ({keyword}).")
                return code
        time.sleep(1.5)
    return None


def _flat(obj, depth: int = 0) -> List[str]:
    out: List[str] = []
    if depth > 8 or obj is None:
        return out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flat(v, depth + 1))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_flat(v, depth + 1))
    return out


def _pick(text: str, keyword: str, prefer_len: Optional[int], stale: set) -> Optional[str]:
    import html as _html
    clean = _html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"#[0-9a-fA-F]{6}", " ", text or "")))
    kw = (keyword or "").lower()
    pats = ([r"(?:code|verification|verify|confirm|otp|authenticate|identity)[^\d]{0,60}(\d{8}|\d{6})",
             r"\b(\d{8})\b", r"\b(\d{6})\b"] if kw != "meta"
            else [r"(?:code|verification|verify|confirm|otp)[^\d]{0,60}(\d{6})(?!\d)", r"\b(\d{6})\b"])
    if prefer_len and prefer_len >= 4:
        pats.insert(0, rf"\b(\d{{{int(prefer_len)}}})\b")
    for pat in pats:
        for m in re.finditer(pat, clean, re.IGNORECASE):
            g = m.group(1)
            if len(g) == 6 and g.isdigit() and 2000 <= int(g) <= 2035:
                continue
            if g in stale:
                continue
            return g
    return None


def random_display_name() -> str:
    first = ["Alex", "Sam", "Jordan", "Taylor", "Chris", "Robin", "Avery", "Kai"]
    last = ["Smith", "Carter", "Reyes", "Patel", "Kim", "Novak", "Silva", "Ford"]
    return f"{random.choice(first)} {random.choice(last)}"
