"""engine.eng_mix_launch — anti-detect persistent-context launcher (Nova parity).

Verbatim slice from ``engine/run.py`` ``_MetaInstagramRunner`` (no logic change).
Mixed into :class:`engine._MetaInstagramRunner`; ``self`` provides the other
engine helpers (same browser session invariant unchanged). Zero local-repo
dependencies (``store`` only via function-local lazy import).
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import threading
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import HERE, _NOVA_FLAGS  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import HERE, _NOVA_FLAGS  # noqa: E402
try:
    from .eng_antidetect import _build_antidetect_script, _get_extension_id_from_manifest, _pin_extensions_in_profile, device_identity, pc_mobile_identity  # noqa: E402
except ImportError:
    from eng_antidetect import _build_antidetect_script, _get_extension_id_from_manifest, _pin_extensions_in_profile, device_identity, pc_mobile_identity  # noqa: E402
try:
    from .resource_runtime import register_profile  # type: ignore
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from resource_runtime import register_profile  # type: ignore  # noqa: E402

_BROWSER_EXE_CACHE: dict[tuple[str, ...], str] = {}
_BROWSER_EXE_LOCK = threading.Lock()
_BROWSER_INSTALL_LOCK = threading.Lock()
_BROWSER_INSTALL_ATTEMPTED = False


def _find_bundled_chromium() -> str | None:
    """Find the bundled Chromium once instead of walking it per slot.

    The old launch path recursively scanned the complete Playwright tree for
    every parallel slot.  At 10–20 slots this duplicated a large amount of
    filesystem work during the exact startup burst where resources are
    already most constrained.
    """
    candidates = (
        os.path.join(HERE, "..", "_internal", "ms-playwright"),
        os.path.join(HERE, "_internal", "ms-playwright"),
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
        os.path.join(HERE, "ms-playwright"),
    )
    key = tuple(os.path.normcase(os.path.abspath(p)) if p else "" for p in candidates)
    with _BROWSER_EXE_LOCK:
        cached = _BROWSER_EXE_CACHE.get(key)
        if cached:
            return cached
        for root in candidates:
            if not root or not os.path.isdir(root):
                continue
            for current, _dirs, files in os.walk(root):
                for filename in files:
                    if filename.lower() in ("chrome.exe", "chrome"):
                        found = os.path.normpath(os.path.join(current, filename))
                        _BROWSER_EXE_CACHE[key] = found
                        return found
    return None


def _ensure_playwright_browser() -> bool:
    """Install a missing browser once per worker, never once per slot."""
    global _BROWSER_INSTALL_ATTEMPTED
    found = _find_bundled_chromium()
    if found:
        return True
    with _BROWSER_INSTALL_LOCK:
        found = _find_bundled_chromium()
        if found:
            return True
        if _BROWSER_INSTALL_ATTEMPTED:
            return False
        _BROWSER_INSTALL_ATTEMPTED = True
        try:
            import subprocess
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "chromium-headless-shell"],
                check=True,
                timeout=300,
            )
        except Exception:
            return False
    return bool(_find_bundled_chromium())


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _pc_mode_enabled() -> bool:
    """Use the MetaAuto-AI PC-Mobile contract unless explicitly disabled."""
    raw = os.environ.get("PC_MODE", os.environ.get("META_PROFILE_MODE", "1"))
    return str(raw).strip().lower() in ("1", "true", "yes", "on", "pc", "pc-mobile")


class EngineLaunchMixin:
    def _launch(self):
        w = self.w
        # Fresh profile per run (new account each time), but persistent/warm for
        # the duration of the run. Override with NOVA_PROFILE_DIR/INSTA_PROFILE_DIR.
        override = os.environ.get("NOVA_PROFILE_DIR") or os.environ.get("INSTA_PROFILE_DIR")
        base = os.path.join(os.getcwd(), "profiles")
        os.makedirs(base, exist_ok=True)
        if override:
            override = os.path.expanduser(override)
            slot_num = int(getattr(w, "slot_id", 1) or 1)
            if slot_num > 1 and os.environ.get("INSTA_ALLOW_SHARED_PROFILE", "0") not in ("1", "true", "yes"):
                prof = os.path.join(override, f"slot_{slot_num}")
                self.log(f'[⚠️] Partitioning shared profile override for slot {slot_num}.')
            else:
                prof = override
        else:
            prof = os.path.join(base, f"insta_{w.slot_id}_{time.time_ns()}")
        # Set ownership before any fallible setup so the worker's finally path
        # can always release the registry entry.
        w.user_data_dir = prof
        register_profile(prof)
        if not override:
            # Register before pruning so a just-created slot can never remove
            # its own directory during a concurrent launch burst.
            self._prune_profiles(base)
        os.makedirs(prof, exist_ok=True)

        # Disable Chrome Password Manager & Save Password Bubble in profile, and
        # (re)stamp a CLEAN exit marker. Called again right before every launch
        # attempt: if a previous attempt died hard, the retry on the same profile
        # would otherwise show Chrome's "Restore pages? Chromium didn't shut down
        # correctly" bubble (seen on Windows headed runs).
        def _mark_profile_clean():
            try:
                default_dir = os.path.join(prof, "Default")
                os.makedirs(default_dir, exist_ok=True)
                pref_file = os.path.join(default_dir, "Preferences")
                prefs = {}
                if os.path.isfile(pref_file):
                    try:
                        with open(pref_file, "r", encoding="utf-8") as f:
                            prefs = json.load(f)
                    except Exception:
                        prefs = {}
                prefs["credentials_enable_service"] = False
                p_dict = prefs.setdefault("profile", {})
                if isinstance(p_dict, dict):
                    p_dict["password_manager_enabled"] = False
                    p_dict["exit_type"] = "Normal"
                    p_dict["exited_cleanly"] = True
                    content_settings = p_dict.setdefault("default_content_setting_values", {})
                    if isinstance(content_settings, dict):
                        content_settings["notifications"] = 2
                with open(pref_file, "w", encoding="utf-8") as f:
                    json.dump(prefs, f)

                local_state_file = os.path.join(prof, "Local State")
                local_state = {}
                if os.path.isfile(local_state_file):
                    try:
                        with open(local_state_file, "r", encoding="utf-8") as f:
                            local_state = json.load(f)
                    except Exception:
                        local_state = {}
                ls_profile = local_state.setdefault("profile", {})
                if isinstance(ls_profile, dict):
                    ls_profile["password_manager_enabled"] = False
                    # Crash-restore state also lives in Local State on some
                    # builds — stamp it clean there too.
                    ls_profile["exit_type"] = "Normal"
                    ls_profile["exited_cleanly"] = True
                with open(local_state_file, "w", encoding="utf-8") as f:
                    json.dump(local_state, f)
            except Exception:
                pass

        _mark_profile_clean()

        proxy = w._get_proxy_config()
        if self.core and hasattr(self.core, "sync_playwright"):
            w.playwright = self.core.sync_playwright().start()
        else:
            from playwright.sync_api import sync_playwright
            w.playwright = sync_playwright().start()
        # Keep UA + Client Hints consistent with the real browser build.
        self._chrome_full = self._detect_chrome_version(w)

        # Profile selection.  PC-Mobile is the consumer Meta AI contract from
        # the MetaAuto-AI recon; PC_MODE=0 keeps the older stock-mobile path.
        self.is_mobile = (os.environ.get("INSTA_DEVICE_MODE", "mobile").lower() != "desktop")
        _seed = os.path.basename(str(prof).rstrip("/")) or str(getattr(w, "slot_id", "ig"))
        _pinned = getattr(self, "device_model", None)
        _pc_models = ("SM-S918B", "Pixel 6")
        pc_mode = bool(self.is_mobile and _pc_mode_enabled()
                       and (not _pinned or _pinned in _pc_models))
        if self.is_mobile:
            if pc_mode:
                ident = pc_mobile_identity(_seed, model=_pinned if _pinned in _pc_models else None)
                self.log(
                    f'[📱] Browser profile: PC-Mobile ({ident["model"]} / Android '
                    f'{ident["android_version"]} / Chrome {self._chrome_full})'
                )
            else:
                # Deterministic per-profile identity: diverse across accounts,
                # stable on resume, and shared by the launcher and init script.
                if os.environ.get("INSTA_DEVICE_VARY", "1").strip().lower() in ("0", "false", "no"):
                    ident = {
                        "model": "SM-S928B", "android_version": "14",
                        "ua_os": "Linux; Android 14; SM-S928B", "platform": "Linux armv8l",
                        "gpu_vendor": "Qualcomm", "gpu_renderer": "Adreno (TM) 750",
                        "hw": 8, "mem": 8, "max_touch": 5,
                        "screen": {"width": 393, "height": 852, "pixelRatio": 3},
                        "profile_mode": "stock-mobile",
                    }
                else:
                    ident = device_identity(_seed)
                self.log(f'[📱] Browser profile: Stock Mobile (Android / Touch) — {ident["model"]} / {ident["gpu_renderer"]}')
            # Pinned per account (Nova parity): reuse the creation-time model so
            # every resume/open presents the SAME phone.
            if _pinned and not pc_mode:
                ident = dict(ident, model=_pinned,
                             ua_os=f"Linux; Android {ident.get('android_version', '14')}; {_pinned}")
            self._device_ident = ident
            self.profile_mode = ident.get("profile_mode", "pc-mobile" if pc_mode else "stock-mobile")
            model = ident["model"]
            self.device_model = model
            ua = (f"Mozilla/5.0 ({ident['ua_os']}) AppleWebKit/537.36 "
                  f"(KHTML, like Gecko) Chrome/{self._chrome_full} Mobile Safari/537.36")
            _screen = ident.get("screen") or {"width": 393, "height": 852}
            viewport = {"width": int(_screen["width"]), "height": int(_screen["height"])}
            scale = 3
            touch = True
            platform = ident["platform"]
            gpu_vendor = ident["gpu_vendor"]
            gpu_renderer = ident["gpu_renderer"]
        else:
            pc_mode = False
            self._device_ident = None
            self.profile_mode = "desktop"
            ua = (f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  f"(KHTML, like Gecko) Chrome/{self._chrome_full} Safari/537.36")
            viewport = {"width": 1280, "height": 800}
            scale = 1
            touch = False
            platform = "Linux x86_64"
            gpu_vendor = "Intel"
            gpu_renderer = "Intel(R) UHD Graphics 630"
            self.log('[🖥️] Browser profile: Desktop (Linux x86_64 / 1280x800)')
        self.device_ua = ua
        try:
            with open(os.path.join(prof, "device.json"), "w", encoding="utf-8") as _df:
                import json as _json
                _json.dump({
                    "model": getattr(self, "device_model", model if self.is_mobile else "desktop"),
                    "ua": ua,
                    "profile_mode": getattr(self, "profile_mode", "unknown"),
                    "viewport": viewport,
                    "timezone": (self._device_ident or {}).get("timezone", "")
                    if self.is_mobile else "",
                }, _df)
        except Exception:
            pass

        # Bundle the reCAPTCHA solver extension into every automation profile if requested.
        args = list(_NOVA_FLAGS)
        # High-density / low-memory profile (default on; INSTA_LOW_MEM=0 disables).
        # Headless Chromium's real footprint is ~150-350 MB, so these cuts let a
        # low-end box run 10+ headless slots. GPU/compositing off (headless uses
        # SwiftShader anyway), a capped V8 heap and a renderer limit keep each
        # browser small; WebGL is still spoofed by the anti-detect init script.
        if os.environ.get("INSTA_LOW_MEM", "1") != "0":
            renderer_limit = _bounded_env_int("INSTA_RENDERER_LIMIT", 3, 1, 8)
            v8_heap_mb = _bounded_env_int("INSTA_V8_HEAP_MB", 512, 128, 2048)
            args += [
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-accelerated-2d-canvas",
                "--disable-background-networking",
                f"--js-flags=--max-old-space-size={v8_heap_mb}",
                f"--renderer-process-limit={renderer_limit}",
            ]
        # Suppress the "Chrome for Testing v… is only for automated testing"
        # infobar (CfT's "user education UI"). CfT reads a JSON config via
        # --chrome-for-testing-config; keys are camelCase (verified against
        # chrome/browser/chrome_for_testing/config.cc). Written per-profile so
        # nothing leaks into user data.
        try:
            _cft_cfg = os.path.join(prof, "cft_config.json")
            with open(_cft_cfg, "w", encoding="utf-8") as _cf:
                _cf.write('{"enableUserEducationUI": false}')
            args.append(f"--chrome-for-testing-config={_cft_cfg}")
        except Exception:
            pass
        # Headed tiling: IG/Meta windows open on the LEFT half (small cascade
        # per slot so parallel slots don't stack exactly); TG browsers tile
        # RIGHT (warm_pool._TG_TILE). Without this the later-booted TG window
        # lands on top of the IG onboarding mid-typing.
        if not bool(getattr(w, "is_headless", False)):
            if pc_mode:
                # Keep the visible window consistent with the emulated
                # viewport; a 500px tiled window makes the PC-Mobile contract
                # incoherent even though the page viewport is correct.
                args += [f"--window-size={viewport['width']},{viewport['height']}"]
            # INSTA_UI_MODE controls the headed window strategy:
            #   new (default) — Wayland-native visible windows, exactly like the
            #     "new" branch: the compositor owns focus, so automation can
            #     NEVER steal the user's keystrokes mid-typing. Window position
            #     is not set (Wayland ignores it).
            #   isolated — force --ozone-platform=x11 for left/right tiling and
            #     run on the private virtual display (virtual_display.py).
            elif os.environ.get("INSTA_UI_MODE", "new").strip().lower() in ("new", "desktop", "wayland"):
                args += ["--window-size=500,950"]
            else:
                try:
                    _cascade = (abs(hash(str(getattr(w, "slot_id", 1)))) % 4) * 40
                except Exception:
                    _cascade = 0
                # --ozone-platform=x11: on Wayland sessions Chrome ignores
                # --window-position (windows stack and "jump"); Xwayland runs on
                # :0, so force X11 and the tiling above actually applies.
                args += ["--window-size=500,950", f"--window-position={_cascade},0"]
                if sys.platform.startswith("linux"):
                    args += ["--ozone-platform=x11"]
            # INSTA_START_MINIMIZED=1: open headed windows minimized so slot
            # launches never steal OS focus from your terminal. Restore from
            # the taskbar whenever you want to watch.
            if os.environ.get("INSTA_START_MINIMIZED", "") == "1":
                args += ["--start-minimized"]
        captcha_mode = getattr(self, "captcha_mode", os.environ.get("CAPTCHA_MODE", "extension")).lower()
        ext_dir = os.environ.get("RECAPTCHA_EXT_DIR")
        if not ext_dir or not os.path.isdir(ext_dir):
            ext_dir = os.path.join(HERE, "extensions", "Captcha")
        if not os.path.isdir(ext_dir):
            ext_dir = os.path.join(HERE, "..", "extensions", "Captcha")
        if not os.path.isdir(ext_dir):
            ext_dir = os.path.join(HERE, "extensions", "recaptcha_solver")
        if not os.path.isdir(ext_dir):
            ext_dir = os.path.join(HERE, "..", "extensions", "recaptcha_solver")

        is_headless_launch = bool(getattr(w, "is_headless", False))
        # Headless extension support: Playwright's default headless is the
        # chromium-headless-shell, which CANNOT load unpacked extensions. The
        # 'chromium' channel opts into Chrome's NEW headless mode (full Chromium)
        # which DOES support extensions — so the Visual AI captcha extension can
        # run headless. Opt out with INSTA_HEADLESS_EXTENSION=0.
        headless_ext_ok = (is_headless_launch
                           and os.environ.get("INSTA_HEADLESS_EXTENSION", "1") != "0")
        have_ext = (captcha_mode == "extension"
                    and (not is_headless_launch or headless_ext_ok)
                    and os.path.isdir(ext_dir)
                    and os.environ.get("INSTA_NO_EXTENSION") != "1")
        use_new_headless = bool(have_ext and is_headless_launch)
        if (captcha_mode == "extension" and is_headless_launch
                and os.path.isdir(ext_dir) and not headless_ext_ok):
            self.log('[🧩] Background mode: headless shell cannot load extensions — Audio STT first (Visual on Visible fallback)…')
        if have_ext:
            ext_dir = os.path.normpath(ext_dir).replace("\\", "/")
            args += [f"--load-extension={ext_dir}",
                     f"--disable-extensions-except={ext_dir}"]
            # Pin extension in profile Preferences so Chromium activates it immediately
            try:
                manifest_path = os.path.join(ext_dir, "manifest.json")
                ext_id = _get_extension_id_from_manifest(manifest_path, ext_dir)
                if ext_id and prof:
                    _pin_extensions_in_profile(prof, [ext_id])
            except Exception:
                pass
            ext_name = "JA Captcha (Visual AI)" if "Captcha" in ext_dir else "reCAPTCHA Solver"
            if use_new_headless:
                self.log(f'[🧩] Extension: {ext_name} (loaded & pinned) — headless via channel=chromium (new headless)')
            else:
                self.log(f'[🧩] Extension: {ext_name} (loaded & pinned)')
        else:
            self.log('[🎙️] Captcha solver: Offline Audio STT (Whisper / Vosk)')

        launch_kwargs = dict(
            user_data_dir=prof,
            headless=w.is_headless,
            proxy=proxy,
            user_agent=ua,
            viewport=viewport,
            device_scale_factor=scale,
            is_mobile=self.is_mobile,
            has_touch=touch,
            args=args,
            ignore_default_args=["--enable-automation"],
        )
        if pc_mode:
            # Keep the HTTP Client Hints and JS-visible navigator contract in
            # the same profile.  The major version follows the real bundled
            # Chromium; never pin an old Chrome number against a newer binary.
            _major = (self._chrome_full or "124.0.0.0").split(".")[0]
            launch_kwargs.update(
                screen={"width": viewport["width"], "height": viewport["height"]},
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "sec-ch-ua": f'"Chromium";v="{_major}", "Not=A?Brand";v="24"',
                    "sec-ch-ua-mobile": "?1",
                    "sec-ch-ua-platform": '"Android"',
                },
            )
        bundled_bin = _find_bundled_chromium()

        if bundled_bin and os.path.isfile(bundled_bin):
            launch_kwargs["executable_path"] = bundled_bin
            launch_kwargs.pop("channel", None)
        elif use_new_headless:
            # Full Chromium (new headless) instead of the extension-less
            # headless shell, so the Visual AI captcha extension loads headless.
            launch_kwargs["channel"] = "chromium"

        # Resilient multi-engine launch: bundled Chromium is standard and has 100% unpacked extension support.
        # Fall back to Chrome/Edge if bundled Chromium is missing or fails.
        launched = False
        try:
            _mark_profile_clean()
            w.context = w.playwright.chromium.launch_persistent_context(**launch_kwargs)
            self.log('[🌐] Engine: bundled Chromium (anti-detect enabled)')
            launched = True
        except Exception as exc:
            self.log(f'[⚠️] Bundled Chromium launch failed ({exc}), trying fallbacks…')

        if not launched:
            candidates = [
                ("system Google Chrome", {"channel": "chrome"}),
                ("system Microsoft Edge", {"channel": "msedge"}),
            ]
            system_bins = []
            if os.name == "nt":
                local_app = os.environ.get("LOCALAPPDATA", "")
                prog = os.environ.get("ProgramFiles", "C:\\Program Files")
                prog_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
                system_bins = [
                    os.path.join(prog, "Google\\Chrome\\Application\\chrome.exe"),
                    os.path.join(prog_x86, "Google\\Chrome\\Application\\chrome.exe"),
                    os.path.join(local_app, "Google\\Chrome\\Application\\chrome.exe"),
                    os.path.join(prog_x86, "Microsoft\\Edge\\Application\\msedge.exe"),
                    os.path.join(prog, "Microsoft\\Edge\\Application\\msedge.exe"),
                    os.path.join(prog, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
                ]
            else:
                for b in ("/usr/bin/google-chrome-stable", "/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"):
                    if os.path.isfile(b):
                        system_bins.append(b)

            for sb in system_bins:
                if sb and os.path.isfile(sb):
                    candidates.append((f"executable ({os.path.basename(sb)})", {"executable_path": sb}))

            candidates.append(("bundled Chromium", {}))

            for desc, extra in candidates:
                try:
                    kw = dict(launch_kwargs)
                    kw.pop("executable_path", None)
                    if "channel" in extra:
                        kw["channel"] = extra["channel"]
                    elif not use_new_headless:
                        kw.pop("channel", None)
                    kw.update(extra)
                    _mark_profile_clean()
                    w.context = w.playwright.chromium.launch_persistent_context(**kw)
                    self.log(f'[🌐] Engine: {desc} (anti-detect enabled)')
                    launched = True
                    break
                except Exception:
                    pass

            if not launched:
                # Missing runtimes are a packaging problem.  Coordinate the
                # repair once per worker instead of letting every slot launch
                # its own installer and fallback storm.
                self.log('[⏳] Missing Playwright browser — one shared install attempt…')
                if _ensure_playwright_browser():
                    kw = dict(launch_kwargs)
                    kw.pop("executable_path", None)
                    kw.pop("channel", None)
                    _mark_profile_clean()
                    try:
                        w.context = w.playwright.chromium.launch_persistent_context(**kw)
                        self.log('[🌐] Engine: bundled Chromium (newly installed)')
                        launched = True
                    except Exception as exc:
                        self.log(f'[❌] Post-install browser launch failed: {exc}')
                else:
                    self.log('[❌] Shared Playwright browser install unavailable; aborting this slot.')
            if not launched:
                try:
                    _mark_profile_clean()
                    w.context = w.playwright.chromium.launch_persistent_context(**launch_kwargs)
                except Exception as exc:
                    self.log(f'[❌] Browser launch failed after fallback: {exc}')
        # Block third-party ads/analytics/trackers at the network layer. Cuts
        # page weight, memory and load time during signup. Env-gated:
        # INSTA_BLOCK_TRACKERS=0 disables (for A/B). Only well-known
        # non-essential domains are blocked — nothing Meta/Instagram/Google
        # reCAPTCHA or the mail providers need. One route per domain so
        # non-matching requests are never intercepted (no per-request cost).
        if os.environ.get("INSTA_BLOCK_TRACKERS", "1") != "0":
            _blocked_hosts = (
                "doubleclick.net", "google-analytics.com", "googletagmanager.com",
                "googlesyndication.com", "googleadservices.com", "adservice.google.com",
                "amazon-adsystem.com", "scorecardresearch.com", "quantserve.com",
                "criteo.com", "criteo.net", "taboola.com", "outbrain.com",
                "hotjar.com", "mixpanel.com", "segment.com", "segment.io",
                "optimizely.com", "newrelic.com", "nr-data.net", "appsflyer.com",
                "adjust.com", "branch.io", "ads-twitter.com", "analytics.tiktok.com",
            )
            _blocked_n = 0
            for _host in _blocked_hosts:
                try:
                    w.context.route(f"**{_host}**", lambda route: route.abort())
                    _blocked_n += 1
                except Exception:
                    pass
            if _blocked_n:
                self.log(f'[🚫] Ad/tracker blocking on ({_blocked_n} domains; INSTA_BLOCK_TRACKERS=0 to disable).')
        # Extra low-level leak patches (CDP/webdriver/plugins/chrome.runtime).
        # The PC-Mobile contract uses the inline init script only.  The
        # playwright-stealth package injects its own userAgentData brands and
        # can contradict the real Chromium version, which may freeze Meta's
        # Sign-up button.  Keep it available for the legacy stock profile.
        if not pc_mode:
            try:
                from playwright_stealth import Stealth
                Stealth(
                    navigator_user_agent_override=ua,
                    navigator_platform_override=platform,
                    navigator_languages_override=("en-US", "en"),
                    webgl_vendor_override=gpu_vendor,
                    webgl_renderer_override=gpu_renderer,
                ).apply_stealth_sync(w.context)
                self.log('[🛡️] Stealth patches applied (stock profile).')
            except Exception as exc:
                self.log(f'[⚠️] Stealth skipped: {exc}')
        else:
            self.log('[🛡️] Stealth: inline profile only (PC-Mobile parity).')
        # Port of anti-detect fingerprinting (Page.addScriptToEvaluateOnNewDocument).
        try:
            w.context.add_init_script(_build_antidetect_script(
                ua, self._chrome_full, is_mobile=self.is_mobile,
                identity=getattr(self, "_device_ident", None)))
            self.log('[🧬] Anti-detect fingerprint injected.')
        except Exception as exc:
            self.log(f'[⚠️] Anti-detect inject failed: {exc}')
        try:
            w.context.on("close", lambda: w.on_browser_closed())
        except Exception:
            pass
        self.page = w.context.pages[0] if w.context.pages else w.context.new_page()
        w.page = self.page

