"""Shared Telegram-pipeline helpers: bot factory, name hygiene, inspector registry.

Split out of the former 1488-line ``pipelines/telegram/tg_worker.py`` (2026-09-25).
Everything here is reusable machinery rather than a pipeline step:
  * ``_make_tg_bot`` / ``_drop_tg_bot`` — per-record transport dispatch
    (``mode == "mtproto"`` selects Telethon, else Telegram Web),
  * the name/username sanitizers (IG's 29-char limit, styled Taskly names),
  * ``_boot_bot`` — drive the bot to a usable state, with session-loss detection,
  * the **bounded inspector registry** (``_register_inspector`` /
    ``close_inspectors`` / ``_force_close``) — invariant #26: a strict failure
    must not leak Chromium trees, so retention is opt-in and count-capped,
  * ``_reap_wedged_tg_browser`` / ``_cancel_with_timeout``.

The coupled-cycle's own mutable state (``_task_unavailable_strikes``) deliberately
lives in :mod:`pipelines.telegram.tg_coupled` instead — it is used only there.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
import unicodedata
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai_config import (  # noqa: E402
    DATA_DIR,
    SELFIE_PATH,
    TG_DEFAULT_TASK,
    emit_event,
)
from runner import MetaInstaRunner  # noqa: E402
import store  # noqa: E402

from tg_accounts import tg_manager  # noqa: E402
from tg_bot import PooledTelegramBot  # noqa: E402
from mtproto_bot import MtprotoPooledBot  # noqa: E402
try:
    from instagram.helpers import IGDeadEnd
except ImportError:  # pragma: no cover
    class IGDeadEnd(Exception):  # type: ignore
        pass

# Dead-end types share the "close out, move on, never submit" semantics
# (invariant #17).
_DEAD_ENDS = (IGDeadEnd,)

def _make_tg_bot(acct, bot_target, is_headless, log):
    """Construct the Telegram submitter for this pool record.

    ``mode == "mtproto"`` selects the Telethon backend (no browser); anything
    else uses the Telegram Web pool. Both expose the same method surface, so
    every caller below is transport-agnostic.
    """
    if str(acct.get("mode") or "").lower() == "mtproto":
        return MtprotoPooledBot(session_path=acct.get("session_file"),
                                tg_id=acct.get("id"), bot_target=bot_target,
                                headless=is_headless, log=log)
    return PooledTelegramBot(profile_dir=acct["profile_dir"], bot_target=bot_target,
                             headless=is_headless, log=log)


def _drop_tg_bot(acct) -> None:
    """Free the warm worker for a pool record (transport-aware)."""
    try:
        if str(acct.get("mode") or "").lower() == "mtproto":
            MtprotoPooledBot.drop_profile(acct.get("session_file"))
        else:
            PooledTelegramBot.drop_profile(acct.get("profile_dir"))
    except Exception:
        pass


# -- shared credential hygiene (also imported by core/lifecycle.adapt_to_tg_task)
def _sanitize_name(val: str, fallback: str = "Alex") -> str:
    """Strip emojis/symbols from a bot display name, keeping clean letters."""
    if not val:
        return fallback
    s = str(val)
    if not any(unicodedata.category(c).startswith("L") for c in s):
        return fallback
    leet = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"}
    chars = []
    for ch in s:
        if ch in leet:
            chars.append(leet[ch])
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            chars.append(ch)
        elif ch in ("'", "-"):
            chars.append(ch)
        else:
            chars.append(" ")
    cleaned = re.sub(r"\s+", " ", "".join(chars)).strip().strip("-' ")
    if len(cleaned) < 2:
        return fallback
    # Collapse a doubled phrase ("Real Baskaran Real Baskaran" — bot echo)
    # plus any consecutive duplicate words.
    try:
        _words = cleaned.split(" ")
        if len(_words) % 2 == 0 and len(_words) >= 2:
            _half = len(_words) // 2
            if [w.lower() for w in _words[:_half]] == [w.lower() for w in _words[_half:]]:
                _words = _words[:_half]
        _words = [w for i, w in enumerate(_words)
                  if i == 0 or w.lower() != _words[i - 1].lower()]
        cleaned = " ".join(_words).strip()
        if len(cleaned) < 2:
            return fallback
    except Exception:
        pass
    if cleaned.islower():
        cleaned = cleaned.title()
    return cleaned


def _clean_username(val: str) -> str:
    if not val:
        return ""
    s = str(val).strip().lstrip("@")
    # Normalize internal spaces to underscores (e.g. 'cantikcati073emai6l 2' -> 'cantikcati073emai6l_2')
    s = re.sub(r"\s+", "_", s)
    # Strip any characters not allowed in Instagram usernames
    s = re.sub(r"[^a-zA-Z0-9._]", "", s)
    # Prevent consecutive periods and trailing/leading periods
    s = re.sub(r"\.{2,}", ".", s)
    s = s.strip(".")
    return s[:30]


def _is_valid_ig_username(val: str) -> bool:
    if not val or len(val) > 30:
        return False
    return bool(re.match(r"^(?!.*\.\.)(?!^\.)(?!.*\.$)[a-zA-Z0-9._]{1,30}$", val))


def _is_junk_name(raw: str) -> bool:
    """True when a bot display name is unusable channel-forward junk.

    Live 2026-09-18 (tg_1 history): the bot sometimes echoes a forwarded
    channel tag instead of a person name, e.g. "santu and 1053 others".
    Such names get cancelled + re-requested like malformed logins.
    """
    s = (raw or "").strip()
    if not s:
        return True
    if re.search(r"\band\b.{0,12}\bothers\b", s, re.I) and re.search(r"\d", s):
        return True
    letters = sum(1 for c in s if unicodedata.category(c).startswith("L"))
    if letters < 2 or len(s) > 40 or letters / max(1, len(s)) < 0.3:
        return True
    return False


# Valid, human display names for when the bot's first_name is unusable
# (channel-forward junk / symbol soup / >29 chars — IG rejects "Enter a name
# under 30 characters"). Operator decision 2026-09-21: never fail the task over
# the NAME; only the login + password matter to Taskly.
_RANDOM_DISPLAY_NAMES = (
    "Alex Smith", "Maria Lopez", "David Brown", "Sara Miller", "John Carter",
    "Nina Patel", "Lucas Moore", "Emma Wilson", "Daniel Reed", "Laura Diaz",
)


def _random_display_name() -> str:
    import random as _random
    return _random.choice(_RANDOM_DISPLAY_NAMES)


def _ig_name_too_long(s: str) -> bool:
    """IG counts **UTF-16 code units**, and styled/astral letters (gothic 𝕹, etc.)
    are 2 units each — so a 15-char gothic name is 30+ and IG rejects it with
    'Enter a name under 30 characters'. Check the same way IG does."""
    try:
        return (len((s or "").encode("utf-16-le")) // 2) > 29
    except Exception:
        return len(s or "") > 29


def _is_tg_session_lost(msg) -> bool:
    """True when a bot-boot failure means the profile has NO live web session.

    Only strong login signatures count (QR / "log in to Telegram" / "not
    logged in"). A merely *locked* profile deliberately does NOT match: that
    is a transient single-owner conflict, not a dead session, and disabling
    the account for it would wrongly remove a healthy profile.
    """
    s = str(msg or "").lower()
    return any(sign in s for sign in (
        "not logged in",
        "no longer logged in",
        "session lost",
        "log in to telegram",
        "log in by qr",
        "scan this code",
        "log in by phone number",
    ))


def _boot_bot(b):
    """Boot the pooled bot browser and open its chat; returns (ok, message).

    On failure the message carries an explicit ``not logged in`` marker when
    the cause is a DEAD Telegram session, so the coupled cycle can dynamically
    disable that pool profile and continue on the remaining ones instead of
    failing the whole task (and burning the Meta account created in step 1).
    A live probe disambiguates the "logged out?" case from "profile locked".
    """
    def _session_lost(exc_msg="") -> bool:
        # The owner thread drops the page on a start() failure, so the probe
        # may be unavailable (None) — only an explicit False means logged out.
        # A WEDGED owner ("hung on") must not be probed: that would just stack
        # another 180s wait behind the stuck command. The caller's except
        # handler reaps it instead.
        if "hung on" in str(exc_msg).lower():
            return False
        try:
            state = b.logged_in() if hasattr(b, "logged_in") else None
        except Exception:
            state = None
        return state is False

    def _lost_msg() -> str:
        return (f"{b.bot_name}: Telegram profile is not logged in "
                f"({os.path.basename(b.profile_dir or '')}) — session lost.")

    try:
        if hasattr(b, "open") and callable(b.open):
            b.open()
        else:
            b.start()
    except Exception as exc:
        return False, _lost_msg() if (_is_tg_session_lost(exc)
                                      or _session_lost(exc)) \
            else f"bot start failed: {exc}"
    try:
        if not b.open_bot():
            if _session_lost():
                return False, _lost_msg()
            # Genuinely locked / unresponsive — NOT a session loss. Keep the
            # wording free of login signatures so it is never auto-disabled.
            return False, (f"{b.bot_name} chat could not be opened "
                           "(profile locked or unresponsive?)")
    except Exception as exc:
        return False, _lost_msg() if (_is_tg_session_lost(exc)
                                      or _session_lost(exc)) \
            else f"open_bot failed: {exc}"
    return True, ""



# Bounded registry of browsers deliberately left open on a strict failure (for
# manual inspection). Previously EVERY failure left one open, so a long run
# accumulated dozens of Chromium instances (~1-2 GB each) and exhausted device
# RAM ("Application Stopped — memory nearly full"). Keep at most N; close the
# oldest beyond that. Override with INSPECT_BROWSER_CAP.
_open_inspectors: list = []
_inspect_lock = threading.Lock()
_INSPECT_CAP = max(0, int(os.environ.get("INSPECT_BROWSER_CAP", "6")))
# Retention of stuck VISIBLE browsers is now OPT-IN. By default a strict failure
# closes the browser in headed mode too (like headless) — stuck windows + their
# tabs accumulated RAM/clutter. Set INSPECT_KEEP_VISIBLE=1 to keep up to
# INSPECT_BROWSER_CAP windows open for manual inspection.
_INSPECT_KEEP_VISIBLE = os.environ.get("INSPECT_KEEP_VISIBLE", "0") == "1"


def _inspector_keeps(headless: bool) -> bool:
    """True when a strict-failure browser will be RETAINED for inspection."""
    return (not headless) and _INSPECT_CAP > 0 and _INSPECT_KEEP_VISIBLE


def _force_close(runner, log=None) -> None:
    """Close a retained browser FOR REAL (cross-thread-safe).

    Playwright's sync API is **thread-affine**: the coupled loop runs each cycle
    in a fresh thread, so ``finish()`` on a runner created in an EARLIER cycle
    thread raises (and ``finish()`` swallows it) — the Chromium tree stays alive
    and RAM leaks. Observed live 2026-09-20: 27 held ``insta_*`` browsers vs an
    inspect cap of 6. After ``finish()`` we also SIGTERM any Chromium still
    holding the profile dir, which is thread-agnostic.
    """
    prof = ""
    try:
        prof = str(getattr(getattr(runner, "w", None), "user_data_dir", "") or "")
    except Exception:
        prof = ""
    try:
        runner.finish()
    except Exception:
        pass
    if prof:
        try:
            _reap_wedged_tg_browser(prof, log)
        except Exception:
            pass


def _capture_failure_evidence(runner, log=None) -> str:
    """Save a screenshot + page HTML + URL for a closing headless browser.

    Headless parity (invariant #37): a headed run leaves a visible window on a
    strict failure (INSPECT_KEEP_VISIBLE=1) and you inspect it live. Headless
    has no window, so before the browser is closed we capture the same evidence
    to disk. The run stays just as diagnosable; you read a PNG + HTML instead of
    a live window. Skipped with INSPECT_HEADLESS_EVIDENCE=0.
    """
    if str(os.environ.get("INSPECT_HEADLESS_EVIDENCE", "1")).strip().lower() in (
            "0", "false", "no", "off"):
        return ""
    try:
        page = runner._ig_tab()
    except Exception:
        page = getattr(runner, "page", None)
    if page is None:
        return ""
    try:
        ident = str(getattr(getattr(runner, "w", None), "slot_id", "x"))
    except Exception:
        ident = "x"
    out_dir = os.path.join(BASE_DIR, "logs", "evidence")
    try:
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join(out_dir, f"slot{ident}_{stamp}")
        try:
            page.screenshot(path=base + ".png", full_page=True, timeout=15000)
        except Exception:
            pass
        try:
            with open(base + ".html", "w", encoding="utf-8") as fh:
                fh.write(page.content())
        except Exception:
            pass
        try:
            with open(base + ".txt", "w", encoding="utf-8") as fh:
                fh.write(f"url={page.url}\n")
        except Exception:
            pass
        if log:
            log(f"[🔍] Headless failure evidence saved: {base}.png/.html")
        return base
    except Exception:
        return ""


def _register_inspector(runner, log=None, headless=False) -> bool:
    """Handle a strict-failure browser: retain (opt-in) or CLOSE it.

    Headless always closes — there is no window to look at. Headed now also
    closes by default; retention is opt-in via ``INSPECT_KEEP_VISIBLE=1``
    (cap ``INSPECT_BROWSER_CAP``). Returns True when the browser was retained,
    False when it was closed.

    Headless == visible parity: before the browser is closed we capture the
    evidence a retained window would have shown (screenshot + HTML + URL) to
    ``logs/evidence/`` — in BOTH modes. Previously evidence was captured only
    when headless, so with the default (``INSPECT_KEEP_VISIBLE=0``) a *visible*
    run was actually LESS diagnosable than a headless one.
    """
    if runner is None:
        return False
    if not _inspector_keeps(headless):
        try:
            _capture_failure_evidence(runner, log)
        except Exception:
            pass
        _force_close(runner, log)
        return False
    try:
        with _inspect_lock:
            _open_inspectors.append(runner)
            while len(_open_inspectors) > _INSPECT_CAP:
                old = _open_inspectors.pop(0)
                _force_close(old, log)
                if log:
                    log(f"[tg] cap {_INSPECT_CAP} reached — closed oldest inspection browser")
    except Exception:
        pass
    return True


def close_inspectors(reason="", log=None) -> int:
    """Close EVERY retained inspection browser and return how many were freed.

    Called by the memory guard (``mem_guard``) under pressure and on shutdown.
    These browsers are the cheapest memory to reclaim: they are deliberately
    left open only for manual inspection, so dropping them cannot break a run.
    """
    freed = 0
    while True:
        with _inspect_lock:
            if not _open_inspectors:
                break
            old = _open_inspectors.pop(0)
        _force_close(old, log)
        freed += 1
    if log and freed:
        log(f"[tg] closed {freed} inspection browser(s){(' — ' + reason) if reason else ''}")
    return freed
def _reap_wedged_tg_browser(profile_dir: str, log=None) -> None:
    """Kill leftover Chromium holding a TG profile dir, then drop its pool owner.

    Live 2026-09-19: a bot-thread queue-timeout ("hung on", 180s) leaves the
    owner thread stuck inside the hung command on the shared tg_<id> browser.
    The pool entry survives, so the NEXT lease reuses the same wedged browser
    and hangs too — every later cycle burns a Meta account for nothing. Reap
    the OS process (the hung Playwright call raises on target-close, freeing
    the zombie) and drop the pool entry so the next lease spawns fresh.
    """
    import signal as _signal
    import subprocess as _sp
    say = log or (lambda m: print(m, flush=True))
    try:
        ps = _sp.run(["pgrep", "-af", f"user-data-dir={profile_dir}"],
                     capture_output=True, text=True, timeout=15).stdout
        for line in (ps or "").splitlines():
            if "pgrep" in line:
                continue
            import re as _re
            m = _re.match(r"\s*(\d+)", line)
            if not m:
                continue
            try:
                say(f"[tg] Reaping wedged TG browser pid {m.group(1)} ({profile_dir[-12:]})…")
                import os as _os
                _os.kill(int(m.group(1)), _signal.SIGTERM)
            except Exception:
                pass
    except Exception as exc:
        say(f"[tg] reap pgrep note: {exc}")
    try:
        PooledTelegramBot.drop_profile(profile_dir)
    except Exception:
        pass
    try:
        # MTProto pool key is the session path; for web records this is a no-op.
        MtprotoPooledBot.drop_profile(profile_dir)
    except Exception:
        pass
    try:
        time.sleep(3)
    except Exception:
        pass


def _cancel_with_timeout(bot, log, timeout: int = 60) -> bool:
    """Best-effort bot.cancel_task() capped at `timeout` seconds.

    The pooled _call has a 180s queue timeout — far too long to block a
    failing coupled cycle. Run it on a scratch thread; on timeout the owner
    is wedged and must be reaped by the caller.
    """
    holder = {}
    t = threading.Thread(target=lambda: holder.setdefault("r", bot.cancel_task()),
                         daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return False
    try:
        return bool(holder.get("r"))
    except Exception:
        return False
