"""Test package for module-style unittest invocation.

Importing this package also redirects Python bytecode away from the shipped
trees. Both runners import it before any test module — pytest imports the
package for its modules, unittest imports it for ``tests.test_*`` — so the
guard covers ``python -m pytest``, ``python -m unittest``, and the ``python``
children they spawn. Without it, importing modules from ``template/`` writes
``__pycache__`` next to shipped sources, and the delivery filters are
blacklist-shaped: one filter edit away from reaching user projects.

There is deliberately no ``tests/conftest.py``: a conftest reaches pytest only,
which would leave direct unittest runs unprotected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_PREFIX = ROOT / ".tmp" / "pycache"

if not os.environ.get("PYTHONPYCACHEPREFIX"):
    CACHE_PREFIX.mkdir(parents=True, exist_ok=True)
    os.environ["PYTHONPYCACHEPREFIX"] = str(CACHE_PREFIX)
if not sys.pycache_prefix:
    CACHE_PREFIX.mkdir(parents=True, exist_ok=True)
    sys.pycache_prefix = str(CACHE_PREFIX)
