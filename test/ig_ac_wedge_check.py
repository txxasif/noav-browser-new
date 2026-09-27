#!/usr/bin/env python3
"""ig_ac_wedge_check.py — reproduce the AC "Contact information" wedge.

Scenario from the failed coupled run (2026-09-19): the email step calls
``_ac_section("/personal_info/contact_points/")`` which opens the Contact
information overlay (``.../youraccount/contact_points?is_from_dialog=true``);
the next step then calls ``_ac_section("/password_and_security/")`` while that
overlay is still up, finds no section row inside it, and hard-fails
"AC section unreachable".

This test drives that exact sequence against an ALREADY-LIVE profile (no new
account): open Contact info, then ask for Password and security, and assert we
land on the password section.

Usage:
    .venv/bin/python test/ig_ac_wedge_check.py [--profile DIR]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AI_DIR)
os.chdir(AI_DIR)
try:
    from ai_config import run as _engine_run

    _engine_run._point_playwright_at_browsers()
except Exception:
    pass

from worker import AISlotWorker  # noqa: E402
from runner import MetaInstaRunner  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.path.join(AI_DIR, "profiles", "insta_e2e_once_1789803346"))
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    os.environ["INSTA_PROFILE_DIR"] = args.profile
    os.environ["KEEP_PROFILE"] = "1"

    w = AISlotWorker(slot_id="wedge_check", is_headless=args.headless)
    r = MetaInstaRunner(w, telegram=False)

    def where(tag: str) -> None:
        try:
            p = r._ig_tab()
            print(f"[[WEDGE]] {tag}: url={p.url}", flush=True)
            try:
                print(f"[[WEDGE]] {tag}: in_password_section="
                      f"{r._ac_in_section((p.url or '').split('?')[0].rstrip('/'), 'password_and_security')}",
                      flush=True)
            except Exception:
                pass
        except Exception as exc:
            print(f"[[WEDGE]] {tag}: (no tab) {exc}", flush=True)

    rc = 1
    try:
        print(f"[[WEDGE]] launching profile {args.profile}", flush=True)
        r._launch()
        try:
            names = r._ig_cookie_names()
        except Exception:
            names = []
        print(f"[[WEDGE]] ig cookies: {sorted(set(names))}", flush=True)
        if "sessionid" not in set(names):
            print("[[WEDGE]] no sessionid in this profile — cannot test (pick a live profile).", flush=True)
            return 2

        print("[[WEDGE]] step 1: open Contact info (expected to open the overlay)…", flush=True)
        t0 = time.time()
        try:
            r._ac_section("/personal_info/contact_points/", "Contact info")
        except Exception as exc:
            print(f"[[WEDGE]] step 1 note (expected on alias mismatch): {exc}", flush=True)
        where("after_contact")
        print(f"[[WEDGE]] step 1 took {time.time() - t0:.1f}s", flush=True)

        print("[[WEDGE]] step 2: now ask for Password and security "
              "(the wedge point; fix must close the overlay and reach it)…", flush=True)
        t0 = time.time()
        try:
            r._ac_section("/password_and_security/", "Password and security")
            where("after_password")
            p = r._ig_tab()
            ok = r._ac_in_section((p.url or "").split("?")[0].rstrip("/"), "password_and_security")
            print(f"[[WEDGE]] RESULT: reached_password_section={ok} in {time.time() - t0:.1f}s", flush=True)
            rc = 0 if ok else 1
        except Exception as exc:
            print(f"[[WEDGE]] RESULT: FAILED — {exc}", flush=True)
            traceback.print_exc()
            rc = 1
    finally:
        try:
            r.finish()
            print("[[WEDGE]] closed cleanly", flush=True)
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
