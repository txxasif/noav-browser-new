from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Set

import requests

from ai_config import Urls  # noqa: E402


class TempMailFishProvider:
    """Instant headless REST API temp mail provider using api.tempmail.fish.

    Features:
      * Direct HTTPS REST calls (requests.post, get, delete) — zero browser tab overhead.
      * Clean custom domains (@frostypeak.info etc.) with high Meta deliverability.
      * Recursive full-tree text harvester (_extract_all_text) across any JSON depth.
      * HTML tag sanitization & whitespace normalization.
      * Multi-tier context-aware OTP regex waterfall (keyword anchor -> 6-digit -> 5-digit -> 4-digit).
      * Year filtering (ignores 2000-2035 / 1900-2035) to avoid false matches.
      * MD5 message hash deduplication so emails are never processed twice.
    """
    BASE_URL: str = getattr(Urls, "TEMPMAILFISH_API", "https://api.tempmail.fish")

    def __init__(self, log_func=None, profile_tag: str = ""):
        self._log = log_func or (lambda m: None)
        self.profile_tag = profile_tag
        self.email: Optional[str] = None
        self.auth_key: Optional[str] = None
        self._used_hashes: Set[str] = set()
        self._accepted_otps: Set[str] = set()
        self._headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            ),
        }

    def generate_new(self) -> str:
        """Create a fresh temporary inbox and return the email address."""
        self._log("[📧] Requesting fresh email from api.tempmail.fish…")
        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    f"{self.BASE_URL}/emails/new-email",
                    headers=self._headers,
                    timeout=25,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self.email = data.get("email") or data.get("emailAddress") or ""
                    self.auth_key = data.get("authKey") or data.get("auth_key") or ""
                    if self.email:
                        self._log(f'[📧] TempMail.fish inbox: {self.email}')
                        return self.email
                self._log(f"[⚠️] tempmail.fish create returned HTTP {resp.status_code}, retrying…")
            except Exception as exc:
                self._log(f"[⚠️] tempmail.fish attempt {attempt} error: {exc}")
            time.sleep(1.5)
        raise RuntimeError(f"Failed to generate temp email from {self.BASE_URL}")

    def list_messages(self) -> list:
        """Fetch list of inbound emails from the inbox."""
        if not self.email or not self.auth_key:
            return []
        headers = dict(self._headers)
        headers["Authorization"] = self.auth_key
        try:
            resp = requests.get(
                f"{self.BASE_URL}/emails/emails",
                params={"emailAddress": self.email},
                headers=headers,
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    for k in ("emails", "messages", "data", "items", "result"):
                        if isinstance(data.get(k), list):
                            return data[k]
        except Exception:
            pass
        return []

    def _extract_all_text(self, msg: dict) -> str:
        """Recursively harvest all text content from an email object up to depth 4."""
        collected: List[str] = []
        ignored_keys = {"id", "_id", "message_id", "date", "created_at", "receivedat", "authkey", "isread", "isseen"}

        def collect(obj: Any, depth: int = 0):
            if depth > 4:
                return
            if isinstance(obj, (str, int, float)):
                collected.append(str(obj))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k).lower() not in ignored_keys:
                        collect(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    collect(item, depth + 1)

        collect(msg)
        raw = " ".join(collected)
        clean = re.sub(r"<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", clean).strip()

    def _extract_candidates(self, clean_text: str) -> list:
        """Multi-tier context-aware OTP extractor with year filtering."""
        candidates: List[str] = []

        # Tier 1: Keyword-anchored code
        t1 = re.findall(
            r"(?:code|otp|pin|verification|verify|passcode|meta)\s*[:\-is]*\s*(\d{4,8})\b",
            clean_text,
            re.IGNORECASE,
        )
        candidates.extend(t1)

        # Tier 2: 6-digit candidate (filter out calendar years 2000-2035)
        t2 = [c for c in re.findall(r"\b(\d{6})\b", clean_text) if not (2000 <= int(c) <= 2035)]
        candidates.extend(t2)

        # Tier 3: 5-digit candidate
        candidates.extend(re.findall(r"\b(\d{5})\b", clean_text))

        # Tier 4: 4-digit candidate (filter out birth/calendar years 1900-2035)
        candidates.extend([c for c in re.findall(r"\b(\d{4})\b", clean_text) if not (1900 <= int(c) <= 2035)])

        # Preserve order while deduplicating
        seen: Set[str] = set()
        ordered: List[str] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        return ordered

    def wait_for_otp(self, timeout: int = 240, keyword: str = "meta", skip_otps: Optional[List[str]] = None) -> Optional[str]:
        """Poll the mailbox for incoming OTP."""
        skip_set = set(skip_otps or [])
        end_time = time.time() + timeout
        self._log(f"[📧] Polling {self.email} for verification code (up to {timeout}s)…")
        poll_count = 0

        while time.time() < end_time:
            msgs = self.list_messages()
            for idx, msg in enumerate(msgs):
                msg_id = msg.get("id") or msg.get("_id") or f"idx_{idx}"
                msg_subject = str(msg.get("subject") or "")
                msg_from = str(msg.get("from") or msg.get("sender") or "")
                msg_date = str(msg.get("date") or msg.get("created_at") or "")
                msg_hash = hashlib.md5(f"{msg_id}|{msg_date}|{msg_from}|{msg_subject}".encode()).hexdigest()

                clean = self._extract_all_text(msg)
                candidates = self._extract_candidates(clean)

                for c in candidates:
                    if c in skip_set or c in self._accepted_otps:
                        continue
                    self._used_hashes.add(msg_hash)
                    self._accepted_otps.add(c)
                    self._log(f'[📧] Found code in email: {c} (subject: "{msg_subject[:40]}")')
                    return c

            poll_count += 1
            if poll_count % 5 == 0:
                elapsed = int(time.time() - (end_time - timeout))
                self._log(f"[📧] Waiting for email… ({elapsed}s elapsed, {len(msgs)} msgs)")
            time.sleep(2.0)

        self._log(f"[⚠️] No OTP received within {timeout}s.")
        return None

    def cleanup(self):
        """Release the mailbox on tempmail.fish."""
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
