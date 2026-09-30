"""tg.common — shared Telegram helpers (buttons, gate, sessions, guards).

Pure utilities with no engine imports at module load. Telethon is imported
lazily inside the async helpers so importing ``tg.common`` never needs it.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unicodedata
from typing import Optional

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


# ---------------------------------------------------------------- text/match
def norm(text: str) -> str:
    """NFKC-fold + lowercase (FastPay's labels are Unicode-bold 𝗧𝗮𝘀𝗸)."""
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def match_button(buttons, want: str) -> Optional[str]:
    """The first button text whose normalized form contains ``want``."""
    w = norm(want)
    for row in buttons or []:
        for b in row:
            if w in norm(getattr(b, "text", b)):
                return getattr(b, "text", None)
    return None


def match_callback(buttons, data: bytes):
    for row in buttons or []:
        for b in row:
            if getattr(b, "data", None) == data:
                return b
    return None


# ---------------------------------------------------------------- sessions
def session_path(tg_id: str) -> str:
    from mtproto_bot import session_file
    return session_file(tg_id)


def api_credentials():
    from mtproto_bot import _api_credentials
    return _api_credentials()


def has_session(rec: dict) -> bool:
    from mtproto_bot import has_mtproto_session, session_file
    sess = rec.get("session_file")
    if not sess or not os.path.isfile(sess):
        sess = session_file(str(rec.get("id") or ""))
    return has_mtproto_session(sess)


# ---------------------------------------------------------------- bot driving
async def last_message(client, ent, limit: int = 1):
    """Newest message in the chat (or None)."""
    msgs = await client.get_messages(ent, limit=limit)
    return msgs[0] if msgs else None


async def click_text(client, ent, want: str, tries: int = 6, gap: float = 2.0):
    """Click the reply/inline button matching ``want`` on the newest message."""
    for _ in range(tries):
        m = await last_message(client, ent)
        if m and getattr(m, "buttons", None):
            for row in m.buttons:
                for b in row:
                    if norm(want) in norm(b.text):
                        await b.click()
                        await asyncio.sleep(3)
                        return True, await last_message(client, ent)
        await asyncio.sleep(gap)
    return False, await last_message(client, ent)


async def ensure_channels(client, ent, channels, log=print) -> bool:
    """Join each channel (by @username). Idempotent; returns True if all ok."""
    from telethon import functions
    ok = True
    for ch in channels or []:
        try:
            await client(functions.channels.JoinChannelRequest(channel=await client.get_entity(ch)))
            log(f"[tg] joined channel {ch}")
        except Exception as exc:  # already participant / private / flood
            log(f"[tg] channel {ch}: {exc}")
            ok = ok and ("already" in str(exc).lower() or "participant" in str(exc).lower())
        await asyncio.sleep(1)
    return ok


async def ensure_language(client, ent, lang: str = "en") -> bool:
    """Select the bot language if it asks (callback data ``setlang_<lang>``)."""
    m = await last_message(client, ent)
    if not (m and getattr(m, "buttons", None)):
        return True
    target = f"setlang_{lang}".encode()
    for row in m.buttons:
        for b in row:
            if getattr(b, "data", None) == target:
                await b.click()
                await asyncio.sleep(3)
                return True
    return True


async def gate_bot(client, ent, bot_id: str, log=print) -> dict:
    """Bring a bot from cold to its menu: /start -> join channels -> Verify ->
    language. Idempotent; safe to call every session.

    Returns ``{"ok": bool, "stage": str}``. Reads channels/language from the
    registry so a new bot needs no code change here.
    """
    from tg.registry import bot as bot_spec
    spec = bot_spec(bot_id) or {}
    channels = spec.get("required_channels") or []
    lang = spec.get("language") or "en"

    await client.send_message(ent, "/start")
    await asyncio.sleep(3)
    for _ in range(5):
        m = await last_message(client, ent)
        if not m:
            await asyncio.sleep(2)
            continue
        text = norm(getattr(m, "text", ""))
        btns = getattr(m, "buttons", None) or []
        # channel gate
        if "join our channels" in text or "must join" in text:
            await ensure_channels(client, ent, channels, log)
            v = match_callback(btns, b"verify_join")
            if v is not None:
                await v.click()
            await asyncio.sleep(3)
            continue
        # language gate
        if any(getattr(b, "data", None) == b"setlang_en" for row in btns for b in row):
            await ensure_language(client, ent, lang)
            continue
        return {"ok": True, "stage": "menu"}
    return {"ok": False, "stage": "gate"}


def run_sync(coro):
    """Run an async helper from sync code (fresh loop; no running loop here)."""
    return asyncio.run(coro)
