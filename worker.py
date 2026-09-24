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
    Urls,
    emit_event,
    run,
)
import store

# Ensure Playwright browser points at bundled anti-detect browsers
try:
    run._point_playwright_at_browsers()
except Exception:
    pass

_session_count = 0
_session_lock = threading.Lock()
_stop_requested = threading.Event()


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

        emit_event(evt)

    def _get_proxy_config(self):
        return None

    def on_browser_closed(self):
        self.is_running = False

    def _cleanup_browser_resources(self):
        for close in (
            lambda: self.context and self.context.close(),
            lambda: self.playwright and self.playwright.stop(),
        ):
            try:
                close()
            except Exception:
                pass
        if self.user_data_dir and os.path.exists(self.user_data_dir) and os.environ.get("KEEP_PROFILE") != "1":
            try:
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
            except Exception:
                pass


def run_single_meta_cycle(slot_id: int, is_headless: bool = False, mail_provider: str = "mailtd", captcha_mode: str = "extension", mode: str = "meta", new_password: str = "", new_username: str = "") -> tuple[bool, str]:
    """Execute one Meta Account Creation cycle (`meta` = Meta only, `meta-ig` = Meta + Instagram join)."""
    from runner import MetaInstaRunner

    worker = AISlotWorker(slot_id=slot_id, is_headless=is_headless, password=new_password or None)
    runner = MetaInstaRunner(
        worker,
        mail_provider=mail_provider,
        captcha_mode=captcha_mode,
        new_password=new_password or None,
        new_username=new_username or None,
    )

    emit_event({
        "type": "slot_event",
        "slot_id": slot_id,
        "status": "launching",
        "detail": "Launching anti-detect browser context...",
    })

    try:
        # Phase: Meta creation (parked as MetaCreated), plus the Instagram
        # join when mode == "meta-ig" (parked as Created with IG session).
        meta_only = (mode != "meta-ig")
        rec_id = runner.create_account(twofa=False, meta_only=meta_only)
        worker.emit(f"✅ Successfully created {'Meta→IG' if not meta_only else 'Meta'} account: {runner.email}")
        emit_event({
            "type": "slot_event",
            "slot_id": slot_id,
            "status": "closed",
            "detail": f"Completed: {runner.email}",
            "email": runner.email,
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
        worker.emit(f"❌ Cycle failed: {exc}")
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
            "detail": f"Error: {exc}",
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


def slot_loop(slot_id: int, is_headless: bool = False, target: int = 0, delay: int = 4, mail_provider: str = "mailtd", captcha_mode: str = "extension", mode: str = "meta", new_password: str = "", new_username: str = ""):
    """Loop for a single slot creating Meta accounts continuously."""
    consecutive_fails = 0

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

        ok, detail = run_single_meta_cycle(
            slot_id=slot_id,
            is_headless=is_headless,
            mail_provider=mail_provider,
            captcha_mode=captcha_mode,
            mode=mode,
            new_password=new_password,
            new_username=new_username,
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


def main():
    parser = argparse.ArgumentParser(description="MetaAuto Linux — Dedicated Meta Account Creator")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent worker slots")
    parser.add_argument("--target", type=int, default=0, help="Target total accounts to create (0 = unlimited)")
    parser.add_argument("--delay", type=int, default=4, help="Delay in seconds between cycles")
    parser.add_argument("--headless", action="store_true", help="Run in headless browser mode")
    parser.add_argument("--mail", type=str, default="mailtd", choices=("mailtd",), help="Mailbox provider (mail.td only)")
    parser.add_argument("--captcha", type=str, default="extension", choices=Urls.CAPTCHA_MODES, help="Captcha solving mode")
    parser.add_argument("--mode", type=str, default="meta", choices=["meta", "meta-ig"], help="Creation mode: Meta account only, or Meta + Instagram join")

    args = parser.parse_args()

    concurrency = max(1, min(args.concurrency, 50))
    target = max(0, args.target)
    delay = max(1, args.delay)
    headless = args.headless

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

    # Keep the user-selected concurrency exactly as requested.  The launcher
    # applies low-memory browser flags and cleans up completed profiles; the
    # worker does not impose a second RAM policy.
    print(f"[*] Concurrency policy: user-selected value {concurrency} will be used without RAM clamping.")

    def sig_handler(signum, frame):
        _stop_requested.set()
        emit_event({"type": "log", "message": "Stop signal received, shutting down gracefully..."})

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    emit_event({
        "type": "loop_started",
        "concurrency": concurrency,
        "target": target,
        "delay": delay,
        "headless": headless,
        "mail_provider": args.mail,
        "mode": args.mode,
    })

    print(f"[*] Meta Account Creator initialized: concurrency={concurrency}, target={target}, headless={headless}, mode={args.mode}, global_pw={'on' if global_password else 'off'}, fixed_user={'on' if global_username else 'off'}")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                slot_loop,
                slot_id=i + 1,
                is_headless=headless,
                target=target,
                delay=delay,
                mail_provider=args.mail,
                captcha_mode=args.captcha,
                mode=args.mode,
                new_password=global_password,
                new_username=global_username,
            )
            for i in range(concurrency)
        ]
        for f in futures:
            try:
                f.result()
            except Exception as exc:
                print(f"[!] Worker exception: {exc}")

    emit_event({"type": "loop_stopped", "message": "All slots finished."})
    print("[*] Meta Account Creator stopped.")


if __name__ == "__main__":
    main()
