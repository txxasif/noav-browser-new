"""
test/devtools_client.py — Chrome DevTools & CDP Inspection Helper
==================================================================
Provides real-time DOM accessibility scraping, interactive node discovery,
and step-by-step telemetry for reverse-engineering modern Instagram and Meta flows.
"""
from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, List, Optional


def find_free_port(preferred: int = 9222) -> int:
    """Return preferred port if free, or the next available port."""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def dump_full_session(context, path: str, warm_urls: tuple = ("https://mail.td/", "https://www.instagram.com/")) -> Dict[str, Any]:
    """Persist storage_state with localStorage origins intact.

    Playwright only serializes localStorage for origins touched in the
    current context session. A bare ``storage_state(path=...)`` on a fresh
    relaunch therefore silently drops ``mail.td`` tokens (and IG keys).
    Visiting each origin once before dumping keeps them in the file.
    Returns the dumped state dict.
    """
    lp = None
    try:
        lp = context.new_page()
        for url in warm_urls:
            try:
                lp.goto(url, wait_until="domcontentloaded", timeout=30000)
                lp.wait_for_timeout(2500)
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
    state = context.storage_state(path=path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return state


class DevToolsInspector:
    """Inspects live Playwright pages using DevTools DOM queries and CDP."""

    def __init__(self, artifacts_dir: Optional[str] = None):
        self.artifacts_dir = artifacts_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "artifacts"
        )
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self.step_counter = 0

    def capture(self, page, name: str, print_summary: bool = True) -> Dict[str, Any]:
        """Capture screenshot, DOM interactive elements, and accessibility snapshot."""
        self.step_counter += 1
        prefix = f"{self.step_counter:02d}_{name}"
        shot_path = os.path.join(self.artifacts_dir, f"{prefix}.png")
        json_path = os.path.join(self.artifacts_dir, f"{prefix}_summary.json")

        # 1. Screenshot
        try:
            page.screenshot(path=shot_path)
        except Exception as exc:
            shot_path = f"FAILED: {exc}"

        # 2. Extract DOM interactive nodes via evaluate
        dom_data = self._scrape_dom(page)
        dom_data["step"] = prefix
        dom_data["url"] = page.url
        dom_data["screenshot"] = shot_path

        # 3. Save JSON summary
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(dom_data, f, indent=2)
        except Exception:
            pass

        if print_summary:
            self._print_summary(prefix, dom_data)

        return dom_data

    def _scrape_dom(self, page) -> Dict[str, Any]:
        """Scrape interactive elements (buttons, inputs, dialogs) from the page."""
        js_script = """
        () => {
            const getVisible = (el) => {
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       style.opacity !== '0' &&
                       rect.width > 0 && rect.height > 0;
            };

            const buttons = [];
            document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]').forEach(el => {
                if (getVisible(el)) {
                    buttons.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || '',
                        role: el.getAttribute('role') || '',
                        text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 100),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        disabled: el.disabled || el.getAttribute('aria-disabled') === 'true'
                    });
                }
            });

            const inputs = [];
            document.querySelectorAll('input, textarea, select').forEach(el => {
                if (getVisible(el) && el.type !== 'hidden') {
                    inputs.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        placeholder: el.placeholder || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        autocomplete: el.getAttribute('autocomplete') || '',
                        valueLength: (el.value || '').length
                    });
                }
            });

            const dialogs = [];
            document.querySelectorAll('[role="dialog"], [role="alertdialog"], [aria-modal="true"]').forEach(el => {
                if (getVisible(el)) {
                    dialogs.push({
                        role: el.getAttribute('role') || 'dialog',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        textSnippet: (el.innerText || '').slice(0, 200).replace(/\\s+/g, ' ')
                    });
                }
            });

            const headings = [];
            document.querySelectorAll('h1, h2, h3, [role="heading"]').forEach(el => {
                if (getVisible(el)) {
                    headings.push({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 100)
                    });
                }
            });

            return {
                title: document.title,
                headings: headings.slice(0, 10),
                dialogs: dialogs.slice(0, 5),
                inputs: inputs.slice(0, 20),
                buttons: buttons.slice(0, 30),
                bodyPreview: (document.body ? document.body.innerText || '' : '').slice(0, 400).replace(/\\s+/g, ' ')
            };
        }
        """
        try:
            return page.evaluate(js_script)
        except Exception as exc:
            return {"error": str(exc)}

    def _print_summary(self, prefix: str, data: Dict[str, Any]):
        """Print structured terminal summary for pair-programming observability."""
        print(f"\n=======================================================", flush=True)
        print(f"  [DevTools Inspector] STEP: {prefix}", flush=True)
        print(f"  URL:   {data.get('url')}", flush=True)
        print(f"  Title: {data.get('title')}", flush=True)
        if data.get("headings"):
            hd_str = " | ".join(f"[{h.get('tag')}] {h.get('text')}" for h in data["headings"][:4])
            print(f"  Headings: {hd_str}", flush=True)
        if data.get("dialogs"):
            print(f"  ⚠️ Modals/Dialogs ({len(data['dialogs'])}):", flush=True)
            for d in data["dialogs"]:
                print(f"    - {d.get('role')} (aria='{d.get('ariaLabel')}'): {d.get('textSnippet')[:80]}...", flush=True)
        if data.get("inputs"):
            print(f"  Inputs ({len(data['inputs'])}):", flush=True)
            for inp in data["inputs"]:
                print(f"    - <input type='{inp.get('type')}' name='{inp.get('name')}' placeholder='{inp.get('placeholder')}' aria='{inp.get('ariaLabel')}'>", flush=True)
        if data.get("buttons"):
            btn_texts = [f"'{b.get('text')}'" for b in data["buttons"] if b.get("text")]
            print(f"  Buttons ({len(btn_texts)}): {', '.join(btn_texts[:10])}", flush=True)
        print(f"  Shot: {data.get('screenshot')}", flush=True)
        print(f"=======================================================\n", flush=True)
