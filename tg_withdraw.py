#!/usr/bin/env python3
"""tg_withdraw.py — withdraw USDT (BEP-20) from Taskly / PayGo / FastPay.

Flows (learned live 2026-10-02):
  * Taskly / PayGo : /start -> 📤 Withdraw -> USDT (BEP-20) -> address -> amount
                     -> "✅ Withdrawal request created!"   (USD, fee $0.025, min $0.20)
  * FastPay        : /start -> Balance -> Withdraw -> amount (৳ BDT, min 50)
                     -> USDT(BEP-20) -> address -> "✅ Auto Withdrawal Successful!"

SAFETY — withdraw is a sensitive op, so it takes EXCLUSIVE ownership of TG:
  1. ``tg_accounts.set_frozen(True)`` writes a file flag every worker reads, so
     NO other code can lease a Telegram profile while this runs.
  2. It waits for any in-flight leases to clear before touching a session.
  3. It unfreezes in a ``finally`` (even on error).

Output: one JSON line per action + a final summary JSON (the dashboard parses it).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from ai_config import DATA_DIR, TG_BOTS  # noqa: E402
from tg_accounts import (  # noqa: E402
    tg_manager, session_ok, set_frozen, freeze_info, is_frozen,
)

WALLET_FILE = os.path.join(DATA_DIR, "settings.json")
DEFAULT_WALLET = ""


def _log(msg):
    print(f"[withdraw] {msg}", flush=True)


def _norm(s):
    return unicodedata.normalize("NFKC", str(s or "")).lower()


def load_wallet() -> str:
    try:
        with open(WALLET_FILE, encoding="utf-8") as f:
            return str(json.load(f).get("bep20Wallet") or "").strip()
    except Exception:
        return ""


def _buttons(msg):
    return [(b.text or "", b) for r in (getattr(msg, "buttons", None) or []) for b in r]


def _newest(client, ent):
    msgs = client.get_messages(ent, limit=1)
    return msgs[0] if msgs else None


def _texts(client, ent, n=5):
    return [(m.text or "") for m in client.get_messages(ent, limit=n)]


def _click(client, ent, want, tries=8, gap=1.5):
    for _ in range(tries):
        m = _newest(client, ent)
        for text, b in _buttons(m):
            if _norm(want) in _norm(text):
                b.click()
                time.sleep(2.5)
                return text
        time.sleep(gap)
    return None


def _read_balance(client, ent) -> float | None:
    _click(client, ent, "balance")
    time.sleep(2)
    for t in _texts(client, ent, 4):
        if "balance" in t.lower():
            m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", t)
            if m:
                return float(m.group(1))
    return None


def _withdraw_paygo_taskly(client, bot: str, amount: float, wallet: str) -> dict:
    """PayGo/Taskly: Withdraw -> USDT(BEP-20) -> address -> amount (USD)."""
    ent = client.get_entity(TG_BOTS[bot]["username"])
    client.send_message(ent, "/start")
    time.sleep(3.5)

    bal = _read_balance(client, ent)
    if bal is not None and bal + 1e-9 < amount:
        return {"ok": False, "bot": bot, "error": f"balance ${bal:.4f} < amount ${amount:.4f}", "balance": bal}

    if not _click(client, ent, "withdraw"):
        return {"ok": False, "bot": bot, "error": "no '📤 Withdraw' button", "balance": bal}
    if not _click(client, ent, "usdt"):
        return {"ok": False, "bot": bot, "error": "no 'USDT (BEP-20)' method", "balance": bal}

    client.send_message(ent, wallet); time.sleep(2.5)          # address first
    client.send_message(ent, f"{amount:g}"); time.sleep(3.5)    # then amount

    for t in _texts(client, ent, 5):
        low = t.lower()
        if "withdrawal request created" in low:
            return {"ok": True, "bot": bot, "balance": bal, "confirmation": t.replace("\n", " | ")}
        if "minimum" in low and "amount" in low:
            return {"ok": False, "bot": bot, "error": t.replace("\n", " | ")[:220], "balance": bal}
        if "invalid" in low and "address" in low:
            return {"ok": False, "bot": bot, "error": t.replace("\n", " | ")[:220], "balance": bal}
        if "insufficient" in low or "not enough" in low:
            return {"ok": False, "bot": bot, "error": t.replace("\n", " | ")[:220], "balance": bal}
    return {"ok": False, "bot": bot, "error": "no confirmation seen", "balance": bal, "last": _texts(client, ent, 2)}


def _withdraw_fastpay(client, amount_bdt: float, wallet: str) -> dict:
    """FastPay: Balance -> Withdraw -> amount (৳ BDt) -> USDT(BEP-20) -> address."""
    ent = client.get_entity(TG_BOTS["fastpay"]["username"])
    client.send_message(ent, "/start")
    time.sleep(3.5)

    if not _click(client, ent, "balance"):
        return {"ok": False, "bot": "fastpay", "error": "no 'Balance' button"}
    if not _click(client, ent, "withdraw"):
        return {"ok": False, "bot": "fastpay", "error": "no 'WITHDRAW' button"}
    client.send_message(ent, f"{amount_bdt:g}"); time.sleep(3)   # amount (৳) first
    if not _click(client, ent, "usdt"):
        return {"ok": False, "bot": "fastpay", "error": "no 'USDT(BEP-20)' method"}
    client.send_message(ent, wallet); time.sleep(3.5)            # then address

    for t in _texts(client, ent, 5):
        low = t.lower()
        if "withdrawal successful" in low or "auto withdrawal successful" in low:
            return {"ok": True, "bot": "fastpay", "confirmation": t.replace("\n", " | ")}
        if "limit" in low and ("min" in low or "max" in low):
            return {"ok": False, "bot": "fastpay", "error": t.replace("\n", " | ")[:220]}
        if "insufficient" in low or "not enough" in low:
            return {"ok": False, "bot": "fastpay", "error": t.replace("\n", " | ")[:220]}
        if "invalid" in low and "address" in low:
            return {"ok": False, "bot": "fastpay", "error": t.replace("\n", " | ")[:220]}
    return {"ok": False, "bot": "fastpay", "error": "no confirmation seen", "last": _texts(client, ent, 2)}


def withdraw_one(client, bot: str, amount: float, wallet: str) -> dict:
    """Dispatch to the right bot flow. FastPay amount is in BDT (৳), others USD."""
    if bot == "fastpay":
        return _withdraw_fastpay(client, amount, wallet)
    return _withdraw_paygo_taskly(client, bot, amount, wallet)


def _pick_profile(tg_id: str | None):
    accts = tg_manager.list()
    ok = [a for a in accts if session_ok(a) and a.get("enabled") is not False]
    if tg_id:
        ok = [a for a in ok if a.get("id") == tg_id]
    return ok


def main():
    ap = argparse.ArgumentParser(description="Withdraw USDT (BEP-20) from Taskly/PayGo")
    ap.add_argument("--bot", default="paygo", choices=("paygo", "taskly", "fastpay"))
    ap.add_argument("--amount", type=float, default=0.20)
    ap.add_argument("--wallet", default="")
    ap.add_argument("--tg-id", default="", help="specific profile id (default: any)")
    ap.add_argument("--all", action="store_true", help="withdraw from EVERY profile for this bot")
    ap.add_argument("--no-freeze", action="store_true", help="do not freeze TG (unsafe)")
    args = ap.parse_args()

    wallet = (args.wallet or load_wallet()).strip()
    if not wallet:
        print(json.dumps({"ok": False, "error": "no BEP-20 wallet configured"}))
        return 2
    if args.amount <= 0:
        print(json.dumps({"ok": False, "error": "amount must be > 0"}))
        return 2

    frozen_by_us = False
    if not args.no_freeze:
        set_frozen(True, f"withdraw {args.bot} ${args.amount:g}")
        frozen_by_us = True
        _log("TG frozen — exclusive access for withdrawal.")

    results = []
    try:
        # Wait for in-flight leases to clear (workers release at cycle end).
        deadline = time.time() + 90
        while tg_manager.leased_ids() and time.time() < deadline:
            _log("waiting for in-flight TG leases to clear…")
            time.sleep(2)

        profiles = _pick_profile(args.tg_id or None)
        if not profiles:
            print(json.dumps({"ok": False, "error": "no logged-in TG profile"}))
            return 1
        if not args.all:
            profiles = profiles[:1]

        from telethon.sync import TelegramClient
        from mtproto_bot import _api_credentials, session_file

        aid, ah = _api_credentials()
        for rec in profiles:
            tid = rec.get("id")
            sess = rec.get("session_file") or session_file(tid)
            client = None
            try:
                client = TelegramClient(sess, aid, ah)
                client.connect()
                if not client.is_user_authorized():
                    results.append({"ok": False, "tg_id": tid, "error": "session not authorized"})
                    continue
                res = withdraw_one(client, args.bot, args.amount, wallet)
                res["tg_id"] = tid
                results.append(res)
                _log(json.dumps(res))
            except Exception as exc:
                results.append({"ok": False, "tg_id": tid, "error": str(exc)[:200]})
                _log(f"{tid} ERROR: {exc}")
            finally:
                try:
                    if client is not None:
                        client.disconnect()
                except Exception:
                    pass
            time.sleep(2)
    finally:
        if frozen_by_us:
            set_frozen(False)
            _log("TG unfrozen.")

    print(json.dumps({"ok": any(r.get("ok") for r in results), "results": results}))
    return 0 if any(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
