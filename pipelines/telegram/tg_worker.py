"""
pipelines/telegram/tg_worker.py — Telegram Taskly pipeline (facade)
====================================================================
Thin re-export shim. The implementation was split out of this single
1488-line file on 2026-09-25; every public name is re-exported here so the
existing callers keep working unchanged:

* ``worker.py`` → ``tg_worker.run_tg_create_cycle`` / ``run_tg_submit_one`` /
  ``run_tg_coupled_cycle``
* ``mem_guard.py`` → ``tg_worker.close_inspectors``
* ``core/lifecycle.py`` → ``from pipelines.telegram.tg_worker import _sanitize_name``

Modules
-------
* :mod:`pipelines.telegram.tg_support` — bot factory, name/username hygiene,
  ``_boot_bot``, the bounded inspector registry (invariant #26), wedged-browser
  reaping, cancel-with-timeout.
* :mod:`pipelines.telegram.tg_cycles` — the two decoupled cycles
  (``run_tg_create_cycle`` Phase 1, ``run_tg_submit_one`` Phase 2).
* :mod:`pipelines.telegram.tg_coupled` — ``run_tg_coupled_cycle``, the
  ONE-browser Meta → TG → IG → submit orchestrator (classic + TG-Emu phases).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from pipelines.telegram.tg_support import (  # noqa: E402,F401
    _DEAD_ENDS,
    _INSPECT_CAP,
    _INSPECT_KEEP_VISIBLE,
    # Registry internals are re-exported on purpose: they are MUTABLE objects
    # (a list + a Lock), so re-export preserves identity and a caller/test that
    # does `tw._open_inspectors[:] = reps` mutates the very list
    # `close_inspectors` drains. Do not rebind them here.
    _inspect_lock,
    _open_inspectors,
    _boot_bot,
    _cancel_with_timeout,
    _clean_username,
    _drop_tg_bot,
    _force_close,
    _ig_name_too_long,
    _inspector_keeps,
    _is_junk_name,
    _is_tg_session_lost,
    _is_valid_ig_username,
    _make_tg_bot,
    _random_display_name,
    _reap_wedged_tg_browser,
    _register_inspector,
    _sanitize_name,
    close_inspectors,
    IGDeadEnd,
)
from pipelines.telegram.tg_cycles import (  # noqa: E402,F401
    run_tg_create_cycle,
    run_tg_submit_one,
)
from pipelines.telegram.tg_coupled import run_tg_coupled_cycle  # noqa: E402,F401

__all__ = [
    "run_tg_create_cycle",
    "run_tg_submit_one",
    "run_tg_coupled_cycle",
    "close_inspectors",
]
