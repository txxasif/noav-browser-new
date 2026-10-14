import json
import multiprocessing as mp
import os
import tempfile
import unittest

import tg_accounts


def _worker(path, barrier, out):
    tg_accounts.TG_ACCOUNTS_JSON = path
    tg_accounts.session_ok = lambda _a: True
    tg_accounts.is_frozen = lambda: False
    mgr = tg_accounts.TGAccountManager()
    barrier.wait()
    got = mgr.acquire(timeout=0.2)
    out.put(got["id"] if got else None)


class LeaseRaceTests(unittest.TestCase):
    def test_one_account_is_leased_to_exactly_one_process(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tg_accounts.json")
            rec = {"id": "tg_1", "label": "TG #1", "status": "idle", "enabled": True,
                   "mode": "mtproto", "profile_dir": d, "last_used": None}
            with open(path, "w", encoding="utf-8") as f:
                json.dump([rec], f)

            n = 6
            ctx = mp.get_context("fork")
            barrier = ctx.Barrier(n)
            out = ctx.Queue()
            procs = [ctx.Process(target=_worker, args=(path, barrier, out)) for _ in range(n)]
            for p in procs:
                p.start()
            for p in procs:
                p.join(30)
            results = [out.get(timeout=5) for _ in range(n)]
            self.assertEqual(results.count("tg_1"), 1, results)
            self.assertEqual(results.count(None), n - 1, results)

    def test_write_is_atomic_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tg_accounts.json")
            old = tg_accounts.TG_ACCOUNTS_JSON
            tg_accounts.TG_ACCOUNTS_JSON = path
            self.addCleanup(setattr, tg_accounts, "TG_ACCOUNTS_JSON", old)
            mgr = tg_accounts.TGAccountManager.__new__(tg_accounts.TGAccountManager)
            mgr._write([{"id": "tg_9"}])
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), [{"id": "tg_9"}])
            self.assertFalse([n for n in os.listdir(d) if n.endswith(".tmp")])


if __name__ == "__main__":
    unittest.main()
