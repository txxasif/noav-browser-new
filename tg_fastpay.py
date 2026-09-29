#!/usr/bin/env python3
"""tg_fastpay.py — submit Instagram 2FA keys to FastPay2025_bot and claim the payout.

Flow (reverse-engineered live 2026-09-28)
-----------------------------------------
Gate (once per Telegram account):
    /start -> "You must join our channels to use the bot:" ->
        join  t.me/FastPyOfficial  +  t.me/FastPayOfficial2026  ->  press `Verify`
    -> "Please select your language:" -> choose English.
Menu:
    `Task` -> category `Instagram` -> `Instagram 2FA | ৳3.0 | $0.024`
Task contract (no bot-issued creds — the bot is a PAYOUT for keys):
    bot:  "Please send the 2FA Key below:" -> send the base32 secret
    bot:  "2FA Code: NNNNNN" (+ Confirm / Cancel)
    press `Confirm` -> "Task Completed Successfully! Pending Balance: ..."

Usage
-----
    .venv/bin/python tg_fastpay.py --profile tg_4 --keys 3
    .venv/bin/python tg_fastpay.py --profile tg_4 --key JBSWY3DPEHPK3PXP
    .venv/bin/python tg_fastpay.py --profile tg_4 --all        # every ledger key
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import unicodedata

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from ai_config import TG_ACCOUNTS_JSON  # noqa: E402
from mtproto_bot import _api_credentials, session_file  # noqa: E402

BOT = "FastPay2025_bot"
CHANNELS = ["FastPyOfficial", "FastPayOfficial2026"]
TASK = "Instagram 2FA"


def _norm(t) -> str:
    return unicodedata.normalize("NFKC", str(t or "")).lower()


async def _last(client, ent):
    msgs = await client.get_messages(ent, limit=1)
    return msgs[0] if msgs else None


async def _send_until(client, ent, match, tries=6, gap=2.0):
    """Send the reply-keyboard button whose text matches; return (ok, msg)."""
    for _ in range(tries):
        m = await _last(client, ent)
        if m and m.buttons:
            for row in m.buttons:
                for b in row:
                    if match in _norm(b.text):
                        await b.click()
                        await asyncio.sleep(3)
                        return True, await _last(client, ent)
        await asyncio.sleep(gap)
    return False, await _last(client, ent)


async def _ensure_gate(client, ent):
    """Join required channels + Verify + set English. Idempotent."""
    from telethon import functions
    await client.send_message(ent, "/start")
    await asyncio.sleep(3)
    for _ in range(4):
        m = await _last(client, ent)
        if not m or not m.buttons:
            await asyncio.sleep(2)
            continue
        texts = [_norm(b.text) for row in m.buttons for b in row]
        if any("english" in t or "setlang" in t for t in texts) or \
           any(getattr(b, "data", None) == b"setlang_en" for row in m.buttons for b in row):
            for row in m.buttons:
                for b in row:
                    if getattr(b, "data", None) == b"setlang_en":
                        await b.click()
            await asyncio.sleep(3)
            continue
        if "join our channels" in _norm(getattr(m, "text", "")):
            for ch in CHANNELS:
                try:
                    await client(functions.channels.JoinChannelRequest(channel=await client.get_entity(ch)))
                except Exception:
                    pass
                await asyncio.sleep(1)
            for row in m.buttons:
                for b in row:
                    if getattr(b, "data", None) == b"verify_join":
                        await b.click()
            await asyncio.sleep(3)
            continue
        break
    return await _last(client, ent)


async def _choose_task(client, ent):
    m = await _last(client, ent)
    have = [_norm(b.text) for row in (m.buttons or []) for b in row] if m and m.buttons else []
    if not any("instagram 2fa" in t for t in have):
        await _send_until(client, ent, "task", tries=4)
        await _send_until(client, ent, "instagram", tries=4)
    ok, _m = await _send_until(client, ent, "instagram 2fa", tries=4)
    return ok


async def _submit_one(client, ent, key):
    ok = await _choose_task(client, ent)
    if not ok:
        return False, "task 'Instagram 2FA' not offered"
    await client.send_message(ent, key)
    await asyncio.sleep(5)
    m = await _last(client, ent)
    code = None
    if m:
        txt = getattr(m, "text", "") or ""
        if "2FA Code" in txt:
            code = txt.split("`")[1] if "`" in txt else None
    ok2, m2 = await _send_until(client, ent, "confirm", tries=4)
    await asyncio.sleep(4)
    m3 = await _last(client, ent)
    done = bool(m3 and "task completed" in _norm(getattr(m3, "text", "")))
    return done, (code or (getattr(m2, "text", "") if m2 else "")[:80])


def _ledger_all():
    """Every ledger record (raw rows), for id-addressed lookups."""
    try:
        return json.load(open("data/accounts.json", encoding="utf-8")) or []
    except Exception:
        return []


def _ledger_keys(include_paid: bool = False):
    """[(id, secret)] for accounts that hold a 2FA key.

    Already-paid accounts are skipped unless ``include_paid`` — the bot pays
    once per key, so re-submitting a paid key just burns bot rate limit.
    """
    try:
        rows = json.load(open("data/accounts.json", encoding="utf-8"))
    except Exception:
        return []
    out = []
    for r in rows:
        secret = (r.get("twofa_secret") or "").strip()
        if not secret:
            continue
        if r.get("fastpay_paid") and not include_paid:
            continue
        out.append((r.get("id"), secret))
    return out


def _mark_paid(aid: str) -> None:
    """Stamp fastpay_paid / fastpay_paid_at so the account is not re-submitted."""
    try:
        import store
        import time as _t
        store.update_account(aid, {"fastpay_paid": 1,
                                   "fastpay_paid_at": _t.strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as exc:
        print(f"[fastpay] could not stamp {aid}: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Submit IG 2FA keys to FastPay2025_bot")
    ap.add_argument("--profile", required=True, help="pool id whose session to drive, e.g. tg_4")
    ap.add_argument("--key", help="one base32 key")
    ap.add_argument("--keys", type=int, help="submit the first N ledger keys")
    ap.add_argument("--ids", help="comma-separated ledger ids to pay (explicit disjoint set)")
    ap.add_argument("--all", action="store_true", help="submit every unpaid ledger key")
    ap.add_argument("--include-paid", action="store_true",
                    help="also re-submit keys already marked fastpay_paid")
    args = ap.parse_args()

    if args.key:
        work = [("<manual>", args.key)]
    elif args.ids:
        # Explicit id set — the dashboard splits the pending keys across parallel
        # runners. Passing ids (not offsets) keeps each runner's work disjoint
        # even though ~all runners read the ledger at the same moment.
        by_id = {r.get("id"): (r.get("twofa_secret") or "").strip()
                 for r in _ledger_all()}
        want = [x.strip() for x in args.ids.split(",") if x.strip()]
        work = [(i, by_id.get(i, "")) for i in want if by_id.get(i)]
        if not work:
            print("[fastpay] none of the requested ids have a 2FA key")
            return 1
    else:
        keys = _ledger_keys(include_paid=args.include_paid)
        if not keys:
            print("[fastpay] no unpaid 2FA keys in the ledger "
                  "(use --include-paid to re-submit paid ones)")
            return 1
        work = keys if args.all else keys[: (args.keys or 1)]

    api_id, api_hash = _api_credentials()
    from telethon import TelegramClient

    async def run():
        client = TelegramClient(session_file(args.profile), api_id, api_hash)
        await client.connect()
        ent = await client.get_entity(BOT)
        await _ensure_gate(client, ent)
        print(f"[fastpay] profile={args.profile} keys={len(work)}")
        ok_n = 0
        for aid, key in work:
            try:
                ok, detail = await _submit_one(client, ent, key)
            except Exception as exc:
                ok, detail = False, str(exc)[:120]
            print(f"  - {aid}: {'OK' if ok else 'FAIL'} {detail}")
            ok_n += 1 if ok else 0
            if ok and aid != "<manual>":
                _mark_paid(aid)
            await asyncio.sleep(3)
        await client.disconnect()
        print(f"[fastpay] completed {ok_n}/{len(work)}")
        return ok_n

    return 0 if asyncio.run(run()) else 1


if __name__ == "__main__":
    sys.exit(main())
