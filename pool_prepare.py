"""Account PREPARATION for the cookie drains (IG pool + Meta list).

Three independent pieces, all best-effort and import-light:

* :func:`follow_explore` — follow N of Instagram's OWN suggested accounts from
  ``/explore/people/`` with real taps and human pacing. Targets differ per
  viewer, unlike the fixed operator list the API path uses (every account
  following the same list is an easy correlation signal).
* :func:`rename_in_page` — the ``accounts/edit`` POST issued FROM INSIDE the
  warmed page (browser cookies + JS tokens + fingerprint). The bare ``requests``
  POST is the one IG challenges (R&D — Cookie-Farm §14.1); this carries the
  context that one lacks, with no Accounts-Center UI walk.
* :class:`MetaListSession` — drains a Meta Creator account (platform ``Meta``,
  status ``MetaCreated``, no IG session yet): claim → browser → IG login happen
  BEFORE the Telegram task starts, so a login challenge costs no bot TTL; after
  the task issues the username, join with it, follow, export the cookie.
"""
from __future__ import annotations

import os
import random
import re
import time
from typing import Callable, Optional

import store

try:  # same dead-end type the rest of the cookie cycles already handle
    from pipelines.telegram.tg_support import IGDeadEnd
except Exception:  # pragma: no cover
    class IGDeadEnd(Exception):
        pass

_FOLLOW_LABELS = ("follow", "follow back")


# ──────────────────────────────────────────────────────────────────────────
# Follow — /explore/people/ (IG's own suggestions, real taps, human pacing)
# ──────────────────────────────────────────────────────────────────────────
_JS_TAG_FOLLOW = """(labels) => {
  document.querySelectorAll('[data-mc-follow]').forEach(e => e.removeAttribute('data-mc-follow'));
  const vh = window.innerHeight || 800;
  const els = Array.from(document.querySelectorAll('button, div[role="button"]'));
  for (const el of els) {
    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
    if (!labels.includes(t)) continue;
    if (el.hasAttribute('data-mc-skip')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
    el.setAttribute('data-mc-follow', '1');
    return true;
  }
  return false;
}"""

_JS_FAILED_TO_LOAD = """() => {
  const t = (document.body && document.body.innerText || '').toLowerCase();
  return t.includes('failed to load');
}"""

_JS_ACTION_BLOCK = """() => {
  const t = (document.body && document.body.innerText || '').toLowerCase();
  return /try again later|action blocked|we limit how often|temporarily blocked/.test(t);
}"""


# The in-app entry points to "Discover people" (header icon / "See all" on the
# feed's Suggested-for-you rail). Clicked like a user would — no typed deep link.
_PEOPLE_SELECTORS = (
    'a[href="/explore/people/"]',
    'a[href*="/explore/people"]',
    '[aria-label="Discover people"]',
    '[aria-label*="Discover people" i]',
    '[aria-label="Discover People"]',
)


def _open_people_by_click(runner, page, log) -> bool:
    """Reach /explore/people/ by navigating the UI: feed -> Discover people.
    Falls back to a direct goto ONLY when no in-app entry point exists."""
    try:
        if "/explore/people" in (page.url or ""):
            return True
        if "instagram.com" not in (page.url or "") or "/accounts/" in (page.url or ""):
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45000)
        try:
            runner._dismiss_ig_sheets(page)
        except Exception:
            pass
        # settle on the feed like a user: a short look, a small scroll
        page.wait_for_timeout(random.randint(2500, 5000))
        try:
            runner._touch_scroll(page, dy=random.randint(200, 420))
            page.wait_for_timeout(random.randint(900, 2000))
            runner._touch_scroll(page, dy=-random.randint(120, 300))
        except Exception:
            pass
        for sel in _PEOPLE_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    page.wait_for_timeout(random.randint(600, 1400))
                    loc.click(timeout=4000)
                    page.wait_for_url("**/explore/people**", timeout=15000)
                    log("[👥] opened Discover people from the feed (clicked).")
                    return True
            except Exception:
                continue
        log("[👥] no in-app Discover-people entry found — falling back to a direct load.")
        page.goto("https://www.instagram.com/explore/people/",
                  wait_until="domcontentloaded", timeout=45000)
        return True
    except Exception as exc:
        log(f"[👥] explore/people load failed: {str(exc)[:80]}")
        return False



def follow_explore(runner, page, need: int, log: Callable[[str], None],
                   humanize: bool = True) -> int:
    """Follow ``need`` suggested accounts on ``/explore/people/``. Returns the
    number that actually flipped to Following/Requested.

    Raises :class:`IGDeadEnd` ONLY on Instagram's "Failed to Load." toast after
    a tap — a DEAD account. The drain purges it and moves on; the Meta-list
    session marks it Failed. Everything else is swallowed (returns what was
    achieved)."""
    need = int(need or 0)
    if need <= 0:
        return 0
    if not _open_people_by_click(runner, page, log):
        return 0
    try:
        runner._dismiss_ig_sheets(page)
    except Exception:
        pass
    # Human beat before the first tap.
    try:
        page.wait_for_timeout(random.randint(1500, 3000) if humanize else random.randint(800, 1500))
    except Exception:
        return 0

    # One-time trace of the page's OWN follow request (names only — no cookie or
    # token values) so the API follow can be matched to what Instagram really
    # accepts. Logs at most 2 lines; INSTA_TRACE_FOLLOW=0 turns it off.
    if str(os.environ.get("INSTA_TRACE_FOLLOW", "1")).strip().lower() not in ("0", "false", "no", "off"):
        _seen = []

        def _trace_req(r):
            try:
                if len(_seen) >= 2 or r.method != "POST":
                    return
                u = r.url
                if not any(k in u for k in ("friendships", "graphql", "/api/v1/")):
                    return
                h = {k.lower(): v for k, v in (r.headers or {}).items()}
                keep = {k: h[k] for k in ("x-ig-app-id", "x-asbd-id", "x-instagram-ajax",
                                          "content-type", "x-requested-with") if k in h}
                body_keys = sorted({kv.split("=")[0] for kv in (r.post_data or "").split("&") if kv})[:12]
                _seen.append(1)
                log(f"[👥][trace] page POST {u.split('instagram.com')[-1][:90]} hdr={keep} "
                    f"has_claim={'x-ig-www-claim' in h} body_keys={body_keys}")
            except Exception:
                pass

        try:
            page.on("request", _trace_req)
        except Exception:
            pass

    done = 0
    misses = 0
    attempts = 0
    max_attempts = max(need * 4, 12)
    while done < need and attempts < max_attempts:
        attempts += 1
        try:
            found = page.evaluate(_JS_TAG_FOLLOW, list(_FOLLOW_LABELS))
        except Exception:
            found = False
        if not found:
            misses += 1
            if misses > 6:
                log(f"[👥] no Follow button found on explore/people ({done}/{need}).")
                break
            try:
                runner._touch_scroll(page, dy=random.randint(260, 520))
            except Exception:
                pass
            try:
                page.wait_for_timeout(900 if misses < 3 else 1600)
            except Exception:
                break
            continue
        misses = 0
        btn = page.locator('[data-mc-follow="1"]').first
        try:
            # multi_insta.exe parity: scroll into center view and execute direct DOM click
            # to dispatch native click events to React without synthetic touch detection.
            btn.evaluate("""el => {
                el.scrollIntoView({block: 'center'});
                el.click();
            }""")
        except Exception as exc:
            try:
                btn.click(timeout=2000, force=True)
            except Exception:
                pass
        # IG's "Failed to Load." toast after a Follow tap = this account is
        # follow-blocked right now. Exit immediately.
        try:
            page.wait_for_timeout(500)
            if page.evaluate(_JS_FAILED_TO_LOAD):
                try:
                    runner.ig_followed_count = done
                except Exception:
                    pass
                log(f"[❌] 'Failed to Load' toast detected after {done} follow(s) — exiting immediately.")
                raise IGDeadEnd(f"follow 'Failed to Load' toast after {done} follow(s) — dead account")
        except IGDeadEnd:
            raise
        except Exception:
            pass
        # multi_insta.exe parity: count the follow upon click and skip to next row
        done += 1
        log(f"[👥] followed {done}/{need} (explore/people).")
        try:
            page.evaluate("document.querySelectorAll('[data-mc-follow]')"
                          ".forEach(e => e.setAttribute('data-mc-skip','1'))")
        except Exception:
            pass
        try:
            if page.evaluate(_JS_ACTION_BLOCK):
                log(f"[❌] IG action-block notice after {done} follow(s) — exiting immediately.")
                raise IGDeadEnd(f"IG action-block notice after {done} follow(s)")
        except IGDeadEnd:
            raise
        except Exception:
            pass
        try:
            runner._touch_scroll(page, dy=random.randint(120, 320))
        except Exception:
            pass
        try:
            page.wait_for_timeout(random.randint(3000, 7000) if humanize else random.randint(2000, 4500))
        except Exception:
            break
    try:
        runner.ig_followed_count = done
    except Exception:
        pass
    return done


# ──────────────────────────────────────────────────────────────────────────
# Rename — accounts/edit POST from INSIDE the warmed page
# ──────────────────────────────────────────────────────────────────────────
_JS_RENAME = """async ([target, csrf]) => {
  const body = new URLSearchParams({ username: target }).toString();
  const r = await fetch('/api/v1/web/accounts/edit/', {
    method: 'POST', credentials: 'include',
    headers: {
      'X-CSRFToken': csrf,
      'X-IG-App-ID': '936619743392459',
      'X-Requested-With': 'XMLHttpRequest',
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  const text = await r.text();
  return { status: r.status, body: text.slice(0, 400) };
}"""


def rename_in_page(page, ctx, target: str) -> tuple[bool, str]:
    """POST ``accounts/edit`` from the open instagram.com page. (ok, message)."""
    import json
    try:
        csrf = ""
        for c in ctx.cookies():
            if c.get("name") == "csrftoken" and "instagram.com" in str(c.get("domain", "")):
                csrf = c.get("value") or ""
                break
        if "instagram.com" not in (page.url or ""):
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
        res = page.evaluate(_JS_RENAME, [target, csrf]) or {}
    except Exception as exc:
        return False, f"in-page rename error: {str(exc)[:100]}"
    body = str(res.get("body") or "")
    status = res.get("status")
    try:
        j = json.loads(body)
        if j.get("status") == "ok":
            return True, "ok (in-page)"
        msg = j.get("message") or body[:160]
        if j.get("checkpoint_url") or j.get("lock"):
            msg = f"{msg} [lock url={j.get('checkpoint_url') or ''}]"
        return False, f"IG API: {msg}"
    except Exception:
        if body.lstrip()[:1] == "<":
            return False, f"HTTP {status} HTML (login/challenge — not renamed)"
        return False, f"HTTP {status}: {body[:100]}"


# ──────────────────────────────────────────────────────────────────────────
# Meta-list source
# ──────────────────────────────────────────────────────────────────────────
# "Can't find account" is deliberately NOT here: Meta Creator saves the account
# even when its best-effort provisioning wait times out (core/captcha.py
# _wait_meta_provisioned is "not a gate"), so a freshly saved account can be
# unknown to Instagram for a while. Treated as transient (retried, 3 strikes).
_PERMANENT = ("incorrect password", "phone number", "mobile number", "failed to load")


class MetaListSession:
    """One Meta-list account, owned from claim until it is consumed or released.

    ``open()``   — claim + browser + Instagram login (BEFORE the TG task).
    ``finish()`` — after the bot issued the username: join with it, follow,
                   (optional mock-2FA hook), export the cookie. On success the
                   record is converted into a pool-style account so every
                   existing downstream path (submit / restore / delete) works.
    ``close()``  — idempotent; restores the account if it was never finished.
    """

    def __init__(self, slot_id, is_headless, worker_factory, log,
                 stop_event=None, task="", captcha_mode="none"):
        self.slot_id = slot_id
        self.is_headless = is_headless
        self.worker_factory = worker_factory
        self.log = log
        self.stop_event = stop_event
        self.task = task
        self.captcha_mode = captcha_mode
        self.acc: Optional[dict] = None
        self.worker = None
        self.runner = None
        self.login_result = None
        self._settled = False       # account state already resolved (finished/failed)
        self._browser_open = False

    # ---- state helpers -------------------------------------------------
    def _fail(self, exc: BaseException) -> None:
        """Resolve the account after a failure: permanent → Failed, else set aside."""
        if self.acc is None or self._settled:
            return
        self._settled = True
        msg = str(exc).lower()
        try:
            if any(k in msg for k in _PERMANENT):
                store.update_account(self.acc["id"], {"status": "Failed"})
                self.log(f"[meta-list] {self.acc['id']} unusable on IG ({str(exc)[:70]}) — marked Failed.")
            else:
                store.mark_meta_list_challenged(self.acc["id"])
                self.log(f"[meta-list] {self.acc['id']} set aside "
                         f"{int(store._CHALLENGE_RETRY_SEC / 60)} min ({str(exc)[:70]}).")
        except Exception:
            pass

    def close_browser(self) -> None:
        if self.runner is not None:
            try:
                self.runner.finish()
            except Exception:
                pass
        if self.worker is not None:
            try:
                self.worker._cleanup_browser_resources()
            except Exception:
                pass
        self.runner = None
        self.worker = None
        self._browser_open = False

    def close(self) -> None:
        """Idempotent. Never leaves a claimed account stranded or a browser open."""
        if self.acc is not None and not self._settled:
            self._settled = True
            try:
                store.restore_ig_creator_account(self.acc["id"], rotate=True)
            except Exception:
                pass
        self.close_browser()

    # ---- phase 1: before the task -------------------------------------
    def open(self) -> Optional[dict]:
        """Claim + login. Returns the account, or None when the list is empty.
        Raises RuntimeError (account already resolved) when login fails."""
        acc = store.pop_meta_list_account()
        if not acc:
            return None
        self.acc = acc
        try:
            from runner import MetaInstaRunner
            from ai_config import SELFIE_PATH
            wf = self.worker_factory
            if wf is None:
                from worker import AISlotWorker as wf
            self.worker = wf(slot_id=self.slot_id, is_headless=self.is_headless)
            r = MetaInstaRunner(
                self.worker, twofa=False, telegram=False, tg_task=self.task,
                captcha_mode=self.captcha_mode, mail_provider="mailtd", target="telegram")
            if os.path.exists(SELFIE_PATH):
                r.selfie_path = SELFIE_PATH
            r.email = acc.get("email") or ""
            r.password = acc.get("meta_password") or acc.get("password") or ""
            r.username = acc.get("username") or ""
            r.name = acc.get("name") or ""
            # Present the SAME phone the Meta account was created on.
            if acc.get("device_model"):
                r.device_model = acc["device_model"]
            if acc.get("device_ua"):
                r.device_ua = acc["device_ua"]
            self.runner = r
            try:
                r._install_screenshot_hooks()
            except Exception:
                pass
            r._launch()
            self._browser_open = True
            self.log(f"[meta-list] claimed {acc['id']} ({r.email}) — logging in to Instagram…")
            self.login_result = r.ig_login()
            page = r._ig_tab()
            if r._has_human_check(page):
                raise RuntimeError("Instagram human checkpoint at login — dead end")
            self.log(f"[meta-list] IG login ok for {acc['id']} "
                     f"({'needs join' if self.login_result == 'needs_join' else 'profile step'}).")
            return acc
        except BaseException as exc:  # noqa: BLE001 — resolve the claim, then re-raise
            self._fail(exc)
            self.close_browser()
            raise RuntimeError(f"meta-list login failed: {exc}") from exc

    # ---- phase 2: after the task issued the username --------------------
    def finish(self, login: str, creds: dict, follow_count: int,
               pre_export: Optional[Callable[[], None]] = None) -> dict:
        """Join with the bot's username, follow, export the cookie. Returns the
        account dict (``cookies`` set) ready for the shared submit path."""
        r = self.runner
        acc = self.acc
        if r is None or acc is None:
            raise RuntimeError("meta-list session not open")
        try:
            creds = dict(creds or {})
            creds["login"] = login
            r.tg_creds = creds
            r.new_username = login
            r.new_password = creds.get("password")
            cname = (creds.get("first_name") or "").strip()
            if cname:
                r.name = cname

            self.log(f"[meta-list] joining Instagram as '{login}'…")
            r.ig_click_meta_card()
            r.ig_complete_join()
            if getattr(r, "ig_username", None):
                r.new_username = r.ig_username
            r.ig_dismiss_onboarding(follow=False)
            page = r._ig_tab()
            if r._has_human_check(page):
                raise RuntimeError("Instagram human checkpoint on fresh account — dead end")

            n = 0
            if follow_count > 0:
                # explore/people first, feed rail for any shortfall (core/follow.py).
                n = int(r.ig_follow_suggested(
                    max_follows=follow_count, humanize=follow_count > 2) or 0)
                self.log(f"[👥] followed {n}/{follow_count} on '{login}'.")

            # Short dwell before anything sensitive (human settle).
            try:
                dwell = float(os.environ.get("INSTA_META_DWELL_SEC", "8") or 8)
            except Exception:
                dwell = 8.0
            end = time.time() + max(0.0, dwell)
            while time.time() < end:
                try:
                    r._touch_scroll(page, dy=random.randint(250, 600))
                    page.wait_for_timeout(random.randint(1200, 2800))
                except Exception:
                    break

            if pre_export is not None:
                pre_export()

            ctx = getattr(getattr(r, "w", None), "context", None)
            jar = ctx.cookies() if ctx is not None else []
            ig = [c for c in jar if "instagram.com" in str(c.get("domain", ""))]
            if "sessionid" not in {c.get("name") for c in ig}:
                raise RuntimeError("no IG sessionid after join (login not completed)")
            cookie_str = "; ".join(
                f"{c['name']}={c['value']}" for c in ig
                if c.get("name") and c.get("value") is not None)
            if len(cookie_str) < 100:
                raise RuntimeError("cookie string too short (<100 chars) after join")
        except BaseException as exc:  # noqa: BLE001
            self._fail(exc)
            self.close_browser()
            raise

        # Convert the Meta record into a pool-style account: from here every
        # shared path (submit failure → restore, rejected → delete, success →
        # delete) behaves exactly as for an IG-pool account, and a failed
        # submit leaves a ready-to-drain IG account instead of a half-joined
        # Meta one.
        acc = dict(acc)
        acc.update({
            "cookies": cookie_str, "cookie": cookie_str,
            "platform": "Meta+Instagram", "username": login,
            "instagram_username": login, "followed": n,
            "status": "Submitting_PayGo",
        })
        try:
            store.update_account(acc["id"], {
                "cookies": cookie_str, "cookie": cookie_str,
                "platform": "Meta+Instagram", "username": login,
                "instagram_username": login, "followed": n,
                "status": "Submitting_PayGo", "claimed_at": time.time(),
            })
        except Exception:
            pass
        self._settled = True      # ownership passes to the shared submit path
        self.acc = acc
        self.close_browser()
        return acc
