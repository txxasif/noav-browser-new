"""tg — Telegram manager package.

Layers
------
* :mod:`tg.common`   — shared utilities (normalize/match, Telethon helpers,
  channel-join + Verify gate, language select, message/button walking).
* :mod:`tg.registry` — single source of truth for the BOTS (id, handle, peer,
  required channels, tasks, flows) and which bots this BUILD ships.
* :mod:`tg.manager`  — lease + mutual-exclusion + readiness + balance; the API
  the dashboard talks to.
* :mod:`tg.bots.*`   — one thin descriptor per bot (taskly / paygo / fastpay).

Nothing here duplicates the engines: the Telegram Web bot stays in ``tg_bot.py``
and the MTProto (Telethon) bot stays in ``mtproto_bot.py``; the pool/lease store
stays in ``tg_accounts.py``. This package is the MANAGER layer over them.
"""
from __future__ import annotations

__all__ = ["common", "registry", "manager"]
