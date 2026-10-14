"""A reply left behind by an abandoned call must never be read as the next call's answer."""
import os
import queue
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mtproto_bot  # noqa: E402,F401  (import order: breaks the pool<->bot cycle)
from mtproto_pool import MtprotoPooledBot  # noqa: E402
from mtproto_bot import _stock_counter, _is_conversation_reset  # noqa: E402


class StockTests(unittest.TestCase):
    def test_counter(self):
        self.assertEqual(_stock_counter("⚡️ Available this hour: 2333/3500"), 2333)
        self.assertEqual(_stock_counter("Available this hour: 0/3500"), 0)
        self.assertIsNone(_stock_counter("hello"))

    def test_reset_marker(self):
        self.assertTrue(_is_conversation_reset("ℹ️ Our previous conversation was reset, please start again from the main menu."))


class ReplyMatchTests(unittest.TestCase):
    def test_stale_reply_is_skipped(self):
        q_in, q_out = queue.Queue(), queue.Queue()
        q_out.put((True, "ok", 0))                      # orphan from an earlier call
        ent = {"thread": threading.current_thread(), "q_in": q_in, "q_out": q_out, "last_used": 0}
        bot = MtprotoPooledBot.__new__(MtprotoPooledBot)
        bot._key, bot.session_path, bot.tg_id, bot.bot_target, bot.log = "k", "k", "tg_x", "paygo", print
        MtprotoPooledBot._pool["k"] = ent

        def owner():
            cmd, _t, _a, _k, rid = q_in.get()
            q_out.put((True, {"login": "abc"}, rid))
        threading.Thread(target=owner, daemon=True).start()
        try:
            self.assertEqual(bot._call("start_task"), {"login": "abc"})
        finally:
            MtprotoPooledBot._pool.pop("k", None)


if __name__ == "__main__":
    unittest.main()
