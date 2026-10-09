from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

from ai_config import (  # noqa: E402
    ACCOUNTS_CSV,
    ACCOUNTS_TXT,
    AI_DIR,
    SESSIONS_DIR,
    Urls,
    emit_event,
)

import store  # noqa: E402
try:
    from instagram.helpers import IGDeadEnd
except ImportError:  # pragma: no cover - top-level import path
    class IGDeadEnd(Exception):  # type: ignore
        pass


def _is_ig_origin(url: str) -> bool:
    u = (url or "").lower()
    return "instagram.com" in u and "meta.com" not in u and "facebook.com" not in u


def dump_ig_storage_state(context, path: str) -> None:
    """Persist ONLY Instagram state (cookies + localStorage origins).

    Meta/Facebook state is deliberately dropped (IG-only scope): presenting
    Meta cookies from a different device/profile is a checkpoint trigger,
    and nothing in the pipeline consumes Meta state after creation.
    """
    state = context.storage_state()
    try:
        cookies = [c for c in (state.get("cookies") or [])
                   if _is_ig_origin(c.get("domain") or "")]
        origins = [o for o in (state.get("origins") or [])
                   if _is_ig_origin(o.get("origin") or "")]
        state = {"cookies": cookies, "origins": origins}
    except Exception:
        pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


class LifecycleMixin:
    def create_account(self, twofa: bool = False, password: Optional[str] = None,
                       target: Optional[str] = None, meta_only: bool = False) -> str:
        """Phase 1 (parallel): create the Meta+Instagram account.

        Does **not** touch Telegram — the account is parked with
        ``status="Created"`` (and storage_state saved) so a submitter drains it
        later through a free Telegram account or Nitro Follower.

        ``meta_only=True`` stops after the Meta account, human verification,
        and selfie checkpoint complete, then parks it as ``MetaCreated``
        (no Instagram join) — used by the Coinsta direct flow where the
        Instagram signup happens inside the app webview.
        """
        tgt = target or getattr(self, "target", "telegram") or "telegram"
        self._install_screenshot_hooks()
        self._launch()
        self.open_mail()
        self.meta_signup()                        # Meta account + email code
        if not self.ensure_meta_verified():       # reCAPTCHA audio + selfie
            raise RuntimeError("Meta account verification not confirmed — aborting before Instagram to prevent phone wall")
        if meta_only:
            self.save_ai_result(status="MetaCreated", target=tgt)
            return self.last_record_id
        self.ig_login()
        self.ig_click_meta_card()
        self.ig_complete_join()                   # username = bot Login / chosen
        # Fail fast: with no sessionid the onboarding/follow passes only run on a
        # logged-out page (0 follows, ~minutes wasted) — go straight to direct login.
        try:
            _cookies = self.w.context.cookies()
            _names = {c["name"] for c in _cookies if "instagram" in (c.get("domain") or "").lower()} or {c["name"] for c in self.w.context.cookies(Urls.IG_HOME)}
            _has_sid = "sessionid" in _names
        except Exception:
            _has_sid = False
        if _has_sid:
            self.ig_dismiss_onboarding()
        else:
            self.log('[⚠️] No sessionid after join — skipping onboarding/follow passes.')
        ig_page = self._ig_tab()
        if self._has_human_check(ig_page):
            try:
                self._handle_human(ig_page, timeout=30)
            except Exception:
                pass

        # Require a full IG session (sessionid) before parking
        try:
            _cookies = self.w.context.cookies()
            names = [c["name"] for c in _cookies if "instagram" in (c.get("domain") or "").lower()] or [c["name"] for c in self.w.context.cookies(Urls.IG_HOME)]
        except Exception:
            names = []
        if "sessionid" not in set(names):
            self.log('[⚠️] No Instagram sessionid after join — attempting direct login…')
            if not self.ig_direct_login(self.ig_username or self.username or self.email, self.password):
                raise RuntimeError("Instagram session not established (no sessionid); not parking")

        if twofa:
            self.log('[🔐] 2FA Key option enabled — copying Instagram 2FA key from Accounts Center…')
            secret = self.ig_enable_2fa()
            if not secret:
                raise RuntimeError("Instagram 2FA key copy failed (no secret key extracted)")
            self.twofa_secret = secret
            self.insta_secret = secret
            self.log(f'<font color="#00FF00"><b>[✔] 2FA key copied: {secret[:4]}****</b></font>')

        try:
            self.ig_api_profile()       # optional API bio / avatar / first post
        except Exception as exc:
            self.log(f'[⚠️] API profile step note: {str(exc)[:100]}')

        # Phase 2 complete: store username, password, email, and cookies
        self.save_ai_result(status="Created", target=tgt)
        return self.last_record_id

    def resume_session(self, session_file: str, check_meta: bool = False, warm_ctx=None) -> bool:
        """Launch browser with anti-detect settings and restore session state/cookies.

        IG-only scope: only Instagram state is restored; the Meta leg is NOT
        verified (nothing consumes Meta state after creation). Set
        ``runner.device_model`` from the account record BEFORE calling so the
        pinned phone model is presented instead of a random one.
        ``warm_ctx`` attaches an externally created (warm) context instead of
        launching — pair with :meth:`finish_warm`, never :meth:`finish`.
        """
        self._install_screenshot_hooks()
        self._warm_ctx = None
        if warm_ctx is not None:
            self.w.context = warm_ctx
            try:
                _pages = list(warm_ctx.pages)
            except Exception:
                _pages = []
            self.page = _pages[0] if _pages else warm_ctx.new_page()
            self.w.page = self.page
            self._warm_ctx = warm_ctx
        else:
            self._launch()
        if session_file and os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cookies = []
                if isinstance(data, dict) and "cookies" in data:
                    cookies = data["cookies"]
                elif isinstance(data, list):
                    cookies = data
                if cookies:
                    clean_cookies = []
                    for c in cookies:
                        c_copy = dict(c)
                        if c_copy.get("sameSite") == "None" and not c_copy.get("secure"):
                            c_copy["secure"] = True
                        if c_copy.get("expires") == -1:
                            c_copy.pop("expires", None)
                        clean_cookies.append(c_copy)
                    self.w.context.add_cookies(clean_cookies)
                    self.log(f'[🍪] Restored {len(clean_cookies)} session cookies from {os.path.basename(session_file)}')

                # Restore localStorage for Instagram origins only (IG-only scope;
                # Meta/Facebook state is never persisted, see dump_ig_storage_state).
                origins = data.get("origins") or [] if isinstance(data, dict) else []
                prio = [o for o in origins
                        if (_is_ig_origin(str(o.get("origin") or ""))
                            or "mail.td" in str(o.get("origin") or ""))
                        and (o.get("localStorage") or [])][:8]
                n_ls = 0
                if prio:
                    lp = None
                    try:
                        lp = self.w.context.new_page()
                        for origin in prio:
                            try:
                                url = origin.get("origin") or ""
                                items = origin.get("localStorage") or []
                                if not url.startswith(("http://", "https://")) or not items:
                                    continue
                                pairs = {i.get("name"): i.get("value") for i in items if i.get("name")}
                                if not pairs:
                                    continue
                                lp.goto(url, wait_until="domcontentloaded", timeout=30000)
                                lp.wait_for_timeout(1200)
                                lp.evaluate(
                                    "(kv) => { for (const [k, v] of Object.entries(kv))"
                                    " { try { localStorage.setItem(k, v); } catch (e) {} } }",
                                    pairs,
                                )
                                n_ls += len(pairs)
                            except Exception:
                                continue
                    except Exception:
                        pass
                    finally:
                        try:
                            if lp is not None:
                                lp.close()
                        except Exception:
                            pass
                if n_ls:
                    self.log(f'[🍪] Restored {n_ls} localStorage keys across {len(prio)} origins')
            except Exception as exc:
                self.log(f'[⚠️] Session cookie restore error: {exc}')

        p = self._ig_tab()
        # Meta verification (Meta → Instagram → Task)
        if check_meta:
            try:
                p.goto(Urls.META_SIGNUP, wait_until="domcontentloaded", timeout=60000)
                p.wait_for_timeout(4000)
                meta_url = p.url or ""
                meta_body = ""
                try:
                    meta_body = (p.inner_text("body") or "").lower()
                except Exception:
                    pass
                bounced = "instagram.com/accounts/login" in meta_url
                meta_ok = (
                    not bounced
                    and "auth.meta.com" in meta_url
                    and any(k in meta_body for k in ("log out", "accounts centre", "account center", "meta verified"))
                )
                self.log(f'[🌐] Meta session first: ok={meta_ok}')
                if bounced:
                    self.log('[⚠️] Meta front door bounced to Instagram login (Meta cookies dead/expired).')
            except Exception as exc:
                self.log(f'[⚠️] Meta session check warning: {exc}')

        try:
            p.goto(Urls.IG_HOME, wait_until="domcontentloaded", timeout=60000)
            p.wait_for_timeout(3500)
        except Exception as exc:
            self.log(f'[⚠️] Navigating home warning: {exc}')
        try:
            if len((p.inner_text("body") or "").strip()) < 20:
                self.log('[⚠️] Instagram home rendered blank (IG bootstrap rate-limited). '
                         'Session check will likely fail; cooldown if it persists.')
        except Exception:
            pass
        self.ig_dismiss_onboarding()

        names = self._ig_cookie_names()
        is_logged_in = "sessionid" in names
        self.log(f'[🌐] Resumed session verified: logged_in={is_logged_in}')
        return is_logged_in

    def adapt_to_tg_task(self, rec: Dict[str, Any], creds: Dict[str, Any], bot) -> Dict[str, Any]:
        """Adapt a parked account to match the Taskly bot task:
        1. Set First name to creds['first_name']
        2. Set Username to creds['login']
        3. Set Password to creds['password'] (on the Meta profile row in Accounts Center)
        4. Send 2FA key to the bot to get the 6-digit one-time code
        5. Confirm 2FA on Instagram (or confirm already active)
        """
        first_name_raw = creds.get("first_name")
        first_name = None
        if first_name_raw:
            try:
                from pipelines.telegram.tg_worker import _sanitize_name
                first_name = _sanitize_name(first_name_raw)
            except Exception:
                first_name = first_name_raw
        login = creds.get("login")
        password = creds.get("password")
        curr_pw = rec.get("meta_password") or rec.get("password")
        if rec.get("name"):
            self.name = rec["name"]
        if rec.get("username"):
            self.ig_username = rec["username"]
        if curr_pw:
            self.password = curr_pw

        self.log(f'[🔄] Adapting account {rec.get("id")} → Name: {first_name_raw} (clean: {first_name}), User: {login}, Pass: {"*"*len(password) if password else "N/A"}')

        # Order (user requirement): display name FIRST, copied from the bot
        # and applied immediately — never a placeholder-then-fix. The live
        # re-read skip still guards the 2-changes/14-days quota when the
        # name already matches. For a fully bot-named account, start the
        # task BEFORE the IG join and type the bot's first name on the
        # "What's your name?" screen (coupled flow); adapt then only
        # verifies it here.
        # 1. Change display name FIRST, but only when the LIVE name differs.
        # The record's name is stale by design (username edits can rewrite it
        # as a side effect); always re-read before spending a quota change.
        if first_name:
            try:
                live_name = self.ig_get_display_name()
            except Exception:
                live_name = None
            if live_name is not None and (live_name or "").strip().lower() == (first_name or "").strip().lower():
                self.log('[✓] Display name already matches; skipping (quota preserved).')
                self.name = first_name
            else:
                ok_name = self.ig_change_name(first_name)
                if ok_name:
                    self.name = first_name
                else:
                    self.log(f'[⚠️] Could not update name to {first_name}, continuing...')

        # 2. Change username if specified and actually different
        if login and (login or "").strip().lower() != (self.ig_username or "").strip().lower():
            ok_user = self.ig_change_username(login)
            if ok_user:
                self.ig_username = login
            else:
                self.log(f'[⚠️] Could not update username to {login}, continuing...')
        elif login:
            self.log('[✓] Username already matches; skipping.')

        # 3. Set password if specified and actually different (Meta row)
        if password and password != curr_pw:
            ok_pw = self.ig_set_password(password, current_password=curr_pw)
            if ok_pw:
                self.password = password
            else:
                self.log('[⚠️] Could not update password, continuing...')
        elif password:
            self.log('[✓] Password already matches; skipping.')

        # 4. Verify email is linked to Instagram before completing Taskly submission
        try:
            self.ig_link_email_to_instagram(rec.get("email") or self.email)
        except Exception as exc:
            self.log(f'[⚠️] Contact points link check note: {exc}')

        # 5. 2FA strict: fresh key -> submit to bot -> confirm bot code. No fallback.
        # Exception: 2FA already ON from Phase 1 (parked secret exists) — there
        # is no setup screen to confirm into. Submit the parked secret so the
        # bot holds the CURRENT key, require the bot's code as receipt, and
        # cross-check it against local TOTP instead of an IG entry.
        secret = self.ig_2fa_begin()
        if secret:
            self.log(f'[🔑] 2FA secret: {secret}. Submitting to {getattr(bot, "bot_name", "Telegram bot")}…')
            code = bot.submit_2fa_key(secret, allow_local_fallback=False)
            if not code:
                raise RuntimeError("Telegram bot did not return a one-time code")
            self.log(f'[📲] Received verification code: {code}.')
            ok_2fa = self.ig_2fa_confirm(code)
            if not ok_2fa:
                raise RuntimeError("2FA code from bot was rejected by Instagram")
        else:
            parked = rec.get("twofa_secret") or getattr(self, "insta_secret", None)
            if not parked:
                raise RuntimeError("Failed to obtain 2FA key from Account Center")
            self.log('[🔑] 2FA already on; submitting parked secret to '
                     f'{getattr(bot, "bot_name", "Telegram bot")}…')
            code = bot.submit_2fa_key(parked, allow_local_fallback=False)
            if not code:
                raise RuntimeError("Telegram bot did not return a one-time code")
            import pyotp as _pyotp
            if code != _pyotp.TOTP(parked.strip()).now():
                self.log('[⚠️] Bot code differs from local TOTP window; continuing (bot holds the key).')
            secret, code = parked, code

        return {
            "name": self.name or first_name or rec.get("name"),
            "username": self.ig_username or login or rec.get("username"),
            "password": self.password or password or curr_pw,
            "twofa_secret": secret,
            "code": code,
        }

    def run_flow(self):
        """Full meta_auto_ai cycle: Meta signup → Instagram → Telegram submit."""
        self._install_screenshot_hooks()
        self._launch()
        self.open_mail()
        self.meta_signup()                        # Meta account + email confirmation code
        if not self.ensure_meta_verified():       # reCAPTCHA + selfie (MetaAuto method)
            raise RuntimeError("Meta account verification not confirmed on auth.meta.com — aborting before Instagram to prevent phone wall")

        # Telegram task FIRST: its Login/Password will register the account
        if self.telegram:
            self._telegram_start()

        self.ig_login()
        self.ig_click_meta_card()
        self.ig_complete_join()                   # username = bot Login (if any)
        self.ig_dismiss_onboarding()

        # Instagram-side human check, if any
        try:
            self._handle_human(self._ig_tab(), timeout=300)
        except Exception:
            pass

        # username (bot) + password (bot) BEFORE 2FA
        if self.new_username and self.ig_username != self.new_username:
            self.ig_change_username(self.new_username)
        target_pw = self.tg_creds.get("password") or self.new_password
        if target_pw:
            ok_pw = self.ig_set_password(target_pw, current_password=self.password)
            if not ok_pw:
                self.log('[⚠️] Meta-row password change failed; falling back to reset link…')
                self.ig_reset_password(target_pw)

        # 2FA LAST: the bot supplies the code, then submit
        secret = self.ig_2fa_begin() if self.twofa else None
        if secret:
            self._telegram_send_key(secret)
            import pyotp
            self.ig_2fa_confirm(self.tg_code or pyotp.TOTP(secret).now())
        if self.telegram and self.tg:
            try:
                self.tg_submitted = self.tg.mark_registered()
            except Exception as exc:  # noqa: BLE001
                self.log(f'[⚠️] Telegram mark failed: {exc}')
            finally:
                self.tg.close()

        self.save_ai_result(status="Submitted" if self.tg_submitted else "Verified")

    def save_ai_result(self, status: str = "Created", target: Optional[str] = None):
        """Export session, update SQLite/JSON store, CSV, accounts.txt and cookies."""
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        is_meta_only = (status == "MetaCreated")

        rec_id = getattr(self, "last_record_id", None) or f"ai_{int(time.time() * 1000)}_{getattr(self.w, 'slot_id', 1)}"
        self.last_record_id = rec_id
        session_file = ""
        if not is_meta_only:
            session_file = os.path.join(SESSIONS_DIR, f"{rec_id}.json")
            try:
                os.makedirs(SESSIONS_DIR, exist_ok=True)
                if hasattr(self, "w") and getattr(self.w, "context", None):
                    dump_ig_storage_state(self.w.context, session_file)
                    self.log(f'[💾] Saved IG session storage state: {os.path.basename(session_file)}')
            except Exception as exc:
                self.log(f'[⚠️] Note on storage state: {exc}')
                session_file = ""

        # Persist mail.td tokens so LATER phases (warm submitter contexts with
        # no mailbox tab) can re-open the SAME inbox instead of failing the
        # email OTP fetch. Survives store via the `extra` JSON column.
        mail_tokens: dict = {}
        try:
            mail_page = getattr(self, "mail", None)
            if mail_page is not None and not mail_page.is_closed():
                mail_tokens = mail_page.evaluate("""() => {
                    return {
                        tempmail_token: localStorage.getItem("tempmail_token") || "",
                        tempmail_account_id: localStorage.getItem("tempmail_account_id") || "",
                    };
                }""") or {}
        except Exception:
            mail_tokens = {}

        # Extract cookies before saving (only for Instagram accounts; Meta Creator does not store cookies)
        cookies_list = []
        cookie_str = ""
        if not is_meta_only:
            try:
                if hasattr(self, "w") and getattr(self.w, "context", None):
                    cookies_list = self.w.context.cookies()
                    ig_cookies = [c for c in cookies_list if "instagram.com" in c.get("domain", "")]
                    chosen = ig_cookies if ig_cookies else cookies_list
                    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in chosen if c.get("name") and c.get("value") is not None)
            except Exception:
                pass

        tgt = target or getattr(self, "target", None) or ("meta" if is_meta_only else "Meta")
        rec = {
            "id": rec_id,
            "target": tgt,
            "mail_tokens": mail_tokens if isinstance(mail_tokens, dict) else {},
            "name": getattr(self, "tg_creds", {}).get("first_name") or getattr(self, "name", "") or "",
            "email": getattr(self, "email", "") or "",
            "password": getattr(self, "password", "") or "",
            "meta_password": getattr(self, "password", "") or "",
            "username": getattr(self, "ig_username", None) or getattr(self, "username", None) or "",
            "instagram_username": "" if is_meta_only else (getattr(self, "ig_username", None) or getattr(self, "username", None) or ""),
            "twofa_secret": getattr(self, "insta_secret", None) or "",
            "session_file": session_file,
            "tg_account": getattr(self, "tg_id", "") or "",
            "tg_login": getattr(self, "tg_creds", {}).get("login", ""),
            "tg_password": getattr(self, "tg_creds", {}).get("password", ""),
            "tg_one_time_code": getattr(self, "tg_code", "") or "",
            "tg_submitted": getattr(self, "tg_submitted", False),
            "tg_bot": getattr(self, "tg_bot", ""),
            "dob": f"{getattr(self, 'dob_year', '1995')}-{getattr(self, 'dob_month', '5')}-{getattr(self, 'dob_day', '12')}",
            "mail_provider": getattr(self, "mail_provider", "mailtd"),
            "profile_dir": getattr(getattr(self, "w", None), "user_data_dir", None) or "",
            "device_model": getattr(self, "device_model", None) or "",
            "device_ua": getattr(self, "device_ua", None) or "",
            "created_at": created,
            "status": status,
            "platform": "Meta" if is_meta_only else "Meta+Instagram",
            "cookies": cookie_str,
            "cookie": cookie_str,
            # How many suggested profiles this account followed at creation.
            # The PayGo cookie POOL drain reads this and skips its own follow
            # step when >= 5 (the bot's mandatory subscriptions).
            "followed": int(getattr(self, "ig_followed_count", 0) or 0),
        }

        # Follow enabled but < 5 followed → keep the account out of the IG list.
        if not is_meta_only:
            try:
                want = int(os.environ.get("INSTA_FOLLOW_COUNT", "0") or 0)
            except Exception:
                want = 0
            on = str(os.environ.get("INSTA_FOLLOW_AFTER_LOGIN", "1")).strip().lower() not in ("0", "false", "no", "off")
            if on and want >= 5 and rec["followed"] < 5:
                self.log(f'[⚠️] Followed only {rec["followed"]}/5 — not adding @{rec["username"] or rec["email"]} to the IG list')
                try:
                    if session_file and os.path.exists(session_file):
                        os.remove(session_file)
                except Exception:
                    pass
                # Raise (not return): worker.py treats a return as success and
                # would announce an account_created that was never stored.
                self.last_record_id = None
                raise RuntimeError(f"Follow incomplete ({rec['followed']}/5) — account not added to the IG list")

        # 1. JSON & SQLite (dashboard) — thread-safe store insert
        try:
            store.add(rec)
        except Exception as exc:
            self.log(f'[⚠️] Store add notice: {exc}')
        self.last_record_id = rec["id"]

        # 4. Raw Playwright cookies export
        try:
            if cookies_list:
                cdir = os.path.join(AI_DIR, "cookies")
                os.makedirs(cdir, exist_ok=True)
                fn = os.path.join(cdir, f"cookies_{rec['id']}.txt")
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(cookies_list, f, indent=2)
        except Exception:
            pass

        # 5. Dashboard SSE broadcast & log
        try:
            public_rec = {k: rec.get(k) for k in (
                "id", "target", "status", "name", "email", "username",
                "instagram_username", "twofa_secret", "tg_account", "tg_login", "tg_submitted",
                "tg_bot", "dob", "mail_provider", "created_at", "platform", "cookies")}
            emit_event({
                "type": "account_created",
                "slot_id": getattr(self.w, "slot_id", 1),
                "id": rec_id,
                "email": rec["email"],
                "name": rec["name"],
                "account": public_rec
            })
        except Exception:
            pass
        self.log(f'<font color="#00FF00"><b>[🎉] Saved: @{rec["username"] or rec["email"]} (ID: {rec_id})</b></font>')
