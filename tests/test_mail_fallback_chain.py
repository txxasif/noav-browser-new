"""Mail provider choice: the selected provider first, then the fallback order. Disabled providers are skipped."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mailbox import MailboxMixin  # noqa: E402


class _Tab:
    def __init__(self):
        self.closed = False

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


class _Runner(MailboxMixin):
    """Stands in for the engine: a provider either returns an address or raises."""

    def __init__(self, primary, working):
        self.mail_provider = primary
        self._mail_primary = primary
        self.working = set(working)
        self.tried = []
        self.logs = []
        self.mail = None
        self.email = None

    def log(self, m):
        self.logs.append(m)

    def _open_mail_provider(self):
        self.tried.append(self.mail_provider)
        self.mail = _Tab()
        if self.mail_provider not in self.working:
            raise RuntimeError("could not read address")
        self.email = f"a@{self.mail_provider}.test"
        return self.email

    def _snapshot_mail_session(self):
        return {}


class FallbackTests(unittest.TestCase):
    def test_selected_provider_works_and_is_kept(self):
        r = _Runner("mailtd", {"mailtd"})
        self.assertEqual(r.open_mail(), "a@mailtd.test")
        self.assertEqual(r.tried, ["mailtd"])
        self.assertEqual(r.mail_provider, "mailtd")

    def test_mailtd_failure_switches_to_tempmail_fish(self):
        r = _Runner("mailtd", {"mailfish"})
        self.assertEqual(r.open_mail(), "a@mailfish.test")
        self.assertEqual(r.tried, ["mailtd", "mailfish"])
        self.assertEqual(r.mail_provider, "mailfish")
        self.assertTrue(any("switched" in m for m in r.logs))

    def test_fish_failure_falls_back_to_mailtd(self):
        r = _Runner("mailfish", {"mailtd"})
        self.assertEqual(r.open_mail(), "a@mailtd.test")
        self.assertEqual(r.tried, ["mailfish", "mailtd"])

    def test_all_enabled_providers_failing_raises_the_last_error(self):
        r = _Runner("mailtd", set())
        with self.assertRaises(RuntimeError):
            r.open_mail()
        self.assertEqual(r.tried, ["mailtd", "mailfish"])

    def test_next_account_starts_from_the_selected_provider_again(self):
        r = _Runner("mailtd", {"mailfish"})
        r.open_mail()
        r.working = {"mailtd", "mailfish"}
        r.tried.clear()
        r.open_mail()
        self.assertEqual(r.tried, ["mailtd"])

    def test_failed_tab_is_closed_before_the_next_provider(self):
        r = _Runner("mailtd", {"mailfish"})
        tabs = []
        orig = r._open_mail_provider

        def spy():
            try:
                return orig()
            finally:
                tabs.append(r.mail)
        r._open_mail_provider = spy
        r.open_mail()
        self.assertTrue(tabs[0].closed)

    def test_alias_open_mailtd_never_switches_provider(self):
        r = _Runner("mailfish", set())
        with self.assertRaises(RuntimeError):
            r.open_mailtd()
        self.assertEqual(r.tried, ["mailtd"])


class DisabledProviderTests(unittest.TestCase):
    def test_yamin_and_cloudflare_are_skipped(self):
        for prim in ("yamin", "mailcf", "guerrilla"):
            r = _Runner(prim, set())
            r._mail_primary = prim
            self.assertEqual(r._mail_chain(), ["mailfish", "mailtd"], prim)

    def test_disabled_selection_uses_the_enabled_provider(self):
        r = _Runner("yamin", {"mailfish"})
        self.assertEqual(r.open_mail(), "a@mailfish.test")
        self.assertEqual(r.tried, ["mailfish"])

    def test_list_keeps_the_disabled_names(self):
        from ai_config import Urls
        self.assertIn("yamin", Urls.MAIL_PROVIDERS)
        self.assertIn("mailcf", Urls.MAIL_PROVIDERS)
        self.assertEqual(set(Urls.DISABLED_MAIL_PROVIDERS), {"yamin", "mailcf", "guerrilla"})


class _EngineStub:
    td_works = True

    def open_mailtd(self):
        self.mail = _TdTab()
        if not self.td_works:
            raise RuntimeError("could not read mail.td address")
        self.email = "x@nqmo.com"

    def open_mailfish(self):
        raise RuntimeError("web inbox not used here")


class _TdTab(_Tab):
    def evaluate(self, js):
        return {"tempmail_token": "tok", "tempmail_account_id": "acc"}


class _Real(MailboxMixin, _EngineStub):
    def __init__(self, primary):
        self.mail_provider = primary
        self._mail_primary = primary
        self.mail = None
        self.email = None
        self.logs = []

    def log(self, m):
        self.logs.append(m)


class SavedTokensTests(unittest.TestCase):
    def test_selected_mailtd_saves_mailtd_tokens(self):
        import pool_common
        r = _Real("mailtd")
        r.open_mail()
        tokens = r._snapshot_mail_session()
        self.assertEqual(pool_common._mail_provider(tokens), "mailtd")
        self.assertEqual(tokens["tempmail_token"], "tok")


class FishServerDownTests(unittest.TestCase):
    """tempmail.fish API down: its web inbox is not tried, the chain moves on to mail.td."""

    def test_fish_api_down_skips_web_inbox_and_uses_mailtd(self):
        from core import mailfish_api
        r = _Real("mailfish")
        web_tried = []
        r.open_mailfish = lambda: web_tried.append(1)
        with mock.patch.object(mailfish_api, "api_enabled", lambda: True), \
                mock.patch.object(mailfish_api, "create_inbox", lambda style="random": ""), \
                mock.patch.object(mailfish_api, "last_failure", "down"):
            r.open_mail()
        self.assertEqual(web_tried, [])
        self.assertEqual(r.mail_provider, "mailtd")


if __name__ == "__main__":
    unittest.main()
