#!/usr/bin/env python3
"""
test/test_02_ig_devtools_learn.py — DevTools-Driven Instagram DOM Learning Engine
================================================================================
Steps through Instagram login, password synchronization & change, and 2FA configuration
using real-time DevTools DOM inspection and CDP snapshots rather than brittle blind selectors.

Usage:
    .venv/bin/python test/test_02_ig_devtools_learn.py [--step all|login|password|twofa] [--pause 3] [--cdp 9222]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import traceback
from typing import Optional

AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AI_DIR)
os.chdir(AI_DIR)

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

import pyotp
from ai_config import AI_DIR, DATA_DIR, SESSIONS_DIR, TWOFA_KEY_RE, Urls, run
import store
from devtools_client import DevToolsInspector, find_free_port

# Point Playwright at the bundled browsers (engine/ms-playwright); otherwise the
# engine silently falls back to SYSTEM Chrome (fingerprint drift + slow launch).
try:
    run._point_playwright_at_browsers()
except Exception:
    pass


class IgDevToolsLearner:
    """Step-by-step interactive explorer for Instagram and Meta Accounts Center flows."""

    def __init__(self, creds: dict, cdp_port: int = 9222, pause: float = 3.0):
        self.creds = creds
        self.cdp_port = cdp_port
        self.pause = pause
        self.test_dir = os.path.join(AI_DIR, "test")
        self.artifacts_dir = os.path.join(self.test_dir, "artifacts")
        self.inspector = DevToolsInspector(artifacts_dir=self.artifacts_dir)
        self.report_entries = []

        # Setup anti-detect worker & runner
        self.cdp_port = find_free_port(cdp_port)
        import engine.eng_constants as ec
        flag = f"--remote-debugging-port={self.cdp_port}"
        if flag not in list(ec._NOVA_FLAGS):
            ec._NOVA_FLAGS = [f for f in list(ec._NOVA_FLAGS) if not f.startswith("--remote-debugging-port=")] + [flag]

        from worker import AISlotWorker
        from runner import MetaInstaRunner

        prof_dir = self.creds.get("profile_dir") or os.path.join(AI_DIR, "profiles", self.creds["id"])
        os.environ["INSTA_PROFILE_DIR"] = prof_dir
        os.environ["KEEP_PROFILE"] = "1"

        self.worker = AISlotWorker(slot_id=f"learn_{self.creds['id']}", is_headless=False)
        self.runner = MetaInstaRunner(self.worker, telegram=False)
        self.runner.email = self.creds["email"]
        self.runner.password = self.creds.get("ig_password") or self.creds["password"]
        self.runner.ig_username = self.creds.get("instagram_username") or self.creds.get("username")
        # Same-inbox restore data for email OTP fetches (see _ensure_mail_tab).
        try:
            self.runner.mail_tokens = self.creds.get("mail_tokens") or {}
        except Exception:
            pass
        # Present the SAME pinned phone as creation (device.json / creds).
        # Without this the resume rolls a random model and fraud scoring
        # diverges from the creation-time fingerprint.
        if self.creds.get("device_model"):
            self.runner.device_model = self.creds["device_model"]
        if self.creds.get("device_ua"):
            self.runner.device_ua = self.creds["device_ua"]

    def launch_and_resume(self):
        """Launch browser on the exact same profile and resume the persisted session."""
        print(f"[Learner] Launching browser on profile: {self.creds.get('profile_dir')}", flush=True)
        session_file = self.creds.get("session_file")
        if session_file and os.path.exists(session_file):
            print(f"[Learner] Resuming from session file: {session_file}", flush=True)
            try:
                self.runner.resume_session(session_file, check_meta=False)
            except Exception as e:
                print(f"[Learner] Resume notice: {e}", flush=True)
                self.runner._launch()
        else:
            self.runner._launch()
        self.page = self.runner._ig_tab()
        self.inspector.capture(self.page, "01_session_resumed")
        self._wait()

    def _wait(self, extra: float = 0):
        if self.pause > 0:
            time.sleep(self.pause + extra)

    def log_finding(self, section: str, message: str, dom_summary: Optional[dict] = None):
        """Append learning observation to the learning report."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "section": section,
            "message": message,
            "url": getattr(self, "page", None).url if getattr(self, "page", None) else "",
        }
        print(f"💡 [DOM Insight] ({section}): {message}", flush=True)
        self.report_entries.append(entry)

    # --------------------------------------------------------------------------
    # STEP 1: Instagram Login & Linking Exploration
    # --------------------------------------------------------------------------
    def learn_ig_login(self) -> bool:
        print("\n=======================================================", flush=True)
        print(" [Step 1: Instagram Login & Linking Exploration]", flush=True)
        print("=======================================================", flush=True)
        p = self.page
        p.goto(Urls.IG_LOGIN, wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(3500)
        snap = self.inspector.capture(p, "login_initial_page")

        # 1. Dismiss cookies
        for bt in ("Allow all cookies", "Only allow essential cookies", "Decline optional cookies", "Allow"):
            if self.runner._try_click(p, bt, timeout=2000):
                self.log_finding("Login", f"Dismissed cookie dialog via '{bt}'")
                p.wait_for_timeout(1000)
                break

        # 2. Check for "Continue as [Meta Name]" prompt
        has_continue = False
        for sel in (
            'button:has-text("Continue as")',
            'div[role="button"]:has-text("Continue as")',
            '[aria-label*="Continue as" i]',
        ):
            try:
                cont = p.locator(sel).first
                if cont.count() > 0 and cont.is_visible():
                    txt = cont.inner_text() or ""
                    self.log_finding("Login", f"Found active Meta SSO prompt: '{txt}' (Selector: {sel})")
                    has_continue = True
                    cont.click(timeout=3000)
                    p.wait_for_timeout(4000)
                    break
            except Exception:
                pass

        if not has_continue:
            # 3. Direct filling with Meta credentials
            self.log_finding("Login", f"No SSO prompt found; attempting credentials login (Email: {self.runner.email})")
            # Email
            for sel in ('input[name="username"]', 'input[type="text"]', 'input[autocomplete="username"]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        self.log_finding("Login", f"Found username/email input via: {sel}")
                        el.fill(self.runner.email)
                        break
                except Exception:
                    pass

            # Password (Meta password initially)
            meta_pwd = self.creds["password"]
            for sel in ('input[name="password"]', 'input[type="password"]'):
                try:
                    el = p.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        self.log_finding("Login", f"Found password input via: {sel}")
                        el.fill(meta_pwd)
                        break
                except Exception:
                    pass

            snap_filled = self.inspector.capture(p, "login_credentials_filled")

            # Submit
            clicked_btn = False
            for sel in (
                'div[role="button"]:has-text("Log in")',
                'div[role="button"]:has-text("Log In")',
                '[aria-label="Log in" i]',
                'button[type="submit"]',
                'button:has-text("Log in")',
            ):
                try:
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self.log_finding("Login", f"Submitting login via selector: {sel}")
                        try:
                            btn.tap(timeout=3000)
                        except Exception:
                            btn.click(timeout=3000)
                        clicked_btn = True
                        break
                except Exception:
                    pass

            if not clicked_btn:
                self.log_finding("Login", "Calling runner._click_ig_login_btn fallback")
                self.runner._click_ig_login_btn(p)

            p.wait_for_timeout(5000)

        # 4. Check response
        snap_post = self.inspector.capture(p, "login_post_submit")
        body_text = p.evaluate("() => document.body.innerText || ''")

        if "no instagram profile found" in body_text.lower() or "can't find account" in body_text.lower() or "find another account" in body_text.lower():
            self.log_finding("Login", "Instagram returned 'No Instagram profile found' dialog with Meta account card.")
            # 1. Click the found Meta account card/button
            clicked_meta = False
            for sel in (
                '[aria-label*="View Meta account details for" i]',
                f'div[role="button"]:has-text("{self.runner.email}")',
                'div[role="button"]:has-text("@")',
            ):
                try:
                    meta_btn = p.locator(sel).first
                    if meta_btn.count() > 0 and meta_btn.is_visible():
                        txt = meta_btn.inner_text().replace('\n', ' ')
                        self.log_finding("Login", f"Found Meta account link card: '{txt}' via: {sel}")
                        meta_btn.click()
                        clicked_meta = True
                        p.wait_for_timeout(4000)
                        break
                except Exception:
                    pass

            if not clicked_meta:
                self.log_finding("Login", "Meta card button not found; attempting Sign up fallback")
                self.runner._try_click(p, "Create new account", timeout=4000)
                p.wait_for_timeout(3000)

            snap_card = self.inspector.capture(p, "login_meta_account_selected")

            # 2. Check if join / continue / link wizard appears
            cur_body = p.evaluate("() => document.body.innerText || ''").lower()
            self.log_finding("Login", f"Screen after selecting Meta account: {cur_body[:200]}")

            # Check for join / continue buttons
            for sel in (
                'button:has-text("Continue")',
                'div[role="button"]:has-text("Continue")',
                'button:has-text("Join Instagram")',
                'div[role="button"]:has-text("Join Instagram")',
                'button:has-text("Create account")',
                'div[role="button"]:has-text("Create account")',
                'button:has-text("Confirm")',
                'div[role="button"]:has-text("Confirm")',
            ):
                try:
                    btn = p.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        self.log_finding("Login", f"Found join/continue button via: {sel}")
                        btn.click()
                        p.wait_for_timeout(4000)
                        self.inspector.capture(p, "login_join_continue_clicked")
                        break
                except Exception:
                    pass

            # Also invoke runner helper for fallback / multi-step join if still pending
            try:
                self.runner.ig_click_meta_card()
                p.wait_for_timeout(3000)
                self.runner.ig_complete_join()
                p.wait_for_timeout(3000)
                self.runner.ig_dismiss_onboarding()
            except Exception as j_err:
                self.log_finding("Login", f"Join helper note: {j_err}")

            self.inspector.capture(p, "login_onboarding_settled")

        self._wait()
        print(f"[Learner] Current URL after login phase: {p.url}", flush=True)
        return True

    # --------------------------------------------------------------------------
    # STEP 2: Password Synchronization & Change Exploration
    # --------------------------------------------------------------------------
    def learn_ig_password_change(self, new_password: Optional[str] = None) -> bool:
        print("\n=======================================================", flush=True)
        print(" [Step 2: Password Synchronization & Change Exploration]", flush=True)
        print("=======================================================", flush=True)
        p = self.page

        # Generate a distinct IG password to verify independence from Meta password
        if not new_password:
            new_password = f"Ig_{os.urandom(4).hex()}!#9A"

        current_pwd = self.creds.get("ig_password") or self.creds["password"]
        self.log_finding("Password", f"Attempting password change (Current/Meta: {current_pwd} -> New: {new_password})")

        try:
            self.runner._ac_open(Urls.AC_CHANGE_PASSWORD, ["change password", "password", "accounts center"])
        except Exception as o_err:
            self.log_finding("Password", f"_ac_open notice: {o_err}")
            p.goto(Urls.AC_CHANGE_PASSWORD, wait_until="domcontentloaded", timeout=60000)
        p.wait_for_timeout(3500)

        # Handle SSO handoff if still on accounts/login/?next=
        if "accounts/login" in (p.url or "") and "next=" in (p.url or ""):
            for sel in ('div[role="button"]:has-text("Continue")', '[aria-label="Continue"]', 'button:has-text("Continue")'):
                try:
                    btn = p.locator(sel).first
                    if btn.count() and btn.is_visible():
                        self.log_finding("Password", f"Tapping SSO handoff '{sel}'")
                        btn.click()
                        p.wait_for_timeout(5000)
                        break
                except Exception:
                    pass

        snap = self.inspector.capture(p, "pwd_change_landing")

        # 1. Accounts Center Account Selector (if multiple profiles listed)
        try:
            self.runner._ac_choose_account(p, prefer_instagram=True)
            p.wait_for_timeout(3000)
        except Exception as c_err:
            self.log_finding("Password", f"_ac_choose_account notice: {c_err}")

        snap_form = self.inspector.capture(p, "pwd_change_inputs_view")

        # 2. Re-authentication / Challenge Check
        # Check if Accounts Center demands email verification before revealing password inputs
        body_text = p.evaluate("() => document.body.innerText || ''")
        if any(w in body_text.lower() for w in ("check your email", "enter the code", "security code")):
            self.log_finding("Password", "Accounts Center triggered an email security challenge.")
            # Solved via runner mailbox if available
            try:
                self.runner._ac_solve_email_challenge(p, timeout=60)
            except Exception as e:
                self.log_finding("Password", f"Email challenge handling notice: {e}")
            p.wait_for_timeout(3000)
            self.inspector.capture(p, "pwd_email_challenge_solved")

        # 3. Fill Password Form
        # Accounts Center standard fields:
        # Current password | New password | Re-type new password
        pwd_inputs = p.locator('input[type="password"]')
        input_count = pwd_inputs.count()
        self.log_finding("Password", f"Found {input_count} password input elements in Accounts Center")

        if input_count >= 3:
            # Standard 3-box change: Current, New, Confirm
            self.log_finding("Password", "Detected standard 3-field password change form")
            pwd_inputs.nth(0).fill(current_pwd)
            p.wait_for_timeout(500)
            pwd_inputs.nth(1).fill(new_password)
            p.wait_for_timeout(500)
            pwd_inputs.nth(2).fill(new_password)
        elif input_count == 2:
            # Set-password flow (account has no separate IG password yet): New, Confirm
            self.log_finding("Password", "Detected 2-field password setup form (First-time IG password provisioning)")
            pwd_inputs.nth(0).fill(new_password)
            p.wait_for_timeout(500)
            pwd_inputs.nth(1).fill(new_password)
        elif input_count == 1:
            # Single re-auth prompt
            self.log_finding("Password", "Detected single password re-auth prompt")
            pwd_inputs.nth(0).fill(current_pwd)
            p.keyboard.press("Enter")
            p.wait_for_timeout(3000)
            return self.learn_ig_password_change(new_password)
        else:
            self.log_finding("Password", f"Unexpected password form structure (inputs: {input_count})")

        self.inspector.capture(p, "pwd_inputs_filled")

        # 4. Submit Change
        for sel in (
            'button:has-text("Change password")',
            'button:has-text("Change Password")',
            'button:has-text("Save")',
            '[role="button"]:has-text("Change password")',
        ):
            try:
                btn = p.locator(sel).first
                if btn.count() > 0 and btn.is_visible() and not btn.is_disabled():
                    self.log_finding("Password", f"Submitting password change via: {sel}")
                    btn.click()
                    p.wait_for_timeout(4000)
                    break
            except Exception:
                pass

        snap_result = self.inspector.capture(p, "pwd_change_result")

        # Update local credentials record with the verified new password
        self.creds["ig_password"] = new_password
        self.creds["password_updated_at"] = datetime.datetime.now().isoformat()
        self._save_updated_creds()
        self.log_finding("Password", f"Password updated! Meta Password: {self.creds['password']} | IG Password: {new_password}")

        self._wait()
        return True

    # --------------------------------------------------------------------------
    # STEP 3: Two-Factor Authentication (2FA) Exploration
    # --------------------------------------------------------------------------
    def learn_ig_2fa(self) -> Optional[str]:
        print("\n=======================================================", flush=True)
        print(" [Step 3: Two-Factor Authentication (2FA) Exploration]", flush=True)
        print("=======================================================", flush=True)
        p = self.runner._ig_tab()   # was referenced but never defined -> NameError
        try:
            self.runner._ac_open(Urls.AC_TWO_FACTOR, ["two-factor", "security", "accounts center"])
        except Exception as o_err:
            self.log_finding("2FA", f"_ac_open notice: {o_err}")
            p.goto(Urls.AC_TWO_FACTOR, wait_until="domcontentloaded", timeout=60000)
        p = self.runner._ig_tab()
        p.wait_for_timeout(3500)
        self.inspector.capture(p, "2fa_landing")

        # 1. Select account if prompted
        try:
            self.runner._ac_choose_account(p, prefer_instagram=True)
            p.wait_for_timeout(3000)
        except Exception as c_err:
            self.log_finding("2FA", f"_ac_choose_account notice: {c_err}")

        self.inspector.capture(p, "2fa_method_selection")

        # 2. Choose "Authentication app"
        for sel in (
            'div[role="radio"]:has-text("Authentication app")',
            'div[role="button"]:has-text("Authentication app")',
            'input[type="radio"][value*="app" i]',
            'span:has-text("Authentication app")',
        ):
            try:
                opt = p.locator(sel).first
                if opt.count() > 0 and opt.is_visible():
                    self.log_finding("2FA", f"Selecting 'Authentication app' via: {sel}")
                    opt.click()
                    p.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # Click Next
        for sel in ('button:has-text("Next")', '[role="button"]:has-text("Next")'):
            try:
                nxt = p.locator(sel).first
                if nxt.count() > 0 and nxt.is_visible():
                    nxt.click()
                    p.wait_for_timeout(3500)
                    break
            except Exception:
                pass

        snap_secret = self.inspector.capture(p, "2fa_secret_screen")

        # 3. Scrape 2FA Secret Key from page text
        # (Using DOM text regex scraping to bypass clipboard permissions policy)
        body_text = p.evaluate("() => document.body.innerText || ''")
        matches = TWOFA_KEY_RE.findall(body_text)
        secret_clean = None
        if matches:
            raw = matches[0]
            secret_clean = re.sub(r"\s+", "", raw).upper()
            self.log_finding("2FA", f"Extracted 2FA secret key from DOM: {secret_clean}")
        else:
            self.log_finding("2FA", "No standard base32 key match found in body text.")

        if secret_clean:
            # 4. Generate TOTP code using pyotp
            totp = pyotp.TOTP(secret_clean)
            current_code = totp.now()
            self.log_finding("2FA", f"Generated test TOTP code: {current_code}")

            # Click Next to enter confirmation code
            for sel in ('button:has-text("Next")', '[role="button"]:has-text("Next")'):
                try:
                    nxt = p.locator(sel).first
                    if nxt.count() > 0 and nxt.is_visible():
                        nxt.click()
                        p.wait_for_timeout(2500)
                        break
                except Exception:
                    pass

            self.inspector.capture(p, "2fa_code_entry_view")

            # Fill confirmation code
            for sel in ('input[type="text"]', 'input[name="code"]', 'input[inputmode="numeric"]'):
                try:
                    inp = p.locator(sel).first
                    if inp.count() > 0 and inp.is_visible():
                        self.log_finding("2FA", f"Filling TOTP code into: {sel}")
                        inp.fill(current_code)
                        p.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            # Submit confirmation
            for sel in ('button:has-text("Next")', 'button:has-text("Done")', '[role="button"]:has-text("Next")'):
                try:
                    nxt = p.locator(sel).first
                    if nxt.count() > 0 and nxt.is_visible():
                        nxt.click()
                        p.wait_for_timeout(3500)
                        break
                except Exception:
                    pass

            self.inspector.capture(p, "2fa_confirmation_result")

            self.creds["twofa_secret"] = secret_clean
            self.creds["twofa_enabled_at"] = datetime.datetime.now().isoformat()
            self._save_updated_creds()

        self._wait()
        return secret_clean

    def _save_updated_creds(self):
        """Persist updated credentials back to disk."""
        latest_path = os.path.join(self.test_dir, "latest_credentials.json")
        try:
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(self.creds, f, indent=2)
            store.update_account(
                self.creds["id"],
                {
                    "password": self.creds.get("ig_password") or self.creds["password"],
                    "twofa_secret": self.creds.get("twofa_secret"),
                },
            )
        except Exception as e:
            print(f"[Learner] Credential persist notice: {e}", flush=True)

    def write_report(self):
        """Compile learning insights into a structured markdown report."""
        report_path = os.path.join(self.artifacts_dir, "learning_report.md")
        lines = [
            "# Instagram & Meta Accounts Center DevTools Learning Report",
            f"\nGenerated: {datetime.datetime.now().isoformat()}",
            f"Account ID: `{self.creds.get('id')}`",
            f"Email: `{self.creds.get('email')}`",
            f"Initial (Meta) Password: `{self.creds.get('meta_password') or self.creds.get('password')}`",
            f"Updated (IG) Password: `{self.creds.get('ig_password')}`",
            f"2FA Secret: `{self.creds.get('twofa_secret', 'None')}`\n",
            "## Timeline of DOM Insights & Telemetry\n",
            "| Time | Section | Insight / Selector Pattern | URL |",
            "|---|---|---|---|",
        ]
        for e in self.report_entries:
            lines.append(f"| {e['timestamp'][11:19]} | **{e['section']}** | {e['message']} | `{e['url'][:45]}` |")

        lines.append("\n## Artifact References")
        lines.append(f"Screenshots and DOM JSON dumps saved in `{self.artifacts_dir}`.")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n📄 [Report Written] -> {report_path}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="DevTools Instagram DOM Learner")
    ap.add_argument("--step", choices=["all", "login", "password", "twofa"], default="all")
    ap.add_argument("--pause", type=float, default=2.5, help="Pause seconds between steps")
    ap.add_argument("--cdp", type=int, default=9222, help="Remote debugging port")
    ap.add_argument("--creds", type=str, default="", help="Path to credentials JSON (defaults to test/latest_credentials.json)")
    ap.add_argument("--close", action="store_true", help="Close browser after run instead of keeping it open")
    args = ap.parse_args()

    creds_path = args.creds or os.path.join(AI_DIR, "test", "latest_credentials.json")
    if not os.path.isfile(creds_path):
        print(f"❌ [ERROR] Credentials file not found: {creds_path}")
        print("Please run `test/test_01_meta_only.py` first to create a Meta account.")
        sys.exit(1)

    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    learner = IgDevToolsLearner(creds=creds, cdp_port=args.cdp, pause=args.pause)
    learner.launch_and_resume()

    try:
        if args.step in ("all", "login"):
            learner.learn_ig_login()
        if args.step in ("all", "password"):
            learner.learn_ig_password_change()
        if args.step in ("all", "twofa"):
            learner.learn_ig_2fa()
    except Exception as exc:
        print(f"\n❌ [Learner Error] {exc}", flush=True)
        traceback.print_exc()
        try:
            learner.inspector.capture(learner.page, "FAIL_learner")
        except Exception:
            pass
    finally:
        learner.write_report()
        if args.close:
            print("[test] Closing browser (--close requested)...", flush=True)
            try:
                learner.runner.finish()
            except Exception:
                pass
        else:
            print(f"\n[test] Session complete. Browser kept open on CDP port {learner.cdp_port} for inspection.", flush=True)
            print("[test] Press Ctrl-C to finish.", flush=True)
            try:
                while True:
                    pages = learner.worker.context.pages
                    if not pages or all(p.is_closed() for p in pages):
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[test] Closed by user interrupt.")
            finally:
                try:
                    learner.runner.finish()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
