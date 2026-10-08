"""mtproto_client.py — low-level Telethon (MTProto) transport/session/login layer.

Split out of ``mtproto_bot.py`` as a **pure code move** (no behaviour change).
It holds the session-file helpers, api credentials, per-account device identity,
Telethon client construction/hardening and the dashboard login flow.

``mtproto_bot`` re-exports every name defined here for back-compat, so
``from mtproto_bot import session_file`` (and friends) keep working.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_config import DATA_DIR  # noqa: E402
from tg_fingerprint import for_profile  # noqa: E402

TG_SESSIONS_DIR = os.path.join(DATA_DIR, "tg_sessions")
os.makedirs(TG_SESSIONS_DIR, exist_ok=True)

# Deterministic per-account device identity (seeded by the account id) so two
# MTProto sessions never present the same app/device pair (invariant 25).
_APP_VERSIONS = ("4.16.8", "4.15.2", "4.14.12", "4.13.1")
_SYS_VERSIONS = {
    "Windows": ("Windows 10", "Windows 11"),
    "macOS": ("macOS 13.5", "macOS 14.2"),
    "Linux": ("Linux", "Ubuntu 22.04"),
}
_DEVICE_MODELS = ("Desktop", "Desktop", "Desktop", "Laptop")


def session_file(tg_id: str) -> str:
    """Path of the Telethon session file for a pool id (``tg_4`` → data/...)."""
    return os.path.join(TG_SESSIONS_DIR, f"{tg_id}.session")


def has_mtproto_session(path: str) -> bool:
    """True when a usable Telethon session file exists."""
    try:
        return bool(path) and os.path.isfile(path)
    except Exception:
        return False


def _api_credentials():
    """(api_id, api_hash) from env or data/tg_mtproto.json. Raises when absent."""
    aid = os.environ.get("TG_API_ID")
    ah = os.environ.get("TG_API_HASH")
    if not (aid and ah):
        cfg = os.path.join(DATA_DIR, "tg_mtproto.json")
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as fh:
                    d = json.load(fh) or {}
                aid = aid or d.get("api_id")
                ah = ah or d.get("api_hash")
            except Exception:
                pass
    if not (aid and ah):
        raise RuntimeError(
            "MTProto needs api_id/api_hash. Set TG_API_ID/TG_API_HASH, or write "
            'data/tg_mtproto.json {"api_id":..,"api_hash":..}. Get them free at '
            "https://my.telegram.org → API development tools.")
    return int(aid), str(ah)


def _device_identity(tg_id: str) -> dict:
    """Stable Telethon device fields for this account (distinct across accounts)."""
    ident = for_profile(tg_id)
    os_name = ident.get("os") or "Windows"
    import hashlib
    hh = int(hashlib.sha256(str(tg_id).encode("utf-8")).hexdigest(), 16)
    sys_ver = _SYS_VERSIONS.get(os_name, _SYS_VERSIONS["Windows"])[(hh // 31) % 2]
    return {
        "device_model": _DEVICE_MODELS[(hh // 41) % len(_DEVICE_MODELS)],
        "system_version": sys_ver,
        "app_version": _APP_VERSIONS[(hh // 53) % len(_APP_VERSIONS)],
        "lang_code": "en",
        "system_lang_code": "en-US",
    }


# Session files this PROCESS currently holds open. SQLite cannot resolve a lock
# whose holder is ourselves: busy_timeout waits, then fails anyway, because the
# holder is the one blocked. Tracking it lets us name the real cause instead of
# retrying a self-deadlock (observed 2026-10-01: a slot leased tg_2 and the same
# worker built a second client for it -> "bot start failed: database is locked").
_OPEN_SESSIONS: set = set()


def _make_client(tg_id: str, sess_path: str):
    """Create a sync Telethon client bound to this thread's event loop."""
    import asyncio
    from telethon.sync import TelegramClient
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        loop = None
    api_id, api_hash = _api_credentials()
    os.makedirs(os.path.dirname(sess_path) or ".", exist_ok=True)
    # catch_up=False: do NOT fetch the update backlog on connect. A session that
    # has been idle replays thousands of stale updates, which Telethon logs as
    # "Server sent a very old message … ignoring" and then aborts with
    # "Security error … Too many messages had to be ignored consecutively"
    # (observed 2026-09-21). We read history explicitly via get_messages(), so
    # the update stream buys us nothing and only risks dropping the connection.
    client = TelegramClient(sess_path, api_id, api_hash, catch_up=False,
                            **_device_identity(tg_id))
    # Telethon opens its session store with sqlite3's DEFAULT busy timeout (0),
    # so ANY concurrent writer — the PayGo orchestrator probing the same account,
    # a balance check, a pool lease handed to a second slot, or an orphaned engine
    # from a previous run — makes the next write fail INSTANTLY with
    # "database is locked" instead of waiting its turn (observed 2026-10-01:
    # "bot boot: bot start failed: database is locked" the instant a slot leased
    # tg_5). SQLite serialises writers; the correct behaviour is to WAIT for the
    # holder to finish, which is exactly what busy_timeout does. WAL additionally
    # lets readers proceed while a write is in flight.
    _harden_session_db(client)
    _OPEN_SESSIONS.add(os.path.abspath(sess_path))
    # Pin the connection loop so Playwright's sync API (which resets the
    # process's running loop via asyncio._set_running_loop) cannot make Telethon
    # build a DIFFERENT loop later — that raises "The asyncio event loop must
    # not change after connection". _pin_loop() re-asserts this on every
    # connect/auth-check.
    try:
        client._pinned_loop = loop
    except Exception:
        pass
    return client


def _pin_loop(client) -> None:
    """Re-assert ``client``'s connection loop on the CURRENT thread.

    Playwright's sync API changes the process asyncio loop; the pooled bot's
    owner thread then has NO current loop, Telethon builds a fresh one, and
    every request fails with "The asyncio event loop must not change after
    connection". Re-setting the pinned loop before each connect/auth-check keeps
    the running loop identical to the one the client connected on.
    """
    try:
        import asyncio
        lp = getattr(client, "_pinned_loop", None)
        if lp is not None:
            asyncio.set_event_loop(lp)
    except Exception:
        pass


def _harden_session_db(client, timeout_s: float = 30.0) -> None:
    """Give Telethon's session SQLite a busy timeout + WAL (best effort).

    NOTE on the attribute name: Telethon's ``SQLiteSession`` stores its handle
    as ``._conn`` (private) and creates it LAZILY inside ``_cursor()``. An
    earlier version of this helper read ``.conn`` -- which does not exist -- so
    ``getattr(..., None)`` returned None and the whole call was a silent NO-OP.
    That is why "database is locked" persisted after the "fix". Resolve the
    handle defensively (both spellings) and FORCE creation via ``_cursor()``
    when it is still None, so the PRAGMAs always land.
    """
    try:
        sess = getattr(client, "session", None)
        if sess is None:
            return
        conn = getattr(sess, "_conn", None) or getattr(sess, "conn", None)
        if conn is None:
            # Lazy-created: ask the session for a cursor, which opens the
            # connection as a side effect.
            try:
                sess._cursor()
            except Exception:
                pass
            conn = getattr(sess, "_conn", None) or getattr(sess, "conn", None)
        if conn is None:
            return
        secs = int(timeout_s)
        conn.execute(f"PRAGMA busy_timeout={secs * 1000}")
        # WAL is persistent per-database; failures here are harmless (e.g. a
        # read-only mount), so they must never abort the connect.
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
    except Exception:
        pass


def _reply_button_texts(msg) -> list:
    """Texts of a message's reply-keyboard buttons (empty list when none)."""
    out = []
    try:
        rm = getattr(msg, "reply_markup", None)
        for row in (getattr(rm, "rows", None) or []):
            for b in (getattr(row, "buttons", None) or []):
                t = (getattr(b, "text", "") or "").strip()
                if t:
                    out.append(t)
    except Exception:
        pass
    return out


def _inline_buttons(msg) -> list:
    """Inline buttons as (text, data) pairs (Taskly uses reply keyboards)."""
    out = []
    try:
        for b in (getattr(msg, "buttons", None) or []):
            for row in b:
                out.append(((row.text or "").strip(),
                            getattr(row, "data", None), row))
    except Exception:
        pass
    return out


class MtprotoNeedsPassword(Exception):
    """Raised when the account has 2FA enabled and no password was supplied."""


def _session_is_foreign(tg_id, phone, sess) -> bool:
    """True when ``sess`` is authorized as a DIFFERENT phone than ``phone``.

    A leftover session file is a footgun: Telethon's ``sign_in`` is a NO-OP on
    an already-authorized client, so adding a new account into a reused id would
    silently adopt the OLD account (observed 2026-09-21: an orphaned
    ``tg_1.session`` held the previous account). The caller deletes the file so
    the login starts clean.
    """
    if not sess or not os.path.isfile(sess):
        return False
    want = re.sub(r"\D", "", str(phone or ""))
    if not want:
        return False
    try:
        c = _make_client(tg_id, sess)
        try:
            c.connect()
            if not c.is_user_authorized():
                return False
            me = c.get_me()
            cur = re.sub(r"\D", "", str(getattr(me, "phone", "") or ""))
            return bool(cur) and cur != want
        finally:
            try:
                c.disconnect()
            except Exception:
                pass
    except Exception:
        return False


def send_login_code(tg_id, phone, session_path=None):
    """Step 1 of the dashboard MTProto login: request a login code.

    Telethon's interactive ``start()`` can't be used from the dashboard (the
    code arrives asynchronously and the form has to collect it), so the flow is
    split. Returns ``{"phone_code_hash": ...}``, which the caller MUST pass back
    to :func:`complete_login`.
    """
    from telethon.errors import FloodWaitError, PhoneNumberInvalidError

    sess = session_path or session_file(tg_id)
    # Never reuse a session that belongs to a different account.
    if _session_is_foreign(tg_id, phone, sess):
        for f in (sess, sess + "-journal"):
            try:
                os.remove(f)
            except Exception:
                pass

    client = _make_client(tg_id, sess)
    try:
        client.connect()
        sent = client.send_code_request(str(phone).strip())
        return {"phone_code_hash": sent.phone_code_hash,
                "type": type(sent.type).__name__}
    except PhoneNumberInvalidError:
        raise RuntimeError("Telegram rejected that phone number (use +countrycode…)")
    except FloodWaitError as exc:
        raise RuntimeError(f"Telegram asked to wait {getattr(exc, 'seconds', '?')}s before another code")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def complete_login(tg_id, phone, code, phone_code_hash, password=None,
                   session_path=None, label=None, proxy=None):
    """Step 2: sign in with the code (+ 2FA password) and register the pool record.

    Raises :class:`MtprotoNeedsPassword` when the account has 2FA and the caller
    did not supply a password, so the UI can prompt and retry.
    """
    from telethon.errors import (SessionPasswordNeededError, PhoneCodeInvalidError,
                                 PhoneCodeExpiredError, PasswordHashInvalidError,
                                 FloodWaitError)
    from tg_accounts import tg_manager  # local import avoids an import cycle

    sess = session_path or session_file(tg_id)
    client = _make_client(tg_id, sess)
    try:
        client.connect()
        try:
            client.sign_in(phone=str(phone).strip(), code=str(code).strip(),
                           phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise MtprotoNeedsPassword()
            try:
                client.sign_in(password=str(password))
            except PasswordHashInvalidError:
                raise RuntimeError("Wrong 2FA password")
        me = client.get_me()
    except PhoneCodeInvalidError:
        raise RuntimeError("Invalid login code")
    except PhoneCodeExpiredError:
        raise RuntimeError("Login code expired — request a new one")
    except FloodWaitError as exc:
        raise RuntimeError(f"Telegram asked to wait {getattr(exc, 'seconds', '?')}s")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

    if me is None:
        raise RuntimeError("Login did not return an account (code rejected?)")

    name = (getattr(me, "first_name", "") or "").strip()
    rec = tg_manager.upsert_mtproto(
        tg_id, sess, label=label or f"TG {tg_id} · MTProto",
        name=name or None, phone=getattr(me, "phone", None),
        user_id=getattr(me, "id", None), proxy=proxy)
    return rec
