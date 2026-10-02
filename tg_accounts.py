"""
meta_auto_ai — Telegram account pool
====================================
Manages **multiple** persistent Telegram profiles so several account-creation
tasks can run in parallel, each in its own Telegram account (the Taskly bot
allows only one task per account/bot at a time).

Model
-----
* Each account has a persistent Chromium profile under ``telegram_profiles/<id>``
  (session survives restarts).
* Accounts are **leased**: a worker picks an ``idle`` account, marks it ``busy``,
  runs one cycle, then releases it back to ``idle``.
* Metadata is persisted in ``data/tg_accounts.json``:

      { id, label, profile_dir, status, logged_in, tasks_done, last_used, last_account, leased_at }

* Leases carry ``leased_at`` (unix ts); a ``busy`` record whose lease is
  older than ``LEASE_TTL`` is reclaimed automatically (dead worker safety).
* Up to ``TG_MAX_ACCOUNTS`` (20) sessions are kept; up to ``TG_MAX_PARALLEL`` (5)
  run at once.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_config import (  # noqa: E402
    DATA_DIR,
    LEGACY_TELEGRAM_PROFILE,
    TELEGRAM_PROFILES_DIR,
    TG_ACCOUNTS_JSON,
    TG_DEFAULT_MODE,
    TG_MAX_ACCOUNTS,
)


# --------------------------------------------------------------------------- #
# TG FREEZE — exclusive access for sensitive ops (WITHDRAW).
# A file flag every Python process reads, so NO worker can lease a Telegram
# profile while a withdrawal is in flight. Set/cleared by tg_withdraw.py and
# the dashboard's "Freeze TG" button.
# --------------------------------------------------------------------------- #
FREEZE_FILE = os.path.join(DATA_DIR, "tg_freeze.json")


def is_frozen() -> bool:
    """True while TG is frozen for an exclusive operation (e.g. withdraw)."""
    try:
        with open(FREEZE_FILE, encoding="utf-8") as f:
            return bool(json.load(f).get("frozen"))
    except Exception:
        return False


def freeze_info() -> dict:
    try:
        with open(FREEZE_FILE, encoding="utf-8") as f:
            d = json.load(f)
            return {"frozen": bool(d.get("frozen")), "reason": d.get("reason") or "", "at": d.get("at")}
    except Exception:
        return {"frozen": False, "reason": "", "at": None}


def set_frozen(on: bool, reason: str = "") -> dict:
    """Freeze/unfreeze TG access. Frozen blocks acquire()/usable() pool-wide."""
    try:
        if on:
            os.makedirs(os.path.dirname(FREEZE_FILE), exist_ok=True)
            tmp = FREEZE_FILE + f".tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"frozen": True, "reason": reason, "at": time.time()}, f)
            os.replace(tmp, FREEZE_FILE)
        else:
            if os.path.exists(FREEZE_FILE):
                os.remove(FREEZE_FILE)
    except Exception:
        pass
    return freeze_info()


def profile_dir(tg_id: str) -> str:
    return os.path.join(TELEGRAM_PROFILES_DIR, tg_id)


LEASE_TTL = 1200  # seconds; a busy lease older than this is presumed orphaned
# A probe lease is intentionally short-lived (the probe reads one counter and
# releases). The orchestrator caps it at 30s and SIGKILLs on timeout, which
# skips the probe's `finally` and orphans the lease — so reclaim probes far
# sooner than a real task lease, or one slow probe wedges an account for 20 min.
PROBE_LEASE_TTL = 90


def _pid_alive(pid) -> bool:
    """True when ``pid`` names a live process. Missing/unknown -> False.

    Paired with :func:`_pid_is_set` below: a MISSING pid means "not recorded yet"
    (the probe stamps it moments after acquiring), which must NOT be read as
    "owner gone" or we would steal a lease from an actively working probe.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # exists, owned by someone else
    except Exception:
        return False


def _pid_is_set(pid) -> bool:
    """True only when a real, positive pid was actually recorded."""
    try:
        return int(pid) > 0
    except (TypeError, ValueError):
        return False


def _owner_gone(rec: dict) -> bool:
    """True when a probe lease was stamped with a pid that is now DEAD."""
    pid = rec.get("probe_pid")
    return _pid_is_set(pid) and not _pid_alive(pid)


def _lease_age(rec: dict) -> float | None:
    """Age in seconds of a busy lease, or None if it cannot be determined.

    Prefers the ``leased_at`` stamp; falls back to ``last_used`` for leases
    taken before stamps existed. Unknown age → None (never auto-reclaim).
    """
    try:
        if rec.get("leased_at"):
            return time.time() - float(rec["leased_at"])
        lu = rec.get("last_used")
        if lu:
            dt = datetime.strptime(str(lu), "%Y-%m-%d %H:%M:%S")
            return time.time() - dt.timestamp()
    except Exception:
        pass
    return None


def has_session(dir_path: str) -> bool:
    """True only when the profile holds a LIVE Telegram Web session.

    The web session is authenticated by the ``stel_web_auth`` cookie; the old
    check (any "telegram" file in IndexedDB/localStorage) stayed True after a
    logout, so a logged-out profile kept being leased and the bot boot failed
    with "Telegram profile is not logged in" (observed 2026-09-20: tg_2/tg_4).
    Cookie-name is plaintext in the SQLite file, so we can check it cheaply.
    Falls back to the legacy heuristic if the DB is missing/locked (never a
    false "logged out" while a browser is mid-write).
    """
    default = os.path.join(dir_path, "Default")
    cookie_db = os.path.join(default, "Cookies")
    if os.path.isfile(cookie_db):
        try:
            import sqlite3
            con = sqlite3.connect(f"file:{cookie_db}?mode=ro", uri=True, timeout=2.0)
            try:
                hit = con.execute(
                    "SELECT 1 FROM cookies WHERE name='stel_web_auth' LIMIT 1").fetchone()
                return bool(hit)
            finally:
                con.close()
        except Exception:
            pass  # DB busy/locked -> fall through to the legacy heuristic
    for sub in ("IndexedDB", os.path.join("Local Storage", "leveldb")):
        try:
            p = os.path.join(default, sub)
            if os.path.isdir(p) and any("telegram" in n.lower() for n in os.listdir(p)):
                return True
        except Exception:
            pass
    return False


def record_mode(rec: dict) -> str:
    """Transport for a pool record: ``"mtproto"`` (Telethon) or ``"web"``."""
    return "mtproto" if str(rec.get("mode") or "").lower() == "mtproto" else "web"


def session_ok(rec: dict) -> bool:
    """Live Telegram session for this record, regardless of transport.

    Web records authenticate via the ``stel_web_auth`` cookie in the Chromium
    profile; MTProto records authenticate via a Telethon ``.session`` file. The
    pool's lease/skip logic must ask THIS, not ``has_session`` directly, or
    MTProto accounts would never be considered logged in.
    """
    if record_mode(rec) == "mtproto":
        try:
            from mtproto_bot import has_mtproto_session, session_file
            sess = rec.get("session_file")
            if not sess or not os.path.isfile(sess):
                sess = session_file(str(rec.get("id") or ""))
            return has_mtproto_session(sess)
        except Exception:
            return False
    pdir = rec.get("profile_dir")
    if not pdir or not os.path.isdir(pdir):
        pdir = profile_dir(str(rec.get("id") or ""))
    return has_session(pdir)


def _profile_locked(dir_path: str) -> bool:
    """True when a live Chromium still holds this profile's SingletonLock.
    Mirrors ``warm_pool.lock_holder_alive`` / ``store.js tgProfileLocked``:
    read the ``<host>-<pid>`` symlink target and verify /proc/<pid>/cmdline
    still references the dir. Used to tell a LIVE dashboard inspection from a
    STALE hold left behind by a crashed/killed window.
    """
    import re as _re

    dur = str(dir_path or "")
    if not dur:
        return False
    try:
        target = os.readlink(os.path.join(dur, "SingletonLock"))
    except Exception:
        return False
    m = _re.search(r"-(\d+)$", target or "")
    if not m:
        return False
    try:
        with open(f"/proc/{m.group(1)}/cmdline", "rb") as fh:
            cmd = fh.read().decode("utf-8", "replace")
    except Exception:
        return False
    return dur in cmd and ("chrome" in cmd or "chromium" in cmd)


class TGAccountManager:
    """Thread-safe pool of Telegram accounts (lease / release / persist)."""

    def __init__(self):
        self._cv = threading.Condition()
        self._migrate_legacy()
        self.accounts = self._load()

    # -- persistence ----------------------------------------------------
    def _migrate_legacy(self):
        """Move the old single ``telegram_profile/`` to ``telegram_profiles/tg_1``."""
        t1 = profile_dir("tg_1")
        if os.path.isdir(LEGACY_TELEGRAM_PROFILE) and not os.path.isdir(t1):
            try:
                shutil.move(LEGACY_TELEGRAM_PROFILE, t1)
            except Exception:
                pass

    def _new_record(self, tg_id, label):
        d = profile_dir(tg_id)
        rec = {"id": tg_id, "label": label, "profile_dir": d, "status": "idle",
               "mode": TG_DEFAULT_MODE,
               "logged_in": has_session(d), "tasks_done": 0,
               "last_used": None, "last_account": None}
        if TG_DEFAULT_MODE == "mtproto":
            try:
                from mtproto_bot import session_file as _sf
                rec["session_file"] = _sf(tg_id)
                rec["logged_in"] = os.path.isfile(rec["session_file"])
            except Exception:
                rec["logged_in"] = False
        return rec

    def _load(self):
        if os.path.exists(TG_ACCOUNTS_JSON):
            try:
                return json.load(open(TG_ACCOUNTS_JSON, encoding="utf-8"))
            except Exception:
                return []
        if os.path.isdir(profile_dir("tg_1")):
            recs = [self._new_record("tg_1", "TG #1")]
            self._write(recs)
            return recs
        return []

    def _reload(self):
        """Re-read from disk (picks up accounts added by the dashboard)."""
        if os.path.exists(TG_ACCOUNTS_JSON):
            try:
                self.accounts = json.load(open(TG_ACCOUNTS_JSON, encoding="utf-8"))
            except Exception:
                pass

    def _write(self, recs):
        os.makedirs(os.path.dirname(TG_ACCOUNTS_JSON), exist_ok=True)
        json.dump(recs, open(TG_ACCOUNTS_JSON, "w", encoding="utf-8"), indent=2)

    def save(self):
        self._write(self.accounts)

    # -- queries --------------------------------------------------------
    def list(self, refresh=True):
        with self._cv:
            self._reload()
            if refresh:
                for a in self.accounts:
                    a["logged_in"] = session_ok(a)
            return [dict(a) for a in self.accounts]

    def idle(self):
        return [a for a in self.accounts
                if a.get("status") in ("idle", "available")
                and a.get("enabled") is not False
                and session_ok(a)]

    def idle_count(self):
        with self._cv:
            self._reload()
            return len(self.idle())

    def usable(self):
        """True when at least one profile is enabled AND holds a live session.

        Ignores lease status: a ``busy`` (but logged-in) profile is still a
        usable one for a waiting worker. Only when NO profile can ever be
        leased does the pipeline need to stop early — otherwise it would
        create a Meta account and only then discover the pool is dead.
        """
        with self._cv:
            self._reload()
            if is_frozen():
                return False
            return any(a.get("enabled") is not False
                       and session_ok(a)
                       for a in self.accounts)

    def stats(self):
        with self._cv:
            self._reload()
            for a in self.accounts:
                a["logged_in"] = session_ok(a)
            return {
                "total": len(self.accounts),
                "idle": len(self.idle()),
                "busy": sum(1 for a in self.accounts if a.get("status") == "busy"),
                "max": TG_MAX_ACCOUNTS,
                "accounts": [dict(a) for a in self.accounts],
            }

    # -- mutations ------------------------------------------------------
    def add(self, label=None):
        with self._cv:
            self._reload()
            if len(self.accounts) >= TG_MAX_ACCOUNTS:
                raise RuntimeError(f"max {TG_MAX_ACCOUNTS} Telegram accounts reached")
            used = {a["id"] for a in self.accounts}
            n = 1
            while f"tg_{n}" in used:
                n += 1
            rec = self._new_record(f"tg_{n}", label or f"TG #{n}")
            if record_mode(rec) != "mtproto":
                os.makedirs(rec["profile_dir"], exist_ok=True)
            self.accounts.append(rec)
            self.save()
            return rec

    def upsert_mtproto(self, tg_id, session_file, *, label=None, name=None,
                       phone=None, user_id=None, email=None, proxy=None):
        """Create/update a pool record for an MTProto (Telethon) session.

        Called by ``tg_login_mtproto.py`` after a successful login. The record
        shape stays identical to a web record — only ``mode``/``session_file``
        differ — so leasing, LRU rotation and enable/disable are shared.
        """
        with self._cv:
            self._reload()
            rec = next((a for a in self.accounts if a.get("id") == tg_id), None)
            if rec is None:
                rec = {"id": tg_id, "label": label or tg_id,
                       "profile_dir": profile_dir(tg_id), "status": "idle",
                       "tasks_done": 0, "last_used": None, "last_account": None,
                       "busy_bots": {}, "enabled": True}
                self.accounts.append(rec)
            rec["mode"] = "mtproto"
            rec["session_file"] = session_file
            rec["logged_in"] = os.path.isfile(session_file)
            if label:
                rec["label"] = label
            if name:
                rec["name"] = name
            if phone:
                rec["phone"] = phone
            if user_id is not None:
                rec["user_id"] = str(user_id)
            if email is not None:
                rec["email"] = email
            if proxy is not None:
                rec["proxy"] = proxy
            rec.setdefault("enabled", True)
            self.save()
            return dict(rec)

    def acquire(self, timeout=None, bot=None, only_id=None):
        """Lease an idle, logged-in account (marks it busy). Waits if needed.

        Reclaims ``busy`` leases older than ``LEASE_TTL`` (dead-worker safety);
        leases of unknown age are never auto-reclaimed (use Reset instead).
        Dashboard inspection holds (``lease_note`` ~ inspect, set by Scan QR /
        Open) are never leased and never reclaimed — two Chromiums on one
        profile dir corrupt both sessions.
        """
        with self._cv:
            end = None if timeout is None else time.time() + timeout
            while True:
                self._reload()
                # FROZEN: a sensitive op (withdraw) owns TG exclusively — refuse
                # to lease anything until it clears the freeze.
                if is_frozen():
                    return None
                # Pass 1 — reclaim stale/expired ``busy`` leases (dead-worker
                # safety) and never disturb a LIVE inspection hold.
                for a in self.accounts:
                    note = str(a.get("lease_note") or "").lower()
                    if a.get("status") == "busy":
                        if "inspect" in note:
                            # Live inspection windows must never be stolen, but
                            # a hold whose Chromium is gone is STALE (crashed or
                            # killed window) → reclaim it. Otherwise the profile
                            # is wedged forever: acquire() skips it and Reset
                            # can't free it (this wedged TG #2).
                            if not _profile_locked(a.get("profile_dir", "")):
                                a["status"] = "idle"
                                a["leased_at"] = None
                                a["lease_note"] = None
                                self.save()
                        else:
                            age = _lease_age(a)
                            # A PROBE lease is short by construction: the probe
                            # reads the hourly counter and releases (its own
                            # finally). But the orchestrator runs it via
                            # runPythonJson with a 30s cap and a SIGKILL on
                            # timeout — SIGKILL skips `finally`, so the lease is
                            # orphaned. Under the normal 20-min LEASE_TTL that
                            # wedges one TG account for 20 minutes after every
                            # slow probe, and acquire() silently skips it (this
                            # is the "not using all TG accounts" symptom). A
                            # probe never legitimately holds an account longer
                            # than its own timeout, so reclaim it on a short TTL.
                            is_probe = "probe" in str(a.get("busy_bot") or "").lower()
                            ttl = PROBE_LEASE_TTL if is_probe else LEASE_TTL
                            if is_probe and _owner_gone(a):
                                # Definitive: the probe process is GONE, so the
                                # lease can never be released by its owner.
                                # Reclaim immediately instead of waiting out the
                                # TTL — this is what left tg_2/tg_3 stuck "BUSY -
                                # PAYGO_PROBE" with no probe running at all.
                                a["status"] = "idle"
                                a["leased_at"] = None
                                a["lease_note"] = None
                                a["busy_bot"] = None
                                a.pop("probe_pid", None)
                            elif age is not None and age > ttl:
                                a["status"] = "idle"
                                a["leased_at"] = None
                                a["lease_note"] = None
                                a["busy_bot"] = None
                                a.pop("probe_pid", None)
                # Pass 2 — fair-share pick. The old loop returned the FIRST
                # eligible profile in fixed index order, so tg_1 absorbed the
                # bulk of every run (lifetime 94 / 52 / 23) while later
                # profiles starved. Rotate by least-recently-used instead:
                # every enabled, logged-in profile gets an equal share of
                # attempts, so lifetime counts converge. ``last_used`` is
                # stamped on release, so a profile that just finished (or just
                # failed) moves to the back rather than being hammered again.
                # ``id`` is only a deterministic tie-break (e.g. a fresh pool
                # where every last_used is None) — it must NOT be tasks_done,
                # which re-picks the same account whenever timestamps collide.
                eligible = []
                for a in self.accounts:
                    if ("inspect" in str(a.get("lease_note") or "").lower()
                            and _profile_locked(a.get("profile_dir", ""))):
                        continue
                    # Per-profile enable switch (dashboard): a disabled profile
                    # is never leased for task completion. Missing = enabled.
                    if a.get("enabled") is False:
                        continue
                    # Optional HARD PIN (manual ops / one-shot tests): restrict the
                    # lease to a single profile id. None = normal fair-share LRU.
                    if only_id is not None and str(a.get("id")) != str(only_id):
                        continue
                    # FLOOD-LIMITED accounts are not leasable. Telegram returns an
                    # absolute retry time, so a request inside that window cannot
                    # succeed — and hammering it risks EXTENDING the penalty.
                    # Without this check a 3–5h FloodWait (observed 2026-10-01)
                    # made every slot cycle through all 6 accounts every ~25s
                    # with zero possible submissions.
                    _fu = a.get("flood_until")
                    if _fu:
                        try:
                            if float(_fu) > time.time():
                                continue
                            a["flood_until"] = None      # expired -> clear
                        except (TypeError, ValueError):
                            a["flood_until"] = None
                    if (a.get("status") in ("idle", "available")
                            and session_ok(a)):
                        eligible.append(a)
                if eligible:
                    eligible.sort(key=lambda x: (
                        str(x.get("last_used") or ""),        # LRU first
                        str(x.get("id") or ""),                # deterministic tie-break
                    ))
                    a = eligible[0]
                    a["status"] = "busy"
                    a["leased_at"] = time.time()
                    a["busy_bot"] = (str(bot) if bot else None)
                    self.save()
                    return dict(a)
                if end is not None and time.time() >= end:
                    return None
                self._cv.wait(2)

    def release(self, tg_id, ok=True, account_id=None, count=True, bot_error=False):
        """Return an account to the pool and record what it produced.

        Only flags status="error" if bot_error is explicitly True (e.g. TG session lost or bot chat dead).
        Transient Instagram or task-level errors release back to "idle".
        Inspection holds are never touched (dashboard owns them).
        """
        with self._cv:
            self._reload()
            for a in self.accounts:
                if a.get("id") == tg_id:
                    if "inspect" in str(a.get("lease_note") or "").lower():
                        break
                    if not ok and bot_error:
                        a["status"] = "error"
                    else:
                        a["status"] = "idle"
                    a["leased_at"] = None
                    a.pop("busy_bot", None)
                    if ok and count:
                        a["tasks_done"] = int(a.get("tasks_done", 0)) + 1
                    if count:
                        a["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if account_id:
                        a["last_account"] = account_id
                    break
            self.save()
            self._cv.notify_all()

    def leased_ids(self):
        """Ids + session/profile keys currently leased to a live cycle.

        The warm bot pools (``PooledTelegramBot`` / ``MtprotoPooledBot``) must
        never reap or drop these owners: a long IG phase (2FA grind,
        scraping-warning recovery) holds no pool traffic for tens of minutes,
        so idle-time eviction would murder a LIVE lease mid-task (observed
        2026-09-24: mem-shed ``drop_all`` killed Slot #5's tg_5 owner at
        03:56, its 05:12 ``submit_2fa_key`` then died unpacking the shutdown
        sentinel). Returns every key shape the pools use: record ``id``,
        ``session_file`` and ``profile_dir``.
        """
        with self._cv:
            self._reload()
            keys = set()
            for a in self.accounts:
                if a.get("status") == "busy":
                    for k in (a.get("id"), a.get("session_file"),
                              a.get("profile_dir")):
                        if k:
                            keys.add(str(k))
                            try:
                                keys.add(os.path.basename(str(k)))
                            except Exception:
                                pass
            return keys

    def heartbeat(self, tg_id):
        """Refresh a live lease so LEASE_TTL never reclaims it mid-cycle.

        Long IG phases (90-min 2FA grind observed 2026-09-24) otherwise exceed
        the 20-min dead-worker reclaim and a second slot leases the SAME
        profile — two cycles then interleave commands on one pool owner and
        steal each other's replies. Best-effort; never raises.
        """
        try:
            with self._cv:
                self._reload()
                for a in self.accounts:
                    if a.get("id") == tg_id and a.get("status") == "busy":
                        a["leased_at"] = time.time()
                        self.save()
                        break
        except Exception:
            pass

    def disable(self, tg_id, reason=None):
        """Take a profile out of rotation without deleting it.

        Used when a lease turns out to hold a DEAD Telegram web session
        (``stel_web_auth`` gone / QR screen): mark ``enabled=False`` so
        ``acquire()``/``idle()`` skip it immediately (every acquire reloads
        from disk) and the pipeline keeps running on the remaining logged-in
        profiles. The profile dir and ledger record are preserved.

        Re-enable from the dashboard switch, or implicitly by opening a fresh
        ``tg_login.py`` window — ``release_inspect()`` clears the flag only for
        an auto-disable (one that carries ``disabled_reason``), never for a
        deliberate manual switch-off.
        """
        with self._cv:
            self._reload()
            updated = False
            for a in self.accounts:
                if a.get("id") == tg_id:
                    a["status"] = "idle"
                    a["enabled"] = False
                    a["logged_in"] = False
                    a["leased_at"] = None
                    a["lease_note"] = None
                    if reason:
                        a["disabled_reason"] = str(reason)[:300]
                    else:
                        a.pop("disabled_reason", None)
                    a["disabled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updated = True
                    break
            if updated:
                self.save()
                self._cv.notify_all()
            return updated

    def lease_inspect(self, tg_id, note="devtools-inspect"):
        """Hold a profile for dashboard inspection (Scan QR / Open).

        Workers skip it in acquire(); reset_all() preserves it. Returns the
        record, or None when already busy.
        """
        with self._cv:
            self._reload()
            for a in self.accounts:
                if a.get("id") == tg_id:
                    if a.get("status") == "busy":
                        return None
                    a["status"] = "busy"
                    a["leased_at"] = time.time()
                    a["lease_note"] = note or "devtools-inspect"
                    self.save()
                    self._cv.notify_all()
                    return dict(a)
            return None

    def release_inspect(self, tg_id):
        """Release a dashboard inspection hold. Never touches worker leases."""
        with self._cv:
            self._reload()
            updated = False
            for a in self.accounts:
                if a.get("id") == tg_id:
                    if "inspect" not in str(a.get("lease_note") or "").lower():
                        break
                    a["status"] = "idle"
                    a["leased_at"] = None
                    a["lease_note"] = None
                    a["logged_in"] = session_ok(a)
                    # A fresh logged-in window HEALS a session-loss auto-disable
                    # (the dynamic-disable path stamps `disabled_reason`). A
                    # deliberate manual switch-off has no reason and stays off.
                    if a["logged_in"] and a.get("disabled_reason"):
                        a["enabled"] = True
                        a.pop("disabled_reason", None)
                        a.pop("disabled_at", None)
                    updated = True
                    break
            if updated:
                self.save()
                self._cv.notify_all()
            return updated

    def reset_account(self, tg_id):
        """Reset a single Telegram profile from error/busy back to idle.

        Refuses only when a LIVE Chromium still holds the profile (an open
        dashboard inspection window) — two browsers on one dir corrupt both.
        A stale inspect hold (no live window) is cleared.
        """
        with self._cv:
            self._reload()
            updated = False
            for a in self.accounts:
                if a.get("id") == tg_id:
                    if (a.get("status") == "busy"
                            and "inspect" in str(a.get("lease_note") or "").lower()
                            and _profile_locked(a.get("profile_dir", ""))):
                        break
                    a["status"] = "idle"
                    a["leased_at"] = None
                    a["lease_note"] = None
                    a["logged_in"] = session_ok(a)
                    updated = True
                    break
            if updated:
                self.save()
                self._cv.notify_all()
            return updated

    def reset_all(self, preserve_notes=("devtools-inspect",)):
        """Reset Telegram profiles back to idle — except LIVE inspections.

        Engine start/stop used to wipe everything, stealing profiles with an
        open dashboard window → two browsers on one dir → blank profile on
        both sides. A preserved lease stays busy so workers wait instead — but
        only while its Chromium is actually alive; stale holds are reclaimed.
        """
        keep = set(preserve_notes or [])
        with self._cv:
            self._reload()
            for a in self.accounts:
                try:
                    notes = str(a.get("lease_note") or "")
                except Exception:
                    notes = ""
                if (a.get("status") == "busy" and any(k in notes for k in keep)
                        and _profile_locked(a.get("profile_dir", ""))):
                    continue
                a["status"] = "idle"
                a["leased_at"] = None
                a["lease_note"] = None
                a["busy_bot"] = None
                a["flood_until"] = None
                a.pop("probe_pid", None)
                a["logged_in"] = session_ok(a)
            self.save()
            self._cv.notify_all()
            return True

    def clear_flood(self, tg_id=None):
        """Clear the flood_until lockout for one or all profiles."""
        with self._cv:
            self._reload()
            changed = False
            for a in self.accounts:
                if tg_id is None or a.get("id") == tg_id:
                    if a.get("flood_until") is not None:
                        a["flood_until"] = None
                        changed = True
            if changed:
                self.save()
            self._cv.notify_all()
            return True

    def set_enabled(self, tg_id, enabled):
        """Flip the per-profile task switch.

        acquire() already skips ``enabled is False``, so a disabled profile is
        simply never leased — it stays logged in and keeps its session, it just
        stops receiving tasks. Refused while leased: disabling a profile mid-task
        would let acquire() hand the same profile to a second worker.
        """
        with self._cv:
            self._reload()
            rec = next((a for a in self.accounts if a.get("id") == tg_id), None)
            if rec is None:
                raise KeyError(f"unknown Telegram profile: {tg_id}")
            if rec.get("status") == "busy":
                raise RuntimeError(f"{tg_id} is busy (leased by a worker); stop the engine first")
            rec["enabled"] = bool(enabled)
            self.save()
            return rec.get("enabled")

    def update_profile(self, tg_id, name=None, phone=None):
        """Edit identifying fields (display name / phone number).

        Runtime state is untouched. Refused while leased, same as
        set_enabled/remove — mutating a busy profile mid-task would
        confuse the worker that leased it.
        """
        with self._cv:
            self._reload()
            rec = next((a for a in self.accounts if a.get("id") == tg_id), None)
            if rec is None:
                raise KeyError(f"unknown Telegram profile: {tg_id}")
            if rec.get("status") == "busy":
                raise RuntimeError(f"{tg_id} is busy (leased by a worker); stop the engine first")
            if name is not None:
                rec["name"] = str(name).strip()
            if phone is not None:
                rec["phone"] = str(phone).strip()
            self.save()
            return {"id": tg_id, "name": rec.get("name"), "phone": rec.get("phone")}

    def remove(self, tg_id):
        with self._cv:
            self._reload()
            rec = next((a for a in self.accounts if a.get("id") == tg_id), None)
            if rec is None:
                # Report honestly — silently "succeeding" on an unknown id made a
                # typo/typo'd API call look like a successful delete.
                raise KeyError(f"unknown Telegram profile: {tg_id}")
            if rec.get("status") == "busy":
                raise RuntimeError(f"{tg_id} is busy (leased by a worker); stop the engine first")
            self.accounts = [a for a in self.accounts if a.get("id") != tg_id]
            self.save()
            try:
                shutil.rmtree(profile_dir(tg_id), ignore_errors=True)
            except Exception:
                pass


# module-level singleton (shared by all worker threads)
tg_manager = TGAccountManager()
