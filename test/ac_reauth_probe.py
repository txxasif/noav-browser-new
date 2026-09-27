#!/usr/bin/env python3
"""ac_reauth_probe.py — verify `_ac_reauth` short-circuits on the Change-password form.

Observed bug (run #4): the already-open Change-password form (3 password inputs)
was mistaken for a re-auth prompt, so `_ac_reauth` filled its Current-password
field and pressed Enter, and the caller's retry loop ran it 5x (~13s dead).

Direct URL is DIAGNOSTIC ONLY. We place the tab on the change-password form,
assert `_ac_pw_form_open()` is True, then time `_ac_reauth()` and assert it does
NOT fill/submit (returns fast).
"""
from __future__ import annotations

import os
import sys
import time

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
    "session_file": os.path.join(AI_DIR, "data", "sessions", "ai_1789805562615_e2e_once.json"),
    "profile_dir": os.path.join(AI_DIR, "profiles", "_ac_reauth_probe"),
}
FORM_URL = "https://accountscenter.instagram.com/password_and_security/password/change/"


def main() -> int:
    os.environ["INSTA_PROFILE_DIR"] = REC["profile_dir"]
    os.environ["KEEP_PROFILE"] = "1"
    w = AISlotWorker(slot_id="reauth_probe", is_headless=False)
    r = MetaInstaRunner(w, telegram=False)
    r.password = REC["password"]
    r.email = REC["email"]
    rc = 1
    try:
        r.resume_session(REC["session_file"], check_meta=False)
        p = r._ig_tab()
        p.goto(FORM_URL, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        print(f"[[REAUTH]] url={p.url}", flush=True)
        try:
            n = p.locator('input[type="password"]').count()
        except Exception:
            n = -1
        form_open = r._ac_pw_form_open(p)
        print(f"[[REAUTH]] password_inputs={n} form_open={form_open}", flush=True)

        t0 = time.time()
        solved = r._ac_reauth(p, password=REC["password"])
        dt = time.time() - t0
        print(f"[[REAUTH]] _ac_reauth returned={solved} in {dt:.2f}s", flush=True)
        # With the form open and a fresh password, the guard must short-circuit.
        ok = form_open and (solved is False) and dt < 2.0
        print(f"[[REAUTH]] RESULT guard_short_circuit={ok} (expect True/False/<2s)", flush=True)
        rc = 0 if ok else 1
    except Exception as exc:
        print(f"[[REAUTH]] INCONCLUSIVE/FAILED: {exc}", flush=True)
    finally:
        try:
            r.finish()
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
