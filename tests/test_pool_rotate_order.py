"""An account that was just claimed and put back (rename rate-limited) must go to the BACK of the queue."""
import os
import sqlite3
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402


class RotateOrderTests(unittest.TestCase):
    def test_recently_claimed_goes_last(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE accounts (id TEXT, platform TEXT, cookies TEXT, status TEXT, challenged_at REAL, "
                     "extra TEXT, created_at TEXT, claimed_at REAL)")
        now = time.time()
        c = "c" * 30
        conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?)", [
            ("fresh_but_just_failed", "Meta+Instagram", c, "Created", None, "{}", "2026-10-12 23:00:00", now - 5),
            ("older_a", "Meta+Instagram", c, "Created", None, "{}", "2026-10-12 22:00:00", None),
            ("older_b", "Meta+Instagram", c, "Created", None, "{}", "2026-10-12 21:00:00", None),
        ])
        conn.create_function("drain_ok", 1, lambda extra: 1)
        with mock.patch.object(store, "_conn", lambda: conn), \
                mock.patch.object(store, "recover_stale_submitting", lambda: None), \
                mock.patch.object(store, "sync_files", lambda: None):
            first = store.pop_ig_creator_account()
        self.assertEqual(first["id"], "older_a")     # not the account that just failed


if __name__ == "__main__":
    unittest.main()
