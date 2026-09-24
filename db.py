"""
meta_auto_ai — SQLite Database Engine (WAL Mode)
=================================================
High-concurrency SQLite storage backed by data/store.db.
Uses WAL (Write-Ahead Logging) for concurrent reads/writes and microsecond row updates.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from ai_config import ACCOUNTS_JSON, DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "store.db")
_local = threading.local()

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    target TEXT DEFAULT 'telegram',
    status TEXT DEFAULT 'Created',
    name TEXT,
    email TEXT,
    password TEXT,
    meta_password TEXT,
    username TEXT,
    instagram_username TEXT,
    twofa_secret TEXT,
    session_file TEXT,
    tg_account TEXT,
    tg_login TEXT,
    tg_password TEXT,
    tg_one_time_code TEXT,
    tg_submitted INTEGER DEFAULT 0,
    tg_bot TEXT,
    profile_dir TEXT,
    device_model TEXT,
    device_ua TEXT,
    nitro_device TEXT,
    nitro_submitted INTEGER DEFAULT 0,
    nitro_submitted_at TEXT,
    coinsta_device TEXT,
    coinsta_submitted INTEGER DEFAULT 0,
    coinsta_submitted_at TEXT,
    dob TEXT,
    mail_provider TEXT,
    created_at TEXT,
    claimed_at REAL,
    attempts INTEGER DEFAULT 0,
    platform TEXT,
    extra TEXT
);

CREATE INDEX IF NOT EXISTS idx_acc_target_status ON accounts(target, status);
CREATE INDEX IF NOT EXISTS idx_acc_pending_nitro ON accounts(target, status, nitro_submitted, twofa_secret);
CREATE INDEX IF NOT EXISTS idx_acc_pending_tg ON accounts(target, status, tg_submitted);
CREATE INDEX IF NOT EXISTS idx_acc_username ON accounts(username);
CREATE INDEX IF NOT EXISTS idx_acc_created_at ON accounts(created_at);
"""

COLUMNS = [
    "id", "target", "status", "name", "email", "password", "meta_password",
    "username", "instagram_username", "twofa_secret", "session_file",
    "tg_account", "tg_login", "tg_password", "tg_one_time_code", "tg_submitted", "tg_bot",
    "profile_dir", "device_model", "device_ua",
    "nitro_device", "nitro_submitted", "nitro_submitted_at",
    "coinsta_device", "coinsta_submitted", "coinsta_submitted_at",
    "dob", "mail_provider", "created_at", "claimed_at", "attempts", "platform", "extra"
]


def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection configured for high-concurrency WAL mode."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        # WAL Mode enables simultaneous non-blocking concurrent readers while a writer writes
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        _local.conn = conn
    return conn


def close_local_connection() -> None:
    """Close and drop THIS thread's cached SQLite connection.

    The connection is thread-local; the coupled loop runs each cycle in a fresh
    thread, so without an explicit close a long run can churn file descriptors
    until GC catches up. Call this at the end of a cycle thread.
    """
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        try:
            delattr(_local, "conn")
        except Exception:
            pass


def init_db() -> None:
    """Initialize SQLite database schema and migrate existing JSON accounts if present."""
    conn = get_connection()
    conn.executescript(CREATE_TABLE_SQL)

    # Safe migration: ensure tg_bot column exists for existing tables
    try:
        conn.execute("ALTER TABLE accounts ADD COLUMN tg_bot TEXT;")
    except Exception:
        pass
    for _col in ("profile_dir", "device_model", "device_ua"):
        try:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {_col} TEXT;")
        except Exception:
            pass
    # Coinsta pipeline columns (additive migration for existing store.db files)
    try:
        conn.execute("ALTER TABLE accounts ADD COLUMN coinsta_device TEXT;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE accounts ADD COLUMN coinsta_submitted INTEGER DEFAULT 0;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE accounts ADD COLUMN coinsta_submitted_at TEXT;")
    except Exception:
        pass
    # Index after the columns exist (safe on both fresh and migrated tables).
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_acc_pending_coinsta ON accounts(target, status, coinsta_submitted);")
    except Exception:
        pass

    # Check if database is empty and accounts.json has records to import
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM accounts")
    count = cur.fetchone()[0]

    if count == 0 and os.path.exists(ACCOUNTS_JSON):
        migrate_from_json(ACCOUNTS_JSON)


def dict_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert an sqlite3.Row to standard account dictionary matching legacy JSON format."""
    d = dict(row)
    # Convert integer flags back to booleans for full JSON compatibility
    d["tg_submitted"] = bool(d.get("tg_submitted"))
    d["nitro_submitted"] = bool(d.get("nitro_submitted"))
    d["coinsta_submitted"] = bool(d.get("coinsta_submitted"))
    if d.get("attempts") is not None:
        d["attempts"] = int(d["attempts"])
    if d.get("claimed_at") is not None:
        try:
            d["claimed_at"] = float(d["claimed_at"])
        except (ValueError, TypeError):
            d["claimed_at"] = None
    if d.get("extra"):
        try:
            extra = json.loads(d["extra"])
            if isinstance(extra, dict):
                for k, v in extra.items():
                    if k not in d:
                        d[k] = v
        except Exception:
            pass
    return d


def row_from_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare an account dictionary for SQLite insertion."""
    row: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}

    for k, v in d.items():
        if k in COLUMNS and k != "extra":
            if k in ("tg_submitted", "nitro_submitted", "coinsta_submitted"):
                row[k] = 1 if v else 0
            elif k == "attempts":
                row[k] = int(v) if v is not None else 0
            elif k == "claimed_at":
                row[k] = float(v) if v is not None else None
            else:
                row[k] = str(v) if v is not None else None
        else:
            if k not in COLUMNS:
                extra[k] = v

    for col in COLUMNS:
        if col not in row and col != "extra":
            if col in ("tg_submitted", "nitro_submitted", "coinsta_submitted", "attempts"):
                row[col] = 0
            else:
                row[col] = None

    row["extra"] = json.dumps(extra) if extra else None
    return row


def migrate_from_json(json_path: str = ACCOUNTS_JSON) -> int:
    """Migrate all accounts from accounts.json into SQLite store.db without data loss."""
    if not os.path.exists(json_path):
        return 0

    try:
        with open(json_path, encoding="utf-8") as f:
            records = json.load(f)
    except Exception as e:
        print(f"[db] Warning: Could not read {json_path} for migration: {e}")
        return 0

    if not isinstance(records, list) or not records:
        return 0

    conn = get_connection()
    inserted = 0

    with conn:
        for r in records:
            if not isinstance(r, dict) or not r.get("id"):
                continue
            row = row_from_dict(r)
            placeholders = ", ".join("?" for _ in COLUMNS)
            cols = ", ".join(COLUMNS)
            values = [row.get(c) for c in COLUMNS]
            conn.execute(
                f"INSERT OR REPLACE INTO accounts ({cols}) VALUES ({placeholders})",
                values
            )
            inserted += 1

    print(f"[db] Successfully migrated {inserted} accounts into SQLite store.db")
    return inserted


# Initialize on import
init_db()
