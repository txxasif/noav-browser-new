#!/usr/bin/env python3
"""ac_stay_probe.py — verify `_ac_section` does NOT step Back off the section root.

Observed bug (run #3, 13:58:49): right after a successful password change the
page was on `accountscenter.instagram.com/password_and_security` (rows: Contact
info / Change password / Two-factor authentication), yet `_ac_section` clicked
Back and dropped to the AC home, forcing ig_2fa_begin into a full
home -> Login-and-security -> 2FA re-navigation ("2FA bounced out" x2).

Direct URL is DIAGNOSTIC ONLY (pipeline never jumps URLs): we place the tab on
the section root, call `_ac_section` exactly as the pipeline does, and assert the
URL stays on the section root (no Back).
"""
from __future__ import annotations

import argparse
import os
import sys

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

REC = {
    "email": "7fc0dr@nqmo.com",
    "password": "NBmopt1tyoaK",
    "session_file": os.path.join(AI_DIR, "data", "sessions", "ai_1789804793950_e2e_once.json"),
    "profile_dir": os.path.join(AI_DIR, "profiles", "_ac_stay_probe"),
}
SECTION_URL = "https://accountscenter.instagram.com/password_and_security/"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    os.environ["INSTA_PROFILE_DIR"] = REC["profile_dir"]
    os.environ["KEEP_PROFILE"] = "1"

    w = AISlotWorker(slot_id="stay_probe", is_headless=args.headless)
    r = MetaInstaRunner(w, telegram=False)
    r.password = REC["password"]
    r.email = REC["email"]
    rc = 1
    try:
        r.resume_session(REC["session_file"], check_meta=False)
        p = r._ig_tab()
        p.goto(SECTION_URL, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        before = p.url
        print(f"[[STAY]] before={before}", flush=True)
        try:
            rows = p.evaluate("""() => {
                const vis = el => !!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);
                return Array.from(document.querySelectorAll('div[role=button],a,button'))
                    .filter(vis).map(e => (e.innerText||'').trim().split('\\n')[0]).filter(Boolean).slice(0,12);
            }""")
            print(f"[[STAY]] rows_on_page={rows}", flush=True)
        except Exception as exc:
            print(f"[[STAY]] rows err: {exc}", flush=True)

        # Exactly what ig_2fa_begin does first.
        r._ac_section("/password_and_security/", "Password and security")
        p = r._ig_tab()
        after = p.url
        print(f"[[STAY]] after={after}", flush=True)
        stayed = "password_and_security" in after
        print(f"[[STAY]] RESULT stayed_on_section={stayed}", flush=True)
        rc = 0 if stayed else 1
    except Exception as exc:
        print(f"[[STAY]] INCONCLUSIVE/FAILED: {exc}", flush=True)
        rc = 1
    finally:
        try:
            r.finish()
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
