"""Configure application-level logging to a rotating file in logs/app.log."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from app.config import LOGS_DIR

_LOG_FILE: Path = LOGS_DIR / "app.log"
_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB per file
_BACKUP_COUNT: int = 3


def configure_logging(level: int = logging.INFO) -> None:
    """Set up root logger with a rotating file handler and a console handler."""
    root = logging.getLogger()
    if root.handlers:
        # Already configured — avoid duplicate handlers in tests
        return

    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Console handler (helpful during development)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    root.addHandler(ch)
