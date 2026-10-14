"""Mr Follower: claim the oldest account owing follows, hide it from the drains, put it back marked."""
import os
import sqlite3
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store  # noqa: E402

C = "c" * 30


def _db():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE accounts (id TEXT, platform TEXT, cookies TEXT, status TEXT, challenged_at REAL, "
                 "extra TEXT, created_at TEXT, claimed_at REAL, followed INTEGER DEFAULT 0, "
                 "attempts INTEGER DEFAULT 0, username TEXT, instagram_username TEXT)")
    now = time.time()
    fmt = lambda age: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - age))  # noqa: E731
    rows = [
        ("old", "Created", 0, fmt(3000)),        # oldest, owes follows
        ("mid", "Created", 2, fmt(2000)),        # owes 3
        ("done", "Created", 5, fmt(2500)),       # already has 5
        ("busy", "Submitting_PayGo", 0, fmt(2800)),
        ("new", "Created", 0, fmt(100)),
    ]
    conn.executemany("INSERT INTO accounts (id, platform, cookies, status, followed, created_at) "
                     "VALUES (?, 'Meta+Instagram', ?, ?, ?, ?)",
                     [(i, C, st, f, ca) for i, st, f, ca in rows])
    return conn


class FollowMakerStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = _db()
        self.patches = [
            mock.patch.object(store, "_conn", lambda: self.conn),
            mock.patch.object(store, "recover_stale_submitting", lambda: None),
            mock.patch.object(store, "sync_files", lambda: None),
            mock.patch.object(store.db, "dict_from_row", lambda r: dict(r)),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_claims_oldest_owing_account_and_hides_it(self):
        a = store.claim_for_follow(need=5)
        self.assertEqual(a["id"], "old")
        st = self.conn.execute("SELECT status FROM accounts WHERE id='old'").fetchone()[0]
        self.assertEqual(st, store.FOLLOW_STATUS)
        self.assertEqual(store.claim_for_follow(need=5)["id"], "mid")   # next one, never the same twice

    def test_skips_done_busy_and_too_old(self):
        got = []
        while True:
            a = store.claim_for_follow(need=5, max_age_s=2500)           # excludes 'old' (3000s)
            if not a:
                break
            got.append(a["id"])
        self.assertEqual(got, ["mid", "new"])

    def test_min_age_leaves_young_accounts_alone(self):
        got = []
        while True:
            a = store.claim_for_follow(need=5, min_age_s=1500)           # 'new' is only 100s old
            if not a:
                break
            got.append(a["id"])
        self.assertEqual(got, ["old", "mid"])

    def test_finish_ok_returns_account_marked_five(self):
        a = store.claim_for_follow(need=5)
        store.finish_follow(a["id"], 5, True)
        row = self.conn.execute("SELECT status, followed, claimed_at FROM accounts WHERE id='old'").fetchone()
        self.assertEqual((row[0], row[1], row[2]), ("Created", 5, None))
        self.assertGreaterEqual(store.count_follow_backlog()["done"], 2)

    def test_partial_failure_counts_attempts_then_gives_up(self):
        for _ in range(store.MAX_SUBMIT_ATTEMPTS):
            self.conn.execute("UPDATE accounts SET status='Created', claimed_at=NULL WHERE id='old'")
            a = store.claim_for_follow(need=5)
            self.assertEqual(a["id"], "old")
            store.finish_follow("old", 1, False)
        self.assertEqual(self.conn.execute("SELECT status FROM accounts WHERE id='old'").fetchone()[0], "Failed")

    def test_failed_account_rests_before_retry(self):
        a = store.claim_for_follow(need=5)
        store.finish_follow(a["id"], 1, False)
        self.assertEqual(store.claim_for_follow(need=5)["id"], "mid")     # not 'old' again at once
        self.conn.execute("UPDATE accounts SET claimed_at = ? WHERE id='old'", (time.time() - store.FOLLOW_RETRY_S - 5,))
        self.conn.execute("UPDATE accounts SET status='Created' WHERE id='mid'")
        self.assertEqual(store.claim_for_follow(need=5)["id"], "old")      # rested long enough

    def test_progress_does_not_cost_an_attempt(self):
        a = store.claim_for_follow(need=5)
        store.finish_follow(a["id"], 3, False, progressed=True)
        self.assertEqual(self.conn.execute("SELECT attempts, followed FROM accounts WHERE id='old'").fetchone()[:], (0, 3))

    def test_release_returns_every_claim(self):
        store.claim_for_follow(need=5)
        store.claim_for_follow(need=5)
        self.assertEqual(store.release_follow_claims(), 2)
        self.assertEqual(store.count_follow_backlog()["in_progress"], 0)

    def test_lost_race_with_another_process_picks_the_next_account(self):
        real = self.conn
        calls = {"n": 0}

        class Racing:
            """First UPDATE loses (another process took the row); later ones go through."""
            def __getattr__(self, name):
                return getattr(real, name)
            def __enter__(self):
                return real.__enter__()
            def __exit__(self, *a):
                return real.__exit__(*a)
            def execute(self, sql, params=()):
                if sql.startswith("UPDATE accounts SET status = ?, claimed_at") and calls["n"] == 0:
                    calls["n"] += 1
                    real.execute("UPDATE accounts SET status='Submitting_PayGo' WHERE id='old'")
                return real.execute(sql, params)

        with mock.patch.object(store, "_conn", lambda: Racing()):
            a = store.claim_for_follow(need=5)
        self.assertEqual(a["id"], "mid")

    def test_next_eligible_countdown(self):
        # 'new' is ~100s old; with a 10 min minimum it becomes eligible in ~500s
        nxt = store.next_follow_eligible_in(need=5, min_age_s=600)
        self.assertIsNotNone(nxt)
        self.assertTrue(480 <= nxt <= 520, nxt)
        self.assertIsNone(store.next_follow_eligible_in(need=5, min_age_s=0))

    def test_backlog_counts(self):
        c = store.count_follow_backlog()
        self.assertEqual((c["waiting"], c["in_progress"], c["done"]), (3, 0, 1))


if __name__ == "__main__":
    unittest.main()
