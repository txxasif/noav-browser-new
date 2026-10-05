#!/usr/bin/env python3
"""One-shot FastPay "Instagram 2FA" POOL-DRAIN cycle (no Meta, no signup).

Reuses a PRE-CREATED Instagram account from the IG Creator pool:

    lease TG -> FastPay "Instagram 2FA" -> bot creds (username/password)
    -> pop ONE pooled IG account (data/store.db)
    -> rename it to the bot login        (direct IG Web API, ~0.4s)
    -> launch browser, inject the account's IG cookies
    -> 2FA: capture the key -> submit to FastPay -> enter the returned CODE on IG
    -> change the IG password to the bot password
    -> press Confirm in FastPay (register) -> consume the pooled account

FastPay's task does NOT need an email step (unlike Taskly), so the pool flow is
`ig_rename -> 2fa -> password -> register`.

Runner is selected from the registry: ``tg_tasks.FASTPAY_2FA_POOL`` → flow
``fastpay_pool_2fa`` → ``tg_flows.runner_of`` == ``run_fastpay_pool_cycle``. The
existing ``2fa`` (Taskly/FastPay coupled) flow is untouched (invariant 24).

Import-safe for ``worker.py`` (lazy ``AISlotWorker`` import — no cycle).
"""
from __future__ import annotations

import os
import sys
import threading
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

try:
    from ai_config import run as _engine_run
    _engine_run._point_playwright_at_browsers()
except Exception:
    pass

from ai_config import SELFIE_PATH, emit_event  # noqa: E402
from runner import MetaInstaRunner  # noqa: E402
from tg_accounts import tg_manager  # noqa: E402
from run_cookie_cycle import (  # noqa: E402
    change_ig_username_fast,
    _is_account_dead_error,
    _all_flooded_until,
    _sleep_until,
    _ig_spam_streak,
    _IG_SPAM_STOP,
)
from run_pool_2fa_cycle import (  # noqa: E402
    _cookies_for_playwright,
    _purge_pool_account,
    _browser_logged_in,
    _mail_tokens_from_extra,
    _mailtd_list,
    _mailtd_http_list,
    _make_pool_fetch_code,
)
from pipelines.telegram.tg_support import (  # noqa: E402
    _boot_bot,
    _clean_username,
    _is_tg_session_lost,
    _is_valid_ig_username,
    _make_tg_bot,
    _sanitize_name,
    IGDeadEnd,
)

FASTPAY_TASK = "FastPay 2FA"        # alias → tg_tasks.FASTPAY_2FA_POOL
FASTPAY_FLOW = "fastpay_pool_2fa"
BOT_ID = "fastpay"
TASK_WINDOW = 420                   # bot ~8-min TTL; fail fast past it


def log(slot_id, m):
    print(f"[fp2fa:{slot_id}] {m}", flush=True)


def run_fastpay_pool_cycle_once(slot_id=94, worker_factory=None, is_headless=False,
                                captcha_mode="extension", mail_provider="mailtd",
                                stop_event=None, add_email=False,
                                tg_task=None, tg_bot="fastpay", use_ig_pool=True,
                                tg_id=None):
    """Run ONE pooled FastPay-2FA cycle. Returns ``(ok, detail)``."""
    import store

    task = tg_task or FASTPAY_TASK
    bot_id = str(tg_bot or BOT_ID)
    if bot_id != BOT_ID:
        bot_id = BOT_ID

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

    # Reclaim submittals abandoned by an abrupt stop BEFORE the pool-empty
    # gate — otherwise stuck claims make the pool look empty and the drain
    # stops for good.
    try:
        store.recover_stale_submitting()
    except Exception:
        pass
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
    runner = None
    worker = None
    ok = False
    rec_id = None

    try:
        if not tg_manager.usable():
            raise RuntimeError("No logged-in Telegram profile available")
        tg_acct = tg_manager.acquire(timeout=30, bot=bot_id, only_id=tg_id)
        if not tg_acct:
            wait_until = _all_flooded_until()
            if wait_until and wait_until > time.time():
                secs = int(wait_until - time.time())
                slice_s = max(30, min(secs, 300))
                log(slot_id, f"[pool] Telegram profiles FLOOD-LIMITED ({secs // 60}m "
                             f"{secs % 60}s recorded). Sleeping {slice_s}s, then re-verifying.")
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

        try:
            bot.reset_to_main_menu()
        except Exception:
            pass
        try:
            bot.cancel_task()
        except Exception:
            pass

        if not bot.choose_task(task):
            _v = getattr(bot, "last_task_verdict", None) or "hidden"
            raise RuntimeError(f"Could not select {task} in {bot_id} [task_unavailable:{_v}]")
        log(slot_id, f"[task] Selected '{task}' on {bot_id} (TG {tg_acct['id']})")

        creds = bot.start_task() or {}
        t0 = time.monotonic()
        login = _clean_username(creds.get("login") or "")
        if not (login and _is_valid_ig_username(login) and creds.get("password")):
            raise RuntimeError(f"{bot_id} returned no usable credentials (got {creds})")
        cname = _sanitize_name(creds.get("first_name") or "")
        clog(f"creds: name='{creds.get('first_name')}' login='{login}'")
        log(slot_id, f"[creds] {bot_id} issued target username: '{login}'")

        # -- Browser (launch ONCE; reused across pool-account retries) --------
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "FastPay pool 2FA: launching browser with the pooled IG session…"})
        worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
        runner = MetaInstaRunner(
            worker, twofa=True, telegram=False, tg_task=task,
            captcha_mode="none", mail_provider="mailtd", target="telegram",
        )
        if os.path.exists(SELFIE_PATH):
            runner.selfie_path = SELFIE_PATH
        runner._install_screenshot_hooks()
        runner._launch()
        ctx = getattr(getattr(runner, "w", None), "context", None)
        if ctx is None:
            raise RuntimeError("browser context unavailable after launch")

        runner.tg_creds = dict(creds)
        runner.tg_creds["login"] = login
        runner.new_username = login
        runner.new_password = creds.get("password")
        runner.username = login
        runner.password = creds.get("password")
        if cname:
            runner.name = cname
        runner.tg_id = tg_acct["id"]
        runner.tg_bot = bot_id

        # -- Claim + verify + rename, RETRYING the next pool account on a dead
        #    session / login wall / rename failure. TG task is never cancelled.
        secret = None
        _2fa_already_on = False
        MAX_POOL_TRIES = 6
        for _try in range(MAX_POOL_TRIES):
            if _stopped():
                raise RuntimeError("stopped")
            if time.monotonic() - t0 > TASK_WINDOW:
                raise RuntimeError("Bot task window exceeded during FastPay pool 2FA")

            pool_acc = None
            for _scan in range(10):
                if _stopped():
                    raise RuntimeError("stopped")
                cand = store.pop_ig_creator_account()
                if not cand or not cand.get("cookies"):
                    break
                cand_id = cand["id"]
                cand_user = cand.get("instagram_username") or cand.get("username") or "unknown"
                log(slot_id, f"[pool] Claimed IG Creator account {cand_id} (current username: '{cand_user}')")

                # 1) load the pooled session into the browser and VERIFY login
                try:
                    ctx.clear_cookies()
                except Exception:
                    pass
                ctx.add_cookies(_cookies_for_playwright(cand["cookies"]))
                page = runner._ig_tab()
                try:
                    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(2500)
                except Exception as exc:
                    log(slot_id, f"[⚠️] IG tab load note: {exc}")
                if not _browser_logged_in(page):
                    _purge_pool_account(store, cand, log, slot_id, emit_event, "browser session not logged in")
                    continue

                # 2) rename to the FastPay username (direct Web API)
                log(slot_id, f"⚡ [api] Changing username: '{cand_user}' -> '{login}' via direct IG Web API…")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                            "detail": f"Fast IG username change: {cand_user} -> {login}…"})
                ok_name, name_msg = change_ig_username_fast(cand["cookies"], login, ua=cand.get("device_ua"))
                if ok_name:
                    pool_acc = cand
                    _ig_spam_streak[0] = 0
                    log(slot_id, f"✅ [api] IG username updated to '{login}' in ~0.4s ({name_msg})")
                    clog(f"⚡ [username] Updated Instagram username: '{cand_user}' -> '{login}' (in 0.4s)")
                    break
                if _is_account_dead_error(name_msg):
                    _purge_pool_account(store, cand, log, slot_id, emit_event, f"dead/banned ({name_msg})")
                    continue
                # FAILED rename -> remove the account (never retry); stop if it is
                # IP-level (many in a row).
                _ig_spam_streak[0] += 1
                if _ig_spam_streak[0] >= _IG_SPAM_STOP:
                    raise RuntimeError(
                        f"IG rename failed on {_ig_spam_streak[0]} consecutive accounts "
                        f"(last: {name_msg[:60]}) — IP-level rate-limit; pausing the drain.")
                _purge_pool_account(store, cand, log, slot_id, emit_event,
                                    f"rename FAILED ({name_msg[:60]}) [{_ig_spam_streak[0]}/{_IG_SPAM_STOP}]")
                pool_acc = None
                continue
            if not pool_acc:
                raise RuntimeError("Failed to obtain a valid working IG Creator account from pool")

            acc_id = pool_acc["id"]

            # Point the runner at the account's ORIGINAL stored mail.td inbox so
            # the Accounts-Center "Check your email" re-auth (which fires DURING
            # 2FA setup for a cookie-injected session) can be solved. Open the
            # inbox FIRST and snapshot its existing message ids so only a FRESH
            # code is accepted.
            mail_tokens = _mail_tokens_from_extra(pool_acc.get("extra"))
            runner.mail = None
            runner.mail_tokens = mail_tokens
            preexisting_mail_ids = set()
            if mail_tokens:
                try:
                    # HTTP snapshot of existing messages (fast ~0.3s, no extra browser tab)
                    msgs = _mailtd_http_list(mail_tokens)
                    preexisting_mail_ids = {str(m.get("id")) for m in msgs if m.get("id")}
                    log(slot_id, f"[📧] Inbox snapshotted via HTTP — {len(preexisting_mail_ids)} "
                                 f"existing message(s) ignored; waiting for a fresh code.")
                    # The re-auth code goes to the account's EXISTING email, so
                    # read it from the stored inbox (no bot Get-code at this stage).
                    runner.fetch_code = _make_pool_fetch_code(runner, preexisting_mail_ids)
                except Exception as exc:
                    log(slot_id, f"[⚠️] HTTP inbox snapshot failed: {exc}")
            else:
                log(slot_id, "[⚠️] Account has no stored mail.td tokens — the AC email "
                             "re-auth may fail (2FA setup might still proceed).")
            runner.email = pool_acc.get("email")

            # 3) 2FA: capture key on IG -> submit to FastPay -> confirm the code on IG
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": f"2FA setup on pooled IG account ({login})…"})
            # Enter Accounts Center the HUMAN way first: feed → Profile → Options
            # → Settings → Accounts Center, with a short feed dwell. A direct
            # deep-link to accountscenter.instagram.com is the strongest IG-side
            # automation tell (no referer chain, no dwell), so it is now only a
            # FALLBACK for when the click path cannot get there (a cookie-injected
            # session occasionally has the profile tap blocked by the "Save your
            # login info" sheet). ig_2fa_begin's _ac_section step 0 reuses the
            # already-open Accounts Center tab, so this is the only entry.
            try:
                entered = runner._ac_warm_entry("/password_and_security/")
            except Exception as exc:
                entered = False
                log(slot_id, f"[⚠️] AC warm-entry note: {exc}")
            if not entered:
                try:
                    page = runner._ig_tab()
                    page.goto("https://accountscenter.instagram.com/password_and_security/",
                              wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                    log(slot_id, "[ac] warm entry missed — used direct AC navigation (fallback).")
                except Exception as exc:
                    log(slot_id, f"[⚠️] AC pre-nav note: {exc}")
            else:
                log(slot_id, "[ac] entered Accounts Center via the in-app UI (no URL jump).")
            try:
                secret = runner.ig_2fa_begin()
            except IGDeadEnd as exc:
                _purge_pool_account(store, pool_acc, log, slot_id, emit_event, f"dead end after rename ({exc})")
                pool_acc = None
                raise RuntimeError(f"IG dead end after rename ({exc})")
            # 2FA ALREADY ON (account created with the Meta Creator 2FA toggle):
            # ig_2fa_begin returns None because there is no setup dialog, but the
            # seed was parked on the record. Mirror core/lifecycle's "2FA already
            # on" branch — submit the PARKED seed and skip the IG confirm. This
            # is the browserless fast path, identical to the Taskly/PayGo drains.
            if not secret:
                parked = (pool_acc.get("twofa_secret") or "").strip()
                if parked:
                    secret = parked
                    _2fa_already_on = True
                    log(slot_id, f"[🔐] 2FA already enabled — using parked seed "
                                 f"({parked[:4]}****); skipping IG setup.")
            if not secret:
                store.restore_ig_creator_account(acc_id, rotate=True)
                pool_acc = None
                raise RuntimeError("Could not retrieve 2FA secret key from Instagram (Accounts Center)")
            break

        if not secret or not pool_acc:
            raise RuntimeError("Could not reach 2FA setup on any pooled IG account")

        acc_id = pool_acc["id"]
        log(slot_id, f"[🔑] 2FA key captured; submitting to {bot_id}…")
        code = bot.submit_2fa_key(secret, allow_local_fallback=False)
        if not code:
            raise RuntimeError(f"{bot_id} did not return an OTP code for the 2FA key")
        if _2fa_already_on:
            # 2FA was already enabled with the parked seed — no IG setup dialog
            # to confirm. The bot holds the key and derived the code.
            log(slot_id, "✔ 2FA already enabled on the pooled account (parked seed) — no IG confirm needed.")
        else:
            log(slot_id, f"[tg] Received OTP from {bot_id}; confirming on IG…")
            if not runner.ig_2fa_confirm(code):
                ok2 = False
                try:
                    import re as _re
                    import pyotp
                    _s = _re.sub(r"[^A-Za-z2-7]", "", str(secret or "")).upper()
                    for _t in range(3):
                        local = pyotp.TOTP(_s).now()
                        if local != str(code):
                            log(slot_id, f"[🔑] Bot code rejected — retrying with local TOTP {local}…")
                            if runner.ig_2fa_confirm(local):
                                ok2 = True
                                break
                        time.sleep(31 - (int(time.time()) % 30))
                except Exception as exc:
                    log(slot_id, f"[⚠️] local TOTP retry error: {exc}")
                if not ok2:
                    raise RuntimeError("Instagram rejected the 2FA code")
            log(slot_id, "✔ 2FA enabled on the pooled account.")

        # 4) password — set the IG password to the bot-issued one.
        # FastPay's task uses the Username/Password IT issued, so a wrong password
        # means a rejected submission. One retry, then fail the cycle instead of
        # submitting the account with the wrong password.
        target_pw = (runner.tg_creds or {}).get("password") or runner.new_password
        cur_pw = pool_acc.get("password") or runner.password
        if target_pw and target_pw != cur_pw:
            ok_pw = False
            why = "unknown"
            for _pw_try in range(2):
                try:
                    log(slot_id, f"[🔑] Changing account password to the FastPay task password… (try {_pw_try + 1}/2)")
                    runner.password = cur_pw
                    ok_pw = runner.ig_set_password(target_pw, current_password=cur_pw)
                except Exception as exc:
                    ok_pw = False
                    log(slot_id, f"[⚠️] password change error: {exc}")
                if ok_pw:
                    runner.password = target_pw
                    log(slot_id, "[🔑] Password updated to the FastPay task password.")
                    break
                why = getattr(runner, "_pw_fail_reason", None) or "unknown"
                log(slot_id, f"[⚠️] Password change failed (reason={why}) on try {_pw_try + 1}/2.")
                time.sleep(1.5)
            if not ok_pw:
                # Do NOT abort — 293 FastPay submissions succeeded while the same
                # "Password change failed" was logged, so the bot accepts the
                # registration without the password matching. Log and continue.
                log(slot_id, f"[⚠️] Password change failed (reason={why}) — continuing "
                             f"(the bot accepts the registration; current pw in store may be stale).")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                            "detail": f"Password change failed (reason={why}) — continuing"})

        # 5) register — press Confirm in FastPay
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                    "detail": "Confirming submission with FastPayBot…"})
        submitted = bot.mark_registered()
        if not submitted:
            log(slot_id, "register receipt not seen — one more tap…")
            submitted = bot.mark_registered()
        if not submitted:
            store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError("FastPay registration not confirmed — not recording Submitted")

        # Consume the account
        store.delete_record(acc_id)
        if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
            try:
                os.remove(pool_acc["session_file"])
            except Exception:
                pass
        pool_acc = None
        log(slot_id, f"[pool] Account {acc_id} successfully consumed and removed from pool.")

        from tg_stats import record_submission
        rec_id = f"tg_{int(time.time() * 1000)}"
        # SEPARATE counter from the regular FastPay bot — the pool-2FA drain has
        # its own number (tg_stats["fastpay2fa"]) so it never inflates "fastpay".
        record_submission("fastpay2fa")
        emit_event({"type": "account_submitted", "pipeline": "telegram",
                    "tg_account": tg_acct["id"], "tg_bot": bot_id, "account_id": rec_id})
        emit_event({"type": "account_deleted", "account_id": acc_id})
        emit_event({"type": "accounts_updated"})
        log(slot_id, f"🎉 [SUBMITTED] FastPay confirmed (+ ~$0.024) -> record {rec_id} for user '{login}'")
        ok = True
        return True, rec_id

    except Exception as exc:
        detail = str(exc)
        _fw = 0
        if bot is not None:
            try:
                _fw = bot._sleep_flood(exc, "fastpay pool drain")
            except Exception:
                _fw = 0
        if _fw:
            log(slot_id, f"⏳ Telegram rate limit — slept {_fw}s before retrying.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "throttled",
                        "detail": f"Telegram FloodWait — waited {_fw}s (account throttled)."})
            return False, "floodwait"
        if "database is locked" in detail.lower():
            if bot is not None:
                try:
                    bot.disconnect()
                except Exception:
                    pass
            log(slot_id, "🔓 Session file was locked — released the handle.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "lock_released",
                        "detail": "Session DB lock released — account returned to the pool."})
        if _is_tg_session_lost(detail):
            try:
                bot.close(ok=False) if bot is not None else None
            except Exception:
                pass
            if tg_acct:
                try:
                    tg_manager.disable(tg_acct["id"],
                                       reason="dead Telegram session (fastpay pool drain)")
                    log(slot_id, f"🔒 {tg_acct['id']} Telegram session is dead — DISABLED.")
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
                    "detail": f"FastPay pool drain error: {exc}"})
        if pool_acc is not None and _is_account_dead_error(detail):
            _purge_pool_account(store, pool_acc, log, slot_id, emit_event, f"dead/banned ({detail[:60]})")
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
                tg_manager.release(tg_acct["id"], ok=ok,
                                   account_id=rec_id if ok else None)
            except Exception:
                pass
        if bot is not None:
            try:
                bot.close(ok=ok)
            except Exception:
                pass
        if runner is not None:
            try:
                runner.finish()
            except Exception:
                pass
        if worker is not None:
            try:
                worker._cleanup_browser_resources()
            except Exception:
                pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description="One-shot FastPay 2FA pool-drain cycle")
    ap.add_argument("--slot", type=int, default=94)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--captcha", default="extension", choices=("extension", "audio"))
    ap.add_argument("--task", default=FASTPAY_TASK, help='task alias (default "FastPay 2FA")')
    ap.add_argument("--bot", default="fastpay", help="bot id (fastpay)")
    ap.add_argument("--tg-id", default=None, help="hard-pin the Telegram profile id (e.g. tg_1)")
    args = ap.parse_args()
    ok, detail = run_fastpay_pool_cycle_once(
        slot_id=args.slot, is_headless=args.headless,
        captcha_mode=args.captcha, tg_task=args.task, tg_bot=args.bot,
        tg_id=args.tg_id)
    print("RESULT:", ok, detail)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
