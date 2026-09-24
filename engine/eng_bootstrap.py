"""engine.eng_bootstrap — offline stub, browser path, core loader, license removal.

Verbatim from ``engine/run.py`` (no logic change). Zero local-repo dependencies.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import types

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import HERE, CORE_PYC, _FREE_EXPIRY  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import HERE, CORE_PYC, _FREE_EXPIRY  # noqa: E402

def _install_offline_supabase_stub() -> None:
    """Shield the app from the vendor's Supabase licensing backend."""
    if "supabase" in sys.modules:
        return

    stub = types.ModuleType("supabase")

    class _OfflineTable:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def update(self, *a, **k):
            return self

        def execute(self):
            class _Resp:
                data = []

            return _Resp()

    class _OfflineClient:
        def table(self, *a, **k):
            return _OfflineTable()

    def create_client(*args, **kwargs):  # noqa: ARG001
        return _OfflineClient()

    class Client:  # minimal placeholder for `from supabase import Client`
        pass

    stub.create_client = create_client
    stub.Client = Client
    sys.modules["supabase"] = stub


def _find_browsers_dir():
    """Return a directory that actually contains Playwright browsers, or None."""
    candidates = [
        os.path.join(HERE, "ms-playwright"),
        os.path.join(HERE, "..", "_internal", "ms-playwright"),
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
        os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright"),
    ]
    for path in candidates:
        if not path or not os.path.isdir(path):
            continue
        try:
            entries = os.listdir(path)
        except OSError:
            continue
        if any(e.startswith(("chromium", "firefox", "webkit")) for e in entries):
            return path
    return None


def _point_playwright_at_browsers() -> None:
    """The core hard-forces PLAYWRIGHT_BROWSERS_PATH to <app>/ms-playwright.

    Point it at wherever the browsers were actually installed instead.
    """
    found = _find_browsers_dir()
    if found:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = found

def _load_core():
    if not os.path.exists(CORE_PYC):
        sys.exit(
            f"error: application core not found: {CORE_PYC}\n"
            "Re-extract it from the original 'instaauto.zip' (PyInstaller "
            "archive) and place it next to this launcher."
        )
    loader = importlib.machinery.SourcelessFileLoader("instaauto_core", CORE_PYC)
    spec = importlib.util.spec_from_loader("instaauto_core", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["instaauto_core"] = module
    loader.exec_module(module)
    return module

def _remove_license(core) -> None:
    from PyQt5.QtWidgets import QGroupBox, QMessageBox

    ui = core.AppUI

    def _unlock(self):
        self.is_activated = True
        self.license_expiration_time = _FREE_EXPIRY
        try:
            self.update_expiry_status()
        except Exception:
            pass

    original_init = ui.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _unlock(self)
        # Hide the activation panel entirely.
        try:
            for box in self.findChildren(QGroupBox):
                if "License" in box.title() or "license" in box.title():
                    box.setVisible(False)
        except Exception:
            pass

    def patched_auto_check_saved_key(self):
        _unlock(self)

    def patched_verify_key_supabase(self, key=None, auto_mode=False, retry=3):
        _unlock(self)
        return True

    def patched_activate_license_key(self):
        _unlock(self)
        try:
            QMessageBox.information(
                self,
                "Free Edition",
                "This is the free Linux edition — no activation key is required.",
            )
        except Exception:
            pass

    ui.__init__ = patched_init
    ui.auto_check_saved_key = patched_auto_check_saved_key
    ui.verify_key_supabase = patched_verify_key_supabase
    ui.activate_license_key = patched_activate_license_key
