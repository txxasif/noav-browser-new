"""Cookie drain takes every usable account; the 2FA drain takes only accounts with a readable mailbox."""
import json
import os
import sqlite3
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store  # noqa: E402

FISH = json.dumps({"mail_tokens": {"mailfish_email": "a@coolember.com", "mailfish_api": True}})
MAILTD = json.dumps({"mail_tokens": {"tempmail_token": "t", "tempmail_account_id": "i"}})
NONE = json.dumps({"mail_tokens": {}})


def _db():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE accounts (id TEXT, platform TEXT, cookies TEXT, status TEXT, challenged_at REAL, "
                 "extra TEXT, created_at TEXT, claimed_at REAL, followed INTEGER DEFAULT 0)")
    c = "c" * 30
    conn.executemany("INSERT INTO accounts (id, platform, cookies, status, extra, created_at, followed) "
                     "VALUES (?,?,?,?,?,?,0)", [
                         ("fish", "Meta+Instagram", c, "Created", FISH, "2026-10-13 03:00:00"),
                         ("mailtd", "Meta+Instagram", c, "Created", MAILTD, "2026-10-13 02:00:00"),
                         ("none", "Meta+Instagram", c, "Created", NONE, "2026-10-13 01:00:00"),
                     ])
    conn.create_function("drain_ok", 1, lambda extra: 1)
    conn.create_function("mailbox_ok", 1, store._has_readable_mailbox)
    return conn


def _pop(conn, **kw):
    with mock.patch.object(store, "_conn", lambda: conn), \
            mock.patch.object(store, "recover_stale_submitting", lambda: None), \
            mock.patch.object(store, "sync_files", lambda: None):
        r = store.pop_ig_creator_account(**kw)
    return r["id"] if r else None


class MailboxGateTests(unittest.TestCase):
    def test_cookie_drain_takes_accounts_without_a_mailbox(self):
        conn = _db()
        self.assertEqual([_pop(conn) for _ in range(3)], ["fish", "mailtd", "none"])

    def test_2fa_drain_skips_accounts_without_a_readable_mailbox(self):
        conn = _db()
        got = [_pop(conn, need_mail=True) for _ in range(3)]
        self.assertEqual(got[:2], ["fish", "mailtd"])
        self.assertIsNone(got[2])                       # "none" never reaches a 2FA task
        self.assertNotIn("none", got)

    def test_counts_follow_the_same_rule(self):
        conn = _db()
        with mock.patch.object(store, "_conn", lambda: conn):
            self.assertEqual(store.count_ig_creator_accounts(), 3)
            self.assertEqual(store.count_ig_creator_accounts(need_mail=True), 2)

    def test_yamin_and_guerrilla_mailboxes_count_as_readable(self):
        self.assertEqual(store._has_readable_mailbox(json.dumps({"mail_tokens": {"yamin_email": "x@epicz.xyz"}})), 1)
        self.assertEqual(store._has_readable_mailbox(json.dumps({"mail_tokens": {"guerrilla_email": "x@g.test"}})), 1)
        self.assertEqual(store._has_readable_mailbox(json.dumps({"mail_tokens": {"tempmail_token": "t"}})), 0)


if __name__ == "__main__":
    unittest.main()
