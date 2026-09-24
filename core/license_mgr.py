"""Meta Creator — Software License Manager (Python mirror of core/licenseManager.js).

Authoritative License Connector for Cloudflare Workers + D1 License Backend.
Wire-compatible with Node.js implementation: identical HWID formula, seed file
locations, HMAC scheme, and cache layout so activations work seamlessly across
both runtimes.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import platform
import re
import secrets
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

APP_NAME = "Meta Creator"
APP_VERSION = "1.0.0"
LICENSE_DEFAULT_SERVER_URL = "https://nova-license.ahasiffff.workers.dev"
LICENSE_REQUEST_TIMEOUT_S = 10
LICENSE_MICRO_CACHE_MINUTES = 3
LICENSE_GRACE_PERIOD_HOURS = 72
LICENSE_FALLBACK_HMAC_SECRET = (
    os.environ.get("HMAC_SECRET")
    or "8F19B23E86FBFF4984993F89AEF3D883183451F127C69A8A0359861B3149D0BC"
)

IGNORED_INTERFACE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"vpn", r"nox", r"virtual", r"veth", r"tun", r"tap", r"wireguard",
        r"hyper-v", r"vmware", r"npcap", r"loopback", r"wsl", r"docker",
        r"br-[a-f0-9]+", r"virbr",
    )
]

_cached_stable_os_id: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value) -> datetime | None:
    try:
        if not value:
            return None
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def resolve_user_seed_dir() -> str | None:
    if sys.platform == "win32":
        roaming = os.environ.get("APPDATA")
        if not roaming and os.environ.get("USERPROFILE"):
            roaming = os.path.join(os.environ["USERPROFILE"], "AppData", "Roaming")
        if roaming:
            nova_path = os.path.join(roaming, "NovaBrowser")
            if os.path.isfile(os.path.join(nova_path, "machine_id.node")):
                return nova_path
            return os.path.join(roaming, "MetaCreator")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
        if xdg:
            nova_path = os.path.join(xdg, "nova-browser")
            if os.path.isfile(os.path.join(nova_path, "machine_id.node")):
                return nova_path
            return os.path.join(xdg, "meta-creator")
    return None


def _read_seed_file(path: str | None) -> str | None:
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                seed = f.read().strip()
            if seed and len(seed) >= 16:
                return seed
    except Exception:
        pass
    return None


def _chmod_private(path: str, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except Exception:
        pass


def _write_seed_file(path: str | None, seed: str) -> bool:
    try:
        if not path:
            return False
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        _chmod_private(os.path.dirname(path), 0o700)
        with open(path, "w", encoding="utf-8") as f:
            f.write(seed)
        _chmod_private(path, 0o600)
        return True
    except Exception:
        return False


def get_stable_os_id() -> str:
    global _cached_stable_os_id
    if _cached_stable_os_id is not None:
        return _cached_stable_os_id
    try:
        for f in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                if os.path.exists(f):
                    with open(f, "r", encoding="utf-8") as fh:
                        v = fh.read().strip().lower()
                    if v and len(v) >= 8:
                        _cached_stable_os_id = v
                        return v
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                ) as key:
                    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    _cached_stable_os_id = str(guid).strip().lower()
                    return _cached_stable_os_id
            except Exception:
                pass
    except Exception:
        pass
    _cached_stable_os_id = ""
    return ""


def get_cpu_models() -> str:
    """Returns comma-separated CPU models matching Node.js os.cpus().map(c => c.model).join(',')."""
    if sys.platform == "win32":
        try:
            import winreg
            models = []
            i = 0
            while True:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"HARDWARE\DESCRIPTION\System\CentralProcessor\{i}") as k:
                        val, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                        models.append(str(val).strip())
                    i += 1
                except OSError:
                    break
            if models:
                return ",".join(models)
        except Exception:
            pass
    elif os.path.exists("/proc/cpuinfo"):
        try:
            models = []
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith("model name"):
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            models.append(parts[1].strip())
            if models:
                return ",".join(models)
        except Exception:
            pass
    return ""


def get_node_arch() -> str:
    """Matches Node.js os.arch() values."""
    m = platform.machine().lower()
    if m in ("x86_64", "amd64", "x64"):
        return "x64"
    if m in ("i386", "i686", "x86"):
        return "ia32"
    if m in ("aarch64", "arm64"):
        return "arm64"
    if m.startswith("arm"):
        return "arm"
    return m


def get_node_platform() -> str:
    """Matches Node.js os.platform() values."""
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform.startswith("darwin"):
        return "darwin"
    return sys.platform


def _format_hwid(hash_hex: str) -> str:
    h = str(hash_hex).upper()
    return f"HWID-{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


class LicenseManager:
    def __init__(self, base_dir: str | None = None) -> None:
        if base_dir:
            base = base_dir
        elif getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        self.license_dir = os.path.join(base, "license_data")
        self.cache_file = os.path.join(self.license_dir, "license_data.json")
        self.legacy_seed_file = os.path.join(self.license_dir, "machine_id.node")
        user_seed_dir = resolve_user_seed_dir()
        self.user_seed_file = (
            os.path.join(user_seed_dir, "machine_id.node")
            if user_seed_dir
            else None
        )
        self.config_file = os.path.join(self.license_dir, "license_config.json")
        self.grace_hours = LICENSE_GRACE_PERIOD_HOURS
        self.hmac_secret = LICENSE_FALLBACK_HMAC_SECRET
        self.is_validating = False
        self.remote_api_base = self.get_remote_api_url()

    def get_remote_api_url(self) -> str:
        env = os.environ.get("REMOTE_LICENSE_API_URL")
        if env:
            return env.rstrip("/")
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    conf = json.load(f)
                if conf.get("serverUrl"):
                    return str(conf["serverUrl"]).rstrip("/")
        except Exception:
            pass
        return LICENSE_DEFAULT_SERVER_URL

    def ensure_license_dir(self) -> None:
        try:
            os.makedirs(self.license_dir, exist_ok=True)
        except Exception:
            pass

    def _local_seed(self) -> str:
        local = _read_seed_file(self.legacy_seed_file)
        if local:
            if self.user_seed_file and not _read_seed_file(self.user_seed_file):
                _write_seed_file(self.user_seed_file, local)
        else:
            local = _read_seed_file(self.user_seed_file)
        if not local:
            local = secrets.token_hex(16)
            if not _write_seed_file(self.user_seed_file, local):
                _write_seed_file(self.legacy_seed_file, local)
        return local

    def get_legacy_machine_fingerprint(self) -> str:
        self.ensure_license_dir()
        seed = self._local_seed()
        try:
            username = os.getlogin()
        except Exception:
            username = os.environ.get("USER", os.environ.get("USERNAME", ""))
        try:
            totalmem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except Exception:
            totalmem = 0
        try:
            cpu_models = get_cpu_models()
        except Exception:
            cpu_models = ""
        raw = "||".join(
            [
                platform.node(),
                get_node_arch(),
                get_node_platform(),
                cpu_models,
                str(totalmem),
                username,
                "",
                seed,
            ]
        )
        return _format_hwid(hashlib.sha256(raw.encode()).hexdigest())

    def get_machine_fingerprint(self) -> str:
        """Computes hardware machine fingerprint (100% byte-for-byte identical to Node.js)."""
        self.ensure_license_dir()
        seed = self._local_seed()
        raw = "||".join(
            [seed, get_stable_os_id(), get_cpu_models(), get_node_arch(), get_node_platform()]
        )
        return _format_hwid(hashlib.sha256(raw.encode()).hexdigest())

    def request_remote_api(self, path: str, payload: dict | None = None) -> dict:
        url = self.get_remote_api_url() + path
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LICENSE_REQUEST_TIMEOUT_S) as res:
            return {"status_code": res.status, "data": json.loads(res.read().decode("utf-8"))}

    def _derived_hmac_secret(self) -> str | None:
        try:
            seed = self._local_seed()
            if seed:
                return hashlib.sha256(
                    f"nova-hmac||{seed}||{get_stable_os_id()}".encode("utf-8")
                ).hexdigest()
        except Exception:
            pass
        return None

    def _hmac_body(self, obj: dict) -> str:
        return (
            f"{obj.get('license_key')}||{obj.get('status')}||"
            f"{obj.get('expires_at') or 'LIFETIME'}||"
            f"{obj.get('last_validated_at')}||{obj.get('hwid')}"
        )

    def calculate_hmac(self, obj: dict) -> str:
        derived = self._derived_hmac_secret()
        secret = (derived or self.hmac_secret).encode("utf-8")
        return hmac_mod.new(
            secret,
            self._hmac_body(obj).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify_hmac(self, obj: dict) -> bool:
        if not obj or not obj.get("signature"):
            return False
        if obj["signature"] == self.calculate_hmac(obj):
            return True
        try:
            legacy = hmac_mod.new(
                self.hmac_secret.encode("utf-8"),
                self._hmac_body(obj).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return obj["signature"] == legacy
        except Exception:
            return False

    def get_saved_cache(self) -> dict | None:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if cache and cache.get("signature"):
                    if self.verify_hmac(cache):
                        return cache
                    print("[LicenseManager] TAMPER DETECTED: Cache signature mismatch. Clearing corrupted cache.")
                    self.clear_cache()
        except Exception as e:
            print(f"[LicenseManager] Error reading cache: {e}")
        return None

    def save_cache(self, obj: dict) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_file), mode=0o700, exist_ok=True)
            _chmod_private(os.path.dirname(self.cache_file), 0o700)
            obj["signature"] = self.calculate_hmac(obj)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
            _chmod_private(self.cache_file, 0o600)
        except Exception as e:
            print(f"[LicenseManager] Error saving cache: {e}")

    def clear_cache(self) -> None:
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        except Exception:
            pass

    def validate_or_activate(
        self, input_key: str | None = None, force_remote: bool = False
    ) -> dict:
        if os.environ.get("META_DEV_MODE") == "1" or os.environ.get("SKIP_LICENSE") == "1":
            return {
                "status": "ACTIVE",
                "isValid": True,
                "devMode": True,
                "message": "Running in developer override mode.",
                "hwid": self.get_machine_fingerprint(),
                "license": {
                    "license_key": "DEV-MODE-OVERRIDE",
                    "status": "ACTIVE",
                    "license_type": "DEVELOPER",
                    "expires_at": "NEVER",
                },
            }

        if self.is_validating:
            cache = self.get_saved_cache()
            if cache and cache.get("status") == "ACTIVE":
                return {
                    "status": "ACTIVE",
                    "isValid": True,
                    "license": cache,
                    "hwid": self.get_machine_fingerprint(),
                }

        self.is_validating = True
        try:
            hwid = self.get_machine_fingerprint()
            cache = self.get_saved_cache()
            key = ((input_key or (cache or {}).get("license_key") or "").strip().upper())

            # Micro-cache check
            if not force_remote and not input_key and cache and cache.get("status") == "ACTIVE" and cache.get("last_validated_at"):
                exp = cache.get("expires_at")
                expired = (
                    exp not in (None, "", "LIFETIME", "NEVER")
                    and (_parse_dt(exp) is not None)
                    and (_utcnow() > _parse_dt(exp))
                )
                if not expired:
                    last = _parse_dt(cache["last_validated_at"])
                    if last and 0 <= (_utcnow() - last).total_seconds() / 60 < LICENSE_MICRO_CACHE_MINUTES:
                        return {
                            "status": "ACTIVE",
                            "isValid": True,
                            "license": cache,
                            "hwid": hwid,
                            "fromLocalCache": True,
                        }

            if not key:
                self.clear_cache()
                return {
                    "status": "UNLICENSED",
                    "message": "No active license found. Please enter your license key to activate.",
                    "isValid": False,
                    "hwid": hwid,
                }

            # Remote validation via Cloudflare Workers
            try:
                endpoint = "/api/license/activate" if input_key else "/api/license/validate"
                try:
                    legacy = self.get_legacy_machine_fingerprint()
                except Exception:
                    legacy = None

                payload = {
                    "licenseKey": key,
                    "hwid": hwid,
                    "hostname": socket.gethostname(),
                    "platform": sys.platform,
                }
                if legacy and legacy != hwid:
                    payload["previousHwid"] = legacy

                res = self.request_remote_api(endpoint, payload)
                data = (res or {}).get("data") or {}
                lic = data.get("license") or {}

                if data.get("isValid") and lic.get("status") == "ACTIVE":
                    lic["hwid"] = hwid
                    lic["last_validated_at"] = _utcnow().isoformat()
                    self.save_cache(lic)
                    return {
                        "status": "ACTIVE",
                        "message": data.get("message") or "License validated successfully.",
                        "isValid": True,
                        "license": lic,
                        "hwid": hwid,
                    }

                msg = data.get("message") or ""
                mismatch = (
                    data.get("status") == "HWID_MISMATCH"
                    or data.get("code") == "HWID_MISMATCH"
                    or "HWID" in msg
                )
                if not mismatch:
                    self.clear_cache()
                return {
                    "status": data.get("status") or "INVALID",
                    "message": msg or "License is invalid or suspended.",
                    "isValid": False,
                    "hwid": hwid,
                }
            except Exception as e:
                # Network unreachable: check offline grace period
                if cache:
                    offline = self.check_offline_grace(cache, hwid)
                    if offline.get("isValid"):
                        return offline
                return {
                    "status": "OFFLINE_UNREACHABLE",
                    "message": f"License server unreachable ({e}). Internet connection required.",
                    "isValid": False,
                    "hwid": hwid,
                }
        finally:
            self.is_validating = False

    def check_offline_grace(self, cache: dict, current_hwid: str) -> dict:
        if not cache or not cache.get("license_key") or not cache.get("last_validated_at"):
            return {
                "status": "OFFLINE_NO_CACHE",
                "message": "Internet connection required for initial activation.",
                "isValid": False,
                "hwid": current_hwid,
            }

        try:
            legacy_hwid = self.get_legacy_machine_fingerprint()
        except Exception:
            legacy_hwid = None

        if cache.get("hwid") and cache["hwid"] not in (current_hwid, legacy_hwid):
            if self.verify_hmac(cache):
                cache["hwid"] = current_hwid
                self.save_cache(cache)
            else:
                return {
                    "status": "HWID_MISMATCH",
                    "message": "Hardware fingerprint mismatch.",
                    "isValid": False,
                    "hwid": current_hwid,
                }

        exp = cache.get("expires_at")
        if exp not in (None, "", "LIFETIME", "NEVER"):
            edt = _parse_dt(exp)
            if edt and _utcnow() > edt:
                self.clear_cache()
                return {
                    "status": "EXPIRED",
                    "message": "License has expired.",
                    "isValid": False,
                    "hwid": current_hwid,
                }

        last = _parse_dt(cache["last_validated_at"])
        hours = ((_utcnow() - last).total_seconds() / 3600) if last else 1e9
        if hours <= self.grace_hours:
            rem = max(0, round(self.grace_hours - hours))
            return {
                "status": "ACTIVE_OFFLINE_GRACE",
                "message": f"Running in Offline Grace Period ({rem}h remaining). Please connect to internet soon.",
                "isValid": True,
                "license": cache,
                "hwid": current_hwid,
                "isOfflineGrace": True,
            }

        self.clear_cache()
        return {
            "status": "OFFLINE_GRACE_EXPIRED",
            "message": "Offline grace period expired. Internet connection required to re-verify license.",
            "isValid": False,
            "hwid": current_hwid,
        }

    def deactivate(self) -> dict:
        cache = self.get_saved_cache()
        hwid = self.get_machine_fingerprint()
        if cache and cache.get("license_key"):
            try:
                self.request_remote_api(
                    "/api/license/deactivate",
                    {"licenseKey": cache["license_key"], "hwid": hwid},
                )
            except Exception:
                pass
        self.clear_cache()
        return {"success": True, "message": "Device deactivated successfully."}


if __name__ == "__main__":
    lm = LicenseManager()
    print("=" * 60)
    print(f"  {APP_NAME} — License Manager Diagnostic")
    print("=" * 60)
    hwid = lm.get_machine_fingerprint()
    print(f"HWID:   {hwid}")
    print(f"Server: {lm.get_remote_api_url()}")
    res = lm.validate_or_activate()
    print(f"Status: {res.get('status')}")
    print(f"Valid:  {res.get('isValid')}")
    print(f"Detail: {res.get('message')}")
    print("=" * 60)
