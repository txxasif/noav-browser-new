from __future__ import annotations

import os
import re
import sys
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
    "can't process your request at the moment",
    "cannot process your request at the moment",
    "sending automated queries",
    "unusual traffic",
)


def _meta_ip_blocked(page_or_body, url: str = "") -> bool:
    """True for Meta's or Google's terminal 'automated queries' / 'try again later' refusal."""
    if hasattr(page_or_body, "frames"):
        page = page_or_body
        u = (getattr(page, "url", None) or "").lower()
        try:
            frames = [page] + list(page.frames)
        except Exception:
            frames = [page]
        seen = set()
        for f in frames:
            if id(f) in seen:
                continue
            seen.add(id(f))
            try:
                b = (f.evaluate("() => document.body ? document.body.innerText : ''") or "").lower()
            except Exception:
                continue
            if any(m in b for m in _META_IP_BLOCK_MARKERS):
                if ("confirm that you're human" in b or "checkpoint" in u or "try again later" in b or "queries" in b):
                    return True
        return False

    b = (page_or_body or "").lower()
    u = (url or "").lower()
    if not any(m in b for m in _META_IP_BLOCK_MARKERS):
        return False
    return ("confirm that you're human" in b
            or "checkpoint" in u
            or "try again later" in b)


class CaptchaMixin:
    def _has_human_check(self, page) -> bool:
        """True if the page is on an Instagram/Meta human checkpoint or challenge screen."""
        try:
            u = (page.url or "").lower()
            if "accounts/suspended" in u or "checkpoint" in u or "challenge" in u:
                return True
        except Exception:
            pass
        try:
            body = (page.inner_text("body") or "").lower()
            if any(m in body for m in (
                "confirm you're human",
                "confirm that you're human",
                "can't read this text",
                "hear this code",
                "upload a verification selfie",
                "enter the code from the image",
                "suspect automated",
            )):
                return True
        except Exception:
            pass
        return False

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
            if _meta_ip_blocked(p) or _meta_ip_blocked(cur_body, cur_url):
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

            # If on a checkpoint or attempt > 1 with no meta.ai success, check auth.meta.com
            if attempt > 1 or (not is_meta_ai_success and "checkpoints" not in cur_url and not has_checkpoint and "auth.meta.com" not in cur_url):
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

            # Stuck-checkpoint guard: auth.meta.com/checkpoint… that only ever
            # renders grey placeholder bars (skeleton) — no reCAPTCHA, no
            # Continue. Nothing to solve and nothing to click, so the 4 retries
            # just burn the whole 600s window. Wait ~12s for real controls; if
            # none appear, dead-end now (close + next account).
            if "checkpoint" in cur_url or "checkpoint" in cur_body or "checkpoints" in cur_url:
                _ready = False
                for _ in range(12):
                    try:
                        _n = p.evaluate("""() => {
                            const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
                            const btns = Array.from(document.querySelectorAll('button, div[role="button"]')).filter(vis);
                            const inps = Array.from(document.querySelectorAll('input')).filter(vis);
                            return btns.length + inps.length;
                        }""")
                    except Exception:
                        _n = 1
                    if _n:
                        _ready = True
                        break
                    p.wait_for_timeout(1000)
                if not _ready and self._has_human_check(p) is False and "confirm" not in cur_body:
                    self.log('[🛡️] Meta checkpoint is a stuck skeleton (no controls rendered in 12s) '
                             '— dead end; closing and moving to the next account.')
                    raise MetaCheckpointBlocked(
                        "Meta checkpoint rendered no controls (stuck loading skeleton) — "
                        "dead end, not a solvable captcha")

            if self._has_human_check(p) or "confirm" in cur_body or "checkpoints" in cur_url:
                self._try_click(p, "Continue", timeout=8000)
                self._poll_checkpoint_settled(p, timeout=8)
                # reCAPTCHA audio + selfie + Continue. The selfie result GATES:
                # an upload that never cleared must not ride on into Instagram
                # (Meta answers with the phone wall and burns the account).
                selfie_ok = self._meta_selfie_checkpoint(p, timeout=per)
                self._try_click(p, "Continue", timeout=8000)
                self._poll_checkpoint_settled(p, timeout=8)
                if selfie_ok is False and self.w.is_running:
                    raise RuntimeError(
                        "Meta selfie checkpoint never accepted the upload "
                        "(file sent, prompt never cleared) — NOT verified, "
                        "closing and moving to the next account instead of "
                        "driving an unverified account into Instagram")
                # Early exit: as soon as the human check is gone we are DONE.
                # The old code also required "checkpoints" to leave the URL, so
                # it ran attempts 2-4 (each re-entering the selfie checkpoint)
                # for ~23s AFTER the selfie had already been accepted.
                if not self._has_human_check(p):
                    self.log('<font color="#00FF00"><b>[✔] Meta human verification cleared.</b></font>')
                    self._maybe_accept_meta_terms(p)
                    self._wait_meta_provisioned(p, timeout=45)
                    return True
            if not self._has_human_check(p) and "checkpoints" not in (p.url or ""):
                self.log('<font color="#00FF00"><b>[✔] Meta human verification cleared.</b></font>')
                self._maybe_accept_meta_terms(p)
                self._wait_meta_provisioned(p, timeout=45)
                return True
            p.wait_for_timeout(3000)
        self.log('[⚠️] Meta human verification still pending.')
        return not self._has_human_check(p)

    def _recaptcha_anchor_checked(self, anchor):
        """Return True for both ARIA and Google checkbox state variants."""
        if anchor is None:
            return False
        try:
            cb = anchor.locator("#recaptcha-anchor").first
            if cb.count() == 0:
                return False
            try:
                aria = (cb.get_attribute("aria-checked") or "").strip().lower()
                if aria == "true":
                    return True
                if aria == "false":
                    return False
            except Exception:
                pass
            return bool(cb.evaluate("""el => {
                const aria = (el.getAttribute('aria-checked') || '').trim().toLowerCase();
                if (aria === 'true') return true;
                if (aria === 'false') return false;
                const root = el.closest('.recaptcha-checkbox') || el.parentElement || el;
                const cls = (root.className || '').toLowerCase();
                if (cls.includes('recaptcha-checkbox-unchecked') || cls.includes('rc-anchor-checkbox-noglow')) return false;
                if (cls.includes('recaptcha-checkbox-checked')) return true;
                const state = [cls, root.getAttribute('data-state') || '',
                               root.getAttribute('aria-label') || ''].join(' ').toLowerCase();
                if (state.includes('unchecked')) return false;
                return /(^|\\s|-)checked(\\s|$)/.test(state) || /(^|\\s|-)verified(\\s|$)/.test(state);
            }"""))
        except Exception:
            return False

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
                    try:
                        _vt = float(os.environ.get("INSTA_VISUAL_CAPTCHA_TIMEOUT", "20") or 20)
                    except Exception:
                        _vt = 20.0
                    self._in_extension_fallback = False
                    if self._wait_for_extension_solve(page, timeout=_vt):
                        return True
                    self.log("[⚠️] Visual AI did not finish; falling back to Audio STT…")
                else:
                    self._in_extension_fallback = (solver == "audio" and "extension" in self._captcha_order())
                    if self._solve_recaptcha_audio(page, tries=2):
                        return True
                    self.log("[⚠️] Audio STT did not finish.")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[⚠️] {solver} solver error: {exc}")
        # Also try image captcha if present
        try:
            if self._solve_image_captcha(page):
                return True
        except Exception as exc:
            self.log(f"[⚠️] Image captcha error in ordered solver: {exc}")
        return False

    def _solve_image_captcha(self, page, max_attempts: int = 3) -> bool:
        """OCR Instagram/Meta 'enter the code from the image' captcha with RapidOCR."""
        try:
            ocr_engine = self._ensure_ocr()
        except Exception as exc:
            self.log(f'[⚠️] OCR engine unavailable: {exc}')
            return False

        for attempt in range(max_attempts):
            best, best_area = None, 0
            try:
                for img in page.locator("img").all():
                    try:
                        box = img.bounding_box()
                        if box and box["width"] > 60 and box["height"] > 30:
                            area = box["width"] * box["height"]
                            if area > best_area:
                                best, best_area = img, area
                    except Exception:
                        pass
            except Exception:
                pass

            if best is None:
                try:
                    if not page.get_by_text("Enter the code from the image", exact=False).is_visible():
                        return True
                except Exception:
                    pass
                return False

            try:
                shot = best.screenshot()
            except Exception as exc:
                self.log(f'[⚠️] Could not capture captcha screenshot: {exc}')
                return False

            try:
                from engine.eng_mix_audio import _OCR_INFER_LOCK, HERE
                png = os.path.join(HERE, f"captcha_img_{attempt}.png")
                with open(png, "wb") as f:
                    f.write(shot)
                with _OCR_INFER_LOCK:
                    result, _ = ocr_engine(png)
            except Exception as exc:
                self.log(f'[⚠️] RapidOCR inference error: {exc}')
                return False

            # Direct recognizer with multi-padding bounding box crop
            # Instagram captchas are 6 characters with blank side margins and thin scratch lines
            candidates = []
            try:
                import cv2
                img_arr = cv2.imread(png)
                if img_arr is not None:
                    gray = cv2.cvtColor(img_arr, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
                    pts = cv2.findNonZero(thresh)
                    if pts is not None and hasattr(ocr_engine, "text_recognizer"):
                        x, y, w, h = cv2.boundingRect(pts)
                        for pad in (5, 2, 8, 0, 10):
                            x0 = max(0, x - pad)
                            y0 = max(0, y - pad)
                            w0 = min(img_arr.shape[1] - x0, w + 2 * pad)
                            h0 = min(img_arr.shape[0] - y0, h + 2 * pad)
                            crop = img_arr[y0:y0 + h0, x0:x0 + w0]
                            rec_res, _ = ocr_engine.text_recognizer(crop)
                            if rec_res and rec_res[0] and rec_res[0][0]:
                                cand = "".join(c for c in str(rec_res[0][0]) if c.isalnum())
                                conf = float(rec_res[0][1]) if len(rec_res[0]) > 1 else 0.5
                                candidates.append((len(cand) == 6, conf, cand))
            except Exception as ocr_crop_exc:
                self.log(f'[⚠️] OCR crop note: {ocr_crop_exc}')

            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
                best_cand = candidates[0]
                result = [[None, best_cand[2], best_cand[1]]]
            elif not result and hasattr(ocr_engine, "text_recognizer"):
                try:
                    rec_res, _ = ocr_engine.text_recognizer(img_arr)
                    if rec_res and rec_res[0] and rec_res[0][0]:
                        cand = "".join(c for c in str(rec_res[0][0]) if c.isalnum())
                        score = float(rec_res[0][1]) if len(rec_res[0]) > 1 else 0.5
                        result = [[None, cand, score]]
                except Exception:
                    pass

            code = "".join(t[1] for t in result).replace(" ", "").strip() if result else ""

            # Instagram captcha is 6 characters. If < 6 characters and we have attempts left,
            # refresh the image rather than submitting a guaranteed-rejected code!
            if (not code or len(code) < 6) and attempt < (max_attempts - 1):
                self.log(f'[⚠️] Decoded code "{code}" incomplete (<6 chars, attempt {attempt + 1}/{max_attempts}) — refreshing image…')
                for rel_sel in (
                    'a:has-text("can\'t read this text")',
                    'button:has-text("can\'t read this text")',
                    '[role="button"]:has-text("can\'t read this text")',
                    'button[aria-label*="new code" i]',
                    'button[aria-label*="reload" i]',
                    'a:has-text("Try another code")',
                    'button:has-text("Try another code")',
                ):
                    try:
                        r = page.locator(rel_sel).first
                        if r.count() > 0 and r.is_visible():
                            r.click()
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass
                continue

            if not code:
                self.log(f'[⚠️] RapidOCR detected no text in captcha (attempt {attempt + 1}/{max_attempts})')
                continue

            self.log(f'[🤖] RapidOCR decoded image captcha: "{code}" (attempt {attempt + 1}/{max_attempts})')

            input_box = None
            try:
                for inp in page.locator("input:visible").all():
                    try:
                        t = (inp.get_attribute("type") or "text").lower()
                        if t not in ("hidden", "submit", "button", "checkbox", "radio", "image", "file"):
                            input_box = inp
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            if input_box is None:
                try:
                    for tb in page.get_by_role("textbox").all():
                        if tb.is_visible():
                            input_box = tb
                            break
                except Exception:
                    pass

            if input_box is None:
                for sel in (
                    'input:not([type="hidden"])',
                    'input[type="text"]',
                    'input',
                    'textarea',
                    '[contenteditable="true"]',
                ):
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            input_box = el
                            break
                    except Exception:
                        continue

            if input_box is None:
                self.log('[⚠️] Image captcha input element not found')
                return False

            try:
                input_box.click(timeout=3000)
            except Exception:
                pass
            try:
                input_box.fill(code, timeout=3000)
            except Exception:
                pass
            try:
                if hasattr(self, "_human_type"):
                    self._human_type(input_box, code)
            except Exception:
                pass
            try:
                input_box.evaluate(
                    "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
                    code,
                )
            except Exception:
                pass
            try:
                input_box.press("Enter", timeout=3000)
            except Exception as fill_exc:
                self.log(f'[⚠️] Note on typing captcha code: {fill_exc}')

            # Tap submission buttons (Next, Continue, Submit, Confirm)
            tapped = False
            for btn_name in ("Next", "Continue", "Submit", "Confirm"):
                for btn_sel in (
                    f'button:has-text("{btn_name}")',
                    f'[role="button"]:has-text("{btn_name}")',
                    f'input[type="submit"][value*="{btn_name}" i]',
                    'button[type="submit"]',
                ):
                    try:
                        b = page.locator(btn_sel).first
                        if b.count() > 0 and b.is_visible():
                            b.click(timeout=3000)
                            tapped = True
                            break
                    except Exception:
                        pass
                if tapped:
                    break

            for _wait in range(8):
                page.wait_for_timeout(1000)
                try:
                    body_now = (page.inner_text("body") or "").lower()
                except Exception:
                    body_now = ""
                # Screen has transitioned if none of the captcha prompts remain
                captcha_active = any(k in body_now for k in (
                    "can't read this text",
                    "hear this code",
                    "enter the code from the image",
                    "enter the code",
                ))
                if not captcha_active:
                    self.log(f'[✔] Image captcha submitted and screen transitioned! URL: {page.url}')
                    return True
                if any(err in body_now for err in ("incorrect code", "try again", "wrong code", "invalid code")):
                    self.log(f'[⚠️] Captcha code "{code}" was rejected; retrying with refreshed image…')
                    break

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

        Returns True when no selfie was required or the upload was ACCEPTED
        (prompt gone). Returns False when a selfie upload was attempted but
        the checkpoint never cleared — the caller must NOT drive the account
        onward (Meta answers with the phone wall). Never raises for Stop:
        when the worker is stopping the result is untrusted, so True.
        """
        end = time.time() + timeout
        uploaded = False
        accepted = False
        saw_selfie = False
        uploaded_ever = False
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
                    saw_selfie = True
                    # Attempt IMMEDIATELY the first time (no 5s throttle), then
                    # retry every 5s so a single transient miss can't wedge.
                    due = (not first_attempt_done) or (time.time() - last_attempt) > 5
                    if not uploaded and due:
                        last_attempt = time.time()
                        first_attempt_done = True
                        uploaded = bool(self._upload_selfie(page))
                        uploaded_ever = uploaded_ever or uploaded
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
                    saw_selfie = True
                    uploaded = True
                    uploaded_ever = True
                    self._try_click(page, "Continue", timeout=8000)
                    self._poll_checkpoint_settled(page, timeout=8)
                    continue
            except Exception:
                pass
            if self._has_human_check(page):
                if _meta_ip_blocked(page):
                    raise MetaCheckpointBlocked(
                        'Meta human-verification checkpoint refused the request '
                        '("Try again later" / "sending automated queries") — an '
                        'IP/network block, not a solvable captcha. Closing the '
                        'browser and moving to the next account.')
                solved = self._solve_captcha_ordered(page)
                if solved or not self._has_human_check(page):
                    clicked = False
                    if hasattr(self, "_click_checkpoint_action"):
                        clicked = self._click_checkpoint_action(page, "Continue", timeout=3000)
                    if not clicked:
                        self._try_click(page, "Continue", timeout=4000)
                    self._poll_checkpoint_settled(page, timeout=10)
                    continue
                if _meta_ip_blocked(page):
                    raise MetaCheckpointBlocked(
                        'Meta human-verification checkpoint refused the request '
                        '("Try again later" / "sending automated queries") — an '
                        'IP/network block, not a solvable captcha. Closing the '
                        'browser and moving to the next account.')
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
        if not self.w.is_running:
            return True
        if not saw_selfie:
            # No selfie UI ever appeared — nothing to gate on.
            return True
        if not accepted and uploaded_ever:
            # The clear may have landed via a later Continue (captcha leg)
            # after the last _cleared() check — re-evaluate once now.
            try:
                accepted = _cleared()
            except Exception:
                accepted = False
        return accepted

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
        lang_first_seen = None
        while _t.time() < deadline:
            try:
                url = str(page.url or '')
                # Primary (cheap, decisive): the settings page on the auth host.
                if 'auth.meta.com' in url and ('/language' in url or '/settings' in url):
                    if lang_first_seen is None:
                        lang_first_seen = _t.time()
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
                    # Give React up to 5s to populate accountId before accepting bare page
                    if (_t.time() - lang_first_seen) > 5:
                        self.log('[⏱️] Meta provisioned — reached auth.meta.com/language '
                                 '(no accountId in HTML yet, session settled).')
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
