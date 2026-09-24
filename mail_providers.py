"""
meta_auto_ai — multi-tier temp-mail providers (self-contained)
===============================================================
Shared email engine used by ``runner.MetaInstaRunner.open_rest_provider``.

Fallback chain (first success wins):
  1. tempmail.fish  — https://api.tempmail.fish (REST, authKey)
  2. Guerrilla Mail — https://api.guerrillamail.com/ajax.php (sid_token)
  3. mail.tm        — https://api.mail.tm (account + bearer token)
  4. mail.td        — legacy web inbox (handled by the caller, not here)

Only stdlib + ``requests``. No imports from sibling projects — this module
is fully self-contained (design mirrors Nova's provider architecture:
strict-order registry + ``create_any_provider`` auto chain).

Patterns:
* ``BaseTempMailProvider`` — recursive text harvester, OTP waterfall
  (keyword-anchored 4-8 digits -> 6-digit -> 5-digit -> 4-digit) with
  year filtering (2000-2035 for 6/5-digit, 1900-2035 for 4-digit),
  MD5 message-hash dedup, 3-5s polling.
* Provider registry + ``create_any_provider`` strict-order fallback.
"""

from __future__ import annotations

import hashlib
import random
import re
import string
import time

import requests

PROVIDER_LIST = ("tempmail.fish", "Guerrilla", "mail.tm", "temp-mails")

_OTP_POLL_MIN = 3.0
_OTP_POLL_MAX = 5.0


def safe_str(value, max_len=50) -> str:
    """Truncate anything to a short log-safe string."""
    try:
        text = str(value if value is not None else "")
    except Exception:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[:max_len]
    return text


class BaseTempMailProvider:
    """Common OTP plumbing. Subclasses implement transport only."""

    name = "base"

    def __init__(self, log_func=None, profile_tag=""):
        self._log = log_func or (lambda m: None)
        self.profile_tag = profile_tag
        self.email = None
        self.auth_key = None
        self._used_hashes = set()
        self._accepted_otps = set()
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    # -- transport (override) -------------------------------------------
    def generate_new(self) -> str:
        raise NotImplementedError

    def list_messages(self) -> list:
        raise NotImplementedError

    def cleanup(self) -> None:
        return None

    # -- shared helpers ---------------------------------------------------
    def _extract_all_text(self, msg: dict) -> str:
        """Recursively harvest text from any JSON mail object (depth 5)."""
        collected = []
        ignored = {
            "id", "_id", "message_id", "msgid", "mail_id", "date",
            "created_at", "createdat", "receivedat", "authkey",
            "isread", "isseen",
        }

        def collect(obj, depth=0):
            if depth > 5:
                return
            if isinstance(obj, (str, int, float)):
                collected.append(str(obj))
            elif isinstance(obj, dict):
                for key, val in obj.items():
                    if str(key).lower() not in ignored:
                        collect(val, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    collect(item, depth + 1)

        collect(msg)
        raw = " ".join(collected)
        clean = re.sub(r"<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", clean).strip()

    def _extract_candidates(self, clean_text: str, prefer_len=None) -> list:
        """OTP waterfall: 6-digit codes first, shorter fallbacks after.

        Meta/Instagram forms demand exactly 6 digits — an early
        keyword-anchored hit on a 4-digit fragment (footer IDs, split
        markup) used to win over the real code and get submitted to a
        6-digit field. Order is now: keyword-anchored 6-digit ->
        standalone 6-digit (plus a whitespace-collapsed pass for codes
        split across HTML spans, e.g. "4 8 3 9 2 0") -> keyword-anchored
        4-8 -> standalone 5-digit -> standalone 4-digit. Year-looking
        numbers are discarded (2000-2035 for 6/5-digit, 1900-2035 for
        4-digit) so dates never surface as codes.

        ``prefer_len`` (e.g. 8 for the "Authenticate your profile" email
        challenge) is tried FIRST as a standalone digit run, since that
        challenge's 8-digit code may sit far from any code keyword.
        """
        candidates = []

        def _add(match, lo=None, hi=None):
            try:
                if not match or not str(match).isdigit():
                    return
                if match in candidates:
                    return
                if lo is not None:
                    try:
                        if lo <= int(match) <= hi:
                            return
                    except Exception:
                        pass
                candidates.append(match)
            except Exception:
                pass

        texts = [clean_text]
        try:
            joined = re.sub(r"(?<=\d)\s+(?=\d)", "", clean_text)
            if joined != clean_text:
                texts.append(joined)
        except Exception:
            pass

        # Tier 0: preferred exact length first (AC email challenge = 8).
        try:
            _pl = int(prefer_len) if prefer_len else 0
        except Exception:
            _pl = 0
        if _pl >= 4:
            for text in texts:
                try:
                    for match in re.findall(rf"\b(\d{{{_pl}}})\b", text):
                        _add(match, 2000, 2035)
                except Exception:
                    pass

        # Tier 1: keyword-anchored exact 6-digit.
        for text in texts:
            try:
                for match in re.findall(
                    r"(?:code|otp|pin|verification|verify|passcode)\s*[:\-is]*\s*(\d{6})\b",
                    text, re.IGNORECASE):
                    _add(match, 2000, 2035)
            except Exception:
                pass
        # Tier 2: standalone 6-digit.
        for text in texts:
            try:
                for match in re.findall(r"\b(\d{6})\b", text):
                    _add(match, 2000, 2035)
            except Exception:
                pass
        # Tier 3: keyword-anchored 4-8 digits (short-code forms fallback).
        try:
            for match in re.findall(
                r"(?:code|otp|pin|verification|verify|passcode)\s*[:\-is]*\s*(\d{4,8})\b",
                clean_text, re.IGNORECASE):
                if not match.isdigit() or not 4 <= len(match) <= 8:
                    continue
                if len(match) in (5, 6):
                    _add(match, 2000, 2035)
                elif len(match) == 4:
                    _add(match, 1900, 2035)
                else:
                    _add(match)
        except Exception:
            pass
        # Tier 4: standalone 5-digit (skip 2000-2035).
        try:
            for match in re.findall(r"\b(\d{5})\b", clean_text):
                _add(match, 2000, 2035)
        except Exception:
            pass
        # Tier 5: standalone 4-digit (skip 1900-2035).
        try:
            for match in re.findall(r"\b(\d{4})\b", clean_text):
                if match in candidates:
                    continue
                try:
                    num = int(match)
                except Exception:
                    candidates.append(match)
                    continue
                if 1900 <= num <= 2035:
                    continue
                candidates.append(match)
        except Exception:
            pass
        return candidates

    def wait_for_otp(self, timeout=180, keyword="meta", skip_otps=None,
                     subject_hint=None, prefer_len=None) -> str | None:
        """Poll the inbox for an OTP (3-5s interval, MD5 dedup).

        Guide "Way Of Getting Out" (Scenario 2): the Accounts Center email
        challenge ALWAYS comes as subject "Authenticate your profile" from
        noreply@account.meta.com with an 8-digit code. Pass
        ``subject_hint="authenticate your profile", prefer_len=8`` and the
        poll scans newest-first for hint-matching messages before falling
        back to the legacy unfiltered content waterfall (Meta 6-digit
        confirm codes etc.).
        """
        _ = keyword  # keyword kept for API parity; waterfall is content-based.
        skip_set = set(skip_otps or [])
        hint = str(subject_hint or "").strip().lower() or None
        self._log(f"[📧] Polling {self.email} for OTP (up to {timeout}s)...")
        start = time.time()
        poll = 0
        consecutive_fail = 0
        while time.time() - start < timeout:
            try:
                messages = self.list_messages()
                consecutive_fail = 0
            except Exception as exc:
                consecutive_fail += 1
                self._log(f"[⚠️] list_messages err: {exc}")
                time.sleep(min(3.0 * consecutive_fail, 15.0))
                continue
            order = list(reversed(messages)) if hint else list(messages)
            deferred = []
            for idx, msg in enumerate(order):
                if not isinstance(msg, dict):
                    continue
                try:
                    msg_id = (
                        msg.get("id") or msg.get("_id") or msg.get("message_id")
                        or msg.get("msgid") or msg.get("mail_id") or f"idx_{idx}"
                    )
                    date = (
                        msg.get("date") or msg.get("created_at")
                        or msg.get("createdAt") or msg.get("timestamp")
                        or msg.get("mail_timestamp") or ""
                    )
                    sender = (
                        msg.get("from") or msg.get("sender")
                        or msg.get("mail_from") or msg.get("fromAddr") or ""
                    )
                    subject = (
                        msg.get("subject") or msg.get("mail_subject")
                        or msg.get("headerSubject") or ""
                    )
                    sig = hashlib.md5(
                        f"{msg_id}|{date}|{sender}|{subject}".encode()
                    ).hexdigest()
                    if sig in self._used_hashes:
                        continue
                    matched_hint = bool(hint) and hint in f"{subject} {sender}".lower()
                    if hint and not matched_hint:
                        deferred.append((msg, subject, sig))
                        continue
                    full_text = self._extract_all_text(msg)
                    clean = re.sub(r"<[^>]+>", " ", full_text)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    candidates = self._extract_candidates(clean, prefer_len=prefer_len)
                    for otp in candidates:
                        if otp in skip_set or otp in self._accepted_otps:
                            continue
                        self._used_hashes.add(sig)
                        self._accepted_otps.add(otp)
                        self._log(
                            f"[📧] OTP FOUND: {otp} "
                            f"(subject: '{safe_str(subject, 40)}')"
                        )
                        return otp
                except Exception:
                    continue
            if hint and deferred:
                # Pass 2: no hint-matching message held a code — legacy
                # unfiltered scan over the deferred messages (API order).
                for msg, subject, sig in deferred:
                    try:
                        full_text = self._extract_all_text(msg)
                    except Exception:
                        continue
                    clean = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", full_text or "")).strip()
                    for otp in self._extract_candidates(clean, prefer_len=prefer_len):
                        if otp in skip_set or otp in self._accepted_otps:
                            continue
                        self._used_hashes.add(sig)
                        self._accepted_otps.add(otp)
                        self._log(f"[📧] OTP FOUND (unfiltered fallback): {otp} "
                                  f"(subject: '{safe_str(subject, 40)}')")
                        return otp
            poll += 1
            if poll % 5 == 0:
                elapsed = int(time.time() - start)
                self._log(
                    f"[📧] Waiting for email... ({elapsed}s elapsed, "
                    f"{len(messages)} msgs)"
                )
            time.sleep(random.uniform(_OTP_POLL_MIN, _OTP_POLL_MAX))
        self._log(f"[⚠️] No OTP received within {timeout}s.")
        return None


class TempMailFishProvider(BaseTempMailProvider):
    """api.tempmail.fish — REST inbox (authKey header)."""

    name = "tempmail.fish"
    BASE_URL = "https://api.tempmail.fish"

    def __init__(self, log_func=None, profile_tag=""):
        super().__init__(log_func, profile_tag)
        # The provider factory treats construction as acquisition.  The old
        # implementation only implemented generate_new(), so every factory
        # instance returned with email=None and was rejected as an "empty
        # inbox" even though the REST endpoint was healthy.
        self.generate_new()

    def generate_new(self) -> str:
        self._log("[📧] Requesting fresh email from api.tempmail.fish...")
        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    f"{self.BASE_URL}/emails/new-email",
                    headers=self._headers,
                    timeout=30,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self.email = data.get("email") or data.get("emailAddress") or ""
                    self.auth_key = data.get("authKey") or data.get("auth_key") or ""
                    if self.email:
                        self._log(
                            f"[📧] TempMail.fish inbox: {self.email}"
                        )
                        return self.email
                self._log(
                    f"[⚠️] tempmail.fish create HTTP {resp.status_code}, retrying..."
                )
            except Exception as exc:
                self._log(f"[⚠️] tempmail.fish attempt {attempt} error: {exc}")
            time.sleep(1.5)
        raise RuntimeError(f"Failed to generate temp email from {self.BASE_URL}")

    def list_messages(self) -> list:
        if not self.email or not self.auth_key:
            return []
        headers = dict(self._headers)
        headers["Authorization"] = self.auth_key
        resp = requests.get(
            f"{self.BASE_URL}/emails/emails",
            params={"emailAddress": self.email},
            headers=headers,
            timeout=25,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("emails", "messages", "data", "items", "result"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def cleanup(self) -> None:
        if not self.email or not self.auth_key:
            return
        headers = dict(self._headers)
        headers["Authorization"] = self.auth_key
        try:
            requests.delete(
                f"{self.BASE_URL}/emails/email",
                params={"emailAddress": self.email},
                headers=headers,
                timeout=10,
            )
        except Exception:
            pass


class GuerrillaMailProvider(BaseTempMailProvider):
    """api.guerrillamail.com — session inbox (sid_token)."""

    name = "Guerrilla"
    BASE_URL = "https://api.guerrillamail.com/ajax.php"

    def __init__(self, log_func=None, profile_tag=""):
        super().__init__(log_func, profile_tag)
        self._session = requests.Session()
        try:
            self.generate_new()
        except Exception:
            pass

    def generate_new(self) -> str:
        try:
            resp = self._session.get(
                f"{self.BASE_URL}?f=get_email_address&lang=en",
                headers=self._headers,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.email = data.get("email_addr") or ""
                self.auth_key = data.get("sid_token") or ""
                if self.email:
                    self._log(f"[📧] Guerrilla inbox: {self.email}")
                    return self.email
        except Exception as exc:
            self._log(f"[⚠️] Guerrilla attempt error: {exc}")
        raise RuntimeError("Failed to generate Guerrilla inbox")

    def list_messages(self) -> list:
        if not self.email or not self.auth_key:
            return []
        resp = self._session.get(
            f"{self.BASE_URL}?f=check_email&seq=0&sid_token={self.auth_key}",
            headers=self._headers,
            timeout=25,
        )
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []
        items = data.get("list") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        out = []
        for entry in items:
            try:
                mail_id = entry.get("mail_id")
                if not mail_id:
                    continue
                time.sleep(0.5)
                body_resp = self._session.get(
                    f"{self.BASE_URL}?f=fetch_email&email_id={mail_id}"
                    f"&sid_token={self.auth_key}",
                    headers=self._headers,
                    timeout=15,
                )
                if body_resp.status_code == 200:
                    out.append(body_resp.json())
                else:
                    out.append({"mail_body": entry.get("mail_body", "")})
            except Exception:
                continue
        return out


class MailTmProvider(BaseTempMailProvider):
    """api.mail.tm — account + bearer-token inbox."""

    name = "mail.tm"
    BASE_URL = "https://api.mail.tm"

    def __init__(self, log_func=None, profile_tag=""):
        super().__init__(log_func, profile_tag)
        self._account_password = ""
        try:
            self.generate_new()
        except Exception:
            pass

    def generate_new(self) -> str:
        try:
            domains_resp = requests.get(
                f"{self.BASE_URL}/domains",
                headers=self._headers,
                timeout=30,
            )
            domain = ""
            if domains_resp.status_code == 200:
                domains_data = domains_resp.json() or []
                # mail.tm currently returns a bare JSON array; older builds
                # returned {"hydra:member": [...]}. Accept both shapes.
                if isinstance(domains_data, dict):
                    members = domains_data.get("hydra:member", [])
                else:
                    members = domains_data
                active = [
                    d for d in members
                    if isinstance(d, dict) and d.get("isActive") and d.get("domain")
                ]
                if active:
                    domain = active[0].get("domain", "")
            if not domain:
                raise RuntimeError("no active mail.tm domain")
            local = "meta" + "".join(
                random.choices(string.ascii_lowercase + string.digits, k=10)
            )
            self.email = f"{local}@{domain}"
            self._account_password = "".join(
                random.choices(string.ascii_letters + string.digits, k=16)
            )
            create = requests.post(
                f"{self.BASE_URL}/accounts",
                headers=self._headers,
                json={"address": self.email, "password": self._account_password},
                timeout=30,
            )
            if create.status_code not in (200, 201):
                raise RuntimeError(f"account HTTP {create.status_code}")
            token_resp = requests.post(
                f"{self.BASE_URL}/token",
                headers=self._headers,
                json={"address": self.email, "password": self._account_password},
                timeout=30,
            )
            if token_resp.status_code == 200:
                self.auth_key = (token_resp.json() or {}).get("token", "")
            if self.email and self.auth_key:
                self._log(f"[📧] mail.tm inbox: {self.email}")
                return self.email
        except Exception as exc:
            self._log(f"[⚠️] mail.tm attempt error: {exc}")
        raise RuntimeError("Failed to generate mail.tm inbox")


PROVIDER_REGISTRY = {
    "tempmail.fish": TempMailFishProvider,
    "guerrilla": GuerrillaMailProvider,
    "mail.tm": MailTmProvider,
}


def create_temp_mail_provider(provider_name, log_func=None, profile_tag="",
                              retries=2):
    """Create one named provider with retries (strict single pick)."""
    log = log_func or (lambda m: None)
    key = str(provider_name or "").strip().lower()
    cls = PROVIDER_REGISTRY.get(key)
    if cls is None:
        raise RuntimeError(f"[Provider] Unknown: {provider_name}")
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            provider = cls(log_func=log, profile_tag=profile_tag)
            if getattr(provider, "email", None):
                return provider
            last_err = RuntimeError("empty inbox")
        except Exception as exc:
            last_err = exc
            log(f"[Provider] {provider_name} attempt {attempt} err: {exc}")
        time.sleep(1.5)
    raise RuntimeError(f"[Provider] {provider_name} failed: {last_err}")


def create_any_provider(log_func=None, profile_tag="", preferred=None):
    """First working provider: preferred, then fish -> Guerrilla -> mail.tm."""
    order = []
    if preferred:
        order.append(str(preferred))
    for name in ("tempmail.fish", "Guerrilla", "mail.tm"):
        if name not in order:
            order.append(name)
    last_err = RuntimeError("no providers")
    for name in order:
        try:
            return create_temp_mail_provider(
                name, log_func=log_func, profile_tag=profile_tag
            )
        except Exception as exc:
            last_err = exc
            continue
    raise last_err
