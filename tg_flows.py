"""tg_flows.py — per-flow step pipelines (single source of truth).

A **task** (``tg_tasks.py``) declares which **flow** it uses (``"2fa"``,
``"cookie"``, ``"cookie_2fa"`` or ``"native"``). A **flow** declares the ordered **steps** its runner executes
*after* the shared preamble. The runner walks ``steps_of(flow)`` and calls the
matching step callable — so adding a flow or a step happens in ONE place and
the existing flows are untouched.

Shared preamble (every flow, implemented by each runner):
    Meta create -> lease TG profile -> choose task -> Start -> creds.

Add a new flow:
    1. add an entry to ``FLOWS`` with its ``runner`` + ordered ``steps``;
    2. implement the new step callable(s) in that runner;
    3. map the task to the flow in ``tg_tasks.TASKS[...]["flow"]``.
Nothing else changes.
"""
from __future__ import annotations

FLOWS = {
    # PayGo "📱 Create Inst (Cookies)" — verifies via the exported IG cookie.
    # NO email link (a cookie task does not need a confirmed email) and NO
    # 2FA/password (the cookie IS the credential the bot checks).
    "cookie": {
        "label": "Create Inst (Cookies) — cookie export + submit",
        "runner": "run_cookie_cycle",
        "steps": ["ig_join", "cookie_export", "submit_cookie"],
        "needs_email": False,
        "needs_2fa": False,
    },
    # Taskly "🍪 Cookies → 🍪 Create Inst (No mail)" — 2FA FIRST, then cookie.
    # Verified live 2026-09-28: Start sends First name/Login/Password, then
    # "🔑 Please enter your 2FA key to get the code:"; after the key round-trip
    # the bot asks for the account Cookie. Shares the cookie runner.
    "cookie_2fa": {
        "label": "Create Inst (Cookies) + 2FA — 2FA then cookie",
        "runner": "run_cookie_cycle",
        "steps": ["ig_join", "2fa", "cookie_export", "submit_cookie"],
        "needs_email": False,
        "needs_2fa": True,
    },
    # Taskly "📱 Create Inst (2FA)" — NATIVE signup (learned live 2026-09-28).    # The bot issues First name/Login/Password/Email (Email ordered async
    # after Start) plus the email code via its Get-code key. IG NATIVE email
    # signup with the bot data — NO Meta account, NO temp mail — then the
    # "Account Registered" key. Shares nothing with the "2fa" (Meta-coupled)
    # flow; its own runner below.
    "native": {
        "label": "Create Inst (2FA) — native signup with bot email+code",
        "runner": "run_native_cycle",
        "steps": ["ig_signup", "2fa", "register"],
        "needs_email": False,
        "needs_2fa": True,
    },
    # Taskly "📱 Create Inst (2FA)" run as a POOL DRAIN (no Meta, no signup):
    # reuse a pre-created IG account from the IG Creator pool — rename it to the
    # bot login via the direct Web API, enable 2FA from the account's STORED
    # mail.td inbox (`extra.mail_tokens`), submit the key to Taskly, confirm the
    # code, register, then consume (delete) the account. Own runner.
    "pool_2fa": {
        "label": "Create Inst (2FA) — pooled account drain (no Meta)",
        "runner": "run_pool_2fa_cycle",
        "steps": ["ig_rename", "password", "email_link", "2fa", "register"],
        "needs_email": True,
        "needs_2fa": True,
    },
    # PayGo "📱 Create Inst (2FA)" run as a POOL DRAIN (no Meta, no signup):
    # same-to-same as Taskly's pool_2fa — reuse a pre-created IG account from
    # the IG Creator pool: rename to the bot login via the direct Web API,
    # link the bot-issued email (📥 Get code), enable 2FA from the account's
    # STORED mail.td inbox, register, then consume. Own runner so the Taskly
    # drain, the PayGo cookie drain and their counters stay untouched
    # (invariant 24).
    "paygo_pool_2fa": {
        "label": "Create Inst (2FA) — PayGo pooled account drain (no Meta)",
        "runner": "run_paygo_pool_2fa_cycle",
        "steps": ["ig_rename", "password", "email_link", "2fa", "register"],
        "needs_email": True,
        "needs_2fa": True,
    },
    # PayGo "PayGo 2FA Optimized" panel — EXPERIMENTAL variant of
    # paygo_pool_2fa with the email_link step dropped (runner
    # run_paygo_pool_2fa_opt_cycle skips it: PayGo accepted registration
    # with linkage False, while the step burns ~60s). Additive only — the
    # original paygo_pool_2fa flow is untouched.
    "paygo_pool_2fa_opt": {
        "label": "Create Inst (2FA) — PayGo OPTIMIZED pooled drain (no email link)",
        "runner": "run_paygo_pool_2fa_opt_cycle",
        "steps": ["ig_rename", "password", "2fa", "register"],
        "needs_email": False,
        "needs_2fa": True,
    },
    # FastPay2025_bot "Instagram 2FA" run as a POOL DRAIN (no Meta, no signup):
    # reuse a pre-created IG account — rename to the bot login, capture the 2FA
    # key -> submit to FastPay -> enter the returned CODE on IG, set the IG
    # password to the bot password, then Confirm in FastPay. Own runner.
    "fastpay_pool_2fa": {
        "label": "Instagram 2FA — FastPay pooled account drain (no Meta)",
        "runner": "run_fastpay_pool_cycle",
        "steps": ["ig_rename", "2fa", "password", "register"],
        "needs_email": False,
        "needs_2fa": True,
    },
    # Taskly "🔥 Create Inst (No mail)" (Meta-coupled; the 2FA task moved to
    # the "native" flow above).
    "2fa": {
        "label": "Create Inst (No mail) — password + email + 2FA + register",
        "runner": "tg_coupled",
        "steps": ["password", "email_link", "2fa", "extra_email", "register"],
        "needs_email": True,
        "needs_2fa": True,
    },
    # FastPay2025_bot "Instagram 2FA" — a CREATE task like Taskly's 2FA, but the
    # 2FA key is submitted to FastPay (→ 2FA Code → Confirm → ৳3.0). It shares
    # the "2fa" flow: Meta → IG (bot Username) → follow 2 → AC 2FA+submit →
    # password (bot Password) → optional extra email. No separate flow needed.
    # (Was briefly modelled as payout-only — corrected 2026-09-28: the bot sends
    #  Username/Password in the message BEFORE the key prompt.)
}

# Human labels for the task-window gate log (phase names).
STEP_LABELS = {
    "ig_join": "IG join",
    "ig_rename": "IG rename",
    "ig_signup": "IG native signup",
    "cookie_export": "cookie export",
    "submit_cookie": "cookie submit",
    "email_link": "email link",
    "2fa": "2FA submit",
    "password": "password change",
    "extra_email": "extra email",
    "register": "register confirm",
    "submit_key": "submit 2FA key",
    "confirm": "confirm registration",
}


def flow_of(task_flow: str) -> str:
    """Known flow name, else the conservative default ("2fa")."""
    f = str(task_flow or "").strip().lower()
    return f if f in FLOWS else "2fa"


def spec(flow: str) -> dict:
    return dict(FLOWS.get(flow_of(flow), FLOWS["2fa"]))


def steps_of(flow: str):
    """Ordered step names for a flow (copy)."""
    return list(spec(flow).get("steps") or [])


def step_label(step: str) -> str:
    return STEP_LABELS.get(step, step)


def needs_email(flow: str) -> bool:
    return bool(spec(flow).get("needs_email"))


def needs_2fa(flow: str) -> bool:
    return bool(spec(flow).get("needs_2fa"))


def runner_of(flow: str) -> str:
    return str(spec(flow).get("runner") or "")


def resolve_steps(bot_target: str, task) -> list:
    """Ordered step list for a (bot, task), honouring per-task overrides.

    Resolution order:
      1. ``TASKS[bot][task]["steps"]``  — an explicit list beats the flow;
      2. else the task's ``flow`` steps (default flow = ``2fa``);
      3. minus ``TASKS[bot][task]["skip"]``.

    This is what makes "a different task needs different steps" a DATA edit:
    a task can drop ``password``/``extra_email`` (or add a learned step) with no
    runner change. Unknown steps are ignored-with-a-warning by the callers.
    """
    try:
        import tg_tasks
        tid, _reason = tg_tasks.resolve(bot_target, task)
        tspec = (tg_tasks.TASKS.get(str(bot_target), {}) or {}).get(tid) if tid else None
    except Exception:
        tspec = None
    if not tspec:
        return list(FLOWS["2fa"]["steps"])
    flow = tspec.get("flow") or "2fa"
    steps = tspec.get("steps") or list(FLOWS.get(flow, FLOWS["2fa"]).get("steps") or [])
    skip = set(tspec.get("skip") or [])
    return [s for s in steps if s not in skip]


def validate_steps(bot_target: str, task) -> list:
    """Human-readable problems with a task's resolved steps (empty = ok)."""
    issues = []
    steps = resolve_steps(bot_target, task)
    try:
        import tg_steps
        err = tg_steps.validate(steps)
        if err:
            issues.append(err)
    except Exception:
        pass
    if not steps:
        issues.append("resolved to an empty step list")
    return issues

