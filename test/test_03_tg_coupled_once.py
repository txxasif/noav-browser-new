#!/usr/bin/env python3
"""test/test_03_tg_coupled_once.py — ONE coupled Telegram cycle, timed.

Runs exactly one ``run_tg_coupled_cycle`` (Meta -> TG task creds -> IG join ->
password -> 2FA key -> bot code -> confirm -> register) and exits, whichever
way it resolves.

Why not ``worker.py --coupled --target 1``? That loop retries on failure and
keeps minting fresh Meta accounts until one succeeds, which burns accounts and
buries the first failure. A scoped validation wants exactly one attempt.

Visible by default (is_headless=False): captcha/selfie need a real window and
the run must be allowed to close cleanly so the IG ``sessionid`` cookie is
re-dumped (a killed browser loses it — AGENTS.md #17).

Usage:
    .venv/bin/python test/test_03_tg_coupled_once.py [--tg-bot taskly|paygo|both]
        [--task "Create Inst (No mail)"] [--headless] [--mail-provider mailtd]
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import traceback

AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AI_DIR)
os.chdir(AI_DIR)

# Point Playwright at the bundled browsers before any launch (AGENTS.md #15).
try:
    from ai_config import run as _engine_run

    _engine_run._point_playwright_at_browsers()
except Exception:
    pass

from worker import AISlotWorker  # noqa: E402
from pipelines.telegram import tg_worker  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="One-shot coupled Telegram cycle")
    ap.add_argument("--task", default=None, help="Taskly task (default: engine TG_DEFAULT_TASK)")
    ap.add_argument("--tg-bot", default="both", choices=("both", "taskly", "paygo", "fastpay"))
    ap.add_argument("--captcha-mode", default="extension", choices=("extension", "audio"))
    ap.add_argument("--mail-provider", default="mailtd")
    ap.add_argument("--slot", default="e2e_once")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--add-email", action="store_true",
                    help="extra step: after 2FA, add a fresh mail.td email before registering")
    args = ap.parse_args()

    stop = threading.Event()
    t0 = time.monotonic()
    print(
        f"[[E2E]] start slot={args.slot} headless={args.headless} "
        f"ui_mode={os.environ.get('INSTA_UI_MODE', 'new')} bot={args.tg_bot}",
        flush=True,
    )

    ok = False
    detail = None
    try:
        ok, detail = tg_worker.run_tg_coupled_cycle(
            AISlotWorker,
            slot_id=args.slot,
            is_headless=args.headless,
            tg_task=args.task,
            tg_bot=args.tg_bot,
            captcha_mode=args.captcha_mode,
            mail_provider=args.mail_provider,
            add_email=args.add_email,
            stop_event=stop,
        )
    except Exception as exc:  # noqa: BLE001 — report, never mask
        traceback.print_exc()
        detail = f"uncaught: {exc}"
    finally:
        print(
            f"[[E2E]] done ok={ok} detail={detail!r} elapsed={time.monotonic() - t0:.1f}s",
            flush=True,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
