"""DOM-driven page state for the Meta/Instagram signup flow.

``classify(page)`` reads the live page (URL host/path, visible text, visible inputs)
and returns one state name, so the flow decides what to do from what is on screen.
``dump(page, slot, tag)`` stores the full DOM and a list of interactive elements for
that state, so every screen can be audited afterwards without re-running the flow.
"""
from __future__ import annotations

import json
import os
import time
from urllib.parse import urlparse

_ELEMENTS_JS = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(); return !!(e.offsetParent || e.getClientRects().length) && r.width > 0 && r.height > 0; };
  return [...document.querySelectorAll('button, a, input, textarea, select, label, [role], [aria-label], [tabindex], dialog')]
    .map((e, i) => {
      const r = e.getBoundingClientRect();
      const attrs = {};
      for (const a of e.attributes) { if (a.value.length < 200) attrs[a.name] = a.value; }
      return { idx: i, tag: e.tagName.toLowerCase(), visible: vis(e),
               text: (e.innerText || '').trim().slice(0, 120),
               value: (e.type === 'password') ? '<password>' : ('value' in e ? String(e.value).slice(0, 80) : undefined),
               disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true',
               bbox: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)], attrs };
    });
}"""

STATES = (
    "checkpoint", "consent", "login_code", "password", "email_form", "chooser",
    "get_started", "edit_details", "details", "code", "meta_ai_home", "selfie",
    "confirmed", "unknown",
)


def _visible_inputs(page):
    """(type, name) pairs for visible inputs (first 20)."""
    out = []
    try:
        for el in page.locator("input").all()[:20]:
            try:
                if el.is_visible():
                    out.append(((el.get_attribute("type") or "text").lower(),
                                (el.get_attribute("name") or "").lower()))
            except Exception:
                continue
    except Exception:
        pass
    return out


def classify(page) -> str:
    """Return one of STATES from the live page. Never raises."""
    try:
        parsed = urlparse(page.url or "")
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        host, path = "", ""
    try:
        body = (page.inner_text("body") or "").lower()
    except Exception:
        body = ""
    inputs = _visible_inputs(page)
    has_text_input = any(t in ("text", "tel", "email", "") for t, _ in inputs)
    has_pw = any(t == "password" for t, _ in inputs)
    has_code = any("code" in n for _, n in inputs)

    if host.endswith("auth.meta.com") and "/checkpoints" in path and "confirm you" in body:
        return "checkpoint"
    if "/privacy/consent" in path or "allow the use of cookies from" in body:
        return "consent"
    if "check your email" in body and ("enter the code we sent" in body or "enter password instead" in body):
        return "login_code"
    if has_pw:
        return "password"
    if "what's your mobile number or email" in body or "what’s your mobile number or email" in body:
        return "email_form"
    if host.endswith("auth.meta.com") and ("log in or create an account" in body
                                           or "log in with your meta account" in body):
        return "chooser"
    if "get started on meta" in body:
        return "get_started"
    if "edit your meta ai details" in body:
        return "edit_details"
    if "first name" in body or "date of birth" in body or "select day" in body:
        return "details"
    if "confirmation code" in body or (has_code and "enter the code" in body):
        return "code"
    if host.endswith("meta.ai"):
        return "meta_ai_home"
    if "upload a verification selfie" in body or "selfie" in body:
        return "selfie"
    if "account created" in body or "where should we start" in body or "provisioned" in body:
        return "confirmed"
    if has_text_input:
        return "email_form"
    return "unknown"


def dump(page, slot, tag: str, root: str | None = None) -> str:
    """Store the full DOM (+ elements) under logs/dom/<slot>/. Returns the base path."""
    base_root = root or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "dom")
    d = os.path.join(base_root, str(slot or "unknown"))
    os.makedirs(d, exist_ok=True)
    stem = f"{time.strftime('%H%M%S')}_{tag}".replace("/", "_")
    base = os.path.join(d, stem)
    try:
        with open(base + ".html", "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception as e:
        with open(base + ".error.txt", "w", encoding="utf-8") as f:
            f.write(str(e))
    try:
        els = page.evaluate(_ELEMENTS_JS)
        with open(base + ".elements.json", "w", encoding="utf-8") as f:
            json.dump({"url": page.url, "elements": els}, f, indent=1, ensure_ascii=False)
    except Exception:
        pass
    return base
