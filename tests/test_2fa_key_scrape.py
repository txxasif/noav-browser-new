"""The 2FA key scraper must only ever return the real key.

Live bug (2026-10-12): on the Accounts Center intro screen the loose text filter accepted the heading
"Set up extra protection for your Meta Account" (letters only; spaces removed it is a valid base32
string), a junk key went to the PayGo bot and Instagram rejected every code afterwards.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagram.twofa import IgTwofaMixin  # noqa: E402


class FakePage:
    def __init__(self, url, body, candidates):
        self.url = url
        self._body = body
        self._cands = candidates

    def evaluate(self, script, *a):
        if "data-clipboard-text" in script:
            return self._cands
        if "otpauth" in script:
            return None
        return self._body

    def locator(self, *_a, **_k):  # reveal-trigger probes: nothing visible
        class _L:
            first = None

            def count(self_inner):
                return 0

        _L.first = _L()
        return _L()


class Scraper(IgTwofaMixin):
    pass


AC = "https://accountscenter.instagram.com/password_and_security/two_factor/"

INTRO_BODY = ("Set up extra protection for your Meta Account Add an extra login step for new devices "
              "to confirm it's you. Keeps you protected even if your password is guessed or stolen. Get started")
INTRO_CANDS = ["Set up extra protection for your Meta Account",
               "Best for accounts with sensitive information Meta has security measures to protect all accounts"]

KEY_BODY = ("Instructions for setup 1. Download an authentication app 2. Scan this barcode/QR code or copy "
            "the key ET5L WUFA Z3SA QUYW Copy key 3. Copy and enter 6-digit code Enter code")


class KeyScrapeTests(unittest.TestCase):
    def test_intro_screen_never_yields_a_key(self):
        self.assertIsNone(Scraper().ig_scrape_2fa_key(FakePage(AC, INTRO_BODY, INTRO_CANDS)))

    def test_real_key_is_read_from_the_key_screen(self):
        page = FakePage(AC, KEY_BODY, ["ET5L WUFA Z3SA QUYW"])
        self.assertEqual(Scraper().ig_scrape_2fa_key(page), "ET5LWUFAZ3SAQUYW")

    def test_32_char_key_in_eight_groups(self):
        key = "5B2V BGES GRZY JFS4 E3DM HBQA SV44 ENO6"
        body = KEY_BODY.replace("ET5L WUFA Z3SA QUYW", key)
        self.assertEqual(Scraper().ig_scrape_2fa_key(FakePage(AC, body, [key])),
                         key.replace(" ", ""))

    def test_lowercase_text_is_never_a_key_candidate(self):
        page = FakePage(AC, KEY_BODY.replace("ET5L WUFA Z3SA QUYW", ""),
                        ["Set up extra protection for your Meta Account"])
        self.assertIsNone(Scraper().ig_scrape_2fa_key(page))


if __name__ == "__main__":
    unittest.main()
