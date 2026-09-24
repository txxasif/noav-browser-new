"""Thin re-export shim (Nova-parity refactor).

InstagramFlowMixin now lives in the :mod:`instagram` package as a mixin
combo (helpers/login/join/password/twofa/identity). This module remains so
``from ig_flow import InstagramFlowMixin`` keeps working for runner.py and
meta_worker_ai.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from instagram import InstagramFlowMixin  # noqa: E402,F401

__all__ = ["InstagramFlowMixin"]
