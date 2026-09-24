from __future__ import annotations

import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MailboxMixin:
    """mail.td-only mailbox lifecycle helpers.

    The creator intentionally has one mailbox backend in this build.  The
    actual address/OTP implementation lives in ``engine.eng_mix_mail``; this
    mixin only preserves the existing runner hooks and the persisted-tab
    restore behavior.
    """

    def open_mail(self):
        """Open a fresh mail.td inbox in the current browser context."""
        self.mail_provider = "mailtd"
        return super().open_mailtd()

    def _ensure_mail_tab(self):
        """Restore a persisted mail.td tab when a warm runner needs it."""
        try:
            mail = getattr(self, "mail", None)
            if mail is not None and not mail.is_closed():
                return mail
        except Exception:
            pass

        tokens = getattr(self, "mail_tokens", None) or {}
        if not isinstance(tokens, dict) or not tokens.get("tempmail_token"):
            return None

        try:
            ctx = getattr(getattr(self, "w", None), "context", None)
            if ctx is None:
                return None
            page = ctx.new_page()
            page.goto("https://mail.td/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            page.evaluate(
                """(kv) => {
                    try {
                        if (kv.tempmail_token) localStorage.setItem("tempmail_token", kv.tempmail_token);
                        if (kv.tempmail_account_id) localStorage.setItem("tempmail_account_id", kv.tempmail_account_id);
                    } catch (e) {}
                }""",
                {
                    "tempmail_token": tokens.get("tempmail_token", ""),
                    "tempmail_account_id": tokens.get("tempmail_account_id", ""),
                },
            )
            page.reload(wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            self.mail = page
            try:
                self.log("[📧] Re-opened mail.td inbox from stored tokens (same address).")
            except Exception:
                pass
            return page
        except Exception:
            return None

    def fetch_code(
        self,
        keyword: str = "meta",
        timeout: int = 240,
        subject_hint=None,
        prefer_len=None,
    ) -> Optional[str]:
        """Fetch an OTP from the mail.td tab/API.

        ``subject_hint`` and ``prefer_len`` remain accepted for compatibility
        with the older multi-provider runner API; the browser mail.td parser
        determines the code length from the message contents.
        """
        try:
            self._ensure_mail_tab()
        except Exception:
            pass
        return super().fetch_code(keyword, timeout=timeout)

    def finish(self):
        """Clean up the runner/browser through the existing engine hook."""
        return super().finish()

    def finish_warm(self):
        """Close only the account context; the warm browser pool survives."""
        try:
            if getattr(self.w, "context", None) is not None:
                self.w.context.close()
        except Exception:
            pass
        try:
            self.w.context = None
        except Exception:
            pass

    def open_mailtd(self):
        """Backward-compatible alias for the sole mail.td provider."""
        return self.open_mail()
