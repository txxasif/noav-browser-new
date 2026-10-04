"""Decoupled Telegram cycles: Phase-1 creators and Phase-2 submitters.

Split out of the former 1488-line ``pipelines/telegram/tg_worker.py`` (2026-09-25).
These are the two *independent* cycles (invariant #8): ``run_tg_create_cycle``
creates Meta+IG accounts in parallel and parks them (``status="Created"``), and
``run_tg_submit_one`` drains that queue one-by-one through the TG pool
(``status="Submitted"``). Neither shares state with the coupled cycle beyond the
helpers in :mod:`pipelines.telegram.tg_support`.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
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
import warm_pool  # noqa: E402
from tg_accounts import tg_manager  # noqa: E402

from pipelines.telegram.tg_support import (  # noqa: E402
    _boot_bot,
    _cancel_with_timeout,
    _force_close,
    _is_tg_session_lost,
    _make_tg_bot,
    _drop_tg_bot,
    _register_inspector,
    _reap_wedged_tg_browser,
    _sanitize_name,
    close_inspectors,
)

def run_tg_create_cycle(
    worker_factory,
    slot_id: int,
    is_headless: bool = False,
    twofa: bool = True,
    new_username: Optional[str] = None,
    new_password: Optional[str] = None,
    telegram: bool = False,
    tg_task: Optional[str] = None,
    captcha_mode: str = "extension",
    mail_provider: str = "mailtd",
    stop_event: Optional[threading.Event] = None,
):
    """Create ONE Meta+Instagram account targeted for Telegram with Instagram email linkage."""
    if stop_event and stop_event.is_set():
        return False, None

    tg_acct = None
    if telegram:
        tg_acct = tg_manager.acquire(timeout=60)
        if not tg_acct:
            msg = f"Slot #{slot_id}: No idle Telegram account available in pool. Waiting..."
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "waiting", "detail": msg})
            raise RuntimeError(msg)

    worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
    runner = None
    try:
        runner = MetaInstaRunner(
            worker,
            twofa=twofa,
            new_username=new_username,
            new_password=new_password,
            telegram=telegram,
            tg_task=tg_task or TG_DEFAULT_TASK,
            tg_id=tg_acct["id"] if tg_acct else None,
            tg_profile_dir=tg_acct["profile_dir"] if tg_acct else None,
            captcha_mode=captcha_mode,
            mail_provider=mail_provider,
            target="telegram",
        )
    except Exception as exc:
        if tg_acct:
            try:
                tg_manager.release(tg_acct["id"], ok=False, bot_error=True)
            except Exception:
                pass
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error", "detail": f"Error: {exc}"})
        return False, str(exc)

    if os.path.exists(SELFIE_PATH):
        runner.selfie_path = SELFIE_PATH

    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching", "detail": "Launching anti-detect browser (TG target)…"})
    ok = False
    rec_id = None
    try:
        if telegram:
            runner.run_flow()
            rec_id = runner.last_record_id
            ok = runner.tg_submitted
        else:
            rec_id = runner.create_account(twofa=twofa, target="telegram")
            ok = True
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "created", "detail": f"TG Account completed ({rec_id})."})
        return True, rec_id
    except Exception as exc:
        if tg_acct and _is_tg_session_lost(exc):
            # Dead Telegram session in the legacy linked flow: disable the
            # profile so the next create cycle leases a different one instead
            # of re-picking this one (has_session heuristics can mask it).
            try:
                tg_manager.disable(tg_acct["id"],
                                   reason="dead Telegram session (create flow)")
            except Exception:
                pass
            emit_event({"type": "log", "slot_id": slot_id,
                        "message": f"[tg] {tg_acct['id']} logged out — disabled, "
                                   "switching to another Telegram profile."})
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error", "detail": f"Error: {exc}"})
        return False, str(exc)
    finally:
        if tg_acct:
            try:
                tg_manager.release(tg_acct["id"], ok=ok, account_id=rec_id)
            except Exception:
                pass
        try:
            if runner is not None:
                runner.finish()
        except Exception:
            pass
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "closed", "detail": "Browser closed."})


def run_tg_submit_one(worker_factory, acct: dict, task: str = TG_DEFAULT_TASK, is_headless: bool = True, bot_choice: str = "taskly"):
    """Submit ONE parked account to chosen Telegram bot (Taskly Bot or PayGoBot) using an acquired Telegram profile."""
    rec = store.pop_pending(destination="telegram")
    if rec is None:
        return None, False, True

    session_file = rec.get("session_file")
    if not session_file or not os.path.exists(session_file):
        sdir = os.path.join(DATA_DIR, "sessions")
        candidate = os.path.join(sdir, f"{rec['id']}.json")
        if os.path.exists(candidate):
            session_file = candidate
        elif not session_file:
            session_file = candidate

    bot_target = "paygo" if bot_choice == "paygo" else "taskly"
    log = lambda m: print(f"[tg:{acct['id']}] {m}", flush=True)
    log(f"Claimed parked account {rec.get('id')} ({rec.get('username')}) for {bot_target.upper()} task")

    bot = None
    worker = None
    runner = None
    ig_wb = None
    ig_ctx = None
    ok, code, creds, secret = False, None, {}, None
    updated_user, updated_pw, updated_name = None, None, None
    bot_error = False

    from concurrent.futures import ThreadPoolExecutor

    try:
        # 1+2. Warm contexts for both legs (fresh per account, processes
        # reused): IG resume runs here while the pooled bot opens in parallel.
        worker = worker_factory(slot_id=f"tg_{acct['id']}", is_headless=is_headless)
        runner = MetaInstaRunner(worker, telegram=False, target="telegram")
        # Hand the parked mail.td tokens to the runner so email OTP fetches
        # can re-open the SAME inbox in this warm context (no mailbox tab here).
        try:
            runner.mail_tokens = rec.get("mail_tokens") or {}
        except Exception:
            pass
        if os.path.exists(SELFIE_PATH):
            runner.selfie_path = SELFIE_PATH
        # Playwright sync objects are bound to their creating thread: key the
        # warm IG browser per submitter THREAD, never per TG profile, or a
        # later submit on another thread crashes with greenlet thread-switch.
        ig_wb = warm_pool.get("ig", f"thr_{threading.get_ident()}", is_headless)
        ig_ctx = ig_wb.new_account_context(log=runner.log)
        bot = _make_tg_bot(acct, bot_target, is_headless, log)

        with ThreadPoolExecutor(max_workers=1) as _pool:
            _bot_fut = _pool.submit(_boot_bot, bot)
            resumed = runner.resume_session(session_file, check_meta=False, warm_ctx=ig_ctx)
            if not resumed:
                log("[⚠️] Session resume not verified, attempting direct login…")
                user = rec.get("username") or rec.get("instagram_username") or rec.get("email")
                pw = rec.get("password") or rec.get("meta_password")
                sec = rec.get("twofa_secret")
                if user and pw:
                    resumed = runner.ig_direct_login(user, pw, twofa_secret=sec)
            bot_ok, bot_msg = _bot_fut.result()

        if not resumed:
            raise RuntimeError("Failed to restore session or log in to Instagram for account")
        if not bot_ok:
            bot_error = True
            if _is_tg_session_lost(bot_msg):
                # Dead session: take the profile out of rotation so the next
                # submitter loop iteration leases a different one, then fail
                # just this account (never the loop).
                try:
                    tg_manager.disable(acct["id"],
                                       reason="dead Telegram session (submit boot check)")
                except Exception:
                    pass
                emit_event({"type": "log", "slot_id": None,
                            "message": f"[tg] {acct['id']} logged out — disabled, "
                                       "switching to another Telegram profile."})
            raise RuntimeError(bot_msg)
        if not bot.choose_task(task):
            bot_error = True
            _v = getattr(bot, "last_task_verdict", None) or "hidden"
            raise RuntimeError(f"Task '{task}' could not be selected in {bot.bot_name} [task_unavailable:{_v}]")
        # Taskly task window: bot auto-cancels ~8 min after Start ("Time's
        # up!"). Budget is logged at every phase boundary; if adapt runs
        # long, prefer Account Registered with username+password+2FA aligned
        # over burning the window on the display name (14-day quota anyway).
        import time as _t
        _task_t0 = _t.time()
        _TASK_WINDOW = 480
        def _budget(phase):
            left = _TASK_WINDOW - (_t.time() - _task_t0)
            log(f'[⏱️] Task window: {phase} — {max(0, int(left))}s left of ~{_TASK_WINDOW}s'
                + (' — OVERDUE, finish fast!' if left < 60 else ''))
        creds = bot.start_task()
        _budget("task started")
        if not (creds.get("login") and creds.get("password")):
            bot_error = True
            raise RuntimeError(f"{bot.bot_name} returned no credentials (got {creds})")

        # 3. Adapt username, password, email linkage, and live 2FA
        _budget("adapt begin")
        res = runner.adapt_to_tg_task(rec, creds, bot)
        _budget("adapt done")
        secret = res.get("twofa_secret")
        code = res.get("code")
        updated_name = res.get("name")
        updated_user = res.get("username")
        updated_pw = res.get("password")

        # 4. Confirm registration on Telegram
        _budget("confirming registration")
        ok = bot.mark_registered()

        # Update session state after credentials change
        if session_file and runner.w and runner.w.context:
            try:
                runner.w.context.storage_state(path=session_file)
            except Exception:
                pass

    except Exception as exc:
        log(f"TG Submit flow failed on {bot_target}: {exc}")
        ok = False
        try:
            if bot is not None:
                bot.cancel_task()
        except Exception:
            pass
    finally:
        # Warm teardown: close ONLY the per-account contexts (processes stay
        # warm for the next submit); feed the circuit breaker with the outcome.
        if runner is not None:
            try:
                runner.finish_warm()
            except Exception:
                pass
        try:
            if ig_ctx is not None:
                warm_pool.close_account_context(ig_ctx)
        except Exception:
            pass
        try:
            if ig_wb is not None:
                ig_wb.note_result(ok)
        except Exception:
            pass
        try:
            if bot is not None:
                bot.close(ok=ok)
        except Exception:
            pass

    try:
        store.finish_submit(
            rec["id"],
            ok,
            tg_id=acct["id"],
            code=code,
            tg_creds=creds,
            twofa_secret=secret,
            updated_username=updated_user,
            updated_password=updated_pw,
            updated_name=updated_name,
            tg_bot=bot_target,
        )
    except Exception as exc:
        log(f"⚠️ finish_submit failed: {exc}")
        try:
            store.finish_submit(rec["id"], False, tg_id=acct["id"])
        except Exception:
            pass

    emit_event({
        "type": "account_submitted" if ok else "submit_failed",
        "pipeline": "telegram",
        "tg_account": acct["id"],
        "tg_bot": bot_target,
        "account_id": rec["id"],
    })
    return rec["id"], ok, not bot_error
