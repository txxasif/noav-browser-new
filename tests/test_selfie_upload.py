"""Selfie checkpoint: upload is a send (not a preview gate), decoy inputs are skipped,
and Continue is waited for instead of clicked while Meta is still processing."""
import os
import sys
import tempfile
import types
from unittest import mock
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.captcha import CaptchaMixin  # noqa: E402


class FakeInput:
    def __init__(self, fail=False):
        self.fail, self.set_with = fail, []

    def set_input_files(self, path, timeout=0):
        if self.fail:
            raise RuntimeError("not attachable")
        self.set_with.append(path)

    def evaluate(self, _js):
        pass


class FakeLocator:
    def __init__(self, inputs):
        self.inputs = inputs

    def count(self):
        return len(self.inputs)

    def nth(self, i):
        return self.inputs[i]

    @property
    def first(self):
        return self.inputs[0]


class FakeFrame:
    def __init__(self, inputs):
        self.inputs = inputs

    def locator(self, sel):
        return FakeLocator(self.inputs if sel == 'input[type="file"]' else [])


class FakePage:
    """No upload buttons, no file chooser, no CDP: only the inputs can take the file."""

    def __init__(self, frames):
        self.frames = frames
        self.url = "https://auth.meta.com/checkpoints/1/"
        self.context = types.SimpleNamespace(new_cdp_session=self._no_cdp)

    def _no_cdp(self, _page):
        raise RuntimeError("no CDP")

    def locator(self, _sel):
        return FakeLocator([])

    def wait_for_timeout(self, _ms):
        pass


class M(CaptchaMixin):
    def __init__(self):
        self.logs = []
        self.w = types.SimpleNamespace(is_running=True)

    def log(self, msg, *_a, **_k):
        self.logs.append(msg)


class SelfieUploadTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".png")
        os.write(fd, b"png")
        os.close(fd)

    def tearDown(self):
        os.remove(self.path)

    def _mixin(self):
        m = M()
        m.selfie_path = self.path
        return m

    def test_direct_input_send_counts_as_sent_without_preview(self):
        inp = FakeInput()
        m = self._mixin()
        self.assertTrue(m._upload_selfie(FakePage([FakeFrame([inp])])))
        self.assertEqual(inp.set_with, [self.path])

    def test_decoy_input_does_not_block_the_real_one(self):
        decoy, real = FakeInput(fail=True), FakeInput()
        m = self._mixin()
        self.assertTrue(m._upload_selfie(FakePage([FakeFrame([decoy, real])])))
        self.assertEqual(real.set_with, [self.path])

    def test_reports_failure_only_when_nothing_accepts_the_file(self):
        m = self._mixin()
        self.assertFalse(m._upload_selfie(FakePage([FakeFrame([FakeInput(fail=True)])])))
        self.assertFalse(m._upload_selfie(FakePage([FakeFrame([])])))

    def test_missing_selfie_file_fails_fast(self):
        m = M()
        m.selfie_path = os.path.join(tempfile.gettempdir(), "does-not-exist-selfie.png")
        missing = m.selfie_path
        with mock.patch("ai_config.get_random_selfie", return_value=missing):
            inp = FakeInput()
            self.assertFalse(m._upload_selfie(FakePage([FakeFrame([inp])])))
        self.assertEqual(inp.set_with, [])

    def test_continue_waits_until_enabled_then_clicks(self):
        m = self._mixin()
        states = [None, None, object()]          # Continue disabled twice, then enabled
        clicked = []
        m._checkpoint_action = lambda page, names, require_enabled: states.pop(0)
        m._click_checkpoint_action = lambda page, name, timeout: clicked.append(name) or True
        self.assertTrue(m._wait_selfie_continue(FakePage([]), timeout=5))
        self.assertEqual(clicked, ["Continue"])

    def test_continue_never_enabled_returns_false_without_clicking(self):
        m = self._mixin()
        clicked = []
        m._checkpoint_action = lambda page, names, require_enabled: None
        m._click_checkpoint_action = lambda *a, **k: clicked.append(1) or True
        self.assertFalse(m._wait_selfie_continue(FakePage([]), timeout=0.01))
        self.assertEqual(clicked, [])


if __name__ == "__main__":
    unittest.main()
