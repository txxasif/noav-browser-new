import unittest

from instagram.password import IgPasswordMixin


class _Loc:
    def __init__(self, page):
        self.page = page
        self.first = self

    def wait_for(self, **_kw):
        return None

    def click(self, **_kw):
        return None

    def fill(self, value):
        self.page.filled.append(value)


class _Page:
    def __init__(self, bodies):
        self.bodies = list(bodies)       # successive inner_text("body") results
        self.filled = []
        self.urls = []

    def goto(self, url, **_kw):
        self.urls.append(url)

    def locator(self, _sel):
        return _Loc(self)

    def wait_for_timeout(self, _ms):
        return None

    def inner_text(self, _sel):
        return self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]


class _Preauth(IgPasswordMixin):
    def __init__(self, page, reauth=None):
        self._page = page
        self._reauth = reauth
        self.reauth_calls = 0
        self.logs = []

    def _ig_tab(self):
        return self._page

    def log(self, msg):
        self.logs.append(msg)

    def _ac_section(self, *_a, **_k):
        return None          # Accounts Center reached by UI clicks (no URL)

    def _try_click(self, *_a, **_k):
        return True          # "Change password" row clicked

    def _ac_reauth(self, _p, password=None):
        self.reauth_calls += 1
        if self._reauth:
            self._reauth()
        return True


CHALLENGE = "Two Step Verification Check your email Enter the code we sent to r******z@f*****.info"


class AcPreauthTests(unittest.TestCase):
    def test_no_challenge_means_already_verified(self):
        page = _Page(["Change password Current password New password"])
        m = _Preauth(page)
        self.assertTrue(m.ig_ac_preauth("secret-pw", max_wait=5))
        self.assertEqual(m.reauth_calls, 0)
        self.assertEqual(page.filled, ["", "secret-pw"])   # set in ONE step, never typed key by key
        self.assertIn("password/change", page.urls[0])   # old flow: direct change-password form

    def test_challenge_is_solved_before_returning(self):
        page = _Page([CHALLENGE, CHALLENGE, "Change password New password"])
        m = _Preauth(page)
        self.assertTrue(m.ig_ac_preauth("secret-pw", max_wait=10))
        self.assertGreaterEqual(m.reauth_calls, 1)

    def test_unsolved_challenge_returns_false_without_raising(self):
        page = _Page([CHALLENGE])
        m = _Preauth(page)
        self.assertFalse(m.ig_ac_preauth("secret-pw", max_wait=0.1))

    def test_missing_password_is_a_noop(self):
        m = _Preauth(_Page(["x"]))
        self.assertFalse(m.ig_ac_preauth("", max_wait=1))
        self.assertEqual(m.reauth_calls, 0)


if __name__ == "__main__":
    unittest.main()
