"""engine.eng_constants — shared paths, URLs, JS snippets & fingerprint template.

Verbatim slices from the former monolithic ``engine/run.py`` (no logic change):
HERE/CORE_PYC/_FREE_EXPIRY, _JS_* terms helpers, Meta/IG/mail URLs, _MONTHS,
_HUMAN_TEXTS, _ANTIDETECT_TEMPLATE, _NOVA_FLAGS. Zero local-repo dependencies.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
# The app writes profiles/, cookies/, accounts.txt, key.txt, ... relative to
# the current working directory. Keep them next to the app for predictability.

CORE_PYC = os.environ.get("CORE_PYC") or os.path.join(HERE, "app.pyc")

# A far-future expiry so the UI clock keeps showing "Active".
_FREE_EXPIRY = datetime.now(timezone.utc) + timedelta(days=3650)

# --- Instagram terms step -------------------------------------------------
# The original only looks for a button whose text literally contains
# "i agree". Instagram's current UI labels it differently (and sometimes
# requires ticking a consent box first), so the signup stalls at the last
# screen. This replacement is more forgiving and logs what it sees.

_JS_TICK_CHECKBOXES = r"""
() => {
    document.querySelectorAll('input[type=checkbox]').forEach(cb => {
        if (!cb.checked) {
            cb.click(); cb.checked = true;
            cb.dispatchEvent(new Event('input',  {bubbles:true}));
            cb.dispatchEvent(new Event('change', {bubbles:true}));
        }
    });
    return true;
}
"""

_JS_SCROLL_DOWN = r"""
() => {
    window.scrollTo(0, document.body.scrollHeight);
    document.querySelectorAll('div').forEach(d => {
        if (d.scrollHeight > d.clientHeight + 40 && d.clientHeight > 200) {
            d.scrollTop = d.scrollHeight;
        }
    });
    return true;
}
"""

_JS_DUMP_BUTTONS = r"""
() => {
    const norm = s => (s || '').replace(/\s+/g, ' ').trim();
    const out = [];
    document.querySelectorAll('button,[role=button],a,input[type=submit]').forEach(el => {
        const r = el.getBoundingClientRect();
        const t = norm(el.textContent);
        const a = norm(el.getAttribute('aria-label'));
        if ((t || a) && r.width > 0 && r.height > 0) {
            out.push({
                text: t.slice(0, 45),
                aria: a.slice(0, 45),
                disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true')
            });
        }
    });
    return out;
}
"""

_JS_CLICK_TERMS = r"""
() => {
    const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const els = [...document.querySelectorAll('button,[role=button],a,input[type=submit]')];
    const patterns = ['i agree', 'agree', 'accept', 'allow', 'sign up', 'signup',
                      'next', 'continue'];
    for (const pat of patterns) {
        const el = els.find(e => {
            const r = e.getBoundingClientRect();
            const dis = !!(e.disabled || e.getAttribute('aria-disabled') === 'true');
            const txt = norm(e.textContent) + ' ' + norm(e.getAttribute('aria-label'));
            return !dis && r.width > 0 && r.height > 0 && txt.includes(pat);
        });
        if (el) {
            el.scrollIntoView({block: 'center'});
            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']
                .forEach(ev => el.dispatchEvent(new MouseEvent(ev, {
                    bubbles: true, cancelable: true, view: window
                })));
            try { el.click(); } catch (e) {}
            return {clicked: true, text: norm(el.textContent || el.getAttribute('aria-label')).slice(0, 50)};
        }
    }
    return {clicked: false};
}
"""


# --- "Meta → Instagram" flow ------------------------------------------------
# Creates a Meta account (auth.meta.com) with a browser-driven mail.td inbox,
# confirms it by email code, then creates the Instagram account with that same
# Meta account. Human checks (reCAPTCHA / image code / selfie) are surfaced to
# the user, who solves them in the visible browser; the flow waits and resumes.

_META_AUTH_URL = "https://auth.meta.com/"
_META_AI_URL = "https://www.meta.ai/"
_META_AI_APEX = "https://meta.ai/"
_META_POST_URL = (
    "https://auth.meta.com/?waterfall_id=a552040e-c796-4049-b51d-ba27ed09b88a"
    "&redirect_uri=https%3A%2F%2Fauth.meta.com%2Foidc%2F%3Fapp_id%3D1522763855472543"
    "%26redirect_uri%3Dhttps%253A%252F%252Fauth.meta.ai%252Fecto%26response_type%3Dcode"
    "%26scope%3Dopenid%252Blinking%26state%3DeyJjc3JmX3Rva2VuIjoic3BWaGlCMVBxR2J1RXdqZGNL"
    "djFGNlpkOVc3UUhZdHg2LXVTdzRGb0M0OCIsInJlZGlyZWN0X3RvIjoiaHR0cHM6Ly93d3cubWV0YS5haS9"
    "vaWRjL2NhbGxiYWNrIiwic3RhcnRlZF9hdCI6MTc4ODUwMDM2NTMwNywid2F0ZXJmYWxsX2lkIjoiYTU1"
    "MjA0MGUtYzc5Ni00MDQ5LWI1MWQtYmEyN2VkMDliODhhIn0%253D%26waterfall_id%3Da552040e-c796-4049"
    "-b51d-ba27ed09b88a%26code_challenge%3DFPDmfOIZAD-SabmPfFp5ncXlW5BckyIl-ONacvVO_AE"
    "%26code_challenge_method%3DS256&source_app_id=1522763855472543&force_reauth=0"
    "&rcs=ATpGj6uc0wSwRKfKt4r0d13LoBJ__NFx0MbR2e7oKl5u52MwdsjJeOFLijjoT0Hh8DlghJfF307PuNf18j1CDUrVYCEIDQvOsklJMII4tsp1pY43PmF1N-z46zsRuIpr0tMMa_o0aQQG3hyCTtbuaLYy28X17J711RLGmDzzA42tmomLjynfBfrkv0k"
)
_MAILTD_URL = "https://mail.td/"
_IG_LOGIN_URL = "https://www.instagram.com/accounts/login/"
_IG_SIGNUP_URL = "https://www.instagram.com/accounts/emailsignup/"

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]

_HUMAN_TEXTS = [
    "Confirm you're human",
    "Confirm that you're human",
    "Upload a verification selfie",
    "Enter the code from the image",
]


_ANTIDETECT_TEMPLATE = r"""
(function() {
  'use strict';
  const CONFIG = __CONFIG__;
  const isMobile = CONFIG.type === 'ANDROID_MOBILE';
  const defaultUA = isMobile
    ? 'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
    : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';
  const userAgent = CONFIG.userAgent || defaultUA;
  const appVersion = CONFIG.appVersion || userAgent.replace(/^Mozilla\//, '');
  const platform = CONFIG.platform || (isMobile ? 'Linux armv8l' : 'Win32');
  const vendor = CONFIG.vendor || 'Google Inc.';
  const hardwareConcurrency = CONFIG.hardwareConcurrency || 8;
  const deviceMemory = CONFIG.deviceMemory || 8;
  const maxTouchPoints = typeof CONFIG.maxTouchPoints === 'number'
    ? CONFIG.maxTouchPoints : (isMobile ? 5 : 0);
  const languages = Object.freeze(
    Array.isArray(CONFIG.network && CONFIG.network.languages) && CONFIG.network.languages.length > 0
      ? CONFIG.network.languages : ['en-US', 'en']);
  const language = (CONFIG.network && CONFIG.network.languages && CONFIG.network.languages[0]) || 'en-US';
  const nav = { userAgent, appVersion, platform, vendor, hardwareConcurrency,
                deviceMemory, maxTouchPoints, languages, language };
  if (isMobile) { nav.ontouchstart = function() {}; }
  for (const key of Object.keys(nav)) {
    try { Object.defineProperty(navigator, key, { get: () => nav[key], configurable: true, enumerable: true }); } catch(e) {}
  }
  try {
    const brands = [{ brand: 'Chromium', version: CONFIG.chMajor || '124' },
                    { brand: 'Google Chrome', version: CONFIG.chMajor || '124' },
                    { brand: 'Not-A.Brand', version: '99' }];
    const uaDataMock = isMobile
      ? { brands, mobile: true, platform: 'Android',
          getHighEntropyValues: async function() { return { architecture: '', bitness: '', brands,
            fullVersionList: [{ brand: 'Chromium', version: (CONFIG.chFull || '124.0.6367.82') },
                              { brand: 'Google Chrome', version: (CONFIG.chFull || '124.0.6367.82') }],
            mobile: true, model: (CONFIG.device && CONFIG.device.model) || 'SM-G998B',
            platform: 'Android', platformVersion: (CONFIG.device && CONFIG.device.androidVersion) || '13',
            uaFullVersion: (CONFIG.chFull || '124.0.6367.82') }; } }
      : { brands, mobile: false, platform: 'Windows',
          getHighEntropyValues: async function() { return { architecture: 'x86', bitness: '64', brands,
            fullVersionList: [{ brand: 'Chromium', version: '124.0.6367.82' },
                              { brand: 'Google Chrome', version: '124.0.6367.82' }],
            mobile: false, model: '', platform: 'Windows', platformVersion: '10.0.0',
            uaFullVersion: '124.0.6367.82' }; } };
    Object.defineProperty(navigator, 'userAgentData', { get: () => uaDataMock, configurable: true, enumerable: true });
  } catch(e) {}
  try {
    const screenWidth = (CONFIG.screen && CONFIG.screen.width) || (isMobile ? 393 : 1920);
    const screenHeight = (CONFIG.screen && CONFIG.screen.height) || (isMobile ? 852 : 1080);
    const pixelRatio = (CONFIG.screen && CONFIG.screen.pixelRatio) || (isMobile ? 3 : 1);
    Object.defineProperty(window, 'screen', { value: {
      width: screenWidth, height: screenHeight, availWidth: screenWidth, availHeight: screenHeight,
      colorDepth: 24, pixelDepth: 24,
      orientation: isMobile ? { type: 'portrait-primary', angle: 0 } : { type: 'landscape-primary', angle: 0 }
    }, configurable: true });
    Object.defineProperty(window, 'devicePixelRatio', { get: () => pixelRatio });
    if (isMobile) {
      if (typeof window.TouchEvent === 'undefined') { window.TouchEvent = function TouchEvent() {}; }
      window.ontouchstart = function() {};
      if (typeof document !== 'undefined') { document.ontouchstart = function() {}; }
    }
  } catch(e) {}
  if (isMobile) {
    function enforceMobileLayout() {
      try {
        if (typeof document === 'undefined') return;
        const screenWidth = (CONFIG.screen && CONFIG.screen.width) || 393;
        let meta = document.querySelector('meta[name="viewport"]');
        if (!meta) { meta = document.createElement('meta'); meta.name = 'viewport';
          if (document.head) document.head.appendChild(meta); }
        meta.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
        const style = document.createElement('style');
        style.id = 'antidetect-mobile-style';
        style.innerHTML = 'html, body { max-width: ' + screenWidth + 'px !important; margin: 0 auto !important; overflow-x: hidden !important; }' +
                          'body._a9-- { max-width: 100% !important; } section._a9_0 { width: 100% !important; max-width: 100% !important; }';
        if (document.head && !document.getElementById('antidetect-mobile-style')) { document.head.appendChild(style); }
      } catch(e) {}
    }
    if (typeof document !== 'undefined') {
      if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', enforceMobileLayout); }
      else { enforceMobileLayout(); }
    }
  }
  try {
    const raw = (CONFIG.noise && CONFIG.noise.canvas) != null ? CONFIG.noise.canvas : 0.0001;
    const nR = typeof raw === 'object' ? (raw.r != null ? raw.r : 0.0001) : raw;
    const nG = typeof raw === 'object' ? (raw.g != null ? raw.g : 0.0001) : raw;
    const nB = typeof raw === 'object' ? (raw.b != null ? raw.b : 0.0001) : raw;
    if (typeof CanvasRenderingContext2D !== 'undefined') {
      const orig = CanvasRenderingContext2D.prototype.getImageData;
      CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
        const d = orig.apply(this, arguments);
        for (let i = 0; i < d.data.length; i += 4) {
          d.data[i] = Math.min(255, Math.max(0, d.data[i] + (nR * 255)));
          d.data[i+1] = Math.min(255, Math.max(0, d.data[i+1] + (nG * 255)));
          d.data[i+2] = Math.min(255, Math.max(0, d.data[i+2] + (nB * 255)));
        }
        return d;
      };
    }
    if (typeof HTMLCanvasElement !== 'undefined') {
      const o2 = HTMLCanvasElement.prototype.toDataURL;
      HTMLCanvasElement.prototype.toDataURL = function(type) {
        const ctx = this.getContext('2d');
        if (ctx) { try { const d = ctx.getImageData(0, 0, this.width, this.height); ctx.putImageData(d, 0, 0); } catch(e) {} }
        return o2.apply(this, arguments);
      };
    }
  } catch(e) {}
  try {
    const gpuVendor = (CONFIG.device && CONFIG.device.gpu && CONFIG.device.gpu.vendor) || (isMobile ? 'Qualcomm' : 'Google Inc. (NVIDIA)');
    const gpuRenderer = (CONFIG.device && CONFIG.device.gpu && CONFIG.device.gpu.renderer) || (isMobile ? 'Adreno (TM) 660' : 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)');
    const proxy = function(orig) {
      return function(p) {
        if (p === 37445) return gpuVendor;
        if (p === 37446) return gpuRenderer;
        if (p === 7936) return 'WebKit';
        if (p === 7937) return 'WebKit WebGL';
        return orig.apply(this, arguments);
      };
    };
    if (typeof WebGLRenderingContext !== 'undefined') { WebGLRenderingContext.prototype.getParameter = proxy(WebGLRenderingContext.prototype.getParameter); }
    if (typeof WebGL2RenderingContext !== 'undefined') { WebGL2RenderingContext.prototype.getParameter = proxy(WebGL2RenderingContext.prototype.getParameter); }
  } catch(e) {}
  try {
    const audioNoise = (CONFIG.noise && typeof CONFIG.noise.audio === 'number') ? CONFIG.noise.audio : 0.0001;
    if (typeof AudioBuffer !== 'undefined') {
      const orig = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = function() {
        const res = orig.apply(this, arguments);
        for (let i = 0; i < res.length; i += 100) { res[i] = res[i] + audioNoise; }
        return res;
      };
    }
  } catch(e) {}
  try {
    if (CONFIG.network && CONFIG.network.webrtc === 'BLOCK') {
      if (typeof window.RTCPeerConnection !== 'undefined') {
        window.RTCPeerConnection = function() { throw new Error('WebRTC Disabled by Anti-Detect Engine'); };
      }
      if (typeof window.webkitRTCPeerConnection !== 'undefined') {
        window.webkitRTCPeerConnection = function() { throw new Error('WebRTC Disabled by Anti-Detect Engine'); };
      }
    }
  } catch(e) {}
  try {
    const geo = CONFIG.network && CONFIG.network.geolocation;
    if (navigator.geolocation && geo) {
      navigator.geolocation.getCurrentPosition = function(success) {
        if (success) success({ coords: { latitude: geo.latitude, longitude: geo.longitude,
          accuracy: geo.accuracy || 15, altitude: null, altitudeAccuracy: null, heading: null, speed: null },
          timestamp: Date.now() });
      };
      navigator.geolocation.watchPosition = function(success, error, options) {
        navigator.geolocation.getCurrentPosition(success, error, options); return 1;
      };
    }
  } catch(e) {}
  try {
    const tz = CONFIG.network && CONFIG.network.timezone;
    if (tz && typeof Intl !== 'undefined' && Intl.DateTimeFormat) {
      const O = Intl.DateTimeFormat;
      Intl.DateTimeFormat = function(locale, options) {
        const opts = Object.assign({}, options || {});
        opts.timeZone = opts.timeZone || tz;
        return new O(locale, opts);
      };
      Intl.DateTimeFormat.prototype = O.prototype;
      if (typeof O.supportedLocalesOf === 'function') { Intl.DateTimeFormat.supportedLocalesOf = O.supportedLocalesOf.bind(O); }
    }
  } catch(e) {}
})();
"""

# Hardened Chrome flags for anti-detect persistent contexts.
_NOVA_FLAGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",
    # NOTE: the "=gpu" value matters — bare --test-type does NOT suppress the
    # "Chrome for Testing v... is only for automated testing" startup banner
    # on Windows, --test-type=gpu does.
    "--test-type=gpu",
    "--silent-debugger-extension-api",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--touch-events=enabled",
    "--enable-viewport",
    "--disable-save-password-bubble",
    "--disable-session-crashed-bubble",
    "--hide-crash-restore-bubble",
    # Explicit even though recent Playwright also passes it by default:
    # suppresses the automation / Chrome-for-Testing infobar.
    "--disable-infobars",
    "--disable-features=PasswordManager,AutofillServerCommunication,PasswordGeneration,BackForwardCache,Translate,MediaRouter,IsolateOrigins,site-per-process",
    "--password-store=basic",
]
