"""ig_check --workers: lookups run in parallel, results still arrive complete and (batch mode) in order."""
import io
import json
import os
import sys
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ig_check  # noqa: E402

NAMES = [f"user{i}" for i in range(8)]


def slow_check(name):
    time.sleep(0.2)
    return {"username": name, "status": "not_found" if name.endswith("3") else "active"}


def run(argv):
    buf = io.StringIO()
    t0 = time.time()
    with mock.patch.object(ig_check, "check_instagram_account", slow_check), redirect_stdout(buf):
        ig_check.main(argv)
    return buf.getvalue().strip().splitlines(), time.time() - t0


class ParallelCheckTests(unittest.TestCase):
    def test_stream_with_workers_is_faster_and_complete(self):
        lines, took = run(["--usernames-json", json.dumps(NAMES), "--delay-ms", "0", "--ndjson", "--workers", "4"])
        msgs = [json.loads(l) for l in lines]
        results = [m for m in msgs if m["type"] == "result"]
        self.assertEqual(sorted(r["result"]["username"] for r in results), sorted(NAMES))
        self.assertEqual([r["progress"]["done"] for r in results], list(range(1, 9)))   # counter never skips
        self.assertEqual(msgs[0], {"type": "total", "count": 8})
        self.assertEqual(msgs[-1], {"type": "done"})
        self.assertLess(took, 0.2 * 8 * 0.7)            # serial would take 1.6s

    def test_batch_mode_keeps_order(self):
        lines, _ = run(["--usernames-json", json.dumps(NAMES), "--delay-ms", "0", "--workers", "5"])
        got = json.loads(lines[-1])["results"]
        self.assertEqual([r["username"] for r in got], NAMES)
        self.assertEqual([r["status"] for r in got].count("not_found"), 1)

    def test_default_is_still_one_at_a_time(self):
        _, took = run(["--usernames-json", json.dumps(NAMES[:4]), "--delay-ms", "0", "--ndjson"])
        self.assertGreaterEqual(took, 0.2 * 4 * 0.9)

    def test_workers_are_capped(self):
        lines, _ = run(["--usernames-json", json.dumps(NAMES), "--delay-ms", "0", "--ndjson", "--workers", "99"])
        self.assertEqual(sum(1 for l in lines if '"result"' in l), 8)


if __name__ == "__main__":
    unittest.main()
