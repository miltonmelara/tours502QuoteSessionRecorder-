"""Timestamp utilities."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Return current UTC time as an ISO 8601 string with timezone info."""
    return datetime.now(tz=timezone.utc).isoformat()


def session_timestamp() -> str:
    """Return a compact timestamp string suitable for folder/file names.

    Example: 20260505_143022
    """
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
