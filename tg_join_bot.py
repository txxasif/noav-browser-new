#!/usr/bin/env python3
"""tg_join_bot.py — send /start to a Telegram bot from every pooled MTProto account.

Ops tool: resolve the given bot username from each ``data/tg_sessions/*.session``
MTProto account and send ``/start`` (which is what "joining" a bot means — it
opens the bot chat and registers the account with the bot's menu).

Only ONE Telethon client may use a session file at a time, so leased (``busy``)
accounts are SKIPPED by default while an engine is running; ``--include-busy``
overrides (unsafe mid-task).

Usage:
    .venv/bin/python tg_join_bot.py --bot FastPay2025_bot
    .venv/bin/python tg_join_bot.py --bot @FastPay2025_bot --id tg_4
    .venv/bin/python tg_join_bot.py --bot FastPay2025_bot --include-busy
    .venv/bin/python tg_join_bot.py --bot FastPay2025_bot --gate   # join channels + Verify + English
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from ai_config import TG_ACCOUNTS_JSON  # noqa: E402
from mtproto_bot import _api_credentials, has_mtproto_session, session_file  # noqa: E402

START_MESSAGE = "/start"


def _pool():
    try:
        with open(TG_ACCOUNTS_JSON, "r", encoding="utf-8") as fh:
            return json.load(fh) or []
    except Exception:
        return []


def _norm_bot(bot: str) -> str:
    b = str(bot or "").strip()
    return b[1:] if b.startswith("@") else b


def _bot_id_for_username(username: str) -> str:
    """Registry bot id whose username matches (e.g. FastPay2025_bot -> fastpay).

    gate_bot() reads channels/language from the registry by bot id, so without
    this the channel gate would have no channels to join. Falls back to the raw
    username (gate_bot then simply finds no spec and no-ops).
    """
    try:
        from tg.registry import all_bots, bot as bot_spec
        want = str(username or "").lstrip("@").lower()
        for bid in all_bots():
            spec = bot_spec(bid) or {}
            if str(spec.get("username") or "").lstrip("@").lower() == want:
                return bid
    except Exception:
        pass
    return username


async def _join_one(rec, bot_username, api_id, api_hash, wait=6.0, gate=False, bot_id=None):
    from telethon import TelegramClient

    tg_id = str(rec.get("id") or "")
    sess = rec.get("session_file") or session_file(tg_id)
    if not sess or not os.path.isfile(sess):
        return tg_id, False, "no session file"
    client = TelegramClient(sess, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return tg_id, False, "session not authorized"
        ent = await client.get_entity(bot_username)

        if gate:
            # Full cold-start gate: /start -> join required channels -> Verify ->
            # language. This is what a banned/never-joined account is missing —
            # a bare /start only prints "You must join our channels to use the bot".
            from tg.common import gate_bot
            res = await gate_bot(client, ent, bot_id or bot_username)
            await asyncio.sleep(wait)
            msgs = await client.get_messages(ent, limit=1)
            reply = ""
            if msgs:
                reply = (getattr(msgs[0], "text", "") or "").replace("\n", " ")[:120]
            stage = (res or {}).get("stage") or "?"
            ok = bool((res or {}).get("ok")) and stage == "menu"
            return tg_id, ok, f"stage={stage} | {reply or '(no reply yet)'}"

        await client.send_message(ent, START_MESSAGE)
        await asyncio.sleep(wait)
        msgs = await client.get_messages(ent, limit=1)
        reply = ""
        if msgs:
            reply = (getattr(msgs[0], "text", "") or "").replace("\n", " ")[:140]
        return tg_id, True, reply or "(no reply yet)"
    except Exception as exc:  # noqa: BLE001
        return tg_id, False, str(exc)[:200]
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Send /start to a bot from pooled MTProto accounts")
    ap.add_argument("--bot", required=True, help="bot username, e.g. FastPay2025_bot or @FastPay2025_bot")
    ap.add_argument("--id", default=None, help="only this pool id (e.g. tg_4)")
    ap.add_argument("--include-busy", action="store_true",
                    help="also use accounts leased by a running engine (UNSAFE mid-task)")
    ap.add_argument("--gate", action="store_true",
                    help="run the bot's FULL gate (join required channels + Verify + language), "
                         "not just a bare /start")
    ap.add_argument("--wait", type=float, default=6.0, help="seconds to wait for the bot reply")
    args = ap.parse_args()

    bot_username = _norm_bot(args.bot)
    bot_id = _bot_id_for_username(bot_username)
    try:
        api_id, api_hash = _api_credentials()
    except Exception as exc:
        print(f"[join] ERROR: {exc}")
        return 2

    pool = [a for a in _pool() if str(a.get("mode") or "").lower() == "mtproto"]
    if args.id:
        pool = [a for a in pool if str(a.get("id")) == str(args.id)]
    if not pool:
        print("[join] no MTProto accounts in the pool")
        return 1

    print(f"[join] bot=@{bot_username} (id={bot_id})  accounts={len(pool)}  "
          f"include_busy={args.include_busy}  gate={args.gate}")
    results = []
    for rec in pool:
        tg_id = str(rec.get("id"))
        if rec.get("enabled") is False:
            print(f"  - {tg_id}: skipped (disabled)")
            continue
        if not has_mtproto_session(rec.get("session_file") or session_file(tg_id)):
            print(f"  - {tg_id}: skipped (no session)")
            continue
        if str(rec.get("status") or "").lower() == "busy" and not args.include_busy:
            print(f"  - {tg_id}: skipped (leased by a running engine; stop it or --include-busy)")
            results.append((tg_id, None))
            continue
        tid, ok, detail = asyncio.run(_join_one(rec, bot_username, api_id, api_hash,
                                                args.wait, gate=args.gate, bot_id=bot_id))
        mark = "OK " if ok else "FAIL"
        print(f"  - {tid}: {mark} {detail}")
        results.append((tid, ok))

    done = [t for t, ok in results if ok]
    failed = [t for t, ok in results if ok is False]
    skipped = [t for t, ok in results if ok is None]
    print(f"[join] joined={len(done)} {done}  failed={len(failed)} {failed}  skipped(busy)={len(skipped)} {skipped}")
    if args.gate and failed:
        print("[join] NOTE: 'stage=gate' means the account still cannot use the bot — "
              "check the required channels are joinable (a new/private channel blocks everyone).")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
