#!/usr/bin/env python3
"""One-shot PayGo Cookies task cycle: Meta -> TG Cookies creds -> IG join ->
follow ~2 -> export IG cookie header -> submit cookie -> register -> Submitted.

The post-lease STEPS are data-driven by :mod:`tg_flows` (single source of
truth). For the ``cookie`` flow that is exactly::

    ig_join -> cookie_export -> submit_cookie

A cookie task verifies via the exported IG cookie, so there is **no email
link** and **no 2FA/password** step (the former "email after follow" step made
a fresh account sit in Accounts Center for ~90s and was actively harmful).
Adding/removing a step = edit ``tg_flows.FLOWS`` + implement the callable —
the preamble is shared and untouched.

Preamble (all flows): Meta creation (no TG lease held) -> lease ONE TG profile
-> choose "Create Inst (Cookies)" -> Start -> creds.

Strict: first failure cancels the TG task, releases the lease, closes the
browser, and exits nonzero with the step in the message.
"""
from __future__ import annotations

import os
import sys
import threading
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from ai_config import SELFIE_PATH, DATA_DIR, emit_event  # noqa: E402
# NOTE: AISlotWorker is imported lazily inside run_cookie_cycle_once —
# worker.py (which defines it) lazily imports this module for the --cookie
# engine path, so a top-level import here would be circular.
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
# Browserless API path (opt-in via IG_API_MODE=1). Imported here only for the
# switch check; the browser code below is untouched when the switch is OFF.
from instagram import ig_api  # noqa: E402
from instagram import ig_api_cycle  # noqa: E402

COOKIE_TASK = "📱 Create Inst (Cookies)"
COOKIE_FLOW = "cookie"
TASK_WINDOW = 420  # bot ~8-min TTL; fail fast past it

# Cookie-drain task per bot (pool failover candidates). fastpay offers no
# cookie task, so it never appears here. Labels mirror the dashboard so the
# pool UI offers the SAME options as the main TG Classic UI.
COOKIE_TASK_FOR_BOT = {
    "paygo": "📱 Create Inst (Cookies)",
    "taskly": "Taskly Cookie",
}
# Classic-creation labels per bot. The classic runner only implements
# ig_join/2fa/cookie_export/submit_cookie, so classic failover MUST use labels
# resolving to the cookie/cookie_2fa flows — never a pool alias (ig_rename has
# no classic implementation and would crash the cycle).
COOKIE_CLASSIC_TASK_FOR_BOT = {
    "paygo": "📱 Create Inst (Cookies)",
    "taskly": "🍪 Create Inst (No mail)",
}
DEFAULT_COOKIE_PRIORITY = ["paygo", "taskly"]


def read_cookie_priority() -> list:
    """Ordered cookie-drain bot ids from data/settings.json (dashboard UI).

    Unknown/stale ids are dropped; missing ids are appended in default order
    so the result always covers every cookie bot exactly once.
    """
    try:
        import json as _json
        with open(os.path.join(DATA_DIR, "settings.json"), "r", encoding="utf-8") as fh:
            j = _json.load(fh) or {}
        order = j.get("tg_cookie_priority") or []
        seen, out = set(), []
        for b in order:
            b = str(b or "").strip().lower()
            if b in COOKIE_TASK_FOR_BOT and b not in seen:
                seen.add(b)
                out.append(b)
        for b in DEFAULT_COOKIE_PRIORITY:
            if b not in seen:
                out.append(b)
        return out
    except Exception:
        return list(DEFAULT_COOKIE_PRIORITY)


def cookie_candidates(primary_bot: str, primary_task: str, pool_mode: bool = True) -> list:
    """[(bot, task)] — primary first, then priority-ordered failover bots.

    ``pool_mode`` selects pool aliases (ig_rename steps) vs classic labels
    (ig_join steps) for the failover targets, matching the runner path.
    """
    first = str(primary_bot or "paygo").strip().lower() or "paygo"
    table = COOKIE_TASK_FOR_BOT if pool_mode else COOKIE_CLASSIC_TASK_FOR_BOT
    cands = [(first, primary_task)]
    for b in read_cookie_priority():
        if b != first and b in table:
            cands.append((b, table[b]))
    return cands

_profile_pacing_lock = threading.Lock()
_profile_last_start: dict[str, float] = {}

# IG anti-spam ({"spam":true}) on the rename endpoint. A single hit marks the
# ACCOUNT as blocked (remove it); a long CONSECUTIVE streak means the IP is
# flagged, so STOP the drain instead of emptying the whole pool.
_ig_spam_streak = [0]
_IG_SPAM_STOP = int(os.environ.get("INSTA_IG_SPAM_STOP", "20") or 20)

# IG "checkpoint_required" on the rename endpoint. A burst of these across many
# accounts in a few seconds is the IP being CHALLENGED — NOT N dead accounts.
# Observed 2026-10-08: 6 parallel slots purged dozens of perfectly resumable
# accounts in ~30s this way. Correct handling = RESTORE the account (retry it
# later) and trip a FAST breaker so the drain PAUSES instead of emptying the
# pool.
_IG_CHECKPOINT_STOP = int(os.environ.get("INSTA_IG_CHECKPOINT_STOP", "0") or 0)
_IG_CHALLENGE_COOLDOWN = int(os.environ.get("INSTA_IG_CHALLENGE_COOLDOWN", "180") or 180)
_IG_CHALLENGE_MAX = int(os.environ.get("INSTA_IG_CHALLENGE_MAX", "1800") or 1800)
_ig_challenge_until = [0.0]
_challenge_trips = [0]   # progressive backoff: 180 → 360 → 720 → … capped at MAX


def _is_ig_checkpoint_error(msg: str) -> bool:
    """Rename-endpoint challenge signals — the account is NOT dead."""
    low = str(msg or "").lower()
    return any(p in low for p in (
        "checkpoint", "challenge_required", "consent_required",
        "rate limit", "rate_limit", "too many requests", "429", "please_wait",
    ))


def _trip_challenge_backoff():
    """Progressive IP-challenge backoff: base ×2 per trip, capped at MAX.

    A single 180s window does not clear a real IP flag (observed: it re-tripped
    immediately), so each consecutive trip doubles the wait. Returns the chosen
    cooldown (seconds) and arms the shared ``_ig_challenge_until``.
    """
    _challenge_trips[0] += 1
    cd = min(_IG_CHALLENGE_COOLDOWN * (2 ** (_challenge_trips[0] - 1)), _IG_CHALLENGE_MAX)
    _ig_challenge_until[0] = time.time() + cd
    return cd


# Serialize + space out rename calls ACROSS slots — ADAPTIVELY. Six slots
# hitting /api/v1/web/accounts/edit/ within the same second from one IP is what
# invites the checkpoint. The interval starts at 0 (the fast path pays NOTHING),
# rises only AFTER Instagram actually challenges a rename, and decays back to 0
# once renames succeed again.
_rename_pace_lock = threading.Lock()
_rename_last = [0.0]
_rename_interval = [0.0]
_rename_ok_streak = [0]
_IG_RENAME_MIN_INTERVAL = float(os.environ.get("INSTA_IG_RENAME_MIN_INTERVAL", "1.2") or 1.2)
_IG_RENAME_OK_DECAY = int(os.environ.get("INSTA_IG_RENAME_OK_DECAY", "15") or 15)


def _rename_pace_gate():
    with _rename_pace_lock:
        iv = _rename_interval[0]
        if iv > 0:
            wait = _rename_last[0] + iv - time.time()
            if wait > 0:
                time.sleep(wait)
        _rename_last[0] = time.time()


def _note_rename_result(ok: bool):
    """Ramp the pace on a challenge; decay it once renames flow again."""
    if ok:
        _rename_ok_streak[0] += 1
        if _rename_interval[0] > 0 and _rename_ok_streak[0] >= _IG_RENAME_OK_DECAY:
            _rename_interval[0] = 0.0
    else:
        _rename_ok_streak[0] = 0
        if _IG_RENAME_MIN_INTERVAL > 0:
            _rename_interval[0] = min(max(_rename_interval[0] + 0.6, _IG_RENAME_MIN_INTERVAL), 3.0)

# Once the API follow fails on the first attempt, stop trying it for the rest of
# this process. IG blocks the raw API login (429 / "out of date"), so every retry
# only burns ~25s before the browser fallback. Reset on the next engine start.
_API_FOLLOW_DISABLED = False


def _ig_spam_blocked(msg: str) -> bool:
    return "spam" in str(msg or "").lower()


def log(slot_id, m):
    print(f"[cookie:{slot_id}] {m}", flush=True)


def _is_account_dead_error(msg: str) -> bool:
    """Return True if error indicates the account is banned, checkpointed, or has a dead session."""
    low = str(msg or "").lower()
    return any(p in low for p in (
        "checkpoint", "suspended", "login_required", "logged_out",
        "challenge", "unauthorized", "forbidden", "401", "403",
        "feedback_required", "disabled", "banned", "user_has_logged_out",
        "session expired", "invalid cookie", "user not found"
    ))


_IG_SESSION = None
_IG_SESSION_LOCK = threading.Lock()

def _rename_proxy():
    """``PROXY_URL`` for the direct rename API.

    The browser already honours ``PROXY_URL``, but the rename POST used to go
    out on the HOST IP — so a flagged host stayed flagged even with a proxy
    configured, and the drain could never recover. ``{session}`` is substituted
    with a stable per-process token so every rename shares one egress.
    """
    try:
        url = (os.environ.get("PROXY_URL") or "").strip()
    except Exception:
        return None
    if not url:
        return None
    if "{session}" in url:
        tok = os.environ.get("INSTA_PROXY_SESSION") or f"r{os.getpid()}"
        url = url.replace("{session}", tok)
    return url


def _get_ig_session():
    global _IG_SESSION
    if _IG_SESSION is None:
        with _IG_SESSION_LOCK:
            if _IG_SESSION is None:
                try:
                    import requests
                    from requests.adapters import HTTPAdapter
                    s = requests.Session()
                    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
                    s.mount("https://", adapter)
                    _px = _rename_proxy()
                    if _px:
                        s.proxies.update({"http": _px, "https": _px})
                    _IG_SESSION = s
                except Exception:
                    _IG_SESSION = False
    return _IG_SESSION


def _pool_health_purge(store_mod, slot_id, limit=6):
    """NETWORK health check: probe the newest pooled accounts and PURGE the
    suspended ones BEFORE leasing a TG profile / pressing Start.

    A stored ``sessionid`` is not proof the session still works — IG invalidates
    it on suspension, which is why the follow later fails with "no IG sessionid
    after follow". One cheap ``web_form_data`` GET per account (~0.5s) tells the
    truth, so a dead account costs ~0.5s instead of a whole bot task (lease +
    Start + 2FA round-trips). Returns ``(live, dead)``.
    """
    try:
        rows = store_mod.peek_pool_accounts(limit)
    except Exception:
        return (0, 0)
    live = dead = 0
    for rec in rows:
        try:
            _cl = ig_api.client_for_account(rec)
            if _cl.is_locked():
                dead += 1
                try:
                    store_mod.delete_record(rec["id"])
                except Exception:
                    pass
            else:
                live += 1
        except Exception:
            pass
    if dead:
        emit_event({"type": "accounts_updated"})
    return (live, dead)


def change_ig_username_fast(cookie_str: str, target_username: str, ua: str = None) -> tuple[bool, str]:
    """Change Instagram username via the direct Web API (~0.1-0.4s).

    Thin wrapper over ``_change_ig_username_fast_impl`` that also feeds the
    ADAPTIVE rename pacer: a challenge ramps the per-call spacing, sustained
    success decays it back to zero.
    """
    _rename_pace_gate()
    ok, msg = _change_ig_username_fast_impl(cookie_str, target_username, ua)
    if ok:
        confirmed = _verify_ig_username(cookie_str, target_username, ua)
        if confirmed is False:
            return False, "IG said ok but the username did not change (verify failed)"
    if ok:
        _note_rename_result(True)
    elif _is_ig_checkpoint_error(msg):
        _note_rename_result(False)
    return ok, msg


def _verify_ig_username(cookie_str: str, target_username: str, ua: str = None):
    """True/False = the account's username now equals ``target_username``;
    None = could not check (then the API's own 'ok' stands)."""
    import json
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://www.instagram.com/api/v1/accounts/edit/web_form_data/",
            headers={"User-Agent": ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                     "X-IG-App-ID": "936619743392459", "Cookie": cookie_str, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=10) as r:
            got = ((json.loads(r.read().decode("utf-8", "replace")).get("form_data") or {}).get("username") or "")
        return (got.lower() == str(target_username).lower()) if got else None
    except Exception:
        return None


def _change_ig_username_fast_impl(cookie_str: str, target_username: str, ua: str = None) -> tuple[bool, str]:
    """Change Instagram username via direct Web API in ~0.1s using persistent Keep-Alive connections.

    POST https://www.instagram.com/api/v1/web/accounts/edit/
    Requires sessionid and csrftoken in cookie_str.
    """
    import json
    import re
    import urllib.error
    import urllib.parse
    import urllib.request

    csrf_match = re.search(r"csrftoken=([^; ]+)", cookie_str)
    csrf_token = csrf_match.group(1) if csrf_match else ""

    headers = {
        "User-Agent": ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-CSRFToken": csrf_token,
        "X-IG-App-ID": "936619743392459",
        "Referer": "https://www.instagram.com/accounts/edit/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie_str,
        "Accept": "*/*",
    }

    # Fast path: persistent Keep-Alive session (~0.1s)
    session = _get_ig_session()
    if session:
        try:
            resp = session.post(
                "https://www.instagram.com/api/v1/web/accounts/edit/",
                data={"username": target_username},
                headers=headers,
                timeout=10,
            )
            body = resp.text
            try:
                res_json = resp.json()
                if res_json.get("status") == "ok":
                    return True, "ok"
                msg = res_json.get("message") or body[:200]
                _cu = res_json.get("checkpoint_url") or ""
                if _cu or res_json.get("lock"):
                    msg = f"{msg} [lock url={_cu}]"
                return False, f"IG API: {msg}"
            except Exception:
                # An HTML page (login redirect / challenge) with HTTP 200 is NOT
                # a success — returning True here logged "✅ updated" with
                # <!DOCTYPE html> for a rename that never happened.
                if (body or "").lstrip()[:1] == "<":
                    return False, f"HTTP {resp.status_code} HTML (login/challenge — not renamed)"
                return False, f"HTTP {resp.status_code} non-JSON — rename not confirmed: {body[:80]}"
        except Exception:
            pass  # Fall back to standard urllib below

    data = urllib.parse.urlencode({"username": target_username}).encode("utf-8")
    req = urllib.request.Request(
        "https://www.instagram.com/api/v1/web/accounts/edit/",
        data=data,
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                res_json = json.loads(body)
                if res_json.get("status") == "ok":
                    return True, "ok"
                msg = res_json.get("message") or body[:200]
                _cu = res_json.get("checkpoint_url") or ""
                if _cu or res_json.get("lock"):
                    msg = f"{msg} [lock url={_cu}]"
                return False, f"IG API: {msg}"
            except Exception:
                if (body or "").lstrip()[:1] == "<":
                    return False, "HTTP 200 HTML (login/challenge — not renamed)"
                return False, f"non-JSON 200 — rename not confirmed: {body[:80]}"
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body)
            msg = err_json.get("message") or err_body[:200]
            return False, f"HTTP {exc.code}: {msg}"
        except Exception:
            return False, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        return False, str(exc)


def _all_flooded_until():
    """Earliest ``flood_until`` when EVERY leasable account is flood-limited.

    Returns ``None`` if at least one account is usable (so the caller keeps its
    normal busy/retry behaviour) or if flood state cannot be read.
    """
    try:
        from tg_accounts import tg_manager as _m
        _m._reload()
        now = time.time()
        untils = []
        for a in _m.accounts:
            if a.get("enabled") is False or not a.get("logged_in"):
                continue
            fu = a.get("flood_until")
            try:
                fu = float(fu) if fu else 0.0
            except (TypeError, ValueError):
                fu = 0.0
            if fu <= now:
                return None          # one usable account -> not "all flooded"
            untils.append(fu)
        return min(untils) if untils else None
    except Exception:
        return None


def _sleep_until(when, stop_event=None, chunk=30.0):
    """Sleep until ``when`` (epoch secs) in stop-aware chunks."""
    while True:
        try:
            if stop_event is not None and stop_event.is_set():
                return
        except Exception:
            pass
        left = float(when) - time.time()
        if left <= 0:
            return
        time.sleep(min(chunk, left))


def _click_reload_if_unavailable(p) -> bool:
    """Click IG/Accounts-Center 'Reload Page' on the transient error screen.

    Operator instruction 2026-10-07: on accountscenter.instagram.com
    "This page isn't available right now" (technical error + Reload Page),
    CLICK RELOAD PAGE. The generic ``_recover_something_went_wrong`` deliberately
    avoids reloading AC routes (it takes a Way Out), so this explicit reload is
    applied where the operator wants it. Returns True when it clicked.
    """
    try:
        tail = (p.inner_text("body") or "").lower()
    except Exception:
        tail = ""
    if not any(k in tail for k in ("isn't available right now", "isn’t available right now",
                                   "reload page", "something went wrong", "technical error")):
        return False
    clicked = False
    try:
        btn = p.locator('button:has-text("Reload page"), div[role="button"]:has-text("Reload page"), '
                        'a:has-text("Reload page")').first
        if btn.count() > 0 and btn.is_visible():
            try:
                btn.click(timeout=3000)
            except Exception:
                btn.click(force=True, timeout=2000)
            clicked = True
    except Exception:
        pass
    if not clicked:
        try:
            clicked = bool(p.evaluate("""() => {
                for (const el of document.querySelectorAll('button, div[role="button"], a, span')) {
                    if ((el.innerText || el.textContent || '').trim().toLowerCase() === 'reload page') {
                        el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                        el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                        el.click();
                        return true;
                    }
                }
                return false;
            }"""))
        except Exception:
            pass
    if clicked:
        try:
            p.wait_for_timeout(3500)
        except Exception:
            pass
    return clicked


def _mock_2fa_secret() -> str:
    """Random 16-char base32 secret in the real IG format (see twofa.py)."""
    import secrets as _secrets
    return (_secrets.token_hex(8).upper().replace("0", "A").replace("1", "B")
            .replace("8", "C").replace("9", "D"))


def _flow_has_2fa(bot_target, task) -> bool:
    """True when the task's resolved flow contains a 2FA-submit step (the bot
    expects a key before the cookie — Taskly does, PayGo Cookies does not)."""
    try:
        from tg_flows import resolve_steps as _rs
        return "2fa" in (_rs(bot_target, task) or [])
    except Exception:
        return False


def _pool_api_2fa_and_export_cookie(slot_id, bot, bot_id, pool_acc, login,
                                    follow_count=5, task=None):
    """BROWSERLESS 2FA + follow + cookie export (IG_API_MODE=1).

    API mode is REAL-2FA ONLY. The MOCK-2FA path exists ONLY when API mode is
    OFF. If the API 2FA fails here the cycle FAILS (the caller restores the
    account) — it never falls back to a mock key or the browser.

      * follow ``follow_count`` random targets from the fixed operator list
        (instagram.ig_api.IG_FOLLOW_TARGETS) via the private API;
      * REAL 2FA: generate the seed, submit it to the bot, enable with the
        bot's code (+ pyotp fallback) — no Accounts Center, no email OTP;
      * export cookie = the STORED cookie (unchanged: no password change here).

    Raises IGDeadEnd for a genuinely dead session.
    """
    global _API_FOLLOW_DISABLED

    def _log(m):
        log(slot_id, m)

    # The IG Creator stores how many profiles the account followed at creation
    # (`followed`). Follow only the REMAINDER here — otherwise the task would
    # double-follow (velocity risk) and, in API mode, boot the browser
    # pointlessly. An account that already hit the mandate stays browserless.
    try:
        _have = int(pool_acc.get("followed") or 0)
    except Exception:
        _have = 0
    _need_follow = max(0, follow_count - _have)          # only the remainder is owed
    _skip_follow = follow_count <= 0 or _need_follow <= 0

    # Once the API follow has failed once this run (and a follow is still owed),
    # go straight to the browser — the API login is blocked by IG (429), so
    # retrying it only wastes ~25s each.
    if follow_count > 0 and not _skip_follow and _API_FOLLOW_DISABLED:
        _log("[👥][api] API follow disabled after an earlier failure — browser directly.")
        return _pool_enable_2fa_and_export_cookie(
            slot_id, bot, bot_id, pool_acc, login, None, None,
            follow_count=follow_count)

    client = ig_api_cycle.client_for(pool_acc, username=login)
    _log(f"[⚙️][api] Browserless path ON — follow {_need_follow} "
         f"(had {_have}/{follow_count}) + stored cookie.")

    # 1) Follow only the REMAINDER (unless already done at creation).
    if _skip_follow:
        _log(f"[👥][api] Follows already done at creation ({_have}/{follow_count}) — "
             f"skipping the follow step.")
        n_ok = 0
    else:
        n_ok = 0
        try:
            n_ok = ig_api_cycle.follow_targets(client, _need_follow, _log,
                                               self_username=login)
            _log(f"[👥][api] Followed {n_ok}/{_need_follow} "
                 f"(had {_have} → {_have + n_ok}/{follow_count}).")
        except IGDeadEnd:
            raise
        except Exception as exc:
            _log(f"[⚠️][api] follow step error ({exc}) — continuing to 2FA.")

    # The API login is blocked by IG (429 / "out of date") — proven NOT an IP
    # issue (the follow request reached IG fine). So the browser (session reuse,
    # NO login) is the working transport. Disable the API follow for the rest of
    # the run on the FIRST failure so we stop paying ~25s/account for it.
    if follow_count > 0 and (_have + n_ok) < follow_count:
        _API_FOLLOW_DISABLED = True
        _log(f"[👥][api] API follow incomplete ({_have + n_ok}/{follow_count}) — disabling "
             f"the API follow for this run; browser from here (session reuse, no login).")
        return _pool_enable_2fa_and_export_cookie(
            slot_id, bot, bot_id, pool_acc, login, None, None,
            follow_count=follow_count)

    # 2) 2FA — REAL by default in API mode; MOCK only when the API-mock toggle
    #    is on (that toggle is shown ONLY in API mode).
    if _flow_has_2fa(bot_id, task):
        if ig_api.mock_2fa():
            secret = _mock_2fa_secret()
            _log(f"[🔑][api] MOCK 2FA key generated ({secret[:4]}****); submitting to the bot…")
            try:
                _code = bot.submit_2fa_key(secret, allow_local_fallback=True)
                _log(f"[🔑][api] MOCK 2FA submitted (bot code: {_code or 'none'}).")
            except Exception as _exc:
                _log(f"[⚠️][api] MOCK 2FA submit note ({_exc}) — continuing to cookie submit.")
        else:
            secret, ok = ig_api_cycle.enable_2fa(
                client, bot, _log,
                parked_seed=ig_api_cycle.parked_seed_of(pool_acc))
            if not (ok and secret):
                raise RuntimeError("API 2FA failed (API mode = real 2FA only; no mock)")
            # Park the seed on the record so a later restore keeps it.
            try:
                import store as _store
                _store.update_account(pool_acc["id"], {"twofa_secret": secret})
            except Exception:
                pass

    # 3) Cookie export = the stored cookie (no password change on this path).
    cookie = ig_api_cycle.export_cookie(pool_acc)
    if not cookie or len(cookie) < 100:
        raise RuntimeError("stored IG cookie missing/too short for the API path")
    _log(f"[🍪][api] Stored cookie ready ({len(cookie)} chars).")
    return cookie


def _pool_enable_2fa_and_export_cookie(slot_id, bot, bot_id, pool_acc, login,
                                       is_headless, worker_factory, follow_count=5,
                                       rename_to=None):
    """MOCK 2FA + follow + fresh cookie export (paygopool 2FA+Cookie ON).

    Follow N suggested accounts on the home feed, submit a MOCK 2FA key to
    the bot (no Accounts-Center nav, no email OTP, no ig_2fa_begin/confirm —
    that is what hit the Block/Restrict dead end), then export a fresh IG
    cookie header. Returns the cookie string. Used only when the 2FA toggle
    is ON.
    """
    # Shared pool helpers live in pool_common (imported lazily so the runner
    # module stays import-light).
    from pool_common import (
        _cookies_for_playwright, _browser_logged_in,
    )
    from runner import MetaInstaRunner
    from ai_config import SELFIE_PATH

    if worker_factory is None:
        from worker import AISlotWorker as _W
        worker_factory = _W

    worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
    runner = MetaInstaRunner(
        worker, twofa=True, telegram=False, tg_task=COOKIE_TASK,
        captcha_mode="none", mail_provider="mailtd", target="telegram")
    if os.path.exists(SELFIE_PATH):
        runner.selfie_path = SELFIE_PATH
    try:
        runner._install_screenshot_hooks()
    except Exception:
        pass
    try:
        runner._launch()
        ctx = getattr(getattr(runner, "w", None), "context", None)
        if ctx is None:
            raise RuntimeError("browser context unavailable after launch")
        try:
            ctx.clear_cookies()
        except Exception:
            pass
        ctx.add_cookies(_cookies_for_playwright(pool_acc["cookies"]))
        page = runner._ig_tab()
        # (1) Verify the session on the HOME feed FIRST — exactly how the working
        #     PayGo-2FA pool detects a dead session: a logged-OUT visitor feed
        #     renders "Log in"/"Open app", so _browser_logged_in() returns False.
        #     Checking the PROFILE instead was the bug: a visitor view of the
        #     account's own profile can look "logged in", so the flow sailed into
        #     Accounts Center and only then hit the Block/Restrict sheet.
        try:
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_selector('[role="dialog"], div[aria-modal="true"]', timeout=1200)
            except Exception:
                pass
            runner._dismiss_ig_sheets(page)
        except Exception as exc:
            log(slot_id, f"[⚠️] IG home load note: {exc}")
        if not _browser_logged_in(page):
            raise IGDeadEnd("pooled IG session not logged in (home feed)")
        # NOTE: the Accounts-Center rename walk was REMOVED (2026-10-08). On the
        # pooled accounts it never reached Settings — the profile route bounces to
        # /accounts/suspended/ — so it burned ~2 min/slot and never renamed. The
        # bare API rename above is the only rename; a challenged account simply
        # proceeds to the cookie submit (the bot decides, and a rejection restores
        # it). See R&D — Cookie-Farm §14.
        # MOCK mode: NO profile nav, NO ownership gates, NO AC nav. The
        # Block/Restrict dead end came from Step 1/2 profile+gear taps — we
        # never go there. Follow happens on the home feed only (below).
        for _attr in ("new_username", "username", "ig_username"):
            try:
                setattr(runner, _attr, login)
            except Exception:
                pass
        runner.password = pool_acc.get("password") or getattr(runner, "password", None)
        runner.new_password = pool_acc.get("password")

        # Follow warm-up (bot: "Did you make 5 subscriptions after registration?
        # … mandatory …"). The count is PER-TASK from tg_tasks ("follow"):
        # PayGo cookie = 5, Taskly cookie pool = 5. SKIP when the IG Creator
        # already followed >= the count at creation (record "followed").
        if follow_count <= 0:
            log(slot_id, "[👥] Follow step skipped — this task does not require follows.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": "Follow step skipped (not required for this task)."})
        else:
            try:
                already_followed = int(pool_acc.get("followed") or 0)
            except Exception:
                already_followed = 0
            if already_followed >= follow_count:
                log(slot_id, f"[👥] Account already followed {already_followed} in the IG Creator — "
                             f"skipping the follow step (bot's {follow_count}-subscription rule satisfied).")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                            "detail": f"Follow skipped — already followed {already_followed} at creation."})
            else:
                try:
                    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                                "detail": f"Following suggested accounts on {login} (bot requires {follow_count})…"})
                    # Already on the IG home feed (verified just above) — do NOT
                    # reload (the old second page.goto() cost a full page load).
                    # Follow only the REMAINDER owed so the task never
                    # double-follows past the mandate.
                    _need = max(1, follow_count - already_followed)
                    # explore/people first, feed rail for any shortfall
                    # (core/follow.py:ExploreFollowMixin.ig_follow_suggested).
                    runner._ig_follow_done = False
                    n_followed = int(runner.ig_follow_suggested(
                        max_follows=_need, humanize=True) or 0)
                    log(slot_id, f"[👥] Followed {n_followed}/{_need} suggested account(s) on the "
                                 f"pooled account (had {already_followed} → "
                                 f"{already_followed + n_followed}/{follow_count}).")
                except IGDeadEnd:
                    raise
                except Exception as exc:
                    log(slot_id, f"[⚠️] follow step note (continuing): {exc}")

        # In-page rename: the bare-API and mobile renames were both refused, so
        # retry the SAME accounts/edit POST from inside this warmed, followed
        # session (browser cookies + JS tokens + fingerprint). Best-effort: a
        # failure leaves the cookie to be submitted as before.
        if rename_to:
            try:
                from pool_prepare import rename_in_page
                _okr, _mr = rename_in_page(page, ctx, rename_to)
            except Exception as _er:
                _okr, _mr = False, str(_er)[:100]
            if _okr:
                log(slot_id, f"✅ [in-page] IG username updated to '{rename_to}' ({_mr}).")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                            "detail": f"Username set to {rename_to} (in-page)."})
            else:
                log(slot_id, f"↻ [in-page] rename to '{rename_to}' refused ({_mr[:80]}) — "
                             f"submitting the cookie as is.")

        # MOCK 2FA submit — no AC nav, no OTP, no ig_2fa_begin/confirm.
        # Just follow (above) + send a fake key so the bot advances, then
        # export the cookie. Nothing else.
        _mock_secret = _mock_2fa_secret()
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                    "detail": f"MOCK 2FA submit on pooled IG account ({login})…"})
        log(slot_id, f"[🔑] MOCK 2FA key generated ({_mock_secret[:4]}****); submitting to the bot…")
        try:
            code = bot.submit_2fa_key(_mock_secret, allow_local_fallback=True)
            log(slot_id, f"[🔑] MOCK 2FA submitted (bot code: {code or 'none — continuing anyway'})…")
        except Exception as exc:
            log(slot_id, f"[⚠️] MOCK 2FA submit note ({exc}) — continuing to cookie export anyway.")

        # Fresh cookie header from the followed session.
        jar = ctx.cookies()
        ig_cookies = [c for c in jar if "instagram.com" in str(c.get("domain", ""))]
        names = {c.get("name") for c in ig_cookies}
        if "sessionid" not in names:
            raise RuntimeError(f"no IG sessionid after follow (have: {sorted(names)})")
        cookie_str = "; ".join(
            f"{c['name']}={c['value']}" for c in ig_cookies
            if c.get("name") and c.get("value") is not None)
        if len(cookie_str) < 100:
            raise RuntimeError("cookie string too short (<100 chars) after follow")
        log(slot_id, f"[🍪] Fresh cookie exported after follow+MOCK 2FA ({len(cookie_str)} chars).")
        return cookie_str
    finally:
        try:
            runner.finish()
        except Exception:
            pass
        try:
            worker._cleanup_browser_resources()
        except Exception:
            pass


def _run_pool_drain_cycle(slot_id=91, is_headless=False, stop_event=None,
                          tg_task=COOKIE_TASK, tg_bot="paygo",
                          cookie_2fa=False, worker_factory=None,
                          fallback=False):
    """Run ONE PayGo drain cycle using pre-created accounts from data/accounts.json.

    1. Checks for available accounts in IG Creator pool.
    2. Leases ONE TG profile.
    3. Starts task on PayGo (📱 Create Inst (Cookies)) -> obtains target login.
    4. Claims an account from the pool.
    5. Changes its username to the bot's login in ~0.4s via direct IG Web API.
    6. Submits the account's cookie string to PayGo.
    7. Confirms registration (bot.mark_registered()).
    8. Deletes the consumed account from store.db / accounts.json so it is not double-spent.
    9. Records submission and releases lease.
    """
    import store

    def _stopped():
        try:
            return bool(stop_event and stop_event.is_set())
        except Exception:
            return False

    if _stopped():
        return False, "stopped"

    bot_id = str(tg_bot or "paygo")
    task = tg_task or COOKIE_TASK
    # Account SOURCE for this drain: "ig" = IG Creator pool (default, unchanged),
    # "meta" = Meta Creator list (login → join → follow → cookie). Set by
    # worker.py from --account-source; read here so no signature changes.
    _meta_src = (os.environ.get("COOKIE_ACCOUNT_SOURCE", "ig") or "ig").strip().lower() == "meta"

    # IP-level rename challenge cooldown (see _is_ig_checkpoint_error). Check
    # BEFORE leasing a TG profile / pressing Start: a parked slot must NOT burn
    # a bot task window (the earlier placement parked AFTER start_task, so every
    # retry re-issued creds and flooded the bot).
    if time.time() < _ig_challenge_until[0]:
        _remain = int(_ig_challenge_until[0] - time.time())
        log(slot_id, f"[pool] IG rename CHALLENGE cooldown — parking {min(_remain, 60)}s "
                     f"before leasing (accounts stay safe in the pool).")
        _sleep_until(time.time() + max(1, min(_remain, 60)), stop_event)
        return False, "ig_challenge_cooldown"

    if not _meta_src:
        # Reclaim submittals abandoned by an abrupt stop BEFORE the pool-empty
        # gate — otherwise stuck claims make the pool look empty and the drain
        # stops for good.
        try:
            store.recover_stale_submitting()
        except Exception:
            pass
        # Pre-flight HEALTH CHECK: drop accounts whose stored cookie has no
        # `sessionid` — they can never log in (the follow then fails with "no IG
        # sessionid"). This is a DB-only test: instant, no network, no TG lease, no
        # bot Start — so a dead account costs nothing instead of a whole task.
        try:
            _dead = store.purge_dead_sessions()
            if _dead:
                log(slot_id, f"[pool] Health: purged {_dead} dead-session account(s) "
                             f"(no sessionid) before leasing.")
                emit_event({"type": "accounts_updated"})
        except Exception as _pe:
            log(slot_id, f"[pool] health purge note: {_pe}")

        # NETWORK health check — probe the newest accounts and purge the SUSPENDED
        # ones BEFORE leasing/Start. A stored sessionid is not proof the session
        # works (IG invalidates it on suspension). If none are alive, skip the cycle
        # entirely so no bot task is spent on a dead pool.
        try:
            _hl, _hd = _pool_health_purge(
                store, slot_id, int(os.environ.get("INSTA_HEALTH_PROBE_N", "6") or 6))
            if _hd or _hl:
                log(slot_id, f"[pool] Health probe: {_hl} live / {_hd} suspended (purged).")
            if _hl <= 0:
                log(slot_id, "[pool] No LIVE pooled account — skipping the cycle (no bot task spent).")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "waiting",
                            "detail": "No live pooled IG account — waiting (health check)."})
                _sleep_until(time.time() + 20 + (slot_id % 6), stop_event)
                return False, "no_live_pool"
        except Exception as _he:
            log(slot_id, f"[pool] health probe note: {_he}")

        avail = store.count_ig_creator_accounts()
        if avail <= 0:
            log(slot_id, "[pool] No available IG Creator accounts in pool to drain.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                        "detail": "Pool empty: No IG Creator accounts left to drain."})
            _sleep_until(time.time() + 15 + (slot_id % 6), stop_event)
            return False, "no_pool_accounts"
        log(slot_id, f"[pool] Found {avail} available IG Creator account(s) in pool.")
    else:
        # META-LIST source: accounts are Meta Creator rows (no IG session yet).
        try:
            store.recover_stale_submitting()
        except Exception:
            pass
        avail = store.count_meta_list_accounts()
        if avail <= 0:
            log(slot_id, "[meta-list] No usable Meta-list account to drain.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                        "detail": "Meta list empty: no usable Meta Creator accounts left."})
            _sleep_until(time.time() + 15 + (slot_id % 6), stop_event)
            return False, "no_pool_accounts"
        log(slot_id, f"[meta-list] Found {avail} usable Meta-list account(s).")

    bot = None
    tg_acct = None
    lease_stop = None
    pool_acc = None
    ok = False
    rec_id = None
    msess = None

    try:
        if _meta_src:
            # Claim + browser + Instagram login BEFORE any Telegram work: a
            # login challenge here costs no bot TTL and no lease.
            from pool_prepare import MetaListSession
            msess = MetaListSession(
                slot_id, is_headless, worker_factory, lambda m: log(slot_id, m),
                stop_event=stop_event, task=task)
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": "Meta list: claiming an account + Instagram login…"})
            try:
                _macc = msess.open()
            except Exception:
                _sleep_until(time.time() + 6 + (slot_id % 5), stop_event)
                raise
            if _macc is None:
                raise RuntimeError("no_pool_accounts: Meta list ran dry")
        # Failover candidates: primary first, then priority-ordered cookie bots
        # (dashboard tg_cookie_priority). Without fallback there is exactly one.
        # Pool aliases here (ig_rename steps) — the classic path uses labels.
        _cands = cookie_candidates(bot_id, task, pool_mode=True) if fallback else [(bot_id, task)]
        if fallback and len(_cands) > 1:
            log(slot_id, "[failover] ON — order: " + " → ".join(
                f"{_b}" for _b, _t in _cands))
        login = None
        for _ci, (_cbot, _ctask) in enumerate(_cands):
            if _stopped():
                raise RuntimeError("stopped")
            if _ci > 0:
                log(slot_id, f"[failover] trying next bot: {_cbot} / {_ctask}…")
            if not tg_manager.usable():
                raise RuntimeError("No logged-in Telegram profile available")
            tg_acct = tg_manager.acquire(timeout=30, bot=_cbot)
            if not tg_acct:
                # Distinguish "merely busy" from "FLOOD-LIMITED until a known time".
                # A flood ban has a definite expiry, so spinning the loop every 1.5s
                # (30s acquire + 1.5s sleep) just spams the log with zero chance of
                # work — observed 2026-10-01: the same two lines every ~12s forever
                # while all 6 accounts served 3-5h waits. Sleep it out instead.
                wait_until = _all_flooded_until()
                if wait_until and wait_until > time.time():
                    secs = int(wait_until - time.time())
                    # NEVER sleep the full recorded window. `flood_until` is a
                    # STALE RECORD that nothing re-verifies: it is written from a
                    # FloodWaitError at one moment, and the real throttle can lift
                    # much earlier. Trusting it benched six accounts that could
                    # demonstrably still send (verified 2026-10-01 22:00 — all six
                    # passed reset_to_main_menu while the record claimed 128 min).
                    # Sleep a bounded slice, then let the loop re-try: if the
                    # throttle is real the attempt re-parks it (re-recording the
                    # fresh value); if it lifted, work resumes within one slice.
                    try:
                        _cap = int(os.environ.get("INSTA_TG_PARK_MAX_SLEEP", "300") or 300)
                    except (TypeError, ValueError):
                        _cap = 300
                    slice_s = max(30, min(secs, _cap))
                    log(slot_id, f"[pool] Every Telegram profile is reported FLOOD-LIMITED "
                                 f"(recorded {secs // 60}m {secs % 60}s). Sleeping {slice_s}s, "
                                 f"then re-verifying against reality.")
                    _sleep_until(time.time() + slice_s, stop_event)
                    try:
                        tg_manager.clear_flood()
                    except Exception:
                        pass
                    return False, "flooded"
                log(slot_id, "[pool] All Telegram profiles busy — waiting for next slot cycle.")
                _sleep_until(time.time() + 15 + (slot_id % 6), stop_event)
                return False, "lease_busy"
            log(slot_id, f"[pool] Leased TG {tg_acct['id']} for {_cbot}")

            clog = lambda m, _id=tg_acct["id"], _b=_cbot: print(f"[tg:{_id}:{_b}] {m}", flush=True)
            if _stopped():
                raise RuntimeError("stopped")

            bot = _make_tg_bot(tg_acct, _cbot, is_headless, clog)
            ok_boot, msg_boot = _boot_bot(bot)
            if not ok_boot:
                raise RuntimeError(f"bot boot: {msg_boot}")

            # Fresh-lease orphan clear (preempt victim): the killed engine's task
            # is still live on this chat — Cancel it ONCE so choose_task starts
            # from a clean menu instead of spinning hidden (2026-10-04: 5/6 slots
            # stuck while guards protected the corpses).
            try:
                _clear = getattr(bot, "clear_orphan_task", None)
                if callable(_clear):
                    _clear()
            except Exception:
                pass

            lease_stop = threading.Event()
            lid = tg_acct["id"]

            def _beat(_stop=lease_stop, _lid=lid):
                while not _stop.wait(300):
                    try:
                        tg_manager.heartbeat(_lid)
                    except Exception:
                        break

            threading.Thread(target=_beat, daemon=True).start()

            # Profile pacing: minimum gap between task starts on the SAME Telegram
            # profile.
            #
            # THIS IS THE THROUGHPUT / ANTI-FLOOD LEVER. A drain cycle costs 6-9 SENDS:
            #   reset_to_main_menu (inside choose_task)  1-4
            #   choose_task menu navigation                2
            #   start_task / submit_cookie / mark_registered 3
            #
            # Default 12s — FAST profile, selected deliberately for max throughput:
            # 6 profiles / 12s => ~30 cycles/min total (~5/min per ACCOUNT) =>
            # ~30-45 sends/min PER ACCOUNT, at/above Telegram's practical
            # SendMessage ceiling of ~20/min. 12s is the exact gap that previously
            # produced the multi-hour FloodWaits that blocked every account
            # (observed 2026-10-01: all 6 on 3-5h waits) — expect FloodWait
            # penalties under load and let bot._sleep_flood() park the throttled
            # profile; the pool re-verifies and resumes.
            #
            # For the conservative profile (30s ≈ 2 cycles/min ≈ 14 sends/min,
            # safely under the ceiling) set INSTA_TG_PROFILE_PACING_SEC=30 — no code
            # change needed. Raising it is the ONLY safe way to add headroom; going
            # lower multiplies the ban risk.
            try:
                _pacing = float(os.environ.get("INSTA_TG_PROFILE_PACING_SEC", "12") or 12)
            except (TypeError, ValueError):
                _pacing = 12.0
            _pacing = max(0.0, _pacing)
            with _profile_pacing_lock:
                last_t = _profile_last_start.get(tg_acct["id"], 0.0)
                wait_rem = _pacing - (time.time() - last_t)
                if wait_rem > 1:
                    log(slot_id, f"[pace] {tg_acct['id']} idle {wait_rem:.1f}s "
                                 f"(start-to-start pacing {_pacing:.0f}s)")
                    time.sleep(wait_rem)
                _profile_last_start[tg_acct["id"]] = time.time()

            try:
                if not bot.choose_task(_ctask):
                    recent_err = ""
                    try:
                        for t in (bot._call("_recent_texts", 4) if hasattr(bot, "_call") else bot._recent_texts(4)):
                            if any(ph in t.lower() for ph in ("limit is reached", "hour's limit", "available this hour: 0/", "available this hour: 0 ")):
                                recent_err = t.strip()
                                break
                    except Exception:
                        pass
                    if recent_err:
                        raise RuntimeError(f"{_cbot} hourly limit reached: {recent_err} [task_unavailable:soldout]")
                    _v = getattr(bot, "last_task_verdict", None) or "hidden"
                    raise RuntimeError(f"Could not select {_ctask} in {_cbot} [task_unavailable:{_v}]")

                log(slot_id, f"[task] Selected '{_ctask}' on {_cbot} (TG {tg_acct['id']})")
                creds = bot.start_task() or {}
                if creds.get("error") == "limit_reached":
                    raise RuntimeError(f"{_cbot} hourly limit reached: {creds.get('detail', '')} [task_unavailable:soldout]")
                login = _clean_username(creds.get("login") or "")
                if not (login and _is_valid_ig_username(login)):
                    raise RuntimeError(f"{_cbot} returned no usable credentials (got {creds}) [task_unavailable:badcreds]")
                log(slot_id, f"[creds] {_cbot} issued target username: '{login}'")
            except Exception as _ce:
                if "[task_unavailable:" in str(_ce) and _ci + 1 < len(_cands):
                    log(slot_id, f"[failover] {_cbot} unavailable ({_ce}) — moving to next bot…")
                    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                                "detail": f"{_cbot} unavailable — failing over to next bot…"})
                    try:
                        bot.cancel_task()
                    except Exception:
                        pass
                    try:
                        bot.close(ok=False)
                    except Exception:
                        pass
                    try:
                        if lease_stop is not None:
                            lease_stop.set()
                    except Exception:
                        pass
                    try:
                        tg_manager.release(tg_acct["id"], ok=False)
                    except Exception:
                        pass
                    bot = None
                    tg_acct = None
                    lease_stop = None
                    continue
                raise
            # Winner: the rest of the cycle (claim pool, rename, mock 2FA,
            # submit cookie, register) runs on this bot/task.
            bot_id, task = _cbot, _ctask
            break
        else:
            raise RuntimeError("All cookie bots unavailable [task_unavailable:all]")

        # Claim an account from the pool (skip any that turn out to be checkpointed/dead)
        pool_acc = None
        if msess is not None:
            # META-LIST: the account is already claimed + logged in. Join with
            # the bot's username (no rename needed), follow, export the cookie.
            def _meta_pre_export():
                if _flow_has_2fa(bot_id, task):
                    _ms = _mock_2fa_secret()
                    log(slot_id, f"[🔑] MOCK 2FA key generated ({_ms[:4]}****); submitting to the bot…")
                    try:
                        _cd = bot.submit_2fa_key(_ms, allow_local_fallback=True)
                        log(slot_id, f"[🔑] MOCK 2FA submitted (bot code: {_cd or 'none — continuing anyway'})…")
                    except Exception as _e2:
                        log(slot_id, f"[⚠️] MOCK 2FA submit note ({_e2}) — continuing to cookie export anyway.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"Meta list: joining Instagram as {login}…"})
            pool_acc = msess.finish(
                login, creds, _follow_count(bot_id, task, default=5),
                pre_export=_meta_pre_export)
            log(slot_id, f"[meta-list] ✅ '{login}' ready — {len(pool_acc['cookies'])} char cookie, "
                         f"followed {pool_acc.get('followed', 0)}.")
        for _attempt in range(0 if msess is not None else 10):
            cand = store.pop_ig_creator_account()
            if not cand or not cand.get("cookies"):
                break
            cand_id = cand["id"]
            cand_user = cand.get("username") or cand.get("instagram_username") or "unknown"
            log(slot_id, f"[pool] Claimed IG Creator account {cand_id} (current username: '{cand_user}')")
            log(slot_id, f"⚡ [api] Changing username: '{cand_user}' -> '{login}' via direct IG Web API…")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"Fast IG username change: {cand_user} -> {login}…"})
            ok_name, name_msg = change_ig_username_fast(
                cand["cookies"], login, ua=cand.get("device_ua")
            )
            if ok_name:
                pool_acc = cand
                _ig_spam_streak[0] = 0
                _challenge_trips[0] = 0
                log(slot_id, f"✅ [api] IG username updated successfully to '{login}' in ~0.4s ({name_msg})")
                clog(f"⚡ [username] Updated Instagram username: '{cand_user}' -> '{login}' (in 0.4s)")
                break
            # The web POST is challenged (checkpoint_required). Try the MOBILE
            # transport — app UA -> Bearer -> accounts/edit_profile with a PLAIN
            # form — which renames where the web one is refused (verified live
            # 2026-10-08). Only if BOTH fail do we submit the cookie unchanged.
            if _is_ig_checkpoint_error(name_msg):
                _mcl = None
                _mob_msg = "skipped"
                try:
                    _mcl = ig_api.client_for_account(cand)
                    _ok_m, _mob_msg = _mcl.rename(login)
                except Exception as _ce:
                    _ok_m, _mob_msg = False, str(_ce)[:120]
                if _ok_m:
                    pool_acc = cand
                    _ig_spam_streak[0] = 0
                    _challenge_trips[0] = 0
                    log(slot_id, f"✅ [mobile] IG username updated to '{login}' ({_mob_msg})")
                    clog(f"⚡ [username] Updated Instagram username: '{cand_user}' -> '{login}' (mobile)")
                    break
                # Both transports refused. A LOCKED/SUSPENDED account never
                # recovers → PURGE it (never park it for 30 min). A transient
                # challenge → use the account and submit the cookie anyway.
                _locked = False
                try:
                    _locked = bool(_mcl.is_locked()) if _mcl is not None else False
                except Exception:
                    _locked = False
                if _locked:
                    log(slot_id, f"⛔ [pool] Account {cand_id} ({cand_user}) is SUSPENDED/locked "
                                 f"({name_msg[:50]}) — purging (not parking).")
                    try:
                        store.delete_record(cand_id)
                    except Exception:
                        pass
                    if cand.get("session_file") and os.path.exists(cand["session_file"]):
                        try:
                            os.remove(cand["session_file"])
                        except Exception:
                            pass
                    emit_event({"type": "account_deleted", "account_id": cand_id})
                    emit_event({"type": "accounts_updated"})
                    continue
                pool_acc = cand
                pool_acc["_rename_pending"] = login
                _challenge_trips[0] = 0
                log(slot_id, f"↻ [pool] Rename '{login}' failed on web+mobile for {cand_id} "
                             f"({name_msg[:50]} | {_mob_msg[:60]}) — submitting the cookie anyway.")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                            "detail": "Rename failed (web+mobile) — submitting the cookie anyway."})
                break
            # If suspended / banned / session dead, permanently delete from list and try next account
            if _is_account_dead_error(name_msg):
                log(slot_id, f"⚠️ [pool] Account {cand_id} ({cand_user}) is dead/banned on IG ({name_msg}) — permanently removing from accounts list.")
                store.delete_record(cand_id)
                if cand.get("session_file") and os.path.exists(cand["session_file"]):
                    try:
                        os.remove(cand["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": cand_id})
                emit_event({"type": "accounts_updated"})
                continue
            else:
                # FAILED means FAILED: a rejected rename (spam / taken / invalid)
                # removes the account from the pool — never retried / re-logged-in.
                # Safety: if MANY fail in a ROW the IP itself is flagged, so STOP
                # the drain instead of emptying the whole pool.
                _ig_spam_streak[0] += 1
                if _ig_spam_streak[0] >= _IG_SPAM_STOP:
                    raise RuntimeError(
                        f"IG rename failed on {_ig_spam_streak[0]} consecutive accounts "
                        f"(last: {name_msg[:60]}) — IP-level rate-limit; pausing the drain.")
                log(slot_id, f"[pool] Rename '{login}' FAILED for {cand_id} ({name_msg[:80]}) — "
                             f"removing from pool ({_ig_spam_streak[0]}/{_IG_SPAM_STOP}).")
                store.delete_record(cand_id)
                if cand.get("session_file") and os.path.exists(cand["session_file"]):
                    try:
                        os.remove(cand["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": cand_id})
                emit_event({"type": "accounts_updated"})
                continue

        if not pool_acc:
            raise RuntimeError("Failed to obtain a valid working IG Creator account from pool")

        acc_id = pool_acc["id"]

        # MOCK 2FA mode (toggle ON): follow (browser) + mock key, then cookie.
        # Toggle OFF = legacy path (stored cookie straight to the bot).
        # BROWSERLESS FAST PATH: when the account already satisfied the follow
        # requirement at creation, no browser opens at all — rename already
        # went through the direct API, the 2FA key is mock (no IG touch), and
        # the STORED cookie is submitted. The browser (follow + fresh export)
        # runs ONLY when follows are still owed.
        submit_cookie_str = pool_acc["cookies"]
        if msess is not None:
            pass    # cookie already exported by MetaListSession.finish()
        elif ig_api.api_mode():
            # ---- BROWSERLESS path (IG_API_MODE=1): follow + real 2FA + stored cookie
            _need = _follow_count(bot_id, task, default=5)
            if pool_acc.get("_rename_pending"):
                # Web + mobile rename both failed: the cookie would be submitted
                # under the OLD username and the bot would reject it. Don't.
                log(slot_id, f"⚠️ [pool][api] rename to '{login}' failed for {pool_acc['id']} — "
                             f"not submitting the cookie under the old username; moving on.")
                try:
                    store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                except Exception:
                    pass
                _rp = pool_acc["id"]
                pool_acc = None
                raise RuntimeError(f"rename failed (api, next account): {_rp}")
            try:
                submit_cookie_str = _pool_api_2fa_and_export_cookie(
                    slot_id, bot, bot_id, pool_acc, login,
                    follow_count=_need, task=task)
            except IGDeadEnd as _de:
                _lmsg = str(_de).lower()
                # Follow issues (rate limits, toasts) are NOT a dead session.
                # RESTORE the account so it can retry later instead of purging it.
                if "follow" in _lmsg:
                    log(slot_id, f"⚠️ [pool][api] follow blocked ({_de}) — restoring "
                                 f"account {pool_acc['id']} (NOT purging) and moving on.")
                    try:
                        store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                    except Exception:
                        pass
                    pool_acc = None
                    raise RuntimeError(f"follow blocked (api, next account): {_de}")
                log(slot_id, f"⚠️ [pool][api] DEAD session ({_de}) — purging account "
                             f"{pool_acc['id']} and moving to the next.")
                try:
                    store.delete_record(pool_acc["id"])
                except Exception:
                    pass
                if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
                    try:
                        os.remove(pool_acc["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": pool_acc["id"]})
                emit_event({"type": "accounts_updated"})
                pool_acc = None
                raise RuntimeError(f"pooled IG dead session (api, next account): {_de}")
            except Exception as _exc:
                log(slot_id, f"⚠️ [pool][api] step failed ({_exc}) — not submitting the "
                             f"cookie; moving on.")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                            "detail": "API step failed — not submitting the cookie; moving on."})
                try:
                    store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                except Exception:
                    pass
                pool_acc = None
                raise RuntimeError(f"API step failed (next account): {_exc}")
        elif cookie_2fa:
            _need = _follow_count(bot_id, task, default=5)
            try:
                _have = int(pool_acc.get("followed") or 0)
            except Exception:
                _have = 0
            if _need > 0 and _have >= _need and not pool_acc.get("_rename_pending"):
                log(slot_id, f"[⚡] Follows already satisfied ({_have}/{_need}) — NO browser: "
                             f"mock key + stored cookie submit…")
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                            "detail": f"Follows done at creation ({_have}/{_need}) — browserless submit…"})
                if _flow_has_2fa(bot_id, task):
                    _mock_secret = _mock_2fa_secret()
                    log(slot_id, f"[🔑] MOCK 2FA key generated ({_mock_secret[:4]}****); submitting to the bot…")
                    try:
                        _code = bot.submit_2fa_key(_mock_secret, allow_local_fallback=True)
                        log(slot_id, f"[🔑] MOCK 2FA submitted (bot code: {_code or 'none — continuing anyway'})…")
                    except Exception as _exc:
                        log(slot_id, f"[⚠️] MOCK 2FA submit note ({_exc}) — continuing to cookie submit anyway.")
                # else: PayGo expects only the cookie — no key submit at all.
            else:
                log(slot_id, "[🔐] MOCK 2FA mode ON — follow + mock key, then cookie submit…")
                try:
                    submit_cookie_str = _pool_enable_2fa_and_export_cookie(
                        slot_id, bot, bot_id, pool_acc, login, is_headless, worker_factory,
                        follow_count=_need, rename_to=pool_acc.get("_rename_pending"))
                except IGDeadEnd as _de:
                    _lmsg = str(_de).lower()
                    # Follow issues (rate limits, toasts) are NOT a dead session.
                    # RESTORE so it can retry later, do NOT purge it from the pool.
                    if "follow" in _lmsg:
                        log(slot_id, f"⚠️ [pool] follow blocked ({_de}) — restoring "
                                     f"account {pool_acc['id']} (NOT purging) and moving on.")
                        try:
                            store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                        except Exception:
                            pass
                        pool_acc = None
                        raise RuntimeError(f"follow blocked (next account): {_de}")
                    # DEAD session / visitor / risky gate — a hard dead end. PURGE the
                    # account and move to the NEXT one immediately: do NOT waste a
                    # stored-cookie submit + verdict round-trip on a dead session
                    # (operator: "if one closes, move to the next fast").
                    log(slot_id, f"⚠️ [pool] DEAD session ({_de}) — purging account "
                                 f"{pool_acc['id']} and moving to the next.")
                    try:
                        store.delete_record(pool_acc["id"])
                    except Exception:
                        pass
                    if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
                        try:
                            os.remove(pool_acc["session_file"])
                        except Exception:
                            pass
                    emit_event({"type": "account_deleted", "account_id": pool_acc["id"]})
                    emit_event({"type": "accounts_updated"})
                    pool_acc = None
                    raise RuntimeError(f"pooled IG dead session (next account): {_de}")
                except Exception as _exc:
                    # Mock-2FA step failed for a non-dead-end reason (follow flake,
                    # submit error, cookie export). The account may be fine, so
                    # restore it and move to the next cycle (do NOT submit a cookie
                    # from a half-done step).
                    log(slot_id, f"⚠️ [pool] 2FA step failed ({_exc}) — NOT submitting the "
                                 f"cookie (bot is at the 2FA-key prompt); moving on.")
                    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                                "detail": "2FA step failed — not submitting the cookie; moving on."})
                    try:
                        store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                    except Exception:
                        pass
                    pool_acc = None
                    raise RuntimeError(f"2FA step failed (next account): {_exc}")

        # Submit cookie to the winning bot
        log(slot_id, f"[submit] Submitting {len(submit_cookie_str)} chars IG cookie string to {bot_id}…")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                    "detail": f"Submitting IG cookie to {bot_id}…"})
        ok_cookie, reply = bot.submit_cookie(submit_cookie_str, timeout=25)
        if not ok_cookie:
            if _is_account_dead_error(reply):
                log(slot_id, f"⚠️ [pool] {bot_id} rejected dead/banned account {acc_id} ({reply[:100]}) — permanently removing from accounts list.")
                store.delete_record(acc_id)
                if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
                    try:
                        os.remove(pool_acc["session_file"])
                    except Exception:
                        pass
                emit_event({"type": "account_deleted", "account_id": acc_id})
                emit_event({"type": "accounts_updated"})
            else:
                store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError(f"{bot_id} rejected cookie: {reply[:200]}")

        log(slot_id, f"✅ [{bot_id}] Cookie accepted by {bot_id} — confirming registration…")

        # Register confirm (retry up to 3 times to ensure receipt)
        submitted = False
        for _rc in range(3):
            submitted = bot.mark_registered()
            if submitted:
                break
            log(slot_id, f"register receipt not seen (attempt {_rc+1}/3) — retrying confirm tap…")
            time.sleep(0.6)
        if not submitted:
            store.restore_ig_creator_account(acc_id, rotate=True)
            pool_acc = None
            raise RuntimeError(f"{bot_id} registration not confirmed — not recording Submitted")

        # Success: consume record from store so it cannot be double-spent
        store.delete_record(acc_id)
        if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
            try:
                os.remove(pool_acc["session_file"])
            except Exception:
                pass
        log(slot_id, f"[pool] Account {acc_id} successfully consumed and removed from pool.")
        pool_acc = None

        from tg_stats import record_submission
        rec_id = f"tg_{int(time.time()*1000)}"
        # POOL DRAIN gets its OWN counter so it never inflates the normal
        # `paygo`/`taskly` (browser-creator) number — mirrors taskly2fa/fastpay2fa.
        _b = (bot_id or "paygo").lower()
        _counter = ("paygo_pool" if _b == "paygo"
                    else "taskly_cookie_pool" if _b == "taskly"
                    else _b)
        record_submission(_counter)
        emit_event({"type": "account_submitted", "pipeline": "telegram",
                    "tg_account": tg_acct["id"], "tg_bot": bot_id or "paygo",
                    "account_id": rec_id})
        emit_event({"type": "account_deleted", "account_id": acc_id})
        emit_event({"type": "accounts_updated"})
        log(slot_id, f"🎉 [SUBMITTED] Registration confirmed (+ $0.02) -> record {rec_id} for user '{login}'")
        ok = True
        return True, rec_id

    except Exception as exc:
        detail = str(exc)
        # Telegram throttles per ACCOUNT, not per slot. Without this the slot
        # returned instantly and the loop leased the next account ~2s later, so
        # every account kept re-arming its own FloodWait and the whole pool
        # churned through hundreds of pointless retries (observed: "A wait of
        # 483 / 388 / 245s required" on every slot, seconds apart). Sleep the
        # penalty out BEFORE restoring the lease, and report it as throttled so
        # the slot backs off instead of hammering.
        _fw = 0
        if bot is not None:
            try:
                _fw = bot._sleep_flood(exc, "cookie pool drain")
            except Exception:
                _fw = 0
        if _fw:
            log(slot_id, f"⏳ Telegram rate limit — slept {_fw}s before retrying.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "throttled",
                        "detail": f"Telegram FloodWait — waited {_fw}s (account throttled)."})
            return False, "floodwait"
        # A locked session is a RESOURCE problem, not a task failure: the sqlite
        # file is still held (usually by a client that failed to boot, so
        # disconnect() never ran). Drop the handle NOW so the next lease of this
        # account opens cleanly instead of re-locking. Business logic untouched.
        if "database is locked" in detail.lower() or "database is locked" in str(exc).lower():
            if bot is not None:
                try:
                    bot.disconnect()          # releases the sqlite handle
                except Exception:
                    pass
            log(slot_id, "🔓 Session file was locked — released the handle; "
                         "the account is free to be leased again.")
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "lock_released",
                        "detail": "Session DB lock released — account returned to the pool."})
        # A DEAD session must take the account OUT of rotation. The cookie drain
        # imported _is_tg_session_lost but never called it, so a genuinely
        # revoked profile stayed enabled: the pool re-leased it within ~3s and
        # failed again, forever — a tight loop that spammed "session lost" and
        # starved the slot. tg_coupled already disables; this path was missing it.
        # GUARD (2026-10-07): _is_tg_session_lost matches "not logged in" —
        # an IG-dead-session error ("pooled IG session not logged in (home
        # feed)") contains that text but says NOTHING about Telegram (the TG
        # lease booted + started the task fine). Only disable on TG-attributed
        # errors, never on IG/pool/cookie ones — that false positive disabled
        # a healthy tg_6 and wedged the drain into a hot "No logged-in" loop.
        _detail_low = detail.lower()
        _is_ig_attributed = any(k in _detail_low for k in (
            "pooled ig", "ig session", "ig dead", "instagram",
            "home feed", "cookie", "visitor", "block/restrict"))
        if _is_tg_session_lost(detail) and not _is_ig_attributed:
            try:
                bot.close(ok=False)          # release the sqlite handle first
            except Exception:
                pass
            if tg_acct:
                try:
                    tg_manager.disable(
                        tg_acct["id"],
                        reason="dead Telegram session (cookie pool drain)")
                    log(slot_id, f"🔒 {tg_acct['id']} Telegram session is dead — "
                                 f"DISABLED so the pool stops re-leasing it.")
                    emit_event({"type": "slot_event", "slot_id": slot_id,
                                "status": "disabled",
                                "detail": f"{tg_acct['id']} disabled (dead Telegram session)."})
                except Exception:
                    pass
            if pool_acc is not None:
                try:
                    store.restore_ig_creator_account(pool_acc["id"], rotate=True)
                except Exception:
                    pass
            return False, "session_lost"
        log(slot_id, f"FAILED: {exc}")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "error",
                    "detail": f"Cookie pool drain error: {exc}"})
        # If the failure itself is a dead/banned signal (raised rather than
        # returned by an explicit branch), take the account OUT of the pool —
        # restoring it just makes the next slot re-claim and fail on it forever.
        if pool_acc is not None and _is_account_dead_error(detail) and not _is_ig_checkpoint_error(detail):
            log(slot_id, f"⚠️ [pool] Account {pool_acc['id']} is dead/banned ({detail[:90]}) — permanently removing.")
            try:
                store.delete_record(pool_acc["id"])
            except Exception:
                pass
            if pool_acc.get("session_file") and os.path.exists(pool_acc["session_file"]):
                try:
                    os.remove(pool_acc["session_file"])
                except Exception:
                    pass
            emit_event({"type": "account_deleted", "account_id": pool_acc["id"]})
            emit_event({"type": "accounts_updated"})
            pool_acc = None
        if pool_acc is not None:
            try:
                store.restore_ig_creator_account(pool_acc["id"], rotate=True)
            except Exception:
                pass
        if bot is not None:
            try:
                bot.cancel_task()
            except Exception:
                pass
        # Backoff: wait-states park instead of hot-spinning (observed: "No
        # logged-in Telegram profile available" every ~0.5s forever after a
        # false disable). Park ~15s stop-aware (slot-staggered) so the log
        # stays readable and TG/IG are not hammered while unavailable.
        _dl = detail.lower()
        if ("no logged-in telegram profile" in _dl or "lease_busy" in _dl
                or "no_pool_accounts" in _dl or "all telegram profiles busy" in _dl
                or "all cookie bots unavailable" in _dl or "ip-level rate-limit" in _dl):
            _sleep_until(time.time() + 15 + (slot_id % 6), stop_event)
        return False, detail
    finally:
        if msess is not None:
            try:
                msess.close()      # restores an unfinished claim + closes the browser
            except Exception:
                pass
        try:
            if lease_stop is not None:
                lease_stop.set()
        except Exception:
            pass
        if tg_acct:
            try:
                # NOTE: `_profile_last_start` is stamped once, at task start
                # (above), so pacing really is start-to-start as documented.
                # Re-stamping here at release would make the effective window
                # `cycle_time + pacing` (~2x the configured value) — that is
                # what pinned each profile to ~60s at a 30s setting.
                tg_manager.release(tg_acct["id"], ok=ok,
                                   account_id=rec_id if ok else None)
            except Exception:
                pass
        if bot is not None:
            try:
                bot.close(ok=ok)
            except Exception:
                pass


def _flow_tag(bot_target, task):
    """The flow tag for a (bot, task) — 'cookie' | 'cookie_2fa' | '2fa' | None."""
    try:
        import tg_tasks
        tid, _ = tg_tasks.resolve(bot_target, task)
        if tid:
            return (tg_tasks.TASKS.get(str(bot_target), {}).get(tid) or {}).get("flow")
    except Exception:
        pass
    return None


def _follow_count(bot_target, task, default=2):
    """Per-task suggested-follow count (bot mandate); default 2."""
    try:
        import tg_tasks
        tid, _ = tg_tasks.resolve(bot_target, task)
        if tid:
            spec = (tg_tasks.TASKS.get(str(bot_target), {}) or {}).get(tid) or {}
            n = spec.get("follow")
            if n is not None:
                return max(0, int(n))
    except Exception:
        pass
    return default


def run_cookie_cycle_once(slot_id=91, worker_factory=None, is_headless=False,
                          captcha_mode="extension", mail_provider="mailtd",
                          stop_event=None, add_email=False,
                          tg_task=None, tg_bot="paygo", use_ig_pool=False,
                          cookie_2fa=False, fallback=False):
    """Run ONE cookie-family task cycle. Returns ``(ok, detail)``.

    Parametrized so it serves BOTH cookie flows:
      * PayGo  ``cookie``      — ig_join → cookie_export → submit_cookie
      * Taskly ``cookie_2fa``  — ig_join → 2fa → cookie_export → submit_cookie
    The step list comes from ``tg_flows.resolve_steps(tg_bot, task)`` (data).

    When ``use_ig_pool=True``, drains pre-created accounts from the IG Creator
    pool instead of creating fresh Meta accounts in the browser.

    ``add_email`` is accepted for call-site stability but IGNORED: the cookie
    flows have no email step (see ``tg_flows.FLOWS``). Import-safe for
    ``worker.py`` (lazy ``AISlotWorker`` import — no import cycle).
    """
    task = tg_task or COOKIE_TASK
    bot_id = str(tg_bot or "paygo")

    if use_ig_pool:
        return _run_pool_drain_cycle(
            slot_id=slot_id, is_headless=is_headless,
            stop_event=stop_event, tg_task=task, tg_bot=bot_id,
            cookie_2fa=cookie_2fa, worker_factory=worker_factory,
            fallback=fallback
        )
    # NOTE: the winner's flow + runner are built AFTER the failover loop
    # (below), so a failover to another bot switches flow with it.
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

    bot = None
    tg_acct = None
    lease_stop = None
    t0 = None
    ok = False
    rec_id = None
    worker = None
    runner = None

    def window_left():
        return TASK_WINDOW - (time.monotonic() - t0) if t0 else TASK_WINDOW

    def require_window(phase):
        left = window_left()
        log(slot_id, f"[TTL] {phase} — {max(0, int(left))}s left of ~{TASK_WINDOW}s")
        if left <= 0:
            raise RuntimeError(f"Bot task window exceeded before {phase}")

    try:
        # -- Step 1: TG lease + task pre-flight check (fail before Meta) --
        # Failover: candidates are tried in priority order and the first bot
        # whose task is available wins. No Meta account is created until one
        # bot yields creds, so failed candidates burn nothing. Classic labels
        # here (ig_join steps) — pool aliases have no classic implementation.
        _cands = cookie_candidates(bot_id, task, pool_mode=False) if fallback else [(bot_id, task)]
        if fallback and len(_cands) > 1:
            log(slot_id, "[failover] ON — order: " + " → ".join(
                f"{_b}" for _b, _t in _cands))
        login = None
        for _ci, (_cbot, _ctask) in enumerate(_cands):
            if _stopped():
                return False, "stopped"
            if _ci > 0:
                log(slot_id, f"[failover] trying next bot: {_cbot} / {_ctask}…")
            if not tg_manager.usable():
                raise RuntimeError("No logged-in Telegram profile available")
            tg_acct = tg_manager.acquire(timeout=15, bot=_cbot)
            if not tg_acct:
                raise RuntimeError("No Telegram profile slot available [task_unavailable:busy]")
            log(slot_id, f"leased {tg_acct['id']} for {_cbot} (balance not probed — dashboard Get Balance is the source)")

            clog = lambda m, _id=tg_acct["id"], _b=_cbot: print(f"[tg:{_id}:{_b}] {m}", flush=True)
            if _stopped():
                raise RuntimeError("stopped")
            bot = _make_tg_bot(tg_acct, _cbot, is_headless, clog)
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

            # Clear an orphan ACTIVE task left by a dead run (killed engine / a
            # previous failed cycle) so choose_task starts from a CLEAN menu instead
            # of reporting [task_unavailable:hidden] while the task IS available
            # (operator 2026-10-07).
            try:
                _clear = getattr(bot, "clear_orphan_task", None)
                if callable(_clear):
                    _clear()
            except Exception:
                pass

            try:
                if not bot.choose_task(_ctask):
                    _v = getattr(bot, "last_task_verdict", None) or "hidden"
                    raise RuntimeError(f"Could not select {_ctask} in {_cbot} [task_unavailable:{_v}]")
                creds = bot.start_task() or {}
                if creds.get("error") == "limit_reached":
                    raise RuntimeError(f"{_cbot} hourly limit reached: {creds.get('detail', '')} [task_unavailable:soldout]")
                login = _clean_username(creds.get("login") or "")
                if not (login and _is_valid_ig_username(login) and creds.get("password")):
                    raise RuntimeError(f"{_cbot} returned no usable credentials (got {creds}) [task_unavailable:badcreds]")
                t0 = time.monotonic()  # bot TTL anchor: counts from task Start
                creds["login"] = login
                cname = _sanitize_name(creds.get("first_name") or "")
                clog(f"creds: name='{creds.get('first_name')}' login='{login}'")
            except Exception as _ce:
                if "[task_unavailable:" in str(_ce) and _ci + 1 < len(_cands):
                    log(slot_id, f"[failover] {_cbot} unavailable ({_ce}) — moving to next bot…")
                    emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                                "detail": f"{_cbot} unavailable — failing over to next bot…"})
                    try:
                        bot.cancel_task()
                    except Exception:
                        pass
                    try:
                        bot.close(ok=False)
                    except Exception:
                        pass
                    try:
                        if lease_stop is not None:
                            lease_stop.set()
                    except Exception:
                        pass
                    try:
                        tg_manager.release(tg_acct["id"], ok=False)
                    except Exception:
                        pass
                    bot = None
                    tg_acct = None
                    lease_stop = None
                    continue
                raise
            # Winner: everything downstream (Meta, IG, submit) runs on it.
            bot_id, task = _cbot, _ctask
            break
        else:
            raise RuntimeError("All cookie bots unavailable [task_unavailable:all]")

        # Winner's flow + runner (built AFTER creds so a failover switches flow).
        try:
            from tg_flows import resolve_steps as _resolve_steps, needs_2fa as _needs_2fa
            flow_steps = _resolve_steps(bot_id, task)
            flow_needs_2fa = _needs_2fa(_flow_tag(bot_id, task))
        except Exception:
            flow_steps = ["ig_join", "cookie_export", "submit_cookie"]
            flow_needs_2fa = False

        if add_email:
            log(slot_id, "[i] 'Extra email after 2FA + password' ignored — cookie tasks "
                         f"have no email step (steps: {' → '.join(flow_steps)}).")

        worker = worker_factory(slot_id=slot_id, is_headless=is_headless)
        runner = MetaInstaRunner(
            worker, twofa=flow_needs_2fa, telegram=False, tg_task=task,
            captcha_mode=captcha_mode, mail_provider=mail_provider, target="telegram",
        )
        if os.path.exists(SELFIE_PATH):
            runner.selfie_path = SELFIE_PATH

        runner.tg_creds = creds
        runner.new_username = login
        runner.new_password = creds["password"]
        if cname:
            runner.name = cname
        runner.tg_id = tg_acct["id"]
        runner.tg_bot = bot_id

        # -- Step 2: Meta Creation ----------------------------------------
        if _stopped():
            raise RuntimeError("stopped")
        emit_event({"type": "slot_event", "slot_id": slot_id, "status": "launching",
                    "detail": "Cookie cycle: Meta creation…"})
        runner._install_screenshot_hooks()
        runner._launch()
        runner.open_mail()
        runner.meta_signup()
        if not runner.ensure_meta_verified():
            raise RuntimeError("Meta account verification not confirmed on auth.meta.com — aborting before Instagram to prevent phone wall")
        log(slot_id, f"Meta created ({runner.email})")

        # -- Flow steps (data-driven via tg_flows) ------------------------
        # Each step is a callable keyed by the names in tg_flows.FLOWS[flow].
        # A new step = one entry here + one in the flow's "steps" list.
        _has_follow_step = "follow" in flow_steps

        def _step_ig_join(ctx):
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"IG join with bot user ({login})…"})
            runner.ig_login()
            runner.ig_click_meta_card()
            runner.ig_complete_join()
            if runner.ig_username:
                runner.new_username = runner.ig_username
            # Follow count is DATA (per task): PayGo's cookie task mandates 5
            # subscriptions; Taskly's cookie_2fa keeps the default 2. A count >2
            # is done human-like (random target, scrolls, jittered pauses).
            if _has_follow_step:
                # This flow carries its own `follow` step — only dismiss here.
                runner.ig_dismiss_onboarding(follow=False)
            else:
                follow_n = _follow_count(bot_id, task)
                runner.ig_dismiss_onboarding(follow=(follow_n <= 2))
                if follow_n > 0:
                    runner.ig_follow_suggested(max_follows=follow_n, humanize=(follow_n > 2))
            ig_page = runner._ig_tab()
            if runner._has_human_check(ig_page):
                raise RuntimeError("Instagram human checkpoint on fresh account — dead end")
            # Pre-Accounts-Center warm-up (fresh accounts only): a brand-new
            # account that jumps straight to Settings/Accounts Center within
            # seconds is IG's STRONGEST automation tell — IG drops the session
            # and redirects to /accounts/login (the "fresh-account login wall",
            # seen live 2026-10-07). Browse the feed like a human FIRST.
            # Env: INSTA_PRE_AC_WARMUP_SEC (0 disables; default 15s).
            try:
                _warm = float(os.environ.get("INSTA_PRE_AC_WARMUP_SEC", "15") or 15)
            except Exception:
                _warm = 15.0
            if _warm > 0 and not _stopped():
                import random as _rnd
                emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                            "detail": f"Pre-Accounts-Center warm-up — browsing the feed ~{int(_warm)}s…"})
                _end = time.time() + _warm
                while time.time() < _end and not _stopped():
                    try:
                        runner._touch_scroll(ig_page, dy=_rnd.randint(300, 750))
                    except Exception:
                        pass
                    try:
                        ig_page.wait_for_timeout(_rnd.randint(1200, 3200))
                    except Exception:
                        break

        def _step_follow(ctx):
            # Optional `follow` step (only for a flow that lists it); count is
            # per-task DATA (5 for the cookie tasks).
            follow_n = _follow_count(bot_id, task)
            if follow_n <= 0:
                log(slot_id, "[👥] Follow step skipped — this task requires no follows.")
                return
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "onboarding",
                        "detail": f"Following {follow_n} suggested accounts on {login}…"})
            try:
                runner._ig_follow_done = False
            except Exception:
                pass
            n = runner.ig_follow_suggested(max_follows=follow_n, humanize=(follow_n > 2))
            log(slot_id, f"[👥] Follow step done — {n}/{follow_n} on {login}.")

        def _step_2fa(ctx):
            # Taskly's cookie task asks for the 2FA KEY before the cookie:
            # set up 2FA on IG, submit the key to the bot, read the code back,
            # confirm it in Accounts Center. (PayGo's cookie flow skips this.)
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": f"IG 2FA setup + {bot_id} submit…"})
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

        def _step_cookie_export(ctx):
            try:
                jar = runner.w.context.cookies()
            except Exception as exc:
                raise RuntimeError(f"cookie jar unreadable: {exc}")
            ig_cookies = [c for c in jar if "instagram.com" in str(c.get("domain", ""))]
            names = {c.get("name") for c in ig_cookies}
            if "sessionid" not in names:
                raise RuntimeError(
                    f"no IG sessionid after join (have: {sorted(names)}) — refusing to submit")
            cookie_str = "; ".join(
                f"{c['name']}={c['value']}" for c in ig_cookies
                if c.get("name") and c.get("value") is not None)
            log(slot_id, f"cookie: {len(ig_cookies)} IG cookies, {len(cookie_str)} chars, "
                         f"sessionid={'sessionid' in cookie_str}")
            if len(cookie_str) < 100:
                raise RuntimeError("cookie string too short (<100 chars)")
            ctx["cookie_str"] = cookie_str

        def _step_submit_cookie(ctx):
            nonlocal ok, rec_id
            cookie_str = ctx.get("cookie_str") or ""
            emit_event({"type": "slot_event", "slot_id": slot_id, "status": "twofa",
                        "detail": f"Submitting IG cookie to {bot_id}…"})
            ok_cookie, reply = bot.submit_cookie(cookie_str, timeout=25)
            if not ok_cookie:
                raise RuntimeError(f"{bot_id} rejected the cookie: {reply[:200]}")
            require_window("register confirm")
            submitted = bot.mark_registered()
            if not submitted:
                log(slot_id, "register receipt not seen — one more tap…")
                submitted = bot.mark_registered()
            if not submitted:
                raise RuntimeError(f"{bot_id} registration not confirmed — not recording Submitted")
            runner.tg_submitted = submitted
            from tg_stats import record_submission
            rec_id = f"tg_{int(time.time()*1000)}"
            record_submission(bot_id or "paygo")
            runner.last_record_id = rec_id
            emit_event({"type": "account_submitted", "pipeline": "telegram",
                        "tg_account": tg_acct["id"], "tg_bot": bot_id or "paygo",
                        "account_id": rec_id})
            log(slot_id, f"SUBMITTED — user '{login}' (record {rec_id})")
            ok = True

        _STEPS = {
            "ig_join": _step_ig_join,
            "2fa": _step_2fa,
            "follow": _step_follow,
            "cookie_export": _step_cookie_export,
            "submit_cookie": _step_submit_cookie,
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
                    "detail": f"Cookie cycle error: {exc}"})
        if bot is not None:
            try:
                bot.cancel_task()
            except Exception:
                pass
        # Wait-states park instead of hot-spinning (mirrors the pool drain).
        _dl = detail.lower()
        if ("no logged-in telegram profile" in _dl or "lease_busy" in _dl
                or "no_pool_accounts" in _dl or "all telegram profiles busy" in _dl
                or "no telegram profile slot available" in _dl
                or "all cookie bots unavailable" in _dl or "ip-level rate-limit" in _dl):
            _sleep_until(time.time() + 15 + (slot_id % 6), stop_event)
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
    ap = argparse.ArgumentParser(description="One-shot cookie-family task cycle")
    ap.add_argument("--slot", type=int, default=91)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--captcha", default="extension", choices=("extension", "audio"))
    ap.add_argument("--mail", default="mailtd")
    ap.add_argument("--task", default=COOKIE_TASK,
                    help='task label, e.g. "🍪 Create Inst (No mail)"')
    ap.add_argument("--bot", default="paygo", help="bot id: paygo | taskly")
    ap.add_argument("--use-ig-pool", action="store_true",
                    help="Drain pre-created accounts from the IG Creator pool")
    ap.add_argument("--cookie-2fa", action="store_true",
                    help="NEW PayGo cookies protocol: submit 2FA (wait OTP) then cookie")
    ap.add_argument("--tg-fallback", action="store_true",
                    help="Try cookie bots in dashboard priority order, first available wins")
    args = ap.parse_args()
    ok, _detail = run_cookie_cycle_once(
        slot_id=args.slot, is_headless=args.headless,
        captcha_mode=args.captcha, mail_provider=args.mail,
        tg_task=args.task, tg_bot=args.bot, use_ig_pool=args.use_ig_pool,
        cookie_2fa=args.cookie_2fa, fallback=args.tg_fallback)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
