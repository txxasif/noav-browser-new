import json
import unittest
from unittest import mock

from engine.eng_mix_mail import EngineMailMixin
from pool_common import _mail_http_code, _mail_provider, _make_pool_fetch_code


class _Resp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self._body


class _Runner(EngineMailMixin):
    def __init__(self):
        self.logs = []
        self.mail_tokens = {}

    def log(self, msg):
        self.logs.append(msg)


TOKENS = {"mailfish_email": "c1@frostypeak.info", "mailfish_auth_key": "KEY"}


class MailfishOtpTests(unittest.TestCase):
    def test_provider_detected(self):
        self.assertEqual(_mail_provider(TOKENS), "mailfish")

    def test_fresh_authenticate_code_is_read(self):
        msgs = [
            {"subject": "Authenticate your profile", "from": "noreply@account.meta.com",
             "timestamp": 1786446000000, "textBody": "Your code is 11112222"},
            {"subject": "Authenticate your profile", "from": "noreply@account.meta.com",
             "timestamp": 1786449600000, "textBody": "<p>Your code is <b>84736251</b></p>"},
        ]
        with mock.patch("urllib.request.urlopen", return_value=_Resp(msgs)) as up:
            runner = _Runner()
            code = _mail_http_code(runner, TOKENS, {"1786446000000|Authenticate your profile"}, "instagram", 3,
                                   subject_hint="authenticate your profile|authenticate")
        self.assertEqual(code, "84736251")
        req = up.call_args[0][0]
        self.assertIn("emailAddress=c1%40frostypeak.info", req.full_url)
        self.assertEqual(req.get_header("Authorization"), "KEY")

    def test_snapshot_ids_are_ignored(self):
        msgs = [{"subject": "Authenticate your profile", "from": "noreply@account.meta.com",
                 "timestamp": 1786446000000, "textBody": "Your code is 11112222"}]
        with mock.patch("urllib.request.urlopen", return_value=_Resp(msgs)):
            code = _mail_http_code(_Runner(), TOKENS, {"1786446000000|Authenticate your profile"}, "instagram", 1)
        self.assertIsNone(code)

    def test_pool_fetch_uses_mailfish_inbox(self):
        class _R(_Runner):
            pass
        runner = _R()
        runner.mail_tokens = dict(TOKENS)
        msgs = [{"subject": "Authenticate your profile", "from": "noreply@account.meta.com",
                 "timestamp": 1786453200000, "textBody": "code 55667788"}]
        with mock.patch("urllib.request.urlopen", return_value=_Resp(msgs)):
            fetch = _make_pool_fetch_code(runner, set())
            code = fetch("instagram", timeout=2, subject_hint="authenticate your profile")
        self.assertEqual(code, "55667788")

    def test_reader_needs_textbody_not_just_subject(self):
        """Regression: the pool reader once built text from the subject only."""
        msgs = [{"subject": "Authenticate your profile", "from": "noreply@account.meta.com",
                 "timestamp": 1786453200000, "textBody": "<p>Your code is 92454622</p>"}]
        with mock.patch("urllib.request.urlopen", return_value=_Resp(msgs)):
            code = _mail_http_code(_Runner(), TOKENS, set(), "instagram", 2)
        self.assertEqual(code, "92454622")

    def test_should_stop_ends_the_poll_early(self):
        import time as _t
        with mock.patch("urllib.request.urlopen", return_value=_Resp([])):
            t0 = _t.time()
            code = _mail_http_code(_Runner(), TOKENS, set(), "instagram", 30,
                                   should_stop=lambda: True)
        self.assertIsNone(code)
        self.assertLess(_t.time() - t0, 3)

    def test_inbox_check_sees_mailfish_authenticate_mail(self):
        from instagram.ac_reauth import IgAcReauthMixin

        class _S(IgAcReauthMixin):
            mail_tokens = dict(TOKENS)
            mail = None

            def log(self, _m):
                pass

        with_mail = [{"subject": "Authenticate your profile", "from": "noreply@account.meta.com",
                      "timestamp": 1, "textBody": "x"}]
        other = [{"subject": "Action needed", "from": "notification@email.meta.com",
                  "timestamp": 2, "textBody": "y"}]
        with mock.patch("urllib.request.urlopen", return_value=_Resp(with_mail)):
            self.assertTrue(_S()._ac_inbox_has_auth_mail())
        with mock.patch("urllib.request.urlopen", return_value=_Resp(other)):
            self.assertFalse(_S()._ac_inbox_has_auth_mail())


if __name__ == "__main__":
    unittest.main()
