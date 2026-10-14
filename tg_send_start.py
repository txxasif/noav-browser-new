#!/usr/bin/env python3
"""tg_send_start.py — send "/start" to the Telegram bots over MTProto.

Used by the dashboard's "Send /start" button when a bot gets stuck. Opens each
connected, idle MTProto account's session and sends ``/start`` to the chosen
bot (or every enabled bot). Busy/leased, disabled or logged-out accounts are
skipped, never touched.

    .venv/bin/python tg_send_start.py --bot all --json
    .venv/bin/python tg_send_start.py --bot paygo --json

``--json`` prints exactly ONE line.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)

from ai_config import TG_BOTS  # noqa: E402
from mtproto_bot import MtprotoTasklyBot, session_file, _make_client  # noqa: E402
from tg_balance import DEFAULT_WORKERS, _close_client, _is_locked, _pool_records  # noqa: E402
import tg.manager as M  # noqa: E402
import tg.registry as registry  # noqa: E402
from tg_accounts import record_mode  # noqa: E402

START_TEXT = "/start"


def _start_bot(tg_id, target, client):
    """Send /start to ONE bot on a shared client. Never raises."""
    cfg = TG_BOTS.get(target, {})
    out = {"target": target, "name": cfg.get("name") or target, "ok": False}
    bot = None
    try:
        bot = MtprotoTasklyBot(session_path=session_file(tg_id), tg_id=tg_id,
                               bot_target=target, log=lambda *_: None)
        bot._client = client          # share the account's connection
        bot.start()
        if not bot._entity:
            raise RuntimeError(f"could not resolve @{bot.bot_username}")
        bot._send(START_TEXT)
        out["ok"] = True
    except Exception as exc:          # session lost, network, flood, …
        out["error"] = ("busy — session held by a running worker"
                        if _is_locked(exc) else str(exc))
        out["busy"] = _is_locked(exc)
    return out


def _one_account(a, bots):
    """Send /start to every requested bot for ONE account (sequential)."""
    tid = str(a.get("id") or "")
    name = a.get("name") or a.get("label") or tid
    rec = {"id": tid, "name": name, "ok": False, "bots": []}

    if record_mode(a) != "mtproto":
        rec["skipped"] = "not an MTProto account"
        return rec
    ok, why = M.guard(tid, "send /start")
    if not ok:
        rec["skipped"] = why
        return rec

    sess = session_file(tid)
    if not os.path.isfile(sess):
        rec["error"] = "no MTProto session file"
        return rec

    client = None
    try:
        client = _make_client(tid, sess)
        client.connect()
        if not client.is_user_authorized():
            raise RuntimeError("session not logged in")
        rec["bots"] = [_start_bot(tid, b, client) for b in bots]
        rec["ok"] = any(r.get("ok") for r in rec["bots"])
    except Exception as exc:
        rec["error"] = ("busy — session held by a running worker"
                        if _is_locked(exc) else str(exc))
    finally:
        _close_client(client)
    return rec


def send_start(bot_arg: str):
    started = time.time()
    if bot_arg == "all":
        bots = [b for b in registry.enabled_bots() if b != "fastpay"]
    else:
        bots = [bot_arg]
    if not bots:
        return {"ok": False, "error": "no enabled bots"}

    records = _pool_records()
    with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as ex:
        accounts = list(ex.map(lambda a: _one_account(a, bots), records))

    sent = sum(1 for a in accounts if a.get("ok"))
    skipped = sum(1 for a in accounts if a.get("skipped"))
    failed = sum(1 for a in accounts if not a.get("ok") and not a.get("skipped"))
    return {"ok": True, "bot": bot_arg, "bots": bots,
            "sent": sent, "skipped": skipped, "failed": failed,
            "accounts": accounts,
            "elapsed_s": round(time.time() - started, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description='Send "/start" to Telegram bots over MTProto')
    ap.add_argument("--bot", default="all", choices=("all", "taskly", "paygo"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    print(json.dumps(send_start(args.bot)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
