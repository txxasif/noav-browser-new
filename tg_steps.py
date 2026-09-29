"""tg_steps.py — the STEP registry (single source of truth for one unit of work).

A **step** is one atom of a cycle, performed AFTER the shared preamble
(Meta create → lease TG profile → choose task → bot creds). A **flow**
(`tg_flows.py`) is an ordered list of steps; a **task** (`tg_tasks.py`) picks a
flow and may override/skip steps.

Why a registry (not inline code): "a different task needs different steps" must
be a DATA edit, not a code edit. Every step here declares:
  * ``label``  — human name for the task-window gate log
  * ``side``   — ``meta`` | ``tg`` | ``ig`` | ``bot`` (what it touches)
  * ``needs``  — capabilities it requires (``creds`` / ``bot`` / ``mail`` / ``browser``)
  * ``optional`` — may be skipped without failing the cycle
  * ``doc``    — one line on what it does (for an agent / the dashboard)

The runner (`tg_coupled` / `run_cookie_cycle`) walks ``tg_flows.resolve_steps``
and performs only the steps present in the list. Adding a step = one entry here
+ one callable in the runner + list it in a flow. Nothing else changes.

Future "the bot teaches the steps": a task can carry its OWN ``steps`` list in
``tg_tasks.TASKS[bot][task]``, so a flow learned from a bot's instructions can be
expressed as data without touching the runner.
"""
from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------------------- #
# The step catalogue. Order here is documentation only — a FLOW defines order.
# --------------------------------------------------------------------------- #
STEPS = {
    # --- Telegram-side (bot) steps ---
    "choose_task": {
        "label": "choose task", "side": "bot", "needs": ["bot"], "optional": False,
        "doc": "Pick the task in the bot (path-walked via tg_tasks).",
    },
    "creds": {
        "label": "task creds", "side": "bot", "needs": ["bot"], "optional": False,
        "doc": "Read the bot-issued Username/Password (FastPay) or name/login/password.",
    },
    "submit_2fa_key": {
        "label": "2FA submit", "side": "bot", "needs": ["bot"], "optional": False,
        "doc": "Send the account's 2FA key to the bot; read the one-time code.",
    },
    "register": {
        "label": "register confirm", "side": "bot", "needs": ["bot"], "optional": False,
        "doc": "Tap the register/confirm key and classify ONLY the new reply.",
    },
    "submit_cookie": {
        "label": "cookie submit", "side": "bot", "needs": ["bot"], "optional": False,
        "doc": "Send the exported IG cookie header and read the verdict.",
    },

    # --- Instagram-side steps ---
    "ig_join": {
        "label": "IG join", "side": "ig", "needs": ["browser", "creds"], "optional": False,
        "doc": "IG login → Meta card → join wizard with the bot username → dismiss onboarding.",
    },
    "ig_signup": {
        "label": "IG native signup", "side": "ig", "needs": ["browser", "bot", "creds"], "optional": False,
        "doc": "IG NATIVE email signup with the bot-issued email/name/login/password; email code fetched via the bot Get-code key; ends settled on the feed.",
    },
    "follow": {
        "label": "follow warm-up", "side": "ig", "needs": ["browser"], "optional": True,
        "doc": "Follow ~2 suggested profiles (anti-velocity warm-up before Accounts Center).",
    },
    "email_link": {
        "label": "email link", "side": "ig", "needs": ["browser", "mail"], "optional": True,
        "doc": "Link the signup email to Instagram (deferred to after 2FA when extra_email is on).",
    },
    "2fa": {
        "label": "2FA setup", "side": "ig", "needs": ["browser", "bot"], "optional": False,
        "doc": "Set up 2FA in Accounts Center, submit the key to the bot, confirm the code.",
    },
    "password": {
        "label": "password change", "side": "ig", "needs": ["browser", "creds"], "optional": True,
        "doc": "Change the IG password to the task password (AFTER 2FA — no email re-auth).",
    },
    "extra_email": {
        "label": "extra email", "side": "ig", "needs": ["browser", "mail"], "optional": True,
        "doc": "Mint a fresh mail.td inbox and add it to the IG profile (best-effort).",
    },
    "cookie_export": {
        "label": "cookie export", "side": "ig", "needs": ["browser"], "optional": False,
        "doc": "Build the IG cookie header string (hard gate on sessionid + >=100 chars).",
    },
}

# Steps that ONLY make sense with a given flow family — used for validation.
IG_STEPS = tuple(n for n, s in STEPS.items() if s["side"] == "ig")
BOT_STEPS = tuple(n for n, s in STEPS.items() if s["side"] == "bot")


def all_steps() -> list:
    return list(STEPS.keys())


def spec(step: str) -> dict:
    return dict(STEPS.get(str(step)) or {})


def exists(step: str) -> bool:
    return str(step) in STEPS


def label(step: str) -> str:
    return STEPS.get(str(step), {}).get("label") or str(step)


def side(step: str) -> str:
    return STEPS.get(str(step), {}).get("side") or ""


def needs(step: str) -> list:
    return list(STEPS.get(str(step), {}).get("needs") or [])


def is_optional(step: str) -> bool:
    return bool(STEPS.get(str(step), {}).get("optional"))


def validate(steps) -> Optional[str]:
    """Return an error string when a step list references an unknown step."""
    unknown = [s for s in (steps or []) if s not in STEPS]
    if unknown:
        return f"unknown step(s): {unknown}"
    return None
