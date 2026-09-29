"""Per-bot descriptors — ONE module per bot.

These are the build-selectable units: ``build_windows_dist.py --bots a,b`` ships
only the chosen ``tg/bots/<id>.py`` files (and gates the dashboard). A bot's
runtime config still lives in ``ai_config.TG_BOTS`` + ``tg_tasks.TASKS``; this
module documents the bot's kind/runner/gate so the manager and build can reason
about it without loading the engine.
"""
from __future__ import annotations

BOTS = {}


def register(desc: dict):
    BOTS[desc["id"]] = desc
    return desc


def descriptors():
    return list(BOTS.values())


def get(bot_id: str):
    return BOTS.get(str(bot_id))


# Import each descriptor module defensively: a `--bots` build excludes the
# unselected `tg/bots/<id>.py`, so a missing module must NOT break the package.
for _mod in ("taskly", "paygo", "fastpay"):
    try:
        __import__("tg.bots." + _mod)
    except Exception:
        pass
