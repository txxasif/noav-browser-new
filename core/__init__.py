"""meta_auto_ai — core package.

Composes :class:`MetaInstaRunner` from verbatim mixins sliced out of the
former monolithic ``runner.py`` (no logic change):

* :mod:`core.mailbox` — mail.td browser inbox and OTP fetcher.
* :mod:`core.base` — init + anti-detect launch + React event dispatch.
* :mod:`core.captcha` — ordered captcha solvers + Meta verification.
* :mod:`core.signup` — Meta signup + screenshot telemetry hooks.
* :mod:`core.lifecycle` — two-phase lifecycles + ledger export.

MRO note: ``InstagramFlowMixin`` + ``run._MetaInstagramRunner`` stay last
so ``super()`` calls in the mixins resolve to the bundled engine, exactly
as before. Same browser session invariant is unchanged.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_config import run  # noqa: E402
from ig_flow import InstagramFlowMixin  # noqa: E402

from .license_mgr import LicenseManager  # noqa: E402
from .base import MetaBaseMixin  # noqa: E402
from .captcha import CaptchaMixin  # noqa: E402
from .lifecycle import LifecycleMixin  # noqa: E402
from .mailbox import MailboxMixin  # noqa: E402
from .signup import SignupMixin  # noqa: E402


class MetaInstaRunner(
    LifecycleMixin,
    MailboxMixin,
    SignupMixin,
    CaptchaMixin,
    MetaBaseMixin,
    InstagramFlowMixin,
    run._MetaInstagramRunner,
):
    """Meta signup + Instagram login/link/join in the same browser session."""


__all__ = ["MetaInstaRunner", "LicenseManager"]
