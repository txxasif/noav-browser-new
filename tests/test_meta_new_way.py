import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.captcha import CaptchaMixin  # noqa: E402


class _Page:
    def __init__(self, url, goto_fails=False):
        self.url = url
        self._after = url
        self.goto_fails = goto_fails
        self.gotos = []

    def goto(self, url, **kw):
        self.gotos.append(url)
        if self.goto_fails:
            raise RuntimeError("net::ERR")
        self.url = self._after

    def wait_for_timeout(self, ms):
        pass


class _R(CaptchaMixin):
    def __init__(self, page, human=False, provisioned=True):
        self.page = page
        self.logs = []
        self._human = human
        self._prov = provisioned

    def log(self, m):
        self.logs.append(m)

    def _has_human_check(self, p):
        return self._human

    def _wait_meta_provisioned(self, p, timeout=45):
        return self._prov


AUTH_META = "https://auth.meta.com"
LANG = "https://auth.meta.com/language"


class NewWayShortcutTests(unittest.TestCase):
    def test_language_page_with_live_session_is_accepted(self):
        pg = _Page("https://meta.ai/?x"); pg._after = LANG
        r = _R(pg)
        self.assertTrue(r._meta_new_way_shortcut(pg))
        self.assertEqual(pg.gotos, [AUTH_META])

    def test_redirect_to_checkpoint_is_not_conclusive(self):
        pg = _Page("https://meta.ai/"); pg._after = "https://auth.meta.com/checkpoints/675270400317265/"
        self.assertFalse(_R(pg)._meta_new_way_shortcut(pg))

    def test_human_check_on_the_page_is_not_conclusive(self):
        pg = _Page("https://meta.ai/"); pg._after = LANG
        self.assertFalse(_R(pg, human=True)._meta_new_way_shortcut(pg))

    def test_unsettled_session_is_not_conclusive(self):
        pg = _Page("https://meta.ai/"); pg._after = LANG
        self.assertFalse(_R(pg, provisioned=False)._meta_new_way_shortcut(pg))

    def test_navigation_error_is_not_conclusive(self):
        pg = _Page("https://meta.ai/", goto_fails=True)
        self.assertFalse(_R(pg)._meta_new_way_shortcut(pg))


class GuardTests(unittest.TestCase):
    """The shortcut only runs when the dashboard asks for the new way; the default is the old flow."""

    def _run(self, flow):
        pg = _Page("https://meta.ai/home")
        r = _R(pg)
        called = []
        r._meta_new_way_shortcut = lambda p: called.append(1) or True
        env = {} if flow is None else {"INSTA_META_FLOW": flow}
        with mock.patch.dict(os.environ, env, clear=False):
            if flow is None:
                os.environ.pop("INSTA_META_FLOW", None)
            # the old checks are not under test: stop right after the guard
            r._dismiss_cookie_choice = lambda p: (_ for _ in ()).throw(StopIteration())
            try:
                res = r.ensure_meta_verified()
            except StopIteration:
                res = "old-flow-started"
        return called, res

    def test_default_and_old_never_use_the_shortcut(self):
        for flow in (None, "old", "garbage"):
            called, res = self._run(flow)
            self.assertEqual(called, [], flow)
            self.assertEqual(res, "old-flow-started", flow)

    def test_new_way_uses_the_shortcut_and_returns_true(self):
        called, res = self._run("new")
        self.assertEqual(called, [1])
        self.assertIs(res, True)


class PCToolParityTests(unittest.TestCase):
    def test_final_url_for_save(self):
        pg = _Page("https://auth.meta.com/language?foo=bar")
        r = _R(pg)
        self.assertTrue(r._pc_check_final_url_for_save(pg))

        pg_other = _Page("https://auth.meta.com/checkpoints/")
        self.assertFalse(r._pc_check_final_url_for_save(pg_other))

    def test_detect_auth_page_fallback(self):
        pg = _Page("https://auth.meta.com")
        r = _R(pg)
        info = r._pc_detect_auth_page(pg)
        self.assertEqual(info.get("type"), "unknown")

    def test_post_otp_flow_immediate_success(self):
        class _SuccessPage(_Page):
            def evaluate(self, script, *args):
                if "window.location.href" in script:
                    return "url"
                return None
            def wait_for_load_state(self, *a, **k):
                pass
        pg = _SuccessPage("https://meta.ai/chat")
        r = _R(pg)
        r._pc_check_success = lambda p: "url"
        self.assertTrue(r._pc_post_otp_flow(pg))

    def test_dismiss_save_login_info_present(self):
        class _SaveLoginPage(_Page):
            def __init__(self, url):
                super().__init__(url)
                self.clicked = []
            def evaluate(self, script, *args):
                if "save your login info" in script and "document.body" in script:
                    return True
                if "isTarget" in script:
                    self.clicked.append("Save")
                    return "Save"
                return None
        pg = _SaveLoginPage("https://auth.meta.com/?rcs=abc")
        r = _R(pg)
        self.assertTrue(r._dismiss_save_login_info(pg))
        self.assertIn("Save", pg.clicked)

    def test_dismiss_save_login_info_absent(self):
        class _CleanPage(_Page):
            def evaluate(self, script, *args):
                return False
        pg = _CleanPage("https://auth.meta.com/language")
        r = _R(pg)
        self.assertFalse(r._dismiss_save_login_info(pg))


if __name__ == "__main__":
    unittest.main()
