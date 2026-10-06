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
* **Per-task STEP control (optional).** A task may also carry:
  ``steps`` — an explicit ordered step list (beats the flow's list), and
  ``skip`` — step names to drop from the flow. ``tg_flows.resolve_steps``
  applies them; the runner performs only what is listed. So "this task has no
  password step" or "2FA only, no extra email" is a DATA edit::

      INST_2FA:  {"label": "...", "flow": "2fa",
                  "skip": ["extra_email"],          # no extra-email step
                  "path": [...]},
      #   or a fully explicit, learned sequence:
      LEARNED:   {"label": "...", "steps": ["ig_join", "2fa", "register"],
                  "path": [...]},

  Step names live in ``tg_steps.STEPS`` (the step registry).
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
# Taskly "📱 Create Inst (2FA)" run as a POOL DRAIN: reuse a pre-created IG
# account from the IG Creator pool (rename via direct Web API + set 2FA from the
# account's stored mail.td inbox) instead of creating Meta→IG from scratch.
# Same bot button/path as INST_2FA — only the flow (runner) differs.
INST_2FA_POOL = "inst_2fa_pool"
COOKIES_NOMAIL = "cookies_nomail"  # Taskly: Cookies → Create Inst (No mail) (2FA + cookie)
COOKIES = "cookies"      # Create Inst (Cookies) — PayGo only
# PayGo "📱 Create Inst (2FA)" run as a POOL DRAIN: same-to-same as Taskly's
# INST_2FA_POOL (rename via direct Web API + 2FA from the stored inbox).
# Verified live 2026-10-02 over MTProto: identical preview text, identical
# creds (First name/Login/Password/Email via 📥 Get code), identical
# "Account Registered" confirm — only the bot + price ($0.0220) differ.
PAYGO_2FA_POOL = "paygo_2fa_pool"
FASTPAY_2FA = "fastpay_ig_2fa"  # Instagram 2FA payout — FastPay bot (key -> code)
# FastPay "Instagram 2FA" run as a POOL DRAIN: reuse a pre-created IG account
# (rename via Web API + 2FA + password) instead of creating Meta→IG.
FASTPAY_2FA_POOL = "fastpay_2fa_pool"

# Canonical display label per task — mirrors the bot button text EXACTLY
# (same words + same emoji/logo), minus the volatile price suffix.
# Logo truth: Taskly No mail = 🔥 (meta_auto_ai tg_bot_web.py, 1f525 img
# selector); Taskly 2FA = 📱 (live submenu 2026-09-27); PayGo Cookies task
# = 📱 (live submenu 2026-09-27).
LABELS = {
    NOMAIL: "🔥 Create Inst (No mail)",
    INST_2FA: "📱 Create Inst (2FA)",
    INST_2FA_POOL: "📱 Create Inst (2FA)",
    COOKIES_NOMAIL: "🍪 Create Inst (No mail)",
    COOKIES: "📱 Create Inst (Cookies)",
    PAYGO_2FA_POOL: "📱 Create Inst (2FA)",
    FASTPAY_2FA: "Instagram 2FA",
    FASTPAY_2FA_POOL: "Instagram 2FA",
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
    # Dashboard-only alias for the NEW "Taskly 2FA" panel (pooled drain mode).
    # It resolves to the same bot button/path but the pool flow/runner.
    "Taskly 2FA": INST_2FA_POOL,
    "Taskly 2FA (Pool)": INST_2FA_POOL,
    "Pool 2FA": INST_2FA_POOL,
    "Create Inst (Cookies)": COOKIES,
    "📱 Create Inst (Cookies)": COOKIES,
    "Cookies": COOKIES,
    "Cookie": COOKIES,
    "🍪 Cookies": COOKIES,  # category button text (resolves; picker walks it)
    # Taskly Cookies → "🍪 Create Inst (No mail)" (2FA + cookie flow).
    "🍪 Create Inst (No mail)": COOKIES_NOMAIL,
    "Create Inst (No mail) Cookies": COOKIES_NOMAIL,
    # FastPay2025_bot "Instagram 2FA" payout task.
    "Instagram 2FA": FASTPAY_2FA,
    "instagram 2fa": FASTPAY_2FA,
    "IG 2FA": FASTPAY_2FA,
    # Dashboard-only alias for the NEW "FastPay 2FA" panel (pooled drain).
    "FastPay 2FA": FASTPAY_2FA_POOL,
    "FastPay Instagram 2FA": FASTPAY_2FA_POOL,
    # Dashboard-only alias for the NEW "PayGo 2FA" panel (pooled drain mode).
    # Same bot button/path as Taskly's "📱 Create Inst (2FA)" but on PayGo.
    # NOTE: the raw "📱 Create Inst (2FA)" label still resolves to Taskly's
    # INST_2FA (global alias) — the pool panel must send "PayGo 2FA".
    "PayGo 2FA": PAYGO_2FA_POOL,
    "PayGo 2FA (Pool)": PAYGO_2FA_POOL,
    "Paygo 2FA": PAYGO_2FA_POOL,
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
            # Meta-coupled flow: Meta create -> IG join (bot Login) -> password change
            # -> bot email link -> 2FA setup -> register confirm
            "flow": "2fa",
            "price": 0.018,
            "path": [
                {"all": ["task"], "none": ["cookie"]},
                {"all": ["create inst", "2fa"], "none": ["no mail"]},
            ],
            "steps": ["password", "email_link", "2fa", "register"],
        },
        # SAME bot button as INST_2FA, but run as a POOL DRAIN (no Meta, no
        # browser signup): pop a pre-created IG account, rename it to the bot
        # login, enable 2FA using the account's stored mail.td inbox, register.
        INST_2FA_POOL: {
            "label": LABELS[INST_2FA_POOL],
            "flow": "pool_2fa",
            "price": 0.018,
            "path": [
                {"all": ["task"], "none": ["cookie"]},
                {"all": ["create inst", "2fa"], "none": ["no mail"]},
            ],
            # SAME step order as the regular Taskly 2FA task (tg_coupled):
            # password -> email_link (bot email via 📥 Get code) -> 2fa -> register.
            "steps": ["password", "email_link", "2fa", "register"],
        },
        # 🍪 Cookies → 🍪 Create Inst (No mail): 2FA first, then cookie submit.
        COOKIES_NOMAIL: {
            "label": LABELS[COOKIES_NOMAIL],
            "flow": "cookie_2fa",
            "price": 0.023,
            "path": [
                {"all": ["task"], "none": []},                    # 📋 Tasks
                {"all": ["cookies"], "none": []},                 # 🍪 Cookies category
                {"all": ["create inst", "no mail"], "none": ["twitter"]},  # 🍪 Create Inst (No mail)
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
        # SAME bot button as Taskly's "📱 Create Inst (2FA)", but on PayGo
        # ($0.0220, verified live 2026-10-02): Tasks → Create Inst (2FA)
        # DIRECTLY (no Cookies category — the L2 menu holds both
        # "📱 Create Inst (2FA)" and "🍪 Cookies" side by side). Same step
        # order as the Taskly pool drain: password -> email_link (bot email
        # via 📥 Get code) -> 2fa -> register.
        PAYGO_2FA_POOL: {
            "label": LABELS[PAYGO_2FA_POOL],
            "flow": "paygo_pool_2fa",
            "price": 0.022,
            "path": [
                {"all": ["task"], "none": []},                          # 📋 Tasks
                {"all": ["create inst", "2fa"], "none": ["no mail"]},   # 📱 Create Inst (2FA)
            ],
            "steps": ["email_link", "2fa", "password", "register"],
        },
    },
    # FastPay2025_bot — Instagram 2FA CREATE task (reverse-engineered live
    # 2026-09-28). It IS a task issuer after all: selecting the task sends
    #   📋 Task: Instagram 2FA
    #   👤 Username: `...`
    #   🔒 Password: `FASTPAY%27`
    # then asks for the 2FA key. So it runs the SAME create flow as Taskly's
    # "Create Inst (2FA)" (flow "2fa"), except the 2FA key is submitted to
    # FastPay (→ 2FA Code → Confirm → paid) instead of Taskly.
    # NOTE: reading only the LAST message shows just "Please send the 2FA Key
    # below:" — the creds arrive in the PREVIOUS message. Do not "simplify" the
    # creds reader to the last message (that is what made this look payout-only).
    # Labels render as Unicode bold (𝗧𝗮𝘀𝗸/𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺); `normalize` NFKC-folds
    # them to ASCII so these matchers match.
    "fastpay": {
        FASTPAY_2FA: {
            "label": LABELS[FASTPAY_2FA],
            "flow": "2fa",
            "price": 0.024,
            "path": [
                {"all": ["task"], "none": []},                        # 𝗧𝗮𝘀𝗸
                {"all": ["instagram"], "none": ["facebook"]},         # 𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺 category
                {"all": ["instagram", "2fa"], "none": ["facebook"]},  # Instagram 2FA task
            ],
            "steps": ["2fa", "password", "register"],
        },
        # SAME bot button as above, run as a POOL DRAIN (no Meta, no signup):
        # pop a pre-created IG account, rename it to the FastPay username,
        # enable 2FA, set the password, and Confirm the submission.
        FASTPAY_2FA_POOL: {
            "label": LABELS[FASTPAY_2FA_POOL],
            "flow": "fastpay_pool_2fa",
            "price": 0.024,
            "path": [
                {"all": ["task"], "none": []},
                {"all": ["instagram"], "none": ["facebook"]},
                {"all": ["instagram", "2fa"], "none": ["facebook"]},
            ],
        },
    },
}


def normalize(text: str) -> str:
    """Lowercase, NFKC-normalized match surface.

    NFKC folds Unicode "math bold"/fancy letterforms back to plain ASCII
    (FastPay's menu is 𝗧𝗮𝘀𝗸 / 𝗜𝗻𝘀𝘁𝗮𝗴𝗿𝗮𝗺, which ``.lower()`` alone does NOT turn
    into ASCII), so ASCII matcher terms still match. Plain ASCII (Taskly /
    PayGo) is unchanged; emoji and prices are untouched.
    """
    import unicodedata
    return unicodedata.normalize("NFKC", str(text or "")).lower()


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
    """``'2fa'`` | ``'cookie'`` | ``'cookie_2fa'`` | None (unknown combo).

    Accepts a canonical task id OR a label/alias (resolved first), so callers
    can pass whatever the dashboard sent.
    """
    b = (bot_target or "").lower()
    try:
        spec = TASKS.get(b, {}).get(task_id)
        if spec is None:
            tid, _reason = resolve(b, task_id)
            spec = TASKS.get(b, {}).get(tid) if tid else None
        return (spec or {}).get("flow")
    except Exception:
        return None


def offered(bot_target: str):
    """Canonical labels this bot offers (dashboard / diagnostics)."""
    return [LABELS[t] for t in TASKS.get((bot_target or "").lower(), {})]
