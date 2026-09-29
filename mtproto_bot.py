"""mtproto_bot.py — Telethon (MTProto) submitter backend.

Why this exists
---------------
The Telegram submitter drives ``web.telegram.org/a/`` in a full Chromium
(``tg_bot.py``). That costs ~300 MB per account, caps the warm pool
(``TG_WARM_MAX``), and is subject to Telegram's *web*-client session
heuristics — several web logins from one IP and machine fingerprint get
correlated and revoked (AGENTS invariant 25: adding a 4th profile logged
``tg_3`` out, which is what caps the pool at ~3 live sessions).

This module talks MTProto directly with **Telethon** — the same protocol every
official Telegram client speaks — so there is no browser, no DOM, and no web
session ceiling. ~20 MB per account instead of ~300 MB, so the whole pool can
run concurrently on one machine.

It is **additive**: ``tg_bot.py`` (Telegram Web) is untouched and stays the
default. A pool record opts in with ``"mode": "mtproto"`` and a
``"session_file"``; everything else (leasing, task window, verdict parsing,
retries) is shared.

Contract
--------
``MtprotoTasklyBot`` / ``MtprotoPooledBot`` implement the exact method surface
the worker uses (see ``tg_bot.PooledTelegramBot``)::

    start() / open(), logged_in(), open_bot(), choose_task(task),
    start_task(), submit_2fa_key(key, allow_local_fallback=...),
    submit_cookie(cookie, timeout=...),
    mark_registered(), reset_to_main_menu(timeout=...), cancel_task(),
    close(ok=...)

THREADING INVARIANT (observed 2026-09-27): Telethon-sync calls made on a
thread that runs Playwright return UNawaited coroutines — ``connect()``
never connects, ``get_messages()`` yields nothing — so every downstream
read fails as "no Balance key" with zero exceptions. Never call raw
``MtprotoTasklyBot``/``tg_balance.check_bot`` on the browser thread;
use ``MtprotoPooledBot`` (owner thread) or a dedicated thread with a
clean event loop.

Verdict classification is reused verbatim from ``tg_bot.classify_report_reply``
(rejection-first, NEW reply only) — only the transport changes.

Setup
-----
1. Get a free ``api_id`` / ``api_hash`` at https://my.telegram.org
   (API development tools), then either::

       export TG_API_ID=123456
       export TG_API_HASH=abcdef0123456789abcdef0123456789

   or write ``data/tg_mtproto.json``::

       {"api_id": 123456, "api_hash": "abcdef..."}

2. Log in each account once::

       .venv/bin/python tg_login_mtproto.py --id tg_4

   The session lands in ``data/tg_sessions/<id>.session`` and the pool record
   is created/updated with ``"mode": "mtproto"``.
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_config import DATA_DIR, TG_BOTS, TG_DEFAULT_TASK  # noqa: E402
from tg_bot import classify_report_reply  # noqa: E402
from tg_fingerprint import for_profile  # noqa: E402
# NFKC button matching: FastPay renders its menu in Unicode math-bold
# (𝗧𝗮𝘀𝗸 / 𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺), which plain ``.lower()`` never turns into ASCII, so
# every button comparison below goes through ``normalize``. It is a no-op for
# Taskly/PayGo's plain-ASCII menus.
from tg_tasks import normalize as _norm_btn  # noqa: E402

TG_SESSIONS_DIR = os.path.join(DATA_DIR, "tg_sessions")
os.makedirs(TG_SESSIONS_DIR, exist_ok=True)

# Cancellation / TTL markers — a credential block is only valid AFTER the last
# one of these (mirrors tg_bot.TelegramTasklyBot.start_task; a stale task's
# Login/Password must never be submitted as fresh).
_CANCEL_RES = ("action cancelled", "action canceled", "time's up", "time’s up",
               "task cancelled", "task canceled", "please select a task")

# Register-key candidates (reply keyboard), tried in order. NEVER Cancel/Back/
# Return/Menu/Stop/Balance (invariant 23).
_REGISTER_LABELS = ("account registered", "register", "register account",
                    "confirm registration", "confirm", "done")
_REGISTER_BAD = ("cancel", "back", "return", "menu", "stop", "balance")

# Deterministic per-account device identity (seeded by the account id) so two
# MTProto sessions never present the same app/device pair (invariant 25).
_APP_VERSIONS = ("4.16.8", "4.15.2", "4.14.12", "4.13.1")
_SYS_VERSIONS = {
    "Windows": ("Windows 10", "Windows 11"),
    "macOS": ("macOS 13.5", "macOS 14.2"),
    "Linux": ("Linux", "Ubuntu 22.04"),
}
_DEVICE_MODELS = ("Desktop", "Desktop", "Desktop", "Laptop")

# Random IG first names for bots that issue no name (FastPay sends only
# Username/Password). Kept plain ASCII so the IG onboarding field accepts it.
_FIRST_NAMES = (
    "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Lucas", "Mia",
    "Ethan", "Sofia", "Mason", "Isla", "Leo", "Nora", "Ryan", "Zoe",
    "Adam", "Lily", "Omar", "Sara", "Daniel", "Ella", "Marco", "Nina",
)


def _random_first_name() -> str:
    import random
    return random.choice(_FIRST_NAMES)


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


def _make_client(tg_id: str, sess_path: str):
    """Create a sync Telethon client bound to this thread's event loop."""
    import asyncio
    from telethon.sync import TelegramClient
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass
    api_id, api_hash = _api_credentials()
    os.makedirs(os.path.dirname(sess_path) or ".", exist_ok=True)
    # catch_up=False: do NOT fetch the update backlog on connect. A session that
    # has been idle replays thousands of stale updates, which Telethon logs as
    # "Server sent a very old message … ignoring" and then aborts with
    # "Security error … Too many messages had to be ignored consecutively"
    # (observed 2026-09-21). We read history explicitly via get_messages(), so
    # the update stream buys us nothing and only risks dropping the connection.
    return TelegramClient(sess_path, api_id, api_hash, catch_up=False,
                          **_device_identity(tg_id))


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


class MtprotoTasklyBot:
    """MTProto (Telethon) equivalent of ``tg_bot.TelegramTasklyBot``."""

    def __init__(self, session_path=None, bot_target="taskly", bot_name=None,
                 headless=True, log=print, tg_id=None):
        if not session_path and tg_id:
            session_path = session_file(tg_id)
        if not session_path:
            raise RuntimeError("MtprotoTasklyBot needs session_path (or tg_id)")
        self.session_path = session_path
        self.tg_id = tg_id or os.path.basename(str(session_path)).split(".")[0]
        # ``profile_dir`` is part of the shared bot contract (`_boot_bot` logs
        # it); for MTProto it is the session file.
        self.profile_dir = session_path
        self.bot_target = bot_target if bot_target in TG_BOTS else "taskly"
        cfg = TG_BOTS.get(self.bot_target, TG_BOTS["taskly"])
        self.bot_name = bot_name or cfg["name"]
        self.bot_username = cfg.get("username") or (
            "tasklyBux_bot" if self.bot_target == "taskly" else "PayGoBot")
        self.headless = bool(headless)  # unused; kept for interface parity
        self.log = log
        self.creds = {}
        self.one_time_code = None
        self._client = None
        self._entity = None

    # -- lifecycle ------------------------------------------------------
    def start(self, **_kw):
        self._ensure_conn()
        self.log(f"[tg] Telegram MTProto session ready for {self.bot_name} "
                 f"({os.path.basename(self.session_path)}).")
        return self

    open = start

    def logged_in(self):
        try:
            if self._client is None:
                self._client = _make_client(self.tg_id, self.session_path)
            if not self._client.is_connected():
                self._client.connect()
            return bool(self._client.is_user_authorized())
        except Exception:
            return None

    def close(self, ok=True):
        """MTProto has no browser — but the Telethon client DOES hold a lock on
        the session SQLite file (``data/tg_sessions/<id>.session``).

        Not disconnecting here wedged the next client on the same session with
        "database is locked" — the pool reuses a session across cycles and the
        owner loop rebuilds the bot on a bot-target switch (observed
        2026-09-28: an orphaned engine plus a rebuilt owner both held
        ``tg_1.session``). Disconnect so the file is released.
        """
        self.creds = {}
        self.one_time_code = None
        self.disconnect()
        return True

    def disconnect(self):
        try:
            if self._client is not None and self._client.is_connected():
                self._client.disconnect()
        except Exception:
            pass

    # -- low level ------------------------------------------------------
    def _ensure_conn(self):
        """Lazily connect the Telethon client and resolve the bot entity.

        The owner loop (``_mtproto_owner_loop``) builds ``MtprotoTasklyBot``
        on the FIRST command it receives — which is NOT always ``start()``.
        The browser original always had a live page by that point; here
        ``_client`` starts as ``None``, so any command issued first
        (``cancel_task``, ``reset_to_main_menu``, ``choose_task``, …) hit
        ``'NoneType' object has no attribute 'get_messages'``, and because
        ``_messages`` swallows exceptions into an empty list it degraded
        SILENTLY into "no buttons" / "no messages" rather than an error
        (observed 2026-09-27 on a fresh pool: ``cancel_task`` and
        ``reset_to_main_menu`` both no-op'd with only a log note).

        Raises on a lost session so the ``session lost`` marker reaches
        ``_boot_bot``/``_is_tg_session_lost`` instead of a phantom "no reply".
        """
        if self._client is None:
            self._client = _make_client(self.tg_id, self.session_path)
        if not self._client.is_connected():
            self._client.connect()
        if not self._client.is_user_authorized():
            raise RuntimeError(
                f"Telegram session is not logged in ({os.path.basename(self.session_path)}) "
                f"— session lost. Run: tg_login_mtproto.py --id {self.tg_id}")
        if self._entity is None:
            self.open_bot()
        return self._client

    def open_bot(self):
        """Resolve the target bot entity (MTProto has no 'open chat' step)."""
        if self._client is None:
            self._client = _make_client(self.tg_id, self.session_path)
        if not self._client.is_connected():
            self._client.connect()
        try:
            self._entity = self._client.get_entity(self.bot_username)
        except Exception as exc:
            self.log(f"[tg] could not resolve {self.bot_username}: {exc}")
            return False
        return self._entity is not None

    def _messages(self, limit=10, min_id=0):
        """Bot chat messages, NEWEST first."""
        self._ensure_conn()
        try:
            return list(self._client.get_messages(self._entity, limit=limit,
                                                  min_id=min_id) or [])
        except Exception as exc:
            self.log(f"[tg] get_messages note: {exc}")
            return []

    def _send(self, text):
        self._ensure_conn()
        self._client.send_message(self._entity, str(text))
        return True

    def _buttons(self, limit=10):
        """Current reply-keyboard texts (from the newest message carrying one)."""
        for m in self._messages(limit=limit):
            b = _reply_button_texts(m)
            if b:
                return b, m
        return [], None

    def _last(self):
        msgs = self._messages(limit=1)
        return msgs[0] if msgs else None

    def _wait_for_button(self, needle, timeout=12.0):
        """Wait until the CURRENT reply keyboard has a button matching ``needle``.

        Critical: Telegram replaces the keyboard asynchronously. Right after
        sending a task selection the bot still shows the PREVIOUS keyboard, so
        reading it immediately and falling back to a literal ``send("Start")``
        posts a plain message the bot ignores — the task then never starts and
        ``start_task`` times out with "no usable credentials" (observed
        2026-09-21: 23 task selections, 21 credential timeouts, and a literal
        "Start" sitting in the chat). Returns (button_text, message) or (None, None).
        """
        deadline = time.time() + max(0.0, timeout)
        last_msg = None
        while True:
            btns, msg = self._buttons()
            if msg is not None:
                last_msg = msg
            hit = next((b for b in btns if _norm_btn(needle) in _norm_btn(b)), None)
            if hit:
                return hit, msg
            if time.time() >= deadline:
                return None, last_msg
            time.sleep(0.5)

    def _recent_texts(self, n=3):
        """Newest-first bot (incoming) message texts — for diagnostics."""
        out = []
        for m in self._messages(limit=n + 4):
            if getattr(m, "out", False):
                continue
            t = (getattr(m, "text", "") or "").strip()
            if t:
                out.append(t)
            if len(out) >= n:
                break
        return out

    def _last_id(self) -> int:
        m = self._last()
        return int(getattr(m, "id", 0) or 0)

    def _last_text(self) -> str:
        m = self._last()
        return (getattr(m, "text", "") or "").strip()

    def _inspect(self, max_msgs=8, max_btns=30):
        btns, _m = self._buttons()
        msgs = [(getattr(m, "text", "") or "").strip() for m in self._messages(limit=max_msgs)]
        return {"buttons": btns[:max_btns], "messages": [t for t in msgs if t]}

    # -- task flow ------------------------------------------------------
    def reset_to_main_menu(self, timeout=30):
        """Escape to a clean menu — NEVER cancels a submitted task (invariant 23)."""
        try:
            low = self._last_text().lower()
            # NOTE: "review time" is deliberately NOT a marker — the pre-start
            # task PREVIEW also says "⏳ Review time: 64 min ⏳" (169 occurrences
            # in one run), so it would match a non-submitted state. The real
            # post-submit text is "report has been received! Please wait."
            if any(p in low for p in ("report has been received", "please wait",
                                      "under review")):
                # Submitted/under-review screen: /start only, never Cancel.
                self._send("/start")
                time.sleep(1.0)
                return True
            btns, _m = self._buttons()
            cbtn = next((b for b in btns if "cancel" in b.lower()), None)
            if cbtn:
                self._send(cbtn)
                time.sleep(1.5)
                btns, _m = self._buttons()
                rbtn = next((b for b in btns
                             if "return" in b.lower() or "main menu" in b.lower()), None)
                if rbtn:
                    self._send(rbtn)
                    time.sleep(1.2)
            self._send("/start")
            time.sleep(1.0)
            return True
        except Exception as exc:
            self.log(f"[tg] reset_to_main_menu note: {exc}")
            return False

    def cancel_task(self):
        try:
            btns, _m = self._buttons()
            cbtn = next((b for b in btns if "cancel" in b.lower()), None)
            if cbtn:
                self._send(cbtn)
                return True
        except Exception:
            pass
        return False

    def _pick_task_button(self, btns, task, clean):
        """Legacy fuzzy picker — kept for interface parity only.

        New code must use :mod:`tg_tasks` (strict per-bot registry) via
        :meth:`choose_task`. This stays as a thin registry wrapper so any
        external caller keeps working without the old silent-fallback
        behavior (it returns None instead of a wrong task).
        """
        try:
            from tg_tasks import resolve, match_level
        except ImportError:
            return None
        task_id, levels = resolve(self.bot_target, task)
        if task_id is None:
            return None
        for level in levels:
            hit = match_level(btns, level)
            if hit:
                return hit
        return None

    def _await_level(self, level, timeout=8.0):
        """Poll the live keyboard until ``level`` matches (registry matcher)."""
        try:
            from tg_tasks import match_level
        except ImportError:
            return None
        deadline = time.time() + max(0.0, timeout)
        while True:
            btns, _m = self._buttons()
            hit = match_level(btns, level)
            if hit:
                return hit
            if time.time() >= deadline:
                return None
            time.sleep(0.5)

    def choose_task(self, task=TG_DEFAULT_TASK):
        """Walk the registry button path for this bot — strict, no fallback.

        ``tg_tasks.resolve`` maps the requested task for THIS bot only. An
        unknown task, or a task the bot does not offer (e.g. "No mail" on
        PayGo, "Cookies" on Taskly), returns False WITHOUT touching any
        other button — the old alias-remap/fuzzy fallbacks that silently
        started the wrong task are gone. Stock gaps (task temporarily
        absent) poll each level briefly, then fail loud with the missing
        level so the cycle cancels instead of improvising.
        """
        try:
            from tg_tasks import resolve, LABELS
        except ImportError:
            self.log("[tg] tg_tasks registry unavailable — refusing to pick")
            return False
        task_id, levels = resolve(self.bot_target, task)
        if task_id is None:
            self.log(f"[tg] ❌ {levels} (task={task!r}, bot={self.bot_target})")
            return False
        want = LABELS.get(task_id, task)
        for _try in range(2):
            self.reset_to_main_menu()
            navigated = []
            failed = None
            for depth, level in enumerate(levels):
                pick = self._await_level(level, timeout=8.0)
                if not pick:
                    failed = depth
                    break
                self._send(pick)
                navigated.append(pick)
                time.sleep(1.2)
            if failed is None:
                for p in navigated:
                    self.log(f"[tg] Selected task: {p}")
                # The bot answers with the task preview, whose keyboard
                # carries "▶️ Start". Do NOT return until it is there, or
                # start_task will read the stale keyboard and post a
                # literal "Start".
                if not self._wait_for_button("start", timeout=10):
                    self.log("[tg] ⚠️ task selected but no Start key appeared yet")
                return True
            self.log(f"[tg] '{want}' not available right now "
                     f"(level {failed + 1}/{len(levels)} missing; "
                     f"had: {navigated or 'main menu'}) — not substituting.")
        self.log(f"[tg] task '{want}' not found.")
        return False

    def start_task(self):
        """Press Start and parse fresh creds (never stale, never across a cancel)."""
        if self.bot_target == "fastpay":
            return self._start_task_fastpay()
        for attempt in range(4):
            # Guard: if a task is ALREADY mid-flight (2FA-key prompt / code /
            # register prompt), pressing Start is meaningless — it just posts a
            # message the bot ignores. That is what produced the repeated
            # "pressed 'Start'" spam after a parse miss. Bail so the caller
            # cancels and re-requests on a clean menu instead.
            recent = self._recent_texts(1)
            if recent:
                # Match ONLY the first line of the newest bot message — that is
                # the state prompt. The task PREVIEW's first line is
                # "⏳ Review time: 64 min ⏳", but its DESCRIPTION body mentions
                # "one-time code" / "Account registered" / "confirm
                # registration", so scanning the whole body made the guard fire
                # on every healthy cycle (0 task starts, 2026-09-21).
                first = (recent[0].split("\n", 1)[0] or "").strip().lower()
                if ("enter your 2fa key" in first
                        or "confirm registration or cancel the task" in first
                        or "your one-time code" in first):
                    self.log(f"[tg] start_task: task already in progress "
                             f"({first[:60]!r}) — not pressing Start")
                    return {"first_name": "", "login": "", "password": ""}

            # Wait for the task-preview keyboard; only then is "▶️ Start" real.
            sbtn, smsg = self._wait_for_button("start", timeout=12)
            if sbtn:
                self._send(sbtn)
                sent = sbtn
            else:
                sent = None
                for t, _data, btn in _inline_buttons(smsg):
                    if "start" in (t or "").lower():
                        try:
                            btn.click()
                            sent = t
                            break
                        except Exception as exc:
                            self.log(f"[tg] inline Start click failed: {exc}")
                if sent is None:
                    # Last resort only — a plain "Start" is NOT a button press.
                    sent = "Start"
                    self._send("Start")
            self.log(f"[tg] start_task: pressed '{sent}'")

            deadline = time.time() + 15.0
            rate_limited = False
            wait_sec = 5
            found = None
            while time.time() < deadline:
                time.sleep(0.6)
                msgs = list(reversed(self._messages(limit=12)))  # oldest → newest
                # Boundary = last cancellation marker; only the tail is "active".
                last_cancel = -1
                for i, m in enumerate(msgs):
                    tl = (getattr(m, "text", "") or "").lower()
                    if any(c in tl for c in _CANCEL_RES):
                        last_cancel = i
                active = msgs[last_cancel + 1:]
                for m in reversed(active):  # newest → oldest within the active tail
                    if getattr(m, "out", False):
                        continue
                    txt = (getattr(m, "text", "") or "").strip()
                    if not txt:
                        continue
                    # Telethon's .text keeps Markdown SYNTAX characters: the bot
                    # wraps values in backticks ("Login: `abc`") and the
                    # formatting lives in .entities, so the raw text still has
                    # the backticks. The password regex has no backtick in its
                    # class, so without this it NEVER matched and every cycle
                    # died as "no usable credentials" even though the creds
                    # were on screen (observed 2026-09-21).
                    txt = txt.replace("`", "")
                    tl = txt.lower()
                    if "too often" in tl or re.search(r"wait \d+ sec", tl):
                        rate_limited = True
                        mm = re.search(r"(\d+)\s*sec", txt)
                        if mm:
                            wait_sec = int(mm.group(1))
                        break
                    if re.search(r"Login:\s*.+", txt, re.I) and re.search(r"Password:\s*\S+", txt, re.I):
                        found = self._parse_creds(txt)
                        break
                if rate_limited or found:
                    break
            if rate_limited:
                cooldown = max(5, wait_sec) + 1.5
                self.log(f"[tg] ⏳ anti-flood: bot asked to wait {wait_sec}s — "
                         f"sleeping {cooldown:.1f}s (attempt {attempt + 1}/4)…")
                time.sleep(cooldown)
                continue
            if found and found.get("login") and found.get("password"):
                self.creds = found
                self.log(f"[tg] task started → {self.creds}")
                return self.creds
            # Diagnostic: show what the bot actually said so a miss is explainable.
            self.log(f"[tg] start_task miss #{attempt + 1}: last bot msgs = "
                     f"{[t[:140] for t in self._recent_texts(3)]}")
        self.log("[tg] ❌ Could not obtain fresh task credentials (timed out / rate limited).")
        return {"first_name": "", "login": "", "password": ""}

    @staticmethod
    def _parse_creds(txt):
        # The bot wraps labels in Markdown (`**Username:** \`value\``) and
        # Telethon's .text keeps the raw syntax. Strip the decoration so the
        # value is captured cleanly. FastPay uses "Username:", Taskly/PayGo
        # use "Login:"; both carry "Password:". FastPay sends no first name,
        # so the caller fills one in. Taskly's 2FA task ALSO sends the
        # registration email ("Email:", learned live 2026-09-28) — captured
        # additively; callers that don't need it ignore the key.
        txt = str(txt or "").replace("`", "").replace("*", "")
        m_login = re.search(r"(?:Login|Username):\s*(.*?)(?=\s*Password:|\n|\r|$)", txt, re.I)
        m_pwd = re.search(r"Password:\s*([A-Za-z0-9_!@#$%^&*+=?-]+)", txt, re.I)
        m_name = re.search(r"First name:\s*(.*?)(?=\s*(?:Login|Username):|\n|\r|$)", txt, re.I)
        m_email = re.search(r"Email:\s*(\S+)", txt, re.I)
        if not (m_login and m_pwd):
            return None
        out = {"first_name": (m_name.group(1).strip() if m_name else ""),
               "login": m_login.group(1).strip(),
               "password": m_pwd.group(1).strip()}
        if m_email:
            out["email"] = m_email.group(1).strip()
        return out

    def _start_task_fastpay(self):
        """FastPay has NO Start button — selecting the task already sent the creds.

        The bot sends TWO messages on task select::

            📋 Task: 𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺 2𝗙𝗔
            👤 Username: `virginia_howardzau_47203`
            🔒 Password: `FASTPAY%27`
            [𝗥𝗲𝗳𝗿𝗲𝘀𝗵]

            👇 Please send the 2FA Key below: 🔑

        Reading only the NEWEST message shows just the key prompt — which is
        what made this bot look payout-only. Scan a few messages for the creds.
        FastPay sends no first name, so a random one is generated (the engine's
        IG onboarding needs something to type).
        """
        deadline = time.time() + 12.0
        while time.time() < deadline:
            for m in self._messages(limit=6):
                if getattr(m, "out", False):
                    continue
                txt = (getattr(m, "text", "") or "").replace("`", "")
                if not (re.search(r"Username:\s*\S+", txt, re.I)
                        and re.search(r"Password:\s*\S+", txt, re.I)):
                    continue
                creds = self._parse_creds(txt)
                if creds and creds.get("login") and creds.get("password"):
                    creds["first_name"] = _random_first_name()
                    self.creds = creds
                    self.log(f"[tg] task started → {self.creds}")
                    return self.creds
            time.sleep(0.6)
        self.log("[tg] ❌ FastPay did not send task credentials "
                 f"(last msgs: {[t[:90] for t in self._recent_texts(3)]})")
        return {"first_name": "", "login": "", "password": ""}

    def submit_2fa_key(self, key, allow_local_fallback=True):
        clean = str(key or "").strip()
        # Fail-safe: if 'Get code' is still on the keyboard, click it to advance Taskly's state
        try:
            btns, _msg = self._buttons(limit=10)
        except Exception:
            btns = []
        hit = next((b for b in btns or [] if "get code" in _norm_btn(b)), None)
        if hit:
            self.log(f"[tg] '{hit}' button still on keyboard — clicking to advance bot state before submitting 2FA key…")
            self._send(hit)
            time.sleep(1.5)

        before_id = self._last_id()
        self._send(clean)
        self.log(f"[tg] 2FA key submitted to {self.bot_name}; waiting for one-time code…")
        deadline = time.time() + 25.0
        while time.time() < deadline:
            time.sleep(0.25)
            for m in self._messages(limit=4):
                if getattr(m, "out", False):
                    continue
                if int(getattr(m, "id", 0) or 0) <= before_id:
                    continue
                txt = (getattr(m, "text", "") or "")
                txt = txt.replace("`", "")  # Markdown code ticks (see start_task)
                mm = (re.search(r"(?:code|your one-time code)[:\s]*(\d{6})", txt, re.I)
                      or re.search(r"\b(\d{6})\b", txt))
                if mm:
                    self.one_time_code = mm.group(1)
                    self.log(f"[tg] ⚡ One-time code from bot: {self.one_time_code}")
                    return self.one_time_code
        if not allow_local_fallback:
            raise RuntimeError("Telegram bot did not return a one-time code")
        totp_clean = re.sub(r"[^A-Za-z2-7]", "", clean).upper()
        try:
            import pyotp
            self.one_time_code = pyotp.TOTP(totp_clean).now()
            self.log(f"[tg] ⚡ bot reply delayed; used local TOTP: {self.one_time_code}")
            return self.one_time_code
        except Exception as e:
            self.log(f"[tg] [⚠️] local TOTP generation failed for '{totp_clean}': {e}")
            raise RuntimeError("Telegram bot did not return a one-time code")

    def request_email_code(self, timeout: float = 45.0):
        """Press 📥 Get code and read the bot-issued email verification code.

        Taskly 2FA flow (learned live 2026-09-28): after Start the bot orders
        a mailbox and sends First name/Login/Password/Email; the 6-digit IG
        confirmation code for that email is ONLY available via the "📥 Get
        code" key — there is no inbox on our side. Returns the code string,
        else "". Never sends credentials or register keys.
        """
        before_id = self._last_id()
        sent = False
        for _try in range(2):
            try:
                btns, _msg = self._buttons(limit=10)
            except Exception:
                btns = []
            hit = next((b for b in btns or [] if "get code" in _norm_btn(b)), None)
            if hit:
                self._send(hit)
                sent = True
                self.log(f"[tg] requested email code via '{hit}'")
                break
            time.sleep(1.5)
        if not sent:
            self.log("[tg] Get-code key not visible — cannot fetch email code")
            return ""
        deadline = time.time() + max(10.0, timeout)
        _beat = time.time()
        while time.time() < deadline:
            time.sleep(1.5)
            if time.time() - _beat >= 15:
                _beat = time.time()
                left = max(0, int(deadline - time.time()))
                self.log(f"[tg] still waiting for the bot email code… {left}s left (do NOT press Stop)")
            for m in self._messages(limit=6):
                if getattr(m, "out", False):
                    continue
                if int(getattr(m, "id", 0) or 0) <= int(before_id or 0):
                    continue
                txt = (getattr(m, "text", "") or "")
                if not txt.strip():
                    continue
                if any(c in txt.lower() for c in _CANCEL_RES):
                    self.log(f"[tg] email-code wait hit cancel/timeout marker: {txt[:80]}")
                    return ""
                mm = re.search(r"\b(\d{6})\b", txt.replace("`", ""))
                if mm:
                    code = mm.group(1)
                    self.log(f"[tg] ⚡ email code from bot: ****{code[-2:]}")
                    return code
        self.log("[tg] ❌ bot sent no email code in time")
        return ""

    def submit_cookie(self, cookie: str, timeout: float = 20.0):
        """Send the IG cookie header string for a PayGo Cookies task.

        Returns ``(ok, reply)``: ``ok`` is True when the bot moved past the
        cookie prompt — i.e. it asked to confirm registration (the
        ``mark_registered`` gate next) or reported acceptance. A format
        rejection ("too short", "invalid") returns ``(False, reply)`` so the
        caller can abort instead of tapping register on a dead task.

        Learned live 2026-09-27 on PayGoBot "📱 Create Inst (Cookies)":
        after Start the bot says "🍪 Please send the account Cookie:";
        a 209-char ``sessionid/ds_user_id/csrftoken/mid/ig_did`` header got
        "👉 Press the button to confirm registration or cancel the task:"
        with [✅ Account registered, ❌ Cancel]; a short string got
        "❌ Cookie is too short (minimum 100 characters)".
        """
        clean = str(cookie or "").strip()
        if len(clean) < 100:
            return False, "cookie too short (<100 chars) — not sent"
        before_id = self._last_id()
        self._send(clean)
        self.log(f"[tg] Cookie submitted to {self.bot_name} ({len(clean)} chars); waiting for verdict…")
        deadline = time.time() + max(5.0, timeout)
        reply = ""
        while time.time() < deadline:
            time.sleep(0.5)
            for m in self._messages(limit=4):
                if getattr(m, "out", False):
                    continue
                if int(getattr(m, "id", 0) or 0) <= before_id:
                    continue
                txt = (getattr(m, "text", "") or "").strip()
                if not txt:
                    continue
                reply = txt
                low = txt.lower()
                if any(k in low for k in ("too short", "invalid cookie", "incorrect",
                                          "wrong", "rejected", "send the account cookie")) \
                        and "confirm registration" not in low:
                    # Still the cookie prompt (or an explicit rejection) —
                    # keep waiting a little in case the verdict follows,
                    # but remember the rejection.
                    if any(k in low for k in ("too short", "invalid", "rejected")):
                        self.log(f"[tg] cookie rejected: {txt[:160]}")
                        return False, txt
                    continue
                if ("confirm registration" in low or "account registered" in low
                        or "report has been received" in low
                        or "under review" in low or "please wait" in low):
                    self.log(f"[tg] cookie accepted → {txt[:160]}")
                    return True, txt
            # Fallback: the register key appearing means the cookie passed.
            try:
                btns, _ = self._buttons(limit=3)
                if any("regist" in (b or "").lower() or "confirm" in (b or "").lower()
                       for b in btns):
                    self.log("[tg] cookie accepted (register key visible).")
                    return True, reply or "register key visible"
            except Exception:
                pass
        self.log(f"[tg] no cookie verdict yet; last reply: {reply[:160]}")
        # Unknown-but-not-rejected: let the caller try mark_registered; a
        # dead task fails loudly there instead of here.
        return ("confirm registration" in reply.lower()
                or "account registered" in reply.lower()), reply

    def mark_registered(self):
        """Send the register/confirm key and classify ONLY the NEW reply."""
        self.open_bot()
        before_id = self._last_id()
        before_txt = self._last_text()

        btns, msg = self._buttons()
        inline = _inline_buttons(msg) if msg is not None else []
        pick = None
        # 1. Exact label match on the reply keyboard (NFKC: FastPay's Confirm
        #    is `𝗖𝗼𝗻𝗳𝗶𝗿𝗺`, which plain .lower() cannot match).
        for label in _REGISTER_LABELS:
            hit = next((b for b in btns if _norm_btn(b).strip() == label), None)
            if hit:
                pick = hit
                break
        # 2. Register/confirm-LIKE reply key (never a destructive/menu key).
        if not pick:
            pick = next((b for b in btns
                         if ("regist" in _norm_btn(b) or "confirm" in _norm_btn(b))
                         and not any(x in _norm_btn(b) for x in _REGISTER_BAD)), None)
        # 3. Inline button fallback.
        inline_pick = None
        if not pick:
            for t, data, row in inline:
                low = (t or "").lower()
                if any(x in low for x in _REGISTER_BAD):
                    continue
                if "regist" in low or "confirm" in low:
                    inline_pick = row
                    break
        if not pick and inline_pick is None:
            self.log(f"[tg] register key not found; visible buttons: {btns[:20]}")
            return False

        if pick:
            self._send(pick)
            self.log(f"[tg] tapped register key: {pick}")
        else:
            try:
                inline_pick.click()
                self.log(f"[tg] tapped inline register key: {inline_pick.text}")
            except Exception as exc:
                self.log(f"[tg] inline register click failed: {exc}")
                return False

        verdict = "unknown"
        new_text = ""
        deadline = time.time() + 8.0
        while time.time() < deadline:
            time.sleep(0.5)
            for m in self._messages(limit=4):
                if getattr(m, "out", False):
                    continue
                txt = (getattr(m, "text", "") or "").strip()
                if not txt:
                    continue
                if int(getattr(m, "id", 0) or 0) > before_id or txt != before_txt:
                    new_text = txt
                    break
            if new_text:
                verdict = classify_report_reply(new_text)
                if verdict != "unknown":
                    break

        if verdict == "rejected":
            self.log(f"[tg] ❌ bot REJECTED the report — NOT recording Submitted | '{new_text[:160]}'")
            return False
        if verdict == "accepted":
            self.log("[tg] submitted=True (verdict=accepted)")
            return True
        self.log("[tg] no fresh verdict after register send — treating as UNCONFIRMED (not rejected).")
        return False


# ==============================================================================
# Pooled warm workers — same shape/API as tg_bot.PooledTelegramBot
# ==============================================================================
def _mtproto_owner_loop(q_in, q_out, session_path, tg_id, bot_target, log):
    """Owner thread: one Telethon client per session, commands run FIFO."""
    bot = None
    while True:
        cmd, target, args, kwargs = q_in.get()
        if cmd == "shutdown":
            try:
                if bot is not None:
                    bot.disconnect()
            except Exception:
                pass
            try:
                # Tuple-shaped like every other reply: _call unpacks
                # ``ok, res = q_out.get()``, so a bare bool here used to
                # surface as "TypeError: cannot unpack non-iterable bool
                # object" on any racing/in-flight call (Slot #5, 2026-09-24).
                q_out.put((True, True))
            except Exception:
                pass
            break
        try:
            tgt = target or bot_target
            if bot is None or bot.bot_target != tgt:
                if bot is not None:
                    bot.close()
                bot = MtprotoTasklyBot(session_path=session_path, tg_id=tg_id,
                                       bot_target=tgt, log=kwargs.get("log", log) or log)
            fn = getattr(bot, cmd)
            res = fn(*args, **kwargs)
            q_out.put((True, res))
        except Exception as e:
            q_out.put((False, e))


class MtprotoPooledBot:
    """Warm pooled MTProto bot — mirrors ``tg_bot.PooledTelegramBot``.

    The pool key is the session file. No browser, so no SingletonLock, warm
    idle reaping or RAM ceiling — instances are cheap enough to keep all up.
    """

    _pool = {}
    _pool_lock = threading.Lock()
    _WARM_IDLE_SECS = 1800

    def __init__(self, profile_dir=None, bot_name=None, bot_target="taskly",
                 headless=True, log=print, session_path=None, tg_id=None):
        self.session_path = session_path or profile_dir
        if not self.session_path:
            raise RuntimeError("MtprotoPooledBot needs session_path (or profile_dir)")
        self.tg_id = tg_id or os.path.basename(str(self.session_path)).split(".")[0]
        self.bot_target = bot_target
        cfg = TG_BOTS.get(bot_target, TG_BOTS["taskly"])
        self.bot_name = bot_name or cfg["name"]
        self.headless = bool(headless)
        self.log = log
        self.profile_dir = self.session_path  # contract parity
        self._key = self.session_path
        self._reap_idle()
        with MtprotoPooledBot._pool_lock:
            self._ent = MtprotoPooledBot._ensure_locked(
                self._key, self.session_path, self.tg_id, bot_target, log)

    @classmethod
    def _ensure_locked(cls, key, session_path, tg_id, bot_target, log):
        """Return the live pool entry for ``key``, rebuilding a dead one.

        Must hold ``_pool_lock``. A dead owner (reaped/dropped under a live
        lease by mem-shed or idle eviction) is rebuilt transparently so the
        next command reconnects instead of talking to a dead queue.
        """
        ent = cls._pool.get(key)
        try:
            alive = ent is not None and ent["thread"].is_alive()
        except Exception:
            alive = False
        if not alive:
            if ent is not None:
                try:
                    cls._pool.pop(key, None)
                except Exception:
                    pass
            q_in: queue.Queue = queue.Queue()
            q_out: queue.Queue = queue.Queue()
            t = threading.Thread(
                target=_mtproto_owner_loop,
                args=(q_in, q_out, session_path, tg_id,
                      bot_target, log), daemon=True)
            t.start()
            ent = {"thread": t, "q_in": q_in, "q_out": q_out,
                   "last_used": time.time()}
            cls._pool[key] = ent
        ent["last_used"] = time.time()
        return ent

    @staticmethod
    def _leased_keys() -> set:
        """Pool keys currently leased to a live cycle (never reap these)."""
        try:
            from tg_accounts import tg_manager
            return set(tg_manager.leased_ids())
        except Exception:
            return set()

    @staticmethod
    def _reap_idle() -> None:
        victims = []
        leased = MtprotoPooledBot._leased_keys()
        with MtprotoPooledBot._pool_lock:
            now = time.time()
            for k, ent in list(MtprotoPooledBot._pool.items()):
                # A live lease holds no pool traffic during long IG phases
                # (2FA grind), so last_used goes stale while the cycle is
                # very much alive — reaping it murders the task (2026-09-24).
                if str(k) in leased or os.path.basename(str(k)) in leased:
                    continue
                try:
                    if now - float(ent.get("last_used", now)) > MtprotoPooledBot._WARM_IDLE_SECS:
                        victims.append((k, ent))
                        del MtprotoPooledBot._pool[k]
                except Exception:
                    pass
        for _k, ent in victims:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=10)
            except Exception:
                pass

    def _call(self, cmd, *args, **kwargs):
        with MtprotoPooledBot._pool_lock:
            self._ent = MtprotoPooledBot._ensure_locked(
                self._key, self.session_path, self.tg_id,
                self.bot_target, self.log)
            ent = self._ent
        ent["q_in"].put((cmd, self.bot_target, args, kwargs))
        try:
            item = ent["q_out"].get(timeout=180)
        except queue.Empty:
            raise RuntimeError(f"MTProto bot thread hung on '{cmd}' (180s)")
        # A non-tuple here means a stale sentinel from a reaped owner, never
        # a real reply — fail loud with the cause, not "cannot unpack
        # non-iterable bool object".
        if not isinstance(item, tuple) or len(item) != 2:
            raise RuntimeError(
                f"MTProto bot session for '{self.tg_id}' was reaped mid-task "
                f"(stale pool reply) on '{cmd}' — retry the task")
        ok, res = item
        if not ok:
            raise res
        return res

    def start(self):
        return self._call("open", log=self.log)

    def open(self):
        return self.start()

    def logged_in(self):
        try:
            return self._call("logged_in")
        except Exception:
            return None

    def open_bot(self):
        return self._call("open_bot")

    def choose_task(self, task=TG_DEFAULT_TASK):
        return self._call("choose_task", task)

    def start_task(self):
        return self._call("start_task")

    def submit_2fa_key(self, key, allow_local_fallback=True):
        return self._call("submit_2fa_key", key, allow_local_fallback=allow_local_fallback)

    def request_email_code(self, timeout=45.0):
        return self._call("request_email_code", timeout=timeout)

    def submit_cookie(self, cookie, timeout=20.0):
        return self._call("submit_cookie", cookie, timeout=timeout)

    def mark_registered(self):
        return self._call("mark_registered")

    def reset_to_main_menu(self, timeout=30):
        return self._call("reset_to_main_menu", timeout=timeout)

    def cancel_task(self):
        return self._call("cancel_task")

    def close(self, ok=True):
        try:
            return self._call("close", ok=ok)
        except Exception:
            return False

    @classmethod
    def _match_keys(cls, key: str) -> list:
        """Pool keys identifying ``key`` (session path, profile dir or id).

        ``_reap_wedged_tg_browser`` passes the *profile dir* while the pool
        is keyed by *session file* — without flexible matching that reap was
        a silent no-op for MTProto and wedged owners lived forever.
        """
        if not key:
            return []
        cands = {str(key)}
        try:
            cands.add(os.path.basename(str(key)))
            base = os.path.basename(str(key)).split(".")[0]
            cands.add(base)
        except Exception:
            pass
        found = []
        for k in list(cls._pool.keys()):
            try:
                kb = os.path.basename(str(k)).split(".")[0]
            except Exception:
                kb = ""
            if k in cands or str(k) in cands or kb in cands:
                found.append(k)
        return found

    @classmethod
    def drop_profile(cls, key: str) -> None:
        if not key:
            return
        with cls._pool_lock:
            ents = [cls._pool.pop(k, None) for k in cls._match_keys(key)]
            ents = [e for e in ents if e is not None]
        for ent in ents:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=10)
            except Exception:
                pass

    @classmethod
    def drop_all(cls, skip_leased: bool = False) -> None:
        """Shut down pooled owners. ``skip_leased=True`` keeps live leases.

        The memory watchdog MUST pass ``skip_leased``: killing a leased
        owner's thread mid-task poisons its queue and the cycle dies with a
        cryptic unpack error instead of finishing (2026-09-24). Engine
        shutdown paths keep the default (kill everything).
        """
        leased = cls._leased_keys() if skip_leased else set()
        victims = []
        with cls._pool_lock:
            for k in list(cls._pool.keys()):
                try:
                    if (str(k) in leased
                            or os.path.basename(str(k)) in leased
                            or os.path.basename(str(k)).split(".")[0] in leased):
                        continue
                except Exception:
                    pass
                ent = cls._pool.pop(k, None)
                if ent is not None:
                    victims.append(ent)
        for ent in victims:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=5)
            except Exception:
                pass

    @classmethod
    def close_inspectors(cls, *a, **kw) -> int:
        """No browsers to shed — no-op (kept for worker parity)."""
        return 0
