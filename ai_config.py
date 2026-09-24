"""
meta_auto_ai — shared configuration
===================================

Single place for: filesystem paths, the bundled engine import, the URL
registry, the 2FA key regex, Telegram constants and the stdout event emitter.
"""
from __future__ import annotations

import json
import os
import re
import sys

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
AI_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(AI_DIR, "engine")
DATA_DIR = os.path.join(AI_DIR, "data")
ACCOUNTS_JSON = os.path.join(DATA_DIR, "accounts.json")
ACCOUNTS_CSV = os.path.join(DATA_DIR, "accounts.csv")
ACCOUNTS_TXT = os.path.join(AI_DIR, "accounts.txt")
SELFIE_PATH = os.path.join(AI_DIR, "selfie.png")
SELFIES_DIR = os.path.join(AI_DIR, "selfies")
IMG_DIR = os.path.join(AI_DIR, "img")


def get_random_selfie() -> str:
    """Return a randomly chosen selfie image from selfies/ or img/ directory, falling back to SELFIE_PATH."""
    import random
    candidates = []
    for d in (SELFIES_DIR, IMG_DIR):
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    candidates.append(os.path.join(d, f))
    if candidates:
        return random.choice(candidates)
    return SELFIE_PATH

# Self-contained: AI_DIR + bundled ENGINE_DIR only. No sibling-project paths.
sys.path.insert(0, AI_DIR)
if not (os.path.isdir(ENGINE_DIR) and os.path.isfile(os.path.join(ENGINE_DIR, "run.py"))):
    raise ImportError(
        f"bundled engine not found: {os.path.join(ENGINE_DIR, 'run.py')}"
    )
sys.path.insert(0, ENGINE_DIR)

import run  # noqa: E402  (Anti-detect + offline captcha engine)
# Keep current working directory anchored to AI_DIR (run.py sets chdir to its own dir)
os.chdir(AI_DIR)

# mail.td is the only supported mailbox provider for this build.
# The browser-backed mail.td flow is implemented in engine/eng_mix_mail.py.
# The legacy provider module is intentionally not imported or packaged.

SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
CAPTCHA_EXT_DIR = os.path.join(AI_DIR, "extensions", "Captcha")
os.environ.setdefault("RECAPTCHA_EXT_DIR", CAPTCHA_EXT_DIR)

for _d in (DATA_DIR, os.path.join(AI_DIR, "profiles"), os.path.join(AI_DIR, "cookies"), SESSIONS_DIR):
    os.makedirs(_d, exist_ok=True)



# ==========================================================================
# Urls — every endpoint used by the Meta + Instagram flow
# ==========================================================================
class Urls:
    """Single source of truth for all URLs (Instagram + Meta)."""

    # --- Meta ---
    META_AI = "https://www.meta.ai/"
    META_AI_APEX = "https://meta.ai/"
    META_SIGNUP = run._META_AUTH_URL                      # https://auth.meta.com/
    META_POST_CHECKPOINT = run._META_POST_URL

    # --- Temp-mail provider (mail.td only) ---
    MAILTD = "https://mail.td/"
    MAIL_PROVIDERS = ("mailtd",)
    # Keep a single explicit choice for callers that still import this symbol.
    MAIL_PROVIDER_DEFAULT = "mailtd"
    CAPTCHA_MODES = ("extension", "audio")  # chosen first, the other on fallback


    # --- Instagram core ---
    IG_HOME = "https://www.instagram.com/"
    IG_LOGIN = "https://www.instagram.com/accounts/login/"
    IG_SIGNUP = "https://www.instagram.com/accounts/emailsignup/"
    IG_REGISTERED = "https://www.instagram.com/accounts/registered/"
    IG_SUSPENDED = "https://www.instagram.com/accounts/suspended/"

    @staticmethod
    def ig_profile(username: str) -> str:
        return f"https://www.instagram.com/{username}/"

    # --- Instagram settings (web) ---
    IG_SETTINGS = "https://www.instagram.com/accounts/settings/?entrypoint=profile"
    IG_EDIT_PROFILE = "https://www.instagram.com/accounts/edit/"

    # --- Accounts Center (username / password / 2FA live here on web) ---
    AC_BASE = "https://accountscenter.instagram.com"
    AC_HOME = "https://accountscenter.instagram.com/?entry_point=app_settings"
    AC_PROFILES = "https://accountscenter.instagram.com/profiles/"
    AC_PASSWORD_SECURITY = "https://accountscenter.instagram.com/password_and_security/"
    AC_CHANGE_PASSWORD = (
        "https://accountscenter.instagram.com/password_and_security/password/change/"
    )
    AC_TWO_FACTOR = (
        "https://accountscenter.instagram.com/password_and_security/two_factor/"
    )
    AC_CONTACT_POINTS = (
        "https://accountscenter.instagram.com/personal_info/contact_points/"
    )


# Matches the space-grouped base32 2FA key shown during setup, e.g.
# "RSPS 45W3 4LP2 X2WB ROMD IAVQ VV5O LN22"
TWOFA_KEY_RE = re.compile(r"[A-Z2-7]{4}(?:\s+[A-Z2-7]{4}){3,}")

# --------------------------------------------------------------------------
# Telegram (Taskly bot) — pool of persistent, pre-logged-in profiles
# --------------------------------------------------------------------------
TELEGRAM_PROFILES_DIR = os.path.join(AI_DIR, "telegram_profiles")
os.makedirs(TELEGRAM_PROFILES_DIR, exist_ok=True)
LEGACY_TELEGRAM_PROFILE = os.path.join(AI_DIR, "telegram_profile")
TG_ACCOUNTS_JSON = os.path.join(DATA_DIR, "tg_accounts.json")
TG_MAX_ACCOUNTS = 20          # session storage cap
TG_MAX_PARALLEL = 6           # max simultaneous Telegram submissions (one per profile)
TG_DEFAULT_MODE = "web"       # "web" (Telegram Web browser) | "mtproto" (Telethon)
DEFAULT_CREATE_PARALLEL = 5   # default parallel Instagram creations
MAX_CREATE_PARALLEL = 10      # hard cap on parallel creations
TELEGRAM_URL = "https://web.telegram.org/a/"
TG_BOT_NAME = "Taskly Bot"
TG_DEFAULT_TASK = "Create Inst (No mail)"
# TG browsers follow the pipeline Background/Visible switch directly
# (headless flag threaded through worker → tg_worker → PooledTelegramBot).
# No separate TG visibility knob — one switch, both browsers.
TG_BOTS = {
    "taskly": {
        "id": "taskly",
        "name": "Taskly Bot",
        "peer_id": "8661341341",
        "username": "tasklyBux_bot",
        "url": "https://web.telegram.org/a/#8661341341",
        "task_keyword": "Create Inst",
        "tasks": ["Create Inst (2FA)", "Create Inst (No mail)"],
        "task_aliases": {
            "Create Inst (2FA)": "Create Inst (2FA)",
            "Create Inst (No mail)": "Create Inst (No mail)",
        },
    },
    "paygo": {
        "id": "paygo",
        "name": "PayGoBot",
        "peer_id": "8249657346",
        "username": "PayGoBot",
        "url": "https://web.telegram.org/a/#8249657346",
        "task_keyword": "Create Inst",
        # Strict: ONLY 🔥 Create Inst (2FA)
        "tasks": ["Create Inst (2FA)"],
        "task_aliases": {
            "Create Inst (No mail)": "Create Inst (2FA)",
            "Create Inst (2FA)": "Create Inst (2FA)",
        },
    },
}
TG_DEFAULT_BOT = "both"
TG_BOT_CHOICES = ("both", "taskly", "paygo")


def emit_event(evt: dict) -> None:
    """Emit one dashboard event on stdout (parsed by server.js)."""
    print(f"__EVENT__{json.dumps(evt)}", flush=True)
