#!/usr/bin/env python3
"""tg_balance.py — read the Taskly + PayGo bot balances for MTProto accounts.

Why this exists
---------------
An MTProto (Telethon) pool record has **no browser** — its credential is the
``data/tg_sessions/<id>.session`` file, not a Chromium profile. The dashboard's
"Open Telegram Web" button therefore shows a QR login the record can never
satisfy. This script is the browser-free equivalent: it attaches to the
account's session, opens **each** bot (Taskly + PayGo), taps the ``💰 Balance``
reply key and reports whatever the bot sent back.

Usage::

    .venv/bin/python tg_balance.py --id tg_4          # one account, human
    .venv/bin/python tg_balance.py --all              # every MTProto account
    .venv/bin/python tg_balance.py --all --json       # one JSON line (dashboard)

``--json`` prints exactly ONE line.

Single account::

    {"ok": true, "id": "tg_4", "session": "tg_4.session",
     "bots": [{"target": "taskly", "name": "Taskly Bot", "ok": true,
               "balance": "...", "amount": 2.0978, "buttons": [...]},
              {"target": "paygo", ...}]}

All accounts (per-account + totals for the dashboard)::

    {"ok": true, "count": 6, "checked_at": "...",
     "accounts": [{"id": "tg_1", "name": "Ah", "ok": true,
                   "bots": [...], "total": 2.12}, ...],
     "totals": {"taskly": 5.30, "paygo": 0.10, "grand": 5.40}}

Only ONE client may use a session file at a time (Telethon's session is a SQLite
DB), so a busy (leased) account is skipped, and the dashboard refuses the
single-account check while the account is leased.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)

from ai_config import TG_BOTS, TG_ACCOUNTS_JSON  # noqa: E402
from mtproto_bot import MtprotoTasklyBot, session_file  # noqa: E402

# Always report BOTH bots, in this order, so the dashboard layout is stable.
BOT_ORDER = ("taskly", "paygo")


def _amount(text: str):
    """Best-effort numeric value out of a bot balance reply (None if absent)."""
    if not text:
        return None
    m = re.search(r"[$\u20ac\u00a3]?\s*([0-9][0-9., ]*[0-9]|[0-9])", text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "")
    # If both separators appear, the LAST one is the decimal separator.
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    try:
        return round(float(raw), 4)
    except Exception:
        return None


def _new_incoming(bot, before_id, timeout):
    """First NEW bot (incoming) message after ``before_id``.

    Returns ``(text, message_id, buttons)``; ``(None, None, [])`` on timeout.
    Outgoing echoes (our own ``Balance`` message) are skipped so we never show
    the button we just tapped as the "answer".
    """
    deadline = time.time() + max(0.0, timeout)
    while True:
        for m in bot._messages(limit=8):
            mid = int(getattr(m, "id", 0) or 0)
            if mid <= before_id or getattr(m, "out", False):
                continue
            txt = (getattr(m, "text", "") or "").strip()
            if txt:
                btns, _ = bot._buttons(limit=3)
                return txt, mid, btns
        if time.time() >= deadline:
            return None, None, []
        time.sleep(0.4)


def check_bot(tg_id, target, timeout=20.0):
    """Tap 💰 Balance on ONE bot. Returns a JSON-safe dict (never raises)."""
    cfg = TG_BOTS.get(target, {})
    out = {"target": target, "name": cfg.get("name") or target, "ok": False}
    bot = None
    try:
        bot = MtprotoTasklyBot(session_path=session_file(tg_id), tg_id=tg_id,
                               bot_target=target, log=lambda *_: None)
        bot.start()                         # connect + resolve the bot entity
        bot.reset_to_main_menu()            # /start + escape any submenu
        btns, _ = bot._buttons()
        key = next((b for b in btns if "balance" in b.lower()), None)
        if not key:
            out["error"] = "no Balance key on the main menu"
            out["buttons"] = btns
            out["messages"] = bot._recent_texts(2)
            return out
        before = bot._last_id()
        bot._send(key)                      # reply-keyboard button == plain text
        text, _mid, after_btns = _new_incoming(bot, before, timeout)
        if not text:
            out["error"] = "no reply to Balance (timeout)"
            out["messages"] = bot._recent_texts(2)
            return out
        out.update({"ok": True, "balance": text, "text": text,
                    "amount": _amount(text), "buttons": after_btns or []})
        return out
    except Exception as exc:                # session lost, network, 2FA, …
        out["error"] = str(exc)
        return out
    finally:
        try:
            if bot is not None:
                bot.disconnect()
        except Exception:
            pass


def check(tg_id, bots=BOT_ORDER, timeout=20.0):
    """Check every requested bot for ``tg_id`` and return a JSON-safe summary."""
    sess = session_file(tg_id)
    if not os.path.isfile(sess):
        return {"ok": False, "id": tg_id,
                "error": "no MTProto session file for %s (%s)" % (tg_id, sess)}
    results = [check_bot(tg_id, b, timeout=timeout) for b in bots]
    total = sum((r.get("amount") or 0.0) for r in results)
    return {"ok": any(r.get("ok") for r in results), "id": tg_id,
            "session": os.path.basename(sess), "bots": results,
            "total": round(total, 4)}


def _pool_records():
    try:
        with open(TG_ACCOUNTS_JSON, "r", encoding="utf-8") as fh:
            return json.load(fh) or []
    except Exception:
        return []


def check_all(timeout=20.0):
    """Check Taskly + PayGo for EVERY MTProto account; skip leased (busy) ones."""
    recs = [a for a in _pool_records()
            if str(a.get("mode") or "").lower() == "mtproto"]
    accounts, tot = [], {"taskly": 0.0, "paygo": 0.0}
    for a in recs:
        tid = str(a.get("id") or "")
        name = a.get("name") or a.get("label") or tid
        if str(a.get("status") or "").lower() == "busy":
            accounts.append({"id": tid, "name": name, "ok": False,
                             "error": "busy (leased by a worker) — skipped",
                             "bots": [], "total": 0.0})
            continue
        res = check(tid, timeout=timeout)
        for b in res.get("bots", []):
            tgt = b.get("target")
            if tgt in tot:
                tot[tgt] += (b.get("amount") or 0.0)
        accounts.append({"id": tid, "name": name, "ok": res.get("ok"),
                         "error": res.get("error"), "bots": res.get("bots", []),
                         "total": res.get("total", 0.0)})
    grand = tot["taskly"] + tot["paygo"]
    return {"ok": True, "count": len(accounts), "accounts": accounts,
            "totals": {"taskly": round(tot["taskly"], 4),
                       "paygo": round(tot["paygo"], 4),
                       "grand": round(grand, 4)},
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    ap = argparse.ArgumentParser(
        description="Read Taskly/PayGo balances for MTProto account(s)")
    ap.add_argument("--id", help="pool id (e.g. tg_4)")
    ap.add_argument("--all", action="store_true",
                    help="check every MTProto account in the pool")
    ap.add_argument("--json", action="store_true",
                    help="print one JSON line (dashboard)")
    ap.add_argument("--timeout", type=float, default=20.0,
                    help="seconds to wait for each bot's reply")
    args = ap.parse_args()
    if not args.id and not args.all:
        ap.error("pass --id <pool id> or --all")

    res = check_all(timeout=args.timeout) if args.all else check(args.id, timeout=args.timeout)
    if args.json:
        print(json.dumps(res), flush=True)
        return 0 if res.get("ok") else 1

    if args.all:
        print("=== Balances (Taskly + PayGo) ===")
        for a in res.get("accounts", []):
            if not a.get("ok"):
                print("%-6s %-14s ⚠ %s" % (a["id"], a.get("name", ""), a.get("error")))
                continue
            bits = []
            for b in a.get("bots", []):
                bits.append("%s %s" % (b["name"], b.get("balance") if b.get("ok") else ("⚠ " + (b.get("error") or "n/a"))))
            print("%-6s %-14s %s" % (a["id"], a.get("name", ""), " | ".join(bits)))
        t = res.get("totals", {})
        print("TOTALS: Taskly $%.4f · PayGo $%.4f · GRAND $%.4f" % (t.get("taskly", 0), t.get("paygo", 0), t.get("grand", 0)))
        return 0

    print("=== Balance for %s (%s) ===" % (args.id, res.get("session", "—")))
    if res.get("error"):
        print("⚠ " + res["error"])
    for b in res.get("bots", []):
        if b.get("ok"):
            print("[%s] %s" % (b["name"], b["balance"]))
        else:
            print("[%s] ⚠ %s" % (b["name"], b.get("error")))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
