#!/usr/bin/env python3
"""One-shot Taskly "📱 Create Inst (2FA)" POOL-DRAIN cycle (no Meta, no signup).

Reuses a PRE-CREATED Instagram account from the IG Creator pool instead of
creating Meta → Instagram from scratch:

    lease TG -> Taskly "Create Inst (2FA)" -> bot creds (login/password)
    -> pop ONE pooled IG account (data/store.db)
    -> rename it to the bot login        (direct IG Web API, ~0.4s)
    -> launch browser, inject the account's IG cookies
    -> 2FA in Accounts Center (the stored mail.td inbox solves the email re-auth)
    -> submit the 2FA key to Taskly -> enter the returned code -> register
    -> consume (delete) the pooled account

The runner is selected from the registry: ``tg_tasks.INST_2FA_POOL`` →
flow ``pool_2fa`` → ``tg_flows.runner_of`` == ``run_pool_2fa_cycle``. The
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
    _all_flooded_until,
    _sleep_until,
    _ig_spam_streak,
    _IG_SPAM_STOP,
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

POOL_TASK = "Taskly 2FA"          # alias → tg_tasks.INST_2FA_POOL (pool_2fa flow)
POOL_FLOW = "pool_2fa"
TASK_WINDOW = 420                 # bot ~8-min TTL; fail fast past it


def log(slot_id, m):
    print(f"[pool2fa:{slot_id}] {m}", flush=True)


def _cookies_for_playwright(cookie_str: str) -> list:
    """Parse a '; k=v' cookie header into Playwright add_cookies() dicts."""
    out = []
    for part in str(cookie_str or "").split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, val = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        out.append({"name": name, "value": val, "domain": ".instagram.com", "path": "/"})
    return out


def _mail_tokens_from_extra(extra) -> dict:
    """Extract the stored mail.td {tempmail_account_id, tempmail_token}."""
    try:
        ex = extra
        if isinstance(ex, str):
            ex = json.loads(ex) if ex.strip() else {}
        toks = (ex or {}).get("mail_tokens") or {}
        if isinstance(toks, dict) and toks.get("tempmail_token"):
            return toks
    except Exception:
        pass
    return {}


def _mailtd_list(runner):
    """Return the raw mail.td message list for the runner's stored inbox."""
    try:
        mail = getattr(runner, "mail", None)
        if mail is None or mail.is_closed():
            return []
        ctx = runner._mailtd_api_ctx()
        if not ctx:
            return []
        res = mail.evaluate("""async ({id, token}) => {
            try {
                const r = await fetch('/api/accounts/' + id + '/messages?page=1',
                    {headers: {Authorization: 'Bearer ' + token}});
                if (!r.ok) return {status: r.status, messages: []};
                const j = await r.json();
                return {status: 200, messages: (j && j.messages) || []};
            } catch (e) { return {status: -1, messages: []}; }
        }""", {"id": ctx["id"], "token": ctx["token"]})
        return (res or {}).get("messages") or []
    except Exception:
        return []


def _make_pool_fetch_code(runner, preexisting_ids, bot=None):
    """A ``fetch_code`` for the pooled flow.

    Tries the BOT's ``📥 Get code`` first (works once the bot-issued email is
    linked to the account, mirroring the Taskly flow), then falls back to a
    FRESH code from the account's stored mail.td inbox (never the stale
    signup/Meta code).
    """
    def _fetch(keyword="instagram", timeout=60, subject_hint=None, prefer_len=None, **kwargs):
        if bot is not None:
            try:
                c = bot.request_email_code(timeout=min(int(timeout or 45), 45))
                if c:
                    try:
                        runner.log(f"[📧] bot Get-code returned: {c}")
                    except Exception:
                        pass
                    return c
            except Exception:
                pass
        try:
            runner._ensure_mail_tab()
        except Exception:
            pass
        mail = getattr(runner, "mail", None)
        if mail is None:
            return None
        try:
            if mail.is_closed():
                return None
        except Exception:
            pass
        end = time.time() + max(5, int(timeout or 60))
        seen = {}
        while time.time() < end:
            msgs = [m for m in _mailtd_list(runner) if str(m.get("id")) not in preexisting_ids]
            try:
                msgs.sort(key=lambda m: str(m.get("created_at") or m.get("createdAt")
                                              or m.get("updatedAt") or m.get("id") or ""),
                          reverse=True)
            except Exception:
                pass
            for msg in msgs:
                mid = msg.get("id")
                subject = str(msg.get("subject") or "").lower()
                sender = str(msg.get("from") or "").lower()
                if subject_hint:
                    hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                    if not any(h in subject or h in sender for h in hints):
                        continue
                text = seen.get(mid)
                if text is None and mid:
                    try:
                        ctx = runner._mailtd_api_ctx() or {}
                        text = mail.evaluate("""async ({id, mid, token}) => {
                            try {
                                const r = await fetch('/api/accounts/' + id + '/messages/' + mid,
                                    {headers: {Authorization: 'Bearer ' + token}});
                                if (!r.ok) return '';
                                const j = await r.json();
                                return [j.subject||'', j.html_body||'', j.text_body||'', j.text||'', j.body||''].join(' ');
                            } catch (e) { return ''; }
                        }""", {"id": ctx.get("id"), "mid": mid, "token": ctx.get("token")}) or ""
                    except Exception:
                        text = ""
                    if not text:
                        try:
                            text = " ".join(runner._flatten_values(msg))
                        except Exception:
                            text = ""
                    seen[mid] = text
                try:
                    code = runner._pick_code(text or "", keyword, set(), prefer_len=prefer_len)
                except Exception:
                    code = None
                if code:
                    try:
                        runner.log(f'[📧] fresh {keyword} code: {code} (subject: {subject[:40]})')
                    except Exception:
                        pass
                    return code
            try:
                mail.wait_for_timeout(1500)
            except Exception:
                time.sleep(1.5)
        return None
    return _fetch


def _purge_pool_account(store, cand, log, slot_id, emit_event, reason):
    """Permanently remove a pooled account that cannot be used (dead session,
    login wall, no 2FA key). Never cancels the TG task — the caller just moves
    on to the next account."""
    cid = (cand or {}).get("id")
    if not cid:
        return
    try:
        store.delete_record(cid)
    except Exception:
        pass
    sf = (cand or {}).get("session_file")
    if sf and os.path.exists(sf):
        try:
            os.remove(sf)
        except Exception:
            pass
    try:
        log(slot_id, f"[pool] Purged account {cid} ({reason}) — trying the next.")
    except Exception:
        pass
    emit_event({"type": "account_deleted", "account_id": cid})
    emit_event({"type": "accounts_updated"})


def _browser_logged_in(page) -> bool:
    """True when the injected pooled session is actually logged in.

    A logged-OUT browser shows the saved-account chooser ("Use another
    profile"), the /accounts/login wall, or a public visitor view ("Log in" +
    "Open app"). The benign "Save your login info" sheet is NOT a logged-out
    signal, so it must not be treated as one.
    """
    try:
        url = (page.url or "").lower()
        t = (page.inner_text("body") or "").lower()
    except Exception:
        return True
    if "/accounts/login" in url:
        return False
    if "use another profile" in t:
        return False
    if ("log in" in t or "login" in t) and "open app" in t:
        return False
    return True


def run_pool_2fa_cycle_once(slot_id=93, worker_factory=None, is_headless=False,
                            captcha_mode="extension", mail_provider="mailtd",
                            stop_event=None, add_email=False,
                            tg_task=None, tg_bot="taskly", use_ig_pool=True):
    """Run ONE pooled Taskly-2FA cycle. Returns ``(ok, detail)``."""
    import store

    task = tg_task or POOL_TASK
    bot_id = str(tg_bot or "taskly")

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
        # from a clean menu instead of talking into a dead task.
        try:
            bot.reset_to_main_menu()
        except Exception:
            pass
        try:
            bot.cancel_task()
        except Exception:
            pass

        if not bot.choose_task(task):
            raise RuntimeError(f"Could not select {task} in {bot_id}")
        log(slot_id, f"[task] Selected '{task}' on {bot_id} (TG {tg_acct['id']})")

        creds = bot.start_task() or {}
        t0 = time.monotonic()
        login = _clean_username(creds.get("login") or "")
        if not (login and _is_valid_ig_username(login) and creds.get("password")):
            raise RuntimeError(f"{bot_id} returned no usable credentials (got {creds})")
        cname = _sanitize_name(creds.get("first_name") or "")
        clog(f"creds: name='{creds.get('first_name')}' login='{login}'")
        log(slot_id, f"[creds] Taskly issued target username: '{login}'")

        # -- Browser (launch ONCE; reused across pool-account retries) --------
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "Pool 2FA: launching browser with the pooled IG session…"})
        worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
        runner = MetaInstaRunner(
            worker, twofa=True, telegram=False, tg_task=task,
            captcha_mode=captcha_mode, mail_provider="mailtd", target="telegram",
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
                runner.insta_page = None
                page = runner._ig_tab()
                try:
                    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(2500)
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
                    break
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
                    runner._ensure_mail_tab()
                    for _ in range(4):
                        preexisting_mail_ids = {str(m.get("id")) for m in _mailtd_list(runner)}
                        if preexisting_mail_ids:
                            break
                        time.sleep(1.5)
                    log(slot_id, f"[📧] Inbox opened BEFORE 2FA — {len(preexisting_mail_ids)} "
                                 f"existing message(s) ignored; waiting for a fresh code.")
                except Exception as exc:
                    log(slot_id, f"[⚠️] Could not pre-open the stored inbox: {exc}")
                # Password-change OTP goes to the account's EXISTING (old) email
                # -> read it from the stored inbox, NOT the bot. The bot's Get
                # code is reserved for the email-link step below.
                runner.fetch_code = _make_pool_fetch_code(runner, preexisting_mail_ids)

            # -- Same step order as the Taskly flow:
            #    password -> email_link -> 2fa -> register
            runner.email = pool_acc.get("email")
            runner.new_password = creds.get("password")
            cur_pw = pool_acc.get("password") or runner.password

            # (1) password — set the account password to the bot-issued one
            target_pw = (runner.tg_creds or {}).get("password") or runner.new_password
            if target_pw and target_pw != cur_pw:
                try:
                    log(slot_id, "[🔑] Changing account password to the TG task password…")
                    runner.password = cur_pw
                    ok_pw = runner.ig_set_password(target_pw, current_password=cur_pw)
                except Exception as exc:
                    ok_pw = False
                    log(slot_id, f"[⚠️] password change error: {exc}")
                if ok_pw:
                    runner.password = target_pw
                    log(slot_id, "[🔑] Password updated to the TG task password.")
                else:
                    why = getattr(runner, "_pw_fail_reason", None) or "unknown"
                    log(slot_id, f"[⚠️] Password change failed (reason={why}) — continuing.")

            # (2) email_link — link the BOT-issued email, code via the bot's
            #     "📥 Get code" (this is the part we were skipping).
            bot_em = (runner.tg_creds or {}).get("email")
            if bot_em:
                log(slot_id, f"[✉️] Linking bot-issued email {bot_em} via 📥 Get code…")
                try:
                    linked = runner.ig_link_email_to_instagram(
                        bot_em, code_fetcher=lambda: bot.request_email_code(timeout=45))
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
                log(slot_id, f"[✉️] Bot email linkage result: {linked} (continuing regardless)")

            # Email-link done (its OTP came from the bot's 📥 Get code). For the
            # 2FA step, allow the bot's Get code first (the account email may now
            # be the bot's), then fall back to the stored inbox.
            runner.fetch_code = _make_pool_fetch_code(runner, preexisting_mail_ids, bot=bot)

            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": f"2FA setup on pooled IG account ({login})…"})
            # Navigate DIRECTLY into Accounts Center. The in-app profile→gear→AC
            # nav is fragile for a cookie-injected session (the "Save your login
            # info" sheet blocks the profile tap, and the logged-in Settings page
            # trips the Block/Restrict wall check). ig_2fa_begin's _ac_section
            # step 0 reuses an already-open Accounts Center tab, so this skips it.
            try:
                page = runner._ig_tab()
                page.goto("https://accountscenter.instagram.com/password_and_security/",
                          wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                log(slot_id, f"[ac] pre-navigated to Accounts Center ({page.url[:70]})")
            except Exception as exc:
                log(slot_id, f"[⚠️] AC pre-nav note: {exc}")
            try:
                secret = runner.ig_2fa_begin()
            except IGDeadEnd as exc:
                # Genuine dead end (login wall / logged-out / checkpoint): REMOVE
                # it from the pool so it is never re-claimed. The bot username is
                # now taken by this account, so fail this cycle — the slot retries
                # with a fresh Taskly task/login.
                _purge_pool_account(store, pool_acc, log, slot_id, emit_event, f"dead end after rename ({exc})")
                pool_acc = None
                raise RuntimeError(f"IG dead end after rename ({exc})")
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
        log(slot_id, f"[tg] Received OTP from {bot_id}; confirming on IG…")
        if not runner.ig_2fa_confirm(code):
            raise RuntimeError("Instagram rejected the 2FA code")
        log(slot_id, "✔ 2FA enabled on the pooled account.")

        # -- Step: register confirm ------------------------------------------
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                    "detail": "Confirming Account Registered with TasklyBot…"})
        submitted = bot.mark_registered()
        if not submitted:
            log(slot_id, "register receipt not seen — one more tap…")
            submitted = bot.mark_registered()
        if not submitted:
            # Account is now 2FA-enabled but not paid — restore it so it is not
            # silently lost, and let the slot retry.
            store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError("Taskly registration not confirmed — not recording Submitted")

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
        # SEPARATE counter from the regular Taskly bot — the pool-2FA drain has
        # its own number (tg_stats["taskly2fa"]) so it never inflates "taskly".
        record_submission("taskly2fa")
        emit_event({"type": "account_submitted", "pipeline": "telegram",
                    "tg_account": tg_acct["id"], "tg_bot": bot_id,
                    "account_id": rec_id})
        emit_event({"type": "account_deleted", "account_id": acc_id})
        emit_event({"type": "accounts_updated"})
        log(slot_id, f"🎉 [SUBMITTED] Registration confirmed (+ $0.018) -> record {rec_id} for user '{login}'")
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
    ap = argparse.ArgumentParser(description="One-shot Taskly 2FA pool-drain cycle")
    ap.add_argument("--slot", type=int, default=93)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--captcha", default="extension", choices=("extension", "audio"))
    ap.add_argument("--task", default=POOL_TASK, help='task alias (default "Taskly 2FA")')
    ap.add_argument("--bot", default="taskly", help="bot id (taskly)")
    args = ap.parse_args()
    ok, detail = run_pool_2fa_cycle_once(
        slot_id=args.slot, is_headless=args.headless,
        captcha_mode=args.captcha, tg_task=args.task, tg_bot=args.bot)
    print("RESULT:", ok, detail)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
