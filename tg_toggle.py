#!/usr/bin/env python3
"""tg_toggle.py - enable/disable or remove a pooled Telegram profile.

The dashboard calls this instead of importing tg_accounts directly, so the
session/profile mutation happens in a short-lived process with the lock, never
inside the long-running Node server.

  tg_toggle.py --id tg_1 --enabled 1     # enable
  tg_toggle.py --id tg_1 --enabled 0     # disable (acquire() will skip it)
  tg_toggle.py --id tg_1 --remove        # delete profile + dir
  tg_toggle.py --all 1                   # enable/disable every profile
Prints ONE JSON line ({"ok":bool,...}) so the caller can relay it.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=None)
    ap.add_argument("--enabled", default=None, help="1/0")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--all", default=None, help="1/0 for every profile")
    a = ap.parse_args()

    from tg_accounts import tg_manager
    try:
        if a.all is not None:
            want = str(a.all).strip().lower() not in ("0", "false", "no", "")
            n = 0
            for rec in list(tg_manager.list(refresh=False)):
                try:
                    tg_manager.set_enabled(rec.get("id"), want)
                    n += 1
                except Exception:
                    pass  # busy profiles are skipped, not fatal
            return {"ok": True, "updated": n, "enabled": want}

        if not a.id:
            return {"ok": False, "error": "id required (or --all)"}

        if a.remove:
            tg_manager.remove(a.id)
            return {"ok": True, "removed": a.id}

        if a.enabled is None:
            return {"ok": False, "error": "nothing to do (--enabled or --remove)"}
        want = str(a.enabled).strip().lower() not in ("0", "false", "no", "")
        val = tg_manager.set_enabled(a.id, want)
        return {"ok": True, "id": a.id, "enabled": bool(val)}
    except KeyError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    print(json.dumps(main()))
