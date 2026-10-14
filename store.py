"""
meta_auto_ai — thread-safe account store + pending queue (SQLite WAL Mode)
=========================================================================
High-performance account store backed by SQLite (data/store.db) in WAL mode.
Provides instant microsecond updates, atomic queue pops, non-blocking reads,
and automated export sync to accounts.json, accounts.csv, and accounts.txt.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_config import ACCOUNTS_CSV, ACCOUNTS_JSON, ACCOUNTS_TXT, AI_DIR, DATA_DIR, Urls  # noqa: E402
import db  # noqa: E402


# Which accounts a drain may take depends on the drain:
#   * cookie tasks need no mailbox -> every account with cookies (drain_ok = 1);
#   * 2FA tasks read the account's mailbox for the email code -> only accounts that saved a READABLE mailbox
#     (mailbox_ok). That is mail.td, tempmail.fish API, Yamin.bd, Guerrilla or Cloudflare; web-only ones are not.


def _has_readable_mailbox(extra) -> int:
    try:
        ex = json.loads(extra) if isinstance(extra, str) and extra.strip().startswith("{") else (
            extra if isinstance(extra, dict) else {})
        mt = ex.get("mail_tokens") or {}
        ok = (mt.get("mailfish_api") and mt.get("mailfish_email")
              or mt.get("mailfish_email") and mt.get("mailfish_auth_key")
              or mt.get("tempmail_token") and mt.get("tempmail_account_id")
              or mt.get("yamin_email") or mt.get("guerrilla_email")
              or mt.get("mailcf_email") and mt.get("mailcf_token"))
        return 1 if ok else 0
    except Exception:
        return 0


def _conn():
    """The shared connection, with the drain SQL functions registered on it.

    ``drain_ok(extra)`` is always 1 (cookie drain). ``mailbox_ok(extra)`` is 1 only for an account whose mailbox
    can still be read (2FA drain).
    """
    conn = db.get_connection()
    conn.create_function("drain_ok", 1, lambda extra: 1)
    conn.create_function("mailbox_ok", 1, _has_readable_mailbox)
    return conn

_lock = threading.Lock()

# A checkpoint-challenged rename is set aside for this long before it is retried
# (see mark_ig_creator_challenged). A per-account challenge usually clears once
# IG is satisfied; 30 min keeps the drain from churning the same accounts.
_CHALLENGE_RETRY_SEC = int(os.environ.get("INSTA_IG_CHALLENGE_RETRY_SEC", "1800") or 1800)
CLAIM_TIMEOUT = 600  # a Submitting claim older than this is considered stale
MAX_SUBMIT_ATTEMPTS = 3


def _read() -> List[Dict[str, Any]]:
    """Legacy helper: return all accounts as a list of dictionaries (newest first)."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY created_at DESC, rowid DESC")
    return [db.dict_from_row(r) for r in cur.fetchall()]


def _write(recs: List[Dict[str, Any]]) -> None:
    """Legacy helper: write all accounts to SQLite and sync JSON/CSV/TXT."""
    conn = _conn()
    with _lock:
        with conn:
            conn.execute("DELETE FROM accounts")
            for r in recs:
                row = db.row_from_dict(r)
                cols = ", ".join(db.COLUMNS)
                placeholders = ", ".join("?" for _ in db.COLUMNS)
                conn.execute(
                    f"INSERT INTO accounts ({cols}) VALUES ({placeholders})",
                    [row.get(c) for c in db.COLUMNS]
                )
    sync_files()


def add(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new account record (creators)."""
    rec.setdefault("target", "Meta")
    rec.setdefault("status", "Created")
    if not rec.get("id"):
        rec["id"] = f"ai_{int(time.time() * 1000)}_{os.getpid()}"
    if "created_at" not in rec:
        rec["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    conn = _conn()
    row = db.row_from_dict(rec)
    cols = ", ".join(db.COLUMNS)
    placeholders = ", ".join("?" for _ in db.COLUMNS)

    with _lock:
        with conn:
            conn.execute(
                f"INSERT OR REPLACE INTO accounts ({cols}) VALUES ({placeholders})",
                [row.get(c) for c in db.COLUMNS]
            )
        sync_files()
    return rec


def list_all() -> List[Dict[str, Any]]:
    """Retrieve all accounts (newest first)."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY created_at DESC, rowid DESC")
    return [db.dict_from_row(r) for r in cur.fetchall()]


get_accounts = list_all  # alias for backwards compatibility


def get(rec_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single record by its id."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
    row = cur.fetchone()
    return db.dict_from_row(row) if row else None


def counts() -> Dict[str, Any]:
    """Return fast aggregated account statistics in a single query."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Created' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status IN ('Submitting', 'Submitting_Nitro') THEN 1 ELSE 0 END) as submitting,
            SUM(CASE WHEN status IN ('Submitted', 'Submitted_Nitro') THEN 1 ELSE 0 END) as submitted,
            SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN target = 'telegram' THEN 1 ELSE 0 END) as tg_total,
            SUM(CASE WHEN target = 'telegram' AND status = 'Created' AND tg_submitted = 0 THEN 1 ELSE 0 END) as tg_pending,
            SUM(CASE WHEN target = 'telegram' AND status = 'Submitting' THEN 1 ELSE 0 END) as tg_submitting,
            SUM(CASE WHEN target = 'telegram' AND (status = 'Submitted' OR tg_submitted = 1) THEN 1 ELSE 0 END) as tg_submitted,
            SUM(CASE WHEN target = 'telegram' AND status = 'Failed' THEN 1 ELSE 0 END) as tg_failed,
            SUM(CASE WHEN target = 'nitro' THEN 1 ELSE 0 END) as nitro_total,
            SUM(CASE WHEN target = 'nitro' AND status = 'Created' AND nitro_submitted = 0 THEN 1 ELSE 0 END) as nitro_pending,
            SUM(CASE WHEN target = 'nitro' AND status = 'Submitting_Nitro' THEN 1 ELSE 0 END) as nitro_submitting,
            SUM(CASE WHEN target = 'nitro' AND (status = 'Submitted_Nitro' OR nitro_submitted = 1) THEN 1 ELSE 0 END) as nitro_submitted,
            SUM(CASE WHEN target = 'nitro' AND status = 'Submitted_Nitro' THEN 1 ELSE 0 END) as nitro_active,
            SUM(CASE WHEN target = 'nitro' AND status = 'Needs_Rest' THEN 1 ELSE 0 END) as nitro_resting,
            SUM(CASE WHEN target = 'nitro' AND status = 'Failed' THEN 1 ELSE 0 END) as nitro_failed,
            SUM(CASE WHEN target = 'coinsta' THEN 1 ELSE 0 END) as coinsta_total,
            SUM(CASE WHEN target = 'coinsta' AND status IN ('Created', 'MetaCreated') AND coinsta_submitted = 0 THEN 1 ELSE 0 END) as coinsta_pending,
            SUM(CASE WHEN target = 'coinsta' AND status = 'Submitting_Coinsta' THEN 1 ELSE 0 END) as coinsta_submitting,
            SUM(CASE WHEN target = 'coinsta' AND (status = 'Submitted_Coinsta' OR coinsta_submitted = 1) THEN 1 ELSE 0 END) as coinsta_submitted,
            SUM(CASE WHEN target = 'coinsta' AND status = 'Needs_Rest' THEN 1 ELSE 0 END) as coinsta_resting,
            SUM(CASE WHEN target = 'coinsta' AND status = 'Failed' THEN 1 ELSE 0 END) as coinsta_failed
        FROM accounts
    """)
    r = cur.fetchone()
    if not r:
        return {"total": 0, "pending": 0, "submitting": 0, "submitted": 0, "failed": 0,
                "telegram": {"total": 0, "pending": 0, "submitting": 0, "submitted": 0, "failed": 0},
                "nitro": {"total": 0, "pending": 0, "submitting": 0, "submitted": 0, "active": 0, "resting": 0, "failed": 0},
                "coinsta": {"total": 0, "pending": 0, "submitting": 0, "submitted": 0, "active": 0, "resting": 0, "failed": 0}}

    return {
        "total": r["total"] or 0,
        "pending": r["pending"] or 0,
        "submitting": r["submitting"] or 0,
        "submitted": r["submitted"] or 0,
        "failed": r["failed"] or 0,
        "telegram": {
            "total": r["tg_total"] or 0,
            "pending": r["tg_pending"] or 0,
            "submitting": r["tg_submitting"] or 0,
            "submitted": r["tg_submitted"] or 0,
            "failed": r["tg_failed"] or 0,
        },
        "nitro": {
            "total": r["nitro_total"] or 0,
            "pending": r["nitro_pending"] or 0,
            "submitting": r["nitro_submitting"] or 0,
            "submitted": r["nitro_submitted"] or 0,
            "active": r["nitro_active"] or 0,
            "resting": r["nitro_resting"] or 0,
            "failed": r["nitro_failed"] or 0,
        },
        "coinsta": {
            "total": r["coinsta_total"] or 0,
            "pending": r["coinsta_pending"] or 0,
            "submitting": r["coinsta_submitting"] or 0,
            "submitted": r["coinsta_submitted"] or 0,
            "active": r["coinsta_submitted"] or 0,
            "resting": r["coinsta_resting"] or 0,
            "failed": r["coinsta_failed"] or 0,
        },
    }


def pending_count() -> int:
    """Return count of unsubmitted Telegram accounts ready for claiming."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM accounts WHERE target = 'telegram' AND status = 'Created' AND tg_submitted = 0")
    row = cur.fetchone()
    return row[0] if row else 0


def pop_pending(destination: str = "telegram") -> Optional[Dict[str, Any]]:
    """Atomically claim the oldest submittable pending account for the specified pipeline."""
    conn = _conn()
    now = time.time()

    with _lock:
        with conn:
            if destination == "nitro":
                # Prioritize accounts with active 2FA secret (solves in 0.5s via TOTP; bypasses Email OTP)
                cur = conn.execute(
                    """
                    SELECT id FROM accounts
                    WHERE target = 'nitro' AND status = 'Created' AND nitro_submitted = 0
                      AND twofa_secret IS NOT NULL AND twofa_secret != ''
                    ORDER BY rowid ASC LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    cur = conn.execute(
                        """
                        SELECT id FROM accounts
                        WHERE target = 'nitro' AND status = 'Created' AND nitro_submitted = 0
                        ORDER BY rowid ASC LIMIT 1
                        """
                    )
                    row = cur.fetchone()

                if row:
                    rec_id = row[0]
                    conn.execute(
                        "UPDATE accounts SET status = 'Submitting_Nitro', claimed_at = ? WHERE id = ?",
                        (now, rec_id)
                    )
                    cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
                    res = db.dict_from_row(cur.fetchone())
                    sync_files()
                    return res
                return None
            elif destination == "coinsta":
                # Coinsta pipeline: prefer records that still hold a usable IG
                # session (the cookie modal needs sessionid + ds_user_id).
                cur = conn.execute(
                    """
                    SELECT id FROM accounts
                    WHERE target = 'coinsta' AND status IN ('Created', 'MetaCreated') AND coinsta_submitted = 0
                    ORDER BY rowid ASC LIMIT 1
                    """
                )
                row = cur.fetchone()
                if row:
                    rec_id = row[0]
                    conn.execute(
                        "UPDATE accounts SET status = 'Submitting_Coinsta', claimed_at = ? WHERE id = ?",
                        (now, rec_id)
                    )
                    cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
                    res = db.dict_from_row(cur.fetchone())
                    sync_files()
                    return res
                return None
            else:
                # Telegram pipeline
                cur = conn.execute(
                    """
                    SELECT id FROM accounts
                    WHERE target = 'telegram' AND status = 'Created' AND tg_submitted = 0
                    ORDER BY rowid ASC LIMIT 1
                    """
                )
                row = cur.fetchone()
                if row:
                    rec_id = row[0]
                    conn.execute(
                        "UPDATE accounts SET status = 'Submitting', claimed_at = ? WHERE id = ?",
                        (now, rec_id)
                    )
                    cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
                    res = db.dict_from_row(cur.fetchone())
                    sync_files()
                    return res
                return None


def count_ig_creator_accounts(need_mail: bool = False) -> int:
    """Return count of available IG creator accounts with cookies in the pool.

    Applies the SAME filters as ``pop_ig_creator_account`` — including the
    rename-challenge set-aside — so the two never disagree. (They did: the count
    reported "445 available" while pop returned none because every account was
    challenge-stamped, which made the drain log a false pool size and churn.)
    """
    conn = _conn()
    _challenge_cutoff = time.time() - _CHALLENGE_RETRY_SEC
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM accounts
        WHERE platform = 'Meta+Instagram'
          AND cookies IS NOT NULL AND cookies != ''
          AND (status = 'Created' OR status IS NULL)
          AND (challenged_at IS NULL OR challenged_at < ?)
          AND {_mail_clause}
        """.format(_mail_clause=_MAIL_CLAUSE_2FA if need_mail else _MAIL_CLAUSE_COOKIE),
        (_challenge_cutoff,)
    )
    row = cur.fetchone()
    return row[0] if row else 0


def ig_pool_breakdown() -> Dict[str, int]:
    """Why the drainable pool is smaller than the number of accounts created. Same rules as
    ``count_ig_creator_accounts`` / ``pop_ig_creator_account``, split by the reason an account is skipped:
    ``no_mailbox`` = no readable mailbox saved (the 2FA drain cannot read its email code; cookie drain still can),
    ``in_use_or_done`` = status is not Created (claimed by a running slot, submitted, dead),
    ``challenged`` = set aside after a rename challenge, ``no_cookies`` = nothing to log in with."""
    conn = _conn()
    cutoff = time.time() - _CHALLENGE_RETRY_SEC
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*),
          SUM(CASE WHEN cookies IS NULL OR cookies = '' THEN 1 ELSE 0 END),
          SUM(CASE WHEN cookies != '' AND NOT (status = 'Created' OR status IS NULL) THEN 1 ELSE 0 END),
          SUM(CASE WHEN cookies != '' AND (status = 'Created' OR status IS NULL)
                    AND challenged_at IS NOT NULL AND challenged_at >= ? THEN 1 ELSE 0 END),
          SUM(CASE WHEN cookies != '' AND (status = 'Created' OR status IS NULL)
                    AND (challenged_at IS NULL OR challenged_at < ?) AND mailbox_ok(extra) = 0 THEN 1 ELSE 0 END),
          SUM(CASE WHEN cookies != '' AND (status = 'Created' OR status IS NULL)
                    AND (challenged_at IS NULL OR challenged_at < ?) AND mailbox_ok(extra) = 1 THEN 1 ELSE 0 END)
        FROM accounts WHERE platform = 'Meta+Instagram'
        """,
        (cutoff, cutoff, cutoff),
    )
    r = [int(x or 0) for x in (cur.fetchone() or (0,) * 6)]
    return {"total": r[0], "no_cookies": r[1], "in_use_or_done": r[2], "challenged": r[3],
            "no_mailbox": r[4], "usable": r[5]}


# 1 when the account already carries the 5 mandatory follows. `followed` is a real column; the extra-JSON
# value is only a fallback for rows written before the column existed (the CASE guards invalid/NULL JSON).
_FOLLOW5_SQL = ("(CASE WHEN COALESCE(followed, 0) >= 5 THEN 1 WHEN json_valid(extra) AND "
                "CAST(COALESCE(json_extract(extra, '$.followed'), 0) AS INTEGER) >= 5 THEN 1 ELSE 0 END)")


_MAIL_CLAUSE_COOKIE = "drain_ok(extra) = 1"
_MAIL_CLAUSE_2FA = "mailbox_ok(extra) = 1"


def pop_ig_creator_account(prefer_non_follow5: bool = False, prefer_follow5: bool = False,
                           need_mail: bool = False) -> Optional[Dict[str, Any]]:
    """Atomically claim the freshest IG creator account with valid cookies from the pool.

    ``prefer_non_follow5``: accounts that already carry the 5 cookie-mandate
    follows are reserved for the cookie tasks. With this flag they are taken
    only when no other account is left in the pool.
    ``prefer_follow5``: the opposite — the cookie tasks take the accounts that
    already have the 5 follows first (no follow step needed), then the rest.
    Neither flag excludes anything: the other group is still claimed when the preferred one is empty.
    ``need_mail``: the 2FA drains only take accounts whose mailbox can still be read (see mailbox_ok).
    """
    # Self-heal FIRST: reclaim claims abandoned by an abruptly-killed cycle so an
    # engine stop never permanently removes accounts from the pool. Cheap; the
    # lock is taken inside recover_stale_submitting (not held here).
    try:
        recover_stale_submitting()
    except Exception:
        pass
    conn = _conn()
    now = time.time()
    _challenge_cutoff = now - _CHALLENGE_RETRY_SEC
    # 5-follow accounts sort last only when asked; json_valid guards 'Dead: ...' extras.
    # An account claimed in the last 60 s and put back with rotate=True (it failed a rename/submit) goes to
    # the BACK: with the freshest-first order it was re-picked at once, ~10x per second, hammering IG with
    # the same failing rename (observed 2026-10-12 23:06: 11 renames in 8 s on one account).
    _recent = "CASE WHEN claimed_at IS NOT NULL AND claimed_at > {cut} THEN 1 ELSE 0 END ASC, ".format(cut=now - 60)
    if prefer_follow5 and not prefer_non_follow5:
        _order = _recent + _FOLLOW5_SQL + " DESC, created_at DESC, rowid DESC"
    elif prefer_non_follow5 and not prefer_follow5:
        _order = _recent + _FOLLOW5_SQL + " ASC, created_at DESC, rowid DESC"
    else:
        _order = _recent + "created_at DESC, rowid DESC"
    with _lock:
        with conn:
            cur = conn.execute(
                """
                SELECT id FROM accounts
                WHERE platform = 'Meta+Instagram'
                  AND cookies IS NOT NULL AND cookies != ''
                  AND (status = 'Created' OR status IS NULL)
                  AND (challenged_at IS NULL OR challenged_at < ?)
          AND {_mail_clause}
                -- FRESHEST FIRST. The IG Creator's accounts are only viable for
                -- ~1h before IG suspends them, so the drain must consume the
                -- NEWEST ones while they are still alive. Ordering by claimed_at
                -- (least-recently-claimed) made it walk the OLDEST first — i.e.
                -- straight into accounts that were already suspended (observed
                -- 2026-10-08: a whole run purging dead accounts while fresh live
                -- ones sat untouched at the back). Recently-challenged accounts
                -- are already excluded by challenged_at, and locked ones are
                -- purged, so newest-first cannot tight-loop.
                ORDER BY {_order} LIMIT 1
                """.format(_order=_order, _mail_clause=_MAIL_CLAUSE_2FA if need_mail else _MAIL_CLAUSE_COOKIE),
                (_challenge_cutoff,)
            )
            row = cur.fetchone()
            if not row:
                return None
            rec_id = row[0]
            conn.execute(
                "UPDATE accounts SET status = 'Submitting_PayGo', claimed_at = ? WHERE id = ?",
                (now, rec_id)
            )
            cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
            res = db.dict_from_row(cur.fetchone())
            sync_files()
            return res


_META_LIST_WHERE = """
        platform = 'Meta'
        AND status = 'MetaCreated'
        AND email IS NOT NULL AND email != ''
        AND (COALESCE(NULLIF(meta_password, ''), NULLIF(password, '')) IS NOT NULL)
        AND (challenged_at IS NULL OR challenged_at < ?)
          AND drain_ok(extra) = 1
"""


def count_meta_list_accounts() -> int:
    """Meta Creator accounts (no IG session yet) that the Meta-list source can drain.

    Same challenge set-aside as the IG pool, so count and pop never disagree.
    """
    conn = _conn()
    cutoff = time.time() - _CHALLENGE_RETRY_SEC
    cur = conn.execute(f"SELECT COUNT(*) FROM accounts WHERE {_META_LIST_WHERE}", (cutoff,))
    row = cur.fetchone()
    return row[0] if row else 0


def pop_meta_list_account() -> Optional[Dict[str, Any]]:
    """Atomically claim the OLDEST usable Meta-list account.

    Oldest first (opposite of the IG pool): a Meta account is not time-limited
    by an IG suspension clock — it has no IG profile yet — so FIFO keeps the
    list draining evenly. Claims as ``Submitting_MetaCookie`` so a killed cycle
    is reclaimed by ``recover_stale_submitting`` back to ``MetaCreated``.
    """
    try:
        recover_stale_submitting()
    except Exception:
        pass
    conn = _conn()
    now = time.time()
    with _lock:
        with conn:
            cur = conn.execute(
                f"SELECT id FROM accounts WHERE {_META_LIST_WHERE} "
                "ORDER BY created_at ASC, rowid ASC LIMIT 1",
                (now - _CHALLENGE_RETRY_SEC,)
            )
            row = cur.fetchone()
            if not row:
                return None
            rec_id = row[0]
            conn.execute(
                "UPDATE accounts SET status = 'Submitting_MetaCookie', claimed_at = ? WHERE id = ?",
                (now, rec_id)
            )
            cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
            res = db.dict_from_row(cur.fetchone())
        sync_files()
        return res


def mark_meta_list_challenged(rec_id: str) -> None:
    """Set a Meta-list account aside after an IG login challenge (NOT a purge).

    Back to ``MetaCreated`` but stamped ``challenged_at`` so the pop skips it
    for ``INSTA_IG_CHALLENGE_RETRY_SEC`` — the account is not dead, IG just
    wants more than a password from this fresh device.
    """
    conn = _conn()
    now = time.time()
    with _lock:
        with conn:
            row = conn.execute("SELECT attempts FROM accounts WHERE id = ?", (rec_id,)).fetchone()
            attempts = int((row[0] if row else 0) or 0) + 1
            # Bounded: an account that keeps failing at IG login stops being
            # offered (same cap as stale claims) instead of looping forever.
            status = "Failed" if attempts >= MAX_SUBMIT_ATTEMPTS else "MetaCreated"
            conn.execute(
                "UPDATE accounts SET status = ?, attempts = ?, claimed_at = ?, challenged_at = ? WHERE id = ?",
                (status, attempts, now, now, rec_id)
            )
        sync_files()


def restore_ig_creator_account(rec_id: str, rotate: bool = False) -> None:
    """Restore an account's status to 'Created' if drain cycle was aborted.

    ``rotate=True`` KEEPS the account's ``claimed_at`` stamp so it sorts to the
    BACK of the pop queue. Use it when the account failed a rename/submit so the
    next pop picks a DIFFERENT account (a tight re-pick loop is what made IG
    return ``{"spam":true}`` on every username change).
    """
    conn = _conn()
    with _lock:
        with conn:
            # A Meta-LIST account (platform 'Meta', no IG session yet) must go
            # back to 'MetaCreated' — 'Created' would drop it out of the Meta
            # list pool (pop_meta_list_account filters on MetaCreated).
            if rotate:
                conn.execute(
                    "UPDATE accounts SET status = CASE WHEN platform = 'Meta' "
                    "THEN 'MetaCreated' ELSE 'Created' END WHERE id = ?",
                    (rec_id,)
                )
            else:
                conn.execute(
                    "UPDATE accounts SET status = CASE WHEN platform = 'Meta' "
                    "THEN 'MetaCreated' ELSE 'Created' END, claimed_at = NULL WHERE id = ?",
                    (rec_id,)
                )
        sync_files()


def peek_pool_accounts(limit: int = 6) -> list:
    """Return up to ``limit`` NEWEST pooled IG accounts WITHOUT claiming them.

    Read-only — for the pre-flight health probe (never mutates status).
    """
    conn = _conn()
    cutoff = time.time() - _CHALLENGE_RETRY_SEC
    cur = conn.execute(
        """
        SELECT * FROM accounts
        WHERE platform = 'Meta+Instagram'
          AND cookies IS NOT NULL AND cookies != ''
          AND (status = 'Created' OR status IS NULL)
          AND (challenged_at IS NULL OR challenged_at < ?)
          AND drain_ok(extra) = 1
        ORDER BY created_at DESC, rowid DESC LIMIT ?
        """,
        (cutoff, int(limit)),
    )
    return [db.dict_from_row(r) for r in cur.fetchall()]


def purge_dead_sessions() -> int:
    """Delete pooled IG accounts whose stored cookie has NO ``sessionid``.

    A suspended/invalidated IG session loses its ``sessionid`` (``ds_user_id``,
    ``mid``, ``datr`` … survive). Such an account can never log in — the browser
    follow then fails with "no IG sessionid after follow". Purging them up front
    is INSTANT (a DB-only test, no network, no TG lease, no bot Start) and stops
    the drain from burning a whole bot task on an account that is already dead.

    Returns the number of rows deleted.
    """
    conn = _conn()
    n = 0
    with _lock:
        with conn:
            cur = conn.execute(
                """
                DELETE FROM accounts
                WHERE platform = 'Meta+Instagram'
                  AND (status = 'Created' OR status IS NULL)
                  AND (cookies IS NULL OR cookies = '' OR cookies NOT LIKE '%sessionid=%')
                """
            )
            n = cur.rowcount or 0
        if n:
            sync_files()
    return n


def mark_ig_creator_challenged(rec_id: str) -> None:
    """Set a rename-CHALLENGED account aside WITHOUT purging it.

    A ``checkpoint_required`` rename is a PER-ACCOUNT challenge (proven: renames
    on other accounts succeed in the same run), not death. The account is
    restored to the pool but stamped ``challenged_at`` so
    ``pop_ig_creator_account`` skips it for ``INSTA_IG_CHALLENGE_RETRY_SEC``.
    Without the stamp the drain churns the entire pool in one pass, re-trying
    accounts IG is already challenging.
    """
    conn = _conn()
    now = time.time()
    with _lock:
        with conn:
            conn.execute(
                "UPDATE accounts SET status = 'Created', claimed_at = ?, challenged_at = ? WHERE id = ?",
                (now, now, rec_id)
            )
        sync_files()


def mark_ig_creator_dead(rec_id: str, reason: str = "checkpoint_required") -> None:
    """Permanently mark a dead/suspended account so it is never picked again.

    Preserves any existing ``extra`` payload (notably ``mail_tokens``) by
    merging the dead marker into it instead of overwriting the column — a
    plain ``UPDATE extra='Dead: …'`` wiped the mail session JSON, so a later
    full backup of the flagged row lost its inbox. ``is_damaged`` readers
    accept both the legacy ``'Dead: …'`` string and the merged dict form.
    """
    conn = _conn()
    with _lock:
        with conn:
            cur = conn.execute("SELECT extra FROM accounts WHERE id = ?", (rec_id,))
            row = cur.fetchone()
            merged: Dict[str, Any] = {}
            if row and row[0]:
                try:
                    obj = json.loads(row[0])
                    if isinstance(obj, dict):
                        merged = obj
                except Exception:
                    if str(row[0]).startswith("Dead:"):
                        merged = {"dead_reason": str(row[0])[len("Dead:"):].strip()}
            merged["dead_reason"] = reason
            conn.execute(
                "UPDATE accounts SET status = 'Failed', extra = ? WHERE id = ?",
                (json.dumps(merged), rec_id)
            )
        sync_files()


def claim_specific(rec_id: str) -> Optional[Dict[str, Any]]:
    """Atomically claim ONE Created telegram account by id for immediate submit.

    Coupled-loop path: the worker just created this account and submits it in
    the same breath (fresh session, no queue aging). Returns None unless the
    record is still submittable (Created, not yet submitted).
    """
    conn = _conn()
    now = time.time()
    with _lock:
        with conn:
            cur = conn.execute(
                """
                SELECT * FROM accounts
                WHERE id = ? AND target = 'telegram' AND status = 'Created'
                  AND tg_submitted = 0 LIMIT 1
                """,
                (rec_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE accounts SET status = 'Submitting', claimed_at = ? WHERE id = ?",
                (now, rec_id)
            )
            cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
            res = db.dict_from_row(cur.fetchone())
            sync_files()
            return res


def finish_submit(rec_id: str, ok: bool, tg_id: Optional[str] = None, code: Optional[str] = None,
                  tg_creds: Optional[Dict[str, Any]] = None, twofa_secret: Optional[str] = None,
                  updated_username: Optional[str] = None, updated_password: Optional[str] = None,
                  updated_name: Optional[str] = None, tg_bot: Optional[str] = None) -> None:
    """Mark a claimed account Submitted (or revert to Created on failure)."""
    conn = _conn()
    with _lock:
        with conn:
            cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
            row = cur.fetchone()
            if not row:
                return
            rec = db.dict_from_row(row)

            if ok:
                updates: Dict[str, Any] = {
                    "status": "Submitted",
                    "tg_submitted": 1,
                    "claimed_at": None,
                    "attempts": 0,
                }
                if tg_id:
                    updates["tg_account"] = tg_id
                if tg_bot:
                    updates["tg_bot"] = tg_bot
                if code:
                    updates["tg_one_time_code"] = code
                if tg_creds:
                    updates["tg_login"] = tg_creds.get("login", "")
                    updates["tg_password"] = tg_creds.get("password", "")
                    if tg_creds.get("first_name"):
                        updates["name"] = tg_creds["first_name"]
                if updated_name:
                    updates["name"] = updated_name
                if updated_username:
                    updates["username"] = updated_username
                    updates["instagram_username"] = updated_username
                if updated_password:
                    updates["password"] = updated_password
                    updates["meta_password"] = updated_password
                if twofa_secret:
                    updates["twofa_secret"] = twofa_secret

                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                conn.execute(f"UPDATE accounts SET {set_clause} WHERE id = ?", (*updates.values(), rec_id))
            else:
                attempts = int(rec.get("attempts") or 0) + 1
                new_status = "Failed" if attempts >= MAX_SUBMIT_ATTEMPTS else "Created"
                conn.execute(
                    "UPDATE accounts SET status = ?, attempts = ?, claimed_at = NULL WHERE id = ?",
                    (new_status, attempts, rec_id)
                )
        sync_files()


def finish_nitro_submit(rec_id: str, ok: bool, device_serial: Optional[str] = None, message: Optional[str] = None) -> None:
    """Mark an account as Submitted to Nitro Follower."""
    conn = _conn()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    with _lock:
        with conn:
            cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
            row = cur.fetchone()
            if not row:
                return
            rec = db.dict_from_row(row)

            if ok:
                conn.execute(
                    """
                    UPDATE accounts
                    SET status = 'Submitted_Nitro', nitro_submitted = 1,
                        nitro_device = ?, nitro_submitted_at = ?, claimed_at = NULL, attempts = 0
                    WHERE id = ?
                    """,
                    (device_serial or "", now_str, rec_id)
                )
            else:
                attempts = int(rec.get("attempts") or 0) + 1
                new_status = "Failed" if attempts >= MAX_SUBMIT_ATTEMPTS else "Created"
                conn.execute(
                    "UPDATE accounts SET status = ?, attempts = ?, claimed_at = NULL WHERE id = ?",
                    (new_status, attempts, rec_id)
                )
        sync_files()


def finish_coinsta_submit(rec_id: str, ok: bool, device_serial: Optional[str] = None, message: Optional[str] = None) -> None:
    """Mark an account as ingested into Coinsta (cookie session live on a device)."""
    conn = _conn()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    with _lock:
        with conn:
            cur = conn.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
            row = cur.fetchone()
            if not row:
                return
            rec = db.dict_from_row(row)

            if ok:
                conn.execute(
                    """
                    UPDATE accounts
                    SET status = 'Submitted_Coinsta', coinsta_submitted = 1,
                        coinsta_device = ?, coinsta_submitted_at = ?, claimed_at = NULL, attempts = 0
                    WHERE id = ?
                    """,
                    (device_serial or "", now_str, rec_id)
                )
            else:
                attempts = int(rec.get("attempts") or 0) + 1
                new_status = "Failed" if attempts >= MAX_SUBMIT_ATTEMPTS else "Created"
                conn.execute(
                    "UPDATE accounts SET status = ?, attempts = ?, claimed_at = NULL WHERE id = ?",
                    (new_status, attempts, rec_id)
                )
        sync_files()


def mark_submitted(rec_id: str, tg_id: Optional[str] = None, code: Optional[str] = None,
                   tg_creds: Optional[Dict[str, Any]] = None, twofa_secret: Optional[str] = None,
                   updated_username: Optional[str] = None, updated_password: Optional[str] = None) -> None:
    """Convenience alias for finish_submit(rec_id, True, ...)."""
    finish_submit(rec_id, True, tg_id=tg_id, code=code, tg_creds=tg_creds,
                  twofa_secret=twofa_secret, updated_username=updated_username,
                  updated_password=updated_password)


def is_account_unused(r: Dict[str, Any]) -> bool:
    """Return True if account has not been used or submitted to either pipeline."""
    if r.get("tg_submitted") or r.get("nitro_submitted") or r.get("coinsta_submitted"):
        return False
    return r.get("status") == "Created"

def recover_stale_submitting(timeout: float = CLAIM_TIMEOUT) -> int:
    """Reset records stuck in 'Submitting*' back to 'Created'.

    Matches EVERY ``Submitting`` status prefix, not just the three hard-coded
    ones. ``pop_ig_creator_account`` claims with ``Submitting_PayGo`` (and other
    targets use their own suffixes); because that name was missing here, a pool
    account whose cycle was killed abruptly (engine stop / crash — the handler
    that would restore it never runs) stayed ``Submitting_PayGo`` FOREVER: not in
    the pool, not consumed — a permanent leak (47 such records observed live
    2026-10-03). A ``LIKE 'Submitting%'`` sweep cannot be forgotten again when a
    new target is added.
    """
    now = time.time()
    conn = _conn()
    with _lock:
        with conn:
            cur = conn.execute(
                """
                SELECT id, attempts, platform FROM accounts
                WHERE status LIKE 'Submitting%'
                  AND (claimed_at IS NULL OR (? - claimed_at) > ?)
                """,
                (now, timeout)
            )
            stale = cur.fetchall()
            if not stale:
                return 0

            for rec_id, attempts, _plat in stale:
                new_attempts = int(attempts or 0) + 1
                _back = "MetaCreated" if _plat == "Meta" else "Created"
                new_status = "Failed" if new_attempts >= MAX_SUBMIT_ATTEMPTS else _back
                conn.execute(
                    "UPDATE accounts SET status = ?, attempts = ?, claimed_at = NULL WHERE id = ?",
                    (new_status, new_attempts, rec_id)
                )
        sync_files()
        return len(stale)


def prune_submitted_data(ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Free disk for SUBMITTED accounts without losing the ledger record.

    A submitted account is done — its heavy artifacts (Playwright profile dir,
    session file, cookie export) are never needed again. We KEEP the record in
    accounts.json/.csv/accounts.txt (so the table, stats and history survive)
    and delete only the on-disk data, blanking the paths.

    `ids=None` prunes EVERY submitted record; pass a list to prune specific ones.
    Returns {"profiles", "sessions", "cookies", "records"}.
    """
    import shutil as _shutil

    def _is_submitted(r: Dict[str, Any]) -> bool:
        return bool(r.get("tg_submitted") or r.get("nitro_submitted")) \
            or str(r.get("status") or "") == "Submitted"

    conn = _conn()
    removed = {"profiles": 0, "sessions": 0, "cookies": 0, "records": 0}
    with _lock:
        cur = conn.execute("SELECT id, profile_dir, session_file FROM accounts")
        rows = cur.fetchall()
        want = set(ids) if ids else None
        for rid, profile_dir, session_file in rows:
            if want is not None and rid not in want:
                continue
            row = conn.execute(
                "SELECT tg_submitted, nitro_submitted, status FROM accounts WHERE id = ?", (rid,)
            ).fetchone()
            if not row:
                continue
            rec = {"tg_submitted": row[0], "nitro_submitted": row[1], "status": row[2]}
            if not _is_submitted(rec):
                continue
            if profile_dir and os.path.isdir(profile_dir) \
                    and os.path.abspath(profile_dir).startswith(os.path.abspath(DATA_DIR)):
                try:
                    _shutil.rmtree(profile_dir, ignore_errors=True)
                    removed["profiles"] += 1
                except Exception:
                    pass
            if session_file and os.path.isfile(session_file):
                try:
                    os.remove(session_file)
                    removed["sessions"] += 1
                except Exception:
                    pass
            ck = os.path.join(AI_DIR, "cookies", f"cookies_{rid}.txt")
            if os.path.isfile(ck):
                try:
                    os.remove(ck)
                    removed["cookies"] += 1
                except Exception:
                    pass
            with conn:
                conn.execute(
                    "UPDATE accounts SET profile_dir = NULL, session_file = NULL WHERE id = ?", (rid,))
            removed["records"] += 1
        sync_files()
    return removed


def clear_completed() -> int:
    """Remove already submitted accounts to keep queue clean."""
    conn = _conn()
    with _lock:
        with conn:
            cur = conn.execute("DELETE FROM accounts WHERE status = 'Submitted' OR tg_submitted = 1")
            cleared = cur.rowcount
        sync_files()
        return cleared


def delete_record(rec_id: str) -> None:
    """Delete a single record by id and maintain file parity."""
    conn = _conn()
    with _lock:
        with conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (rec_id,))
        sync_files()


def update_account(rec_id_or_username: str, updates: Dict[str, Any]) -> bool:
    """Safely update arbitrary fields on an account by id or username."""
    conn = _conn()
    with _lock:
        with conn:
            cur = conn.execute(
                "SELECT id FROM accounts WHERE id = ? OR username = ? OR instagram_username = ? LIMIT 1",
                (rec_id_or_username, rec_id_or_username, rec_id_or_username)
            )
            row = cur.fetchone()
            if not row:
                return False
            rec_id = row[0]

            clean_updates = {}
            for k, v in updates.items():
                if k in db.COLUMNS and k != "extra":
                    if k in ("tg_submitted", "nitro_submitted"):
                        clean_updates[k] = 1 if v else 0
                    else:
                        clean_updates[k] = v

            if clean_updates:
                set_clause = ", ".join(f"{k} = ?" for k in clean_updates.keys())
                conn.execute(f"UPDATE accounts SET {set_clause} WHERE id = ?", (*clean_updates.values(), rec_id))
        sync_files()
        return True


def clear_all() -> None:
    """Clear all accounts across database and files."""
    conn = _conn()
    with _lock:
        with conn:
            conn.execute("DELETE FROM accounts")
        sync_files()


def clear_kind(kind: str) -> int:
    """Delete only one workspace list: 'meta' (status MetaCreated) or 'ig'
    (everything else). Telegram pool rows are never touched. Returns the
    number of deleted rows."""
    conn = _conn()
    with _lock:
        with conn:
            if kind == "meta":
                cur = conn.execute(
                    "DELETE FROM accounts WHERE status = 'MetaCreated'"
                    " AND (target != 'telegram' OR target IS NULL)")
            else:
                cur = conn.execute(
                    "DELETE FROM accounts WHERE (status IS NULL OR status != 'MetaCreated')"
                    " AND (target != 'telegram' OR target IS NULL)")
            removed = cur.rowcount
        sync_files()
        return removed


def purge_damaged(kind: str = "ig") -> int:
    """Delete only DAMAGED rows in one workspace list and keep everything
    healthy. Damaged = status Failed/Banned, a dead-session note, or 3+
    failed submits (same rule as the Health column and is_damaged()).
    Telegram pool rows are never touched. Returns the deleted count."""
    conn = _conn()
    with _lock:
        with conn:
            scope = ("status = 'MetaCreated'" if kind == "meta"
                     else "(status IS NULL OR status != 'MetaCreated')")
            cur = conn.execute(
                f"DELETE FROM accounts WHERE (target != 'telegram' OR target IS NULL)"
                f" AND {scope}"
                f" AND (status IN ('Failed', 'Banned')"
                f" OR attempts >= {MAX_SUBMIT_ATTEMPTS}"
                f" OR extra LIKE 'Dead:%' OR extra LIKE '%dead_reason%')")
            removed = cur.rowcount
        sync_files()
        return removed


def remove_banned_or_failed() -> int:
    """Remove accounts with status Failed, Banned, or excessive attempts."""
    conn = _conn()
    with _lock:
        with conn:
            cur = conn.execute(
                "DELETE FROM accounts WHERE status IN ('Failed', 'Banned') OR attempts >= ?",
                (MAX_SUBMIT_ATTEMPTS,)
            )
            removed = cur.rowcount
        sync_files()
        return removed


def check_and_purge_banned() -> int:
    """Check Instagram profile endpoints for active accounts; purge any that return 404 or Suspended."""
    import urllib.error
    import urllib.request

    recs = list_all()
    purged_ids = []

    for r in recs:
        if r.get("status") in ("Failed", "Banned") or int(r.get("attempts") or 0) >= MAX_SUBMIT_ATTEMPTS:
            purged_ids.append(r["id"])
            continue
        u = r.get("username") or r.get("instagram_username")
        if not u:
            continue
        url = Urls.ig_profile(u)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        try:
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status != 200:
                purged_ids.append(r["id"])
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                purged_ids.append(r["id"])
        except Exception:
            pass

    if purged_ids:
        conn = _conn()
        with _lock:
            with conn:
                placeholders = ", ".join("?" for _ in purged_ids)
                conn.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", purged_ids)
            sync_files()

    return len(purged_ids)


def sync_files() -> None:
    """Keep accounts.json, accounts.csv and accounts.txt in sync with SQLite."""
    conn = _conn()
    cur = conn.cursor()
    # Strictly store only Meta and Instagram creator accounts (exclude telegram bot tasks)
    cur.execute("SELECT * FROM accounts WHERE target != 'telegram' OR target IS NULL ORDER BY created_at DESC, rowid DESC")
    recs = [db.dict_from_row(r) for r in cur.fetchall()]

    # 1. accounts.json (atomic write)
    try:
        os.makedirs(os.path.dirname(ACCOUNTS_JSON), exist_ok=True)
        tmp_json = f"{ACCOUNTS_JSON}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(recs, f, indent=2)
        os.replace(tmp_json, ACCOUNTS_JSON)
    except Exception:
        try:
            with open(ACCOUNTS_JSON, "w", encoding="utf-8") as f:
                json.dump(recs, f, indent=2)
        except Exception:
            pass

    # 2. accounts.csv (atomic write) — essentials: username, password, email, cookies, twofa_secret
    try:
        headers = ["username", "password", "email", "cookies", "twofa_secret"]
        import csv
        tmp_csv = f"{ACCOUNTS_CSV}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
        with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for r in recs:
                w.writerow(r)
        os.replace(tmp_csv, ACCOUNTS_CSV)
    except Exception:
        try:
            with open(ACCOUNTS_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
                w.writeheader()
                for r in recs:
                    w.writerow(r)
        except Exception:
            pass

    # 3. accounts.txt (atomic write) — format: uname|pass|email|cookie
    try:
        lines = []
        for r in recs:
            u = r.get("instagram_username") or r.get("username") or ""
            p = r.get("password") or ""
            email = r.get("email") or ""
            c = r.get("cookies") or r.get("cookie") or ""
            lines.append(f"{u}|{p}|{email}|{c}")
        content = "\n".join(lines) + "\n" if lines else ""
        tmp_txt = f"{ACCOUNTS_TXT}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_txt, ACCOUNTS_TXT)
    except Exception:
        try:
            with open(ACCOUNTS_TXT, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass


# ── Mr Follower ──────────────────────────────────────────────────────────────
# Claims accounts that still owe follows under their OWN status, 'Submitting_Follow'.
# The drains only take 'Created', so a claimed account is invisible to every other
# cycle, and `recover_stale_submitting` (LIKE 'Submitting%') already reclaims it if
# the run is killed. `followed` is the existing count column (>= 5 = "5 follows").
FOLLOW_STATUS = "Submitting_Follow"
# A failed account is left alone this long before Mr Follower retries it. Without it the
# account is the oldest again the moment it is put back and gets hammered in a tight loop.
FOLLOW_RETRY_S = int(os.environ.get("MRFOLLOW_RETRY_S", "600") or 600)


def _follow_age_sql(now: float, min_age_s: float, max_age_s: float):
    """SQL + args limiting created_at to [now-max_age, now-min_age]. NULL created_at counts as old."""
    fmt = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))  # noqa: E731
    sql, args = "", []
    if min_age_s and min_age_s > 0:
        sql += "AND (created_at IS NULL OR created_at <= ?) "
        args.append(fmt(now - float(min_age_s)))
    if max_age_s and max_age_s > 0:
        sql += "AND created_at >= ? "
        args.append(fmt(now - float(max_age_s)))
    return sql, args


def claim_for_follow(need: int = 5, max_age_s: float = 0, min_age_s: float = 0) -> Optional[Dict[str, Any]]:
    """Claim the OLDEST usable IG account with ``followed < need``.

    ``min_age_s`` > 0 leaves accounts younger than that alone (still settling after creation).
    ``max_age_s`` > 0 skips accounts created longer ago than that (IG suspends them
    after ~1h, so following them only burns requests). Returns the row, or None.
    """
    try:
        recover_stale_submitting()
    except Exception:
        pass
    conn = _conn()
    now = time.time()
    cutoff = now - _CHALLENGE_RETRY_SEC
    age_sql, age_args = _follow_age_sql(now, min_age_s, max_age_s)
    args: list = [cutoff, int(need), now - FOLLOW_RETRY_S] + age_args
    for _try in range(5):
        with _lock:
            with conn:
                row = conn.execute(
                    "SELECT id FROM accounts WHERE platform = 'Meta+Instagram' "
                    "AND cookies IS NOT NULL AND cookies != '' "
                    "AND (status = 'Created' OR status IS NULL) "
                    "AND (challenged_at IS NULL OR challenged_at < ?) "
                    "AND COALESCE(followed, 0) < ? "
                    "AND (claimed_at IS NULL OR claimed_at < ?) " + age_sql +
                    "ORDER BY created_at ASC, rowid ASC LIMIT 1", args).fetchone()
                if not row:
                    return None
                rec_id = row[0]
                # Conditional: another PROCESS (a drain) may have taken it since the SELECT.
                won = conn.execute(
                    "UPDATE accounts SET status = ?, claimed_at = ? WHERE id = ? "
                    "AND (status = 'Created' OR status IS NULL)",
                    (FOLLOW_STATUS, now, rec_id)).rowcount
                if won:
                    res = db.dict_from_row(conn.execute(
                        "SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,)).fetchone())
        if won:
            sync_files()
            return res
    return None


def count_follow_backlog(need: int = 5, max_age_s: float = 0, min_age_s: float = 0) -> Dict[str, int]:
    """Counts for the Mr Follower panel: waiting / in progress / done (>= need follows)."""
    conn = _conn()
    cutoff = time.time() - _CHALLENGE_RETRY_SEC
    age_sql, age_args = _follow_age_sql(time.time(), min_age_s, max_age_s)
    args = [int(need), cutoff, time.time() - FOLLOW_RETRY_S] + age_args
    cur = conn.cursor()
    waiting = cur.execute(
        "SELECT COUNT(*) FROM accounts WHERE platform = 'Meta+Instagram' AND cookies != '' "
        "AND (status = 'Created' OR status IS NULL) AND COALESCE(followed, 0) < ? "
        "AND (challenged_at IS NULL OR challenged_at < ?) "
        "AND (claimed_at IS NULL OR claimed_at < ?) " + age_sql, args).fetchone()[0]
    busy = cur.execute("SELECT COUNT(*) FROM accounts WHERE status = ?", (FOLLOW_STATUS,)).fetchone()[0]
    done = cur.execute(
        "SELECT COUNT(*) FROM accounts WHERE platform = 'Meta+Instagram' "
        "AND (status = 'Created' OR status IS NULL) AND COALESCE(followed, 0) >= ?",
        (int(need),)).fetchone()[0]
    return {"waiting": int(waiting or 0), "in_progress": int(busy or 0), "done": int(done or 0)}


def finish_follow(rec_id: str, followed: int, ok: bool, dead_reason: str = "",
                  progressed: bool = False) -> None:
    """Put a claimed account back in the list with its new follow count.

    ``ok`` (target reached): back to 'Created', follow count saved, claim cleared.
    Not ok: back to 'Created' with the partial count; ``claimed_at`` is stamped so the
    account rests for FOLLOW_RETRY_S before it is retried. It costs an attempt only when
    nothing was gained (``progressed`` False); after MAX_SUBMIT_ATTEMPTS such failures it
    is set to Failed. ``dead_reason`` marks the account dead.
    """
    if dead_reason:
        mark_ig_creator_dead(rec_id, dead_reason)
        return
    conn = _conn()
    with _lock:
        with conn:
            row = conn.execute("SELECT attempts FROM accounts WHERE id = ?", (rec_id,)).fetchone()
            attempts = int((row[0] if row else 0) or 0)
            if not ok and not progressed:
                attempts += 1
            status = "Failed" if attempts >= MAX_SUBMIT_ATTEMPTS else "Created"
            conn.execute(
                "UPDATE accounts SET status = ?, followed = ?, attempts = ?, claimed_at = ? WHERE id = ?",
                (status, int(followed), attempts, None if ok else time.time(), rec_id))
        sync_files()


def release_follow_claims() -> int:
    """Return every account Mr Follower holds to the list (runner start / exit / crash cleanup)."""
    conn = _conn()
    with _lock:
        with conn:
            n = conn.execute(
                "UPDATE accounts SET status = 'Created', claimed_at = NULL WHERE status = ?",
                (FOLLOW_STATUS,)).rowcount
        if n:
            sync_files()
    return int(n or 0)


def next_follow_eligible_in(need: int = 5, min_age_s: float = 0) -> Optional[int]:
    """Seconds until the next account that owes follows becomes old enough (None = none waiting)."""
    if not min_age_s or min_age_s <= 0:
        return None
    conn = _conn()
    row = conn.execute(
        "SELECT created_at FROM accounts WHERE platform = 'Meta+Instagram' AND cookies != '' "
        "AND (status = 'Created' OR status IS NULL) AND COALESCE(followed, 0) < ? "
        "AND created_at > ? ORDER BY created_at ASC LIMIT 1",
        (int(need), time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - float(min_age_s))))).fetchone()
    if not row or not row[0]:
        return None
    try:
        made = time.mktime(time.strptime(str(row[0])[:19], "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None
    return max(0, int(made + float(min_age_s) - time.time()))
