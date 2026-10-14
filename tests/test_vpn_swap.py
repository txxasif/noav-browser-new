"""NordVPN swap: queued swaps wait for running accounts, IP-failure streaks and blocks
queue a swap, city picks follow each city's record, and a failed swap holds new accounts."""
import os
import random
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import vpn_rotate as v  # noqa: E402

QUIET = lambda *_a, **_k: None  # noqa: E731
REAL_SLEEP = v.time.sleep  # captured before any test patches time.sleep


def _fast_sleep(seconds):
    REAL_SLEEP(0.01)


def _reset():
    v._pending, v._halted, v._active = None, False, 0
    v._last_at, v._last_city, v._ip_streak = 0.0, None, 0
    v._stats.clear()
    v._window.clear()
    v._any_window.clear()
    v._episode = None
    v._history_loaded = True  # tests must not read real history or call the NordVPN CLI
    v._exit_hook = True       # ...and must not register an exit hook that writes the real stats file


class SwapTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        # Tests must never write to the real stats file in the project root.
        self.env = mock.patch.dict(os.environ, {
            "NORD_ROTATE": "1", "NORD_ROTATE_STREAK": "3", "NORD_ROTATE_DRAIN_S": "300",
            "NORD_ROTATE_STATS": os.path.join(tempfile.mkdtemp(), "stats.jsonl")})
        self.env.start()
        _reset()

    def tearDown(self):
        self.env.stop()
        _reset()

    def test_pool_has_canada_singapore_and_usa(self):
        self.assertEqual({c for c, _ in v.POOL}, {"Canada", "United_States", "Singapore"})
        self.assertEqual(len(v.POOL), 4 + 1 + 55)

    def test_canada_and_singapore_are_picked_less_than_the_us(self):
        picks = [v._pick_city()[0] for _ in range(3000)]
        share = (picks.count("Canada") + picks.count("Singapore")) / len(picks)
        self.assertLess(share, 0.04)                  # was ~8% with equal weights
        self.assertGreater(share, 0)                  # still reachable

    def test_missing_code_counts_as_ip_and_waiters_give_up_once_a_swap_is_queued(self):
        self.assertEqual(v.classify_failure("RuntimeError Meta confirmation code not received"), "ip")
        self.assertFalse(v.swap_pending())
        v.request_swap("test", log=QUIET)
        self.assertTrue(v.swap_pending())
        from core import mailfish_api
        runner = mock.Mock()
        with mock.patch.object(mailfish_api, "list_messages", side_effect=AssertionError("must not poll")):
            self.assertIsNone(mailfish_api.wait_code(runner, "a@b.c", timeout=60))

    def test_default_drain_protects_running_accounts(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NORD_ROTATE_DRAIN_S", None)
            self.assertEqual(v.drain_max_s(), 300.0)

    def test_disabled_does_nothing(self):
        with mock.patch.dict(os.environ, {"NORD_ROTATE": "0"}):
            v.finish_cycle(False, "MetaCheckpointBlocked", log=QUIET)
            v.request_swap("x", log=QUIET)
            self.assertIsNone(v._pending)
            v.enter_cycle(log=QUIET)
            self.assertEqual(v._active, 0)

    def test_three_ip_failures_queue_one_swap(self):
        for _ in range(2):
            v.finish_cycle(False, "throttled", log=QUIET)
        self.assertIsNone(v._pending)
        v.finish_cycle(False, "throttled", log=QUIET)
        self.assertIsNotNone(v._pending)

    def test_half_failing_window_queues_swap(self):
        with mock.patch.dict(os.environ, {"NORD_ROTATE_WINDOW": "10", "NORD_ROTATE_FAIL_SHARE": "0.5"}):
            for _ in range(5):
                v.finish_cycle(True, log=QUIET)
            self.assertIsNone(v._pending)            # window not full yet
            for _ in range(5):
                v.finish_cycle(False, "meta.ai click did not leave meta.ai (throttled)", log=QUIET)
            self.assertIsNotNone(v._pending)          # full window, 5 of 10 were IP blocks
            self.assertEqual(len(v._window), 0)       # window restarts after the request

    def test_account_failures_queue_a_swap_when_run_is_not_completing(self):
        # Parallel slots keep failing to finish IG creation: any-cause rule fires.
        with mock.patch.dict(os.environ, {"NORD_ROTATE_WINDOW": "10", "NORD_ROTATE_ANY_SHARE": "0.8"}):
            for _ in range(9):
                v.finish_cycle(False, "Instagram session not established (no sessionid)", log=QUIET)
            self.assertIsNone(v._pending)             # window not full
            v.finish_cycle(False, "Instagram session not established (no sessionid)", log=QUIET)
        self.assertIsNotNone(v._pending)
        self.assertIn("did not finish", v._pending)
        self.assertEqual(v._episode["cats"], {"account": 10})

    def test_mostly_completing_run_does_not_queue_on_account_failures(self):
        with mock.patch.dict(os.environ, {"NORD_ROTATE_WINDOW": "10", "NORD_ROTATE_ANY_SHARE": "0.8"}):
            for i in range(10):
                v.finish_cycle(i % 2 == 0, "Instagram session not established (no sessionid)", log=QUIET)
        self.assertIsNone(v._pending)                 # 5 of 10 did not finish: below 0.8

    def test_repeated_rejected_usernames_queue_a_swap(self):
        with mock.patch.dict(os.environ, {"NORD_ROTATE_STREAK": "2"}):
            for _ in range(2):
                v.finish_cycle(False, "RuntimeError Username not accepted by Instagram after 8 attempts", log=QUIET)
        self.assertIsNotNone(v._pending)

    def test_age_rule_is_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NORD_ROTATE_MAX_AGE_MIN", None)
            self.assertEqual(v.max_age_s(), 0.0)

    def test_classify_failure_categories(self):
        self.assertEqual(v.classify_failure("MetaCheckpointBlocked x"), "ip_block")
        self.assertEqual(v.classify_failure("RuntimeError Meta confirmation code screen not found"), "ip")
        self.assertEqual(v.classify_failure("Instagram session not established (no sessionid)"), "account")
        self.assertEqual(v.classify_failure("Page.goto: Target closed"), "other")

    def test_mostly_ok_window_does_not_queue(self):
        with mock.patch.dict(os.environ, {"NORD_ROTATE_WINDOW": "10", "NORD_ROTATE_FAIL_SHARE": "0.5"}):
            for i in range(10):
                v.finish_cycle(i % 3 != 0, "Can't find account", log=QUIET)  # 4 of 10 failed
        self.assertIsNone(v._pending)

    def test_episode_counts_and_is_written_on_close(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "stats.jsonl")
            with mock.patch.dict(os.environ, {"NORD_ROTATE_STATS": path}):
                v._last_city = ("Canada", "Toronto")
                v.finish_cycle(True, log=QUIET)
                v.finish_cycle(True, log=QUIET)
                v.finish_cycle(False, "Can't find account", log=QUIET)
                self.assertEqual(v._episode["city"], "Canada / Toronto")
                self.assertEqual((v._episode["ok"], v._episode["fail"]), (2, 1))
                v._close_episode("test close", log=QUIET)
                self.assertIsNone(v._episode)
                with open(path, encoding="utf-8") as fh:
                    rec = __import__("json").loads(fh.readline())
                self.assertEqual(rec["accounts"], 3)
                self.assertAlmostEqual(rec["fail_share"], 0.333, places=3)
                self.assertEqual(rec["close_reason"], "test close")
                text = v.report(path)
                self.assertIn("Canada / Toronto", text)
                self.assertIn("swap reasons: test close", text)

    def test_checkpoint_block_queues_immediately(self):
        v.finish_cycle(False, "MetaCheckpointBlocked", log=QUIET)
        self.assertEqual(v._pending, "Meta checkpoint block")

    def test_provisioning_failure_never_queues(self):
        for _ in range(5):
            v.finish_cycle(False, "Instagram session not established (no sessionid)", log=QUIET)
        self.assertIsNone(v._pending)

    def test_success_resets_streak(self):
        v.finish_cycle(False, "throttled", log=QUIET)
        v.finish_cycle(False, "throttled", log=QUIET)
        v.finish_cycle(True, log=QUIET)
        v.finish_cycle(False, "throttled", log=QUIET)
        self.assertIsNone(v._pending)

    def test_stale_server_queues_swap_at_next_account(self):
        v._last_at = 1.0  # connected long ago
        seen = []

        def fake_swap(log=None, forced=False):
            seen.append(v._pending)
            v._pending = None  # what the real _perform_swap does in its finally

        with mock.patch.object(v, "_perform_swap", side_effect=fake_swap):
            with mock.patch.dict(os.environ, {"NORD_ROTATE_MAX_AGE_MIN": "1"}):
                v.enter_cycle(log=QUIET)
        self.assertEqual(len(seen), 1)
        self.assertIn("in use", seen[0])
        self.assertEqual(v._active, 1)  # the account was let in after the swap

    def test_new_account_waits_until_running_one_finishes(self):
        v._active = 1
        v._pending = "test swap"
        done = threading.Event()

        def gate():
            v.enter_cycle(log=QUIET)
            done.set()

        with mock.patch.object(v, "rotate", return_value={"ip": "x"}) as rot, \
             mock.patch.object(v.time, "sleep", side_effect=_fast_sleep):
            t = threading.Thread(target=gate, daemon=True)
            t.start()
            self.assertFalse(done.wait(0.3))           # still waiting for the running account
            v.finish_cycle(True, log=QUIET)           # running account ends
            self.assertTrue(done.wait(5))
        rot.assert_called_once()
        self.assertIsNone(v._pending)
        self.assertEqual(v._active, 1)                # the waiting account is now counted

    def test_forced_swap_after_drain_timeout(self):
        v._active = 1                                 # a stuck running account
        v._pending = "test swap"
        with mock.patch.dict(os.environ, {"NORD_ROTATE_DRAIN_S": "0.2"}), \
             mock.patch.object(v, "rotate", return_value={"ip": "x"}) as rot, \
             mock.patch.object(v.time, "sleep", side_effect=_fast_sleep):
            v.enter_cycle(log=QUIET)
        rot.assert_called_once()
        self.assertIsNone(v._pending)

    def test_failed_swap_on_every_city_holds_new_accounts(self):
        with mock.patch.object(v, "rotate", side_effect=RuntimeError("no connect")) as rot:
            v._perform_swap(log=QUIET) if v._pending else None
            v._pending = "test swap"
            v._perform_swap(log=QUIET)
        self.assertEqual(rot.call_count, v.CONNECT_ATTEMPTS)
        self.assertTrue(v._halted)
        self.assertIsNone(v._pending)

    def test_halted_queues_recover_swap_for_next_account(self):
        v._halted = True
        v._last_at = __import__("time").monotonic()  # recently connected: no stale swap first
        seen = []

        def fake_swap(log=None, forced=False):
            seen.append(v._pending)
            v._pending = None

        with mock.patch.object(v, "_perform_swap", side_effect=fake_swap):
            v.enter_cycle(log=QUIET)
        self.assertEqual(seen, [v.RECOVER])

    def test_city_with_fewer_ip_failures_is_picked_more(self):
        v._stats[("Canada", "Toronto")] = [50, 0]
        v._stats[("Canada", "Calgary")] = [0, 50]
        random.seed(7)
        picks = [v._pick_city() for _ in range(3000)]
        self.assertGreater(picks.count(("Canada", "Toronto")), picks.count(("Canada", "Calgary")) * 3)

    def test_new_process_learns_from_history_and_current_server(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "stats.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"city": "Canada / Toronto", "ok": 40, "cats": {"ip": 2}}) + "\n")
                fh.write(json.dumps({"city": "Canada / Calgary", "ok": 5, "cats": {"ip": 30}}) + "\n")
                fh.write(json.dumps({"city": "Nowhere / Atlantis", "ok": 9, "cats": {}}) + "\n")
            v._history_loaded = False
            with mock.patch.dict(os.environ, {"NORD_ROTATE_STATS": path}), \
                 mock.patch.object(v, "_status", return_value={"City": "Sioux Falls"}):
                v._ensure_history()
        self.assertEqual(v._stats[("Canada", "Toronto")], [40, 2])
        self.assertEqual(v._stats[("Canada", "Calgary")], [5, 30])
        self.assertNotIn(("Nowhere", "Atlantis"), v._stats)      # not in the pool
        self.assertEqual(v._last_city, ("United_States", "Sioux_Falls"))
        self.assertGreater(v._score(("Canada", "Toronto")), v._score(("Canada", "Calgary")))

    def test_pick_never_repeats_last_city(self):
        v._last_city = ("Singapore", "Singapore")
        for _ in range(50):
            self.assertNotEqual(v._pick_city(), ("Singapore", "Singapore"))


if __name__ == "__main__":
    unittest.main()
