#!/usr/bin/env python3
"""tg_manager_cli.py — dashboard <-> tg.manager bridge (prints ONE JSON line).

    python tg_manager_cli.py --mode summary
    python tg_manager_cli.py --mode balance
"""
from __future__ import annotations

import argparse
import json
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

import tg.manager as M  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="TG manager bridge")
    ap.add_argument("--mode", required=True, choices=("summary", "balance", "bots"))
    args = ap.parse_args()
    if args.mode == "summary":
        print(json.dumps(M.summary()))
    elif args.mode == "bots":
        print(json.dumps({"ok": True, "bots": M.bots()}))
    else:
        print(json.dumps(M.run_balance()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
