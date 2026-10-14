"""Shared pool-drain helpers used by all pool runners."""
from __future__ import annotations

import json
import os
import time


def _cookies_for_playwright(cookie_str: str, session_only: bool = True) -> list:
    """Parse cookie string for Playwright.

    Parity with multi_insta.exe: inject ONLY sessionid (and ds_user_id if present).
    Discard stale csrftoken, mid, rur, and datr so Instagram generates fresh,
    valid tokens matching this browser session and avoids CSRF/mismatch 403s.
    """
    out = []
    session_id = None
    ds_user_id = None
    raw_str = str(cookie_str or "").strip()
    if not raw_str:
        return out

    if "sessionid=" not in raw_str and ";" not in raw_str:
        # Bare sessionid value
        return [{"name": "sessionid", "value": raw_str, "domain": ".instagram.com", "path": "/"}]

    for part in raw_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, val = part.split("=", 1)
        name, val = name.strip(), val.strip()
        if name == "sessionid":
            session_id = val
        elif name == "ds_user_id":
            ds_user_id = val
        elif not session_only and name:
            out.append({"name": name, "value": val, "domain": ".instagram.com", "path": "/"})

    if session_id:
        out.append({"name": "sessionid", "value": session_id, "domain": ".instagram.com", "path": "/"})
    if ds_user_id and session_only:
        out.append({"name": "ds_user_id", "value": ds_user_id, "domain": ".instagram.com", "path": "/"})
    return out


def _mail_provider(tokens) -> str:
    """Which mailbox an account's stored ``mail_tokens`` read from: mailtd | mailcf | yamin | ''."""
    t = tokens if isinstance(tokens, dict) else {}
    if t.get("tempmail_token"):
        return "mailtd"
    if t.get("mailcf_email"):
        return "mailcf"
    if t.get("yamin_email"):
        return "yamin"
    if t.get("guerrilla_email"):
        return "guerrilla"               # Guerrilla Mail API inbox (address survives an expired sid)
    if t.get("mailfish_email") and t.get("mailfish_api"):
        return "mailfish_api"            # new accounts: inbox created through the premium API
    if t.get("mailfish_email") and t.get("mailfish_auth_key"):
        return "mailfish"                # old accounts: web inbox read with its authKey
    return ""


def _mail_tokens_from_extra(extra) -> dict:
    """Extract the stored mailbox tokens (mail.td, Cloudflare catch-all or Yamin)."""
    try:
        ex = extra
        if isinstance(ex, str):
            ex = json.loads(ex) if ex.strip() else {}
        toks = (ex or {}).get("mail_tokens") or {}
        if isinstance(toks, dict) and _mail_provider(toks):
            return toks
    except Exception:
        pass
    return {}


def _mail_tokens_for_account(acc) -> dict:
    """Mailbox tokens for a pooled account; older accounts with none saved fall back to their address.

    An address on a Yamin domain or the Cloudflare catch-all domain identifies its mailbox
    without a stored token. Anything else (e.g. mailfish) has no reader and returns {}.
    """
    toks = _mail_tokens_from_extra((acc or {}).get("extra"))
    if toks:
        return toks
    email = str((acc or {}).get("email") or "").strip().lower()
    if "@" not in email:
        return {}
    domain = email.split("@", 1)[1]
    try:
        from ai_config import Urls
    except Exception:
        return {}
    if domain in {d.lower() for d in Urls.YAMIN_DOMAINS}:
        return {"yamin_email": email}
    if domain == str(Urls.CF_MAIL_DOMAIN).lower():
        return {"mailcf_email": email}
    return {}


def _msg_id(m: dict) -> str:
    """Stable id for a message: Yamin/mail.td give one; the Cloudflare Worker keys on timestamp+subject."""
    return str(m.get("id") or f"{m.get('timestamp') or ''}|{m.get('subject') or ''}")


def _mail_messages(tokens, runner=None) -> list:
    """Normalised message list (id, subject, from, ts, text, code) for the account's mailbox.

    A failing read (HTTP error, bad auth key, bad JSON) is logged via ``runner`` instead of
    silently looking like an empty inbox.
    """
    prov = _mail_provider(tokens)
    out = []
    try:
        if prov == "mailtd":
            for m in _mailtd_http_list(tokens):
                out.append({"id": str(m.get("id")), "subject": str(m.get("subject") or ""),
                            "from": str(m.get("from") or m.get("sender") or ""),
                            "ts": str(m.get("created_at") or m.get("createdAt") or m.get("id") or ""),
                            "text": None, "code": None})
        elif prov == "guerrilla":
            from core import guerrilla_api
            out.extend(guerrilla_api.list_messages(tokens["guerrilla_email"], tokens.get("guerrilla_sid", "")))
        elif prov == "mailfish_api":
            from core import mailfish_api
            for m in mailfish_api.list_messages(tokens["mailfish_email"]):
                out.append(m)
        elif prov == "mailfish":
            import json as _json
            import urllib.parse as _up
            import urllib.request as _ur
            q = _up.urlencode({"emailAddress": tokens["mailfish_email"]})
            req = _ur.Request(f"https://api.tempmail.fish/emails/emails?{q}",
                              headers={"Authorization": tokens["mailfish_auth_key"], "Accept": "application/json"})
            with _ur.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode("utf-8", "replace"))
            if isinstance(data, dict):
                data = next((data[k] for k in ("emails", "messages", "data", "items", "result")
                             if isinstance(data.get(k), list)), [])
            for m in data if isinstance(data, list) else []:
                if isinstance(m, dict):
                    # tempmail.fish stores the body as `textBody` (may be HTML) and has no `id`.
                    text = " ".join(str(m.get(k) or "") for k in ("subject", "textBody", "body", "text", "html", "content"))
                    out.append({"id": str(m.get("id") or _msg_id(m)), "subject": str(m.get("subject") or ""),
                                "from": str(m.get("from") or m.get("sender") or ""),
                                "ts": str(m.get("timestamp") or m.get("createdAt") or m.get("created_at") or m.get("date") or ""),
                                "text": text, "code": None})
        elif prov == "mailcf" and tokens.get("mailcf_token"):
            from core.mail_reader import list_messages
            for m in list_messages(tokens["mailcf_email"], tokens["mailcf_token"]):
                out.append({"id": _msg_id(m), "subject": str(m.get("subject") or ""),
                            "from": str(m.get("from") or ""), "ts": str(m.get("timestamp") or ""),
                            "text": str(m.get("text") or ""), "code": m.get("code")})
        elif prov == "mailcf":
            # Older accounts saved no read token: the Worker's public latest-code endpoint
            # still serves the newest OTP (15-minute window). The code is its own message.
            from core.mail_reader import latest_code
            code = latest_code(tokens["mailcf_email"])
            if code:
                out.append({"id": f"latest|{code}", "subject": "", "from": "", "ts": str(time.time()),
                            "text": "", "code": code, "trusted": True})
        elif prov == "yamin":
            import json as _json
            import urllib.parse as _up
            import urllib.request as _ur
            import ai_config  # noqa: F401  (puts engine/ on sys.path)
            from eng_constants import YAMIN_MAIL_API, YAMIN_AUTH_KEY
            user, _, domain = str(tokens["yamin_email"]).partition("@")
            q = f"user={_up.quote(user)}&domain={_up.quote(domain)}"
            req = _ur.Request(f"{YAMIN_MAIL_API}/?action=getMessages&{q}",
                              headers={"Authorization": YAMIN_AUTH_KEY, "X-Api-Key": YAMIN_AUTH_KEY})
            with _ur.urlopen(req, timeout=10) as resp:
                for m in _json.loads(resp.read().decode("utf-8", "replace")) or []:
                    if isinstance(m, dict):
                        out.append({"id": str(m.get("id") or ""), "subject": str(m.get("subject") or ""),
                                    "from": str(m.get("from") or "").lower(),
                                    "ts": str(m.get("timestamp") or ""), "text": None, "code": None})
    except Exception as exc:
        if runner is not None and getattr(runner, "_mail_read_err", None) != str(exc):
            try:
                runner._mail_read_err = str(exc)
                runner.log(f"[⚠️] {prov or 'mail'} inbox read failed: {exc}")
            except Exception:
                pass
        return []
    return [m for m in out if m["id"]]


def _mail_body(tokens, msg) -> tuple:
    """(text, code) for one normalised message; text is fetched lazily where the list omits it."""
    if msg.get("text") is not None:
        return msg["text"], msg.get("code")
    if _mail_provider(tokens) == "mailtd":
        return _mailtd_http_body(tokens, msg["id"]), None
    if _mail_provider(tokens) == "yamin":
        try:
            import json as _json
            import urllib.parse as _up
            import urllib.request as _ur
            import ai_config  # noqa: F401  (puts engine/ on sys.path)
            from eng_constants import YAMIN_MAIL_API, YAMIN_AUTH_KEY
            user, _, domain = str(tokens["yamin_email"]).partition("@")
            url = (f"{YAMIN_MAIL_API}/?action=readMessage&user={_up.quote(user)}"
                   f"&domain={_up.quote(domain)}&id={_up.quote(msg['id'])}")
            req = _ur.Request(url, headers={"Authorization": YAMIN_AUTH_KEY, "X-Api-Key": YAMIN_AUTH_KEY})
            with _ur.urlopen(req, timeout=10) as resp:
                body = _json.loads(resp.read().decode("utf-8", "replace")) or {}
            text = " ".join(str(body.get(k) or "") for k in ("subject", "htmlBody", "body", "text"))
            code = str(body.get("code_extracted") or "").strip() or None
            return text, code
        except Exception:
            return "", None
    return "", None


def _mail_ids(tokens) -> set:
    """Ids of every message already in the account's mailbox (the snapshot to ignore)."""
    return {_msg_id(m) for m in _mail_messages(tokens)}


def _mail_http_code(runner, tokens, preexisting_ids, keyword, timeout,
                    subject_hint=None, prefer_len=None, should_stop=None):
    """Poll whichever mailbox the account was created with for a FRESH matching code.

    Dispatches on the account's stored provider (mail.td, Cloudflare catch-all,
    Yamin). Only messages whose id is not in ``preexisting_ids`` count, newest first.
    """
    if not _mail_provider(tokens):
        return None
    end = time.time() + max(5, int(timeout or 60))
    while time.time() < end:
        if should_stop is not None and should_stop():
            return None
        msgs = [m for m in _mail_messages(tokens, runner) if m["id"] not in preexisting_ids]
        msgs.sort(key=lambda m: m["ts"], reverse=True)
        for m in msgs:
            subject = m["subject"].lower()
            sender = m["from"].lower()
            if subject_hint and not m.get("trusted"):
                hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                if not (any(h in subject or h in sender for h in hints)
                        or any(d in sender for d in ("meta", "instagram", "facebook"))):
                    continue
            text, direct = _mail_body(tokens, m)
            code = direct
            if not code and text:
                try:
                    code = runner._pick_code(text, keyword, set(), prefer_len=prefer_len)
                except Exception:
                    code = None
            if code:
                try:
                    runner.log(f'[📧] fresh {keyword} code ({_mail_provider(tokens)}): {code} '
                               f'(subject: {subject[:40]})')
                except Exception:
                    pass
                if isinstance(preexisting_ids, set):
                    preexisting_ids.add(m["id"])
                return str(code)
        time.sleep(0.8)
    return None


def _mailtd_list(runner):
    """Return the raw mail.td message list for the runner's stored inbox."""
    try:
        mail = getattr(runner, "mail", None)
        if mail is None or mail.is_closed():
            return []
        ctx = runner._mailtd_api_ctx()
        if not ctx:
            return []
        res = mail.evaluate("""async ({id, token}) => {
            try {
                const r = await fetch('/api/accounts/' + id + '/messages?page=1',
                    {headers: {Authorization: 'Bearer ' + token}});
                if (!r.ok) return {status: r.status, messages: []};
                const j = await r.json();
                return {status: 200, messages: (j && j.messages) || []};
            } catch (e) { return {status: -1, messages: []}; }
        }""", {"id": ctx["id"], "token": ctx["token"]})
        return (res or {}).get("messages") or []
    except Exception:
        return []


def _mailtd_http_list(tokens):
    """Message list via mail.td REST over plain HTTP — NO browser page/tab.

    The pooled account already stores its own mailbox credential
    (``extra.mail_tokens``), so the OTP can be read with one HTTP GET instead of
    driving a Playwright mail tab (``mail.evaluate(fetch(...))``). Measured
    ~0.7s for the list + ~0.3s for one body on a live inbox.
    """
    try:
        import requests
        tok = (tokens or {}).get("tempmail_token")
        aid = (tokens or {}).get("tempmail_account_id")
        if not tok or not aid:
            return []
        r = requests.get(
            f"https://mail.td/api/accounts/{aid}/messages?page=1",
            headers={"Authorization": "Bearer " + tok, "Accept": "application/json"},
            timeout=12)
        if r.status_code != 200:
            return []
        return (r.json() or {}).get("messages") or []
    except Exception:
        return []


def _mailtd_http_body(tokens, mid):
    """Full message text (subject + html_body + text_body) via plain HTTP."""
    try:
        import requests
        tok = (tokens or {}).get("tempmail_token")
        aid = (tokens or {}).get("tempmail_account_id")
        if not tok or not aid or not mid:
            return ""
        r = requests.get(
            f"https://mail.td/api/accounts/{aid}/messages/{mid}",
            headers={"Authorization": "Bearer " + tok, "Accept": "application/json"},
            timeout=12)
        if r.status_code != 200:
            return ""
        j = r.json() or {}
        return " ".join(str(j.get(k) or "") for k in
                        ("subject", "html_body", "text_body", "text", "body"))
    except Exception:
        return ""


def _mailtd_http_code(runner, tokens, preexisting_ids, keyword, timeout,
                      subject_hint=None, prefer_len=None):
    """Poll the stored inbox over HTTP for a FRESH matching code (no browser).

    Always takes the NEWEST matching message (``created_at`` desc) and never
    returns a code whose message id predates the snapshot. Returns None when
    nothing usable arrives — the caller then falls back to the bot / browser.
    """
    if not tokens:
        return None
    end = time.time() + max(5, int(timeout or 60))
    seen = {}
    while time.time() < end:
        msgs = [m for m in _mailtd_http_list(tokens)
                if str(m.get("id")) not in preexisting_ids]
        try:
            msgs.sort(key=lambda m: str(m.get("created_at") or m.get("createdAt")
                                        or m.get("updated_at") or m.get("updatedAt")
                                        or m.get("id") or ""), reverse=True)
        except Exception:
            pass
        for msg in msgs:
            mid = msg.get("id")
            subject = str(msg.get("subject") or "").lower()
            sender = str(msg.get("from") or msg.get("sender") or "").lower()
            if subject_hint:
                hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                if not (any(h in subject or h in sender for h in hints)
                        or any(d in sender for d in ("meta", "instagram", "facebook"))):
                    continue
            text = seen.get(mid)
            if text is None and mid:
                text = _mailtd_http_body(tokens, mid)
                seen[mid] = text
            try:
                code = runner._pick_code(text or "", keyword, set(), prefer_len=prefer_len)
            except Exception:
                code = None
            if code:
                try:
                    runner.log(f'[📧] fresh {keyword} code (HTTP): {code} '
                               f'(subject: {subject[:40]})')
                except Exception:
                    pass
                if isinstance(preexisting_ids, set):
                    preexisting_ids.add(str(mid))
                return code
        time.sleep(0.8)
    return None


def _make_pool_fetch_code(runner, preexisting_ids, bot=None):
    """A ``fetch_code`` for the pooled flow.

    Order: (1) plain-HTTP read of the account's STORED inbox — fastest, no
    browser tab; (2) the BOT's ``📥 Get code`` (the bot-issued email).

    Deliberately NO browser-tab fallback. ``_ensure_mail_tab`` opened a new
    mail.td tab (goto ≤45s + reload ≤45s) and, on a stale/expired token, polled
    an empty inbox until timeout — the "stuck + mail.td opened in a new tab"
    hang (2026-10-05). The pool account's tokens are already stored, so HTTP is
    the correct source; if both paths miss, the caller already falls through to
    the 2FA submit instead of stalling.
    """
    _tokens = {}
    try:
        _tokens = dict(getattr(runner, "mail_tokens", None) or {})
    except Exception:
        _tokens = {}

    def _fetch(keyword="instagram", timeout=60, subject_hint=None, prefer_len=None, **kwargs):
        # (1) FAST PATH — plain HTTP against the account's stored inbox. The
        #     Accounts-Center challenge mails the account's own address, so this
        #     is both the correct source AND the cheapest read.
        # The account's own mailbox, whichever provider it was created with (mail.td, Cloudflare, Yamin).
        if _mail_provider(_tokens):
            try:
                c = _mail_http_code(runner, _tokens, preexisting_ids, keyword,
                                    timeout, subject_hint=subject_hint, prefer_len=prefer_len)
                if c:
                    return c
            except Exception:
                pass
        else:
            try:
                runner.log("[📧] No stored mailbox token — HTTP OTP read skipped.")
            except Exception:
                pass
        # (2) BOT Get-code (only useful once the bot email is linked).
        if bot is not None:
            try:
                c = bot.request_email_code(timeout=min(int(timeout or 45), 45))
                if c:
                    try:
                        runner.log(f"[📧] bot Get-code returned: {c}")
                    except Exception:
                        pass
                    return c
            except Exception:
                pass
        try:
            runner.log("[📧] No OTP from stored inbox or bot — not opening a mail tab; "
                       "continuing (the caller falls through to 2FA).")
        except Exception:
            pass
        return None
    return _fetch


def _purge_pool_account(store, cand, log, slot_id, emit_event, reason):
    """Permanently remove a pooled account that cannot be used (dead session,
    login wall, no 2FA key). Never cancels the TG task — the caller just moves
    on to the next account."""
    cid = (cand or {}).get("id")
    if not cid:
        return
    try:
        store.delete_record(cid)
    except Exception:
        pass
    sf = (cand or {}).get("session_file")
    if sf and os.path.exists(sf):
        try:
            os.remove(sf)
        except Exception:
            pass
    try:
        log(slot_id, f"[pool] Purged account {cid} ({reason}) — trying the next.")
    except Exception:
        pass
    emit_event({"type": "account_deleted", "account_id": cid})
    emit_event({"type": "accounts_updated"})


def _browser_logged_in(page) -> bool:
    """True when the injected pooled session is actually logged in.

    A logged-OUT browser shows the saved-account chooser ("Use another
    profile"), the /accounts/login wall, or a public visitor view ("Log in" +
    "Open app"). The benign "Save your login info" sheet is NOT a logged-out
    signal, so it must not be treated as one.
    """
    try:
        url = (page.url or "").lower()
        t = (page.inner_text("body") or "").lower()
    except Exception:
        return True
    if "/accounts/login" in url:
        return False
    if "use another profile" in t:
        return False
    if ("log in" in t or "login" in t) and "open app" in t:
        return False
    return True
