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
from tg_tasks import normalize as _norm_btn  # noqa: E402

# Report all enabled bots (Taskly + PayGo + FastPay). Stable ordering.
try:
    from tg.registry import enabled_bots
    BOT_ORDER = tuple(b for b in ("taskly", "paygo", "fastpay") if b in enabled_bots()) or ("taskly", "paygo", "fastpay")
except Exception:
    BOT_ORDER = ("taskly", "paygo", "fastpay")


def _parse_balance_info(text: str) -> dict:
    """Extract numeric amounts and clean summary from a bot's balance message.

    Supports:
      - Taskly: "💰 Your balance: $2.0978"
      - PayGo:  "💰 Your balance: $0.1000"
      - FastPay: "💰 **Balance:** `৳6.0` | `$0.05`\n👛 **Pending:** `৳180.0` | `$1.44`"
    """
    if not text:
        return {"amount": None, "pending": None, "summary": ""}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bal_line = next((line for line in lines if "balance" in line.lower() and "pending" not in line.lower()), None)
    pending_line = next((line for line in lines if "pending" in line.lower()), None)
    amount = None
    pending_amt = None
    target_line = bal_line if bal_line else text

    # Extract amount from bal_line (prioritizing explicit USD '$')
    m_usd = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)", target_line)
    if m_usd:
        amount = round(float(m_usd.group(1)), 4)
    else:
        m_bdt = re.search(r"৳\s*([0-9]+(?:\.[0-9]+)?)", target_line)
        if m_bdt:
            amount = round(float(m_bdt.group(1)) / 125.0, 4)
        else:
            m_gen = re.search(r"[$\u20ac\u00a3]?\s*([0-9]+(?:[.,][0-9]+)?)", target_line)
            if m_gen:
                try:
                    amount = round(float(m_gen.group(1).replace(",", ".")), 4)
                except Exception:
                    pass

    # Extract pending amount if present
    if pending_line:
        m_pusd = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)", pending_line)
        if m_pusd:
            pending_amt = round(float(m_pusd.group(1)), 4)
        else:
            m_pbdt = re.search(r"৳\s*([0-9]+(?:\.[0-9]+)?)", pending_line)
            if m_pbdt:
                pending_amt = round(float(m_pbdt.group(1)) / 125.0, 4)

    # Human-friendly summary string for logs & CLI
    if bal_line and ("৳" in text or "pending" in text.lower()):
        m_b = re.search(r"৳\s*([0-9.]+)", bal_line)
        bdt_str = f"৳{m_b.group(1)}" if m_b else ""
        usd_str = f"${amount:.2f}" if amount is not None else ""
        bal_disp = f"{bdt_str} ({usd_str})".strip() if bdt_str and usd_str else (usd_str or bdt_str)
        summary = f"💰 Balance: {bal_disp}"
        if pending_line:
            m_pb = re.search(r"৳\s*([0-9.]+)", pending_line)
            pbdt_str = f"৳{m_pb.group(1)}" if m_pb else ""
            pusd_str = f"${pending_amt:.2f}" if pending_amt is not None else ""
            p_disp = f"{pbdt_str} ({pusd_str})".strip() if pbdt_str and pusd_str else (pusd_str or pbdt_str)
            summary += f" · Pending: {p_disp}"
    else:
        summary = text.strip().replace("\n", " ")
        if len(summary) > 80:
            summary = summary[:77] + "..."

    return {"amount": amount, "pending": pending_amt, "summary": summary}


def _amount(text: str):
    """Best-effort numeric value out of a bot balance reply (None if absent)."""
    return _parse_balance_info(text)["amount"]


def _is_balance_reply(text: str) -> bool:
    """True only if ``text`` is a bot balance answer, not an unrelated push."""
    if not text or "balance" not in text.lower():
        return False
    return _parse_balance_info(text)["amount"] is not None


def _new_incoming(bot, before_id, timeout, accept=None):
    """Newest NEW bot (incoming) message after ``before_id`` that ``accept``s.

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
            if not txt:
                continue
            if accept is not None and not accept(txt):
                continue
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
        key, _ = bot._wait_for_button("balance", timeout=8.0)
        if not key:
            btns, _ = bot._buttons()
            key = next((b for b in btns if "balance" in _norm_btn(b)), None)
        if not key:
            out["error"] = "no Balance key on the main menu"
            out["buttons"] = bot._buttons()[0] if bot._buttons() else []
            out["messages"] = bot._recent_texts(2)
            return out
        before = bot._last_id()
        bot._send(key)                      # reply-keyboard button == plain text
        text, _mid, after_btns = _new_incoming(bot, before, timeout,
                                               accept=_is_balance_reply)
        if not text:
            out["error"] = "no reply to Balance (timeout)"
            out["messages"] = bot._recent_texts(2)
            return out
        parsed = _parse_balance_info(text)
        out.update({
            "ok": True,
            "balance": parsed["summary"] or text,
            "text": text,
            "amount": parsed["amount"],
            "pending": parsed["pending"],
            "buttons": after_btns or [],
        })
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
    """Check all enabled bots for EVERY MTProto account; skip leased (busy) ones."""
    recs = [a for a in _pool_records()
            if str(a.get("mode") or "").lower() == "mtproto"]
    accounts = []
    tot = {b: 0.0 for b in BOT_ORDER}
    tot_pending = {b: 0.0 for b in BOT_ORDER}
    for a in recs:
        tid = str(a.get("id") or "")
        name = a.get("name") or a.get("label") or tid
        if str(a.get("status") or "").lower() == "busy":
            accounts.append({"id": tid, "name": name, "ok": False,
                             "error": "busy (leased by a worker) — skipped",
                             "bots": [], "total": 0.0})
            continue
        res = check(tid, bots=BOT_ORDER, timeout=timeout)
        for b in res.get("bots", []):
            tgt = b.get("target")
            if tgt in tot:
                tot[tgt] += (b.get("amount") or 0.0)
            if tgt in tot_pending:
                tot_pending[tgt] += (b.get("pending") or 0.0)
        accounts.append({"id": tid, "name": name, "ok": res.get("ok"),
                         "error": res.get("error"), "bots": res.get("bots", []),
                         "total": res.get("total", 0.0)})
    grand = sum(tot.values())
    totals = {b: round(tot[b], 4) for b in BOT_ORDER}
    totals["grand"] = round(grand, 4)
    totals["pending"] = {b: round(tot_pending[b], 4) for b in BOT_ORDER}
    totals["fastpay_pending"] = round(tot_pending.get("fastpay", 0.0), 4)
    return {"ok": True, "count": len(accounts), "accounts": accounts,
            "totals": totals,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    ap = argparse.ArgumentParser(
        description="Read Taskly/PayGo/FastPay balances for MTProto account(s)")
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
        labels = " + ".join((TG_BOTS.get(b, {}).get("name") or b) for b in BOT_ORDER)
        print("=== Balances (%s) ===" % labels)
        for a in res.get("accounts", []):
            if not a.get("ok"):
                print("%-6s %-14s ⚠ %s" % (a["id"], a.get("name", ""), a.get("error")))
                continue
            bits = []
            for b in a.get("bots", []):
                bits.append("%s %s" % (b["name"], b.get("balance") if b.get("ok") else ("⚠ " + (b.get("error") or "n/a"))))
            print("%-6s %-14s %s" % (a["id"], a.get("name", ""), " | ".join(bits)))
        t = res.get("totals", {})
        tot_str = " · ".join("%s $%.4f" % (b.capitalize(), t.get(b, 0)) for b in BOT_ORDER)
        print("TOTALS: %s · GRAND $%.4f" % (tot_str, t.get("grand", 0)))
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
