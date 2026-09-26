#!/usr/bin/env python3
"""One-time Telegram login for one account in the pool.

Opens (headful) the persistent profile for the given Telegram account so you can
scan the QR code. The session is stored in ``telegram_profiles/<id>/`` and reused
by the automation.

Run:
    cd meta_auto_ai
    .venv/bin/python tg_login.py --id tg_2 --label "TG #2"

If ``--id`` is omitted, a new account is added to the pool automatically.
Scan the QR, wait for the chat list, then press Enter.
"""
import argparse
import base64
import os
import shutil
import sys
import threading
import time

AI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI_DIR)

from ai_config import TELEGRAM_URL, run  # noqa: E402
from tg_accounts import profile_dir, tg_manager  # noqa: E402
from tg_fingerprint import for_profile, launch_kwargs, apply_to_context, proxy_for  # noqa: E402

# Point Playwright at the browsers that actually exist. The dashboard spawns
# this script with PLAYWRIGHT_BROWSERS_PATH pointing at ~/.cache/ms-playwright
# (often empty here), which makes Chromium fail to launch and NO window opens
# ("can't open/connect TG"). worker.py does this; the standalone launchers must
# too. Safe no-op when the env is already correct.
try:
    run._point_playwright_at_browsers()
except Exception:
    pass


# ---------------------------------------------------------------------------
# MTProto record → Telegram Web auto-login (no phone scan needed)
# ---------------------------------------------------------------------------
# An `mtproto` pool record is logged in ONLY over Telethon
# (data/tg_sessions/<id>.session): the browser profile has no `stel_web_auth`
# cookie, so "Open TG Web" shows the QR screen (observed 2026-09-22). We do not
# need the phone — the account's own session can ACCEPT the browser's QR token
# via auth.acceptLoginToken, exactly like a Telegram app scanning the QR
# (core.telegram.org/api/qr-login):
#   browser auth.exportLoginToken → QR rendered
#   our Telethon: auth.acceptLoginToken(token)
#   browser gets updateLoginToken → re-exports → loginTokenSuccess → chat list
# The token is read by screenshotting the rendered QR: Web A runs its API in a
# Web Worker (no page fetch/XHR to hook), and its QR is a styled SVG that plain
# cv2.QRCodeDetector cannot read — zxing-cpp can. Fallback on any failure is
# the unchanged manual "scan with your phone" screen.
# Set TG_WEB_QR_AUTO=0 to disable the auto path.
QR_SELECTORS = (".qr-container", ".qr-inner", ".auth-form.qr")


def _qr_gone(page) -> bool:
    """True when the auth QR is no longer on screen."""
    try:
        return not page.locator(".qr-container").first.is_visible()
    except Exception:
        return True


def _web_logged_in(page) -> bool:
    """True when Telegram Web left the QR screen AND a chat UI is showing."""
    if not _qr_gone(page):
        return False
    try:
        return bool(page.evaluate("""() => {
            const sels = ['.ChatList', '.chat-list', '.InboxList',
                          '#column-new-message', '#middle-column',
                          '.messages-layout', '.chatlist'];
            return sels.some(s => {
                const el = document.querySelector(s);
                return !!el && el.offsetParent !== null;
            });
        }"""))
    except Exception:
        return False


def _qr_token(page):
    """Raw login-token bytes from the currently rendered QR, or None."""
    import cv2
    import numpy as np
    import zxingcpp

    for sel in QR_SELECTORS:
        try:
            loc = page.locator(sel).first
            if not (loc.count() and loc.is_visible()):
                continue
            png = loc.screenshot()
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return None
            for bc in zxingcpp.read_barcodes(img):
                txt = bc.text or ""
                i = txt.find("tg://login?token=")
                if i >= 0:
                    s = txt[i + len("tg://login?token="):].strip()
                    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
            return None  # QR visible but not decoded this tick → retry
        except Exception:
            continue
    return None


def _auto_login_web(page, rec, budget: float = 90.0) -> bool:
    """Log the open Telegram Web page in using the record's own MTProto session.

    Thread split is mandatory: Playwright's sync API keeps an asyncio loop
    *running* in the main thread, and Telethon's sync helpers then hand back
    bare coroutines instead of executing (``telethon.sync.syncified``: ``if
    loop.is_running(): return coro``) — so every Telethon call is made on one
    dedicated worker thread that owns the client for its whole life.
    """
    if os.environ.get("TG_WEB_QR_AUTO", "1").strip().lower() in ("0", "off", "no"):
        return False
    if str(rec.get("mode") or "").lower() != "mtproto":
        return False
    from mtproto_bot import has_mtproto_session, session_file

    sess = rec.get("session_file") or session_file(rec["id"])
    if not has_mtproto_session(sess):
        print("  (no MTProto session for this record — scan the QR with your phone)")
        return False

    # Accept from a COPY of the session file: the engine may hold the real
    # .session open, and a second SQLite writer must never fight it. A copy
    # carries the same auth key, so it is the same server-side session.
    # NOTE: TelegramClient() appends ".session" to any path that lacks it, so
    # the copy MUST end in .session or we'd open a brand-new empty session.
    base = sess[:-len(".session")] if sess.endswith(".session") else sess
    tmp = f"{base}.webqr{os.getpid()}.session"
    stop = threading.Event()
    state = {"token": None, "used": None, "accepted": False, "err": None}

    def _worker():
        """Owns the Telethon client: connect → accept the newest QR token."""
        client = None
        try:
            from mtproto_bot import _make_client
            from telethon.errors import RPCError
            from telethon.tl.functions.auth import AcceptLoginTokenRequest

            shutil.copyfile(sess, tmp)
            client = _make_client(rec["id"], tmp)
            client.connect()
            if not client.is_user_authorized():
                state["err"] = "MTProto session not authorized"
                return
            while not stop.is_set():
                tok = state.get("token")
                if tok and tok is not state.get("used"):
                    state["used"] = tok
                    try:
                        client(AcceptLoginTokenRequest(token=tok))
                        state["accepted"] = True
                        return
                    except RPCError as e:
                        # Expired / already-accepted: Web A renders a fresh
                        # QR, so simply take the next one.
                        state["err"] = f"{type(e).__name__}"
                time.sleep(0.3)
        except Exception as e:
            state["err"] = str(e) or type(e).__name__
        finally:
            try:
                if client is not None:
                    client.disconnect()
            except Exception:
                pass
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    th = threading.Thread(target=_worker, daemon=True, name="tg-qr-admit")
    th.start()
    print("  → auto-login: accepting the Web QR from this account's MTProto session…")
    deadline = time.time() + budget
    try:
        while time.time() < deadline:
            if _web_logged_in(page):
                return True
            if state.get("err") and not state.get("accepted") and not th.is_alive():
                print(f"  (auto-login failed: {state['err']} — scan the QR with your phone)")
                return False
            tok = _qr_token(page)
            if tok:
                state["token"] = tok
            page.wait_for_timeout(700)
        print("  (auto-login timed out — scan the QR with your phone)")
        return False
    finally:
        stop.set()
        th.join(timeout=20)


def main():
    ap = argparse.ArgumentParser(description="Log in one Telegram account in the pool")
    ap.add_argument("--id", default=None, help="Telegram account id (e.g. tg_2)")
    ap.add_argument("--label", default=None)
    ap.add_argument("--hold", type=int, default=600,
                    help="seconds to keep the window open when non-interactive (dashboard passes a short hold)")
    args = ap.parse_args()

    if args.id:
        rec = next((a for a in tg_manager.list() if a["id"] == args.id), None)
        if rec is None:
            rec = tg_manager.add(args.label or args.id)
            # Rename the auto id (tg_N) to the requested one when free.
            if rec["id"] != args.id:
                recs = tg_manager.list(refresh=False)
                if not any(a["id"] == args.id for a in recs):
                    import shutil as _shutil
                    old_dir = rec["profile_dir"]
                    new_dir = profile_dir(args.id)
                    try:
                        if os.path.isdir(old_dir) and not os.path.isdir(new_dir):
                            _shutil.move(old_dir, new_dir)
                    except Exception:
                        pass
                    rec["id"] = args.id
                    rec["label"] = args.label or args.id
                    rec["profile_dir"] = new_dir
                    for a in tg_manager.accounts:
                        if a.get("profile_dir") == old_dir:
                            a.update(rec)
                    tg_manager.save()
    else:
        rec = tg_manager.add(args.label)
        print(f"Added Telegram account: {rec['id']} ({rec['label']})")

    from playwright.sync_api import sync_playwright

    print("==========================================================")
    print(f"  Telegram login — {rec['id']}")
    print(f"  Profile: {rec['profile_dir']}")
    print("==========================================================")
    # Single-owner guard: never launch a second Chromium on a profile dir
    # that already has a live holder (engine warm browser OR another
    # inspection window). The second launch either fails or boots a blank
    # profile that looks "logged out" on both sides.
    try:
        import warm_pool as _wp
        _holder = _wp.lock_holder_alive(rec["profile_dir"])
    except Exception:
        _holder = None
    if _holder:
        print(f"❌ Profile {rec['id']} is locked by live pid {_holder} "
              f"(engine running or another window open). Stop the engine or "
              f"close the other window first — refusing to corrupt the session.")
        try:
            tg_manager.release_inspect(rec["id"])
        except Exception:
            pass
        sys.exit(2)
    # Hold an inspection lease so engine workers skip this profile while the
    # window is open (acquire_* skips lease_note ~ inspect; reset_all preserves).
    try:
        tg_manager.lease_inspect(rec["id"])
    except Exception:
        pass
    try:
        with sync_playwright() as pw:
            _login_args = ["--no-first-run", "--no-default-browser-check",
                           "--disable-blink-features=AutomationControlled"]
            # INSTA_UI_MODE=new (default): Wayland-native visible window.
            if os.environ.get("INSTA_UI_MODE", "new").strip().lower() not in ("new", "desktop", "wayland"):
                _login_args.append("--ozone-platform=x11")
            # Per-profile device identity so Telegram cannot link the profiles as
            # one device (see tg_fingerprint.py). Stable across launches.
            ident = for_profile(rec["profile_dir"])
            _kw = dict(user_data_dir=rec["profile_dir"], headless=False, args=_login_args)
            _kw.update(launch_kwargs(ident))
            _px = proxy_for(rec["profile_dir"])
            if _px:
                _kw["proxy"] = _px
                print(f"  Proxy: {_px['server']}")
            ctx = pw.chromium.launch_persistent_context(**_kw)
            apply_to_context(ctx, ident)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(TELEGRAM_URL, wait_until="domcontentloaded", timeout=60000)
            # mtproto records: mint the Web session from the account's own
            # Telethon session instead of demanding a phone scan.
            if _auto_login_web(page, rec):
                print("\n✔ Logged in to Telegram Web automatically "
                      "(QR accepted via this account's MTProto session).\n")
            else:
                print("\n→ Scan the QR code (Settings > Devices > Add Device), wait for the")
                print("  chat list, then press Enter here.\n")
            try:
                input()
            except EOFError:
                print(f"(non-interactive) holding the window open for {args.hold}s…")
                time.sleep(max(0, args.hold))
            try:
                ctx.close()
            except Exception as e:
                # Window already gone (user closed it / browser exited) — that
                # is not a failure, the lease is released by the finally below.
                print(f"(window already closed: {type(e).__name__})")
    finally:
        # Mark usable again: a past failure leaves status=error/busy which blocks
        # leasing until a manual reset — a fresh login window implies intent to use.
        # Inspection lease is always released here (engine may then lease it).
        try:
            tg_manager.release_inspect(rec["id"])
        except Exception:
            try:
                tg_manager._reload()
                for a in tg_manager.accounts:
                    if a.get("id") == rec["id"]:
                        a["status"] = "idle"
                        break
                tg_manager.save()
            except Exception:
                pass
    print("Saved. This Telegram account is ready in the pool.")


if __name__ == "__main__":
    main()
