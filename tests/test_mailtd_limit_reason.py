import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
from engine.eng_mix_mail import EngineMailMixin as M  # noqa: E402


class LimitReasonTests(unittest.TestCase):
    def test_slow_proof_of_work_is_not_a_limit(self):
        retry = {"status": 200, "body": '{"status":"retry","required_difficulty":22,"token":"x"}'}
        self.assertEqual(M._mailtd_limit_reason([retry], "Minting your address…"), "")
        self.assertEqual(M._mailtd_limit_reason([], ""), "")

    def test_rate_limit_and_quota_stop_at_once(self):
        self.assertIn("429", M._mailtd_limit_reason([{"status": 429, "body": "pow_retry_exhausted"}]))
        self.assertIn("quota", M._mailtd_limit_reason([{"status": 403, "body": '{"error":"ops_quota_exceeded"}'}]))

    def test_page_text_alone_is_never_a_limit(self):
        # live check: "Operations used up" was in the page text while a mailbox was being created normally
        self.assertEqual(M._mailtd_limit_reason([], "Operations used up\nYou've reached the free plan limit."), "")
        self.assertEqual(M._mailtd_limit_reason([], "Too many requests — wait a second and try again."), "")

    def test_created_account_is_fine(self):
        self.assertEqual(M._mailtd_limit_reason([{"status": 201, "body": '{"address":"a@b.c"}'}], "a@b.c"), "")


if __name__ == "__main__":
    unittest.main()
