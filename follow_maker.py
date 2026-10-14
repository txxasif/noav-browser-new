"""Mr Follower — gives pooled IG Creator accounts their 5 follows, then returns them to the list.

Each creator thread: claim the OLDEST account that owes follows (``store.claim_for_follow``,
status 'Submitting_Follow' so no drain can take it), open it in the browser with its stored
cookies, follow suggested accounts exactly the way the Taskly/PayGo cookie pool does
(``runner.ig_follow_suggested``), then put it back with ``followed`` updated
(``store.finish_follow``). ``followed >= 5`` is the "has 5 follows" mark the drains can prefer.

CLI (spawned by server/routes-followmaker.js):
    python follow_maker.py --creators 3 --limit 0 --follows 5 --max-age-min 50

Prints one line per event and ``__STATS__{json}`` after each account for the panel.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

# Same class ig_api_cycle raises, so `except IGDeadEnd` catches its dead-session errors.
from instagram.ig_api_cycle import IGDeadEnd  # noqa: E402

SLOT_BASE = 900          # browser slot ids, kept apart from the creators' / drains' slots

_stop = threading.Event()
_lock = threading.Lock()
_stats = {"ok": 0, "partial": 0, "failed": 0, "dead": 0, "follows": 0, "claimed": 0}


def emit(msg: str) -> None:
    try:
        print(msg, flush=True)
    except (BrokenPipeError, OSError):
        _stop.set()          # nobody is reading any more: finish current accounts and exit


_AGE = {"min_s": 0.0, "max_s": 0.0, "need": 5}


def _publish() -> None:
    with _lock:
        snap = dict(_stats)
    snap.update(store.count_follow_backlog(need=_AGE["need"], max_age_s=_AGE["max_s"], min_age_s=_AGE["min_s"]))
    snap["next_eligible_s"] = store.next_follow_eligible_in(_AGE["need"], _AGE["min_s"])
    emit("__STATS__" + json.dumps(snap))


def _bump(key: str, n: int = 1) -> None:
    with _lock:
        _stats[key] += n


class DeadAfter(Exception):
    """The session died (challenge / login) after ``followed`` follows had already gone through."""
    def __init__(self, reason: str, followed: int):
        super().__init__(reason)
        self.reason, self.followed = reason, followed


_FOLLOWED_RE = re.compile(r"Followed @\S+ \(\d+/\d+\)")


def _api_follow(acc: dict, need: int, log) -> int:
    """Follow over the private API (same call the creators and the cookie pool use).

    Returns follows that persisted. Raises DeadAfter for a dead / challenged session, carrying the
    follows made before it died so the count is never lost.
    """
    from instagram import ig_api_cycle
    login = acc.get("instagram_username") or acc.get("username") or ""
    client = ig_api_cycle.client_for(acc, username=login)
    done = {"n": 0}

    def counting(m):
        if _FOLLOWED_RE.search(str(m)):
            done["n"] += 1
        log(m)
    try:
        return int(ig_api_cycle.follow_targets(client, need, counting, self_username=login) or 0)
    except IGDeadEnd as exc:
        raise DeadAfter(str(exc), done["n"])


def _browser_follow(slot_id: int, acc: dict, need: int, headless: bool, log) -> tuple[int, str]:
    """Fallback: follow suggested accounts in a browser with the stored cookies,
    exactly like the cookie pool (runner.ig_follow_suggested). Returns (followed, dead_reason)."""
    from pool_common import _cookies_for_playwright, _browser_logged_in
    from runner import MetaInstaRunner
    from worker import AISlotWorker

    worker = AISlotWorker(slot_id=slot_id, is_headless=headless)
    runner = MetaInstaRunner(worker, twofa=False, telegram=False, tg_task="",
                             captcha_mode="none", mail_provider="mailtd", target="telegram")
    try:
        runner._launch()
        ctx = getattr(getattr(runner, "w", None), "context", None)
        if ctx is None:
            raise RuntimeError("browser context unavailable after launch")
        try:
            ctx.clear_cookies()
        except Exception:
            pass
        ctx.add_cookies(_cookies_for_playwright(acc["cookies"]))
        page = runner._ig_tab()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
        try:
            runner._dismiss_ig_sheets(page)
        except Exception:
            pass
        if not _browser_logged_in(page):
            return 0, "session not logged in (home feed)"
        runner._ig_follow_done = False
        return int(runner.ig_follow_suggested(max_follows=max(1, need), humanize=True) or 0), ""
    finally:
        try:
            runner.finish()
        except Exception:
            pass
        try:
            worker._cleanup_browser_resources()
        except Exception:
            pass


def follow_one(slot_id: int, acc: dict, need: int, headless: bool, mode: str = "auto") -> tuple[int, str]:
    """Bring ``acc`` up to ``need`` follows. API first, browser for the remainder.
    Returns (total_followed, dead_reason)."""
    have = int(acc.get("followed") or 0)
    login = acc.get("instagram_username") or acc.get("username") or "?"
    tag = f"[Follower #{slot_id - SLOT_BASE}]"
    log = lambda m: emit(f"{tag} @{login} {m}")  # noqa: E731
    total = have
    if mode in ("api", "auto"):
        try:
            total += _api_follow(acc, need - total, log)
        except DeadAfter as exc:
            return total + exc.followed, f"IG dead end: {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            log(f"API follow error: {str(exc)[:120]}")
        if total >= need or mode == "api":
            return total, ""
        if _stop.is_set():
            return total, ""                       # stopping: do not open a browser
        log(f"API gave {total}/{need} — browser follow for the rest.")
    else:
        log("browser follow.")
    try:
        got, dead = _browser_follow(slot_id, acc, need - total, headless, log)
    except IGDeadEnd as exc:
        return total, f"IG dead end: {exc}"
    return total + got, dead


_streak = {"fails": 0}
BREAKER_AFTER = 4            # failures in a row (all creators) before the cool-down
BREAKER_COOLDOWN_S = 180


def _record(success: bool, tag: str) -> None:
    """Circuit breaker: a run of failures means IG / the IP is blocking us, so pause instead of
    burning every account in the list. A success resets it."""
    with _lock:
        _streak["fails"] = 0 if success else _streak["fails"] + 1
        trip = _streak["fails"] >= BREAKER_AFTER
        if trip:
            _streak["fails"] = 0
    if trip:
        emit(f"{tag} {BREAKER_AFTER} failures in a row — cooling down {BREAKER_COOLDOWN_S}s "
             f"(IG or the IP is blocking follows).")
        _stop.wait(BREAKER_COOLDOWN_S)


def _claim(args):
    """claim_for_follow that never kills the thread (DB locked, disk hiccup...)."""
    try:
        return store.claim_for_follow(need=args.follows, max_age_s=args.max_age_min * 60,
                                      min_age_s=args.min_age_min * 60)
    except Exception as exc:  # noqa: BLE001
        emit(f"[Mr Follower] could not read the IG list ({str(exc)[:100]}) — retrying in 15s.")
        _stop.wait(15)
        return False


def creator_loop(idx: int, args) -> None:
    slot_id = SLOT_BASE + idx
    tag = f"[Follower #{idx}]"
    while not _stop.is_set():
        with _lock:
            if args.limit and _stats["claimed"] >= args.limit:
                return
            _stats["claimed"] += 1
        acc = _claim(args)
        if not acc:
            with _lock:
                _stats["claimed"] -= 1
            if acc is False:
                continue                      # read error, already waited
            if not args.auto:
                emit(f"{tag} no eligible account left — done.")
                return
            nxt = store.next_follow_eligible_in(args.follows, args.min_age_min * 60)
            when = f"next account old enough in {nxt // 60}m {nxt % 60:02d}s" if nxt is not None else "none waiting"
            emit(f"{tag} waiting — {when}; checking again in {int(args.interval)}s.")
            _publish()
            _stop.wait(args.interval)
            continue
        rec_id = acc["id"]
        have = int(acc.get("followed") or 0)
        login = acc.get("instagram_username") or acc.get("username") or rec_id
        emit(f"{tag} claimed @{login} (followed {have}/{args.follows}).")
        total, dead, released = have, "", False
        try:
            try:
                total, dead = follow_one(slot_id, acc, args.follows, not args.visible, args.mode)
            except Exception as exc:  # noqa: BLE001
                emit(f"{tag} @{login} error: {str(exc)[:160]}")
            gained = max(0, total - have)
            _bump("follows", gained)
            stopped = _stop.is_set() and not dead and total < args.follows
            if not dead and not stopped and total < args.follows and args.on_fail != "retry":
                # A follow that fails = a damaged account — but only once this run has had a success.
                # With none yet, every account failing means the METHOD (IP, API, browser) is broken,
                # and condemning accounts for that would wipe the list.
                with _lock:
                    proven = _stats["ok"] > 0
                if proven:
                    dead = f"follow incomplete ({total}/{args.follows})"
                else:
                    emit(f"{tag} @{login} only {total}/{args.follows} and no account has succeeded yet — "
                         f"blaming the method, not the account; kept in the list.")
            if dead:
                if args.on_fail == "delete":
                    emit(f"{tag} @{login} damaged — deleted ({dead}).")
                    store.delete_record(rec_id)
                else:
                    emit(f"{tag} @{login} damaged — removed from the list ({dead}).")
                    store.finish_follow(rec_id, total, False, dead_reason=dead)
                _bump("dead")
            elif total >= args.follows:
                emit(f"{tag} @{login} has {total}/{args.follows} follows — back in the IG list.")
                store.finish_follow(rec_id, total, True)
                _bump("ok")
            elif stopped:
                emit(f"{tag} @{login} stop requested at {total}/{args.follows} — back in the list untouched.")
                store.finish_follow(rec_id, total, False, progressed=True)
            else:
                emit(f"{tag} @{login} only {total}/{args.follows} — back in the list, retry in "
                     f"{store.FOLLOW_RETRY_S // 60} min.")
                store.finish_follow(rec_id, total, False, progressed=gained > 0)
                _bump("partial" if gained else "failed")
            released = True
        finally:
            if not released:                  # anything unexpected: never leave the account locked
                try:
                    store.finish_follow(rec_id, have, False, progressed=True)
                except Exception:  # noqa: BLE001
                    pass
        _publish()
        _record(success=(not dead and total >= args.follows), tag=tag)
        _stop.wait(args.pause)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--creators", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="accounts to process (0 = until none left / stopped)")
    ap.add_argument("--follows", type=int, default=5)
    ap.add_argument("--min-age-min", type=float, default=10, help="only accounts at least this old (0 = off)")
    ap.add_argument("--max-age-min", type=float, default=0, help="skip accounts older than this (0 = no limit)")
    ap.add_argument("--pause", type=float, default=3.0, help="seconds between accounts per creator")
    ap.add_argument("--visible", action="store_true", help="show the browsers")
    ap.add_argument("--mode", choices=("api", "browser", "auto"), default="auto",
                    help="api = private API only, browser = browser only, auto = API first then browser")
    ap.add_argument("--on-fail", choices=("dead", "delete", "retry"), default="dead",
                    help="account whose follow fails: dead = out of every pool (kept), delete = removed, "
                         "retry = back in the list after a rest")
    ap.add_argument("--auto", action="store_true", help="keep running; wait for accounts to reach the minimum age")
    ap.add_argument("--interval", type=float, default=30, help="seconds between checks while waiting (auto)")
    ap.add_argument("--release-only", action="store_true", help="return every locked account to the list and exit")
    args = ap.parse_args()
    if args.release_only:
        try:
            emit(f"[Mr Follower] released {store.release_follow_claims()} locked account(s).")
        except Exception as exc:  # noqa: BLE001
            emit(f"[Mr Follower] release failed: {str(exc)[:120]}")
        return 0
    args.creators = max(1, min(args.creators, 20))
    args.follows = max(1, min(args.follows, 20))
    _AGE["min_s"], _AGE["max_s"], _AGE["need"] = args.min_age_min * 60, args.max_age_min * 60, args.follows
    args.interval = max(5.0, args.interval)

    def _sig(*_):
        _stop.set()
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    try:
        n = store.release_follow_claims()      # left over from a run that was killed
        if n:
            emit(f"[Mr Follower] released {n} account(s) left locked by a previous run.")
    except Exception as exc:  # noqa: BLE001
        emit(f"[Mr Follower] could not release old claims: {str(exc)[:100]}")
    emit(f"[Mr Follower] starting: {args.creators} creator(s), {args.follows} follows each, "
         f"limit {args.limit or 'none'}, mode {args.mode}{' + AUTO' if args.auto else ''}, on fail {args.on_fail}, "
         f"age {args.min_age_min or 0}-{args.max_age_min or 'any'} min.")
    _publish()
    threads = [threading.Thread(target=creator_loop, args=(i + 1, args), daemon=True)
               for i in range(args.creators)]
    for t in threads:
        t.start()
    for t in threads:
        while t.is_alive():
            t.join(1)
    try:
        store.release_follow_claims()
    except Exception:  # noqa: BLE001
        pass
    emit("[Mr Follower] finished.")
    _publish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
