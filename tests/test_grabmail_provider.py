"""grabmail.io provider: address picking, API reads, and the stored 2FA session.

grabmail has no inbox creation and no token — the address is the whole session — so
these tests pin the two things that matter: the address is picked/kept correctly, and
an OTP can be read back out of that address later (the 2FA task).
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import grabmail_api  # noqa: E402


class _Runner:
    def __init__(self):
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)

    def _pick_code(self, text, keyword, seen, prefer_len=None):
        import re
        m = re.search(r"\b(\d{6})\b", text or "")
        return m.group(1) if m else None


class ProviderTests(unittest.TestCase):
    def setUp(self):
        grabmail_api._premium_cache.update(key="", domains=[])
        grabmail_api.last_failure = ""
        # no key anywhere: keep the public domains deterministic in tests
        self._env = mock.patch.dict(os.environ, {"GRABMAIL_API_KEY": ""})
        self._env.start()
        self.addCleanup(self._env.stop)
        self._settings = mock.patch.object(grabmail_api, "_settings", return_value={})
        self._settings.start()
        self.addCleanup(self._settings.stop)

    # --- address picking ------------------------------------------------
    def test_create_inbox_on_a_public_domain_needs_no_key(self):
        # the API echoes the address that was asked for
        def fake_request(method, path, key=None, **kw):
            return 200, {"address": kw.get("params", {}).get("address")}, 0

        with mock.patch.object(grabmail_api, "_request", side_effect=fake_request) as req:
            email = grabmail_api.create_inbox()
        self.assertIn(email.split("@", 1)[1], grabmail_api.PUBLIC_DOMAINS)
        self.assertTrue(grabmail_api.is_public(email))
        self.assertEqual(grabmail_api.last_failure, "")
        # the read is what confirms the service answers (and holds a premium address)
        self.assertEqual(req.call_args[0][0], "GET")

    def test_premium_pool_is_used_when_a_key_unlocks_it(self):
        def fake_request(method, path, key=None, **kw):
            if path == "/domains":
                return 200, {"premium": {"unlocked": True, "domains": ["private-one.com"]}}, 0
            return 200, {"address": kw.get("params", {}).get("address")}, 0

        with mock.patch.object(grabmail_api, "api_key", return_value="gm_live_test"), \
                mock.patch.object(grabmail_api, "_request", side_effect=fake_request):
            email = grabmail_api.create_inbox()
        self.assertTrue(email.endswith("@private-one.com"))
        self.assertFalse(grabmail_api.is_public(email))

    def test_dead_service_reports_down_so_the_caller_can_fall_back(self):
        with mock.patch.object(grabmail_api, "_request", return_value=(0, None, 0)):
            self.assertEqual(grabmail_api.create_inbox(), "")
        self.assertEqual(grabmail_api.last_failure, "down")

    def test_throttled_creation_still_returns_the_address(self):
        with mock.patch.object(grabmail_api, "_request", return_value=(429, None, 7)):
            email = grabmail_api.create_inbox()
        self.assertIn("@", email)
        self.assertEqual(grabmail_api.last_failure, "")

    # --- reads ----------------------------------------------------------
    def test_list_messages_has_no_body_and_report_message_does(self):
        listing = {"messages": [{"id": "m1", "subject": "Your code", "from": "no-reply@meta.com",
                                 "date": "2026-08-04T18:31:07Z"}]}
        full = {"id": "m1", "subject": "Your code", "from": "no-reply@meta.com",
                "text": "Your code is 481920.", "html": None}

        def fake_request(method, path, key=None, **kw):
            return (200, listing, 0) if path == "/mailbox" else (200, full, 0)

        with mock.patch.object(grabmail_api, "_request", side_effect=fake_request):
            msgs = grabmail_api.list_messages("k7fq2m@grabmail.io")
            self.assertEqual(len(msgs), 1)
            self.assertIsNone(msgs[0]["text"])          # body comes per message
            body = grabmail_api.read_message("k7fq2m@grabmail.io", "m1")
        self.assertIn("481920", grabmail_api.body_text(body))

    def test_rate_limit_retry_after_is_honoured(self):
        self.assertEqual(grabmail_api.retry_after_seconds(429, 7), 7.0)
        self.assertEqual(grabmail_api.retry_after_seconds(429, 0), 1.0)
        self.assertEqual(grabmail_api.retry_after_seconds(200, 0), 0.0)

    # --- the OTP read (what the 2FA task does) --------------------------
    def test_wait_code_reads_the_body_and_skips_seen_ids(self):
        listing = {"messages": [
            {"id": "old", "subject": "Instagram", "from": "no-reply@mail.instagram.com", "date": "1"},
            {"id": "new", "subject": "Instagram", "from": "no-reply@mail.instagram.com", "date": "2"},
        ]}
        bodies = {"new": {"id": "new", "subject": "Instagram", "text": "Your code is 654321."}}

        def fake_request(method, path, key=None, **kw):
            if path == "/mailbox":
                return 200, listing, 0
            mid = path.rsplit("/", 1)[-1]
            return (200, bodies.get(mid, {}), 0)

        runner = _Runner()
        with mock.patch.object(grabmail_api, "_request", side_effect=fake_request):
            code = grabmail_api.wait_code(runner, "k7fq2m@grabmail.io", "instagram", timeout=5,
                                         seen={"old"}, subject_hint="instagram")
        self.assertEqual(code, "654321")
        self.assertTrue(any("grabmail" in m for m in runner.logs))

    def test_wait_code_ignores_unrelated_senders(self):
        listing = {"messages": [{"id": "m1", "subject": "Newsletter", "from": "spam@example.com", "date": "1"}]}
        with mock.patch.object(grabmail_api, "_request", return_value=(200, listing, 0)):
            code = grabmail_api.wait_code(_Runner(), "k7fq2m@grabmail.io", "instagram",
                                          timeout=2, subject_hint="instagram|meta")
        self.assertIsNone(code)

    def test_delete_message(self):
        with mock.patch.object(grabmail_api, "_request", return_value=(200, {"deleted": True}, 0)):
            self.assertTrue(grabmail_api.delete_message("k7fq2m@grabmail.io", "m1"))


if __name__ == "__main__":
    unittest.main()
