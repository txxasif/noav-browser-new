"""tempmail.fish session: address + inbox key are cached while the tab is open and read back over HTTP."""
import json
import unittest
from unittest import mock

import pool_common
from core.mailbox import MailboxMixin


class _Tab:
    def __init__(self, raw_key, closed=False):
        self._raw = raw_key
        self._closed = closed

    def is_closed(self):
        return self._closed

    def evaluate(self, script):
        return self._raw


class _Runner(MailboxMixin):
    def __init__(self, mail=None, email=""):
        self.mail_provider = "mailfish"
        self.mail = mail
        self.email = email


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._b


class MailfishSessionTests(unittest.TestCase):
    def test_open_tab_caches_the_inbox_key(self):
        r = _Runner(mail=_Tab('"key-123"'), email="x@tempmail.example")
        s = r._snapshot_mail_session()
        self.assertEqual(s["mailfish_auth_key"], "key-123")
        self.assertEqual(s["mailfish_email"], "x@tempmail.example")

    def test_closed_tab_keeps_the_cached_key(self):
        r = _Runner(mail=_Tab("key-123"), email="x@tempmail.example")
        r._snapshot_mail_session()
        r.mail = _Tab("", closed=True)
        self.assertEqual(r._snapshot_mail_session()["mailfish_auth_key"], "key-123")

    def test_detected_as_mailfish_only_with_key(self):
        self.assertEqual(pool_common._mail_provider({"mailfish_email": "a@x", "mailfish_auth_key": "k"}), "mailfish")
        self.assertEqual(pool_common._mail_provider({"mailfish_email": "a@x"}), "")

    def test_pool_reads_fresh_message_over_http(self):
        tokens = {"mailfish_email": "a@x.example", "mailfish_auth_key": "k"}
        msgs = [{"id": "m1", "subject": "Your code", "from": "meta", "createdAt": "2026-10-11T10:00:00Z",
                 "body": "Your Instagram code is 482913"}]

        class _Runner:
            def log(self, _m):
                pass

            def _pick_code(self, text, keyword, seen, prefer_len=None):
                import re
                m = re.search(r"\b(\d{6})\b", text or "")
                return m.group(1) if m else None

        with mock.patch("urllib.request.urlopen", return_value=_Resp(msgs)):
            code = pool_common._mail_http_code(_Runner(), tokens, set(), "instagram", 3)
        self.assertEqual(code, "482913")


if __name__ == "__main__":
    unittest.main()
