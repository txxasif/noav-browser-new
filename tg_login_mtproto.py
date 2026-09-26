#!/usr/bin/env python3
"""tg_login_mtproto.py — one-time Telethon login for a pool account.

Logs ONE Telegram account into an MTProto session file
(``data/tg_sessions/<id>.session``) and registers it in the pool with
``"mode": "mtproto"``. After this, the submitter uses ``mtproto_bot.py`` (no
browser) for that account.

Prerequisites (free): an ``api_id`` / ``api_hash`` from
https://my.telegram.org → API development tools, provided either by::

    export TG_API_ID=123456
    export TG_API_HASH=abcdef0123456789abcdef0123456789

or by ``data/tg_mtproto.json``::

    {"api_id": 123456, "api_hash": "abcdef..."}

Usage::

    .venv/bin/python tg_login_mtproto.py --id tg_4 --label "TG #4"
    .venv/bin/python tg_login_mtproto.py                 # next free tg_N

Telegram will ask for the phone number, the login code, and (if set) the
2FA password. The session file is as sensitive as the account itself — it
grants full access, so keep it local (like ``telegram_profiles/``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)

from mtproto_bot import _api_credentials, _device_identity, session_file  # noqa: E402
from tg_accounts import tg_manager  # noqa: E402


def _next_id() -> str:
    used = {a.get("id") for a in tg_manager.list(refresh=False)}
    n = 1
    while f"tg_{n}" in used:
        n += 1
    return f"tg_{n}"


def _emit(obj: dict) -> int:
    """Print one JSON line (the dashboard reads it) and set the exit code."""
    print(json.dumps(obj), flush=True)
    return 0 if obj.get("ok") else 1


def _json_mode(mode: str) -> int:
    """Non-interactive, dashboard-driven login. Secrets arrive on STDIN.

    ``{"id","phone",...}`` for ``--send-code``; the code / 2FA password for
    ``--verify`` are fed on stdin too, so they never appear in ``ps`` argv.
    """
    from mtproto_bot import MtprotoNeedsPassword
    try:
        payload = json.load(sys.stdin) or {}
    except Exception:
        payload = {}
    tg_id = str(payload.get("id") or _next_id())
    phone = str(payload.get("phone") or "").strip()
    if not phone:
        return _emit({"ok": False, "error": "phone required"})
    try:
        if mode == "send-code":
            from mtproto_bot import send_login_code
            r = send_login_code(tg_id, phone)
            return _emit({"ok": True, "id": tg_id, "phone": phone,
                          "phone_code_hash": r["phone_code_hash"], "type": r["type"]})
        from mtproto_bot import complete_login
        code = str(payload.get("code") or "").strip()
        if not code:
            return _emit({"ok": False, "error": "code required"})
        rec = complete_login(
            tg_id, phone, code, payload.get("phone_code_hash"),
            password=payload.get("password"), label=payload.get("label"),
            proxy=payload.get("proxy"))
        return _emit({"ok": True, "account": rec})
    except MtprotoNeedsPassword:
        return _emit({"ok": False, "need_password": True,
                      "error": "This account has 2FA — enter the password."})
    except Exception as exc:
        return _emit({"ok": False, "error": str(exc)})


def _connect(sess: str):
    """Authorized-or-not Telethon client for this session file."""
    from telethon.sync import TelegramClient
    aid, ah = _api_credentials()
    return TelegramClient(sess, aid, ah, **_device_identity(os.path.basename(sess).split(".")[0]))


def _register(tg_id, sess, args, me):
    name = (getattr(me, "first_name", "") or "").strip()
    phone = getattr(me, "phone", None)
    uid = getattr(me, "id", None)
    rec = tg_manager.upsert_mtproto(
        tg_id, sess, label=args.label or f"TG {tg_id} · MTProto",
        name=name or None, phone=phone, user_id=uid, proxy=args.proxy)
    print(f"✔ Registered in the pool: id={rec['id']} mode={rec.get('mode')} "
          f"logged_in={rec.get('logged_in')}")
    print(f"\nNext: run the pipeline as usual — {tg_id} is leased via MTProto "
          f"(no browser). Other accounts are unaffected.\n")


def main():
    ap = argparse.ArgumentParser(description="Log one Telegram account into an MTProto session")
    ap.add_argument("--id", default=None, help="pool id (e.g. tg_4); default = next free")
    ap.add_argument("--label", default=None, help="display label for the dashboard")
    ap.add_argument("--proxy", default=None,
                    help="optional per-account proxy, e.g. socks5://user:pass@host:1080")
    ap.add_argument("--replace", action="store_true",
                    help="re-login even if a session file already exists")
    ap.add_argument("--send-code", action="store_true",
                    help="dashboard mode: read {id,phone,label,proxy} JSON on stdin, request a code")
    ap.add_argument("--verify", action="store_true",
                    help="dashboard mode: read {id,phone,phone_code_hash,code,password} JSON on stdin")
    args = ap.parse_args()

    # Dashboard-driven (non-interactive) two-step flow. Secrets on STDIN.
    if args.send_code:
        return _json_mode("send-code")
    if args.verify:
        return _json_mode("verify")

    try:
        _api_credentials()
    except Exception as exc:
        print(f"\n❌ {exc}\n")
        return 2

    tg_id = args.id or _next_id()
    sess = session_file(tg_id)
    print(f"\n=== MTProto login for {tg_id} ===")
    print(f"session file: {sess}\n")

    # Existing session → just verify + register it (no re-login unless --replace).
    if os.path.isfile(sess) and not args.replace:
        client = None
        try:
            client = _connect(sess)
            client.connect()
            if client.is_user_authorized():
                me = client.get_me()
                print(f"✔ Existing session is valid for "
                      f"{(getattr(me, 'first_name', '') or '')} "
                      f"(+{getattr(me, 'phone', '') or '?'})")
                _register(tg_id, sess, args, me)
                return 0
            print("⚠️  Session file exists but is NOT authorized. "
                  "Re-run with --replace to log in again.")
            return 1
        except Exception as exc:
            print(f"⚠️  Could not verify existing session: {exc}")
            return 1
        finally:
            try:
                if client is not None:
                    client.disconnect()
            except Exception:
                pass

    print("Telegram will now ask for the phone number, the login code, "
          "and any 2FA password.\n")
    client = None
    try:
        client = _connect(sess)
        client.start()  # interactive: phone → code → (2FA password)
        me = client.get_me()
    except Exception as exc:
        print(f"\n❌ Login failed: {exc}\n")
        return 1
    finally:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass

    print(f"\n✔ Logged in as {(getattr(me, 'first_name', '') or '(no name)')} "
          f"{('+' + str(getattr(me, 'phone', ''))) if getattr(me, 'phone', None) else ''} "
          f"(id {getattr(me, 'id', None)})")
    _register(tg_id, sess, args, me)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
