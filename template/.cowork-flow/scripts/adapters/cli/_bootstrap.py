"""Allow CLI adapter scripts to import the scripts package when run directly."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from adapters.cli.encoding import configure_cli_encoding

configure_cli_encoding()
