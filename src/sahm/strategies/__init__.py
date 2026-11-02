"""Strategy library: built-in technical strategies plus your own files.

Write your own with the `strategy` decorator and `Param`, and use `indicators`
for the maths. See STRATEGIES.md at the project root.
"""

from . import indicators
from .base import LOAD_ERRORS, REGISTRY, Param, Strategy, closes, enter_exit, get, hold_while, strategy

_loaded = False


def load_all() -> None:
    """Register the built-in library, then user strategy files. Safe to call twice."""
    global _loaded
    if _loaded:
        return
    from . import library  # noqa: F401  (registers built-ins on import)
    from .loader import load_user_strategies

    load_user_strategies()
    _loaded = True


__all__ = [
    "LOAD_ERRORS", "REGISTRY", "Param", "Strategy", "closes", "enter_exit", "get",
    "hold_while", "indicators", "load_all", "strategy",
]
