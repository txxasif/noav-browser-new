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
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import HERE, _NOVA_FLAGS  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import HERE, _NOVA_FLAGS  # noqa: E402
try:
    from .eng_antidetect import _build_antidetect_script, _get_extension_id_from_manifest, _pin_extensions_in_profile, device_identity  # noqa: E402
except ImportError:
    from eng_antidetect import _build_antidetect_script, _get_extension_id_from_manifest, _pin_extensions_in_profile, device_identity  # noqa: E402

class EngineLaunchMixin:
    def _launch(self):
        w = self.w
        # Fresh profile per run (new account each time), but persistent/warm for
        # the duration of the run. Override with NOVA_PROFILE_DIR/INSTA_PROFILE_DIR.
        override = os.environ.get("NOVA_PROFILE_DIR") or os.environ.get("INSTA_PROFILE_DIR")
        base = os.path.join(os.getcwd(), "profiles")
        os.makedirs(base, exist_ok=True)
        if override:
            prof = os.path.expanduser(override)
        else:
            prof = os.path.join(base, f"insta_{w.slot_id}_{int(time.time())}")
            self._prune_profiles(base)
        w.user_data_dir = prof
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

        # Profile selection: Mobile profile (default proven workable) or Desktop
        self.is_mobile = (os.environ.get("INSTA_DEVICE_MODE", "mobile").lower() != "desktop")
        if self.is_mobile:
            # Deterministic per-profile identity: diverse across accounts, stable
            # on resume, and the single source of truth shared with the
            # anti-detect script so the UA and the injected fingerprint never
            # disagree (they used to: random UA model vs hardcoded SM-S928B).
            # INSTA_DEVICE_VARY=0 restores the old single fixed device.
            _seed = os.path.basename(str(prof).rstrip("/")) or str(getattr(w, "slot_id", "ig"))
            if os.environ.get("INSTA_DEVICE_VARY", "1").strip().lower() in ("0", "false", "no"):
                ident = {"model": "SM-S928B", "android_version": "14",
                         "ua_os": "Linux; Android 14; SM-S928B", "platform": "Linux armv8l",
                         "gpu_vendor": "Qualcomm", "gpu_renderer": "Adreno (TM) 750",
                         "hw": 8, "mem": 8, "max_touch": 5}
            else:
                ident = device_identity(_seed)
            # Pinned per account (Nova parity): reuse the creation-time model so
            # every resume/open presents the SAME phone.
            _pinned = getattr(self, "device_model", None)
            if _pinned:
                ident = dict(ident, model=_pinned,
                             ua_os=f"Linux; Android {ident.get('android_version', '14')}; {_pinned}")
            self._device_ident = ident
            model = ident["model"]
            self.device_model = model
            ua = (f"Mozilla/5.0 ({ident['ua_os']}) AppleWebKit/537.36 "
                  f"(KHTML, like Gecko) Chrome/{self._chrome_full} Mobile Safari/537.36")
            viewport = {"width": 393, "height": 852}
            scale = 3
            touch = True
            platform = ident["platform"]
            gpu_vendor = ident["gpu_vendor"]
            gpu_renderer = ident["gpu_renderer"]
            self.log(f'[📱] Browser profile: Mobile (Android / Touch) — {model} / {gpu_renderer}')
        else:
            self._device_ident = None
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
                _json.dump({"model": getattr(self, "device_model", model if self.is_mobile else "desktop"),
                            "ua": ua}, _df)
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
            args += [
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-accelerated-2d-canvas",
                "--disable-background-networking",
                "--js-flags=--max-old-space-size=512",
                "--renderer-process-limit=3",
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
            # INSTA_UI_MODE controls the headed window strategy:
            #   new (default) — Wayland-native visible windows, exactly like the
            #     "new" branch: the compositor owns focus, so automation can
            #     NEVER steal the user's keystrokes mid-typing. Window position
            #     is not set (Wayland ignores it).
            #   isolated — force --ozone-platform=x11 for left/right tiling and
            #     run on the private virtual display (virtual_display.py).
            if os.environ.get("INSTA_UI_MODE", "new").strip().lower() in ("new", "desktop", "wayland"):
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
        bundled_bin = None
        for bpath in (
            os.path.join(HERE, "..", "_internal", "ms-playwright"),
            os.path.join(HERE, "_internal", "ms-playwright"),
            os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
            os.path.join(HERE, "ms-playwright"),
        ):
            if not bpath or not os.path.isdir(bpath):
                continue
            for root, dirs, files in os.walk(bpath):
                for f in files:
                    if f.lower() in ("chrome.exe", "chrome"):
                        bundled_bin = os.path.normpath(os.path.join(root, f))
                        break
                if bundled_bin:
                    break
            if bundled_bin:
                break

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
                # Auto-install missing Playwright Chromium
                self.log('[⏳] Missing Playwright browser — auto-downloading Chromium...')
                try:
                    import subprocess
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "chromium-headless-shell"], check=True, timeout=300)
                    kw = dict(launch_kwargs)
                    kw.pop("executable_path", None)
                    kw.pop("channel", None)
                    _mark_profile_clean()
                    w.context = w.playwright.chromium.launch_persistent_context(**kw)
                    self.log('[🌐] Engine: bundled Chromium (newly installed)')
                    launched = True
                except Exception as exc:
                    self.log(f'[❌] Playwright install failed: {exc}')
                    _mark_profile_clean()
                    w.context = w.playwright.chromium.launch_persistent_context(**launch_kwargs)
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
        try:
            from playwright_stealth import Stealth
            Stealth(
                navigator_user_agent_override=ua,
                navigator_platform_override=platform,
                navigator_languages_override=("en-US", "en"),
                webgl_vendor_override=gpu_vendor,
                webgl_renderer_override=gpu_renderer,
            ).apply_stealth_sync(w.context)
            self.log('[🛡️] Stealth patches applied.')
        except Exception as exc:
            self.log(f'[⚠️] Stealth skipped: {exc}')
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

