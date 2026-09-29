"""FastPay2025 Bot — Instagram 2FA CREATE task (Meta -> IG -> 2FA -> paid).

Not a payout-only bot: selecting its task sends
``👤 Username`` + ``🔒 Password`` (the creds arrive in the message BEFORE the
``Please send the 2FA Key below`` prompt), then pays ৳3.0 on Confirm. So it
runs the same create flow as Taskly's "Create Inst (2FA)" (flow ``2fa``).

Gate (once per Telegram account): join the required channels -> Verify ->
select English.
"""
from __future__ import annotations

from tg.bots import register

register({
    "id": "fastpay",
    "name": "FastPay Bot",
    "username": "FastPay2025_bot",
    "kind": "mtproto+web",          # works over Telethon or Telegram Web
    "runner": "tg_coupled",         # pipelines/telegram/tg_coupled.py
    "gate": "channels_language",    # join channels + Verify + English
    "flows": ["2fa"],
    "tasks": ["Instagram 2FA"],
    "creates_accounts": True,
    "balance": True,                # has a 💰 Balance menu
})
