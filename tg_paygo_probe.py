#!/usr/bin/env python3
"""tg_paygo_probe.py — Fast, non-blocking PayGo stock & countdown probe.

Checks PayGoBot availability over MTProto without locking or holding Telegram
sessions. Grabs an idle account, reads the hourly stock counter, and releases
immediately in seconds.

Outputs single-line JSON:
  {"ok": true, "stock": 0, "max_stock": 5700, "available": false,
   "wait_seconds": 850, "tg_id": "tg_2"}
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)

from mtproto_bot import MtprotoTasklyBot, session_file  # noqa: E402
from tg_accounts import tg_manager  # noqa: E402


def compute_seconds_until_next_hour() -> int:
    """Calculate seconds until the next :00 clock hour rollover."""
    now = datetime.datetime.now()
    next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    diff = int((next_hour - now).total_seconds())
    return max(10, diff)


def probe_paygo(timeout: float = 0.0) -> dict:
    """Probe PayGo stock using an idle Telegram account. Never holds the lease."""
    if not tg_manager.usable():
        return {"ok": False, "error": "No usable Telegram accounts in pool"}

    # Acquire an idle account non-blocking (0s wait — never block active workers)
    tg_acct = tg_manager.acquire(timeout=0.0, bot="paygo_probe")
    if not tg_acct:
        # All accounts busy: calculate countdown to next hour rollover without disturbing workers
        wait_sec = compute_seconds_until_next_hour()
        return {
            "ok": True,
            "busy_skip": True,
            "stock": None,
            "available": False,
            "wait_seconds": wait_sec,
            "note": "All TG accounts currently busy; checking based on hourly clock rollover."
        }

    tg_id = tg_acct["id"]
    # Stamp OUR pid on the lease. The orchestrator caps this probe at 30s and
    # SIGKILLs on timeout, which skips the release in `finally` — leaving the
    # account "BUSY - PAYGO_PROBE" with no owner. Recording the pid lets
    # tg_manager.reclaim_stale() settle such a lease IMMEDIATELY (owner gone)
    # instead of waiting out a TTL, which is what wedged tg_2/tg_3.
    try:
        tg_manager._reload()
        for _a in tg_manager.accounts:
            if _a.get("id") == tg_id:
                _a["probe_pid"] = os.getpid()
                break
        tg_manager.save()
    except Exception:
        pass
    bot = None
    stock = None
    max_stock = 5700
    wait_sec = None

    try:
        sess_path = session_file(tg_id)
        bot = MtprotoTasklyBot(
            session_path=sess_path,
            tg_id=tg_id,
            bot_target="paygo",
            log=lambda *_: None
        )
        bot.start()
        bot.reset_to_main_menu()
        bot.choose_task("📱 Create Inst (Cookies)")

        # Inspect newest incoming messages from PayGo
        texts = bot._recent_texts(5)
        combined = "\n".join(texts)

        # 1. Parse stock: "Available this hour: 0/5700"
        m_stock = re.search(r"Available this hour:\s*(\d+)/(\d+)", combined, re.IGNORECASE)
        if m_stock:
            stock = int(m_stock.group(1))
            max_stock = int(m_stock.group(2))

        # 2. Parse explicit limit wait: "Next execution will be available in 14 min."
        m_wait_min = re.search(r"available in\s*(\d+)\s*min", combined, re.IGNORECASE)
        m_wait_sec = re.search(r"available in\s*(\d+)\s*sec", combined, re.IGNORECASE)

        if m_wait_min:
            wait_sec = int(m_wait_min.group(1)) * 60
        elif m_wait_sec:
            wait_sec = int(m_wait_sec.group(1))
        else:
            # Fall back to clock rollover to next hour
            wait_sec = compute_seconds_until_next_hour()

        # Available if stock > 0 and no limit notice
        is_limit = "limit is reached" in combined.lower() or (stock is not None and stock == 0)
        available = (stock is not None and stock > 0) and not is_limit

        return {
            "ok": True,
            "stock": stock,
            "max_stock": max_stock,
            "available": bool(available),
            "wait_seconds": wait_sec or compute_seconds_until_next_hour(),
            "tg_id": tg_id,
            "checked_at": int(time.time()),
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "tg_id": tg_id,
            "wait_seconds": compute_seconds_until_next_hour()
        }
    finally:
        if bot:
            try:
                bot.close()
            except Exception:
                pass
        # CRITICAL: Always immediately release the TG account back to the pool
        try:
            tg_manager.release(tg_id, ok=True, count=False)
        except Exception:
            pass


def main():
    timeout = 0.0
    for i, arg in enumerate(sys.argv):
        if arg == "--timeout" and i + 1 < len(sys.argv):
            try:
                timeout = float(sys.argv[i + 1])
            except Exception:
                pass
    res = probe_paygo(timeout=timeout)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
