from __future__ import annotations

import os
import sys
from typing import Optional

from core.mail_reader import retire_mailbox

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MailboxMixin:
    """mail.td-only mailbox lifecycle helpers.

    The creator intentionally has one mailbox backend in this build.  The
    actual address/OTP implementation lives in ``engine.eng_mix_mail``; this
    mixin only preserves the existing runner hooks and the persisted-tab
    restore behavior.
    """

    # Order tried when an inbox cannot be opened: the provider chosen in the dashboard first, then the
    # others. Only these three are offered (Yamin.bd and Guerrilla Mail are disabled).
    _MAIL_FALLBACK_ORDER = ("mailfish", "mailtd")

    @staticmethod
    def _mail_enabled(name: str) -> bool:
        from ai_config import Urls
        return str(name).lower() not in {str(d).lower() for d in Urls.DISABLED_MAIL_PROVIDERS}

    def _mail_chain(self) -> list:
        """Providers to try, in order: the selected one, then the fallback order. Disabled ones are skipped."""
        primary = getattr(self, "_mail_primary", None) or getattr(self, "mail_provider", "mailtd") or "mailtd"
        primary = str(primary).lower()
        chain = []
        for p in [primary] + list(self._MAIL_FALLBACK_ORDER):
            if p not in chain and self._mail_enabled(p):
                chain.append(p)
        return chain or ["mailtd"]

    def open_mail(self):
        """Open a fresh inbox: the selected provider first; if it cannot give an address, the next one.

        The provider that finally works is kept on ``self.mail_provider`` for this whole account (OTP
        reads, saved tokens, 2FA). The next account starts again from the selected provider.
        """
        chain = self._mail_chain()
        last_exc = None
        for idx, prov in enumerate(chain):
            self.mail_provider = prov
            try:
                result = self._open_mail_once()
                if idx:
                    self.log(f'[📧] Mail provider switched: {chain[0]} gave no address → using {prov} for this account.')
                return result
            except Exception as exc:
                last_exc = exc
                nxt = chain[idx + 1] if idx + 1 < len(chain) else None
                self.log(f'[⚠️] {prov} inbox failed ({str(exc)[:90]})'
                         + (f' — switching to {nxt}.' if nxt else ' — no other provider left.'))
                self._discard_failed_mail_tab()
        self.mail_provider = chain[0]       # leave the selected provider as the account default
        raise last_exc

    def _open_mail_once(self):
        """One attempt with ``self.mail_provider`` (no fallback). Aliases like open_mailtd() use this."""
        result = self._open_mail_provider()
        # Capture the session while the tab is still open, so a later close cannot lose it.
        self._snapshot_mail_session()
        return result

    def _discard_failed_mail_tab(self):
        """Close the half-opened mailbox tab and forget its address before the next provider is tried."""
        try:
            mail = getattr(self, "mail", None)
            if mail is not None and not mail.is_closed():
                mail.close()
        except Exception:
            pass
        self.mail = None
        self.email = None
        self._mailfish_api = False
        self._mail_session = {}

    def _open_mail_provider(self):
        provider = getattr(self, "mail_provider", "mailtd") or "mailtd"
        if str(provider).lower() in ("yamin", "yaminbd", "email_yamin", "epicz", "liseller"):
            self.mail_provider = "yamin"
            return super().open_yamin()
        if str(provider).lower() in ("mailcf", "cloudflare", "cf"):
            self.mail_provider = "mailcf"
            return super().open_mailcf()
        # DISABLED: Guerrilla Mail is no longer offered (core/guerrilla_api.py stays so saved accounts can still be read).
#         if str(provider).lower() in ("guerrilla", "guerrillamail", "gm"):
#             # HTTP API inbox: no browser tab. The address + sid_token are saved for later 2FA reads.
#             self.mail_provider = "guerrilla"
#             from core import guerrilla_api
#             email, sid = guerrilla_api.create_inbox()
#             if not email:
#                 raise RuntimeError("could not create a Guerrilla Mail inbox")
#             self.email = email
#             self.mail = None
#             self._guerrilla_sid = sid
#             self._guerrilla_seen = set()
#             self.log(f'<font color="#00FF00"><b>[📧] Meta inbox (Guerrilla API): {email}</b></font>')
#             return email
        if str(provider).lower() in ("mailfish", "tempmail_fish", "fish"):
            self.mail_provider = "mailfish"
            from core import mailfish_api
            if mailfish_api.api_enabled():
                # New accounts: inbox created through the premium API (no browser tab needed).
                email = mailfish_api.create_inbox(style=mailfish_api.alias_style())
                if email:
                    self.email = email
                    self.mail = None
                    self._mailfish_api = True
                    self._mailfish_seen = set()
                    self.log(f'[📧] tempmail.fish API inbox: {email}')
                    return email
                if getattr(mailfish_api, "last_failure", "") == "down":
                    # The service itself is not answering, so its web inbox is down too: do not sit on a blank
                    # page for a minute — raise and let open_mail() try the next provider.
                    raise RuntimeError("tempmail.fish is not answering (API down)")
                self.log('[⚠️] tempmail.fish API inbox failed — falling back to the web inbox.')
            # Old-style web inbox (browser tab + authKey), kept for the fallback path.
            self._mailfish_api = False
            return super().open_mailfish()
        self.mail_provider = "mailtd"
        return super().open_mailtd()

    def _snapshot_mail_session(self) -> dict:
        """Keep the account's mailbox session, whichever provider was chosen.

        Browser-tab providers (mail.td, mailfish) hold their token in the tab's
        localStorage. The values are read while the tab is open and cached on the
        runner, so a tab closed before the account is saved does not lose them.
        """
        cached = dict(getattr(self, "_mail_session", None) or {})
        provider = getattr(self, "mail_provider", "") or ""
        mail = getattr(self, "mail", None)
        fresh = {}
        # DISABLED: Guerrilla session snapshot.
#         if provider == "guerrilla" and getattr(self, "email", ""):
#             from core import guerrilla_api
#             fresh = {"guerrilla_email": self.email,
#                      "guerrilla_sid": guerrilla_api.current_sid(self.email, getattr(self, "_guerrilla_sid", ""))}
        if provider == "mailfish" and getattr(self, "email", ""):
            fresh = {"mailfish_email": self.email}
            if getattr(self, "_mailfish_api", False):
                fresh["mailfish_api"] = True
        try:
            if provider == "mailtd" and mail is not None and not mail.is_closed():
                fresh = mail.evaluate("""() => ({
                    tempmail_token: localStorage.getItem("tempmail_token") || "",
                    tempmail_account_id: localStorage.getItem("tempmail_account_id") || "",
                })""") or {}
            elif provider == "mailfish" and mail is not None and not mail.is_closed():
                # tempmail.fish keeps its inbox key in localStorage (same as engine/eng_mix_mail.py reads it).
                raw = mail.evaluate("() => localStorage.getItem('authKey') || ''") or ""
                key = raw.strip()
                if key.startswith('"'):
                    import json as _json
                    key = _json.loads(key)
                fresh = dict(fresh, mailfish_auth_key=str(key))
        except Exception:
            fresh = {}
        cached.update({k: v for k, v in fresh.items() if v})
        if cached:
            self._mail_session = cached
        return cached

    def new_mail_address(self, timeout: int = 30):
        """Generate a fresh mailbox address (yamin, mailcf, mailtd or mailfish)."""
        provider = getattr(self, "mail_provider", "mailtd") or "mailtd"
        if str(provider).lower() in ("yamin", "yaminbd", "email_yamin", "epicz", "liseller"):
            return super().new_yamin_address(timeout=timeout)
#         if str(provider).lower() in ("guerrilla", "guerrillamail", "gm"):
#             from core import guerrilla_api
#             email, sid = guerrilla_api.create_inbox()
#             if email:
#                 self.email, self._guerrilla_sid, self._guerrilla_seen = email, sid, set()
#             return email or None
        if str(provider).lower() in ("mailcf", "cloudflare", "cf"):
            return super().new_mailcf_address(timeout=timeout)
        if str(provider).lower() in ("mailfish", "tempmail_fish", "fish"):
            return super().new_mailfish_address(timeout=timeout)
        return super().new_mailtd_address(timeout=timeout)

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
        """Fetch an OTP from the active mailbox tab/API (yamin, mailcf, mailtd or mailfish)."""
        # The tab is open while a code is being read: refresh the saved session now.
        self._snapshot_mail_session()
        provider = getattr(self, "mail_provider", "mailtd") or "mailtd"
        if str(provider).lower() in ("yamin", "yaminbd", "email_yamin", "epicz", "liseller"):
            return super().fetch_code_yamin(keyword, timeout=timeout,
                                            subject_hint=subject_hint, prefer_len=prefer_len)
        if str(provider).lower() in ("mailcf", "cloudflare", "cf"):
            return super().fetch_code_cf(keyword, timeout=timeout,
                                         subject_hint=subject_hint, prefer_len=prefer_len)
        # DISABLED: Guerrilla Mail is no longer offered.
#         if str(provider).lower() in ("guerrilla", "guerrillamail", "gm"):
#             from core import guerrilla_api
#             return guerrilla_api.wait_code(
#                 self, self.email, getattr(self, "_guerrilla_sid", ""), keyword=keyword, timeout=timeout,
#                 seen=getattr(self, "_guerrilla_seen", None),
#                 subject_hint=subject_hint, prefer_len=prefer_len)
        if str(provider).lower() in ("mailfish", "tempmail_fish", "fish"):
            if getattr(self, "_mailfish_api", False) and getattr(self, "email", ""):
                from core import mailfish_api
                return mailfish_api.wait_code(
                    self, self.email, keyword=keyword, timeout=timeout,
                    seen=getattr(self, "_mailfish_seen", None),
                    subject_hint=subject_hint, prefer_len=prefer_len)
            return super().fetch_code_mailfish(
                keyword,
                timeout=timeout,
                subject_hint=subject_hint,
                prefer_len=prefer_len,
            )
        try:
            self._ensure_mail_tab()
        except Exception:
            pass
        return super().fetch_code(
            keyword,
            timeout=timeout,
            subject_hint=subject_hint,
            prefer_len=prefer_len,
        )

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
        """Backward-compatible alias for the mail.td provider."""
        self.mail_provider = "mailtd"
        return self._open_mail_once()

    def retire_mail_session(self) -> bool:
        """End the mailcf address once its task is done: the Worker drops it and the token is cleared.

        No-op for mailtd/mailfish. The saved account then has no mailcf_token,
        so its mail can no longer be read.
        """
        if str(getattr(self, "mail_provider", "")).lower() != "mailcf" or not getattr(self, "email", None):
            return False
        ok = retire_mailbox(self.email)
        self.mail_token = ""
        self.log(
            f'[📭] Mail session retired for {self.email}; further mail is dropped.' if ok
            else f'[⚠️] Could not retire mail session for {self.email} (token cleared locally).'
        )
        return ok

    def open_mailcf(self):
        """Alias for the Cloudflare catch-all provider (no browser tab)."""
        self.mail_provider = "mailcf"
        return self._open_mail_once()

#     def open_guerrilla(self):
#         """Alias for the Guerrilla Mail API provider."""
#         self.mail_provider = "guerrilla"
#         return self.open_mail()

    def open_mailfish(self):
        """Backward-compatible alias for the tempmail.fish provider."""
        self.mail_provider = "mailfish"
        return self._open_mail_once()
