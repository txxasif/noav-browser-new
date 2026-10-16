"""EU (Sweden) Meta screens: cookie-choice page before the human check, and its URL trap."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.captcha import CaptchaMixin  # noqa: E402
from instagram.helpers import IgHelpersMixin  # noqa: E402

CONSENT = ("https://auth.meta.com/privacy/consent/?flow=user_cookie_choice_v2&params%5Breferrer%5D="
           "https%3A%2F%2Fauth.meta.com%2Fcheckpoints%2F675270400317265%2F%3Fnext%3Dx")
CHECKPOINT = "https://auth.meta.com/checkpoints/675270400317265/?next=x"


class _Btn:
    def __init__(self, page, name):
        self.page, self.name = page, name
        self.first = self

    def count(self):
        return 1 if self.name in self.page.buttons else 0

    def is_visible(self):
        return self.count() == 1

    def click(self, timeout=0):
        self.page.clicked.append(self.name)
        self.page.url = CHECKPOINT


class FakePage:
    def __init__(self, url, buttons=()):
        self.url, self.buttons, self.clicked = url, set(buttons), []

    def get_by_role(self, role, name=None, exact=False):
        return _Btn(self, name)

    def wait_for_timeout(self, ms):
        pass

    def inner_text(self, sel):
        return "allow the use of cookies from meta?"


class M(CaptchaMixin):
    def log(self, *_a, **_k):
        pass


class EuTests(unittest.TestCase):
    def test_consent_page_is_not_a_human_check(self):
        # the word "checkpoints" sits in the QUERY of the consent URL only
        self.assertFalse(M()._has_human_check(FakePage(CONSENT)))
        self.assertTrue(M()._has_human_check(FakePage(CHECKPOINT)))

    def test_declines_optional_cookies_and_leaves_consent(self):
        pg = FakePage(CONSENT, ["Decline optional cookies", "Allow all cookies"])
        self.assertTrue(M()._dismiss_cookie_choice(pg))
        self.assertEqual(pg.clicked, ["Decline optional cookies"])
        self.assertIn("/checkpoints/", pg.url)

    def test_other_pages_cost_nothing(self):
        pg = FakePage("https://auth.meta.com/", ["Decline optional cookies"])
        self.assertFalse(M()._dismiss_cookie_choice(pg))
        self.assertEqual(pg.clicked, [])


class _IgEuHelpers(IgHelpersMixin):
    """IgHelpersMixin with logging captured; the rest of the mixin is not exercised."""

    def __init__(self):
        self.logs = []

    def log(self, msg, *_a, **_k):
        self.logs.append(str(msg))


class _EuPage:
    """Minimal page: the JS sweep answers ``js_result``, locators answer ``hits``."""

    def __init__(self, js_result=None, hits=()):
        self.js_result, self.hits = js_result, list(hits)
        self.clicked = []
        self.waits = 0

    def evaluate(self, script, *args):
        return self.js_result

    def locator(self, sel):
        outer = self
        hit = any(h in sel for h in self.hits)

        class _Loc:
            def __init__(self):
                self.first = self

            def count(self):
                return 1 if hit else 0

            def is_visible(self):
                return hit

            def scroll_into_view_if_needed(self, timeout=None):
                pass

            def click(self, timeout=None, force=False):
                outer.clicked.append(sel)

        return _Loc()

    def wait_for_timeout(self, ms):
        self.waits += 1


class InstagramAllowAndCreateTests(unittest.TestCase):
    """The screen that lands right after the IG username step:

    'Finish creating your Instagram profile in this Meta Account' -> 'Allow and create'
    (its button sits below the fold of the scrolled modal, hence the JS scroll + real
    pointer/mouse dispatch), with the EU localizations and the terms 'I agree' covered.
    """

    def test_js_sweep_accepts_allow_and_create(self):
        pg = _EuPage(js_result="Allow and create")
        m = _IgEuHelpers()
        self.assertTrue(m._accept_ig_eu_interstitial(pg))
        self.assertEqual(pg.clicked, [])                     # JS path wins
        self.assertTrue(any("interstitial accepted" in s for s in m.logs))

    def test_locator_fallback_when_js_finds_nothing(self):
        pg = _EuPage(js_result=None, hits=("Allow and create",))
        m = _IgEuHelpers()
        self.assertTrue(m._accept_ig_eu_interstitial(pg))
        self.assertTrue(any("Allow and create" in sel for sel in pg.clicked))

    def test_screen_absent_is_a_no_op(self):
        pg = _EuPage(js_result=None)
        m = _IgEuHelpers()
        self.assertFalse(m._accept_ig_eu_interstitial(pg))
        self.assertEqual(pg.clicked, [])


if __name__ == "__main__":
    unittest.main()

class LoginChallengeTests(unittest.TestCase):
    """"Check your email" re-login after the chooser: password first, inbox code as the fallback."""

    class Pg:
        def __init__(self, body, url="https://auth.meta.com/"):
            self.body, self.url, self.waits = body, url, 0

        def inner_text(self, sel):
            return self.body

        def wait_for_timeout(self, ms):
            self.waits += 1

        def locator(self, sel):
            outer = self

            class L:
                first = None

                def is_visible(s):
                    return False
            L.first = L()
            return L()

    class Runner(CaptchaMixin):
        def __init__(self, with_password_option=True):
            self.clicks, self.fills, self.password = [], [], "pw123"
            self.opt = with_password_option

        def log(self, *_a, **_k):
            pass

        def _try_click(self, p, name, role="button", timeout=0):
            self.clicks.append(name)
            return name != "Enter password instead" or self.opt

        def _try_fill(self, p, name, value, role="textbox", timeout=0):
            self.fills.append((name, value))
            return True

        def _poll_checkpoint_settled(self, p, timeout=0):
            pass

        def fetch_code(self, kw, timeout=0):
            return "123456"

    CHECK = "check your email to log in, enter the code we sent to d***@f***.info code resend code log in enter password instead"

    def test_uses_the_password_when_offered(self):
        r = self.Runner()
        self.assertTrue(r._meta_login_challenge(self.Pg(self.CHECK)))
        self.assertEqual(r.clicks, ["Enter password instead", "Log in"])
        self.assertEqual(r.fills, [("Password", "pw123")])

    def test_falls_back_to_the_inbox_code(self):
        r = self.Runner(with_password_option=False)
        self.assertTrue(r._meta_login_challenge(self.Pg(self.CHECK)))
        self.assertEqual(r.fills, [("Code", "123456")])
        self.assertEqual(r.clicks[-1], "Log in")

    def test_other_pages_are_ignored_and_chooser_counts_as_relogin(self):
        r = self.Runner()
        self.assertFalse(r._meta_login_challenge(self.Pg("confirm you're human")))
        self.assertTrue(CaptchaMixin._needs_meta_relogin(self.Pg("log in with your meta account continue as x")))
        self.assertFalse(CaptchaMixin._needs_meta_relogin(self.Pg("confirm you're human", "https://auth.meta.com/checkpoints/1/")))
