"""
meta_auto_ai — MetaInstaRunner (thin re-export shim).

The implementation now lives in the :mod:`core` package (verbatim slices,
no logic change). This module is kept so existing imports keep working::

    from runner import MetaInstaRunner, TempMailFishProvider
"""
from __future__ import annotations

from core import MetaInstaRunner, TempMailFishProvider  # noqa: F401

__all__ = ["MetaInstaRunner", "TempMailFishProvider"]
