from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
from typing import Optional

from ai_config import Urls, create_any_mail_provider, create_mail_provider  # noqa: E402

from .mail_fish import TempMailFishProvider  # noqa: E402

# Per-account rotation cursor for the "rotate" mail provider (domain diversity).
_MAIL_ROTATE_IDX = 0
_MAIL_ROTATE_LOCK = threading.Lock()
_MAIL_ROTATE_ORDER = ("mailtd", "tempmailfish", "guerrilla", "mailtm")


class MailboxMixin:
    def open_mail(self):
        """Obtain temp-mail inbox (ordered multi-tier chain).

        Chain (first success wins): preferred REST provider
        (tempmail.fish / Guerrilla / mail.tm, or ``auto`` for all three in
        order) with the legacy mail.td web inbox as the final fallback.
        ``rotate`` round-robins across ALL four per account for domain diversity.
        """
        provider = str(getattr(self, "mail_provider", "mailtd")).lower()
        if provider == "rotate":
            return self.open_rotating_provider()
        if provider == "mailtd":
            return super().open_mailtd()
        if provider in Urls.MAIL_PROVIDERS + ("mail.tm",):
            try:
                return self.open_rest_provider(provider)
            except Exception as exc:  # noqa: BLE001
                self.log(f"[⚠️] {provider} inbox failed ({exc}); "
                         f"falling back to mail.td web inbox…")
                return super().open_mailtd()
        return super().open_mailtd()

    def open_rotating_provider(self):
        """Pick a different inbox type per account (incl. mail.td), falling back
        to the next on failure. Diversity, not a single flagged domain."""
        global _MAIL_ROTATE_IDX
        with _MAIL_ROTATE_LOCK:
            start = _MAIL_ROTATE_IDX % len(_MAIL_ROTATE_ORDER)
            _MAIL_ROTATE_IDX += 1
        n = len(_MAIL_ROTATE_ORDER)
        for i in range(n):
            name = _MAIL_ROTATE_ORDER[(start + i) % n]
            try:
                if name == "mailtd":
                    self.log("[📧] rotate → mail.td (web inbox)")
                    return super().open_mailtd()
                self.log(f"[📧] rotate → {name}")
                return self.open_rest_provider(name)
            except Exception as exc:  # noqa: BLE001
                self.log(f"[⚠️] rotate: {name} failed ({exc}); trying next…")
        self.log("[⚠️] rotate: all providers failed; falling back to mail.td web inbox")
        return super().open_mailtd()


    def open_rest_provider(self, provider="auto"):
        """Strict single pick, or the full auto chain (ordered).

        An explicit dashboard choice is honored exactly (3 attempts, then a
        clear error) — it never silently switches to another REST provider.
        Only ``auto`` walks fish → Guerrilla → mail.tm in order. The final
        mail.td web fallback happens in :meth:`open_mail`, loudly logged.
        """
        name = str(provider or "auto").lower()
        if name == "mailtm":
            name = "mail.tm"
        tag = str(getattr(self.w, "slot_id", "1"))
        if create_any_mail_provider is None or create_mail_provider is None:
            # Provider module not present — legacy fish-only path.
            if name not in ("auto", "tempmailfish"):
                raise RuntimeError("mailProviders module not available for " + name)
            return self.open_tempmailfish()
        if name == "auto":
            chain = create_any_mail_provider(
                log_func=self.log, profile_tag=tag, preferred=None)
        else:
            single = {"tempmailfish": "tempmail.fish"}.get(name, name)
            self.log(f"[📧] Using {single} (strict choice, no silent switch)…")
            chain = create_mail_provider(
                single, log_func=self.log, profile_tag=tag, retries=3)
        self.tempmail_provider = chain
        self.email = chain.email
        return self.email


    def open_tempmailfish(self) -> str:
        """Create fresh inbox via api.tempmail.fish with zero browser tab overhead."""
        self.tempmail_provider = TempMailFishProvider(
            log_func=self.log,
            profile_tag=str(getattr(self.w, "slot_id", "1")),
        )
        self.email = self.tempmail_provider.generate_new()
        return self.email

    def _ensure_mail_tab(self):
        """Return a live mail.td tab, opening + restoring it when needed.

        Warm submitter contexts launch with NO mailbox tab, so email OTP
        fetches used to fail outright. If stored ``mail_tokens`` exist
        (persisted at creation), open mail.td in the current context,
        inject the tokens, and reload — same inbox, no new address.
        Returns None when there is no context or no tokens to restore.
        """
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
                {"tempmail_token": tokens.get("tempmail_token", ""),
                 "tempmail_account_id": tokens.get("tempmail_account_id", "")},
            )
            page.reload(wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            self.mail = page
            try:
                self.log('[📧] Re-opened mail.td inbox from stored tokens (same address).')
            except Exception:
                pass
            return page
        except Exception:
            return None

    def fetch_code(self, keyword: str = "meta", timeout: int = 240,
                   subject_hint=None, prefer_len=None) -> Optional[str]:
        """Fetch confirmation code from the active temp-mail provider.

        ``subject_hint``/``prefer_len`` (e.g. "authenticate your profile"/8
        for the Accounts Center email challenge) are forwarded to REST
        providers; legacy web-inbox fetchers receive the plain call.
        """
        provider = getattr(self, "tempmail_provider", None)
        if provider is not None:
            label = getattr(provider, "name", None) or getattr(provider, "email", "REST")
            try:
                code = provider.wait_for_otp(timeout=timeout, keyword=keyword,
                                             subject_hint=subject_hint,
                                             prefer_len=prefer_len)
            except TypeError:
                code = provider.wait_for_otp(timeout=timeout, keyword=keyword)
            if code:
                return code
            self.log(f"[⚠️] {label} wait_for_otp returned no code.")
        try:
            mail_page = self._ensure_mail_tab()
        except Exception:
            mail_page = None
        # Always let the engine fetcher run (it reopens mail.td when the tab is
        # missing and logs progress). The old code returned None here, which was
        # a silent, instant OTP failure whenever the mailbox tab was gone.
        return super().fetch_code(keyword, timeout=timeout)

    def finish(self):
        """Clean up mailbox and browser resources."""
        if getattr(self, "tempmail_provider", None):
            try:
                self.tempmail_provider.cleanup()
            except Exception:
                pass
        super().finish()

    def finish_warm(self):
        """End a warm submit: mailbox cleanup + close ONLY the account context.

        The browser process underneath belongs to the warm pool and must
        survive — never call :meth:`finish` on a warm-attached runner.
        """
        if getattr(self, "tempmail_provider", None):
            try:
                self.tempmail_provider.cleanup()
            except Exception:
                pass
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
        """Backward-compatible alias: honors the configured mail provider."""
        return self.open_mail()
