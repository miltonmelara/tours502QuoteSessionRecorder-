"""Screenshot capture service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

from app.storage.file_store import FileStore

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Takes and saves screenshots from the Playwright page."""

    def __init__(self, file_store: FileStore) -> None:
        self._file_store = file_store

    def take_screenshot(self, page: "Page", label: str = "screenshot") -> Path | None:
        """Capture a full-page screenshot and return its path.

        Returns ``None`` if the screenshot fails (e.g. page is closed).
        """
        path = self._file_store.next_screenshot_path(label)
        try:
            # During shutdown/navigation races, page may already be closed.
            if page.is_closed():
                logger.debug("Skipping screenshot for closed page: label=%r", label)
                return None
            page.screenshot(path=str(path), full_page=True, timeout=8_000)
            logger.debug("Screenshot saved: %s", path.name)
            return path
        except Exception as exc:
            # TargetClosedError and similar close-race failures are expected while
            # browser/page is shutting down; keep logs clean by downgrading to debug.
            msg = str(exc)
            if "Target page, context or browser has been closed" in msg:
                logger.debug("Skipping screenshot during page/browser close: label=%r", label)
                return None
            logger.warning("Screenshot failed for label=%r", label, exc_info=True)
            return None
