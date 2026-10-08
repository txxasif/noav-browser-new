"""mtproto_pool.py — pooled warm MTProto workers.

Split out of ``mtproto_bot.py`` as a **pure code move** (no behaviour change).
The pool owner thread builds ``MtprotoTasklyBot`` lazily, so this module imports
it from ``mtproto_bot``; ``mtproto_bot`` re-exports ``MtprotoPooledBot`` and
``_mtproto_owner_loop`` at its end (after the class is defined) to avoid the
import cycle.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_config import TG_BOTS, TG_DEFAULT_TASK  # noqa: E402
from mtproto_bot import MtprotoTasklyBot  # noqa: E402

# ==============================================================================
# Pooled warm workers — same shape/API as tg_bot.PooledTelegramBot
# ==============================================================================
def _mtproto_owner_loop(q_in, q_out, session_path, tg_id, bot_target, log):
    """Owner thread: one Telethon client per session, commands run FIFO."""
    bot = None
    while True:
        cmd, target, args, kwargs = q_in.get()
        if cmd == "shutdown":
            try:
                if bot is not None:
                    bot.disconnect()
            except Exception:
                pass
            try:
                # Tuple-shaped like every other reply: _call unpacks
                # ``ok, res = q_out.get()``, so a bare bool here used to
                # surface as "TypeError: cannot unpack non-iterable bool
                # object" on any racing/in-flight call (Slot #5, 2026-09-24).
                q_out.put((True, True))
            except Exception:
                pass
            break
        try:
            tgt = target or bot_target
            if bot is None or bot.bot_target != tgt:
                if bot is not None:
                    bot.close()
                bot = MtprotoTasklyBot(session_path=session_path, tg_id=tg_id,
                                       bot_target=tgt, log=kwargs.get("log", log) or log)
            fn = getattr(bot, cmd)
            res = fn(*args, **kwargs)
            q_out.put((True, res))
        except Exception as e:
            q_out.put((False, e))


class MtprotoPooledBot:
    """Warm pooled MTProto bot — mirrors ``tg_bot.PooledTelegramBot``.

    The pool key is the session file. No browser, so no SingletonLock, warm
    idle reaping or RAM ceiling — instances are cheap enough to keep all up.
    """

    _pool = {}
    _pool_lock = threading.Lock()
    _WARM_IDLE_SECS = 1800

    def __init__(self, profile_dir=None, bot_name=None, bot_target="taskly",
                 headless=True, log=print, session_path=None, tg_id=None):
        self.session_path = session_path or profile_dir
        if not self.session_path:
            raise RuntimeError("MtprotoPooledBot needs session_path (or profile_dir)")
        self.tg_id = tg_id or os.path.basename(str(self.session_path)).split(".")[0]
        self.bot_target = bot_target
        cfg = TG_BOTS.get(bot_target, TG_BOTS["taskly"])
        self.bot_name = bot_name or cfg["name"]
        self.headless = bool(headless)
        self.log = log
        self.profile_dir = self.session_path  # contract parity
        self._key = self.session_path
        self._reap_idle()
        with MtprotoPooledBot._pool_lock:
            self._ent = MtprotoPooledBot._ensure_locked(
                self._key, self.session_path, self.tg_id, bot_target, log)

    @classmethod
    def _ensure_locked(cls, key, session_path, tg_id, bot_target, log):
        """Return the live pool entry for ``key``, rebuilding a dead one.

        Must hold ``_pool_lock``. A dead owner (reaped/dropped under a live
        lease by mem-shed or idle eviction) is rebuilt transparently so the
        next command reconnects instead of talking to a dead queue.
        """
        ent = cls._pool.get(key)
        try:
            alive = ent is not None and ent["thread"].is_alive()
        except Exception:
            alive = False
        if not alive:
            if ent is not None:
                try:
                    cls._pool.pop(key, None)
                except Exception:
                    pass
            q_in: queue.Queue = queue.Queue()
            q_out: queue.Queue = queue.Queue()
            t = threading.Thread(
                target=_mtproto_owner_loop,
                args=(q_in, q_out, session_path, tg_id,
                      bot_target, log), daemon=True)
            t.start()
            ent = {"thread": t, "q_in": q_in, "q_out": q_out,
                   "last_used": time.time()}
            cls._pool[key] = ent
        ent["last_used"] = time.time()
        return ent

    @staticmethod
    def _leased_keys() -> set:
        """Pool keys currently leased to a live cycle (never reap these)."""
        try:
            from tg_accounts import tg_manager
            return set(tg_manager.leased_ids())
        except Exception:
            return set()

    @staticmethod
    def _reap_idle() -> None:
        victims = []
        leased = MtprotoPooledBot._leased_keys()
        with MtprotoPooledBot._pool_lock:
            now = time.time()
            for k, ent in list(MtprotoPooledBot._pool.items()):
                # A live lease holds no pool traffic during long IG phases
                # (2FA grind), so last_used goes stale while the cycle is
                # very much alive — reaping it murders the task (2026-09-24).
                if str(k) in leased or os.path.basename(str(k)) in leased:
                    continue
                try:
                    if now - float(ent.get("last_used", now)) > MtprotoPooledBot._WARM_IDLE_SECS:
                        victims.append((k, ent))
                        del MtprotoPooledBot._pool[k]
                except Exception:
                    pass
        for _k, ent in victims:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=10)
            except Exception:
                pass

    def _call(self, cmd, *args, **kwargs):
        with MtprotoPooledBot._pool_lock:
            self._ent = MtprotoPooledBot._ensure_locked(
                self._key, self.session_path, self.tg_id,
                self.bot_target, self.log)
            ent = self._ent
        ent["q_in"].put((cmd, self.bot_target, args, kwargs))
        try:
            item = ent["q_out"].get(timeout=180)
        except queue.Empty:
            raise RuntimeError(f"MTProto bot thread hung on '{cmd}' (180s)")
        # A non-tuple here means a stale sentinel from a reaped owner, never
        # a real reply — fail loud with the cause, not "cannot unpack
        # non-iterable bool object".
        if not isinstance(item, tuple) or len(item) != 2:
            raise RuntimeError(
                f"MTProto bot session for '{self.tg_id}' was reaped mid-task "
                f"(stale pool reply) on '{cmd}' — retry the task")
        ok, res = item
        if not ok:
            raise res
        return res

    def start(self):
        return self._call("open", log=self.log)

    def open(self):
        return self.start()

    def logged_in(self):
        try:
            return self._call("logged_in")
        except Exception:
            return None

    def open_bot(self):
        return self._call("open_bot")

    @property
    def last_task_verdict(self):
        try:
            return self._call("get_last_task_verdict")
        except Exception:
            return getattr(self, "_last_task_verdict", None)

    def choose_task(self, task=TG_DEFAULT_TASK):
        res = self._call("choose_task", task)
        try:
            self._last_task_verdict = self._call("get_last_task_verdict")
        except Exception:
            pass
        return res

    def start_task(self):
        return self._call("start_task")

    def submit_2fa_key(self, key, allow_local_fallback=True):
        return self._call("submit_2fa_key", key, allow_local_fallback=allow_local_fallback)

    def request_email_code(self, timeout=45.0):
        return self._call("request_email_code", timeout=timeout)

    def press_get_code(self, wait=6.0):
        return self._call("press_get_code", wait=wait)

    def submit_cookie(self, cookie, timeout=20.0):
        return self._call("submit_cookie", cookie, timeout=timeout)

    def mark_registered(self):
        return self._call("mark_registered")

    def reset_to_main_menu(self, timeout=30):
        return self._call("reset_to_main_menu", timeout=timeout)

    def cancel_task(self):
        return self._call("cancel_task")

    def clear_orphan_task(self):
        try:
            return self._call("clear_orphan_task")
        except Exception:
            return False

    def _sleep_flood(self, exc, what: str = "request") -> int:
        secs = MtprotoTasklyBot._flood_wait_seconds(exc)
        if secs <= 0:
            return 0
        try:
            import tg_accounts as _tgm
            mgr = getattr(_tgm, "tg_manager", None)
            if mgr is not None:
                mgr._reload()
                try:
                    max_rec = int(os.environ.get("INSTA_TG_FLOOD_MAX_RECORD", "120") or 120)
                except Exception:
                    max_rec = 120
                capped = max(1, min(int(secs), max_rec))
                for a in mgr.accounts:
                    if a.get("id") == self.tg_id:
                        a["flood_until"] = int(time.time() + capped)
                        break
                mgr.save()
        except Exception:
            pass
        try:
            cap = int(os.environ.get("INSTA_TG_FLOOD_MAX_SLEEP", "25") or 25)
        except Exception:
            cap = 25
        wait = max(1, min(secs, cap))
        self.log(f"[tg] ⏳ FloodWait {secs}s on {what} — pausing {wait}s, then the account is parked for {secs}s.")
        time.sleep(wait)
        return wait

    def close(self, ok=True):
        try:
            return self._call("close", ok=ok)
        except Exception:
            return False

    @classmethod
    def _match_keys(cls, key: str) -> list:
        """Pool keys identifying ``key`` (session path, profile dir or id).

        ``_reap_wedged_tg_browser`` passes the *profile dir* while the pool
        is keyed by *session file* — without flexible matching that reap was
        a silent no-op for MTProto and wedged owners lived forever.
        """
        if not key:
            return []
        cands = {str(key)}
        try:
            cands.add(os.path.basename(str(key)))
            base = os.path.basename(str(key)).split(".")[0]
            cands.add(base)
        except Exception:
            pass
        found = []
        for k in list(cls._pool.keys()):
            try:
                kb = os.path.basename(str(k)).split(".")[0]
            except Exception:
                kb = ""
            if k in cands or str(k) in cands or kb in cands:
                found.append(k)
        return found

    @classmethod
    def drop_profile(cls, key: str) -> None:
        if not key:
            return
        with cls._pool_lock:
            ents = [cls._pool.pop(k, None) for k in cls._match_keys(key)]
            ents = [e for e in ents if e is not None]
        for ent in ents:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=10)
            except Exception:
                pass

    @classmethod
    def drop_all(cls, skip_leased: bool = False) -> None:
        """Shut down pooled owners. ``skip_leased=True`` keeps live leases.

        The memory watchdog MUST pass ``skip_leased``: killing a leased
        owner's thread mid-task poisons its queue and the cycle dies with a
        cryptic unpack error instead of finishing (2026-09-24). Engine
        shutdown paths keep the default (kill everything).
        """
        leased = cls._leased_keys() if skip_leased else set()
        victims = []
        with cls._pool_lock:
            for k in list(cls._pool.keys()):
                try:
                    if (str(k) in leased
                            or os.path.basename(str(k)) in leased
                            or os.path.basename(str(k)).split(".")[0] in leased):
                        continue
                except Exception:
                    pass
                ent = cls._pool.pop(k, None)
                if ent is not None:
                    victims.append(ent)
        for ent in victims:
            try:
                ent["q_in"].put(("shutdown", None, (), {}))
                ent["thread"].join(timeout=5)
            except Exception:
                pass

    @classmethod
    def close_inspectors(cls, *a, **kw) -> int:
        """No browsers to shed — no-op (kept for worker parity)."""
        return 0
