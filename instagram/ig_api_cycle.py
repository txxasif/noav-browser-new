"""instagram/ig_api_cycle.py — shared browserless step helpers for the pool
runners. Used only when ``ig_api.api_mode()`` is ON; the browser runners call
the existing code otherwise (invariant 24 — zero regression when the switch is
off).

Each helper takes the runner's already-resolved objects (the pooled account
record, the TG bot, the log/emit callables) and does ONE IG-side step through
the private API. Every helper is best-effort and returns a value the runner can
act on; failures raise ``IGDeadEnd`` only for genuine dead sessions so the
caller can purge and move to the next account (same contract as the browser
helpers).
"""
from __future__ import annotations

import random
import time

from instagram.ig_api import api_mode, client_for_account, pick_follow_targets

try:
    from pipelines.telegram.tg_support import IGDeadEnd
except Exception:  # pragma: no cover
    class IGDeadEnd(Exception):
        pass

_DEAD_HINTS = ("checkpoint", "login_required", "logged_out", "challenge",
               "user_has_logged_out", "session expired", "invalid")


def _is_dead(msg: str) -> bool:
    low = str(msg or "").lower()
    return any(p in low for p in _DEAD_HINTS)


def client_for(pool_acc: dict, username: str = "", password: str = ""):
    """Build a browserless client for a pooled account record.

    ``username`` / ``password`` override the record — required because after the
    rename the account's real username is the bot login, and after a password
    change the record's stored password is stale.
    """
    c = client_for_account(pool_acc or {})
    if username:
        c.username = str(username).lstrip("@")
    if password:
        c.password = password
    return c


# --------------------------------------------------------------------------- #
# Follow
# --------------------------------------------------------------------------- #
def follow_targets(client, need: int, log, *, exclude=(), self_username: str = "",
                   mobile: bool = True, delay=(1.5, 1.5)) -> int:
    """Follow ``need`` random targets from the fixed operator list.

    Returns the number of follows that actually persisted. Raises IGDeadEnd on a
    login/challenge (dead session). Never raises for a mere follow failure.
    """
    if need <= 0:
        return 0
    exclude = set(exclude or ())
    if self_username:
        exclude.add(self_username)
    targets = pick_follow_targets(need, exclude=exclude)
    if not targets:
        log("[👥][api] No follow targets available.")
        return 0

    # Get a mobile session first so the (more trusted) mobile follow can be used
    # where the web follow is blocked. Best-effort — web is the fallback.
    try:
        if mobile and not client.token:
            ok, why = client.mobile_login()
            log(f"[👥][api] mobile login: {'ok' if ok else why}")
    except Exception as exc:
        log(f"[👥][api] mobile login note: {exc}")

    # Resolve pk first (also warms the web session), then warm-up, then follow.
    pks = []
    for u in targets:
        pk = client.pk_of(u)
        if pk:
            pks.append((u, pk))
        else:
            log(f"[👥][api] {u}: username not resolvable — skipping.")
    if not pks:
        return 0

    if mobile:
        try:
            client.warmup([pk for _u, pk in pks])
        except Exception:
            pass

    n_ok = 0
    for u, pk in pks:
        ok, why = client.follow(pk, via="auto" if mobile else "web")
        if ok:
            n_ok += 1
            log(f"[👥][api] Followed @{u} ({n_ok}/{need}).")
        else:
            if _is_dead(why):
                raise IGDeadEnd(f"follow dead session: {why}")
            # The web follow transport is blocked for this session (IG answers a
            # login/challenge HTML 200). Trying the REMAINING targets just burns
            # ~2.5s each — bail now and let the caller switch to the browser.
            log(f"[👥][api] @{u} follow failed: {why}")
            log("[👥][api] follow transport blocked — stopping the API follow; browser fallback.")
            break
        time.sleep(random.uniform(*delay))
    return n_ok


# --------------------------------------------------------------------------- #
# 2FA (real, via API) — returns (secret, ok)
# --------------------------------------------------------------------------- #
def enable_2fa(client, bot, log, *, parked_seed: str = "") -> tuple:
    """generate seed -> submit to bot -> enable with the bot's code (+local fallback).

    Returns (secret, ok). ``parked_seed`` short-circuits when the account already
    has a 2FA secret (nothing to generate/confirm on IG).
    """
    secret = ""
    if parked_seed:
        secret = parked_seed.strip()
        log(f"[🔐][api] 2FA already set with parked seed ({secret[:4]}****) — submitting, no IG setup.")
        try:
            bot.submit_2fa_key(secret, allow_local_fallback=False)
        except Exception as exc:
            log(f"[⚠️][api] parked-seed submit note: {exc}")
        return secret, True

    try:
        secret, why = client.totp_generate_seed()
    except Exception as exc:
        secret, why = "", str(exc)
    if not secret:
        if _is_dead(why):
            raise IGDeadEnd(f"2fa dead session: {why}")
        log(f"[⚠️][api] Could not obtain a 2FA seed: {why}")
        return "", False

    log(f"[🔐][api] 2FA seed obtained ({secret[:4]}****) — submitting to the bot…")
    code = ""
    try:
        code = bot.submit_2fa_key(secret, allow_local_fallback=False)
    except Exception as exc:
        log(f"[⚠️][api] submit_2fa_key note: {exc}")

    ok, why = client.totp_enable_with_fallback(code or "", secret)
    if ok:
        log("[🔐][api] 2FA enabled on the account.")
    else:
        log(f"[⚠️][api] 2FA enable failed: {why}")
    return secret, ok


def parked_seed_of(pool_acc: dict) -> str:
    return str((pool_acc or {}).get("twofa_secret") or "").strip()


# --------------------------------------------------------------------------- #
# Password / email
# --------------------------------------------------------------------------- #
def change_password(client, old: str, new: str, log) -> bool:
    if not new or new == old:
        return True
    ok, why = client.change_password(old, new)
    log(f"[🔑][api] password change: {'ok' if ok else why}")
    return ok


def link_email(client, bot, email: str, log, *, fetch_code=None) -> bool:
    """send_confirm_email -> (bot Get-code / fetch_code) -> verify_email_code."""
    if not email:
        return False
    ok, why = client.send_confirm_email(email)
    if not ok:
        if "already" in str(why).lower() or "linked" in str(why).lower():
            log("[✉️][api] email already linked — continuing.")
            return True
        log(f"[⚠️][api] send_confirm_email failed: {why}")
        return False
    code = ""
    try:
        if callable(fetch_code):
            code = fetch_code()
        elif bot is not None:
            code = bot.request_email_code(timeout=45)
    except Exception as exc:
        log(f"[⚠️][api] email code fetch note: {exc}")
    if not code:
        log("[⚠️][api] no email code — email not confirmed.")
        return False
    ok2, why2 = client.verify_email_code(email, code)
    log(f"[✉️][api] email verify: {'ok' if ok2 else why2}")
    return ok2


# --------------------------------------------------------------------------- #
# Cookie
# --------------------------------------------------------------------------- #
def export_cookie(pool_acc: dict) -> str:
    """The stored web cookie header is the export (valid unless the password
    was changed after it was minted)."""
    return str((pool_acc or {}).get("cookies") or (pool_acc or {}).get("cookie") or "")
