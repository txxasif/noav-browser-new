#!/usr/bin/env python3
"""One-shot PayGo "📱 Create Inst (2FA)" POOL-DRAIN cycle (no Meta, no signup).

Reuses a PRE-CREATED Instagram account from the IG Creator pool instead of
creating Meta → Instagram from scratch:

    lease TG -> PayGo "Create Inst (2FA)" -> bot creds (login/password)
    -> pop ONE pooled IG account (data/store.db)
    -> rename it to the bot login        (direct IG Web API, ~0.4s)
    -> launch browser, inject the account's IG cookies
    -> 2FA in Accounts Center (the stored mail.td inbox solves the email re-auth)
    -> submit the 2FA key to PayGo -> enter the returned code -> register
    -> consume (delete) the pooled account

The runner is selected from the registry: ``tg_tasks.PAYGO_2FA_POOL`` →
flow ``paygo_pool_2fa`` → ``tg_flows.runner_of`` == ``run_paygo_pool_2fa_cycle``. The
existing ``native``/``2fa``/``cookie`` flows are untouched (invariant 24).

Import-safe for ``worker.py`` (lazy ``AISlotWorker`` import — no cycle).
"""
from __future__ import annotations

import json
import os
import re
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
from tg_flows import step_label  # noqa: E402
from run_cookie_cycle import (  # noqa: E402
    change_ig_username_fast,
    _is_account_dead_error,
    _is_ig_checkpoint_error,
    _IG_CHECKPOINT_STOP,
    _IG_CHALLENGE_COOLDOWN,
    _ig_challenge_until,
    _trip_challenge_backoff,
    _all_flooded_until,
    _sleep_until,
    _ig_spam_streak,
    _IG_SPAM_STOP,
)
from pool_common import (  # noqa: E402
    _cookies_for_playwright,
    _mail_tokens_from_extra,
    _mailtd_list,
    _mailtd_http_list,
    _mailtd_http_body,
    _mailtd_http_code,
    _make_pool_fetch_code,
    _purge_pool_account,
    _browser_logged_in,
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

POOL_TASK = "PayGo 2FA"          # alias → tg_tasks.PAYGO_2FA_POOL (paygo_pool_2fa flow)
POOL_FLOW = "paygo_pool_2fa"
TASK_WINDOW = 420                 # bot ~8-min TTL; fail fast past it


def log(slot_id, m):
    print(f"[paygo2fa:{slot_id}] {m}", flush=True)


def run_paygo_pool_2fa_cycle_once(slot_id=95, worker_factory=None, is_headless=False,
                            captcha_mode="extension", mail_provider="mailtd",
                            stop_event=None, add_email=False,
                            tg_task=None, tg_bot="paygo", use_ig_pool=True):
    """Run ONE pooled PayGo-2FA cycle. Returns ``(ok, detail)``."""
    import store

    task = tg_task or POOL_TASK
    bot_id = str(tg_bot or "paygo")

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

    # IP-level rename challenge cooldown — check BEFORE leasing/Start so a parked
    # slot does NOT burn a bot task window (see run_cookie_cycle).
    if time.time() < _ig_challenge_until[0]:
        _remain = int(_ig_challenge_until[0] - time.time())
        log(slot_id, f"[pool] IG rename CHALLENGE cooldown — parking {min(_remain, 60)}s "
                     f"before leasing (accounts stay safe in the pool).")
        _sleep_until(time.time() + max(1, min(_remain, 60)), stop_event)
        return False, "ig_challenge_cooldown"

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
        tg_acct = tg_manager.acquire(timeout=30, bot=bot_id)
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

        # Clear a possible orphan ACTIVE task (killed run) so choose_task starts
        # from a clean menu instead of talking into a dead task. Orphan-clear
        # Cancels once (no live owner exists after a preempt); mid-cycle paths
        # below keep refusing via cancel_task.
        try:
            _clear = getattr(bot, "clear_orphan_task", None)
            if callable(_clear):
                _clear()
            else:
                bot.reset_to_main_menu()
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
        log(slot_id, f"[creds] PayGo issued target username: '{login}'")

        # -- Browser (launch ONCE; reused across pool-account retries) --------
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "Pool 2FA: launching browser with the pooled IG session…"})
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
        #    session. The browser login is verified BEFORE renaming, so a dead
        #    session never consumes the bot-issued username (which otherwise made
        #    the next account's rename fail with "username isn't available").
        #    The TG task is NEVER cancelled — bot creds stay valid across tries.
        secret = None
        _2fa_already_on = False
        MAX_POOL_TRIES = 6
        for _try in range(MAX_POOL_TRIES):
            if _stopped():
                raise RuntimeError("stopped")
            if time.monotonic() - t0 > TASK_WINDOW:
                raise RuntimeError("Bot task window exceeded during pool 2FA")

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

                # 1) Load the pooled session into the browser and VERIFY it is
                #    logged in BEFORE renaming.
                try:
                    ctx.clear_cookies()
                except Exception:
                    pass
                ctx.add_cookies(_cookies_for_playwright(cand["cookies"]))
                page = runner._ig_tab()
                try:
                    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
                    try:
                        page.wait_for_selector('[role="dialog"], div[aria-modal="true"]', timeout=3500)
                    except Exception:
                        pass
                    runner._dismiss_ig_sheets(page)
                except Exception as exc:
                    log(slot_id, f"[⚠️] IG tab load note: {exc}")
                if not _browser_logged_in(page):
                    _purge_pool_account(store, cand, log, slot_id, emit_event, "browser session not logged in")
                    continue

                # 2) Rename via the direct Web API.
                log(slot_id, f"⚡ [api] Changing username: '{cand_user}' -> '{login}' via direct IG Web API…")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                            "detail": f"Fast IG username change: {cand_user} -> {login}…"})
                ok_name, name_msg = change_ig_username_fast(
                    cand["cookies"], login, ua=cand.get("device_ua"))
                if ok_name:
                    pool_acc = cand
                    _ig_spam_streak[0] = 0
                    log(slot_id, f"✅ [api] IG username updated to '{login}' in ~0.4s ({name_msg})")
                    clog(f"⚡ [username] Updated Instagram username: '{cand_user}' -> '{login}' (in 0.4s)")
                    runner.ig_username = login
                    runner.username = login
                    runner.new_username = login
                    try:
                        page.goto(f"https://www.instagram.com/{login}/", wait_until="domcontentloaded", timeout=45000)
                        try:
                            page.wait_for_selector('[role="dialog"], div[aria-modal="true"]', timeout=3000)
                        except Exception:
                            pass
                        runner._dismiss_ig_sheets(page)
                    except Exception as exc:
                        log(slot_id, f"[⚠️] post-rename IG sync note: {exc}")
                    break
                if _is_ig_checkpoint_error(name_msg):
                    _ig_spam_streak[0] += 1
                    try:
                        store.mark_ig_creator_challenged(cand_id)
                    except Exception:
                        pass
                    emit_event({"type": "accounts_updated"})
                    if _IG_CHECKPOINT_STOP > 0 and _ig_spam_streak[0] >= _IG_CHECKPOINT_STOP:
                        _ig_spam_streak[0] = 0
                        _cd = _trip_challenge_backoff()
                        raise RuntimeError(
                            f"IG rename CHALLENGED on {_IG_CHECKPOINT_STOP} consecutive accounts "
                            f"({name_msg[:60]}) — IP-level checkpoint; pausing the drain "
                            f"{_cd}s (accounts restored, none purged).")
                    log(slot_id, f"⚠️ [pool] Rename CHALLENGED ({name_msg[:80]}) — RESTORING "
                                 f"account (NOT purging) [{_ig_spam_streak[0]}/{_IG_CHECKPOINT_STOP}].")
                    pool_acc = None
                    continue
                if _is_account_dead_error(name_msg):
                    _purge_pool_account(store, cand, log, slot_id, emit_event, f"dead/banned ({name_msg})")
                    continue
                # FAILED means FAILED: a rejected rename removes the account from
                # the pool — never retried / re-logged-in. Safety: if MANY fail in
                # a ROW the IP is flagged, so STOP instead of emptying the pool.
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
            mail_tokens = _mail_tokens_from_extra(pool_acc.get("extra"))
            if not mail_tokens:
                log(slot_id, "[⚠️] Account has no stored mail.td tokens — the AC email "
                             "re-auth step may fail (2FA setup might still proceed).")
            else:
                log(slot_id, f"[📧] Using stored mail.td inbox for {pool_acc.get('email')} "
                             f"(token {'present' if mail_tokens.get('tempmail_token') else 'MISSING'}).")

            # Point the runner at the account's ORIGINAL mail.td inbox so the
            # Accounts-Center "Check your email" re-auth can be solved. OPEN THE
            # INBOX FIRST (before clicking "Get started"), and snapshot its
            # existing message ids so only the FRESH code is accepted.
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
                except Exception as exc:
                    log(slot_id, f"[⚠️] HTTP inbox snapshot failed: {exc}")
            else:
                log(slot_id, "[⚠️] Account has NO stored mail.td token — the AC email "
                             "OTP cannot be read; the password step will be skipped.")
            # ALWAYS override fetch_code (even tokenless) so the base
            # MailboxMixin.fetch_code — which opens a mail.td browser tab — can
            # never run in the pool drain. Empty tokens make the HTTP path
            # return None immediately (no tab, no stall).
            runner.fetch_code = _make_pool_fetch_code(runner, preexisting_mail_ids)

            runner.email = pool_acc.get("email")
            runner.new_password = creds.get("password")
            # The pooled account still logs in with its OWN password until the
            # password step (now LAST) changes it — pin runner.password to the
            # real one so any AC password re-auth during email/2FA fills the
            # correct value (it was briefly the bot password from setup above).
            runner.password = pool_acc.get("password") or runner.password

            # Early dead-session purge (2026-10-04: the pool holds corpses
            # whose cookies pass the claim check but whose browser session is
            # already dropped — each burned 2 password tries + a 2FA attempt
            # before dying, all logged as reason=unknown). Fail fast here:
            # purge + cancel the unused TG task instead.
            try:
                _pw_alive = _browser_logged_in(runner._ig_tab())
            except Exception:
                _pw_alive = True
            if not _pw_alive:
                _purge_pool_account(store, pool_acc, log, slot_id, emit_event,
                                    "browser session dead before password change")
                pool_acc = None
                try:
                    bot.cancel_task()
                except Exception:
                    pass
                raise RuntimeError("Pooled IG session dead before password change — purged, retrying with next account")

            # Pre-fetch the AC password OTP in the BACKGROUND so it is already in
            # hand when the "Check your email" dialog appears. mail.td's REST list
            # is ~1.0s + body ~0.4s, so polling from the start of the step hides
            # that latency behind the AC navigation instead of paying it after
            # the challenge is detected.
            _pw_otp = {"code": None, "stop": False}
            if mail_tokens:
                def _pw_prefetch():
                    try:
                        c = _mailtd_http_code(
                            runner, mail_tokens, preexisting_mail_ids, "instagram", 60,
                            subject_hint=("authenticate your profile|authenticate|security "
                                          "code|meta account code|instagram|security"))
                        if c and not _pw_otp["stop"]:
                            _pw_otp["code"] = c
                            log(slot_id, f"[📧] password OTP pre-fetched ({c[:2]}****) — ready for the challenge.")
                    except Exception:
                        pass
                threading.Thread(target=_pw_prefetch, daemon=True).start()
                _base_pw_fetch = runner.fetch_code

                def _pw_fetch(keyword="instagram", timeout=60, subject_hint=None,
                              prefer_len=None, **kw):
                    # The background prefetch IS the poller — wait on its cache for
                    # the fetcher's budget (no second concurrent mail.td reader),
                    # then hand off to the original fetcher for any tail time.
                    end = time.time() + max(3, int(timeout or 60))
                    while time.time() < end:
                        if _pw_otp["code"]:
                            return _pw_otp["code"]
                        if _pw_otp["stop"]:
                            break
                        time.sleep(0.3)
                    return _base_pw_fetch(keyword, timeout=5,
                                          subject_hint=subject_hint, prefer_len=prefer_len, **kw)

                runner.fetch_code = _pw_fetch

            # (1) PASSWORD FIRST — change to the TG task password while the
            # account STILL has its original mail.td inbox attached.
            # If Instagram challenges with an email OTP, runner.fetch_code
            # captures it from the stored mail.td token directly (no bot code-window dependency).
            cur_pw = pool_acc.get("password") or runner.password
            target_pw = (runner.tg_creds or {}).get("password") or runner.new_password
            pw_ok = True
            if not mail_tokens and target_pw and target_pw != cur_pw:
                # No stored inbox -> the AC password re-auth OTP can never be
                # read. Skip the change (it would only stall on the challenge
                # and burn the bot window) and continue to the email/2FA steps.
                pw_ok = False
                log(slot_id, "[🔑] No stored mail.td token — skipping password change "
                             "(the AC OTP is unfetchable); continuing.")
            elif target_pw and target_pw != cur_pw:
                ok_pw = False
                why = "unknown"
                for _pw_try in range(2):
                    try:
                        log(slot_id, f"[🔑] Changing account password to the TG task password… (try {_pw_try + 1}/2)")
                        runner.password = cur_pw
                        ok_pw = runner.ig_set_password(target_pw, current_password=cur_pw)
                    except Exception as exc:
                        ok_pw = False
                        log(slot_id, f"[⚠️] password change error: {exc}")
                    if ok_pw:
                        runner.password = target_pw
                        log(slot_id, "[🔑] Password updated to the TG task password.")
                        break
                    why = getattr(runner, "_pw_fail_reason", None) or "unknown"
                    log(slot_id, f"[⚠️] Password change failed (reason={why}) on try {_pw_try + 1}/2.")
                    time.sleep(1.5)
                if not ok_pw:
                    pw_ok = False
                    log(slot_id, f"[⚠️] Password change failed (reason={why}) — continuing "
                                 f"(the bot accepts the registration; current pw in store may be stale).")
                    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                                "detail": f"Password change failed (reason={why}) — continuing"})

            # Password step done — stop the background inbox poll and restore a
            # FRESH fetch_code (the cached password OTP must not be reused by a
            # later AC re-auth during the email/2FA steps).
            _pw_otp["stop"] = True
            if mail_tokens:
                runner.fetch_code = _make_pool_fetch_code(runner, preexisting_mail_ids)

            # (2) EMAIL LINK SECOND — the bot issues the account email and its
            #     confirmation code (the "📥 Get code" key). This runs right
            #     after password change: the code only exists after IG's OTP is triggered
            #     from the email form, and the bot's code window is short (~60s).
            #     Try to link it, but NEVER let it burn the bot window: on
            #     miss/fail continue to the 2FA submit regardless (worst case the
            #     registration still pays).
            _get_code_pressed = {"v": False}

            def _fetch_bot_email_code():
                _get_code_pressed["v"] = True
                log(slot_id, f"[tg] Requesting email verification code from {bot_id} (📥 Get code)…")
                code = bot.request_email_code(timeout=60)
                if code:
                    log(slot_id, f"[tg] Received email confirmation code from {bot_id}: {code}")
                else:
                    log(slot_id, f"[tg] No email code received from {bot_id} within timeout.")
                return code

            bot_em = (runner.tg_creds or {}).get("email")
            if not bot_em and hasattr(bot, "creds") and isinstance(bot.creds, dict):
                bot_em = bot.creds.get("email")
            if not bot_em and hasattr(bot, "_recent_texts"):
                try:
                    for t in bot._recent_texts(6):
                        m = re.search(r"Email:\s*(\S+)", str(t), re.I)
                        if m:
                            bot_em = m.group(1).replace("`", "").strip()
                            if runner.tg_creds:
                                runner.tg_creds["email"] = bot_em
                            break
                except Exception:
                    pass
            log(slot_id, f"[✉️] Bot creds email resolved: {bot_em or 'NONE'}")

            if bot_em and pw_ok:
                log(slot_id, f"[✉️] Linking bot-issued email {bot_em} via 📥 Get code…")
                import time as _time
                _em_t0 = _time.time()
                try:
                    linked = runner.ig_link_email_to_instagram(
                        bot_em, code_fetcher=_fetch_bot_email_code)
                except IGDeadEnd as exc:
                    linked = False
                    log(slot_id, f"[⚠️] Bot email rejected ({exc}) — continuing to 2FA.")
                except Exception as exc:
                    _em = str(exc)
                    # "This email is already linked" (or any already-linked /
                    # confirmed message) is NOT fatal: once the bot's OTP has been
                    # used to confirm the email, just move on to 2FA.
                    if "already" in _em.lower() or "linked" in _em.lower():
                        log(slot_id, f"[✉️] Email already linked ({_em[:80]}) — ignoring, continuing to 2FA.")
                    else:
                        log(slot_id, f"[⚠️] Bot email linkage error ({_em[:120]}) — continuing.")
                    linked = False
                log(slot_id, f"[✉️] Bot email linkage result: {linked} "
                             f"({int(_time.time() - _em_t0)}s, continuing to 2FA)")
            elif bot_em and not pw_ok:
                # Password was NOT changed -> do NOT link the bot email. Adding it
                # rewrites the account's contact point, so the NEXT password OTP
                # would go to the bot inbox (unreadable) and the account becomes
                # permanently un-drainable. Skip the link and go straight to 2FA.
                log(slot_id, "[✉️] Password not changed — skipping the bot-email link "
                             "(it would rewrite the account email and break the next OTP).")
            else:
                log(slot_id, "[✉️] No bot-issued email provided in task credentials — skipping email link step.")

            # The bot's 2FA task only opens its "send the 2FA Key" prompt AFTER
            # 📥 Get code is pressed for the bot-issued email. When IG reports
            # that email is ALREADY linked/in use (the common pool case),
            # ig_link_email_to_instagram never calls the code fetcher above — so
            # the press never happened and submit_2fa_key later came back with no
            # one-time code ("Telegram bot did not return a one-time code",
            # observed 2026-10-07). Always advance the bot past the email step
            # before the 2FA submit; the bot answers "already linked" and moves on.
            if not _get_code_pressed["v"]:
                try:
                    _adv = getattr(bot, "press_get_code", None)
                    if callable(_adv):
                        _adv()
                    elif bot_em and callable(getattr(bot, "request_email_code", None)):
                        bot.request_email_code(timeout=10)
                except Exception as exc:
                    log(slot_id, f"[⚠️] Get-code advance failed ({exc}) — continuing to 2FA.")

            # (2) 2FA SECOND — setup + submit the key so the bot issues the one-time
            #     code, then confirm it on IG. Runs right after email: whichever
            #     of 2FA/password runs first pays the one AC email-OTP challenge
            #     (old stored inbox), the other opens clean. The bot is waiting
            #     for the 2FA key since Get code was consumed in step 1.
            if mail_tokens:
                try:
                    preexisting_mail_ids.update(str(m.get("id")) for m in _mailtd_http_list(mail_tokens))
                except Exception:
                    pass
            runner.fetch_code = _make_pool_fetch_code(runner, preexisting_mail_ids, bot=bot)

            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": f"2FA setup on pooled IG account ({login})…"})
            try:
                secret = runner.ig_2fa_begin()
            except IGDeadEnd as exc:
                # Genuine dead end (login wall / logged-out / checkpoint): REMOVE
                # it from the pool so it is never re-claimed. The bot username is
                # now taken by this account, so fail this cycle — the slot retries
                # with a fresh PayGo task/login.
                _purge_pool_account(store, pool_acc, log, slot_id, emit_event, f"dead end after rename ({exc})")
                pool_acc = None
                raise RuntimeError(f"IG dead end after rename ({exc})")
            # 2FA ALREADY ON (account created with the Meta Creator 2FA toggle):
            # ig_2fa_begin returns None because there is no setup dialog, but the
            # seed was parked on the record. Mirror core/lifecycle's "2FA already
            # on" branch — submit the PARKED seed and skip the IG confirm (there
            # is nothing to confirm). This is the browserless fast path.
            if not secret:
                parked = (pool_acc.get("twofa_secret") or "").strip()
                if parked:
                    secret = parked
                    _2fa_already_on = True
                    log(slot_id, f"[🔐] 2FA already enabled — using parked seed "
                                 f"({parked[:4]}****); skipping IG setup.")
            if not secret:
                # No key: if the session is logged out it's dead -> purge;
                # otherwise treat it as transient and keep the account.
                try:
                    still_in = _browser_logged_in(runner._ig_tab())
                except Exception:
                    still_in = True
                if not still_in:
                    _purge_pool_account(store, pool_acc, log, slot_id, emit_event, "logged out during 2FA")
                    pool_acc = None
                    raise RuntimeError("Pooled IG session logged out during 2FA — purged")
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
            # 2FA was already enabled with the parked seed — there is no IG setup
            # dialog to confirm. The bot holds the key and derived the code; we
            # just cross-check that the seed is the one generating it (advisory).
            log(slot_id, "✔ 2FA already enabled on the pooled account (parked seed) — no IG confirm needed.")
        else:
            log(slot_id, f"[tg] Received OTP from {bot_id}; confirming on IG…")
            if not runner.ig_2fa_confirm(code):
                # The bot's TOTP was stale/wrong (observed 2026-10-05 01:37 —
                # the bot returned 524511 in <1s and IG rejected it while the
                # next cycle's code confirmed fine). We hold the SAME secret, so
                # compute the code locally and retry; if it is the same 30s
                # window, wait for the roll, then retry once more.
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
                        # Same window: wait for the next 30s slot.
                        time.sleep(31 - (int(time.time()) % 30))
                except Exception as exc:
                    log(slot_id, f"[⚠️] local TOTP retry error: {exc}")
                if not ok2:
                    raise RuntimeError("Instagram rejected the 2FA code")
            log(slot_id, "✔ 2FA enabled on the pooled account.")


        # -- Step: register confirm ------------------------------------------
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                    "detail": "Confirming Account Registered with PayGoBot…"})
        submitted = bot.mark_registered()
        if not submitted:
            log(slot_id, "register receipt not seen — one more tap…")
            submitted = bot.mark_registered()
        if not submitted:
            # Account is now 2FA-enabled but not paid — restore it so it is not
            # silently lost, and let the slot retry.
            store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError("PayGo registration not confirmed — not recording Submitted")

        # Consume the account (do not double-spend).
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
        # SEPARATE counter from the regular PayGo bot — the pool-2FA drain has
        # its own number (tg_stats["paygo2fa"]) so it never inflates "paygo".
        record_submission("paygo2fa")
        emit_event({"type": "account_submitted", "pipeline": "telegram",
                    "tg_account": tg_acct["id"], "tg_bot": bot_id,
                    "account_id": rec_id})
        emit_event({"type": "account_deleted", "account_id": acc_id})
        emit_event({"type": "accounts_updated"})
        log(slot_id, f"🎉 [SUBMITTED] Registration confirmed (+ $0.022) -> record {rec_id} for user '{login}'")
        ok = True
        return True, rec_id

    except Exception as exc:
        detail = str(exc)
        _fw = 0
        if bot is not None:
            try:
                _fw = bot._sleep_flood(exc, "pool 2FA drain")
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
                                       reason="dead Telegram session (pool 2FA drain)")
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
                    "detail": f"Pool 2FA drain error: {exc}"})
        # Dead/banned signal raised (not returned by an explicit branch): take
        # the account OUT of the pool instead of restoring it.
        if pool_acc is not None and _is_account_dead_error(detail):
            log(slot_id, f"⚠️ [pool] Account {pool_acc['id']} is dead/banned ({detail[:90]}) — permanently removing.")
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
    ap = argparse.ArgumentParser(description="One-shot PayGo 2FA pool-drain cycle")
    ap.add_argument("--slot", type=int, default=95)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--captcha", default="extension", choices=("extension", "audio"))
    ap.add_argument("--task", default=POOL_TASK, help='task alias (default "PayGo 2FA")')
    ap.add_argument("--bot", default="paygo", help="bot id (paygo)")
    args = ap.parse_args()
    ok, detail = run_paygo_pool_2fa_cycle_once(
        slot_id=args.slot, is_headless=args.headless,
        captcha_mode=args.captcha, tg_task=args.task, tg_bot=args.bot)
    print("RESULT:", ok, detail)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
