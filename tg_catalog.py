#!/usr/bin/env python3
"""tg_catalog.py — dump the task catalog for the Fleet dashboard page.

Single source of truth remains ``tg_tasks.py`` / ``tg_flows.py``; this only
serializes them so the dashboard renders EVERY task (classic + pool) grouped
by bot instead of hardcoding labels in JS.

Outputs single-line JSON:
  {"ok": true, "tasks": [{"bot": "paygo", "id": "cookies",
    "label": "📱 Create Inst (Cookies)", "start_task": "📱 Create Inst (Cookies)",
    "flow": "cookie", "runner": "run_cookie_cycle", "mode": "pool",
    "family": "cookie", "price": 0.02, "follow": 5}, ...]}
"""
from __future__ import annotations

import json
import os
import sys

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)


# Dashboard value to send as tg_task so the engine resolves to this exact
# task id (labels alone are ambiguous across bots).
START_ALIAS = {
    "nomail": "🔥 Create Inst (No mail)",
    "inst_2fa": "📱 Create Inst (2FA)",
    "inst_2fa_pool": "Taskly 2FA",
    "cookies_nomail": "🍪 Create Inst (No mail)",
    "cookies_nomail_pool": "Taskly Cookie",
    "cookies": "📱 Create Inst (Cookies)",
    "paygo_cookies_2fa": "PayGo Cookie",
    "paygo_2fa_pool": "PayGo 2FA",
    "paygo_2fa": "PayGo 2FA (Normal)",
    "fastpay_ig_2fa": "Instagram 2FA",
    "fastpay_2fa_pool": "FastPay 2FA",
}

POOL_FLOWS = {"pool_2fa", "paygo_pool_2fa", "fastpay_pool_2fa", "pool_cookie_2fa"}
COOKIE_FLOWS = {"cookie", "cookie_2fa", "pool_cookie_2fa"}


def main() -> int:
    import tg_tasks  # noqa: E402
    import tg_flows  # noqa: E402

    rows = []
    for bot, catalog in (tg_tasks.TASKS or {}).items():
        for tid, spec in (catalog or {}).items():
            spec = spec or {}
            flow = spec.get("flow") or "2fa"
            try:
                runner = tg_flows.runner_of(flow)
            except Exception:
                runner = ""
            try:
                steps = tg_flows.resolve_steps(bot, tid)
            except Exception:
                steps = []
            base = {
                "bot": bot,
                "id": tid,
                "label": spec.get("label") or tg_tasks.LABELS.get(tid, tid),
                "start_task": START_ALIAS.get(tid, spec.get("label") or tid),
                "flow": flow,
                "runner": runner,
                "steps": steps,
                "family": "cookie" if flow in COOKIE_FLOWS else "2fa",
                "price": spec.get("price"),
                "follow": spec.get("follow", 0) or 0,
            }
            if flow in POOL_FLOWS:
                rows.append(dict(base, mode="pool"))
            elif flow == "cookie":
                # Serves BOTH: classic creation and pool drain (flag).
                rows.append(dict(base, mode="classic"))
                rows.append(dict(base, mode="pool"))
            else:
                rows.append(dict(base, mode="classic"))
    print(json.dumps({"ok": True, "tasks": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
