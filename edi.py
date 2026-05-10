"""
Backward-compatibility shim — imports everything from ``formats.edi``.

New code should import directly from ``formats.edi``::

    from formats.edi import Log, LogQso, Operator, ...
"""
# flake8: noqa — all names are re-exported for backward compat
from formats.edi import *  # noqa: F401, F403
