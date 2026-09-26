from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os
import time

from ai_config import run  # noqa: E402


class MetaCheckpointBlocked(RuntimeError):
    """Meta refused the signup at the human-verification checkpoint.

    The screen reads "Confirm that you're human" with a **Try again later**
    button and "Your computer or network may be sending automated queries … we
    can't process your request right now" (auth.meta.com/checkpoint…).

    This is an IP/NETWORK-level block, NOT a solvable captcha: there is nothing
    to solve, and the reCAPTCHA widget is disabled. Retrying, re-solving or
    re-uploading just parks the slot on a dead screen and burns the account
    (observed 2026-09-26). Terminal for this account — raise so the cycle closes
    the browser and moves to the next one, i.e. the same close-and-move-on
    semantics as IGDeadEnd (invariant 17). The real cure is a clean egress
    (per-account proxy) and a non-temp mail domain (invariant 17), not a retry.
    """


# Markers unique to the "we refused you" checkpoint, as opposed to a normal
# solvable reCAPTCHA. 'try again later' alone is too generic on its own, so it
# is always paired with the automated-queries wording.
_META_IP_BLOCK_MARKERS = (
    "may be sending automated queries",
    "we can't process your request right now",
    "we cannot process your request right now",
    "sending automated queries",
)


def _meta_ip_blocked(body: str, url: str) -> bool:
    """True for Meta's terminal 'automated queries' checkpoint refusal."""
    b = (body or "").lower()
    u = (url or "").lower()
    if not any(m in b for m in _META_IP_BLOCK_MARKERS):
        return False
    return ("confirm that you're human" in b
            or "checkpoint" in u
            or "try again later" in b)


class CaptchaMixin:
    def ensure_meta_verified(self, timeout: int = 600) -> bool:
        """Human verification, done intentionally like before.

        Called right after Meta signup/login success: visits the checkpoint
        front door on purpose and solves reCAPTCHA + selfie until clear.
        Only after this returns does the flow move to Instagram.
        """
        p = self.page
        per = max(120, timeout // 4)
        for attempt in range(1, 5):
            self.log(f'[🛡️] Meta human verification — attempt {attempt}')
            cur_url = (p.url or "").lower()
            cur_body = ""
            try:
                cur_body = (p.inner_text("body") or "").lower()
            except Exception:
                pass

            # Terminal IP/network block — bail BEFORE attempting to solve, or we
            # park the slot on a dead screen and burn the account. Raises so the
            # cycle closes the browser and moves on (IGDeadEnd semantics).
            if _meta_ip_blocked(cur_body, cur_url):
                raise MetaCheckpointBlocked(
                    'Meta human-verification checkpoint refused the request '
                    '("Try again later" / "sending automated queries") — an '
                    'IP/network block, not a solvable captcha. Closing the '
                    'browser and moving to the next account.')

            # Already clear on meta.ai with no active human check/checkpoint.
            is_meta_ai_success = (
                any(x in cur_url for x in ("meta.ai/?", "meta.ai/home", "meta.ai/chat", "meta.ai/prompt"))
                and "error=" not in cur_url
                and "sign in to get started" not in cur_body
            )
            has_checkpoint = self._has_human_check(p) or "confirm" in cur_body or "checkpoints" in cur_url
            if is_meta_ai_success and not has_checkpoint:
                self.log('<font color="#00FF00"><b>[✔] Meta session authenticated on meta.ai naturally.</b></font>')
                return True

            # Intentional visit: drive to the checkpoint front door so any
            # pending verification shows itself and gets solved now.
            if attempt > 1 or (not is_meta_ai_success and "checkpoints" not in cur_url and not has_checkpoint):
                try:
                    p.goto(run._META_AUTH_URL, wait_until="domcontentloaded", timeout=60000)
                    p.wait_for_timeout(4000)
                except Exception:
                    pass

            try:
                cur_body = (p.inner_text("body") or "").lower()
            except Exception:
                pass
            cur_url = (p.url or "").lower()

            # Account chooser ("Log in with your Meta Account"): click the
            # saved account row FIRST — human verification comes after it
            # (live 2026-09-17). The row shows a MASKED email, so match any
            # @ row except "Use another account".
            if "log in with your meta account" in cur_body or "use another account" in cur_body:
                self.log('[🌐] Meta account chooser — clicking the saved account row…')
                try:
                    hit = p.evaluate("""() => {
                        const els = [...document.querySelectorAll('button, div[role="button"], a')];
                        for (const el of els) {
                            const t = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
                            const r = el.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) continue;
                            if (t.includes('use another account')) continue;
                            if (t.includes('@')) { el.click(); return true; }
                        }
                        return false;
                    }""")
                except Exception:
                    hit = False
                if not hit and getattr(self, "email", None):
                    # Unmasked variant: try our full email as button text.
                    hit = self._try_click(p, self.email, timeout=4000)
                p.wait_for_timeout(4000)
                self._poll_checkpoint_settled(p, timeout=8)
                try:
                    cur_body = (p.inner_text("body") or "").lower()
                except Exception:
                    pass
                cur_url = (p.url or "").lower()

            if self._has_human_check(p) or "confirm" in cur_body or "checkpoints" in cur_url:
                self._try_click(p, "Continue", timeout=8000)
                self._poll_checkpoint_settled(p, timeout=8)
                # reCAPTCHA audio + selfie + Continue
                self._meta_selfie_checkpoint(p, timeout=per)
                self._try_click(p, "Continue", timeout=8000)
                self._poll_checkpoint_settled(p, timeout=8)
                # Early exit: as soon as the human check is gone we are DONE.
                # The old code also required "checkpoints" to leave the URL, so
                # it ran attempts 2-4 (each re-entering the selfie checkpoint)
                # for ~23s AFTER the selfie had already been accepted.
                if not self._has_human_check(p):
                    self.log('<font color="#00FF00"><b>[✔] Meta human verification cleared.</b></font>')
                    return True
            if not self._has_human_check(p) and "checkpoints" not in (p.url or ""):
                self.log('<font color="#00FF00"><b>[✔] Meta human verification cleared.</b></font>')
                return True
            p.wait_for_timeout(3000)
        self.log('[⚠️] Meta human verification still pending.')
        return not self._has_human_check(p)

    def _captcha_order(self):
        """Solver order: dashboard pick first, the other second (auto-fallback)."""
        if getattr(self, "captcha_mode", "extension") == "audio":
            return ("audio", "extension")
        return ("extension", "audio")

    def _extension_available(self):
        """True when the Visual AI extension directory is present."""
        try:
            from ai_config import CAPTCHA_EXT_DIR
            return bool(CAPTCHA_EXT_DIR and os.path.isdir(CAPTCHA_EXT_DIR))
        except Exception:
            return False

    def _extension_active(self):
        """True when the JA extension is actually RUNNING in this browser.

        Headless shell (Background mode) silently ignores --load-extension,
        so the extension directory can exist while nothing runs. Since we
        launch with --disable-extensions-except, ANY running extension
        worker must be ours.
        """
        try:
            ctx = getattr(getattr(self, "w", None), "context", None)
            if ctx is None:
                return False
            urls = [w.url for w in list(ctx.service_workers) + list(ctx.background_pages)]
            return any((u or "").startswith("chrome-extension://") for u in urls)
        except Exception:
            return False

    def _wait_for_extension_solve(self, page, timeout=90):
        """Skip Visual immediately when the extension isn't running.

        Without this, every Background-mode checkpoint burns 45s waiting
        for an extension that headless shell can never load, before
        falling back to Audio STT anyway.
        """
        if not self._extension_active():
            self.log("[🧩] Visual AI extension not running in this browser (headless shell) — Audio STT directly…")
            return False
        return super()._wait_for_extension_solve(page, timeout=timeout)

    def _solve_captcha_ordered(self, page):
        """Try solvers in dashboard order; True when the check clears."""
        for solver in self._captcha_order():
            try:
                if not self._has_human_check(page):
                    return True
            except Exception:
                return True
            try:
                if solver == "extension":
                    if not self._extension_available():
                        continue
                    # NOTE (2026-09-23): measured across telegram_20260923_010221
                    # the JA extension solved 0/229 real challenges (only the
                    # fast anchor auto-verify worked, 161x); the long 90s wait
                    # was wasted. Default lowered, env-tunable.
                    try:
                        _vt = float(os.environ.get("INSTA_VISUAL_CAPTCHA_TIMEOUT", "30") or 30)
                    except Exception:
                        _vt = 30.0
                    if self._wait_for_extension_solve(page, timeout=_vt):
                        return True
                    self.log("[⚠️] Visual AI did not finish; falling back to Audio STT…")
                else:
                    if self._solve_recaptcha_audio(page, tries=5):
                        return True
                    self.log("[⚠️] Audio STT did not finish; falling back to Visual AI…")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[⚠️] {solver} solver error: {exc}")
        try:
            return not self._has_human_check(page)
        except Exception:
            return False

    def _meta_selfie_checkpoint(self, page, timeout=900):
        """Checkpoint flow with dashboard-ordered solvers (ordered).

        Overrides the engine version so the attempt order follows the
        dashboard captcha choice (chosen first, the other on fallback)
        instead of the engine's fixed audio-first sequence.

        The selfie upload is RETRIED until the checkpoint accepts the image
        (a single transient failure must not wedge the run — the old code
        uploaded once and then spun on a disabled Continue), and the generic
        file-input photo checkpoint is handled too (engine helpers).
        """
        end = time.time() + timeout
        uploaded = False
        accepted = False
        last_attempt = 0.0
        first_attempt_done = False

        def _cleared() -> bool:
            """True once the selfie prompt is gone — i.e. the checkpoint PASSED."""
            try:
                return not page.get_by_text("Upload a verification selfie",
                                            exact=False).first.is_visible()
            except Exception:
                return True

        while time.time() < end and self.w.is_running:
            try:
                if page.get_by_text("Upload a verification selfie",
                                    exact=False).first.is_visible():
                    # Attempt IMMEDIATELY the first time (no 5s throttle), then
                    # retry every 5s so a single transient miss can't wedge.
                    due = (not first_attempt_done) or (time.time() - last_attempt) > 5
                    if not uploaded and due:
                        last_attempt = time.time()
                        first_attempt_done = True
                        uploaded = bool(self._upload_selfie(page))
                    if uploaded:
                        self._try_click(page, "Continue", timeout=8000)
                        self._poll_checkpoint_settled(page, timeout=8)
                        # 'uploaded' only means a file was SENT. Confirm the
                        # checkpoint actually advanced before believing it —
                        # otherwise we drive an unverified account onward and
                        # Meta answers with the phone wall. Re-arm the latch so
                        # a genuine retry (re-upload) can still happen.
                        if _cleared():
                            accepted = True
                            # The prompt is gone, but the account may not be
                            # PROVISIONED yet — the IG join downstream is what
                            # suffers if we leave now. Wait for the real
                            # post-signup state (auth.meta.com/language +
                            # accountId); returns instantly if already there.
                            self._wait_meta_provisioned(page, timeout=45)
                        else:
                            uploaded = False
                        continue
                    else:
                        page.wait_for_timeout(1500)
                    continue
            except Exception:
                pass
            # NOTE: no break here — falling through is required so the generic
            # file-input photo checkpoint and the captcha branch still run.
            # 'accepted' is set by _cleared() inside the selfie branch above.
            # PC post-OTP photo checkpoint: generic file-input variant of the
            # selfie screen (no "Upload a verification selfie" text).
            try:
                if self._try_image_upload_if_present(page):
                    uploaded = True
                    self._try_click(page, "Continue", timeout=8000)
                    self._poll_checkpoint_settled(page, timeout=8)
                    continue
            except Exception:
                pass
            if self._has_human_check(page):
                solved = self._solve_captcha_ordered(page)
                if solved or not self._has_human_check(page):
                    self._try_click(page, "Continue", timeout=8000)
                    self._poll_checkpoint_settled(page, timeout=10)
                    continue
                self._poll_checkpoint_settled(page, timeout=5)
                continue
            break
        if accepted:
            self.log('<font color="#00FF00"><b>[VERIFIED] Verification selfie '
                     'accepted — checkpoint cleared.</b></font>')
        elif uploaded:
            self.log('<font color="#FFA500"><b>[⚠️] Selfie file was sent but the '
                     'checkpoint never cleared (Continue did not take) — treating '
                     'as NOT verified.</b></font>')
        else:
            self.log('[⚠️] Selfie checkpoint ended without a confirmed upload.')

    def _wait_meta_provisioned(self, page, timeout: int = 90) -> bool:
        """Poll until Meta has actually finished creating the account.

        Why this exists (2026-09-26): after the selfie checkpoint was accepted we
        clicked "Create account" and then slept a FIXED 4s before moving on to
        Instagram. Meta provisions the account (and settles the profile/IG
        linkage) asynchronously, so a 4s blind wait means the IG join routinely
        starts against a half-built account — the most plausible trigger for the
        intermittent "What's your mobile number?" wall (IGDeadEnd burns the
        whole account). This is invariant 19 applied to the one place that still
        had a blind sleep.

        GROUND TRUTH for the settled state (captured from the real post-signup
        page, do NOT guess this again): the account is created ON auth.meta.com
        and lands on **/language** — FRLXAuthSettingsController /
        FRLAuthSettingsRoot.react — carrying a real identity:

            "page_uri":"https://auth.meta.com/language"
            "accountId":"1271284112744162"  "accountName":"opossum_deer_4700"
            "isFetaAccount":true  "has_meta_ai_profile":true
            OCSession + OCSessionToken  (a live session, i.e. really signed in)

        NOTE the page never leaves auth.meta.com on this path, so a
        "did we reach facebook.com" test can NEVER pass here — it just burns the
        full timeout on every account. The URL is the cheap primary signal; the
        accountId is read once, only after the URL matches, purely to log proof.

        Returns True on a settled signal. On timeout it returns False and the
        caller continues anyway — an optimisation, never a new gate that can
        fail an account.
        """
        import re as _re
        import time as _t
        deadline = _t.time() + max(15, int(timeout or 90))
        while _t.time() < deadline:
            try:
                url = str(page.url or '')
                # Primary (cheap, decisive): the settings page on the auth host.
                if 'auth.meta.com' in url and '/language' in url:
                    try:
                        html = page.content() or ''
                    except Exception:
                        html = ''
                    m = _re.search(r'"accountId":"(\d+)"', html)
                    nm = _re.search(r'"accountName":"([^"]+)"', html)
                    if m:
                        self.log(f'[⏱️] Meta provisioned — accountId={m.group(1)}'
                                 + (f' name={nm.group(1)!r}' if nm else '')
                                 + ' (auth.meta.com/language, session live)')
                        return True
                    self.log('[⏱️] Meta provisioned — reached auth.meta.com/language '
                             '(no accountId in HTML yet).')
                    return True
                # Secondary: some builds do continue into the product surface.
                if 'facebook.com' in url and 'auth.meta.com' not in url:
                    self.log(f'[⏱️] Meta provisioned (left auth host): {url[:90]}')
                    return True
            except Exception:
                pass
            page.wait_for_timeout(700)
        self.log('[⏱️] Meta provision wait timed out — continuing anyway '
                 '(optimisation only, not a gate).')
        return False

    def _maybe_accept_meta_terms(self, page) -> bool:
        """Handle Meta's mid-flow dialogs ('Create account', 'Not now', 'I agree')."""
        try:
            # 1. "Finish creating your Meta account" -> "Create account" button
            btn = page.get_by_role("button", name="Create account").first
            if btn.is_visible():
                btn.click()
                self.log('<font color="#00FF00"><b>[✔] Meta: clicked "Create account".</b></font>')
                # Was a fixed 4s blind sleep — the account was then driven into
                # Instagram possibly before Meta finished provisioning it.
                self._wait_meta_provisioned(page)
                return True
        except Exception:
            pass

        try:
            # 2. "Save your login info?" -> "Not now"
            btn = page.get_by_role("button", name="Not now").first
            if btn.is_visible():
                btn.click()
                self.log('[✔] Meta: clicked "Not now".')
                page.wait_for_timeout(3000)
                return True
        except Exception:
            pass

        try:
            # 3. New signup consent page ('To sign up, read and agree to our terms' → 'I agree')
            if (page.get_by_text("read and agree to our terms", exact=False).count() > 0
                    or page.get_by_text("Key points you should know", exact=False).count() > 0):
                for nm in ("I agree", "Agree"):
                    try:
                        btn = page.get_by_role("button", name=nm).first
                        if btn.is_visible():
                            btn.click()
                            self.log('<font color="#00FF00"><b>[✔] Meta: accepted new '
                                     'terms ("I agree").</b></font>')
                            page.wait_for_timeout(4500)
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False
