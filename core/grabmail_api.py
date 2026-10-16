"""grabmail.io mailbox provider — https://grabmail.io/api/v1 (no key on public domains).

A mailbox is never *created* here: it exists the moment a message arrives at an
address, and its mail is deleted 5 days later. "Creating an inbox" therefore only
means picking a name, and the whole session is that address. That address is what
gets stored on the account (``grabmail_email``) so a later 2FA task can read the OTP
back out of the same mailbox over plain HTTP — no browser tab, no token.

Endpoints (all JSON, receive-only):

    GET  /mailbox?address=&limit=&before=   -> {address, alias, count, next, messages:[…]}
    GET  /message/{id}?mailbox=<address>    -> {id, …, text, html, attachments}
    DELETE /message/{id}?mailbox=<address>  -> {deleted: true}
    GET  /domains                           -> public names, premium names only with a paid key
    GET  /me                                -> validate a key

Public domains (@grabmail.io, @mixozia.com, @linqmail.com) need no key but sit on the
public disposable-mail blocklists, so Meta often refuses them. With a key in
GRABMAIL_API_KEY (env, .env, or the settings file) the premium pool of private .com
domains is used instead: those addresses must be read with a valid key, so the key is
looked up at read time and — like mailfish_api — is never stored on the account.

Rate limits: free = 60 requests/minute, 1000/day per IP, and one read per second per
address (that is why polling defaults to 2 s). 429 carries Retry-After, so a throttled
poll waits instead of hammering.
"""
from __future__ import annotations

import json
import os
import random
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

BASE_URL = "https://grabmail.io/api/v1"
PUBLIC_DOMAINS = ("grabmail.io", "mixozia.com", "linqmail.com")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(_ROOT, "data", "settings.json")

last_failure = ""       # why the last create_inbox() returned '': "down" (not answering) | "other"
last_domain = ""        # the domain the last create_inbox() picked (for logs)


def _settings() -> dict:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def api_key() -> str:
    """Premium key: environment first, then .env, then the dashboard setting."""
    key = os.environ.get("GRABMAIL_API_KEY", "").strip()
    if key:
        return key
    for name in (".env.local", ".env"):
        try:
            with open(os.path.join(_ROOT, name), encoding="utf-8") as fh:
                for line in fh:
                    k, sep, v = line.strip().partition("=")
                    if sep and k.strip() == "GRABMAIL_API_KEY" and v.strip():
                        return v.strip().strip('"').strip("'")
        except OSError:
            pass
    return str(_settings().get("grabmail_api_key") or "").strip()


def mode() -> str:
    """'auto' (default: premium pool when a key works, else public) or 'public' (never premium)."""
    return "public" if str(_settings().get("grabmail_mode") or "auto").strip().lower() == "public" else "auto"


def alias_style() -> str:
    """'random' (default) or 'name' (firstlast+digits); mirrors the tempmail.fish control."""
    return "name" if str(_settings().get("grabmail_alias_style") or "random").strip().lower() == "name" else "random"


def _request(method: str, path: str, key: Optional[str] = None, timeout: int = 12,
             params: Optional[dict] = None, body: Optional[dict] = None):
    """(status, parsed JSON or None, retry_after_seconds).

    ``status == 0`` means the service did not answer at all (timeout / DNS / offline).
    """
    url = BASE_URL + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "User-Agent": _UA}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else None), 0
    except urllib.error.HTTPError as exc:
        retry = 0
        try:
            retry = int(exc.headers.get("Retry-After") or 0)
        except (TypeError, ValueError):
            retry = 0
        return exc.code, None, retry
    except OSError:
        return 0, None, 0


def retry_after_seconds(status: int, retry_after: int) -> float:
    """How long to wait after a throttled/missing answer. Honours Retry-After."""
    if retry_after > 0:
        return float(retry_after)
    return 1.0 if status == 429 else 0.0


# ------------------------------------------------------------------ domains
_premium_cache = {"key": "", "domains": []}


def premium_domains(key: Optional[str] = None) -> list:
    """Private pool names — only returned by the API for a paid key (cached per key)."""
    key = key if key is not None else api_key()
    if not key:
        return []
    if _premium_cache["key"] == key:
        return _premium_cache["domains"]
    status, data, _ = _request("GET", "/domains", key, timeout=10)
    names = []
    if status == 200 and isinstance(data, dict):
        prem = data.get("premium") or {}
        if prem.get("unlocked") and isinstance(prem.get("domains"), list):
            names = [str(d).strip().lower() for d in prem["domains"] if d]
    _premium_cache.update(key=key, domains=names)
    return names


def _alias(style: str) -> str:
    """Local part. The API accepts any name on the public domains, so this is free choice."""
    if style == "name":
        first = random.choice(("james", "olivia", "liam", "emma", "noah", "ava", "mason", "mia",
                               "ethan", "ella", "lucas", "sophia", "henry", "grace", "jack", "chloe"))
        last = random.choice(("smith", "jones", "brown", "taylor", "wilson", "moore", "clark",
                              "lewis", "young", "king", "walker", "hall", "allen", "wright"))
        return f"{first}{last}{random.randint(10, 999)}"
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(random.randint(8, 12)))


def create_inbox(style: str = "random", key: Optional[str] = None) -> str:
    """Pick an address and confirm the service answers. Returns the address, or '' on failure.

    A mailbox does not have to be registered, so this is: choose a domain (the premium
    pool when a key works and mode is not 'public', else a public one), choose a name,
    then one read — which also *holds* a premium address to this key so nobody else can
    read that mailbox. A service that does not answer at all sets ``last_failure='down'``
    so the caller can fall back to the next provider instead of sitting on a dead mailbox.
    """
    global last_failure, last_domain
    last_failure = ""
    key = key if key is not None else api_key()
    domains = []
    if key and mode() != "public":
        domains = premium_domains(key)
    domain = random.choice(domains or list(PUBLIC_DOMAINS))
    last_domain = domain
    address = f"{_alias(style)}@{domain}"
    status, data, retry = _request("GET", "/mailbox", key, timeout=10, params={"address": address})
    if status == 0:
        last_failure = "down"
        return ""
    if status == 200:
        return str((data or {}).get("address") or address).strip().lower()
    if status == 429:
        return address                      # throttled, not broken: the address still works
    if status == 404 and domain in domains:
        # the key lost access to the pool between calls: fall back to a public domain
        address = f"{_alias(style)}@{random.choice(list(PUBLIC_DOMAINS))}"
        status2, _d, _r = _request("GET", "/mailbox", None, timeout=10, params={"address": address})
        return "" if status2 == 0 else address
    last_failure = "other"
    return ""


# ------------------------------------------------------------------ messages
def _as_messages(data) -> list:
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"]
    if isinstance(data, list):
        return data
    return []


def list_messages(email: str, key: Optional[str] = None, limit: int = 50) -> list:
    """Message list for an inbox. NOTE: the list carries no body — read one for the text.

    Returns the pool-normalised shape (id, subject, from, ts, text=None, code=None) so
    ``pool_common._mail_body`` fetches the body lazily, exactly like mail.td/Yamin.
    """
    if not email:
        return []
    key = key if key is not None else api_key()
    status, data, _ = _request("GET", "/mailbox", key, params={"address": email, "limit": int(limit)})
    if status != 200:
        return []
    out = []
    for m in _as_messages(data):
        if not isinstance(m, dict):
            continue
        out.append({
            "id": str(m.get("id") or ""),
            "subject": str(m.get("subject") or ""),
            "from": str(m.get("from") or ""),
            "ts": str(m.get("date") or m.get("expires_at") or ""),
            "text": None,                 # fetched per message by read_message()
            "code": None,
        })
    return [m for m in out if m["id"]]


def read_message(email: str, mid: str, key: Optional[str] = None) -> dict:
    """One message with headers, plain text and html. {} on failure."""
    if not email or not mid:
        return {}
    key = key if key is not None else api_key()
    status, data, _ = _request("GET", f"/message/{urllib.parse.quote(str(mid), safe='')}",
                               key, params={"mailbox": email})
    return data if status == 200 and isinstance(data, dict) else {}


def body_text(msg: dict) -> str:
    """Everything searchable in a message: subject + plain text + html."""
    if not isinstance(msg, dict):
        return ""
    return " ".join(str(msg.get(k) or "") for k in ("subject", "text", "html"))


def delete_message(email: str, mid: str, key: Optional[str] = None) -> bool:
    """Remove a message now instead of waiting out the 5-day retention window."""
    if not email or not mid:
        return False
    key = key if key is not None else api_key()
    status, _data, _r = _request("DELETE", f"/message/{urllib.parse.quote(str(mid), safe='')}",
                                 key, params={"mailbox": email})
    return status in (200, 204)


def is_public(address: str) -> bool:
    """True when the address is on a keyless public domain (readable by anyone who knows it)."""
    return str(address or "").partition("@")[2].lower() in PUBLIC_DOMAINS


# ------------------------------------------------------------------ polling
def wait_code(runner, email: str, keyword: str = "meta", timeout: int = 180,
              seen: Optional[set] = None, subject_hint=None, prefer_len=None,
              key: Optional[str] = None, interval: float = 2.0) -> Optional[str]:
    """Poll a grabmail inbox until a code for ``keyword`` arrives; ids in ``seen`` are ignored.

    One read per second per address is the free-tier limit, so one poll is one list call
    plus at most one message read per new message that passes the subject filter.
    """
    seen = seen if seen is not None else set()
    end = time.time() + max(5, int(timeout or 180))
    while time.time() < end:
        try:
            from core import vpn_rotate
            if vpn_rotate.swap_pending():
                runner.log("[🌍] NordVPN swap queued — giving up on this email code (same blocked IP).")
                return None
        except Exception:
            pass
        status, data, retry = _request("GET", "/mailbox", key or api_key(),
                                       params={"address": email, "limit": 50})
        if status == 0:
            time.sleep(min(5.0, interval))
            continue
        wait = retry_after_seconds(status, retry)
        if status != 200:
            time.sleep(wait or interval)
            continue
        for m in _as_messages(data):
            if not isinstance(m, dict):
                continue
            mid = str(m.get("id") or "")
            if not mid or mid in seen:
                continue
            subject = str(m.get("subject") or "").lower()
            sender = str(m.get("from") or "").lower()
            if subject_hint:
                hints = [h.strip().lower() for h in str(subject_hint).split("|") if h.strip()]
                if not (any(h in subject or h in sender for h in hints)
                        or any(d in sender for d in ("meta", "instagram", "facebook"))):
                    continue
            msg = read_message(email, mid, key)
            seen.add(mid)
            text = body_text(msg) if msg else subject
            try:
                code = runner._pick_code(text, keyword, set(), prefer_len=prefer_len)
            except Exception:
                code = None
            if code:
                try:
                    runner.log(f'[📧] fresh {keyword} code (grabmail): {code} '
                               f'(subject: {subject[:40]})')
                except Exception:
                    pass
                return str(code)
        time.sleep(max(1.0, interval))
    return None
