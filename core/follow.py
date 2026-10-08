"""meta_creator-only follow override (keeps ``instagram/join.py`` byte-identical
with ``meta_auto_ai``).

``ig_follow_suggested`` first follows Instagram's OWN suggestions on
``/explore/people/`` (real taps, jittered pauses — see
:func:`pool_prepare.follow_explore`); only a shortfall falls through to the
original home-feed rail implementation. Every caller (IG Creator onboarding,
the cookie cycles, the Meta-list session) gets it through this one method.

Env: ``INSTA_FOLLOW_EXPLORE=0`` restores the original behaviour exactly;
``INSTA_FOLLOW_AFTER_LOGIN`` / ``INSTA_FOLLOW_COUNT`` keep their meaning.
"""
from __future__ import annotations

import os


def _off(name: str, default: str = "1") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in ("0", "false", "no", "off")


class ExploreFollowMixin:
    def ig_follow_suggested(self, max_follows: int = 2, humanize: bool = False):
        # Same gates as the original, so disabled/duplicate/zero-count cases
        # never touch the browser.
        # Profile first (bio / avatar / first post via API), THEN follow: an account
        # with a face and a post before it follows anyone looks like a person.
        self._ig_profile_first()
        api = str(os.environ.get("INSTA_FOLLOW_MODE", "ui")).strip().lower() == "api"
        if _off("INSTA_FOLLOW_AFTER_LOGIN") or (_off("INSTA_FOLLOW_EXPLORE") and not api):
            return super().ig_follow_suggested(max_follows=max_follows, humanize=humanize)
        if getattr(self, "_ig_follow_done", False):
            return super().ig_follow_suggested(max_follows=max_follows, humanize=humanize)
        try:
            need = int(os.environ.get("INSTA_FOLLOW_COUNT", "") or max_follows or 2)
        except Exception:
            need = 2
        if need <= 0:
            return 0
        if api:
            return self._ig_follow_via_api(need)

        try:
            from pool_prepare import follow_explore, IGDeadEnd
        except Exception:    # helper unavailable → the original pass, unchanged
            return super().ig_follow_suggested(max_follows=max_follows, humanize=humanize)

        done = 0
        try:
            p = self._ig_tab()
            if "instagram.com" not in (p.url or ""):
                return super().ig_follow_suggested(max_follows=max_follows, humanize=humanize)
            done = int(follow_explore(self, p, need, self.log, humanize=humanize) or 0)
            if done:
                self._ig_follow_done = True
            try:     # leave the session where the original pass leaves it: the feed
                p.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
        except IGDeadEnd:
            raise            # dead account: let the caller purge it and move on
        except Exception as exc:  # never let the new pass break the flow
            self.log(f'[⚠️] explore follow note (falling back to the feed rail): {str(exc)[:80]}')
            done = 0

        if done >= need:
            self.ig_followed_count = done
            return done
        # Shortfall → the proven feed-rail pass for the remainder.
        self._ig_follow_done = False
        rest = int(super().ig_follow_suggested(
            max_follows=max(1, need - done), humanize=humanize) or 0)
        self.ig_followed_count = done + rest
        return done + rest

    def _ig_follow_via_api(self, need: int) -> int:
        """Follow ``need`` operator-list targets through Instagram's web API,
        called from INSIDE the live tab (real TLS/cookies/headers — see
        instagram/ig_page_api.py). No UI clicks.

        Switch: INSTA_FOLLOW_MODE=api. API-only by design — a shortfall is NOT
        retried with UI clicks, so the operator's choice is what actually ran.
        """
        from instagram import ig_page_api
        from instagram.ig_api import pick_follow_targets
        from pool_prepare import IGDeadEnd
        self._ig_follow_done = True
        self.ig_followed_count = 0
        done = 0
        try:
            p = self._ig_tab()
            if "instagram.com" not in (p.url or ""):
                self.log(f'[👥][page-api] Not on Instagram ({p.url}) — no follow.')
            else:
                user = getattr(self, "ig_username", None) or getattr(self, "username", None) or ""
                # a few spares: unresolvable / failed targets move on to the next
                names = pick_follow_targets(need + 4, exclude=(user,) if user else ())
                done = int(ig_page_api.follow_targets(p, names, need, self.log) or 0)
        except ig_page_api.PageApiDead as exc:
            raise IGDeadEnd(f"API follow: session dead ({exc})")
        except IGDeadEnd:
            raise
        except Exception as exc:
            self.log(f'[⚠️] API follow failed: {str(exc)[:120]}')
        self.log(f'[👥][page-api] Follow pass complete: {done}/{need} (API only, no UI fallback).')
        self.ig_followed_count = done
        return done

    def _ig_profile_first(self) -> None:
        if getattr(self, "_ig_profile_done", False):
            return
        try:
            res = self.ig_api_profile()
            if any(res.values()):
                import random
                import time
                time.sleep(random.uniform(15.0, 35.0))   # let the profile "settle" before following
        except Exception as exc:
            self.log(f'[⚠️] API profile step note: {str(exc)[:100]}')

    def ig_api_profile(self) -> dict:
        """Optional API profile steps for the IG Creator: bio, avatar, first post.

        Each is its own switch (INSTA_API_BIO / INSTA_API_AVATAR / INSTA_API_POST),
        sent from inside the live tab. Media comes from ``IG_MEDIA_DIR`` (default
        ``<repo>/ig_media``): jpg/png/webp; ``bios.txt`` / ``captions.txt`` (one
        per line) are optional. Best-effort — a failed step is logged, never fatal.
        """
        import glob
        import random
        import time
        if getattr(self, "_ig_profile_done", False):
            return {}
        self._ig_profile_done = True
        want = {k: not _off(f"INSTA_API_{k.upper()}", "0") for k in ("bio", "avatar", "post")}
        if not any(want.values()):
            return {}
        from instagram import ig_page_api
        root = os.environ.get("IG_MEDIA_DIR") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ig_media")
        imgs = [f for ext in ("jpg", "jpeg", "png", "webp") for f in glob.glob(os.path.join(root, f"*.{ext}"))]

        def lines(name):
            try:
                with open(os.path.join(root, name), encoding="utf-8") as fh:
                    return [ln.strip() for ln in fh if ln.strip()]
            except Exception:
                return []

        try:
            p = self._ig_tab()
            if "instagram.com" not in (p.url or ""):
                p.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            self.log(f'[⚠️] API profile: no Instagram tab ({str(exc)[:80]})')
            return {}

        steps = []
        if want["bio"]:
            bios = lines("bios.txt")
            steps.append(("bio", (lambda: ig_page_api.set_bio(p, random.choice(bios))) if bios else None))
        if want["avatar"]:
            steps.append(("avatar", (lambda: ig_page_api.set_avatar(p, random.choice(imgs))) if imgs else None))
        if want["post"]:
            caps = lines("captions.txt")
            steps.append(("post", (lambda: ig_page_api.post_photo(
                p, random.choice(imgs), random.choice(caps) if caps else "")) if imgs else None))
        res = {}
        for i, (name, fn) in enumerate(steps):
            if fn is None:
                self.log(f'[🖼️][page-api] {name}: nothing to use in {root} — skipped.')
                res[name] = False
                continue
            if i:
                time.sleep(random.uniform(6.0, 14.0))
            try:
                ok, why = fn()
            except ig_page_api.PageApiDead as exc:
                self.log(f'[🖼️][page-api] {name}: session dead ({exc}) — stopping profile steps.')
                res[name] = False
                break
            except Exception as exc:
                ok, why = False, str(exc)
            res[name] = bool(ok)
            self.log(f'[🖼️][page-api] {name}: {"ok" if ok else "failed — " + str(why)[:100]}')
        return res
