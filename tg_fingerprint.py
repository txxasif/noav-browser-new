"""tg_fingerprint.py — deterministic per-profile device identity for Telegram Web.

Why this exists
---------------
Every Telegram profile was launched with the SAME user-agent and NO fingerprint
masking, all from the same IP (``tg_bot.py`` hard-coded ``Chrome/126.0.0.0``;
``tg_login.py`` passed no UA at all). Telegram can therefore trivially link the
profiles as one device/IP and its multi-account heuristics invalidate sessions
(observed 2026-09-19: adding a 4th profile logged an existing one out — the
blank ``tg_3`` profile).

What it does
------------
* ``for_profile(dir)``  -> a **deterministic** identity seeded by the profile
  directory name. A given profile always presents the SAME device across
  launches (session continuity); different profiles look like different devices.
* ``launch_kwargs(id)`` -> UA / viewport / screen / DPR / locale / timezone for
  ``launch_persistent_context``.
* ``apply_to_context(ctx, id)`` -> injects stealth + hardware/WebGL/Client-Hints
  overrides via ``add_init_script`` (call BEFORE the first ``goto``).
* ``proxy_for(profile_dir)`` -> optional per-account proxy from the pool record
  (``data/tg_accounts.json`` → ``"proxy"``), so profiles can also differ by IP.

Nothing here is random per launch; the seed is stable, so a profile's identity
never changes between runs (changing device mid-session is itself a red flag).
"""
from __future__ import annotations

import hashlib
import json
import os

# The bundled Chromium's major version — the UA must match the real engine or
# Telegram's feature checks flag a mismatch. Override with TG_CHROME_MAJOR.
_CHROME_MAJOR = os.environ.get("TG_CHROME_MAJOR", "151")

# Identity is COMPOSED from independent axes (OS x screen x GPU x cores) so the
# pool can grow well past the number of hand-written templates without profiles
# colliding. Everything is picked deterministically from the profile-name hash.
_OS = (
    {"os": "Windows", "platform": "Win32", "ua_os": "Windows NT 10.0; Win64; x64",
     "gpu": ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)")},
    {"os": "Windows", "platform": "Win32", "ua_os": "Windows NT 10.0; Win64; x64",
     "gpu": ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)")},
    {"os": "Windows", "platform": "Win32", "ua_os": "Windows NT 10.0; Win64; x64",
     "gpu": ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)")},
    {"os": "macOS", "platform": "MacIntel", "ua_os": "Macintosh; Intel Mac OS X 10_15_7",
     "gpu": ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)")},
    {"os": "macOS", "platform": "MacIntel", "ua_os": "Macintosh; Intel Mac OS X 10_15_7",
     "gpu": ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)")},
    {"os": "Linux", "platform": "Linux x86_64", "ua_os": "X11; Linux x86_64",
     "gpu": ("Google Inc. (Intel)", "ANGLE (Intel, Mesa Intel(R) UHD Graphics 620 (KBL GT2), OpenGL 4.6)")},
    {"os": "Linux", "platform": "Linux x86_64", "ua_os": "X11; Linux x86_64",
     "gpu": ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 (POLARIS10, DRM 3.42.0, 5.15.0), OpenGL 4.6)")},
)
_SCREENS = ((1920, 1080, 1.0), (2560, 1440, 1.0), (1728, 1117, 2.0),
            (1600, 900, 1.25), (1366, 768, 1.0), (1536, 864, 1.25), (2048, 1152, 1.0))
_HW = (4, 6, 8, 8, 12, 16)


def for_profile(profile_dir_or_id: str) -> dict:
    """Deterministic per-profile identity (stable for a given profile name)."""
    key = os.path.basename(str(profile_dir_or_id).rstrip("/")) or "tg"
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    o = _OS[h % len(_OS)]
    sw, sh, dpr = _SCREENS[(h // 7) % len(_SCREENS)]
    # Retina Macs report DPR 2; Windows/Linux desktops 1.0–1.5.
    dpr = 2.0 if o["os"] == "macOS" else ((1.0, 1.25, 1.5)[(h // 23) % 3])
    hw = _HW[(h // 13) % len(_HW)]
    # viewport slightly smaller than the screen, as a real maximised window is
    vw = sw - 200 - ((h // 17) % 4) * 40
    vh = sh - 120 - ((h // 19) % 3) * 20
    return {
        "os": o["os"],
        "ua": f"Mozilla/5.0 ({o['ua_os']}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{_CHROME_MAJOR}.0.0.0 Safari/537.36",
        "platform": o["platform"],
        "vendor": "Google Inc.",
        "screen": (sw, sh),
        "viewport": (int(vw), int(vh)),
        "dpr": dpr,
        "webgl_vendor": o["gpu"][0],
        "webgl_renderer": o["gpu"][1],
        "hw": hw,
        "mem": 8 if hw <= 8 else 16,
        "tz": "Asia/Dhaka",
        "locale": "en-US",
        "langs": ["en-US", "en"],
    }


def proxy_for(profile_dir_or_id: str):
    """Optional per-account proxy from the pool record, else None.

    Pool records may carry ``"proxy": "http://user:pass@host:port"``. When
    present, each Telegram profile also differs by IP — the only way to defeat
    IP-based correlation. No proxy configured -> None (unchanged behaviour).
    """
    try:
        import ai_config  # noqa: F401
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tg_accounts.json")
        name = os.path.basename(str(profile_dir_or_id).rstrip("/"))
        with open(path, "r", encoding="utf-8") as fh:
            recs = json.load(fh)
        for r in recs:
            if os.path.basename(str(r.get("profile_dir", "")).rstrip("/")) == name:
                px = (r.get("proxy") or "").strip()
                if px:
                    return {"server": px}
        return None
    except Exception:
        return None


def launch_kwargs(identity: dict) -> dict:
    """Playwright launch_persistent_context kwargs for this identity."""
    return {
        "user_agent": identity["ua"],
        "viewport": {"width": identity["viewport"][0], "height": identity["viewport"][1]},
        "screen": {"width": identity["screen"][0], "height": identity["screen"][1]},
        "device_scale_factor": identity["dpr"],
        "locale": identity["locale"],
        "timezone_id": identity["tz"],
        "color_scheme": "light",
        "is_mobile": False,
        "has_touch": False,
    }


def init_script(identity: dict) -> str:
    """JS injected before page scripts to mask the obvious automation tells.

    Only overrides the risky, high-signal properties; WebGL keeps real values
    except the UNMASKED vendor/renderer, so Telegram's animations keep working.
    """
    cfg = {
        "platform": identity["platform"],
        "vendor": identity["vendor"],
        "hw": identity["hw"],
        "mem": identity["mem"],
        "langs": identity["langs"],
        "wv": identity["webgl_vendor"],
        "wr": identity["webgl_renderer"],
        "ua": identity["ua"],
    }
    return ("(() => { const C = %s;\n" % json.dumps(cfg)) + """
  const def = (o, k, v) => { try { Object.defineProperty(o, k, { get: () => v, configurable: true }); } catch (e) {} };
  try { delete Object.getPrototypeOf(navigator).webdriver; } catch (e) {}
  def(navigator, 'webdriver', undefined);
  def(navigator, 'platform', C.platform);
  def(navigator, 'vendor', C.vendor);
  def(navigator, 'hardwareConcurrency', C.hw);
  def(navigator, 'deviceMemory', C.mem);
  def(navigator, 'languages', C.langs);
  def(navigator, 'language', C.langs[0]);
  // Client Hints
  try {
    Object.defineProperty(navigator, 'userAgentData', { configurable: true, get: () => ({
      brands: [{brand:'Chromium',version:'126'},{brand:'Google Chrome',version:'126'},{brand:'Not.A/Brand',version:'24'}],
      mobile: false, platform: (C.platform === 'Win32' ? 'Windows' : (C.platform.startsWith('Mac') ? 'macOS' : 'Linux')),
      getHighEntropyValues: () => Promise.resolve({ architecture: 'x86', bitness: '64', platformVersion: '10.0.0' })
    })});
  } catch (e) {}
  // WebGL vendor/renderer
  const patchGL = (proto) => { try {
    const gp = proto.getParameter;
    proto.getParameter = function (p) {
      if (p === 37445) return C.wv;   // UNMASKED_VENDOR_WEBGL
      if (p === 37446) return C.wr;   // UNMASKED_RENDERER_WEBGL
      return gp.call(this, p);
    };
  } catch (e) {} };
  patchGL(WebGLRenderingContext.prototype);
  try { patchGL(WebGL2RenderingContext.prototype); } catch (e) {}
  // Permissions: report standard default instead of 'denied' automation look
  try {
    const q = window.navigator.permissions && window.navigator.permissions.query;
    if (q) window.navigator.permissions.query = (p) => (p && p.name === 'notifications')
      ? Promise.resolve({ state: Notification.permission, onchange: null }) : q(p);
  } catch (e) {}
  // chrome runtime shim (real Chrome always has it)
  try { if (!window.chrome) window.chrome = {}; if (!window.chrome.runtime) window.chrome.runtime = {}; } catch (e) {}
})();
"""


def apply_to_context(ctx, identity: dict) -> None:
    """Inject the identity into an already-created context. Call before goto()."""
    try:
        ctx.add_init_script(init_script(identity))
    except Exception:
        pass
