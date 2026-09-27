#!/usr/bin/env python3
"""ig_add_email_probe.py — see how to add an EXTRA email to an Instagram account.

Copies an UNUSED account's saved session (so the original is untouched), opens
it, walks Instagram → Accounts Center → Personal details → Contact info, and
documents (screenshots + selectors) the "Add new contact → Add email" flow and
its verification-code step.

READ-ONLY-ish: it opens the Add-email form but NEVER submits, and never writes
the session back.

Usage:
    .venv/bin/python test/ig_add_email_probe.py --id ai_1789462225073_3 [--headless]
"""
from __future__ import annotations

import argparse
import os
import shutil
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

SHOTS = "/tmp/opencode/addemail"
os.makedirs(SHOTS, exist_ok=True)


def dump(p, tag: str) -> None:
    print(f"\n[[PROBE]] ==== {tag} ====", flush=True)
    try:
        print(f"[[PROBE]] url={p.url}", flush=True)
        print(f"[[PROBE]] body={(p.inner_text('body') or '')[:220]!r}", flush=True)
    except Exception as exc:
        print(f"[[PROBE]] body err: {exc}", flush=True)
    try:
        info = p.evaluate("""() => {
            const vis = el => !!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);
            const out = {buttons: [], inputs: []};
            for (const el of document.querySelectorAll('button,div[role=button],a,[role=link]')) {
                if (!vis(el)) continue;
                const t = (el.innerText||'').trim().split('\\n')[0].slice(0,40);
                if (t && out.buttons.length < 30) out.buttons.push(t);
            }
            for (const el of document.querySelectorAll('input')) {
                if (!vis(el)) continue;
                out.inputs.push({type: el.type, name: el.name, ph: el.placeholder, aria: el.getAttribute('aria-label'), im: el.inputMode});
            }
            return out;
        }""")
        print(f"[[PROBE]] buttons={info.get('buttons')}", flush=True)
        print(f"[[PROBE]] inputs={info.get('inputs')}", flush=True)
    except Exception as exc:
        print(f"[[PROBE]] dom err: {exc}", flush=True)
    try:
        p.screenshot(path=os.path.join(SHOTS, f"{tag}.png"))
        print(f"[[PROBE]] shot={SHOTS}/{tag}.png", flush=True)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="unused account id (has a live IG session)")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    src = os.path.join(AI_DIR, "data", "sessions", f"{args.id}.json")
    if not os.path.isfile(src):
        print(f"[[PROBE]] no session file: {src}", flush=True)
        return 2
    scratch = os.path.join(AI_DIR, "data", "sessions", f"_mailprobe_{args.id}.json")
    shutil.copy(src, scratch)
    prof = os.path.join(AI_DIR, "profiles", f"_mailprobe_{args.id}")
    shutil.rmtree(prof, ignore_errors=True)
    os.environ["INSTA_PROFILE_DIR"] = prof
    os.environ["KEEP_PROFILE"] = "1"

    from worker import AISlotWorker
    from runner import MetaInstaRunner

    w = AISlotWorker(slot_id="mailprobe", is_headless=args.headless)
    r = MetaInstaRunner(w, telegram=False)
    rc = 1
    try:
        r.resume_session(scratch, check_meta=False)
        p = r._ig_tab()
        print(f"[[PROBE]] cookies={sorted(set(r._ig_cookie_names()))}", flush=True)
        if "sessionid" not in r._ig_cookie_names():
            print("[[PROBE]] no sessionid — pick another account", flush=True)
            return 2

        # Walk to Contact info via the SAME in-app route the pipeline uses.
        print("[[PROBE]] opening Contact info via in-app AC clicks…", flush=True)
        try:
            r._ac_section("/personal_info/contact_points/", "Contact info")
        except Exception as exc:
            print(f"[[PROBE]] contact-info note: {exc}", flush=True)
        time.sleep(2)
        dump(p, "01_contact_info")

        # Open the Add-email form (do NOT submit).
        for label in ("Add new contact", "Add contact", "Add email", "Add email address"):
            try:
                el = p.get_by_text(label, exact=False).first
                if el.count() and el.is_visible():
                    print(f"[[PROBE]] clicking '{label}'…", flush=True)
                    el.click()
                    time.sleep(2.5)
                    dump(p, "02_add_email_form")
                    break
            except Exception:
                pass
        rc = 0
    except Exception as exc:
        print(f"[[PROBE]] FAILED: {exc}", flush=True)
    finally:
        try:
            r.finish()
        except Exception:
            pass
        # Never leave a scratch session/profile behind.
        try:
            os.remove(scratch)
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
