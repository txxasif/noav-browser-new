"""tg.registry — single source of truth for the Telegram BOTS.

Wraps the existing registries (``ai_config.TG_BOTS`` for handles/peers,
``tg_tasks`` for tasks/flows) plus the per-BUILD selection manifest
(``tg/enabled_bots.json``, written by ``build_windows_dist.py --bots …``).

Adding a bot = one entry in ``ai_config.TG_BOTS`` + one in ``tg_tasks.TASKS``
(+ optionally ``tg/bots/<id>.py`` for bot-specific hooks). Nothing else.
"""
from __future__ import annotations

import json
import os

from ai_config import TG_BOTS  # noqa: E402
import tg_tasks  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(_HERE, "enabled_bots.json")


def all_bots():
    return list(TG_BOTS.keys())


def enabled_bots():
    """Bots this build ships. Falls back to all when no manifest (dev)."""
    try:
        with open(MANIFEST, "r", encoding="utf-8") as fh:
            ids = [b for b in (json.load(fh).get("bots") or []) if b in TG_BOTS]
        return ids or all_bots()
    except Exception:
        return all_bots()


def is_enabled(bot_id: str) -> bool:
    return str(bot_id) in enabled_bots()


def bot(bot_id: str):
    return TG_BOTS.get(str(bot_id))


def name(bot_id: str) -> str:
    return (bot(bot_id) or {}).get("name") or str(bot_id)


def username(bot_id: str) -> str:
    return (bot(bot_id) or {}).get("username") or ""


def peer_id(bot_id: str):
    return (bot(bot_id) or {}).get("peer_id")


def channels(bot_id: str):
    return list((bot(bot_id) or {}).get("required_channels") or [])


def language(bot_id: str) -> str:
    return (bot(bot_id) or {}).get("language") or "en"


def tasks(bot_id: str):
    return tg_tasks.offered(str(bot_id))


def task_ids(bot_id: str):
    return list((tg_tasks.TASKS.get(str(bot_id)) or {}).keys())


def flow_of(bot_id: str, task: str):
    """Flow tag for a (bot, task): '2fa' | 'cookie' | 'fastpay' | None."""
    tid, _ = tg_tasks.resolve(str(bot_id), task)
    if tid is None:
        return None
    return (tg_tasks.TASKS.get(str(bot_id), {}).get(tid) or {}).get("flow")


def summary():
    """Everything the dashboard needs to render the bot pickers."""
    out = []
    for b in enabled_bots():
        spec = bot(b) or {}
        out.append({
            "id": b,
            "name": spec.get("name") or b,
            "username": spec.get("username") or "",
            "peer_id": spec.get("peer_id"),
            "channels": channels(b),
            "language": language(b),
            "tasks": tasks(b),
            "flows": sorted({f for f in (flow_of(b, t) for t in (spec.get("tasks") or [])) if f}),
        })
    return out
