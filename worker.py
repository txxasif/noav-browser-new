#!/usr/bin/env python3
"""
meta_creator — Multi-Worker Loop Engine
=======================================
Runs N concurrent anti-detect mobile browser windows in a continuous cycle:
1. Open Browser (Samsung S24 Ultra Android anti-detect profile)
2. Initialize the temporary mail.td inbox
3. Execute Meta registration (Adult DOB > 2000, sanitized display name, password)
4. Receive and confirm verification code from email
5. Solve human verification checkpoint (Whisper Audio STT reCAPTCHA + Biometric Selfie)
6. Store verified credentials in SQLite WAL, accounts.json, and accounts.csv
7. Close browser context and repeat in loop until target reached or stopped.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Ensure project root is on sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from ai_config import (
    ACCOUNTS_CSV,
    ACCOUNTS_JSON,
    ACCOUNTS_TXT,
    DATA_DIR,
    SELFIE_PATH,
    TG_BOT_CHOICES,
    Urls,
    emit_event,
    run,
)
import store
from pipelines.telegram import tg_worker  # coupled cycle (TG Classic)

# Ensure Playwright browser points at bundled anti-detect browsers
try:
    run._point_playwright_at_browsers()
except Exception:
    pass

_session_count = 0
_session_lock = threading.Lock()
_stop_requested = threading.Event()
# Alias used by the ported TG Classic code (coupled_loop + the throttle
# helpers reference `_stop`, meta_auto_ai's name for the same event).
# Aliasing means meta_creator's OWN shutdown path (_stop_requested.set())
# also stops the coupled loop — one signal, two names. Without this the
# worker died instantly: "name '_stop' is not defined".
_stop = _stop_requested

# ---- Globals required by the ported TG Classic code ----
# coupled_loop + the throttle/wall helpers were ported from meta_auto_ai
# and reference these module-level names. Without them the worker died at
# startup: "name '_cooldown_lock' is not defined".
_PHONE_WALL_MARKERS = ("mobile number required", "what's your mobile number")

_THROTTLE_MARKERS = ("rate-limited", "rate limit", "rendered blank",
                     "throttled", "bounced to instagram", "429", "1675004",
                     "can't find account",
                     # Accounts Center / session-loss signatures seen in the
                     # 2026-09-20 run: IG bootstrap throttling and the
                     # anti-automation contact-point challenge. Each cycle that
                     # hits one of these should cool the whole pool down, not
                     # feed another fresh Meta account into the same wall.
                     "could not reach accounts center", "update_risky_contactpoint",
                     "could not retrieve 2fa secret key", "ig login wall",
                     # Fresh-account session throttle (observed 2026-09-21): IG
                     # bounces settings/AC to /accounts/login/?__coig_login=1 and
                     # the API answers require_login:"Please wait a few minutes".
                     # This is the strongest velocity signal — cool the whole pool.
                     "__coig_login", "require_login", "please wait a few minutes",
                     # Risky-contact-point gate (IG demands a different email) —
                     # a risk signal; cool the pool instead of hammering.
                     "email_risky_contactpoint")

_cooldown_lock = threading.Lock()

_ig_cooldown_until = 0.0

def _sleep_stop(secs) -> None:
    """Stop-aware sleep in small slices."""
    end = time.time() + max(0.0, float(secs))
    while not _stop.is_set() and time.time() < end:
        time.sleep(min(0.5, max(0.0, end - time.time())))




def _low_end_enabled() -> bool:
    return os.environ.get("INSTA_LOW_END", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _safe_concurrency(requested: int) -> int:
    """Clamp Parallel for weak boxes only when INSTA_LOW_END=1.

    Each headless slot is ~300MB + shared Whisper (~75-150MB). Safe slots
    = (avail_MB - 800MB OS/Python) // 350MB, capped by CPU (1 slot per
    ~2 CPUs on weak boxes), hard-capped 1-3 for low-end. Set
    INSTA_NO_CLAMP=1 to keep the exact requested value.
    """
    req = max(1, min(int(requested), 50))
    if not _low_end_enabled():
        return req
    if os.environ.get("INSTA_NO_CLAMP", "0").strip().lower() in ("1", "true", "yes", "on"):
        return req
    safe = 3
    try:
        import multiprocessing
        cpu = multiprocessing.cpu_count() or 4
        safe = max(1, min(safe, max(1, cpu // 2)))
    except Exception:
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail_mb = int(line.split()[1]) // 1024
                    mem_slots = max(1, (avail_mb - 800) // 350)
                    safe = max(1, min(safe, mem_slots))
                    break
    except Exception:
        pass
    if safe < req:
        print(f"[*] Low-end preset (INSTA_LOW_END=1): clamping Parallel {req} -> {safe} "
              f"(RAM/CPU safe; INSTA_NO_CLAMP=1 to override).")
        emit_event({"type": "log", "message": f"[Low-end] Parallel clamped {req} -> {safe}."})
    return max(1, min(req, safe))


def _resolve_start_stagger_ms(value=None) -> int:
    """Smooth the initial browser launch burst without changing Parallel.

    Nova parity: Nova-Browser staggers creator threads by 1.5s
    (core/metaInstaWorker.py:1205). The old Linux default 0 launched all
    20 Chromiums at once (thundering herd). Default 1500ms per slot now.
    Override with INSTA_START_STAGGER_MS=0 for the old burst behavior.
    """
    if value is None:
        value = os.environ.get("INSTA_START_STAGGER_MS")
    if value is None or str(value).strip() == "":
        value = 1500 if os.name != "nt" else 500
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 1500 if os.name != "nt" else 500
    return max(0, min(value, 10000))


class AISlotWorker:
    """Worker slot interface used by MetaInstaRunner for logging and browser lifecycle."""

    def __init__(self, slot_id=1, is_headless=False, password=None):
        self.slot_id = slot_id
        self.is_headless = is_headless
        self.password = password
        self.is_running = True
        self.target = "Meta"
        self.user_data_dir = None
        self.playwright = None
        self.context = None
        self.page = None
        self.log_signal = self
        self.status_signal = self

    def emit(self, val):
        clean_text = re.sub(r"<[^>]+>", "", str(val)).strip()
        ts = datetime.now().strftime("%H:%M:%S")
        evt = {
            "type": "log",
            "slot_id": self.slot_id,
            "timestamp": ts,
            "message": f"[Slot #{self.slot_id}] {clean_text}",
        }

        # Detect specific step transitions to update dashboard slot cards
        if "[📧] Meta inbox:" in clean_text or "Initializing mail inbox" in clean_text:
            email = clean_text.split(":")[-1].strip() if ":" in clean_text else ""
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "mailbox",
                "detail": f"Inbox ready: {email}",
                "email": email,
            })
        elif "[⌨️] Name:" in clean_text or "Configured adult DOB" in clean_text or "[🎂] DOB" in clean_text:
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "registering",
                "detail": "Filled registration form",
            })
        elif "[🔑] Setting password" in clean_text:
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "registering",
                "detail": "Setting secure password",
            })
        elif "[📨] Waiting for the email code" in clean_text:
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "verifying",
                "detail": "Waiting for email code...",
            })
        elif "[📧] meta code:" in clean_text.lower() or "verification code accepted" in clean_text.lower():
            code = clean_text.split(":")[-1].strip() if ":" in clean_text else ""
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "verifying",
                "detail": f"Code accepted: {code}",
            })
        elif "recaptcha" in clean_text.lower() and ("solved" in clean_text.lower() or "solving" in clean_text.lower()):
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "captcha",
                "detail": "reCAPTCHA solving via audio/extension",
            })
        elif "verification selfie assigned" in clean_text.lower():
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "preparing",
                "detail": "Selfie image assigned",
            })
        elif ("selfie uploaded" in clean_text.lower()
              or "verification selfie submitted" in clean_text.lower()):
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "selfie",
                "detail": "Biometric selfie uploaded",
            })
        elif "meta account confirmed" in clean_text.lower() or "storing" in clean_text.lower():
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "storing",
                "detail": "Account confirmed! Storing...",
            })
        elif "instagram: opening login" in clean_text.lower():
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "login",
                "detail": "Opening Instagram login...",
            })
        elif "meta profile card" in clean_text.lower():
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "linking",
                "detail": "Connecting Meta card to Instagram...",
            })
        elif "instagram: joining" in clean_text.lower() or "joining with" in clean_text.lower():
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "joining",
                "detail": "Joining Instagram...",
            })
        elif "post-registration onboarding" in clean_text.lower():
            emit_event({
                "type": "slot_event",
                "slot_id": self.slot_id,
                "status": "onboarding",
                "detail": "Finalizing onboarding & follow...",
            })

        emit_event(evt)

    def _get_proxy_config(self):
        return None

    def on_browser_closed(self):
        self.is_running = False

    def _cleanup_browser_resources(self):
        profile_dir = self.user_data_dir
        for close in (
            lambda: self.context and self.context.close(),
            lambda: self.playwright and self.playwright.stop(),
        ):
            try:
                close()
            except Exception:
                pass
        self.context = None
        self.playwright = None
        try:
            from engine.resource_runtime import unregister_profile
            unregister_profile(profile_dir)
        except Exception:
            pass
        if profile_dir and os.path.exists(profile_dir) and os.environ.get("KEEP_PROFILE") != "1":
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass
        self.user_data_dir = None


def run_single_meta_cycle(slot_id: int, is_headless: bool = False, mail_provider: str = "mailtd", captcha_mode: str = "extension", mode: str = "meta", new_password: str = "", new_username: str = "", twofa: bool = False) -> tuple[bool, str]:
    """Execute one Meta Account Creation cycle."""
    from runner import MetaInstaRunner

    cycle_started = time.monotonic()
    worker = AISlotWorker(slot_id=slot_id, is_headless=is_headless, password=new_password or None)
    runner = MetaInstaRunner(
        worker,
        mail_provider=mail_provider,
        captcha_mode=captcha_mode,
        new_password=new_password or None,
        new_username=new_username or None,
        # Meta/Instagram Creator is its own pipeline. Without this the runner
        # inherits MetaBaseMixin's default target="telegram", so every Meta/IG
        # account landed in the Telegram ledger and the TG Classic tab counted
        # accounts it never created (meta_auto_ai isolates pipelines by target).
        target="meta",
    )

    emit_event({
        "type": "slot_event",
        "slot_id": slot_id,
        "status": "launching",
        "detail": "Launching anti-detect browser context...",
    })

    try:
        # Full Meta -> Instagram creation flow (always proceed to Instagram join unless explicitly meta-only)
        meta_only = (mode == "meta-only")
        rec_id = runner.create_account(twofa=twofa, meta_only=meta_only)
        worker.emit(f"✅ Successfully created {'Meta' if meta_only else 'Instagram'} account: @{runner.ig_username or runner.username or runner.email}")
        duration_ms = int((time.monotonic() - cycle_started) * 1000)
        emit_event({
            "type": "slot_event",
            "slot_id": slot_id,
            "status": "closed",
            "detail": f"Completed in {duration_ms / 1000:.1f}s: {runner.email}",
            "email": runner.email,
            "duration_ms": duration_ms,
        })
        emit_event({
            "type": "account_created",
            "id": rec_id,
            "email": runner.email,
            "name": runner.name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        return True, rec_id
    except Exception as exc:
        duration_ms = int((time.monotonic() - cycle_started) * 1000)
        worker.emit(f"❌ Cycle failed after {duration_ms / 1000:.1f}s: {exc}")
        if "Connection closed while reading from the driver" in str(exc):
            worker.emit("💡 Browser/driver connection lost — usually RAM pressure or a crashed Chromium. "
                        "The requested Parallel value is preserved; retry or use Headless for lower resource use.")
        if getattr(runner, "last_record_id", None):
            worker.emit(f"💾 Account record preserved in store: {runner.last_record_id}")
            emit_event({
                "type": "account_created",
                "id": runner.last_record_id,
                "email": getattr(runner, "email", ""),
                "name": getattr(runner, "name", ""),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
        emit_event({
            "type": "slot_event",
            "slot_id": slot_id,
            "status": "error",
            "detail": f"Error after {duration_ms / 1000:.1f}s: {exc}",
            "duration_ms": duration_ms,
        })
        return False, str(exc)
    finally:
        try:
            runner.finish()
        except Exception:
            pass
        try:
            worker._cleanup_browser_resources()
        except Exception:
            pass


def slot_loop(slot_id: int, is_headless: bool = False, target: int = 0, delay: int = 4, mail_provider: str = "mailtd", captcha_mode: str = "extension", mode: str = "meta", new_password: str = "", new_username: str = "", start_stagger_ms: int = 0, twofa: bool = False):
    """Loop for a single slot creating Meta accounts continuously."""
    consecutive_fails = 0
    initial_stagger_done = False

    while not _stop_requested.is_set():
        with _session_lock:
            global _session_count
            if target > 0 and _session_count >= target:
                emit_event({
                    "type": "slot_event",
                    "slot_id": slot_id,
                    "status": "idle",
                    "detail": "Target accounts reached.",
                })
                break
            _session_count += 1

        # Periodic license verification (ensures license hasn't expired mid-run)
        try:
            from core.license_mgr import LicenseManager
            _lm = LicenseManager()
            _lic = _lm.validate_or_activate()
            if not _lic.get("isValid"):
                emit_event({
                    "type": "log",
                    "slot_id": slot_id,
                    "message": f"[License] License check failed ({_lic.get('status')}): {_lic.get('message')}. Stopping slot.",
                })
                _stop_requested.set()
                break
        except Exception:
            pass

        # The requested slot count is controlled by the dashboard/CLI.
        # Resource tuning lives in the browser launcher (low-memory flags and
        # tracker blocking); do not silently pause or reduce user-selected
        # concurrency here.
        if not initial_stagger_done:
            initial_stagger_done = True
            stagger_seconds = max(0, int(start_stagger_ms)) * max(0, slot_id - 1) / 1000.0
            deadline = time.monotonic() + stagger_seconds
            while not _stop_requested.is_set() and time.monotonic() < deadline:
                time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

        ok, detail = run_single_meta_cycle(
            slot_id=slot_id,
            is_headless=is_headless,
            mail_provider=mail_provider,
            captcha_mode=captcha_mode,
            mode=mode,
            new_password=new_password,
            new_username=new_username,
            twofa=twofa,
        )

        if not ok:
            with _session_lock:
                _session_count = max(0, _session_count - 1)
            consecutive_fails += 1
            backoff = min(15 * consecutive_fails, 120)
            emit_event({
                "type": "log",
                "slot_id": slot_id,
                "message": f"[Backoff] Cooling down {backoff}s before retry...",
            })
            for _ in range(backoff * 2):
                if _stop_requested.is_set():
                    break
                time.sleep(0.5)
            continue

        consecutive_fails = 0
        emit_event({
            "type": "slot_event",
            "slot_id": slot_id,
            "status": "cooldown",
            "detail": f"Resting {delay}s...",
        })
        for _ in range(delay * 2):
            if _stop_requested.is_set():
                break
            time.sleep(0.5)



# ============================================================================
# TG Classic — coupled per-task loop (Meta -> TG task -> IG -> submit)
# Ported from meta_auto_ai/worker.py. Meta/IG half is shared code; only
# the TG task acquisition + submit gate are telegram-specific.
# ============================================================================
def _wait_ig_cooldown() -> None:
    """Cooldown disabled completely."""
    return

def _note_phone_wall(slot_id) -> bool:
    """Record a phone-wall hit (split mode). No cooldown or throttle banner."""
    emit_event({"type": "log", "slot_id": slot_id,
                "message": "[wall] Instagram phone wall — skipping this account; other slots keep working"})
    return False

def _note_ig_throttle(slot_id, detail="") -> int:
    """No cooldown, no throttle banner."""
    return 0

def _clear_ig_throttle() -> None:
    global _phone_wall_streak
    coupled_loop._throttle_fails = 0
    _phone_wall_streak = 0

def _looks_throttled(detail) -> bool:
    """Throttling disabled — never pause or block cycles."""
    return False
def _is_phone_wall(detail) -> bool:
    """True when the failure is Instagram's "What's your mobile number?" gate."""
    low = str(detail or "").lower()
    return any(m in low for m in _PHONE_WALL_MARKERS)
_phone_wall_streak = 0

TG_DEFAULT_TASK = "Create Inst (No mail)"

_active_slots_lock = threading.Lock()
_active_slots = set()

def _is_no_task_error(err_text: str) -> bool:
    """True ONLY for definitive terminal conditions: bot hourly limit reached or pool empty.

    Transient profile lease delays, network button lags, or single-task credential
    glitches must NOT trip this and must not kill the entire fleet prematurely.
    """
    if not err_text:
        return False
    e = str(err_text).lower()
    return any(p in e for p in (
        "limit is reached",
        "limit reached",
        "hour's limit",
        "hourly limit",
        "available this hour: 0/",
        "available this hour: 0 ",
        "no_pool_accounts",
        "no available ig creator accounts",
        "pool empty",
        "tasks out of stock",
        "temporarily out of stock",
        "all tasks completed",
        "task list is empty",
    ))


def coupled_loop(slot_id, is_headless=False, target=0, delay=2, task=TG_DEFAULT_TASK,
                 tg_bot="taskly", captcha_mode="extension", mail_provider="mailtd",
                 add_email=False, cookie=False, use_ig_pool=False):
    """Coupled per-task loop: ONE browser does Meta → TG task → IG → submit.

    N slots run in parallel (each opens its own Meta/IG browser up front);
    the 2 TG profiles serialize only the TG-task + IG half via short,
    stop-aware lease waits. Each completed task closes its browser and
    releases its lease before the next cycle opens a fresh one.

    Each cycle runs in a FRESH thread: strict mode leaves failed browsers
    OPEN, and a second Playwright driver in the same thread collides with
    the orphaned one (greenlet "Sync API inside asyncio loop" death spiral
    spawning a profile dir every few seconds). A joined per-cycle thread
    bounds that damage.
    """
    with _active_slots_lock:
        _active_slots.add(slot_id)

    if slot_id > 1:
        time.sleep(min(8.0, (slot_id - 1) * 1.5))

    def _once():
        # Each cycle runs in its own thread → close that thread's SQLite
        # connection on exit so FDs don't churn over a long run.
        try:
            return _once_inner()
        finally:
            try:
                import db as _db
                _db.close_local_connection()
            except Exception:
                pass

    def _once_inner():
        with _session_lock:
            global _session_count
            if target and _session_count >= target:
                return "done"
            _session_count += 1
        try:
            # Pick the runner from the REGISTRY (data), not a regex on the task
            # text: "🍪 Create Inst (No mail)" contains no literal "cookie", so a
            # /cookie/i test would wrongly send it to the coupled runner.
            _runner = ""
            try:
                import tg_tasks as _tt
                from tg_flows import runner_of as _runner_of
                _flow = _tt.flow_of(tg_bot, task)
                _runner = _runner_of(_flow) if _flow else ""
            except Exception:
                _runner = ""
            _use_cookie = cookie or str(_runner) == "run_cookie_cycle"
            if _use_cookie:
                # Cookie-family task (PayGo cookie, Taskly cookie_2fa):
                # Meta -> TG creds -> [2FA] -> IG join + follow -> cookie export
                # -> cookie submit. Lazy import: run_cookie_cycle lazily imports
                # AISlotWorker back, so a top-level import here would be circular.
                from run_cookie_cycle import run_cookie_cycle_once
                ok, detail = run_cookie_cycle_once(
                    slot_id=slot_id, worker_factory=AISlotWorker,
                    is_headless=is_headless, captcha_mode=captcha_mode,
                    mail_provider=mail_provider, stop_event=_stop,
                    add_email=add_email, tg_task=task, tg_bot=tg_bot,
                    use_ig_pool=use_ig_pool)
            elif str(_runner) == "run_native_cycle":
                # Taskly 2FA native task: NO Meta, NO mailbox — lease TG,
                # Start, bot email+code, IG native signup, Account Registered.
                # Lazy import for the same circularity reason as above.
                from run_native_cycle import run_native_cycle_once
                ok, detail = run_native_cycle_once(
                    slot_id=slot_id, worker_factory=AISlotWorker,
                    is_headless=is_headless, captcha_mode=captcha_mode,
                    mail_provider=mail_provider, stop_event=_stop,
                    add_email=add_email, tg_task=task, tg_bot=tg_bot)
            elif str(_runner) == "run_pool_2fa_cycle":
                # Taskly "📱 Create Inst (2FA)" POOL DRAIN (new "Taskly 2FA"
                # panel): reuse a pre-created IG account from the pool — rename
                # via Web API + 2FA from the stored inbox — no Meta, no signup.
                from run_pool_2fa_cycle import run_pool_2fa_cycle_once
                ok, detail = run_pool_2fa_cycle_once(
                    slot_id=slot_id, worker_factory=AISlotWorker,
                    is_headless=is_headless, captcha_mode=captcha_mode,
                    mail_provider=mail_provider, stop_event=_stop,
                    add_email=add_email, tg_task=task, tg_bot=tg_bot,
                    use_ig_pool=True)
            else:
                ok, detail = tg_worker.run_tg_coupled_cycle(
                    AISlotWorker, slot_id=slot_id, is_headless=is_headless,
                    tg_task=task, tg_bot=tg_bot,
                    captcha_mode=captcha_mode, mail_provider=mail_provider,
                    add_email=add_email,
                    stop_event=_stop)
            err_text = "" if ok else str(detail or "")
        except Exception as exc:
            ok, err_text = False, str(exc)
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error", "detail": f"Error: {exc}"})
        if not ok:
            if err_text.strip().lower() == "stopped":
                with _session_lock:
                    _session_count = max(0, _session_count - 1)
                return "stopped"
            with _session_lock:
                _session_count = max(0, _session_count - 1)

            # Slot-by-slot graceful shutdown: if bot has no task or pool is empty, retire
            if _is_no_task_error(err_text):
                # When pool is empty or bot has no task available, stop ALL creators immediately
                _stop.set()
                with _active_slots_lock:
                    _active_slots.discard(slot_id)
                    remaining = len(_active_slots)
                print(f"[*] [Slot {slot_id}] 🛑 Bot/pool has no task available ({err_text}). Creator {slot_id} stopped ({remaining} active creator(s) remaining).", flush=True)
                emit_event({
                    "type": "slot_event",
                    "slot_id": slot_id,
                    "status": "stopped",
                    "detail": f"No task available ({err_text}) — Creator {slot_id} stopped ({remaining} remaining)."
                })
                emit_event({
                    "type": "log",
                    "pipeline": "telegram",
                    "message": f"[tg:slot-{slot_id}] Stopped: {err_text} ({remaining} creator(s) remaining)."
                })
                return "no_task"

            if IG_WALL_SPLIT and _is_phone_wall(err_text):
                # Per-account/region gate: skip this account without pausing the
                # pool. Only cool everyone if the breaker trips (IP-wide).
                if _note_phone_wall(slot_id):
                    _note_ig_throttle(slot_id, err_text)
                    return "throttled"
                if IG_WALL_SLOT_BACKOFF:
                    _sleep_stop(IG_WALL_SLOT_BACKOFF)
                return "ok"
            if _looks_throttled(err_text):
                # Pipeline-wide pause: extend the SHARED deadline; the top-of-loop
                # gate makes every slot wait, so a fresh Meta account isn't fed
                # into the same wall.
                _note_ig_throttle(slot_id, err_text)
                return "throttled"
        _clear_ig_throttle()
        return "ok"

    # Stagger initial slot launches so all 6 slots do not hammer the Telegram bot
    # in the exact same millisecond.
    if slot_id > 1:
        time.sleep(min(8.0, (slot_id - 1) * 1.5))

    try:
        while not _stop.is_set():
            _wait_ig_cooldown()
            holder = {}
            t = threading.Thread(target=lambda: holder.setdefault("r", _once()), daemon=True)
            t.start()
            while t.is_alive():
                t.join(timeout=1.0)
            if holder.get("r") in ("done", "stopped", "no_task"):
                break
            # Pool drain: per-profile pacing in run_cookie_cycle already guards individual
            # Telegram accounts from anti-flood, so slots on DIFFERENT accounts can drain immediately.
            eff_delay = 0.5 if use_ig_pool else int(delay)
            for _ in range(max(1, int(eff_delay * 2))):
                if _stop.is_set():
                    break
                time.sleep(0.5)
    finally:
        with _active_slots_lock:
            _active_slots.discard(slot_id)
            remaining = len(_active_slots)
        if remaining == 0:
            print(f"[*] 🛑 All creators stopped — no tasks available from bot. Engine idle until manual restart.", flush=True)
            emit_event({
                "type": "log",
                "pipeline": "telegram",
                "message": f"[tg] All creators stopped. TG engine is idle until manually started."
            })
            emit_event({
                "type": "loop_stopped",
                "message": "All creators stopped — no tasks available from bot."
            })
            _stop.set()

def main():
    parser = argparse.ArgumentParser(description="MetaAuto Linux — Dedicated Meta Account Creator")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent worker slots")
    parser.add_argument("--target", type=int, default=0, help="Target total accounts to create (0 = unlimited)")
    parser.add_argument("--delay", type=int, default=4, help="Delay in seconds between cycles")
    parser.add_argument("--headless", action="store_true", help="Run in headless browser mode")
    parser.add_argument("--mail", type=str, default="mailtd", choices=("mailtd",), help="Mailbox provider (mail.td only)")
    parser.add_argument("--captcha", type=str, default="extension", choices=Urls.CAPTCHA_MODES, help="Captcha solving mode")
    parser.add_argument("--mode", type=str, default="meta", choices=["meta", "meta-ig", "meta-only"], help="Creation mode: Meta account only, or Meta + Instagram join")
    parser.add_argument("--coupled", action="store_true",
                        help="TG Classic: one browser per task (Meta -> TG task -> IG -> submit)")
    parser.add_argument("--twofa", action="store_true", help="Enable 2FA in the IG half")
    parser.add_argument("--tg-task", type=str, default=TG_DEFAULT_TASK, help="Taskly task name")
    parser.add_argument("--tg-bot", type=str, default="taskly",
                        choices=tuple(TG_BOT_CHOICES), help="Task bot")
    parser.add_argument("--add-email", action="store_true",
                        help="telegram coupled: after password+2FA, add a fresh mail.td email in Accounts Center")
    parser.add_argument("--tg-profile", type=str, default=None, help="Force one Telegram profile id")
    parser.add_argument("--cookie", action="store_true",
                        help="PayGo Cookies task loop: Meta -> TG creds -> IG join + follow -> "
                             "cookie export -> cookie submit -> register (no 2FA leg). "
                             "Takes precedence over --tg-task/--tg-bot.")
    parser.add_argument("--use-ig-pool", action="store_true",
                        help="PayGo Cookies task: drain pre-created accounts from the IG Creator pool")
    parser.add_argument("--start-stagger-ms", type=int, default=None,
                        help="Stagger initial slot launches in milliseconds (does not reduce Parallel)")

    args = parser.parse_args()

    concurrency = _safe_concurrency(args.concurrency)
    target = max(0, args.target)
    delay = max(1, args.delay)
    headless = args.headless
    if _low_end_enabled() and not headless:
        print("[*] Low-end preset: headed mode costs ~30% more RAM/CPU — use Headless for max speed.")
    if _low_end_enabled() and args.captcha == "extension":
        print("[*] Low-end tip: --captcha audio uses headless-shell (~100MB lighter/slot than "
              "full Chromium for the Visual AI extension) and Vosk-first STT.")
    start_stagger_ms = _resolve_start_stagger_ms(args.start_stagger_ms)

    # Global password (META_NEW_PASSWORD env from server.js): same password
    # for every created account. Too-short values fall back to auto passwords.
    global_password = (os.environ.get("META_NEW_PASSWORD") or "").strip()[:128]
    if global_password and len(global_password) < 6:
        print("[*] Global password too short (<6 chars) — using auto passwords.")
        global_password = ""

    # Optional fixed username (META_NEW_USERNAME env from server.js). Applied to
    # the Meta display name / Instagram username depending on the mode.
    global_username = (os.environ.get("META_NEW_USERNAME") or "").strip()[:64]

    # License Gate: Hardware-bound license verification
    try:
        from core.license_mgr import LicenseManager
        lic_mgr = LicenseManager()
        lic_res = lic_mgr.validate_or_activate()
        if not lic_res.get("isValid"):
            status_msg = lic_res.get("status", "UNLICENSED")
            detail_msg = lic_res.get("message", "Active license required to run Meta Creator.")
            err = f"[License] Execution blocked ({status_msg}): {detail_msg}"
            print(f"[!] {err}")
            emit_event({"type": "log", "message": err})
            emit_event({
                "type": "license_invalid",
                "status": status_msg,
                "message": detail_msg,
                "hwid": lic_res.get("hwid", ""),
            })
            sys.exit(1)
        else:
            hwid_val = lic_res.get("hwid", "")
            lic_type = (lic_res.get("license") or {}).get("license_type", "ACTIVE")
            print(f"[*] License verified ({lic_type}) [HWID: {hwid_val}]")
    except Exception as exc:
        print(f"[License] Check error: {exc}")
        sys.exit(1)

    # Concurrency policy: exact user value by default; only INSTA_LOW_END=1
    # clamps (see _safe_concurrency). The launcher applies low-memory
    # browser flags and cleans up completed profiles.
    print(f"[*] Concurrency policy: Parallel={concurrency} (low-end clamp "
          f"{'on' if _low_end_enabled() else 'off'}; INSTA_FAST_MODE={os.environ.get('INSTA_FAST_MODE', '1')}).")
    print(f"[*] Startup stagger: {start_stagger_ms}ms per slot (Parallel unchanged).")

    def sig_handler(signum, frame):
        _stop_requested.set()
        emit_event({"type": "log", "message": "Stop signal received, shutting down gracefully..."})
        # TG Classic parity (auto_ai worker._sig_handler): drop warm bot owners
        # and free any lease so a restart is not blocked. Best-effort — a
        # Windows TerminateProcess never reaches this, which is why the coupled
        # startup below also self-heals with tg_manager.reset_all().
        try:
            from tg_bot import PooledTelegramBot
            from mtproto_bot import MtprotoPooledBot
            PooledTelegramBot.drop_all()
            MtprotoPooledBot.drop_all()
        except Exception:
            pass
        try:
            from tg_accounts import tg_manager
            tg_manager.reset_all()
        except Exception:
            pass

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    emit_event({
        "type": "loop_started",
        "concurrency": concurrency,
        "target": target,
        "delay": delay,
        "headless": headless,
        "start_stagger_ms": start_stagger_ms,
        "mail_provider": args.mail,
        "mode": args.mode,
    })

    print(f"[*] Meta Account Creator initialized: concurrency={concurrency}, target={target}, headless={headless}, mode={args.mode}, global_pw={'on' if global_password else 'off'}, fixed_user={'on' if global_username else 'off'}")

    # --coupled runs TG Classic (Meta -> TG task -> IG -> submit) instead of the
    # plain Meta creator. The existing slot_loop path is untouched, so omitting
    # --coupled keeps the previous behaviour exactly.
    _loop = coupled_loop if getattr(args, "coupled", False) else slot_loop
    # Each loop takes a DIFFERENT kwarg set. Passing the union raised
    # "coupled_loop() got an unexpected keyword argument 'mode'" inside the
    # ThreadPoolExecutor, so the worker died before opening a browser and the
    # UI just sat at IDLE with no tab. Build the kwargs per loop.
    _shared = dict(is_headless=headless, target=target, delay=delay,
                   mail_provider=args.mail, captcha_mode=args.captcha)
    if _loop is slot_loop:
        _shared.update(mode=args.mode, new_password=global_password,
                       new_username=global_username, start_stagger_ms=start_stagger_ms,
                       twofa=bool(getattr(args, "twofa", False)))
    else:
        # coupled_loop drives Meta -> TG task -> IG -> submit; credentials come
        # from the leased profile, and there is no fixed username/password.
        _shared.update(task=args.tg_task, tg_bot=args.tg_bot, add_email=args.add_email,
                       cookie=bool(getattr(args, "cookie", False)),
                       use_ig_pool=bool(getattr(args, "use_ig_pool", False)))
    # Self-heal TG leases. The Windows Stop button kills the worker with
    # TerminateProcess, so the coupled cycle's `finally: tg_manager.release`
    # never runs and the profile stays `busy` until LEASE_TTL (20 min). Reset
    # stale leases here so the next start can lease immediately.
    if _loop is coupled_loop:
        try:
            from tg_accounts import tg_manager
            tg_manager.reset_all()
        except Exception:
            pass
        with _active_slots_lock:
            _active_slots.clear()

    stop_flag_path = os.path.join(DATA_DIR, "stop_tg.flag")
    if os.path.exists(stop_flag_path):
        try:
            os.remove(stop_flag_path)
        except Exception:
            pass

    def _watch_stop_flag():
        while not _stop.is_set():
            if os.path.exists(stop_flag_path):
                _stop.set()
                try:
                    os.remove(stop_flag_path)
                except Exception:
                    pass
                print("[*] Graceful stop requested — allowing in-flight tasks to finish...", flush=True)
                break
            time.sleep(0.3)

    threading.Thread(target=_watch_stop_flag, daemon=True).start()

    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_loop, slot_id=i + 1, **_shared)
                for i in range(concurrency)
            ]
            for f in futures:
                try:
                    f.result()
                except Exception as exc:
                    print(f"[!] Worker exception: {exc}")
    finally:
        if _loop is coupled_loop:
            try:
                from tg_accounts import tg_manager
                tg_manager.reset_all()
            except Exception:
                pass
        # Sweep stale profile dirs on the way out. Pruning otherwise only runs
        # at slot LAUNCH, so a run that ends (or is stopped) leaves its dead
        # profile dirs behind until the next start -- and if the engine is not
        # restarted they persist indefinitely (observed: 4 test_meta_* dirs,
        # ~160 MB, three days old). Best-effort; never blocks shutdown.
        try:
            from engine.eng_mix_base import _PROFILE_PREFIXES as _pp  # noqa: F401
            _base = os.path.join(os.getcwd(), "profiles")
            if os.path.isdir(_base):
                import engine.eng_mix_base as _emb
                class _Sweeper(_emb.EngineBaseMixin):
                    def __init__(self):
                        pass  # prune is a pure directory operation
                _Sweeper()._prune_profiles(_base)
        except Exception:
            pass

    emit_event({"type": "loop_stopped", "message": "All slots finished."})
    print("[*] Meta Account Creator stopped.")



# Globals required by the ported TG Classic code. NOTE: these MUST be
# assigned BEFORE the __main__ call below — running as a script executes
# top-to-bottom, so globals placed after `main()` would not exist when the
# coupled threads start ("NameError: IG_WALL_SPLIT is not defined").
_HEADLESS = {"value": False}
IG_WALL_SPLIT = os.environ.get("IG_WALL_SPLIT", "1").strip().lower() not in ("0", "false", "no")
IG_WALL_BREAKER_N = max(1, int(os.environ.get("IG_WALL_BREAKER_N", "6") or 6))
# Pipeline-wide IG throttle cooldown. DISABLED by default (IG_COOLDOWN=0): the
# engine keeps working through a throttle — detection + the dashboard
# toast/error still fire, only the blocking pause is skipped. Set IG_COOLDOWN=1
# to restore the old "cool the whole pool" behaviour.
IG_COOLDOWN_ENABLED = os.environ.get("IG_COOLDOWN", "0").strip().lower() not in ("0", "false", "no", "off")
IG_WALL_SLOT_BACKOFF = max(0.0, float(os.environ.get("IG_WALL_SLOT_BACKOFF", "5") or 0))

if __name__ == "__main__":
    main()
