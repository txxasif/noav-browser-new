#!/usr/bin/env python3
"""One-shot Taskly 2FA task cycle: lease TG -> Start -> bot email/name/login/
password -> IG NATIVE signup (email -> bot Get-code -> code -> details) ->
"Account Registered" -> Submitted.

Learned live 2026-09-28: the bot issues ALL registration data (the Email is
ordered async after Start; its 6-digit code comes ONLY from the bot's Get-code
key — the mailbox is bot-side). NO Meta account, NO temp mailbox.

The post-lease STEPS are data-driven by :mod:`tg_flows` (single source of
truth). For the ``native`` flow that is exactly::

    ig_signup -> register

Strict: first failure cancels the TG task, releases the lease, closes the
browser, and exits nonzero with the step in the message.
"""
from __future__ import annotations

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
# NOTE: AISlotWorker is imported lazily inside run_native_cycle_once —
# worker.py (which defines it) lazily imports this module for the TG engine
# path, so a top-level import here would be circular.
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

NATIVE_TASK = "📱 Create Inst (2FA)"
NATIVE_FLOW = "native"
TASK_WINDOW = 420  # bot TTL; fail fast past it
EMAIL_WAIT = 75    # bot orders the mailbox async after Start ("Ordering email…")


def log(slot_id, m):
    print(f"[native:{slot_id}] {m}", flush=True)


def run_native_cycle_once(slot_id=92, worker_factory=None, is_headless=False,
                          captcha_mode="extension", mail_provider="mailtd",
                          stop_event=None, add_email=False,
                          tg_task=None, tg_bot="taskly"):
    """Run ONE native Taskly-2FA cycle. Returns ``(ok, detail)``.

    ``add_email``/``mail_provider`` are accepted for call-site stability but
    IGNORED: the native flow has no mailbox of its own (email + code are
    bot-issued). Import-safe for ``worker.py`` (lazy ``AISlotWorker``
    import — no import cycle).
    """
    task = tg_task or NATIVE_TASK
    bot_id = str(tg_bot or "taskly")
    try:
        from tg_flows import resolve_steps as _resolve_steps
        flow_steps = _resolve_steps(bot_id, task)
    except Exception:
        flow_steps = ["ig_signup", "2fa", "register"]

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

    if add_email or (mail_provider or "mailtd") != "mailtd":
        log(slot_id, "[i] No local mailbox in the native flow (bot email+code) — "
                     "mail flags ignored.")

    worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
    runner = MetaInstaRunner(
        worker, twofa=False, telegram=False, tg_task=task,
        captcha_mode=captcha_mode, mail_provider="mailtd", target="telegram",
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
        # -- Preamble: lease FIRST (no Meta in this flow) -----------------
        if _stopped():
            return False, "stopped"
        if not tg_manager.usable():
            raise RuntimeError("No logged-in Telegram profile available")
        tg_acct = tg_manager.acquire(timeout=60, bot=bot_id)
        if not tg_acct:
            raise RuntimeError("No Telegram profile slot available")
        log(slot_id, f"leased {tg_acct['id']}")

        clog = lambda m, _id=tg_acct["id"]: print(f"[tg:{_id}:{bot_id}] {m}", flush=True)
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

        # Clear a possible orphan ACTIVE task (killed run) so choose_task
        # starts from a clean menu instead of talking into a dead task.
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
        creds = bot.start_task() or {}
        t0 = time.monotonic()  # bot TTL anchor: counts from task Start
        login = _clean_username(creds.get("login") or "")
        email = str(creds.get("email") or "").strip("`_* ")
        if not email:
            # The mailbox is ordered ASYNC ("Ordering email, please wait…"):
            # creds can arrive first, Email: follows in another message
            # (observed live 2026-09-28). Wait for it, don't re-Start.
            clog("no Email: in first creds — waiting for the follow-up email message…")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "waiting_email",
                        "detail": "Bot is ordering the mailbox (up to ~75s) — do NOT press Stop."})
            dl = time.time() + EMAIL_WAIT
            _beat = time.time()
            while time.time() < dl and not email:
                time.sleep(2)
                if time.time() - _beat >= 12:
                    _beat = time.time()
                    left = max(0, int(dl - time.time()))
                    clog(f"still waiting for bot email… {left}s left (bot orders it async after Start)")
                try:
                    texts = bot._call("_recent_texts", n=6)
                except Exception:
                    texts = []
                for t in texts or []:
                    m = re.search(r"Email:\s*(\S+)", t or "", re.I)
                    if m:
                        email = m.group(1).strip("`_* ")
                        break
            clog(f"email wait done: {email!r}")
        if not (login and _is_valid_ig_username(login) and creds.get("password") and email):
            raise RuntimeError(f"{bot_id} returned no usable credentials+email")
        creds["login"] = login
        creds["email"] = email
        cname = _sanitize_name(creds.get("first_name") or "")
        clog(f"creds: name='{creds.get('first_name')}' login='{login}' email='{email}'")
        runner.tg_creds = creds
        runner.new_username = login
        runner.new_password = creds["password"]
        runner.email = email
        runner.username = login
        runner.password = creds["password"]
        if cname:
            runner.name = cname
        runner.tg_id = tg_acct["id"]
        runner.tg_bot = bot_id
        import random as _rnd
        runner.dob_year, runner.dob_month, runner.dob_day = (
            str(_rnd.randint(1992, 2001)), str(_rnd.randint(1, 12)), str(_rnd.randint(1, 28)))

        # -- Browser (no mail tab, no Meta) --------------------------------
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "Native cycle: launching browser (no Meta)…"})
        runner._install_screenshot_hooks()
        runner._launch()

        # -- Flow steps (data-driven via tg_flows) -------------------------
        def _step_ig_signup(ctx):
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"IG native signup with bot email ({login})…"})
            require_window("native signup")

            def _code():
                return bot.request_email_code(timeout=45)

            live_user = runner.ig_signup_native(
                email, creds.get("first_name") or runner.name, login,
                creds["password"], request_code=_code, max_codes=3,
                dob=(int(runner.dob_year), int(runner.dob_month), int(runner.dob_day)))
            if live_user and live_user.strip().lower() != login.strip().lower():
                raise RuntimeError(
                    f"IG live username {live_user!r} != bot login {login!r} — "
                    "report would be REJECTED, refusing to submit")
            runner.ig_username = login
            runner.new_username = login
            ctx["live_user"] = live_user or login
            try:
                page = runner._ig_tab()
                if runner._has_human_check(page):
                    log(slot_id, "[🛡️] Instagram 'Confirm you're human' checkpoint detected — dead end; exiting immediately.")
                    raise IGDeadEnd(f"Instagram human checkpoint ({page.url}) — dead end")
            except IGDeadEnd:
                raise
            except Exception:
                pass

        def _step_2fa(ctx):
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": "Instagram 2FA setup + TG submit…"})
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

        def _step_register(ctx):
            nonlocal ok, rec_id
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": "Confirming Account Registered with TasklyBot…"})
            require_window("register confirm")
            submitted = bot.mark_registered()
            if not submitted:
                log(slot_id, "register receipt not seen — one more tap…")
                submitted = bot.mark_registered()
            if not submitted:
                raise RuntimeError("Taskly registration not confirmed — not recording Submitted")
            runner.tg_submitted = submitted
            from tg_stats import record_submission
            rec_id = f"tg_{int(time.time()*1000)}"
            record_submission(bot_id or "taskly")
            runner.last_record_id = rec_id
            emit_event({"type": "account_submitted", "pipeline": "telegram",
                        "tg_account": tg_acct["id"], "tg_bot": bot_id,
                        "account_id": rec_id})
            log(slot_id, f"SUBMITTED ({rec_id})")
            ok = True

        _STEPS = {
            "ig_signup": _step_ig_signup,
            "2fa": _step_2fa,
            "register": _step_register,
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
                    "detail": f"Native cycle error: {exc}"})
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
    ap = argparse.ArgumentParser(description="One-shot Taskly 2FA native task cycle")
    ap.add_argument("--slot", type=int, default=92)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--captcha", default="extension", choices=("extension", "audio"))
    ap.add_argument("--task", default=NATIVE_TASK,
                    help='task label, e.g. "📱 Create Inst (2FA)"')
    ap.add_argument("--bot", default="taskly", help="bot id (taskly)")
    args = ap.parse_args()
    ok, _detail = run_native_cycle_once(
        slot_id=args.slot, is_headless=args.headless,
        captcha_mode=args.captcha, tg_task=args.task, tg_bot=args.bot)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
