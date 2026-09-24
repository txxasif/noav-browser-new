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
_PC_MOBILE_DEVICES = (
    {
        "model": "SM-S918B",
        "android_version": "13",
        "screen": {"width": 412, "height": 915, "pixelRatio": 3},
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "Intel Iris OpenGL Engine",
    },
    {
        "model": "Pixel 6",
        "android_version": "12",
        "screen": {"width": 411, "height": 914, "pixelRatio": 3},
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "Intel Iris OpenGL Engine",
    },
)


def pc_mobile_identity(seed, model=None) -> dict:
    """Return the stable PC-Mobile profile used by the Meta AI funnel."""
    key = (str(seed or "") or "meta").strip() or "meta"
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    choices = [d for d in _PC_MOBILE_DEVICES if model is None or d["model"] == model]
    dev = (choices or _PC_MOBILE_DEVICES)[h % max(1, len(choices or _PC_MOBILE_DEVICES))]
    return {
        "model": dev["model"],
        "android_version": dev["android_version"],
        "ua_os": f"Linux; Android {dev['android_version']}; {dev['model']}",
        "platform": "Linux armv8l",
        "gpu_vendor": dev["gpu_vendor"],
        "gpu_renderer": dev["gpu_renderer"],
        "hw": 8,
        "mem": 8,
        "max_touch": 5,
        "screen": dict(dev["screen"]),
        "timezone": "America/New_York",
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
        try:
            if log_fn:
                log_fn('[🌐] Loading Whisper speech model into memory (cached locally on disk)...')
            _SHARED_WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
            if log_fn:
                log_fn('[✅] Whisper speech model ready in memory.')
            return _SHARED_WHISPER_MODEL
        except Exception as exc:
            if log_fn:
                log_fn(f'[⚠️] Whisper load failed: {exc}')
            return None


