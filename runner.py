"""
meta_auto_ai — MetaInstaRunner (thin re-export shim).

The implementation now lives in the :mod:`core` package. This module is kept
so existing imports keep working::

    from runner import MetaInstaRunner
"""
from __future__ import annotations

from core import MetaInstaRunner  # noqa: F401

__all__ = ["MetaInstaRunner"]
