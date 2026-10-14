import sys
import unittest
from unittest import mock

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from core import mailfish_api as m  # noqa: E402


class CreateRetryTests(unittest.TestCase):
    def test_gateway_errors_are_retried_not_treated_as_failure(self):
        answers = iter([(502, None), (429, None), (200, {"email": "A@coolember.com"})])
        with mock.patch.object(m, "_request", lambda *a, **k: next(answers)), mock.patch.object(m.time, "sleep", lambda s: None):
            self.assertEqual(m.create_inbox("k"), "a@coolember.com")

    def test_hard_errors_still_stop(self):
        calls = []
        with mock.patch.object(m, "_request", lambda *a, **k: calls.append(1) or (401, None)), mock.patch.object(m.time, "sleep", lambda s: None):
            self.assertEqual(m.create_inbox("k"), "")
        self.assertEqual(len(calls), 1)

    def test_persistent_overload_gives_up(self):
        with mock.patch.object(m, "_request", lambda *a, **k: (502, None)), mock.patch.object(m.time, "sleep", lambda s: None):
            self.assertEqual(m.create_inbox("k"), "")


    def test_server_that_never_answers_gives_up_after_two_silent_tries(self):
        calls = []
        with mock.patch.object(m, "_request", lambda *a, **k: calls.append(1) or (0, None)), mock.patch.object(m.time, "sleep", lambda s: None):
            self.assertEqual(m.create_inbox("k"), "")
        self.assertEqual(len(calls), 2)                     # not 8 x 15 s on a blank page

    def test_total_time_is_capped(self):
        clock = [1000.0]
        def fake_time():
            return clock[0]
        def fake_request(*a, **k):
            clock[0] += 12                                  # each answer takes 12 s
            return 502, None
        with mock.patch.object(m, "_request", fake_request), mock.patch.object(m.time, "time", fake_time), \
                mock.patch.object(m.time, "sleep", lambda s: None):
            self.assertEqual(m.create_inbox("k"), "")
        self.assertLessEqual(clock[0] - 1000.0, 25 + 12 + 1)


if __name__ == "__main__":
    unittest.main()
