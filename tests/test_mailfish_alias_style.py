"""tempmail.fish API inboxes: random (default) or name-like address, chosen from the IG creator panel."""
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import mailfish_api  # noqa: E402


class AliasStyleTests(unittest.TestCase):
    def _settings(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh)
        self.addCleanup(os.remove, path)
        return mock.patch.object(mailfish_api, "SETTINGS_FILE", path)

    def test_default_is_random(self):
        with self._settings({}):
            self.assertEqual(mailfish_api.alias_style(), "random")
        with mock.patch.object(mailfish_api, "SETTINGS_FILE", "/nonexistent/x.json"):
            self.assertEqual(mailfish_api.alias_style(), "random")

    def test_name_is_read_and_junk_falls_back(self):
        with self._settings({"mailfish_alias_style": "name"}):
            self.assertEqual(mailfish_api.alias_style(), "name")
        with self._settings({"mailfish_alias_style": "weird"}):
            self.assertEqual(mailfish_api.alias_style(), "random")

    def test_name_alias_is_letters_and_digits_only(self):
        for _ in range(50):
            self.assertRegex(mailfish_api._alias("name"), r"^[a-z]+\d{2,3}$")
        self.assertRegex(mailfish_api._alias("random"), r"^[a-z0-9]{8,12}$")

    def test_create_inbox_uses_the_requested_style(self):
        seen = []

        def fake_request(method, path, key, timeout=15, body=None):
            seen.append(body["alias"])
            return 200, {"email": f"{body['alias']}@{body['domain']}"}
        with mock.patch.object(mailfish_api, "_request", fake_request):
            addr = mailfish_api.create_inbox(key="k", style="name")
        self.assertTrue(re.match(r"^[a-z]+\d{2,3}@", addr))


if __name__ == "__main__":
    unittest.main()
