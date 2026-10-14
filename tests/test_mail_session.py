"""The mailbox session is cached while the tab is open, so a tab closed before save keeps it."""
import unittest

from core.mailbox import MailboxMixin


class _Tab:
    def __init__(self, token=None, closed=False):
        self._token = token
        self._closed = closed

    def is_closed(self):
        return self._closed

    def evaluate(self, _script):
        return {"tempmail_token": self._token or "", "tempmail_account_id": "acc-1" if self._token else ""}


class _Runner(MailboxMixin):
    def __init__(self, provider, mail=None, email=""):
        self.mail_provider = provider
        self.mail = mail
        self.email = email


class MailSessionTests(unittest.TestCase):
    def test_open_tab_token_is_cached(self):
        r = _Runner("mailtd", mail=_Tab(token="tok-1"))
        self.assertEqual(r._snapshot_mail_session()["tempmail_token"], "tok-1")
        self.assertEqual(r._mail_session["tempmail_account_id"], "acc-1")

    def test_closed_tab_keeps_the_cached_session(self):
        r = _Runner("mailtd", mail=_Tab(token="tok-1"))
        r._snapshot_mail_session()
        r.mail = _Tab(closed=True)
        self.assertEqual(r._snapshot_mail_session()["tempmail_token"], "tok-1")

    def test_empty_tab_never_overwrites_a_good_token(self):
        r = _Runner("mailtd", mail=_Tab(token="tok-1"))
        r._snapshot_mail_session()
        r.mail = _Tab(token=None)
        self.assertEqual(r._snapshot_mail_session()["tempmail_token"], "tok-1")

    def test_mailfish_keeps_its_address(self):
        r = _Runner("mailfish", mail=None, email="x@tempmail.example")
        self.assertEqual(r._snapshot_mail_session(), {"mailfish_email": "x@tempmail.example"})


if __name__ == "__main__":
    unittest.main()
