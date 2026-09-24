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

_lock = threading.Lock()
CLAIM_TIMEOUT = 600  # a Submitting claim older than this is considered stale
MAX_SUBMIT_ATTEMPTS = 3


def _read() -> List[Dict[str, Any]]:
    """Legacy helper: return all accounts as a list of dictionaries (newest first)."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY created_at DESC, rowid DESC")
    return [db.dict_from_row(r) for r in cur.fetchall()]


def _write(recs: List[Dict[str, Any]]) -> None:
    """Legacy helper: write all accounts to SQLite and sync JSON/CSV/TXT."""
    conn = db.get_connection()
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

    conn = db.get_connection()
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
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY created_at DESC, rowid DESC")
    return [db.dict_from_row(r) for r in cur.fetchall()]


get_accounts = list_all  # alias for backwards compatibility


def get(rec_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single record by its id."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = ? LIMIT 1", (rec_id,))
    row = cur.fetchone()
    return db.dict_from_row(row) if row else None


def counts() -> Dict[str, Any]:
    """Return fast aggregated account statistics in a single query."""
    conn = db.get_connection()
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
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM accounts WHERE target = 'telegram' AND status = 'Created' AND tg_submitted = 0")
    row = cur.fetchone()
    return row[0] if row else 0


def pop_pending(destination: str = "telegram") -> Optional[Dict[str, Any]]:
    """Atomically claim the oldest submittable pending account for the specified pipeline."""
    conn = db.get_connection()
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


def claim_specific(rec_id: str) -> Optional[Dict[str, Any]]:
    """Atomically claim ONE Created telegram account by id for immediate submit.

    Coupled-loop path: the worker just created this account and submits it in
    the same breath (fresh session, no queue aging). Returns None unless the
    record is still submittable (Created, not yet submitted).
    """
    conn = db.get_connection()
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
    conn = db.get_connection()
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
    conn = db.get_connection()
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
    conn = db.get_connection()
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
    """Reset records stuck in 'Submitting' back to 'Created'."""
    now = time.time()
    conn = db.get_connection()
    with _lock:
        with conn:
            cur = conn.execute(
                """
                SELECT id, attempts FROM accounts
                WHERE status IN ('Submitting', 'Submitting_Nitro', 'Submitting_Coinsta')
                  AND (claimed_at IS NULL OR (? - claimed_at) > ?)
                """,
                (now, timeout)
            )
            stale = cur.fetchall()
            if not stale:
                return 0

            for rec_id, attempts in stale:
                new_attempts = int(attempts or 0) + 1
                new_status = "Failed" if new_attempts >= MAX_SUBMIT_ATTEMPTS else "Created"
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

    conn = db.get_connection()
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
    conn = db.get_connection()
    with _lock:
        with conn:
            cur = conn.execute("DELETE FROM accounts WHERE status = 'Submitted' OR tg_submitted = 1")
            cleared = cur.rowcount
        sync_files()
        return cleared


def delete_record(rec_id: str) -> None:
    """Delete a single record by id and maintain file parity."""
    conn = db.get_connection()
    with _lock:
        with conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (rec_id,))
        sync_files()


def update_account(rec_id_or_username: str, updates: Dict[str, Any]) -> bool:
    """Safely update arbitrary fields on an account by id or username."""
    conn = db.get_connection()
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
    conn = db.get_connection()
    with _lock:
        with conn:
            conn.execute("DELETE FROM accounts")
        sync_files()


def remove_banned_or_failed() -> int:
    """Remove accounts with status Failed, Banned, or excessive attempts."""
    conn = db.get_connection()
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
        conn = db.get_connection()
        with _lock:
            with conn:
                placeholders = ", ".join("?" for _ in purged_ids)
                conn.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", purged_ids)
            sync_files()

    return len(purged_ids)


def sync_files() -> None:
    """Keep accounts.json, accounts.csv and accounts.txt in sync with SQLite."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY created_at DESC, rowid DESC")
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

    # 2. accounts.csv (atomic write) — lean Meta export: login essentials
    # only (email, password, username). No disk paths (session_file), no
    # IG dup (instagram_username), no pipeline flags (tg_*/nitro_*/coinsta_*).
    try:
        headers = ["email", "password", "username"]
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

    # 3. accounts.txt (atomic write)
    try:
        lines = []
        for r in recs:
            u = r.get("instagram_username") or r.get("username") or ""
            p = r.get("password") or ""
            sec = r.get("twofa_secret") or ""
            lines.append(f"{u}:{p}:{sec}")
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
