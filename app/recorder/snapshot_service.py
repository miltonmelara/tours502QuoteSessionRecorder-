"""Text-based page snapshot service (MVP — no HTML snapshots)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

from app.storage.file_store import FileStore
from app.utils.time_utils import now_iso

logger = logging.getLogger(__name__)


class SnapshotService:
    """Saves visible text snapshots of the current page."""

    def __init__(self, file_store: FileStore) -> None:
        self._file_store = file_store

    def take_text_snapshot(self, page: "Page", label: str = "snapshot") -> Path | None:
        """Extract visible text from the page and save as a .txt file.

        Returns the path to the saved file, or ``None`` on failure.
        """
        path = self._file_store.next_snapshot_path(label)
        try:
            url = page.url
            title = page.title()
            # Extract inner text from <body> — simple and cross-browser safe
            body_text: str = page.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
            content = (
                f"URL: {url}\n"
                f"Title: {title}\n"
                f"Timestamp: {now_iso()}\n"
                f"{'=' * 60}\n"
                f"{body_text}\n"
            )
            path.write_text(content, encoding="utf-8")
            logger.debug("Text snapshot saved: %s", path.name)
            return path
        except Exception:
            logger.warning("Text snapshot failed for label=%r", label, exc_info=True)
            return None
