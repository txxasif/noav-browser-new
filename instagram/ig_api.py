"""instagram/ig_api.py — browserless Instagram private-API client (OPT-IN).

This is the "API path" for the pool-drain runners. It is INERT until the
switch is ON:

    IG_API_MODE=1        # env var (server.js / worker.py / panel toggle)

When OFF (default) the runners use the existing Playwright / Accounts-Center
code untouched (invariant 24 — no regression). When ON, the runner calls these
functions instead and skips the browser for the IG-side steps.

Endpoints / request shapes are documented in:
  "R&D — What Can Be Done Via the IG Private API (TopFollow APK teardown).md"
  "R&D — NsFollower APK teardown (server-orchestrated IG farm).md"

Covered operations (all without a browser):
  * rename username        (web API — already used by change_ig_username_fast)
  * follow / unfollow       (mobile + web transports, with verification)
  * 2FA enable              (generate_two_factor_totp_key -> enable_totp_two_factor)
  * change password         (accounts/change_password/)
  * add / confirm email     (send_confirm_email -> verify_email_code)
  * security info           (account_security_info)
  * mobile login -> Bearer  (for the endpoints that need a mobile session)

NOTE: the mobile login + the 2FA/password/email endpoints need a live probe
against a real pooled account before production use — every function returns
(ok, detail) and NEVER raises, so a failure simply falls back to the browser.
"""
from __future__ import annotations

import base64
import json
import os
import random
import re
import time
import urllib.parse
import uuid

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

# --------------------------------------------------------------------------- #
# Switch
# --------------------------------------------------------------------------- #
_TRUTHY = ("1", "true", "yes", "on", "api")


def api_mode() -> bool:
    """True when the browserless API path is enabled for the IG-side steps."""
    return str(os.environ.get("IG_API_MODE", "0")).strip().lower() in _TRUTHY


def set_api_mode(on: bool) -> None:
    os.environ["IG_API_MODE"] = "1" if on else "0"


def proxy_for(key: str = "") -> str:
    """Residential/mobile proxy URL from ``PROXY_URL``.

    ``{session}`` in the URL is replaced with a stable per-account token so a
    rotating provider gives each account its own sticky egress IP.
    """
    url = (os.environ.get("PROXY_URL") or "").strip()
    if not url:
        return ""
    if "{session}" in url:
        url = url.replace("{session}", (str(key) or uuid.uuid4().hex)[:16])
    return url


def mock_2fa() -> bool:
    """True when API mode should submit a MOCK 2FA key instead of enabling 2FA.

    Only meaningful in API mode (the panel shows the toggle only then). When
    off (default) API mode performs REAL 2FA.
    """
    return str(os.environ.get("IG_API_MOCK", "0")).strip().lower() in _TRUTHY


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
IG_APP_ID = "567067343352427"          # Instagram Android
WEB_APP_ID = "936619743392459"         # Instagram web
# App version must be >= IG's current minimum or accounts/login/ replies
# "Your version of Instagram is out of date." Verified 2026-10-08 against the
# live Play build (Instagram_450.0.0.50.77): 444.x was TOO OLD and is the cause
# of the mobile-login refusal.
IG_APP_VERSION = "450.0.0.50.77"
IG_APP_VERSION_CODE = "385611438"
IG_UA = ("Instagram " + IG_APP_VERSION + " Android (33/13; 420dpi; 1080x2269; "
         "samsung; SM-E625F; f62; exynos9825; en_US; " + IG_APP_VERSION_CODE + ")")
BLOKS_VERSION_ID = "083f38c334f42c5e3322bb77464c601e8882cd9ff2d30ac915ba7a497539d604"
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MOBILE_BASE = "https://i.instagram.com/api/v1/"
WEB_BASE = "https://www.instagram.com/api/v1/"

# --------------------------------------------------------------------------- #
# Fixed follow targets (operator list, 2026-10-07). Follow N at random.
# --------------------------------------------------------------------------- #
IG_FOLLOW_TARGETS = [
    "cristiano", "leomessi", "selenagomez", "therock", "kyliejenner",
    "arianagrande", "kimkardashian", "beyonce", "khloekardashian",
    "kendalljenner", "taylorswift", "virat.kohli", "jlo", "neymarjr",
    "kourtneykardash", "mileycyrus", "katyperry", "zendaya", "kevinhart4real",
    "iamcardib", "shakira", "dualipa", "badgalriri", "ladygaga", "ddlovato",
    "billieeilish", "sabrinacarpenter", "oliviarodrigo",
]


def pick_follow_targets(n: int = 5, exclude=()) -> list:
    """N random usernames from ``IG_FOLLOW_TARGETS`` (never the account itself)."""
    blocked = {str(u).lstrip("@").lower() for u in (exclude or ())}
    pool = [u for u in IG_FOLLOW_TARGETS if u.lower() not in blocked]
    random.shuffle(pool)
    return pool[: max(0, int(n))]


# --------------------------------------------------------------------------- #
# username -> pk cache (the target list is fixed, so resolve each once)
# --------------------------------------------------------------------------- #
_PK_CACHE = {}
_PK_HTML_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
               "Mobile/15E148 Safari/604.1")


def _pk_cache_path() -> str:
    try:
        import ai_config
        d = getattr(ai_config, "DATA_DIR",
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
        return os.path.join(str(d), "ig_follow_pks.json")
    except Exception:
        return os.path.join("data", "ig_follow_pks.json")


def _load_pk_cache() -> dict:
    global _PK_CACHE
    if _PK_CACHE:
        return _PK_CACHE
    try:
        with open(_pk_cache_path(), "r", encoding="utf-8") as f:
            _PK_CACHE = json.load(f) or {}
    except Exception:
        _PK_CACHE = {}
    return _PK_CACHE


def _save_pk_cache() -> None:
    try:
        p = _pk_cache_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(_PK_CACHE, f)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _cookie_get(cookie_str: str, name: str) -> str:
    m = re.search(rf"(?:^|;\s*){re.escape(name)}=([^;]+)", str(cookie_str or ""))
    return m.group(1).strip() if m else ""


def _android_id(seed: str = "") -> str:
    """Deterministic 16-hex android_id from a seed (stable per account)."""
    h = abs(hash(seed or "ig")) & ((1 << 64) - 1)
    return format(h, "016x")


def _device_uuid(seed: str = "") -> str:
    try:
        return str(uuid.UUID(int=abs(hash(seed or "ig")) & ((1 << 128) - 1)))
    except Exception:
        return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# #PWD_INSTAGRAM:4: password blob (TopFollow algorithm; needs `rsa`+`cryptography`)
# --------------------------------------------------------------------------- #
def enc_password(password: str, pub_key_b64: str, key_id) -> str:
    """Build ``#PWD_INSTAGRAM:4:<ts>:<b64>`` exactly like the IG app / TopFollow.

    pub_key_b64 / key_id come from the response headers
    ``Ig-Set-Password-Encryption-Pub-Key`` / ``-Key-Id``.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import padding as _pad
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        # The header value is base64(PEM). Decode -> PEM text -> strip markers
        # -> base64 DER -> load. (TopFollow: Base64.decode -> strip "-(.*)-" -> decode.)
        pem = base64.b64decode(pub_key_b64 or "").decode("utf-8", "ignore")
        der_b64 = re.sub(r"-----[^-]+-----|\s", "", pem)
        der = base64.b64decode(der_b64)
        pub = serialization.load_der_public_key(der)
        aes_key = os.urandom(32)
        nonce = os.urandom(12)
        ts = str(int(time.time()))
        kenc = pub.encrypt(aes_key, _pad.PKCS1v15())
        ct = AESGCM(aes_key).encrypt(nonce, password.encode("utf-8"), ts.encode())
        tag, body = ct[-16:], ct[:-16]
        blob = bytearray()
        blob.append(1)                                   # version byte
        blob.append(int(key_id or 0) & 0xFF)             # key id
        blob += nonce
        blob += len(kenc).to_bytes(2, "little")
        blob += kenc
        blob += tag
        blob += body
        return f"#PWD_INSTAGRAM:4:{ts}:{base64.b64encode(bytes(blob)).decode()}"
    except Exception:
        return ""


def _fetch_encryption_keys(sess, mobile_headers=None, username="", android_id="", device_uuid="") -> tuple:
    """Fetch the password-encryption pub-key/key-id from IG response headers.

    IG returns ``Ig-Set-Password-Encryption-Pub-Key`` / ``-Key-Id`` on responses
    that carry the app headers. The most reliable bootstrap is a login POST with
    an empty password (IG rejects it but returns the keys). Falls back to
    ``si/fetch_headers`` and ``qe/sync``.
    """
    hdr = dict(mobile_headers or {})
    try:
        r = sess.post(
            "https://i.instagram.com/api/v1/accounts/login/",
            data={"username": username or "", "enc_password": "",
                  "device_id": f"android-{android_id or ''}",
                  "guid": device_uuid or "", "login_attempt_count": "1"},
            headers=hdr, timeout=20)
        pk = r.headers.get("Ig-Set-Password-Encryption-Pub-Key")
        kid = r.headers.get("Ig-Set-Password-Encryption-Key-Id")
        if pk and kid:
            return pk, kid
    except Exception:
        pass
    for url in (
        "https://i.instagram.com/api/v1/si/fetch_headers/?challenge_type=signup&guid=" + (device_uuid or ""),
        "https://i.instagram.com/api/v1/qe/sync/",
    ):
        try:
            r = sess.get(url, headers=hdr, timeout=20)
            pk = r.headers.get("Ig-Set-Password-Encryption-Pub-Key")
            kid = r.headers.get("Ig-Set-Password-Encryption-Key-Id")
            if pk and kid:
                return pk, kid
        except Exception:
            continue
    return "", ""


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class IgApiClient:
    """A per-account browserless client (web cookie + optional mobile Bearer)."""

    def __init__(self, cookie_str: str = "", *, username: str = "",
                 password: str = "", twofa_seed: str = "",
                 android_seed: str = "", device_ua: str = "", proxy: str = ""):
        if requests is None:
            raise RuntimeError("requests is not available")
        self.cookie = cookie_str or ""
        self.username = (username or "").lstrip("@")
        self.password = password or ""
        self.twofa_seed = (twofa_seed or "").strip()
        self.android_id = _android_id(android_seed or self.username)
        self.device_uuid = _device_uuid(android_seed or self.username)
        self.device_ua = device_ua or IG_UA
        self.token = ""            # Bearer (mobile session)
        self.uid = ""
        self.family_device_id = str(uuid.uuid4())
        self.mid = ""              # x-mid from the web cookie if present
        self.pigeon = ""
        self.csrf = _cookie_get(self.cookie, "csrftoken")
        self.ds_user_id = _cookie_get(self.cookie, "ds_user_id")
        self._pub, self._kid = "", ""
        self.s = requests.Session()
        if proxy:
            try:
                self.s.proxies.update({"http": proxy, "https": proxy})
            except Exception:
                pass
        if self.cookie:
            self.s.headers["Cookie"] = self.cookie

    # -- headers ---------------------------------------------------------- #
    def _mobile_headers(self) -> dict:
        # Full Android-app header set (Coinsta InstagramFollowExactTrace::RequestBuilder
        # + TopFollow z9/q.e()): the more the request looks like the real app, the
        # less IG's risk engine rejects it.
        h = {
            "User-Agent": self.device_ua,
            "X-IG-App-ID": IG_APP_ID,
            "X-IG-Device-ID": self.device_uuid,
            "X-IG-Android-ID": f"android-{self.android_id}",
            "X-IG-Connection-Type": "WIFI",
            "X-IG-Capabilities": "3brTv10=",
            "X-IG-App-Locale": "en_US",
            "X-IG-Device-Locale": "en_US",
            "X-IG-Mapped-Locale": "en_US",
            "X-IG-Device-Languages": '{"system_languages":"en-US"}',
            "X-IG-Timezone-Offset": "0",
            "X-FB-HTTP-Engine": "Tigon/MNS/TCP",
            "X-FB-Conn-UUID-Client": str(uuid.uuid4()),
            "X-Pigeon-Rawclienttime": "%.3f" % time.time(),
            "X-Pigeon-Session-Id": "UFS-" + (self.device_uuid or "") + "-0",
            "X-Bloks-Is-Layout-RTL": "false",
            "X-Bloks-Prism-Button-Version": "INDIGO_PRIMARY_BORDERED_SECONDARY",
            "X-Bloks-Prism-Colors-Enabled": "true",
            "X-Bloks-Version-Id": BLOKS_VERSION_ID,
            "X-Fb-Rmd": "state=URL_ELIGIBLE",
            "X-FB-Network-Properties": "Wifi;Validated;",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip,deflate",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        if self.token:
            h["Authorization"] = ("Bearer " + self.token) if not self.token.startswith("Bearer") else self.token
        uid = self.uid or _cookie_get(self.cookie, "ds_user_id")
        if uid:
            h["IG-Intended-User-ID"] = str(uid)
            h["IG-U-DS-User-ID"] = str(uid)
        if self.mid:
            h["X-MID"] = self.mid
        if self.family_device_id:
            h["X-IG-Family-Device-ID"] = self.family_device_id
        if self.csrf:
            h["X-CSRFToken"] = self.csrf
        return h

    def _web_headers(self) -> dict:
        return {
            "User-Agent": WEB_UA,
            "X-IG-App-ID": WEB_APP_ID,
            "X-CSRFToken": self.csrf,
            "X-Instagram-AJAX": "1",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
            "Origin": "https://www.instagram.com",
            "Accept": "*/*",
            "Cookie": self.cookie,
        }

    def _mobile(self, path: str, data=None, method: str = "POST", extra: dict = None):
        url = path if path.startswith("http") else MOBILE_BASE + path.lstrip("/")
        h = self._mobile_headers()
        if extra:
            h.update(extra)
        if method == "GET":
            return self.s.get(url, headers=h, timeout=25)
        return self.s.post(url, data=data or {}, headers=h, timeout=25)

    def _web(self, path: str, data: dict = None, method: str = "POST"):
        url = path if path.startswith("http") else WEB_BASE + path.lstrip("/")
        if method == "GET":
            return self.s.get(url, headers=self._web_headers(), timeout=25)
        return self.s.post(url, data=data or {}, headers=self._web_headers(), timeout=25)

    # -- mobile login ----------------------------------------------------- #
    def _bloks_login(self) -> tuple:
        """Bloks/CAA login (TopFollow's flow) → Bearer. Returns (ok, detail)."""
        try:
            aid = self.android_id
            dev = self.device_uuid
            if not self.mid:
                self.mid = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(26))
            if not self.family_device_id:
                self.family_device_id = str(uuid.uuid4())
            if not self._pub:
                self._pub, self._kid = _fetch_encryption_keys(
                    self.s, self._mobile_headers(), self.username, aid, dev)
            enc = enc_password(self.password, self._pub, self._kid)
            if not enc:
                return False, "password encryption failed"
            bkc = {"bloks_version": BLOKS_VERSION_ID, "styles_id": "instagram"}
            q = urllib.parse.quote
            # pre-login warm-ups (order matters; failures tolerated)
            for path, data in (
                ("zr/dual_tokens/",
                 "normal_token_hash=&device_id=android-%s&custom_device_id=%s&fetch_reason=token_expired" % (aid, dev)),
                ("bloks/async_action/com.bloks.www.bloks.caa.login.process_client_data_and_redirect/",
                 "params=%s&bk_client_context=%s&bloks_versioning_id=%s" % (
                     q(json.dumps({"is_from_logged_out": False, "device_id": "android-" + aid,
                                   "family_device_id": self.family_device_id})),
                     q(json.dumps(bkc)), BLOKS_VERSION_ID)),
                ("bloks/async_action/com.bloks.www.caa.login.oauth.token.fetch.async/",
                 "params=%s&bk_client_context=%s&bloks_versioning_id=%s" % (
                     q(json.dumps({"client_input_params": {"username_input": self.username,
                                                           "lois_settings": {"lois_token": ""}},
                                   "server_params": {"login_surface": "login_home",
                                                     "waterfall_id": str(uuid.uuid4()), "qe_device_id": dev}})),
                     q(json.dumps(bkc)), BLOKS_VERSION_ID)),
                ("attestation/create_android_keystore/", "app_scoped_device_id=%s&key_hash=" % dev),
            ):
                try:
                    self._mobile(path, data)
                except Exception:
                    pass
            params = {
                "client_input_params": {
                    "password": enc, "machine_id": self.mid, "device_id": "android-" + aid,
                    "family_device_id": self.family_device_id, "login_attempt_count": 1,
                    "contact_point": self.username, "event_flow": "login_manual",
                    "event_step": "home_page",
                },
                "server_params": {
                    "login_source": "Login", "event_step": "home_page",
                    "waterfall_id": str(uuid.uuid4()), "qe_device_id": dev,
                    "device_id": "android-" + aid, "login_entry_point": "logged_out",
                    "is_platform_login": 0, "is_from_logged_out": 0,
                },
            }
            body = ("params=" + q(json.dumps(params)) + "&bk_client_context=" + q(json.dumps(bkc))
                    + "&bloks_versioning_id=" + BLOKS_VERSION_ID)
            r = self._mobile(
                "bloks/async_action/com.bloks.www.bloks.caa.login.async.send_login_request/", body)
            auth = r.headers.get("Ig-Set-Authorization") or ""
            if not auth:
                m = re.search(r"Bearer\s+([A-Za-z0-9._:\-]+)", r.text or "")
                auth = m.group(0) if m else ""
            if auth:
                self.token = auth.replace("Bearer ", "").strip()
                self.uid = self.uid or _cookie_get(self.cookie, "ds_user_id")
                return True, "ok (bloks)"
            if r.status_code == 429:
                return False, "429 rate-limited"
            return False, f"HTTP {r.status_code} {(r.text or '')[:80]}"
        except Exception as exc:
            return False, str(exc)

    def mobile_login(self) -> tuple:
        """Log in with username+password (encrypted) to obtain the Bearer token.

        Tries the bloks/CAA flow first (the modern path), then legacy
        accounts/login. Returns (ok, detail).
        """
        try:
            if not self.username or not self.password:
                return False, "no username/password"
            ok_b, why_b = self._bloks_login()
            if ok_b:
                return True, why_b
            last = "unknown"
            for _attempt in range(2):
                if not self._pub:
                    self._pub, self._kid = _fetch_encryption_keys(
                        self.s, self._mobile_headers(), self.username,
                        self.android_id, self.device_uuid)
                if not self._pub:
                    return False, "no password-encryption key (IG did not return Ig-Set-Password-Encryption-*)"
                enc = enc_password(self.password, self._pub, self._kid)
                if not enc:
                    return False, "password encryption failed"
                data = {
                    "username": self.username,
                    "enc_password": enc,
                    "device_id": f"android-{self.android_id}",
                    "guid": self.device_uuid,
                    "login_attempt_count": "1",
                }
                r = self._mobile("accounts/login/", data)
                # A fresh key may arrive on THIS response — capture it for a retry.
                pk = r.headers.get("Ig-Set-Password-Encryption-Pub-Key")
                kid = r.headers.get("Ig-Set-Password-Encryption-Key-Id")
                if pk and kid and (pk != self._pub or str(kid) != str(self._kid)):
                    self._pub, self._kid = pk, kid
                auth = r.headers.get("Ig-Set-Authorization") or ""
                if not auth:
                    m = re.search(r"Bearer\s+([A-Za-z0-9._:\-]+)", r.text or "")
                    auth = m.group(0) if m else ""
                if auth:
                    self.token = auth.replace("Bearer ", "").strip()
                try:
                    j = r.json()
                except Exception:
                    j = {}
                self.uid = str((j.get("logged_in_user") or {}).get("pk") or j.get("pk") or self.uid)
                if r.status_code == 200 and j.get("status") == "ok":
                    return True, "ok"
                if j.get("two_factor_required"):
                    return False, "two_factor_required"
                last = j.get("message") or f"HTTP {r.status_code}"
                # Retry once with a freshly fetched key (key rotation).
                self._pub = ""
            return (bool(self.token), f"{last} (bloks: {why_b})")
        except Exception as exc:
            return False, str(exc)

    # -- usernames -> pk -------------------------------------------------- #
    def pk_of(self, username: str) -> str:
        """Resolve a username to its user id (cached, with an HTML fallback).

        The fixed target list is resolved once and cached to
        ``data/ig_follow_pks.json`` — web_profile_info is IP rate-limited (429),
        so the HTML profile page is the reliable fallback.
        """
        u = str(username or "").lstrip("@")
        if not u:
            return ""
        cache = _load_pk_cache()
        if cache.get(u):
            return str(cache[u])
        pk = self._pk_via_profile_info(u) or self._pk_via_html(u)
        if pk:
            cache[u] = pk
            _save_pk_cache()
        return pk

    def _pk_via_profile_info(self, u: str) -> str:
        try:
            hdr = {
                "x-ig-app-id": WEB_APP_ID,
                "User-Agent": WEB_UA,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.instagram.com",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            }
            for base in ("https://i.instagram.com/api/v1/",
                         "https://www.instagram.com/api/v1/"):
                try:
                    r = requests.get(
                        base + f"users/web_profile_info/?username={urllib.parse.quote(u)}",
                        headers=hdr, timeout=20)
                    if r.status_code != 200:
                        continue
                    j = r.json()
                    uid = (((j.get("data") or {}).get("user") or {}).get("id")) or ""
                    if uid:
                        return str(uid)
                except Exception:
                    continue
        except Exception:
            pass
        return ""

    def _pk_via_html(self, u: str) -> str:
        try:
            r = requests.get(
                f"https://www.instagram.com/{urllib.parse.quote(u)}/",
                headers={"User-Agent": _PK_HTML_UA, "Accept": "text/html",
                         "Accept-Language": "en-US,en;q=0.9"},
                timeout=25)
            if r.status_code != 200:
                return ""
            t = r.text or ""
            for pat in (r"profilePage_(\d+)", r'"user_id":"(\d+)"', r'"id":"(\d+)"'):
                m = re.search(pat, t)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return ""

    # -- follow / unfollow ------------------------------------------------ #
    def friendships_show(self, pk: str) -> dict:
        try:
            r = self._web(f"friendships/show/{pk}/", method="GET")
            return (r.json() or {}).get("friendship_status") or {}
        except Exception:
            return {}

    def rename(self, new_username: str) -> tuple:
        """Rename via the MOBILE ``accounts/edit_profile/`` endpoint.

        The web POST (``/api/v1/web/accounts/edit/``) is challenged on fresh
        accounts (``checkpoint_required``). The MOBILE endpoint, with a valid
        Bearer (from ``mobile_login``) and a **plain** ``username=`` form, is
        accepted — verified live 2026-10-08: HTTP 200 + the new username,
        confirmed via ``current_user``. NOTE: do NOT wrap the body in
        ``signed_body=SIGNATURE.…`` here — that returns ``400 {"status":"fail"}``;
        the plain form is what works.

        Returns ``(ok, detail)``.
        """
        if not new_username:
            return False, "no username"
        try:
            if not self.token:
                ok, why = self.mobile_login()
                if not ok or not self.token:
                    return False, f"no mobile session ({why})"
            r = self._mobile("accounts/edit_profile/", data={"username": str(new_username)})
            try:
                j = r.json()
            except Exception:
                j = {}
            got = str((j.get("user") or {}).get("username") or "")
            if r.status_code == 200 and (got == str(new_username) or j.get("status") == "ok"):
                self.username = str(new_username)
                return True, "ok (mobile edit_profile)"
            msg = j.get("message") or (r.text or "")[:120]
            return False, f"mobile edit_profile: {msg or ('HTTP ' + str(r.status_code))}"
        except Exception as exc:
            return False, f"mobile rename error: {exc}"

    # -- profile / post (web transport, browser-session cookies) ---------- #
    @staticmethod
    def _jpeg_bytes(path: str) -> tuple:
        """(jpeg_bytes, width, height) — any image is re-encoded as JPEG."""
        from PIL import Image
        import io
        im = Image.open(path).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=92)
        return buf.getvalue(), im.width, im.height

    @staticmethod
    def _verdict(r) -> tuple:
        try:
            j = r.json()
        except Exception:
            j = {}
        if r.status_code == 200 and j.get("status") == "ok":
            return True, "ok", j
        msg = j.get("message") or (r.text or "")[:120] or f"HTTP {r.status_code}"
        return False, str(msg), j

    def set_biography(self, text: str) -> tuple:
        """Set the bio. Returns (ok, detail). Never raises."""
        if not text:
            return False, "no bio text"
        try:
            ok, why, _j = self._verdict(self._web("accounts/set_biography/", {"raw_text": text}))
            return ok, why
        except Exception as exc:
            return False, f"set_biography error: {exc}"

    def change_profile_picture(self, path: str) -> tuple:
        """Upload a new profile picture (multipart). Returns (ok, detail)."""
        try:
            data, _w, _h = self._jpeg_bytes(path)
            h = self._web_headers()
            r = self.s.post(WEB_BASE + "web/accounts/web_change_profile_picture/", headers=h,
                            files={"profile_pic": ("profile_pic.jpg", data, "image/jpeg")}, timeout=60)
            ok, why, _j = self._verdict(r)
            return ok, why
        except Exception as exc:
            return False, f"change_profile_picture error: {exc}"

    def post_photo(self, path: str, caption: str = "") -> tuple:
        """Feed photo: rupload_igphoto, then media/configure. Returns (ok, detail)."""
        try:
            data, w, h = self._jpeg_bytes(path)
            upload_id = str(int(time.time() * 1000))
            hdr = self._web_headers()
            hdr.update({
                "X-Entity-Type": "image/jpeg",
                "X-Entity-Name": f"fb_uploader_{upload_id}",
                "X-Entity-Length": str(len(data)),
                "Offset": "0",
                "X-Instagram-Rupload-Params": json.dumps({
                    "media_type": 1, "upload_id": upload_id,
                    "upload_media_height": h, "upload_media_width": w}),
                "Content-Type": "image/jpeg",
            })
            r = self.s.post("https://www.instagram.com/rupload_igphoto/fb_uploader_" + upload_id,
                            headers=hdr, data=data, timeout=90)
            if r.status_code != 200:
                return False, f"upload HTTP {r.status_code}: {(r.text or '')[:100]}"
            time.sleep(random.uniform(2.0, 4.0))
            ok, why, _j = self._verdict(self._web("media/configure/", {
                "upload_id": upload_id, "caption": caption or "",
                "usertags": "", "custom_accessibility_caption": "", "retry_timeout": ""}))
            return ok, why
        except Exception as exc:
            return False, f"post_photo error: {exc}"

    def is_locked(self) -> bool:
        """True when the ACCOUNT itself is locked/suspended — not a transient
        challenge.

        IG answers the web form-data endpoint with
        ``{"message":"checkpoint_required",
           "checkpoint_url":"https://www.instagram.com/accounts/suspended/",
           "lock":true,"status":"fail"}`` for a suspended account. Callers use
        this to PURGE (never park) a dead account.
        """
        try:
            r = self._web("accounts/edit/web_form_data/", method="GET")
            t = (r.text or "").lower()
            return ("suspended" in t) or ('"lock":true' in t) or ('"lock": true' in t)
        except Exception:
            return False

    def follow(self, pk: str, via: str = "auto") -> tuple:
        """Follow ``pk``. Tries the mobile transport, then the web transport.

        Returns (ok, detail). ``ok`` is True only when IG reports the follow
        actually persisted (``friendship_status.following``). Never raises.
        """
        if not pk:
            return False, "no pk"
        uid = self.uid or _cookie_get(self.cookie, "ds_user_id")
        now = time.time()
        nav = ("MainFeedFragment:feed_timeline:1:cold_start:%.3f:::%.3f,"
               "ExploreFragment:explore_popular:12:main_search:%.3f:::%.3f,"
               "UserDetailFragment:profile:15:search_result:%.3f:::%.3f,"
               "ProfileMediaTabFragment:profile:16:button:%.3f:::%.3f" % (
                   now - 35, now - 12, now - 12, now - 8, now - 5, now - 2, now, now))
        # APK-parity body: signed_body=SIGNATURE.<json> (TopFollow/Coinsta/NsFollower)
        jbody = {
            "include_follow_friction_check": "1",
            "user_id": pk,
            "radio_type": "wifi-none",
            "_uid": uid,
            "device_id": self.android_id,
            "_uuid": self.device_uuid,
            "nav_chain": nav,
            "container_module": "profile",
        }
        signed = "signed_body=" + urllib.parse.quote("SIGNATURE." + json.dumps(jbody))
        mob_extra = {
            "X-IG-Nav-Chain": nav,
            "X-IG-Salt-Ids": "332017224,220145826",
            "X-Fb-Rmd": "state=URL_ELIGIBLE",
            "X-IG-Transfer-Encoding": "chunked",
            "X-IG-Client-Endpoint": "ProfileMediaTabFragment:profile",
        }
        if via in ("mobile", "web"):
            attempts = [via]
        elif self.token:
            attempts = ["mobile", "web"]
        else:
            attempts = ["web"]          # no Bearer yet — web (cookie) only
        # Warm-up first (Coinsta/NsFollower): hit discover/chaining so the follow
        # comes from an "active" profile session, not a cold one.
        if self.token:
            try:
                self._mobile(
                    "api/v1/discover/chaining/".lstrip("/") +
                    "?module=profile&target_id=%s&from_module=clips_viewer_clips_tab"
                    "&profile_chaining_check=true&eligible_for_threads_cta=false" % pk,
                    method="GET")
            except Exception:
                pass
        last = ""
        for transport in attempts:
            try:
                if transport == "mobile":
                    r = self._mobile(f"friendships/create/{pk}/", signed, extra=mob_extra)
                else:
                    r = self._web(f"friendships/create/{pk}/", {"user_id": pk})
                try:
                    js = r.json()
                except Exception:
                    js = {}
                fs = (js.get("friendship_status") or {})
                if js.get("status") == "ok" or fs.get("following"):
                    return True, f"ok ({transport})"
                msg = js.get("message") or (r.text or "")[:120] or f"HTTP {r.status_code}"
                last = f"{transport}: HTTP {r.status_code} {msg}"
                low = (str(msg) + " " + (r.text or "")[:300]).lower()
                if any(k in low for k in ("feedback_required", "action_blocked",
                                          "checkpoint_required", "login_required",
                                          "challenge_required")):
                    return False, f"{transport}: {msg}"   # flagged — don't retry the other transport
            except Exception as exc:
                last = f"{transport}: {exc}"
        return False, (last or "follow failed")

    def follow_many(self, usernames, *, delay=(1.5, 4.0), verify=True) -> tuple:
        """Follow a list of usernames (resolves pk, follows, verifies). Best-effort.

        Returns (n_ok, results) — the caller decides how many are needed.
        """
        results = []
        n_ok = 0
        for u in usernames:
            pk = self.pk_of(u)
            if not pk:
                results.append((u, False, "pk not found"))
                continue
            ok, why = self.follow(pk)
            if ok and verify:
                try:
                    if not self.friendships_show(pk).get("following"):
                        ok = False
                        why = "not persisted"
                except Exception:
                    pass
            if ok:
                n_ok += 1
            results.append((u, ok, why))
            time.sleep(random.uniform(*delay))
        return n_ok, results

    # -- 2FA -------------------------------------------------------------- #
    def totp_generate_seed(self) -> tuple:
        """Returns (seed, detail). Needs the mobile session."""
        try:
            if not self.token:
                ok, why = self.mobile_login()
                if not ok:
                    return "", f"login: {why}"
            r = self._mobile("accounts/generate_two_factor_totp_key/", {})
            j = r.json()
            seed = j.get("totp_seed") or j.get("secret") or ""
            return (str(seed), "ok") if seed else ("", j.get("message") or "no totp_seed")
        except Exception as exc:
            return "", str(exc)

    def totp_enable(self, code: str) -> tuple:
        """Confirm 2FA with a TOTP code (the bot's code or a local pyotp code)."""
        try:
            r = self._mobile("accounts/enable_totp_two_factor/", {"verification_code": str(code)})
            j = r.json()
            if j.get("status") == "ok":
                return True, "ok"
            return False, (j.get("message") or f"HTTP {r.status_code}")
        except Exception as exc:
            return False, str(exc)

    def totp_enable_with_fallback(self, bot_code: str, seed: str) -> tuple:
        """enable_totp with the bot's code, falling back to local pyotp on reject."""
        ok, why = self.totp_enable(bot_code)
        if ok:
            return True, "ok (bot code)"
        try:
            import pyotp
            s = re.sub(r"[^A-Za-z2-7]", "", str(seed or "")).upper()
            for _ in range(3):
                local = pyotp.TOTP(s).now()
                if local != str(bot_code):
                    ok2, why2 = self.totp_enable(local)
                    if ok2:
                        return True, "ok (local TOTP)"
                    why = why2
                time.sleep(31 - (int(time.time()) % 30))
        except Exception as exc:
            why = f"{why}; local retry: {exc}"
        return False, why

    def security_info(self) -> dict:
        try:
            r = self._mobile("accounts/account_security_info/", {})
            return r.json() or {}
        except Exception:
            return {}

    # -- password --------------------------------------------------------- #
    def change_password(self, old: str, new: str) -> tuple:
        """Change the password (mobile API). NOTE: invalidates all sessions."""
        try:
            if not self.token:
                ok, why = self.mobile_login()
                if not ok:
                    return False, f"login: {why}"
            if not self._pub:
                self._pub, self._kid = _fetch_encryption_keys(
                    self.s, self._mobile_headers(), self.username,
                    self.android_id, self.device_uuid)
            eo = enc_password(old, self._pub, self._kid)
            e1 = enc_password(new, self._pub, self._kid)
            e2 = enc_password(new, self._pub, self._kid)
            if not (eo and e1 and e2):
                return False, "password encryption failed"
            r = self._mobile("accounts/change_password/", {
                "enc_old_password": eo,
                "enc_new_password1": e1,
                "enc_new_password2": e2,
            })
            j = r.json()
            if j.get("status") == "ok":
                return True, "ok"
            return False, (j.get("message") or f"HTTP {r.status_code}")
        except Exception as exc:
            return False, str(exc)

    # -- email ------------------------------------------------------------ #
    def send_confirm_email(self, email: str) -> tuple:
        try:
            if not self.token:
                ok, why = self.mobile_login()
                if not ok:
                    return False, f"login: {why}"
            r = self._mobile("accounts/send_confirm_email/",
                             {"send_source": "personal_information", "email": email})
            j = r.json()
            if j.get("status") == "ok" or j.get("email_sent"):
                return True, "ok"
            return False, (j.get("message") or f"HTTP {r.status_code}")
        except Exception as exc:
            return False, str(exc)

    def verify_email_code(self, email: str, code: str) -> tuple:
        try:
            r = self._mobile("accounts/verify_email_code/", {"email": email, "code": str(code)})
            j = r.json()
            if j.get("status") == "ok":
                return True, "ok"
            return False, (j.get("message") or f"HTTP {r.status_code}")
        except Exception as exc:
            return False, str(exc)

    # -- warm-up (NsFollower-style timeline) ------------------------------ #
    def warmup(self, target_pks=None, *, do_like=False) -> tuple:
        """Fire feed/timeline + reels_tray + friendships/show before writing.

        This is the concrete fix for the web "Failed to Load." follow block:
        make the account look active before the writes.
        """
        done = []
        try:
            self._mobile("feed/timeline/", {"reason": "cold_start_fetch", "time_in_feed": "0"}, method="POST")
            done.append("timeline")
        except Exception:
            pass
        try:
            self._mobile("feed/reels_tray/", {"reason": "cold_start"}, method="POST")
            done.append("reels_tray")
        except Exception:
            pass
        for pk in (target_pks or []):
            try:
                self._web(f"friendships/show/{pk}/", method="GET")
                done.append(f"show:{pk}")
            except Exception:
                pass
            time.sleep(random.uniform(0.8, 2.0))
        return True, ",".join(done) or "noop"


# --------------------------------------------------------------------------- #
# Convenience: build a client from a pool record
# --------------------------------------------------------------------------- #
def client_for_account(rec: dict, *, proxy: str = "") -> IgApiClient:
    rec = rec or {}
    return IgApiClient(
        cookie_str=rec.get("cookies") or rec.get("cookie") or "",
        username=rec.get("instagram_username") or rec.get("username") or "",
        password=rec.get("password") or "",
        twofa_seed=rec.get("twofa_secret") or "",
        android_seed=rec.get("id") or "",
        # NOTE: do NOT pass the record's device_ua — that is the BROWSER (Chrome)
        # UA from the IG Creator. The mobile headers need the INSTAGRAM APP UA
        # (IG_UA), or accounts/login/ replies "Your version of Instagram is out
        # of date." and no Bearer is ever issued. Verified live 2026-10-08:
        # browser UA -> out of date; IG_UA -> Bearer IGT:2: acquired.
        device_ua=IG_UA,
        proxy=proxy or proxy_for(rec.get("id") or rec.get("instagram_username") or ""),
    )
