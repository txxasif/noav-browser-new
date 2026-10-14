"""Mr Follower runner: edge cases of the claim -> follow -> return loop (store and follow step faked)."""
import argparse
import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import follow_maker as fm  # noqa: E402


def _args(**kw):
    base = dict(creators=1, limit=0, follows=5, min_age_min=10, max_age_min=0, pause=0, visible=False,
                mode="auto", auto=False, interval=5, on_fail="retry")
    base.update(kw)
    return argparse.Namespace(**base)


class FakeStore:
    FOLLOW_RETRY_S = 600

    def __init__(self, accounts):
        self.queue = list(accounts)
        self.finished = []
        self.deleted = []

    def claim_for_follow(self, **kw):
        return self.queue.pop(0) if self.queue else None

    def finish_follow(self, rec_id, followed, ok, dead_reason="", progressed=False):
        self.finished.append((rec_id, followed, ok, dead_reason, progressed))

    def delete_record(self, rec_id):
        self.deleted.append(rec_id)

    def next_follow_eligible_in(self, *a):
        return None

    def count_follow_backlog(self, **kw):
        return {"waiting": 0, "in_progress": 0, "done": 0}


def acc(i, followed=0):
    return {"id": i, "username": i, "followed": followed, "cookies": "c"}


class LoopTests(unittest.TestCase):
    def setUp(self):
        fm._stop.clear()
        for k in fm._stats:
            fm._stats[k] = 0
        fm._streak["fails"] = 0
        self.out = []
        p = mock.patch.object(fm, "emit", lambda m: self.out.append(m))
        p.start()
        self.addCleanup(p.stop)

    def run_loop(self, store, follow, args=None):
        with mock.patch.object(fm, "store", store), mock.patch.object(fm, "follow_one", follow):
            fm.creator_loop(1, args or _args())

    def test_empty_list_without_auto_finishes(self):
        st = FakeStore([])
        self.run_loop(st, lambda *a: (0, ""))
        self.assertTrue(any("done" in m for m in self.out))

    def test_empty_list_in_auto_waits_and_picks_up_a_late_account(self):
        st = FakeStore([])
        calls = {"n": 0}
        real_wait = fm._stop.wait

        def wait(t=None):
            calls["n"] += 1
            if calls["n"] == 1:
                st.queue.append(acc("late"))            # an account appears while it waits
            if calls["n"] >= 3:
                fm._stop.set()
            return False
        with mock.patch.object(fm._stop, "wait", wait):
            self.run_loop(st, lambda *a: (5, ""), _args(auto=True))
        self.assertEqual([f[0] for f in st.finished], ["late"])
        self.assertTrue(st.finished[0][2])               # ok
        self.assertTrue(any("waiting" in m for m in self.out))

    def test_success_returns_account_marked(self):
        st = FakeStore([acc("a")])
        self.run_loop(st, lambda *a: (5, ""))
        self.assertEqual(st.finished, [("a", 5, True, "", False)])

    def test_partial_progress_is_not_penalised(self):
        st = FakeStore([acc("a", 1)])
        self.run_loop(st, lambda *a: (3, ""))
        self.assertEqual(st.finished, [("a", 3, False, "", True)])

    def test_nothing_gained_costs_an_attempt(self):
        st = FakeStore([acc("a", 1)])
        self.run_loop(st, lambda *a: (1, ""))
        self.assertEqual(st.finished, [("a", 1, False, "", False)])

    def test_dead_account_is_marked_dead(self):
        st = FakeStore([acc("a")])
        self.run_loop(st, lambda *a: (0, "IG dead end: x"))
        self.assertEqual(st.finished, [("a", 0, False, "IG dead end: x", False)])

    def test_crash_in_follow_step_still_releases_the_account(self):
        st = FakeStore([acc("a")])

        def boom(*a):
            raise RuntimeError("browser exploded")
        self.run_loop(st, boom)
        self.assertEqual(len(st.finished), 1)            # never left locked
        self.assertFalse(st.finished[0][2])

    def test_unexpected_error_while_returning_still_releases(self):
        st = FakeStore([acc("a")])
        calls = {"n": 0}
        orig = st.finish_follow

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("disk")
            return orig(*a, **k)
        st.finish_follow = flaky
        with self.assertRaises(OSError):
            self.run_loop(st, lambda *a: (5, ""))
        self.assertEqual(len(st.finished), 1)            # the finally-block released it

    def test_limit_stops_after_n_accounts(self):
        st = FakeStore([acc("a"), acc("b"), acc("c")])
        self.run_loop(st, lambda *a: (5, ""), _args(limit=2))
        self.assertEqual([f[0] for f in st.finished], ["a", "b"])

    def test_failed_follow_marks_account_damaged_by_default_policy(self):
        fm._stats["ok"] = 1                              # the method has already worked once this run
        st = FakeStore([acc("a")])
        self.run_loop(st, lambda *a: (2, ""), _args(on_fail="dead"))
        self.assertEqual(st.finished, [("a", 2, False, "follow incomplete (2/5)", False)])
        self.assertEqual(st.deleted, [])

    def test_failed_follow_can_delete_the_account(self):
        fm._stats["ok"] = 1
        st = FakeStore([acc("a")])
        self.run_loop(st, lambda *a: (0, ""), _args(on_fail="delete"))
        self.assertEqual(st.deleted, ["a"])
        self.assertEqual(st.finished, [])

    def test_success_is_never_touched_by_the_fail_policy(self):
        st = FakeStore([acc("a")])
        self.run_loop(st, lambda *a: (5, ""), _args(on_fail="delete"))
        self.assertEqual(st.finished, [("a", 5, True, "", False)])
        self.assertEqual(st.deleted, [])

    def test_no_account_is_condemned_before_any_success(self):
        st = FakeStore([acc("a"), acc("b")])
        self.run_loop(st, lambda *a: (0, ""), _args(on_fail="dead"))
        self.assertEqual(st.deleted, [])
        self.assertTrue(all(f[3] == "" for f in st.finished))        # nobody marked dead
        self.assertTrue(any("blaming the method" in m for m in self.out))

    def test_dead_session_still_condemns_the_account_and_keeps_its_progress(self):
        st = FakeStore([acc("a")])
        self.run_loop(st, lambda *a: (4, "IG dead end: challenge_required"), _args(on_fail="dead"))
        self.assertEqual(st.finished[0][:2], ("a", 4))
        self.assertIn("challenge_required", st.finished[0][3])

    def test_stop_never_judges_the_account(self):
        fm._stats["ok"] = 1
        st = FakeStore([acc("a")])

        def stopped_midway(*a):
            fm._stop.set()
            return 2, ""
        self.run_loop(st, stopped_midway, _args(on_fail="dead"))
        self.assertEqual(st.finished, [("a", 2, False, "", True)])   # back untouched, no penalty
        self.assertTrue(any("stop requested" in m for m in self.out))

    def test_follows_made_before_the_session_died_are_counted(self):
        def fake_follow_targets(client, need, log, **kw):
            log("[👥][api] Followed @a (1/5).")
            log("[👥][api] Followed @b (2/5).")
            raise fm.IGDeadEnd("follow dead session: mobile: challenge_required")
        with mock.patch("instagram.ig_api_cycle.client_for", lambda *a, **k: object()), \
                mock.patch("instagram.ig_api_cycle.follow_targets", fake_follow_targets):
            with self.assertRaises(fm.DeadAfter) as cm:
                fm._api_follow({"username": "u"}, 5, lambda m: None)
        self.assertEqual(cm.exception.followed, 2)

    def test_breaker_trips_after_a_run_of_failures(self):
        st = FakeStore([acc(str(i)) for i in range(fm.BREAKER_AFTER)])
        waits = []
        with mock.patch.object(fm._stop, "wait", lambda t=None: waits.append(t) or False):
            self.run_loop(st, lambda *a: (0, ""))
        self.assertIn(fm.BREAKER_COOLDOWN_S, waits)
        self.assertTrue(any("cooling down" in m for m in self.out))


if __name__ == "__main__":
    unittest.main()
