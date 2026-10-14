"""A worker that starts or exits must not free the leases of another LIVE worker."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tg_accounts  # noqa: E402


class FakeMgr(tg_accounts.TgAccountManager if hasattr(tg_accounts, "TgAccountManager") else object):
    pass


class ResetTests(unittest.TestCase):
    def _mgr(self, accounts):
        cls = type(tg_accounts.tg_manager)
        m = object.__new__(cls)
        import threading
        m._cv = threading.Condition()
        m.accounts = accounts
        m._reload = lambda: None
        m.save = lambda: None
        return m

    def test_live_foreign_lease_survives_a_skip_reset(self):
        other = os.getpid() + 7                      # "another worker"
        accs = [
            {"id": "tg_1", "status": "busy", "lease_pid": other, "profile_dir": "x"},
            {"id": "tg_2", "status": "busy", "lease_pid": os.getpid(), "profile_dir": "x"},
            {"id": "tg_3", "status": "busy", "profile_dir": "x"},                      # owner unknown (legacy)
            {"id": "tg_4", "status": "busy", "lease_pid": 999999, "profile_dir": "x"},  # dead owner
        ]
        m = self._mgr(accs)
        with mock.patch.object(tg_accounts, "_pid_alive", lambda pid: int(pid) == other), \
                mock.patch.object(tg_accounts, "session_ok", lambda a: True):
            m.reset_all(skip_live_owners=True)
        st = {a["id"]: a["status"] for a in accs}
        self.assertEqual(st, {"tg_1": "busy", "tg_2": "idle", "tg_3": "idle", "tg_4": "idle"})

    def test_plain_reset_still_frees_everything(self):
        accs = [{"id": "tg_1", "status": "busy", "lease_pid": os.getpid() + 7, "profile_dir": "x"}]
        m = self._mgr(accs)
        with mock.patch.object(tg_accounts, "session_ok", lambda a: True):
            m.reset_all()
        self.assertEqual(accs[0]["status"], "idle")


if __name__ == "__main__":
    unittest.main()
