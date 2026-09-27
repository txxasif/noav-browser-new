"""tg_flows.py — per-flow step pipelines (single source of truth).

A **task** (``tg_tasks.py``) declares which **flow** it uses (``"2fa"`` or
``"cookie"``). A **flow** declares the ordered **steps** its runner executes
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
    # Taskly "🔥 Create Inst (No mail)" / "📱 Create Inst (2FA)".
    "2fa": {
        "label": "Create Inst (2FA/No mail) — email + 2FA + password + register",
        "runner": "tg_coupled",
        "steps": ["email_link", "2fa", "password", "extra_email", "register"],
        "needs_email": True,
        "needs_2fa": True,
    },
}

# Human labels for the task-window gate log (phase names).
STEP_LABELS = {
    "ig_join": "IG join",
    "cookie_export": "cookie export",
    "submit_cookie": "cookie submit",
    "email_link": "email link",
    "2fa": "2FA submit",
    "password": "password change",
    "extra_email": "extra email",
    "register": "register confirm",
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
