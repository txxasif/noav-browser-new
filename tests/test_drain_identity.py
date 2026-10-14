import json
import os
import tempfile
import unittest

from engine.eng_antidetect import pc_mobile_identity, pc_mobile_models
from run_paygo_pool_2fa_cycle import _pin_creation_device, _restore_session_storage


class _Runner:
    device_model = None
    device_ua = None


class _Page:
    def __init__(self, url):
        self.url = url
        self.calls = []

    def evaluate(self, js, arg=None):
        self.calls.append(arg)


class PinnedPhoneTests(unittest.TestCase):
    def test_saved_model_and_ua_are_pinned_before_launch(self):
        r = _Runner()
        model = _pin_creation_device(r, {"device_model": "Pixel 6", "device_ua": "UA-1"})
        self.assertEqual((model, r.device_model, r.device_ua), ("Pixel 6", "Pixel 6", "UA-1"))

    def test_record_without_a_saved_phone_leaves_the_runner_alone(self):
        r = _Runner()
        self.assertEqual(_pin_creation_device(r, {}), "")
        self.assertIsNone(r.device_model)

    def test_a_pinned_model_gives_the_same_identity_whatever_the_new_profile_name(self):
        """The drain's profile dir is new every run; the pinned model must still decide the phone."""
        for model in pc_mobile_models():
            a = pc_mobile_identity("insta_95_1111", model=model)
            b = pc_mobile_identity("insta_95_2222", model=model)
            self.assertEqual(a, b, model)


class StorageRestoreTests(unittest.TestCase):
    def _session(self, origin):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "s.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"origins": [{"origin": origin,
                                    "localStorage": [{"name": "ig_k", "value": "v1"}]}]}, f)
        return path

    def test_writes_only_when_the_page_is_on_that_origin(self):
        acc = {"session_file": self._session("https://www.instagram.com")}
        page = _Page("https://www.instagram.com/")
        self.assertEqual(_restore_session_storage(page, acc), 1)
        self.assertEqual(page.calls, [{"ig_k": "v1"}])

    def test_other_origin_is_skipped(self):
        acc = {"session_file": self._session("https://www.instagram.com")}
        page = _Page("https://accountscenter.instagram.com/")
        self.assertEqual(_restore_session_storage(page, acc), 0)
        self.assertEqual(page.calls, [])

    def test_missing_session_file_is_a_noop(self):
        self.assertEqual(_restore_session_storage(_Page("https://www.instagram.com/"), {}), 0)


if __name__ == "__main__":
    unittest.main()
