"""Stacked EU consent modals on auth.meta.com / meta.ai must all be cleared, and a clean page costs nothing."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.eng_mix_meta import EngineMetaMixin  # noqa: E402


class _Btn:
    def __init__(self, page, name):
        self.page, self.name, self.first = page, name, self

    def count(self):
        return 1 if self.name in self.page.buttons else 0

    def is_visible(self):
        return self.count() == 1

    def click(self, timeout=0):
        self.page.clicks.append(self.name)
        self.page.kinds.pop(0)          # the modal goes away


class _Scope:
    def __init__(self, page):
        self.page = page

    def get_by_role(self, role, name=None, exact=False):
        return _Btn(self.page, name)


class FakePage:
    def __init__(self, kinds, buttons):
        self.kinds, self.buttons, self.clicks, self.evals = list(kinds), set(buttons), [], 0

    def evaluate(self, js):
        self.evals += 1
        return self.kinds[0] if self.kinds else ""

    def locator(self, sel):
        return _Scope(self)

    def get_by_role(self, role, name=None, exact=False):
        return _Btn(self, name)

    def wait_for_timeout(self, ms):
        pass


class M(EngineMetaMixin):
    def log(self, *_a, **_k):
        pass


class DialogTests(unittest.TestCase):
    def test_two_stacked_cookie_modals_are_both_cleared(self):
        pg = FakePage(["cookie", "cookie"], ["Decline optional cookies", "Allow all cookies"])
        self.assertEqual(M()._dismiss_blocking_dialogs(pg), 2)
        self.assertEqual(pg.clicks, ["Decline optional cookies", "Decline optional cookies"])

    def test_clean_page_is_one_evaluate(self):
        pg = FakePage([], [])
        self.assertEqual(M()._dismiss_blocking_dialogs(pg), 0)
        self.assertEqual(pg.evals, 1)

    def test_save_login_dialog_is_cleared(self):
        pg = FakePage(["save_login"], ["Save"])
        self.assertEqual(M()._dismiss_blocking_dialogs(pg), 1)
        self.assertEqual(pg.clicks, ["Save"])


if __name__ == "__main__":
    unittest.main()
