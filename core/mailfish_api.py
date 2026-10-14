"""tempmail.fish Premium developer API (https://api.tempmail.fish/v1, header X-API-Key).

Used for NEW accounts when TEMPMAILFISH_API_KEY is set. Accounts created before that
(web inbox + authKey) keep the browser/authKey path in core/mailbox.py and pool_common.py.
The key is read from the environment (or .env) and is never stored on the account.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

BASE_URL = "https://api.tempmail.fish/v1"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def api_key() -> str:
    """The premium API key: environment first, then the project's .env file."""
    key = os.environ.get("TEMPMAILFISH_API_KEY", "").strip()
    if key:
        return key
    for name in (".env.local", ".env"):
        try:
            with open(os.path.join(_ROOT, name), encoding="utf-8") as fh:
                for line in fh:
                    k, sep, v = line.strip().partition("=")
                    if sep and k.strip() == "TEMPMAILFISH_API_KEY" and v.strip():
                        return v.strip().strip('"').strip("'")
        except OSError:
            pass
    try:  # key saved from the dashboard (IG creator panel)
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            return str((json.load(fh) or {}).get("tempmailfish_api_key") or "").strip()
    except (OSError, ValueError, AttributeError):
        return ""


SETTINGS_FILE = os.path.join(_ROOT, "data", "settings.json")


def mode() -> str:
    """'api' (Premium API inboxes, the default) or 'web' (browser inboxes). Set from the IG creator panel."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            value = str((json.load(fh) or {}).get("mailfish_mode") or "api").strip().lower()
    except (OSError, ValueError, AttributeError):
        value = "api"
    return "web" if value == "web" else "api"


def alias_style() -> str:
    """'random' (8-12 random characters, default) or 'name' (firstlast+digits). Set from the IG creator panel."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            value = str((json.load(fh) or {}).get("mailfish_alias_style") or "random").strip().lower()
    except (OSError, ValueError, AttributeError):
        value = "random"
    return "name" if value == "name" else "random"


def api_enabled() -> bool:
    """New accounts use the API inbox only when the mode is 'api' AND a key is configured."""
    return mode() == "api" and bool(api_key())


# Premium domains only: new inboxes are created on these three, and nothing else.
PREMIUM_DOMAINS = ("coolember.com", "pepperhill.info", "sunnygrove.info")


def _request(method: str, path: str, key: str, timeout: int = 15, body: Optional[dict] = None):
    """(status, parsed JSON or None). HTTP errors return their status with no body."""
    data = None
    headers = {"X-API-Key": key, "Accept": "application/json", "User-Agent": _UA}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE_URL + path, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except OSError:
        # Timeouts and connection drops are "no answer yet", not a crash: the caller keeps polling.
        return 0, None


_ALIAS_FIRST = ("james", "olivia", "liam", "emma", "noah", "ava", "mason", "mia", "ethan", "ella",
                "lucas", "sophia", "henry", "grace", "jack", "chloe", "ryan", "lily", "adam", "zoe")
_ALIAS_LAST = ("smith", "jones", "brown", "taylor", "wilson", "moore", "clark", "lewis", "young", "king",
               "walker", "hall", "allen", "wright", "scott", "green", "baker", "adams", "nelson", "hill")


def _alias(style: str) -> str:
    import random
    import string
    if style == "name":
        # a person-looking local part (firstlast + digits) instead of random characters. The API only
        # accepts letters and digits (a dot, underscore or hyphen gives HTTP 400).
        return f"{random.choice(_ALIAS_FIRST)}{random.choice(_ALIAS_LAST)}{random.randint(10, 999)}"
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(random.randint(8, 12)))


# The API answers a burst of creations with 502 (gateway overload) / 429 / a timeout (status 0).
# Those are "try again", not "no inbox": 20 slots starting together used to fall back to the slow
# web inbox on most of them. At most CREATE_PARALLEL requests are in flight per process.
import threading as _threading
CREATE_PARALLEL = int(os.environ.get("TEMPMAILFISH_CREATE_PARALLEL", "4") or 4)
_create_gate = _threading.BoundedSemaphore(max(1, CREATE_PARALLEL))
_RETRY_STATUS = (0, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524)   # 52x = Cloudflare: origin down
last_failure = ""          # why the last create_inbox() returned '': "down" (not answering) | "other"


CREATE_BUDGET_SEC = float(os.environ.get("TEMPMAILFISH_CREATE_BUDGET", "25") or 25)


def create_inbox(key: Optional[str] = None, attempts: int = 4, style: str = "random") -> str:
    """Create an inbox on a premium domain. ``style`` is "random" (8-12 random characters, the
    default) or "name" (firstlast+digits). Returns the address, or '' on failure.

    Overload answers (502/429/...) are retried, but only inside CREATE_BUDGET_SEC in total, and a server that
    does not answer at all (status 0 twice in a row) is treated as down at once, so the caller can fall back
    to the next mail provider instead of sitting on a blank page."""
    import random
    global last_failure
    last_failure = ""
    key = key or api_key()
    if not key:
        return ""
    deadline = time.time() + max(5.0, CREATE_BUDGET_SEC)
    transient = 0
    silent = 0
    tries = 0
    while tries < attempts and time.time() < deadline:
        alias = _alias(style)
        domain = random.choice(PREMIUM_DOMAINS)
        with _create_gate:
            status, data = _request("POST", "/emails/custom", key, timeout=12, body={"alias": alias, "domain": domain})
        if status == 200 and isinstance(data, dict) and data.get("email"):
            return str(data["email"]).strip().lower()
        if status in _RETRY_STATUS:
            silent = silent + 1 if status == 0 else 0
            transient += 1
            if status in (0, 520, 521, 522, 523, 524):
                last_failure = "down"
            if silent >= 2 or transient >= 6:
                last_failure = last_failure or "down"
                break                      # not answering / still overloaded: let the caller fall back
            time.sleep(min(max(0.0, deadline - time.time()), min(6.0, 1.0 * transient) + random.random()))
            continue
        tries += 1
        # 409 / already taken: try another alias. Anything else: stop.
        if status not in (409, 422):
            last_failure = "other"
            break
    return ""


def _path(email: str) -> str:
    return "/emails/" + urllib.parse.quote(email, safe="")


def _as_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("messages", "emails", "data", "items", "result"):
            if isinstance(data.get(k), list):
                return data[k]
    return []


def list_messages(email: str, key: Optional[str] = None) -> list:
    """Messages for an inbox as dicts with id, subject, from, ts and text. [] on failure."""
    key = key or api_key()
    if not key or not email:
        return []
    status, data = _request("GET", _path(email), key)
    if status != 200:
        return []
    out = []
    for m in _as_list(data):
        if not isinstance(m, dict):
            continue
        ts = str(m.get("timestamp") or m.get("createdAt") or m.get("created_at") or "")
        subject = str(m.get("subject") or "")
        mid = str(m.get("id") or f"{ts}|{subject}")
        text = " ".join(str(m.get(k) or "") for k in ("subject", "textBody", "body", "text", "html", "content"))
        out.append({"id": mid, "subject": subject,
                    "from": str(m.get("from") or m.get("sender") or ""),
                    "ts": ts, "text": text, "code": None})
    return out


def delete_inbox(email: str, key: Optional[str] = None) -> bool:
    key = key or api_key()
    if not key or not email:
        return False
    status, _ = _request("DELETE", _path(email), key)
    return status in (200, 204)


def wait_code(runner, email: str, keyword: str = "instagram", timeout: int = 180,
              seen: Optional[set] = None, subject_hint=None, prefer_len=None,
              key: Optional[str] = None, interval: float = 2.0) -> Optional[str]:
    """Poll a fresh inbox until a code for keyword arrives. Messages whose id is in
    `seen` are ignored. Returns the code, or None when the window ends."""
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
        for m in list_messages(email, key):
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
                    runner.log(f'[📧] fresh {keyword} code (tempmail.fish API): {code} (subject: {subject[:40]})')
                except Exception:
                    pass
                return str(code)
        time.sleep(interval)
    return None
