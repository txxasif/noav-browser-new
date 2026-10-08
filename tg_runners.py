#!/usr/bin/env python3
"""tg_runners.py — data-driven RUNNER REGISTRY for worker.py's coupled loop.

The coupled loop resolves a runner NAME from the task/flow registries
(``tg_tasks.flow_of`` → ``tg_flows.runner_of``) and then has to dispatch to the
matching ``run_*_once`` entry point. Previously that dispatch was a hard-coded
``elif str(_runner) == "run_XXX"`` chain inside ``worker.py``. Adding a runner
meant editing worker.py. This module turns the dispatch into DATA: one entry in
``RUNNERS`` per runner name.

Every entry:

* takes the SAME normalized keyword signature (see below) — the caller passes
  the whole bag, each entry forwards only the fields its runner accepts;
* performs its lazy import INSIDE the callable (``run_cookie_cycle`` etc.
  lazily import ``AISlotWorker`` back, so a top-level import here would be
  circular);
* returns the runner's ``(ok, detail)`` tuple unchanged.

Normalized signature (identical for every entry)::

    def run_<name>(slot_id, worker_factory, is_headless, captcha_mode,
                   mail_provider, stop_event, add_email, tg_task, tg_bot,
                   use_ig_pool, cookie_2fa, cookie=False, fallback=False) -> tuple

This is a PURE refactor: every call below replicates the exact kwargs the old
worker.py branch passed (note the pool runners hard-code ``use_ig_pool=True``,
exactly as today).
"""
from __future__ import annotations

# Runner name used when the flow registry yields no/unknown runner — the
# TG Classic coupled cycle (the old ``else`` branch).
DEFAULT_RUNNER = "tg_coupled"


def _cookie(slot_id, worker_factory, is_headless, captcha_mode, mail_provider,
            stop_event, add_email, tg_task, tg_bot, use_ig_pool, cookie_2fa,
            cookie=False, fallback=False):
    """Cookie-family task (PayGo cookie, Taskly cookie_2fa).

    Meta -> TG creds -> [2FA] -> IG join + follow -> cookie export -> cookie
    submit. Lazy import: run_cookie_cycle lazily imports AISlotWorker back, so a
    top-level import here would be circular.
    """
    from run_cookie_cycle import run_cookie_cycle_once
    return run_cookie_cycle_once(
        slot_id=slot_id, worker_factory=worker_factory,
        is_headless=is_headless, captcha_mode=captcha_mode,
        mail_provider=mail_provider, stop_event=stop_event,
        add_email=add_email, tg_task=tg_task, tg_bot=tg_bot,
        use_ig_pool=use_ig_pool, cookie_2fa=cookie_2fa, fallback=fallback)


def _native(slot_id, worker_factory, is_headless, captcha_mode, mail_provider,
            stop_event, add_email, tg_task, tg_bot, use_ig_pool, cookie_2fa,
            cookie=False, fallback=False):
    """Taskly 2FA native task: NO Meta, NO mailbox — lease TG, Start, bot
    email+code, IG native signup, Account Registered. Lazy import for the same
    circularity reason as above.
    """
    from run_native_cycle import run_native_cycle_once
    return run_native_cycle_once(
        slot_id=slot_id, worker_factory=worker_factory,
        is_headless=is_headless, captcha_mode=captcha_mode,
        mail_provider=mail_provider, stop_event=stop_event,
        add_email=add_email, tg_task=tg_task, tg_bot=tg_bot)


def _pool_2fa(slot_id, worker_factory, is_headless, captcha_mode, mail_provider,
              stop_event, add_email, tg_task, tg_bot, use_ig_pool, cookie_2fa,
              cookie=False, fallback=False):
    """Taskly "📱 Create Inst (2FA)" POOL DRAIN (new "Taskly 2FA" panel): reuse
    a pre-created IG account from the pool — rename via Web API + 2FA from the
    stored inbox — no Meta, no signup.
    """
    from run_pool_2fa_cycle import run_pool_2fa_cycle_once
    return run_pool_2fa_cycle_once(
        slot_id=slot_id, worker_factory=worker_factory,
        is_headless=is_headless, captcha_mode=captcha_mode,
        mail_provider=mail_provider, stop_event=stop_event,
        add_email=add_email, tg_task=tg_task, tg_bot=tg_bot,
        use_ig_pool=True)


def _fastpay_pool(slot_id, worker_factory, is_headless, captcha_mode,
                  mail_provider, stop_event, add_email, tg_task, tg_bot,
                  use_ig_pool, cookie_2fa, cookie=False, fallback=False):
    """FastPay "Instagram 2FA" POOL DRAIN (new "FastPay 2FA" panel): reuse a
    pre-created IG account — rename + 2FA + password + Confirm in FastPay — no
    Meta, no signup.
    """
    from run_fastpay_pool_cycle import run_fastpay_pool_cycle_once
    return run_fastpay_pool_cycle_once(
        slot_id=slot_id, worker_factory=worker_factory,
        is_headless=is_headless, captcha_mode=captcha_mode,
        mail_provider=mail_provider, stop_event=stop_event,
        add_email=add_email, tg_task=tg_task, tg_bot=tg_bot,
        use_ig_pool=True)


def _paygo_pool_2fa(slot_id, worker_factory, is_headless, captcha_mode,
                    mail_provider, stop_event, add_email, tg_task, tg_bot,
                    use_ig_pool, cookie_2fa, cookie=False, fallback=False):
    """PayGo "📱 Create Inst (2FA)" POOL DRAIN (new "PayGo 2FA" panel): same-to-
    same as the Taskly pool drain — reuse a pre-created IG account (rename via
    Web API + bot email link via 📥 Get code + 2FA from the stored inbox +
    register).
    """
    from run_paygo_pool_2fa_cycle import run_paygo_pool_2fa_cycle_once
    return run_paygo_pool_2fa_cycle_once(
        slot_id=slot_id, worker_factory=worker_factory,
        is_headless=is_headless, captcha_mode=captcha_mode,
        mail_provider=mail_provider, stop_event=stop_event,
        add_email=add_email, tg_task=tg_task, tg_bot=tg_bot,
        use_ig_pool=True)


def _tg_coupled(slot_id, worker_factory, is_headless, captcha_mode,
                mail_provider, stop_event, add_email, tg_task, tg_bot,
                use_ig_pool, cookie_2fa, cookie=False, fallback=False):
    """TG Classic coupled cycle (Meta -> IG -> bot submit). Imported lazily:
    pipelines/ is excluded from non-TG builds. The ImportError message is part
    of the shipped behaviour (the dashboard surfaces it verbatim).
    """
    try:
        from pipelines.telegram import tg_worker
    except ImportError:
        raise RuntimeError("TG Classic is not included in this build (pipelines/telegram missing).")
    return tg_worker.run_tg_coupled_cycle(
        worker_factory, slot_id=slot_id, is_headless=is_headless,
        tg_task=tg_task, tg_bot=tg_bot,
        captcha_mode=captcha_mode, mail_provider=mail_provider,
        add_email=add_email,
        stop_event=stop_event)


# Runner name (as returned by tg_flows.runner_of) -> callable.
RUNNERS = {
    "run_cookie_cycle": _cookie,
    "run_native_cycle": _native,
    "run_pool_2fa_cycle": _pool_2fa,
    "run_fastpay_pool_cycle": _fastpay_pool,
    "run_paygo_pool_2fa_cycle": _paygo_pool_2fa,
    DEFAULT_RUNNER: _tg_coupled,
}


def _fleet_stopped(stop_event) -> bool:
    try:
        return bool(stop_event and stop_event.is_set())
    except Exception:
        return False


def _fleet_pool_empty(detail: str) -> bool:
    """Shared-IG-pool exhaustion: every candidate drinks from the same pool,
    so stop the chain at once and let the worker park dynamically."""
    e = str(detail or "").lower()
    return ("no_pool_accounts" in e or "no available ig creator accounts" in e
            or "pool empty" in e)


def run_fleet_chain(slot_id, worker_factory, is_headless, captcha_mode,
                    mail_provider, stop_event, add_email, cookie_2fa,
                    fleet=None):
    """Run an ORDERED Fleet chain: [(bot, task, pool)] tried in order.

    Each candidate runs its own registry runner as a FULL cycle attempt (each
    runner leases/releases TG itself and restores the pool account on failure,
    so attempts are independent). First success wins; a shared-pool exhaustion
    aborts the chain at once (the worker parks dynamically); anything else
    moves to the next candidate. All candidates fail -> last detail (the
    worker retries; nothing stops automatically).
    """
    print(f"[fleet:{slot_id}] chain: " + " → ".join(
        f"{c.get('bot')}/{c.get('task')}" for c in (fleet or [])), flush=True)
    import tg_tasks as _tt
    from tg_flows import runner_of as _runner_of

    seq = []
    for c in (fleet or [])[:8]:
        if not isinstance(c, dict):
            continue
        b = str(c.get("bot") or "").strip().lower()
        t = str(c.get("task") or "")
        pool = bool(c.get("pool", True))
        if not b or not t:
            continue
        try:
            tid, _reason = _tt.resolve(b, t)
        except Exception:
            tid = None
        if not tid:
            print(f"[fleet:{slot_id}] skipping unresolvable {b}/{t} — moving on.", flush=True)
            continue
        flow = _tt.flow_of(b, tid)
        rname = _runner_of(flow) if flow else ""
        fn = get_runner(rname or DEFAULT_RUNNER)
        seq.append((b, t, pool, rname, fn, bool(c.get("c2fa", True))))
    if not seq:
        return False, "empty fleet chain (nothing resolvable) [task_unavailable:unoffered]"
    last = (False, "fleet chain exhausted")
    for _i, (b, t, pool, rname, fn, c2fa_entry) in enumerate(seq):
        if _fleet_stopped(stop_event):
            return False, "stopped"
        print(f"[fleet:{slot_id}] {_i + 1}/{len(seq)} trying {b} / {t}…", flush=True)
        try:
            # Per-entry 2FA+Cookie switch (Fleet run order); falls back to the
            # run-wide flag when the entry carries none.
            _c2fa = bool((c2fa_entry if c2fa_entry is not None else cookie_2fa) and pool)
            ok, detail = fn(
                slot_id=slot_id, worker_factory=worker_factory,
                is_headless=is_headless, captcha_mode=captcha_mode,
                mail_provider=mail_provider, stop_event=stop_event,
                add_email=add_email, tg_task=t, tg_bot=b,
                use_ig_pool=pool, cookie_2fa=_c2fa,
                cookie=(rname == "run_cookie_cycle"))
        except Exception as exc:
            ok, detail = False, str(exc)
        if ok:
            return True, detail
        d = str(detail or "")
        if _fleet_pool_empty(d):
            return False, d
        print(f"[fleet:{slot_id}] {b} unavailable ({d[:110]}) — next…", flush=True)
        last = (False, d)
    return last


def get_runner(name):
    """Return the runner callable for ``name``.

    Unknown/empty names fall back to the default (TG Classic coupled) runner —
    this preserves the old ``else`` branch's behaviour for a flow the registry
    does not know.
    """
    return RUNNERS.get(str(name or ""), RUNNERS[DEFAULT_RUNNER])
