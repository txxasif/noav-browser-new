"""tg_tasks.py — per-bot task registry (single source of truth).

Why this exists
--------------
Task availability differs per bot AND over time (PayGo's "Create Inst (2FA)"
button vanished 2026-09-27; "Create Inst (No mail)" exists ONLY on Taskly;
PayGo now only offers Cookies). The old code matched buttons with loose
substring logic plus cross-bot alias remaps, so when the wanted task was
absent it silently started a DIFFERENT task — burning money/TTL on the
wrong job. Observed classes:

* alias remap doing "other thing": asking PayGo for "No mail" silently ran
  Cookies (and vice versa);
* generic ``:has-text`` / substring fallback picking the 📱 mobile-logo
  button instead of the 🔥 one on PayGo;
* empty/stale keyboards degrading into a literal ``send("Start")`` the bot
  ignores (credential timeouts).

Contract
--------
* Every task has a canonical id (``NOMAIL``, ``INST_2FA``, ``COOKIES``).
* Each bot entry lists ONLY the tasks it actually offers, each with:
  ``label`` (human name), ``flow`` (``"2fa"`` | ``"cookie"``), ``price``
  (USD, informational), ``path`` — the exact button chain from the main
  menu, where each level is a matcher ``{"all": [...], "none": [...]}``
  applied to normalized button text.
* ``resolve(bot_target, task)`` returns ``(task_id, levels)`` or
  ``(None, reason)``. A task NOT listed for a bot is UNAVAILABLE — the
  caller must refuse (return False), never fall back to another task.
* ``match_level(buttons, level)`` picks the one button satisfying the
  matcher, or None. No fuzzy second-best.

Adding a task later (e.g. PayGo gains "Create Inst (No mail)" in the same
pattern): add one dict entry under that bot with its button path + flow.
Nothing else changes — pickers, aliases and guards read this module.
"""
from __future__ import annotations

# Canonical task ids. UI / CLI / worker strings resolve to these via ALIASES.
NOMAIL = "nomail"        # Create Inst (No mail) — Taskly only
INST_2FA = "inst_2fa"    # Create Inst (2FA) — Taskly only (PayGo button gone)
COOKIES = "cookies"      # Create Inst (Cookies) — PayGo only

# Canonical display label per task — mirrors the bot button text EXACTLY
# (same words + same emoji/logo), minus the volatile price suffix.
# Logo truth: Taskly No mail = 🔥 (meta_auto_ai tg_bot_web.py, 1f525 img
# selector); Taskly 2FA = 📱 (live submenu 2026-09-27); PayGo Cookies task
# = 📱 (live submenu 2026-09-27).
LABELS = {
    NOMAIL: "🔥 Create Inst (No mail)",
    INST_2FA: "📱 Create Inst (2FA)",
    COOKIES: "📱 Create Inst (Cookies)",
}

# User-facing strings (dashboard dropdown, --tg-task, legacy callers) ->
# canonical id. NOTE: deliberately NO cross-bot remaps. Asking a bot for a
# task it does not offer is an error, not an alias ("No mail" on PayGo must
# FAIL, not silently run Cookies).
ALIASES = {
    "Create Inst (No mail)": NOMAIL,
    "🔥 Create Inst (No mail)": NOMAIL,
    "Create Inst (No-mail)": NOMAIL,
    "No mail": NOMAIL,
    "Create Inst (2FA)": INST_2FA,
    "📱 Create Inst (2FA)": INST_2FA,
    "Create Inst": INST_2FA,
    "Create Inst (Cookies)": COOKIES,
    "📱 Create Inst (Cookies)": COOKIES,
    "Cookies": COOKIES,
    "Cookie": COOKIES,
    "🍪 Cookies": COOKIES,  # category button text (resolves; picker walks it)
}

# Per-bot catalog. ``path`` is ordered button levels from the MAIN menu.
# A level matches when the normalized button contains ALL of ``all`` and
# NONE of ``none``. Normalization = lowercase (emoji/price text kept — match
# on words, so "$0.0200" suffixes never matter).
TASKS = {
    "taskly": {
        NOMAIL: {
            "label": LABELS[NOMAIL],
            "flow": "2fa",
            "path": [
                {"all": ["task"], "none": ["cookie"]},           # 📋 Tasks
                {"all": ["create inst", "no mail"], "none": []},  # 🔥 Create Inst (No mail)
            ],
        },
        INST_2FA: {
            "label": LABELS[INST_2FA],
            "flow": "2fa",
            "path": [
                {"all": ["task"], "none": ["cookie"]},
                {"all": ["create inst", "2fa"], "none": ["no mail"]},
            ],
        },
    },
    "paygo": {
        COOKIES: {
            "label": LABELS[COOKIES],
            "flow": "cookie",
            "price": 0.02,
            "path": [
                {"all": ["task"], "none": []},                          # 📋 Tasks
                {"all": ["cookie"], "none": ["create inst"]},           # 🍪 Cookies category
                {"all": ["create inst", "cookie"], "none": []},         # 📱 Create Inst (Cookies)
            ],
        },
    },
}


def normalize(text: str) -> str:
    """Lowercase button/text match surface (emoji kept, harmless)."""
    return str(text or "").lower()


def match_level(buttons, level):
    """The ONE button satisfying ``level``, else None (never second-best)."""
    want_all = [w.lower() for w in (level.get("all") or [])]
    want_none = [w.lower() for w in (level.get("none") or [])]
    for b in buttons or []:
        low = normalize(b)
        if all(w in low for w in want_all) and not any(w in low for w in want_none):
            return b
    return None


def _strip_price(text: str) -> str:
    """Drop a trailing bot price suffix: " ($0.0200)" (prices change)."""
    import re
    return re.sub(r"\s*\(\$[\d.,]+\)\s*$", "", str(text or "")).strip()


def resolve(bot_target: str, task):
    """Resolve ``task`` for ``bot_target``.

    Returns ``(task_id, levels)`` on success, or ``(None, reason)`` when the
    task is unknown or not offered on this bot. Callers MUST treat the
    second case as a hard refusal — never another task.
    """
    bot = (bot_target or "").strip().lower()
    catalog = TASKS.get(bot)
    if catalog is None:
        return None, f"unknown bot '{bot_target}'"
    key = _strip_price(str(task or "").strip())
    task_id = ALIASES.get(key, key if key in catalog else None)
    if task_id not in LABELS:
        return None, f"unknown task '{task}'"
    spec = catalog.get(task_id)
    if spec is None:
        offered = ", ".join(LABELS[t] for t in catalog) or "nothing"
        return None, (f"'{LABELS[task_id]}' is not offered on "
                      f"{bot} (offers: {offered}) — refusing, not substituting")
    return task_id, list(spec.get("path") or [])


def flow_of(bot_target: str, task_id: str):
    """``'2fa'`` | ``'cookie'`` | None (unknown combo)."""
    try:
        return TASKS.get((bot_target or "").lower(), {}).get(task_id, {}).get("flow")
    except Exception:
        return None


def offered(bot_target: str):
    """Canonical labels this bot offers (dashboard / diagnostics)."""
    return [LABELS[t] for t in TASKS.get((bot_target or "").lower(), {})]
