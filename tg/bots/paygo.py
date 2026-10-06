"""PayGo Bot — Meta -> IG -> cookie export -> submit (creates accounts)."""
from __future__ import annotations

from tg.bots import register

register({
    "id": "paygo",
    "name": "PayGo Bot",
    "username": "PayGoeasy_bot",
    "kind": "mtproto+web",
    "runner": "run_cookie_cycle",   # cookies drain; 2FA pool drain: run_paygo_pool_2fa_cycle
    "gate": "none",
    "flows": ["cookie", "paygo_pool_2fa"],
    "tasks": ["📱 Create Inst (Cookies)", "📱 Create Inst (2FA)"],
    "creates_accounts": True,
    "balance": True,
})
