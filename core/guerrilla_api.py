"""Guerrilla Mail over its HTTP API (https://api.guerrillamail.com/ajax.php) — no browser tab.

An inbox is a session: ``get_email_address`` returns the address and a ``sid_token``. The
session expires, but the address does not: ``set_email_user`` with just the part before the
@ re-attaches the same inbox to a new session. So the stored account keeps the full address
(and the last sid as a fast path) and a later 2FA / re-login can always read the mailbox again.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Optional

BASE_URL = "https://api.guerrillamail.com/ajax.php"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# address -> newest sid_token seen in this process (a restore swaps the sid; every reader shares it)
_SIDS: dict = {}
# (address, mail_id) -> normalised message: a body is fetched once
_BODIES: dict = {}


def _call(fn: str, sid: str = "", **params) -> Optional[dict]:
    q = {"f": fn, "ip": "127.0.0.1", "agent": "Mozilla"}
    if sid:
        q["sid_token"] = sid
    q.update({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(BASE_URL + "?" + urllib.parse.urlencode(q),
                                 headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def create_inbox() -> tuple:
    """(address, sid_token) of a brand-new inbox, or ('', '')."""
    for _ in range(3):
        d = _call("get_email_address", lang="en")
        if d and d.get("email_addr") and d.get("sid_token"):
            email = str(d["email_addr"]).strip().lower()
            _SIDS[email] = str(d["sid_token"])
            return email, _SIDS[email]
        time.sleep(1.0)
    return "", ""


def restore(email: str) -> str:
    """Re-attach an existing address to a fresh session. Returns the new sid_token or ''."""
    user = str(email or "").partition("@")[0].strip().lower()
    if not user:
        return ""
    d = _call("set_email_user", email_user=user, lang="en")
    sid = str((d or {}).get("sid_token") or "")
    if sid:
        _SIDS[str(email).strip().lower()] = sid
    return sid


def _sid_for(email: str, sid: str = "") -> str:
    return _SIDS.get(email) or sid or ""


def _check(email: str, sid: str) -> Optional[list]:
    """Inbox list for the address, restoring the session when it has expired. None = unreadable."""
    email = str(email or "").strip().lower()
    cur = _sid_for(email, sid)
    for attempt in range(2):
        if not cur:
            cur = restore(email)
            if not cur:
                return None
        d = _call("check_email", cur, seq=0)
        if d is not None and isinstance(d.get("list"), list):
            return d["list"]
        # "Please call get_email_address or set_email_user first" = the session is gone.
        _SIDS.pop(email, None)
        cur = ""
    return None


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def list_messages(email: str, sid: str = "") -> list:
    """Messages as dicts with id, subject, from, ts and text (body fetched once per message). [] on failure."""
    email = str(email or "").strip().lower()
    items = _check(email, sid)
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("mail_id"):
            continue
        mid = str(it["mail_id"])
        msg = _BODIES.get((email, mid))
        if msg is None:
            subject = str(it.get("mail_subject") or "")
            text = " ".join((subject, str(it.get("mail_excerpt") or "")))
            body = _call("fetch_email", _sid_for(email, sid), email_id=mid)
            raw = ""
            if body and body.get("mail_body"):
                raw = str(body["mail_body"])
                text = " ".join((subject, _strip(raw)))
            # "html" keeps the links (a reset-password mail has its link only in an href).
            msg = {"id": mid, "subject": subject, "from": str(it.get("mail_from") or "").lower(),
                   "ts": str(it.get("mail_timestamp") or ""), "text": text, "code": None, "html": raw}
            # Cache only a fetched body: an excerpt-only message is retried next poll.
            if body and body.get("mail_body"):
                _BODIES[(email, mid)] = msg
        out.append(msg)
    return out


def current_sid(email: str, fallback: str = "") -> str:
    return _SIDS.get(str(email or "").strip().lower()) or fallback


def wait_code(runner, email: str, sid: str = "", keyword: str = "instagram", timeout: int = 180,
              seen: Optional[set] = None, subject_hint=None, prefer_len=None,
              interval: float = 2.0) -> Optional[str]:
    """Poll the inbox until a fresh code for keyword arrives (ids in `seen` are ignored)."""
    seen = seen if seen is not None else set()
    end = time.time() + max(5, int(timeout or 180))
    while time.time() < end:
        for m in list_messages(email, sid):
            if m["id"] in seen:
                continue
            subject = m["subject"].lower()
            sender = m["from"].lower()
            if subject_hint:
                hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                if not (any(h in subject or h in sender for h in hints)
                        or any(d in sender for d in ("meta", "instagram", "facebook"))):
                    continue
            try:
                code = runner._pick_code(m["text"] or "", keyword, set(), prefer_len=prefer_len)
            except Exception:
                code = None
            if code:
                seen.add(m["id"])
                try:
                    runner.log(f'[📧] fresh {keyword} code (Guerrilla API): {code} (subject: {subject[:40]})')
                except Exception:
                    pass
                return str(code)
        time.sleep(interval)
    return None
