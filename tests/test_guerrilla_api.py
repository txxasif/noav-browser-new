import json
import sys
import unittest
from unittest import mock

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from core import guerrilla_api as g  # noqa: E402
import pool_common  # noqa: E402


class _Runner:
    mail_provider = "guerrilla"

    def log(self, *_):
        pass

    def _pick_code(self, text, keyword, used, prefer_len=None):
        import re
        m = re.search(r"\b(\d{6})\b", text)
        return m.group(1) if m else None


class GuerrillaTests(unittest.TestCase):
    def setUp(self):
        g._SIDS.clear()
        g._BODIES.clear()

    def test_provider_detected_from_stored_tokens(self):
        self.assertEqual(pool_common._mail_provider({"guerrilla_email": "a@guerrillamailblock.com"}), "guerrilla")

    def test_expired_sid_is_restored_from_the_address_alone(self):
        calls = []

        def fake(fn, sid="", **kw):
            calls.append((fn, sid, kw))
            if fn == "check_email" and sid == "old":
                return {"error": "Please call get_email_address or set_email_user first"}
            if fn == "set_email_user":
                return {"sid_token": "new", "email_addr": "abc@guerrillamailblock.com"}
            if fn == "check_email":
                return {"list": [{"mail_id": "7", "mail_subject": "Meta code", "mail_from": "security@facebookmail.com",
                                  "mail_excerpt": "x", "mail_timestamp": "1"}]}
            if fn == "fetch_email":
                return {"mail_body": "<p>Your code is 123456</p>"}

        with mock.patch.object(g, "_call", fake):
            msgs = g.list_messages("abc@guerrillamailblock.com", "old")
        self.assertEqual(len(msgs), 1)
        self.assertIn("123456", msgs[0]["text"])
        self.assertTrue(any(c[0] == "set_email_user" and c[2].get("email_user") == "abc" for c in calls))
        self.assertEqual(g.current_sid("abc@guerrillamailblock.com"), "new")

    def test_pool_reader_and_wait_code(self):
        def fake(fn, sid="", **kw):
            if fn == "check_email":
                return {"list": [{"mail_id": "1", "mail_subject": "s", "mail_from": "x@facebookmail.com",
                                  "mail_excerpt": "654321", "mail_timestamp": "1"}]}
            return {"mail_body": "code 654321"}

        with mock.patch.object(g, "_call", fake):
            toks = {"guerrilla_email": "u@sharklasers.com", "guerrilla_sid": "s"}
            self.assertEqual(len(pool_common._mail_messages(toks)), 1)
            self.assertEqual(g.wait_code(_Runner(), "u@sharklasers.com", "s", timeout=5), "654321")


if __name__ == "__main__":
    unittest.main()
