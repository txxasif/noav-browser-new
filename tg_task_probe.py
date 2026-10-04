#!/usr/bin/env python3
"""tg_task_probe.py — single-lease task-availability probe (all bots).

Checks whether ``task`` is currently pickable on ``bot`` over MTProto without
locking or holding Telegram sessions: acquires an idle account non-blocking,
walks the registry button path (never presses Start — creates nothing, costs
nothing), and releases immediately.

Outputs single-line JSON:
  {"ok": true, "available": true, "reason": "ok", "tg_id": "tg_2"}
  {"ok": true, "available": false, "reason": "hidden", "tg_id": "tg_2"}
  {"ok": false, "busy": true, "error": "All Telegram profiles busy ..."}
"""
from __future__ import annotations

import argparse
import json
import os
import sys

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe task availability on a TG bot")
    ap.add_argument("--bot", default="taskly", help="bot id: taskly|paygo|fastpay")
    ap.add_argument("--task", default="", help="task label or id (as the dashboard sends it)")
    ap.add_argument("--level-timeout", type=float, default=8.0,
                    help="seconds to wait per menu level (default 8)")
    ap.add_argument("--tries", type=int, default=2,
                    help="menu-walk attempts (default 2, same as the worker)")
    args = ap.parse_args()

    from mtproto_bot import probe_task_availability  # noqa: E402
    result = probe_task_availability(args.bot, args.task,
                                     level_timeout=args.level_timeout,
                                     tries=args.tries)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
