"""Pool OTP reads pick the mailbox each account was created with (mail.td, Cloudflare, Yamin)."""
import json
import unittest
from unittest import mock

import pool_common


class _Runner:
    def __init__(self):
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)

    def _pick_code(self, text, keyword, seen, prefer_len=None):
        import re
        m = re.search(r"\b(\d{6})\b", text or "")
        return m.group(1) if m else None


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._b


class ProviderDispatchTests(unittest.TestCase):
    def test_provider_detection(self):
        self.assertEqual(pool_common._mail_provider({"tempmail_token": "t"}), "mailtd")
        self.assertEqual(pool_common._mail_provider({"mailcf_token": "t", "mailcf_email": "a@x"}), "mailcf")
        self.assertEqual(pool_common._mail_provider({"yamin_email": "a@epicz.xyz"}), "yamin")
        self.assertEqual(pool_common._mail_provider({"mailfish_email": "a@x"}), "")
        self.assertEqual(pool_common._mail_provider({}), "")

    def test_tokens_from_extra_accepts_all_providers(self):
        extra = json.dumps({"mail_tokens": {"yamin_email": "a@epicz.xyz"}})
        self.assertEqual(pool_common._mail_tokens_from_extra(extra), {"yamin_email": "a@epicz.xyz"})

    def test_cloudflare_fresh_code_ignores_snapshot(self):
        tokens = {"mailcf_token": "tok", "mailcf_email": "a@lumencreative.site"}
        old = {"timestamp": 100, "subject": "old", "from": "meta", "text": "111111"}
        new = {"timestamp": 200, "subject": "new", "from": "meta", "text": "Your code is 222222"}
        snapshot = {pool_common._msg_id(old)}
        with mock.patch("core.mail_reader.list_messages", return_value=[new, old]):
            code = pool_common._mail_http_code(_Runner(), tokens, snapshot, "instagram", 3)
        self.assertEqual(code, "222222")

    def test_yamin_fresh_code_uses_api(self):
        tokens = {"yamin_email": "john.doe.12@epicz.xyz"}
        listing = [{"id": "m1", "subject": "Code", "from": "meta.com", "timestamp": 50}]
        body = {"code_extracted": "654321", "htmlBody": "x"}
        responses = [_Resp(listing), _Resp(body)]
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: responses.pop(0)):
            code = pool_common._mail_http_code(_Runner(), tokens, set(), "instagram", 3)
        self.assertEqual(code, "654321")

    def test_old_yamin_account_without_token_uses_its_address(self):
        acc = {"email": "John.Doe.12@epicz.xyz", "extra": None}
        self.assertEqual(pool_common._mail_tokens_for_account(acc), {"yamin_email": "john.doe.12@epicz.xyz"})

    def test_old_cloudflare_account_reads_public_latest_code(self):
        acc = {"email": "a.b.1@lumencreative.site", "extra": "{}"}
        tokens = pool_common._mail_tokens_for_account(acc)
        self.assertEqual(tokens, {"mailcf_email": "a.b.1@lumencreative.site"})
        with mock.patch("core.mail_reader.latest_code", return_value="333444"):
            code = pool_common._mail_http_code(_Runner(), tokens, set(), "instagram", 3, subject_hint="instagram")
        self.assertEqual(code, "333444")

    def test_unknown_domain_has_no_mailbox(self):
        self.assertEqual(pool_common._mail_tokens_for_account({"email": "x@mailfish.example", "extra": None}), {})

    def test_snapshot_ids_for_yamin(self):
        tokens = {"yamin_email": "john.doe.12@epicz.xyz"}
        with mock.patch("urllib.request.urlopen", return_value=_Resp([{"id": "m9", "timestamp": 1}])):
            self.assertEqual(pool_common._mail_ids(tokens), {"m9"})


if __name__ == "__main__":
    unittest.main()
