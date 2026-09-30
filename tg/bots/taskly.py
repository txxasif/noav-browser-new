"""Taskly Bot — Meta -> IG -> 2FA/No-mail submit (creates accounts).

BOT MIGRATED 2026-09-30: @tasklyBux_bot → @Taskl1_bot (display "Taksly Bot").
The old handle is ToS-banned/dead; the operator's news channel (@tasklybux_news)
announced the new one.
"""
from __future__ import annotations

from tg.bots import register

register({
    "id": "taskly",
    "name": "Taksly Bot",
    "username": "Taskl1_bot",
    "kind": "mtproto+web",          # works over Telethon or Telegram Web
    "runner": "tg_coupled",         # pipelines/telegram/tg_coupled.py
    "gate": "none",                 # no channel/language gate
    "flows": ["2fa", "cookie_2fa", "native"],
    "tasks": ["🔥 Create Inst (No mail)", "📱 Create Inst (2FA)"],
    "creates_accounts": True,
    "balance": True,                # has a 💰 Balance menu
})
