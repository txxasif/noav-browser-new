from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from .helpers import IgHelpersMixin
from .login import IgLoginMixin
from .join import IgJoinMixin
from .password import IgPasswordMixin
from .twofa import IgTwofaMixin
from .identity import IgIdentityMixin

__all__ = [
    "IgHelpersMixin",
    "IgLoginMixin",
    "IgJoinMixin",
    "IgPasswordMixin",
    "IgTwofaMixin",
    "IgIdentityMixin",
    "InstagramFlowMixin",
]


class InstagramFlowMixin(
    IgHelpersMixin,
    IgLoginMixin,
    IgJoinMixin,
    IgPasswordMixin,
    IgTwofaMixin,
    IgIdentityMixin,
):
    """Accounts-Center + Instagram-web actions for MetaInstaRunner (mixin combo)."""
