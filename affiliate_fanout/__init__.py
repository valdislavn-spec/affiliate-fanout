"""Affiliate fan-out: publish affiliate links to free social APIs.

Public helpers are re-exported for library use::

    from affiliate_fanout import load_env, TravelpayoutsLinks, compose_text
"""

from __future__ import annotations

__version__ = "0.1.0"

from .env import load_env  # noqa: F401
from .links import LinkTracker, TravelpayoutsLinks  # noqa: F401
from .cli import compose_text, main, run_publish, run_verify  # noqa: F401

__all__ = [
    "__version__",
    "load_env",
    "TravelpayoutsLinks",
    "LinkTracker",
    "compose_text",
    "run_publish",
    "run_verify",
    "main",
]
