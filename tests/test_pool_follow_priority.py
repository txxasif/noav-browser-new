import os
import sqlite3
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store  # noqa: E402


def _db(rows):
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE accounts (id TEXT, platform TEXT, cookies TEXT, status TEXT, challenged_at REAL, "
                 "extra TEXT, created_at TEXT, claimed_at REAL, followed INTEGER DEFAULT 0)")
    c = "c" * 30
    conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?)",
                     [(i, "Meta+Instagram", c, "Created", None, extra, ts, None, f) for i, f, extra, ts in rows])
    conn.create_function("drain_ok", 1, lambda extra: 1)
    return conn


def _pop(conn, **kw):
    with mock.patch.object(store, "_conn", lambda: conn), \
            mock.patch.object(store, "recover_stale_submitting", lambda: None), \
            mock.patch.object(store, "sync_files", lambda: None):
        r = store.pop_ig_creator_account(**kw)
    return r["id"] if r else None


ROWS = [  # newest first by created_at
    ("new_f0", 0, "{}", "2026-10-13 03:00:00"),
    ("mid_f5", 5, "{}", "2026-10-13 02:00:00"),
    ("old_f5", 5, None, "2026-10-13 01:00:00"),
    ("old_f2", 2, "Dead: x", "2026-10-13 00:30:00"),
    ("legacy_f5", 0, '{"followed": 5}', "2026-10-13 00:10:00"),
]


class FollowPriorityTests(unittest.TestCase):
    def test_default_is_freshest_first(self):
        self.assertEqual(_pop(_db(ROWS)), "new_f0")

    def test_cookie_tasks_take_5_follow_accounts_first_then_the_rest(self):
        conn = _db(ROWS)
        order = [_pop(conn, prefer_follow5=True) for _ in range(5)]
        self.assertEqual(order[:3], ["mid_f5", "old_f5", "legacy_f5"])   # all 5-follow ones, freshest first
        self.assertEqual(order[3:], ["new_f0", "old_f2"])               # then the others, nothing skipped
        self.assertIsNone(_pop(conn, prefer_follow5=True))

    def test_paygo_2fa_takes_non_5_accounts_first_then_5_follow(self):
        conn = _db(ROWS)
        order = [_pop(conn, prefer_non_follow5=True) for _ in range(5)]
        self.assertEqual(order[:2], ["new_f0", "old_f2"])
        self.assertEqual(set(order[2:]), {"mid_f5", "old_f5", "legacy_f5"})

    def test_recently_failed_account_still_goes_to_the_back(self):
        conn = _db(ROWS)
        conn.execute("UPDATE accounts SET claimed_at = ? WHERE id = 'mid_f5'", (time.time() - 5,))
        self.assertEqual(_pop(conn, prefer_follow5=True), "old_f5")


if __name__ == "__main__":
    unittest.main()
