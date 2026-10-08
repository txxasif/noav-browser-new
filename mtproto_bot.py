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

# Low-level transport/session/login layer lives in ``mtproto_client`` (split out
# of this module as a pure code move). Re-exported here so existing callers —
# ``tg_login.py``, ``tg_login_mtproto.py``, ``tg_balance.py``, ``tg/common.py``,
# ``tg_join_bot.py``, ``tg_fastpay.py``, ``tg_withdraw.py``, ``tg_accounts.py`` —
# keep importing these names from ``mtproto_bot``.
from mtproto_client import (  # noqa: E402
    TG_SESSIONS_DIR, MtprotoNeedsPassword, _APP_VERSIONS, _DEVICE_MODELS,
    _OPEN_SESSIONS, _SYS_VERSIONS, _api_credentials, _device_identity,
    _harden_session_db, _inline_buttons, _make_client, _pin_loop,
    _reply_button_texts, _session_is_foreign, complete_login,
    has_mtproto_session, send_login_code, session_file,
)

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

# Hourly stock-limit markers. PayGo's cookie task publishes
# "⚡️ Available this hour: X/5700" and "⏳ This hour's limit is reached. Next
# execution will be available in N min."; Taskly's "🍪 Create Inst (No mail)"
# cookie task uses the SAME shape (the counter resets on the hour). Treating a
# match as "soldout" makes a sold-out hour fail FAST instead of burning the
# whole TASK_WINDOW (invariant 29).
_HOUR_LIMIT_PHRASES = (
    "limit is reached", "hour's limit", "hour’s limit", "hourly limit",
    "limit reached", "next execution will be available",
    "next execution is available", "will be available in",
)
# The stock counter "Available this hour: 0/5700" — 0 means sold out. Match the
# ZERO only: a healthy "5/5700" must NEVER veto the pick.
_HOUR_LIMIT_SOLD_OUT = (
    "available this hour: 0/", "available this hour: 0 ",
    "available this hour: 0\n", "available this hour: 0\u00a0",
)


def _is_hour_limit(text, cookies: bool = False) -> bool:
    """True when ``text`` is an hourly stock-limit / sold-out notice.

    ``cookies`` enables the "Available this hour: 0/N" counter check (only the
    cookie tasks publish that counter). The generic phrases apply to every task.
    """
    tl = (text or "").lower()
    if any(p in tl for p in _HOUR_LIMIT_PHRASES):
        return True
    if cookies and any(p in tl for p in _HOUR_LIMIT_SOLD_OUT):
        return True
    return False


def _is_subscription_confirm(text) -> bool:
    """True for the bot's mandatory 5-subscription affirmative key.

    PayGo's cookie task asks "Did you make 5 subscriptions after registration?
    This is mandatory, otherwise your report will be rejected!" and offers a key
    like "✅ Yes, I made 5 subscriptions". Matches the subscription wording or a
    Yes/I-made-5 phrasing (NFKC-normalized via ``_norm_btn``).
    """
    n = _norm_btn(text)
    if not n:
        return False
    return ("subscription" in n
            or ("yes" in n and "5" in n)
            or ("made" in n and "5" in n))

# A task is LIVE (mid-flight) while the newest bot text contains one of these.
# reset_to_main_menu / cancel_task must NEVER send Cancel here — observed
# 2026-10-03/04: Cancel tapped into a cookie prompt, a 2FA-key prompt, or a
# task preview ("Review time…") reset the task ("Our previous conversation
# was reset"). Includes the preview: mid-cycle retries must not kill a task
# that was just selected but not Started yet.
_ACTIVE_TASK_MARKERS = (
    "please send the account cookie", "send the account cookie",
    "please send your cookie", "please send the cookie",
    "send the 2fa key", "please send the 2fa", "enter your 2fa key",
    "press the button to get the code",
    "confirm registration", "please send the account",
)

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
        self.bot_username = cfg.get("username") or TG_BOTS["taskly"]["username"]
        self.headless = bool(headless)  # unused; kept for interface parity
        self.log = log
        self.creds = {}
        self.one_time_code = None
        self._client = None
        self._entity = None
        # Machine-readable outcome of the last choose_task() call (None until
        # it runs, "ok" on success). Runners surface it as
        # "task_unavailable:<reason>" so the worker can tell a HIDDEN task
        # button from SOLD-OUT stock without fragile prose matching.
        # Reasons: "unoffered" (registry refuses this bot+task), "hidden"
        # (button absent twice), "soldout" (limit/counter/0-stock or no Start
        # key), "flood" (Telegram flood-limit on this profile — slot-local,
        # never a fleet stop).
        self.last_task_verdict = None

    # -- lifecycle ------------------------------------------------------
    def start(self, **_kw):
        self._ensure_conn()
        self.log(f"[tg] Telegram MTProto session ready for {self.bot_name} "
                 f"({os.path.basename(self.session_path)}).")
        return self

    open = start

    def logged_in(self):
        """True=authorized | False=definitively logged out | None=unknown.

        ``_boot_bot`` treats ``False`` as "session lost" and DISABLES the
        profile, so a transient network failure must surface as ``None``
        (unknown), never ``False``. The old body returned
        ``bool(is_user_authorized())`` -- which is ``False`` on ANY exception --
        so every dropped connection permanently disabled a healthy account.
        """
        if self._client is None:
            self._client = _make_client(self.tg_id, self.session_path)
        _pin_loop(self._client)
        if not self._client.is_connected():
            self._client.connect()
        return self._probe_authorization()

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

    def _release_session_handle(self):
        """Force-close the session's SQLite handle and drop its file lock.

        ``disconnect()`` below only runs when the client reports ``is_connected()``.
        On a LOCK failure the client never connected, so disconnect() is a no-op
        and the sqlite connection (and its OS file lock) is leaked — which is why
        "database is locked" kept recurring on the SAME account: the pool released
        the LEASE, but the dead process still held the FILE. Telethon keeps the
        handle on ``session._conn`` and does not close it on a failed boot.

        This is pure resource cleanup — it changes no task/earning behaviour.
        """
        sess = None
        try:
            sess = getattr(self._client, "session", None)
            conn = getattr(sess, "_conn", None) or getattr(sess, "conn", None)
            if conn is not None:
                for step in (lambda: conn.commit(), conn.close):
                    try:
                        step()
                    except Exception:
                        pass
                try:
                    sess._conn = None
                except Exception:
                    pass
            fname = getattr(sess, "filename", None)
            if fname:
                _OPEN_SESSIONS.discard(os.path.abspath(fname))
        except Exception:
            pass

    def disconnect(self):
        # Release the network connection first (normal path), then ALWAYS drop
        # the SQLite handle — including when the client never connected, which
        # is exactly the lock-failure case that leaked the file before.
        try:
            if self._client is not None and self._client.is_connected():
                self._client.disconnect()
        except Exception:
            pass
        self._release_session_handle()

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
        _pin_loop(self._client)
        if not self._client.is_connected():
            self._client.connect()
        self._assert_authorized()
        if self._entity is None:
            self.open_bot()
        return self._client

    #: Marker prefix for a FAILED auth CHECK (network/lock/flood) as opposed to a
    #: genuinely revoked session. Deliberately contains none of the phrases in
    #: ``tg_support._is_tg_session_lost`` ("not logged in", "session lost", …),
    #: so a transient failure can never be classified as a dead session — which
    #: would DISABLE the profile.
    TRANSIENT_AUTH_MARKER = "transient-auth-check-failed"

    @staticmethod
    def _is_auth_death(exc) -> bool:
        """True ONLY for Telethon's definitive auth-revocation errors.

        Everything else (network drop, SQLite lock, FloodWait, timeout) is a
        TRANSIENT failure and must never be read as "logged out".
        """
        name = type(exc).__name__.upper()
        msg = str(exc).upper()
        return any(m in name or m in msg for m in (
            "AUTH_KEY_UNREGISTERED", "AUTH_KEY_INVALID",
            "SESSION_REVOKED", "SESSION_EXPIRED",
            "USER_DEACTIVATED", "AUTH_KEY_DUPLICATED"))

    def _probe_authorization(self):
        """True=authorized | False=definitively logged out | None=unknown.

        ``TelegramClient.is_user_authorized()`` swallows EVERY exception and
        returns ``False``, so a dropped connection ("Server closed the
        connection: 0 bytes read"), a SQLite lock or a FloodWait was
        indistinguishable from a revoked auth key. Callers treat ``False`` as
        "session lost" and DISABLE the profile, which turned ordinary network
        blips into permanent account loss and spammed the dashboard with
        "A Telegram session is dead". Classify by exception TYPE instead.

        ``None`` (unknown) is the safe answer for a transient failure: the
        caller keeps the profile enabled and simply retries.
        """
        try:
            me = self._client.get_me()
        except Exception as exc:
            if self._is_auth_death(exc):
                return False
            try:
                self.log(f"[tg] {os.path.basename(self.session_path)}: auth check "
                         f"failed transiently ({exc}) — session NOT considered lost.")
            except Exception:
                pass
            return None
        return me is not None

    def _assert_authorized(self):
        """Raise if the session is genuinely dead; mark transient failures apart."""
        state = self._probe_authorization()
        if state is False:
            raise RuntimeError(
                f"Telegram session is not logged in "
                f"({os.path.basename(self.session_path)}) — session lost. "
                f"Run: tg_login_mtproto.py --id {self.tg_id}")
        if state is None:
            raise RuntimeError(
                f"{self.TRANSIENT_AUTH_MARKER}: "
                f"{os.path.basename(self.session_path)}: auth check unavailable "
                f"(network/lock/flood) — session NOT lost.")
        return True

    def open_bot(self):
        """Resolve the target bot entity (MTProto has no 'open chat' step)."""
        if self._client is None:
            self._client = _make_client(self.tg_id, self.session_path)
        _pin_loop(self._client)
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

    # -- flood control ---------------------------------------------------
    # Telegram answers a rate-limited account with FloodWaitError, whose
    # ``seconds`` field says exactly how long to stop. It was being swallowed by
    # a bare ``except Exception`` upstream (reset_to_main_menu / the cookie
    # drain loop), logged as a harmless "note", and retried ~2s later — so every
    # retry landed INSIDE the penalty window and re-armed it. Observed as an
    # ever-changing "A wait of 483 / 388 / 245 ... seconds is required" on every
    # slot, cycling accounts and churning the entire pool for nothing.
    @staticmethod
    def _flood_wait_seconds(exc) -> int:
        """Seconds Telegram demands, or 0. Handles wrapped/nested/transported forms."""
        seen = 0
        cur = exc
        while cur is not None and seen < 6:
            secs = getattr(cur, "seconds", None)
            if isinstance(secs, (int, float)) and secs > 0:
                return int(secs)
            # Telethon sometimes nests the original under .original_exception.
            nxt = getattr(cur, "original_exception", None)
            if nxt is None or nxt is cur:
                break
            cur = nxt
            seen += 1
        # Fallback: parse the canonical Telethon wording. Some paths transport
        # the exception across the pool's queue (`_call` does `raise res`), and
        # an exception re-raised that way can lose the `.seconds` attribute
        # while keeping its message — which made the drain log a plain FAILED
        # instead of recognising a FloodWait (observed 2026-10-01 21:11).
        try:
            import re as _re
            m = _re.search(r"a wait of\s+(\d+)\s+seconds", str(exc), _re.I)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    def _sleep_flood(self, exc, what: str = "request") -> int:
        """Brief pause on a FloodWait, then hand the account back.

        Sleeping the FULL penalty inside the slot blocks that slot for the whole
        window while other accounts sit idle — throughput loss for no gain,
        because the account is unusable either way. So sleep only a short slice
        and report the flood; the caller releases the lease and the pool rotates.

        The account is ALSO marked ``flood_until`` so acquire() stops leasing it
        until Telegram will actually accept requests again. Without that, the
        pool kept re-leasing a flood-limited account every ~25s — a request that
        cannot succeed, and one that risks extending the penalty (observed
        2026-10-01: all 6 accounts on 3–5h waits, ~430 pointless attempts each).
        """
        secs = self._flood_wait_seconds(exc)
        if secs <= 0:
            return 0
        self._last_flood_wait = time.time() + secs
        self._record_flood_until(secs)
        try:
            cap = int(os.environ.get("INSTA_TG_FLOOD_MAX_SLEEP", "25") or 25)
        except Exception:
            cap = 25
        wait = max(1, min(secs, cap))
        self.log(f"[tg] ⏳ FloodWait {secs}s on {what} — pausing {wait}s, then the "
                 f"account is parked for {secs}s (not re-leased until Telegram "
                 f"accepts requests again).")
        end = time.time() + wait
        while time.time() < end:
            time.sleep(min(1.0, max(0.0, end - time.time())))
        return wait

    def _record_flood_until(self, seconds: int) -> None:
        """Persist the absolute time this account becomes usable again (capped to prevent multi-hour lockouts)."""
        try:
            import tg_accounts as _tgm
            mgr = getattr(_tgm, "tg_manager", None)
            if mgr is None:
                return
            mgr._reload()
            # Capping: Telegram RPC throttle must never bench an account for hours without allowing a retry.
            try:
                max_rec = int(os.environ.get("INSTA_TG_FLOOD_MAX_RECORD", "120") or 120)
            except Exception:
                max_rec = 120
            capped = max(1, min(int(seconds), max_rec))
            for a in mgr.accounts:
                if a.get("id") == self.tg_id:
                    a["flood_until"] = int(time.time() + capped)
                    break
            mgr.save()
        except Exception:
            pass

    def _clear_flood_until(self) -> None:
        """Clear any flood lockout when the account communicates successfully."""
        try:
            import tg_accounts as _tgm
            mgr = getattr(_tgm, "tg_manager", None)
            if mgr is None:
                return
            mgr.clear_flood(self.tg_id)
        except Exception:
            pass

    _last_start_times = {}

    def _is_at_main_menu(self, btns: list) -> bool:
        """Check if the reply keyboard is currently showing the bot's main menu."""
        if not btns:
            return False
        # 1. Match against the top level of any registered task for this bot
        try:
            from tg_tasks import resolve as _resolve
            for _t in ("📱 Create Inst (Cookies)", "Create Inst (No mail)",
                       "Instagram 2FA", "Create Inst (2FA)"):
                _tid, _lv = _resolve(self.bot_target, _t)
                if _lv and isinstance(_lv, list):
                    l0 = _lv[0]
                    for b in btns:
                        b_low = _norm_btn(b)
                        if isinstance(l0, dict):
                            alls = [str(x).lower() for x in (l0.get("all") or [])]
                            nones = [str(x).lower() for x in (l0.get("none") or [])]
                            if bool(alls) and all(a in b_low for a in alls) and not any(n in b_low for n in nones):
                                return True
                        elif str(l0).lower() in b_low:
                            return True
                    break
        except Exception:
            pass
        # 2. General heuristic: 'tasks' or 'balance' on the keyboard
        for b in btns:
            nb = _norm_btn(b)
            if any(k in nb for k in ("tasks", "task", "balance")):
                return True
        return False

    def reset_to_main_menu(self, timeout=15):
        """Escape to a clean menu — NEVER cancels a submitted task and NEVER spams /start (invariant 23)."""
        try:
            # Step 1: Check if already at main menu (or poll briefly up to 2.5s for keyboard)
            btns, _m = self._buttons()
            if self._is_at_main_menu(btns):
                self.log("[tg] reset_to_main_menu: already at the main menu — no send.")
                self._clear_flood_until()
                return True

            end_wait = time.time() + min(2.5, float(timeout))
            while time.time() < end_wait:
                time.sleep(0.4)
                btns, _m = self._buttons()
                if self._is_at_main_menu(btns):
                    self.log("[tg] reset_to_main_menu: already at the main menu — no send.")
                    self._clear_flood_until()
                    return True

            # Step 2: Check if task was just submitted or is under review
            low = self._last_text().lower()
            if any(p in low for p in ("report has been received", "under review", "check your work")):
                # Submitted/under-review screen: PayGo / Taskly ALWAYS provide the main menu.
                # NEVER send /start here — doing so right after task completion trips Telegram's
                # SendMessage command flood filter and triggers FloodWait 4000+s.
                self.log("[tg] reset_to_main_menu: task submitted/under review — main menu ready, zero sends.")
                self._clear_flood_until()
                return True

            # NEVER cancel a LIVE task. The bot's task keyboard ALWAYS carries a
            # Cancel button (e.g. [📥 Get code] [❌ Cancel] / [🥧 send Cookie]
            # [❌ Cancel]), so ANY errant reset — a second slot, the PayGo stock
            # probe, choose_task's retry, a stale lease — used to tap it and kill a
            # task that was mid-flight. Observed live 2026-10-03: the bot tapped
            # Cancel right after "🍪 Please send the account Cookie:", then the
            # cookie was sent into a dead task ("Action cancelled" after the
            # prompt). A task awaiting the cookie / 2FA key must be LEFT ALONE.
            if any(k in low for k in _ACTIVE_TASK_MARKERS):
                self.log("[tg] reset_to_main_menu: task is ACTIVE (awaiting cookie/key) — "
                         "NOT cancelling (invariant 23).")
                self._clear_flood_until()
                return True

            # Step 3: Handle cancel or back buttons in active sub-menus
            cbtn = next((b for b in btns if "cancel" in _norm_btn(b)), None)
            if cbtn:
                self._send(cbtn)
                time.sleep(1.0)
                btns, _m = self._buttons()
                if self._is_at_main_menu(btns):
                    self._clear_flood_until()
                    return True

            rbtn = next((b for b in btns
                         if any(k in _norm_btn(b) for k in ("return", "back", "main menu"))), None)
            if rbtn:
                self._send(rbtn)
                time.sleep(1.0)
                btns, _m = self._buttons()
                if self._is_at_main_menu(btns):
                    self._clear_flood_until()
                    return True

            # Step 4: If buttons already exist (some other sub-menu), don't blindly /start
            if self._is_at_main_menu(btns):
                self._clear_flood_until()
                return True

            # Step 5: Absolute fallback when NO buttons exist at all. Re-check
            # the chat FIRST: keyboards swap asynchronously, so "no buttons"
            # can be a transient gap on a LIVE task — /start there resets it
            # ("Our previous conversation was reset", observed 2026-10-04).
            try:
                _fresh_low = self._last_text().lower()
            except Exception:
                _fresh_low = ""
            if any(k in _fresh_low for k in _ACTIVE_TASK_MARKERS):
                self.log("[tg] reset_to_main_menu: no buttons but task looks ACTIVE — "
                         "NOT sending /start (invariant 23).")
                self._clear_flood_until()
                return True
            # Strictly throttle /start to once every 60s per account
            now = time.time()
            last_start = MtprotoTasklyBot._last_start_times.get(self.tg_id, 0.0)
            if now - last_start < 60.0:
                self.log(f"[tg] reset_to_main_menu: /start throttled ({int(60 - (now - last_start))}s cooldown left) — skipping.")
                return True

            MtprotoTasklyBot._last_start_times[self.tg_id] = now
            self.log("[tg] reset_to_main_menu: no menu buttons found — sending /start fallback.")
            self._send("/start")
            time.sleep(1.0)
            self._clear_flood_until()
            return True
        except Exception as exc:
            # A FloodWait here means Telegram is throttling this ACCOUNT, not a
            # broken menu. Sleeping it out is the whole point — retrying early
            # re-arms the penalty and burns the slot.
            if self._sleep_flood(exc, "reset_to_main_menu"):
                return False
            self.log(f"[tg] reset_to_main_menu note: {exc}")
            return False

    def cancel_task(self):
        """Cancel a PENDING task — NEVER a submitted one (invariant 23).

        This was UNGUARDED, and the drain's error handler calls it on every
        failure. So a failed cycle sent Cancel, PayGo replied "Our previous
        conversation was reset, please start again from the main menu", and the
        NEXT cycle then found a reset menu and failed with
        "'📱 Create Inst (Cookies)' not available right now (level 2/3 missing)"
        — which failed again, cancelled again. A self-sustaining failure loop
        (observed 2026-10-01 22:02: tg_2/tg_4/tg_6 all stuck on it while only
        tg_5 completed).

        It also risked destroying a real submission: with a task submitted and
        "under review", a Cancel would throw the work away. reset_to_main_menu
        already refuses in that state; this now matches it.
        """
        try:
            low = self._last_text().lower()
            if any(p in low for p in ("report has been received", "under review", "check your work")):
                self.log("[tg] cancel_task: task looks SUBMITTED/under review — "
                         "refusing to cancel (invariant 23).")
                return False
            # Same live-task guard as reset_to_main_menu: a task awaiting the
            # cookie / 2FA key must not be cancelled by an unrelated error path.
            if any(k in low for k in _ACTIVE_TASK_MARKERS):
                self.log("[tg] cancel_task: task is ACTIVE (awaiting cookie/key) — "
                         "refusing to cancel (invariant 23).")
                return False
            btns, _m = self._buttons()
            cbtn = next((b for b in btns if "cancel" in b.lower()), None)
            if cbtn:
                self._send(cbtn)
                return True
        except Exception:
            pass
        return False

    def clear_orphan_task(self):
        """Cancel ONE orphan task left by a killed engine — fresh-lease startup only.

        After a preempt/SIGTERM the old engine is dead but its bot tasks stay
        live on every TG account. A fresh cycle inheriting such a chat can
        never walk the menu (mid-task keyboards hold no task buttons), so it
        spins on hidden forever — observed 2026-10-04: 5/6 cookie slots stuck
        while the ACTIVE guards protected the corpses. Call ONCE right after
        leasing, NEVER mid-cycle (mid-cycle keeps refusing via cancel_task).
        Still refuses submitted/under-review states. Probes never Start, so a
        racing probe's preview is the only collateral — and it fails open.
        """
        try:
            low = self._last_text().lower()
            if any(p in low for p in ("report has been received", "under review", "check your work")):
                self.log("[tg] clear_orphan_task: task looks SUBMITTED/under review — leaving it.")
                return False
            btns, _m = self._buttons()
            cbtn = next((b for b in btns if "cancel" in _norm_btn(b)), None)
            if cbtn:
                self._send(cbtn)
                self.log("[tg] clear_orphan_task: cancelled one orphan task from a dead run — menu should be clean.")
                time.sleep(1.5)
                return True
            rbtn = next((b for b in btns
                         if any(k in _norm_btn(b) for k in ("return", "back", "main menu"))), None)
            if rbtn:
                self._send(rbtn)
                time.sleep(1.0)
                return True
            # No button visible, but the chat is on an ACTIVE task prompt (an
            # orphan from a dead run). Telegram bots also accept the reply-keyboard
            # button TEXT as a plain message, so send "Cancel" to clear the corpse
            # — otherwise the menu walk can never find the task buttons and every
            # cycle reports [task_unavailable:hidden] even though the task IS
            # available (operator 2026-10-07).
            if any(k in low for k in _ACTIVE_TASK_MARKERS):
                self._send("Cancel")
                time.sleep(1.5)
                _low2 = ""
                try:
                    _low2 = self._last_text().lower()
                except Exception:
                    pass
                if any(k in _low2 for k in _ACTIVE_TASK_MARKERS):
                    self._send("Return to main menu")
                    time.sleep(1.5)
                self.log("[tg] clear_orphan_task: sent Cancel text to clear an active orphan task.")
                return True
            return True
        except Exception as exc:
            self.log(f"[tg] clear_orphan_task note: {exc}")
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

    def choose_task(self, task=TG_DEFAULT_TASK, level_timeout=8.0, tries=2):
        """Walk the registry button path for this bot — strict, no fallback.

        ``tg_tasks.resolve`` maps the requested task for THIS bot only. An
        unknown task, or a task the bot does not offer (e.g. "No mail" on
        PayGo, "Cookies" on Taskly), returns False WITHOUT touching any
        other button — the old alias-remap/fuzzy fallbacks that silently
        started the wrong task are gone. Stock gaps (task temporarily
        absent) poll each level briefly, then fail loud with the missing
        level so the cycle cancels instead of improvising.

        Records ``self.last_task_verdict`` ("ok" | "unoffered" | "hidden" |
        "soldout" | "flood") for the fleet availability gate.
        """
        try:
            from tg_tasks import resolve, LABELS
        except ImportError:
            self.last_task_verdict = "hidden"
            self.log("[tg] tg_tasks registry unavailable — refusing to pick")
            return False
        task_id, levels = resolve(self.bot_target, task)
        if task_id is None:
            self.last_task_verdict = "unoffered"
            self.log(f"[tg] ❌ {levels} (task={task!r}, bot={self.bot_target})")
            return False
        self.last_task_verdict = None
        want = LABELS.get(task_id, task)
        # Only the Cookies tasks publish the hourly stock counter
        # ("Available this hour: 0/5700"). A stale 0-stock message from an
        # earlier Cookies check must never mark a 2FA task sold out.
        is_cookies_task = "cookie" in str(task_id or "").lower()
        for _try in range(max(1, int(tries or 1))):
            if not self.reset_to_main_menu():
                if getattr(self, "_last_flood_wait", 0) > time.time():
                    self.last_task_verdict = "flood"
                    self.log("[tg] choose_task: aborting — account is currently flood-limited by Telegram.")
                    return False
            try:
                base_id = self._last_id() or 0
            except Exception:
                base_id = 0
            navigated = []
            failed = None
            for depth, level in enumerate(levels):
                pick = self._await_level(level, timeout=level_timeout)
                if not pick:
                    failed = depth
                    break
                self._send(pick)
                navigated.append(pick)
                time.sleep(1.2)
            if failed is None:
                for p in navigated:
                    self.log(f"[tg] Selected task: {p}")
                # Sold-out check — FRESH messages only (posted after our
                # selection). Scanning stale history made an old Cookies
                # "0/5700" or an old limit notice veto a healthy 2FA pick.
                try:
                    fresh = []
                    for m in self._messages(limit=10, min_id=base_id):
                        if getattr(m, "out", False):
                            continue
                        t = (getattr(m, "text", "") or "").strip()
                        if t:
                            fresh.append(t)
                        if len(fresh) >= 4:
                            break
                except Exception:
                    fresh = []
                for t in fresh:
                    if _is_hour_limit(t, cookies=is_cookies_task):
                        self.last_task_verdict = "soldout"
                        self.log(f"[tg] choose_task: {self.bot_target} hourly limit reached: {t.strip()[:120]}")
                        return False
                # The bot answers with the task preview, whose keyboard
                # carries "▶️ Start". (FastPay has no Start button — selecting task issues creds immediately).
                if self.bot_target != "fastpay":
                    if not self._wait_for_button("start", timeout=12):
                        self.last_task_verdict = "soldout"
                        self.log(f"[tg] ⚠️ task selected but no Start key appeared (sold out or limit reached)")
                        return False
                self.last_task_verdict = "ok"
                return True
            self.last_task_verdict = "hidden"
            self.log(f"[tg] '{want}' not available right now "
                     f"(level {failed + 1}/{len(levels)} missing; "
                     f"had: {navigated or 'main menu'}) — not substituting.")
        self.last_task_verdict = "hidden"
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
                    for m in reversed(self._messages(limit=6)):
                        txt = (getattr(m, "text", "") or "").replace("`", "").replace("*", "")
                        if re.search(r"(?:Login|Username):\s*.+", txt, re.I) and re.search(r"Password:\s*\S+", txt, re.I):
                            found = self._parse_creds(txt)
                            if found and found.get("login") and found.get("password"):
                                self.creds = found
                                self.log(f"[tg] start_task: recovered active creds already sent by bot → {self.creds}")
                                return self.creds
                    for t in self._recent_texts(4):
                        tl = t.lower()
                        if _is_hour_limit(t, cookies=True):
                            self.log(f"[tg] start_task: {self.bot_target} hourly limit reached: {t.strip()}")
                            return {"error": "limit_reached", "detail": t.strip(), "login": "", "password": ""}
                    self.log("[tg] start_task: 'Start' button not present on screen")
                    return {"first_name": "", "login": "", "password": ""}
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
                    if _is_hour_limit(txt, cookies=True):
                        self.log(f"[tg] start_task: {self.bot_target} hourly limit reached: {txt[:80]}")
                        found = {"error": "limit_reached", "detail": txt.strip(), "login": "", "password": ""}
                        break
                    if re.search(r"Login:\s*.+", txt, re.I) and re.search(r"Password:\s*\S+", txt, re.I):
                        found = self._parse_creds(txt)
                        break
                if rate_limited or found:
                    break
            if found and found.get("error") == "limit_reached":
                return found
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
        clean = re.sub(r"[^A-Za-z2-7]", "", str(key or "")).upper()
        # Fail-safe: check if task is already canceled or timed out
        last_t = (self._last_text() or "").lower()
        if any(c in last_t for c in ("time's up", "time’s up", "action cancelled", "action canceled", "task cancelled", "task canceled")):
            self.log(f"[tg] ⚠️ Bot already reported expired/cancelled ('{last_t[:60]}') — aborting 2FA submit.")
            raise RuntimeError(f"bot_task_expired: {last_t[:60]}")

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
                if any(c in txt.lower() for c in ("time's up", "time’s up", "action cancelled", "action canceled", "task cancelled", "task canceled")):
                    self.log(f"[tg] ⚠️ Bot task cancelled during 2FA wait: {txt[:80]}")
                    raise RuntimeError(f"bot_task_expired: {txt[:80]}")
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
        _taps = 1
        _last_tap = time.time()
        _last_new = time.time()
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
                _last_new = time.time()
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
                # Bot mailbox still ordering ("Code not found" / "please wait"):
                # the single Get-code tap is spent — re-tap so the code is
                # actually issued instead of passively waiting out the clock.
                # Worst case the loop still ends at `deadline` and the caller
                # falls through to the 2FA submit.
                low = txt.lower()
                if (_taps < 3 and time.time() - _last_tap >= 10.0
                        and any(k in low for k in ("code not found", "not found",
                                                   "ordering email", "please wait"))):
                    try:
                        btns, _msg = self._buttons(limit=10)
                    except Exception:
                        btns = []
                    hit = next((b for b in btns or [] if "get code" in _norm_btn(b)), None)
                    if hit:
                        self._send(hit)
                        _taps += 1
                        _last_tap = time.time()
                        self.log(f"[tg] re-tapped '{hit}' ({_taps}/3 — bot said: {txt.strip()[:60]})")
            # Silent mailbox (no new bot message at all — cold order takes ~75s
            # on first tap, re-tap answers in ~1s live 2026-10-04): one scheduled
            # re-tap instead of waiting out the clock.
            if (_taps < 3 and time.time() - _last_tap >= 15.0
                    and time.time() - _last_new >= 15.0
                    and time.time() + 5.0 < deadline):
                try:
                    btns, _msg = self._buttons(limit=10)
                except Exception:
                    btns = []
                hit = next((b for b in btns or [] if "get code" in _norm_btn(b)), None)
                if hit:
                    self._send(hit)
                    _taps += 1
                    _last_tap = time.time()
                    self.log(f"[tg] re-tapped '{hit}' ({_taps}/3 — silent wait, nudging the order)")
        self.log("[tg] ❌ bot sent no email code in time")
        return ""

    def press_get_code(self, wait: float = 6.0):
        """Press 📥 Get code to advance the bot past its email step.

        PayGo/Taskly's "Create Inst (2FA)" task prompts "press the button to get
        the code" for the bot-issued email, and only opens the "send the 2FA
        Key" prompt AFTER that press. When Instagram reports the email is
        ALREADY linked, ``ig_link_email_to_instagram`` never calls the code
        fetcher — so without this the bot stays parked on the email step and the
        later ``submit_2fa_key`` gets no one-time code back ("Telegram bot did
        not return a one-time code"). Presses the key and returns the bot's
        first reply (a fresh 6-digit code when one is issued, else the ack text
        like "already linked", else "").
        """
        try:
            btns, _ = self._buttons(limit=10)
        except Exception:
            btns = []
        hit = next((b for b in btns or [] if "get code" in _norm_btn(b)), None)
        if not hit:
            self.log("[tg] Get-code key not visible — nothing to advance.")
            return ""
        before_id = self._last_id()
        self._send(hit)
        self.log(f"[tg] pressed '{hit}' to advance the email step…")
        end = time.time() + max(2.0, float(wait or 0))
        reply = ""
        while time.time() < end:
            time.sleep(0.5)
            new = ""
            for m in self._messages(limit=4):
                if getattr(m, "out", False):
                    continue
                if int(getattr(m, "id", 0) or 0) <= int(before_id or 0):
                    continue
                t = (getattr(m, "text", "") or "").replace("`", "").strip()
                if t:
                    new = t
            if new:
                reply = new
                break
        self.log(f"[tg] Get-code advance reply: {reply[:80] or '(none yet)'}")
        return reply

    def _wait_for_cookie_prompt(self, timeout: float = 60.0) -> bool:
        """Wait until the bot explicitly asks for the account cookie.

        PayGo's "📱 Create Inst (Cookies)" flow says
        "🍪 Please send the account Cookie:" only AFTER the account is ready.
        Sending the cookie before that prompt lands out of order (the bot
        replies with a stale/placeholder verdict or ignores it), so the send is
        gated on the prompt.
        """
        deadline = time.time() + max(5.0, timeout)
        while time.time() < deadline:
            for m in self._messages(limit=8):
                if getattr(m, "out", False):
                    continue
                t = (getattr(m, "text", "") or "").lower()
                if ("send the account cookie" in t
                        or "account cookie" in t
                        or "send the cookie" in t
                        or "please send the cookie" in t
                        or "please send your cookie" in t
                        or "please send cookies" in t
                        or ("send" in t and "cookie" in t)):
                    return True
            # A "send … cookie" reply key also means the prompt is up. Require
            # BOTH words so the task menu button "📱 Create Inst (Cookies)"
            # (has "cookie" but not "send") never counts as the prompt.
            try:
                btns, _ = self._buttons(limit=3)
                if any(("send" in (b or "").lower() and "cookie" in (b or "").lower()) for b in btns):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False

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
        # Do NOT send until the bot asks for the cookie (see
        # _wait_for_cookie_prompt). Sending before the prompt lands out of
        # order — this is what the pool path hit (rename is ~0.4s, the prompt
        # had not arrived yet).
        if not self._wait_for_cookie_prompt(timeout=3.0):
            # The 2FA step (when a task needs one) runs BEFORE this call and, on
            # FAILURE, the caller aborts instead of submitting — so we never reach
            # here while the bot is genuinely waiting for the 2FA key. Detection
            # can still miss the prompt text (message window / edited message /
            # emoji), so SEND the cookie anyway (best-effort) instead of blocking
            # a live task (that guard wrongly blocked the cookie right after a
            # SUCCESSFUL 2FA — the exact bug).
            self.log("[tg] 'Please send the account Cookie' prompt not seen — sending the cookie anyway (best-effort).")
        before_id = self._last_id()
        self._send(clean)
        self.log(f"[tg] Cookie submitted to {self.bot_name} ({len(clean)} chars); waiting for verdict…")
        deadline = time.time() + min(max(4.0, timeout), 15.0)
        reply = ""
        _poll = 0
        while time.time() < deadline:
            time.sleep(0.25)
            _poll += 1
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
                # NEW PayGo cookie protocol (2026-10-07): AFTER the cookie the bot
                # asks "Did you make 5 subscriptions after registration? …" and
                # only accepts the report once the affirmative key is tapped.
                # Treat it as cookie-accepted so mark_registered() taps "Yes".
                if "subscription" in low and ("5" in low or "made" in low or "did you" in low):
                    self.log(f"[tg] cookie accepted → bot asks the 5-subscription confirmation: {txt[:120]}")
                    return True, txt
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
            # Fallback (every ~1s): the register key appearing means it passed.
            if _poll % 4 == 0:
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
        """Drive the register/confirm chain and classify the FINAL reply.

        The bot can ask MORE THAN ONE question in a row — observed live on
        Taskly's cookie task: "👉 Press the button to confirm registration"
        (→ "✅ Account registered"), and only THEN "Did you make 5
        subscriptions?" (→ "✅ Yes, I made 5+ subscriptions"). The old single-tap
        version tapped the first key, waited the full 8s for a verdict that never
        came, returned False, and left the caller's 1.2s retry to tap the second
        key — ~15s wasted per account. This follows the whole chain in ONE call.
        """
        self.open_bot()
        for _round in range(3):
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
            # 2b. PayGo/Taskly's mandatory 5-subscription confirmation.
            if not pick:
                pick = next((b for b in btns
                             if _is_subscription_confirm(b)
                             and not any(x in _norm_btn(b) for x in _REGISTER_BAD)), None)
            # 3. Inline button fallback.
            inline_pick = None
            if not pick:
                for t, data, row in inline:
                    low = (t or "").lower()
                    if any(x in low for x in _REGISTER_BAD):
                        continue
                    if "regist" in low or "confirm" in low or _is_subscription_confirm(t):
                        inline_pick = row
                        break
            if not pick and inline_pick is None:
                if _round == 0:
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

            # Short poll — the bot answers in ~1s. 5s is plenty (the old 8s stall
            # was pure dead time before the caller's retry).
            verdict = "unknown"
            new_text = ""
            deadline = time.time() + 5.0
            while time.time() < deadline:
                time.sleep(0.25)
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
                    # A follow-up QUESTION (e.g. the 5-subscription confirm) is not
                    # a final verdict — stop waiting NOW and tap its key next round
                    # instead of burning the full 5s poll.
                    if _is_subscription_confirm(new_text) or "subscription" in new_text.lower():
                        break
                    verdict = classify_report_reply(new_text)
                    if verdict != "unknown":
                        break

            if verdict == "rejected":
                self.log(f"[tg] ❌ bot REJECTED the report — NOT recording Submitted | '{new_text[:160]}'")
                return False
            if verdict == "accepted":
                self.log("[tg] submitted=True (verdict=accepted)")
                return True
            # Not final: the bot most likely asked ANOTHER question (e.g. the
            # 5-subscription confirm) — tap its key next round instead of
            # returning False and paying the caller's retry stall.
            self.log(f"[tg] register round {_round + 1}: no final verdict yet "
                     f"('{new_text[:70]}') — checking for a follow-up key…")
        self.log("[tg] no fresh verdict after register chain — treating as UNCONFIRMED (not rejected).")
        return False

    def get_last_task_verdict(self):
        return getattr(self, "last_task_verdict", None)


def probe_task_availability(bot_target, task, level_timeout=8.0, tries=2):
    """Single-lease availability probe: is ``task`` currently pickable on ``bot_target``?

    Non-blocking: acquires an idle profile with timeout=0 and releases it in
    ``finally`` — never disturbs running workers. Walks the registry button
    path WITHOUT pressing Start (choose_task never starts anything), so the
    probe creates no task and costs nothing.

    Returns {"ok": True, "available": bool, "reason": ...} where reason is one
    of "ok" | "unoffered" | "hidden" | "soldout" | "flood". {"ok": False,
    "busy": True} when every profile is leased (callers should fail OPEN and
    let the mid-run all-slots gate decide).
    """
    try:
        import tg_accounts as _tgm
    except ImportError:
        return {"ok": False, "error": "tg_accounts unavailable"}
    try:
        manager = _tgm.tg_manager
        if not manager.usable():
            return {"ok": False, "error": "No usable Telegram accounts in pool"}
        acct = manager.acquire(timeout=0.0, bot="task_probe")
        if not acct:
            return {"ok": False, "busy": True,
                    "error": "All Telegram profiles busy — skipping pre-flight probe"}
        tg_id = acct.get("id")
        bot = None
        try:
            bot = MtprotoTasklyBot(session_path=session_file(tg_id),
                                   tg_id=tg_id, bot_target=(bot_target or "taskly").lower(),
                                   log=lambda *a: None)
            bot.start()
            picked = bot.choose_task(task, level_timeout=level_timeout, tries=tries)
            verdict = bot.last_task_verdict or ("ok" if picked else "hidden")
            return {"ok": True, "available": bool(picked), "reason": verdict,
                    "tg_id": tg_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}
        finally:
            try:
                if bot is not None:
                    bot.disconnect()
            except Exception:
                pass
            try:
                manager.release(tg_id)
            except Exception:
                pass
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


# Pooled warm workers now live in mtproto_pool (pure code move). Re-exported
# here so existing callers (``pipelines/telegram/tg_support.py``, ``worker.py``)
# keep importing them from ``mtproto_bot``. This late import is required to
# avoid a cycle: mtproto_pool imports MtprotoTasklyBot from this module, which
# is defined by the time execution reaches here.
from mtproto_pool import MtprotoPooledBot, _mtproto_owner_loop  # noqa: E402,F401
