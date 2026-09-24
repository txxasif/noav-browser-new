"""engine.eng_mix_captcha — human-check polls, selfie upload & checkpoint flow.

Verbatim slice from ``engine/run.py`` ``_MetaInstagramRunner`` (no logic change).
Mixed into :class:`engine._MetaInstagramRunner`; ``self`` provides the other
engine helpers (same browser session invariant unchanged). Zero local-repo
dependencies (``store`` only via function-local lazy import).
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import _HUMAN_TEXTS  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import _HUMAN_TEXTS  # noqa: E402

class EngineCaptchaMixin:
    def _has_human_check(self, page):
        for t in _HUMAN_TEXTS:
            try:
                if page.get_by_text(t, exact=False).first.is_visible():
                    return True
            except Exception:
                pass
        return False

    def _handle_human(self, page, timeout=600):
        if not self._has_human_check(page):
            return
        # Free offline solvers first.
        if self._solve_recaptcha_audio(page):
            page.wait_for_timeout(3000)
            if not self._has_human_check(page):
                return
        if self._solve_image_captcha(page):
            page.wait_for_timeout(3000)
            if not self._has_human_check(page):
                return
        self.log('<font color="#FFD700"><b>[✋] Human verification still needed — '
                 'solve it in the browser window. Waiting…</b></font>')
        end = time.time() + timeout
        while time.time() < end and self.w.is_running:
            page.wait_for_timeout(3000)
            if not self._has_human_check(page):
                self.log('<font color="#00FF00"><b>[✔] Human verification passed.</b></font>')
                return
        self.log('[⚠️] Timed out waiting for human verification.')

    def _selfie_preview_settled(self, page, timeout=8):
        """True once the checkpoint accepted the image (blob/data preview or an
        enabled Continue). Polls instead of a blind sleep."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                ok = page.evaluate("""() => {
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const blobImg = imgs.some(i => {
                        const s = i.currentSrc || i.src || '';
                        return s.startsWith('blob:') || s.startsWith('data:image');
                    });
                    if (blobImg) return true;
                    // Meta sometimes renders the preview as a CSS background-image
                    // (not an <img>) — the old check missed it and re-uploaded forever.
                    const bg = Array.from(document.querySelectorAll('div,span,section'))
                        .some(el => {
                            try {
                                const b = getComputedStyle(el).backgroundImage || '';
                                return b.includes('blob:') || b.includes('data:image');
                            } catch (e) { return false; }
                        });
                    if (bg) return true;
                    const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
                    const cont = btns.find(b => /continue/i.test(b.textContent || ''));
                    if (cont && !cont.disabled && cont.getAttribute('aria-disabled') !== 'true') return true;
                    return false;
                }""")
                if ok:
                    return True
            except Exception:
                pass
            try:
                page.wait_for_timeout(500)
            except Exception:
                return False
        return False

    def _upload_selfie(self, page):
        """Upload the selfie to the Meta verification checkpoint (robust).

        Tries, in order:
          1. the underlying ``input[type="file"]`` directly (works even when the
             input is hidden — the common React dropzone; Meta's redesigned
             checkpoint only opens the picker this way);
          2. click-to-file-chooser across several button/label/dropzone selectors.
        Verifies a preview / enabled Continue before declaring success, and logs
        exactly what happened so a future UI change is obvious.
        """
        path = getattr(self, "selfie_path", None)
        if not path or not os.path.exists(path):
            try:
                from ai_config import get_random_selfie
                path = get_random_selfie()
                self.selfie_path = path
            except Exception:
                pass
        if not path or not os.path.exists(path):
            self.log('[⚠️] No selfie image found — put "selfie.png" next to run.py '
                     'or images in selfies/.')
            return False
        name = os.path.basename(path)

        # Wait briefly for the React dropzone to hydrate (ANY frame) so we hit the
        # INSTANT hidden-input path instead of the slow chooser fallback
        # (observed 2026-09-21: the checkpoint is an SPA — the input appears a
        # beat after the heading, and racing it forced the 12s chooser path).
        try:
            for _ in range(8):  # up to ~4s
                if self._file_inputs(page):
                    break
                page.wait_for_timeout(500)
        except Exception:
            pass

        # 1) Direct file input across EVERY frame (the checkpoint can render the
        # dropzone in a child frame; hidden inputs are fine for Playwright).
        for inp in self._file_inputs(page):
            try:
                try:
                    inp.set_input_files(path, timeout=20000)
                except Exception:
                    # Some builds need the input made visible first.
                    inp.evaluate("el => { el.style.display='block'; el.style.visibility='visible'; el.style.opacity=1; }")
                    inp.set_input_files(path, timeout=20000)
                if self._selfie_preview_settled(page, timeout=12):
                    self.log(f'<font color="#00FF00"><b>[🖼️] Selfie uploaded: {name}</b></font>')
                    return True
                self.log('[i] file input set but no preview yet — trying next path…')
            except Exception as exc:
                self.log(f'[i] direct file-input upload failed ({exc}); trying next path…')

        # 2) Click-to-file-chooser across likely controls (the label text is often
        # split across child spans, so match the container too), then a real
        # coordinate click on the dropzone as a fallback.
        for sel in (
            'button:has-text("Upload Image")',
            '[role="button"]:has-text("Upload Image")',
            'label:has-text("Upload Image")',
            'div:has-text("Upload Image")',
            'span:has-text("Upload Image")',
            'text=Upload Image',
            'button:has-text("Upload")',
        ):
            try:
                loc = page.locator(sel).last
                if loc.count() == 0 or not loc.is_visible():
                    continue
                try:
                    with page.expect_file_chooser(timeout=8000) as fc:
                        try:
                            loc.click(timeout=6000)
                        except Exception:
                            loc.evaluate("el => el.click()")
                    fc.value.set_files(path)
                except Exception:
                    box = loc.bounding_box()
                    if not box:
                        continue
                    with page.expect_file_chooser(timeout=8000) as fc:
                        page.mouse.click(box["x"] + box["width"] / 2,
                                         box["y"] + box["height"] / 2)
                    fc.value.set_files(path)
                if self._selfie_preview_settled(page, timeout=12):
                    self.log(f'<font color="#00FF00"><b>[🖼️] Selfie uploaded: {name}</b></font>')
                    return True
            except Exception:
                continue

        # 3) CDP last resort: find the file input PIERCING shadow DOM and set the
        # file directly — covers inputs the locator API cannot reach (a common
        # reason a slot stalls on this screen forever).
        try:
            if self._cdp_set_file_input(page, path) and self._selfie_preview_settled(page, timeout=12):
                self.log(f'<font color="#00FF00"><b>[🖼️] Selfie uploaded (CDP): {name}</b></font>')
                return True
        except Exception:
            pass

        self.log('[⚠️] Selfie upload failed — no file input accepted the image. '
                 'Meta may have changed the checkpoint UI; upload manually in the window.')
        return False

    def _file_inputs(self, page):
        """All ``input[type=file]`` locators across every frame (first per frame)."""
        out = []
        try:
            frames = list(page.frames)
        except Exception:
            frames = [page]
        for fr in frames:
            try:
                loc = fr.locator('input[type="file"]')
                if loc.count() > 0:
                    out.append(loc.first)
            except Exception:
                continue
        return out

    def _cdp_set_file_input(self, page, path) -> bool:
        """Last resort: set the file on a file input found via CDP (pierces
        shadow DOM), which the locator API cannot always reach."""
        try:
            cdp = page.context.new_cdp_session(page)
            doc = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
            root = (doc.get("root") or {}).get("nodeId")
            if not root:
                return False
            res = cdp.send("DOM.querySelectorAll",
                           {"nodeId": root, "selector": 'input[type="file"]', "pierce": True})
            for nid in (res.get("nodeIds") or []):
                try:
                    cdp.send("DOM.setFileInputFiles", {"files": [path], "nodeId": nid})
                    return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    def _try_image_upload_if_present(self, page):
        """Generic photo checkpoint (PC parity): a bare ``input[type="file"]``
        with no "Upload a verification selfie" heading. Never raises."""
        try:
            inp = page.locator('input[type="file"]').first
            if inp.count() == 0:
                return False
            # Only treat it as a checkpoint when the page hints at it, so a
            # random file input elsewhere never triggers a stray upload.
            try:
                body = (page.evaluate("() => (document.body && document.body.innerText) || ''") or "").lower()
                url = (page.url or "").lower()
            except Exception:
                body, url = "", ""
            if not ("selfie" in body or "photo" in body or "verification" in body
                    or "upload" in body or "checkpoint" in url):
                return False
            if not getattr(self, "selfie_path", None) or not os.path.exists(self.selfie_path):
                try:
                    from ai_config import get_random_selfie
                    self.selfie_path = get_random_selfie()
                except Exception:
                    pass
            if not getattr(self, "selfie_path", None) or not os.path.exists(self.selfie_path):
                self.log('[⚠️] Photo checkpoint present but no selfie image found.')
                return False
            self.log('[🖼️] Photo checkpoint detected — uploading selfie…')
            return bool(self._upload_selfie(page))
        except Exception:
            return False

    def _poll_checkpoint_settled(self, page, timeout=10):
        """Wait until the checkpoint page visibly advances (URL/body change
        or human-check gone), polling every 500ms (Nova-parity)."""
        try:
            start_url = page.url or ""
            start_tail = self._page_tail(page, 120)
        except Exception:
            page.wait_for_timeout(1000)
            return
        end = time.time() + timeout
        while time.time() < end and self.w.is_running:
            page.wait_for_timeout(500)
            try:
                if (page.url or "") != start_url:
                    return
                if self._page_tail(page, 120) != start_tail:
                    return
                if not self._has_human_check(page):
                    return
            except Exception:
                return

    def _wait_for_extension_solve(self, page, timeout=90):
        """Wait for in-browser JA Captcha extension to solve visual / Turnstile challenge (Nova-parity).

        Measured 2026-09-23: the extension solved 0/229 real challenges — only
        the fast anchor auto-verify and the selfie checkpoint cleared checks, so
        the old 45s mid-bail / 90s cap were mostly dead time. Both are now
        env-tunable and default lower:
        INSTA_VISUAL_CAPTCHA_TIMEOUT (cap) / INSTA_VISUAL_CAPTCHA_BAIL (hand-off).
        """
        try:
            timeout = float(os.environ.get("INSTA_VISUAL_CAPTCHA_TIMEOUT", "30") or 30)
        except Exception:
            timeout = 30.0
        try:
            bail = float(os.environ.get("INSTA_VISUAL_CAPTCHA_BAIL", "15") or 15)
        except Exception:
            bail = 15.0
        self.log(f'[🧩] Visual AI Extension: monitoring DOM for in-browser solve (up to {int(timeout)}s)…')
        start = time.time()
        initial_url = page.url or ""

        # Ensure reCAPTCHA checkbox is clicked so challenge / extension activates
        anchor, bframe = self._recaptcha_frames(page)
        if anchor is not None:
            try:
                cb = anchor.locator("#recaptcha-anchor")
                if cb.count() > 0 and cb.get_attribute("aria-checked") != "true":
                    self.log('[🧩] Clicking reCAPTCHA "I\'m not a robot" checkbox…')
                    self._human_click_recaptcha(page, cb, timeout=6000)
                    page.wait_for_timeout(2000)
            except Exception:
                pass

        while time.time() - start < timeout and self.w.is_running:
            page.wait_for_timeout(1000)
            cur_url = page.url or ""

            # Check if reCAPTCHA anchor was verified (green checkmark)
            anchor, bframe = self._recaptcha_frames(page)
            if anchor is not None:
                try:
                    if anchor.locator("#recaptcha-anchor").get_attribute("aria-checked") == "true":
                        self.log(f'<font color="#00FF00"><b>[✅] reCAPTCHA verified in {int(time.time() - start)}s!</b></font>')
                        return True
                except Exception:
                    pass

            # If URL moved beyond checkpoint
            if "checkpoints" not in cur_url and cur_url != initial_url:
                self.log(f'[✅] Challenge cleared (URL changed in {int(time.time() - start)}s)!')
                return True

            # If human check is no longer present
            if not self._has_human_check(page):
                self.log(f'[✅] Visual AI Extension solved challenge in {int(time.time() - start)}s!')
                return True

            # Attempt to click Continue if active
            for btn_txt in ("Continue", "Next", "Confirm"):
                if self._try_click(page, btn_txt, timeout=1200):
                    self.log(f'[+] Clicked {btn_txt} during visual solve…')
                    self._poll_checkpoint_settled(page, timeout=4)
                    if not self._has_human_check(page):
                        return True

            # If extension has not solved after the bail window and a challenge
            # iframe remains open, hand off to Audio STT instead of waiting the cap.
            if (time.time() - start) >= bail and bframe is not None:
                self.log(f'[⚠️] Visual AI did not finish in {int(bail)}s; falling back to Audio STT…')
                return False

        self.log(f'[⚠️] Visual AI extension did not finish in {timeout}s; falling back to Audio STT…')
        return False

    def _meta_selfie_checkpoint(self, page, timeout=900):
        """Engine checkpoint flow, polling waits instead of blind sleeps (Nova-parity).

        Supports dual-mode captcha solving: Visual AI Extension with automatic Audio STT fallback.
        The selfie upload is retried every few seconds until the checkpoint
        accepts the image, so a single transient failure can never wedge the run.
        """
        end = time.time() + timeout
        uploaded = False
        last_attempt = 0.0
        first_attempt_done = False
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
                    else:
                        page.wait_for_timeout(1500)
                    continue
            except Exception:
                pass
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
                solved = False
                if getattr(self, "captcha_mode", "extension") == "extension":
                    solved = self._wait_for_extension_solve(page, timeout=90)
                if not solved and self._has_human_check(page):
                    solved = self._solve_recaptcha_audio(page, tries=5)
                if solved or not self._has_human_check(page):
                    self._try_click(page, "Continue", timeout=8000)
                    self._poll_checkpoint_settled(page, timeout=10)
                    continue
                self._poll_checkpoint_settled(page, timeout=5)
                continue
            break
        if uploaded:
            self.log('<font color="#00FF00"><b>[VERIFIED] Verification selfie submitted.</b></font>')
        else:
            self.log('[⚠️] Selfie checkpoint ended without a confirmed upload.')

    # -- free captcha solving (offline) ------------------------------------
