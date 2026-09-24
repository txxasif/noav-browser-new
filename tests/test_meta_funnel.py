import time
import unittest

from engine.eng_mix_meta import EngineMetaMixin


class _Locator:
    def __init__(self, visible=False, count=1, page=None):
        self.visible = visible
        self._count = count
        self.page = page
        self.clicks = 0

    @property
    def first(self):
        return self

    def count(self):
        return self._count

    def is_visible(self):
        return self.visible

    def click(self, **kwargs):
        self.clicks += 1
        self.visible = False
        if self.page is not None:
            self.page.consent_clicks += 1


class _Page:
    def __init__(self, consent=False):
        self.consent = _Locator(visible=consent, count=1 if consent else 0, page=self)
        self.dialog = _Locator(visible=False, count=0)
        self.signup = _Locator(visible=True)
        self.waits = []
        self.consent_clicks = 0

    def locator(self, selector):
        if selector == 'div[role="dialog"]':
            return self.dialog
        if 'Sign up' in selector:
            return self.signup
        return _Locator(visible=False, count=0)

    def get_by_role(self, role, name):
        return self.consent

    def wait_for_timeout(self, timeout):
        self.waits.append(timeout)


class MetaFunnelReadinessTests(unittest.TestCase):
    def test_ready_signup_returns_without_sleep(self):
        page = _Page()
        started = time.monotonic()
        result = EngineMetaMixin()._wait_for_meta_signup_control(page, timeout=8000)
        self.assertIs(result, page.signup)
        self.assertLess(time.monotonic() - started, 0.2)
        self.assertEqual(page.waits, [])

    def test_consent_is_dismissed_before_signup(self):
        page = _Page(consent=True)
        result = EngineMetaMixin()._wait_for_meta_signup_control(page, timeout=8000)
        self.assertIs(result, page.signup)
        self.assertEqual(page.consent_clicks, 1)
        self.assertEqual(page.waits, [250])


if __name__ == "__main__":
    unittest.main()
