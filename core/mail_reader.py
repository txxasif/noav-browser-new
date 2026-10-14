"""Read a saved mailcf account's mail later, using its address and read token.

The token comes from ``account["mail_tokens"]["mailcf_token"]`` (saved by
``save_ai_result``). Mail is kept by the Worker for 15 days.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

from ai_config import Urls

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def mailcf_token_for(account: dict) -> str:
    """Return the saved read token for an account, or '' if it has none."""
    tokens = account.get("mail_tokens") or {}
    return tokens.get("mailcf_token", "") if isinstance(tokens, dict) else ""


def list_messages(email: str, token: str, timeout: int = 15) -> list[dict]:
    """All stored messages for an address, newest first. Raises on a bad token (HTTP 403)."""
    query = urllib.parse.urlencode({"email": email, "token": token})
    req = urllib.request.Request(f"{Urls.CF_MAIL_WORKER}/messages?{query}", headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace")).get("messages", [])


def retire_mailbox(email: str, timeout: int = 15) -> bool:
    """Kill an address (POST /retire): token, codes and mail are wiped and new mail is dropped.

    Returns False if the admin token is missing or the Worker rejects the call.
    """
    if not Urls.CF_MAIL_ADMIN_TOKEN:
        return False
    req = urllib.request.Request(
        f"{Urls.CF_MAIL_WORKER}/retire",
        data=json.dumps({"email": email}).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {Urls.CF_MAIL_ADMIN_TOKEN}",
            "User-Agent": _UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def latest_code(email: str, timeout: int = 15) -> Optional[str]:
    """Latest OTP code for an address (15-minute window), or None if none has arrived."""
    query = urllib.parse.urlencode({"email": email})
    req = urllib.request.Request(f"{Urls.CF_MAIL_WORKER}/?{query}", headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return str(data["code"]) if data.get("code") else None
