"""Telegram Bot Submission Statistics Tracker.

Tracks submission counters per bot (FastPay, Taskly, PayGo) in `data/tg_stats.json`
without dumping full account records into the Meta/Instagram creator inventory.
"""

import json
import os
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
STATS_FILE = os.path.join(DATA_DIR, "tg_stats.json")


def get_stats() -> dict:
    """Read the current stats or return zeroed defaults."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"total": 0, "submitted": 0, "taskly": 0, "paygo": 0, "fastpay": 0,
            "taskly2fa": 0, "fastpay2fa": 0, "paygo_pool": 0, "paygo2fa": 0}


def record_submission(bot_name: str) -> dict:
    """Atomically increment the submission count for the given bot."""
    os.makedirs(DATA_DIR, exist_ok=True)
    b = (bot_name or "taskly").strip().lower()
    stats = get_stats()

    stats[b] = stats.get(b, 0) + 1
    stats["submitted"] = stats.get("submitted", 0) + 1
    stats["total"] = stats.get("total", 0) + 1
    stats["last_submitted_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    tmp = f"{STATS_FILE}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATS_FILE)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

    return stats
