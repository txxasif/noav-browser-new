"""tempmail.fish Premium API: new accounts use it, old web-inbox accounts keep the old reader."""
import json
import os
import unittest
from unittest import mock

from core import mailfish_api
import pool_common


class _Resp:
    def __init__(self, payload, status=200):
        self._b = json.dumps(payload).encode() if payload is not None else b""
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._b


class _Runner:
    def log(self, _m):
        pass

    def _pick_code(self, text, keyword, seen, prefer_len=None):
        import re
        m = re.search(r"\b(\d{6})\b", text or "")
        return m.group(1) if m else None


class ApiKeyTests(unittest.TestCase):
    def test_key_from_environment(self):
        with mock.patch.dict(os.environ, {"TEMPMAILFISH_API_KEY": "tmf_test"}):
            self.assertEqual(mailfish_api.api_key(), "tmf_test")

    def test_empty_key_means_web_inbox(self):
        with mock.patch.dict(os.environ, {"TEMPMAILFISH_API_KEY": ""}), \
                mock.patch("builtins.open", side_effect=OSError):
            self.assertEqual(mailfish_api.api_key(), "")


class ApiCallTests(unittest.TestCase):
    def test_create_inbox_returns_the_address(self):
        with mock.patch("urllib.request.urlopen", return_value=_Resp({"email": "A.B@Example.TLD"})):
            self.assertEqual(mailfish_api.create_inbox("tmf_k"), "a.b@example.tld")

    def test_create_inbox_failure_is_empty(self):
        with mock.patch("urllib.request.urlopen", return_value=_Resp(None, status=402)):
            self.assertEqual(mailfish_api.create_inbox("tmf_k"), "")

    def test_list_messages_accepts_list_and_wrapped_shapes(self):
        msg = {"from": "noreply@account.meta.com", "subject": "Authenticate your profile",
               "textBody": "Your code is 482913", "timestamp": "2026-10-12T10:00:00Z"}
        for payload in ([msg], {"messages": [msg]}):
            with mock.patch("urllib.request.urlopen", return_value=_Resp(payload)):
                out = mailfish_api.list_messages("a@x.tld", "tmf_k")
            self.assertEqual(len(out), 1)
            self.assertIn("482913", out[0]["text"])

    def test_wait_code_skips_seen_messages(self):
        old = {"id": "old", "subject": "Authenticate", "from": "meta", "ts": "1", "text": "111111", "code": None}
        new = {"id": "new", "subject": "Authenticate", "from": "meta", "ts": "2", "text": "Code 222222", "code": None}
        seen = {"old"}
        with mock.patch("core.mailfish_api.list_messages", return_value=[old, new]):
            code = mailfish_api.wait_code(_Runner(), "a@x.tld", timeout=5, seen=seen, interval=0)
        self.assertEqual(code, "222222")


class PoolReaderTests(unittest.TestCase):
    def test_api_inbox_is_detected_separately_from_web_inbox(self):
        self.assertEqual(pool_common._mail_provider({"mailfish_email": "a@x", "mailfish_api": True}), "mailfish_api")
        self.assertEqual(pool_common._mail_provider({"mailfish_email": "a@x", "mailfish_auth_key": "k"}), "mailfish")

    def test_pool_reads_api_inbox_for_a_code(self):
        tokens = {"mailfish_email": "a@x.tld", "mailfish_api": True}
        msgs = [{"from": "meta", "subject": "Authenticate your profile", "textBody": "Code 654321"}]
        with mock.patch("urllib.request.urlopen", return_value=_Resp(msgs)), \
                mock.patch.dict(os.environ, {"TEMPMAILFISH_API_KEY": "tmf_k"}):
            code = pool_common._mail_http_code(_Runner(), tokens, set(), "instagram", 3)
        self.assertEqual(code, "654321")


if __name__ == "__main__":
    unittest.main()
