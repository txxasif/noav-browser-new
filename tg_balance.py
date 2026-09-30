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
from mtproto_bot import MtprotoTasklyBot, session_file, _make_client  # noqa: E402

# --- perf tunables (status read only — never the task pipeline) ------------
# Poll interval while waiting for a balance reply. The task flows in
# mtproto_bot.py keep their own 0.4-0.5 s pacing; touching that would change
# other pipelines' behaviour (invariant 24), so the fast interval is local to
# this file. Balance replies land in ~100-300 ms.
POLL_FAST = 0.15
# Accounts read in parallel. Each account owns a separate .session file, so
# there is no SQLite contention between workers; within an account the bots
# stay strictly sequential (one client per session file).
DEFAULT_WORKERS = 6
# TTL for a dashboard re-click inside the same window (seconds). A balance only
# moves when a task completes, so a short cache is safe; 0 disables it.
DEFAULT_CACHE_TTL = 45.0

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


# --- session-file contention ------------------------------------------------
# A Telethon .session IS a SQLite DB and serves ONE client at a time. While a
# worker is mid-task it holds the file open (MtprotoPooledBot keeps a live
# client per leased profile — invariant 11). Reading then fails with
# "database is locked". That is a CONTENTION signal, not a broken account:
# report it as "busy" and skip, exactly like a leased record, rather than
# surfacing a raw sqlite string or fighting a worker for the lock.
_LOCK_MARKERS = ("database is locked", "database table is locked",
                 "sqlite3.operationalerror")


def _is_locked(exc: BaseException) -> bool:
    return any(m in str(exc).lower() for m in _LOCK_MARKERS)


def _drain_loop() -> None:
    """Cancel Telethon's still-pending tasks on THIS thread's event loop.

    ``disconnect()`` stops the sender but MTProtoSender's ``_recv_loop`` task
    can still be queued; when the loop is later GC'd it prints
    "Task was destroyed but it is pending" / "Event loop is closed" on stderr.
    With one loop per worker thread that noise is multiplied, so drain it
    before the thread dies. Purely cosmetic — never raises.
    """
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            return
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending,
                                                   return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
    except Exception:
        pass


def _close_client(client) -> None:
    """Disconnect a Telethon client and release its thread's loop cleanly."""
    try:
        if client is not None and client.is_connected():
            client.disconnect()
    except Exception:
        pass
    _drain_loop()


def _new_incoming(bot, before_id, timeout, accept=None):
    """Newest NEW bot (incoming) message after ``before_id`` that ``accept``s.

    Returns ``(text, message_id, buttons)``; ``(None, None, [])`` on timeout.
    Outgoing echoes (our own ``Balance`` message) are skipped so we never show
    the button we just tapped as the "answer".

    Perf: uses ``min_id`` so the server returns ONLY newer messages (1 short
    round trip instead of 8), and polls at ``POLL_FAST`` instead of a flat
    0.4 s. Balances are a status read, never a credential wait, so a tight
    poll is safe here — the shared task-flow pacing in mtproto_bot.py is
    deliberately NOT touched (invariant 24: other pipelines stay undisturbed).
    """
    deadline = time.time() + max(0.0, timeout)
    while True:
        for m in bot._messages(limit=4, min_id=before_id):
            if getattr(m, "out", False):
                continue
            txt = (getattr(m, "text", "") or "").strip()
            if not txt:
                continue
            if accept is not None and not accept(txt):
                continue
            btns, _ = bot._buttons(limit=2)
            return txt, int(getattr(m, "id", 0) or 0), btns
        if time.time() >= deadline:
            return None, None, []
        time.sleep(POLL_FAST)


def check_bot(tg_id, target, timeout=20.0, client=None, cache=None, cache_ttl=0.0):
    """Tap 💰 Balance on ONE bot. Returns a JSON-safe dict (never raises).

    ``client`` reuses an already-connected Telethon client for this ACCOUNT
    (one session file serves one client, so all of an account's bots share a
    single connection instead of reconnecting per bot). ``cache`` enables a
    short TTL so repeated dashboard clicks inside the window do not re-send.
    """
    cfg = TG_BOTS.get(target, {})
    out = {"target": target, "name": cfg.get("name") or target, "ok": False}

    # ---- fresh cache hit? serve without touching the network -------------
    if cache is not None and cache_ttl > 0:
        hit = cache.get((tg_id, target))
        if hit and (time.time() - hit[0]) < cache_ttl:
            return dict(hit[1], cached=True)

    bot = None
    owns_client = client is None
    try:
        bot = MtprotoTasklyBot(session_path=session_file(tg_id), tg_id=tg_id,
                               bot_target=target, log=lambda *_: None)
        if client is not None:
            # Share the account's connection; only the BOT entity differs.
            bot._client = client
        bot.start()                         # connect (or reuse) + resolve entity
        if not bot._entity:
            raise RuntimeError(f"could not resolve @{bot.bot_username}")

        # ---- fast path: Balance already on the live keyboard -> skip reset.
        btns, _m = bot._buttons()
        key = next((b for b in btns if "balance" in _norm_btn(b)), None)
        if key is None:
            cbtn = next((b for b in btns if any(w in _norm_btn(b) for w in ("cancel", "return", "back", "main menu"))), None)
            if cbtn:
                bot._send(cbtn)
                time.sleep(0.3)
                btns, _m = bot._buttons()
                key = next((b for b in btns if "balance" in _norm_btn(b)), None)
            if key is None:
                bot._send("/start")
                deadline = time.time() + min(4.0, timeout)
                while time.time() < deadline:
                    time.sleep(POLL_FAST)
                    btns, _m = bot._buttons()
                    key = next((b for b in btns if "balance" in _norm_btn(b)), None)
                    if key:
                        break
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
        if cache is not None and cache_ttl > 0:
            cache[(tg_id, target)] = (time.time(), dict(out))
        return out
    except Exception as exc:                # session lost, network, 2FA, …
        out["error"] = ("busy — session held by a running worker "
                        "(restart it when the pool is idle)"
                        if _is_locked(exc) else str(exc))
        out["busy"] = _is_locked(exc)
        return out
    finally:
        try:
            if bot is not None and owns_client:
                bot.disconnect()
        except Exception:
            pass


def check(tg_id, bots=BOT_ORDER, timeout=20.0, cache=None, cache_ttl=0.0):
    """Check every requested bot for ``tg_id`` and return a JSON-safe summary.

    ONE Telethon client is opened for the whole account and shared by all of
    its bots — a .session file is a SQLite DB that serves a single client, so
    this is also the only correct way to read several bots for one account.
    """
    sess = session_file(tg_id)
    if not os.path.isfile(sess):
        return {"ok": False, "id": tg_id,
                "error": "no MTProto session file for %s (%s)" % (tg_id, sess)}
    client = None
    results = []
    try:
        client = _make_client(tg_id, sess)
        client.connect()
        if not client.is_user_authorized():
            raise RuntimeError(f"session not logged in ({os.path.basename(sess)})")
    except Exception as exc:
        _close_client(client)
        if _is_locked(exc):
            return {"ok": False, "id": tg_id, "session": os.path.basename(sess),
                    "error": "busy — session held by a running worker "
                             "(restart it when the pool is idle)",
                    "busy": True, "bots": [], "total": 0.0}
        return {"ok": False, "id": tg_id, "session": os.path.basename(sess),
                "error": str(exc), "bots": [], "total": 0.0}
    try:
        results = [check_bot(tg_id, b, timeout=timeout, client=client,
                             cache=cache, cache_ttl=cache_ttl) for b in bots]
    finally:
        _close_client(client)
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


def _one_account(a, timeout, cache, cache_ttl):
    """Read every bot for ONE account. Returns the dashboard account record.

    Runs in a worker thread, so each thread gets its own Telethon event loop
    (``_make_client`` installs a fresh loop per thread). Bots within an account
    stay SEQUENTIAL — one .session file serves one client at a time.
    """
    tid = str(a.get("id") or "")
    name = a.get("name") or a.get("label") or tid
    if str(a.get("status") or "").lower() == "busy" or a.get("leased_at"):
        return {"id": tid, "name": name, "ok": False, "busy": True,
                "error": "busy (leased by a worker) — skipped",
                "bots": [], "total": 0.0}
    res = check(tid, bots=BOT_ORDER, timeout=timeout,
                cache=cache, cache_ttl=cache_ttl)
    if res.get("busy"):
        # A worker holds the .session even though the pool row still says
        # idle (the lease heartbeat refreshes lazily). One quick retry after a
        # short backoff rescues the "worker just finished" case for ~1 s.
        time.sleep(1.0)
        res = check(tid, bots=BOT_ORDER, timeout=timeout,
                    cache=cache, cache_ttl=cache_ttl)
    return {"id": tid, "name": name, "ok": res.get("ok"),
            "error": res.get("error"), "busy": bool(res.get("busy")),
            "bots": res.get("bots", []), "total": res.get("total", 0.0)}


def check_all(timeout=20.0, workers=DEFAULT_WORKERS, cache_ttl=DEFAULT_CACHE_TTL):
    """Check all enabled bots for EVERY MTProto account; skip leased (busy) ones.

    Accounts run in PARALLEL (default 6 workers). Each account owns a distinct
    ``data/tg_sessions/<id>.session`` file, so there is no shared SQLite lock
    and no Telegram-side contention; parallelism is per-account only.
    """
    recs = [a for a in _pool_records()
            if str(a.get("mode") or "").lower() == "mtproto"]
    cache = {} if cache_ttl > 0 else None
    workers = max(1, min(int(workers or 1), len(recs) or 1))

    t0 = time.time()
    if workers == 1:
        accounts = [_one_account(a, timeout, cache, cache_ttl) for a in recs]
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers,
                                thread_name_prefix="tgbal") as pool:
            accounts = list(pool.map(
                lambda a: _one_account(a, timeout, cache, cache_ttl), recs))

    tot = {b: 0.0 for b in BOT_ORDER}
    tot_pending = {b: 0.0 for b in BOT_ORDER}
    for rec in accounts:
        for b in rec.get("bots", []):
            tgt = b.get("target")
            if tgt in tot:
                tot[tgt] += (b.get("amount") or 0.0)
            if tgt in tot_pending:
                tot_pending[tgt] += (b.get("pending") or 0.0)
    grand = sum(tot.values())
    totals = {b: round(tot[b], 4) for b in BOT_ORDER}
    totals["grand"] = round(grand, 4)
    totals["pending"] = {b: round(tot_pending[b], 4) for b in BOT_ORDER}
    totals["fastpay_pending"] = round(tot_pending.get("fastpay", 0.0), 4)
    out = {"ok": True, "count": len(accounts), "accounts": accounts,
           "totals": totals,
           "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out["elapsed_s"] = round(time.time() - t0, 2)
    if cache:
        out["cached"] = sum(1 for rec in accounts for b in rec.get("bots", [])
                            if b.get("cached"))
    return out


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
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help="accounts read in parallel (default %d; 1 = serial)"
                         % DEFAULT_WORKERS)
    ap.add_argument("--cache", type=float, default=DEFAULT_CACHE_TTL,
                    help="serve a just-fetched balance for N seconds "
                         "(default %.0fs, 0 = always fetch)" % DEFAULT_CACHE_TTL)
    args = ap.parse_args()
    if not args.id and not args.all:
        ap.error("pass --id <pool id> or --all")

    if args.all:
        res = check_all(timeout=args.timeout, workers=args.workers,
                        cache_ttl=args.cache)
    else:
        cache = {} if args.cache > 0 else None
        try:
            res = check(args.id, timeout=args.timeout, cache=cache,
                        cache_ttl=args.cache)
        except Exception as exc:            # never let one account kill the run
            res = {"ok": False, "id": args.id, "error": str(exc),
                   "bots": [], "total": 0.0}
    if args.json:
        print(json.dumps(res), flush=True)
        return 0 if res.get("ok") else 1

    if args.all:
        labels = " + ".join((TG_BOTS.get(b, {}).get("name") or b) for b in BOT_ORDER)
        print("=== Balances (%s) ===" % labels)
        for a in res.get("accounts", []):
            if not a.get("ok"):
                tag = "⏳" if a.get("busy") else "⚠ "
                print("%-6s %-14s %s%s" % (a["id"], a.get("name", ""), tag,
                                            a.get("error")))
                continue
            bits = []
            for b in a.get("bots", []):
                bits.append("%s %s" % (b["name"], b.get("balance") if b.get("ok") else ("⚠ " + (b.get("error") or "n/a"))))
            print("%-6s %-14s %s" % (a["id"], a.get("name", ""), " | ".join(bits)))
        t = res.get("totals", {})
        tot_str = " · ".join("%s $%.4f" % (b.capitalize(), t.get(b, 0)) for b in BOT_ORDER)
        print("TOTALS: %s · GRAND $%.4f" % (tot_str, t.get("grand", 0)))
        if res.get("elapsed_s") is not None:
            print("(%d accounts in %.1fs · %d workers%s)"
                  % (res.get("count", 0), res["elapsed_s"], args.workers,
                     " · %d cached" % res["cached"] if res.get("cached") else ""))
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
