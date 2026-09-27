#!/usr/bin/env python3
"""run_monitor.py — background health monitor for a meta_creator run log.

READ-ONLY. This process never touches the run: a stall is *reported*, never
reaped, because killing Chromium drops the IG ``sessionid`` cookie and wedges
every later Accounts-Center step (AGENTS.md #17 / handoff gotchas). Point the
pipeline's stdout at ``--log`` and start this alongside it.

It parses the engine's ``__EVENT__{json}`` stdout lines and answers two
questions continuously:

  1. Is it *progressing*? (phase reached, log heartbeat, stall age)
  2. Did it *finish correctly*? (terminal success / failure / dead-end)

Minimal exit set (each code is a distinct, actionable verdict):

    0  terminal success  — ``slot_event: submitted``
    2  stall             — no log growth for ``--stall`` seconds
    3  terminal failure  — ``slot_event: error`` / strict ``held_open``
    4  dead end          — IGDeadEnd / phone-wall / dead IG session signature
    5  process vanished  — ``--pid`` gone with no terminal event
    6  timeout           — ``--max-seconds`` elapsed first

Usage:
    .venv/bin/python test/run_monitor.py --log /tmp/opencode/e2e.log --pid PID
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

# Ordered phase checklist. A phase is "hit" when a slot_event status (or the
# first matching keyword) is seen. Order matters for the progress line only —
# we never fail on a missing phase, we just report it.
PHASES = [
    ("launch", ("launching",)),
    ("meta", ("meta_verified",)),
    ("tg_task", ("bot_boot", "bot_task")),
    ("ig_onboard", ("onboarding",)),
    ("twofa", ("twofa",)),
    ("submitted", ("submitted",)),
]

# NOTE: do NOT match a bare "mobile number" — the Meta signup funnel legitimately
# logs `Selecting "Use mobile number or email"`, which is not the IG phone wall.
DEAD_END_RE = re.compile(
    r"phone wall|what'?s your mobile|mobile number required|"
    r"dead[- ]?end|ig session dead|session is dead|not salvageable|"
    r"can'?t find account.*sign ?up|bare.*profile",
    re.I,
)
FAIL_RE = re.compile(
    r"task window exceeded|did not return otp|rejected the 2fa code|"
    r"could not retrieve 2fa secret|could not reach accounts center|"
    r"no telegram profile slot available|"
    r"returned no usable credentials|returned junk display name|"
    r"could not select task",
    re.I,
)
THROTTLE_RE = re.compile(r"throttled|cooling down|mobile number required", re.I)


def load_events(path: str, pos: int):
    """Read new lines from *path* starting at byte *pos*.

    Returns (events, new_pos, grew). ``events`` is a list of (raw, parsed|None)
    for lines beginning with ``__EVENT__``. Truncation/rotation resets to 0.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], pos, False
    if size < pos:
        pos = 0  # rotated/truncated
    if size == pos:
        return [], pos, False
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(pos)
            data = fh.read()
            pos = fh.tell()
    except OSError:
        return [], pos, False
    for line in data.splitlines():
        if not line.startswith("__EVENT__"):
            continue
        raw = line[len("__EVENT__"):].strip()
        try:
            out.append((line, json.loads(raw)))
        except Exception:
            out.append((line, None))
    return out, pos, True


def main() -> int:
    ap = argparse.ArgumentParser(description="Background run-health monitor")
    ap.add_argument("--log", required=True, help="run stdout log to tail")
    ap.add_argument("--pid", type=int, default=0, help="optional pipeline PID")
    ap.add_argument("--stall", type=float, default=120.0,
                    help="report a stall after this many seconds with no new bytes")
    ap.add_argument("--max-seconds", type=float, default=0.0,
                    help="hard timeout (0 = none)")
    ap.add_argument("--heartbeat", type=float, default=20.0,
                    help="progress line interval")
    ap.add_argument("--slot", default=None, help="only track this slot_id")
    ap.add_argument("--from-start", action="store_true",
                    help="replay the whole log from byte 0 (default: only new output)")
    args = ap.parse_args()

    started = time.time()
    pos = 0
    # Default: skip pre-existing content so the monitor judges only fresh output.
    # Exception: a tiny log means we attached to a just-started run — replay from
    # 0 so the early `launching`/`meta_verified` phases aren't missed.
    if not args.from_start:
        try:
            size = os.path.getsize(args.log)
            pos = 0 if size < 65536 else size
        except OSError:
            pos = 0

    phase_hit = {name: False for name, _ in PHASES}
    last_msg = ""
    last_progress_at = time.time()
    last_beat_at = time.time()
    verdict = None
    exit_code = None
    error_msgs = []

    print(f"[[MONITOR]] watching {args.log} (pid={args.pid or '-'} stall={args.stall:.0f}s) "
          f"from byte {pos}", flush=True)

    while True:
        now = time.time()
        events, pos, grew = load_events(args.log, pos)
        if grew:
            last_progress_at = now
        for line, ev in events:
            if not isinstance(ev, dict):
                continue
            if args.slot and ev.get("type") in ("slot_event", "log", "slot_indicator") \
                    and str(ev.get("slot_id")) not in (str(args.slot), ""):
                continue
            etype = ev.get("type")
            status = ev.get("status") or ""
            detail = str(ev.get("detail") or "")
            message = str(ev.get("message") or "")

            if etype == "log" and message:
                last_msg = message
                if FAIL_RE.search(message):
                    error_msgs.append(message)
            if etype == "slot_event":
                last_msg = f"[{status}] {detail}"
                for name, keys in PHASES:
                    if status in keys:
                        if not phase_hit[name]:
                            print(f"[[MONITOR]] +{now - started:6.1f}s  phase: {name} ({status})", flush=True)
                        phase_hit[name] = True
                if status == "submitted":
                    verdict, exit_code = "SUBMITTED", 0
                elif status in ("error", "held_open"):
                    # Keep reading a moment: a strict error is followed by held_open.
                    if status == "held_open":
                        verdict, exit_code = "FAILED (browser held open)", 3
                    else:
                        verdict, exit_code = "ERROR", 3
                        if DEAD_END_RE.search(detail) or DEAD_END_RE.search(last_msg):
                            verdict, exit_code = "DEAD-END (aborted, next account)", 4
                if status == "closed" and exit_code is None:
                    verdict, exit_code = "CLOSED (no submitted event)", 3
            if etype == "loop_stopped" and exit_code is None:
                verdict, exit_code = "LOOP STOPPED (no submitted event)", 5
            # Signature-based dead-end scan on any text.
            blob = f"{detail} {message}"
            if exit_code is None and DEAD_END_RE.search(blob):
                verdict, exit_code = "DEAD-END signature detected", 4

        if exit_code is not None:
            break

        # Process liveness.
        if args.pid:
            try:
                os.kill(args.pid, 0)
            except ProcessLookupError:
                time.sleep(1.0)
                events, pos, grew = load_events(args.log, pos)  # final drain
                for _l, ev in events:
                    if isinstance(ev, dict) and ev.get("type") == "slot_event":
                        if ev.get("status") == "submitted":
                            verdict, exit_code = "SUBMITTED", 0
                        elif ev.get("status") in ("error", "held_open"):
                            verdict, exit_code = "FAILED", 3
                if exit_code is None:
                    verdict, exit_code = "PROCESS VANISHED (no terminal event)", 5
                break
            except PermissionError:
                pass

        # Stall detection.
        if args.stall and (now - last_progress_at) > args.stall:
            verdict = f"STALL (no log output for {int(now - last_progress_at)}s)"
            exit_code = 2
            break

        # Hard timeout.
        if args.max_seconds and (now - started) > args.max_seconds:
            verdict = f"TIMEOUT after {int(now - started)}s"
            exit_code = 6
            break

        # Heartbeat.
        if args.heartbeat and (now - last_beat_at) >= args.heartbeat:
            last_beat_at = now
            hit = [n for n, _ in PHASES if phase_hit[n]]
            print(f"[[MONITOR]] +{now - started:6.1f}s  idle={now - last_progress_at:5.1f}s  "
                  f"phases={hit}  last={last_msg[:90]!r}", flush=True)

        time.sleep(2.0)

    print(f"[[MONITOR]] phases seen: {[n for n, _ in PHASES if phase_hit[n]]}", flush=True)
    if error_msgs:
        print(f"[[MONITOR]] failure signatures: {error_msgs[-3:]}", flush=True)
    print(f"[[MONITOR-VERDICT]] {verdict} | exit={exit_code} | elapsed={time.time() - started:.1f}s",
          flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
