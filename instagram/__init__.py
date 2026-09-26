from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from .helpers import IgHelpersMixin
from .login import IgLoginMixin
from .join import IgJoinMixin
from .ac_reauth import IgAcReauthMixin
from .ac_nav import IgAcNavMixin
from .password import IgPasswordMixin
from .twofa import IgTwofaMixin
from .identity import IgIdentityMixin

__all__ = [
    "IgHelpersMixin",
    "IgLoginMixin",
    "IgJoinMixin",
    "IgAcReauthMixin",
    "IgAcNavMixin",
    "IgPasswordMixin",
    "IgTwofaMixin",
    "IgIdentityMixin",
    "InstagramFlowMixin",
]


class InstagramFlowMixin(
    IgHelpersMixin,
    IgLoginMixin,
    IgJoinMixin,
    # AC re-auth BEFORE navigation: both call each other, and keeping re-auth
    # first means its guards are the ones a navigation pass hits first.
    IgAcReauthMixin,
    IgAcNavMixin,
    IgPasswordMixin,
    IgTwofaMixin,
    IgIdentityMixin,
):
    """Accounts-Center + Instagram-web actions for MetaInstaRunner (mixin combo)."""
