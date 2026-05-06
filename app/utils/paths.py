"""Path utilities — cross-platform safe filenames and directory helpers."""

from __future__ import annotations

import re
from pathlib import Path

from app.config import EXPORTS_DIR


# Characters not allowed in Windows file/folder names (superset covers macOS too)
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACES = re.compile(r'\s+')


def safe_filename(value: str, max_len: int = 40) -> str:
    """Return a filesystem-safe version of *value*.

    Replaces unsafe characters with underscores, collapses whitespace,
    and truncates to *max_len* characters.
    """
    value = _UNSAFE_CHARS.sub("_", value)
    value = _MULTI_SPACES.sub("_", value.strip())
    # Remove leading/trailing dots and spaces (Windows restriction)
    value = value.strip(". ")
    return value[:max_len] if value else "unnamed"


def session_folder_path(timestamp_str: str, agent_name: str, client_reference: str) -> Path:
    """Build the session folder path inside EXPORTS_DIR.

    Example: exports/session_20260505_143022_Alice_Smith_Gomez_Family
    """
    agent_safe = safe_filename(agent_name, 20)
    client_safe = safe_filename(client_reference, 20)
    folder_name = f"session_{timestamp_str}_{agent_safe}_{client_safe}"
    return EXPORTS_DIR / folder_name


def ensure_dirs(*paths: Path) -> None:
    """Create all given directories (and parents) if they don't exist."""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
