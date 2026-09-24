from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Optional

from ai_config import TG_DEFAULT_TASK, Urls, get_random_selfie  # noqa: E402


class MetaBaseMixin:
    def __init__(
        self,
        worker,
        twofa: bool = False,
        new_password: Optional[str] = None,
        new_username: Optional[str] = None,
        telegram: bool = False,
        tg_task: str = TG_DEFAULT_TASK,
        tg_id: Optional[str] = None,
        tg_profile_dir: Optional[str] = None,
        captcha_mode: str = "extension",
        mail_provider: str = "mailtd",
        target: str = "telegram",
    ):
        super().__init__(worker)
        self.target = target              # pipeline target: "telegram" or "nitro"
        self.twofa = twofa
        self.new_password = new_password
        self.new_username = new_username
        self.telegram = telegram          # submit to Taskly bot
        self.tg_task = tg_task
        self.tg_id = tg_id                # leased Telegram account id
        self.tg_profile_dir = tg_profile_dir
        # ordered: Visual AI first (audio on fallback). The choice only
        # sets attempt ORDER — both solvers stay loaded (see _launch).
        self.captcha_mode = (captcha_mode or "extension").lower()
        if self.captcha_mode not in Urls.CAPTCHA_MODES:
            self.captcha_mode = "extension"
        # mail.td is the only supported mailbox provider.
        self.mail_provider = "mailtd"
        self.insta_secret = None          # 2FA base32 secret (space-stripped)
        self.device_model = None          # pinned phone model (Nova parity; set from record before resume)
        self.device_ua = None             # pinned full UA string
        self.ig_username = None           # confirmed Instagram username
        self.tg = None                    # TelegramTasklyBot
        self.tg_creds = {}                # bot-provided first_name/login/password
        self.tg_code = None               # bot-provided one-time code
        self.tg_submitted = False
        self.last_record_id = None        # id of the record this run saved
        self.meta_name = getattr(self, "name", None)  # preserved Meta account name across task renames

    def _launch(self):
        """Configure anti-detect captcha environment before launching Playwright browser context.

        ordered: the Visual AI extension is bundled when present AND the
        browser is headed — headless shell silently ignores --load-extension,
        so Background mode runs Audio STT first (Visual on Visible fallback).
        The dashboard captcha choice only sets the attempt ORDER.
        """
        from ai_config import CAPTCHA_EXT_DIR
        is_headless = bool(getattr(getattr(self, "w", None), "is_headless", False))
        # Headless now uses Chrome's NEW headless (channel="chromium", see
        # eng_mix_launch.py) which DOES support unpacked extensions, so the
        # Visual AI extension loads headless too — unless INSTA_HEADLESS_EXTENSION=0.
        # Previously this set INSTA_NO_EXTENSION=1 whenever headless, which
        # silently defeated the channel="chromium" load.
        headless_ext_ok = (not is_headless) or os.environ.get("INSTA_HEADLESS_EXTENSION", "1") != "0"
        if os.path.isdir(CAPTCHA_EXT_DIR) and headless_ext_ok:
            os.environ.pop("INSTA_NO_EXTENSION", None)
            os.environ["RECAPTCHA_EXT_DIR"] = CAPTCHA_EXT_DIR
        else:
            os.environ["INSTA_NO_EXTENSION"] = "1"
            os.environ.pop("RECAPTCHA_EXT_DIR", None)
        if getattr(self, "captcha_mode", "extension") == "audio":
            self.log('[🎙️] Captcha solver: Audio STT first, Visual AI on fallback')
        elif is_headless and not headless_ext_ok:
            self.log('[🧩] Captcha solver: Background mode — Audio STT first (Visual needs Visible window)')
        elif is_headless:
            self.log('[🧩] Captcha solver: Background mode — Visual AI extension via new-headless (channel=chromium)')
        else:
            self.log(f'[🧩] Captcha solver: Visual AI first, Audio STT on fallback ({os.path.basename(CAPTCHA_EXT_DIR) if os.path.isdir(CAPTCHA_EXT_DIR) else "extension missing — audio only"})')
        super()._launch()
        self.selfie_path = get_random_selfie()
        if os.path.exists(self.selfie_path):
            self.log(f'[🖼️] Verification selfie assigned: {os.path.basename(self.selfie_path)}')

    def _dispatch_react_events(self, page, locator):
        """Dispatch explicit synthetic React events (input, change, blur) to synchronize Fiber tree."""
        try:
            locator.evaluate("""(el) => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }""")
        except Exception:
            pass
