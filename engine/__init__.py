"""engine — self-contained Meta→Instagram anti-detect engine (package).

Split from the former monolithic ``engine/run.py`` (now a thin re-export shim)
with zero logic change. Submodules are verbatim slices:

* :mod:`engine.eng_constants` — HERE/CORE_PYC/URLs/JS/fingerprint/_NOVA_FLAGS.
* :mod:`engine.eng_antidetect` — script builder, extension + Whisper helpers.
* :mod:`engine.eng_bootstrap` — offline stub, browser path, core loader, license.
* :mod:`engine.eng_patches` — Qt patches + entrypoint.
* :mod:`engine.eng_mix_base` — identity/logging/human input.
* :mod:`engine.eng_mix_launch` — persistent-context launcher.
* :mod:`engine.eng_mix_interact` — visible-first clicks/fills/advance.
* :mod:`engine.eng_mix_captcha` — checkpoint/selfie/extension flow.
* :mod:`engine.eng_mix_audio` — offline reCAPTCHA audio STT + image fallback.
* :mod:`engine.eng_mix_mail` — mail.td inbox.
* :mod:`engine.eng_mix_meta` — meta.ai funnel.
* :mod:`engine.eng_mix_signup` — auth.meta.com wizard.
* :mod:`engine.eng_mix_ig` — Instagram link/join + run_meta_instagram.

Zero local-repo dependencies (``store`` only via function-local lazy import).
``import run`` keeps working via ``engine/run.py`` shim which re-exports this
package's symbols (single class object — no duplication).
"""
from __future__ import annotations

from .eng_antidetect import (
    _WHISPER_LOCK,
    _build_antidetect_script,
    _get_extension_id_from_manifest,
    _get_shared_whisper_model,
    _pin_extensions_in_profile,
)
from .eng_bootstrap import (
    _find_browsers_dir,
    _install_offline_supabase_stub,
    _load_core,
    _point_playwright_at_browsers,
    _remove_license,
)
from .eng_constants import (
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
    HERE,
)
from .eng_mix_audio import EngineAudioMixin
from .eng_mix_base import EngineBaseMixin
from .eng_mix_captcha import EngineCaptchaMixin
from .eng_mix_ig import EngineIgMixin, run_meta_instagram
from .eng_mix_interact import EngineInteractMixin
from .eng_mix_launch import EngineLaunchMixin
from .eng_mix_mail import EngineMailMixin
from .eng_mix_meta import EngineMetaMixin
from .eng_mix_signup import EngineSignupMixin
from .eng_patches import _patch_accept_terms, _patch_meta_flow, _patch_target_option, main


class _MetaInstagramRunner(
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
    "_build_antidetect_script",
    "_get_extension_id_from_manifest",
    "_pin_extensions_in_profile",
    "_get_shared_whisper_model",
    "_SHARED_WHISPER_MODEL",
    "_WHISPER_LOCK",
    "_install_offline_supabase_stub",
    "_find_browsers_dir",
    "_point_playwright_at_browsers",
    "_load_core",
    "_remove_license",
    "_patch_accept_terms",
    "_patch_meta_flow",
    "_patch_target_option",
    "EngineBaseMixin",
    "EngineLaunchMixin",
    "EngineInteractMixin",
    "EngineCaptchaMixin",
    "EngineAudioMixin",
    "EngineMailMixin",
    "EngineMetaMixin",
    "EngineSignupMixin",
    "EngineIgMixin",
    "_MetaInstagramRunner",
    "run_meta_instagram",
    "main",
]


def __getattr__(name: str):
    # Live-forward the Whisper cache singleton (reassigned on first load).
    # A plain `from ... import` would snapshot None forever.
    if name == "_SHARED_WHISPER_MODEL":
        from . import eng_antidetect as _ad

        return _ad._SHARED_WHISPER_MODEL
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
