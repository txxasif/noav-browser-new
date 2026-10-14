"""NordVPN server swap for IP-throttled Meta/IG runs (Canada / USA / Singapore pool).

The NordVPN tunnel is system-wide, so one swap affects every running slot. That is
why a swap works like this, at any Parallel value:

* a swap is *requested* (by an IP-type failure streak, a Meta checkpoint block, or
  the server being in use too long);
* new accounts wait at ``enter_cycle()`` while the running ones finish;
* when nothing is running, the swap runs and the waiting accounts continue on the
  new server. If running accounts are still busy after ``NORD_ROTATE_DRAIN_S``
  seconds, the swap is forced;
* the next city is picked from its own record: cities whose accounts hit fewer IP
  failures are picked more often, but every city can still be picked.
* if every connect attempt fails, new accounts are held back, so nothing runs on the
  real IP.

Enable with ``NORD_ROTATE=1``.
"""
from __future__ import annotations

import atexit
import json
import os
import random
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from collections import Counter, defaultdict, deque
from typing import Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cities as the NordVPN CLI names them (``nordvpn cities CA`` / ``US``; Singapore has one city).
POOL: list[tuple[str, str]] = (
    [("Canada", c) for c in ("Calgary", "Montreal", "Toronto", "Vancouver")]
    + [("Singapore", "Singapore")]
    + [("United_States", c) for c in (
        "Albuquerque", "Anchorage", "Ashburn", "Atlanta", "Baltimore", "Billings",
        "Boise", "Boston", "Buffalo", "Burlington", "Charleston", "Charlotte",
        "Cheyenne", "Chicago", "Columbus", "Dallas", "Denver", "Des_Moines", "Detroit",
        "Fargo", "Honolulu", "Houston", "Huntington", "Indianapolis", "Jackson",
        "Kansas_City", "Las_Vegas", "Lewiston", "Little_Rock", "Los_Angeles",
        "Louisville", "McAllen", "Miami", "Milwaukee", "Minneapolis", "Montgomery",
        "Nashua", "Nashville", "New_Haven", "New_Orleans", "New_York", "Oklahoma_City",
        "Omaha", "Phoenix", "Pittsburgh", "Portland", "Providence", "Saint_Louis",
        "Salt_Lake_City", "San_Francisco", "Seattle", "Sioux_Falls", "Trenton",
        "Wichita", "Wilmington")]
)

# Minimum seconds between two swap requests, so a block does not make us hop endlessly.
COOLDOWN_S = 60.0
CONNECT_TIMEOUT_S = 120
CONNECT_ATTEMPTS = 3
RECOVER = "recover after a failed swap"

# Failure text that points at the IP, taken from the run logs. The Instagram
# "Can't find account" / "no sessionid" failures are NOT here: they are an account
# provisioning problem, and a new server does not fix them.
IP_FAIL_MARKERS = (
    "throttled",                                  # meta.ai click did not leave meta.ai
    "Oops! Something went wrong",                 # Meta error page on the code screen
    "429",                                        # rate limited
    "Try again later",
    "automated queries",
    "MetaCheckpointBlocked",
    "Mobile number required",                     # phone wall
    "Meta confirmation code screen not found",
    "Meta confirmation code not received",        # a blocked IP gets no mail either
    # 8 fresh random-hex usernames all "taken" is not a collision: Instagram is
    # soft-blocking this IP, so a new server is the fix.
    "Username not accepted by Instagram",
)

_state = threading.Lock()        # guards the fields below
_swap_lock = threading.Lock()    # one swap at a time
_active = 0                      # accounts running right now
_pending: Optional[str] = None   # swap requested, waiting for running accounts
_halted = False                  # last swap failed on every city: hold new accounts
_last_city: Optional[tuple[str, str]] = None
_last_at = 0.0                   # monotonic time of the last successful connect
_ip_streak = 0
_stats: dict = {}                # city -> [ok_accounts, ip_fail_accounts]
_window: deque = deque(maxlen=20)      # per finished account: True = IP-type failure
_any_window: deque = deque(maxlen=20)  # per finished account: True = did not complete (any cause)
_episode: Optional[dict] = None    # the server currently in use, with its counts so far


def stats_path() -> str:
    """JSON-lines file with one record per server episode. Override with NORD_ROTATE_STATS."""
    return os.environ.get("NORD_ROTATE_STATS") or os.path.join(ROOT_DIR, "nord_rotate_stats.jsonl")


def enabled() -> bool:
    return os.environ.get("NORD_ROTATE", "0").strip().lower() in ("1", "true", "on", "yes")


def max_age_s() -> float:
    """How long one server may stay in use before the next account moves on (0 = off)."""
    try:
        return max(0.0, float(os.environ.get("NORD_ROTATE_MAX_AGE_MIN", "0")) * 60)
    except ValueError:
        return 0.0


def streak_needed() -> int:
    try:
        return max(1, int(os.environ.get("NORD_ROTATE_STREAK", "2")))
    except ValueError:
        return 2


def window_size() -> int:
    """How many finished accounts the failure-share rule looks at."""
    try:
        return max(2, int(os.environ.get("NORD_ROTATE_WINDOW", "20")))
    except ValueError:
        return 20


def fail_share() -> float:
    """Share of failed accounts in the window that queues a swap (0.5 = half)."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("NORD_ROTATE_FAIL_SHARE", "0.5"))))
    except ValueError:
        return 0.5


def any_fail_share() -> float:
    """Share of accounts that did not complete (any cause) that queues a swap (0.8 = 4 in 5)."""
    try:
        return min(1.0, max(0.0, float(os.environ.get("NORD_ROTATE_ANY_SHARE", "0.8"))))
    except ValueError:
        return 0.8


def classify_failure(message: str) -> str:
    """Category of a failed account. Only "ip" and "ip_block" can be fixed by a new server.

    "account": Instagram answered "Can't find account" / no sessionid. That follows a
    username that was rejected earlier, so the account never existed. A new server
    does not fix it, so it is counted but never triggers a swap.
    """
    text = (message or "").lower()
    if "metacheckpointblocked" in text:
        return "ip_block"
    if any(m.lower() in text for m in IP_FAIL_MARKERS):
        return "ip"
    if "no sessionid" in text or "can't find account" in text:
        return "account"
    return "other"


def _new_episode(city) -> dict:
    return {"city": f"{city[0]} / {city[1]}" if city else "(before first swap)",
            "started": time.time(), "ok": 0, "fail": 0, "cats": {}}


def _close_episode(reason: str, log=print) -> None:
    """Write the server episode that just ended to the stats file and log its summary."""
    global _episode
    with _state:
        ep, _episode = _episode, None
    if ep is None:
        return
    n = ep["ok"] + ep["fail"]
    rec = dict(ep, ended=time.time(), accounts=n,
               fail_share=round(ep["fail"] / n, 3) if n else None,
               minutes=round((time.time() - ep["started"]) / 60, 1), close_reason=reason)
    try:
        with open(stats_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError as exc:
        log(f"[⚠️] NordVPN stats not written: {exc}")
    share = f"{rec['fail_share']:.0%}" if rec["fail_share"] is not None else "n/a"
    log(f"[📊] NordVPN {rec['city']}: {n} accounts, {ep['ok']} ok, {ep['fail']} failed ({share}), "
        f"{rec['minutes']} min — closed: {reason}")


def report(path: Optional[str] = None) -> str:
    """Per-server summary of every closed episode in the stats file, worst server first."""
    path = path or stats_path()
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except FileNotFoundError:
        return f"no stats yet ({path})"
    if not rows:
        return "no closed episodes yet"
    agg: dict = defaultdict(lambda: {"eps": 0, "accounts": 0, "ok": 0, "fail": 0, "minutes": 0.0})
    for r in rows:
        a = agg[r["city"]]
        a["eps"] += 1
        a["accounts"] += r["accounts"]
        a["ok"] += r["ok"]
        a["fail"] += r["fail"]
        a["minutes"] += r["minutes"]
    out = [f"{'server':28} {'eps':>4} {'accts':>6} {'ok':>6} {'fail%':>6} {'min/ep':>7}"]
    for city, a in sorted(agg.items(), key=lambda kv: -kv[1]["fail"] / max(1, kv[1]["accounts"])):
        share = 100 * a["fail"] / a["accounts"] if a["accounts"] else 0
        out.append(f"{city:28} {a['eps']:>4} {a['accounts']:>6} {a['ok']:>6} {share:>5.0f}% "
                   f"{a['minutes'] / a['eps']:>7.1f}")
    span_h = max(1e-9, (max(r["ended"] for r in rows) - min(r["started"] for r in rows)) / 3600)
    total = sum(r["accounts"] for r in rows)
    fails = sum(r["fail"] for r in rows)
    out.append("")
    out.append(f"run span {span_h:.2f} h · swaps {len(rows)} ({len(rows) / span_h:.1f}/h) · "
               f"accounts {total} · overall fail {100 * fails / max(1, total):.0f}%")
    out.append("swap reasons: " + ", ".join(f"{k} ×{v}" for k, v in Counter(r["close_reason"] for r in rows).most_common()))
    cats: Counter = Counter()
    for r in rows:
        cats.update(r.get("cats") or {})
    if cats:
        out.append("failure types: " + ", ".join(f"{k} ×{v}" for k, v in cats.most_common()))
    return "\n".join(out)


def _record_window(category: str, log=print) -> None:
    """Record one finished account by category. Queue a swap when a full window is mostly IP blocks.

    The window holds one flag per account: True when the account failed for an IP reason.
    Account and other failures are counted in the episode record but never queue a swap.
    """
    global _window, _any_window, _episode
    size = window_size()
    ok = category == "ok"
    is_ip = category in ("ip", "ip_block")
    trigger = None
    share = 0.0
    with _state:
        if _episode is None:
            _episode = _new_episode(_last_city)
        _episode["ok" if ok else "fail"] += 1
        _episode["cats"][category] = _episode["cats"].get(category, 0) + 1
        if _window.maxlen != size:
            _window = deque(_window, maxlen=size)
        if _any_window.maxlen != size:
            _any_window = deque(_any_window, maxlen=size)
        _window.append(is_ip)
        # A rejected username is not a network problem, so it never counts toward switching.
        _any_window.append(not ok and category != "username")
        # Rule 1: the run is not completing accounts (any cause) — e.g. a parallel
        # slot keeps failing to finish Instagram creation.
        if len(_any_window) == size:
            not_done = sum(_any_window)
            share = not_done / size
            if share >= any_fail_share():
                trigger = f"{not_done} of the last {size} accounts did not finish"
        # Rule 2: IP blocks dominate the window.
        if trigger is None and len(_window) == size:
            ip_fails = sum(_window)
            share = ip_fails / size
            if share >= fail_share():
                trigger = f"{ip_fails} of the last {size} accounts hit an IP block"
        if trigger is not None:
            _window.clear()
            _any_window.clear()
    if trigger is not None:
        request_swap(f"{trigger} ({share:.0%})", log)


def drain_max_s() -> float:
    try:
        return max(0.0, float(os.environ.get("NORD_ROTATE_DRAIN_S", "300")))
    except ValueError:
        return 300.0


def _nord(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    binary = shutil.which("nordvpn") or "nordvpn"
    return subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)


def _status() -> dict:
    out = _nord("status", timeout=15).stdout or ""
    return {k.strip(): v.strip() for k, v in re.findall(r"^([A-Za-z][A-Za-z ]*?):\s*(.+)$", out, re.M)}


def _norm(name: str) -> str:
    return re.sub(r"[\s_]+", " ", name or "").strip().lower()


def public_ip(timeout: int = 10) -> Optional[str]:
    """Exit IP as the internet sees it (through the tunnel when routing is on)."""
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace").strip() or None
    except Exception:
        return None


def _exit_ip_after_connect(attempts: int = 6, wait_s: float = 5.0) -> Optional[str]:
    """The route takes a few seconds to settle after connect, so retry the IP check."""
    for _ in range(attempts):
        ip = public_ip()
        if ip:
            return ip
        time.sleep(wait_s)
    return None


def _score(city) -> float:
    """Laplace-smoothed share of accounts that were not IP-blocked on this city."""
    ok, fail = _stats.get(city, [0, 0])
    return (ok + 1) / (ok + fail + 2)


_history_loaded = False
_exit_hook = False


def _ensure_history() -> None:
    """Once per process: seed city records from past runs and learn the current server.

    A new process would otherwise start blind: no record of which cities worked, and no
    idea which server NordVPN is on, so it could pick the same one again.
    """
    global _history_loaded, _last_city
    with _state:
        if _history_loaded:
            return
        _history_loaded = True
    rows = []
    try:
        with open(stats_path(), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        rows = []
    with _state:
        for r in rows:
            parts = str(r.get("city", "")).split(" / ")
            key = (parts[0], parts[1]) if len(parts) == 2 else None
            if key not in POOL:
                continue
            cats = r.get("cats") or {}
            bad = int(cats.get("ip", 0)) + int(cats.get("ip_block", 0))
            seen = _stats.setdefault(key, [0, 0])
            seen[0] += int(r.get("ok", 0))
            seen[1] += bad
    try:
        city = _norm(_status().get("City", ""))
        match = next((p for p in POOL if _norm(p[1]) == city), None)
        with _state:
            if match and _last_city is None:
                _last_city = match
    except Exception:  # noqa: BLE001 — NordVPN CLI missing or not connected
        pass


# Pick weight per country on top of each city's record: Canada and Singapore are
# used less than the US cities. Never 0, so they can still be picked.
COUNTRY_WEIGHT = {"Canada": 0.25, "Singapore": 0.15}


def country_weight(country: str) -> float:
    """Pick-weight multiplier; override with NORD_WEIGHT_CANADA / NORD_WEIGHT_SINGAPORE."""
    default = COUNTRY_WEIGHT.get(country, 1.0)
    try:
        val = float(os.environ.get(f"NORD_WEIGHT_{country.upper()}", default))
    except ValueError:
        val = default
    return max(0.01, val)


def _pick_city() -> tuple[str, str]:
    """Random pick weighted by each city's record, never the city just used."""
    _ensure_history()
    with _state:
        cands = [p for p in POOL if p != _last_city] or list(POOL)
        weights = [_score(p) * country_weight(p[0]) for p in cands]
    return random.choices(cands, weights=weights, k=1)[0]


def rotate(log=print, city: Optional[tuple[str, str]] = None) -> dict:
    """Connect to ``city`` (or a weighted pick) and confirm it. Raises RuntimeError on failure."""
    global _last_city, _last_at
    country, name = city or _pick_city()
    before = public_ip()
    log(f"[🌍] NordVPN swap: {country.replace('_', ' ')} / {name.replace('_', ' ')}"
        f" (exit was {before or 'unknown'})")
    _nord("disconnect", timeout=30)
    res = _nord("connect", country, name, timeout=CONNECT_TIMEOUT_S)
    st = _status()
    if st.get("Status") != "Connected" or _norm(st.get("City", "")) != _norm(name):
        raise RuntimeError(
            f"connect to {name} failed: {(res.stdout + res.stderr).strip()[:200] or st}")
    after = _exit_ip_after_connect()
    if not after:
        raise RuntimeError(f"connected to {name} but the exit IP could not be checked")
    with _state:
        _last_city, _last_at = (country, name), time.monotonic()
    log(f"[🌍] NordVPN connected: {st.get('City', name)} ({st.get('Country', country)}) exit {after}")
    return {"country": country, "city": name, "ip": after, "before": before}


def _perform_swap(log=print, forced: bool = False) -> None:
    """Run the pending swap (retrying other cities). Only one runs at a time."""
    global _pending, _halted
    with _swap_lock:
        with _state:
            if _pending is None:
                return
            reason = _pending
        if forced:
            log(f"[⚠️] NordVPN swap ({reason}): running accounts did not finish in time — swapping anyway")
        try:
            tried = set()
            for _ in range(CONNECT_ATTEMPTS):
                pick = _pick_city()
                if pick in tried:
                    continue
                tried.add(pick)
                try:
                    rotate(log=log, city=pick)
                    _close_episode(reason, log)
                    with _state:
                        _halted = False
                        _window.clear()  # judge the new server on its own accounts
                        _any_window.clear()
                        _episode = _new_episode(pick)
                    return
                except Exception as exc:  # noqa: BLE001 — try another city
                    log(f"[⚠️] NordVPN swap to {pick[1]} failed: {exc}")
            with _state:
                _halted = True
            log("[⛔] NordVPN swap failed on every city — new accounts are held until a connect works.")
        finally:
            with _state:
                _pending = None


def swap_pending() -> bool:
    """True while a swap is queued. Accounts still at the pre-signup email-code stage are doomed on
    the same blocked IP, so they use this to give up at once instead of waiting out their timeout
    (which is what kept the swap waiting ~100s in the 40-slot run). Accounts further along are not
    touched: they finish and the swap waits for them."""
    if not enabled():
        return False
    with _state:
        return _pending is not None


def request_swap(reason: str, log=print) -> None:
    """Queue a swap. Ignored when one is already queued or within the cooldown."""
    global _pending
    if not enabled():
        return
    with _state:
        if _pending is not None:
            return
        if reason != RECOVER and _last_at and time.monotonic() - _last_at < COOLDOWN_S:
            return
        _pending = reason
    log(f"[🌍] NordVPN swap queued ({reason}): new accounts wait while running ones finish")


def enter_cycle(log=print) -> None:
    """Call before an account starts. Waits for a queued swap, then counts the account as running."""
    global _active, _pending, _exit_hook
    if not enabled():
        return
    if not _exit_hook:
        _exit_hook = True
        # Save the server stay still in progress when the worker exits (stop, Ctrl+C, end of run).
        atexit.register(_close_episode, "run ended")
    age = max_age_s()
    with _state:
        stale = age > 0 and (_last_at == 0 or time.monotonic() - _last_at >= age)
    if stale:
        request_swap(f"server in use for {int(age // 60)} min", log)
    with _state:
        if _halted and _pending is None:
            _pending = RECOVER
    started = time.monotonic()
    while True:
        with _state:
            if _pending is None:
                _active += 1
                return
            idle = _active == 0
        if idle:
            _perform_swap(log)
        elif drain_max_s() and time.monotonic() - started >= drain_max_s():
            _perform_swap(log, forced=True)
        else:
            time.sleep(3)


def finish_cycle(ok: bool, message: str = "", log=print) -> None:
    """Call when an account ends. Updates the city record and the failure streak."""
    global _active, _ip_streak
    if not enabled():
        return
    _record_window("ok" if ok else classify_failure(message), log)
    block = False
    streak = need = 0
    with _state:
        _active = max(0, _active - 1)
        city = _last_city
        is_ip = (not ok) and any(m.lower() in (message or "").lower() for m in IP_FAIL_MARKERS)
        if city is not None and (ok or is_ip):
            _stats.setdefault(city, [0, 0])[0 if ok else 1] += 1
        if ok or not is_ip:
            _ip_streak = 0
        elif "MetaCheckpointBlocked" in message:
            _ip_streak = 0
            block = True
        else:
            _ip_streak += 1
            streak, need = _ip_streak, streak_needed()
            if streak >= need:
                _ip_streak = 0
    if block:
        request_swap("Meta checkpoint block", log)
    elif is_ip:
        log(f"[🌍] IP-type failure {streak}/{need}: {message[:120]}")
        if streak >= need:
            request_swap(f"{need} IP failures in a row", log)


if __name__ == "__main__":
    # Measurement report for a long run:  .venv/bin/python core/vpn_rotate.py
    print(report())
