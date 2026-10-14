import json
import unittest
from unittest import mock

from engine import eng_mix_mail
from engine.eng_mix_mail import EngineMailMixin


class _Resp:
    def __init__(self, body: bytes = b"{}"):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class _Creator(EngineMailMixin):
    def __init__(self):
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)


class MailcfTokenTests(unittest.TestCase):
    def test_new_address_registers_token_with_admin_auth(self):
        creator = _Creator()
        sent = {}

        def fake_urlopen(req, timeout=None):
            sent["url"] = req.full_url
            sent["auth"] = req.get_header("Authorization")
            sent["body"] = json.loads(req.data.decode())
            return _Resp()

        with mock.patch.object(eng_mix_mail, "CF_MAIL_ADMIN_TOKEN", "admin-secret"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            addr = creator.new_mailcf_address()

        self.assertTrue(sent["url"].endswith("/register"))
        self.assertEqual(sent["auth"], "Bearer admin-secret")
        self.assertEqual(sent["body"]["email"], addr)
        self.assertEqual(sent["body"]["token"], creator.mail_token)
        self.assertGreaterEqual(len(creator.mail_token), 24)

    def test_missing_admin_token_skips_registration_without_failing(self):
        creator = _Creator()
        with mock.patch.object(eng_mix_mail, "CF_MAIL_ADMIN_TOKEN", ""), \
                mock.patch("urllib.request.urlopen") as opener:
            addr = creator.new_mailcf_address()
        opener.assert_not_called()
        self.assertTrue(addr.endswith("@" + eng_mix_mail.CF_MAIL_DOMAIN))
        self.assertIn("CF_MAIL_ADMIN_TOKEN not set", creator.logs[-1])

    def test_each_address_gets_its_own_token(self):
        creator = _Creator()
        with mock.patch.object(eng_mix_mail, "CF_MAIL_ADMIN_TOKEN", ""):
            creator.new_mailcf_address()
            first = creator.mail_token
            creator.new_mailcf_address()
        self.assertNotEqual(first, creator.mail_token)


class MailReaderTests(unittest.TestCase):
    def test_list_messages_sends_email_and_token(self):
        from core import mail_reader

        body = json.dumps({"messages": [{"subject": "hi"}]}).encode()
        with mock.patch("urllib.request.urlopen", return_value=_Resp(body)) as opener:
            msgs = mail_reader.list_messages("a.b.1@lumencreative.site", "tok123")
        req = opener.call_args[0][0]
        self.assertIn("/messages?", req.full_url)
        self.assertIn("email=a.b.1%40lumencreative.site", req.full_url)
        self.assertIn("token=tok123", req.full_url)
        self.assertEqual(msgs, [{"subject": "hi"}])

    def test_mailcf_token_for_reads_saved_token(self):
        from core import mail_reader

        self.assertEqual(mail_reader.mailcf_token_for({"mail_tokens": {"mailcf_token": "x"}}), "x")
        self.assertEqual(mail_reader.mailcf_token_for({"mail_tokens": {}}), "")
        self.assertEqual(mail_reader.mailcf_token_for({}), "")


if __name__ == "__main__":
    unittest.main()


class MailRetireTests(unittest.TestCase):
    def test_retire_posts_admin_auth_and_email(self):
        from core import mail_reader

        sent = {}

        def fake_urlopen(req, timeout=None):
            sent["url"] = req.full_url
            sent["auth"] = req.get_header("Authorization")
            sent["body"] = json.loads(req.data.decode())
            resp = _Resp()
            resp.status = 200
            return resp

        with mock.patch.object(mail_reader.Urls, "CF_MAIL_ADMIN_TOKEN", "admin-secret"), \
                mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok = mail_reader.retire_mailbox("a.b.1@lumencreative.site")
        self.assertTrue(ok)
        self.assertTrue(sent["url"].endswith("/retire"))
        self.assertEqual(sent["auth"], "Bearer admin-secret")
        self.assertEqual(sent["body"], {"email": "a.b.1@lumencreative.site"})

    def test_retire_without_admin_token_does_nothing(self):
        from core import mail_reader

        with mock.patch.object(mail_reader.Urls, "CF_MAIL_ADMIN_TOKEN", ""), \
                mock.patch("urllib.request.urlopen") as opener:
            self.assertFalse(mail_reader.retire_mailbox("a.b.1@lumencreative.site"))
        opener.assert_not_called()

    def test_retire_session_is_noop_for_mailtd(self):
        from core.mailbox import MailboxMixin

        class Runner(MailboxMixin):
            mail_provider = "mailtd"
            email = "x@mail.td"
            def log(self, msg):
                pass

        with mock.patch("core.mailbox.retire_mailbox") as retire:
            self.assertFalse(Runner().retire_mail_session())
        retire.assert_not_called()

    def test_link_retires_only_on_success(self):
        from instagram.identity import IgIdentityMixin

        class Runner(IgIdentityMixin):
            def __init__(self, result):
                self._result = result
                self.retired = 0
            def _ig_link_email_impl(self, target_email=None, code_fetcher=None):
                return self._result
            def retire_mail_session(self):
                self.retired += 1
                return True

        ok = Runner(True)
        self.assertTrue(ok.ig_link_email_to_instagram("a@x.y"))
        self.assertEqual(ok.retired, 1)

        failed = Runner(False)
        self.assertFalse(failed.ig_link_email_to_instagram("a@x.y"))
        self.assertEqual(failed.retired, 0)
