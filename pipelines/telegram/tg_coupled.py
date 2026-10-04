"""The coupled per-task cycle: ONE browser does Meta -> TG task -> IG -> submit.

Split out of the former 1488-line ``pipelines/telegram/tg_worker.py`` (2026-09-25).
``run_tg_coupled_cycle`` is the engine's main path and stays in one module
deliberately: it is one long stateful sequence whose steps share the live
locals (``runner``, ``bot``, ``creds``, ``_require_window``, the TG task window).
Extracting steps would mean threading a dozen parameters through, which is where
this file's bugs came from originally.

Order (classic): Meta creation (no lease held, so N slots create in parallel) ->
lease a TG profile -> bot task creds -> IG login + Meta card + join (same
browser) -> dismiss onboarding (Back out of the registered cards + follow ~2) ->
Accounts Center: 2FA -> password -> email -> ``mark_registered`` submit gate ->
Submitted, close the browser, release the lease.
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
    TG_BOTS,
    TG_DEFAULT_TASK,
    TG_MAX_PARALLEL,
    emit_event,
)
from runner import MetaInstaRunner  # noqa: E402
import store  # noqa: E402
from tg_accounts import tg_manager  # noqa: E402

from pipelines.telegram.tg_support import (  # noqa: E402
    _boot_bot,
    _cancel_with_timeout,
    _clean_username,
    _drop_tg_bot,
    _force_close,
    _ig_name_too_long,
    _inspector_keeps,
    _is_junk_name,
    _is_tg_session_lost,
    _is_valid_ig_username,
    _make_tg_bot,
    _random_display_name,
    _register_inspector,
    _reap_wedged_tg_browser,
    _sanitize_name,
    close_inspectors,
    _DEAD_ENDS,
    IGDeadEnd,
)
from tg_flows import resolve_steps as _resolve_steps  # noqa: E402

# Coupled-cycle state. Lives HERE, not in tg_support, because it is touched only
# inside run_tg_coupled_cycle.
# Consecutive "bot offers no task" strikes per TG profile (anti Meta-burn).
_task_unavailable_strikes: dict = {}

def run_tg_coupled_cycle(
    worker_factory,
    slot_id: int,
    is_headless: bool = False,
    tg_task: Optional[str] = None,
    tg_bot: str = "taskly",
    captcha_mode: str = "extension",
    mail_provider: str = "mailtd",
    add_email: bool = False,
    stop_event: Optional[threading.Event] = None,
    strict: bool = True,
):
    """Coupled per-task flow — ONE browser, TG task first, IG-side completion.

    STRICT (default, no fallbacks): every step runs exactly once. No
    cancel-and-retry on bad creds, no username-swap hooks, no silent
    recovery. The first failure raises immediately with the step in the
    error, the TG lease is released, and the BROWSER IS LEFT OPEN (nothing
    is closed) so the failure can be inspected manually where it stopped.
    Only a fully Submitted task closes its browser.
    """
    """Coupled per-task flow — ONE browser, TG task first, IG-side completion.

    Order (no URL jumping inside IG — every screen is driven click-by-click):
      1. Meta: launch browser → mail → signup → verified (no TG lease held,
         so N slots can create in parallel).
      2. TG: lease a profile → boot bot → choose task → Start → bot creds
         (name / login / password). Malformed logins are cancelled and
         re-requested (max 3) before any IG step.
      3. IG (SAME browser session): login → click the Meta card → join wizard
         injects the bot's name/login directly → dismiss onboarding.
      4. IG-side completion: link email → change password to the bot password
         (Accounts Center, Meta row) → 2FA setup → submit key to the bot
         (strict, no local fallback) → confirm OTP on IG → Account registered.
      5. Save Submitted, close the browser, release the TG lease. Next task
         opens a fresh browser.

    A failed task burns its bot creds, so nothing is parked — the slot just
    closes the browser, releases the lease and reports the error.
    """
    if stop_event and stop_event.is_set():
        return False, None

    worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
    runner = None
    bot = None
    tg_acct = None
    bot_choice = None
    rec_id = None
    ok = False
    dead_end = False
    _lease_stop = None

    def _stopped() -> bool:
        try:
            return bool(stop_event and stop_event.is_set())
        except Exception:
            return False

    def _nolease_log(m):
        print(f"[slot:{slot_id}] {m}", flush=True)

    log = _nolease_log

    try:
        runner = MetaInstaRunner(
            worker,
            twofa=True,
            telegram=False,
            tg_task=tg_task or TG_DEFAULT_TASK,
            captcha_mode=captcha_mode,
            mail_provider=mail_provider,
            target="telegram",
        )
        if os.path.exists(SELFIE_PATH):
            runner.selfie_path = SELFIE_PATH

        # -- Step 1: Meta (no TG lease held) -------------------------------
        if _stopped():
            return False, "stopped"
        # Pre-flight: Meta creation is the expensive, irreversible step. If NO
        # pool profile is enabled AND logged-in, no lease can ever succeed —
        # fail now with a clear reason instead of burning a Meta account and
        # only then hitting "No Telegram profile slot available".
        if not tg_manager.usable():
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "waiting",
                        "detail": "No logged-in Telegram profile available…"})
            raise RuntimeError(
                "No Telegram profile is logged in (all disabled/logged out) — "
                "log in via Dashboard → Telegram Accounts.")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "Launching browser (Meta creation)…"})
        runner._install_screenshot_hooks()
        runner._launch()
        runner.open_mail()
        runner.meta_signup()
        if not runner.ensure_meta_verified():
            raise RuntimeError("Meta account verification not confirmed on auth.meta.com — aborting before Instagram to prevent phone wall")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "meta_verified",
                    "detail": f"Meta account created ({runner.email})."})

        # -- Step 2: TG task FIRST (before IG) ------------------------------
        if _stopped():
            raise RuntimeError("stopped")
        # Validate against the BOT REGISTRY, not a hardcoded tuple — the old
        # `in ("taskly", "paygo")` silently downgraded fastpay to taskly, so a
        # FastPay run leased a taskly profile and then refused "Instagram 2FA".
        _known_bots = tuple(TG_BOTS.keys())
        pinned = tg_bot if tg_bot in _known_bots else None
        target_task = tg_task or TG_DEFAULT_TASK
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "waiting",
                    "detail": "Acquiring Telegram bot slot…"})
        # Stop-aware lease wait: short acquires so Stop lands in seconds.
        # One explicit bot per run — no taskly/paygo alternation.
        #
        # Dead-session guard: a "leasable" profile can still hold a dead
        # stel_web_auth cookie (server-side logout, or the legacy has_session
        # heuristic masking a missing DB). Committing to it would fail only
        # AFTER step 1 burned a Meta account. So on a session-lost boot
        # failure we dynamically DISABLE that profile and lease the next one —
        # the task keeps running on the remaining logged-in accounts. Bounded
        # so a pool of dead profiles cannot loop forever (a dry acquire() ends
        # it too).
        _dead_profiles = []
        _max_leases = max(1, TG_MAX_PARALLEL + 2)
        while not _stopped():
            tg_acct = tg_manager.acquire(timeout=15, bot=(pinned or _known_bots[0]))
            if not tg_acct:
                break
            # One explicit bot per run — the old taskly/paygo 50-50 alternation
            # for "both" was removed; an unset/legacy value falls back to the
            # first registered bot.
            bot_choice = pinned or _known_bots[0]
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "bot_boot",
                        "detail": f"Leased {tg_acct['id']} ({bot_choice}) — starting TG task…"})
            # Bind the current id/bot into the log closure (the loop rebinds
            # tg_acct on the next iteration).
            log = (lambda m, _id=tg_acct["id"], _b=bot_choice:
                   print(f"[tg:{_id}:{_b}] {m}", flush=True))
            bot = _make_tg_bot(tg_acct, bot_choice, is_headless, log)
            bot_ok, bot_msg = _boot_bot(bot)
            if bot_ok:
                break
            if not _is_tg_session_lost(bot_msg):
                raise RuntimeError(bot_msg)
            # Session lost → disable this profile and continue with another.
            log(f"[🔄] Telegram session lost on {tg_acct['id']} — disabling it and "
                f"continuing with the next available profile.")
            _dead_profiles.append(tg_acct["id"])
            try:
                tg_manager.disable(tg_acct["id"],
                                   reason="dead Telegram session (boot check)")
            except Exception as d_exc:
                log(f"[⚠️] disable {tg_acct['id']}: {d_exc}")
            emit_event({"type": "log", "slot_id": slot_id,
                        "message": f"[tg] {tg_acct['id']} logged out — disabled, "
                                   "switching to another Telegram profile."})
            # Free the dead profile's warm browser + lock before moving on.
            try:
                bot.close(ok=False)
            except Exception:
                pass
            _drop_tg_bot(tg_acct)
            bot = None
            tg_acct = None
            if len(_dead_profiles) >= _max_leases:
                break
        if not tg_acct:
            if _dead_profiles:
                raise RuntimeError(
                    "All leasable Telegram profiles are logged out "
                    f"(disabled: {', '.join(_dead_profiles)}) — log in via "
                    "Dashboard → Telegram Accounts.")
            raise RuntimeError("stopped" if _stopped() else "No Telegram profile slot available")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "bot_task",
                    "detail": f"{tg_acct['id']}: Starting {target_task} on {bot.bot_name}…"})
        # Lease heartbeat: long IG phases (2FA grind, scraping-warning
        # recovery) hold no pool traffic for tens of minutes. Without this,
        # LEASE_TTL (20 min) reclaims the busy record and a second slot
        # leases the SAME profile — two cycles then interleave commands on
        # one pool owner and steal each other's replies.
        _lease_stop = threading.Event()
        _lease_id = tg_acct["id"]
        def _beat(_stop=_lease_stop, _lid=_lease_id):
            while not _stop.wait(300):
                try:
                    tg_manager.heartbeat(_lid)
                except Exception:
                    break
        threading.Thread(target=_beat, daemon=True).start()
        # Claim a task. If the bot returns unusable CREDENTIALS (bad login /
        # missing password), cancel and re-request a fresh task IN-SESSION (the
        # Meta/IG browser stays OPEN) up to 3 times — operator decision
        # 2026-09-21. The NAME is never fatal: junk / too-long names get a random
        # substitute so the task proceeds.
        creds = None
        login_try = raw_name = None
        for _try in range(3):
            if not bot.choose_task(target_task):
                _v = getattr(bot, "last_task_verdict", None) or "hidden"
                raise RuntimeError(f"Could not select task '{target_task}' in {bot.bot_name} [task_unavailable:{_v}]")
            creds = bot.start_task() or {}
            login_try = _clean_username(creds.get("login") or "")
            raw_name = creds.get("first_name") or ""
            if login_try and _is_valid_ig_username(login_try) and creds.get("password"):
                break
            log(f"[🔁] {bot.bot_name} returned unusable credentials (try {_try + 1}/3) — re-requesting…")
            try:
                bot.cancel_task()
            except Exception:
                pass
            creds = None
        if not creds:
            raise RuntimeError(f"{bot.bot_name} returned no usable credentials after 3 tries")
        if _is_junk_name(raw_name) or _ig_name_too_long(_sanitize_name(raw_name)):
            log(f"[📝] Bot name unusable ({raw_name!r}) — using random display name.")
            raw_name = _random_display_name()
            creds["first_name"] = raw_name
        creds["login"] = login_try

        clean_name = _sanitize_name(creds.get("first_name") or "")
        log(f"TG task credentials: name='{creds.get('first_name')}' (clean='{clean_name}'), login='{creds['login']}'")
        # Bot TTL anchor: the ~8-min auto-cancel counts from task Start (now),
        # not from Step 4 — onboarding alone eats 2-4 min of it.
        _task_t0 = time.monotonic()
        try:
            _task_unavailable_strikes.pop(tg_acct["id"], None)
        except Exception:
            pass
        log("[⏳] Bot task TTL is ~8 min (observed 'Time's up! Task cancelled') — "
            "IG onboarding + password + 2FA + register must finish inside it.")
        runner.tg_creds = creds
        runner.new_username = creds["login"]
        runner.new_password = creds["password"]
        if clean_name:
            runner.name = clean_name
        runner.tg_id = tg_acct["id"]
        runner.tg_bot = bot_choice
        # Which steps THIS task runs. Data-driven via tg_flows.resolve_steps
        # (a task's own `steps`/`skip` beat the flow's list). Default = the full
        # "2fa" flow, so existing tasks behave exactly as before; opting a task
        # out of `password`/`extra_email` is a registry edit, not a code change.
        _flow_steps = _resolve_steps(getattr(bot, "bot_target", "taskly"), target_task)
        runner.log(f"[steps] {getattr(bot, 'bot_target', '?')} · {target_task} → {_flow_steps}")

        # Username-only swap: "X is not available" mid-join cancels the TG
        # task, starts a fresh one, and swaps JUST the username (name stays;
        # nothing closes, process continues). Max 3, then the wizard's own
        # suggestion fallback takes over.
        _swaps = {"n": 0}

        def _swap_tg_username(reason, bad_login):
            nonlocal _task_t0
            if _swaps["n"] >= 8:
                log(f'Login "{bad_login}" rejected ({reason}); swap budget spent (8 attempts).')
                return None
            _swaps["n"] += 1
            log(f'[🔁] Login "{bad_login}" rejected ({reason}); cancelling active TG task and getting fresh replacement task (swap {_swaps["n"]}/8)…')
            try:
                bot.cancel_task()
            except Exception as exc:
                log(f"[⚠️] cancel_task: {exc}")
            time.sleep(1.0)
            try:
                if not bot.choose_task(target_task):
                    return None
                fresh = bot.start_task()
            except Exception as exc:
                log(f"[⚠️] replacement task failed: {exc}")
                return None
            if not (fresh and fresh.get("login") and fresh.get("password")):
                return None
            fresh["login"] = _clean_username(fresh["login"])
            if not _is_valid_ig_username(fresh["login"]):
                return None
            # Update credentials for subsequent flow (ignoring first_name, keeping existing profile name)
            runner.tg_creds = fresh
            runner.new_username = fresh["login"]
            runner.new_password = fresh.get("password") or runner.new_password
            _task_t0 = time.monotonic()  # Reset task TTL window with the fresh task
            log(f"[🔁] Replacement TG task acquired: login='{fresh['login']}' (ignoring first_name '{fresh.get('first_name')}', original name '{runner.name}' kept).")
            return fresh["login"]

        runner._on_username_taken = _swap_tg_username
        runner._on_credentials_rejected = _swap_tg_username

        # -- Task-window gate (shared by classic + emu paths) ------------------
        # The bot auto-cancels ~8 min after Start. Past ~7 min every downstream
        # submit fails on a dead task while burning more minutes (observed
        # 2026-09-19: 10-min challenge grind + doomed 2FA). Fail fast at phase
        # boundaries instead. Anchor _task_t0 is set at task Start (Step 2).
        _TASK_WINDOW = 420

        def _window_left() -> float:
            return _TASK_WINDOW - (time.monotonic() - _task_t0)

        def _require_window(phase: str) -> None:
            left = _window_left()
            log(f"[⏱️] Task window: {phase} — {max(0, int(left))}s left of ~{_TASK_WINDOW}s")
            if left <= 0:
                raise RuntimeError(f"Bot task window exceeded before {phase} (~7 min elapsed)")

        # -- Step 3: IG in the SAME session, click-by-click ------------------
        if _stopped():
            raise RuntimeError("stopped")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                    "detail": f"IG onboarding with bot user ({creds['login']})…"})
        runner.ig_login()
        runner.ig_click_meta_card()
        runner.ig_complete_join()
        if runner.ig_username:
            runner.new_username = runner.ig_username
        runner.ig_dismiss_onboarding()   # Back-out of the /accounts/registered
        # cards (never Skip) + follows ~2 suggested profiles on the feed — the
        # warm-up that replaced the old feed-SCROLL settle (a brand-new account
        # driven straight into settings/AC is IG's strongest velocity signal;
        # observed 2026-09-21: AC bounced to /accounts/login/?__coig_login=1).
        # Env: INSTA_FOLLOW_AFTER_LOGIN=0, INSTA_FOLLOW_COUNT. No scrolling.
        ig_page = runner._ig_tab()
        if runner._has_human_check(ig_page):
            runner.log('[🛡️] Instagram human checkpoint detected — dead end; exiting immediately.')
            raise IGDeadEnd(
                "Instagram: human checkpoint ('Confirm you're human to use your "
                "profile') on a fresh account — dead end; closing and starting a "
                "new task")

        # -- Step 4: IG-side completion (classic path; window gate above) -----
        # The pre-AC human warm-up (exit the registered cards with Back, then
        # follow ~2 suggested profiles) already happened inside
        # ig_dismiss_onboarding above — deliberately NOT repeated here
        # (invariant #20). Accounts Center is next.

        # Email linkage. When the extra-email step is ON we DEFER this to after
        # 2FA + password (a fresh mail.td email is added there) — doing it here
        # too would navigate Accounts Center twice for the same purpose. When
        # OFF, the signup email is linked here; ig_link_email_to_instagram
        # solves its own email re-auth via _ac_reauth.
        #
        # Operator rule: this is the LAST stop and never kills the task — a
        # link failure logs loudly and the account still submits (both bots
        # have accepted email-less reports live).
        # -- Flow Steps Execution (Order strictly dictated by _flow_steps) ---
        def _step_password():
            target_pw = (runner.tg_creds or {}).get("password") or runner.new_password
            if target_pw and target_pw != runner.password:
                _require_window("password change")
                log("[🔑] Changing account password to the TG task password (authenticated via signup email)…")
                runner.log("[🔑] Changing account password to the TG task password (authenticated via signup email)…")
                if not runner.ig_set_password(target_pw, current_password=runner.password):
                    _why = getattr(runner, "_pw_fail_reason", None) or "unknown"
                    log(f"[🔑] password change failed (reason={_why}) — not submitting")
                    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                                "detail": f"Password change failed (reason={_why})"})
                    raise RuntimeError(
                        f"Password change to the TG task password failed (reason={_why}) — "
                        "refusing to submit the account with the wrong password "
                        "(Taskly/FastPay expects the bot password)")
                runner.password = target_pw

        def _step_email_link():
            bot_em = (runner.tg_creds or {}).get("email")
            _require_window("email link")
            if bot_em:
                runner.log(f"[✉️] Bot-issued email {bot_em} present — linking via bot code fetcher (📥 Get code)…")
                try:
                    linked = runner.ig_link_email_to_instagram(
                        bot_em,
                        code_fetcher=lambda: bot.request_email_code(timeout=45),
                    )
                except IGDeadEnd as exc:
                    log(f"[⚠️] Bot email rejected ({exc}) — proceeding to 2FA anyway.")
                    linked = False
                except Exception as exc:
                    linked = False
                    log(f"[⚠️] Bot email linkage error ({exc}) — continuing.")
                runner.log(f"[✉️] Bot email linkage result: {linked}")
            elif add_email:
                runner.log("[✉️] Extra-email requested (no bot email) — deferring email link to extra_email.")
            else:
                try:
                    linked = runner.ig_link_email_to_instagram(runner.email)
                except IGDeadEnd as exc:
                    log(f"[⚠️] Email rejected ({exc}) — proceeding to 2FA anyway.")
                    linked = False
                except Exception as exc:
                    linked = False
                    log(f"[⚠️] Email linkage error ({exc}) — submitting anyway (email never rejects).")
                if not linked:
                    log("[⚠️] Signup email unconfirmed — submitting anyway (email never rejects).")
                else:
                    runner.log("[✉️] Signup email linked.")

        def _step_2fa():
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": "Instagram 2FA setup + TG submit…"})
            _require_window("2FA submit")
            secret = runner.ig_2fa_begin()
            if not secret:
                raise RuntimeError("Could not retrieve 2FA secret key from Instagram")
            code = bot.submit_2fa_key(secret, allow_local_fallback=True)
            if not code:
                raise RuntimeError(f"{bot.bot_name} did not return OTP code for 2FA key")
            runner.tg_code = code
            log(f"Received OTP from {bot.bot_name}; confirming on IG…")
            if not runner.ig_2fa_confirm(code):
                raise RuntimeError("Instagram rejected the 2FA code")

        def _step_extra_email():
            bot_em = (runner.tg_creds or {}).get("email")
            if add_email and not bot_em:
                _require_window("extra email")
                email_ok = False
                log("[✉️] Extra-email step enabled — minting a fresh mail.td address…")
                new_em = None
                try:
                    new_em = runner.new_mailtd_address()
                except Exception as exc:  # noqa: BLE001
                    log(f"[⚠️] Extra-email: could not mint address: {exc}")
                if not new_em:
                    log("[⚠️] Extra-email: no mail.td address minted — continuing (best-effort).")
                else:
                    log(f"[✉️] Adding extra email {new_em} to Instagram (Accounts Center)…")
                    try:
                        email_ok = runner.ig_link_email_to_instagram(new_em)
                    except IGDeadEnd as exc:
                        log(f"[⚠️] Extra-email rejected ({exc}) — continuing.")
                        email_ok = False
                    except Exception as exc:  # noqa: BLE001
                        log(f"[⚠️] Extra-email step failed ({exc}) — continuing (best-effort).")
                        email_ok = False
                    log(f"[✉️] Extra-email result: {email_ok}")
                if not email_ok:
                    log("[✉️] Extra email unavailable — falling back to the signup email…")
                    fb = False
                    try:
                        fb = runner.ig_link_email_to_instagram(runner.email)
                    except IGDeadEnd as exc:
                        log(f"[⚠️] Fallback email rejected ({exc}) — continuing.")
                        fb = False
                    except Exception as exc:  # noqa: BLE001
                        log(f"[⚠️] Email fallback failed ({exc}).")
                    if fb:
                        log("[✓] Signup email linked as fallback — continuing.")
                    else:
                        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                                    "detail": "No email confirmed — submitting anyway (best-effort)"})
                        log("[⚠️] No email confirmed — submitting anyway (extra-email is best-effort).")

        step_dispatch = {
            "password": _step_password,
            "email_link": _step_email_link,
            "2fa": _step_2fa,
            "extra_email": _step_extra_email,
        }
        for st in _flow_steps:
            if st in step_dispatch:
                step_dispatch[st]()
            elif st != "register":
                runner.log(f"[{st}] step unknown or skipped.")

        # Submit/report is the point of the whole task — never record a
        # Submitted account unless the register key was actually tapped and
        # the bot confirmed. mark_registered() refuses to press Cancel and
        # returns False when it cannot find the key; the old code ignored that
        # and set ok=True anyway, producing a FALSE Submitted.
        _require_window("register confirm")
        runner.tg_submitted = bot.mark_registered()
        if not runner.tg_submitted:
            # Receipt/keyboard can lag a beat — one bounded re-scan (still
            # never Cancel), then fail loud instead of faking success.
            log("[⚠️] Registration receipt not seen — one more register tap…")
            runner.tg_submitted = bot.mark_registered()
        if not runner.tg_submitted:
            raise RuntimeError(
                f"{bot.bot_name} registration not confirmed (register key/receipt) — "
                "not recording Submitted")
        ok = True

        from tg_stats import record_submission
        rec_id = f"tg_{int(time.time()*1000)}"
        record_submission(bot_choice or "taskly")
        runner.last_record_id = rec_id
        emit_event({"type": "account_submitted", "pipeline": "telegram",
                    "tg_account": tg_acct["id"], "tg_bot": bot_choice or "taskly",
                    "account_id": rec_id})
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "submitted",
                    "detail": f"TG task completed ({rec_id})."})
        return True, rec_id

    except _DEAD_ENDS as exc:
        # Dead end (bare saved-account chooser / IG session lost, browser or
        # emulator / email already in use): the account is not salvageable.
        # Cancel the active TG task, close out and move to the next one.
        dead_end = True
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                    "detail": f"Dead end: {exc}"})
        if bot is not None and tg_acct is not None:
            try:
                bot.cancel_task()
            except Exception:
                pass
        return False, str(exc)

    except Exception as exc:
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                    "detail": f"Error: {exc}"})
        if strict:
            # STRICT: the IG/Meta browser is never touched (left open for
            # manual inspection), but the TG side MUST be left clean:
            # - a wedged bot thread ("hung on") poisons every later lease of
            #   the same profile (proven 2026-09-19: 3 cycles hung in a row)
            #   → reap its browser + drop the pool owner.
            # - an IG-side failure with a responsive bot leaves an orphan
            #   ACTIVE task whose TTL expiry scrambles the next attempt's
            #   menu → best-effort cancel (capped 60s), IG tabs untouched.
            # - "Could not select task" on the SAME profile twice in a row
            #   means the account persistently offers no task (tg_2 2026-09-19:
            #   YES/NO gate, zero task rows). Burning a fresh Meta per retry
            #   is futile → stop-aware 5-min cooldown before the next cycle.
            wedged = "hung on" in str(exc)
            no_task = "could not select task" in str(exc).lower()
            if bot is not None and tg_acct is not None:
                prof_dir = tg_acct.get("profile_dir")
                prof_id = tg_acct.get("id")
                if no_task and prof_id:
                    n = _task_unavailable_strikes.get(prof_id, 0) + 1
                    _task_unavailable_strikes[prof_id] = n
                    log(f"[tg] No task offered on {prof_id} ({n} in a row).")
                    if n >= 2:
                        log("[tg] Cooling down 5 min (task stock/flag may refresh)…")
                        for _ in range(300):
                            if _stopped():
                                break
                            time.sleep(1)
                if wedged and prof_dir:
                    log(f"[tg] Bot thread wedged ({exc}) — reaping profile browser…")
                    try:
                        _reap_wedged_tg_browser(prof_dir, log=log)
                    except Exception as re_exc:
                        log(f"[tg] reap note: {re_exc}")
                elif prof_dir:
                    try:
                        if _cancel_with_timeout(bot, log):
                            log("[tg] Orphan TG task cancelled (bot chat clean for next lease).")
                        else:
                            log("[tg] Cancel timed out — reaping profile browser…")
                            _reap_wedged_tg_browser(prof_dir, log=log)
                    except Exception as c_exc:
                        log(f"[tg] cancel note: {c_exc}")
            try:
                _pages = ", ".join(
                    (p.url or "")[:60] for p in (runner.w.context.pages
                                                 if runner is not None and getattr(runner, "w", None)
                                                 and getattr(runner.w, "context", None) else []))
            except Exception:
                _pages = "?"
            _bstate = ("browser LEFT OPEN" if _inspector_keeps(is_headless)
                       else "browser closing")
            log(f"[🛑] STRICT stop at: {exc} | {_bstate} "
                f"(profile {getattr(getattr(runner, 'w', None), 'user_data_dir', '?')}) | tabs: {_pages}")
        else:
            if bot is not None and tg_acct is not None:
                try:
                    bot.cancel_task()
                except Exception:
                    pass
        return False, str(exc)

    finally:
        try:
            if _lease_stop is not None:
                _lease_stop.set()
        except Exception:
            pass
        if tg_acct:
            try:
                tg_manager.release(tg_acct["id"], ok=ok, account_id=rec_id)
            except Exception:
                pass
        if ok:
            # Only a Submitted task cleans up. Anything else stays open.
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
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "closed",
                        "detail": "Browser closed."})
            # Submitted => the artifacts (profile dir, session file, cookie
            # export) are never needed again. Free them now; the ledger record
            # is kept. Bounds disk on unlimited runs (INSPECT_BROWSER_CAP-style
            # growth guard for the disk).
            try:
                import store as _store
                if rec_id:
                    _store.prune_submitted_data([rec_id])
            except Exception:
                pass
        elif dead_end:
            # Dead end: the browser was already closed by the caller's finish()
            # or is closed here; report it clearly and let the slot retry.
            if runner is not None:
                try:
                    runner.finish()
                except Exception:
                    pass
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "closed",
                        "detail": "Dead end — browser closed, moving to next account."})
        elif strict:
            # Headed retention is OPT-IN (INSPECT_KEEP_VISIBLE=1); otherwise the
            # browser is force-closed like headless. Report the TRUE outcome so
            # the dashboard never claims a closed browser is "held open".
            _kept = _register_inspector(runner, log, headless=is_headless)
            if _kept:
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "held_open",
                            "detail": "Browser left open for inspection (INSPECT_KEEP_VISIBLE=1)."})
            else:
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "closed",
                            "detail": "Strict failure — browser closed."})
