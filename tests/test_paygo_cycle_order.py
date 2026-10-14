"""Smoke test of run_paygo_pool_2fa_cycle_once with fakes: the order of the new pre-phase
and the cleanup when the bot task cannot start."""
import os
import sys
import types
import unittest
from unittest import mock

import run_paygo_pool_2fa_cycle as rm

ORDER = []
RESTORED = []

ACCOUNT = {
    "id": "acc1", "cookies": "sessionid=abc; ds_user_id=1", "password": "pw-1",
    "device_model": "Pixel 6", "device_ua": "UA-pixel",
    "extra": {"mail_tokens": {"mailfish_email": "a@b.c", "mailfish_auth_key": "K"}},
}


class _Page:
    url = "https://www.instagram.com/"

    def goto(self, url, *_a, **_k):
        # the session check opens Accounts Center once and reads the page it lands on
        self.url = url
        return None

    def inner_text(self, *_a, **_k):
        return "Change password Current password New password Re-type new password"

    def reload(self, *_a, **_k):
        return None

    def evaluate(self, *_a, **_k):
        return None


class _Ctx:
    def clear_cookies(self):
        return None

    def add_cookies(self, _c):
        return None


class _Runner:
    def __init__(self, *_a, **_k):
        self.device_model = None
        self.device_ua = None
        self.w = types.SimpleNamespace(context=_Ctx())

    def _install_screenshot_hooks(self):
        return None

    def _launch(self):
        ORDER.append(f"launch(model={self.device_model})")

    def _ig_tab(self):
        return _Page()

    def _dismiss_ig_sheets(self, _p):
        return None

    def ig_ac_preauth(self, pw):
        ORDER.append(f"preauth(pw={pw})")
        return True

    def finish(self):
        return None


class _Bot:
    def clear_orphan_task(self):
        return None

    def choose_task(self, _task):
        ORDER.append("choose_task")
        return False                      # the task cannot start -> early failure

    last_task_verdict = "soldout"

    def cancel_task(self):
        return None

    def close(self, ok=True):
        return None

    def disconnect(self):
        return None

    def _sleep_flood(self, *_a, **_k):
        return 0


class _Worker:
    def _cleanup_browser_resources(self):
        return None


def _fake_store():
    st = types.ModuleType("store")
    st.recover_stale_submitting = lambda: None
    st.count_ig_creator_accounts = lambda need_mail=False: 3
    pool = [dict(ACCOUNT)]

    def pop(prefer_non_follow5=False, **kw):
        ORDER.append("pop")
        return pool.pop(0) if pool else None

    st.pop_ig_creator_account = pop
    st.restore_ig_creator_account = lambda aid, rotate=True: RESTORED.append(aid)
    return st


class CycleOrderTests(unittest.TestCase):
    def setUp(self):
        ORDER.clear()
        RESTORED.clear()

    def _run_cycle(self, preauth_env):
        tg = mock.Mock()
        tg.usable.return_value = True
        tg.acquire.return_value = {"id": "tg_9"}
        env = {"PAYGO_PREAUTH": preauth_env} if preauth_env is not None else {}
        with mock.patch.dict(os.environ, env), \
             mock.patch.dict(sys.modules, {"store": _fake_store()}), \
             mock.patch.object(rm, "tg_manager", tg), \
             mock.patch.object(rm, "_make_tg_bot", lambda *_a, **_k: _Bot()), \
             mock.patch.object(rm, "_boot_bot", lambda _b: (True, "")), \
             mock.patch.object(rm, "MetaInstaRunner", _Runner), \
             mock.patch.object(rm, "_browser_logged_in", lambda _p: True), \
             mock.patch.object(rm, "_cookies_for_playwright", lambda _c: []), \
             mock.patch.object(rm, "_mail_ids", lambda _t: set()), \
             mock.patch.object(rm, "emit_event", lambda *_a, **_k: None):
            ok, detail = rm.run_paygo_pool_2fa_cycle_once(
                slot_id=7, worker_factory=lambda **_k: _Worker())
        return tg, ok, detail

    def test_default_skips_preauth(self):
        # Live checks (2026-10-12): the email challenge only shows on submit, so pre-auth is opt-in.
        tg, ok, detail = self._run_cycle(None)
        self.assertFalse(ok)
        self.assertEqual(ORDER, ["pop", "launch(model=Pixel 6)", "choose_task"])
        self.assertEqual(RESTORED, ["acc1"])

    def test_prephase_order_and_account_returned_when_task_cannot_start(self):
        tg = mock.Mock()
        tg.usable.return_value = True
        tg.acquire.return_value = {"id": "tg_9"}
        with mock.patch.dict(os.environ, {"PAYGO_PREAUTH": "1"}), \
             mock.patch.dict(sys.modules, {"store": _fake_store()}), \
             mock.patch.object(rm, "tg_manager", tg), \
             mock.patch.object(rm, "_make_tg_bot", lambda *_a, **_k: _Bot()), \
             mock.patch.object(rm, "_boot_bot", lambda _b: (True, "")), \
             mock.patch.object(rm, "MetaInstaRunner", _Runner), \
             mock.patch.object(rm, "_browser_logged_in", lambda _p: True), \
             mock.patch.object(rm, "_cookies_for_playwright", lambda _c: []), \
             mock.patch.object(rm, "_mail_ids", lambda _t: set()), \
             mock.patch.object(rm, "emit_event", lambda *_a, **_k: None):
            ok, detail = rm.run_paygo_pool_2fa_cycle_once(
                slot_id=7, worker_factory=lambda **_k: _Worker())

        self.assertFalse(ok)
        self.assertIn("Could not select", detail)
        # account claimed first, phone pinned BEFORE launch, email challenge cleared
        # BEFORE the bot task is even chosen
        self.assertEqual(ORDER, ["pop", "launch(model=Pixel 6)", "preauth(pw=pw-1)", "choose_task"])
        # the task never started, so the pre-claimed account must go back to the pool
        self.assertEqual(RESTORED, ["acc1"])
        tg.release.assert_called()


if __name__ == "__main__":
    unittest.main()
