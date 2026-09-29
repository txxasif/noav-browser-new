"""PayGo Bot — Meta -> IG -> cookie export -> submit (creates accounts)."""
from __future__ import annotations

from tg.bots import register

register({
    "id": "paygo",
    "name": "PayGo Bot",
    "username": "PayGoeasy_bot",
    "kind": "mtproto+web",
    "runner": "run_cookie_cycle",   # run_cookie_cycle.py
    "gate": "none",
    "flows": ["cookie"],
    "tasks": ["📱 Create Inst (Cookies)"],
    "creates_accounts": True,
    "balance": True,
})
