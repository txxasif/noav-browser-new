"""engine.eng_patches — Qt patches (terms/license/target) + entrypoint.

Verbatim from ``engine/run.py`` (no logic change). Cross-module calls are
function-local lazy imports to avoid cycles (same pattern as nitro/).
"""
from __future__ import annotations

import os
import sys

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import _JS_TICK_CHECKBOXES, _JS_SCROLL_DOWN, _JS_DUMP_BUTTONS, _JS_CLICK_TERMS  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _JS_TICK_CHECKBOXES, _JS_SCROLL_DOWN, _JS_DUMP_BUTTONS, _JS_CLICK_TERMS  # noqa: E402

def _patch_accept_terms(core) -> None:
    worker = core.AutomationWorker

    def robust_accept_terms(self):
        page = getattr(self, "page", None)
        if page is None:
            return False
        for attempt in range(1, 7):
            try:
                page.wait_for_timeout(800)
                page.evaluate(_JS_TICK_CHECKBOXES)
                page.evaluate(_JS_SCROLL_DOWN)
                page.wait_for_timeout(300)

                # Show what is actually on the page, to stderr AND the log.
                try:
                    for entry in page.evaluate(_JS_DUMP_BUTTONS)[:20]:
                        print("[terms] button:", entry, flush=True)
                        self.log_signal.emit("[terms] " + repr(entry))
                except Exception:
                    pass

                result = page.evaluate(_JS_CLICK_TERMS)
                print(f"[terms] attempt {attempt}: click -> {result}", flush=True)
                self.log_signal.emit(
                    f'[terms] attempt {attempt}: clicked={result.get("clicked")} '
                    f'({result.get("text", "")})'
                )

                if result.get("clicked"):
                    for _ in range(8):
                        page.wait_for_timeout(700)
                        url = (page.url or "").lower()
                        if any(k in url for k in
                               ("registered", "one_tap", "accounts/onetap", "variant")):
                            self.log_signal.emit(
                                '<font color="#00FF00"><b>[✔] Page transitioned after "I agree".</b></font>'
                            )
                            return True
                        try:
                            save = page.locator(
                                'span:has-text("Save"), div[role="button"]:has-text("Save")'
                            ).first
                            if save.is_visible():
                                self.log_signal.emit(
                                    '<font color="#00FF00"><b>[✔] Page transitioned after "I agree".</b></font>'
                                )
                                return True
                        except Exception:
                            pass
            except Exception as exc:  # noqa: BLE001
                self.log_signal.emit(
                    f'<font color="#FF4D4D"><b>[❌] Terms error: {exc}</b></font>'
                )
        self.log_signal.emit(
            '<font color="#FF4D4D"><b>[❌] Failed to accept terms after multiple attempts.</b></font>'
        )
        return False

    worker._accept_terms = robust_accept_terms

def _patch_meta_flow(core) -> None:
    worker = core.AutomationWorker
    original_run = worker.run

    def dispatch_run(self, *args, **kwargs):
        if "meta" in (getattr(self, "target", "") or "").lower():
            try:
                from .eng_mix_ig import run_meta_instagram  # package mode
            except ImportError:
                from eng_mix_ig import run_meta_instagram  # noqa: E402
            return run_meta_instagram(self)
        return original_run(self, *args, **kwargs)

    worker.run = dispatch_run


def _patch_target_option(core) -> None:
    from PyQt5.QtWidgets import QComboBox

    ui = core.AppUI
    original_add = ui.add_new_slot

    def patched_add(self, *args, **kwargs):
        # Qt's `clicked` signal passes a `checked` bool; add_new_slot takes none.
        result = original_add(self)
        try:
            for combo in self.findChildren(QComboBox):
                items = [combo.itemText(i) for i in range(combo.count())]
                if "2nd-no.com" in items and "Meta → Instagram" not in items:
                    combo.addItem("Meta → Instagram")
        except Exception:
            pass
        return result

    ui.add_new_slot = patched_add


def main() -> int:
    try:
        from .eng_bootstrap import (  # package mode
            _install_offline_supabase_stub,
            _load_core,
            _point_playwright_at_browsers,
            _remove_license,
        )
    except ImportError:  # top-level `import run` mode
        from eng_bootstrap import (  # noqa: E402
            _install_offline_supabase_stub,
            _load_core,
            _point_playwright_at_browsers,
            _remove_license,
        )
    _install_offline_supabase_stub()
    core = _load_core()
    _point_playwright_at_browsers()
    _remove_license(core)
    _patch_accept_terms(core)
    _patch_meta_flow(core)
    _patch_target_option(core)

    from PyQt5.QtWidgets import QApplication

    core.ensure_user_agent_file()

    app = QApplication(sys.argv)
    window = core.AppUI()
    window.show()
    return app.exec_()

