"""Auto-Mine priority rules (simulated with a fake slot): Taskly takes over only at the hourly refill,
the previous bot resumes when Taskly is exhausted, nothing is probed or paused mid-hour."""
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which("node"), "node not installed")
class OrchestratorLogic(unittest.TestCase):
    def test_priority_rules(self):
        out = subprocess.run(["node", os.path.join(ROOT, "tests", "cookie_orch_sim.js")], cwd=ROOT,
                             capture_output=True, text=True, timeout=60).stdout
        self.assertIn("PASS", out)
        self.assertNotIn("FAIL", out, out)
        self.assertEqual(out.count("PASS"), 9, out)


if __name__ == "__main__":
    unittest.main()
