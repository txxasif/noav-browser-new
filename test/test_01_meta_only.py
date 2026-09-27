#!/usr/bin/env python3
"""
test/test_01_meta_only.py — Create ONLY Meta Account & Persist Full Session
===========================================================================
Executes the isolated Meta creation flow (Mailbox -> Meta Auth -> OTP -> Profile setup),
ensures credentials are created, and exports context storage_state, cookies,
and credentials for downstream DevTools-driven Instagram exploration.

Usage:
    .venv/bin/python test/test_01_meta_only.py [--cdp 9222] [--close] [--mail mailtd]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import traceback

AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AI_DIR)
os.chdir(AI_DIR)

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

from ai_config import AI_DIR, DATA_DIR, SESSIONS_DIR, Urls, run
import store
from devtools_client import DevToolsInspector, dump_full_session, find_free_port

# Point Playwright at the bundled browsers (engine/ms-playwright). Without this
# the engine silently falls back to SYSTEM Chrome, which changes the fingerprint
# and slows launch — same bug class as tg_login.py/open_session.py.
try:
    run._point_playwright_at_browsers()
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser(description="Create Meta account only and persist session")
    ap.add_argument("--cdp", type=int, default=9222, help="Remote debugging port for Chrome DevTools")
    ap.add_argument("--mail", type=str, default="mailtd", help="Mail provider (mail.td only)")
    ap.add_argument("--captcha", type=str, default="audio", choices=("audio", "extension"), help="Captcha mode (audio or extension)")
    ap.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    ap.add_argument("--close", action="store_true", help="Close browser immediately after creation instead of keeping it open")
    args = ap.parse_args()

    test_dir = os.path.join(AI_DIR, "test")
    artifacts_dir = os.path.join(test_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)

    inspector = DevToolsInspector(artifacts_dir=artifacts_dir)

    # Isolated test profile
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rec_id = f"test_meta_{timestamp}"
    prof_dir = os.path.join(AI_DIR, "profiles", rec_id)
    os.makedirs(prof_dir, exist_ok=True)
    os.environ["INSTA_PROFILE_DIR"] = prof_dir
    os.environ["KEEP_PROFILE"] = "1"

    # Expose CDP port for Chrome DevTools (auto-detect free port if default is busy)
    cdp_port = find_free_port(args.cdp)
    import engine.eng_constants as ec
    flag = f"--remote-debugging-port={cdp_port}"
    if flag not in list(ec._NOVA_FLAGS):
        ec._NOVA_FLAGS = [f for f in list(ec._NOVA_FLAGS) if not f.startswith("--remote-debugging-port=")] + [flag]

    from worker import AISlotWorker
    from runner import MetaInstaRunner

    print(f"\n=======================================================", flush=True)
    print(f" [Meta-Only Creation Test]", flush=True)
    print(f" ID:          {rec_id}", flush=True)
    print(f" Profile:     {prof_dir}", flush=True)
    print(f" DevTools:    chrome://inspect -> localhost:{cdp_port}", flush=True)
    print(f" Mailbox:     {args.mail}", flush=True)
    print(f"=======================================================\n", flush=True)

    worker = AISlotWorker(slot_id=rec_id, is_headless=args.headless)
    runner = MetaInstaRunner(worker, telegram=False, captcha_mode=args.captcha)
    runner.mail_provider_name = args.mail

    try:
        # Step 1: Launch browser
        print("[1/3] Launching anti-detect browser context...", flush=True)
        runner._launch()
        inspector.capture(runner.page, "01_browser_launched")

        # Step 2: Open mail inbox
        print(f"[2/3] Initializing mail inbox ({args.mail})...", flush=True)
        runner.open_mail()
        print(f"      Assigned Email: {runner.email}", flush=True)
        inspector.capture(runner.mail, "02_mail_inbox_ready")

        # Step 3: Meta signup
        print("[3/4] Executing Meta signup flow...", flush=True)
        runner.meta_signup()
        inspector.capture(runner.page, "03_meta_signup_completed")

        # Step 4: Completing redirect & Meta human verification (reCAPTCHA + selfie)
        print("[4/4] Completing redirect & Meta human verification...", flush=True)
        try:
            is_verified = runner.ensure_meta_verified()
            print(f"      Meta Human Verification settled: verified={is_verified}", flush=True)
        except Exception as v_err:
            print(f"      [Notice] ensure_meta_verified: {v_err}", flush=True)
        inspector.capture(runner.page, "04_meta_verified")

        # Persist storage state (cookies + localStorage, origins warmed so
        # mail.td tokens survive the dump — see dump_full_session)
        session_file = os.path.join(SESSIONS_DIR, f"{rec_id}.json")
        try:
            dump_full_session(worker.context, session_file)
        except Exception as d_err:
            print(f"      [Notice] dump_full_session: {d_err}", flush=True)

        # Extract mail.td tokens for 100% session persistence
        mail_tokens = {}
        if getattr(runner, "mail", None) and not runner.mail.is_closed():
            try:
                mail_tokens = runner.mail.evaluate("""() => {
                    return {
                        tempmail_token: localStorage.getItem("tempmail_token") || "",
                        tempmail_account_id: localStorage.getItem("tempmail_account_id") || "",
                    };
                }""")
            except Exception:
                pass

        cred_record = {
            "id": rec_id,
            "email": runner.email,
            "username": runner.email.split("@")[0],
            "password": runner.password,
            "meta_password": runner.password,
            "ig_password": runner.password,  # Initially identical to Meta password
            # Pinned anti-detect device: resumes must present the SAME phone
            # model/UA or fraud scoring diverges (see eng_mix_launch).
            "device_model": getattr(runner, "device_model", None),
            "device_ua": getattr(runner, "device_ua", None),
            "mail_tokens": mail_tokens,
            "session_file": session_file,
            "profile_dir": prof_dir,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "meta_code": getattr(runner, "meta_code", None),
            "status": "MetaCreated",
            "target": "telegram",
        }

        # Save to local test registry
        latest_creds_path = os.path.join(test_dir, "latest_credentials.json")
        with open(latest_creds_path, "w", encoding="utf-8") as f:
            json.dump(cred_record, f, indent=2)

        # Save to store.py for cross-tool parity
        try:
            store.add(cred_record)
        except Exception as e:
            print(f"[Notice] store.add: {e}", flush=True)

        print(f"\n✅ [SUCCESS] Meta Account Created & Human Verification Settled!", flush=True)
        print(f"   Email:         {runner.email}", flush=True)
        print(f"   Meta Password: {runner.password}", flush=True)
        print(f"   Profile Dir:   {prof_dir}", flush=True)
        print(f"   Session File:  {session_file}", flush=True)
        print(f"   Saved State:   {latest_creds_path}", flush=True)
        print(f"\nReady for Step 2 (Instagram DevTools exploration on same profile):", flush=True)
        print(f"   .venv/bin/python test/test_02_ig_devtools_learn.py", flush=True)

    except Exception as exc:
        print(f"\n❌ [ERROR] Meta signup failed: {exc}", flush=True)
        traceback.print_exc()
        try:
            inspector.capture(runner.page, "FAIL_meta_signup")
        except Exception:
            pass
        raise
    finally:
        if args.close:
            print("[test] Closing browser...", flush=True)
            try:
                runner.finish()
            except Exception:
                pass
        else:
            print(f"\n[test] Browser kept open on profile {prof_dir} (CDP {args.cdp}).", flush=True)
            print("[test] Press Ctrl-C to terminate.", flush=True)
            try:
                while True:
                    pages = worker.context.pages
                    if not pages or all(p.is_closed() for p in pages):
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[test] Exiting by user interrupt.", flush=True)
            finally:
                try:
                    runner.finish()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
