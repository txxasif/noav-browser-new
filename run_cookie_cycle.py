#!/usr/bin/env python3
"""One-shot PayGo Cookies task cycle: Meta -> TG Cookies creds -> IG join ->
follow ~2 -> export IG cookie header -> submit cookie -> register -> Submitted.

The post-lease STEPS are data-driven by :mod:`tg_flows` (single source of
truth). For the ``cookie`` flow that is exactly::

    ig_join -> cookie_export -> submit_cookie

A cookie task verifies via the exported IG cookie, so there is **no email
link** and **no 2FA/password** step (the former "email after follow" step made
a fresh account sit in Accounts Center for ~90s and was actively harmful).
Adding/removing a step = edit ``tg_flows.FLOWS`` + implement the callable —
the preamble is shared and untouched.

Preamble (all flows): Meta creation (no TG lease held) -> lease ONE TG profile
-> choose "Create Inst (Cookies)" -> Start -> creds.

Strict: first failure cancels the TG task, releases the lease, closes the
browser, and exits nonzero with the step in the message.
"""
from __future__ import annotations

import os
import sys
import threading
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from ai_config import SELFIE_PATH, emit_event  # noqa: E402
# NOTE: AISlotWorker is imported lazily inside run_cookie_cycle_once —
# worker.py (which defines it) lazily imports this module for the --cookie
# engine path, so a top-level import here would be circular.
from runner import MetaInstaRunner  # noqa: E402
from tg_accounts import tg_manager  # noqa: E402
from tg_flows import steps_of, step_label  # noqa: E402
from pipelines.telegram.tg_support import (  # noqa: E402
    _boot_bot,
    _clean_username,
    _is_tg_session_lost,
    _is_valid_ig_username,
    _make_tg_bot,
    _sanitize_name,
    IGDeadEnd,
)

COOKIE_TASK = "📱 Create Inst (Cookies)"
COOKIE_FLOW = "cookie"
TASK_WINDOW = 420  # bot ~8-min TTL; fail fast past it

_profile_pacing_lock = threading.Lock()
_profile_last_start: dict[str, float] = {}

# IG anti-spam ({"spam":true}) on the rename endpoint. A single hit marks the
# ACCOUNT as blocked (remove it); a long CONSECUTIVE streak means the IP is
# flagged, so STOP the drain instead of emptying the whole pool.
_ig_spam_streak = [0]
_IG_SPAM_STOP = int(os.environ.get("INSTA_IG_SPAM_STOP", "20") or 20)


def _ig_spam_blocked(msg: str) -> bool:
    return "spam" in str(msg or "").lower()


def log(slot_id, m):
    print(f"[cookie:{slot_id}] {m}", flush=True)


def _is_account_dead_error(msg: str) -> bool:
    """Return True if error indicates the account is banned, checkpointed, or has a dead session."""
    low = str(msg or "").lower()
    return any(p in low for p in (
        "checkpoint", "suspended", "login_required", "logged_out",
        "challenge", "unauthorized", "forbidden", "401", "403",
        "feedback_required", "disabled", "banned", "user_has_logged_out",
        "session expired", "invalid cookie", "user not found"
    ))


_IG_SESSION = None
_IG_SESSION_LOCK = threading.Lock()

def _get_ig_session():
    global _IG_SESSION
    if _IG_SESSION is None:
        with _IG_SESSION_LOCK:
            if _IG_SESSION is None:
                try:
                    import requests
                    from requests.adapters import HTTPAdapter
                    s = requests.Session()
                    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
                    s.mount("https://", adapter)
                    _IG_SESSION = s
                except Exception:
                    _IG_SESSION = False
    return _IG_SESSION


def change_ig_username_fast(cookie_str: str, target_username: str, ua: str = None) -> tuple[bool, str]:
    """Change Instagram username via direct Web API in ~0.1s using persistent Keep-Alive connections.

    POST https://www.instagram.com/api/v1/web/accounts/edit/
    Requires sessionid and csrftoken in cookie_str.
    """
    import json
    import re
    import urllib.error
    import urllib.parse
    import urllib.request

    csrf_match = re.search(r"csrftoken=([^; ]+)", cookie_str)
    csrf_token = csrf_match.group(1) if csrf_match else ""

    headers = {
        "User-Agent": ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-CSRFToken": csrf_token,
        "X-IG-App-ID": "936619743392459",
        "Referer": "https://www.instagram.com/accounts/edit/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie_str,
        "Accept": "*/*",
    }

    # Fast path: persistent Keep-Alive session (~0.1s)
    session = _get_ig_session()
    if session:
        try:
            resp = session.post(
                "https://www.instagram.com/api/v1/web/accounts/edit/",
                data={"username": target_username},
                headers=headers,
                timeout=10,
            )
            body = resp.text
            try:
                res_json = resp.json()
                if res_json.get("status") == "ok":
                    return True, "ok"
                msg = res_json.get("message") or body[:200]
                return False, f"IG API: {msg}"
            except Exception:
                if resp.status_code == 200:
                    return True, body[:100]
                return False, f"HTTP {resp.status_code}: {body[:100]}"
        except Exception:
            pass  # Fall back to standard urllib below

    data = urllib.parse.urlencode({"username": target_username}).encode("utf-8")
    req = urllib.request.Request(
        "https://www.instagram.com/api/v1/web/accounts/edit/",
        data=data,
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                res_json = json.loads(body)
                if res_json.get("status") == "ok":
                    return True, "ok"
                msg = res_json.get("message") or body[:200]
                return False, f"IG API: {msg}"
            except Exception:
                return True, body[:100]
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            msg = err_json.get("message") or err_body[:200]
            return False, f"HTTP {exc.code}: {msg}"
        except Exception:
            return False, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        return False, str(exc)


def _all_flooded_until():
    """Earliest ``flood_until`` when EVERY leasable account is flood-limited.

    Returns ``None`` if at least one account is usable (so the caller keeps its
    normal busy/retry behaviour) or if flood state cannot be read.
    """
    try:
        from tg_accounts import tg_manager as _m
        _m._reload()
        now = time.time()
        untils = []
        for a in _m.accounts:
            if a.get("enabled") is False or not a.get("logged_in"):
                continue
            fu = a.get("flood_until")
            try:
                fu = float(fu) if fu else 0.0
            except (TypeError, ValueError):
                fu = 0.0
            if fu <= now:
                return None          # one usable account -> not "all flooded"
            untils.append(fu)
        return min(untils) if untils else None
    except Exception:
        return None


def _sleep_until(when, stop_event=None, chunk=30.0):
    """Sleep until ``when`` (epoch secs) in stop-aware chunks."""
    while True:
        try:
            if stop_event is not None and stop_event.is_set():
                return
        except Exception:
            pass
        left = float(when) - time.time()
        if left <= 0:
            return
        time.sleep(min(chunk, left))


def _run_pool_drain_cycle(slot_id=91, is_headless=False, stop_event=None,
                          tg_task=COOKIE_TASK, tg_bot="paygo"):
    """Run ONE PayGo drain cycle using pre-created accounts from data/accounts.json.

    1. Checks for available accounts in IG Creator pool.
    2. Leases ONE TG profile.
    3. Starts task on PayGo (📱 Create Inst (Cookies)) -> obtains target login.
    4. Claims an account from the pool.
    5. Changes its username to the bot's login in ~0.4s via direct IG Web API.
    6. Submits the account's cookie string to PayGo.
    7. Confirms registration (bot.mark_registered()).
    8. Deletes the consumed account from store.db / accounts.json so it is not double-spent.
    9. Records submission and releases lease.
    """
    import store

    def _stopped():
        try:
            return bool(stop_event and stop_event.is_set())
        except Exception:
            return False

    if _stopped():
        return False, "stopped"

    bot_id = str(tg_bot or "paygo")
    task = tg_task or COOKIE_TASK

    avail = store.count_ig_creator_accounts()
    if avail <= 0:
        log(slot_id, "[pool] No available IG Creator accounts in pool to drain.")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                    "detail": "Pool empty: No IG Creator accounts left to drain."})
        return False, "no_pool_accounts"
    log(slot_id, f"[pool] Found {avail} available IG Creator account(s) in pool.")

    bot = None
    tg_acct = None
    lease_stop = None
    pool_acc = None
    ok = False
    rec_id = None

    try:
        if not tg_manager.usable():
            raise RuntimeError("No logged-in Telegram profile available")
        tg_acct = tg_manager.acquire(timeout=30, bot=bot_id)
        if not tg_acct:
            # Distinguish "merely busy" from "FLOOD-LIMITED until a known time".
            # A flood ban has a definite expiry, so spinning the loop every 1.5s
            # (30s acquire + 1.5s sleep) just spams the log with zero chance of
            # work — observed 2026-10-01: the same two lines every ~12s forever
            # while all 6 accounts served 3-5h waits. Sleep it out instead.
            wait_until = _all_flooded_until()
            if wait_until and wait_until > time.time():
                secs = int(wait_until - time.time())
                # NEVER sleep the full recorded window. `flood_until` is a
                # STALE RECORD that nothing re-verifies: it is written from a
                # FloodWaitError at one moment, and the real throttle can lift
                # much earlier. Trusting it benched six accounts that could
                # demonstrably still send (verified 2026-10-01 22:00 — all six
                # passed reset_to_main_menu while the record claimed 128 min).
                # Sleep a bounded slice, then let the loop re-try: if the
                # throttle is real the attempt re-parks it (re-recording the
                # fresh value); if it lifted, work resumes within one slice.
                try:
                    _cap = int(os.environ.get("INSTA_TG_PARK_MAX_SLEEP", "300") or 300)
                except (TypeError, ValueError):
                    _cap = 300
                slice_s = max(30, min(secs, _cap))
                log(slot_id, f"[pool] Every Telegram profile is reported FLOOD-LIMITED "
                             f"(recorded {secs // 60}m {secs % 60}s). Sleeping {slice_s}s, "
                             f"then re-verifying against reality.")
                _sleep_until(time.time() + slice_s, stop_event)
                try:
                    tg_manager.clear_flood()
                except Exception:
                    pass
                return False, "flooded"
            log(slot_id, "[pool] All Telegram profiles busy — waiting for next slot cycle.")
            return False, "lease_busy"
        log(slot_id, f"[pool] Leased TG {tg_acct['id']}")

        clog = lambda m, _id=tg_acct["id"]: print(f"[tg:{_id}:{bot_id}] {m}", flush=True)
        if _stopped():
            raise RuntimeError("stopped")

        bot = _make_tg_bot(tg_acct, bot_id, is_headless, clog)
        ok_boot, msg_boot = _boot_bot(bot)
        if not ok_boot:
            raise RuntimeError(f"bot boot: {msg_boot}")

        lease_stop = threading.Event()
        lid = tg_acct["id"]

        def _beat(_stop=lease_stop, _lid=lid):
            while not _stop.wait(300):
                try:
                    tg_manager.heartbeat(_lid)
                except Exception:
                    break

        threading.Thread(target=_beat, daemon=True).start()

        # Profile pacing: minimum gap between task starts on the SAME Telegram
        # profile.
        #
        # THIS IS THE THROUGHPUT / ANTI-FLOOD LEVER. A drain cycle costs 6-9 SENDS:
        #   reset_to_main_menu (inside choose_task)  1-4
        #   choose_task menu navigation                2
        #   start_task / submit_cookie / mark_registered 3
        #
        # Default 12s — FAST profile, selected deliberately for max throughput:
        # 6 profiles / 12s => ~30 cycles/min total (~5/min per ACCOUNT) =>
        # ~30-45 sends/min PER ACCOUNT, at/above Telegram's practical
        # SendMessage ceiling of ~20/min. 12s is the exact gap that previously
        # produced the multi-hour FloodWaits that blocked every account
        # (observed 2026-10-01: all 6 on 3-5h waits) — expect FloodWait
        # penalties under load and let bot._sleep_flood() park the throttled
        # profile; the pool re-verifies and resumes.
        #
        # For the conservative profile (30s ≈ 2 cycles/min ≈ 14 sends/min,
        # safely under the ceiling) set INSTA_TG_PROFILE_PACING_SEC=30 — no code
        # change needed. Raising it is the ONLY safe way to add headroom; going
        # lower multiplies the ban risk.
        try:
            _pacing = float(os.environ.get("INSTA_TG_PROFILE_PACING_SEC", "12") or 12)
        except (TypeError, ValueError):
            _pacing = 12.0
        _pacing = max(0.0, _pacing)
        with _profile_pacing_lock:
            last_t = _profile_last_start.get(tg_acct["id"], 0.0)
            wait_rem = _pacing - (time.time() - last_t)
            if wait_rem > 1:
                log(slot_id, f"[pace] {tg_acct['id']} idle {wait_rem:.1f}s "
                             f"(start-to-start pacing {_pacing:.0f}s)")
                time.sleep(wait_rem)
            _profile_last_start[tg_acct["id"]] = time.time()

        if not bot.choose_task(task):
            recent_err = ""
            try:
                for t in (bot._call("_recent_texts", 4) if hasattr(bot, "_call") else bot._recent_texts(4)):
                    if any(ph in t.lower() for ph in ("limit is reached", "hour's limit", "available this hour: 0/", "available this hour: 0 ")):
                        recent_err = t.strip()
                        break
            except Exception:
                pass
            if recent_err:
                raise RuntimeError(f"PayGo hourly limit reached: {recent_err}")
            raise RuntimeError(f"Could not select {task} in {bot_id}")

        log(slot_id, f"[task] Selected '{task}' on {bot_id} (TG {tg_acct['id']})")
        creds = bot.start_task() or {}
        if creds.get("error") == "limit_reached":
            raise RuntimeError(f"PayGo hourly limit reached: {creds.get('detail', '')}")
        login = _clean_username(creds.get("login") or "")
        if not (login and _is_valid_ig_username(login)):
            raise RuntimeError(f"{bot_id} returned no usable credentials (got {creds})")
        log(slot_id, f"[creds] PayGo issued target username: '{login}'")

        # Claim an account from the pool (skip any that turn out to be checkpointed/dead)
        pool_acc = None
        for _attempt in range(10):
            cand = store.pop_ig_creator_account()
            if not cand or not cand.get("cookies"):
                break
            cand_id = cand["id"]
            cand_user = cand.get("username") or cand.get("instagram_username") or "unknown"
            log(slot_id, f"[pool] Claimed IG Creator account {cand_id} (current username: '{cand_user}')")
            log(slot_id, f"⚡ [api] Changing username: '{cand_user}' -> '{login}' via direct IG Web API…")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"Fast IG username change: {cand_user} -> {login}…"})
            ok_name, name_msg = change_ig_username_fast(
                cand["cookies"], login, ua=cand.get("device_ua")
            )
            if ok_name:
                pool_acc = cand
                _ig_spam_streak[0] = 0
                log(slot_id, f"✅ [api] IG username updated successfully to '{login}' in ~0.4s ({name_msg})")
                clog(f"⚡ [username] Updated Instagram username: '{cand_user}' -> '{login}' (in 0.4s)")
                break
            # If checkpointed / suspended / banned / session dead, permanently delete from list and try next account
            if _is_account_dead_error(name_msg):
                log(slot_id, f"⚠️ [pool] Account {cand_id} ({cand_user}) is dead/banned on IG ({name_msg}) — permanently removing from accounts list.")
                store.delete_record(cand_id)
                if cand.get("session_file") and os.path.exists(cand["session_file"]):
                    try:
                        os.remove(cand["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": cand_id})
                emit_event({"type": "accounts_updated"})
                continue
            else:
                # FAILED means FAILED: a rejected rename (spam / taken / invalid)
                # removes the account from the pool — never retried / re-logged-in.
                # Safety: if MANY fail in a ROW the IP itself is flagged, so STOP
                # the drain instead of emptying the whole pool.
                _ig_spam_streak[0] += 1
                if _ig_spam_streak[0] >= _IG_SPAM_STOP:
                    raise RuntimeError(
                        f"IG rename failed on {_ig_spam_streak[0]} consecutive accounts "
                        f"(last: {name_msg[:60]}) — IP-level rate-limit; pausing the drain.")
                log(slot_id, f"[pool] Rename '{login}' FAILED for {cand_id} ({name_msg[:80]}) — "
                             f"removing from pool ({_ig_spam_streak[0]}/{_IG_SPAM_STOP}).")
                store.delete_record(cand_id)
                if cand.get("session_file") and os.path.exists(cand["session_file"]):
                    try:
                        os.remove(cand["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": cand_id})
                emit_event({"type": "accounts_updated"})
                continue

        if not pool_acc:
            raise RuntimeError("Failed to obtain a valid working IG Creator account from pool")

        acc_id = pool_acc["id"]

        # Submit cookie to PayGo
        log(slot_id, f"[submit] Submitting {len(pool_acc['cookies'])} chars IG cookie string to {bot_id}…")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                    "detail": "Submitting IG cookie to PayGoBot…"})
        ok_cookie, reply = bot.submit_cookie(pool_acc["cookies"], timeout=25)
        if not ok_cookie:
            if _is_account_dead_error(reply):
                log(slot_id, f"⚠️ [pool] PayGo rejected dead/banned account {acc_id} ({reply[:100]}) — permanently removing from accounts list.")
                store.delete_record(acc_id)
                if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
                    try:
                        os.remove(pool_acc["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": acc_id})
                emit_event({"type": "accounts_updated"})
            else:
                store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError(f"PayGo rejected cookie: {reply[:200]}")

        log(slot_id, f"✅ [paygo] Cookie accepted by {bot_id} — confirming registration…")

        # Register confirm (retry up to 3 times to ensure receipt)
        submitted = False
        for _rc in range(3):
            submitted = bot.mark_registered()
            if submitted:
                break
            log(slot_id, f"register receipt not seen (attempt {_rc+1}/3) — retrying confirm tap…")
            time.sleep(1.2)
        if not submitted:
            store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError("PayGo registration not confirmed — not recording Submitted")

        # Success: consume record from store so it cannot be double-spent
        store.delete_record(acc_id)
        if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
            try:
                os.remove(pool_acc["session_file"])
            except Exception:
                pass
        log(slot_id, f"[pool] Account {acc_id} successfully consumed and removed from pool.")
        pool_acc = None

        from tg_stats import record_submission
        rec_id = f"tg_{int(time.time()*1000)}"
        # POOL DRAIN gets its OWN counter so it never inflates the normal
        # `paygo` (browser-creator) number — mirrors taskly2fa / fastpay2fa.
        record_submission("paygo_pool" if (bot_id or "paygo").lower() == "paygo" else (bot_id or "paygo"))
        emit_event({"type": "account_submitted", "pipeline": "telegram",
                    "tg_account": tg_acct["id"], "tg_bot": bot_id or "paygo",
                    "account_id": rec_id})
        emit_event({"type": "account_deleted", "account_id": acc_id})
        emit_event({"type": "accounts_updated"})
        log(slot_id, f"🎉 [SUBMITTED] Registration confirmed (+ $0.02) -> record {rec_id} for user '{login}'")
        ok = True
        return True, rec_id

    except Exception as exc:
        detail = str(exc)
        # Telegram throttles per ACCOUNT, not per slot. Without this the slot
        # returned instantly and the loop leased the next account ~2s later, so
        # every account kept re-arming its own FloodWait and the whole pool
        # churned through hundreds of pointless retries (observed: "A wait of
        # 483 / 388 / 245s required" on every slot, seconds apart). Sleep the
        # penalty out BEFORE restoring the lease, and report it as throttled so
        # the slot backs off instead of hammering.
        _fw = 0
        if bot is not None:
            try:
                _fw = bot._sleep_flood(exc, "cookie pool drain")
            except Exception:
                _fw = 0
        if _fw:
            log(slot_id, f"⏳ Telegram rate limit — slept {_fw}s before retrying.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "throttled",
                        "detail": f"Telegram FloodWait — waited {_fw}s (account throttled)."})
            return False, "floodwait"
        # A locked session is a RESOURCE problem, not a task failure: the sqlite
        # file is still held (usually by a client that failed to boot, so
        # disconnect() never ran). Drop the handle NOW so the next lease of this
        # account opens cleanly instead of re-locking. Business logic untouched.
        if "database is locked" in detail.lower() or "database is locked" in str(exc).lower():
            if bot is not None:
                try:
                    bot.disconnect()          # releases the sqlite handle
                except Exception:
                    pass
            log(slot_id, "🔓 Session file was locked — released the handle; "
                         "the account is free to be leased again.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "lock_released",
                        "detail": "Session DB lock released — account returned to the pool."})
        # A DEAD session must take the account OUT of rotation. The cookie drain
        # imported _is_tg_session_lost but never called it, so a genuinely
        # revoked profile stayed enabled: the pool re-leased it within ~3s and
        # failed again, forever — a tight loop that spammed "session lost" and
        # starved the slot. tg_coupled already disables; this path was missing it.
        if _is_tg_session_lost(detail):
            try:
                bot.close(ok=False)          # release the sqlite handle first
            except Exception:
                pass
            if tg_acct:
                try:
                    tg_manager.disable(
                        tg_acct["id"],
                        reason="dead Telegram session (cookie pool drain)")
                    log(slot_id, f"🔒 {tg_acct['id']} Telegram session is dead — "
                                 f"DISABLED so the pool stops re-leasing it.")
                    emit_event({"type": "slot_event", "slot_id": slot_id,
                                "status": "disabled",
                                "detail": f"{tg_acct['id']} disabled (dead Telegram session)."})
                except Exception:
                    pass
            if pool_acc is not None:
                try:
                    store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                except Exception:
                    pass
            return False, "session_lost"
        log(slot_id, f"FAILED: {exc}")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                    "detail": f"Cookie pool drain error: {exc}"})
        # If the failure itself is a dead/banned signal (raised rather than
        # returned by an explicit branch), take the account OUT of the pool —
        # restoring it just makes the next slot re-claim and fail on it forever.
        if pool_acc is not None and _is_account_dead_error(detail):
            log(slot_id, f"⚠️ [pool] Account {pool_acc['id']} is dead/banned ({detail[:90]}) — permanently removing.")
            try:
                store.delete_record(pool_acc["id"])
            except Exception:
                pass
            if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
                try:
                    os.remove(pool_acc["session_file"])
                except Exception:
                    pass
            emit_event({"type": "account_deleted", "account_id": pool_acc["id"]})
            emit_event({"type": "accounts_updated"})
            pool_acc = None
        if pool_acc is not None:
            try:
                store.restore_ig_creator_account(pool_acc["id"], rotate=True)
            except Exception:
                pass
        if bot is not None:
            try:
                bot.cancel_task()
            except Exception:
                pass
        return False, detail
    finally:
        try:
            if lease_stop is not None:
                lease_stop.set()
        except Exception:
            pass
        if tg_acct:
            try:
                # NOTE: `_profile_last_start` is stamped once, at task start
                # (above), so pacing really is start-to-start as documented.
                # Re-stamping here at release would make the effective window
                # `cycle_time + pacing` (~2x the configured value) — that is
                # what pinned each profile to ~60s at a 30s setting.
                tg_manager.release(tg_acct["id"], ok=ok,
                                   account_id=rec_id if ok else None)
            except Exception:
                pass
        if bot is not None:
            try:
                bot.close(ok=ok)
            except Exception:
                pass


def _flow_tag(bot_target, task):
    """The flow tag for a (bot, task) — 'cookie' | 'cookie_2fa' | '2fa' | None."""
    try:
        import tg_tasks
        tid, _ = tg_tasks.resolve(bot_target, task)
        if tid:
            return (tg_tasks.TASKS.get(str(bot_target), {}).get(tid) or {}).get("flow")
    except Exception:
        pass
    return None


def run_cookie_cycle_once(slot_id=91, worker_factory=None, is_headless=False,
                          captcha_mode="extension", mail_provider="mailtd",
                          stop_event=None, add_email=False,
                          tg_task=None, tg_bot="paygo", use_ig_pool=False):
    """Run ONE cookie-family task cycle. Returns ``(ok, detail)``.

    Parametrized so it serves BOTH cookie flows:
      * PayGo  ``cookie``      — ig_join → cookie_export → submit_cookie
      * Taskly ``cookie_2fa``  — ig_join → 2fa → cookie_export → submit_cookie
    The step list comes from ``tg_flows.resolve_steps(tg_bot, task)`` (data).

    When ``use_ig_pool=True``, drains pre-created accounts from the IG Creator
    pool instead of creating fresh Meta accounts in the browser.

    ``add_email`` is accepted for call-site stability but IGNORED: the cookie
    flows have no email step (see ``tg_flows.FLOWS``). Import-safe for
    ``worker.py`` (lazy ``AISlotWorker`` import — no import cycle).
    """
    task = tg_task or COOKIE_TASK
    bot_id = str(tg_bot or "paygo")

    if use_ig_pool:
        return _run_pool_drain_cycle(
            slot_id=slot_id, is_headless=is_headless,
            stop_event=stop_event, tg_task=task, tg_bot=bot_id
        )
    try:
        from tg_flows import resolve_steps as _resolve_steps, needs_2fa as _needs_2fa
        flow_steps = _resolve_steps(bot_id, task)
        flow_needs_2fa = _needs_2fa(_flow_tag(bot_id, task))
    except Exception:
        flow_steps = ["ig_join", "cookie_export", "submit_cookie"]
        flow_needs_2fa = False

    if worker_factory is None:
        from worker import AISlotWorker as _W
        worker_factory = _W

    def _stopped():
        try:
            return bool(stop_event and stop_event.is_set())
        except Exception:
            return False

    if _stopped():
        return False, "stopped"

    if add_email:
        log(slot_id, "[i] 'Extra email after 2FA + password' ignored — cookie tasks "
                     f"have no email step (steps: {' → '.join(flow_steps)}).")

    worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
    runner = MetaInstaRunner(
        worker, twofa=flow_needs_2fa, telegram=False, tg_task=task,
        captcha_mode=captcha_mode, mail_provider=mail_provider, target="telegram",
    )
    if os.path.exists(SELFIE_PATH):
        runner.selfie_path = SELFIE_PATH

    bot = None
    tg_acct = None
    lease_stop = None
    t0 = None
    ok = False
    rec_id = None

    def window_left():
        return TASK_WINDOW - (time.monotonic() - t0) if t0 else TASK_WINDOW

    def require_window(phase):
        left = window_left()
        log(slot_id, f"[TTL] {phase} — {max(0, int(left))}s left of ~{TASK_WINDOW}s")
        if left <= 0:
            raise RuntimeError(f"Bot task window exceeded before {phase}")

    try:
        # -- Step 1: TG lease + task pre-flight check (fail before Meta) --
        if _stopped():
            return False, "stopped"
        if not tg_manager.usable():
            raise RuntimeError("No logged-in Telegram profile available")
        tg_acct = tg_manager.acquire(timeout=15, bot=bot_id)
        if not tg_acct:
            raise RuntimeError("No Telegram profile slot available")
        log(slot_id, f"leased {tg_acct['id']} (balance not probed — dashboard Get Balance is the source)")

        clog = lambda m, _id=tg_acct["id"]: print(f"[tg:{_id}:{bot_id}] {m}", flush=True)
        if _stopped():
            raise RuntimeError("stopped")
        bot = _make_tg_bot(tg_acct, bot_id, is_headless, clog)
        ok_boot, msg_boot = _boot_bot(bot)
        if not ok_boot:
            raise RuntimeError(f"bot boot: {msg_boot}")

        lease_stop = threading.Event()
        lid = tg_acct["id"]

        def _beat(_stop=lease_stop, _lid=lid):
            while not _stop.wait(300):
                try:
                    tg_manager.heartbeat(_lid)
                except Exception:
                    break

        threading.Thread(target=_beat, daemon=True).start()

        if not bot.choose_task(task):
            raise RuntimeError(f"Could not select {task} in {bot_id}")
        creds = bot.start_task() or {}
        if creds.get("error") == "limit_reached":
            raise RuntimeError(f"PayGo hourly limit reached: {creds.get('detail', '')}")
        login = _clean_username(creds.get("login") or "")
        if not (login and _is_valid_ig_username(login) and creds.get("password")):
            raise RuntimeError(f"{bot_id} returned no usable credentials (got {creds})")
        t0 = time.monotonic()  # bot TTL anchor: counts from task Start
        creds["login"] = login
        cname = _sanitize_name(creds.get("first_name") or "")
        clog(f"creds: name='{creds.get('first_name')}' login='{login}'")
        runner.tg_creds = creds
        runner.new_username = login
        runner.new_password = creds["password"]
        if cname:
            runner.name = cname
        runner.tg_id = tg_acct["id"]
        runner.tg_bot = bot_id

        # -- Step 2: Meta Creation ----------------------------------------
        if _stopped():
            raise RuntimeError("stopped")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "Cookie cycle: Meta creation…"})
        runner._install_screenshot_hooks()
        runner._launch()
        runner.open_mail()
        runner.meta_signup()
        if not runner.ensure_meta_verified():
            raise RuntimeError("Meta account verification not confirmed on auth.meta.com — aborting before Instagram to prevent phone wall")
        log(slot_id, f"Meta created ({runner.email})")

        # -- Flow steps (data-driven via tg_flows) ------------------------
        # Each step is a callable keyed by the names in tg_flows.FLOWS[flow].
        # A new step = one entry here + one in the flow's "steps" list.
        def _step_ig_join(ctx):
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"IG join with bot user ({login})…"})
            runner.ig_login()
            runner.ig_click_meta_card()
            runner.ig_complete_join()
            if runner.ig_username:
                runner.new_username = runner.ig_username
            runner.ig_dismiss_onboarding()  # Back-out + follow ~2 suggested
            ig_page = runner._ig_tab()
            if runner._has_human_check(ig_page):
                raise RuntimeError("Instagram human checkpoint on fresh account — dead end")

        def _step_2fa(ctx):
            # Taskly's cookie task asks for the 2FA KEY before the cookie:
            # set up 2FA on IG, submit the key to the bot, read the code back,
            # confirm it in Accounts Center. (PayGo's cookie flow skips this.)
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": f"IG 2FA setup + {bot_id} submit…"})
            require_window("2FA submit")
            secret = runner.ig_2fa_begin()
            if not secret:
                raise RuntimeError("Could not retrieve 2FA secret key from Instagram")
            code = bot.submit_2fa_key(secret, allow_local_fallback=False)
            if not code:
                raise RuntimeError(f"{bot.bot_name} did not return OTP code for 2FA key")
            log(slot_id, f"Received OTP from {bot.bot_name}; confirming on IG…")
            if not runner.ig_2fa_confirm(code):
                raise RuntimeError("Instagram rejected the 2FA code")

        def _step_cookie_export(ctx):
            try:
                jar = runner.w.context.cookies()
            except Exception as exc:
                raise RuntimeError(f"cookie jar unreadable: {exc}")
            ig_cookies = [c for c in jar if "instagram.com" in str(c.get("domain", ""))]
            names = {c.get("name") for c in ig_cookies}
            if "sessionid" not in names:
                raise RuntimeError(
                    f"no IG sessionid after join (have: {sorted(names)}) — refusing to submit")
            cookie_str = "; ".join(
                f"{c['name']}={c['value']}" for c in ig_cookies
                if c.get("name") and c.get("value") is not None)
            log(slot_id, f"cookie: {len(ig_cookies)} IG cookies, {len(cookie_str)} chars, "
                         f"sessionid={'sessionid' in cookie_str}")
            if len(cookie_str) < 100:
                raise RuntimeError("cookie string too short (<100 chars)")
            ctx["cookie_str"] = cookie_str

        def _step_submit_cookie(ctx):
            nonlocal ok, rec_id
            cookie_str = ctx.get("cookie_str") or ""
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": "Submitting IG cookie to PayGoBot…"})
            ok_cookie, reply = bot.submit_cookie(cookie_str, timeout=25)
            if not ok_cookie:
                raise RuntimeError(f"PayGo rejected the cookie: {reply[:200]}")
            require_window("register confirm")
            submitted = bot.mark_registered()
            if not submitted:
                log(slot_id, "register receipt not seen — one more tap…")
                submitted = bot.mark_registered()
            if not submitted:
                raise RuntimeError("PayGo registration not confirmed — not recording Submitted")
            runner.tg_submitted = submitted
            from tg_stats import record_submission
            rec_id = f"tg_{int(time.time()*1000)}"
            record_submission(bot_id or "paygo")
            runner.last_record_id = rec_id
            emit_event({"type": "account_submitted", "pipeline": "telegram",
                        "tg_account": tg_acct["id"], "tg_bot": bot_id or "paygo",
                        "account_id": rec_id})
            log(slot_id, f"SUBMITTED ({rec_id})")
            ok = True

        _STEPS = {
            "ig_join": _step_ig_join,
            "2fa": _step_2fa,
            "cookie_export": _step_cookie_export,
            "submit_cookie": _step_submit_cookie,
        }
        ctx = {}
        for _step in flow_steps:
            require_window(step_label(_step))
            _fn = _STEPS.get(_step)
            if _fn is None:
                raise RuntimeError(
                    f"flow for {bot_id}/{task!r}: step '{_step}' has no implementation")
            _fn(ctx)
        return True, rec_id

    except Exception as exc:
        detail = str(exc)
        log(slot_id, f"FAILED: {exc}")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                    "detail": f"Cookie cycle error: {exc}"})
        if bot is not None:
            try:
                bot.cancel_task()
            except Exception:
                pass
        return False, detail
    finally:
        try:
            if lease_stop is not None:
                lease_stop.set()
        except Exception:
            pass
        if tg_acct:
            try:
                tg_manager.release(tg_acct["id"], ok=ok,
                                   account_id=rec_id if ok else None)
            except Exception:
                pass
        if bot is not None:
            try:
                bot.close(ok=ok)
            except Exception:
                pass
        try:
            runner.finish()
        except Exception:
            pass
        try:
            worker._cleanup_browser_resources()
        except Exception:
            pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description="One-shot cookie-family task cycle")
    ap.add_argument("--slot", type=int, default=91)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--captcha", default="extension", choices=("extension", "audio"))
    ap.add_argument("--mail", default="mailtd")
    ap.add_argument("--task", default=COOKIE_TASK,
                    help='task label, e.g. "🍪 Create Inst (No mail)"')
    ap.add_argument("--bot", default="paygo", help="bot id: paygo | taskly")
    ap.add_argument("--use-ig-pool", action="store_true",
                    help="Drain pre-created accounts from the IG Creator pool")
    args = ap.parse_args()
    ok, _detail = run_cookie_cycle_once(
        slot_id=args.slot, is_headless=args.headless,
        captcha_mode=args.captcha, mail_provider=args.mail,
        tg_task=args.task, tg_bot=args.bot, use_ig_pool=args.use_ig_pool)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
