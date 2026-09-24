"""Small cross-thread runtime helpers for browser resource management.

The worker uses one Python process with several slot threads.  Keeping the
active-profile registry here avoids racing profile pruning when many slots
start at once, and the throttle prevents every slot from doing the same
filesystem/database scan during a burst.
"""
from __future__ import annotations

import os
import threading
import time
from typing import FrozenSet

_ACTIVE_PROFILES: set[str] = set()
_ACTIVE_PROFILES_LOCK = threading.RLock()
_PRUNE_LOCK = threading.Lock()
_LAST_PRUNE: dict[str, float] = {}


def _normalise(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def register_profile(path: str | os.PathLike[str] | None) -> None:
    """Mark a profile as owned by a live slot in this worker process."""
    if not path:
        return
    with _ACTIVE_PROFILES_LOCK:
        _ACTIVE_PROFILES.add(_normalise(path))


def unregister_profile(path: str | os.PathLike[str] | None) -> None:
    """Release a profile after its context/browser has been closed."""
    if not path:
        return
    with _ACTIVE_PROFILES_LOCK:
        _ACTIVE_PROFILES.discard(_normalise(path))


def active_profiles() -> FrozenSet[str]:
    """Return a stable snapshot of profiles currently owned by live slots."""
    with _ACTIVE_PROFILES_LOCK:
        return frozenset(_ACTIVE_PROFILES)


def should_prune(key: str, interval_seconds: float) -> bool:
    """Return True for one caller, while throttling duplicate scans.

    A non-positive interval disables throttling.  The timestamp is updated
    before the scan starts, so a failed scan cannot cause a thundering herd
    on the next slot launch.
    """
    try:
        interval = max(0.0, float(interval_seconds))
    except (TypeError, ValueError):
        interval = 30.0
    if interval <= 0:
        return True
    now = time.monotonic()
    with _PRUNE_LOCK:
        if now - _LAST_PRUNE.get(key, 0.0) < interval:
            return False
        _LAST_PRUNE[key] = now
    return True
