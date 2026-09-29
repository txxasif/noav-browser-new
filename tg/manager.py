"""tg.manager — lease + mutual-exclusion + readiness + balance.

The dashboard talks to THIS module (via the Node server). It never touches the
pool store directly. Key guarantees:

* **Mutual exclusion** — a profile leased for one bot shows ``busy_bot`` and is
  never handed to another bot (the pool's ``acquire`` already skips ``busy``;
  this layer surfaces *which* bot holds it and refuses manual ops meanwhile).
* **Readiness** — per bot: how many connected+enabled profiles can serve it.
* **Guards** — ``guard(account_id, action)`` refuses balance/join/claim on a
  leased, disabled, or session-less profile with a clear reason.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Optional

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import tg.registry as registry  # noqa: E402


# ---------------------------------------------------------------- pool views
def _pool():
    from tg_accounts import tg_manager
    return tg_manager.list()


def _is_busy(a: dict) -> bool:
    return str(a.get("status") or "").lower() == "busy"


def account_view(a: dict) -> dict:
    busy = _is_busy(a)
    return {
        "id": a.get("id"),
        "label": a.get("label") or a.get("id"),
        "mode": a.get("mode") or "web",
        "enabled": a.get("enabled") is not False,
        "status": a.get("status") or "idle",
        "logged_in": a.get("logged_in") is True,
        "tasks_done": a.get("tasks_done") or 0,
        "phone": a.get("phone") or "",
        "name": a.get("name") or "",
        # Only meaningful while leased — which bot currently owns the session.
        "busy_bot": (a.get("busy_bot") if busy else None),
        "free": (not busy) and a.get("enabled") is not False and a.get("logged_in") is True,
    }


def accounts():
    return [account_view(a) for a in _pool()]


# ---------------------------------------------------------------- bot views
def bots():
    out = []
    for spec in registry.summary():
        pool = _pool()
        enabled_conn = [a for a in pool
                        if a.get("enabled") is not False and a.get("logged_in") is True]
        free = [a for a in enabled_conn if not _is_busy(a)]
        busy_here = [a for a in enabled_conn if _is_busy(a)
                     and str(a.get("busy_bot") or "") == spec["id"]]
        busy_other = [a for a in enabled_conn if _is_busy(a)
                      and str(a.get("busy_bot") or "") != spec["id"]]
        spec = dict(spec)
        spec.update({
            "connected": len(enabled_conn),
            "free": len(free),
            "busy_here": len(busy_here),
            "busy_other": len(busy_other),
        })
        out.append(spec)
    return out


def counts():
    pool = _pool()
    return {
        "total": len(pool),
        "connected": sum(1 for a in pool if a.get("logged_in") is True),
        "enabled": sum(1 for a in pool if a.get("enabled") is not False),
        "busy": sum(1 for a in pool if _is_busy(a)),
        "free": sum(1 for a in pool if account_view(a)["free"]),
    }


def summary():
    return {
        "ok": True,
        "enabled_bots": registry.enabled_bots(),
        "bots": bots(),
        "accounts": accounts(),
        "counts": counts(),
    }


# ---------------------------------------------------------------- guards
def guard(account_id: str, action: str = "use") -> tuple[bool, str]:
    """Refuse a manual op (``balance``/``join``/``claim``/``use``) with a reason."""
    rec = None
    for a in _pool():
        if str(a.get("id")) == str(account_id):
            rec = a
            break
    if rec is None:
        return False, f"unknown Telegram profile: {account_id}"
    if _is_busy(rec):
        who = rec.get("busy_bot") or "a running task"
        return False, f"{account_id} is busy in {who} — it cannot be used for {action} until released."
    if rec.get("enabled") is False:
        return False, f"{account_id} is disabled — enable it first."
    if rec.get("logged_in") is not True:
        return False, f"{account_id} has no live session — reconnect it first."
    return True, ""


def assert_free(account_id: str):
    ok, why = guard(account_id)
    if not ok:
        raise RuntimeError(why)


# ---------------------------------------------------------------- balance
def run_balance(timeout: int = 900, ids=None):
    """Taskly + PayGo balances (MTProto). Delegates to tg_balance.py."""
    args = [sys.executable, os.path.join(APP_DIR, "tg_balance.py")]
    args += (["--all"] if not ids else ["--all"]) + ["--json"]
    try:
        out = subprocess.run(args, cwd=APP_DIR, capture_output=True, text=True, timeout=timeout)
        return json.loads((out.stdout or "").strip().splitlines()[-1] or "{}")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
