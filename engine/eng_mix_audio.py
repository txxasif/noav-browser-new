"""engine.eng_mix_audio — offline reCAPTCHA audio STT (Whisper->Vosk) + image fallback.

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
import threading
import time

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
try:
    from .eng_constants import HERE  # package import
except ImportError:  # top-level `import run` (ENGINE_DIR on sys.path)
    from eng_constants import HERE  # noqa: E402
try:
    from .eng_antidetect import _get_shared_whisper_model  # noqa: E402
except ImportError:
    from eng_antidetect import _get_shared_whisper_model  # noqa: E402

_SHARED_VOSK_MODEL = None
_VOSK_MODEL_LOCK = threading.Lock()
_VOSK_INFER_LOCK = threading.Lock()
_SHARED_OCR_ENGINE = None
_OCR_MODEL_LOCK = threading.Lock()
_OCR_INFER_LOCK = threading.Lock()


class EngineAudioMixin:
    def _run(self, cmd, timeout=60):
        import subprocess
        return subprocess.run(cmd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=timeout)

    def _ensure_vosk(self):
        global _SHARED_VOSK_MODEL
        if self._vosk_model is not None:
            return self._vosk_model
        with _VOSK_MODEL_LOCK:
            if _SHARED_VOSK_MODEL is not None:
                self._vosk_model = _SHARED_VOSK_MODEL
                return self._vosk_model
            try:
                import vosk
            except Exception:
                return None
            model_dir = os.path.join(HERE, "models", "vosk-model-small-en-us-0.15")
            if not os.path.isdir(model_dir):
                try:
                    import urllib.request
                    import zipfile
                    os.makedirs(os.path.join(HERE, "models"), exist_ok=True)
                    zp = os.path.join(HERE, "models", "vosk.zip")
                    self.log('[🌐] Downloading Vosk speech model (first time, ~40 MB)…')
                    urllib.request.urlretrieve(
                        "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
                        zp)
                    with zipfile.ZipFile(zp) as z:
                        z.extractall(os.path.join(HERE, "models"))
                    os.remove(zp)
                except Exception as exc:
                    self.log(f'[⚠️] Vosk model download failed: {exc}')
                    return None
            try:
                vosk.SetLogLevel(-1)
                _SHARED_VOSK_MODEL = vosk.Model(model_dir)
                self._vosk_model = _SHARED_VOSK_MODEL
                return self._vosk_model
            except Exception as exc:
                self.log(f'[⚠️] Vosk load failed: {exc}')
                return None
    def _ensure_whisper(self):
        return _get_shared_whisper_model(self.log)

    def _transcribe(self, wav_path):
        # Whisper first (handles phrases, not just digits), Vosk as fallback.
        wm = self._ensure_whisper()
        if wm is not None:
            try:
                with _WHISPER_LOCK:
                    segs, _ = wm.transcribe(wav_path, language="en", beam_size=5)
                    return " ".join(s.text for s in segs).strip()
            except Exception:
                pass
        import json as _json
        import wave
        import vosk
        model = self._ensure_vosk()
        if model is None:
            return ""
        with _VOSK_INFER_LOCK:
            wf = wave.open(wav_path, "rb")
            try:
                rec = vosk.KaldiRecognizer(model, wf.getframerate())
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)
                return _json.loads(rec.FinalResult()).get("text", "")
            finally:
                wf.close()

    def _normalize_captcha(self, text):
        """reCAPTCHA audio is a spoken *phrase* now — submit the whole thing with homophone mapping."""
        t = (text or "").lower()
        w2n = {
            "zero": "0", "one": "1", "won": "1",
            "two": "2", "to": "2", "too": "2",
            "three": "3", "tree": "3",
            "four": "4", "for": "4", "fore": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8", "ate": "8",
            "nine": "9",
        }
        toks = [w2n.get(tok, tok) for tok in re.findall(r"[a-z0-9]+", t)]
        return " ".join(toks).strip()

    def _recaptcha_frames(self, page):
        anchor = bframe = None
        for f in page.frames:
            u = (f.url or "").lower()
            if "recaptcha" not in u:
                continue
            if "anchor" in u:
                anchor = f
            if "bframe" in u:
                bframe = f
        return anchor, bframe

    def _recaptcha_present(self, page):
        return any("recaptcha" in (f.url or "").lower() for f in page.frames)

    def _google_blocked(self, page):
        """True when Google is refusing reCAPTCHA ('automated queries' wall)."""
        for f in page.frames:
            try:
                t = (f.evaluate("() => document.body ? document.body.innerText : ''") or "")
            except Exception:
                continue
            low = t.lower()
            if ("automated queries" in low
                    or "can't process your request" in low
                    or "cannot process your request" in low
                    or "unusual traffic" in low):
                return True
        return False

    def _human_click_recaptcha(self, page, locator, timeout=8000):
        """Click recaptcha element with smooth human mouse movement and natural hover pause, with force click fallback."""
        try:
            box = locator.bounding_box(timeout=timeout)
            if box and box.get("width", 0) > 0 and box.get("height", 0) > 0:
                tx = box["x"] + box["width"] * random.uniform(0.35, 0.65)
                ty = box["y"] + box["height"] * random.uniform(0.35, 0.65)
                page.mouse.move(tx, ty, steps=random.randint(14, 26))
                page.wait_for_timeout(random.randint(150, 320))
                page.mouse.down()
                page.wait_for_timeout(random.randint(60, 130))
                page.mouse.up()
        except Exception:
            pass
        try:
            locator.click(force=True, timeout=timeout)
            return True
        except Exception:
            return False

    def _solve_recaptcha_audio(self, page, tries=5):
        """Click the reCAPTCHA checkbox (it is nested inside a fbsbx iframe),
        and if an image challenge appears switch to the audio challenge and
        transcribe it locally with Whisper / Vosk."""
        anchor = None
        for _ in range(5):
            anchor, bframe = self._recaptcha_frames(page)
            if anchor is not None:
                try:
                    cb = anchor.locator("#recaptcha-anchor")
                    if cb.count() > 0:
                        self._human_click_recaptcha(page, cb, timeout=6000)
                        page.wait_for_timeout(2000)
                        if anchor.locator("#recaptcha-anchor").get_attribute("aria-checked") == "true":
                            self.log('<font color="#00FF00"><b>[✔] reCAPTCHA passed (no image challenge).</b></font>')
                            return True
                        break
                except Exception:
                    pass
            page.wait_for_timeout(1500)
        page.wait_for_timeout(2000)

        # No challenge? The checkbox may have auto-passed.
        anchor, bframe = self._recaptcha_frames(page)
        if anchor is not None:
            try:
                if anchor.locator("#recaptcha-anchor").get_attribute("aria-checked") == "true":
                    self.log('<font color="#00FF00"><b>[✔] reCAPTCHA passed (no image challenge).</b></font>')
                    return True
            except Exception:
                pass

        if bframe is None:
            # Re-try direct click on anchor if challenge popup hasn't opened yet
            if anchor is not None:
                try:
                    cb = anchor.locator("#recaptcha-anchor")
                    if cb.count() > 0 and cb.get_attribute("aria-checked") != "true":
                        cb.click(force=True, timeout=4000)
                        page.wait_for_timeout(2500)
                        anchor, bframe = self._recaptcha_frames(page)
                except Exception:
                    pass

        if bframe is None:
            if anchor is not None and anchor.locator("#recaptcha-anchor").get_attribute("aria-checked") == "true":
                return True
            self.log('[⚠️] reCAPTCHA challenge popup did not appear.')
            return False

        for i in range(tries):
            if self._google_blocked(page):
                self.log('[⚠️] Google rate-limited audio ("automated queries"). Attempting reload…')
                _a, bframe = self._recaptcha_frames(page)
                if bframe is not None:
                    self._reload_audio(page, bframe)
                    page.wait_for_timeout(2500)
                if self._google_blocked(page):
                    if getattr(self, "captcha_mode", "audio") == "extension" and hasattr(self, "_wait_for_extension_solve"):
                        self.log('[🧩] Audio blocked by Google; auto-falling back to Visual AI solver…')
                        return self._wait_for_extension_solve(page, timeout=180)
                    self.log('<font color="#FFD700"><b>[⚠️] Google rate-limited this IP ("automated queries") — stopping auto-solve.</b></font>')
                    return False

            _a, bframe = self._recaptcha_frames(page)
            if bframe is None:
                if anchor is not None and anchor.locator("#recaptcha-anchor").get_attribute("aria-checked") == "true":
                    self.log('<font color="#00FF00"><b>[✔] reCAPTCHA solved!</b></font>')
                    return True
                return False

            try:
                # Realistic human delay before deciding to click audio button (1.4 - 2.4s)
                page.wait_for_timeout(int(random.uniform(1.4, 2.4) * 1000))
                audio_btn = bframe.locator("#recaptcha-audio-button")
                if audio_btn.is_visible(timeout=3000):
                    self._human_click_recaptcha(page, audio_btn, timeout=6000)
                page.wait_for_timeout(1800)

                if self._google_blocked(page):
                    self.log('[⚠️] Google blocked audio ("automated queries"). Attempting challenge reload…')
                    self._reload_audio(page, bframe)
                    page.wait_for_timeout(2500)
                    if self._google_blocked(page):
                        if getattr(self, "captcha_mode", "audio") == "extension" and hasattr(self, "_wait_for_extension_solve"):
                            self.log('[🧩] Audio blocked by Google; auto-falling back to Visual AI solver…')
                            return self._wait_for_extension_solve(page, timeout=180)
                        continue

                # Ensure the clip is actually loaded (the play control).
                try:
                    bframe.locator(".rc-audiochallenge-play-button").first.click(timeout=2500)
                except Exception:
                    pass
                page.wait_for_timeout(800)

                src = None
                for sel, attr in (
                    ("#audio-source", "src"),
                    (".rc-audiochallenge-tdownload-link", "href"),
                    ("a[href*='audio']", "href"),
                    ("a[href*='payload']", "href"),
                    ("audio", "src"),
                    ("audio source", "src"),
                ):
                    try:
                        el = bframe.locator(sel).first
                        if el.count() > 0:
                            val = el.get_attribute(attr, timeout=2000)
                            if val:
                                src = val
                                break
                    except Exception:
                        pass
                if not src:
                    self.log(f'[⚠️] audio clip not ready (attempt {i + 1}) — reloading…')
                    self._reload_audio(page, bframe)
                    continue
                body = page.context.request.get(src).body()
                self.log(f'[🤖] audio clip: {len(body)} bytes')
                if len(body) < 1200:
                    self.log(f'[⚠️] audio clip too small (attempt {i + 1}) — reloading…')
                    self._reload_audio(page, bframe)
                    continue

                slot_suffix = f"_{getattr(self.w, 'slot_id', 0)}_{int(time.time() * 1000)}"
                mp3 = os.path.join(HERE, f"captcha{slot_suffix}.mp3")
                wav = os.path.join(HERE, f"captcha{slot_suffix}.wav")
                text = ""
                try:
                    with open(mp3, "wb") as f:
                        f.write(body)
                    self._run(["ffmpeg", "-y", "-i", mp3, "-ar", "16000", "-ac", "1",
                               "-f", "wav", wav])
                    text = self._normalize_captcha(self._transcribe(wav))
                    self.log(f'[🤖] reCAPTCHA audio heard: "{text}"')
                finally:
                    for temp_f in (mp3, wav):
                        if os.path.exists(temp_f):
                            try:
                                os.remove(temp_f)
                            except Exception:
                                pass

                if not text:
                    self.log(f'[⚠️] transcription empty (attempt {i + 1}) — reloading…')
                    self._reload_audio(page, bframe)
                    continue
                try:
                    bframe.evaluate("""(val) => {
                        const inp = document.getElementById('audio-response');
                        if (inp) {
                            inp.removeAttribute('disabled');
                            inp.disabled = false;
                            inp.focus();
                            inp.value = val;
                            ['focus', 'keydown', 'keypress', 'input', 'keyup', 'change'].forEach(ev => inp.dispatchEvent(new Event(ev, {bubbles: true})));
                        }
                        const btn = document.getElementById('recaptcha-verify-button');
                        if (btn) {
                            btn.removeAttribute('disabled');
                            btn.disabled = false;
                            btn.click();
                        }
                    }""", text)
                except Exception:
                    try:
                        bframe.locator("#audio-response").fill(text, timeout=3000)
                    except Exception:
                        pass
                page.wait_for_timeout(500)
                try:
                    bframe.locator("#recaptcha-verify-button").click(force=True, timeout=4000)
                except Exception:
                    pass
                page.wait_for_timeout(3000)
                _a, bframe = self._recaptcha_frames(page)
                if bframe is None or (anchor is not None and anchor.locator("#recaptcha-anchor").get_attribute("aria-checked") == "true"):
                    self.log('<font color="#00FF00"><b>[✔] reCAPTCHA solved (audio).</b></font>')
                    return True
            except Exception as exc:
                self.log(f'[⚠️] reCAPTCHA audio attempt {i + 1}: {exc}')
            page.wait_for_timeout(1500)
        return False

    def _reload_audio(self, page, bframe):
        for sel in ("#recaptcha-reload-button", ".rc-button.reload",
                    "button[title='Get a new challenge']"):
            try:
                bframe.locator(sel).first.click(timeout=2500)
                page.wait_for_timeout(1800)
                return True
            except Exception:
                continue
        return False

    def _ensure_ocr(self):
        """Load one shared OCR model instead of one ONNX session per slot."""
        global _SHARED_OCR_ENGINE
        if self._ocr_engine is not None:
            return self._ocr_engine
        with _OCR_MODEL_LOCK:
            if _SHARED_OCR_ENGINE is None:
                from rapidocr_onnxruntime import RapidOCR
                _SHARED_OCR_ENGINE = RapidOCR()
            self._ocr_engine = _SHARED_OCR_ENGINE
        return self._ocr_engine

    def _solve_image_captcha(self, page):
        """OCR Meta's 'enter the code from the image' captcha with RapidOCR."""
        try:
            ocr_engine = self._ensure_ocr()
        except Exception:
            return False
        try:
            # pick the largest visible <img> (the captcha image)
            best, best_area = None, 0
            for img in page.locator("img").all():
                try:
                    box = img.bounding_box()
                    if box and box["width"] > 60 and box["height"] > 30:
                        area = box["width"] * box["height"]
                        if area > best_area:
                            best, best_area = img, area
                except Exception:
                    pass
            if best is None:
                return False
            shot = best.screenshot()
            png = os.path.join(HERE, "captcha_img.png")
            with open(png, "wb") as f:
                f.write(shot)
            with _OCR_INFER_LOCK:
                result, _ = ocr_engine(png)
            if not result:
                return False
            code = "".join(t[1] for t in result).replace(" ", "")
            self.log(f'[🤖] Image captcha OCR: "{code}"')
            box = page.get_by_role("textbox", name="Enter the code from the image").first
            box.fill(code)
            self._try_click(page, "Next", timeout=8000)
            page.wait_for_timeout(5000)
            return True
        except Exception as exc:
            self.log(f'[⚠️] Image captcha OCR failed: {exc}')
            return False

    # -- mail.td inbox ------------------------------------------------------
