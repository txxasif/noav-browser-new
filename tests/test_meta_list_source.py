"""Meta-list source: store claim/restore semantics + pool_prepare helpers.

Runs against a throw-away SQLite file; ``store.sync_files`` is stubbed so the
real data/accounts.json|csv|txt are never touched.
"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import store  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.DB_PATH
        self._old_json = db.ACCOUNTS_JSON
        db.DB_PATH = os.path.join(self._tmp.name, "store.db")
        # Never migrate the operator's real accounts.json into the test DB.
        db.ACCOUNTS_JSON = os.path.join(self._tmp.name, "none.json")
        db.close_local_connection()
        db.init_db()
        self._old_sync = store.sync_files
        store.sync_files = lambda *a, **k: None

    def tearDown(self):
        store.sync_files = self._old_sync
        db.close_local_connection()
        db.DB_PATH = self._old_path
        db.ACCOUNTS_JSON = self._old_json
        self._tmp.cleanup()

    def add_meta(self, rec_id, created, **over):
        rec = {
            "id": rec_id, "status": "MetaCreated", "platform": "Meta",
            "email": f"{rec_id}@x.test", "meta_password": "pw", "password": "pw",
            "created_at": created, "cookies": "",
        }
        rec.update(over)
        store.add(rec)

    def status(self, rec_id):
        row = db.get_connection().execute(
            "SELECT status FROM accounts WHERE id = ?", (rec_id,)).fetchone()
        return row[0] if row else None


class MetaListStoreTests(_Base):
    def test_count_and_pop_agree_and_are_fifo(self):
        self.add_meta("m_new", "2026-10-08 12:00:00")
        self.add_meta("m_old", "2026-10-08 08:00:00")
        self.assertEqual(store.count_meta_list_accounts(), 2)
        a = store.pop_meta_list_account()
        self.assertEqual(a["id"], "m_old")                  # oldest first
        self.assertEqual(self.status("m_old"), "Submitting_MetaCookie")
        self.assertEqual(store.count_meta_list_accounts(), 1)

    def test_ineligible_rows_are_ignored(self):
        self.add_meta("no_email", "2026-10-08 08:00:00", email="")
        self.add_meta("no_pw", "2026-10-08 08:00:00", meta_password="", password="")
        self.add_meta("ig_acct", "2026-10-08 08:00:00",
                      platform="Meta+Instagram", status="Created", cookies="sessionid=x" * 20)
        self.add_meta("done", "2026-10-08 08:00:00", status="Failed")
        self.assertEqual(store.count_meta_list_accounts(), 0)
        self.assertIsNone(store.pop_meta_list_account())

    def test_ig_pool_never_sees_meta_rows(self):
        self.add_meta("m1", "2026-10-08 08:00:00")
        self.assertEqual(store.count_ig_creator_accounts(), 0)
        self.assertIsNone(store.pop_ig_creator_account())

    def test_restore_returns_meta_row_to_the_meta_list(self):
        self.add_meta("m1", "2026-10-08 08:00:00")
        store.pop_meta_list_account()
        store.restore_ig_creator_account("m1", rotate=True)
        self.assertEqual(self.status("m1"), "MetaCreated")
        store.pop_meta_list_account()
        store.restore_ig_creator_account("m1")
        self.assertEqual(self.status("m1"), "MetaCreated")

    def test_stale_claim_is_reclaimed_to_meta_created(self):
        self.add_meta("m1", "2026-10-08 08:00:00")
        store.pop_meta_list_account()
        # Age the claim past CLAIM_TIMEOUT.
        db.get_connection().execute(
            "UPDATE accounts SET claimed_at = ? WHERE id = 'm1'", (time.time() - 99999,))
        self.assertEqual(store.recover_stale_submitting(), 1)
        self.assertEqual(self.status("m1"), "MetaCreated")

    def test_challenged_is_set_aside_then_failed_after_max_attempts(self):
        self.add_meta("m1", "2026-10-08 08:00:00")
        store.pop_meta_list_account()
        store.mark_meta_list_challenged("m1")
        self.assertEqual(self.status("m1"), "MetaCreated")
        self.assertEqual(store.count_meta_list_accounts(), 0)      # cooling down
        for _ in range(store.MAX_SUBMIT_ATTEMPTS):
            store.mark_meta_list_challenged("m1")
        self.assertEqual(self.status("m1"), "Failed")

    def test_ig_pool_restore_still_returns_created(self):
        store.add({"id": "ig1", "status": "Created", "platform": "Meta+Instagram",
                   "cookies": "sessionid=abc; " * 12, "created_at": "2026-10-08 08:00:00"})
        a = store.pop_ig_creator_account()
        self.assertEqual(a["id"], "ig1")
        store.restore_ig_creator_account("ig1", rotate=True)
        self.assertEqual(self.status("ig1"), "Created")


class _FakeCtx:
    def __init__(self, cookies):
        self._c = cookies

    def cookies(self):
        return self._c


class _FakePage:
    url = "https://www.instagram.com/"

    def __init__(self, result):
        self.result = result
        self.args = None

    def evaluate(self, js, arg=None):
        self.args = arg
        return self.result


class PoolPrepareTests(unittest.TestCase):
    def test_rename_in_page_ok_and_csrf_forwarded(self):
        import pool_prepare as pp
        page = _FakePage({"status": 200, "body": json.dumps({"status": "ok"})})
        ctx = _FakeCtx([{"name": "csrftoken", "value": "TOK", "domain": ".instagram.com"}])
        ok, msg = pp.rename_in_page(page, ctx, "newname")
        self.assertTrue(ok, msg)
        self.assertEqual(page.args, ["newname", "TOK"])

    def test_rename_in_page_html_challenge_is_not_success(self):
        import pool_prepare as pp
        page = _FakePage({"status": 200, "body": "<!DOCTYPE html><html>"})
        ok, msg = pp.rename_in_page(page, _FakeCtx([]), "x")
        self.assertFalse(ok)
        self.assertIn("HTML", msg)

    def test_rename_in_page_checkpoint_json_is_failure(self):
        import pool_prepare as pp
        page = _FakePage({"status": 400, "body": json.dumps(
            {"message": "checkpoint_required", "checkpoint_url": "/challenge/"})})
        ok, msg = pp.rename_in_page(page, _FakeCtx([]), "x")
        self.assertFalse(ok)
        self.assertIn("checkpoint_required", msg)

    def test_follow_explore_zero_need_is_noop(self):
        import pool_prepare as pp
        self.assertEqual(pp.follow_explore(object(), object(), 0, lambda m: None), 0)


class MetaSessionLifecycleTests(_Base):
    def test_close_without_finish_restores_the_claim(self):
        import pool_prepare as pp
        self.add_meta("m1", "2026-10-08 08:00:00")
        sess = pp.MetaListSession(1, True, None, lambda m: None)
        sess.acc = store.pop_meta_list_account()
        self.assertEqual(self.status("m1"), "Submitting_MetaCookie")
        sess.close()
        self.assertEqual(self.status("m1"), "MetaCreated")
        sess.close()                                            # idempotent
        self.assertEqual(self.status("m1"), "MetaCreated")

    def test_permanent_failure_marks_failed_transient_sets_aside(self):
        import pool_prepare as pp
        self.add_meta("perm", "2026-10-08 08:00:00")
        self.add_meta("soft", "2026-10-08 09:00:00")
        s1 = pp.MetaListSession(1, True, None, lambda m: None)
        s1.acc = store.pop_meta_list_account()
        s1._fail(RuntimeError("Instagram: incorrect password (login rejected)"))
        self.assertEqual(self.status("perm"), "Failed")
        s2 = pp.MetaListSession(2, True, None, lambda m: None)
        s2.acc = store.pop_meta_list_account()
        s2._fail(RuntimeError("Instagram human checkpoint at login"))
        self.assertEqual(self.status("soft"), "MetaCreated")
        self.assertEqual(store.count_meta_list_accounts(), 0)   # cooling down


class _FakeWorker:
    def __init__(self, slot_id=1, is_headless=True):
        self.cleaned = False

    def _cleanup_browser_resources(self):
        self.cleaned = True


class _FakeRunnerPage:
    url = "https://www.instagram.com/"

    def goto(self, *a, **k):
        pass

    def wait_for_timeout(self, ms):
        pass


class _FakeRunner:
    """Stands in for MetaInstaRunner: records calls, scripted outcomes."""
    login_exc = None
    join_exc = None
    human = False
    cookies = [{"name": "sessionid", "value": "S" * 40, "domain": ".instagram.com"},
               {"name": "csrftoken", "value": "C" * 40, "domain": ".instagram.com"},
               {"name": "mid", "value": "M" * 40, "domain": ".instagram.com"}]
    last = None

    def __init__(self, worker, **kw):
        type(self).last = self
        self.calls = []
        self.w = type("W", (), {"context": type("C", (), {"cookies": staticmethod(lambda: _FakeRunner.cookies)})()})()
        self.worker = worker
        self.ig_username = None

    def _install_screenshot_hooks(self): pass
    def _launch(self): self.calls.append("launch")
    def _ig_tab(self): return _FakeRunnerPage()
    def _has_human_check(self, p): return type(self).human
    def _touch_scroll(self, p, dy=0): pass
    def finish(self): self.calls.append("finish")

    def ig_login(self):
        self.calls.append("login")
        if type(self).login_exc:
            raise type(self).login_exc
        return "needs_join"

    def ig_click_meta_card(self): self.calls.append("meta_card")

    def ig_complete_join(self):
        self.calls.append("join")
        if type(self).join_exc:
            raise type(self).join_exc
        self.ig_username = self.tg_creds["login"]

    def ig_dismiss_onboarding(self, follow=True): self.calls.append("dismiss")
    def ig_follow_suggested(self, max_follows=2, humanize=False): return max_follows


class MetaSessionFlowTests(_Base):
    def setUp(self):
        super().setUp()
        import runner as _runner
        import pool_prepare as pp
        self._runner_mod, self._pp = _runner, pp
        self._old_cls = _runner.MetaInstaRunner
        self._old_follow = pp.follow_explore
        _runner.MetaInstaRunner = _FakeRunner
        pp.follow_explore = lambda r, p, need, log, humanize=True: need
        _FakeRunner.login_exc = _FakeRunner.join_exc = None
        _FakeRunner.human = False
        os.environ["INSTA_META_DWELL_SEC"] = "0"
        self.add_meta("m1", "2026-10-08 08:00:00", device_model="Pixel 6", device_ua="UA/1")

    def tearDown(self):
        self._runner_mod.MetaInstaRunner = self._old_cls
        self._pp.follow_explore = self._old_follow
        os.environ.pop("INSTA_META_DWELL_SEC", None)
        super().tearDown()

    def _session(self):
        return self._pp.MetaListSession(1, True, _FakeWorker, lambda m: None)

    def test_happy_path_converts_record_to_pool_account(self):
        sess = self._session()
        acc = sess.open()
        self.assertEqual(acc["id"], "m1")
        r = _FakeRunner.last
        self.assertEqual((r.device_model, r.device_ua), ("Pixel 6", "UA/1"))   # same phone as creation
        out = sess.finish("bot_user", {"login": "Bot_User!", "password": "pw2", "first_name": "Ann"}, 5)
        self.assertEqual(r.calls[:5], ["launch", "login", "meta_card", "join", "dismiss"])
        self.assertEqual(r.tg_creds["login"], "bot_user")                       # cleaned login wins
        self.assertEqual(out["platform"], "Meta+Instagram")
        self.assertEqual(out["followed"], 5)
        self.assertIn("sessionid=", out["cookies"])
        row = db.get_connection().execute(
            "SELECT platform, status, username FROM accounts WHERE id='m1'").fetchone()
        self.assertEqual(tuple(row), ("Meta+Instagram", "Submitting_PayGo", "bot_user"))
        sess.close()                                    # ownership passed on: must NOT restore
        self.assertEqual(self.status("m1"), "Submitting_PayGo")
        # A failed submit downstream restores it as a regular IG-pool account.
        store.restore_ig_creator_account("m1", rotate=True)
        self.assertEqual(self.status("m1"), "Created")
        self.assertEqual(store.count_meta_list_accounts(), 0)

    def test_login_challenge_sets_account_aside_and_raises(self):
        _FakeRunner.login_exc = RuntimeError("Instagram login entry blocked (no login form)")
        sess = self._session()
        with self.assertRaises(RuntimeError):
            sess.open()
        self.assertEqual(self.status("m1"), "MetaCreated")
        self.assertEqual(store.count_meta_list_accounts(), 0)       # cooling down
        sess.close()

    def test_wrong_password_is_permanent(self):
        _FakeRunner.login_exc = RuntimeError("Instagram: incorrect password (login rejected)")
        sess = self._session()
        with self.assertRaises(RuntimeError):
            sess.open()
        self.assertEqual(self.status("m1"), "Failed")

    def test_phone_wall_during_join_marks_failed_and_closes_browser(self):
        sess = self._session()
        sess.open()
        _FakeRunner.join_exc = RuntimeError("Instagram: Mobile number required (What's your mobile number)")
        with self.assertRaises(RuntimeError):
            sess.finish("bot_user", {"password": "x"}, 5)
        self.assertEqual(self.status("m1"), "Failed")
        self.assertTrue(sess.worker is None)                        # browser torn down

    def test_human_checkpoint_after_login_is_transient(self):
        _FakeRunner.human = True
        sess = self._session()
        with self.assertRaises(RuntimeError):
            sess.open()
        self.assertEqual(self.status("m1"), "MetaCreated")

    def test_empty_list_returns_none(self):
        store.update_account("m1", {"status": "Failed"})
        self.assertIsNone(self._session().open())


class _BaseFollow:
    """Stands in for the original feed-rail implementation (join.py)."""
    def __init__(self):
        self.rail_calls = []
        self._ig_follow_done = False
        self.logs = []
        self.page = _FakeRunnerPage()

    def log(self, m): self.logs.append(m)
    def _ig_tab(self): return self.page
    def ig_follow_suggested(self, max_follows=2, humanize=False):
        self.rail_calls.append(max_follows)
        self._ig_follow_done = True
        return max_follows


class ExploreFollowMixinTests(unittest.TestCase):
    def setUp(self):
        import pool_prepare as pp
        from core.follow import ExploreFollowMixin

        class R(ExploreFollowMixin, _BaseFollow):
            pass
        self.R, self.pp = R, pp
        self._old = pp.follow_explore
        for k in ("INSTA_FOLLOW_EXPLORE", "INSTA_FOLLOW_AFTER_LOGIN", "INSTA_FOLLOW_COUNT", "INSTA_FOLLOW_MODE"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.pp.follow_explore = self._old
        for k in ("INSTA_FOLLOW_EXPLORE", "INSTA_FOLLOW_AFTER_LOGIN", "INSTA_FOLLOW_COUNT", "INSTA_FOLLOW_MODE"):
            os.environ.pop(k, None)

    def test_full_explore_success_skips_the_rail(self):
        self.pp.follow_explore = lambda r, p, need, log, humanize=True: need
        r = self.R()
        self.assertEqual(r.ig_follow_suggested(max_follows=5), 5)
        self.assertEqual(r.rail_calls, [])
        self.assertEqual(r.ig_followed_count, 5)
        self.assertTrue(r._ig_follow_done)

    def test_shortfall_goes_to_rail_for_the_remainder(self):
        self.pp.follow_explore = lambda r, p, need, log, humanize=True: 2
        r = self.R()
        self.assertEqual(r.ig_follow_suggested(max_follows=5), 5)
        self.assertEqual(r.rail_calls, [3])
        self.assertEqual(r.ig_followed_count, 5)

    def test_zero_from_explore_runs_full_rail(self):
        self.pp.follow_explore = lambda r, p, need, log, humanize=True: 0
        r = self.R()
        self.assertEqual(r.ig_follow_suggested(max_follows=4), 4)
        self.assertEqual(r.rail_calls, [4])

    def test_explore_exception_falls_back_not_raises(self):
        def boom(*a, **k):
            raise RuntimeError("selector drift")
        self.pp.follow_explore = boom
        r = self.R()
        self.assertEqual(r.ig_follow_suggested(max_follows=3), 3)
        self.assertEqual(r.rail_calls, [3])

    def test_kill_switch_restores_original_behaviour(self):
        os.environ["INSTA_FOLLOW_EXPLORE"] = "0"
        self.pp.follow_explore = lambda *a, **k: self.fail("explore must not run")
        r = self.R()
        self.assertEqual(r.ig_follow_suggested(max_follows=2), 2)
        self.assertEqual(r.rail_calls, [2])

    def test_zero_count_and_duplicate_pass_do_nothing_new(self):
        self.pp.follow_explore = lambda *a, **k: self.fail("explore must not run")
        r = self.R()
        os.environ["INSTA_FOLLOW_COUNT"] = "0"           # the dashboard "Follow off" switch
        self.assertEqual(r.ig_follow_suggested(max_follows=5), 0)
        self.assertEqual(r.rail_calls, [])
        os.environ.pop("INSTA_FOLLOW_COUNT")
        r._ig_follow_done = True                 # already ran this cycle
        r.ig_follow_suggested(max_follows=2)
        self.assertEqual(r.rail_calls, [2])      # delegated to the original guard


    def test_failed_to_load_dead_end_propagates_without_rail_fallback(self):
        from pool_prepare import IGDeadEnd

        def blocked(*a, **k):
            raise IGDeadEnd("follow 'Failed to Load' toast after 2 follow(s)")
        self.pp.follow_explore = blocked
        r = self.R()
        with self.assertRaises(IGDeadEnd):
            r.ig_follow_suggested(max_follows=5)
        self.assertEqual(r.rail_calls, [])        # do not keep tapping a blocked account

    def test_multi_insta_mode_routes_to_engine(self):
        os.environ["INSTA_FOLLOW_MODE"] = "multi"
        r = self.R()
        called = []
        r._ig_follow_via_multi_insta = lambda need: (called.append(need) or need)
        self.assertEqual(r.ig_follow_suggested(max_follows=5), 5)
        self.assertEqual(called, [5])
        self.assertEqual(r.rail_calls, [])


class _ToastPage:
    """Page whose body shows IG's 'Failed to Load.' toast after the 3rd tap."""
    url = "https://www.instagram.com/explore/people/"

    def __init__(self):
        self.taps = 0
        self.skip = set()

    def goto(self, *a, **k): pass
    def wait_for_timeout(self, ms): pass

    def evaluate(self, js, arg=None):
        if "includes('failed to load')" in js:
            return self.taps >= 3
        if "data-mc-follow" in js and "labels" in js:
            return True
        if "try again later" in js:
            return False
        if "__gone__" in js:
            return "following"
        return None

    def locator(self, sel):
        page = self

        class L:
            first = None
            def scroll_into_view_if_needed(self, **k): pass
            def click(self, **k): page.taps += 1
        l = L(); l.first = l
        return l


class FollowExploreToastTests(unittest.TestCase):
    def test_toast_after_third_tap_raises_dead_end_and_records_progress(self):
        import pool_prepare as pp

        class R:
            ig_followed_count = 0
            def _dismiss_ig_sheets(self, p): pass
            def _touch_scroll(self, p, dy=0): pass
        r = R()
        with self.assertRaises(pp.IGDeadEnd):
            pp.follow_explore(r, _ToastPage(), 5, lambda m: None, humanize=False)
        self.assertEqual(r.ig_followed_count, 2)


if __name__ == "__main__":
    unittest.main()
