"""The drain log must be able to say why fewer accounts are drainable than were created."""
import json
import os
import sqlite3
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402


def _api(extra_api):
    return json.dumps({"mail_tokens": {"mailfish_email": "x@coolember.com", "mailfish_api": True}} if extra_api else {"mail_tokens": {}})


class BreakdownTests(unittest.TestCase):
    def test_reasons_add_up(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE accounts (id TEXT, platform TEXT, cookies TEXT, status TEXT, challenged_at REAL, extra TEXT)")
        now = time.time()
        rows = [
            ("a", "Meta+Instagram", "c" * 30, "Created", None, _api(True)),            # usable (api mode)
            ("b", "Meta+Instagram", "c" * 30, "Created", None, _api(True)),            # usable
            ("c", "Meta+Instagram", "c" * 30, "Created", None, "{}"),                  # no readable mailbox
            ("d", "Meta+Instagram", "c" * 30, "Submitting_PayGo", None, _api(True)),   # in use
            ("e", "Meta+Instagram", "c" * 30, "Created", now, _api(True)),             # challenged just now
            ("f", "Meta+Instagram", "", "Created", None, _api(True)),                  # no cookies
        ]
        conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?)", rows)
        conn.create_function("drain_ok", 1, lambda extra: 1)
        conn.create_function("mailbox_ok", 1, store._has_readable_mailbox)
        with mock.patch.object(store, "_conn", lambda: conn):
            b = store.ig_pool_breakdown()
        self.assertEqual(b, {"total": 6, "no_cookies": 1, "in_use_or_done": 1, "challenged": 1,
                             "no_mailbox": 1, "usable": 2})
        self.assertEqual(b["total"], sum(v for k, v in b.items() if k != "total"))


if __name__ == "__main__":
    unittest.main()
