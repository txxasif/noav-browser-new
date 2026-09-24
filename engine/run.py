#!/usr/bin/env python3
"""run.py — thin re-export shim (engine refactor).

The implementation now lives in the :mod:`engine` package as verbatim slices
(no logic change). This module is kept so existing imports keep working::

    import run                      # via ENGINE_DIR on sys.path (ai_config)
    from ai_config import run
    import run as _eng              # warm_pool.py

Single class object: :class:`engine._MetaInstagramRunner` is re-exported, never
redefined. ``os.chdir(HERE)`` import-time side effect is preserved.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The app writes profiles/, cookies/, accounts.txt, ... relative to CWD.
# Keep them next to the app for predictability (verbatim from original).
os.chdir(HERE)
sys.path.insert(0, HERE)

try:  # package mode (AI_DIR on sys.path — the normal ai_config flow)
    from engine import (  # noqa: E402,F401
        _ANTIDETECT_TEMPLATE,
        _FREE_EXPIRY,
        _HUMAN_TEXTS,
        _IG_LOGIN_URL,
        _IG_SIGNUP_URL,
        _JS_CLICK_TERMS,
        _JS_DUMP_BUTTONS,
        _JS_SCROLL_DOWN,
        _JS_TICK_CHECKBOXES,
        _MAILTD_URL,
        _META_AI_URL,
        _META_AI_APEX,
        _META_AUTH_URL,
        _META_POST_URL,
        _MONTHS,
        _NOVA_FLAGS,
        _MetaInstagramRunner,
        _build_antidetect_script,
        _find_browsers_dir,
        _get_extension_id_from_manifest,
        _get_shared_whisper_model,
        _install_offline_supabase_stub,
        _load_core,
        _patch_accept_terms,
        _patch_meta_flow,
        _patch_target_option,
        _pin_extensions_in_profile,
        CORE_PYC,
        HERE as _HERE_PKG,
        main,
        run_meta_instagram,
    )
    from engine import _WHISPER_LOCK  # noqa: E402,F401
    HERE = _HERE_PKG
except ImportError:  # standalone `python engine/run.py` (no package context)
    from eng_constants import (  # noqa: E402,F401
        _ANTIDETECT_TEMPLATE,
        _FREE_EXPIRY,
        _HUMAN_TEXTS,
        _IG_LOGIN_URL,
        _IG_SIGNUP_URL,
        _JS_CLICK_TERMS,
        _JS_DUMP_BUTTONS,
        _JS_SCROLL_DOWN,
        _JS_TICK_CHECKBOXES,
        _MAILTD_URL,
        _META_AI_URL,
        _META_AI_APEX,
        _META_AUTH_URL,
        _META_POST_URL,
        _MONTHS,
        _NOVA_FLAGS,
        CORE_PYC,
        HERE as _HERE_TOP,
    )
    from eng_antidetect import (  # noqa: E402,F401
        _build_antidetect_script,
        _get_extension_id_from_manifest,
        _get_shared_whisper_model,
        _pin_extensions_in_profile,
    )
    from eng_antidetect import _WHISPER_LOCK  # noqa: E402,F401
    from eng_bootstrap import (  # noqa: E402,F401
        _find_browsers_dir,
        _install_offline_supabase_stub,
        _load_core,
        _point_playwright_at_browsers,
        _remove_license,
    )
    from eng_patches import (  # noqa: E402,F401
        _patch_accept_terms,
        _patch_meta_flow,
        _patch_target_option,
        main,
    )
    from eng_mix_ig import run_meta_instagram  # noqa: E402,F401
    # Compose the runner locally (same MRO as engine package).
    from eng_mix_audio import EngineAudioMixin  # noqa: E402
    from eng_mix_base import EngineBaseMixin  # noqa: E402
    from eng_mix_captcha import EngineCaptchaMixin  # noqa: E402
    from eng_mix_ig import EngineIgMixin  # noqa: E402
    from eng_mix_interact import EngineInteractMixin  # noqa: E402
    from eng_mix_launch import EngineLaunchMixin  # noqa: E402
    from eng_mix_mail import EngineMailMixin  # noqa: E402
    from eng_mix_meta import EngineMetaMixin  # noqa: E402
    from eng_mix_signup import EngineSignupMixin  # noqa: E402

    HERE = _HERE_TOP

    class _MetaInstagramRunner(  # noqa: F811 — standalone fallback only
        EngineIgMixin,
        EngineSignupMixin,
        EngineMetaMixin,
        EngineMailMixin,
        EngineAudioMixin,
        EngineCaptchaMixin,
        EngineInteractMixin,
        EngineLaunchMixin,
        EngineBaseMixin,
    ):
        """Meta account creation + Instagram link/join in the same browser session."""

    try:
        from eng_bootstrap import _remove_license  # noqa: E402,F401
    except ImportError:
        pass

# _point_playwright_at_browsers / _remove_license are imported in only one
# branch above (package __init__ exports _remove_license but the shim's
# package branch didn't list _point_playwright_at_browsers). Normalise here
# so both `run._point_playwright_at_browsers` and `run._remove_license`
# always resolve (worker.py uses both).
try:
    _point_playwright_at_browsers  # noqa: F821 — defined in one branch above
except NameError:
    try:
        from engine.eng_bootstrap import (  # noqa: E402
            _point_playwright_at_browsers,
            _remove_license,
        )
    except ImportError:
        from eng_bootstrap import (  # noqa: E402
            _point_playwright_at_browsers,
            _remove_license,
        )


def __getattr__(name: str):
    # Live-forward the Whisper cache singleton (reassigned on first load).
    if name == "_SHARED_WHISPER_MODEL":
        try:
            from engine import eng_antidetect as _ad
        except ImportError:
            import eng_antidetect as _ad  # noqa: E402
        return _ad._SHARED_WHISPER_MODEL
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "HERE",
    "CORE_PYC",
    "_FREE_EXPIRY",
    "_META_AUTH_URL",
    "_META_AI_URL",
    "_META_AI_APEX",
    "_META_POST_URL",
    "_MAILTD_URL",
    "_IG_LOGIN_URL",
    "_IG_SIGNUP_URL",
    "_MONTHS",
    "_HUMAN_TEXTS",
    "_NOVA_FLAGS",
    "_ANTIDETECT_TEMPLATE",
    "_JS_TICK_CHECKBOXES",
    "_JS_SCROLL_DOWN",
    "_JS_DUMP_BUTTONS",
    "_JS_CLICK_TERMS",
    "_SHARED_WHISPER_MODEL",
    "_WHISPER_LOCK",
    "_build_antidetect_script",
    "_get_extension_id_from_manifest",
    "_pin_extensions_in_profile",
    "_get_shared_whisper_model",
    "_install_offline_supabase_stub",
    "_find_browsers_dir",
    "_point_playwright_at_browsers",
    "_load_core",
    "_remove_license",
    "_patch_accept_terms",
    "_patch_meta_flow",
    "_patch_target_option",
    "_MetaInstagramRunner",
    "run_meta_instagram",
    "main",
]

if __name__ == "__main__":
    sys.exit(main())
