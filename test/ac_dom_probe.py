#!/usr/bin/env python3
"""ac_dom_probe.py — DIAGNOSTIC ONLY. Direct-URL AC probe to inspect the real DOM.

Not part of the pipeline (the pipeline never direct-jumps URLs). Purpose: get
hard evidence for (a) whether an already-live profile's AC session works, (b)
what the Contact-information overlay's close control actually is, and (c)
whether closing it reveals the AC section list.
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

AC_HOME = "https://accountscenter.instagram.com/"
CONTACT_DIALOG = "https://accountscenter.instagram.com/youraccount/contact_points/?entrypoint=profile_page&is_from_dialog=true"


def dump(p, tag: str) -> None:
    print(f"\n[[PROBE]] ==== {tag} ====", flush=True)
    try:
        print(f"[[PROBE]] url={p.url}", flush=True)
        body = (p.inner_text("body") or "")
        print(f"[[PROBE]] body_head={body[:180]!r}", flush=True)
        print(f"[[PROBE]] has 'Login and security': {'login and security' in body.lower()}", flush=True)
        print(f"[[PROBE]] has 'Contact information': {'contact information' in body.lower()}", flush=True)
    except Exception as exc:
        print(f"[[PROBE]] body err: {exc}", flush=True)
    try:
        info = p.evaluate("""() => {
            const out = {buttons: [], closes: [], backs: []};
            const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            for (const el of document.querySelectorAll('button,div[role=button],a,[aria-label]')) {
                if (!vis(el)) continue;
                const al = (el.getAttribute('aria-label')||'').slice(0,40);
                const tx = (el.innerText||'').trim().slice(0,30);
                if (/close/i.test(al)) out.closes.push(al);
                if (/back/i.test(al)) out.backs.push(al);
                if (out.buttons.length < 25 && (tx||al)) out.buttons.push((al?('aria='+al+' ') : '')+('text='+tx));
            }
            return out;
        }""")
        print(f"[[PROBE]] close-ish controls: {info.get('closes')}", flush=True)
        print(f"[[PROBE]] back-ish controls: {info.get('backs')}", flush=True)
        print(f"[[PROBE]] visible buttons: {info.get('buttons')}", flush=True)
    except Exception as exc:
        print(f"[[PROBE]] dom err: {exc}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.path.join(AI_DIR, "profiles", "insta_e2e_once_1789803346"))
    args = ap.parse_args()
    os.environ["INSTA_PROFILE_DIR"] = args.profile
    os.environ["KEEP_PROFILE"] = "1"

    w = AISlotWorker(slot_id="ac_probe", is_headless=False)
    r = MetaInstaRunner(w, telegram=False)
    try:
        r._launch()
        print(f"[[PROBE]] cookies={sorted(set(r._ig_cookie_names()))}", flush=True)
        p = r._ig_tab()
        p.goto(AC_HOME, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        dump(p, "AC_HOME")
        p.goto(CONTACT_DIALOG, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        dump(p, "CONTACT_DIALOG(before)")
        print(f"\n[[PROBE]] _ac_leave_subpage -> {r._ac_leave_subpage(p)}", flush=True)
        p.wait_for_timeout(1500)
        dump(p, "AFTER _ac_leave_subpage")

        # The real assertion: from the (formerly wedged) overlay state, can we
        # now reach the password section via the normal in-app section search?
        print("\n[[PROBE]] now calling _ac_section(password_and_security)…", flush=True)
        try:
            r._ac_section("/password_and_security/", "Password and security")
            p = r._ig_tab()
            reached = r._ac_in_section((p.url or "").split("?")[0].rstrip("/"), "password_and_security")
            print(f"[[PROBE]] RESULT reached_password_section={reached} url={p.url}", flush=True)
        except Exception as exc:
            print(f"[[PROBE]] RESULT FAILED: {exc}", flush=True)
    finally:
        try:
            r.finish()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
