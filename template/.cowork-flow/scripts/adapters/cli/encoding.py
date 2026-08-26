"""CLI stream encoding setup."""

from __future__ import annotations

import io
import sys


def _configure_stream(stream: object) -> object:
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        return stream
    if hasattr(stream, "detach"):
        return io.TextIOWrapper(
            stream.detach(),  # type: ignore[union-attr]
            encoding="utf-8",
            errors="replace",
        )
    return stream


def configure_cli_encoding() -> None:
    """Configure stdio for UTF-8 when CLI scripts run on Windows."""
    if sys.platform != "win32":
        return
    sys.stdout = _configure_stream(sys.stdout)  # type: ignore[assignment]
    sys.stderr = _configure_stream(sys.stderr)  # type: ignore[assignment]
    sys.stdin = _configure_stream(sys.stdin)  # type: ignore[assignment]
