from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Optional

from tg_bot import TelegramTasklyBot, ThreadedTelegramBot  # noqa: E402


class TgMixin:
    def _telegram_start(self):
        """Open the persistent Telegram profile, pick the task and Start it.

        Started EARLY so the bot's Login/Password can register the Instagram
        account directly (no separate username/password step afterwards).
        Raises on any bot failure — the linked flow must not continue blind
        with empty credentials.
        """
        try:
            # TG follows the pipeline Background/Visible switch directly.
            headless = getattr(getattr(self, "w", None), "is_headless", True)
            self.tg = ThreadedTelegramBot(
                profile_dir=self.tg_profile_dir,
                headless=headless,
                log=self.log,
            )
            self.tg.start()
            if not self.tg.open_bot():
                raise RuntimeError("Taskly Bot chat could not be opened")
            if not self.tg.choose_task(self.tg_task):
                raise RuntimeError(f"Task '{self.tg_task}' could not be selected")
            self.tg_creds = self.tg.start_task()
            if not (self.tg_creds.get("login") and self.tg_creds.get("password")):
                raise RuntimeError(f"Taskly Bot returned no credentials (got {self.tg_creds})")
            self.log(f'[tg] task credentials: {self.tg_creds}')
            if self.tg_creds.get("login"):
                self.new_username = self.tg_creds["login"]
            if self.tg_creds.get("password"):
                self.new_password = self.tg_creds["password"]
            if self.tg_creds.get("first_name"):
                if not getattr(self, "meta_name", None) and self.name:
                    self.meta_name = self.name
                import unicodedata, re
                raw_fn = str(self.tg_creds["first_name"])
                fallback = getattr(self, "first", "") or "Alex"
                if not any(unicodedata.category(c).startswith("L") for c in raw_fn):
                    clean_fn = fallback
                else:
                    leetspeak = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"}
                    chars = []
                    for ch in raw_fn:
                        if ch in leetspeak:
                            chars.append(leetspeak[ch])
                            continue
                        cat = unicodedata.category(ch)
                        if cat.startswith("L"):
                            chars.append(ch)
                        elif ch in ("'", "-"):
                            chars.append(ch)
                        else:
                            chars.append(" ")
                    clean_fn = re.sub(r"\s+", " ", "".join(chars)).strip().strip("-' ")
                    if len(clean_fn) < 2:
                        clean_fn = fallback
                    elif clean_fn.islower():
                        clean_fn = clean_fn.title()
                self.name = clean_fn or fallback
        except Exception as exc:  # noqa: BLE001
            self.log(f'[⚠️] Telegram start failed: {exc}')
            self.tg = None

    def _telegram_send_key(self, secret: str) -> Optional[str]:
        """Send the 2FA key to the bot and read back the one-time code."""
        if not (self.tg and secret):
            return None
        try:
            self.tg_code = self.tg.submit_2fa_key(secret)
            return self.tg_code
        except Exception as exc:  # noqa: BLE001
            self.log(f'[⚠️] Telegram key submit failed: {exc}')
            return None
