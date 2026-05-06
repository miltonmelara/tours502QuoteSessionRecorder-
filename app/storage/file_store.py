"""File-system store: creates and manages the session folder and sub-directories."""

from __future__ import annotations

import logging
from pathlib import Path

from app.utils.paths import ensure_dirs

logger = logging.getLogger(__name__)


class FileStore:
    """Manages the on-disk layout of a single recording session.

    Folder layout::

        exports/session_<ts>_<agent>_<client>/
            screenshots/
            snapshots/
            final_quote/
    """

    def __init__(self, session_folder: Path) -> None:
        self.session_folder: Path = session_folder
        self.screenshots_dir: Path = session_folder / "screenshots"
        self.snapshots_dir: Path = session_folder / "snapshots"
        self.final_quote_dir: Path = session_folder / "final_quote"
        self._screenshot_counter: int = 0

    def initialise(self) -> None:
        """Create all required sub-directories."""
        ensure_dirs(
            self.session_folder,
            self.screenshots_dir,
            self.snapshots_dir,
            self.final_quote_dir,
        )
        logger.info("Session folder initialised: %s", self.session_folder)

    def next_screenshot_path(self, label: str = "screenshot") -> Path:
        """Return the next numbered screenshot file path (not yet written).

        Example: screenshots/003_note_option_rejected.png
        """
        self._screenshot_counter += 1
        from app.utils.paths import safe_filename
        safe_label = safe_filename(label, max_len=40)
        filename = f"{self._screenshot_counter:03d}_{safe_label}.png"
        return self.screenshots_dir / filename

    def next_snapshot_path(self, label: str = "snapshot") -> Path:
        """Return the next snapshot file path (text)."""
        from app.utils.paths import safe_filename
        safe_label = safe_filename(label, max_len=40)
        filename = f"{self._screenshot_counter:03d}_{safe_label}.txt"
        return self.snapshots_dir / filename

    @property
    def screenshot_count(self) -> int:
        return self._screenshot_counter
