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


def _mail_tokens_from_extra(extra) -> dict:
    """Extract the stored mail.td {tempmail_account_id, tempmail_token}."""
    try:
        ex = extra
        if isinstance(ex, str):
            ex = json.loads(ex) if ex.strip() else {}
        toks = (ex or {}).get("mail_tokens") or {}
        if isinstance(toks, dict) and toks.get("tempmail_token"):
            return toks
    except Exception:
        pass
    return {}


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
        if _tokens.get("tempmail_token"):
            try:
                c = _mailtd_http_code(runner, _tokens, preexisting_ids, keyword,
                                      timeout, subject_hint=subject_hint, prefer_len=prefer_len)
                if c:
                    return c
            except Exception:
                pass
        else:
            try:
                runner.log("[📧] No stored mail.td token — HTTP OTP read skipped.")
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
