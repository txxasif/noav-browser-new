"""engine.eng_antidetect — anti-detect script builder, extension + Whisper helpers.

Verbatim from ``engine/run.py`` (no logic change). Zero local-repo dependencies.
Adds the missing ``import hashlib`` (original used it without importing —
NameError only when a manifest ``key`` is present).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import threading
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import _ANTIDETECT_TEMPLATE  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _ANTIDETECT_TEMPLATE  # noqa: E402

# Per-profile mobile identity (deterministic, seeded by the profile dir/name).
# Diversity matters: Instagram links accounts presenting an identical device
# fingerprint, and before this every profile injected the SAME device
# (SM-S928B / Adreno 750 / 8). The launch UA picked a random model while this
# script hardcoded SM-S928B, so the UA and the injected fingerprint also
# disagreed. device_identity() is now the single source of truth, used by both
# the launch (eng_mix_launch) and this script. Screen stays the proven
# mobile layout (393x852@3) so UI flows are unaffected.
_MOBILE_MODELS = (
    ("SM-S928B", "14"), ("SM-S918B", "14"), ("SM-G991B", "13"),
    ("Pixel 8 Pro", "14"), ("Pixel 7", "14"), ("Pixel 6", "13"),
    ("OnePlus 12", "14"), ("CPH2527", "13"), ("moto g84 5G", "13"),
)
_MOBILE_GPUS = (
    ("Qualcomm", "Adreno (TM) 750"),
    ("Qualcomm", "Adreno (TM) 740"),
    ("Qualcomm", "Adreno (TM) 730"),
    ("Qualcomm", "Adreno (TM) 660"),
    ("ARM", "Mali-G715-Immortalis MC11"),
    ("ARM", "Mali-G610 MC6"),
    ("ARM", "Mali-G78 MP14"),
)
_MOBILE_HW = (6, 8, 8, 12)
_MOBILE_MEM = (6, 8, 8, 12)
_MOBILE_TOUCH = (5, 10)

# Consumer Meta AI profile documented by the MetaAuto-AI recon.  The UA
# version is filled from the real bundled Chromium at launch; these values
# only describe the device contract.  Keep this list small and coherent:
# model, Android version, viewport, and GPU must agree in the injected
# fingerprint, HTTP Client Hints, and JavaScript navigator values.
# Coherent Android device table for the PC-Mobile contract.
#
# Every entry lists ONLY pairings that exist on real hardware (a Tensor Pixel
# never ships an Adreno; a budget moto never ships 12 GB), so any generated
# fingerprint is believable — a shared/implausible fingerprint is a stronger
# linking signal than a varied one. pc_mobile_identity() picks ONE entry, one of
# its GPUs, and a plausible core/RAM count — deterministically per seed (same
# seed -> same phone, stable on resume), varied across profiles.
#
# Screens stay in the PROVEN PC-Mobile viewport class (411-412 x 914-915 @ 3) so
# the UI flows are unaffected.
_PC_MOBILE_SCREENS = ((412, 915, 3), (411, 914, 3))

_PC_MOBILE_DEVICES = (
    # (model, android_version, gpus, hw_choices, mem_choices)
    ("Pixel 8 Pro", "14", (("ARM", "Mali-G715-Immortalis MC11"),), (8,), (12,)),
    ("Pixel 7", "13", (("ARM", "Mali-G710 MC10"),), (8,), (8,)),
    ("Pixel 6", "12", (("ARM", "Mali-G78"),), (8,), (8,)),
    ("SM-S928B", "14", (("Qualcomm", "Adreno (TM) 750"),), (8,), (12,)),
    ("SM-S918B", "13", (("Qualcomm", "Adreno (TM) 740"),), (8,), (8, 12)),
    ("SM-S911B", "13", (("Qualcomm", "Adreno (TM) 740"),), (8,), (8,)),
    ("SM-G991B", "13", (("ARM", "Mali-G78 MP14"),), (8,), (8,)),
    ("SM-A546B", "13", (("ARM", "Mali-G68 MP5"),), (8,), (6, 8)),
    ("OnePlus 12", "14", (("Qualcomm", "Adreno (TM) 750"),), (8,), (12,)),
    ("OnePlus 11", "13", (("Qualcomm", "Adreno (TM) 740"),), (8,), (8, 16)),
    ("CPH2527", "13", (("ARM", "Mali-G610 MC6"),), (8,), (8,)),
    ("moto g84 5G", "13", (("Qualcomm", "Adreno (TM) 695"),), (8,), (8,)),
    ("moto g73 5G", "13", (("Qualcomm", "Adreno (TM) 619"),), (6, 8), (6, 8)),
    ("moto g54 5G", "13", (("Qualcomm", "Adreno (TM) 619"),), (8,), (6, 8)),
    ("V2312", "13", (("ARM", "Mali-G610 MC6"),), (8,), (8,)),
    ("V2254", "13", (("Qualcomm", "Adreno (TM) 619"),), (6, 8), (6, 8)),
    ("2201123G", "13", (("Qualcomm", "Adreno (TM) 695"),), (8,), (6, 8)),
    ("RMX3780", "13", (("ARM", "Mali-G68 MC4"),), (8,), (8,)),
    ("SM-S921B", "14", (("Qualcomm", "Adreno (TM) 750"),), (8,), (8, 12)),
    ("SM-S906B", "13", (("Qualcomm", "Adreno (TM) 730"),), (8,), (8,)),
    ("SM-A346B", "13", (("ARM", "Mali-G68 MC4"),), (8,), (6, 8)),
    ("Pixel 8", "14", (("ARM", "Mali-G715 MC7"),), (8,), (8,)),
    ("Pixel 7a", "13", (("ARM", "Mali-G710 MC10"),), (8,), (8,)),
    ("Pixel 6a", "13", (("ARM", "Mali-G78 MP20"),), (8,), (6,)),
    ("OnePlus 10 Pro", "13", (("Qualcomm", "Adreno (TM) 730"),), (8,), (8, 12)),
    ("OnePlus Nord 3", "13", (("ARM", "Mali-G710 MC10"),), (8,), (8, 16)),
    ("CPH2451", "13", (("ARM", "Mali-G68 MC4"),), (8,), (8,)),
    ("CPH2557", "14", (("ARM", "Mali-G610 MC6"),), (8,), (8, 12)),
    ("moto g34 5G", "13", (("Qualcomm", "Adreno (TM) 619"),), (8,), (6, 8)),
    ("Redmi Note 13", "13", (("ARM", "Mali-G57 MC2"),), (8,), (6, 8)),
    ("2312DRA50C", "14", (("Qualcomm", "Adreno (TM) 710"),), (8,), (8, 12)),
    ("V2324", "14", (("ARM", "Mali-G610 MC6"),), (8,), (8,)),
    ("RMX3820", "13", (("ARM", "Mali-G68 MC4"),), (8,), (8, 12)),
    ("23078PND5G", "13", (("Qualcomm", "Adreno (TM) 725"),), (8,), (8, 12)),
    ("SM-F946B", "14", (("Qualcomm", "Adreno (TM) 740"),), (8,), (12,)),
    ("Pixel Fold", "14", (("ARM", "Mali-G715 MC7"),), (8,), (12,)),
    ("CPH2525", "13", (("Qualcomm", "Adreno (TM) 695"),), (8,), (8, 12)),
    ("moto edge 40", "13", (("ARM", "Mali-G77 MC9"),), (8,), (8,)),
    ("22081212C", "13", (("Qualcomm", "Adreno (TM) 730"),), (8,), (8, 12)),
)


# Country -> primary IANA timezone. The browser/JS timezone MUST agree with the
# egress IP — a fingerprint claiming America/New_York behind a Singapore proxy is
# a classic automation flag (observed 2026-10-08: hardcoded US zone on a SG VPS).
_COUNTRY_TZ = {
    "us": "America/New_York", "ca": "America/Toronto", "mx": "America/Mexico_City",
    "br": "America/Sao_Paulo", "ar": "America/Argentina/Buenos_Aires",
    "co": "America/Bogota", "cl": "America/Santiago", "pe": "America/Lima",
    "gb": "Europe/London", "ie": "Europe/Dublin", "de": "Europe/Berlin",
    "fr": "Europe/Paris", "es": "Europe/Madrid", "it": "Europe/Rome",
    "nl": "Europe/Amsterdam", "be": "Europe/Brussels", "pt": "Europe/Lisbon",
    "pl": "Europe/Warsaw", "se": "Europe/Stockholm", "no": "Europe/Oslo",
    "dk": "Europe/Copenhagen", "fi": "Europe/Helsinki", "ch": "Europe/Zurich",
    "at": "Europe/Vienna", "cz": "Europe/Prague", "ro": "Europe/Bucharest",
    "gr": "Europe/Athens", "ru": "Europe/Moscow", "ua": "Europe/Kiev",
    "tr": "Europe/Istanbul", "in": "Asia/Kolkata", "pk": "Asia/Karachi",
    "bd": "Asia/Dhaka", "lk": "Asia/Colombo", "np": "Asia/Kathmandu",
    "id": "Asia/Jakarta", "ph": "Asia/Manila", "vn": "Asia/Ho_Chi_Minh",
    "th": "Asia/Bangkok", "sg": "Asia/Singapore", "my": "Asia/Kuala_Lumpur",
    "jp": "Asia/Tokyo", "kr": "Asia/Seoul", "cn": "Asia/Shanghai",
    "hk": "Asia/Hong_Kong", "tw": "Asia/Taipei", "ae": "Asia/Dubai",
    "sa": "Asia/Riyadh", "il": "Asia/Jerusalem", "ir": "Asia/Tehran",
    "kz": "Asia/Almaty", "uz": "Asia/Tashkent",
    "eg": "Africa/Cairo", "ng": "Africa/Lagos", "ke": "Africa/Nairobi",
    "gh": "Africa/Accra", "za": "Africa/Johannesburg", "ma": "Africa/Casablanca",
    "dz": "Africa/Algiers", "tn": "Africa/Tunis", "et": "Africa/Addis_Ababa",
    "au": "Australia/Sydney", "nz": "Pacific/Auckland",
}

_TZ_CACHE = None
_TZ_CACHE_AT = 0.0
# Re-detect the egress timezone this often (seconds; INSTA_TZ_TTL). A VPN/proxy
# switch is adopted within the TTL without restarting the worker. The browser's
# timezone is fixed at LAUNCH, so a running browser keeps its zone; new launches
# adopt. Set INSTA_TZ_TTL=0 to re-detect on every launch (one small IP lookup).
try:
    _TZ_TTL = float(os.environ.get("INSTA_TZ_TTL", "60") or 0)
except Exception:
    _TZ_TTL = 60.0


def resolve_timezone() -> str:
    """IANA timezone for the fingerprint, aligned with the egress.

    Resolution order:
      1. ``INSTA_TZ`` (explicit IANA name — set this to match your proxy)
      2. the country token in ``PROXY_URL`` (e.g. ``...country-sg...``)
      3. the public IP's country (best-effort, 5s timeout)
      4. ``UTC``

    Never hardcode a US zone behind a non-US egress — the mismatch is a flag.
    Cached for ``_TZ_TTL`` seconds so a VPN switch is picked up automatically.
    """
    global _TZ_CACHE, _TZ_CACHE_AT
    now = time.time()
    if _TZ_CACHE and (now - _TZ_CACHE_AT) < _TZ_TTL:
        return _TZ_CACHE
    tz = ""
    try:
        tz = (os.environ.get("INSTA_TZ") or "").strip()
    except Exception:
        tz = ""
    if not tz:
        try:
            import re as _re
            px = os.environ.get("PROXY_URL") or ""
            m = (_re.search(r"country[-_=]([a-zA-Z]{2})", px)
                 or _re.search(r"(?:cc|geo|region|loc)[-_=]([a-zA-Z]{2})", px))
            if m:
                tz = _COUNTRY_TZ.get(m.group(1).lower(), "")
        except Exception:
            pass
    if not tz:
        try:
            import urllib.request
            with urllib.request.urlopen("https://ipinfo.io/country", timeout=5) as r:
                cc = (r.read().decode("utf-8", "replace") or "").strip().lower()
            tz = _COUNTRY_TZ.get(cc, "")
        except Exception:
            tz = ""
    _TZ_CACHE = tz or "UTC"
    _TZ_CACHE_AT = now
    return _TZ_CACHE


def pc_mobile_models() -> tuple:
    """Every model name in the PC-Mobile table (for pinning / validation)."""
    return tuple(d[0] for d in _PC_MOBILE_DEVICES)


def pc_mobile_identity(seed, model=None) -> dict:
    """Return a stable, COHERENT PC-Mobile profile for one seed.

    Draws from ``_PC_MOBILE_DEVICES`` (each model carries only its real GPUs /
    core / RAM counts) so every generated fingerprint is plausible, and different
    seeds get different phones — stable on resume (same seed -> same device).
    """
    key = (str(seed or "") or "meta").strip() or "meta"
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    choices = [d for d in _PC_MOBILE_DEVICES if model is None or d[0] == model]
    dev = (choices or _PC_MOBILE_DEVICES)[h % max(1, len(choices or _PC_MOBILE_DEVICES))]
    _model, _android, gpus, hws, mems = dev
    gpu_vendor, gpu_renderer = gpus[(h // 7) % len(gpus)]
    hw = hws[(h // 11) % len(hws)]
    mem = mems[(h // 13) % len(mems)]
    screen = _PC_MOBILE_SCREENS[(h // 17) % len(_PC_MOBILE_SCREENS)]
    return {
        "model": _model,
        "android_version": _android,
        "ua_os": f"Linux; Android {_android}; {_model}",
        "platform": "Linux armv8l",
        "gpu_vendor": gpu_vendor,
        "gpu_renderer": gpu_renderer,
        "hw": hw,
        "mem": mem,
        "max_touch": 5,
        "screen": {"width": screen[0], "height": screen[1], "pixelRatio": screen[2]},
        "timezone": resolve_timezone(),
        "locale": "en-US",
        "profile_mode": "pc-mobile",
    }


def device_identity(seed) -> dict:
    """Deterministic, diverse mobile device identity for one profile.

    Stable for a given seed (profile dir/name) so a resumed account keeps the
    same phone, but different across profiles so accounts never share a device
    fingerprint.
    """
    key = (str(seed or "") or "ig").strip() or "ig"
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    model, android_version = _MOBILE_MODELS[h % len(_MOBILE_MODELS)]
    gpu_vendor, gpu_renderer = _MOBILE_GPUS[(h // 13) % len(_MOBILE_GPUS)]
    return {
        "model": model,
        "android_version": android_version,
        "ua_os": f"Linux; Android {android_version}; {model}",
        "platform": "Linux armv8l",
        "gpu_vendor": gpu_vendor,
        "gpu_renderer": gpu_renderer,
        "hw": _MOBILE_HW[(h // 17) % len(_MOBILE_HW)],
        "mem": _MOBILE_MEM[(h // 19) % len(_MOBILE_MEM)],
        "max_touch": _MOBILE_TOUCH[(h // 23) % len(_MOBILE_TOUCH)],
        "screen": {"width": 393, "height": 852, "pixelRatio": 3},
        "timezone": resolve_timezone(),
        "profile_mode": "stock-mobile",
    }


def _build_antidetect_script(user_agent, chrome_full="124.0.6367.82", is_mobile=True,
                             identity=None):
    major = chrome_full.split(".")[0]
    if is_mobile:
        # No explicit identity (other callers) keeps the legacy fixed device.
        ident = identity or {
            "model": "SM-S928B", "android_version": "14", "platform": "Linux armv8l",
            "gpu_vendor": "Qualcomm", "gpu_renderer": "Adreno (TM) 750",
            "hw": 8, "mem": 8, "max_touch": 5,
        }
        screen = ident.get("screen") or {"width": 393, "height": 852, "pixelRatio": 3}
        network = {"languages": ["en-US", "en"], "webrtc": "BLOCK"}
        if ident.get("timezone"):
            network["timezone"] = str(ident["timezone"])
        cfg = {
            "name": "InstaAuto-Mobile",
            "type": "ANDROID_MOBILE",
            "userAgent": user_agent,
            "chMajor": major,
            "chFull": chrome_full,
            "platform": ident.get("platform", "Linux armv8l"),
            "vendor": "Google Inc.",
            "hardwareConcurrency": int(ident.get("hw", 8)),
            "deviceMemory": int(ident.get("mem", 8)),
            "maxTouchPoints": int(ident.get("max_touch", 5)),
            "network": network,
            "screen": screen,
            "device": {"model": ident.get("model", "SM-S928B"),
                       "androidVersion": ident.get("android_version", "14"),
                       "gpu": {"vendor": ident.get("gpu_vendor", "Qualcomm"),
                               "renderer": ident.get("gpu_renderer", "Adreno (TM) 750")}},
            "noise": {"canvas": 0.0001, "audio": 0.0001},
        }
    else:
        cfg = {
            "name": "InstaAuto-Desktop",
            "type": "LINUX_DESKTOP",
            "userAgent": user_agent,
            "chMajor": major,
            "chFull": chrome_full,
            "platform": "Linux x86_64",
            "vendor": "Google Inc.",
            "hardwareConcurrency": 8,
            "deviceMemory": 8,
            "maxTouchPoints": 0,
            "network": {"languages": ["en-US", "en"], "webrtc": "BLOCK"},
            "screen": {"width": 1920, "height": 1080, "pixelRatio": 1},
            "device": {"model": "PC", "gpu": {"vendor": "Intel", "renderer": "Intel(R) UHD Graphics 630"}},
            "noise": {"canvas": 0.0001, "audio": 0.0001},
        }
    return _ANTIDETECT_TEMPLATE.replace("__CONFIG__", json.dumps(cfg))

def _get_extension_id_from_manifest(manifest_path, ext_dir=None):
    try:
        if os.path.isfile(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            key = manifest.get("key")
            if key:
                import base64
                key_bytes = base64.b64decode(key)
                hash_bytes = hashlib.sha256(key_bytes).digest()[:16]
                return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 15)) for b in hash_bytes).lower()
        if ext_dir and os.path.isdir(ext_dir):
            hash_bytes = hashlib.sha256(os.path.abspath(ext_dir).encode("utf-8")).digest()[:16]
            return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 15)) for b in hash_bytes).lower()
    except Exception:
        pass
    return None


def _pin_extensions_in_profile(user_data_dir, extension_ids):
    try:
        prefs_path = os.path.join(user_data_dir, "Default", "Preferences")
        os.makedirs(os.path.dirname(prefs_path), exist_ok=True)
        prefs = {}
        if os.path.exists(prefs_path):
            try:
                with open(prefs_path, "r", encoding="utf-8") as f:
                    prefs = json.load(f)
            except Exception:
                prefs = {}
        ext_dict = prefs.setdefault("extensions", {})
        pinned = ext_dict.setdefault("pinned_extensions", [])
        settings = ext_dict.setdefault("settings", {})
        for ext_id in extension_ids:
            if not ext_id:
                continue
            ext_id = ext_id.lower()
            if ext_id not in pinned:
                pinned.append(ext_id)
            settings.setdefault(ext_id, {})["pinned"] = True
            settings[ext_id]["state"] = 1
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
        return True
    except Exception:
        return False

_SHARED_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()


def _get_shared_whisper_model(log_fn=None):
    global _SHARED_WHISPER_MODEL
    with _WHISPER_LOCK:
        if _SHARED_WHISPER_MODEL is not None:
            return _SHARED_WHISPER_MODEL
        try:
            from faster_whisper import WhisperModel
        except Exception:
            return None
        # Low-end preset: tiny (~75MB, 2-3x faster on weak CPU) instead of
        # base (~150MB). Override with INSTA_WHISPER_MODEL=base/small/...
        try:
            _low = os.environ.get("INSTA_LOW_END", "0").strip().lower() in (
                "1", "true", "yes", "on")
        except Exception:
            _low = False
        model_name = (os.environ.get("INSTA_WHISPER_MODEL") or "").strip() or ("tiny" if _low else "base")
        try:
            if log_fn:
                log_fn('[🌐] Loading Whisper speech model into memory (cached locally on disk)...')
            _SHARED_WHISPER_MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")
            if log_fn:
                log_fn('[✅] Whisper speech model ready in memory.')
            return _SHARED_WHISPER_MODEL
        except Exception as exc:
            if log_fn:
                log_fn(f'[⚠️] Whisper load failed: {exc}')
            return None


