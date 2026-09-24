import os
import unittest

from engine.eng_antidetect import _build_antidetect_script, device_identity, pc_mobile_identity
from engine.eng_mix_launch import _pc_mode_enabled
from engine.resource_runtime import active_profiles, register_profile, unregister_profile


class MetaProfileContractTests(unittest.TestCase):
    def test_pc_mobile_identity_is_stable_and_coherent(self):
        first = pc_mobile_identity("profile-a")
        second = pc_mobile_identity("profile-a")
        self.assertEqual(first, second)
        self.assertIn(first["model"], ("SM-S918B", "Pixel 6"))
        self.assertIn(first["android_version"], ("12", "13"))
        self.assertEqual(first["screen"]["width"] in (411, 412), True)
        self.assertEqual(first["screen"]["height"] in (914, 915), True)
        self.assertEqual(first["gpu_renderer"], "Intel Iris OpenGL Engine")
        self.assertEqual(first["timezone"], "America/New_York")

    def test_init_script_uses_the_selected_profile(self):
        identity = pc_mobile_identity("profile-b", model="SM-S918B")
        script = _build_antidetect_script(
            "Mozilla/5.0 (Linux; Android 13; SM-S918B) Chrome/153.0.1.2 Mobile",
            "153.0.1.2",
            is_mobile=True,
            identity=identity,
        )
        self.assertIn("SM-S918B", script)
        self.assertIn("Intel Iris OpenGL Engine", script)
        self.assertIn("America/New_York", script)
        self.assertIn('"width": 412', script)

    def test_stock_profile_fallback_remains_available(self):
        old = os.environ.get("PC_MODE")
        try:
            os.environ["PC_MODE"] = "0"
            self.assertFalse(_pc_mode_enabled())
            os.environ["PC_MODE"] = "1"
            self.assertTrue(_pc_mode_enabled())
        finally:
            if old is None:
                os.environ.pop("PC_MODE", None)
            else:
                os.environ["PC_MODE"] = old

    def test_active_profile_registry_is_normalized(self):
        path = os.path.abspath("profiles/test-profile")
        register_profile(path)
        self.assertIn(os.path.normcase(path), active_profiles())
        unregister_profile(path)
        self.assertNotIn(os.path.normcase(path), active_profiles())


if __name__ == "__main__":
    unittest.main()
