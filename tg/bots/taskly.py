"""Taskly Bot — Meta -> IG -> 2FA/No-mail submit (creates accounts)."""
from __future__ import annotations

from tg.bots import register

register({
    "id": "taskly",
    "name": "Taskly Bot",
    "username": "tasklyBux_bot",
    "kind": "mtproto+web",          # works over Telethon or Telegram Web
    "runner": "tg_coupled",         # pipelines/telegram/tg_coupled.py
    "gate": "none",                 # no channel/language gate
    "flows": ["2fa", "cookie_2fa", "native"],
    "tasks": ["🔥 Create Inst (No mail)", "📱 Create Inst (2FA)"],
    "creates_accounts": True,
    "balance": True,                # has a 💰 Balance menu
})
